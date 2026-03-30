"""
NoSurprisesActDetector — FR-14

Flags line items where the provider is recorded as out-of-network and the
service context meets the federal criteria for balance billing prohibition:
  - Services rendered at an in-network facility, OR
  - Emergency care

NSA does NOT apply to elective out-of-network care at out-of-network facilities.
The detector correctly skips those cases (US-011 AC5).
"""

from detectors.base import BaseDetector, DetectionResult

# CPT code ranges considered emergency care for NSA purposes
# These are approximations — a production system would use a comprehensive CMS list
EMERGENCY_CPT_RANGES = [
    ("99281", "99285"),  # Emergency department E&M visits
    ("99291", "99292"),  # Critical care
]

# Keywords in provider name that suggest out-of-network ancillary providers
# (anaesthesiologists, radiologists, pathologists — common NSA violation contexts)
ANCILLARY_KEYWORDS = [
    "anesthesia", "anaesthesia", "radiology", "pathology",
    "emergency medicine", "hospitalist",
]


def _is_emergency_cpt(cpt: str) -> bool:
    for start, end in EMERGENCY_CPT_RANGES:
        if start <= cpt <= end:
            return True
    return False


def _is_ancillary_provider(provider_name: str) -> bool:
    name_lower = (provider_name or "").lower()
    return any(kw in name_lower for kw in ANCILLARY_KEYWORDS)


class NoSurprisesActDetector(BaseDetector):

    @property
    def module_name(self) -> str:
        return "no_surprises_act"

    def run(self, confirmed_fields: dict) -> list[DetectionResult]:
        """
        Check for potential No Surprises Act violations.

        Requires EOB data to identify out-of-network flags.
        Returns empty list if no EOB items present (cannot determine network status).
        """
        results = []

        all_items = confirmed_fields.get("line_items", [])
        eob_items = [i for i in all_items if i.get("source") == "eob"]

        # Cannot detect NSA violations without EOB data — return empty, not an error
        if not eob_items:
            return []

        # Build EOB lookup: cpt_code → eob item
        eob_by_cpt = {
            (i.get("cpt_code") or "").strip(): i
            for i in eob_items
            if i.get("cpt_code")
        }

        bill_items = [i for i in all_items if i.get("source") == "bill"]
        provider_name = confirmed_fields.get("provider_name", "")

        for bill_item in bill_items:
            cpt = (bill_item.get("cpt_code") or "").strip()
            if not cpt:
                continue

            eob_item = eob_by_cpt.get(cpt)
            if not eob_item:
                continue

            # Check if provider is flagged as out-of-network in EOB
            network_status = (eob_item.get("network_status") or "").lower()
            is_out_of_network = network_status in ("out-of-network", "out_of_network", "oon", "non-participating")

            if not is_out_of_network:
                continue

            # Determine if NSA applies: emergency CPT or ancillary at in-network facility
            is_emergency = _is_emergency_cpt(cpt)
            is_ancillary = _is_ancillary_provider(provider_name)

            if not (is_emergency or is_ancillary):
                # NSA does not apply — elective out-of-network outpatient (US-011 AC5)
                continue

            context = "emergency care" if is_emergency else "services by an out-of-network ancillary provider at an in-network facility"

            results.append(DetectionResult(
                module=self.module_name,
                error_type="No Surprises Act Violation",
                description=(
                    f"CPT {cpt} (line item {bill_item['line_number']}) may be a balance billing "
                    f"charge prohibited under the No Surprises Act. The provider is recorded as "
                    f"out-of-network in your EOB, and this charge relates to {context}. "
                    f"Under the No Surprises Act (Pub. L. 116-260), patients are protected from "
                    f"balance billing in this context."
                ),
                line_items_affected=[bill_item["line_number"]],
                estimated_dollar_impact=float(bill_item.get("amount", 0)),
                confidence="medium",
            ))

        return results
