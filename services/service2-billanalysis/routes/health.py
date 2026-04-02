from flask import Blueprint, jsonify

health_bp = Blueprint("health", __name__)


@health_bp.get("/health")
def health():
    """
    Health check endpoint (NFR-12, US-016).
    Must respond within 2 seconds (NFR-04).
    Does not require authentication (US-016 AC5).
    Must be implemented and responding before any other endpoint is ready (NFR-12).
    """
    return (
        jsonify(
            {
                "status": "ok",
                "service": "bill-analysis",
                "version": "1.0.0",
            }
        ),
        200,
    )
