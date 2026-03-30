"""
MedicareRateDetector — FR-12

Compares billed amounts against CMS Physician Fee Schedule locality-adjusted
Medicare rates. Flags any line item where the billed amount exceeds 300% of
the applicable Medicare rate.

CPT descriptions are NEVER used — AMA copyright (agreed decision).
Only numeric CPT codes and CMS rate data are referenced.
"""

import os
import json
from detectors.base import BaseDetector, DetectionResult

# Threshold: billed amount / medicare rate > 3.0 triggers a flag (FR-12)
OUTLIER_THRESHOLD = 3.0

# Default locality — SC Rest of State
DEFAULT_LOCALITY = "07"
DEFAULT_LOCALITY_NAME = "CMS Locality 07 — Rest of South Carolina"


class MedicareRateDetector(BaseDetector):

    def __init__(self, fee_schedule_path: str = None):
        """
        Args:
            fee_schedule_path: Path to the CMS fee schedule JSON file.
                               Defaults to data/cms_fee_schedule.json relative to app root.
        """
        self._fee_schedule_path = fee_schedule_path or os.path.join(
            os.path.dirname(__file__), "..", "data", "cms_fee_schedule.json"
        )
        self._fee_schedule: dict | None = None

    @property
    def module_name(self) -> str:
        return "medicare_rate_outlier"

    @property
    def fee_schedule(self) -> dict:
        """Lazy-load fee schedule from JSON file."""
        if self._fee_schedule is None:
            try:
                with open(self._fee_schedule_path) as f:
                    self._fee_schedule = json.load(f)
            except FileNotFoundError:
                # Return empty schedule — detector will produce no results
                # rather than crashing the pipeline (FR-10: must not silently omit)
                self._fee_schedule = {}
        return self._fee_schedule

    def run(self, confirmed_fields: dict) -> list[DetectionResult]:
        """
        Compare each bill line item's billed amount against the Medicare rate.
        Items exceeding 300% of Medicare rate are flagged as outliers.
        """
        results = []

        bill_items = [
            item for item in confirmed_fields.get("line_items", [])
            if item.get("source") == "bill" and item.get("cpt_code")
        ]

        for item in bill_items:
            cpt         = item["cpt_code"]
            billed      = float(item.get("amount", 0))
            medicare    = self._get_medicare_rate(cpt)

            if medicare is None or medicare <= 0:
                continue  # No rate data for this CPT — skip, not an error

            ratio = billed / medicare

            if ratio > OUTLIER_THRESHOLD:
                percentage = round(ratio * 100)
                dollar_impact = round(billed - medicare, 2)

                results.append(DetectionResult(
                    module=self.module_name,
                    error_type="Medicare Rate Outlier",
                    description=(
                        f"CPT {cpt} is billed at ${billed:.2f}, which is {percentage}% of the "
                        f"Medicare rate of ${medicare:.2f} ({DEFAULT_LOCALITY_NAME}). "
                        f"Charges exceeding 300% of the Medicare rate are flagged as outliers."
                    ),
                    line_items_affected=[item["line_number"]],
                    estimated_dollar_impact=dollar_impact,
                    confidence=self._confidence_from_ratio(ratio),
                ))

        return results

    # ── Private helpers ────────────────────────────────────────────────────────

    def _get_medicare_rate(self, cpt_code: str) -> float | None:
        """Look up Medicare rate for a CPT code in the loaded fee schedule."""
        return self.fee_schedule.get(cpt_code, {}).get("rate")

    def _confidence_from_ratio(self, ratio: float) -> str:
        """Map ratio magnitude to a confidence string."""
        if ratio >= 5.0:
            return "high"
        if ratio >= 3.5:
            return "medium"
        return "low"
