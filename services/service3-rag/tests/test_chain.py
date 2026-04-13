"""
tests/test_chain.py
Unit tests for rag/chain.py — explain_detection() and draft_letter_content().

All OpenAI and ChromaDB calls are mocked. These tests verify:
- RuntimeError when chain is called before init_chain()
- Output shape and citation format
- Citation deduplication
- Correct handling of empty retrieval results
"""

import pytest
from unittest.mock import MagicMock, patch
from langchain.schema import Document


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_doc(title, section, page):
    """Create a mock Document with controlled metadata."""
    doc = MagicMock(spec=Document)
    doc.page_content = f"Regulatory content from {title}."
    doc.metadata = {
        "document_title": title,
        "section": section,
        "page_number": page,
    }
    return doc


def _reset_chain_singletons():
    """Reset module-level singletons between tests."""
    import rag.chain as chain_module
    chain_module._retriever = None
    chain_module._chain = None
    chain_module._letter_chain = None


# ── explain_detection() ───────────────────────────────────────────────────────

class TestExplainDetection:

    def setup_method(self):
        _reset_chain_singletons()

    def test_raises_when_not_initialized(self):
        from rag.chain import explain_detection
        with pytest.raises(RuntimeError, match="not initialized"):
            explain_detection({"error_type": "Duplicate Charge", "description": "test"})

    def test_returns_explanation_and_citations(self):
        import rag.chain as chain_module

        mock_doc = _make_doc(
            "No Surprises Act at a Glance", "Key Protections", 2
        )
        chain_module._retriever = MagicMock()
        chain_module._retriever.invoke.return_value = [mock_doc]
        chain_module._chain = MagicMock()
        chain_module._chain.invoke.return_value = "This is a plain-English explanation."

        from rag.chain import explain_detection
        detection = {
            "error_id": "err_001",
            "module": "no_surprises_act",
            "error_type": "Surprise Billing Violation",
            "description": "Patient billed by out-of-network provider.",
        }
        result = explain_detection(detection)

        assert result["explanation"] == "This is a plain-English explanation."
        assert len(result["citations"]) == 1
        assert result["citations"][0]["source"] == "No Surprises Act at a Glance"
        assert result["citations"][0]["section"] == "Key Protections"
        assert result["citations"][0]["url"] is None

    def test_citation_uses_page_when_no_section(self):
        import rag.chain as chain_module

        doc = _make_doc("ICD-10-CM Guidelines", "", 5)
        chain_module._retriever = MagicMock()
        chain_module._retriever.invoke.return_value = [doc]
        chain_module._chain = MagicMock()
        chain_module._chain.invoke.return_value = "Explanation text."

        from rag.chain import explain_detection
        result = explain_detection({
            "error_type": "Coding Error",
            "description": "Wrong ICD-10 code used.",
        })

        assert result["citations"][0]["section"] == "p. 5"

    def test_citations_are_deduplicated(self):
        import rag.chain as chain_module

        # Two docs from the same source document
        docs = [
            _make_doc("No Surprises Act at a Glance", "Section A", 1),
            _make_doc("No Surprises Act at a Glance", "Section B", 3),
        ]
        chain_module._retriever = MagicMock()
        chain_module._retriever.invoke.return_value = docs
        chain_module._chain = MagicMock()
        chain_module._chain.invoke.return_value = "Explanation."

        from rag.chain import explain_detection
        result = explain_detection({"error_type": "Test", "description": "Test"})

        assert len(result["citations"]) == 1

    def test_empty_retrieval_returns_empty_citations(self):
        import rag.chain as chain_module

        chain_module._retriever = MagicMock()
        chain_module._retriever.invoke.return_value = []
        chain_module._chain = MagicMock()
        chain_module._chain.invoke.return_value = "Explanation with no context."

        from rag.chain import explain_detection
        result = explain_detection({"error_type": "Test", "description": "Test"})

        assert result["citations"] == []

    def test_original_fields_preserved(self):
        import rag.chain as chain_module

        chain_module._retriever = MagicMock()
        chain_module._retriever.invoke.return_value = []
        chain_module._chain = MagicMock()
        chain_module._chain.invoke.return_value = "Explanation."

        from rag.chain import explain_detection
        detection = {
            "error_id": "err_001",
            "module": "duplicate_charge",
            "error_type": "Duplicate Charge",
            "description": "CPT 99213 billed twice.",
            "estimated_dollar_impact": 150.0,
            "confidence": "high",
        }
        result = explain_detection(detection)

        assert result["error_id"] == "err_001"
        assert result["module"] == "duplicate_charge"
        assert result["estimated_dollar_impact"] == 150.0


# ── draft_letter_content() ────────────────────────────────────────────────────

class TestDraftLetterContent:

    def setup_method(self):
        _reset_chain_singletons()

    def test_raises_when_not_initialized(self):
        from rag.chain import draft_letter_content
        with pytest.raises(RuntimeError, match="not initialized"):
            draft_letter_content({"patient_name": "Jane"})

    def test_returns_string(self):
        import rag.chain as chain_module

        chain_module._retriever = MagicMock()
        chain_module._retriever.invoke.return_value = []
        chain_module._letter_chain = MagicMock()
        chain_module._letter_chain.invoke.return_value = "I respectfully request a review."

        from rag.chain import draft_letter_content
        result = draft_letter_content({
            "patient_name": "James Whitfield",
            "provider_name": "Atrium Health",
            "total_estimated_savings": 747.0,
            "errors": [
                {"error_type": "Duplicate Charge", "estimated_dollar_impact": 480.0}
            ],
        })

        assert isinstance(result, str)
        assert len(result) > 0

    def test_handles_empty_errors_list(self):
        import rag.chain as chain_module

        chain_module._retriever = MagicMock()
        chain_module._retriever.invoke.return_value = []
        chain_module._letter_chain = MagicMock()
        chain_module._letter_chain.invoke.return_value = "Dispute paragraph."

        from rag.chain import draft_letter_content
        result = draft_letter_content({
            "patient_name": "Jane",
            "provider_name": "Provider",
            "total_estimated_savings": 0.0,
            "errors": [],
        })

        assert isinstance(result, str)
