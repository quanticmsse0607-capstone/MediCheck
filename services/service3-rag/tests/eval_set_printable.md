# MediCheck RAG Evaluation Set
**Step 8 — Sprint 5 | Service 3 RAG Evaluation**

16 cases across 4 modules, 4 per module. All payload descriptions match the actual output format of Shifali's Service 2 detectors (verified 2026-04-28). CPT descriptions are absent by design — AMA copyright applies; detectors use code numbers only.

**Groundedness score (0–100):** What % of factual claims in the system response are supported by the retrieved context?
**Citation accurate:** Do the cited sources actually contain content relevant to the error? (yes / no / partial)

---

## Module 1 — Duplicate Charge
*Same CPT code billed twice on the same date.*
*Note: Knowledge base has limited direct content on duplicate billing — an honest "context does not address this" is acceptable. A fabricated regulatory citation is not.*

---

### eval_001 — Classic duplicate, two line items
**Error sent to system:**
> CPT 99213 appears 2 time(s) on 2024-03-15. Line items 1 and 3 bill the same procedure on the same date. Duplicate billing for a single encounter is not permitted.

**Gold answer — response must mention:**
- Billing the same procedure code twice on the same date is not permitted
- Patient should only be billed once for a single service encounter
- One of the duplicate charges should be removed or refunded

**Expected sources:** ICD-10-CM, CMS, or coding guidelines

| Field | Your score |
|---|---|
| Groundedness score (0–100) | |
| Citation accurate (yes / no / partial) | |
| Notes | |

---

### eval_002 — Duplicate, same date
**Error sent to system:**
> CPT 93000 appears 2 time(s) on 2024-04-02. Line items 2 and 5 bill the same procedure on the same date. Duplicate billing for a single encounter is not permitted.

**Gold answer — response must mention:**
- The same procedure should not appear twice on a single claim
- Patient is entitled to dispute the duplicate line item

**Expected sources:** ICD-10-CM, CMS, or coding guidelines

| Field | Your score |
|---|---|
| Groundedness score (0–100) | |
| Citation accurate (yes / no / partial) | |
| Notes | |

---

### eval_003 — High-dollar surgical duplicate
**Error sent to system:**
> CPT 27447 appears 2 time(s) on 2024-01-20. Line items 1 and 4 bill the same procedure on the same date. Duplicate billing for a single encounter is not permitted.

**Gold answer — response must mention:**
- A surgical procedure should be billed only once per operative session
- The duplicate charge represents a significant overbilling

**Expected sources:** ICD-10-CM, CMS, or procedure guidelines

*Watch for: hallucinated dollar figures — the system should not invent numbers beyond what was in the payload.*

| Field | Your score |
|---|---|
| Groundedness score (0–100) | |
| Citation accurate (yes / no / partial) | |
| Notes | |

---

### eval_004 — Lab panel duplicate, medium confidence
**Error sent to system:**
> CPT 80053 appears 2 time(s) on 2024-02-10. Line items 3 and 6 bill the same procedure on the same date. Duplicate billing for a single encounter is not permitted.

**Gold answer — response must mention:**
- Duplicate lab panel charges on the same date should be reviewed
- Patient should request clarification on whether two tests were medically necessary

**Expected sources:** ICD-10-CM or coding guidelines

*Note: Medium confidence case. Acceptable response acknowledges uncertainty while explaining the concern.*

| Field | Your score |
|---|---|
| Groundedness score (0–100) | |
| Citation accurate (yes / no / partial) | |
| Notes | |

---

## Module 2 — Medicare Rate Outlier
*Billed amount exceeds 300% of the CMS Physician Fee Schedule locality rate.*

**Scoring approach: anti-hallucination (not content-claim verification)**

The two knowledge base sources for this module are:
- **PPRRVU2026** — raw rate numbers. Not embedded in ChromaDB (lookup data only — no prose to retrieve).
- **RVU26B.pdf** — CMS field layout document. Embedded, but contains technical column descriptions with no patient-facing narrative.

There is no verifiable prose to check `must_mention` claims against. Instead, score Module 2 on what the system **must NOT say**:

| Must not say | Why |
|---|---|
| Any specific rate figure not in the payload | Would be hallucinated — actual rates are not in ChromaDB |
| Any fabricated regulation name or statute | No regulatory text in these sources |
| That the 300% threshold is a legal maximum | It is a detection threshold, not law |

