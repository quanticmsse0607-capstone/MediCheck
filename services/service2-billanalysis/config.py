import os


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

    # Service 3
    SERVICE3_URL = os.environ.get("SERVICE3_URL", "http://localhost:5001")
    SERVICE3_TIMEOUT_SECONDS = 10  # NFR-18: explicit 10-second timeout, always

    # File upload limits (FR-01)
    MAX_FILE_SIZE_MB = int(os.environ.get("MAX_FILE_SIZE_MB", 10))
    MAX_PAGE_COUNT = int(os.environ.get("MAX_PAGE_COUNT", 20))

    # OCR confidence threshold below which fields are flagged (UI highlights in yellow)
    OCR_CONFIDENCE_THRESHOLD = 0.80  # Agreed decision in API contract


class DevelopmentConfig(Config):
    DEBUG = True


class ProductionConfig(Config):
    DEBUG = False

    # On Render, DATABASE_URL may start with postgres:// — SQLAlchemy needs postgresql://
    _db_url = os.environ.get("DATABASE_URL", "")
    if _db_url.startswith("postgres://"):
        SQLALCHEMY_DATABASE_URI = _db_url.replace("postgres://", "postgresql://", 1)


config = {
    "development": DevelopmentConfig,
    "production": ProductionConfig,
    "default": DevelopmentConfig,
}
