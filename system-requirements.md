# MediCheck — System Requirements

**Project:** MediCheck — AI-Powered Healthcare Bill Accuracy & Dispute Assistant  
**Version:** 4.0  
**Sprint:** 1  
**Owner:** Member 2 (Scrum Master + Code Owner)  
**Status:** Draft — Traceability matrix to be completed once user stories are finalised

---

## Table of Contents

1. [Functional Requirements](#functional-requirements)
   - [FR — Document Upload](#fr--document-upload)
   - [FR — Field Confirmation](#fr--field-confirmation)
   - [FR — Error Detection](#fr--error-detection)
   - [FR — Knowledge-Grounded Explanations](#fr--knowledge-grounded-explanations)
   - [FR — Dispute Letter Generation](#fr--dispute-letter-generation)
   - [FR — Session Management](#fr--session-management)
2. [Non-Functional Requirements](#non-functional-requirements)
   - [NFR — Performance & Latency](#nfr--performance--latency)
   - [NFR — Security & Data Handling](#nfr--security--data-handling)
   - [NFR — Deployment & Availability](#nfr--deployment--availability)
   - [NFR — API Contract](#nfr--api-contract)
   - [NFR — UI & Accessibility](#nfr--ui--accessibility)
   - [NFR — Testing & CI/CD](#nfr--testing--cicd)
3. [Requirements Traceability Matrix](#requirements-traceability-matrix)

---

## Functional Requirements

### FR — Document Upload

**FR-01**  
The system shall accept PDF document uploads with a maximum file size of 10 MB and a maximum document length of 20 pages per file. Files exceeding either limit shall be rejected before processing begins.

**FR-02**  
The system shall extract structured text and key-value data from uploaded PDF documents automatically. The extraction output shall include at minimum: patient name, provider name, date of service, and all line items with their associated procedure codes and billed amounts. No manual data entry shall be required from the user to produce these fields.

**FR-03**  
The system shall support upload of two documents per session: one provider bill and one Explanation of Benefits (EOB). If the user attempts to trigger analysis with zero documents uploaded, the system shall return an error and refuse to proceed.

**FR-04**  
The system shall generate and return a unique session identifier upon successful document upload. The session identifier shall be a UUID and shall be included in the response body of every subsequent request that references that session.

**FR-05**  
The system shall validate every upload request and return an HTTP 400 response with a structured error body if the file is not a PDF, exceeds 10 MB, or exceeds 20 pages. The error body shall include at minimum an error code and a human-readable description of the specific validation failure.

---

### FR — Field Confirmation

**FR-06**  
The system shall display all extracted fields to the user on the field confirmation page before analysis is permitted. The page shall display at minimum: patient name, provider name, date of service, and all extracted line items. The user shall not be able to proceed to analysis without first visiting this page.

**FR-07**  
The system shall allow the user to edit any extracted field on the field confirmation page. Every edited value shall replace the original extracted value for all downstream processing. The original extracted value shall be retained separately in the data store for audit purposes.

**FR-08**  
Upon submission of confirmed fields, the system shall persist the confirmed data linked to the session identifier and return an HTTP 200 response. The system shall block any analysis request submitted for a session whose status is not yet confirmed, returning an HTTP 400 response in that case.

**FR-09**  
The system shall return an HTTP 404 response if a field confirmation submission references a session identifier that does not exist in the data store.

---

### FR — Error Detection

**FR-10**  
The system shall execute all four error detection checks against the confirmed bill data for every analysis request. The analysis response shall include a result — either an error finding or an explicit all-clear — for each of the four checks, with no check silently omitted from the output.

**FR-11**  
The duplicate charge detection check shall identify every instance where the same procedure code appears more than once for the same date of service within the confirmed provider bill line items. Each duplicate pair shall produce a separate error result in the analysis output.

**FR-12**  
The rate outlier detection check shall compare the billed amount for each procedure code against the CMS Physician Fee Schedule locality-adjusted Medicare rate. Any line item where the billed amount exceeds 300% of the applicable Medicare rate shall produce an error result. The error result shall include the billed amount, the applicable Medicare rate, and the percentage by which the billed amount exceeds it.

**FR-13**  
The EOB reconciliation check shall compare every line item in the confirmed provider bill against the confirmed EOB. Any discrepancy in procedure code, date of service, quantity, or billed amount shall produce a separate error result identifying the specific field that differs and the values recorded in each document.

**FR-14**  
The No Surprises Act violation check shall produce an error result for every line item where the provider is recorded as out-of-network and the service context meets the federal criteria for balance billing prohibition — specifically, services rendered at an in-network facility or constituting emergency care. The error result shall identify the provider, the network status recorded, and the applicable federal protection.

**FR-15**  
The error detection pipeline shall be designed such that a new detection check can be added and executed alongside the existing four checks without modifying any existing check or any part of the pipeline orchestration logic. This shall be demonstrated by the ability to add a fifth check during development without touching existing check code.

**FR-16**  
Every error result produced by the analysis shall include the following six fields: the name of the detection check that produced it, the category of error, a plain-English description of the issue, the line items affected (by line number and procedure code), an estimated dollar impact expressed in USD, and a confidence level of high, medium, or low. Any error result missing one or more of these fields shall be treated as a system defect.

---

### FR — Knowledge-Grounded Explanations

**FR-17**  
The system shall maintain a knowledge base populated from the following four publicly available CMS sources: the CMS Physician Fee Schedule, ICD-10-CM coding guidelines, No Surprises Act regulatory text and CMS guidance, and the CMS Procedure-to-RVU crosswalk. All four sources shall be present and queryable before the explanation service is considered ready for use.

**FR-18**  
For each error result in the analysis output, the system shall produce a plain-English explanation retrieved from the knowledge base. Each explanation shall include at least one citation specifying the source document name and the relevant section or page. An explanation response that contains no citation shall be treated as a system defect.

**FR-19**  
The explanation service shall return an error response — rather than a generated explanation — for any query that is determined to be outside the medical billing domain. The domain boundary shall be enforced for every request, with no exceptions based on phrasing or framing of the query.

**FR-20**  
The knowledge-grounded explanation capability shall be hosted as a service independent of the error detection capability. A redeployment or restart of the explanation service shall have no effect on the availability or behaviour of the error detection pipeline, and vice versa.

---

### FR — Dispute Letter Generation

**FR-21**  
The system shall generate a formal dispute letter on request for any session that has completed analysis. The letter shall be produced in both Word (.docx) and PDF formats. Both files shall be available for download within the same request response, with no additional user action required beyond initiating the letter generation request.

**FR-22**  
The generated dispute letter shall contain all of the following: the patient's name and insurance member ID, the provider's name and identifier, the session reference identifier, the date the letter was generated, a numbered list of every detected error including the procedure code, billed amount, estimated overcharge in USD, and the specific regulatory citation that supports the dispute, a total estimated overcharge summed across all errors, and a formal written dispute request paragraph. A letter missing any of these elements shall be treated as a system defect.

**FR-23**  
Both the Word and PDF versions of the dispute letter shall be retrievable at any point within the session without requiring the user to re-upload documents, re-confirm fields, or repeat the analysis.

---

### FR — Session Management

**FR-24**  
The system shall not require users to register an account, provide an email address, or supply any personal credentials in order to use the service. A session shall be initiated solely by a successful document upload, with no prior authentication step.

**FR-25**  
The system shall persist all session data — uploaded documents, confirmed field values, analysis results, and generated dispute letters — in a durable relational data store. Session data shall remain retrievable by session identifier for a minimum of 24 hours after the session is created.

**FR-26**  
Each session shall have a status field that reflects its current stage in the workflow. The status shall transition through the following stages in order, and only in this order: document uploaded → fields confirmed → analysis complete → letter generated. A request that would cause a status to transition out of sequence shall be rejected with an HTTP 400 response.

**FR-27**  
At the point of session creation, the system shall display the session identifier to the user and present a clear message stating that the session identifier is the sole means of referencing their results, and that results cannot be recovered if it is lost. This message shall remain visible on screen until the user explicitly proceeds to the next step.

---

## Non-Functional Requirements

### NFR — Performance & Latency

**NFR-01**  
The system shall return a complete analysis response — including all four detection check results and all knowledge-grounded explanations — within 30 seconds of receiving a valid analysis request for a document of up to 20 pages, measured under normal operating conditions with no more than 10 concurrent users.

**NFR-02**  
If the explanation service does not return a response within 10 seconds of being called, the bill analysis service shall abandon the explanation request and return a partial response to the caller containing the detection results and a flag set to false indicating that explanations are unavailable. The caller shall receive this partial response within 2 seconds of the 10-second timeout elapsing.

**NFR-03**  
The system shall return a session identifier to the caller within 60 seconds of receiving a document upload request for a document of up to 20 pages, under normal operating conditions.

**NFR-04**  
Each health check endpoint shall return an HTTP 200 response within 2 seconds of being called under normal operating conditions. A response time exceeding 2 seconds shall be treated as a health check failure by the CI/CD pipeline.

**NFR-05**  
The explanation service shall achieve a median (p50) end-to-end response latency of under 10 seconds and a 95th percentile (p95) latency of under 20 seconds. These targets shall be validated against a minimum of 15 test queries drawn from the knowledge base evaluation set during Sprint 5.

---

### NFR — Security & Data Handling

**NFR-06**  
No real patient data shall be used at any stage of development, testing, or demonstration. All test and demonstration documents shall be generated from the synthetic data specification. Every synthetic document shall include a visible disclaimer identifying it as synthetic on the first page.

**NFR-07**  
All credentials and secret configuration values — including API keys, database connection strings, and inter-service URLs — shall be stored as environment variables. Zero secrets shall be present in any file committed to the source code repository at any time. A reference configuration file listing all required variable names without values shall be maintained in the repository root.

**NFR-08**  
All communication between the user's browser and the application, and all communication between services, shall use HTTPS. Any request received over plain HTTP shall be redirected to HTTPS or rejected.

**NFR-09**  
All service-to-service addresses shall be read from environment configuration at runtime. A code review check shall confirm that no service address is hardcoded in any committed file. Any pull request containing a hardcoded service address shall be blocked from merging.

**NFR-10**  
No copyrighted procedure code descriptions shall appear in any stored data, API response, user interface element, or generated document at any time. All detection and analysis logic shall reference procedure codes by their numeric identifier only, using publicly available CMS rate data. Compliance shall be verified as part of the code review process for every pull request touching detection or display logic.

---

### NFR — Deployment & Availability

**NFR-11**  
Each functional capability of the system shall be independently deployable. Redeploying one capability shall not cause downtime, a restart, or a configuration change in any other. Each deployable unit shall have its own publicly accessible URL and its own independently managed set of environment variables.

**NFR-12**  
Each backend service shall expose a health check endpoint at GET /health that returns HTTP 200 with a JSON body containing at minimum a status field set to "ok" and a service name field. This endpoint shall be implemented and responding before any other endpoint on that service is considered ready for use.

**NFR-13**  
The knowledge base used by the explanation service shall be stored on a persistent volume that survives service restarts. Following a restart, the explanation service shall be able to serve explanation requests without re-ingesting any knowledge base source document.

**NFR-14**  
The total infrastructure cost of running all deployed services shall not exceed $0 per month for a prototype deployment operating within free-tier hosting limits. A cost analysis comparing free-tier prototype costs against estimated production-scale costs shall be documented in the design and testing document.

---

### NFR — API Contract

**NFR-15**  
All inter-service request and response payloads shall use JSON with a Content-Type header of application/json. The schema for every inter-service payload — including all field names, types, and required versus optional status — shall be defined and documented in a single shared location. Any deviation between the documented schema and the actual payload sent or received shall be treated as a defect.

**NFR-16**  
All API endpoints shall return error responses in a consistent structure containing at minimum three fields: a machine-readable error code (string), a human-readable message (string), and the session identifier (string or null where not applicable). Every endpoint shall conform to this structure for all error conditions without exception.

**NFR-17**  
The system shall return HTTP 400 for any analysis request submitted before field confirmation is complete for that session. The system shall return HTTP 404 for any letter generation request submitted for a session that has no completed analysis results. Both conditions shall be tested as part of the integration test suite.

**NFR-18**  
Every outbound HTTP call from the bill analysis service to the explanation service shall specify an explicit timeout of 10 seconds. The absence of an explicit timeout on any such call shall constitute a code review failure and shall block the associated pull request from merging.

---

### NFR — UI & Accessibility

**NFR-19**  
The user interface shall apply a consistent visual design — including typography, colour palette, spacing, and component styling — across all four pages: document upload, field confirmation, error report, and dispute letter download. Visual inconsistencies between pages shall be treated as defects during review.

**NFR-20**  
Error report results shall communicate severity using both a colour indicator and a text label. High-impact errors (estimated dollar impact above $500) shall display in red with the label "High Impact". Medium-impact errors ($100–$500) shall display in amber with the label "Medium Impact". Informational findings (below $100) shall display in green with the label "Informational". All three severity levels shall be present and correctly applied in the test scenario output.

**NFR-21**  
Every input field on the field confirmation page shall have a visible label. Any required field that is left blank when the user attempts to proceed shall display an inline error message identifying the specific field and the reason it is required. The system shall prevent navigation to the analysis step until all required fields contain a non-empty value.

**NFR-22**  
The user interface shall be responsive and usable across common desktop, tablet, and mobile screen sizes without horizontal scrolling or overlapping content. Responsive behaviour shall be verified against at minimum three screen size categories — mobile, tablet, and desktop — as part of the Sprint 5 review.

---

### NFR — Testing & CI/CD

**NFR-23**  
The automated build and test pipeline shall execute on every pull request and every push to the main branch. The pipeline shall: install all dependencies, run the full unit and integration test suite, and run a lint check. Any pull request where one or more pipeline steps fail shall be blocked from merging to main without exception.

**NFR-24**  
On a successful pipeline run triggered by a push to main, all deployed services shall be automatically redeployed in sequence. Following redeployment, the pipeline shall call the health check endpoint of each backend service and verify it returns HTTP 200 within 5 seconds. The pipeline run shall be marked as failed if any health check does not return HTTP 200 within the 5-second window, and the failure shall be reported in the CI/CD run log.

**NFR-25**  
The test suite shall include a minimum of 15 unit tests distributed across all four error detection checks, with at least 3 tests per check: one test using input that should produce an error result (positive case), one test using input that should produce no error result (negative case), and one test using input at the exact boundary condition of the detection threshold (boundary case). The suite shall also include integration tests for the end-to-end analysis pipeline and smoke tests for all service health check endpoints.

**NFR-26**  
Every integration test that exercises a code path involving a call from the bill analysis service to the explanation service shall use a simulated response in place of a live HTTP call. The test suite shall pass in its entirety without requiring a running instance of the explanation service. Any integration test that makes a live HTTP call to another service shall be rejected in code review.

**NFR-27**  
A test coverage report shall be generated as part of the Sprint 5 test run and the summary shall be committed to the design and testing document. The line coverage across all four error detection checks shall be a minimum of 80%. A coverage result below 80% on any detection check shall constitute a Sprint 5 acceptance failure requiring remediation before code freeze.

---

## Requirements Traceability Matrix

*To be completed once user stories from Member 1 are finalised. The matrix will link each requirement to one or more user story IDs.*

| Requirement ID | Description (summary) | Category | Linked User Stories |
|---|---|---|---|
| FR-01 | PDF upload — max 10 MB and 20 pages; rejected before processing if exceeded | Functional | TBD |
| FR-02 | Automatic extraction of at minimum 4 field categories; no manual entry required | Functional | TBD |
| FR-03 | Two documents per session; analysis blocked if zero documents present | Functional | TBD |
| FR-04 | UUID session identifier returned in every subsequent response body | Functional | TBD |
| FR-05 | HTTP 400 with error code and description on upload validation failure | Functional | TBD |
| FR-06 | All extracted fields displayed before analysis; user cannot bypass this step | Functional | TBD |
| FR-07 | Every field editable; edited values replace originals; originals retained | Functional | TBD |
| FR-08 | Confirmed fields persisted; HTTP 400 if analysis requested before confirmation | Functional | TBD |
| FR-09 | HTTP 404 if confirmation references non-existent session | Functional | TBD |
| FR-10 | All four checks executed every time; each produces a result or explicit all-clear | Functional | TBD |
| FR-11 | Duplicate charge detection — each duplicate pair produces a separate result | Functional | TBD |
| FR-12 | Rate outlier — >300% of Medicare rate flagged; result includes amounts and percentage | Functional | TBD |
| FR-13 | EOB reconciliation — each field discrepancy produces a separate result | Functional | TBD |
| FR-14 | NSA violation — result identifies provider, network status, and applicable protection | Functional | TBD |
| FR-15 | Fifth check addable without modifying existing checks or pipeline logic | Functional | TBD |
| FR-16 | Every error result includes all six required fields; missing field = defect | Functional | TBD |
| FR-17 | All four CMS sources present and queryable before service is ready | Functional | TBD |
| FR-18 | Each explanation includes at least one citation; zero citations = defect | Functional | TBD |
| FR-19 | Out-of-domain queries return error response; no exceptions | Functional | TBD |
| FR-20 | Explanation service restart has no effect on detection pipeline | Functional | TBD |
| FR-21 | Both Word and PDF produced and available for download in single request | Functional | TBD |
| FR-22 | Letter contains all required elements; any missing element = defect | Functional | TBD |
| FR-23 | Both formats retrievable without repeating any prior step | Functional | TBD |
| FR-24 | No registration or credentials required; session initiated by upload only | Functional | TBD |
| FR-25 | All session data retrievable by session ID for minimum 24 hours | Functional | TBD |
| FR-26 | Session status transitions in defined order; out-of-sequence requests return HTTP 400 | Functional | TBD |
| FR-27 | Session ID and recovery warning displayed before user proceeds from upload | Functional | TBD |
| NFR-01 | Full analysis response within 30 seconds; up to 20 pages; up to 10 concurrent users | Performance | TBD |
| NFR-02 | Partial response returned within 2 seconds of 10-second explanation timeout | Performance | TBD |
| NFR-03 | Session identifier returned within 60 seconds of upload request | Performance | TBD |
| NFR-04 | Health check response within 2 seconds; exceeding limit = pipeline failure | Performance | TBD |
| NFR-05 | Explanation latency p50 <10s, p95 <20s; validated over minimum 15 queries | Performance | TBD |
| NFR-06 | Synthetic data only; every test document includes visible disclaimer | Security | TBD |
| NFR-07 | Zero secrets in repository; reference config file in repo root | Security | TBD |
| NFR-08 | All communication over HTTPS; plain HTTP rejected or redirected | Security | TBD |
| NFR-09 | No hardcoded service addresses; violation blocks pull request | Security | TBD |
| NFR-10 | No copyrighted CPT descriptions anywhere; verified in every relevant PR | Security | TBD |
| NFR-11 | Each capability independently deployable; own URL and environment config | Deployment | TBD |
| NFR-12 | GET /health returns HTTP 200 with status and service name before other endpoints ready | Deployment | TBD |
| NFR-13 | Knowledge base survives restarts; explanation service ready without re-ingestion | Deployment | TBD |
| NFR-14 | Prototype cost $0/month; free-tier vs production cost analysis documented | Deployment | TBD |
| NFR-15 | All inter-service payloads JSON; schema defined in one place; deviation = defect | API Contract | TBD |
| NFR-16 | All error responses include error code, message, and session ID; no exceptions | API Contract | TBD |
| NFR-17 | HTTP 400 before confirmation; HTTP 404 for missing results; both integration-tested | API Contract | TBD |
| NFR-18 | All explanation service calls have explicit 10-second timeout; missing timeout blocks PR | API Contract | TBD |
| NFR-19 | Consistent design across all four pages; inconsistencies treated as defects | UI | TBD |
| NFR-20 | Three severity levels with correct colour and text label; verified in test scenario output | UI | TBD |
| NFR-21 | All fields labelled; required fields block progression until non-empty | UI | TBD |
| NFR-22 | Responsive across mobile, tablet, desktop; verified against all three in Sprint 5 review | UI | TBD |
| NFR-23 | Pipeline runs on every PR and push to main; failing step blocks merge without exception | Testing/CI/CD | TBD |
| NFR-24 | Auto-deploy on passing main; health checks within 5 seconds post-deploy; failure logged | Testing/CI/CD | TBD |
| NFR-25 | Minimum 15 unit tests; 3 per check (positive, negative, boundary); plus integration and smoke tests | Testing/CI/CD | TBD |
| NFR-26 | All inter-service integration tests use simulated responses; live calls rejected in review | Testing/CI/CD | TBD |
| NFR-27 | Coverage report committed; minimum 80% per detection check; below 80% = Sprint 5 failure | Testing/CI/CD | TBD |
