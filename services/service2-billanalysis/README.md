# Service 2: Bill Analysis Backend — Complete Explanation

## 📋 Overview

**Service 2** is a **Flask-based REST API** that analyzes medical bills for billing errors. It processes uploaded bill and EOB (Explanation of Benefits) documents, extracts key data via OCR, performs error detection checks, and generates dispute letters.

---

## 🏗️ Architecture

### Layered Design
```
Routes (HTTP API)
    ↓
Services (Business Logic)
    ├── OCR Service (AWS Textract wrapper)
    ├── Error Detection Engine (orchestrates 4 detectors)
    ├── Letter Builder (generates dispute letters)
    └── RAG Client (calls Service 3 for explanations)
    ↓
Models (SQLAlchemy ORM)
    ├── Session (tracks user workflow state)
    ├── ExtractedField (bill data extracted by OCR)
    ├── LineItem (individual charges)
    └── AnalysisResult (detected errors)
    ↓
Database (SQLite dev, PostgreSQL prod)
```

---

## 📁 Directory Structure

```
service2-billanalysis/
├── app.py                  # Flask application factory
├── config.py               # Environment configuration
├── models.py               # SQLAlchemy ORM models
├── extensions.py           # Database initialization
│
├── routes/                 # HTTP endpoint handlers
│   ├── health.py           # GET  /health (service status)
│   ├── upload.py           # POST /upload (OCR + persist)
│   ├── confirm.py          # POST /confirm (user corrections)
│   ├── analyse.py          # POST /analyse (error detection)
│   └── letter.py           # POST /letter, GET /download (dispute letters)
│
├── detectors/              # Error detection strategy pattern
│   ├── base.py             # BaseDetector abstract class
│   ├── duplicate.py        # Duplicate charge detector
│   ├── medicare_rate.py    # Medicare rate detector
│   ├── eob_reconciliation.py # EOB mismatch detector
│   └── no_surprises.py     # Surprise billing detector
│
├── services/               # Business logic
│   ├── ocr.py              # AWS Textract wrapper
│   ├── engine.py           # Error detection orchestrator
│   ├── letter_builder.py   # Dispute letter generation
│   └── rag_client.py       # Service 3 HTTP client
│
└── tests/                  # Unit tests
    ├── test_upload.py
    ├── test_detectors.py
    └── test_analyse.py
```

---

## 🎯 Core Components

### 1. **Application Factory** (`app.py`)

```python
def create_app(config_name: str = None) -> Flask:
    """
    Factory pattern for Flask app initialization.
    - Loads environment-specific config
    - Initializes database
    - Registers all blueprints (route handlers)
    """
    app = Flask(__name__)
    app.config.from_object(config[config_name])
    db.init_app(app)
    # Register blueprints...
    return app
```

**Why factory pattern?**
- Allows testing with different configs
- Enables multiple app instances
- Separates concerns

---

### 2. **Configuration** (`config.py`)

Three environments: **Development**, **Production**, and **Default**

| Setting | Purpose |
|---------|---------|
| `SQLALCHEMY_DATABASE_URI` | SQLite (dev) or PostgreSQL (prod) |
| `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY` | Textract credentials |
| `SERVICE3_URL` | RAG service endpoint |
| `MAX_FILE_SIZE_MB`, `MAX_PAGE_COUNT` | Upload limits (FR-01) |
| `OCR_CONFIDENCE_THRESHOLD` | 0.80 for yellow-highlight flagging |

---

### 3. **Database Models** (`models.py`)

#### **Session**
Represents one user's entire workflow from upload → letter generation.

```python
class Session(db.Model):
    session_id: str          # UUID, primary key
    status: str              # extracted → confirmed → analysed → letter_generated
    created_at: DateTime     # Auto-set on creation
    updated_at: DateTime     # Auto-updated on any change
    
    # Relationships
    extracted_fields: list[ExtractedField]  # Cascade delete
    analysis_results: list[AnalysisResult]  # Cascade delete
    letter: DisputeLetter                   # One-to-one
```

