"""
Unit tests for all four error detection checks.
NFR-25: minimum 15 unit tests, at least 3 per check:
  - positive case (should produce an error result)
  - negative case (should produce no error result)
  - boundary case (at the exact threshold)

All tests use synthetic data only (NFR-06).
Tests run without any external services — no live HTTP calls (NFR-26).
"""

import pytest
from detectors.duplicate import DuplicateChargeDetector
from detectors.medicare_rate import MedicareRateDetector
from detectors.eob_reconciliation import EOBReconciliationDetector
from detectors.no_surprises import NoSurprisesActDetector


# ── Fixtures ──────────────────────────────────────────────────────────────────

def _bill_item(line_number, cpt_code, amount, date="2025-09-17", quantity=1, source="bill"):
    return {
        "line_number": line_number,
        "cpt_code": cpt_code,
        "amount": amount,
        "date": date,
        "quantity": quantity,
        "source": source,
    }

def _eob_item(line_number, cpt_code, amount, date="2025-09-17", quantity=1, network_status="in-network"):
    item = _bill_item(line_number, cpt_code, amount, date, quantity, source="eob")
    item["network_status"] = network_status
    return item

def _fields(*items, patient_name="James Whitfield", provider_name="Atrium Health CMC",
             date_of_service="2025-09-17"):
    return {
        "patient_name": patient_name,
        "provider_name": provider_name,
        "date_of_service": date_of_service,
        "line_items": list(items),
    }


# ══════════════════════════════════════════════════════════════════════════════
# DuplicateChargeDetector  (FR-11)
# ══════════════════════════════════════════════════════════════════════════════

class TestDuplicateChargeDetector:

    def setup_method(self):
        self.detector = DuplicateChargeDetector()

    # ── Positive: same CPT, same date → flag ──────────────────────────────────
    def test_detects_exact_duplicate(self):
        fields = _fields(
            _bill_item(1, "29881", 3200.00, "2025-09-17"),
            _bill_item(7, "29881", 3200.00, "2025-09-17"),
        )
        results = self.detector.run(fields)
        assert len(results) == 1
        assert results[0].error_type == "Duplicate Charge"
        assert 1 in results[0].line_items_affected
        assert 7 in results[0].line_items_affected
        assert results[0].estimated_dollar_impact == 3200.00

    # ── Positive: three of the same CPT on same date → two results ────────────
    def test_detects_triple_duplicate(self):
        fields = _fields(
            _bill_item(1, "99213", 100.00, "2025-09-17"),
            _bill_item(2, "99213", 100.00, "2025-09-17"),
            _bill_item(3, "99213", 100.00, "2025-09-17"),
        )
        results = self.detector.run(fields)
        assert len(results) == 2

    # ── Negative: same CPT, different dates → no flag (FR-11 boundary) ────────
    def test_same_cpt_different_dates_not_flagged(self):
        fields = _fields(
            _bill_item(1, "29881", 3200.00, "2025-09-17"),
            _bill_item(2, "29881", 3200.00, "2025-09-18"),  # different date
        )
        results = self.detector.run(fields)
        assert len(results) == 0

    # ── Negative: different CPT codes → no flag ────────────────────────────────
    def test_different_cpt_codes_not_flagged(self):
        fields = _fields(
            _bill_item(1, "29881", 3200.00, "2025-09-17"),
            _bill_item(2, "99215", 267.00,  "2025-09-17"),
        )
        results = self.detector.run(fields)
        assert len(results) == 0

    # ── Boundary: EOB items with same CPT not flagged (only bill items) ────────
    def test_eob_items_not_flagged_as_duplicates(self):
        fields = _fields(
            _bill_item(1, "29881", 3200.00, "2025-09-17", source="bill"),
            _eob_item(2,  "29881", 3200.00, "2025-09-17"),  # source='eob'
        )
        results = self.detector.run(fields)
        assert len(results) == 0

    # ── Validates FR-16 fields present ────────────────────────────────────────
    def test_result_has_all_required_fields(self):
        fields = _fields(
            _bill_item(1, "29881", 3200.00, "2025-09-17"),
            _bill_item(7, "29881", 3200.00, "2025-09-17"),
        )
        results = self.detector.run(fields)
        assert len(results) == 1
        r = results[0]
        assert r.validate() == []   # no defects
        assert r.module == "duplicate_charge"
        assert r.confidence in ("high", "medium", "low")


