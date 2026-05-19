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


VALID_MEDICARE_ERROR_1 = {
    "error_id": "err_med_001",
    "module": "medicare_rate_outlier",
    "error_type": "Medicare Rate Outlier",
    "description": "CPT 99215 is billed at $650.00, which is 793% of the Medicare rate of $82.00.",
    "line_items_affected": [9],
    "estimated_dollar_impact": 568.0,
    "confidence": "high",
}

VALID_MEDICARE_ERROR_2 = {
    "error_id": "err_med_002",
    "module": "medicare_rate_outlier",
    "error_type": "Medicare Rate Outlier",
    "description": "CPT 99282 is billed at $850.00, which is 1809% of the Medicare rate of $47.00.",
    "line_items_affected": [1],
    "estimated_dollar_impact": 803.0,
    "confidence": "high",
}

MOCK_MODULE_RESULT = {
    "explanation": "The CMS Physician Fee Schedule uses RVUs and a conversion factor.",
    "citations": [
        {"source": "CMS Physician Fee Schedule 2026", "section": "p. 1", "url": None}
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


def test_explain_session_id_echoed_in_response(client):
    mock_result = {**VALID_ERROR, **MOCK_EXPLANATION}
    with patch("routes.explain.explain_detection", return_value=mock_result):
        response = client.post(
            "/explain",
            json={"session_id": "test-session-abc", "errors": [VALID_ERROR]},
        )
    assert response.get_json()["session_id"] == "test-session-abc"


def test_explain_session_id_optional(client):
    """session_id is accepted but not required — Service 2 always sends it."""
    mock_result = {**VALID_ERROR, **MOCK_EXPLANATION}
    with patch("routes.explain.explain_detection", return_value=mock_result):
        response = client.post("/explain", json={"errors": [VALID_ERROR]})
    assert response.status_code == 200


# ── Shared module explanations ────────────────────────────────────────────────


def test_explain_shared_module_uses_module_context_not_detection(client):
    """medicare_rate_outlier errors use explain_module_context, not explain_detection."""
    with patch(
        "routes.explain.explain_module_context", return_value=MOCK_MODULE_RESULT
    ) as mock_ctx, patch("routes.explain.explain_detection") as mock_detect:
        response = client.post(
            "/explain",
            json={"session_id": "test-123", "errors": [VALID_MEDICARE_ERROR_1]},
        )
    assert response.status_code == 200
    mock_ctx.assert_called_once()
    mock_detect.assert_not_called()


def test_explain_shared_module_called_once_for_multiple_errors(client):
    """explain_module_context is called exactly once even when two medicare errors are present."""
    with patch(
        "routes.explain.explain_module_context", return_value=MOCK_MODULE_RESULT
    ) as mock_ctx:
        response = client.post(
            "/explain",
            json={
                "session_id": "test-123",
                "errors": [VALID_MEDICARE_ERROR_1, VALID_MEDICARE_ERROR_2],
            },
        )
    assert response.status_code == 200
    mock_ctx.assert_called_once_with("medicare_rate_outlier")


def test_explain_shared_module_explanation_identical_across_errors(client):
    """Both medicare errors receive the same explanation text and citations."""
    with patch(
        "routes.explain.explain_module_context", return_value=MOCK_MODULE_RESULT
    ):
        response = client.post(
            "/explain",
            json={
                "session_id": "test-123",
                "errors": [VALID_MEDICARE_ERROR_1, VALID_MEDICARE_ERROR_2],
            },
        )
    data = response.get_json()["explanations"]
    assert data["err_med_001"]["explanation"] == data["err_med_002"]["explanation"]
    assert data["err_med_001"]["citations"] == data["err_med_002"]["citations"]


def test_explain_mixed_modules_routes_correctly(client):
    """Medicare error uses explain_module_context; non-medicare error uses explain_detection."""
    mock_detect_result = {**VALID_ERROR, **MOCK_EXPLANATION}
    with patch(
        "routes.explain.explain_module_context", return_value=MOCK_MODULE_RESULT
    ) as mock_ctx, patch(
        "routes.explain.explain_detection", return_value=mock_detect_result
    ) as mock_detect:
        response = client.post(
            "/explain",
            json={
                "session_id": "test-123",
                "errors": [VALID_MEDICARE_ERROR_1, VALID_ERROR],
            },
        )
    assert response.status_code == 200
    mock_ctx.assert_called_once_with("medicare_rate_outlier")
    mock_detect.assert_called_once()
    data = response.get_json()["explanations"]
    assert "err_med_001" in data
    assert "err_001" in data


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
