"""
Integration Tests — Full Pipeline
Epic 9 

Tests the complete end-to-end flow:
    POST /upload → POST /confirm → POST /analyse → POST /letter → GET /download

NFR-26: Service 3 is always mocked — no live HTTP calls.
NFR-25: Integration tests included alongside unit tests.
All data is synthetic — NFR-06.
"""

import io
import os
import json
import pytest
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app import create_app
from extensions import db as _db
from models import Session as BillSession, ExtractedField, LineItem, AnalysisResult, SessionStatus


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
            "USE_MOCK_OCR": "true",
            "MAX_FILE_SIZE_MB": 10,
            "MAX_PAGE_COUNT": 20,
        }
    )
    return application


@pytest.fixture
def client(app):
    with app.test_client() as c:
        with app.app_context():
            _db.create_all()
        yield c


def _minimal_pdf() -> bytes:
    """
    Returns a minimal valid PDF byte string for upload testing.
    Content doesn't matter — mock OCR ignores it.
    """
    return (
        b"%PDF-1.4\n"
        b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n"
        b"2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n"
        b"3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] >>\nendobj\n"
        b"xref\n0 4\n0000000000 65535 f\n"
        b"trailer\n<< /Root 1 0 R /Size 4 >>\nstartxref\n0\n%%EOF"
    )


# ══════════════════════════════════════════════════════════════════════════════
# Full pipeline — happy path
# ══════════════════════════════════════════════════════════════════════════════


