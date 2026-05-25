"""
Integration tests for GET /report/<session_id> and POST /letter.

Updated for base64 letter response — no file storage, no download endpoints.
Letters are returned as base64-encoded strings in the POST /letter response.

NFR-26: Service 3 is always mocked — no live HTTP calls.
"""

import json
import os
import sys
import base64

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app import create_app
from extensions import db as _db
from models import Session, ExtractedField, AnalysisResult, DisputeLetter, SessionStatus


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
            "SERVICE2_BASE_URL": "http://localhost:5001",
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
def analysed_session(app):
    """Session in ANALYSED state with one error result."""
    with app.app_context():
        session = Session(status=SessionStatus.ANALYSED)
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
            AnalysisResult(
                session_id=session.session_id,
                error_id="err_001",
                module="duplicate_charge",
                error_type="Duplicate Charge",
                description="CPT 29881 billed twice on 2025-09-17.",
                line_items_affected=json.dumps([1, 7]),
                estimated_dollar_impact=3200.00,
                confidence="high",
                explanation="This charge appears more than once.",
                citations=json.dumps([]),
            )
        )
        _db.session.commit()
        return session.session_id


# ══════════════════════════════════════════════════════════════════════════════
# GET /report/<session_id>
# ══════════════════════════════════════════════════════════════════════════════


class TestGetReport:

    def test_404_for_unknown_session(self, client):
        r = client.get("/report/does-not-exist")
        assert r.status_code == 404
        assert r.get_json()["error_code"] == "SESSION_NOT_FOUND"

    def test_returns_analysis_results(self, client, analysed_session):
        r = client.get(f"/report/{analysed_session}")
        assert r.status_code == 200
        data = r.get_json()
        assert data["session_id"] == analysed_session
        assert data["status"] == SessionStatus.ANALYSED
        assert data["total_errors"] == 1
        assert data["all_clear"] is False
        assert len(data["errors"]) == 1
        assert data["errors"][0]["error_id"] == "err_001"

    def test_all_clear_when_no_errors(self, app, client):
        with app.app_context():
            session = Session(status=SessionStatus.ANALYSED)
            _db.session.add(session)
            _db.session.commit()
            sid = session.session_id

        r = client.get(f"/report/{sid}")
        data = r.get_json()
        assert data["all_clear"] is True
        assert data["total_errors"] == 0
        assert data["errors"] == []

    def test_rag_available_false_when_explanation_missing(self, app, client):
        with app.app_context():
            session = Session(status=SessionStatus.ANALYSED)
            _db.session.add(session)
            _db.session.flush()
            _db.session.add(
                AnalysisResult(
                    session_id=session.session_id,
                    error_id="err_001",
                    module="duplicate_charge",
                    error_type="Duplicate Charge",
                    description="CPT billed twice.",
                    line_items_affected=json.dumps([1]),
                    estimated_dollar_impact=100.00,
                    confidence="high",
                    explanation=None,
                    citations=json.dumps([]),
                )
            )
            _db.session.commit()
            sid = session.session_id

        r = client.get(f"/report/{sid}")
        assert r.get_json()["rag_available"] is False

    def test_no_downloads_key_in_report(self, client, analysed_session):
        """
        GET /report no longer returns downloads — letters are base64 in
        POST /letter response. Report only returns analysis results.
        """
        r = client.get(f"/report/{analysed_session}")
        data = r.get_json()
        assert r.status_code == 200
        # downloads key is NOT expected in GET /report response
        assert "downloads" not in data


# ══════════════════════════════════════════════════════════════════════════════
# POST /letter — base64 response (no disk storage)
# ══════════════════════════════════════════════════════════════════════════════


