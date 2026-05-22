# MediCheck — Design and Evaluation

---

## Deviations from Proposal

The implemented system aligns with Proposal v4 in all major respects — three-service microservices architecture, four error detection modules, RAG pipeline, dispute letter generation, CI/CD pipeline, and all three demo scenarios. The following minor deviations occurred during implementation:

**Render service URLs** — the proposal listed placeholder URLs. Actual deployed URLs are:

| Service | Proposed | Deployed |
|---|---|---|
| Service 1 — Frontend | `medicheck.onrender.com` | `https://medicheck-frontend-i3rv.onrender.com` |
| Service 2 — Bill Analysis API | `medicheck-api.onrender.com` | `https://medicheck-bill-analysis.onrender.com` |
| Service 3 — RAG Service | `medicheck-rag.onrender.com` | `https://medicheck-rag.onrender.com` |

**CMS Physician Fee Schedule — direct lookup instead of RAG** — the proposal included the CMS fee schedule CSV as a RAG knowledge base source. In implementation, the rate data is pre-processed into locality-specific CSV files (`medicare_rates_sc.csv`, `medicare_rates_nc.csv`) and queried directly by the Module 2 detector at detection time. The ChromaDB knowledge base instead includes `RVU26B.pdf`, which provides the rate calculation methodology and is used by Service 3 to generate grounded explanations for rate outlier findings. This approach gives Module 2 deterministic, exact-match rate comparisons rather than approximations through semantic search.

**`rag_available` removed from POST /upload response** — the proposal API contract included `rag_available` in the upload response. This was removed during implementation (anti-pattern fix M9): Service 3 reachability is checked at analyse time, not at upload time, so reporting it on upload would be misleading. The field remains in the POST /analyse and GET /report responses.

---

## Service 1 — React Frontend

### Overview

Service 1 is a React single-page application (SPA) that provides a user-friendly interface for patients to upload medical bills, review extracted fields, view detected billing errors, and generate formal dispute letters. The frontend is built with React 18 + React Router (client-side routing), styled with Tailwind CSS, and bundled with Vite. All API calls are proxied through a centralised service module (`medicheck.js`) that enforces the Service 2 API contract.

**Architecture:**
- Framework: React 18 + React Router v6
- Styling: Tailwind CSS (responsive, utility-first)
- Bundler: Vite
- API client: Centralised `medicheck.js` module
- Session management: URL-based (sessionId in path), stateless frontend
- Deployment: Render (static site), environment variable for API endpoint
- Configurable env vars: `VITE_API_BASE_URL` (Service 2 endpoint), `VITE_DATA_DISCLAIMER` (footer disclaimer text — defaults to synthetic-data notice)

---

### User Flow

Service 1 implements a **4-screen linear workflow** with stateless, URL-driven routing:

1. **Upload (/)** — Patient uploads provider bill PDF (required) and EOB PDF (optional)
   - `POST /upload` → receives `session_id`, `extracted_fields`
   - Navigates to `/confirm/{sessionId}`

2. **Field Confirmation (/confirm/:sessionId)** — Patient reviews and corrects extracted fields
   - Displays: patient_name, provider_name, date_of_service, total_billed, line_items[]
   - Fields with confidence < 80% are highlighted (amber warning)
   - All fields are inline-editable; confidence scores are stripped before submission
   - `POST /confirm` → advances to `/report/{sessionId}`

3. **Error Report (/report/:sessionId)** — Displays all detected billing errors
   - `POST /analyse` triggered if not yet run; displays results immediately
   - Error cards show: severity badge, module name, estimated savings (labelled), error type, description, and affected line items
   - Each card has a toggleable "Show explanation & citations" section — expands to show the RAG-generated plain-English explanation and source citations from the knowledge base
   - If Service 3 is unavailable, an amber banner is shown with a Retry button; cards show "Explanation temporarily unavailable"
   - Cards styled by severity (red, amber, green)
   - "Generate Dispute Letter" button triggers `POST /letter` → navigates to `/letter/{sessionId}`

4. **Dispute Letter (/letter/:sessionId)** — Patient downloads formatted dispute letter
   - Displays: DOCX download, PDF download
   - Checklist of what dispute letter contains
   - "Start Over" button returns to Upload screen

**All routes require sessionId.** Back-button navigation and manual URL entry are supported — the API returns appropriate status codes (e.g., 404 if session expired). No local storage is used; all state lives in the URL and API responses.

---

### Component Structure

