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
| Member 1 — Product Owner | User stories, Trello backlog, Figma wireframes, RAG service (Service 3) |
| Member 2 — Scrum Master + Code Owner | GitHub repo, CI/CD, Render services, Bill Analysis API (Service 2) |

---

## Project Board

Trello board: *(link to be added in Sprint 1)*

---

## Repository Structure

```
medicheck/
├── .github/
│   └── workflows/
│       └── ci-cd.yml           # GitHub Actions CI/CD pipeline (Sprint 2)
├── docs/
│   ├── diagrams/               # UML and architecture diagrams (.drawio + exports)
│   └── postman/                # Postman collection for API testing
├── services/
│   ├── frontend/               # Service 1 — React + Vite SPA (Sprint 2)
│   ├── bill-analysis/          # Service 2 — Flask Bill Analysis API (Sprint 2)
│   └── rag-service/            # Service 3 — Flask RAG & Letter Service (Sprint 3)
├── test-data/
│   ├── generate_test_data.py   # Synthetic document generator (Sprint 3)
│   └── synthetic/              # Generated PDFs
├── README.md                   # This file
├── deployed.md                 # Live Render service URLs
├── requirements.md             # User stories, user journey, traceability matrix
├── system-requirements.md      # Functional and non-functional system requirements
├── design-and-testing.md       # Architecture, UML, patterns, test results (Sprint 5)
├── design-and-evaluation.md    # RAG evaluation results (Sprint 5)
├── ai-tooling.md               # AI tools used during development
└── .env.example                # Required environment variables (no real values)
```

---

## Local Setup

*To be completed in Sprint 2 once service scaffolding is in place.*

### Prerequisites

- Node.js 18+
- Python 3.11+
- PostgreSQL

### Environment Variables

Copy `.env.example` to `.env` and fill in all required values before running any service locally.

```bash
cp .env.example .env
```

---

## CI/CD

GitHub Actions pipeline runs on every pull request and every push to `main`.

- Installs dependencies
- Runs pytest and lint
- On passing `main`: auto-deploys all three Render services
- Post-deploy: pings `/health` on both Flask services

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
