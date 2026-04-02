"""
Mock OCR service — returns synthetic test data without calling AWS Textract.

Used for development and testing when USE_MOCK_OCR=true environment variable is set.

CPT code descriptions are NEVER populated — AMA copyright (agreed decision in API contract).
Confidence threshold for yellow highlight: 0.80 (agreed decision).
"""

import re


class MockOCRService:
    """
    Mock OCR that returns realistic synthetic data for testing.
    Does not require AWS credentials or call any external APIs.
    """

    def __init__(self):
        pass

    def extract(self, file_bytes: bytes, source: str = "bill") -> dict:
        """
        Return mock extracted data.

        Args:
            file_bytes: Raw PDF bytes (not used, for interface compatibility).
            source: 'bill' or 'eob' — tagged on every line item.

        Returns:
            dict with keys: patient_name, provider_name, date_of_service,
            total_billed, line_items (list of dicts).
        """
        # Return realistic synthetic bill/EOB data
        if source == "bill":
            return self._get_mock_bill_data()
        else:
            return self._get_mock_eob_data()

    def _get_mock_bill_data(self) -> dict:
        """Return mock medical bill data."""
        return {
            "patient_name": "John Doe",
            "provider_name": "Acme Hospital",
            "date_of_service": "2024-01-15",
            "total_billed": 1500.00,
            "line_items": [
                {
                    "line_number": 1,
                    "cpt_code": "99213",
                    "description": "",  # AMA copyright — never populated
                    "quantity": 1,
                    "amount": 150.00,
                    "date": "2024-01-15",
                    "confidence": 0.95,
                    "source": "bill",
                },
                {
                    "line_number": 2,
                    "cpt_code": "99213",  # Duplicate for testing duplicate detector
                    "description": "",
                    "quantity": 1,
                    "amount": 150.00,
                    "date": "2024-01-15",
                    "confidence": 0.95,
                    "source": "bill",
                },
                {
                    "line_number": 3,
                    "cpt_code": "99214",
                    "description": "",
                    "quantity": 1,
                    "amount": 300.00,
                    "date": "2024-01-15",
                    "confidence": 0.92,
                    "source": "bill",
                },
                {
                    "line_number": 4,
                    "cpt_code": "99215",
                    "description": "",
                    "quantity": 1,
                    "amount": 900.00,
                    "date": "2024-01-15",
                    "confidence": 0.88,
                    "source": "bill",
                },
            ],
        }

    def _get_mock_eob_data(self) -> dict:
        """Return mock EOB data."""
        return {
            "patient_name": "John Doe",
            "provider_name": "Acme Hospital",
            "date_of_service": "2024-01-15",
            "total_billed": 1200.00,  # Less than bill (mismatch for testing)
            "line_items": [
                {
                    "line_number": 1,
                    "cpt_code": "99213",
                    "description": "",
                    "quantity": 1,
                    "amount": 120.00,
                    "date": "2024-01-15",
                    "confidence": 0.94,
                    "source": "eob",
                },
                {
                    "line_number": 2,
                    "cpt_code": "99214",
                    "description": "",
                    "quantity": 1,
                    "amount": 240.00,
                    "date": "2024-01-15",
                    "confidence": 0.94,
                    "source": "eob",
                },
                {
                    "line_number": 3,
                    "cpt_code": "99215",
                    "description": "",
                    "quantity": 1,
                    "amount": 840.00,
                    "date": "2024-01-15",
                    "confidence": 0.90,
                    "source": "eob",
                },
            ],
        }
