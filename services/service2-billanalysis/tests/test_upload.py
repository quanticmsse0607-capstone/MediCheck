"""
Integration tests for POST /upload.
FR-01, FR-02, FR-03, FR-04, FR-05

Covers: happy path response structure, DB state, bill+EOB upload,
and file validation (non-PDF, oversized, missing bill field).
NFR-26: OCR is always mocked — no live Textract calls.
"""

import io
import sys
import os

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app import create_app
from extensions import db as _db
from models import Session, ExtractedField, LineItem, SessionStatus


# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture
def app():
    application = create_app("development")
    application.config.update(
        {
            "TESTING": True,
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
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
    return (
        b"%PDF-1.4\n"
        b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n"
        b"2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n"
        b"3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] >>\nendobj\n"
        b"xref\n0 4\n0000000000 65535 f\n"
        b"trailer\n<< /Root 1 0 R /Size 4 >>\nstartxref\n0\n%%EOF"
    )


_MOCK_BILL_OCR = {
    "patient_name": "James Whitfield",
    "provider_name": "Atrium Health CMC",
    "date_of_service": "2025-09-17",
    "total_billed": 3200.00,
    "line_items": [
        {
            "line_number": 1,
            "cpt_code": "29881",
            "amount": 3200.00,
            "date": "2025-09-17",
            "confidence": 0.97,
            "source": "bill",
        }
    ],
}

_MOCK_EOB_OCR = {
    "patient_name": "James Whitfield",
    "provider_name": "Atrium Health CMC",
    "date_of_service": "2025-09-17",
    "total_billed": 3200.00,
    "line_items": [
        {
            "line_number": 1,
            "cpt_code": "29881",
            "amount": 2800.00,
            "date": "2025-09-17",
            "confidence": 0.95,
            "source": "eob",
        }
    ],
}


# ══════════════════════════════════════════════════════════════════════════════
# Happy path — response structure
# ══════════════════════════════════════════════════════════════════════════════


class TestUploadHappyPath:

    def test_returns_200_with_session_id(self, client, mocker):
        """FR-01: successful upload returns HTTP 200 and a session_id."""
        mocker.patch("routes.upload.ocr_service.extract", return_value=_MOCK_BILL_OCR)

        r = client.post(
            "/upload",
            data={"bill": (io.BytesIO(_minimal_pdf()), "bill.pdf")},
            content_type="multipart/form-data",
        )

        assert r.status_code == 200
        data = r.get_json()
        assert data["session_id"] is not None
        assert data["status"] == "extracted"

    def test_response_contains_extracted_fields(self, client, mocker):
        """FR-04: extracted_fields in response matches OCR output."""
        mocker.patch("routes.upload.ocr_service.extract", return_value=_MOCK_BILL_OCR)

        r = client.post(
            "/upload",
            data={"bill": (io.BytesIO(_minimal_pdf()), "bill.pdf")},
            content_type="multipart/form-data",
        )

        fields = r.get_json()["extracted_fields"]
        assert fields["patient_name"] == "James Whitfield"
        assert fields["provider_name"] == "Atrium Health CMC"
        assert fields["date_of_service"] == "2025-09-17"
        assert fields["total_billed"] == 3200.00
        assert len(fields["line_items"]) == 1
        assert fields["line_items"][0]["cpt_code"] == "29881"
        assert fields["line_items"][0]["source"] == "bill"

    def test_session_persisted_with_extracted_status(self, app, client, mocker):
        """FR-03: session is created in DB with status=extracted."""
        mocker.patch("routes.upload.ocr_service.extract", return_value=_MOCK_BILL_OCR)

        r = client.post(
            "/upload",
            data={"bill": (io.BytesIO(_minimal_pdf()), "bill.pdf")},
            content_type="multipart/form-data",
        )

        session_id = r.get_json()["session_id"]
        with app.app_context():
            session = _db.session.get(Session, session_id)
            assert session is not None
            assert session.status == SessionStatus.EXTRACTED

    def test_upload_with_eob_includes_both_sources(self, client, mocker):
        """FR-02: uploading bill + EOB returns line items from both sources."""
        mocker.patch(
            "routes.upload.ocr_service.extract",
            side_effect=[_MOCK_BILL_OCR, _MOCK_EOB_OCR],
        )

        r = client.post(
            "/upload",
            data={
                "bill": (io.BytesIO(_minimal_pdf()), "bill.pdf"),
                "eob": (io.BytesIO(_minimal_pdf()), "eob.pdf"),
            },
            content_type="multipart/form-data",
        )

        assert r.status_code == 200
        line_items = r.get_json()["extracted_fields"]["line_items"]
        sources = [item["source"] for item in line_items]
        assert "bill" in sources
        assert "eob" in sources

    def test_response_does_not_include_rag_available(self, client, mocker):
        """M9 fix: upload response must not include rag_available (checked at analyse time)."""
        mocker.patch("routes.upload.ocr_service.extract", return_value=_MOCK_BILL_OCR)

        r = client.post(
            "/upload",
            data={"bill": (io.BytesIO(_minimal_pdf()), "bill.pdf")},
            content_type="multipart/form-data",
        )

        assert "rag_available" not in r.get_json()


# ══════════════════════════════════════════════════════════════════════════════
# Validation — rejection cases
# ══════════════════════════════════════════════════════════════════════════════


class TestUploadValidation:

    def test_no_bill_field_returns_400(self, client):
        """FR-05: request without a 'bill' field returns 400 NO_BILL_UPLOADED."""
        r = client.post("/upload", data={}, content_type="multipart/form-data")
        assert r.status_code == 400
        assert r.get_json()["error_code"] == "NO_BILL_UPLOADED"

    def test_non_pdf_extension_returns_400(self, client):
        """FR-05: non-PDF file returns 400 INVALID_FILE_TYPE."""
        r = client.post(
            "/upload",
            data={"bill": (io.BytesIO(b"not a pdf"), "bill.txt")},
            content_type="multipart/form-data",
        )
        assert r.status_code == 400
        assert r.get_json()["error_code"] == "INVALID_FILE_TYPE"

    def test_file_too_large_returns_400(self, app, client):
        """FR-01: file exceeding MAX_FILE_SIZE_MB returns 400 FILE_TOO_LARGE."""
        app.config["MAX_FILE_SIZE_MB"] = 0.000001  # force any file to exceed limit
        large_bytes = b"%PDF-1.4\n" + b"x" * 2048

        r = client.post(
            "/upload",
            data={"bill": (io.BytesIO(large_bytes), "big_bill.pdf")},
            content_type="multipart/form-data",
        )

        assert r.status_code == 400
        assert r.get_json()["error_code"] == "FILE_TOO_LARGE"

    def test_eob_wrong_type_returns_400(self, client):
        """FR-05: non-PDF EOB file returns 400 INVALID_FILE_TYPE."""
        r = client.post(
            "/upload",
            data={
                "bill": (io.BytesIO(_minimal_pdf()), "bill.pdf"),
                "eob": (io.BytesIO(b"not a pdf"), "eob.docx"),
            },
            content_type="multipart/form-data",
        )
        assert r.status_code == 400
        assert r.get_json()["error_code"] == "INVALID_FILE_TYPE"
