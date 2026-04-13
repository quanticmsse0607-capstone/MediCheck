"""
tests/test_health.py
Unit tests for GET /health.
"""

import pytest


def test_health_returns_200(client):
    response = client.get("/health")
    assert response.status_code == 200


def test_health_response_shape(client):
    response = client.get("/health")
    data = response.get_json()
    assert data["status"] == "ok"
    assert data["service"] == "rag-letter"
