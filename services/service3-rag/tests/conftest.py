"""
tests/conftest.py
Shared test configuration and fixtures.

IMPORTANT: The env var and patch must be set up BEFORE any test file imports
app.py, because app.py runs `app = create_app()` at module level, which calls
init_chain(). conftest.py is loaded by pytest before test collection begins.
"""

import os
import pytest
from unittest.mock import patch

# Set a dummy API key so OpenAIEmbeddings validation passes during import
os.environ.setdefault("OPENAI_API_KEY", "sk-test-not-real")

# Patch init_chain before any test module triggers app.py import.
# This prevents real OpenAI/ChromaDB connections during test collection.
patch("rag.chain.init_chain").start()

from app import create_app  # noqa: E402 — must come after patch


@pytest.fixture
def client():
    app = create_app("development")
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c