**State Machine (FR-26):**
```
[EXTRACTED] --confirm--> [CONFIRMED] --analyse--> [ANALYSED] --letter--> [LETTER_GENERATED]
```
- Any request that skips a step → HTTP 400 `NOT_CONFIRMED`

---

#### **ExtractedField**
Stores OCR-extracted bill data and user corrections.

```python
class ExtractedField(db.Model):
    id: int
    session_id: str (FK)
    
    # Main fields
    patient_name: str       # From OCR
    provider_name: str      # From OCR
    date_of_service: str    # From OCR
    total_billed: Decimal   # From OCR
    
    # Line items stored as relationship
    line_items: list[LineItem]  # Each charge
```

**Key design decision:**
- `extracted_value` is never overwritten
- User corrections stored in `corrected_value`
- Audit trail preserved

---

#### **LineItem**
One row per charge on the bill or EOB.

```python
class LineItem(db.Model):
    id: int
    extracted_field_id: int (FK)
    
    line_number: int        # Row position (1, 2, 3...)
    cpt_code: str           # Procedure code (e.g., "99213")
    description: str        # Procedure name
    quantity: int           # Units billed
    unit_price: Decimal     # Price per unit
    amount: Decimal         # quantity × unit_price
    date: str               # Service date (if different from session date)
    source: str             # 'bill' or 'eob'
```

---

#### **AnalysisResult**
Stores detected billing errors after analysis.

```python
class AnalysisResult(db.Model):
    result_id: int
    session_id: str (FK)
    
    module: str                      # "duplicate_charge"
    error_type: str                  # "Duplicate Charge"
    description: str                 # Full error details
    line_items_affected: list[int]   # [1, 3] (line numbers)
    estimated_dollar_impact: Decimal # USD savings if fixed
    confidence: str                  # 'high' | 'medium' | 'low'
    explanation: str                 # RAG-generated (nullable)
```

---

### 4. **OCR Service** (`services/ocr.py`)

Wraps **AWS Textract AnalyzeDocument** API.

```python
class OCRService:
    def extract(self, file_bytes: bytes, source: str = "bill") -> dict:
        """
        Input: Raw PDF bytes
        Output: Structured dict with extracted fields and line items
        """
        response = textract.analyze_document(
            Document={"Bytes": file_bytes},
            FeatureTypes=["TABLES", "FORMS"]
        )
        
        # Extract key-value pairs (forms)
        kv_pairs = self._extract_key_value_pairs(response)
        
        # Extract table rows (line items)
        line_items = self._extract_line_items(response, source)
        
        # Map field names
        return {
            "patient_name": ...,
            "provider_name": ...,
            "date_of_service": ...,
            "total_billed": ...,
            "line_items": [...]
        }
```

**Features:**
- Uses `TABLES` feature for line items
- Uses `FORMS` feature for key-value pairs (patient, provider, etc.)
- Fuzzy field matching (handles "Patient Name", "Patient", "Name")
- Currency parsing ($1,234.56 → 1234.56)
- **Never populates CPT descriptions** (AMA copyright)

---

### 5. **Error Detection Engine** (`services/engine.py`)

**Strategy pattern:** Orchestrates four pluggable detectors.

```python
class ErrorDetectionEngine:
    def run(self, confirmed_fields: dict) -> dict:
        """
        Args: confirmed_fields (user-corrected bill data)
        
        Returns:
        {
            "results": [DetectionResult, ...],
            "all_clear": bool,
            "module_summary": {"duplicate_charge": 2, "medicare_rate": 1}
        }
        """
        all_results = []
        
        for detector in self._detectors:
            detector_results = detector.run(confirmed_fields)
            all_results.extend(detector_results)
        
        return {
            "results": all_results,
            "all_clear": len(all_results) == 0,
            "module_summary": {...}
        }
```

**Why pluggable?**
- New detector? Just subclass `BaseDetector` and add to `_build_detectors()`
- No changes to existing detectors or engine needed
- Satisfies **FR-15** (extensibility without modification)

---

### 6. **Detectors** (`detectors/`)

All detectors return `list[DetectionResult]`. Each detector is independent.

#### **DuplicateChargeDetector** (`duplicate.py`)
Flags when the same CPT code appears multiple times on the same date.

