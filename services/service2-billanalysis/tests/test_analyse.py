"""
Integration tests for POST /analyse.
NFR-26: Service 3 is always mocked — no live HTTP calls.
Tests the full request → detection → partial response path.
"""

import pytest
import json
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app import create_app
from extensions import db as _db
from models import Session, ExtractedField, LineItem, SessionStatus


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
def client(app):
    with app.test_client() as c:
        with app.app_context():
            _db.create_all()
        yield c


@pytest.fixture
def confirmed_session(app):
    """Create a confirmed session with one line item in the test DB."""
    with app.app_context():
        session = Session(status=SessionStatus.CONFIRMED)
        _db.session.add(session)
        _db.session.flush()

        extracted = ExtractedField(
            session_id=session.session_id,
            patient_name="James Whitfield",
            provider_name="Atrium Health CMC",
            date_of_service="2025-09-17",
            total_billed=3200.00,
        )
        _db.session.add(extracted)
        _db.session.flush()

        _db.session.add(
            LineItem(
                extracted_field_id=extracted.id,
                line_number=1,
                cpt_code="29881",
                extracted_amount=3200.00,
                confidence=0.97,
                source="bill",
            )
        )
        _db.session.add(
            LineItem(
                extracted_field_id=extracted.id,
                line_number=7,
                cpt_code="29881",
                extracted_amount=3200.00,
                confidence=0.97,
                source="bill",
            )
        )

        _db.session.commit()
        return session.session_id


class TestAnalyseEndpoint:

    def test_returns_404_for_unknown_session(self, client):
        response = client.post("/analyse", json={"session_id": "nonexistent-id"})
        assert response.status_code == 404
        assert response.get_json()["error_code"] == "SESSION_NOT_FOUND"

    def test_returns_400_before_confirmation(self, app, client):
        """NFR-17: HTTP 400 if session not confirmed."""
        with app.app_context():
            session = Session(status=SessionStatus.EXTRACTED)
            _db.session.add(session)
            _db.session.commit()
            sid = session.session_id

        response = client.post("/analyse", json={"session_id": sid})
        assert response.status_code == 400
        assert response.get_json()["error_code"] == "NOT_CONFIRMED"

    def test_analyse_with_rag_available(self, app, client, confirmed_session, mocker):
        """Full analysis response when Service 3 responds successfully."""
        mocker.patch(
            "routes.analyse.rag_client.get_explanations",
            return_value={
                "success": True,
                "rag_available": True,
                "explanations": {
                    "err_001": {
                        "explanation": "Duplicate billing is not permitted.",
                        "citations": [
                            {"source": "CMS Manual", "section": "Ch 23", "url": ""}
                        ],
                    }
                },
            },
        )

        response = client.post("/analyse", json={"session_id": confirmed_session})
        data = response.get_json()

        assert response.status_code == 200
        assert data["rag_available"] is True
        assert data["total_errors"] >= 1
        assert data["errors"][0]["explanation"] == "Duplicate billing is not permitted."

    def test_analyse_partial_response_on_rag_timeout(
        self, app, client, confirmed_session, mocker
    ):
        """
        NFR-02, US-015: When Service 3 times out, return partial response.
        explanation: null, citations: [], rag_available: false.
        Response is still HTTP 200 — not a 503.
        """
        mocker.patch(
            "routes.analyse.rag_client.get_explanations",
            return_value={
                "success": False,
                "rag_available": False,
                "explanations": {},
            },
        )

        response = client.post("/analyse", json={"session_id": confirmed_session})
        data = response.get_json()

        assert response.status_code == 200
        assert data["rag_available"] is False
        for error in data["errors"]:
            assert error["explanation"] is None
            assert error["citations"] == []

    def test_all_clear_response_when_no_errors(self, app, client, mocker):
        """FR-10: no errors found → all_clear: true, errors: []."""
        with app.app_context():
            session = Session(status=SessionStatus.CONFIRMED)
            _db.session.add(session)
            _db.session.flush()
            extracted = ExtractedField(
                session_id=session.session_id,
                patient_name="Clean Bill Patient",
                provider_name="Good Hospital",
                date_of_service="2025-09-17",
                total_billed=82.00,
            )
            _db.session.add(extracted)
            _db.session.flush()
            _db.session.add(
                LineItem(
                    extracted_field_id=extracted.id,
                    line_number=1,
                    cpt_code="99999",  # CPT not in any fee schedule
                    extracted_amount=82.00,
                    confidence=0.99,
                    source="bill",
                )
            )
            _db.session.commit()
            sid = session.session_id

        mocker.patch(
            "routes.analyse.rag_client.get_explanations",
            return_value={"success": True, "rag_available": True, "explanations": {}},
        )

        response = client.post("/analyse", json={"session_id": sid})
        data = response.get_json()

        assert response.status_code == 200
        assert data["all_clear"] is True
        assert data["errors"] == []
        assert data["total_errors"] == 0
