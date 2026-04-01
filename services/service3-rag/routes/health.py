from flask import Blueprint, jsonify

health_bp = Blueprint("health", __name__)


@health_bp.get("/health")
def health():
    """
    Health check endpoint.
    Must respond within 2 seconds (NFR-04).
    Does not require authentication.
    """
    return jsonify({
        "status": "ok",
        "service": "rag-letter",
        "version": "1.0.0",
    }), 200