```python
class DuplicateChargeDetector(BaseDetector):
    module_name = "duplicate_charge"
    
    def run(self, confirmed_fields: dict) -> list[DetectionResult]:
        # Group bill items by (cpt_code, date)
        # If 2+ items in a group → duplicate
        # Each extra item produces one DetectionResult
```

**Example:**
```
Line 1: CPT 99213 on 2024-01-15, $150
Line 3: CPT 99213 on 2024-01-15, $150  ← Duplicate!
Line 2: CPT 99214 on 2024-01-15, $200  ← OK (different code)

Result: Duplicate found, line_items_affected=[1, 3], estimated_dollar_impact=$150
```

---

#### **MedicareRateDetector** (`medicare_rate.py`)
Flags charges exceeding Medicare allowed amounts.

```python
class MedicareRateDetector(BaseDetector):
    module_name = "medicare_rate"
    
    def run(self, confirmed_fields: dict) -> list[DetectionResult]:
        # For each bill line item:
        #   1. Look up CPT code in Medicare fee schedule
        #   2. If billed amount > allowed amount → flag
        #   3. Estimate savings (charged - allowed)
```

---

#### **EOBReconciliationDetector** (`eob_reconciliation.py`)
Flags mismatches between bill and EOB.

```python
class EOBReconciliationDetector(BaseDetector):
    module_name = "eob_reconciliation"
    
    def run(self, confirmed_fields: dict) -> list[DetectionResult]:
        # If EOB present:
        #   For each bill line item, find matching EOB line
        #   If amount billed ≠ amount covered by insurance → flag
        # If no EOB → return []
```

---

#### **NoSurprisesActDetector** (`no_surprises.py`)
Flags charges that violate the No Surprises Act (surprise billing).

```python
class NoSurprisesActDetector(BaseDetector):
    module_name = "no_surprises"
    
    def run(self, confirmed_fields: dict) -> list[DetectionResult]:
        # Heuristics:
        #   - Out-of-network provider + high deviation from average rate
        #   - Emergency service + out-of-network
        #   - Assisted reproductive technology + certain conditions
```

---

### 7. **HTTP Routes**

#### **GET /health**
Simple liveness check (2-second response guarantee).

```python
@health_bp.get("/health")
def health():
    return {
        "status": "ok",
        "service": "bill-analysis",
        "version": "1.0.0"
    }, 200
```

---

#### **POST /upload**
Accepts bill PDF (required) + EOB PDF (optional). Runs OCR, creates session.

**Request:**
```
POST /upload
Content-Type: multipart/form-data

bill  ← PDF file (required)
eob   ← PDF file (optional)
```

**Response 200 (success):**
```json
{
  "session_id": "a1b2c3d4-...",
  "status": "extracted",
  "extracted_fields": {
    "patient_name": "John Doe",
    "provider_name": "Acme Hospital",
    "date_of_service": "2024-01-15",
    "total_billed": "1500.00",
    "line_items": [
      {
        "line_number": 1,
        "cpt_code": "99213",
        "description": "Office visit",
        "quantity": 1,
        "unit_price": "150.00",
        "amount": "150.00",
        "confidence": 0.95,
        "source": "bill"
      },
      ...
    ]
  },
  "rag_available": false
}
```

**Response 400 (error):**
```json
{
  "error_code": "INVALID_FILE_TYPE",
  "message": "File must be PDF. Received: image/jpeg",
  "session_id": null
}
```

**Validation (FR-01, FR-02, FR-03, FR-04, FR-05):**
- Bill file must be present
- Both files must be PDF
- File size ≤ 10 MB (configurable)
- Page count ≤ 20 (configurable)

---

#### **POST /confirm**
User reviews extracted fields, optionally corrects them.

**Request:**
```json
{
  "session_id": "a1b2c3d4-...",
  "corrections": {
    "patient_name": "Jane Doe",  # Changed from "John Doe"
    "line_items": [
      {
        "line_number": 1,
        "amount": "140.00"  # Corrected from 150.00
      }
    ]
  }
}
```