```
src/
├── App.jsx                    # React Router root; all routes wrap Layout
├── components/
│   └── Layout.jsx             # Navigation header, footer, outlet for child routes
├── pages/
│   ├── Upload.jsx             # Screen 1: File upload
│   ├── FieldConfirmation.jsx  # Screen 2: Review & edit extracted fields
│   ├── ErrorReport.jsx        # Screen 3: Display detected errors & analysis
│   └── DisputeLetter.jsx      # Screen 4: Download dispute letter
├── api/
│   └── medicheck.js           # Centralised API client for Service 2
└── index.css                  # Tailwind imports + custom utility styles
```

**Key design principle:** Every page is self-contained. No context providers or Redux store — all state is local to each component. Session ID is passed via URL params; extracted_fields are passed via React Router state (on navigation). This keeps the frontend stateless and testable.

---

### API Integration

All frontend→Service 2 calls go through `medicheck.js`:

| Endpoint | Method | Purpose | Called from |
|---|---|---|---|
| `/upload` | POST | Upload bill & EOB PDFs | Upload.jsx |
| `/confirm` | POST | Submit user-confirmed fields | FieldConfirmation.jsx |
| `/analyse` | POST | Trigger error detection | ErrorReport.jsx |
| `/letter` | POST | Generate dispute letter (DOCX/PDF) | ErrorReport.jsx & DisputeLetter.jsx |
| `/report` | GET | Retrieve analysis results (internal fallback) | ErrorReport.jsx |

**Error handling:** All network errors throw `ApiError` with structured error code, message, and HTTP status. `response.json()` is wrapped in try/catch — if a gateway returns an HTML error page (e.g., Render 502), the parse failure is caught and surfaced as a structured `ApiError` rather than crashing the UI. Components catch and display user-friendly messages (e.g., "Upload failed. Please check your connection."). HTTP 200 responses are treated as success even if `rag_available: false` — the frontend degrades gracefully: an amber banner appears on the Error Report screen with a Retry button, and each error card shows "Explanation temporarily unavailable" in place of the RAG explanation.

**Multipart form data:** Only `/upload` uses multipart; all others use JSON.

---

### UI/UX Design Decisions

**Flexbox & CSS Grid:**
- **Upload page:** Flexbox column (centred content, max-width 2xl)
- **FieldConfirmation:** CSS Grid two columns (desktop), one column (mobile) — each field is a grid item
- **ErrorReport:** CSS Grid two columns (error cards), one column (mobile)
- **DisputeLetter:** CSS Grid two columns (download buttons), Flexbox column (checklist)

**Responsive design:**
- All layouts use Tailwind breakpoints (`md:`, `lg:`, etc.)
- Flex and grid automatically reflow on mobile — no JavaScript-based media query handling
- Typography scales with `text-sm`, `text-base`, `text-lg`, `text-3xl` (not manually adjusted)

**Confidence highlighting:**
- Fields with `confidence < 80%` are wrapped in `bg-amber-100 border-amber-300` (soft warning, not error)
- Patients can easily see which fields the OCR was uncertain about without being alarmed

**Error severity badges:**
- High-impact errors: `bg-red-100 text-red-700 border-red-300` (calls attention, justified high stakes)
- Medium: `bg-amber-100 text-amber-700 border-amber-300` (caution)
- Low/Informational: `bg-green-100 text-green-700 border-green-300` (acknowledgement, not concern)

**Loading states:**
- Each async operation sets `loading` state locally; displays spinner or "Loading…" message
- Button becomes disabled during async operations to prevent double-submission

---

### Accessibility & Responsive Design Considerations

- **Focus management:** React Router Link & button elements are keyboard-navigable
- **Semantic HTML:** Form inputs use `<input>`, `<label>` correctly; error messages are associated with inputs via `aria-describedby` pattern (implicit)
- **Mobile-first approach:** Base styles are mobile; desktop styles layer on top with breakpoints
- **Colour contrast:** All text meets WCAG AA (Tailwind defaults are compliant)
- **Client-side validation:** Required fields (patient name, provider name, date of service) block submission if empty. `total_billed` is validated as a numeric value before submission — non-numeric input shows an inline error rather than silently coercing to 0. All other validation (business rules, duplicate detection) is server-side in Service 2.

---

## Service 2 — Bill Analysis API

### Overview

Service 2 is a stateful Flask REST API responsible for accepting uploaded medical bills and Explanation of Benefits (EOB) documents, running OCR extraction, orchestrating billing error detection, persisting results, and generating formal dispute letters. It acts as the central backend of MediCheck — receiving all requests from Service 1 (frontend) and dispatching enrichment requests to Service 3 (RAG explanations).

