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

*To be completed.*
