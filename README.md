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

## Repository Structure

```
medicheck/
├── .github/
│   └── workflows/
│       └── ci-cd.yml           # GitHub Actions CI/CD pipeline
├── docs/
│   ├── diagrams/               # UML and architecture diagrams (.drawio + exports)
│   └── postman/                # Postman collection for API testing
├── services/
│   ├── frontend/               # Service 1 — React + Vite SPA
│   ├── bill-analysis/          # Service 2 — Flask Bill Analysis API
│   └── rag-service/            # Service 3 — Flask RAG & Letter Service
├── test-data/
│   ├── generate_test_data.py   # Synthetic document generator
│   └── synthetic/              # Generated PDFs (gitignored)
├── README.md                   # This file
├── deployed.md                 # Live Render service URLs
├── requirements.md             # User stories, system requirements, traceability matrix
├── design-and-testing.md       # Architecture, UML, patterns, test results (Sprint 5)
├── design-and-evaluation.md    # RAG evaluation results (Sprint 5)
├── ai-tooling.md               # AI tools used during development
└── .env.example                # Required environment variables (no real values)
```

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
cd services/bill-analysis

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
cd services/rag-service

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
cd services/frontend

# Install dependencies
npm install

# Run locally
npm run dev
```

Service 1 will be available at `http://localhost:5173`.

---

### 6. Generate synthetic test documents

```bash
# From repo root
python test-data/generate_test_data.py
```

Output: `test-data/synthetic/` — six PDFs (three bills, three EOBs) covering all three demo scenarios.

---

### Running tests

```bash
# Service 2
cd services/bill-analysis
source venv/bin/activate
pytest --cov

# Service 3
cd services/rag-service
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

## Sprint Demo Recordings

| Sprint | Recording |
|--------|-----------|
| Sprint 1 | *(to be added)* |
| Sprint 2 | *(to be added)* |
| Sprint 3 | *(to be added)* |
| Sprint 4 | *(to be added)* |
| Sprint 5 | *(to be added)* |
| Sprint 6 | *(final presentation — to be added)* |
