"""
DuplicateChargeDetector — FR-11

Flags every instance where the same CPT code appears more than once
for the same date of service in the confirmed provider bill line items.
Each duplicate pair produces a separate DetectionResult.
"""

from detectors.base import BaseDetector, DetectionResult


class DuplicateChargeDetector(BaseDetector):

    @property
    def module_name(self) -> str:
        return "duplicate_charge"

    def run(self, confirmed_fields: dict) -> list[DetectionResult]:
        """
        Scan bill line items for duplicate (cpt_code, date_of_service) pairs.

        Logic:
          - Only checks source='bill' items (not EOB)
          - Ignores items with no CPT code
          - Same CPT on different dates = not a duplicate (FR-11 boundary condition)
          - Same CPT on same date = duplicate, each pair is a separate result
        """
        results = []
        bill_items = [
            item
            for item in confirmed_fields.get("line_items", [])
            if item.get("source") == "bill" and item.get("cpt_code")
        ]

        # Group by (cpt_code, date) — date falls back to session date_of_service
        session_date = confirmed_fields.get("date_of_service", "")
        seen: dict[tuple, list] = {}

        for item in bill_items:
            cpt = item["cpt_code"]
            date = item.get("date") or session_date
            key = (cpt, date)

            if key not in seen:
                seen[key] = []
            seen[key].append(item)

        # Any key with more than one item is a duplicate group
        for (cpt, date), items in seen.items():
            if len(items) < 2:
                continue

            # Each pair in the group produces one result
            for i in range(1, len(items)):
                original = items[0]
                duplicate = items[i]

                dollar_impact = float(duplicate.get("amount", 0))

                results.append(
                    DetectionResult(
                        module=self.module_name,
                        error_type="Duplicate Charge",
                        description=(
                            f"CPT {cpt} appears {len(items)} time(s) on {date}. "
                            f"Line items {original['line_number']} and {duplicate['line_number']} "
                            f"bill the same procedure on the same date. "
                            f"Duplicate billing for a single encounter is not permitted."
                        ),
                        line_items_affected=[
                            original["line_number"],
                            duplicate["line_number"],
                        ],
                        estimated_dollar_impact=dollar_impact,
                        confidence="high",
                    )
                )

        return results