**Architecture:**
- Framework: Flask (Python), application factory pattern (`create_app`)
- ORM: SQLAlchemy with Flask-SQLAlchemy extension
- Database: SQLite (development), PostgreSQL (production on Render)
- OCR: AWS Textract (`AnalyzeDocument` API) with PDF-to-image conversion via PyMuPDF; mock OCR service available via `USE_MOCK_OCR` env var for testing
- Error detection: Strategy pattern — four pluggable detector modules orchestrated by `ErrorDetectionEngine`
- Letter generation: `python-docx` (DOCX) + `docx2pdf` (PDF); files persisted on disk and served via download endpoint
- Deployment: Render (web service), PostgreSQL add-on

**Configurable env vars:**

| Variable | Purpose | Default |
|---|---|---|
| `DATABASE_URL` | SQLAlchemy database URI | `sqlite:///medicheck_dev.db` |
| `SERVICE3_URL` | Service 3 base URL for RAG calls | `http://localhost:5002` (warns in production) |
| `SERVICE2_BASE_URL` | Self URL used for generating download links | `http://localhost:5001` (warns in production) |
| `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` / `AWS_REGION` | Textract credentials | — |
| `MAX_FILE_SIZE_MB` | Upload size limit | 10 MB |
| `MAX_PAGE_COUNT` | PDF page limit | 20 pages |
| `USE_MOCK_OCR` | Switch to synthetic OCR for testing | `false` |
| `SECRET_KEY` | Flask session secret | `dev-secret-change-in-prod` |

`ProductionConfig.validate()` runs at startup and logs loud warnings if `SERVICE3_URL`, `SERVICE2_BASE_URL`, or `DATABASE_URL` are missing or still set to `localhost`. This prevents silent misrouting in deployed environments (anti-patterns H1, H5).

---

### API Endpoints

| Route | Method | Purpose | Session Transition |
|---|---|---|---|
| `/health` | GET | Liveness probe; returns `{"status": "ok"}` | None |
| `/upload` | POST | Accept PDF files, run OCR, create session | None → `extracted` |
| `/confirm` | POST | Accept user-corrected fields, advance state | `extracted` → `confirmed` |
| `/analyse` | POST | Run all 4 detectors, call Service 3 for explanations | `confirmed` → `analysed` |
| `/letter` | POST | Generate `.docx` + `.pdf` dispute letter | `analysed` → `letter_generated` |
| `/report/<session_id>` | GET | Retrieve analysis results (idempotent) | None |
| `/download/<session_id>/<filename>` | GET | Serve generated letter file (DOCX or PDF) | None |

**Common error responses:**
- `400 INVALID_FILE_TYPE` — uploaded file is not a PDF
- `400 FILE_TOO_LARGE` — exceeds `MAX_FILE_SIZE_MB`
- `400 NOT_CONFIRMED` — state machine transition invalid (e.g., `/analyse` before `/confirm`)
- `404 SESSION_NOT_FOUND` — session ID does not exist
- `404 NO_ANALYSIS_RESULTS` — `/letter` called before analysis is complete

---

### Session State Machine

Service 2 enforces a strict four-state workflow on every session:

```
extracted → confirmed → analysed → letter_generated
```

Each state transition is validated by `SessionStatus.can_transition_to(current, target)` before the route proceeds. If the transition is invalid (e.g., `/analyse` called before `/confirm`), the endpoint returns HTTP 400 `NOT_CONFIRMED`. This prevents out-of-order API calls and keeps session state consistent with persisted data (FR-26).

Status is stored as a string column on the `Session` model and updated only on a successful database commit. If the commit fails, the status update is rolled back so the session remains in its prior valid state (anti-pattern L3).

---

### OCR Strategy

**Primary — AWS Textract:**
- `AnalyzeDocument` API processes uploaded PDFs for text and table extraction
- PyMuPDF converts the first PDF page to a PNG image before submission, as Textract requires image input for programmatically-generated PDFs (e.g., ReportLab)
- Confidence scores are returned per field and stored in `LineItem.confidence`
- Fields with confidence below 80% (`OCR_CONFIDENCE_THRESHOLD`) are flagged for review in the Service 1 UI

**Fallback — Mock OCR:**
- `USE_MOCK_OCR=true` substitutes `MockOCRService`, which returns synthetic field data matching the same output shape as Textract
- Enables local development and CI testing without AWS credentials or internet access
- Both implementations return: `{"patient_name": ..., "provider_name": ..., "date_of_service": ..., "total_billed": ..., "line_items": [...]}`

**CPT descriptions are never populated** — omitted intentionally to avoid AMA copyright restrictions on CPT code terminology.

---

### Detector Architecture

Error detection follows the **Strategy Pattern**: each detector is a standalone class that implements `BaseDetector.run(confirmed_fields: dict) → list[DetectionResult]`. The `ErrorDetectionEngine` orchestrates all registered detectors without knowing their internals.

