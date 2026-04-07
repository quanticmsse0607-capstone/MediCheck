# MediCheck

**AI-Powered Healthcare Bill Accuracy & Dispute Assistant**  
Quantic MSSE Capstone | 2-Person Team | 11 Weeks

---

## Overview

MediCheck is a web-based document analysis platform that helps patients detect errors in US medical bills and Explanations of Benefits (EOBs), and generate ready-to-send dispute letters grounded in CMS regulations and the No Surprises Act.

The system is built as three independently deployed services using a microservices architecture with domain-driven design principles.

---

## Deployed Services

See [deployed.md](./deployed.md) for all live service URLs.

---

## Team

| Role | Responsibility |
|------|---------------|
| Member 1 — Product Owner | User stories, Trello backlog, RAG service (Service 3) |
| Member 2 — Scrum Master + Code Owner | GitHub repo, CI/CD, Render services, Bill Analysis API (Service 2) |

---

## Project Board

Trello board: https://trello.com/b/4cHIOhhU/medicheck-capstone-scrum-board

---

## Project Documents

This table is the single source of truth for all project documentation. Update the Sprint column when a document is meaningfully revised.

| Document | Purpose | Owner | Last Updated |
|---|---|---|---|
| `requirements.md` | Personas, user stories, system requirements (FR/NFR), traceability matrix, future work | Both | Sprint 1 |
| `docs/api-contract.md` | Inter-service JSON contract — all Service 1 → Service 2 endpoints, request/response schemas, decisions log | Both | Sprint 2 |
| `SERVICE2_EXPLAINED.md` | Service 2 architecture explanation and endpoint reference | Member 2 | Sprint 2 |
| `deployed.md` | Live Render service URLs and health check endpoints | Member 2 | Each sprint |
| `ai-tooling.md` | AI tools used during development | Both | Each sprint |
| `design-and-testing.md` | Architecture decisions, UML diagrams, design patterns, anti-patterns, deployment cost analysis, test results | Both | Sprint 5 |
| `design-and-evaluation.md` | RAG evaluation question set, groundedness scores, citation accuracy, latency results | Member 1 | Sprint 5 |

---

## Repository Structure

```
medicheck/
├── .github/
│   └── workflows/
│       └── ci-cd.yml                   # GitHub Actions CI/CD pipeline
├── docs/
│   ├── api-contract.md                 # Inter-service API contract (Service 1 → Service 2)
│   ├── diagrams/                       # UML and architecture diagrams (.drawio + exports)
│   └── postman/                        # Postman collection for API testing
├── services/
│   ├── service1-frontend/              # Service 1 — React + Vite SPA
│   ├── service2-billanalysis/          # Service 2 — Flask Bill Analysis API
│   └── service3-rag/                   # Service 3 — Flask RAG & Letter Service
│       └── data/
│           ├── cms_rvu_parser.py       # Parses CMS PPRRVU fixed-width file → medicare_rates.csv
│           ├── cms_gpci_parser.py      # Applies GPCI locality adjustments → medicare_rates_{state}.csv
│           ├── raw/                    # All source files committed (PDFs, HTML, .txt, .csv)
│           └── processed/             # Processed CSVs (committed)
│               ├── medicare_rates.csv          # National unadjusted Medicare rates
│               ├── medicare_rates_sc.csv       # South Carolina locality-adjusted rates
│               └── medicare_rates_nc.csv       # North Carolina locality-adjusted rates
├── test-data/
│   ├── generate_test_data.py           # Synthetic document generator
│   └── synthetic/                      # Generated PDFs (gitignored)
├── README.md                           # This file
├── deployed.md                         # Live Render service URLs
├── requirements.md                     # User stories, system requirements, traceability matrix
├── SERVICE2_EXPLAINED.md               # Service 2 architecture explanation
├── medicheck_requirements_document.pdf # Requirements document (PDF export)
├── design-and-testing.md               # Architecture, UML, patterns, test results (Sprint 5)
├── design-and-evaluation.md            # RAG evaluation results (Sprint 5)
├── ai-tooling.md                       # AI tools used during development
└── .env.example                        # Required environment variables (no real values)
```

### Gitignored files

The following are excluded from version control and must be sourced locally or regenerated:

