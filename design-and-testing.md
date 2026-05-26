# MediCheck — Design and Testing Document

## Architecture Decisions and Rationale

Decision 1 — Three-Service Microservices Split
MediCheck is decomposed into three independently deployable services rather than a monolith.
Drivers: The OCR/analysis pipeline (Service 2) and the RAG/LLM pipeline (Service 3) have fundamentally different scaling profiles, dependency trees, and failure modes. Separating them allows each to be scaled, deployed, and updated independently without risking a full-system outage.
Decision: Service 1 (React frontend) communicates with Service 2 (Bill Analysis API) over REST. Service 2 calls Service 3 (RAG & Letter) internally. Service 3 is never called directly by the frontend.
Trade-offs accepted: Added deployment complexity and inter-service latency. Mitigated by startup health checks, per-service timeouts (NFR-02, NFR-18), and graceful degradation — if Service 3 is unavailable, Service 2 returns results with rag_available: false rather than failing entirely.

Decision 2 — React SPA with Vite (Service 1)
Drivers: A multi-step user flow (upload → confirm fields → view report → download letter) maps naturally to a client-side routed SPA rather than server-rendered pages.
Decision: React with Vite as the build tool. All API calls go through a thin medicheck.js client module with a centralised ApiError type, keeping error handling consistent across the UI.
Trade-offs accepted: No server-side rendering; SEO is not a requirement for this application.

Decision 3 — Flask REST API with Supabase PostgreSQL (Service 2)
Drivers: A lightweight synchronous request/response model suits the analysis flow. Supabase provides a managed PostgreSQL database with a simple connection string, removing the need to operate database infrastructure. The session state machine (EXTRACTED → CONFIRMED → ANALYSED → LETTER_GEN) is enforced at the route layer — out-of-order requests return HTTP 400. All detector logic is isolated behind the ErrorDetectionEngine abstraction.
Decision: Flask with SQLAlchemy as the ORM layer connecting to Supabase PostgreSQL (db.xxxx.supabase.co:5432). Supabase was selected over a self-managed PostgreSQL instance for its free tier with no expiry, built-in connection pooling, and zero-ops maintenance burden appropriate for prototype scale.
Trade-offs accepted: Synchronous processing means long-running analyses block the worker. Acceptable at prototype scale; a task queue (e.g. Celery) would be the natural next step for production. Supabase free tier imposes connection limits that would need review before scaling.

Decision 4 — OCR Strategy: PDFPlumber then AWS Textract
Drivers: Extracting structured billing data from patient PDFs is the critical first step of the entire pipeline. The accuracy and reliability of this extraction directly determines the quality of downstream error detection.
Initial approach — PDFPlumber: The first implementation used PDFPlumber, a Python library for extracting text and tables from PDF files. It required no external API calls, had no per-use cost, and worked well for programmatically generated PDFs with clean text layers.
Problem encountered: Real-world hospital bills and EOBs are frequently scanned documents or image-based PDFs with no embedded text layer. PDFPlumber returned empty or near-empty extractions on these inputs, making the downstream field extraction unreliable. Confidence scores were low and the correction burden on the user at the Field Confirmation step was unacceptably high.
Switch to AWS Textract: AWS Textract's AnalyzeDocument API uses machine learning to extract text and structured form data from both native-text and scanned PDFs. It correctly identified key-value pairs (e.g. "Total Billed: $2,400.00") and table structures (line items with CPT codes and amounts) from image-based documents where PDFPlumber had failed entirely.
Trade-offs accepted: AWS Textract introduces a per-page API cost and an external dependency on AWS credentials. This makes it impossible to run live OCR in CI without real credentials. Mitigated by USE_MOCK_OCR=true, which substitutes MockOCRService for all test and CI runs, returning pre-defined extracted fields from synthetic test data. The services/ocr.py module is excluded from coverage reporting for this reason.

Decision 5 — LangChain RAG Pipeline with ChromaDB (Service 3)
Drivers: Explanations must be grounded in real regulatory sources (CMS Physician Fee Schedule, No Surprises Act Pub. L. 116-260, ICD-10-CM coding guidelines, Procedure-to-RVU crosswalk) rather than relying on LLM parametric memory alone, to reduce hallucination risk in a healthcare context (FR-17).
Decision: LangChain orchestrates retrieval-augmented generation. ChromaDB is the vector store, persisted as a volume on Render so it survives restarts (NFR-13). Source PDFs are ingested via ingest.py and embedded using OpenAI embeddings. GPT-4o-mini generates explanations at temperature=0 for deterministic output.
Trade-offs accepted: Cold start latency on Render free tier (up to 6 minutes). Mitigated by extended health-check retries in CI/CD (24 retries at 15s intervals) and a @app.before_request guard that re-initialises the chain if the Werkzeug reloader resets module globals (L5).