**Response 200:**
```json
{
  "session_id": "a1b2c3d4-...",
  "status": "confirmed",
  "message": "Session confirmed and ready for analysis"
}
```

**State Machine:**
- Only callable when `status == "extracted"`
- Advances status to `"confirmed"`

---

#### **POST /analyse**
Runs all four detectors on confirmed data. Calls Service 3 for explanations (10-second timeout).

**Request:**
```json
{
  "session_id": "a1b2c3d4-..."
}
```

**Response 200 (full, with explanations):**
```json
{
  "session_id": "a1b2c3d4-...",
  "status": "analysed",
  "errors": [
    {
      "error_id": "err_1",
      "module": "duplicate_charge",
      "error_type": "Duplicate Charge",
      "description": "CPT 99213 appears 2 times on 2024-01-15...",
      "line_items_affected": [1, 3],
      "estimated_dollar_impact": 150.00,
      "confidence": "high",
      "explanation": "This charge appears twice in the billing records...",
      "citations": ["Medicare Billing Rule 123", "CMS Guidance Doc"]
    },
    ...
  ],
  "total_errors": 3,
  "total_savings": 450.00,
  "all_clear": false,
  "rag_available": true
}
```

**Response 200 (partial, Service 3 timeout):**
```json
{
  "session_id": "a1b2c3d4-...",
  "errors": [
    {
      "error_id": "err_1",
      "module": "duplicate_charge",
      "error_type": "Duplicate Charge",
      "description": "CPT 99213 appears 2 times...",
      "line_items_affected": [1, 3],
      "estimated_dollar_impact": 150.00,
      "confidence": "high",
      "explanation": null,  # ← Timed out
      "citations": []
    },
    ...
  ],
  "total_errors": 3,
  "total_savings": 450.00,
  "all_clear": false,
  "rag_available": false
}
```

**Resilience (NFR-02, NFR-18):**
- Service 3 times out after 10 seconds
- Response still returns errors with `explanation: null`
- Frontend can show "explanations unavailable" message
- Partial response is acceptable

---

#### **POST /letter**
Generates a dispute letter based on detected errors.

**Request:**
```json
{
  "session_id": "a1b2c3d4-..."
}
```

**Response 200:**
```json
{
  "session_id": "a1b2c3d4-...",
  "status": "letter_generated",
  "letter_id": "ltr_1",
  "preview": "Dear [Provider],\n\nWe have identified the following billing errors...",
  "download_url": "/letter/download/ltr_1"
}
```

**State Machine:**
- Only callable when `status == "analysed"`
- Advances status to `"letter_generated"`

---

#### **GET /letter/download/{letter_id}**
Returns the generated dispute letter as a PDF.

**Response 200:**
```
Content-Type: application/pdf
Content-Disposition: attachment; filename="dispute_letter_ltr_1.pdf"

[PDF binary data]
```

---

## 🔄 Request Lifecycle

```
1. User uploads bill + EOB PDFs
   ↓
   POST /upload
   ├─ Validate files (size, type, page count)
   ├─ Run OCR on each PDF (AWS Textract)
   ├─ Extract: patient, provider, date, total, line items
   ├─ Create Session with status=extracted
   ├─ Persist ExtractedField + LineItem rows
   └─ Return: session_id + extracted_fields

2. User reviews extracted data
   ↓
   POST /confirm
   ├─ Receive user corrections
   ├─ Update ExtractedField + LineItem rows
   ├─ Advance status → confirmed
   └─ Return: status=confirmed

3. User requests error analysis
   ↓
   POST /analyse
   ├─ Load confirmed_fields from DB
   ├─ Run ErrorDetectionEngine:
   │  ├─ DuplicateChargeDetector.run()
   │  ├─ MedicareRateDetector.run()
   │  ├─ EOBReconciliationDetector.run()
   │  └─ NoSurprisesActDetector.run()
   ├─ Consolidate results
   ├─ For each result, call Service 3 (RAG):
   │  ├─ "Explain this error to a patient" (with 10-sec timeout)
   │  ├─ Populate explanation + citations
   │  └─ Or return null explanation if timeout
   ├─ Persist AnalysisResult rows
   ├─ Advance status → analysed
   └─ Return: errors[] + total_savings

4. User generates dispute letter
   ↓
   POST /letter
   ├─ Load errors + session data from DB
   ├─ LetterBuilder.generate() builds the PDF
   ├─ Persist DisputeLetter row
   ├─ Advance status → letter_generated
   └─ Return: download_url

5. User downloads letter
   ↓
   GET /letter/download/{letter_id}
   └─ Return PDF binary
```