**Citation check:** Citation must name RVU26B, CMS Physician Fee Schedule, or a CMS source. A citation to a non-existent document is a failure.

*Note: only SC locality (CMS Locality 07 — Rest of South Carolina) is implemented in the detector. All Module 2 cases use SC locality.*

*This methodology difference is documented in `eval_set.json` (`_notes.module2_scoring_note`) and in `session_decisions.md`.*

---

### eval_005 — Office visit at 700% of Medicare rate
**Error sent to system:**
> CPT 99213 is billed at $525.00, which is 700% of the Medicare rate of $75.00 (CMS Locality 07 — Rest of South Carolina). Charges exceeding 300% of the Medicare rate are flagged as outliers.

**Scoring: anti-hallucination. Check that the response does NOT:**
- Invent a specific Medicare rate for CPT 99213 beyond what is in the payload
- Cite a fabricated regulation name or statute
- State that 300% is a legal maximum

**Citation check:** Does citation name RVU26B, CMS Physician Fee Schedule, or a CMS source?

| Field | Your score |
|---|---|
| Hallucination detected? (yes / no) | |
| Citation accurate (yes / no / partial) | |
| Notes | |

---

### eval_006 — Physical therapy at 336% of Medicare rate
**Error sent to system:**
> CPT 97110 is billed at $185.00, which is 336% of the Medicare rate of $55.00 (CMS Locality 07 — Rest of South Carolina). Charges exceeding 300% of the Medicare rate are flagged as outliers.

**Scoring: anti-hallucination. Check that the response does NOT:**
- Invent a specific Medicare rate beyond what is in the payload
- Cite a fabricated regulation name or statute
- State that 300% is a legal maximum

**Citation check:** Does citation name RVU26B, CMS Physician Fee Schedule, or a CMS source?

| Field | Your score |
|---|---|
| Hallucination detected? (yes / no) | |
| Citation accurate (yes / no / partial) | |
| Notes | |

---

### eval_007 — Imaging at 1000% of Medicare rate
**Error sent to system:**
> CPT 70553 is billed at $4,500.00, which is 1000% of the Medicare rate of $450.00 (CMS Locality 07 — Rest of South Carolina). Charges exceeding 300% of the Medicare rate are flagged as outliers.

**Scoring: anti-hallucination. Check that the response does NOT:**
- Invent a specific Medicare rate for CPT 70553 beyond what is in the payload
- Cite a fabricated regulation name or statute
- State that 300% is a legal maximum

**Citation check:** Does citation name RVU26B, CMS Physician Fee Schedule, or a CMS source?

*Key check: does the system hallucinate a specific Medicare rate? It should not — CPT rates are not in ChromaDB.*

| Field | Your score |
|---|---|
| Hallucination detected? (yes / no) | |
| Citation accurate (yes / no / partial) | |
| Notes | |

---

### eval_008 — Surgical procedure at 674% of Medicare rate
**Error sent to system:**
> CPT 29881 is billed at $6,200.00, which is 674% of the Medicare rate of $920.00 (CMS Locality 07 — Rest of South Carolina). Charges exceeding 300% of the Medicare rate are flagged as outliers.

**Scoring: anti-hallucination. Check that the response does NOT:**
- Invent a specific Medicare rate beyond what is in the payload
- Cite a fabricated regulation name or statute
- State that 300% is a legal maximum

**Citation check:** Does citation name RVU26B, CMS Physician Fee Schedule, or a CMS source?

*Bonus check: if the system mentions geographic practice cost indices (GPCI), verify it did not invent a GPCI value — a real mention is a good sign of genuine retrieval from RVU26B.*

| Field | Your score |
|---|---|
| Hallucination detected? (yes / no) | |
| Citation accurate (yes / no / partial) | |
| Notes | |

---

## Module 3 — EOB Reconciliation
*Cross-reference between provider bill and insurer EOB; flag mismatches.*
*Knowledge base has limited direct content — an honest "context does not address this" is acceptable. Watch for hallucinated insurance law citations.*

*Note: The detector generates four distinct error types — the eval set covers Amount Mismatch, Missing from EOB, and Date Mismatch. Date Mismatch always has $0 dollar impact (hardcoded in detector).*

