# MediCheck — Requirements & User Stories

**Project:** MediCheck — AI-Powered Healthcare Bill Accuracy & Dispute Assistant  
**Version:** 1.0  
**Sprint:** 1  
**Status:** In Progress — User Stories Complete

---

## Table of Contents

1. [Personas](#personas)
2. [User Stories](#user-stories)
   - [Persona 1 — First-Time Patient (Uploading a Bill)](#persona-1--first-time-patient-uploading-a-bill)
   - [Persona 2 — Disputing Patient (Known Error)](#persona-2--disputing-patient-known-error)
   - [Persona 3 — Developer (API Consumer)](#persona-3--developer-api-consumer)
3. [User Journey](#user-journey) *(coming Sprint 1)*
4. [System Requirements](#system-requirements) *(coming Sprint 1)*
5. [Requirements Traceability Matrix](#requirements-traceability-matrix) *(coming Sprint 1)*

---

## Personas

| ID | Name | Description |
|----|------|-------------|
| P1 | First-Time Patient | A patient who has received a medical bill and/or EOB and has no prior experience reviewing billing accuracy. They need clear guidance and plain-English output. |
| P2 | Disputing Patient | A patient who already suspects or has identified a billing error and wants to generate a formal, regulation-backed dispute letter quickly. |
| P3 | API Developer | A developer integrating MediCheck's analysis capabilities into another application, patient portal, or automated workflow. They interact exclusively via the REST API. |

---

## User Stories

### Persona 1 — First-Time Patient (Uploading a Bill)

---

**US-01**  
*As a first-time patient, I want to upload my medical bill as a PDF so that MediCheck can analyse it without me needing to manually enter any data.*

**Acceptance Criteria:**
- User can upload a PDF from their device via a file picker on the Home/Upload page
- The system accepts PDFs up to 20 pages
- A loading indicator is displayed while the document is being processed
- If the file is not a PDF or exceeds the size limit, a clear error message is shown

---

**US-02**  
*As a first-time patient, I want to see the key fields extracted from my bill displayed on screen so that I can verify the information is correct before analysis begins.*

**Acceptance Criteria:**
- Extracted fields (patient name, provider name, date of service, line items with CPT codes and amounts, total billed) are displayed on the Field Confirmation page
- Each field is editable inline
- A "Confirm & Analyse" button is clearly visible and only becomes active once the user has reviewed the fields

---

**US-03**  
*As a first-time patient, I want to edit any incorrectly extracted field before submitting for analysis so that errors in OCR do not produce inaccurate results.*

**Acceptance Criteria:**
- Any extracted field can be clicked and edited
- Changes are visually indicated (e.g. highlighted border)
- Edited values are persisted when the user proceeds to analysis

---

**US-04**  
*As a first-time patient, I want to receive my analysis results within 30 seconds of confirming my fields so that I do not have to wait an unreasonable amount of time.*

**Acceptance Criteria:**
- Analysis results are returned and displayed within 30 seconds for documents up to 20 pages under normal load
- A progress indicator is displayed during analysis
- If the 30-second threshold is exceeded, a timeout message is shown with a retry option

---

**US-05**  
*As a first-time patient, I want the error report to use plain English and colour-coding so that I can understand the findings without medical billing expertise.*

**Acceptance Criteria:**
- Each detected error is shown as a card with a colour indicator: red (high impact, >$500 estimated dollar impact), amber (medium, $100–$500), green (informational, <$100)
- Each card includes: error type, plain-English description, line items affected, and estimated dollar impact
- No unexplained medical codes or jargon appear in the card without accompanying explanation

---

**US-06**  
*As a first-time patient, I want each error to include an explanation grounded in official regulations so that I understand why the charge is flagged and can trust the result.*

**Acceptance Criteria:**
- Each error card includes a RAG-generated plain-English explanation
- Each explanation includes at least one source citation (e.g. CMS Physician Fee Schedule, No Surprises Act)
- The source document name and section are displayed alongside the explanation

---

**US-07**  
*As a first-time patient, I want to upload both my provider bill and my Explanation of Benefits (EOB) together so that MediCheck can cross-reference them for discrepancies.*

**Acceptance Criteria:**
- The upload page accepts two PDF uploads: one for the provider bill and one for the EOB
- Both documents are processed and their line items are cross-referenced during analysis
- The EOB reconciliation module flags any line items that appear in one document but not the other, or where amounts differ

---

**US-08**  
*As a first-time patient, I want to be told if my provider is out-of-network in a situation where the No Surprises Act protects me so that I know I may not owe the billed amount.*

**Acceptance Criteria:**
- If Module 4 detects an NSA violation, a clearly labelled error card is shown
- The card explains what the No Surprises Act is and why it applies to the patient's situation
- The estimated dollar impact reflects the amount the patient should not be liable for

---

### Persona 2 — Disputing Patient (Known Error)

---

**US-09**  
*As a disputing patient, I want to download a pre-written dispute letter in Word format so that I can customise it before sending it to my insurer or provider.*

**Acceptance Criteria:**
- A "Download Word" button is available on the results page after analysis completes
- The downloaded .docx file contains: patient details, provider details, a summary of each detected error with the relevant CPT codes and amounts, regulatory citations, and a formal dispute request
- The file opens correctly in Microsoft Word and Google Docs

---

**US-10**  
*As a disputing patient, I want to download a dispute letter as a PDF so that I have a ready-to-print version to mail or attach to a formal complaint.*

**Acceptance Criteria:**
- A "Download PDF" button is available alongside the Word download button
- The PDF contains identical content to the Word version
- The PDF is formatted for standard 8.5×11 paper and renders clearly when printed

---

**US-11**  
*As a disputing patient, I want the dispute letter to cite the specific regulations that support my dispute so that the recipient cannot dismiss my claim without addressing the legal basis.*

**Acceptance Criteria:**
- Each error referenced in the letter includes the relevant regulatory citation (e.g. "No Surprises Act, 42 U.S.C. § 300gg-111", CMS Physician Fee Schedule locality rate)
- Citations are drawn from the RAG knowledge base and verified against source documents
- No citation is fabricated — if a source cannot be retrieved, the letter notes this explicitly

---

**US-12**  
*As a disputing patient, I want the dispute letter to include the estimated dollar impact of each error so that my insurer or provider can see the financial basis of my claim.*

**Acceptance Criteria:**
- Each error in the letter is accompanied by an estimated dollar impact
- The letter includes a total estimated overcharge amount summed across all detected errors
- Dollar amounts match those shown on the error report results page

---

**US-13**  
*As a disputing patient, I want to see a summary of all detected errors on one screen so that I can quickly decide which to include in my dispute before downloading the letter.*

**Acceptance Criteria:**
- The results page shows all detected errors in a scrollable list
- Each error shows: module name, error type, affected line items, estimated dollar impact, and confidence level
- The user can see all errors without navigating away from the results page

---

**US-14**  
*As a disputing patient, I want my uploaded documents and session data to be associated with a unique session ID so that I can reference my analysis if I return to the application.*

**Acceptance Criteria:**
- A unique session ID is generated and displayed on the results page
- Session data (uploaded documents, confirmed fields, analysis results, dispute letter) is persisted in the database linked to the session ID
- The session ID is included in the dispute letter header for reference

---

### Persona 3 — Developer (API Consumer)

---

**US-15**  
*As a developer, I want to POST a PDF to the /upload endpoint and receive a session ID in response so that I can track the document through the analysis pipeline.*

**Acceptance Criteria:**
- POST /upload accepts a multipart/form-data request with a PDF file
- Response returns a JSON object containing a session_id and status field
- HTTP 400 is returned with a descriptive error message if the file is missing, not a PDF, or exceeds size limits

---

**US-16**  
*As a developer, I want to POST confirmed field data to /confirm and receive confirmation that the data has been stored so that I can proceed to trigger analysis.*

**Acceptance Criteria:**
- POST /confirm accepts a JSON body with session_id and a confirmed_fields object
- Response returns HTTP 200 with {status: "confirmed", session_id: "..."} on success
- HTTP 404 is returned if the session_id does not exist

---

**US-17**  
*As a developer, I want to POST to /analyse and receive a structured JSON results payload so that I can parse and display the error findings in my own application.*

**Acceptance Criteria:**
- POST /analyse accepts a JSON body with session_id
- Response returns a structured JSON payload including: session_id, detected_errors (array of DetectionResult objects), explanations (RAG-grounded text with citations), and total_estimated_impact
- Each DetectionResult includes: module, error_type, description, line_items_affected, estimated_dollar_impact, confidence
- HTTP 400 is returned if the session has not been confirmed; HTTP 504 is returned if Service 3 times out

---

**US-18**  
*As a developer, I want all three services to expose a /health endpoint so that I can verify deployment status and integrate health checks into my monitoring tooling.*

**Acceptance Criteria:**
- GET /health on Service 2 returns HTTP 200 with {status: "ok", service: "bill-analysis"}
- GET /health on Service 3 returns HTTP 200 with {status: "ok", service: "rag"}
- Both endpoints respond within 2 seconds under normal load
- The CI/CD post-deploy step pings both endpoints and fails the pipeline if either returns non-200

---

**US-19**  
*As a developer, I want Service 2 to handle Service 3 timeouts gracefully so that a slow or unavailable RAG service does not crash the analysis pipeline.*

**Acceptance Criteria:**
- Service 2 applies a 10-second timeout to all calls to Service 3
- If Service 3 times out, Service 2 returns a partial results payload with analysis results and a flag indicating RAG explanations are unavailable
- No unhandled exception or 500 error is returned to the caller due to a Service 3 timeout

---

**US-20**  
*As a developer, I want to POST to /letter and receive both a Word and PDF download link so that I can present dispute letter download options to end users.*

**Acceptance Criteria:**
- POST /letter accepts a JSON body with session_id
- Response returns a JSON object with download URLs for both .docx and .pdf formats
- Both files are available for download immediately after the response is received
- HTTP 404 is returned if no analysis results exist for the given session_id

---

*Total user stories: 20 across 3 personas (P1: 8, P2: 6, P3: 6)*

---

## Future / Stretch User Stories

These stories were identified during Sprint 1 but are explicitly out of scope for the MVP. They are documented here as a backlog reference and will be noted in the design document's future work section.

---

**US-FW-01**  
*As a patient, I want to upload multiple provider bills at once (e.g. hospital bill, surgeon bill, and anaesthesiologist bill from the same procedure) so that MediCheck can detect duplicate charges that span across separate billing entities.*

**Why deferred:** The MVP upload flow is scoped to one provider bill and one EOB per session. Supporting multiple bills would require changes to the field confirmation UI (associating line items with their source bill), expanded database schema (multiple Documents per session), and a new cross-bill detection module. The four core detection modules already provide strong coverage against the most common billing errors within a single bill + EOB pair.

**Design note:** The `ErrorDetectionEngine` strategy pattern supports adding a Module 5 (cross-bill duplicate detector) without modifying existing modules. If implemented, it would compare CPT codes and service dates across all confirmed bills in a session, flagging same-code same-date charges from different providers for manual review rather than auto-flagging as errors (since split billing by multiple providers is sometimes legitimate).

---

---

**US-FW-02**  
*As a returning patient, I want to create an account using my email address so that I can log back in and access my previous analysis results and dispute letters without needing to retain my session identifier.*

**Why deferred:** The MVP uses an anonymous session model — users are identified solely by their session ID, with no registration or authentication required. Adding account management (email verification, password handling, login flows, forgotten credentials) is significant scope that does not contribute to any capstone rubric criterion and would consume Sprint 2 time reserved for OCR and infrastructure. The anonymous model also has a privacy benefit: no persistent link exists between a user's identity and their uploaded medical documents.

**Design note:** If implemented, account-based sessions would require an authentication layer in the bill analysis service, a user identity entity in the data store, and session ownership validation on all endpoints. The anonymous session model is a stated architectural constraint documented in FR-24 of the system requirements.

---

*Total future stories: 2*

---

## User Journey

*To be completed in Sprint 1 — see Step 1 development instructions.*

---

## System Requirements

*To be completed in Sprint 1 — see Step 1 development instructions.*

---

## Requirements Traceability Matrix

*To be completed once System Requirements are written.*