# ══════════════════════════════════════════════════════════════════════════════
# MedicareRateDetector  (FR-12)
# ══════════════════════════════════════════════════════════════════════════════

class TestMedicareRateDetector:

    def setup_method(self):
        # Inject a minimal in-memory fee schedule — no filesystem needed
        self.detector = MedicareRateDetector()
        self.detector._fee_schedule = {
            "99215": {"rate": 82.00},   # outlier threshold: $246.01+
            "29881": {"rate": 800.00},  # outlier threshold: $2400.01+
            "99213": {"rate": 75.00},   # outlier threshold: $225.01+
        }

    # ── Positive: billed > 300% Medicare rate → flag ──────────────────────────
    def test_detects_rate_outlier(self):
        fields = _fields(_bill_item(1, "99215", 350.00))  # 427% of $82
        results = self.detector.run(fields)
        assert len(results) == 1
        assert results[0].error_type == "Medicare Rate Outlier"
        assert results[0].estimated_dollar_impact == round(350.00 - 82.00, 2)

    # ── Positive: multiple outlier items → multiple results ───────────────────
    def test_multiple_outliers_produce_multiple_results(self):
        fields = _fields(
            _bill_item(1, "99215", 350.00),  # outlier
            _bill_item(2, "99213", 300.00),  # outlier
        )
        results = self.detector.run(fields)
        assert len(results) == 2

    # ── Negative: billed at exactly 300% → no flag (boundary) ─────────────────
    def test_exactly_300_percent_not_flagged(self):
        # 300% of $82 = $246.00 — must be ABOVE threshold, not at it
        fields = _fields(_bill_item(1, "99215", 246.00))
        results = self.detector.run(fields)
        assert len(results) == 0

    # ── Boundary: just above 300% → flag ──────────────────────────────────────
    def test_just_above_300_percent_flagged(self):
        fields = _fields(_bill_item(1, "99215", 246.01))  # 300.01%
        results = self.detector.run(fields)
        assert len(results) == 1

    # ── Negative: CPT not in fee schedule → no flag (skip gracefully) ─────────
    def test_unknown_cpt_not_flagged(self):
        fields = _fields(_bill_item(1, "00000", 9999.00))
        results = self.detector.run(fields)
        assert len(results) == 0

    # ── Negative: EOB items not compared against Medicare rates ───────────────
    def test_eob_items_not_evaluated(self):
        fields = _fields(_eob_item(1, "99215", 500.00))  # source='eob', high amount
        results = self.detector.run(fields)
        assert len(results) == 0


# ══════════════════════════════════════════════════════════════════════════════
# EOBReconciliationDetector  (FR-13)
# ══════════════════════════════════════════════════════════════════════════════

