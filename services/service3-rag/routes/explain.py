"""
routes/explain.py
POST /explain — receives DetectionResults from Service 2, returns grounded
plain-English explanations with source citations for each detected billing error.

Contract (matches Service 2 rag_client.py):

Request body:
    {
        "session_id": "uuid",
        "errors": [
            {
                "error_id": "err_001",
                "module": "duplicate_charge",
                "error_type": "Duplicate Charge",
                "description": "...",
                "line_items_affected": [2, 4],
                "estimated_dollar_impact": 150.00,
                "confidence": "high"
            },
            ...
        ]
    }

Response (200):
    {
        "explanations": {
            "err_001": {
                "explanation": "Plain-English explanation grounded in RAG sources.",
                "citations": ["No Surprises Act at a Glance, p. 2", ...]
            },
            ...
        }
    }
"""

import logging

from flask import Blueprint, jsonify, request

from rag.chain import explain_detection

logger = logging.getLogger(__name__)

explain_bp = Blueprint("explain", __name__)

# Known module names from Service 2 detectors — used for logging only.
# We do not reject unknown modules so that new detectors don't break this service.
KNOWN_MODULES = {
    "duplicate_charge",
    "medicare_rate_outlier",
    "no_surprises_act",
    "eob_reconciliation",
}

REQUIRED_FIELDS = ("error_id", "module", "error_type", "description")


@explain_bp.post("/explain")
def explain():
    """
    Accepts a list of error dicts from Service 2, returns a dict of
    RAG-grounded explanations and citations keyed by error_id.
    """
    body = request.get_json(silent=True)

    if not body or "errors" not in body:
        return jsonify({"error": "Request body must include an 'errors' list."}), 400

    errors = body["errors"]
    if not isinstance(errors, list):
        return jsonify({"error": "'errors' must be a list."}), 400

    if len(errors) == 0:
        return jsonify({"explanations": {}}), 200

    explanations: dict[str, dict] = {}

    for i, error in enumerate(errors):
        # Validate required fields
        for field in REQUIRED_FIELDS:
            if not error.get(field):
                return (
                    jsonify(
                        {
                            "error": f"Error at index {i} is missing required field '{field}'."
                        }
                    ),
                    400,
                )

        if error["module"] not in KNOWN_MODULES:
            logger.warning(
                "Received unknown module '%s' — processing anyway.", error["module"]
            )

        try:
            result = explain_detection(error)
        except RuntimeError as exc:
            logger.exception("RAG chain not ready for error at index %d", i)
            return jsonify({"error": str(exc)}), 503
        except Exception as exc:
            logger.exception(
                "RAG chain error for module '%s' at index %d", error.get("module"), i
            )
            return jsonify({"error": "RAG chain error.", "detail": str(exc)}), 500

        explanations[error["error_id"]] = {
            "explanation": result["explanation"],
            "citations": result["citations"],
        }

    return jsonify({"explanations": explanations}), 200