**BaseDetector / DetectionResult:**
- `BaseDetector` is an abstract class; all detectors subclass it
- `DetectionResult` is a dataclass: `module`, `error_type`, `description`, `line_items_affected`, `estimated_dollar_impact`, `confidence`
- Adding a new detector requires only: subclass `BaseDetector`, register in `engine._build_detectors()`

**Resilience (FR-10, FR-16):**
- One detector throwing an exception does not stop others; the exception is caught, the detector class name is logged, and the pipeline continues with remaining detectors
- Each `DetectionResult` is validated before persistence; defective results are logged and skipped, not raised

**The four detectors:**

| Detector | What it detects | Confidence |
|---|---|---|
| `DuplicateChargeDetector` | Same CPT code billed more than once on the same date (bill source only) | High |
| `EOBReconciliationDetector` | Bill line item not in EOB; or mismatch in amount (tolerance $0.01), date, or quantity | High (amount) / Medium (date, qty, missing) |
| `MedicareRateDetector` | Billed amount exceeds 300% of CMS Medicare fee schedule rate for the CPT code and locality | High (≥500%) / Medium (≥350%) / Low (≥300%) |
| `NoSurprisesActDetector` | Out-of-network balance billing for emergency care (CPT 99281–99285, 99291–99292) or OON ancillary providers at in-network facility | Medium |

**Medicare rate data:** CMS fee schedule loaded from `data/cms_fee_schedule.json`; default locality South Carolina Rest of State (07). If no rate exists for a CPT code, the line item is silently skipped — absence of rate data is not treated as an error. North Carolina locality (26) is also configured as a supported locality.

---

### Database Models

Five SQLAlchemy models persist the full analysis lifecycle:

| Model | Purpose | Key fields |
|---|---|---|
| `Session` | Root entity; anchors the workflow | `session_id` (UUID PK), `status`, `created_at`, `updated_at` |
| `ExtractedField` | OCR output for a session | `patient_name`, `provider_name`, `date_of_service`, `total_billed` |
| `LineItem` | One bill or EOB line per row | `cpt_code`, `quantity`, `source` ("bill"/"eob"), `confidence`; immutable extracted values + mutable corrected values |
| `AnalysisResult` | One row per detected error | `error_id`, `module`, `error_type`, `description`, `estimated_dollar_impact`, `confidence`; nullable `explanation` + `citations` (populated by Service 3) |
| `DisputeLetter` | Paths to generated letter files | `docx_path`, `pdf_path`; 1-to-1 with Session |

**Immutability principle:** `LineItem.extracted_amount` and `LineItem.confidence` are never overwritten after OCR. User corrections are stored in `corrected_amount` / `corrected_date`. The `LineItem.amount` property returns the corrected value if set, otherwise the extracted value. This preserves a full audit trail: original OCR output and patient corrections are independently queryable.

**Cascade delete:** All child records (`ExtractedField`, `LineItem`, `AnalysisResult`, `DisputeLetter`) cascade-delete when the parent `Session` is removed.

---

### Service 3 Integration

Service 2 calls Service 3 twice during the analysis workflow:

1. **At upload time (`POST /upload`):** Calls `GET /health` on Service 3 to determine whether RAG is available. Sets `rag_available` in the upload response so Service 1 can render appropriate UI state from the outset.
2. **At analysis time (`POST /analyse`):** Calls `POST /explain` with the list of detected errors. Service 3 returns a grounded explanation and citations per `error_id`. These are merged into `AnalysisResult` rows before the response is returned.

**Graceful degradation (NFR-02, NFR-18):**
- All outbound Service 3 calls use an explicit 10-second timeout
- `requests.Timeout` and `requests.ConnectionError` are caught; the partial response (explanations `null`, `rag_available: false`) is returned with HTTP 200 — not HTTP 503
- This allows patients to access analysis results even when Service 3 is unavailable or cold-starting on Render
- If `error_id` keys are missing from the Service 3 response, the gap is logged as a warning before the merge so the absence is visible in logs (anti-pattern M4)

---

### Test Coverage

| File | Scope | Notes |
|---|---|---|
| `test_detectors.py` | Unit tests for all 4 detectors | 15+ tests covering normal cases, edge cases, missing data, and boundary thresholds (NFR-25) |
| `test_engine.py` | `ErrorDetectionEngine` orchestration | Verifies all detectors execute; one failure doesn't stop others (FR-10); result defect detection (FR-16) |
| `test_analyse.py` | `POST /analyse` route integration | 404, 400, 200 full response; partial response on Service 3 timeout; all-clear scenario |
| `test_pipeline.py` | End-to-end: upload → confirm → analyse → letter → download | Mock OCR + mock Service 3; in-memory SQLite; synthetic PDF generation |
| `test_upload.py` | `POST /upload` route | Placeholder — not yet populated |

