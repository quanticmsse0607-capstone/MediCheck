"""
Integration tests for GET /report/<session_id> and GET /download/<session_id>/<filename>.
Also covers the POST /letter re-serve path (FR-23: existing letter returned without regeneration).

NFR-26: Service 3 is always mocked — no live HTTP calls.
"""

import json
import os
import sys
import tempfile

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

    def test_includes_download_urls_when_letter_exists(
        self, app, client, analysed_session
    ):
        with app.app_context():
            with tempfile.TemporaryDirectory() as tmpdir:
                docx_path = os.path.join(tmpdir, "letter.docx")
                pdf_path = os.path.join(tmpdir, "letter.pdf")
                open(docx_path, "wb").close()
                open(pdf_path, "wb").close()

                _db.session.add(
                    DisputeLetter(
                        session_id=analysed_session,
                        docx_path=docx_path,
                        pdf_path=pdf_path,
                    )
                )
                _db.session.commit()

                r = client.get(f"/report/{analysed_session}")
                data = r.get_json()
                assert "downloads" in data
                assert "docx" in data["downloads"]
                assert "pdf" in data["downloads"]


# ══════════════════════════════════════════════════════════════════════════════
# GET /download/<session_id>/<filename>
# ══════════════════════════════════════════════════════════════════════════════


class TestDownloadFile:

    def test_invalid_filename_returns_400(self, client, analysed_session):
        r = client.get(f"/download/{analysed_session}/evil.exe")
        assert r.status_code == 400
        assert r.get_json()["error_code"] == "INVALID_FILENAME"

    def test_404_when_no_letter_record(self, client, analysed_session):
        r = client.get(f"/download/{analysed_session}/letter.docx")
        assert r.status_code == 404
        assert r.get_json()["error_code"] == "NO_ANALYSIS_RESULTS"

    def test_404_when_file_missing_from_disk(self, app, client, analysed_session):
        with app.app_context():
            _db.session.add(
                DisputeLetter(
                    session_id=analysed_session,
                    docx_path="/nonexistent/letter.docx",
                    pdf_path="/nonexistent/letter.pdf",
                )
            )
            _db.session.commit()

        r = client.get(f"/download/{analysed_session}/letter.docx")
        assert r.status_code == 404
        assert r.get_json()["error_code"] == "FILE_NOT_FOUND"

    def test_serves_file_when_present(self, app, client, analysed_session):
        with app.app_context():
            with tempfile.NamedTemporaryFile(suffix=".docx", delete=False) as f:
                f.write(b"PK fake docx content")
                docx_path = f.name

            _db.session.add(
                DisputeLetter(
                    session_id=analysed_session,
                    docx_path=docx_path,
                    pdf_path=docx_path,
                )
            )
            _db.session.commit()

        r = client.get(f"/download/{analysed_session}/letter.docx")
        assert r.status_code == 200
        # File left for OS cleanup — send_file holds handle open on Windows


# ══════════════════════════════════════════════════════════════════════════════
# POST /letter — re-serve existing letter (FR-23)
# ══════════════════════════════════════════════════════════════════════════════


class TestLetterReserve:

    def test_returns_existing_letter_without_regenerating(
        self, app, client, analysed_session, mocker
    ):
        """FR-23: second call to POST /letter returns existing files, no Service 3 call."""
        with app.app_context():
            with tempfile.TemporaryDirectory() as tmpdir:
                docx_path = os.path.join(tmpdir, "letter.docx")
                pdf_path = os.path.join(tmpdir, "letter.pdf")
                open(docx_path, "wb").close()
                open(pdf_path, "wb").close()

                session = _db.session.get(Session, analysed_session)
                session.status = SessionStatus.LETTER_GENERATED
                _db.session.add(
                    DisputeLetter(
                        session_id=analysed_session,
                        docx_path=docx_path,
                        pdf_path=pdf_path,
                    )
                )
                _db.session.commit()

                generate_letter_mock = mocker.patch(
                    "routes.letter.rag_client.generate_letter"
                )

                r = client.post("/letter", json={"session_id": analysed_session})

                assert r.status_code == 200
                assert r.get_json()["status"] == "letter_generated"
                generate_letter_mock.assert_not_called()
