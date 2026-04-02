"""
SQLAlchemy models for MediCheck Service 2.

Session state machine (FR-26):
    extracted → confirmed → analysed → letter_generated

Any request that would skip a step returns HTTP 400 NOT_CONFIRMED.
"""

import uuid
from datetime import datetime, timezone

from extensions import db


# ── Helpers ───────────────────────────────────────────────────────────────────


def _new_uuid():
    return str(uuid.uuid4())


def _now():
    return datetime.now(timezone.utc)


# ── Valid session statuses (FR-26) ────────────────────────────────────────────


class SessionStatus:
    EXTRACTED = "extracted"
    CONFIRMED = "confirmed"
    ANALYSED = "analysed"
    LETTER_GENERATED = "letter_generated"

    # Ordered transitions — a request is valid only if current status matches
    # the expected predecessor
    TRANSITIONS = {
        EXTRACTED: None,  # set on upload, no predecessor
        CONFIRMED: EXTRACTED,  # confirm requires extracted
        ANALYSED: CONFIRMED,  # analyse requires confirmed
        LETTER_GENERATED: ANALYSED,  # letter requires analysed
    }

    @classmethod
    def can_transition_to(cls, current: str, target: str) -> bool:
        return cls.TRANSITIONS.get(target) == current


# ── Models ────────────────────────────────────────────────────────────────────


class Session(db.Model):
    """
    One session per user upload interaction.
    Created by POST /upload, progresses through status transitions.
    Retained for minimum 24 hours (FR-25).
    """

    __tablename__ = "sessions"

    session_id = db.Column(db.String(36), primary_key=True, default=_new_uuid)
    status = db.Column(db.String(32), nullable=False, default=SessionStatus.EXTRACTED)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=_now)
    updated_at = db.Column(
        db.DateTime(timezone=True), nullable=False, default=_now, onupdate=_now
    )

    # Back-references
    extracted_fields = db.relationship(
        "ExtractedField", backref="session", lazy=True, cascade="all, delete-orphan"
    )
    analysis_results = db.relationship(
        "AnalysisResult", backref="session", lazy=True, cascade="all, delete-orphan"
    )
    letter = db.relationship(
        "DisputeLetter", backref="session", uselist=False, cascade="all, delete-orphan"
    )

    def to_dict(self):
        return {
            "session_id": self.session_id,
            "status": self.status,
            "created_at": self.created_at.isoformat(),
        }


class ExtractedField(db.Model):
    """
    One row per extracted field per session.
    Stores both the raw OCR value and the user-corrected value (FR-07).
    Original extracted_value is never overwritten — corrected_value holds edits.
    source: 'bill' or 'eob' — agreed decision in API contract.
    """

    __tablename__ = "extracted_fields"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    session_id = db.Column(
        db.String(36), db.ForeignKey("sessions.session_id"), nullable=False
    )

    # Top-level fields
    patient_name = db.Column(db.String(256))
    provider_name = db.Column(db.String(256))
    date_of_service = db.Column(db.String(32))  # stored as ISO string
    total_billed = db.Column(db.Numeric(10, 2))

    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=_now)

    # Line items stored as a relationship
    line_items = db.relationship(
        "LineItem", backref="extracted_field", lazy=True, cascade="all, delete-orphan"
    )

    def to_dict(self):
        return {
            "patient_name": self.patient_name,
            "provider_name": self.provider_name,
            "date_of_service": self.date_of_service,
            "total_billed": float(self.total_billed) if self.total_billed else None,
            "line_items": [li.to_dict() for li in self.line_items],
        }


class LineItem(db.Model):
    """
    One row per line item in the extracted bill or EOB.
    Stores both original extracted values and user-corrected values.
    Confidence is stored at extraction time and NOT forwarded to /confirm (agreed decision).
    """

    __tablename__ = "line_items"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    extracted_field_id = db.Column(
        db.Integer, db.ForeignKey("extracted_fields.id"), nullable=False
    )

    line_number = db.Column(db.Integer, nullable=False)
    cpt_code = db.Column(db.String(16))
    description = db.Column(
        db.String(512), default=""
    )  # always empty — AMA copyright (agreed decision)
    quantity = db.Column(db.Integer, default=1)
    source = db.Column(db.String(8), nullable=False, default="bill")  # 'bill' or 'eob'

    # Extracted values (immutable after OCR)
    extracted_amount = db.Column(db.Numeric(10, 2))
    extracted_date = db.Column(db.String(32))
    confidence = db.Column(db.Numeric(4, 3))  # 0.000 – 1.000

    # Corrected values (set by POST /confirm, may be null if user made no changes)
    corrected_amount = db.Column(db.Numeric(10, 2))
    corrected_date = db.Column(db.String(32))

    @property
    def amount(self):
        """Return corrected amount if available, otherwise extracted."""
        return (
            float(self.corrected_amount)
            if self.corrected_amount is not None
            else float(self.extracted_amount or 0)
        )

    def to_dict(self, include_confidence=False):
        d = {
            "line_number": self.line_number,
            "cpt_code": self.cpt_code,
            "description": self.description,
            "quantity": self.quantity,
            "amount": self.amount,
            "source": self.source,
        }
        if include_confidence:
            d["confidence"] = float(self.confidence) if self.confidence else None
        return d


class AnalysisResult(db.Model):
    """
    One row per detected error per session.
    Produced by POST /analyse → ErrorDetectionEngine.
    explanation and citations are null when RAG service times out (NFR-02).
    """

    __tablename__ = "analysis_results"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    session_id = db.Column(
        db.String(36), db.ForeignKey("sessions.session_id"), nullable=False
    )

    error_id = db.Column(db.String(16), nullable=False)  # e.g. "err_001"
    module = db.Column(db.String(64), nullable=False)  # e.g. "duplicate_charge"
    error_type = db.Column(db.String(128), nullable=False)
    description = db.Column(db.Text, nullable=False)
    line_items_affected = db.Column(db.Text)  # JSON-encoded list of line numbers
    estimated_dollar_impact = db.Column(db.Numeric(10, 2))
    confidence = db.Column(db.String(8))  # 'high', 'medium', 'low' (agreed decision)

    # RAG-populated fields — null if Service 3 timed out
    explanation = db.Column(db.Text)
    citations = db.Column(db.Text)  # JSON-encoded list of citation objects

    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=_now)

    def to_dict(self):
        import json

        return {
            "error_id": self.error_id,
            "module": self.module,
            "error_type": self.error_type,
            "description": self.description,
            "line_items_affected": (
                json.loads(self.line_items_affected) if self.line_items_affected else []
            ),
            "estimated_dollar_impact": (
                float(self.estimated_dollar_impact)
                if self.estimated_dollar_impact
                else 0.0
            ),
            "confidence": self.confidence,
            "explanation": self.explanation,
            "citations": json.loads(self.citations) if self.citations else [],
        }


class DisputeLetter(db.Model):
    """
    Generated dispute letter for a session.
    Both docx and pdf paths stored so files can be re-served without regenerating (FR-23).
    """

    __tablename__ = "dispute_letters"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    session_id = db.Column(
        db.String(36), db.ForeignKey("sessions.session_id"), nullable=False
    )

    docx_path = db.Column(db.String(512))  # filesystem path to generated .docx
    pdf_path = db.Column(db.String(512))  # filesystem path to generated .pdf

    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=_now)