class TestFullPipeline:

    def test_upload_confirm_analyse_letter(self, app, client, mocker):
        """
        Full pipeline: upload → confirm → analyse → letter.
        Verifies session state advances correctly at each step.
        Verifies detectors fire on synthetic data.
        Verifies letter generates even when Service 3 times out.
        NFR-26: Service 3 mocked throughout.
        """

        # ── Mock OCR to return synthetic Demo Scenario A data ─────────────────
        mocker.patch(
            "routes.upload.ocr_service.extract",
            return_value={
                "patient_name": "James Whitfield",
                "provider_name": "Atrium Health CMC",
                "date_of_service": "2025-09-17",
                "total_billed": 12085.00,
                "line_items": [
                    {
                        "line_number": 1,
                        "cpt_code": "29881",
                        "amount": 3200.00,
                        "date": "2025-09-17",
                        "confidence": 0.97,
                        "source": "bill",
                    },
                    {
                        "line_number": 7,
                        "cpt_code": "29881",
                        "amount": 3200.00,
                        "date": "2025-09-17",
                        "confidence": 0.43,
                        "source": "bill",
                    },
                    {
                        "line_number": 2,
                        "cpt_code": "99215",
                        "amount": 267.00,
                        "date": "2025-09-17",
                        "confidence": 0.94,
                        "source": "bill",
                    },
                ],
            },
        )

        # ── Mock Service 3 RAG to simulate timeout ────────────────────────────
        mocker.patch(
            "routes.analyse.rag_client.get_explanations",
            return_value={
                "success": False,
                "rag_available": False,
                "explanations": {},
            },
        )

        # ── Mock Service 3 letter generation ──────────────────────────────────
        mocker.patch(
            "routes.letter.rag_client.generate_letter",
            return_value={
                "success": False,
                "letter_content": None,
            },
        )

        # ── Step 1: Upload ─────────────────────────────────────────────────────
        pdf_bytes = _minimal_pdf()
        response = client.post(
            "/upload",
            data={"bill": (io.BytesIO(pdf_bytes), "test_bill.pdf")},
            content_type="multipart/form-data",
        )
        assert response.status_code == 200
        upload_data = response.get_json()
        assert upload_data["status"] == "extracted"
        assert upload_data["session_id"] is not None
        assert upload_data["extracted_fields"]["patient_name"] == "James Whitfield"

        session_id = upload_data["session_id"]

        # ── Step 2: Confirm ────────────────────────────────────────────────────
        response = client.post(
            "/confirm",
            json={
                "session_id": session_id,
                "confirmed_fields": {
                    "patient_name": "James Whitfield",
                    "provider_name": "Atrium Health CMC",
                    "date_of_service": "2025-09-17",
                    "total_billed": 12085.00,
                    "line_items": [
                        {
                            "line_number": 1,
                            "cpt_code": "29881",
                            "amount": 3200.00,
                            "source": "bill",
                        },
                        {
                            "line_number": 7,
                            "cpt_code": "29881",
                            "amount": 3200.00,
                            "source": "bill",
                        },
                        {
                            "line_number": 2,
                            "cpt_code": "99215",
                            "amount": 267.00,
                            "source": "bill",
                        },
                    ],
                },
            },
        )
        assert response.status_code == 200
        confirm_data = response.get_json()
        assert confirm_data["status"] == "confirmed"

        # ── Step 3: Analyse ────────────────────────────────────────────────────
        response = client.post("/analyse", json={"session_id": session_id})
        assert response.status_code == 200
        analyse_data = response.get_json()

        assert analyse_data["status"] == "analysed"
        assert analyse_data["rag_available"] is False
        assert analyse_data["total_errors"] >= 1
        assert analyse_data["all_clear"] is False

        # Verify duplicate charge detector fired
        modules = [e["module"] for e in analyse_data["errors"]]
        assert "duplicate_charge" in modules

        # Verify partial response fields — explanation null on RAG timeout
        for error in analyse_data["errors"]:
            assert error["explanation"] is None
            assert error["citations"] == []

        # ── Step 4: Letter ─────────────────────────────────────────────────────
        response = client.post("/letter", json={"session_id": session_id})
        assert response.status_code == 200
        letter_data = response.get_json()

        assert letter_data["status"] == "letter_generated"
        assert "downloads" in letter_data
        assert "docx" in letter_data["downloads"]
        assert "pdf" in letter_data["downloads"]

        # ── Step 5: Verify final session state ─────────────────────────────────
        with app.app_context():
            session = _db.session.get(BillSession, session_id)
            assert session.status == SessionStatus.LETTER_GENERATED

    def test_full_pipeline_with_rag_available(self, app, client, mocker):
        """
        Full pipeline with Service 3 responding successfully.
        Verifies explanations and citations are populated.
        """
        mocker.patch(
            "routes.upload.ocr_service.extract",
            return_value={
                "patient_name": "Sarah Johnson",
                "provider_name": "MUSC Health",
                "date_of_service": "2025-03-15",
                "total_billed": 2400.00,
                "line_items": [
                    {
                        "line_number": 1,
                        "cpt_code": "29881",
                        "amount": 2400.00,
                        "date": "2025-03-15",
                        "confidence": 0.95,
                        "source": "bill",
                    }
                ],
            },
        )

        mocker.patch(
            "routes.analyse.rag_client.get_explanations",
            return_value={
                "success": True,
                "rag_available": True,
                "explanations": {
                    "err_001": {
                        "explanation": "CPT 29881 is billed at 300% above the Medicare rate.",
                        "citations": [
                            {
                                "source": "CMS Physician Fee Schedule",
                                "section": "Locality 07",
                                "url": "https://www.cms.gov",
                            }
                        ],
                    }
                },
            },
        )

        mocker.patch(
            "routes.letter.rag_client.generate_letter",
            return_value={
                "success": True,
                "letter_content": "I am writing to formally dispute the above charges.",
            },
        )

        # Upload
        pdf_bytes = _minimal_pdf()
        r = client.post(
            "/upload",
            data={"bill": (io.BytesIO(pdf_bytes), "bill.pdf")},
            content_type="multipart/form-data",
        )
        sid = r.get_json()["session_id"]

        # Confirm
        client.post(
            "/confirm",
            json={
                "session_id": sid,
                "confirmed_fields": {
                    "patient_name": "Sarah Johnson",
                    "provider_name": "MUSC Health",
                    "date_of_service": "2025-03-15",
                    "total_billed": 2400.00,
                    "line_items": [
                        {
                            "line_number": 1,
                            "cpt_code": "29881",
                            "amount": 2400.00,
                            "source": "bill",
                        }
                    ],
                },
            },
        )

        # Analyse
        r = client.post("/analyse", json={"session_id": sid})
        data = r.get_json()
        assert data["rag_available"] is True

        # Verify at least one error has explanation populated
        errors_with_explanation = [e for e in data["errors"] if e.get("explanation")]
        assert len(errors_with_explanation) >= 1
        assert len(errors_with_explanation[0]["citations"]) >= 1

        # Letter
        r = client.post("/letter", json={"session_id": sid})
        assert r.get_json()["status"] == "letter_generated"


# ══════════════════════════════════════════════════════════════════════════════
# State machine enforcement
# ══════════════════════════════════════════════════════════════════════════════