Decision 6 — Graceful Degradation over Hard Dependency
Drivers: Service 3 involves an external paid API (OpenAI) and a cold-start delay. Making it a hard dependency would cause the entire analysis flow to fail on any transient LLM issue.
Decision: Service 2 treats Service 3 as an optional enrichment layer. A 10-second timeout is enforced per the NFR-18 inter-service timeout requirement. If Service 3 times out or is unreachable, analysis results are returned without explanations and rag_available is set to false. The user sees a partial report with a retry prompt rather than an error page.

*see design-and-evaluation.md for Service 3 design decisions.*

---

## Domain-Driven Design Bounded Contexts

MediCheck is organised around two primary bounded contexts corresponding to Services 2 and 3, with Service 1 acting as the presentation layer. The bounded context diagram can be found at: Docs/diagrams/medicheck_bounded_context.png

Context 1 — Bill Processing Context
Service: Service 2 — Flask API · PostgreSQL (Supabase) · pdfplumber / Textract
Responsibilities: Accepting patient bill and EOB documents, running OCR extraction, storing structured billing fields, allowing the user to correct extracted values before analysis, running the four error detectors, persisting results, and generating the dispute letter document.
Key entities: Session, ExtractedField, LineItem, AnalysisResult, DisputeLetter
Services: OCRService (pdfplumber / Textract), ErrorDetectionEngine (Strategy pattern, 4 detectors), RAGClient (HTTP · 10s timeout), LetterBuilder (python-docx · ReportLab)
Session state machine (FR-26): EXTRACTED → CONFIRMED → ANALYSED → LETTER_GEN
API endpoints: GET /health, POST /upload, POST /confirm, POST /analyse, POST /letter, GET /download/<id>/file
Language: "upload", "session", "confirmed fields", "EOB", "line item", "detection", "error type", "confidence", "RAG available"
Boundary: Detectors operate on in-memory confirmed_fields dicts — they never query the database directly. RAGClient is the only point of contact with the Knowledge & Explanation context, translating any failure into a safe fallback (rag_available: false) rather than propagating exceptions.

Context 2 — Knowledge & Explanation Context
Service: Service 3 — Flask · ChromaDB · LangChain · GPT-4o-mini
Responsibilities: Retrieving relevant regulatory document chunks from ChromaDB, generating grounded plain-language explanations for detected errors, and drafting dispute letter content.
Key entities: KnowledgeBase (ChromaDB vector store · CMS document chunks · embeddings), Explanation (error_id · text · citations[] · source_passages[]), LetterContent (body_text · regulatory_refs · dispute_paragraph), Citation (source · section · url · passage_excerpt), RAGChain (LangChain retrieval · GPT-4o-mini · temperature=0), LetterGenerator (GPT-4o-mini · knowledge-grounded · temperature=0)
CMS knowledge base sources (FR-17): CMS Physician Fee Schedule (MPFS), No Surprises Act — Pub. L. 116-260, ICD-10-CM coding guidelines, Procedure-to-RVU crosswalk
API endpoints: GET /health, POST /explain → explanations[] + citations[], POST /draft-letter → letter content (string)
Language: "explain", "retrieval", "citations", "module", "draft letter", "completions"
Boundary: This context has no knowledge of sessions, patients, or billing fields. It receives only error type, description, and module name — no PII crosses this boundary. This is a deliberate HIPAA risk-reduction decision (NFR-21, NFR-24).

Infrastructure (shared)

PostgreSQL — Supabase: sessions · extracted_fields · line_items · analysis_results · dispute_letters. Free tier · no expiry.
GitHub Actions CI/CD: black · pylint · pytest · auto-deploy · health check. NFR-23, NFR-24.
OpenAI API: GPT-4o-mini · temperature=0 · RAG-grounded. 429 → retry.
Service 1 — React frontend: Vite · Tailwind · http://localhost:5173. Pages: Upload, Field Confirmation, Error Report, Dispute Letter.

## Microservices Architecture Diagram
The deployment and communication diagram is maintained as a separate file and can be found at: Docs/diagrams/medicheck_deployment_diagram.png

The diagram shows three Render-hosted services communicating over HTTPS REST. Service 1 (React SPA, static site) sends requests via a Vite proxy to Service 2 (Bill Analysis API, web service). Service 2 calls Service 3 (RAG & Letter, web service) via POST /explain and POST /draft-letter with a 10-second timeout (NFR-18); on timeout, rag_available falls back to false. External dependencies shown: Supabase PostgreSQL (sessions, fields, results, letters), ChromaDB (persistent volume on Service 3, survives restarts per NFR-13), and OpenAI API (GPT-4o-mini, embeddings, 429 → retry).

