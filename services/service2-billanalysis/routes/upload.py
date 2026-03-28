"""
POST /upload — FR-01, FR-02, FR-03, FR-04, FR-05
Accepts one or two PDF files, runs OCR, returns session_id + extracted fields.
"""

import io
import os
from flask import Blueprint, request, jsonify, current_app
from extensions import db
from models import Session, ExtractedField, LineItem, SessionStatus
if os.environ.get("USE_MOCK_OCR", "false").lower() == "true":
    from services.mock_ocr import MockOCRService
    ocr_service = MockOCRService()
else:
    from services.ocr import OCRService
    ocr_service = OCRService()

upload_bp = Blueprint("upload", __name__)

# ── Error codes (from API contract error code reference) ──────────────────────
ERR_INVALID_FILE_TYPE = "INVALID_FILE_TYPE"
ERR_FILE_TOO_LARGE    = "FILE_TOO_LARGE"
ERR_PAGE_LIMIT        = "PAGE_LIMIT_EXCEEDED"
ERR_NO_BILL           = "NO_BILL_UPLOADED"


@upload_bp.post("/upload")
def upload():
    """
    Accept bill PDF (required) and EOB PDF (optional).
    Run OCR on each, persist extracted fields, return session_id.

    Request: multipart/form-data
        bill  — PDF file (required)
        eob   — PDF file (optional)

    Response 200: session_id, status, extracted_fields, rag_available
    Response 400: error_code, message, session_id: null
    """

    # ── 1. Validate bill file is present ──────────────────────────────────────
    if "bill" not in request.files:
        return _error(400, ERR_NO_BILL, "No bill file uploaded. Field name must be 'bill'.")

    bill_file = request.files["bill"]
    eob_file  = request.files.get("eob")

    # ── 2. Validate bill file ──────────────────────────────────────────────────
    validation_error = _validate_pdf(bill_file, current_app.config)
    if validation_error:
        return validation_error

    # ── 3. Validate EOB file if present ───────────────────────────────────────
    if eob_file:
        validation_error = _validate_pdf(eob_file, current_app.config)
        if validation_error:
            return validation_error

    # ── 4. Run OCR on bill ────────────────────────────────────────────────────
    bill_bytes = bill_file.read()
    bill_data  = ocr_service.extract(bill_bytes, source="bill")

    # ── 5. Run OCR on EOB if present ──────────────────────────────────────────
    eob_data = None
    if eob_file:
        eob_bytes = eob_file.read()
        eob_data  = ocr_service.extract(eob_bytes, source="eob")

    # ── 6. Persist session ────────────────────────────────────────────────────
    session = Session(status=SessionStatus.EXTRACTED)
    db.session.add(session)
    db.session.flush()  # get session_id before committing

    # ── 7. Persist extracted fields ───────────────────────────────────────────
    extracted = ExtractedField(
        session_id=session.session_id,
        patient_name=bill_data.get("patient_name"),
        provider_name=bill_data.get("provider_name"),
        date_of_service=bill_data.get("date_of_service"),
        total_billed=bill_data.get("total_billed"),
    )
    db.session.add(extracted)
    db.session.flush()

    # Bill line items
    for item in bill_data.get("line_items", []):
        db.session.add(_build_line_item(extracted.id, item, source="bill"))

    # EOB line items (separate, tagged source='eob')
    if eob_data:
        for item in eob_data.get("line_items", []):
            db.session.add(_build_line_item(extracted.id, item, source="eob"))

    db.session.commit()

    # ── 8. Build response ─────────────────────────────────────────────────────
    all_line_items = []
    for item in bill_data.get("line_items", []):
        all_line_items.append(_format_line_item(item, "bill"))
    if eob_data:
        for item in eob_data.get("line_items", []):
            all_line_items.append(_format_line_item(item, "eob"))

    return jsonify({
        "session_id": session.session_id,
        "status": "extracted",
        "extracted_fields": {
            "patient_name": bill_data.get("patient_name"),
            "provider_name": bill_data.get("provider_name"),
            "date_of_service": bill_data.get("date_of_service"),
            "total_billed": bill_data.get("total_billed"),
            "line_items": all_line_items,
        },
        "rag_available": True,  # checked at analyse time, assume available on upload
    }), 200


# ── Helpers ───────────────────────────────────────────────────────────────────

def _validate_pdf(file, config) -> tuple | None:
    """
    Validate file type and size. Returns an error response tuple or None if valid.
    FR-01, FR-05.
    """
    filename = file.filename or ""

    # Type check
    if not filename.lower().endswith(".pdf"):
        return _error(400, ERR_INVALID_FILE_TYPE, "Uploaded file is not a PDF.")

    # Size check (read into memory to get size, then reset)
    file.seek(0, 2)  # seek to end
    size_bytes = file.tell()
    file.seek(0)     # reset

    max_bytes = config["MAX_FILE_SIZE_MB"] * 1024 * 1024
    if size_bytes > max_bytes:
        return _error(
            400, ERR_FILE_TOO_LARGE,
            f"File exceeds the {config['MAX_FILE_SIZE_MB']} MB limit."
        )

    return None


def _build_line_item(extracted_field_id: int, item: dict, source: str) -> LineItem:
    return LineItem(
        extracted_field_id=extracted_field_id,
        line_number=item["line_number"],
        cpt_code=item.get("cpt_code"),
        description="",   # never populated — AMA copyright
        quantity=item.get("quantity", 1),
        extracted_amount=item.get("amount"),
        extracted_date=item.get("date"),
        confidence=item.get("confidence"),
        source=source,
    )


def _format_line_item(item: dict, source: str) -> dict:
    """Format a line item for the API response (includes confidence for UI highlighting)."""
    return {
        "line_number": item["line_number"],
        "cpt_code": item.get("cpt_code"),
        "description": "",   # AMA copyright — always empty
        "quantity": item.get("quantity", 1),
        "amount": item.get("amount", 0.0),
        "confidence": item.get("confidence"),
        "source": source,
    }


def _error(status: int, code: str, message: str):
    return jsonify({
        "error_code": code,
        "message": message,
        "session_id": None,
    }), status
