# Service 2: Bill Analysis API — Complete Explanation

## 🎯 Purpose

Service 2 is the **core backend engine** of MediCheck. It:
1. **Extracts** medical bill data via OCR (AWS Textract)
2. **Stores** extracted data in a database
3. **Detects** 4 types of billing errors using pluggable detectors
4. **Coordinates** with Service 3 (RAG) for plain-English explanations
5. **Generates** dispute letters as PDFs

**Technology Stack:**
- Flask (Python web framework)
- SQLAlchemy (ORM for database)
- AWS Textract (OCR extraction)
- PostgreSQL / SQLite (database)
- Render (production deployment)

**Port:** 5001 (development), Render-deployed (production)

---

## 📁 Directory Structure

```
service2-billanalysis/
├── app.py                      # Flask application factory
├── config.py                   # Environment configuration
├── models.py                   # SQLAlchemy database models
├── extensions.py               # Database initialization
│
├── routes/                     # HTTP endpoint handlers
│   ├── __init__.py
│   ├── health.py               # GET /health (service status)
│   ├── upload.py               # POST /upload (OCR + persist)
│   ├── confirm.py              # POST /confirm (user corrections)
│   ├── analyse.py              # POST /analyse (error detection)
│   └── letter.py               # POST /letter + GET /download
│
├── detectors/                  # Error detection (Strategy pattern)
│   ├── __init__.py
│   ├── base.py                 # BaseDetector abstract class
│   ├── duplicate.py            # Duplicate charge detector
│   ├── medicare_rate.py        # Medicare rate detector
│   ├── eob_reconciliation.py   # EOB mismatch detector
│   └── no_surprises.py         # Surprise billing detector
│
├── services/                   # Business logic layer
│   ├── __init__.py
│   ├── ocr.py                  # AWS Textract wrapper
│   ├── mock_ocr.py             # Mock OCR for testing
│   ├── engine.py               # ErrorDetectionEngine orchestrator
│   ├── letter_builder.py       # Dispute letter generation
│   └── rag_client.py           # Service 3 HTTP client
│
├── tests/                      # Unit tests
│   ├── __init__.py
│   ├── test_upload.py
│   ├── test_detectors.py
│   └── test_analyse.py
│
├── instance/
│   └── medicheck_dev.db        # SQLite database (development only)
│
├── requirements.txt            # Python dependencies
├── requirements-dev.txt        # Development dependencies
├── Procfile                    # Render deployment config
├── runtime.txt                 # Python version
└── README.md                   # Service-specific README
```

---

## 🏭 Application Factory Pattern

### `app.py` — How the app starts

```python
from flask import Flask
from config import config
from extensions import db

def create_app(config_name: str = None) -> Flask:
    """
    Application factory — creates and configures Flask app.
    
    Usage:
        app = create_app()                    # Uses FLASK_ENV env var
        app = create_app('production')        # Explicit config
        app = create_app('development')       # For local dev
    """
    app = Flask(__name__)
    
    # 1. Load environment-specific config
    config_name = config_name or os.environ.get("FLASK_ENV", "default")
    app.config.from_object(config[config_name])
    
    # 2. Initialize database
    db.init_app(app)
    
    # 3. Register route blueprints
    from routes.health  import health_bp
    from routes.upload  import upload_bp
    from routes.confirm import confirm_bp
    from routes.analyse import analyse_bp
    from routes.letter  import letter_bp
    
    app.register_blueprint(health_bp)
    app.register_blueprint(upload_bp)
    app.register_blueprint(confirm_bp)
    app.register_blueprint(analyse_bp)
    app.register_blueprint(letter_bp)
    
    # 4. Create database tables
    with app.app_context():
        db.create_all()
    
    return app

# Entry point for flask run and gunicorn
app = create_app()

if __name__ == "__main__":
    app.run(debug=True, port=5000)
```

**Why factory pattern?**
- ✅ Testable — Create app with different configs for testing
- ✅ Flexible — Multiple app instances possible
- ✅ Clean — Separates app creation from configuration
- ✅ Extensible — Easy to add middleware, error handlers

---

## ⚙️ Configuration

### `config.py` — Environment settings

```python
import os

class Config:
    """Base configuration — shared across all environments"""
    
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-change-in-prod")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # Database connection
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL", 
        "sqlite:///medicheck_dev.db"  # Default for local dev
    )
    
    # AWS Textract credentials
    AWS_ACCESS_KEY_ID = os.environ.get("AWS_ACCESS_KEY_ID")
    AWS_SECRET_ACCESS_KEY = os.environ.get("AWS_SECRET_ACCESS_KEY")
    AWS_REGION = os.environ.get("AWS_REGION", "us-east-1")
    
    # Service 3 (RAG) integration
    SERVICE3_URL = os.environ.get("SERVICE3_URL", "http://localhost:5002")
    SERVICE3_TIMEOUT_SECONDS = 10  # Explicit timeout (NFR-18)
    
    # Upload constraints (FR-01, FR-05)
    MAX_FILE_SIZE_MB = int(os.environ.get("MAX_FILE_SIZE_MB", 10))
    MAX_PAGE_COUNT = int(os.environ.get("MAX_PAGE_COUNT", 20))
    
    # OCR confidence threshold for yellow highlighting
    OCR_CONFIDENCE_THRESHOLD = 0.80  # Agreed in API contract

class DevelopmentConfig(Config):
    DEBUG = True

class ProductionConfig(Config):
    DEBUG = False
    # Fix PostgreSQL URI (Render uses postgres://, SQLAlchemy needs postgresql://)
    _db_url = os.environ.get("DATABASE_URL", "")
    if _db_url.startswith("postgres://"):
        SQLALCHEMY_DATABASE_URI = _db_url.replace("postgres://", "postgresql://", 1)

config = {
    "development": DevelopmentConfig,
    "production": ProductionConfig,
    "default": DevelopmentConfig,
}
```