## UML Structural Diagram (Class Diagram)

Two class diagrams are maintained as separate files:
Strategy pattern (detector hierarchy only):Docs/diagrams/medicheck_uml_class_diagram.png

Shows BaseDetector (abstract), DetectionResult (dataclass), ErrorDetectionEngine, and the four concrete detector subclasses: DuplicateChargeDetector, MedicareRateDetector, EOBReconciliationDetector, NoSurprisesActDetector. Relationships: inheritance (BaseDetector → detectors), dependency/uses (ErrorDetectionEngine → BaseDetector), and <returns> (BaseDetector → DetectionResult).

Combined full diagram (all services): Docs/diagrams/medicheck_combined_uml.png
Extends the above with Flask route blueprints (Service 2), Supabase/PostgreSQL models (Session, ExtractedField, LineItem, AnalysisResult, DisputeLetter), service classes (RAGClient, LetterBuilder), and RAGChain components (Service 3: RAGChain, KnowledgeBase, LetterGenerator).

## UML Behavioural Diagram (Sequence Diagram)

The sequence diagram is maintained as a separate file and can be found at: Docs/diagrams/medicheck_sequence_diagram.png

The diagram traces the full four-phase flow across five participants: Service 1 (React UI), Service 2 (Bill Analysis), OCR (pdfplumber), PostgreSQL (Supabase), and Service 3 (RAG & Letter).

Phase 1 — Upload & OCR extraction: POST /upload → extract(file_bytes) → extracted_fields() → INSERT session + extracted_fields → session_id (UUID) → 200 (session_id, extracted_fields).
Phase 2 — Field confirmation: POST /confirm (session_id, confirmed_fields) → UPDATE corrected_amount, cpt_code → status = confirmed → 200 (status: confirmed).
Phase 3 — Error detection & RAG explanation: POST /analyse (session_id) → SELECT confirmed_fields + line_items → run 4 detectors (duplicate · medicare · nsa · eob) → POST /explain (errors[]) — 10s timeout (NFR-18) → RAG retrieval + GPT-4o-mini → [explanations[], citations[]] → alt fragment: timeout after 3s → rag_available: false · explanation: null → INSERT analysis_results[] → status = analysed → 200 (errors[], total_errors, rag_available).
Phase 4 — Dispute letter generation & download: POST /letter (session_id) → SELECT analysis_results[] → POST /draft-letter (session_id, analysis) → GPT-4o-mini letter generation → letter_content (string) → build .docx + .pdf (python-docx + ReportLab) → INSERT dispute_letters (docx_path, pdf_path) → 200 (downloads: {docx_url, pdf_url}) → GET /download/<id>/letter.docx → 200 letter.docx (binary — FR-13).

## Design Patterns Applied

1. Strategy Pattern — Billing Error Detectors
Where: services/service2-billanalysis/detectors/
Description: Each of the four billing error detectors (DuplicateChargeDetector, EOBReconciliationDetector, MedicareRateDetector, NoSurprisesActDetector) extends the abstract BaseDetector class and implements the run(confirmed_fields: dict) → list[DetectionResult] interface. ErrorDetectionEngine holds a list[BaseDetector] and calls run() on each without knowing the concrete type.
Benefit: New detectors can be added without modifying the engine. One detector raising an exception does not stop the others (FR-10). Tests for each detector are fully isolated.

2. Anti-Corruption Layer — RAGClient
Where: services/service2-billanalysis/services/rag_client.py
Description: RAGClient wraps all calls to Service 3, translating HTTP errors, timeouts, and connection failures into a safe return value (explanations: {}, letter: None) rather than propagating exceptions into the analysis route. timeout: 10s is enforced on every call (NFR-18).
Benefit: The Bill Processing context is completely insulated from the availability and interface of the Knowledge & Explanation context. Changing the Service 3 API contract requires changes only in RAGClient.

3. Template Method Pattern — Letter Builder
Where: services/service2-billanalysis/services/letter_builder.py
Description: LetterBuilder defines the overall structure of a dispute letter (header, patient details, itemised errors, closing, signature block) with each section implemented as a discrete method. The top-level build() method calls each section in order, producing both .docx (python-docx) and .pdf (ReportLab) outputs.
Benefit: Individual sections can be overridden or extended (e.g. for a different letter format) without rewriting the full build logic.

4. Factory / Registry Pattern — Module Routing in RAG Chain
Where: services/service3-rag/rag/chain.py
Description: A module-name-to-retrieval-filter mapping routes each detected error to the correct regulatory document subset in ChromaDB (e.g. "medicare_rate_outlier" → MPFS documents, "no_surprises_act" → Pub. L. 116-260 chunks). Unknown modules skip retrieval entirely rather than searching the full knowledge base (M3).
Benefit: Retrieval is scoped to relevant regulatory sources, reducing noise in the LLM context window and preventing cross-module hallucination.