| Path | Reason | How to regenerate |
|---|---|---|
| `services/service3-rag/chroma_db/` | Vector store — rebuilt on each ingest | Run `python ingest.py` in `services/service3-rag/` |
| `test-data/synthetic/*.pdf` | Synthetic test PDFs | Run `python test-data/generate_test_data.py` |
| `venv/` | Python virtual environments | Run `pip install -r requirements-dev.txt` in each service directory |
| `node_modules/` | Node dependencies | Run `npm install` in `services/service1-frontend/` |
| `.env` | Secrets — never committed | Copy `.env.example` and fill in values |


---

## Local Setup

### Prerequisites

- Python 3.11.9
- Node.js 18+
- pip
- An AWS account with Textract access
- An OpenAI API key
- A PostgreSQL instance (local or Render-managed)

---

### 1. Clone the repository

```bash
git clone https://github.com/<your-org>/medicheck.git
cd medicheck
```

---

### 2. Environment variables

Copy `.env.example` to `.env` and fill in all required values before running any service.

```bash
cp .env.example .env
```

Open `.env` and provide values for all variables. See `.env.example` for descriptions of each.

---

### 3. Service 2 — Bill Analysis API

```bash
cd services/service2-billanalysis

# Create and activate virtual environment
python -m venv venv

# macOS / Linux
source venv/bin/activate

# Windows
venv\Scripts\activate

# Install all dependencies including dev and test tools
pip install -r requirements-dev.txt

# Run locally
flask run --port 5001
```

Service 2 will be available at `http://localhost:5001`.  
Verify with: `curl http://localhost:5001/health`

> **Note:** `requirements-dev.txt` installs production dependencies plus dev tools (pytest, black, pylint, flake8). Render uses `requirements.txt` (production only) when deploying.

---

### 4. Service 3 — RAG & Letter Service

```bash
cd services/service3-rag

# Create and activate virtual environment
python -m venv venv

# macOS / Linux
source venv/bin/activate

# Windows
venv\Scripts\activate

# Install all dependencies including dev and test tools
pip install -r requirements-dev.txt

# Run locally
flask run --port 5002
```

Service 3 will be available at `http://localhost:5002`.  
Verify with: `curl http://localhost:5002/health`

> **Note:** `requirements-dev.txt` installs production dependencies plus dev tools (pytest, black, pylint, flake8). Render uses `requirements.txt` (production only) when deploying.

---

### 5. Service 1 — Frontend

```bash
cd services/service1-frontend

# Install dependencies
npm install

# Run locally
npm run dev
```

Service 1 will be available at `http://localhost:5173`.

---

### 6. CMS Data Pipeline (Service 3)

All raw CMS source files are committed to the repo in `services/service3-rag/data/raw/` and do not need to be downloaded. The processed Medicare rate files are also committed and do not need to be regenerated unless CMS releases a new annual or quarterly update.

If you do need to regenerate the processed rate files:

**Step 1 — Parse national rates**

```bash
cd services/service3-rag
source venv/bin/activate  # or venv\Scripts\activate on Windows

python data/cms_rvu_parser.py \
  --input data/raw/PPRRVU2026_Apr_nonQPP.txt \
  --output data/processed/medicare_rates.csv
```

**Step 2 — Generate locality-adjusted rates**

```bash
# South Carolina (covers Charleston and Greenville demo scenarios)
python data/cms_gpci_parser.py \
  --rvu data/processed/medicare_rates.csv \
  --gpci data/raw/GPCI2026.csv \
  --state SC \
  --output data/processed/medicare_rates_sc.csv

# North Carolina (covers Charlotte / Atrium Health demo scenario)
python data/cms_gpci_parser.py \
  --rvu data/processed/medicare_rates.csv \
  --gpci data/raw/GPCI2026.csv \
  --state NC \
  --output data/processed/medicare_rates_nc.csv
```

> **When CMS releases a new quarterly update** (July 1 = RVU26C, October 1 = RVU26D): download the new PPRRVU file, place it in `data/raw/`, and re-run Steps 2 and 3 with the updated filename. No code changes required unless CMS changes the file layout.

---

### 7. RAG Knowledge Base (Service 3)

The ChromaDB vector store is gitignored and must be built locally before Service 3 can serve explanation requests. The knowledge base is built from the source documents listed below — all committed to the repo at `services/service3-rag/data/raw/`.

**RAG source documents — all committed to the repo**

