import os


class Config:
    """Base configuration — values shared across all environments."""

    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-change-in-prod")

    # OpenAI
    OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
    OPENAI_MODEL = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")

    # ChromaDB — vector store for RAG knowledge base
    CHROMA_PERSIST_PATH = os.environ.get("CHROMA_PERSIST_PATH", "./chroma_db")

    # CORS — origins allowed to call this service
    # In production this should be the Render URL of Service 2
    CORS_ORIGINS = os.environ.get("CORS_ORIGINS", "*").split(",")

    # Service 2 (used if Service 3 needs to call back)
    SERVICE2_URL = os.environ.get("SERVICE2_URL", "http://localhost:5000")

    # RAG retrieval settings
    RAG_TOP_K = int(os.environ.get("RAG_TOP_K", 3))


class DevelopmentConfig(Config):
    DEBUG = True


class ProductionConfig(Config):
    DEBUG = False


config = {
    "development": DevelopmentConfig,
    "production": ProductionConfig,
    "default": DevelopmentConfig,
}
