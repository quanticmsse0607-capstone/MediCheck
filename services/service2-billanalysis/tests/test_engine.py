"""
Integration tests for ErrorDetectionEngine.
Verifies engine orchestration — all detectors run, results consolidated.
NFR-26: No live HTTP calls — Service 3 is mocked.
"""

import pytest
from services.engine import ErrorDetectionEngine


def _fields(*items, date_of_service="2025-09-17"):
    return {
        "patient_name": "James Whitfield",
        "provider_name": "Atrium Health CMC",
        "date_of_service": date_of_service,
        "line_items": list(items),
    }


def _item(
    line_number,
    cpt,
    amount,
    source="bill",
    date="2025-09-17",
    quantity=1,
    network_status=None,
):
    i = {
        "line_number": line_number,
        "cpt_code": cpt,
        "amount": amount,
        "date": date,
        "quantity": quantity,
        "source": source,
    }
    if network_status:
        i["network_status"] = network_status
    return i


@pytest.fixture
def engine():
    e = ErrorDetectionEngine()
    # Inject in-memory fee schedule for Medicare rate tests
    e._detectors[1]._fee_schedule = {"99215": {"rate": 82.00}}
    return e


class TestErrorDetectionEngine:

    def test_all_modules_run_and_return_summary(self, engine):
        """FR-10: all four checks execute, each produces a result or empty list."""
        fields = _fields(_item(1, "99213", 100.00))
        output = engine.run(fields)
        summary = output["module_summary"]

        assert "duplicate_charge" in summary
        assert "medicare_rate_outlier" in summary
        assert "eob_reconciliation" in summary
        assert "no_surprises_act" in summary

    def test_all_clear_when_no_errors(self, engine):
        fields = _fields(_item(1, "99215", 82.00))  # exactly at Medicare rate
        output = engine.run(fields)
        assert output["all_clear"] is True
        assert output["results"] == []

    def test_multiple_modules_can_fire_simultaneously(self, engine):
        """Demo Scenario A — duplicate + rate outlier both fire."""
        fields = _fields(
            _item(1, "29881", 3200.00),
            _item(2, "29881", 3200.00),  # duplicate
            _item(3, "99215", 500.00),  # rate outlier (>300% of $82)
        )
        output = engine.run(fields)
        modules = {r.module for r in output["results"]}
        assert "duplicate_charge" in modules
        assert "medicare_rate_outlier" in modules

    def test_engine_does_not_crash_if_one_detector_raises(self, engine, mocker):
        """FR-10: one detector failure must not stop the others."""
        mocker.patch.object(
            engine._detectors[0],
            "run",
            side_effect=Exception("Simulated detector crash"),
        )
        fields = _fields(_item(1, "99215", 500.00))
        output = engine.run(fields)
        # Other detectors still ran
        assert "medicare_rate_outlier" in output["module_summary"]

    def test_result_defects_logged_not_raised(self, engine, mocker):
        """FR-16: defective results are logged, not raised."""
        from detectors.base import DetectionResult

        bad_result = DetectionResult(
            module="",  # missing — defect
            error_type="Test",
            description="Test",
            line_items_affected=[1],
            estimated_dollar_impact=100.0,
            confidence="high",
        )
        mocker.patch.object(engine._detectors[0], "run", return_value=[bad_result])
        fields = _fields(_item(1, "99215", 500.00))
        output = engine.run(fields)
        assert len(output["defects"]) >= 1