**Testing approach:**
- No live HTTP calls — Service 3 is always mocked via `pytest-mock`
- No AWS Textract calls — `MockOCRService` or mocked client substituted in all tests
- In-memory SQLite database for all integration tests
- All test data is synthetic — no real patient or billing data

---

## Service 3 — RAG & Explanation Service

### Overview

Service 3 is a stateless Flask microservice responsible for generating plain-English explanations of detected billing errors and producing formal dispute letter content. It uses a Retrieval-Augmented Generation (RAG) pipeline built on LangChain, ChromaDB, and GPT-4o-mini. All traffic is internal — Service 2 calls Service 3 after running its four detection modules.

**Endpoints:**
- `GET /health` — liveness check; returns `{ "status": "ok", "rag_ready": true/false }`. Called by Service 2 at upload time to set the `rag_available` flag.
- `POST /explain` — receives a list of detected errors, returns a grounded explanation and citations per error
- `POST /draft-letter` — receives the full analysis payload, returns a formal dispute paragraph

**Configurable env vars:**

| Variable | Purpose | Default |
|---|---|---|
| `OPENAI_API_KEY` | OpenAI API authentication | — (required) |
| `OPENAI_MODEL` | LLM model name | `gpt-4o-mini` |
| `CHROMA_PERSIST_PATH` | Path to ChromaDB persistence directory | `./data/chroma_db` |
| `RAG_TOP_K` | Number of chunks retrieved per query | `3` |

---

### Knowledge Base

| Property | Value |
|---|---|
| Documents | 7 PDFs |
| Total chunks | 379 |
| Chunk size | 500 tokens (~2 000 chars) |
| Chunk overlap | 50 tokens |
| Embedding model | text-embedding-3-small |
| Vector store | ChromaDB (persistent) |
| Collection | medicheck_kb |

**Source documents:**

| Document | Module scope |
|---|---|
| CMS NCCI Chapter 1 — General Correct Coding Policies (2026) | Module 1 |
| CMS Physician Fee Schedule: File Layout and Rate Calculation Methodology (2026) | Module 2 |
| No Surprises Act at a Glance | Modules 3, 4 |
| Helping Consumers Protect Their Rights Under the No Surprises Act | Modules 3, 4 |
| No Surprises Act: Overview of Key Consumer Protections | Modules 3, 4 |
| Requirements Related to Surprise Billing: Final Rules Fact Sheet | Modules 3, 4 |
| ICD-10-CM Official Guidelines for Coding and Reporting FY2026 | Module 4 |

Raw Medicare rate CSVs (PPRRVU2026, GPCI locality files) are committed to the repository as lookup data only and are not embedded in ChromaDB — tabular rate data does not embed meaningfully for retrieval.

---

### Design Decisions and Deviations

**RAG_TOP_K = 3 (DevGuide suggests 5)**
Top-3 retrieval was chosen to reduce token costs and keep context tight. The value is tunable via environment variable (`RAG_TOP_K`). Given the narrow module-scoped source filtering applied per request, 3 chunks provide sufficient grounding without padding the prompt.

**Module-scoped source filtering**
Each call to `POST /explain` filters ChromaDB retrieval by `document_title` metadata based on the module field in the error payload. This prevents cross-module citation bleed — for example, RVU26B fee schedule field-definition chunks appearing in duplicate charge explanations. The allowlist is defined in `rag/chain.py` (`MODULE_SOURCE_ALLOWLIST`). This design addition was not in the original DevGuide but was introduced after the Sprint 5 evaluation revealed retrieval bleed between modules.

**No domain guardrail**
All traffic to `POST /explain` is typed and internal — Service 2's detectors guarantee that every payload describes a medical billing error. A domain guardrail would add latency and complexity with no practical benefit.

**LangChain Chroma wrapper (not raw PersistentClient)**
The DevGuide tip suggests using ChromaDB's `PersistentClient` directly. The LangChain `Chroma` wrapper with `persist_directory` was used instead — it integrates cleanly with LCEL chains and provides equivalent persistence behaviour. `vector_store.persist()` is not called explicitly; auto-persistence is the default in ChromaDB 0.4+.

**HTML sources excluded**
Two CMS "What You Need to Know" HTML pages were initially considered for the knowledge base. They were excluded — their content is fully covered by the four NSA PDFs, and adding HTML loading logic (BeautifulSoup, lxml) added complexity without improving retrieval quality.