5. Guard Clause Pattern — Route State Machine
Where: services/service2-billanalysis/routes/analyse.py, confirm.py
Description: Each route checks the session's current state at the top of the handler and returns HTTP 400 immediately if the request is out of order (e.g. calling /analyse before /confirm). No business logic executes until the guard passes. Enforces FR-26.
Benefit: State machine enforcement is explicit and co-located with the route, rather than buried in model methods.

## Anti-Patterns Identified and Resolved

### Overview

20 anti-patterns were identified across all three services during Sprint 5 code review. 18 of 20 were resolved; 1 was deferred as low risk for prototype scope, and 1 was reclassified as not applicable after investigation.

### Summary Table

| ID  | Severity | Service | Description | Status |
|-----|----------|---------|-------------|--------|
| H1  | High     | 2       | Hardcoded localhost fallback silently misroutes in production | ✅ Fixed |
| H2  | High     | 2       | Delete without rollback risks partial data loss | ✅ Fixed |
| H3  | High     | 3       | Swallowed init exception leaves Service 3 in broken state | ✅ Fixed |
| H4  | High     | 1       | Unhandled JSON parse crash on gateway errors | ✅ Fixed |
| H5  | High     | 2       | SERVICE3_URL defaults to localhost in production | ✅ Fixed |
| M1  | Medium   | 2       | File seek state left at unknown position after validation failure | ✅ Fixed |
| M2  | Medium   | 2       | Nullable FK query silently matches orphaned records | ✅ Fixed |
| M3  | Medium   | 3       | Unknown module name searches entire knowledge base | ✅ Fixed |
| M4  | Medium   | 2       | RAG explanation merge has no consistency check | ✅ Fixed |
| M5  | Medium   | 3       | Explain endpoint validation stops at first invalid error | ✅ Fixed |
| M6  | Medium   | 1       | Silent type coercion hides invalid user input | ✅ Fixed |
| M7  | Medium   | 3       | Prompt injection via string concatenation | ✅ Fixed |
| M8  | Medium   | 2       | Failed detector not identified in error log | ✅ Fixed |
| M9  | Medium   | 2       | Upload endpoint hardcodes `rag_available: true` | ✅ Fixed |
| M10 | Medium   | 2       | ORM `onupdate` invocation not verified | ⚠ Deferred |
| L1  | Low      | 1       | Fragile URL rewrite via regex | ✅ Fixed |
| L2  | Low      | 1       | Hardcoded deployment message in source | ✅ Fixed |
| L3  | Low      | 2       | Missing rollback on session status transition failure | ✅ Fixed |
| L4  | Low      | 2       | No timeout on DB queries in detectors | N/A |
| L5  | Low      | 3       | `is_ready()` accesses module-level singletons directly | ✅ Fixed |

---

### High Severity

**H1 — Hardcoded localhost fallback silently misroutes in production**
- **Found:** `SERVICE2_BASE_URL` defaulted to `http://localhost:5000` in `config.py`. No startup validation warned on missing production config, so traffic silently routed to an unreachable endpoint.
- **Fixed:** Default changed to empty string. `ProductionConfig.validate()` added — logs a loud warning at startup if `SERVICE2_BASE_URL` or `SERVICE3_URL` is missing or still set to localhost.
- **File:** `services/service2-billanalysis/config.py`

---

**H2 — Delete without rollback risks partial data loss**
- **Found:** `AnalysisResult.query.filter_by(...).delete()` in `analyse.py` was called without a transaction rollback guard. A partial delete followed by a failed write permanently lost analysis results with no recovery path.
- **Fixed:** Delete and subsequent writes wrapped in a try/except with `db.session.rollback()` on failure.
- **File:** `services/service2-billanalysis/routes/analyse.py`

---

**H3 — Swallowed init exception leaves Service 3 in broken state**
- **Found:** `init_chain()` was wrapped in a bare `try/except` that logged the error and continued. Service 3 started and accepted traffic, but every `/explain` call returned HTTP 503 with no deploy-time signal.
- **Fixed:** Exception is now re-raised after logging, causing the app to abort startup rather than start in a broken state.
- **File:** `services/service3-rag/app.py`

---

**H4 — Unhandled JSON parse crash on gateway errors**
- **Found:** `await response.json()` in `medicheck.js` was not wrapped in try/catch. Gateway errors returning HTML (e.g., Render 502) threw a `SyntaxError` that bypassed the `ApiError` handler and produced an unrecoverable UI crash.
- **Fixed:** `response.json()` wrapped in try/catch. Parse failures throw a structured `ApiError` with a user-friendly message.
- **File:** `services/service1-frontend/src/api/medicheck.js`