**Environment Variables Required:**
```bash
# AWS (for Textract OCR)
AWS_ACCESS_KEY_ID=your-aws-key
AWS_SECRET_ACCESS_KEY=your-aws-secret
AWS_REGION=us-east-1

# Database
DATABASE_URL=postgresql://user:pass@host/db  # Production
# or sqlite:///medicheck_dev.db  # Development

# Service 3 integration
SERVICE3_URL=http://localhost:5002

# Upload limits
MAX_FILE_SIZE_MB=10
MAX_PAGE_COUNT=20

# Flask
FLASK_ENV=development
SECRET_KEY=your-secret-key
```

---

## 🗄️ Database Models

### Entity Relationship Diagram

```
Session (root aggregate)
  ├─ ExtractedField (1:N) — One per upload
  │  ├─ LineItem (1:N) — One per charge line
  │  ├─ line_number, cpt_code, amount, confidence
  │  └─ extracted_value, corrected_value (audit trail)
  ├─ AnalysisResult (1:N) — One per detected error
  │  ├─ module, error_type, description
  │  ├─ line_items_affected, estimated_dollar_impact
  │  └─ explanation (from RAG), citations
  └─ DisputeLetter (1:1) — Generated document
     ├─ letter_text (HTML)
     └─ pdf_binary
```

### `models.py` — Data layer

#### Session Model
```python
class Session(db.Model):
    """
    Represents one patient's entire workflow.
    State machine enforces correct progression (FR-26).
    """
    __tablename__ = "sessions"
    
    session_id = db.Column(db.String(36), primary_key=True, default=_new_uuid)
    status = db.Column(
        db.String(32), 
        nullable=False, 
        default=SessionStatus.EXTRACTED
    )
    # Status values: extracted → confirmed → analysed → letter_generated
    
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=_now)
    updated_at = db.Column(db.DateTime(timezone=True), nullable=False, default=_now, onupdate=_now)
    
    # Relationships
    extracted_fields = db.relationship(
        "ExtractedField", 
        backref="session", 
        lazy=True, 
        cascade="all, delete-orphan"  # Auto-delete when session deleted
    )
    analysis_results = db.relationship(
        "AnalysisResult", 
        backref="session", 
        lazy=True, 
        cascade="all, delete-orphan"
    )
    letter = db.relationship(
        "DisputeLetter", 
        backref="session", 
        uselist=False, 
        cascade="all, delete-orphan"
    )
    
    def to_dict(self):
        return {
            "session_id": self.session_id,
            "status": self.status,
            "created_at": self.created_at.isoformat(),
        }
```

#### ExtractedField Model
```python
class ExtractedField(db.Model):
    """
    Stores OCR-extracted bill data.
    Preserves audit trail: extracted_value never overwritten.
    """
    __tablename__ = "extracted_fields"
    
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    session_id = db.Column(db.String(36), db.ForeignKey("sessions.session_id"), nullable=False)
    
    # Main fields
    patient_name = db.Column(db.String(256))
    provider_name = db.Column(db.String(256))
    date_of_service = db.Column(db.String(32))  # ISO format: "2024-01-15"
    total_billed = db.Column(db.Numeric(10, 2))
    
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=_now)
    
    # Line items (charges)
    line_items = db.relationship(
        "LineItem", 
        backref="extracted_field", 
        lazy=True, 
        cascade="all, delete-orphan"
    )
    
    def to_dict(self):
        return {
            "patient_name": self.patient_name,
            "provider_name": self.provider_name,
            "date_of_service": self.date_of_service,
            "total_billed": float(self.total_billed or 0),
            "line_items": [li.to_dict() for li in self.line_items],
        }
```

#### LineItem Model
```python
class LineItem(db.Model):
    """
    One row per charge on the bill or EOB.
    Stores both extracted and corrected values.
    """
    __tablename__ = "line_items"
    
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    extracted_field_id = db.Column(
        db.Integer, 
        db.ForeignKey("extracted_fields.id"), 
        nullable=False
    )
    
    # Charge details
    line_number = db.Column(db.Integer, nullable=False)  # Position in bill
    cpt_code = db.Column(db.String(10))  # e.g., "99213"
    description = db.Column(db.String(256))  # Procedure name (rarely used)
    quantity = db.Column(db.Integer, default=1)
    
    # Amount fields — audit trail
    extracted_amount = db.Column(db.Numeric(10, 2))  # Original OCR value
    corrected_amount = db.Column(db.Numeric(10, 2))  # User correction (if any)
    
    # Metadata
    extracted_date = db.Column(db.String(32))  # Service date from OCR
    corrected_date = db.Column(db.String(32))  # User correction (if any)
    confidence = db.Column(db.Float)  # OCR confidence (0.0 — 1.0)
    
    source = db.Column(db.String(32))  # "bill" or "eob"
    
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=_now)
    
    @property
    def amount(self):
        """Return corrected amount if available, else extracted amount"""
        return self.corrected_amount or self.extracted_amount
    
    @property
    def date(self):
        """Return corrected date if available, else extracted date"""
        return self.corrected_date or self.extracted_date
    
    def to_dict(self):
        return {
            "line_number": self.line_number,
            "cpt_code": self.cpt_code,
            "description": self.description,
            "quantity": self.quantity,
            "amount": float(self.amount or 0),
            "date": self.date,
            "confidence": self.confidence,
            "source": self.source,
        }
```