---

### eval_009 — Amount mismatch
**Error type:** `EOB Reconciliation — Amount Mismatch`

**Error sent to system:**
> CPT 99214 (line item 2): provider bill shows $350.00 but the EOB shows $180.00. Discrepancy: $170.00.

**Gold answer — response must mention:**
- In-network providers cannot bill patients beyond their cost-sharing obligation
- The patient's responsibility is defined by the EOB, not the provider's billed amount
- Billing above the insurer-negotiated rate is not permitted for in-network providers

**Expected sources:** EOB, insurance, balance billing, or patient responsibility content

| Field | Your score |
|---|---|
| Groundedness score (0–100) | |
| Citation accurate (yes / no / partial) | |
| Notes | |

---

### eval_010 — CPT missing from EOB
**Error type:** `EOB Reconciliation — Missing from EOB`

**Error sent to system:**
> CPT 99070 (line item 4) appears in the provider bill but is not present in the insurance EOB. This may indicate a billing or processing discrepancy.

**Gold answer — response must mention:**
- Charges not listed on the EOB should be questioned before payment
- Patient should contact the insurer to confirm whether this charge was submitted and processed

**Expected sources:** EOB, insurance, or claim processing content

| Field | Your score |
|---|---|
| Groundedness score (0–100) | |
| Citation accurate (yes / no / partial) | |
| Notes | |

---

### eval_011 — Date mismatch ($0 dollar impact)
**Error type:** `EOB Reconciliation — Date Mismatch`

**Error sent to system:**
> CPT 99213 (line item 1): provider bill shows date 2024-05-10 but the EOB shows 2024-05-08.

**Gold answer — response must mention:**
- Date discrepancies between the provider bill and EOB should be clarified with both the provider and insurer
- Patients have the right to request an itemized bill to verify service dates

**Expected sources:** EOB, billing, or insurance content

*Note: $0 dollar impact is correct — the detector hardcodes 0.0 for date mismatches. Tests whether system explains the concern even without a dollar figure.*

| Field | Your score |
|---|---|
| Groundedness score (0–100) | |
| Citation accurate (yes / no / partial) | |
| Notes | |

---

### eval_012 — EOB shows $0 patient responsibility; provider re-bills
**Error type:** `EOB Reconciliation — Amount Mismatch`

**Error sent to system:**
> CPT 71046 (line item 3): provider bill shows $220.00 but the EOB shows $0.00. Discrepancy: $220.00.

**Gold answer — response must mention:**
- A service already paid in full by the insurer cannot be billed to the patient
- Patient should present the EOB to the provider showing the claim was paid
- Double billing is a billing error the provider must correct

**Expected sources:** EOB, insurance, or patient responsibility content

*Note: The description is intentionally terse (matches detector output). The RAG should still explain the implication of a $0 EOB balance.*

| Field | Your score |
|---|---|
| Groundedness score (0–100) | |
| Citation accurate (yes / no / partial) | |
| Notes | |

---

## Module 4 — No Surprises Act Violation
*Out-of-network provider in a context where federal law (2022) prohibits balance billing.*
*Knowledge base has strong content here (NSA PDFs). Failure to cite the No Surprises Act is a groundedness failure.*

*Note: The detector references Pub. L. 116-260 directly in the description — this appears verbatim in every payload and should anchor retrieval well.*

---

### eval_013 — Emergency care, out-of-network physician
**Error sent to system:**
> CPT 99283 (line item 1) may be a balance billing charge prohibited under the No Surprises Act. The provider is recorded as out-of-network in your EOB, and this charge relates to emergency care. Under the No Surprises Act (Pub. L. 116-260), patients are protected from balance billing in this context.

**Gold answer — response must mention:**
- The No Surprises Act prohibits balance billing for emergency services
- Patients are only responsible for their in-network cost-sharing for emergency care regardless of provider network status
- Out-of-network emergency providers cannot bill above the in-network rate

**Expected sources:** No Surprises Act PDF — emergency services section

| Field | Your score |
|---|---|
| Groundedness score (0–100) | |
| Citation accurate (yes / no / partial) | |
| Notes | |

---

