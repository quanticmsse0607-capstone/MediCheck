"""
BaseDetector — abstract base class for all error detection checks.

Strategy pattern implementation (FR-15):
    A new detector can be added by subclassing BaseDetector and implementing run().
    ErrorDetectionEngine discovers and runs detectors without modification.

Every detector must return a list of DetectionResult objects.
A missing required field on any result is treated as a system defect (FR-16).
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class DetectionResult:
    """
    Represents a single detected billing error.
    All six fields required by FR-16. Any None on a required field = system defect.
    """

    # FR-16 required fields
    module: str                           # name of the detector that produced this result
    error_type: str                       # human-readable category e.g. "Duplicate Charge"
    description: str                      # plain-English description of the issue
    line_items_affected: list[int]        # line numbers of affected items
    estimated_dollar_impact: float        # USD
    confidence: str                       # 'high', 'medium', or 'low'

    # RAG-populated fields — filled by rag_client after detection, null on timeout
    explanation: Optional[str] = None
    citations: list = field(default_factory=list)

    def validate(self) -> list[str]:
        """
        Returns a list of validation errors.
        Empty list means result is valid.
        Called by ErrorDetectionEngine before persisting.
        """
        errors = []
        if not self.module:
            errors.append("module is required")
        if not self.error_type:
            errors.append("error_type is required")
        if not self.description:
            errors.append("description is required")
        if self.line_items_affected is None:
            errors.append("line_items_affected is required (use empty list if none)")
        if self.estimated_dollar_impact is None:
            errors.append("estimated_dollar_impact is required")
        if self.confidence not in ("high", "medium", "low"):
            errors.append("confidence must be 'high', 'medium', or 'low'")
        return errors

    def to_dict(self) -> dict:
        return {
            "module": self.module,
            "error_type": self.error_type,
            "description": self.description,
            "line_items_affected": self.line_items_affected,
            "estimated_dollar_impact": self.estimated_dollar_impact,
            "confidence": self.confidence,
            "explanation": self.explanation,
            "citations": self.citations,
        }


class BaseDetector(ABC):
    """
    Abstract base class for all error detection checks.

    Subclass this and implement run() to add a new detector.
    No changes to ErrorDetectionEngine or any other detector are required (FR-15).
    """

    @property
    @abstractmethod
    def module_name(self) -> str:
        """
        Unique identifier for this detector.
        Used in DetectionResult.module and in error_id generation.
        Example: 'duplicate_charge', 'medicare_rate_outlier'
        """

    @abstractmethod
    def run(self, confirmed_fields: dict) -> list[DetectionResult]:
        """
        Run this detection check against confirmed bill data.

        Args:
            confirmed_fields: dict containing:
                patient_name, provider_name, date_of_service, total_billed,
                line_items: list of {line_number, cpt_code, amount, date, source, quantity}

        Returns:
            List of DetectionResult objects — empty list means all clear for this check.
            FR-10: must return result (finding or empty list) — never raise silently.
        """
