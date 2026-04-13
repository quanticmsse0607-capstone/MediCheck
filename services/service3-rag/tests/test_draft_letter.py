"""
tests/test_draft_letter.py
Unit tests for POST /draft-letter (routes/draft_letter.py).

draft_letter_content() is mocked at the route import level — these tests cover
only the HTTP layer: request validation, response shape, and error handling.
"""

import pytest
from unittest.mock import patch

VALID_ANALYSIS = {
    "session_id": "test-session-001",
    "patient_name": "James Whitfield",
    "provider_name": "Atrium Health Carolinas Medical Center",
    "date_of_service": "2025-09-17",
    "total_estimated_savings": 747.0,
    "errors": [
        {
            "error_id": "err_001",
            "error_type": "Duplicate Charge",
            "estimated_dollar_impact": 480.0,
        }
    ],
}

MOCK_LETTER_CONTENT = (
    "I respectfully request that Atrium Health review the above errors "
    "and issue a corrected bill reflecting a total adjustment of $747.00."
)


# ── Valid requests ────────────────────────────────────────────────────────────


def test_draft_letter_valid_request_returns_200(client):
    with patch(
        "routes.draft_letter.draft_letter_content", return_value=MOCK_LETTER_CONTENT
    ):
        response = client.post(
            "/draft-letter",
            json={
                "session_id": "test-session-001",
                "analysis": VALID_ANALYSIS,
            },
        )
    assert response.status_code == 200


def test_draft_letter_response_contains_letter_content(client):
    with patch(
        "routes.draft_letter.draft_letter_content", return_value=MOCK_LETTER_CONTENT
    ):
        response = client.post(
            "/draft-letter",
            json={
                "session_id": "test-session-001",
                "analysis": VALID_ANALYSIS,
            },
        )
    data = response.get_json()
    assert "letter_content" in data
    assert isinstance(data["letter_content"], str)
    assert len(data["letter_content"]) > 0


def test_draft_letter_session_id_optional(client):
    """session_id is accepted but not required — Service 2 always sends it."""
    with patch(
        "routes.draft_letter.draft_letter_content", return_value=MOCK_LETTER_CONTENT
    ):
        response = client.post("/draft-letter", json={"analysis": VALID_ANALYSIS})
    assert response.status_code == 200


# ── Validation errors ─────────────────────────────────────────────────────────


def test_draft_letter_missing_analysis_key_returns_400(client):
    response = client.post("/draft-letter", json={"session_id": "test-123"})
    assert response.status_code == 400


def test_draft_letter_analysis_not_dict_returns_400(client):
    response = client.post("/draft-letter", json={"analysis": "not-a-dict"})
    assert response.status_code == 400


def test_draft_letter_empty_body_returns_400(client):
    response = client.post("/draft-letter", json={})
    assert response.status_code == 400


# ── Error handling ────────────────────────────────────────────────────────────


def test_draft_letter_chain_not_initialized_returns_503(client):
    with patch(
        "routes.draft_letter.draft_letter_content",
        side_effect=RuntimeError("not initialized"),
    ):
        response = client.post(
            "/draft-letter",
            json={
                "session_id": "test-123",
                "analysis": VALID_ANALYSIS,
            },
        )
    assert response.status_code == 503


def test_draft_letter_unexpected_error_returns_500(client):
    with patch(
        "routes.draft_letter.draft_letter_content",
        side_effect=Exception("unexpected"),
    ):
        response = client.post(
            "/draft-letter",
            json={
                "session_id": "test-123",
                "analysis": VALID_ANALYSIS,
            },
        )
    assert response.status_code == 500