---

**H5 — SERVICE3_URL defaults to localhost in production**
- **Found:** `SERVICE3_URL` defaulted to `http://localhost:5002`. If not set on Render, all RAG calls silently failed with a connection error rather than a clear startup warning.
- **Fixed:** Same fix as H1 — production config validation warns loudly at startup on missing or localhost-defaulted `SERVICE3_URL`.
- **File:** `services/service2-billanalysis/config.py`

---

### Medium Severity

**M1 — File seek state left at unknown position after validation failure**
- **Found:** `file.seek()` called multiple times during upload validation without a guaranteed reset. A validation failure on the EOB after partially reading the bill left the bill file pointer at an unknown position, corrupting subsequent reads.
- **Fixed:** Explicit `file.seek(0)` added after each validation step to guarantee a known file pointer position before any subsequent read.
- **File:** `services/service2-billanalysis/routes/upload.py`

---

**M2 — Nullable FK query silently matches orphaned records**
- **Found:** `LineItem.query.filter_by(extracted_field_id=extracted.id if extracted else None, ...)` — when `extracted` was `None`, this queried for `extracted_field_id IS NULL`, silently matching orphaned records instead of returning empty.
- **Fixed:** Guard added to return an empty list immediately when `extracted` is `None` rather than issuing a nullable FK query.
- **File:** `services/service2-billanalysis/routes/confirm.py`

---

**M3 — Unknown module name searches entire knowledge base**
- **Found:** If a detector sent an unknown module name, a warning was logged but retrieval fell back to searching all documents. An explanation could be grounded in the wrong regulatory context.
- **Fixed:** Unknown modules now skip retrieval entirely (`docs = []`) rather than performing an unfiltered search. The warning is preserved.
- **File:** `services/service3-rag/rag/chain.py`

---

**M4 — RAG explanation merge has no consistency check**
- **Found:** If the `explanations` dict from Service 3 was missing an `error_id` key, `explanation: null` was silently written to the database with no log entry. Callers could not distinguish "RAG unavailable" from "RAG returned incomplete data."
- **Fixed:** Explicit check added after the Service 3 call — missing `error_id` keys are logged as warnings before the merge, making the gap visible in logs.
- **File:** `services/service2-billanalysis/routes/analyse.py`

---

**M5 — Explain endpoint validation stops at first invalid error**
- **Found:** Required field validation in `/explain` exited on the first invalid item. Multiple invalid items in a request produced only one error message.
- **Fixed:** Validation now collects all invalid items in a list comprehension before returning 400, reporting every validation failure in a single response.
- **File:** `services/service3-rag/routes/explain.py`

---

**M6 — Silent type coercion hides invalid user input**
- **Found:** `parseFloat(fields.total_billed) || 0` in `FieldConfirmation.jsx` silently converted non-numeric input (e.g., "abc") to 0. The user received no feedback that their correction was discarded.
- **Fixed:** `handleConfirm` now validates `total_billed` before submission — if non-empty and non-numeric, the submit is blocked and an inline error is shown to the user.
- **File:** `services/service1-frontend/src/pages/FieldConfirmation.jsx`

---

**M7 — Prompt injection via string concatenation**
- **Found:** `query = f"{detection['error_type']}: {detection['description']}"` used OCR-originated text directly as an embedding query and LLM prompt variable without sanitisation. Adversarial OCR output could manipulate the retrieval query or prompt.
- **Fixed:** `_sanitize(text, max_length)` added — truncates to a safe length and strips control characters. Called on `error_type` (max 100) and `description` (max 500) before use.
- **File:** `services/service3-rag/rag/chain.py`

---

**M8 — Failed detector not identified in error log**
- **Found:** Exception logging in `engine.py` included the traceback but not the detector class name. An operator had to parse the stack trace to identify which of the four detectors threw.
- **Fixed:** Detector class name added to the log message: `"Detector %s raised: %s", detector.__class__.__name__, exc`.
- **File:** `services/service2-billanalysis/services/engine.py`

---

**M9 — Upload endpoint hardcodes `rag_available: true`**
- **Found:** `POST /upload` returned `"rag_available": True` with no actual health check against Service 3. The frontend could display RAG-dependent UI before analysis confirmed Service 3 was reachable.
- **Fixed:** Upload response now calls the Service 3 `/health` endpoint and sets `rag_available` from the result. Falls back to `False` on timeout or connection error.
- **File:** `services/service2-billanalysis/routes/upload.py`

---

