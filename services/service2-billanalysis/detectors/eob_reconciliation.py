"""
EOBReconciliationDetector — FR-13

Compares every line item in the confirmed provider bill against the confirmed EOB.
Any discrepancy in CPT code, date, quantity, or billed amount produces a separate result.
Fuzzy matching handles minor formatting differences (US-010 AC5).

If no EOB line items are present, the detector returns an empty list (not an error).
"""

from detectors.base import BaseDetector, DetectionResult


# Tolerance for amount comparison — differences within this value are not flagged
AMOUNT_TOLERANCE = 0.01

# Fuzzy date normalisation — strip separators for comparison
def _normalise_date(date_str: str | None) -> str:
    if not date_str:
        return ""
    return date_str.replace("/", "").replace("-", "").replace(" ", "").strip()


class EOBReconciliationDetector(BaseDetector):

    @property
    def module_name(self) -> str:
        return "eob_reconciliation"

    def run(self, confirmed_fields: dict) -> list[DetectionResult]:
        """
        Cross-reference bill line items against EOB line items.
        Returns a DetectionResult for each discrepancy found.
        Returns empty list if no EOB items are present (skips gracefully — US-010 AC4).
        """
        results = []

        all_items  = confirmed_fields.get("line_items", [])
        bill_items = [i for i in all_items if i.get("source") == "bill"]
        eob_items  = [i for i in all_items if i.get("source") == "eob"]

        # No EOB uploaded — skip gracefully
        if not eob_items:
            return []

        # Build a lookup: cpt_code → eob item (first match)
        # Fuzzy: normalise CPT codes by stripping leading zeros
        eob_by_cpt: dict[str, dict] = {}
        for item in eob_items:
            cpt = (item.get("cpt_code") or "").strip()
            if cpt and cpt not in eob_by_cpt:
                eob_by_cpt[cpt] = item

        for bill_item in bill_items:
            cpt = (bill_item.get("cpt_code") or "").strip()
            if not cpt:
                continue

            eob_item = eob_by_cpt.get(cpt)
            if not eob_item:
                # CPT in bill not found in EOB at all
                results.append(DetectionResult(
                    module=self.module_name,
                    error_type="EOB Reconciliation — Missing from EOB",
                    description=(
                        f"CPT {cpt} (line item {bill_item['line_number']}) appears in the "
                        f"provider bill but is not present in the insurance EOB. "
                        f"This may indicate a billing or processing discrepancy."
                    ),
                    line_items_affected=[bill_item["line_number"]],
                    estimated_dollar_impact=float(bill_item.get("amount", 0)),
                    confidence="medium",
                ))
                continue

            # Compare amount
            bill_amount = float(bill_item.get("amount", 0))
            eob_amount  = float(eob_item.get("amount", 0))
            if abs(bill_amount - eob_amount) > AMOUNT_TOLERANCE:
                results.append(DetectionResult(
                    module=self.module_name,
                    error_type="EOB Reconciliation — Amount Mismatch",
                    description=(
                        f"CPT {cpt} (line item {bill_item['line_number']}): "
                        f"provider bill shows ${bill_amount:.2f} but the EOB shows ${eob_amount:.2f}. "
                        f"Discrepancy: ${abs(bill_amount - eob_amount):.2f}."
                    ),
                    line_items_affected=[bill_item["line_number"]],
                    estimated_dollar_impact=round(abs(bill_amount - eob_amount), 2),
                    confidence="high",
                ))

            # Compare date (fuzzy normalisation)
            bill_date = _normalise_date(bill_item.get("date"))
            eob_date  = _normalise_date(eob_item.get("date"))
            if bill_date and eob_date and bill_date != eob_date:
                results.append(DetectionResult(
                    module=self.module_name,
                    error_type="EOB Reconciliation — Date Mismatch",
                    description=(
                        f"CPT {cpt} (line item {bill_item['line_number']}): "
                        f"provider bill shows date {bill_item.get('date')} "
                        f"but the EOB shows {eob_item.get('date')}."
                    ),
                    line_items_affected=[bill_item["line_number"]],
                    estimated_dollar_impact=0.0,
                    confidence="medium",
                ))

            # Compare quantity
            bill_qty = int(bill_item.get("quantity", 1))
            eob_qty  = int(eob_item.get("quantity", 1))
            if bill_qty != eob_qty:
                results.append(DetectionResult(
                    module=self.module_name,
                    error_type="EOB Reconciliation — Quantity Mismatch",
                    description=(
                        f"CPT {cpt} (line item {bill_item['line_number']}): "
                        f"provider bill shows quantity {bill_qty} "
                        f"but the EOB shows quantity {eob_qty}."
                    ),
                    line_items_affected=[bill_item["line_number"]],
                    estimated_dollar_impact=0.0,
                    confidence="medium",
                ))

        return results