---

## 🧪 Testing Strategy

### Unit Tests (`tests/`)

**test_upload.py:**
- Valid bill + EOB upload
- Missing bill file (error)
- Invalid file type (error)
- File too large (error)
- Page count exceeds limit (error)

**test_detectors.py:**
- DuplicateChargeDetector with duplicate CPT
- MedicareRateDetector with overbilled amount
- EOBReconciliationDetector with bill/EOB mismatch
- NoSurprisesActDetector with surprise billing scenario

**test_analyse.py:**
- POST /analyse with valid session_id
- Session not found (404)
- Session not confirmed (400)
- Service 3 timeout (partial response)

---

## 📊 Key Design Decisions

| Decision | Rationale |
|----------|-----------|
| **Factory pattern** | Testability + multi-config support |
| **State machine** | Enforce correct workflow (extracted → confirmed → analysed → letter) |
| **Strategy pattern (detectors)** | Extensibility without modification (FR-15) |
| **Pluggable RAG client** | Decouple Service 3 dependency, enable graceful degradation |
| **Cascade delete** | Deleting a session auto-deletes related records |
| **Never overwrite extracted_value** | Audit trail + recoverability |
| **10-sec RAG timeout** | Acceptable latency trade-off (NFR-18) |
| **Partial response on RAG timeout** | Users still see errors, just without explanations (NFR-02) |

---

## 🚀 Running the Backend

### Local Development
```bash
# Install dependencies
pip install -r requirements.txt

# Set environment
export FLASK_ENV=development
export DATABASE_URL=sqlite:///medicheck_dev.db

# Run server
flask run --port 5001
```

### Production (Render)
```bash
# Procfile defines:
web: gunicorn app:app --bind 0.0.0.0:$PORT

# Environment:
FLASK_ENV=production
DATABASE_URL=postgresql://...
```

---

## 📝 Requirements Mapping

| Requirement | Implementation |
|-------------|-----------------|
| **FR-01** | upload.py: validate file size ≤ 10MB |
| **FR-02** | upload.py: validate PDF file type |
| **FR-03** | upload.py: accept bill + optional EOB |
| **FR-04** | upload.py: return session_id + extracted fields |
| **FR-05** | upload.py: validate page count ≤ 20 |
| **FR-10** | engine.py: run all 4 detectors, no silent omissions |
| **FR-11** | duplicate.py: flag duplicate (CPT, DOS) pairs |
| **FR-15** | engine.py + base.py: pluggable detectors (strategy) |
| **FR-16** | base.py: validate all 6 required fields per result |
| **FR-25** | models.py: sessions retained 24+ hours (TTL job cleanup) |
| **FR-26** | models.py: session state machine with transitions |
| **NFR-01** | analyse.py: return < 30 errors per analysis |
| **NFR-02** | analyse.py: partial response if Service 3 times out |
| **NFR-04** | health.py: respond within 2 seconds |
| **NFR-12** | health.py: health check endpoint implemented first |
| **NFR-17** | analyse.py: HTTP 400 if session not confirmed |
| **NFR-18** | rag_client.py: 10-second timeout on Service 3 |

---

## 🎯 Next Steps

1. **Run the backend:** `flask run --port 5001`
2. **Test upload:** `POST /upload` with sample bill PDF
3. **Check health:** `GET /health`
4. **Review database:** `sqlite3 instance/medicheck_dev.db`
5. **Run unit tests:** `pytest tests/`
6. **Integrate with Service 3:** Ensure RAG client points to Service 3 endpoint

---

**Questions?** Check the inline comments in each file — they reference specific requirements (FR-*, NFR-*, US-*).