**M10 — ORM `onupdate` invocation not verified** ⚠ Deferred
- **Found:** `onupdate=_now` on `updated_at` in `models.py`. SQLAlchemy does not invoke `onupdate` callbacks on bulk `update()` operations, so `updated_at` may become stale.
- **Decision:** Deferred. MediCheck does not use bulk ORM `update()` calls — all updates go through individual model instances. The risk is limited to a future code path that doesn't exist yet. No test added; accepted for prototype scope.
- **File:** `services/service2-billanalysis/models.py`

---

### Low Severity

**L1 — Fragile URL rewrite via regex**
- **Found:** `url.replace(/^https?:\/\/[^/]+/, '/api')` in `DisputeLetter.jsx` silently produced a malformed URL if the URL format deviated from expectations.
- **Fixed:** Replaced with `new URL(url).pathname` wrapped in try/catch. Malformed URLs fall back to `'#'` rather than a broken proxy path.
- **File:** `services/service1-frontend/src/pages/DisputeLetter.jsx`

---

**L2 — Hardcoded deployment message in source**
- **Found:** "All patient data is synthetic and generated for demonstration purposes only." was a hardcoded string literal in `Layout.jsx`. Deploying with real data would require a code change rather than a config change.
- **Fixed:** Message now read from `import.meta.env.VITE_DATA_DISCLAIMER` with the synthetic-data text as the fallback default. Operators can override via environment variable without a code change.
- **File:** `services/service1-frontend/src/components/Layout.jsx`

---

**L3 — Missing rollback on session status transition failure**
- **Found:** `session.status = SessionStatus.ANALYSED` followed by `db.session.commit()` in `analyse.py` had no rollback if the commit failed, leaving session status inconsistent with persisted results.
- **Fixed:** Status transition and commit wrapped in try/except with `db.session.rollback()` on failure.
- **File:** `services/service2-billanalysis/routes/analyse.py`

---

**L4 — No timeout on DB queries in detectors** — Not Applicable
- **Found (audit):** SQLAlchemy queries in detectors identified as having no explicit timeout.
- **Reclassified:** Investigation confirmed that detectors do not query the database directly — they operate on in-memory `confirmed_fields` dicts passed from the route layer. Database queries occur only in route handlers (`analyse.py`, `confirm.py`), where SQLAlchemy's connection pool timeout applies. No code change required.
- **File:** `services/service2-billanalysis/detectors/`

---

**L5 — `is_ready()` accesses module-level singletons directly**
- **Found:** `is_ready()` read `_vectorstore` and `_chain` as module globals. Flask's Werkzeug debug reloader can reload modules mid-session, resetting singletons to `None` without re-calling `init_chain()`, causing `is_ready()` to return `False` and all subsequent requests to return HTTP 503.
- **Fixed:** `@app.before_request` guard added in `create_app()`. If `is_ready()` returns `False` on any request (e.g., after a debug reloader reset), `init_chain(app)` is called again before the request is handled. In production (gunicorn, no reloader), the guard adds only a two-None-check overhead per request.
- **File:** `services/service3-rag/app.py`

---

## Deployment Options and Cost Analysis

*To be completed.*

---

## Test Suite Summary

### Overview

| Service | Framework | Tests | Coverage | Notes |
|---|---|---|---|---|
| Service 1 — React Frontend | Vitest 4.x | 10 | — | API client unit tests only; no component tests |
| Service 2 — Bill Analysis API | pytest 8.x | 74 | 94% | Excludes `services/ocr.py` (requires live AWS Textract) |
| Service 3 — RAG & Letter | pytest 8.x | 43 | — | All OpenAI and ChromaDB calls mocked |
| Cross-service Integration | pytest + requests | 10 | — | Live HTTP, real OpenAI calls; push to `main` only |

**Total: 137 tests across all three services.**

---

### Service 1 — Vitest Unit Tests

**File:** `services/service1-frontend/src/api/medicheck.test.js`

All tests mock `fetch()` globally — no live HTTP traffic.

| Class / Group | Tests | What it covers |
|---|---|---|
| `ApiError` | 3 | Constructor fields, null defaults, instanceof Error |
| `request — error handling` | 3 | Non-OK response throws ApiError with server error_code; non-JSON response (e.g. Render 502 HTML) throws INVALID_RESPONSE (H4 regression guard); successful response returns parsed data |
| `confirmFields` | 1 | Request body contains session_id and confirmed_fields |
| `uploadDocuments` | 2 | FormData contains bill file; EOB appended when provided |
| `getReport` | 1 | GET request targets correct URL path |

**Run locally:**
```
cd services/service1-frontend
npm test
```

---

### Service 2 — pytest Integration Tests

**74 tests across 7 files.** All tests use in-memory SQLite, mock OCR (`USE_MOCK_OCR=true`), and mock Service 3 (`pytest-mock`). No live AWS or HTTP calls.