class TestEOBReconciliationDetector:

    def setup_method(self):
        self.detector = EOBReconciliationDetector()

    # ── Positive: amount mismatch → flag ──────────────────────────────────────
    def test_detects_amount_mismatch(self):
        fields = _fields(
            _bill_item(1, "99215", 350.00),
            _eob_item(2,  "99215", 82.00),   # EOB shows lower amount
        )
        results = self.detector.run(fields)
        assert any(r.error_type == "EOB Reconciliation — Amount Mismatch" for r in results)

    # ── Positive: CPT in bill but missing from EOB → flag ─────────────────────
    def test_detects_cpt_missing_from_eob(self):
        fields = _fields(
            _bill_item(1, "29881", 3200.00),
            _eob_item(2,  "99215", 82.00),   # different CPT in EOB
        )
        results = self.detector.run(fields)
        assert any(r.error_type == "EOB Reconciliation — Missing from EOB" for r in results)

    # ── Positive: date mismatch → flag ────────────────────────────────────────
    def test_detects_date_mismatch(self):
        fields = _fields(
            _bill_item(1, "99215", 82.00, date="2025-09-17"),
            _eob_item(2,  "99215", 82.00, date="2025-09-18"),  # different date
        )
        results = self.detector.run(fields)
        assert any(r.error_type == "EOB Reconciliation — Date Mismatch" for r in results)

    # ── Negative: no EOB uploaded → returns empty list, no error ──────────────
    def test_no_eob_returns_empty_gracefully(self):
        fields = _fields(_bill_item(1, "99215", 82.00))  # no EOB items
        results = self.detector.run(fields)
        assert results == []

    # ── Negative: bill and EOB match → no flag ────────────────────────────────
    def test_matching_items_not_flagged(self):
        fields = _fields(
            _bill_item(1, "99215", 82.00, "2025-09-17", quantity=1),
            _eob_item(2,  "99215", 82.00, "2025-09-17", quantity=1),
        )
        results = self.detector.run(fields)
        assert len(results) == 0

    # ── Boundary: amount difference within tolerance → no flag ────────────────
    def test_amount_within_tolerance_not_flagged(self):
        fields = _fields(
            _bill_item(1, "99215", 82.00),
            _eob_item(2,  "99215", 82.005),  # within $0.01 tolerance
        )
        results = self.detector.run(fields)
        amount_mismatches = [
            r for r in results
            if r.error_type == "EOB Reconciliation — Amount Mismatch"
        ]
        assert len(amount_mismatches) == 0

    # ── Boundary: fuzzy date normalisation ────────────────────────────────────
    def test_fuzzy_date_matching(self):
        # "09/17/2025" and "2025-09-17" should be treated as matching
        fields = _fields(
            _bill_item(1, "99215", 82.00, date="09/17/2025"),
            _eob_item(2,  "99215", 82.00, date="09172025"),
        )
        results = self.detector.run(fields)
        date_mismatches = [
            r for r in results
            if r.error_type == "EOB Reconciliation — Date Mismatch"
        ]
        assert len(date_mismatches) == 0


# ══════════════════════════════════════════════════════════════════════════════
# NoSurprisesActDetector  (FR-14)
# ══════════════════════════════════════════════════════════════════════════════

class TestNoSurprisesActDetector:

    def setup_method(self):
        self.detector = NoSurprisesActDetector()

    # ── Positive: emergency CPT, out-of-network → flag ───────────────────────
    def test_detects_nsa_violation_emergency(self):
        fields = _fields(
            _bill_item(1, "99285", 800.00),               # ED E&M — emergency CPT
            _eob_item(2,  "99285", 800.00, network_status="out-of-network"),
        )
        results = self.detector.run(fields)
        assert len(results) == 1
        assert results[0].error_type == "No Surprises Act Violation"

    # ── Positive: ancillary provider, out-of-network → flag ───────────────────
    def test_detects_nsa_violation_ancillary(self):
        fields = _fields(
            _bill_item(1, "99215", 500.00),
            _eob_item(2,  "99215", 500.00, network_status="out-of-network"),
            provider_name="Southeastern Anesthesia Partners",  # ancillary keyword
        )
        results = self.detector.run(fields)
        assert len(results) == 1

    # ── Negative: out-of-network but elective non-emergency → no flag ─────────
    def test_elective_out_of_network_not_flagged(self):
        """NSA does not apply to elective out-of-network outpatient (US-011 AC5)."""
        fields = _fields(
            _bill_item(1, "99213", 200.00),               # routine office visit
            _eob_item(2,  "99213", 200.00, network_status="out-of-network"),
            provider_name="General Practice Clinic",       # not ancillary
        )
        results = self.detector.run(fields)
        assert len(results) == 0

    # ── Negative: in-network provider → no flag ────────────────────────────────
    def test_in_network_not_flagged(self):
        fields = _fields(
            _bill_item(1, "99285", 800.00),
            _eob_item(2,  "99285", 800.00, network_status="in-network"),
        )
        results = self.detector.run(fields)
        assert len(results) == 0

    # ── Negative: no EOB → returns empty, no crash ────────────────────────────
    def test_no_eob_returns_empty(self):
        fields = _fields(_bill_item(1, "99285", 800.00))
        results = self.detector.run(fields)
        assert results == []

    # ── Boundary: network_status not set → no flag ────────────────────────────
    def test_missing_network_status_not_flagged(self):
        item = _eob_item(2, "99285", 800.00)
        del item["network_status"]
        fields = _fields(_bill_item(1, "99285", 800.00), item)
        results = self.detector.run(fields)
        assert len(results) == 0
