"""
ErrorDetectionEngine — FR-10, FR-15, FR-16

Orchestrates all four error detection checks.
Designed so a fifth detector can be added by registering it here
without modifying any existing detector (FR-15).

All four checks always run. Each produces either findings or an explicit
empty list — no check is ever silently omitted (FR-10).
"""

from detectors.base import BaseDetector, DetectionResult
from detectors.duplicate import DuplicateChargeDetector
from detectors.medicare_rate import MedicareRateDetector
from detectors.eob_reconciliation import EOBReconciliationDetector
from detectors.no_surprises import NoSurprisesActDetector


class ErrorDetectionEngine:
    """
    Runs all registered detectors and returns a consolidated list of results.

    To add a fifth detector (FR-15):
        1. Create detectors/my_new_detector.py subclassing BaseDetector
        2. Add it to _build_detectors() below
        3. No other file needs to change
    """

    def __init__(self, fee_schedule_path: str = None):
        self._detectors: list[BaseDetector] = self._build_detectors(fee_schedule_path)

    def _build_detectors(self, fee_schedule_path: str = None) -> list[BaseDetector]:
        """
        Register all active detectors here.
        Order determines the order results appear in the response.
        """
        return [
            DuplicateChargeDetector(),
            MedicareRateDetector(fee_schedule_path=fee_schedule_path),
            EOBReconciliationDetector(),
            NoSurprisesActDetector(),
        ]

    def run(self, confirmed_fields: dict) -> dict:
        """
        Run all detectors against confirmed bill data.

        Args:
            confirmed_fields: dict from ExtractedField.to_dict() + line items

        Returns:
            {
                "results": [DetectionResult, ...],  — all findings across all detectors
                "all_clear": bool,                  — True if no findings
                "module_summary": {module: count},  — for debugging/logging
            }
        """
        all_results: list[DetectionResult] = []
        module_summary: dict[str, int] = {}
        defects: list[str] = []

        for detector in self._detectors:
            try:
                findings = detector.run(confirmed_fields)
            except Exception as exc:
                # Log but do not let one detector crash the whole pipeline (FR-10)
                import logging
                logging.error(
                    "Detector %s raised an exception: %s",
                    detector.module_name, exc, exc_info=True
                )
                findings = []

            # Validate each result — missing required fields = system defect (FR-16)
            validated = []
            for result in findings:
                errors = result.validate()
                if errors:
                    defects.append(
                        f"{detector.module_name}: result missing fields {errors}"
                    )
                else:
                    validated.append(result)

            all_results.extend(validated)
            module_summary[detector.module_name] = len(validated)

        if defects:
            import logging
            logging.warning("DetectionResult defects found: %s", defects)

        return {
            "results": all_results,
            "all_clear": len(all_results) == 0,
            "module_summary": module_summary,
            "defects": defects,
        }