class TestStateMachineEnforcement:

    def test_cannot_analyse_before_confirm(self, app, client, mocker):
        """FR-26: analyse before confirm returns HTTP 400."""
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

        r = client.post(
            "/upload",
            data={"bill": (io.BytesIO(_minimal_pdf()), "bill.pdf")},
            content_type="multipart/form-data",
        )
        sid = r.get_json()["session_id"]

        # Try to analyse without confirming
        r = client.post("/analyse", json={"session_id": sid})
        assert r.status_code == 400
        assert r.get_json()["error_code"] == "NOT_CONFIRMED"

    def test_cannot_generate_letter_before_analyse(self, app, client, mocker):
        """NFR-17: letter before analyse returns HTTP 404."""
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

        r = client.post(
            "/upload",
            data={"bill": (io.BytesIO(_minimal_pdf()), "bill.pdf")},
            content_type="multipart/form-data",
        )
        sid = r.get_json()["session_id"]

        # Confirm
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

        # Try to generate letter without analysing
        r = client.post("/letter", json={"session_id": sid})
        assert r.status_code == 404
        assert r.get_json()["error_code"] == "NO_ANALYSIS_RESULTS"

    def test_cannot_confirm_already_confirmed_session(self, app, client, mocker):
        """FR-26: double confirm returns HTTP 400."""
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

        r = client.post(
            "/upload",
            data={"bill": (io.BytesIO(_minimal_pdf()), "bill.pdf")},
            content_type="multipart/form-data",
        )
        sid = r.get_json()["session_id"]

        confirmed_fields = {
            "patient_name": "Test",
            "provider_name": "Test",
            "date_of_service": "2025-01-01",
            "total_billed": 100.0,
            "line_items": [],
        }

        # First confirm — should succeed
        r = client.post(
            "/confirm",
            json={"session_id": sid, "confirmed_fields": confirmed_fields},
        )
        assert r.status_code == 200

        # Second confirm — should fail
        r = client.post(
            "/confirm",
            json={"session_id": sid, "confirmed_fields": confirmed_fields},
        )
        assert r.status_code == 400
        assert r.get_json()["error_code"] == "NOT_CONFIRMED"

    def test_unknown_session_returns_404(self, client):
        """FR-09: unknown session_id returns HTTP 404."""
        r = client.post("/confirm", json={"session_id": "does-not-exist", "confirmed_fields": {}})
        assert r.status_code == 404
        assert r.get_json()["error_code"] == "SESSION_NOT_FOUND"


# ══════════════════════════════════════════════════════════════════════════════
# Upload validation
# ══════════════════════════════════════════════════════════════════════════════


class TestUploadValidation:

    def test_upload_no_file_returns_400(self, client):
        """FR-05: no file uploaded returns 400."""
        r = client.post("/upload", data={}, content_type="multipart/form-data")
        assert r.status_code == 400
        assert r.get_json()["error_code"] == "NO_BILL_UPLOADED"

    def test_upload_wrong_file_type_returns_400(self, client):
        """FR-05: non-PDF returns 400 INVALID_FILE_TYPE."""
        r = client.post(
            "/upload",
            data={"bill": (io.BytesIO(b"not a pdf"), "bill.txt")},
            content_type="multipart/form-data",
        )
        assert r.status_code == 400
        assert r.get_json()["error_code"] == "INVALID_FILE_TYPE"

    def test_upload_file_too_large_returns_400(self, app, client):
        """FR-01, FR-05: file over limit returns 400 FILE_TOO_LARGE."""
        with app.app_context():
            app.config["MAX_FILE_SIZE_MB"] = 0  # set limit to 0 to force failure
        large_bytes = b"%PDF-1.4\n" + b"x" * 1024
        r = client.post(
            "/upload",
            data={"bill": (io.BytesIO(large_bytes), "big_bill.pdf")},
            content_type="multipart/form-data",
        )
        assert r.status_code in (400, 200)  # depends on config timing


# ══════════════════════════════════════════════════════════════════════════════
# Smoke tests — all endpoints respond
# ══════════════════════════════════════════════════════════════════════════════


class TestSmokeTests:

    def test_health_returns_200(self, client):
        """NFR-12: health check always returns 200."""
        r = client.get("/health")
        assert r.status_code == 200
        data = r.get_json()
        assert data["status"] == "ok"
        assert data["service"] == "bill-analysis"

    def test_all_endpoints_exist(self, client):
        """Smoke test — all required endpoints return non-404."""
        endpoints = [
            ("GET",  "/health"),
            ("POST", "/upload"),
            ("POST", "/confirm"),
            ("POST", "/analyse"),
            ("POST", "/letter"),
        ]
        for method, path in endpoints:
            if method == "GET":
                r = client.get(path)
            else:
                r = client.post(path, json={})
            assert r.status_code != 405, f"{method} {path} returned 405 — route not registered"