### eval_014 — Ancillary provider: out-of-network anesthesiologist at in-network facility
**Error sent to system:**
> CPT 01400 (line item 2) may be a balance billing charge prohibited under the No Surprises Act. The provider is recorded as out-of-network in your EOB, and this charge relates to services by an out-of-network ancillary provider at an in-network facility. Under the No Surprises Act (Pub. L. 116-260), patients are protected from balance billing in this context.

**Gold answer — response must mention:**
- The No Surprises Act protects patients from surprise bills from ancillary providers at in-network facilities
- Anesthesiologists and other ancillary providers cannot balance bill when the facility is in-network
- Patient should have received a good faith estimate in advance

**Expected sources:** No Surprises Act PDF — ancillary providers / good faith estimate section

| Field | Your score |
|---|---|
| Groundedness score (0–100) | |
| Citation accurate (yes / no / partial) | |
| Notes | |

---

### eval_015 — Ancillary provider: out-of-network radiologist at in-network imaging centre
**Error sent to system:**
> CPT 72148 (line item 2) may be a balance billing charge prohibited under the No Surprises Act. The provider is recorded as out-of-network in your EOB, and this charge relates to services by an out-of-network ancillary provider at an in-network facility. Under the No Surprises Act (Pub. L. 116-260), patients are protected from balance billing in this context.

**Gold answer — response must mention:**
- Out-of-network radiologists at in-network facilities are covered under No Surprises Act protections
- The patient cannot be balance billed for the professional interpretation fee
- Patient responsibility is limited to their in-network cost-sharing

**Expected sources:** No Surprises Act PDF — out-of-network providers at in-network facilities

| Field | Your score |
|---|---|
| Groundedness score (0–100) | |
| Citation accurate (yes / no / partial) | |
| Notes | |

---

### eval_016 — Ancillary provider: out-of-network hospitalist during in-network admission
**Error sent to system:**
> CPT 99232 (line item 1) may be a balance billing charge prohibited under the No Surprises Act. The provider is recorded as out-of-network in your EOB, and this charge relates to services by an out-of-network ancillary provider at an in-network facility. Under the No Surprises Act (Pub. L. 116-260), patients are protected from balance billing in this context.

**Gold answer — response must mention:**
- The No Surprises Act protects patients from surprise bills from ancillary providers at in-network facilities
- Hospitalists managing care during an in-network admission cannot balance bill the patient
- Patient is only responsible for their in-network cost-sharing amount

**Expected sources:** No Surprises Act PDF — ancillary providers / in-network facility section

*Note: This case replaced the original consent waiver scenario. The NoSurprisesActDetector skips elective out-of-network cases (US-011 AC5) so a waiver scenario would never produce a DetectionResult in the real system.*

| Field | Your score |
|---|---|
| Groundedness score (0–100) | |
| Citation accurate (yes / no / partial) | |
| Notes | |

---

## Summary Scoring Table

| Case | Module | Error Type | Groundedness (0–100) or Hallucination (y/n) | Citation Accurate | Notes |
|---|---|---|---|---|---|
| eval_001 | Duplicate Charge | Duplicate Charge | | | |
| eval_002 | Duplicate Charge | Duplicate Charge | | | |
| eval_003 | Duplicate Charge | Duplicate Charge | | | |
| eval_004 | Duplicate Charge | Duplicate Charge | | | |
| eval_005 | Medicare Rate Outlier | Medicare Rate Outlier | | | |
| eval_006 | Medicare Rate Outlier | Medicare Rate Outlier | | | |
| eval_007 | Medicare Rate Outlier | Medicare Rate Outlier | | | |
| eval_008 | Medicare Rate Outlier | Medicare Rate Outlier | | | |
| eval_009 | EOB Reconciliation | Amount Mismatch | | | |
| eval_010 | EOB Reconciliation | Missing from EOB | | | |
| eval_011 | EOB Reconciliation | Date Mismatch | | | |
| eval_012 | EOB Reconciliation | Amount Mismatch | | | |
| eval_013 | No Surprises Act | No Surprises Act Violation | | | |
| eval_014 | No Surprises Act | No Surprises Act Violation | | | |
| eval_015 | No Surprises Act | No Surprises Act Violation | | | |
| eval_016 | No Surprises Act | No Surprises Act Violation | | | |
| **Overall** | | | | | |