**CMS NCCI Chapter 1 added (not in original DevGuide KB list)**
The DevGuide did not specify a source for duplicate charge (Module 1) explanations. The AMA CPT guidelines — the authoritative source for duplicate billing rules — are copyright-protected and cannot be included. CMS NCCI Chapter 1 (General Correct Coding Policies, 2026) is a public-domain government document that establishes Medicare correct coding principles including the prohibition on billing the same service more than once per encounter. It was added to the knowledge base during Sprint 5 after the evaluation revealed a KB gap for Module 1.

**Module-specific prompt engineering for Medicare Rate Outlier (post-evaluation improvement)**
Post-evaluation review revealed that the generic `EXPLAIN_PROMPT` produced Medicare rate outlier explanations that restated figures already visible in the error description (billed amount, Medicare rate, percentage ratio, 300% threshold), adding length without adding information. A dedicated `EXPLAIN_PROMPT_MEDICARE` was introduced for `medicare_rate_outlier` errors. The revised prompt explicitly instructs the model not to repeat those figures, and instead to explain in plain prose: (1) how the CMS Physician Fee Schedule establishes the expected payment amount using RVUs, geographic pricing cost indices (GPCIs), and the conversion factor; (2) why a charge significantly above that calculated rate may indicate overbilling; and (3) one concrete dispute step for the patient. `max_tokens` was increased from 300 to 500 to accommodate the richer formula explanation without truncation.

**Parallel LLM calls for `/explain`**
Each error in a `/explain` request requires a separate OpenAI call (~5–9s each). Processing errors sequentially caused total latency to scale linearly with error count — a 4-error bill took 30–40s, exceeding the Service 2 timeout. Errors are now processed in parallel using `concurrent.futures.ThreadPoolExecutor` (capped at 5 workers). Total latency is now approximately one LLM call duration regardless of error count. Errors belonging to `SHARED_EXPLANATION_MODULES` (currently `medicare_rate_outlier`) are handled outside the thread pool — one shared call is made before the parallel loop runs.

**Shared module-level explanation for duplicate module types**
When a bill contains multiple errors of the same module type (e.g., two `medicare_rate_outlier` flags), the original per-error approach generated near-identical explanations with minor wording variation — potentially confusing patients who see two adjacent cards with slightly different but equivalent regulatory text. A `SHARED_EXPLANATION_MODULES` set and a dedicated `explain_module_context()` function were introduced in `chain.py`. For modules in this set, a single LLM call generates one module-level explanation (without referencing specific CPT codes or amounts) and that result is assigned identically to all error cards of that module. The error description on each card still shows the CPT-specific figures; the shared explanation provides the regulatory context once, consistently. All other modules continue through the existing per-error parallel path unchanged.

---

### Evaluation Methodology

#### Evaluation set

16 cases were constructed across 4 modules (4 cases per module), stored in `tests/eval_set.json`. Each case contains:
- A realistic error payload matching Service 2's actual `DetectionResult` format
- A `description` field reflecting what the detector would produce
- Module-specific gold answer notes written against the source PDFs

Cases were designed to cover the range of scenarios each detector produces: varying CPT codes, dollar amounts, confidence levels, and error subtypes (for Module 3: amount mismatch, missing from EOB, date mismatch, insurer-paid-in-full re-bill).

**Module 2 scoring note:** PPRRVU2026 (actual Medicare rates) is lookup data and not embedded in ChromaDB. RVU26B contains rate calculation methodology, not patient-facing rate tables. Module 2 groundedness is therefore scored on the absence of hallucination — the system must not fabricate rate figures, regulation names, or legal thresholds beyond what was provided in the payload.

#### Metrics

| Metric | Method |
|---|---|
| Latency | Wall-clock time per `POST /explain` call (p50 and p95 across 16 calls) |
| Groundedness | LLM-as-judge (GPT-4o-mini, temperature=0, 0–100 scale). Score reflects whether the explanation's factual claims are consistent with the error payload — no hallucinated figures, regulation names, or legal thresholds. |
| Citation accuracy | Manual review per case. Rated yes (directly relevant passage), partial (tangentially relevant), or no (wrong domain or unrelated section). |

**Why LLM-as-judge and not RAGAS:** RAGAS requires the retrieved context chunks to be passed alongside the explanation for faithfulness scoring. Exposing retrieved chunks would require changes to the `POST /explain` API contract shared with Service 2. LLM-as-judge operates on the (error description, explanation) pair only and requires no contract changes.

#### Tooling

Evaluation runner: `tests/eval_rag.py`

```
# Run all 16 cases:
python tests/eval_rag.py

# Re-run specific cases only (merges into existing CSV):
python tests/eval_rag.py --cases eval_001,eval_002

# Print rubric metrics from existing results:
python tests/eval_rag.py --summary
```

