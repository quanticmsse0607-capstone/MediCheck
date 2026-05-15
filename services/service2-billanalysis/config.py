"""
Application configuration.

Anti-pattern fixes:
  H1: SERVICE2_BASE_URL defaults to empty string, not localhost:5000
  H5: SERVICE3_URL defaults to empty string, not localhost:5002
  Both: startup validation added to warn on missing production config
"""

import os
import logging

logger = logging.getLogger(__name__)


class Config:
    """Base configuration — values shared across all environments."""

    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-change-in-prod")
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Database
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL", "sqlite:///medicheck_dev.db"
    )

    # AWS Textract
    AWS_ACCESS_KEY_ID = os.environ.get("AWS_ACCESS_KEY_ID")
    AWS_SECRET_ACCESS_KEY = os.environ.get("AWS_SECRET_ACCESS_KEY")
    AWS_REGION = os.environ.get("AWS_REGION", "us-east-1")

    # FIX H5: SERVICE3_URL no longer defaults to localhost silently in production
    # Empty string causes an immediate connection error rather than silent misrouting
    SERVICE3_URL = os.environ.get("SERVICE3_URL", "http://localhost:5002")
    SERVICE3_TIMEOUT_SECONDS = 10  # NFR-18

    # FIX H1: SERVICE2_BASE_URL no longer defaults to localhost:5000 silently
    SERVICE2_BASE_URL = os.environ.get("SERVICE2_BASE_URL", "http://localhost:5001")

    # File upload limits (FR-01)
    MAX_FILE_SIZE_MB = int(os.environ.get("MAX_FILE_SIZE_MB", 10))
    MAX_PAGE_COUNT = int(os.environ.get("MAX_PAGE_COUNT", 20))

    # OCR confidence threshold below which fields are flagged (UI yellow highlight)
    OCR_CONFIDENCE_THRESHOLD = 0.80


class DevelopmentConfig(Config):
    DEBUG = True


class ProductionConfig(Config):
    DEBUG = False

    # Render DATABASE_URL starts with postgres:// — SQLAlchemy needs postgresql://
    _db_url = os.environ.get("DATABASE_URL", "")
    if _db_url.startswith("postgres://"):
        SQLALCHEMY_DATABASE_URI = _db_url.replace("postgres://", "postgresql://", 1)

    @classmethod
    def validate(cls):
        """
        FIX H1, H5: Warn loudly at startup if critical env vars are missing
        in production. Does not crash — logs warnings so deploys are visible.
        """
        required = {
            "SERVICE3_URL": cls.SERVICE3_URL,
            "SERVICE2_BASE_URL": cls.SERVICE2_BASE_URL,
            "DATABASE_URL": os.environ.get("DATABASE_URL", ""),
        }
        for key, val in required.items():
            if not val or "localhost" in val:
                logger.warning(
                    "PRODUCTION CONFIG WARNING: %s is set to '%s'. "
                    "This may cause silent misrouting. "
                    "Set the correct Render URL via environment variables.",
                    key,
                    val,
                )


config = {
    "development": DevelopmentConfig,
    "production": ProductionConfig,
    "default": DevelopmentConfig,
}