#### AnalysisResult Model
```python
class AnalysisResult(db.Model):
    """
    Stores one detected billing error.
    Created by error detection pipeline.
    """
    __tablename__ = "analysis_results"
    
    result_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    session_id = db.Column(db.String(36), db.ForeignKey("sessions.session_id"), nullable=False)
    
    # Error detection fields (FR-16 required)
    module = db.Column(db.String(256), nullable=False)  # "duplicate_charge"
    error_type = db.Column(db.String(256), nullable=False)  # "Duplicate Charge"
    description = db.Column(db.Text, nullable=False)  # Detailed explanation
    line_items_affected = db.Column(db.JSON, nullable=False, default=[])  # [1, 3]
    estimated_dollar_impact = db.Column(db.Numeric(10, 2), nullable=False)  # USD
    confidence = db.Column(db.String(32), nullable=False)  # "high", "medium", "low"
    
    # RAG-populated fields (nullable if Service 3 times out)
    explanation = db.Column(db.Text)  # Plain-English explanation from RAG
    citations = db.Column(db.JSON, default=[])  # [regulation_ref, ...]
    
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=_now)
    
    def to_dict(self):
        return {
            "result_id": self.result_id,
            "module": self.module,
            "error_type": self.error_type,
            "description": self.description,
            "line_items_affected": self.line_items_affected,
            "estimated_dollar_impact": float(self.estimated_dollar_impact),
            "confidence": self.confidence,
            "explanation": self.explanation,
            "citations": self.citations,
        }
```

#### DisputeLetter Model
```python
class DisputeLetter(db.Model):
    """
    Stores generated dispute letter.
    Created after error detection is complete.
    """
    __tablename__ = "dispute_letters"
    
    letter_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    session_id = db.Column(
        db.String(36), 
        db.ForeignKey("sessions.session_id"), 
        nullable=False, 
        unique=True
    )
    
    # Letter content
    letter_text = db.Column(db.Text, nullable=False)  # HTML
    pdf_binary = db.Column(db.LargeBinary, nullable=True)  # PDF bytes
    
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=_now)
    
    def to_dict(self):
        return {
            "letter_id": self.letter_id,
            "session_id": self.session_id,
            "created_at": self.created_at.isoformat(),
        }
```

---

## 🌐 HTTP Routes (API Endpoints)

### State Machine Overview

```
POST /upload
    ↓ Creates session (status=extracted)
    ↓ Returns session_id + extracted_fields
    ↓
POST /confirm
    ↓ Requires status=extracted
    ↓ Updates fields with corrections
    ↓ Advances status → confirmed
    ↓
POST /analyse
    ↓ Requires status=confirmed
    ↓ Runs error detection
    ↓ Calls Service 3 for explanations (10-sec timeout)
    ↓ Advances status → analysed
    ↓
POST /letter
    ↓ Requires status=analysed
    ↓ Generates PDF letter
    ↓ Advances status → letter_generated
    ↓
GET /letter/download/{id}
    ↓ Returns PDF binary
```

### GET /health

Simple liveness check (must respond within 2 seconds — NFR-04).

```python
@health_bp.get("/health")
def health():
    """
    Health check endpoint (NFR-12, US-016).
    Must respond within 2 seconds (NFR-04).
    Does not require authentication (US-016 AC5).
    """
    return jsonify({
        "status": "ok",
        "service": "bill-analysis",
        "version": "1.0.0",
    }), 200
```

**Request:**
```bash
curl http://localhost:5001/health
```

**Response 200:**
```json
{
  "status": "ok",
  "service": "bill-analysis",
  "version": "1.0.0"
}
```

---

### POST /upload

Upload bill (required) and EOB (optional) PDFs. Extract fields via OCR.

