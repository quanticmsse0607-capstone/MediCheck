"""
ingest.py
RAG Knowledge Base Ingestion Pipeline

Loads all source documents from data/raw/, chunks them, generates embeddings
via OpenAI text-embedding-3-small, and persists the ChromaDB vector store to
data/chroma_db/.

Source documents:
    PDFs  — loaded with PyPDFLoader, split with RecursiveCharacterTextSplitter
    HTML  — loaded with BSHTMLLoader, split with RecursiveCharacterTextSplitter

Chunking strategy:
    - ICD-10-CM guidelines: heading-aware splitting (Section/Chapter headings
      used as natural split points before falling back to token window)
    - NSA PDFs: paragraph-based splitting within 500-token window
    - HTML files: paragraph-based splitting within 500-token window
    - All chunks: 500 tokens, 50-token overlap, per Trello Story 2 AC

Metadata per chunk:
    source, document_title, section, page_number

Usage:
    python ingest.py                        # uses defaults
    python ingest.py --raw  data/raw        # override raw dir
    python ingest.py --db   data/chroma_db  # override vector store path
    python ingest.py --reset                # wipe and rebuild from scratch

Requirements:
    OPENAI_API_KEY must be set in .env or environment before running.
"""

import argparse
import logging
import os
import re
import sys
from pathlib import Path

from bs4 import BeautifulSoup
from dotenv import load_dotenv
from langchain.schema import Document
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.document_loaders import BSHTMLLoader, PyPDFLoader
from langchain_community.vectorstores import Chroma
from langchain_openai import OpenAIEmbeddings

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)s  %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

# ── Constants ─────────────────────────────────────────────────────────────────

CHUNK_SIZE    = 500   # tokens (approximate — splitter uses chars internally)
CHUNK_OVERLAP = 50
EMBEDDING_MODEL = "text-embedding-3-small"
COLLECTION_NAME = "medicheck_kb"

# Map each filename to a clean document title for metadata
DOCUMENT_TITLES = {
    "icd_10_cm_october_2025_guidelines_0.pdf": "ICD-10-CM Official Guidelines for Coding and Reporting FY2026",
    "nsa-at-a-glance.pdf":                     "No Surprises Act at a Glance",
    "nsa-helping-consumers.pdf":               "Helping Consumers Protect Their Rights Under the No Surprises Act",
    "nsa-keyprotections_1.pdf":                "No Surprises Act: Overview of Key Consumer Protections",
    "surprise-billing-requirements-final-rules-fact-sheet.pdf":
                                               "Requirements Related to Surprise Billing: Final Rules Fact Sheet",
    "What_You_Need_to_Know_about_the_Biden-Harris_Administration_s_Actions_to_Prevent_Surprise_Billing___CMS.html":
                                               "What You Need to Know: Actions to Prevent Surprise Billing (July 2021)",
    "What_You_Need_to_Know_about_the_Biden-Harris_Administration_s_Actions_to_Prevent_Surprise_Billing-September2021.html":
                                               "What You Need to Know: Actions to Prevent Surprise Billing (September 2021)",
}

# ICD-10 heading patterns — used to detect natural section boundaries
ICD10_HEADING_PATTERNS = [
    r"^Section\s+[IVX]+\.",
    r"^[A-Z]\.\s+[A-Z]",
    r"^Chapter\s+\d+",
]


# ── Loaders ───────────────────────────────────────────────────────────────────

def load_pdf(filepath: Path) -> list[Document]:
    """Load a PDF using PyPDFLoader. Returns one Document per page."""
    logger.info(f"  Loading PDF: {filepath.name}")
    loader = PyPDFLoader(str(filepath))
    pages = loader.load()
    # Inject source filename into metadata for traceability
    for page in pages:
        page.metadata["source"] = filepath.name
        page.metadata["document_title"] = DOCUMENT_TITLES.get(filepath.name, filepath.stem)
    logger.info(f"    {len(pages)} pages loaded")
    return pages