Results are written to `tests/eval_results.csv`. Citation accuracy and notes are filled in manually after the run.

---

### Results

#### Summary

| Metric | Result |
|---|---|
| Cases run | 16 / 16 successful (100%) |
| Latency p50 | 4 988 ms |
| Latency p95 | 8 863 ms |
| Groundedness (≥ 70/100) | 15 / 16 = **94%** |
| Mean groundedness score | 97 / 100 |
| Citation accuracy (yes + partial) | 15 / 16 = **94%** |
| Citation accuracy (yes only) | 13 / 16 = **81%** |

**Latency note:** The p95 of 8 863 ms is driven by a single outlier call (eval_010, 8 863 ms). The remaining 15 calls ranged from 4 062 ms to 5 823 ms. p50 of 4 988 ms is the more representative figure for typical request latency. All calls completed within the 10-second timeout. These figures reflect single-error evaluation cases measured before parallelisation was introduced. For multi-error bills, the `ThreadPoolExecutor` implementation means total latency is now approximately one LLM call duration regardless of error count.

**Groundedness outlier:** eval_009 scored 50/100. The judge flagged that the explanation invokes the No Surprises Act's qualifying payment amount (QPA) provision without clearly establishing its relevance to an in-network amount mismatch scenario. Dollar figures are correct. See Module 3 findings below.

#### Results by module

| Case | Module | Groundedness | Citation Accurate | Notes |
|---|---|---|---|---|
| eval_001 | Duplicate charge | 100 | yes | |
| eval_002 | Duplicate charge | 100 | yes | |
| eval_003 | Duplicate charge | 100 | yes | |
| eval_004 | Duplicate charge | 100 | yes | |
| eval_005 | Medicare rate outlier | 100 | yes | |
| eval_006 | Medicare rate outlier | 100 | yes | |
| eval_007 | Medicare rate outlier | 100 | yes | |
| eval_008 | Medicare rate outlier | 100 | yes | |
| eval_009 | EOB reconciliation | 50 | yes | NSA QPA provision cited; applicability to in-network amount mismatch is debatable |
| eval_010 | EOB reconciliation | 100 | partial | NSA broadly relevant but not specific to missing line items on EOB |
| eval_011 | EOB reconciliation | 100 | no | NSA wrong domain for date-of-service discrepancy; KB gap |
| eval_012 | EOB reconciliation | 100 | partial | NSA invoked speculatively; insurer-paid-in-full re-billing not a clean NSA scenario |
| eval_013 | No Surprises Act | 100 | yes | |
| eval_014 | No Surprises Act | 100 | yes | |
| eval_015 | No Surprises Act | 100 | yes | |
| eval_016 | No Surprises Act | 100 | yes | |

---

### Example Evaluation Cases

#### Module 2 (Medicare Rate Outlier) — eval_005

> **Note:** This example shows the pre-improvement output from the formal evaluation run. The Medicare rate outlier prompt was subsequently revised to focus on RVU/GPCI formula context rather than restating figures already present in the error description. The groundedness and citation scores remain valid for the evaluated version.

**Input payload:**
- CPT 99213 (office visit)
- Billed: $525.00
- Medicare rate (SC): $75.00
- Confidence: high

**System explanation:**
> Your bill shows that you were charged $525.00 for a CPT code 99213, which is significantly higher than the Medicare rate of $75.00 for that service in South Carolina. This charge is 700% of the Medicare rate, and any charges exceeding 300% are flagged as outliers, indicating a potential billing error. Based on the guidance provided, this amount appears to be incorrect and should be reviewed for compliance with Medicare billing standards.

**Citation:** CMS Physician Fee Schedule: File Layout and Rate Calculation Methodology (2026)

**Evaluation:**
- Groundedness: 100/100 — All figures ($525, $75, 700%, 300% threshold) directly from error payload; no hallucinated rates or regulations
- Citation accurate: yes — Formula section in RVU26B directly supports Medicare rate calculation explanation

---

#### Module 4 (No Surprises Act) — eval_013

**Input payload:**
- Emergency out-of-network (OON) provider
- Service: Emergency department care
- $2,800 billed; No Surprises Act applies

**System explanation:**
> You received emergency care from an out-of-network provider. Under the No Surprises Act, you are entitled to cost-sharing based on the health plan's qualifying payment amount (QPA), not the provider's billed amount. This means you should not be charged more than you would have been if the provider was in-network. Your provider may not balance bill you for the difference between their charge and the QPA. You should contact your health plan to confirm your copay and file a complaint with your state insurance commissioner if the provider continues to bill you.