| File | Tests | What it covers |
|---|---|---|
| `test_detectors.py` | 15 | Unit tests for all 4 detectors: DuplicateCharge, EOBReconciliation, MedicareRate, NoSurprisesAct — normal cases, edge cases, boundary thresholds (NFR-25) |
| `test_engine.py` | 6 | ErrorDetectionEngine orchestration: all detectors execute, one failure doesn't stop others (FR-10), result defect detection (FR-16) |
| `test_upload.py` | 9 | POST /upload happy path (response structure, DB state, bill+EOB, no rag_available in response); file validation (no bill, non-PDF, oversized, bad EOB) |
| `test_analyse.py` | 5 | POST /analyse: 404, 400 state guard, full response with RAG, partial response on timeout (NFR-02), all-clear scenario |
| `test_report.py` | 10 | GET /report (404, results, all_clear, rag_available flag, download URLs); GET /download (invalid filename, no record, missing file, serves file); POST /letter re-serve without regenerating (FR-23) |
| `test_rag_client.py` | 9 | RAGClient.get_explanations and generate_letter: success, timeout (NFR-02), HTTP error, connection error, explicit timeout assertion (NFR-18) |
| `test_pipeline.py` | 20 | End-to-end: upload → confirm → analyse → letter → download; state machine enforcement (out-of-order requests return HTTP 400) |

**Coverage baseline (2026-05-20):** 94% across testable code. `services/ocr.py` (live AWS Textract) excluded — cannot run in CI without credentials.

```
Name                              Stmts   Miss  Cover   Missing
---------------------------------------------------------------
app.py                               31      4    87%   50-52, 63
config.py                            30      5    83%   58, 66-73
detectors\base.py                    36      5    86%   46, 48, 50, 52, 54
detectors\duplicate.py               26      0   100%
detectors\eob_reconciliation.py      43      3    93%   21, 58, 121
detectors\medicare_rate.py           45      2    96%   48-51
detectors\no_surprises.py            42      2    95%   79, 83
extensions.py                         2      0   100%
models.py                            85      6    93%   81, 117, 167-177
routes\analyse.py                    68      6    91%   143-153, 186
routes\confirm.py                    48      2    96%   86, 90
routes\health.py                      5      0   100%
routes\letter.py                     70      2    97%   112-113
routes\upload.py                     73      2    97%   25-27
services\engine.py                   34      0   100%
services\letter_builder.py          147      0   100%
services\mock_ocr.py                 12      5    58%   35-38, 42, 93
services\rag_client.py               48      3    94%   88-90
---------------------------------------------------------------
TOTAL                               845     47    94%
```

**Run locally (PowerShell from repo root):**
```powershell
cd services\service2-billanalysis
$env:USE_MOCK_OCR="true"; $env:FLASK_ENV="development"; $env:DATABASE_URL="sqlite:///test.db"; $env:SECRET_KEY="test"; $env:SERVICE3_URL="http://mock"
venv\Scripts\pytest tests\ --cov=. --cov-report=term-missing
```

---

### Service 3 — pytest Unit Tests

**43 tests across 4 files.** All OpenAI and ChromaDB calls are mocked. `conftest.py` sets a dummy `OPENAI_API_KEY` and patches `init_chain` before test collection, preventing any live API calls even if the secret is present.

| File | Tests | What it covers |
|---|---|---|
| `test_chain.py` | 22 | `init_chain`, `explain_detection`, `explain_module_context`: not-initialized guard, module-scoped retrieval filtering, sanitisation (M7), unknown module skips retrieval (M3), shared module explanation (Medicare rate outlier), citations structure |
| `test_explain.py` | 17 | POST /explain: validation (missing fields, empty list, unknown module), parallel execution, shared module called once for multiple errors, mixed module routing, Service 3 chain error returns 500 |
| `test_health.py` | 2 | GET /health: HTTP 200, response shape (`status`, `rag_chain_ready`) |
| `test_draft_letter.py` | 2 | POST /draft-letter: happy path, missing session_id returns 400 |

**Run locally:**
```
cd services/service3-rag
pytest tests/ -v
```

---

### Cross-Service Integration Tests

**File:** `tests/integration/test_e2e.py`

**10 tests** that run the full user flow against live services on `localhost`. Unlike the per-service tests above, these make real HTTP calls and trigger real OpenAI API calls through Service 3. They are the only tests in the suite that verify the two services work correctly together.

**Setup:** Service 2 runs with `USE_MOCK_OCR=true` (no AWS required) and `SERVICE3_URL=http://localhost:5002`. Service 3 runs with a real `OPENAI_API_KEY`; the ChromaDB vector store (`data/chroma_db/`, gitignored) is built by `ingest.py` in CI before Service 3 starts (cached via `actions/cache@v4` keyed on the raw source PDFs — only rebuilt when source documents change).

