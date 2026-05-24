# MediCheck — AI Tooling

This document records all AI tools used during the development of MediCheck, as required by the Capstone rubric.

---

## Part 1 — AI Development Assistants

Tools used to assist with writing, reviewing, and debugging code during development.

| Tool | Provider | Used by | Purpose | Sprints |
|------|----------|---------|---------|---------|
| Claude Code (CLI) | Anthropic | Member 1 | Code generation, refactoring, test writing, documentation, code review | 1–6 |
| *(to be completed)* | | Member 2 | | |

**Notes on use:**
- All AI-assisted code was reviewed, understood, and validated by the responsible team member before being committed.
- AI tools were used to accelerate development, not to replace engineering judgment. All architectural decisions, design patterns, and requirement definitions reflect the team's own analysis.
- No AI-generated code was committed without the responsible developer understanding and being able to explain it.

---

## Part 2 — AI Services Embedded in the Application

AI APIs and models that form part of MediCheck's production functionality (Service 3).

| Model | Provider | Service | Purpose | Configuration |
|-------|----------|---------|---------|---------------|
| `text-embedding-3-small` | OpenAI | Service 3 | Generates vector embeddings for RAG knowledge base chunks stored in ChromaDB | Default dimensionality |
| `gpt-4o-mini` | OpenAI | Service 3 | Generates grounded plain-English explanations for detected billing errors and dispute letter content | `temperature=0` for deterministic output |

**Design decisions:**
- `gpt-4o-mini` was chosen over `gpt-4o` for cost efficiency — at `temperature=0` for structured, grounded output the quality difference is negligible for this use case, and the cost difference is approximately 10×.
- `text-embedding-3-small` was chosen over `text-embedding-ada-002` for better retrieval quality at lower cost.
- `temperature=0` is set on all generation calls to ensure deterministic, citation-grounded responses rather than creative elaboration.
- All LLM calls are subject to a configurable timeout (`SERVICE3_TIMEOUT_SECONDS`, default 30 seconds). If Service 3 does not respond in time, Service 2 returns a partial response with `rag_available: false` rather than failing (NFR-02).
