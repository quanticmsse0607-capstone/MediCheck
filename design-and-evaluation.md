# MediCheck — Design and Evaluation

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

### Findings

#### Module 1 — Duplicate Charge

Initial evaluation revealed a systematic KB gap: all four duplicate charge cases returned citations from ICD-10-CM (diagnostic coding conventions) and NSA documents — neither of which contains rules about duplicate CPT billing. The explanations were factually correct (the LLM knows the rule from training), but no retrieved chunk supported them.

**Corrective action:** CMS NCCI Chapter 1 (General Correct Coding Policies, 2026) was added to the knowledge base (70 chunks). Post-fix, all four Module 1 cases cite the correct authoritative source. Citation accuracy improved from 0/4 to 4/4.

#### Module 2 — Medicare Rate Outlier

All four cases cited the CMS Physician Fee Schedule methodology document at the correct formula section. The RVU26B-only source filter worked correctly — no cross-module bleed. 4/4 yes.

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
