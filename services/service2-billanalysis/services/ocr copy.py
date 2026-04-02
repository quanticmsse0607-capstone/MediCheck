"""
Mock OCR service for local development — no AWS required.

Swap this in by setting USE_MOCK_OCR=true in your .env.
Returns realistic synthetic data matching Demo Scenario A (Atrium Health).

Switch back to real Textract anytime by setting USE_MOCK_OCR=false.
"""


class MockOCRService:

    def extract(self, file_bytes: bytes, source: str = "bill") -> dict:
        """
        Returns a realistic synthetic extraction without calling AWS.
        Matches Demo Scenario A: Atrium Health, BCBS SC PPO.
        """
        if source == "bill":
            return self._mock_bill()
        return self._mock_eob()

    def _mock_bill(self) -> dict:
        return {
            "patient_name": "James Whitfield",
            "provider_name": "Atrium Health Carolinas Medical Center",
            "date_of_service": "2025-09-17",
            "total_billed": 12085.00,
            "line_items": [
                {
                    "line_number": 1,
                    "cpt_code": "29881",
                    "description": "",
                    "quantity": 1,
                    "amount": 3200.00,
                    "date": "2025-09-17",
                    "confidence": 0.97,
                    "source": "bill",
                },
                {
                    "line_number": 2,
                    "cpt_code": "99215",
                    "description": "",
                    "quantity": 1,
                    "amount": 267.00,  # 327% of Medicare rate $82 — triggers Module 2
                    "date": "2025-09-17",
                    "confidence": 0.94,
                    "source": "bill",
                },
                {
                    "line_number": 3,
                    "cpt_code": "00400",
                    "description": "",
                    "quantity": 1,
                    "amount": 1850.00,
                    "date": "2025-09-17",
                    "confidence": 0.91,
                    "source": "bill",
                },
                {
                    "line_number": 7,
                    "cpt_code": "29881",  # duplicate of line 1 — triggers Module 1
                    "description": "",
                    "quantity": 1,
                    "amount": 3200.00,
                    "date": "2025-09-17",
                    "confidence": 0.43,  # low confidence — will highlight yellow in UI
                    "source": "bill",
                },
            ],
        }

    def _mock_eob(self) -> dict:
        return {
            "patient_name": "James Whitfield",
            "provider_name": "Atrium Health Carolinas Medical Center",
            "date_of_service": "2025-09-17",
            "total_billed": 12085.00,
            "line_items": [
                {
                    "line_number": 1,
                    "cpt_code": "29881",
                    "description": "",
                    "quantity": 1,
                    "amount": 798.74,  # EOB shows Medicare rate — triggers Module 3
                    "date": "2025-09-17",
                    "confidence": 0.96,
                    "source": "eob",
                    "network_status": "in-network",
                },
                {
                    "line_number": 2,
                    "cpt_code": "00400",
                    "description": "",
                    "quantity": 1,
                    "amount": 1850.00,
                    "date": "2025-09-17",
                    "confidence": 0.95,
                    "source": "eob",
                    "network_status": "out-of-network",  # triggers Module 4 (NSA)
                },
            ],
        }