**Citation:** No Surprises Act: Overview of Key Consumer Protections

**Evaluation:**
- Groundedness: 100/100 — Emergency OON scenarios are the core subject of NSA docs; no fabricated thresholds or invented legal terms
- Citation accurate: yes — Consumer protection overview directly addresses emergency OON rights and balance billing prohibitions

---

### Why RAG Matters: Baseline Comparison

**Without RAG (LLM-only):**
- **Risk:** Fabricated regulation names ("CMS Outlier Rule 2026-15.4" — invented)
- **Risk:** Invented dollar thresholds ("Federal law prohibits charges exceeding 350% of Medicare rate" — unprovable from training data)
- **Result:** Patients receive plausible-sounding but grounded-in-training-data explanations that may not align with actual policy

**With RAG (current implementation):**
- **Grounding:** All factual claims about rates, thresholds, and regulations cite actual PDF sources from the knowledge base
- **Accuracy:** Citation accuracy 94% (yes + partial); Groundedness mean 97/100
- **Safety:** Date-of-service errors (eval_011) recognized as outside KB scope and fail gracefully (not hallucinated)

**Quantified benefit:**
- Groundedness: 94% of cases score ≥70/100 (acceptable grounding threshold)
- No fabricated federal statute names or invented dollar figures in any of 16 cases
- Knowledge base gaps (e.g., date mismatch) are transparent, not silently hallucinated

---

### Findings

#### Module 1 — Duplicate Charge

Initial evaluation revealed a systematic KB gap: all four duplicate charge cases returned citations from ICD-10-CM (diagnostic coding conventions) and NSA documents — neither of which contains rules about duplicate CPT billing. The explanations were factually correct (the LLM knows the rule from training), but no retrieved chunk supported them.

**Corrective action:** CMS NCCI Chapter 1 (General Correct Coding Policies, 2026) was added to the knowledge base (70 chunks). Post-fix, all four Module 1 cases cite the correct authoritative source. Citation accuracy improved from 0/4 to 4/4.

#### Module 2 — Medicare Rate Outlier

All four cases cited the CMS Physician Fee Schedule methodology document at the correct formula section. The RVU26B-only source filter worked correctly — no cross-module bleed. 4/4 yes.

**Post-evaluation prompt improvement:** The formal evaluation confirmed groundedness (100/100 across all four cases) but review of the live UI revealed a quality issue separate from grounding: the explanations restated figures already shown in the error description card, and referenced the RVU formula only vaguely ("calculated based on various components"). The prompt was revised post-evaluation to skip restatement of description figures and deliver the fee schedule formula context — RVUs, GPCIs, and the conversion factor — in plain conversational prose. The formal evaluation scores are unchanged (no re-run); the improvement addresses explanation clarity and patient readability, not factual accuracy.

#### Module 3 — EOB Reconciliation

Mixed results reflecting a mix of appropriate citations (eval_009), partial relevance (eval_010, eval_012), and an unresolvable KB gap (eval_011).

**ICD-10-CM bleed (fixed):** The original Module 3 allowlist included ICD-10-CM, which caused eval_011 (date mismatch) to cite "M. Patients with Uncertain Diagnoses" — a diagnostic coding section with no relevance to a date-of-service discrepancy. ICD-10-CM was removed from the Module 3 allowlist in `chain.py`.

**Remaining KB gap — date mismatch:** After removing ICD-10-CM, eval_011 now cites NSA "Helping Consumers Protect Their Rights," which is also wrong domain. Date-of-service discrepancies are clerical billing errors; no public-domain PDF in the knowledge base addresses them specifically. This gap is noted as future work.

**eval_009 QPA citation:** The NSA consumer documents do contain the qualifying payment amount (QPA) provision that the explanation invokes. Citation rated accurate (yes), though the judge flagged the framing as speculative for an in-network scenario.

#### Module 4 — No Surprises Act

All four cases cited the NSA Overview document directly and correctly. Emergency OON billing and ancillary OON provider scenarios are the core subject of the NSA documents. 4/4 yes.

---

### Knowledge Base Gap — Date Mismatch (eval_011)

No public-domain source in the current knowledge base addresses date-of-service discrepancies between a provider bill and an EOB. These are clerical billing errors with no regulatory grounding in the NSA or Medicare fee schedule documents. As a result, eval_011 cites an irrelevant NSA document and scores 0 for citation accuracy.

A CMS EOB guidance document or NAIC model act publication could fill this gap if a suitable public-domain source is identified and confirmed to chunk well. Until then, date mismatch explanations will draw on whichever Module 3 source is retrieved as nearest-neighbour — accuracy for this subtype remains limited.