def load_html(filepath: Path) -> list[Document]:
    """
    Load an HTML file using BSHTMLLoader.
    Strips navigation, header, footer, and script elements before extraction
    to avoid embedding boilerplate CMS website chrome.
    """
    logger.info(f"  Loading HTML: {filepath.name}")

    with open(filepath, encoding="utf-8", errors="ignore") as f:
        raw_html = f.read()

    soup = BeautifulSoup(raw_html, "lxml")

    # Remove boilerplate elements
    for tag in soup(["script", "style", "nav", "footer", "header",
                     "noscript", "iframe", "form"]):
        tag.decompose()

    # Also remove CMS site navigation divs by common class patterns
    for tag in soup.find_all(class_=re.compile(r"nav|menu|sidebar|breadcrumb|footer|header", re.I)):
        tag.decompose()

    text = soup.get_text(separator="\n", strip=True)

    # Remove excessive blank lines
    text = re.sub(r"\n{3,}", "\n\n", text)

    doc = Document(
        page_content=text,
        metadata={
            "source": filepath.name,
            "document_title": DOCUMENT_TITLES.get(filepath.name, filepath.stem),
            "page_number": 1,
        }
    )
    logger.info(f"    {len(text.split())} words extracted")
    return [doc]


# ── Chunking ──────────────────────────────────────────────────────────────────

def make_splitter(chunk_size: int = CHUNK_SIZE,
                  chunk_overlap: int = CHUNK_OVERLAP) -> RecursiveCharacterTextSplitter:
    """
    RecursiveCharacterTextSplitter with separators ordered from coarse to fine.
    Tries to split on double newlines (paragraphs) first, then single newlines,
    then sentences, then words. This preserves semantic coherence.

    chunk_size uses characters not tokens — 500 tokens ≈ 2000 characters
    for typical English prose at ~4 chars/token.
    """
    return RecursiveCharacterTextSplitter(
        chunk_size=chunk_size * 4,      # ~4 chars per token
        chunk_overlap=chunk_overlap * 4,
        separators=["\n\n", "\n", ". ", " ", ""],
        length_function=len,
    )


def split_icd10(pages: list[Document]) -> list[Document]:
    """
    ICD-10 specific splitting strategy.

    The ICD-10 guidelines have a clear Section/Chapter heading hierarchy.
    We first join all page text, then split on major section headings to
    create large semantic units, then apply the standard token-window
    splitter within each unit. This keeps section content together and
    produces cleaner retrieval results.
    """
    heading_re = re.compile(
        r"(Section\s+[IVX]+\.|^[A-Z]\.\s+[A-Z][a-z]|^Chapter\s+\d+)",
        re.MULTILINE
    )

    splitter = make_splitter()
    chunks = []

    current_section = "Introduction"
    current_text = ""
    current_page = 1

    for page in pages:
        text = page.page_content
        page_num = page.metadata.get("page", 1)

        # Detect if this page starts a new major section
        match = heading_re.search(text)
        if match:
            # Flush current section buffer
            if current_text.strip():
                section_chunks = splitter.create_documents(
                    [current_text],
                    metadatas=[{
                        "source": page.metadata["source"],
                        "document_title": page.metadata["document_title"],
                        "section": current_section,
                        "page_number": current_page,
                    }]
                )
                chunks.extend(section_chunks)

            current_section = match.group(0).strip()
            current_text = text
            current_page = page_num
        else:
            current_text += "\n" + text

    # Flush final section
    if current_text.strip():
        section_chunks = splitter.create_documents(
            [current_text],
            metadatas=[{
                "source": pages[0].metadata["source"],
                "document_title": pages[0].metadata["document_title"],
                "section": current_section,
                "page_number": current_page,
            }]
        )
        chunks.extend(section_chunks)

    return chunks


