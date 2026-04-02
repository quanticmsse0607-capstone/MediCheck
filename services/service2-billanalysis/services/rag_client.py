"""
RAG client — HTTP client for Service 3 (explanation + letter generation).

NFR-18: Every outbound call to Service 3 MUST specify an explicit 10-second timeout.
        Missing timeout = code review failure.
NFR-02: If Service 3 does not respond in 10 seconds, return partial response.
        Caller receives rag_available: false — never a 500 error.
"""

import requests
import logging
from flask import current_app

logger = logging.getLogger(__name__)


class RAGClient:

    def __init__(self):
        self._base_url: str | None = None
        self._timeout: int | None = None

    @property
    def base_url(self) -> str:
        if self._base_url is None:
            self._base_url = current_app.config["SERVICE3_URL"].rstrip("/")
        return self._base_url

    @property
    def timeout(self) -> int:
        if self._timeout is None:
            self._timeout = current_app.config["SERVICE3_TIMEOUT_SECONDS"]  # always 10
        return self._timeout

    def get_explanations(self, session_id: str, errors: list[dict]) -> dict:
        """
        Call Service 3 POST /explain to get RAG-grounded explanations.

        Args:
            session_id: Current session ID (for retry endpoint)
            errors: List of error dicts from DetectionEngine

        Returns:
            {
                "success": bool,
                "explanations": {error_id: {"explanation": str, "citations": list}},
                "rag_available": bool,
            }
        """
        try:
            response = requests.post(
                f"{self.base_url}/explain",
                json={"session_id": session_id, "errors": errors},
                timeout=self.timeout,  # NFR-18: explicit 10-second timeout — ALWAYS present
            )
            response.raise_for_status()
            data = response.json()
            return {
                "success": True,
                "explanations": data.get("explanations", {}),
                "rag_available": True,
            }

        except requests.Timeout:
            # NFR-02: timeout → partial response, rag_available: false
            logger.warning(
                "Service 3 /explain timed out after %ss for session %s",
                self.timeout,
                session_id,
            )
            return {
                "success": False,
                "explanations": {},
                "rag_available": False,
            }

        except requests.RequestException as exc:
            # Any other connectivity issue — treat same as timeout
            logger.error("Service 3 /explain error for session %s: %s", session_id, exc)
            return {
                "success": False,
                "explanations": {},
                "rag_available": False,
            }

    def generate_letter(self, session_id: str, analysis_data: dict) -> dict:
        """
        Call Service 3 POST /draft-letter to generate dispute letter content.

        Args:
            session_id: Current session ID
            analysis_data: Full analysis payload including errors + confirmed fields

        Returns:
            {
                "success": bool,
                "letter_content": str or None,
            }
        """
        try:
            response = requests.post(
                f"{self.base_url}/draft-letter",
                json={"session_id": session_id, "analysis": analysis_data},
                timeout=self.timeout,  # NFR-18: explicit 10-second timeout — ALWAYS present
            )
            response.raise_for_status()
            data = response.json()
            return {
                "success": True,
                "letter_content": data.get("letter_content"),
            }

        except requests.Timeout:
            logger.warning(
                "Service 3 /draft-letter timed out after %ss for session %s",
                self.timeout,
                session_id,
            )
            return {"success": False, "letter_content": None}

        except requests.RequestException as exc:
            logger.error(
                "Service 3 /draft-letter error for session %s: %s", session_id, exc
            )
            return {"success": False, "letter_content": None}