| File | Format | Source | Relevance |
|---|---|---|---|
| `icd_10_cm_october_2025_guidelines_0.pdf` | PDF | [cms.gov/medicare/coding-billing/icd-10-codes](https://www.cms.gov/medicare/coding-billing/icd-10-codes) | ICD-10-CM coding guidelines — supports billing error explanations |
| `nsa-at-a-glance.pdf` | PDF | [cms.gov/files/document/nsa-at-a-glance.pdf](https://www.cms.gov/files/document/nsa-at-a-glance.pdf) | No Surprises Act overview — Module 4 citations |
| `nsa-helping-consumers.pdf` | PDF | [cms.gov/files/document/nsa-helping-consumers.pdf](https://www.cms.gov/files/document/nsa-helping-consumers.pdf) | Patient-facing NSA guidance — Module 4 plain-English explanations |
| `nsa-keyprotections_1.pdf` | PDF | [cms.gov/files/document/nsa-keyprotections.pdf](https://www.cms.gov/files/document/nsa-keyprotections.pdf) | Key consumer protections — Module 4 citations |
| `surprise-billing-requirements-final-rules-fact-sheet.pdf` | PDF | [cms.gov/nosurprises](https://www.cms.gov/nosurprises) | Final rules summary — QPA disclosure and IDR payment determination |
| `What_You_Need_to_Know...July2021.html` | HTML | [cms.gov/newsroom](https://www.cms.gov/newsroom) | Part I interim final rule plain-language summary — emergency and ancillary service protections |
| `What_You_Need_to_Know...September2021.html` | HTML | [cms.gov/newsroom](https://www.cms.gov/newsroom) | Part II interim final rule plain-language summary — good faith estimates and IDR process |

> **Documents intentionally excluded:** `Requirements_Related_to_Surprise_Billing_Part1.pdf` and `Part2.pdf` are excluded — they are image-based scanned PDFs with no extractable text. The HTML equivalents above cover the same content. The IDR process proposed rule fact sheet and the Prescription Drug interim final rule are also excluded as outside MediCheck's scope.

**Step 1 — Build the vector store**

```bash
cd services/service3-rag
source venv/bin/activate  # or venv\Scripts\activate on Windows

python ingest.py
```

This chunks all source documents, generates embeddings via OpenAI (`text-embedding-3-small`), and writes the ChromaDB vector store to `data/chroma_db/`. Requires `OPENAI_API_KEY` to be set in `.env`. Allow 2–5 minutes on first run.

---

### 8. Generate synthetic test documents

```bash
# From repo root
python test-data/generate_test_data.py
```

Output: `test-data/synthetic/` — six PDFs (three bills, three EOBs) covering all three demo scenarios.

---

### Running tests

```bash
# Service 2
cd services/service2-billanalysis
source venv/bin/activate
pytest --cov

# Service 3
cd services/service3-rag
source venv/bin/activate
pytest --cov
```

---

## CI/CD

GitHub Actions pipeline runs on every pull request and every push to `main`.

- Installs dependencies for both Flask services
- Runs pytest and flake8 lint on both services
- Blocks merges to main if any step fails
- On passing `main`: auto-deploys all three Render services via deploy hooks
- Post-deploy: pings `/health` on both Flask services and fails the pipeline if either returns non-200

Pipeline configuration: [.github/workflows/ci-cd.yml](.github/workflows/ci-cd.yml)

---

## Branch Protection

All merges to `main` require a pull request approved by the Code Owner (Member 2). Direct pushes to `main` are disabled.

---

## Branch Naming Convention

| Prefix | Purpose | Example |
|---|---|---|
| `feature/` | New functionality | `feature/service3-rag-chain` |
| `fix/` | Bug fixes | `fix/service2-upload-validation` |
| `chore/` | Config, tooling, documentation | `chore/readme-update` |
| `hotfix/` | Urgent production fix | `hotfix/service2-health-endpoint` |

Always branch from the latest `main`. Delete feature branches after merging.

---

## Sprint Demo Recordings

| Sprint | Recording |
|--------|-----------|
| Sprint 1 | *(to be added)* |
| Sprint 2 | *(to be added)* |
| Sprint 3 | *(to be added)* |
| Sprint 4 | *(to be added)* |
| Sprint 5 | *(to be added)* |
| Sprint 6 | *(final presentation — to be added)* |
