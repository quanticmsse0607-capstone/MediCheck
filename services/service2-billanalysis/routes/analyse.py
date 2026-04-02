"""
POST /analyse — FR-10, FR-16, NFR-01, NFR-02, NFR-17, NFR-18
Runs all four detectors, calls Service 3 for explanations, returns results.
"""

import json
from flask import Blueprint, request, jsonify
from extensions import db
from models import Session, ExtractedField, LineItem, AnalysisResult, SessionStatus
from services.engine import ErrorDetectionEngine
from services.rag_client import RAGClient

analyse_bp = Blueprint("analyse", __name__)
engine = ErrorDetectionEngine()
rag_client = RAGClient()

ERR_SESSION_NOT_FOUND = "SESSION_NOT_FOUND"
ERR_NOT_CONFIRMED = "NOT_CONFIRMED"


@analyse_bp.post("/analyse")
def analyse():
    """
    Run error detection on confirmed session data.
    Calls Service 3 for RAG explanations with a 10-second timeout (NFR-18).
    Returns partial response if Service 3 times out (NFR-02, US-015).

    Request JSON: { "session_id": "uuid" }

    Response 200 (full):    errors[], total_errors, total_savings, all_clear, rag_available: true
    Response 200 (partial): errors[] with explanation: null, rag_available: false
    Response 200 (clear):   errors: [], all_clear: true
    Response 400:           NOT_CONFIRMED
    Response 404:           SESSION_NOT_FOUND
    """

    data = request.get_json(silent=True) or {}
    session_id = data.get("session_id")

    # ── 1. Validate session ───────────────────────────────────────────────────
    session = Session.query.get(session_id)
    if not session:
        return _error(
            404,
            ERR_SESSION_NOT_FOUND,
            "No session found for the provided session_id.",
            session_id,
        )

    # ── 2. Validate session state (NFR-17: HTTP 400 before confirmation) ──────
    if not SessionStatus.can_transition_to(session.status, SessionStatus.ANALYSED):
        return _error(
            400,
            ERR_NOT_CONFIRMED,
            f"Session status is '{session.status}'. "
            "Analysis requires status 'confirmed'.",
            session_id,
        )

    # ── 3. Load confirmed fields from DB ──────────────────────────────────────
    confirmed_fields = _load_confirmed_fields(session_id)

    # ── 4. Run all four detectors ─────────────────────────────────────────────
    engine_output = engine.run(confirmed_fields)
    detection_results = engine_output["results"]
    all_clear = engine_output["all_clear"]

    # ── 5. Build errors list with error_ids ───────────────────────────────────
    errors_payload = []
    for idx, result in enumerate(detection_results, start=1):
        errors_payload.append(
            {
                "error_id": f"err_{idx:03d}",
                **result.to_dict(),
            }
        )

    # ── 6. Call Service 3 for explanations (10s timeout — NFR-18) ────────────
    rag_response = rag_client.get_explanations(session_id, errors_payload)
    rag_available = rag_response["rag_available"]

    # ── 7. Merge explanations into errors payload ─────────────────────────────
    if rag_available:
        explanations = rag_response.get("explanations", {})
        for error in errors_payload:
            eid = error["error_id"]
            if eid in explanations:
                error["explanation"] = explanations[eid].get("explanation")
                error["citations"] = explanations[eid].get("citations", [])
    else:
        # Partial response — explanation: null, citations: [] (US-015 AC1)
        for error in errors_payload:
            error["explanation"] = None
            error["citations"] = []

    # ── 8. Persist results ────────────────────────────────────────────────────
    # Clear any previous results for this session (re-analyse scenario)
    AnalysisResult.query.filter_by(session_id=session_id).delete()

    for error in errors_payload:
        db.session.add(
            AnalysisResult(
                session_id=session_id,
                error_id=error["error_id"],
                module=error["module"],
                error_type=error["error_type"],
                description=error["description"],
                line_items_affected=json.dumps(error["line_items_affected"]),
                estimated_dollar_impact=error["estimated_dollar_impact"],
                confidence=error["confidence"],
                explanation=error.get("explanation"),
                citations=json.dumps(error.get("citations", [])),
            )
        )

    # ── 9. Advance session status ─────────────────────────────────────────────
    session.status = SessionStatus.ANALYSED
    db.session.commit()

    # ── 10. Build response ────────────────────────────────────────────────────
    total_savings = round(sum(e["estimated_dollar_impact"] for e in errors_payload), 2)

    return (
        jsonify(
            {
                "session_id": session_id,
                "status": "analysed",
                "total_errors": len(errors_payload),
                "total_estimated_savings": total_savings,
                "all_clear": all_clear,
                "rag_available": rag_available,
                "errors": errors_payload,
            }
        ),
        200,
    )


# ── Helpers ───────────────────────────────────────────────────────────────────


def _load_confirmed_fields(session_id: str) -> dict:
    """Load confirmed fields + line items from DB into the shape detectors expect."""
    extracted = ExtractedField.query.filter_by(session_id=session_id).first()
    if not extracted:
        return {"line_items": []}

    line_items = []
    for li in LineItem.query.filter_by(extracted_field_id=extracted.id).all():
        line_items.append(
            {
                "line_number": li.line_number,
                "cpt_code": li.cpt_code,
                "amount": li.amount,  # uses corrected if available (model property)
                "date": li.corrected_date or li.extracted_date,
                "quantity": li.quantity,
                "source": li.source,
            }
        )

    return {
        "patient_name": extracted.patient_name,
        "provider_name": extracted.provider_name,
        "date_of_service": extracted.date_of_service,
        "total_billed": (
            float(extracted.total_billed) if extracted.total_billed else None
        ),
        "line_items": line_items,
    }


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