def split_standard(docs: list[Document], section_hint: str = "") -> list[Document]:
    """
    Standard paragraph-based splitting for NSA PDFs and HTML files.
    Applies RecursiveCharacterTextSplitter across all pages/documents,
    preserving source and page metadata on each chunk.
    """
    splitter = make_splitter()
    chunks = []

    for doc in docs:
        page_chunks = splitter.create_documents(
            [doc.page_content],
            metadatas=[{
                "source": doc.metadata.get("source", ""),
                "document_title": doc.metadata.get("document_title", ""),
                "section": section_hint or _infer_section(doc.page_content),
                "page_number": doc.metadata.get("page", doc.metadata.get("page_number", 1)),
            }]
        )
        chunks.extend(page_chunks)

    return chunks


def _infer_section(text: str) -> str:
    """
    Extract a section label from the first meaningful line of a chunk.
    Used for NSA documents where headings appear inline in the text.
    Falls back to empty string if no clear heading is found.
    """
    lines = [l.strip() for l in text.splitlines() if len(l.strip()) > 10]
    if not lines:
        return ""
    first = lines[0]
    # Use as section label only if it looks like a heading (short, no period mid-line)
    if len(first) < 80 and not re.search(r"\.\s+[a-z]", first):
        return first[:80]
    return ""


# ── Ingestion pipeline ────────────────────────────────────────────────────────

def load_and_chunk_all(raw_dir: Path) -> list[Document]:
    """
    Load all source documents from raw_dir and chunk them.
    Returns a flat list of Document chunks ready for embedding.
    """
    all_chunks = []

    # Define processing order — ICD-10 first (largest, most chunks)
    pdf_files = [f for f in sorted(raw_dir.glob("*.pdf"))
                 if f.name in DOCUMENT_TITLES]
    html_files = [f for f in sorted(raw_dir.glob("*.html"))
                  if f.name in DOCUMENT_TITLES]

    logger.info(f"Found {len(pdf_files)} PDFs and {len(html_files)} HTML files to ingest")

    for pdf_path in pdf_files:
        pages = load_pdf(pdf_path)
        if not pages:
            logger.warning(f"  No pages extracted from {pdf_path.name} — skipping")
            continue

        if "icd_10" in pdf_path.name:
            chunks = split_icd10(pages)
        else:
            chunks = split_standard(pages)

        logger.info(f"  → {len(chunks)} chunks from {pdf_path.name}")
        all_chunks.extend(chunks)

    for html_path in html_files:
        docs = load_html(html_path)
        chunks = split_standard(docs)
        logger.info(f"  → {len(chunks)} chunks from {html_path.name}")
        all_chunks.extend(chunks)

    return all_chunks


