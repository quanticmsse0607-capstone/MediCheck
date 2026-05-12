# MediCheck — Code Anti-Pattern Audit
**Date:** 2026-05-11  
**Scope:** Service 1 (React), Service 2 (Flask Bill Analysis), Service 3 (Flask RAG)  
**Method:** Static code review across all source files (venv and node_modules excluded)  
**Note:** Findings to be incorporated into design-and-testing.md

---

## Summary

| Severity | Count | Service 1 | Service 2 | Service 3 |
|----------|-------|-----------|-----------|-----------|
| High     | 5     | 1         | 3         | 1         |
| Medium   | 10    | 1         | 7         | 3         |
| Low      | 5     | 1         | 3         | 1         |
| **Total**| **20**| **3**     | **13**    | **5**     |

---

## High Severity

### H1 — Hardcoded localhost fallback silently misroutes in production
**File:** `services/service2-billanalysis/routes/letter.py:228`  
**Owner:** Service 2  
If `SERVICE2_BASE_URL` is not set in the production environment, the default `http://localhost:5000` is used silently. No startup validation fails fast on missing config, so production traffic can route to an unreachable endpoint without any error.

---

### H2 — Delete without rollback risks partial data loss
**File:** `services/service2-billanalysis/routes/analyse.py:98`  
**Owner:** Service 2  
`AnalysisResult.query.filter_by(session_id=session_id).delete()` is called without a transaction rollback guard. If the deletion partially succeeds and a subsequent write fails, analysis results for that session are permanently lost with no recovery path.

---

### H3 — Swallowed init exception leaves Service 3 in broken state
**File:** `services/service3-rag/app.py:42`  
**Owner:** Service 3  
The `init_chain()` call is wrapped in a bare `try/except` that logs the error and continues. Service 3 starts up and accepts traffic, but every `/explain` call returns HTTP 503. There is no deploy-time guard to prevent deploying a broken Service 3 instance.

---

### H4 — Unhandled JSON parse crash on gateway errors
**File:** `services/service1-frontend/src/api/medicheck.js:38`  
**Owner:** Service 1  
`await response.json()` is not wrapped in a try/catch. When a gateway or proxy returns an HTML error page (e.g., Render 502), `response.json()` throws a SyntaxError that propagates unhandled to the UI, bypassing the `ApiError` handler and producing an unrecoverable crash state.

---

### H5 — SERVICE3_URL defaults to localhost in production
**File:** `services/service2-billanalysis/config.py:24`  
**Owner:** Service 2  
`SERVICE3_URL` defaults to `http://localhost:5002`. If this env var is not set on Render, all RAG calls silently fail with a connection error rather than a clear configuration warning at startup.

---

## Medium Severity

### M1 — File seek state left at unknown position after validation failure
**File:** `services/service2-billanalysis/routes/upload.py:54–62`  
**Owner:** Service 2  
`file.seek()` is called multiple times during validation without a guaranteed reset. If `_validate_pdf()` fails on the EOB after partially reading the bill, the bill file pointer is left at an unknown position, corrupting subsequent reads.

---

### M2 — Nullable FK query silently matches orphaned records
**File:** `services/service2-billanalysis/routes/confirm.py:79–83`  
**Owner:** Service 2  
`LineItem.query.filter_by(extracted_field_id=extracted.id if extracted else None, ...)` — if `extracted` is None, this queries for `extracted_field_id IS NULL`, silently matching any orphaned line items rather than returning an empty result.

---

### M3 — Unknown module name searches entire knowledge base
**File:** `services/service3-rag/rag/chain.py:164`  
**Owner:** Service 3  
If a detector sends an unknown module name, a warning is logged but retrieval falls back to searching all documents. An explanation may be grounded in the wrong regulatory context (e.g., No Surprises Act text cited for a duplicate charge error).

---

### M4 — RAG explanation merge has no consistency check
**File:** `services/service2-billanalysis/routes/analyse.py:79–89`  
**Owner:** Service 2  
If `explanations` dict from Service 3 is missing an `error_id` key, `explanation: null` is silently written to the database without any log entry. The caller cannot distinguish between "RAG unavailable" and "RAG returned incomplete data".

---

### M5 — Explain endpoint validation stops at first invalid error
**File:** `services/service3-rag/routes/explain.py:84–92`  
**Owner:** Service 3  
Required field validation exits on the first invalid item in the `errors` list. If errors at indices 0–3 are valid but index 4 is not, indices 5–9 are never validated. The caller receives one error but may have multiple invalid items.

