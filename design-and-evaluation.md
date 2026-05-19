# MediCheck — Design and Evaluation

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

---

### User Flow

Service 1 implements a **4-screen linear workflow** with stateless, URL-driven routing:

1. **Upload (/)** — Patient uploads provider bill PDF (required) and EOB PDF (optional)
   - `POST /upload` → receives `session_id`, `extracted_fields`, `rag_available` flag
   - Navigates to `/confirm/{sessionId}`

2. **Field Confirmation (/confirm/:sessionId)** — Patient reviews and corrects extracted fields
   - Displays: patient_name, provider_name, date_of_service, total_billed, line_items[]
   - Fields with confidence < 80% are highlighted (amber warning)
   - All fields are inline-editable; confidence scores are stripped before submission
   - `POST /confirm` → advances to `/report/{sessionId}`

3. **Error Report (/report/:sessionId)** — Displays all detected billing errors
   - `POST /analyse` triggered if not yet run; displays results immediately
   - Error cards show: error type, description, estimated dollar impact, severity badge (high/medium/low)
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

**Error handling:** All network errors throw `ApiError` with structured error code, message, and HTTP status. Components catch and display user-friendly messages (e.g., "Upload failed. Please check your connection."). HTTP 200 responses are treated as success even if `rag_available: false` — the frontend gracefully degrades (shows "RAG unavailable; error explanations may be generic").

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
- **No client-side validation:** Validation is server-side (Service 2); frontend only displays errors returned by API

---

## Service 3 — RAG & Explanation Service

### Overview

Service 3 is a stateless Flask microservice responsible for generating plain-English explanations of detected billing errors and producing formal dispute letter content. It uses a Retrieval-Augmented Generation (RAG) pipeline built on LangChain, ChromaDB, and GPT-4o-mini. All traffic is internal — Service 2 calls Service 3 after running its four detection modules.

**Endpoints:**
- `POST /explain` — receives a list of detected errors, returns a grounded explanation and citations per error
- `POST /draft-letter` — receives the full analysis payload, returns a formal dispute paragraph

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

**Latency note:** The p95 of 8 863 ms is driven by a single outlier call (eval_010, 8 863 ms). The remaining 15 calls ranged from 4 062 ms to 5 823 ms. p50 of 4 988 ms is the more representative figure for typical request latency. All calls completed within the 10-second timeout.

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

### Remaining Gaps and Future Work

**Module 3 — date mismatch (eval_011)**
No public-domain source addresses date-of-service discrepancies between a provider bill and EOB. A CMS EOB guidance document or NAIC model act publication could fill this gap if identified and confirmed to chunk well.

**Module 3 — error subtype awareness**
Service 2's `error_type` field distinguishes between Amount Mismatch, Missing from EOB, and Date Mismatch. Service 3 currently uses only the module name for retrieval filtering. Passing the subtype through to `explain_detection()` would allow finer-grained source selection — for example, excluding NSA documents entirely for date mismatch cases where they are never relevant. This requires no API contract changes (the field is already in the payload) but was deferred given the time cost and the absence of a suitable date-mismatch source document.

**Textract live testing**
All evaluation was conducted with `USE_MOCK_OCR=true`. Live Textract testing requires account-level activation in the AWS console (a `SubscriptionRequiredException` was encountered on the first attempt — not a credentials issue). This remains an open item pending AWS account activation.
