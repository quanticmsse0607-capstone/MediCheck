# MediCheck RAG Evaluation Results
**Sprint 5 — Step 8 | Service 3: RAG & Explanation Service**
Generated: 2026-05-07 (post NCCI KB addition and Module 3 retrieval fix)

---

## Summary

| Metric | Result |
|---|---|
| Cases run | 16 / 16 successful (100%) |
| Latency p50 | 4 988 ms |
| Latency p95 | 8 863 ms |
| Groundedness (≥ 70/100) | 15 / 16 = **94%** |
| Mean groundedness score | 97 / 100 |
| Citation Accuracy | 13 / 16 yes · 2 / 16 partial · 1 / 16 no |

**Groundedness method:** LLM-as-judge (GPT-4o-mini, temperature=0). Judge evaluates whether factual claims in the explanation are consistent with the error payload — no hallucinated figures, regulation names, or legal thresholds beyond what was provided.

**eval_009 note:** Scored 50/100. Judge flagged that the explanation invokes the No Surprises Act's qualifying payment amount (QPA) provision without clearly establishing its relevance to this specific in-network amount mismatch scenario. Dollar figures are correct. Citation rated accurate (yes) — the NSA doc does contain the QPA provision.

**eval_011 note:** Citation rated no — date-of-service discrepancy is a clerical billing error; no public-domain KB source addresses it. KB gap documented as future work.

**Module-scoped filtering:** Active. Module 1 retrieves from CMS NCCI Chapter 1 only. Module 2 retrieves from RVU26B only. Modules 3 and 4 retrieve from NSA docs only (ICD-10-CM removed from Module 3 after eval revealed irrelevant diagnostic coding citations for EOB errors).

---

## Module 1 — Duplicate Charge

### eval_001
**Description:** Classic duplicate — same CPT code billed twice on same date, identical amounts

**Explanation:**
> It looks like there was a billing error on your bill for the date of March 15, 2024, where the same procedure, CPT code 99213, was charged twice. According to billing regulations, you cannot be billed for the same service more than once during a single visit. This means that one of those charges should be removed to correct the bill.

**Citation:** CMS NCCI Chapter 1 — General Correct Coding Policies — *Revision Date (Medicare): 1/1/2026*
**Groundedness:** 100/100 — Every factual claim is consistent with the error description, accurately reflecting the duplicate billing issue without introducing any invented details.
**Citation accurate:** ☑ yes ☐ no ☐ partial
**Notes:**

---

### eval_002
**Description:** Duplicate — same CPT, same date, two line items

**Explanation:**
> It looks like there was a billing error on your bill because the same procedure, identified by CPT code 93000, was charged twice on the same date, April 2, 2024. According to billing guidelines, you cannot bill for the same procedure more than once for a single encounter. This means that one of those charges should be removed to correct the bill.

**Citation:** CMS NCCI Chapter 1 — General Correct Coding Policies — *Revision Date (Medicare): 1/1/2026*
**Groundedness:** 100/100 — Every factual claim accurately reflects the error description regarding the duplicate billing of CPT code 93000.
**Citation accurate:** ☑ yes ☐ no ☐ partial
**Notes:**

---

### eval_003
**Description:** High-dollar duplicate surgical code

**Explanation:**
> It appears that you have been charged for the same procedure, CPT 27447, twice on your bill for the date of January 20, 2024. According to billing regulations, duplicate charges for a single encounter are not allowed unless specific conditions are met, which do not apply in this case. Therefore, this duplicate charge may be incorrect and should be reviewed for correction.

**Citation:** CMS NCCI Chapter 1 — General Correct Coding Policies — *Revision Date (Medicare): 1/1/2026*
**Groundedness:** 100/100 — Every factual claim is consistent with the error description, accurately reflecting the issue of duplicate billing for the same procedure on the same date.
**Citation accurate:** ☑ yes ☐ no ☐ partial
**Notes:**

---

### eval_004
**Description:** Duplicate lab panel — medium confidence

**Explanation:**
> Your bill shows that the same lab test, identified by CPT code 80053, was charged twice on February 10, 2024. This is considered a duplicate charge, which is not allowed for a single visit. According to billing guidelines, you should only be billed once for this specific test on the same date, unless there are special circumstances that justify a second charge, which does not appear to apply here.

**Citation:** CMS NCCI Chapter 1 — General Correct Coding Policies — *Revision Date (Medicare): 1/1/2026*
**Groundedness:** 100/100 — Every factual claim accurately reflects the error description regarding duplicate billing for the same lab test on the same date.
**Citation accurate:** ☑ yes ☐ no ☐ partial
**Notes:**

---

## Module 2 — Medicare Rate Outlier

### eval_005
**Description:** Office visit billed at 700% of Medicare rate, SC locality

**Explanation:**
> Your bill shows that you were charged $525.00 for a CPT code 99213, which is significantly higher than the Medicare rate of $75.00 for that service in South Carolina. This charge is 700% of the Medicare rate, and any charges exceeding 300% are flagged as outliers, indicating a potential billing error. Based on the guidance provided, this amount appears to be incorrect and should be reviewed for compliance with Medicare billing standards.

