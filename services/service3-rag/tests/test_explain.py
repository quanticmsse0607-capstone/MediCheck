"""
tests/test_explain.py
Unit tests for POST /explain (routes/explain.py).

explain_detection() is mocked at the route import level — these tests cover
only the HTTP layer: request validation, response shape, and error handling.
"""

import pytest
from unittest.mock import patch

VALID_ERROR = {
    "error_id": "err_001",
    "module": "duplicate_charge",
    "error_type": "Duplicate Charge",
    "description": "CPT 99213 appears twice on the same date.",
    "line_items_affected": [1, 3],
    "estimated_dollar_impact": 150.0,
    "confidence": "high",
}

MOCK_EXPLANATION = {
    "explanation": "This charge appears twice on your bill.",
    "citations": [
        {"source": "No Surprises Act at a Glance", "section": "p. 1", "url": None}
    ],
}


# ── Valid requests ────────────────────────────────────────────────────────────


def test_explain_valid_request_returns_200(client):
    mock_result = {**VALID_ERROR, **MOCK_EXPLANATION}
    with patch("routes.explain.explain_detection", return_value=mock_result):
        response = client.post(
            "/explain",
            json={
                "session_id": "test-123",
                "errors": [VALID_ERROR],
            },
        )
    assert response.status_code == 200


def test_explain_response_keyed_by_error_id(client):
    mock_result = {**VALID_ERROR, **MOCK_EXPLANATION}
    with patch("routes.explain.explain_detection", return_value=mock_result):
        response = client.post(
            "/explain",
            json={
                "session_id": "test-123",
                "errors": [VALID_ERROR],
            },
        )
    data = response.get_json()
    assert "explanations" in data
    assert "err_001" in data["explanations"]


def test_explain_response_contains_explanation_and_citations(client):
    mock_result = {**VALID_ERROR, **MOCK_EXPLANATION}
    with patch("routes.explain.explain_detection", return_value=mock_result):
        response = client.post(
            "/explain",
            json={
                "session_id": "test-123",
                "errors": [VALID_ERROR],
            },
        )
    entry = response.get_json()["explanations"]["err_001"]
    assert "explanation" in entry
    assert "citations" in entry


def test_explain_empty_errors_returns_empty_dict(client):
    response = client.post(
        "/explain",
        json={
            "session_id": "test-123",
            "errors": [],
        },
    )
    assert response.status_code == 200
    assert response.get_json()["explanations"] == {}


def test_explain_session_id_optional(client):
    """session_id is accepted but not required — Service 2 always sends it."""
    mock_result = {**VALID_ERROR, **MOCK_EXPLANATION}
    with patch("routes.explain.explain_detection", return_value=mock_result):
        response = client.post("/explain", json={"errors": [VALID_ERROR]})
    assert response.status_code == 200


# ── Validation errors ─────────────────────────────────────────────────────────


def test_explain_missing_errors_key_returns_400(client):
    response = client.post("/explain", json={"session_id": "test-123"})
    assert response.status_code == 400


def test_explain_errors_not_a_list_returns_400(client):
    response = client.post("/explain", json={"errors": "not-a-list"})
    assert response.status_code == 400


@pytest.mark.parametrize(
    "missing_field", ["error_id", "module", "error_type", "description"]
)
def test_explain_missing_required_field_returns_400(client, missing_field):
    error = {k: v for k, v in VALID_ERROR.items() if k != missing_field}
    response = client.post("/explain", json={"errors": [error]})
    assert response.status_code == 400


# ── Error handling ────────────────────────────────────────────────────────────


def test_explain_chain_not_initialized_returns_503(client):
    with patch(
        "routes.explain.explain_detection", side_effect=RuntimeError("not initialized")
    ):
        response = client.post(
            "/explain",
            json={
                "session_id": "test-123",
                "errors": [VALID_ERROR],
            },
        )
    assert response.status_code == 503


def test_explain_unexpected_chain_error_returns_500(client):
    with patch("routes.explain.explain_detection", side_effect=Exception("unexpected")):
        response = client.post(
            "/explain",
            json={
                "session_id": "test-123",
                "errors": [VALID_ERROR],
            },
        )
    assert response.status_code == 500
