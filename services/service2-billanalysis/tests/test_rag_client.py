"""
Unit tests for services/rag_client.py — RAGClient HTTP methods.

Tests the actual HTTP call paths (success, timeout, connection error, HTTP error)
that are bypassed when rag_client is mocked at the route level in other tests.
NFR-18: verifies timeout is always passed to requests.post.
NFR-02: verifies partial response returned on any Service 3 failure.
"""

import sys
import os

import pytest
import requests as req

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app import create_app
from services.rag_client import RAGClient


# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture
def app():
    application = create_app("development")
    application.config.update(
        {
            "TESTING": True,
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
            "SERVICE3_URL": "http://mock-service3",
            "SERVICE3_TIMEOUT_SECONDS": 10,
        }
    )
    return application


@pytest.fixture
def client_ctx(app):
    """Provides an active app context — RAGClient lazy-loads config from current_app."""
    with app.app_context():
        yield RAGClient()


# ── Sample payloads ───────────────────────────────────────────────────────────

_ERRORS = [
    {
        "error_id": "err_001",
        "module": "duplicate_charge",
        "error_type": "Duplicate Charge",
        "description": "CPT 29881 billed twice.",
        "confidence": "high",
    }
]

_ANALYSIS = {
    "session_id": "abc-123",
    "patient_name": "James Whitfield",
    "errors": _ERRORS,
}


# ══════════════════════════════════════════════════════════════════════════════
# RAGClient.get_explanations
# ══════════════════════════════════════════════════════════════════════════════


class TestGetExplanations:

    def test_returns_explanations_on_success(self, client_ctx, mocker):
        mocker.patch(
            "services.rag_client.requests.post",
            return_value=mocker.Mock(
                status_code=200,
                json=lambda: {
                    "explanations": {
                        "err_001": {
                            "explanation": "Duplicate CPT billing is not permitted.",
                            "citations": [{"source": "NCCI", "section": "Ch 1"}],
                        }
                    }
                },
                raise_for_status=lambda: None,
            ),
        )

        result = client_ctx.get_explanations("abc-123", _ERRORS)

        assert result["success"] is True
        assert result["rag_available"] is True
        assert "err_001" in result["explanations"]
        assert result["explanations"]["err_001"]["explanation"] == "Duplicate CPT billing is not permitted."

    def test_passes_explicit_timeout(self, client_ctx, mocker):
        """NFR-18: timeout must always be passed to requests.post."""
        mock_post = mocker.patch(
            "services.rag_client.requests.post",
            return_value=mocker.Mock(
                status_code=200,
                json=lambda: {"explanations": {}},
                raise_for_status=lambda: None,
            ),
        )

        client_ctx.get_explanations("abc-123", _ERRORS)

        _, kwargs = mock_post.call_args
        assert "timeout" in kwargs
        assert kwargs["timeout"] == 10

    def test_returns_partial_on_timeout(self, client_ctx, mocker):
        """NFR-02: timeout → success: False, rag_available: False, never raises."""
        mocker.patch(
            "services.rag_client.requests.post",
            side_effect=req.Timeout(),
        )

        result = client_ctx.get_explanations("abc-123", _ERRORS)

        assert result["success"] is False
        assert result["rag_available"] is False
        assert result["explanations"] == {}

    def test_returns_partial_on_http_error(self, client_ctx, mocker):
        mock_response = mocker.Mock(status_code=503, text="Service Unavailable")
        mocker.patch(
            "services.rag_client.requests.post",
            return_value=mocker.Mock(
                raise_for_status=mocker.Mock(
                    side_effect=req.HTTPError(response=mock_response)
                )
            ),
        )

        result = client_ctx.get_explanations("abc-123", _ERRORS)

        assert result["success"] is False
        assert result["rag_available"] is False

    def test_returns_partial_on_connection_error(self, client_ctx, mocker):
        mocker.patch(
            "services.rag_client.requests.post",
            side_effect=req.ConnectionError(),
        )

        result = client_ctx.get_explanations("abc-123", _ERRORS)

        assert result["success"] is False
        assert result["rag_available"] is False


# ══════════════════════════════════════════════════════════════════════════════
# RAGClient.generate_letter
# ══════════════════════════════════════════════════════════════════════════════


class TestGenerateLetter:

    def test_returns_letter_content_on_success(self, client_ctx, mocker):
        mocker.patch(
            "services.rag_client.requests.post",
            return_value=mocker.Mock(
                status_code=200,
                json=lambda: {"letter_content": "I am writing to dispute these charges."},
                raise_for_status=lambda: None,
            ),
        )

        result = client_ctx.generate_letter("abc-123", _ANALYSIS)

        assert result["success"] is True
        assert result["letter_content"] == "I am writing to dispute these charges."

    def test_passes_explicit_timeout(self, client_ctx, mocker):
        """NFR-18: timeout must always be passed to requests.post."""
        mock_post = mocker.patch(
            "services.rag_client.requests.post",
            return_value=mocker.Mock(
                status_code=200,
                json=lambda: {"letter_content": "Letter text."},
                raise_for_status=lambda: None,
            ),
        )

        client_ctx.generate_letter("abc-123", _ANALYSIS)

        _, kwargs = mock_post.call_args
        assert "timeout" in kwargs
        assert kwargs["timeout"] == 10

    def test_returns_partial_on_timeout(self, client_ctx, mocker):
        """NFR-02: timeout → success: False, letter_content: None, never raises."""
        mocker.patch(
            "services.rag_client.requests.post",
            side_effect=req.Timeout(),
        )

        result = client_ctx.generate_letter("abc-123", _ANALYSIS)

        assert result["success"] is False
        assert result["letter_content"] is None

    def test_returns_partial_on_request_exception(self, client_ctx, mocker):
        mocker.patch(
            "services.rag_client.requests.post",
            side_effect=req.RequestException("unexpected"),
        )

        result = client_ctx.generate_letter("abc-123", _ANALYSIS)

        assert result["success"] is False
        assert result["letter_content"] is None