**Citation:** CMS Physician Fee Schedule: File Layout and Rate Calculation Methodology (2026) — *The formula for 2026 physician fee schedule payment amount is as follows:*
**Groundedness:** 100/100 — Every factual claim is consistent with the error description, including the dollar amounts and the percentage comparison to the Medicare rate.
**Citation accurate:** ☑ yes ☐ no ☐ partial
**Notes:**

---

### eval_006
**Description:** Physical therapy billed at 336% of Medicare rate, SC locality

**Explanation:**
> Your bill shows that you were charged $185.00 for a service coded as CPT 97110, but the Medicare rate for that service is only $55.00. This means your charge is 336% of the Medicare rate, which is flagged as an outlier since charges over 300% are considered excessive. According to the guidelines, the charge should not exceed a certain limit based on the Medicare fee schedule, so this amount may be incorrect.

**Citation:** CMS Physician Fee Schedule: File Layout and Rate Calculation Methodology (2026) — *The formula for 2026 physician fee schedule payment amount is as follows:*
**Groundedness:** 100/100 — Every factual claim is consistent with the error description, including the dollar amounts and the percentage calculation.
**Citation accurate:** ☑ yes ☐ no ☐ partial
**Notes:**

---

### eval_007
**Description:** Imaging procedure billed at 1000% of Medicare rate, SC locality

**Explanation:**
> Your bill shows a charge of $4,500 for a CPT code 70553, but the Medicare rate for this service is only $450. This means your charge is 1,000% higher than the Medicare rate, which is flagged as an outlier since it exceeds 300% of the Medicare rate. According to the guidelines, charges that are significantly higher than the Medicare fee schedule may be incorrect, and you should discuss this discrepancy with your provider or billing department.

**Citation:** CMS Physician Fee Schedule: File Layout and Rate Calculation Methodology (2026) — *The formula for 2026 physician fee schedule payment amount is as follows:*
**Groundedness:** 100/100 — Every factual claim is consistent with the error description, including the dollar amounts and the percentage comparison to the Medicare rate.
**Citation accurate:** ☑ yes ☐ no ☐ partial
**Notes:**

---

### eval_008
**Description:** Surgical procedure billed at 674% of Medicare rate, SC locality

**Explanation:**
> Your bill shows that CPT code 29881 was charged at $6,200, which is significantly higher than the Medicare rate of $920 for this procedure in South Carolina. This charge exceeds 300% of the Medicare rate, which flags it as a potential outlier according to Medicare guidelines. Based on the provided information, this billing may be incorrect, as it should align more closely with the established Medicare rates.

**Citation:** CMS Physician Fee Schedule: File Layout and Rate Calculation Methodology (2026) — *The formula for 2026 physician fee schedule payment amount is as follows:*
**Groundedness:** 100/100 — Every factual claim is consistent with the error description, including the dollar amounts and the outlier threshold.
**Citation accurate:** ☑ yes ☐ no ☐ partial
**Notes:**

---

## Module 3 — EOB Reconciliation

### eval_009 ⚠️
**Description:** Amount mismatch — provider bill shows more than EOB

**Explanation:**
> Your bill shows a charge of $350.00 for a CPT 99214 service, but the Explanation of Benefits (EOB) from your health plan indicates that the amount should be $180.00, creating a $170.00 discrepancy. This may be incorrect because, under the No Surprises Act, your cost-sharing should be based on the lesser of the billed charge or the health plan's qualifying payment amount. You should ask your provider to review the bill and contact your health plan to recalculate your cost-sharing based on this information.

**Citation:** Helping Consumers Protect Their Rights Under the No Surprises Act — *Helping Consumers Protect Their Rights*
**Groundedness:** 50/100 — The explanation correctly identifies the discrepancy but introduces the No Surprises Act without clear context or relevance to the specific billing issue.
**Citation accurate:** ☑ yes ☐ no ☐ partial
**Notes:** Judge scored 50/100 on re-run — NSA QPA citation accurate but applicability to in-network amount mismatch is debatable.

---

### eval_010
**Description:** CPT in provider bill not present on EOB at all

**Explanation:**
> It looks like there is a billing error on your bill because the service coded as CPT 99070 is included in the provider's bill but is missing from your insurance Explanation of Benefits (EOB). This could indicate a discrepancy in how the claim was processed. According to the guidance, you should ask the provider to review the bill and check with your health plan to ensure that your cost-sharing is calculated correctly, especially since this may relate to protections under the No Surprises Act.

**Citation:** Helping Consumers Protect Their Rights Under the No Surprises Act — *Helping Consumers Protect Their Rights*
**Groundedness:** 100/100 — Every factual claim is consistent with the error description, and no invented regulations or figures are included.
**Citation accurate:** ☐ yes ☐ no ☑ partial
**Notes:** NSA broadly relevant but not specific to missing line items on EOB.

---

### eval_011
**Description:** Date of service mismatch between provider bill and EOB