class TestLetterEndpoint:

    def test_letter_returns_base64_docx_and_pdf(
        self, app, client, analysed_session, mocker
    ):
        """FR-21: both formats returned in single response as base64."""
        mocker.patch(
            "routes.letter.rag_client.generate_letter",
            return_value={"success": False, "letter_content": None},
        )

        r = client.post("/letter", json={"session_id": analysed_session})
        assert r.status_code == 200
        data = r.get_json()

        assert data["status"] == "letter_generated"
        assert "downloads" in data
        assert "docx" in data["downloads"]
        assert "pdf" in data["downloads"]

        # Verify both are valid base64
        docx_bytes = base64.b64decode(data["downloads"]["docx"])
        pdf_bytes = base64.b64decode(data["downloads"]["pdf"])
        assert len(docx_bytes) > 0
        assert len(pdf_bytes) > 0

    def test_letter_docx_is_valid_zip(self, app, client, analysed_session, mocker):
        """Word .docx files are ZIP archives — verify magic bytes."""
        mocker.patch(
            "routes.letter.rag_client.generate_letter",
            return_value={"success": False, "letter_content": None},
        )

        r = client.post("/letter", json={"session_id": analysed_session})
        data = r.get_json()
        docx_bytes = base64.b64decode(data["downloads"]["docx"])

        # .docx is a ZIP — magic bytes PK
        assert docx_bytes[:2] == b"PK"

    def test_letter_pdf_has_pdf_header(self, app, client, analysed_session, mocker):
        """PDF files start with %PDF."""
        mocker.patch(
            "routes.letter.rag_client.generate_letter",
            return_value={"success": False, "letter_content": None},
        )

        r = client.post("/letter", json={"session_id": analysed_session})
        data = r.get_json()
        pdf_bytes = base64.b64decode(data["downloads"]["pdf"])

        assert pdf_bytes[:4] == b"%PDF"

    def test_letter_response_includes_filenames_and_content_types(
        self, app, client, analysed_session, mocker
    ):
        """Response includes filenames and MIME types for frontend download."""
        mocker.patch(
            "routes.letter.rag_client.generate_letter",
            return_value={"success": False, "letter_content": None},
        )

        r = client.post("/letter", json={"session_id": analysed_session})
        data = r.get_json()

        assert "content_types" in data
        assert "filenames" in data
        assert data["content_types"]["docx"] == (
            "application/vnd.openxmlformats-officedocument" ".wordprocessingml.document"
        )
        assert data["content_types"]["pdf"] == "application/pdf"
        assert data["filenames"]["docx"].endswith(".docx")
        assert data["filenames"]["pdf"].endswith(".pdf")

    def test_letter_advances_session_to_letter_generated(
        self, app, client, analysed_session, mocker
    ):
        """FR-26: session status advances to letter_generated."""
        mocker.patch(
            "routes.letter.rag_client.generate_letter",
            return_value={"success": False, "letter_content": None},
        )

        client.post("/letter", json={"session_id": analysed_session})

        with app.app_context():
            session = _db.session.get(Session, analysed_session)
            assert session.status == SessionStatus.LETTER_GENERATED

    def test_letter_404_for_unknown_session(self, client):
        r = client.post("/letter", json={"session_id": "fake-uuid"})
        assert r.status_code == 404
        assert r.get_json()["error_code"] == "SESSION_NOT_FOUND"

    def test_letter_404_before_analyse(self, app, client, mocker):
        """NFR-17: letter before analyse returns 404."""
        mocker.patch(
            "routes.upload.ocr_service.extract",
            return_value={
                "patient_name": "Test",
                "provider_name": "Test",
                "date_of_service": "2025-01-01",
                "total_billed": 100.0,
                "line_items": [],
            },
        )
        import io

        pdf = (
            b"%PDF-1.4\n1 0 obj\n<< >>\nendobj\n"
            b"trailer\n<< /Root 1 0 R >>\nstartxref\n0\n%%EOF"
        )
        r = client.post(
            "/upload",
            data={"bill": (io.BytesIO(pdf), "bill.pdf")},
            content_type="multipart/form-data",
        )
        sid = r.get_json()["session_id"]

        # Confirm but don't analyse
        client.post(
            "/confirm",
            json={
                "session_id": sid,
                "confirmed_fields": {
                    "patient_name": "Test",
                    "provider_name": "Test",
                    "date_of_service": "2025-01-01",
                    "total_billed": 100.0,
                    "line_items": [],
                },
            },
        )

        r = client.post("/letter", json={"session_id": sid})
        assert r.status_code == 404
        assert r.get_json()["error_code"] == "NO_ANALYSIS_RESULTS"

    def test_letter_regenerates_on_second_call(
        self, app, client, analysed_session, mocker
    ):
        """
        FR-23 updated: base64 approach regenerates on each call since
        no files are stored. Both calls must return valid base64.
        """
        mock = mocker.patch(
            "routes.letter.rag_client.generate_letter",
            return_value={"success": False, "letter_content": None},
        )

        r1 = client.post("/letter", json={"session_id": analysed_session})
        assert r1.status_code == 200

        # Session is now LETTER_GENERATED — second call still works
        r2 = client.post("/letter", json={"session_id": analysed_session})
        assert r2.status_code == 200

        d1 = r1.get_json()["downloads"]["docx"]
        d2 = r2.get_json()["downloads"]["docx"]

        # Both are valid base64
        assert len(base64.b64decode(d1)) > 0
        assert len(base64.b64decode(d2)) > 0