```python
@upload_bp.post("/upload")
def upload():
    """
    Accept bill PDF (required) and EOB PDF (optional).
    Run OCR on each, persist extracted fields, return session_id.
    
    Functional Requirements:
        FR-01: Validate file size ≤ 10 MB
        FR-02: Accept PDF files only
        FR-03: Accept bill + optional EOB
        FR-04: Extract and return fields
        FR-05: Validate page count ≤ 20
    """
    # 1. Validate bill file is present
    if "bill" not in request.files:
        return _error(400, ERR_NO_BILL, "No bill file uploaded.")
    
    bill_file = request.files["bill"]
    eob_file = request.files.get("eob")
    
    # 2. Validate files
    validation_error = _validate_pdf(bill_file, current_app.config)
    if validation_error:
        return validation_error
    
    if eob_file:
        validation_error = _validate_pdf(eob_file, current_app.config)
        if validation_error:
            return validation_error
    
    # 3. Run OCR
    bill_bytes = bill_file.read()
    bill_data = ocr_service.extract(bill_bytes, source="bill")
    
    eob_data = None
    if eob_file:
        eob_bytes = eob_file.read()
        eob_data = ocr_service.extract(eob_bytes, source="eob")
    
    # 4. Create session
    session = Session(status=SessionStatus.EXTRACTED)
    db.session.add(session)
    db.session.flush()  # Get session_id before committing
    
    # 5. Persist extracted fields
    extracted = ExtractedField(
        session_id=session.session_id,
        patient_name=bill_data.get("patient_name"),
        provider_name=bill_data.get("provider_name"),
        date_of_service=bill_data.get("date_of_service"),
        total_billed=bill_data.get("total_billed"),
    )
    db.session.add(extracted)
    db.session.flush()
    
    # 6. Persist line items
    for item in bill_data.get("line_items", []):
        db.session.add(_build_line_item(extracted.id, item, "bill"))
    
    if eob_data:
        for item in eob_data.get("line_items", []):
            db.session.add(_build_line_item(extracted.id, item, "eob"))
    
    db.session.commit()
    
    # 7. Return response
    return jsonify({
        "session_id": session.session_id,
        "status": "extracted",
        "extracted_fields": {
            "patient_name": bill_data.get("patient_name"),
            "provider_name": bill_data.get("provider_name"),
            "date_of_service": bill_data.get("date_of_service"),
            "total_billed": bill_data.get("total_billed"),
            "line_items": [_format_line_item(item, "bill") for item in bill_data.get("line_items", [])],
        },
        "rag_available": True,
    }), 200
```

**Request:**
```bash
curl -X POST http://localhost:5001/upload \
  -F "bill=@bill.pdf" \
  -F "eob=@eob.pdf"
```

**Response 200:**
```json
{
  "session_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "extracted",
  "extracted_fields": {
    "patient_name": "John Doe",
    "provider_name": "Acme Hospital",
    "date_of_service": "2024-01-15",
    "total_billed": 1500.00,
    "line_items": [
      {
        "line_number": 1,
        "cpt_code": "99213",
        "quantity": 1,
        "amount": 150.00,
        "confidence": 0.95,
        "source": "bill"
      }
    ]
  },
  "rag_available": true
}
```

**Response 400 (error):**
```json
{
  "error_code": "FILE_TOO_LARGE",
  "message": "File exceeds the 10 MB limit.",
  "session_id": null
}
```

---

### POST /confirm

User reviews and optionally corrects extracted fields.

```python
@confirm_bp.post("/confirm")
def confirm():
    """
    Submit user-corrected field values.
    Advances session status from 'extracted' → 'confirmed'.
    
    Functional Requirement:
        FR-07: Store user-corrected values
        FR-26: Enforce state machine (extracted → confirmed)
    """
    data = request.get_json(silent=True) or {}
    session_id = data.get("session_id")
    corrections = data.get("corrections", {})
    
    # 1. Validate session
    session = Session.query.get(session_id)
    if not session:
        return _error(404, ERR_SESSION_NOT_FOUND, "Session not found.", session_id)
    
    # 2. Validate state (must be extracted)
    if session.status != SessionStatus.EXTRACTED:
        return _error(400, ERR_NOT_EXTRACTED,
                      f"Session status is '{session.status}'. "
                      "Confirmation requires status 'extracted'.", session_id)
    
    # 3. Update fields with corrections
    extracted = ExtractedField.query.filter_by(session_id=session_id).first()
    if extracted:
        if "patient_name" in corrections:
            extracted.patient_name = corrections["patient_name"]
        if "provider_name" in corrections:
            extracted.provider_name = corrections["provider_name"]
        if "date_of_service" in corrections:
            extracted.date_of_service = corrections["date_of_service"]
        if "total_billed" in corrections:
            extracted.total_billed = corrections["total_billed"]
    
    # 4. Update line items
    for li_correction in corrections.get("line_items", []):
        line_number = li_correction.get("line_number")
        line_item = LineItem.query.filter_by(
            extracted_field_id=extracted.id,
            line_number=line_number
        ).first()
        if line_item:
            if "amount" in li_correction:
                line_item.corrected_amount = li_correction["amount"]
            if "date" in li_correction:
                line_item.corrected_date = li_correction["date"]
    
    # 5. Advance status
    session.status = SessionStatus.CONFIRMED
    db.session.commit()
    
    return jsonify({
        "session_id": session_id,
        "status": "confirmed",
        "message": "Session confirmed and ready for analysis"
    }), 200
```

**Request:**
```json
{
  "session_id": "550e8400-e29b-41d4-a716-446655440000",
  "corrections": {
    "patient_name": "Jane Doe",
    "line_items": [
      {
        "line_number": 1,
        "amount": 140.00
      }
    ]
  }
}
```

**Response 200:**
```json
{
  "session_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "confirmed",
  "message": "Session confirmed and ready for analysis"
}
```

---

### POST /analyse

Run error detection on confirmed data. Calls Service 3 for explanations (with 10-second timeout).