def build_vector_store(
    chunks: list[Document],
    db_path: Path,
    reset: bool = False,
    batch_size: int = 50,
    batch_delay: float = 8.0,
) -> Chroma:
    """
    Embed all chunks in batches and persist to ChromaDB.

    Batching is required because text-embedding-3-small has a 40,000 TPM
    limit on free/tier-1 accounts. At ~500 tokens per chunk, batch_size=50
    yields ~25,000 tokens per batch — safely under the limit. A delay between
    batches allows the token window to reset.

    Args:
        chunks:      List of Document chunks to embed
        db_path:     Path for ChromaDB persistent storage
        reset:       If True, wipe existing store before ingesting
        batch_size:  Number of chunks per embedding batch (default: 50)
        batch_delay: Seconds to wait between batches (default: 8.0)

    Returns:
        Populated Chroma vector store
    """
    import math
    import time
    import shutil

    if reset and db_path.exists():
        shutil.rmtree(db_path)
        logger.info(f"Wiped existing vector store at {db_path}")

    db_path.mkdir(parents=True, exist_ok=True)

    embeddings = OpenAIEmbeddings(model=EMBEDDING_MODEL)

    total_batches = math.ceil(len(chunks) / batch_size)
    logger.info(
        f"Embedding {len(chunks)} chunks in {total_batches} batches "
        f"of {batch_size} ({batch_delay}s delay between batches)..."
    )
    logger.info("This will make OpenAI API calls — ensure OPENAI_API_KEY is set.")

    vector_store = None

    for i in range(0, len(chunks), batch_size):
        batch = chunks[i : i + batch_size]
        batch_num = (i // batch_size) + 1
        logger.info(f"  Batch {batch_num}/{total_batches} — {len(batch)} chunks...")

        if vector_store is None:
            # First batch — create the collection
            vector_store = Chroma.from_documents(
                documents=batch,
                embedding=embeddings,
                collection_name=COLLECTION_NAME,
                persist_directory=str(db_path),
            )
        else:
            # Subsequent batches — add to existing collection
            vector_store.add_documents(batch)

        # Persist after each batch so progress isn't lost on failure
        vector_store.persist()

        # Wait between batches to respect TPM limit (skip after last batch)
        if i + batch_size < len(chunks):
            logger.info(f"  Waiting {batch_delay}s before next batch...")
            time.sleep(batch_delay)

    logger.info(f"Vector store persisted to {db_path}")
    return vector_store


def verify_vector_store(vector_store: Chroma) -> None:
    """
    Run a quick smoke test against the vector store to verify retrieval works.
    Tests two queries — one NSA-related, one ICD-10-related.
    """
    logger.info("Running smoke tests...")

    test_queries = [
        "What is balance billing under the No Surprises Act?",
        "What are the ICD-10 coding guidelines for emergency services?",
    ]

    for query in test_queries:
        results = vector_store.similarity_search(query, k=3)
        if results:
            logger.info(
                f"  Query: '{query[:50]}...'\n"
                f"    Top result: {results[0].metadata.get('document_title', 'unknown')} "
                f"(section: {results[0].metadata.get('section', 'n/a')[:40]})"
            )
        else:
            logger.warning(f"  No results for: {query}")


# ── CLI entrypoint ────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Build MediCheck RAG knowledge base from source documents."
    )
    parser.add_argument(
        "--raw",
        default="data/raw",
        help="Directory containing source PDFs and HTML files (default: data/raw)",
    )
    parser.add_argument(
        "--db",
        default="data/chroma_db",
        help="Output path for ChromaDB vector store (default: data/chroma_db)",
    )
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Wipe existing vector store before rebuilding",
    )
    args = parser.parse_args()

    # Validate environment
    if not os.getenv("OPENAI_API_KEY"):
        logger.error("OPENAI_API_KEY is not set. Add it to .env before running.")
        sys.exit(1)

    raw_dir = Path(args.raw)
    db_path = Path(args.db)

    if not raw_dir.exists():
        logger.error(f"Raw directory not found: {raw_dir}")
        sys.exit(1)

    logger.info("=" * 60)
    logger.info("MediCheck RAG Knowledge Base Ingestion")
    logger.info("=" * 60)
    logger.info(f"Source directory : {raw_dir.resolve()}")
    logger.info(f"Vector store     : {db_path.resolve()}")
    logger.info(f"Embedding model  : {EMBEDDING_MODEL}")
    logger.info(f"Chunk size       : {CHUNK_SIZE} tokens (~{CHUNK_SIZE * 4} chars)")
    logger.info(f"Chunk overlap    : {CHUNK_OVERLAP} tokens")
    logger.info("")

    # Load and chunk
    logger.info("Step 1: Loading and chunking source documents...")
    chunks = load_and_chunk_all(raw_dir)
    logger.info(f"\nTotal chunks to embed: {len(chunks)}")

    if not chunks:
        logger.error("No chunks produced. Check that source files exist in data/raw/.")
        sys.exit(1)

    # Embed and persist
    logger.info("\nStep 2: Embedding and persisting to ChromaDB...")
    vector_store = build_vector_store(chunks, db_path, reset=args.reset)

    # Verify
    logger.info("\nStep 3: Verifying vector store...")
    verify_vector_store(vector_store)

    logger.info("\n" + "=" * 60)
    logger.info(f"Done. {len(chunks)} chunks ingested successfully.")
    logger.info(f"Vector store ready at: {db_path.resolve()}")
    logger.info("=" * 60)


if __name__ == "__main__":
    main()