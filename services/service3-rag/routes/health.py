from flask import Blueprint, jsonify
from rag.chain import is_ready

health_bp = Blueprint("health", __name__)


@health_bp.get("/health")
def health():
    """
    Health check endpoint.
    Must respond within 2 seconds (NFR-04).
    Does not require authentication.
    """
    rag_ready = is_ready()
    return (
        jsonify(
            {
                "status": "ok" if rag_ready else "degraded",
                "service": "rag-letter",
                "version": "1.0.0",
                "rag_chain_ready": rag_ready,
            }
        ),
        200,
    )
