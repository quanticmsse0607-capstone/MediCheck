"""
routes/draft_letter.py
POST /draft-letter — called by Service 2 to generate the formal dispute paragraph
for inclusion in the patient's billing dispute letter.

Contract (matches Service 2 rag_client.generate_letter()):

Request body:
    {
        "session_id": "uuid",
        "analysis": {
            "session_id": "uuid",
            "patient_name": "James Whitfield",
            "provider_name": "Atrium Health",
            "date_of_service": "2025-09-17",
            "total_estimated_savings": 747.00,
            "errors": [
                {
                    "error_id": "err_001",
                    "error_type": "Duplicate Charge",
                    "estimated_dollar_impact": 480.00,
                    ...
                }
            ]
        }
    }

Response (200):
    {
        "letter_content": "I respectfully request that ..."
    }
"""

import logging

from flask import Blueprint, jsonify, request

from rag.chain import draft_letter_content

logger = logging.getLogger(__name__)

draft_letter_bp = Blueprint("draft_letter", __name__)


@draft_letter_bp.post("/draft-letter")
def draft_letter():
    """
    Generates a RAG-grounded formal dispute paragraph for the billing dispute letter.
    Service 2 inserts this paragraph into the full letter document it builds locally.
    """
    body = request.get_json(silent=True)

    if not body or "analysis" not in body:
        return jsonify({"error": "Request body must include 'analysis'."}), 400

    session_id = body.get("session_id")
    analysis = body["analysis"]

    if not isinstance(analysis, dict):
        return jsonify({"error": "'analysis' must be an object."}), 400

    try:
        content = draft_letter_content(analysis)
    except RuntimeError as exc:
        logger.exception("RAG chain not ready for /draft-letter")
        return jsonify({"error": str(exc)}), 503
    except Exception as exc:
        logger.exception("RAG chain error in /draft-letter")
        return jsonify({"error": "RAG chain error.", "detail": str(exc)}), 500

    return jsonify({"session_id": session_id, "letter_content": content}), 200
