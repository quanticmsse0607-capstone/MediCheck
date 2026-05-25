"""
POST /letter  — FR-21, FR-22, FR-23
GET  /report/<session_id> — return analysis results + letter if generated

Generates dispute letter in both Word (.docx) and PDF formats.
Returns files as base64-encoded strings in the response body — no disk
storage required, works on Render free tier (no persistent disk needed).
"""

import json
import base64
import logging
from flask import Blueprint, request, jsonify, current_app
from extensions import db
from models import Session, ExtractedField, AnalysisResult, DisputeLetter, SessionStatus
from services.rag_client import RAGClient
from services.letter_builder import build_docx_bytes, build_pdf_bytes

logger = logging.getLogger(__name__)
letter_bp = Blueprint("letter", __name__)
rag_client = RAGClient()

ERR_SESSION_NOT_FOUND = "SESSION_NOT_FOUND"
ERR_NO_ANALYSIS_RESULTS = "NO_ANALYSIS_RESULTS"


@letter_bp.post("/letter")
def generate_letter():
    """
    Generate dispute letter in Word and PDF formats.
    Returns both files as base64-encoded strings — no disk storage needed.
    Frontend decodes and triggers browser download.

    Request JSON: { "session_id": "uuid" }

    Response 200: session_id, status, downloads: { docx: base64, pdf: base64 },
                  content_types: { docx: mime, pdf: mime }
    Response 404: SESSION_NOT_FOUND or NO_ANALYSIS_RESULTS
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

    # ── 2. Check analysis results exist ───────────────────────────────────────
    results = AnalysisResult.query.filter_by(session_id=session_id).all()
    if session.status not in (SessionStatus.ANALYSED, SessionStatus.LETTER_GENERATED):
        return _error(
            404,
            ERR_NO_ANALYSIS_RESULTS,
            "No analysis results found for this session. "
            "Run POST /analyse before requesting a letter.",
            session_id,
        )

    if not results:
        return _error(
            404,
            ERR_NO_ANALYSIS_RESULTS,
            "No analysis results found for this session. "
            "Run POST /analyse before requesting a letter.",
            session_id,
        )

    # ── 3. Build analysis data for letter ─────────────────────────────────────
    extracted = ExtractedField.query.filter_by(session_id=session_id).first()
    analysis_data = {
        "session_id": session_id,
        "patient_name": extracted.patient_name if extracted else None,
        "provider_name": extracted.provider_name if extracted else None,
        "date_of_service": extracted.date_of_service if extracted else None,
        "total_estimated_savings": sum(
            float(r.estimated_dollar_impact or 0) for r in results
        ),
        "errors": [r.to_dict() for r in results],
    }

    # ── 4. Call Service 3 for letter content ──────────────────────────────────
    rag_response = rag_client.generate_letter(session_id, analysis_data)
    letter_content = (
        rag_response.get("letter_content") if rag_response.get("success") else None
    )

    # ── 5. Generate letter in memory (no disk required) ───────────────────────
    try:
        docx_bytes = build_docx_bytes(analysis_data, letter_content)
        pdf_bytes = build_pdf_bytes(analysis_data, letter_content)
    except Exception as exc:
        logger.error(
            "Letter generation failed for session=%s: %s",
            session_id,
            exc,
            exc_info=True,
        )
        return _error(
            500,
            "LETTER_BUILD_FAILED",
            "Letter could not be generated. Please try again.",
            session_id,
        )

    # ── 6. Advance session status ─────────────────────────────────────────────
    session.status = SessionStatus.LETTER_GENERATED
    db.session.commit()

    # ── 7. Return base64-encoded files ────────────────────────────────────────
    return (
        jsonify(
            {
                "session_id": session_id,
                "status": "letter_generated",
                "downloads": {
                    "docx": base64.b64encode(docx_bytes).decode("utf-8"),
                    "pdf": base64.b64encode(pdf_bytes).decode("utf-8"),
                },
                "content_types": {
                    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    "pdf": "application/pdf",
                },
                "filenames": {
                    "docx": f"dispute_letter_{session_id[:8]}.docx",
                    "pdf": f"dispute_letter_{session_id[:8]}.pdf",
                },
            }
        ),
        200,
    )


@letter_bp.get("/report/<session_id>")
def get_report(session_id: str):
    """
    GET /report/<session_id>
    Returns analysis results for an existing session.
    Used by Service 1 ErrorReport page to check if already analysed.
    """
    session = Session.query.get(session_id)
    if not session:
        return _error(
            404,
            ERR_SESSION_NOT_FOUND,
            "No session found for the provided session_id.",
            session_id,
        )

    results = AnalysisResult.query.filter_by(session_id=session_id).all()
    total_savings = sum(float(r.estimated_dollar_impact or 0) for r in results)

    return (
        jsonify(
            {
                "session_id": session_id,
                "status": session.status,
                "total_errors": len(results),
                "total_estimated_savings": total_savings,
                "all_clear": len(results) == 0,
                "rag_available": (
                    all(r.explanation is not None for r in results) if results else True
                ),
                "errors": [r.to_dict() for r in results],
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