```python
@analyse_bp.post("/analyse")
def analyse():
    """
    Run all four error detectors.
    Call Service 3 for RAG explanations (10-second timeout, NFR-18).
    Return partial response if Service 3 times out (NFR-02).
    
    Functional Requirements:
        FR-10: Run all 4 detectors, no silent omissions
        FR-16: Validate all required fields on DetectionResult
    
    Non-Functional Requirements:
        NFR-01: ≤ 30 errors per analysis
        NFR-02: Graceful timeout on Service 3
        NFR-17: HTTP 400 if session not confirmed
        NFR-18: 10-second timeout on Service 3 requests
    """
    data = request.get_json(silent=True) or {}
    session_id = data.get("session_id")
    
    # 1. Validate session exists
    session = Session.query.get(session_id)
    if not session:
        return _error(404, ERR_SESSION_NOT_FOUND,
                      "No session found for the provided session_id.", session_id)
    
    # 2. Validate status = confirmed (NFR-17)
    if session.status != SessionStatus.CONFIRMED:
        return _error(400, ERR_NOT_CONFIRMED,
                      f"Session status is '{session.status}'. "
                      "Analysis requires status 'confirmed'.", session_id)
    
    # 3. Load confirmed fields from database
    confirmed_fields = _load_confirmed_fields(session_id)
    
    # 4. Run ErrorDetectionEngine
    engine_output = engine.run(confirmed_fields)
    detection_results = engine_output["results"]
    all_clear = engine_output["all_clear"]
    
    # 5. For each result, call Service 3 (RAG) with timeout
    errors_with_explanations = []
    total_savings = 0
    rag_available = True
    
    for result in detection_results:
        error_dict = result.to_dict()
        
        try:
            # Call Service 3 with 10-second timeout
            explanation, citations = rag_client.explain(
                error_type=result.error_type,
                description=result.description,
                timeout_seconds=10  # NFR-18
            )
            error_dict["explanation"] = explanation
            error_dict["citations"] = citations
        except TimeoutError:
            # Service 3 timed out — return partial response (NFR-02)
            error_dict["explanation"] = None
            error_dict["citations"] = []
            rag_available = False
        except Exception as e:
            # Other Service 3 error — log and continue with null explanation
            print(f"RAG error: {e}")
            error_dict["explanation"] = None
            error_dict["citations"] = []
            rag_available = False
        
        total_savings += float(result.estimated_dollar_impact)
        
        # 6. Persist AnalysisResult
        analysis_result = AnalysisResult(
            session_id=session_id,
            module=result.module,
            error_type=result.error_type,
            description=result.description,
            line_items_affected=result.line_items_affected,
            estimated_dollar_impact=result.estimated_dollar_impact,
            confidence=result.confidence,
            explanation=error_dict.get("explanation"),
            citations=error_dict.get("citations", []),
        )
        db.session.add(analysis_result)
        errors_with_explanations.append(error_dict)
    
    # 7. Advance status
    session.status = SessionStatus.ANALYSED
    db.session.commit()
    
    return jsonify({
        "session_id": session_id,
        "status": "analysed",
        "errors": errors_with_explanations,
        "total_errors": len(errors_with_explanations),
        "total_savings": total_savings,
        "all_clear": all_clear,
        "rag_available": rag_available,
    }), 200
```