**Explanation:**
> It looks like there is a date mismatch on your bill for the CPT code 99213. The provider's bill shows the service date as May 10, 2024, but the Explanation of Benefits (EOB) states it was on May 8, 2024. This discrepancy could lead to issues with billing compliance, as the dates need to match for accurate processing and payment. Based on the information provided, this error should be addressed to ensure your bill reflects the correct date of service.

**Citation:** Helping Consumers Protect Their Rights Under the No Surprises Act — *Helping Consumers Protect Their Rights*
**Groundedness:** 100/100 — Every factual claim accurately reflects the date mismatch described in the error description without introducing any additional inaccuracies or speculative information.
**Citation accurate:** ☐ yes ☑ no ☐ partial
**Notes:** NSA wrong domain for date-of-service discrepancy; KB gap — no public-domain source for this error subtype.

---

### eval_012
**Description:** Insurer paid the claim in full — provider re-bills patient for $0 EOB balance

**Explanation:**
> It looks like there is a billing error related to your CPT code 71046. The provider billed $220.00 for this service, but the Explanation of Benefits (EOB) shows $0.00, which means the health plan did not process this charge. According to the No Surprises Act, if you believe this amount is incorrect, you should ask the provider to review the bill and the health plan to recalculate your cost-sharing based on the correct amount.

**Citation:** Helping Consumers Protect Their Rights Under the No Surprises Act — *Helping Consumers Protect Their Rights*
**Groundedness:** 100/100 — Every factual claim is consistent with the error description, and no invented regulation names or incorrect dollar figures are present.
**Citation accurate:** ☐ yes ☐ no ☑ partial
**Notes:** NSA invoked speculatively; insurer-paid-in-full rebilling not a clean NSA scenario.

---

## Module 4 — No Surprises Act

### eval_013
**Description:** Out-of-network emergency physician at in-network hospital — emergency CPT range

**Explanation:**
> It appears that you were charged for a service (CPT 99283) related to emergency care, but the provider is listed as out-of-network on your Explanation of Benefits (EOB). According to the No Surprises Act, you should not be billed for the balance of this charge because it was for emergency services, which are protected from balance billing when you receive care for an emergency medical condition. This means that your out-of-pocket costs for this service should not exceed what you would pay if the provider were in-network.

**Citation:** No Surprises Act: Overview of Key Consumer Protections — *No Surprises Act*
**Groundedness:** 100/100 — Every factual claim is consistent with the error description and accurately reflects the protections under the No Surprises Act.
**Citation accurate:** ☑ yes ☐ no ☐ partial
**Notes:**

---

### eval_014
**Description:** Out-of-network anesthesiologist at in-network facility — ancillary provider

**Explanation:**
> It looks like there may be an error on your bill related to a charge for CPT 01400, which is for services provided by an out-of-network provider at an in-network facility. According to the No Surprises Act, you should not be billed for this out-of-network service because it falls under the protections against surprise billing when receiving non-emergency services at an in-network facility. This means you should not have to pay the balance billed for this service.

**Citation:** No Surprises Act: Overview of Key Consumer Protections — *No Surprises Act*
**Groundedness:** 100/100 — Every factual claim aligns with the error description and accurately reflects the protections under the No Surprises Act.
**Citation accurate:** ☑ yes ☐ no ☐ partial
**Notes:**

---

### eval_015
**Description:** Out-of-network radiologist at in-network imaging centre — ancillary provider

**Explanation:**
> It looks like there may be an error on your bill related to a charge for CPT 72148, which is for a service provided by an out-of-network provider at an in-network facility. According to the No Surprises Act, you should not be billed for this out-of-network service because it falls under the protections against surprise billing when receiving non-emergency services at an in-network facility. This means you should not have to pay the balance billed for this service.

**Citation:** No Surprises Act: Overview of Key Consumer Protections — *No Surprises Act*
**Groundedness:** 100/100 — Every factual claim aligns with the error description and accurately reflects the protections under the No Surprises Act.
**Citation accurate:** ☑ yes ☐ no ☐ partial
**Notes:**

---

### eval_016
**Description:** Out-of-network hospitalist during in-network hospital admission — ancillary provider

**Explanation:**
> It looks like there may be an error on your bill regarding the charge for CPT 99232. This charge is from an out-of-network provider who treated you at an in-network facility, which is not allowed under the No Surprises Act. According to the Act, you should not be billed for out-of-network services in this situation, as it protects you from unexpected charges like this.

**Citation:** No Surprises Act: Overview of Key Consumer Protections — *No Surprises Act*
**Groundedness:** 100/100 — The explanation accurately reflects the error description regarding the No Surprises Act and the context of balance billing for out-of-network services at an in-network facility.
**Citation accurate:** ☑ yes ☐ no ☐ partial
**Notes:**

---

## Scoring Guide

**Groundedness (auto-scored, 0–100)**
Did the explanation invent any facts not present in the error payload? 100 = no hallucination. Scored by GPT-4o-mini judge on each (description, explanation) pair.

**Citation Accurate (manual, per row)**
- **yes** — the cited source document contains a passage directly relevant to the error type explained
- **partial** — the source is tangentially relevant but the specific section cited is not the strongest support
- **no** — the cited section is unrelated to the error type
