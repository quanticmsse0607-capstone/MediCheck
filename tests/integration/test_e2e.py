"""
Cross-service integration tests: Service 2 (Bill Analysis) × Service 3 (RAG & Letter)

Runs against live services on localhost:5001 and localhost:5002.

Requirements:
  - Service 2 at SERVICE2_URL (default: http://localhost:5001)
    with USE_MOCK_OCR=true and SERVICE3_URL pointed at Service 3
  - Service 3 at SERVICE3_URL (default: http://localhost:5002)
    with OPENAI_API_KEY and CHROMA_PERSIST_PATH set

These tests make real HTTP calls to real running services and trigger
real OpenAI API calls through Service 3. Do not run during isolated
unit test passes — they are gated to push-to-main in CI.
"""

import os

import pytest
import requests

SERVICE2_URL = os.environ.get("SERVICE2_URL", "http://localhost:5001")
SERVICE3_URL = os.environ.get("SERVICE3_URL", "http://localhost:5002")

BILL_PDF = os.path.normpath(
    os.path.join(
        os.path.dirname(__file__), "../../test-data/synthetic/test_bill.pdf"
    )
)


# ── Shared fixture: run the full upload → confirm → analyse flow once ─────────


@pytest.fixture(scope="module")
def e2e_result():
    """
    Run the complete upload → confirm → analyse flow once per test module.
    Returns a dict containing the session_id and each endpoint's response data.

    Assertions here are preconditions — if any step fails, the entire module
    is skipped via pytest's fixture failure mechanism.
    """
    # Step 1: Upload the synthetic bill PDF
    with open(BILL_PDF, "rb") as f:
        upload_r = requests.post(
            f"{SERVICE2_URL}/upload",
            files={"bill": ("test_bill.pdf", f, "application/pdf")},
            timeout=30,
        )
    assert upload_r.status_code == 200, (
        f"Upload failed ({upload_r.status_code}): {upload_r.text}"
    )
    upload_data = upload_r.json()
    assert "session_id" in upload_data, "Upload response missing session_id"
    session_id = upload_data["session_id"]

    # Step 2: Confirm extracted fields as-is (no corrections)
    confirm_r = requests.post(
        f"{SERVICE2_URL}/confirm",
        json={"session_id": session_id, "confirmed_fields": {}},
        timeout=10,
    )
    assert confirm_r.status_code == 200, (
        f"Confirm failed ({confirm_r.status_code}): {confirm_r.text}"
    )

    # Step 3: Analyse — internally calls Service 3 for RAG explanations
    analyse_r = requests.post(
        f"{SERVICE2_URL}/analyse",
        json={"session_id": session_id},
        timeout=120,  # Service 3 may make several parallel LLM calls
    )
    assert analyse_r.status_code == 200, (
        f"Analyse failed ({analyse_r.status_code}): {analyse_r.text}"
    )

    return {
        "session_id": session_id,
        "upload": upload_data,
        "analyse": analyse_r.json(),
    }


# ══════════════════════════════════════════════════════════════════════════════
# Health — both services must be reachable before any other test
# ══════════════════════════════════════════════════════════════════════════════


class TestHealth:

    def test_service2_healthy(self):
        r = requests.get(f"{SERVICE2_URL}/health", timeout=5)
        assert r.status_code == 200
        assert r.json()["status"] == "ok"

    def test_service3_healthy(self):
        r = requests.get(f"{SERVICE3_URL}/health", timeout=5)
        assert r.status_code == 200
        assert r.json()["status"] == "ok"


# ══════════════════════════════════════════════════════════════════════════════
# Upload — POST /upload returns extracted fields
# ══════════════════════════════════════════════════════════════════════════════


class TestUpload:

    def test_returns_session_id(self, e2e_result):
        assert e2e_result["session_id"] is not None
        assert len(e2e_result["session_id"]) > 0

    def test_returns_extracted_fields(self, e2e_result):
        fields = e2e_result["upload"]["extracted_fields"]
        assert "patient_name" in fields
        assert "date_of_service" in fields
        assert "total_billed" in fields
        assert isinstance(fields["line_items"], list)
        assert len(fields["line_items"]) > 0


# ══════════════════════════════════════════════════════════════════════════════
# Analyse — POST /analyse triggers Service 3 RAG pipeline
# ══════════════════════════════════════════════════════════════════════════════


class TestAnalyse:

    def test_status_is_analysed(self, e2e_result):
        data = e2e_result["analyse"]
        assert data["session_id"] == e2e_result["session_id"]
        assert data["status"] == "analysed"

    def test_rag_available(self, e2e_result):
        """Core integration assertion: Service 3 RAG pipeline must have responded."""
        assert e2e_result["analyse"]["rag_available"] is True, (
            "rag_available is False — Service 3 did not return explanations. "
            f"Full response: {e2e_result['analyse']}"
        )

    def test_errors_have_explanations(self, e2e_result):
        """Each detected error must carry an LLM-generated explanation from Service 3."""
        errors = e2e_result["analyse"]["errors"]
        for error in errors:
            assert error.get("explanation") is not None, (
                f"Missing RAG explanation for error_id={error.get('error_id')}"
            )
            assert isinstance(error.get("citations"), list), (
                f"Citations must be a list for error_id={error.get('error_id')}"
            )

    def test_total_errors_matches_list_length(self, e2e_result):
        data = e2e_result["analyse"]
        assert data["total_errors"] == len(data["errors"])


# ══════════════════════════════════════════════════════════════════════════════
# Report — GET /report reflects persisted analysis
# ══════════════════════════════════════════════════════════════════════════════


class TestReport:

    def test_report_returns_analysed_session(self, e2e_result):
        r = requests.get(
            f"{SERVICE2_URL}/report/{e2e_result['session_id']}", timeout=10
        )
        assert r.status_code == 200
        data = r.json()
        assert data["session_id"] == e2e_result["session_id"]
        assert data["status"] == "analysed"

    def test_report_error_count_matches_analyse(self, e2e_result):
        r = requests.get(
            f"{SERVICE2_URL}/report/{e2e_result['session_id']}", timeout=10
        )
        report_data = r.json()
        assert report_data["total_errors"] == e2e_result["analyse"]["total_errors"]
