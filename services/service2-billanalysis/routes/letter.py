"""
POST /letter  — FR-21, FR-22, FR-23
GET  /download/<session_id>/<filename> — serve generated files

Generates dispute letter in both Word (.docx) and PDF formats.
Files are stored on disk and re-served without regeneration (FR-23).
"""

import os
import json
from flask import Blueprint, request, jsonify, send_file, current_app
from extensions import db
from models import Session, ExtractedField, AnalysisResult, DisputeLetter, SessionStatus
from services.rag_client import RAGClient
from services.letter_builder import build_docx, build_pdf

letter_bp = Blueprint("letter", __name__)
rag_client = RAGClient()

ERR_SESSION_NOT_FOUND = "SESSION_NOT_FOUND"
ERR_NO_ANALYSIS_RESULTS = "NO_ANALYSIS_RESULTS"


@letter_bp.post("/letter")
def generate_letter():
    """
    Generate dispute letter in Word and PDF formats.
    Calls Service 3 to generate letter content, then formats locally.
    Both files are stored and re-servable without repeating analysis (FR-23).

    Request JSON: { "session_id": "uuid" }

    Response 200: session_id, status, downloads: { docx: url, pdf: url }
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

    # ── 2. Check analysis results exist (NFR-17: HTTP 404 if no analysis) ─────
    results = AnalysisResult.query.filter_by(session_id=session_id).all()
    if session.status not in (SessionStatus.ANALYSED, SessionStatus.LETTER_GENERATED):
        return _error(
            404,
            ERR_NO_ANALYSIS_RESULTS,
            "No analysis results found for this session. "
            "Run POST /analyse before requesting a letter.",
            session_id,
        )

    # ── 3. If letter already generated, return existing download URLs (FR-23) ─
    existing = DisputeLetter.query.filter_by(session_id=session_id).first()
    if (
        existing
        and os.path.exists(existing.docx_path or "")
        and os.path.exists(existing.pdf_path or "")
    ):
        return (
            jsonify(
                {
                    "session_id": session_id,
                    "status": "letter_generated",
                    "downloads": {
                        "docx": _download_url(session_id, "letter.docx"),
                        "pdf": _download_url(session_id, "letter.pdf"),
                    },
                }
            ),
            200,
        )

    # ── 4. Load data for letter ───────────────────────────────────────────────
    extracted = ExtractedField.query.filter_by(session_id=session_id).first()
    analysis_data = {
        "session_id": session_id,
        "patient_name": extracted.patient_name if extracted else "",
        "provider_name": extracted.provider_name if extracted else "",
        "date_of_service": extracted.date_of_service if extracted else "",
        "errors": [r.to_dict() for r in results],
        "total_estimated_savings": sum(
            float(r.estimated_dollar_impact or 0) for r in results
        ),
    }

    # ── 5. Call Service 3 to generate letter content ──────────────────────────
    rag_response = rag_client.generate_letter(session_id, analysis_data)
    letter_content = rag_response.get("letter_content")

    # ── 6. Build output directory ─────────────────────────────────────────────
    output_dir = os.path.join(current_app.root_path, "generated_letters", session_id)
    os.makedirs(output_dir, exist_ok=True)

    docx_path = os.path.join(output_dir, "letter.docx")
    pdf_path = os.path.join(output_dir, "letter.pdf")

    # ── 7. Generate Word and PDF ──────────────────────────────────────────────
    build_docx(analysis_data, letter_content, docx_path)
    build_pdf(analysis_data, letter_content, pdf_path)

    # ── 8. Persist letter record ──────────────────────────────────────────────
    if existing:
        existing.docx_path = docx_path
        existing.pdf_path = pdf_path
    else:
        db.session.add(
            DisputeLetter(
                session_id=session_id,
                docx_path=docx_path,
                pdf_path=pdf_path,
            )
        )

    session.status = SessionStatus.LETTER_GENERATED
    db.session.commit()

    return (
        jsonify(
            {
                "session_id": session_id,
                "status": "letter_generated",
                "downloads": {
                    "docx": _download_url(session_id, "letter.docx"),
                    "pdf": _download_url(session_id, "letter.pdf"),
                },
            }
        ),
        200,
    )


@letter_bp.get("/download/<session_id>/<filename>")
def download_file(session_id: str, filename: str):
    """
    Serve a generated letter file.
    Both formats are retrievable without re-running analysis (FR-23).
    """
    if filename not in ("letter.docx", "letter.pdf"):
        return _error(
            400,
            "INVALID_FILENAME",
            "filename must be letter.docx or letter.pdf",
            session_id,
        )

    letter = DisputeLetter.query.filter_by(session_id=session_id).first()
    if not letter:
        return _error(
            404,
            ERR_NO_ANALYSIS_RESULTS,
            "No letter found for this session.",
            session_id,
        )

    path = letter.docx_path if filename == "letter.docx" else letter.pdf_path

    if not path or not os.path.exists(path):
        return _error(
            404, "FILE_NOT_FOUND", "Letter file not found on server.", session_id
        )

    mimetype = (
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        if filename == "letter.docx"
        else "application/pdf"
    )

    return send_file(
        path,
        mimetype=mimetype,
        as_attachment=True,
        download_name=filename,
    )

# Add the report endpoint
@letter_bp.get("/report/<session_id>")
def get_report(session_id):
    """
    GET /report/<session_id>
    Returns analysis results + download URLs if letter already generated.
    FR-23: both formats retrievable without repeating analysis.
    """
    session = Session.query.get(session_id)
    if not session:
        return _error(404, ERR_SESSION_NOT_FOUND,
                      "No session found.", session_id)

    results = AnalysisResult.query.filter_by(session_id=session_id).all()
    letter  = DisputeLetter.query.filter_by(session_id=session_id).first()

    extracted = ExtractedField.query.filter_by(session_id=session_id).first()
    total_savings = sum(float(r.estimated_dollar_impact or 0) for r in results)

    response = {
        "session_id": session_id,
        "status": session.status,
        "total_errors": len(results),
        "total_estimated_savings": total_savings,
        "all_clear": len(results) == 0,
        "rag_available": True,
        "errors": [r.to_dict() for r in results],
    }

    if letter and os.path.exists(letter.docx_path or ""):
        base = current_app.config.get("SERVICE2_BASE_URL", "http://localhost:5001")
        response["downloads"] = {
            "docx": f"{base}/download/{session_id}/letter.docx",
            "pdf":  f"{base}/download/{session_id}/letter.pdf",
        }

    return jsonify(response), 200

# ── Helpers ───────────────────────────────────────────────────────────────────


def _download_url(session_id: str, filename: str) -> str:
    """Build absolute download URL (agreed decision: full absolute URLs)."""
    base = current_app.config.get("SERVICE2_BASE_URL", "http://localhost:5000")
    return f"{base}/download/{session_id}/{filename}"


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
