# MediCheck — Design and Testing Document

---

## Architecture Decisions and Rationale

*To be completed — see design-and-evaluation.md for Service 3 design decisions.*

---

## Domain-Driven Design Bounded Contexts

*To be completed.*

---

## Microservices Architecture Diagram

*To be completed.*

---

## UML Structural Diagram (Class Diagram)

*To be completed.*

---

## UML Behavioural Diagram (Sequence Diagram)

*To be completed.*

---

## Design Patterns Applied

*To be completed.*

---

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

**Setup:** Service 2 runs with `USE_MOCK_OCR=true` (no AWS required) and `SERVICE3_URL=http://localhost:5002`. Service 3 runs with a real `OPENAI_API_KEY` and loads the committed ChromaDB embeddings from `data/chroma_db/`.

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

All test data is synthetic — no real patient or billing information (NFR-06).

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
- Starts Service 3 on `localhost:5002` via `nohup` with real `OPENAI_API_KEY`; waits up to 150s for `/health`
- Starts Service 2 on `localhost:5001` via `nohup` with `USE_MOCK_OCR=true`; waits up to 60s for `/health`
- Runs `pytest tests/integration/ -v` — all 10 cross-service tests must pass
- Gated to push-to-main only to avoid OpenAI API costs on every PR

**Deploy job (push to `main` only, after all four jobs pass):**
- Triggers Render deploys for Service 2 and Service 3 via API
- Post-deploy health checks: Service 2 retries 3× at 30s intervals; Service 3 retries 24× at 15s intervals (up to 6 minutes, accommodating Render free-tier cold start)