| Class | Tests | What it covers |
|---|---|---|
| `TestHealth` | 2 | Both services respond 200 on `/health` before tests begin |
| `TestUpload` | 2 | `POST /upload` returns a `session_id`; extracted fields and line items are present |
| `TestAnalyse` | 4 | `POST /analyse` returns `status=analysed`; `rag_available=True` confirms Service 3 RAG pipeline responded; each detected error has a non-null LLM explanation and citations list; `total_errors` matches `errors` list length |
| `TestReport` | 2 | `GET /report` returns the persisted session with `status=analysed` and the same error count as the analyse response |

**Key integration assertion — `rag_available=True`:** This is the critical cross-service check. It proves Service 2 successfully called Service 3's `/explain` endpoint, Service 3 ran the RAG chain (ChromaDB retrieval + OpenAI LLM), and returned grounded explanations within the 60-second timeout.

**Run locally:**
```powershell
# Terminal 1 — Service 3 (loads .env for OPENAI_API_KEY)
cd services\service3-rag
.\venv\Scripts\Activate.ps1
flask run --port 5002

# Terminal 2 — Service 2 (wait for Service 3 "RAG chain initialized")
cd services\service2-billanalysis
$env:USE_MOCK_OCR="true"; $env:SERVICE3_URL="http://localhost:5002"; $env:SERVICE3_TIMEOUT_SECONDS="60"
.\venv\Scripts\Activate.ps1
python app.py

# Terminal 3 — run integration tests
$env:SERVICE2_URL="http://localhost:5001"; $env:SERVICE3_URL="http://localhost:5002"
.\services\service2-billanalysis\venv\Scripts\Activate.ps1
pytest tests/integration/ -v
```

---

### Testing Approach

**No live external calls in any unit or service-level test.** All infrastructure dependencies are isolated:

| Dependency | How isolated |
|---|---|
| AWS Textract (OCR) | `USE_MOCK_OCR=true` substitutes `MockOCRService` |
| Service 3 (RAG explanations) | `mocker.patch("routes.analyse.rag_client.get_explanations", ...)` |
| OpenAI API | `conftest.py` patches `init_chain`; LangChain chain mocked per test |
| ChromaDB | Module-level singletons reset between tests; `_vectorstore` mocked |
| Database | In-memory SQLite (`sqlite:///:memory:`) for all integration tests |

**HIPAA compliance — synthetic data only (NFR-06):** No real patient or billing information is used at any stage of testing or demonstration. All patient names, dates of birth, addresses, member IDs, and policy numbers are generated programmatically using the Python `Faker` library (`test-data/generate_test_data.py`). Provider names and NPI numbers used are either publicly available from the CMS NPPES registry or explicitly marked as synthetic (`NPI: 9999000001` etc.). The three demo scenarios (Scenario A — BCBS SC / Atrium Health, Scenario B — Ambetter / MUSC Health, Scenario C — Molina / Prisma Health) inject billing errors by design — CPT codes, dollar amounts, and error types were specified before any test documents were generated.

---

### Continuous Integration

The CI pipeline (`.github/workflows/ci-cd.yml`) runs on every pull request and push to `main`.

**Per-service jobs (run in parallel on every PR and push):**

| Job | Steps |
|---|---|
| Service 2 | Black formatting check → Pylint (≥7.0, all modules) → pytest with coverage report |
| Service 3 | Black formatting check → Pylint (≥7.0, app + routes + rag) → pytest |
| Service 1 | ESLint (`--max-warnings 0`) → Vitest → Vite production build |

**Integration job (push to `main` only, after Service 2 and Service 3 pass):**
- Generates a synthetic test bill PDF using reportlab
- Restores ChromaDB vector store from cache (keyed on `data/raw/**`); runs `ingest.py` only if source PDFs have changed
- Starts Service 3 on `localhost:5002` via `nohup` with real `OPENAI_API_KEY`; waits up to 150s for `/health`
- Starts Service 2 on `localhost:5001` via `nohup` with `USE_MOCK_OCR=true`; waits up to 60s for `/health`
- Runs `pytest tests/integration/ -v` — all 10 cross-service tests must pass
- Gated to push-to-main only to avoid OpenAI API costs on every PR

**Deploy job (push to `main` only, after all four jobs pass):**
- Triggers Render deploys for Service 2 and Service 3 via API
- Post-deploy health checks for all three services:
  - Service 1 (`https://medicheck-frontend-i3rv.onrender.com/`): retries 3× at 30s intervals
  - Service 2 (`/health`): retries 3× at 30s intervals
  - Service 3 (`/health`): retries 24× at 15s intervals (up to 6 minutes, accommodating Render free-tier cold start)