---

### M6 — Silent type coercion hides invalid user input
**File:** `services/service1-frontend/src/pages/FieldConfirmation.jsx:73–74`  
**Owner:** Service 1  
`parseFloat(fields.total_billed) || 0` silently converts non-numeric input (e.g., "abc") to 0. The user receives no feedback that their correction was discarded.

---

### M7 — Prompt injection via string concatenation
**File:** `services/service3-rag/rag/chain.py:161`  
**Owner:** Service 3  
```python
query = f"{detection['error_type']}: {detection['description']}"
```
Both fields originate from OCR output and could contain adversarial text. Although Service 3 is only called by Service 2 internally, this is a low-barrier injection vector if the call chain is ever extended or a validation bypass occurs upstream.

---

### M8 — Failed detector not identified in error log
**File:** `services/service2-billanalysis/services/engine.py:69–74`  
**Owner:** Service 2  
Exceptions include the traceback (`exc_info=True`) but not the detector class name. An operator reading logs must parse the stack trace to determine which of the four detectors threw.

---

### M9 — Upload endpoint hardcodes `rag_available: true`
**File:** `services/service2-billanalysis/routes/upload.py:121`  
**Owner:** Service 2  
The upload response includes `"rag_available": True` with no actual health check against Service 3. This assumption can mislead the frontend into showing RAG-dependent UI elements before analysis is run.

---

### M10 — ORM `onupdate` invocation not verified
**File:** `services/service2-billanalysis/models.py:66`  
**Owner:** Service 2  
`onupdate=_now` is passed to SQLAlchemy for `updated_at`. If the ORM does not invoke the callable on bulk updates (a known SQLAlchemy behaviour with `update()`), `updated_at` becomes stale. No test verifies this.

---

## Low Severity

### L1 — Fragile URL rewrite via regex
**File:** `services/service1-frontend/src/pages/DisputeLetter.jsx:22`  
**Owner:** Service 1  
`url.replace(/^https?:\/\/[^/]+/, '/api')` will silently produce a malformed URL if the URL format deviates from expectations. Better to construct the proxy path from application state than to transform a downloaded URL string.

---

### L2 — Hardcoded deployment message in source
**File:** `services/service1-frontend/src/components/Layout.jsx:29`  
**Owner:** Service 1  
"All patient data is synthetic" is a deployment-time fact, not a build-time constant. If this service is later deployed with real data, the message requires a code change rather than a config change.

---

### L3 — Missing rollback on session status transition failure
**File:** `services/service2-billanalysis/routes/analyse.py:116–118`  
**Owner:** Service 2  
`session.status = SessionStatus.ANALYSED` and `db.session.commit()` are called after analysis. If the commit fails, the session status is inconsistent with the persisted results. No rollback restores the previous state.

---

### L4 — No timeout on DB queries in detectors
**File:** `services/service2-billanalysis/detectors/`  
**Owner:** Service 2  
SQLAlchemy queries in detectors have no explicit timeout. A slow or locked DB will block the entire analysis request indefinitely with no NFR-compliant timeout behaviour.

---

### L5 — `is_ready()` accesses module-level singletons directly
**File:** `services/service3-rag/rag/chain.py:98`  
**Owner:** Service 3  
`is_ready()` reads `_vectorstore` and `_chain` as module globals. If the module is ever reloaded (e.g., Flask debug reloader in a multi-process scenario), the singletons reset to `None` without `init_chain()` being re-called, causing a false `is_ready() = False` result.

---

## Recommended Fix Order

| Priority | Item | Effort | Risk if unfixed |
|----------|------|--------|----------------|
| 1 | H4 — JSON parse crash in API client | Low | Unrecoverable UI crash on any gateway error |
| 2 | M7 — Prompt injection in RAG query | Low | Security exposure if call chain extended |
| 3 | H3 — Service 3 starts in broken state | Low | Silent 503s with no deploy-time signal |
| 4 | M3 — Unknown module searches all docs | Low | Wrong citations in explanations |
| 5 | H1/H5 — Hardcoded localhost defaults | Low | Silent misrouting in production |
| 6 | H2 — Delete without rollback | Medium | Data loss on re-analysis |
| 7 | M5 — Explain validates only first error | Low | Incomplete validation feedback |

---

*Generated by static code review — 2026-05-11*