**Request:**
```json
{
  "session_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

**Response 200 (full, with RAG explanations):**
```json
{
  "session_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "analysed",
  "errors": [
    {
      "result_id": 1,
      "module": "duplicate_charge",
      "error_type": "Duplicate Charge",
      "description": "CPT 99213 appears 2 times on 2024-01-15.",
      "line_items_affected": [1, 3],
      "estimated_dollar_impact": 150.00,
      "confidence": "high",
      "explanation": "This charge appears twice in your billing records. Only one procedure can be billed per date.",
      "citations": ["42 CFR 482.24", "Medicare Billing Guidance"]
    }
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
  "session_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "analysed",
  "errors": [
    {
      "result_id": 1,
      "module": "duplicate_charge",
      "error_type": "Duplicate Charge",
      "description": "CPT 99213 appears 2 times on 2024-01-15.",
      "line_items_affected": [1, 3],
      "estimated_dollar_impact": 150.00,
      "confidence": "high",
      "explanation": null,
      "citations": []
    }
  ],
  "total_errors": 3,
  "total_savings": 450.00,
  "all_clear": false,
  "rag_available": false
}
```

---

### POST /letter

Generate dispute letter from analysis results.

```python
@letter_bp.post("/letter")
def letter():
    """
    Generate a dispute letter based on detected errors.
    Advances session status from 'analysed' → 'letter_generated'.
    """
    data = request.get_json(silent=True) or {}
    session_id = data.get("session_id")
    
    # 1. Validate session
    session = Session.query.get(session_id)
    if not session:
        return _error(404, ERR_SESSION_NOT_FOUND, "Session not found.", session_id)
    
    # 2. Validate status = analysed
    if session.status != SessionStatus.ANALYSED:
        return _error(400, ERR_NOT_ANALYSED,
                      f"Session status is '{session.status}'. "
                      "Letter requires status 'analysed'.", session_id)
    
    # 3. Load session data
    extracted = ExtractedField.query.filter_by(session_id=session_id).first()
    errors = AnalysisResult.query.filter_by(session_id=session_id).all()
    
    # 4. Build letter
    letter_html = letter_builder.generate(extracted, errors)
    
    # 5. Convert to PDF (using reportlab or wkhtmltopdf)
    pdf_bytes = _html_to_pdf(letter_html)
    
    # 6. Persist letter
    dispute_letter = DisputeLetter(
        session_id=session_id,
        letter_text=letter_html,
        pdf_binary=pdf_bytes,
    )
    db.session.add(dispute_letter)
    
    # 7. Advance status
    session.status = SessionStatus.LETTER_GENERATED
    db.session.commit()
    
    return jsonify({
        "session_id": session_id,
        "status": "letter_generated",
        "letter_id": dispute_letter.letter_id,
        "preview": letter_html[:500],  # First 500 chars
        "download_url": f"/letter/download/{dispute_letter.letter_id}",
    }), 200
```

**Request:**
```json
{
  "session_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

**Response 200:**
```json
{
  "session_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "letter_generated",
  "letter_id": 1,
  "preview": "Dear Provider,\n\nWe have identified the following billing errors...",
  "download_url": "/letter/download/1"
}
```

---

### GET /letter/download/{letter_id}

Download generated dispute letter as PDF.

```python
@letter_bp.get("/letter/download/<int:letter_id>")
def download_letter(letter_id):
    """
    Return the dispute letter as a PDF file for download.
    """
    letter = DisputeLetter.query.get(letter_id)
    if not letter:
        return jsonify({"error": "Letter not found"}), 404
    
    return send_file(
        io.BytesIO(letter.pdf_binary),
        mimetype="application/pdf",
        as_attachment=True,
        download_name=f"dispute_letter_{letter_id}.pdf"
    )
```

**Request:**
```bash
curl -O http://localhost:5001/letter/download/1
```

**Response 200:**
```
Content-Type: application/pdf
Content-Disposition: attachment; filename="dispute_letter_1.pdf"

[PDF binary data]
```

---

## 🔍 OCR Service (AWS Textract Integration)

### `services/ocr.py` — AWS Textract wrapper

```python
import boto3

class OCRService:
    """Wraps AWS Textract AnalyzeDocument API."""
    
    def __init__(self):
        self._client = None
    
    @property
    def client(self):
        """Lazy-load Textract client."""
        if self._client is None:
            self._client = boto3.client(
                "textract",
                region_name=current_app.config["AWS_REGION"],
                aws_access_key_id=current_app.config["AWS_ACCESS_KEY_ID"],
                aws_secret_access_key=current_app.config["AWS_SECRET_ACCESS_KEY"],
            )
        return self._client
    
    def extract(self, file_bytes: bytes, source: str = "bill") -> dict:
        """
        Extract structured data from a PDF.
        
        Args:
            file_bytes: Raw PDF bytes
            source: 'bill' or 'eob'
        
        Returns:
            {
                "patient_name": str,
                "provider_name": str,
                "date_of_service": str,
                "total_billed": float,
                "line_items": [
                    {
                        "line_number": int,
                        "cpt_code": str,
                        "quantity": int,
                        "amount": float,
                        "confidence": float,
                        "source": str,
                    },
                    ...
                ]
            }
        """
        # Call Textract API
        response = self.client.analyze_document(
            Document={"Bytes": file_bytes},
            FeatureTypes=["TABLES", "FORMS"],
        )
        
        # Extract key-value pairs (forms: patient, provider, etc.)
        kv_pairs = self._extract_key_value_pairs(response)
        
        # Extract line items (tables: charges)
        line_items = self._extract_line_items(response, source)
        
        # Map field names
        patient_name = self._find_field(kv_pairs, ["patient name", "patient", "name"])
        provider_name = self._find_field(kv_pairs, ["provider", "facility", "hospital"])
        date_of_service = self._find_field(kv_pairs, ["date of service", "dos"])
        total_billed = self._parse_amount(
            self._find_field(kv_pairs, ["total", "amount due", "total billed"])
        )
        
        return {
            "patient_name": patient_name,
            "provider_name": provider_name,
            "date_of_service": date_of_service,
            "total_billed": total_billed,
            "line_items": line_items,
        }
    
    # Private helper methods...
    def _extract_key_value_pairs(self, response: dict) -> list[dict]:
        """Parse Textract FORMS response."""
        # Implementation details...
        pass
    
    def _extract_line_items(self, response: dict, source: str) -> list[dict]:
        """Parse Textract TABLES response."""
        # Implementation details...
        pass
```

### `services/mock_ocr.py` — Mock OCR for testing (no AWS credentials)

```python
class MockOCRService:
    """
    Mock OCR that returns synthetic test data.
    Used when USE_MOCK_OCR=true (development only).
    Requires no AWS credentials.
    """
    
    def extract(self, file_bytes: bytes, source: str = "bill") -> dict:
        """Return realistic synthetic bill/EOB data."""
        if source == "bill":
            return self._get_mock_bill_data()
        else:
            return self._get_mock_eob_data()
    
    def _get_mock_bill_data(self) -> dict:
        """Return mock medical bill data."""
        return {
            "patient_name": "John Doe",
            "provider_name": "Acme Hospital",
            "date_of_service": "2024-01-15",
            "total_billed": 1500.00,
            "line_items": [
                {
                    "line_number": 1,
                    "cpt_code": "99213",
                    "quantity": 1,
                    "amount": 150.00,
                    "confidence": 0.95,
                    "source": "bill",
                },
                {
                    "line_number": 2,
                    "cpt_code": "99213",  # Duplicate for testing
                    "quantity": 1,
                    "amount": 150.00,
                    "confidence": 0.95,
                    "source": "bill",
                },
                # ... more line items
            ],
        }
```

---

## 🔎 Error Detection Engine

### `services/engine.py` — Orchestrates all detectors

```python
from detectors.base import BaseDetector
from detectors.duplicate import DuplicateChargeDetector
from detectors.medicare_rate import MedicareRateDetector
from detectors.eob_reconciliation import EOBReconciliationDetector
from detectors.no_surprises import NoSurprisesActDetector

class ErrorDetectionEngine:
    """
    Runs all registered detectors and consolidates results.
    
    Strategy pattern (FR-15):
        To add a 5th detector, just subclass BaseDetector
        and add to _build_detectors(). No other changes needed.
    """
    
    def __init__(self, fee_schedule_path: str = None):
        self._detectors: list[BaseDetector] = self._build_detectors(fee_schedule_path)
    
    def _build_detectors(self, fee_schedule_path: str = None) -> list[BaseDetector]:
        """Register all active detectors here."""
        return [
            DuplicateChargeDetector(),
            MedicareRateDetector(fee_schedule_path=fee_schedule_path),
            EOBReconciliationDetector(),
            NoSurprisesActDetector(),
        ]
    
    def run(self, confirmed_fields: dict) -> dict:
        """
        Run all detectors against confirmed bill data.
        
        Args:
            confirmed_fields: dict with patient_name, provider_name, 
                            date_of_service, total_billed, line_items
        
        Returns:
            {
                "results": [DetectionResult, ...],
                "all_clear": bool,
                "module_summary": {"duplicate_charge": 2, ...},
            }
        """
        all_results: list[DetectionResult] = []
        module_summary: dict[str, int] = {}
        defects: list[str] = []
        
        # Run all detectors (FR-10: all 4 always run)
        for detector in self._detectors:
            try:
                results = detector.run(confirmed_fields)
                
                # Validate each result (FR-16)
                for result in results:
                    errors = result.validate()
                    if errors:
                        defects.extend(errors)
                
                all_results.extend(results)
                module_summary[detector.module_name] = len(results)
            except Exception as e:
                print(f"Detector error: {detector.module_name}: {e}")
                defects.append(f"{detector.module_name}: {e}")
        
        # Check for system defects
        if defects:
            return {
                "results": [],
                "all_clear": True,
                "module_summary": module_summary,
                "system_defects": defects,  # Alert for investigation
            }
        
        return {
            "results": all_results,
            "all_clear": len(all_results) == 0,
            "module_summary": module_summary,
        }
```

---

## 🎯 The 4 Error Detectors

### 1. DuplicateChargeDetector (`detectors/duplicate.py`)

Flags when the same CPT code appears multiple times on the same date.

```python
class DuplicateChargeDetector(BaseDetector):
    
    @property
    def module_name(self) -> str:
        return "duplicate_charge"
    
    def run(self, confirmed_fields: dict) -> list[DetectionResult]:
        """
        Logic:
            Group bill items by (cpt_code, date_of_service)
            If count > 1 → duplicate
            Each extra item → separate DetectionResult
        """
        results = []
        bill_items = [
            item for item in confirmed_fields.get("line_items", [])
            if item.get("source") == "bill" and item.get("cpt_code")
        ]
        
        seen: dict[tuple, list] = {}
        
        for item in bill_items:
            cpt = item["cpt_code"]
            date = item.get("date") or confirmed_fields.get("date_of_service")
            key = (cpt, date)
            
            if key not in seen:
                seen[key] = []
            seen[key].append(item)
        
        # Flag duplicates
        for (cpt, date), items in seen.items():
            if len(items) < 2:
                continue
            
            for i in range(1, len(items)):
                original = items[0]
                duplicate = items[i]
                
                results.append(DetectionResult(
                    module=self.module_name,
                    error_type="Duplicate Charge",
                    description=f"CPT {cpt} appears {len(items)} times on {date}. "
                               f"Only one procedure can be billed per date.",
                    line_items_affected=[original["line_number"], duplicate["line_number"]],
                    estimated_dollar_impact=float(duplicate.get("amount", 0)),
                    confidence="high",
                ))
        
        return results
```

---

### 2. MedicareRateDetector (`detectors/medicare_rate.py`)

Flags charges exceeding Medicare allowed amounts.

```python
class MedicareRateDetector(BaseDetector):
    
    def __init__(self, fee_schedule_path: str = None):
        self.fee_schedule = self._load_fee_schedule(fee_schedule_path)
    
    @property
    def module_name(self) -> str:
        return "medicare_rate"
    
    def run(self, confirmed_fields: dict) -> list[DetectionResult]:
        """
        Logic:
            For each bill item:
                Look up Medicare allowed amount
                If billed > allowed → flag
        """
        results = []
        bill_items = [
            item for item in confirmed_fields.get("line_items", [])
            if item.get("source") == "bill"
        ]
        
        for item in bill_items:
            cpt = item.get("cpt_code")
            if not cpt:
                continue
            
            billed = float(item.get("amount", 0))
            allowed = self.fee_schedule.get(cpt, billed)  # Assume billed if not found
            
            if billed > allowed:
                overage = billed - allowed
                results.append(DetectionResult(
                    module=self.module_name,
                    error_type="Exceeds Medicare Rate",
                    description=f"CPT {cpt} billed at ${billed:.2f}, "
                               f"but Medicare allows ${allowed:.2f}. "
                               f"Overbilled by ${overage:.2f}.",
                    line_items_affected=[item["line_number"]],
                    estimated_dollar_impact=overage,
                    confidence="high",
                ))
        
        return results
```

---

### 3. EOBReconciliationDetector (`detectors/eob_reconciliation.py`)

Flags mismatches between bill and EOB amounts.

```python
class EOBReconciliationDetector(BaseDetector):
    
    @property
    def module_name(self) -> str:
        return "eob_reconciliation"
    
    def run(self, confirmed_fields: dict) -> list[DetectionResult]:
        """
        Logic:
            For each bill item, find matching EOB item
            If amounts differ → flag as mismatch
        """
        results = []
        bill_items = [
            item for item in confirmed_fields.get("line_items", [])
            if item.get("source") == "bill"
        ]
        eob_items = [
            item for item in confirmed_fields.get("line_items", [])
            if item.get("source") == "eob"
        ]
        
        for bill_item in bill_items:
            cpt = bill_item.get("cpt_code")
            bill_date = bill_item.get("date") or confirmed_fields.get("date_of_service")
            bill_amount = float(bill_item.get("amount", 0))
            
            # Find matching EOB item
            matching_eob = None
            for eob_item in eob_items:
                if eob_item.get("cpt_code") == cpt:
                    eob_date = eob_item.get("date") or confirmed_fields.get("date_of_service")
                    if eob_date == bill_date:
                        matching_eob = eob_item
                        break
            
            if matching_eob:
                eob_amount = float(matching_eob.get("amount", 0))
                if bill_amount != eob_amount:
                    difference = abs(bill_amount - eob_amount)
                    results.append(DetectionResult(
                        module=self.module_name,
                        error_type="Bill/EOB Mismatch",
                        description=f"CPT {cpt} shows ${bill_amount:.2f} on bill "
                                   f"but ${eob_amount:.2f} on EOB. "
                                   f"Discrepancy: ${difference:.2f}",
                        line_items_affected=[bill_item["line_number"]],
                        estimated_dollar_impact=difference,
                        confidence="medium",
                    ))
        
        return results
```

---

### 4. NoSurprisesActDetector (`detectors/no_surprises.py`)

Flags potential surprise billing (out-of-network + high charges).

```python
class NoSurprisesActDetector(BaseDetector):
    
    @property
    def module_name(self) -> str:
        return "no_surprises"
    
    def run(self, confirmed_fields: dict) -> list[DetectionResult]:
        """
        Heuristics for surprise billing detection:
            1. Out-of-network provider + charge >> market average
            2. Emergency service + out-of-network
            3. Assisted reproductive + certain conditions
        """
        results = []
        # Implementation uses heuristics and market data...
        return results
```

---

## 🧪 Testing

### `tests/test_detectors.py` — Detector tests

```python
import pytest
from detectors.duplicate import DuplicateChargeDetector

def test_duplicate_charge_detector():
    """Test duplicate charge detection."""
    detector = DuplicateChargeDetector()
    
    confirmed_fields = {
        "date_of_service": "2024-01-15",
        "line_items": [
            {
                "line_number": 1,
                "cpt_code": "99213",
                "amount": 150.00,
                "source": "bill",
            },
            {
                "line_number": 2,
                "cpt_code": "99213",  # Duplicate
                "amount": 150.00,
                "source": "bill",
            },
        ],
    }
    
    results = detector.run(confirmed_fields)
    
    assert len(results) == 1
    assert results[0].error_type == "Duplicate Charge"
    assert results[0].estimated_dollar_impact == 150.00
    assert results[0].confidence == "high"
```

### Run tests

```bash
cd services/service2-billanalysis
pytest tests/ -v --cov=. --cov-report=html
```

---

## 🚀 Running Service 2

### With Mock OCR (no AWS credentials needed)
```bash
cd services/service2-billanalysis
pip install -r requirements.txt
export USE_MOCK_OCR=true
flask run --port 5001
```

### With Real AWS Textract
```bash
export AWS_ACCESS_KEY_ID=your-key
export AWS_SECRET_ACCESS_KEY=your-secret
export AWS_REGION=us-east-1
export USE_MOCK_OCR=false
flask run --port 5001
```

### With PostgreSQL (production)
```bash
export DATABASE_URL=postgresql://user:pass@host/medicheck
export FLASK_ENV=production
gunicorn app:app --bind 0.0.0.0:5001
```

---

## 📋 Summary

**Service 2** is a well-architected Flask backend that:

1. **Accepts** bill PDFs via POST /upload
2. **Extracts** fields using AWS Textract (or mock OCR)
3. **Persists** data in a state machine (extracted → confirmed → analysed → letter_generated)
4. **Detects** errors using 4 pluggable detectors
5. **Coordinates** with Service 3 for explanations
6. **Generates** dispute letters as PDFs
7. **Returns** structured JSON responses with error details and dollar impact

**Key Design Patterns:**
- Factory pattern (app initialization)
- State machine (session workflow)
- Strategy pattern (pluggable detectors)
- Repository pattern (SQLAlchemy models)

**Key Technologies:**
- Flask (REST API)
- SQLAlchemy (ORM)
- AWS Textract (OCR)
- PostgreSQL (production database)

---

**Last Updated:** April 2026
