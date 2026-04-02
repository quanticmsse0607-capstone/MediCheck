"""
POST /confirm — FR-06, FR-07, FR-08, FR-09
Receives user-corrected field values, persists them, advances session status.
Confidence scores are stripped before persisting (agreed decision in API contract).
"""

from flask import Blueprint, request, jsonify
from extensions import db
from models import Session, ExtractedField, LineItem, SessionStatus

confirm_bp = Blueprint("confirm", __name__)

ERR_SESSION_NOT_FOUND = "SESSION_NOT_FOUND"
ERR_NOT_CONFIRMED = "NOT_CONFIRMED"


@confirm_bp.post("/confirm")
def confirm():
    """
    Accept confirmed field values from the field confirmation UI.
    Persists corrected values while retaining originals for audit (FR-07).
    Advances session status from 'extracted' → 'confirmed'.

    Request JSON:
        session_id       — string (required)
        confirmed_fields — object with patient_name, provider_name,
                           date_of_service, total_billed, line_items[]

    Response 200: session_id, status: 'confirmed'
    Response 400: NOT_CONFIRMED (wrong session state)
    Response 404: SESSION_NOT_FOUND
    """

    data = request.get_json(silent=True) or {}

    session_id = data.get("session_id")
    confirmed = data.get("confirmed_fields", {})

    # ── 1. Validate session exists ────────────────────────────────────────────
    session = Session.query.get(session_id)
    if not session:
        return _error(
            404,
            ERR_SESSION_NOT_FOUND,
            "No session found for the provided session_id.",
            session_id,
        )

    # ── 2. Validate session state (FR-26) ─────────────────────────────────────
    if not SessionStatus.can_transition_to(session.status, SessionStatus.CONFIRMED):
        return _error(
            400,
            ERR_NOT_CONFIRMED,
            f"Session status is '{session.status}'. "
            "Field confirmation requires status 'extracted'.",
            session_id,
        )

    # ── 3. Update top-level confirmed fields ──────────────────────────────────
    extracted = ExtractedField.query.filter_by(session_id=session_id).first()
    if extracted:
        # Overwrite with corrected values — originals in extracted_* columns are untouched
        if "patient_name" in confirmed:
            extracted.patient_name = confirmed["patient_name"]
        if "provider_name" in confirmed:
            extracted.provider_name = confirmed["provider_name"]
        if "date_of_service" in confirmed:
            extracted.date_of_service = confirmed["date_of_service"]
        if "total_billed" in confirmed:
            extracted.total_billed = confirmed["total_billed"]

    # ── 4. Update corrected line item values ──────────────────────────────────
    # Confidence scores are NOT accepted from the frontend (stripped — agreed decision)
    confirmed_items = confirmed.get("line_items", [])
    for confirmed_item in confirmed_items:
        line_number = confirmed_item.get("line_number")
        source = confirmed_item.get("source", "bill")

        line_item = LineItem.query.filter_by(
            extracted_field_id=extracted.id if extracted else None,
            line_number=line_number,
            source=source,
        ).first()

        if line_item:
            if "amount" in confirmed_item:
                line_item.corrected_amount = confirmed_item["amount"]
            if "date" in confirmed_item:
                line_item.corrected_date = confirmed_item["date"]
            # cpt_code corrections accepted if user fixes an OCR misread
            if "cpt_code" in confirmed_item:
                line_item.cpt_code = confirmed_item["cpt_code"]

    # ── 5. Advance session status ─────────────────────────────────────────────
    session.status = SessionStatus.CONFIRMED
    db.session.commit()

    return (
        jsonify(
            {
                "session_id": session_id,
                "status": "confirmed",
            }
        ),
        200,
    )


# ── Helpers ───────────────────────────────────────────────────────────────────


def _error(status: int, code: str, message: str, session_id=None):
    return (
        jsonify(
            {
                "error_code": code,
                "message": message,
                "session_id": session_id,
            }
        ),
        status,
    )
