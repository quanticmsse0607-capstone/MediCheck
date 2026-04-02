"""
OCR service — wraps AWS Textract AnalyzeDocument API.

Returns extracted fields in the shape expected by POST /upload response
and for persistence into ExtractedField + LineItem models.

CPT code descriptions are NEVER populated — AMA copyright (agreed decision in API contract).
Confidence threshold for yellow highlight: 0.80 (agreed decision).
"""

import boto3
import re
from flask import current_app


class OCRService:

    def __init__(self):
        self._client = None

    @property
    def client(self):
        if self._client is None:
            self._client = boto3.client(
                "textract",
                region_name=current_app.config["AWS_REGION"],
                aws_access_key_id=current_app.config["AWS_ACCESS_KEY_ID"],
                aws_secret_access_key=current_app.config["AWS_SECRET_ACCESS_KEY"],
            )
        return self._client

    def extract(self, file_bytes: bytes, source: str = "bill") -> dict:
        """
        Run Textract AnalyzeDocument on a PDF file.

        Args:
            file_bytes: Raw PDF bytes.
            source: 'bill' or 'eob' — tagged on every line item.

        Returns:
            dict with keys: patient_name, provider_name, date_of_service,
            total_billed, line_items (list of dicts).
        """
        response = self.client.analyze_document(
            Document={"Bytes": file_bytes},
            FeatureTypes=["TABLES", "FORMS"],
        )

        # Extract key-value pairs from FORMS feature
        kv_pairs = self._extract_key_value_pairs(response)

        # Extract table rows from TABLES feature (line items)
        line_items = self._extract_line_items(response, source)

        # Map known field names from key-value pairs
        patient_name = self._find_field(kv_pairs, ["patient name", "patient", "name"])
        provider_name = self._find_field(
            kv_pairs, ["provider", "facility", "hospital", "provider name"]
        )
        date_of_service = self._find_field(
            kv_pairs, ["date of service", "dos", "service date"]
        )
        total_billed = self._parse_amount(
            self._find_field(
                kv_pairs, ["total", "amount due", "total billed", "total charges"]
            )
        )

        return {
            "patient_name": patient_name,
            "provider_name": provider_name,
            "date_of_service": date_of_service,
            "total_billed": total_billed,
            "line_items": line_items,
        }

    # ── Private helpers ────────────────────────────────────────────────────────

    def _extract_key_value_pairs(self, response: dict) -> list[dict]:
        """
        Parse Textract FORMS response into a list of {key, value, confidence} dicts.
        """
        blocks = response.get("Blocks", [])
        block_map = {b["Id"]: b for b in blocks}

        kv_pairs = []
        for block in blocks:
            if block["BlockType"] == "KEY_VALUE_SET" and "KEY" in block.get(
                "EntityTypes", []
            ):
                key_text = self._get_text_from_block(block, block_map)
                value_block = self._get_value_block(block, block_map)
                if value_block:
                    value_text = self._get_text_from_block(value_block, block_map)
                    confidence = block.get("Confidence", 0) / 100.0
                    kv_pairs.append(
                        {
                            "key": key_text.strip().lower(),
                            "value": value_text.strip(),
                            "confidence": round(confidence, 3),
                        }
                    )

        return kv_pairs

    def _extract_line_items(self, response: dict, source: str) -> list[dict]:
        """
        Parse Textract TABLES response into line items.
        Each row with a CPT code pattern is treated as a line item.
        """
        blocks = response.get("Blocks", [])
        block_map = {b["Id"]: b for b in blocks}

        line_items = []
        line_number = 1

        for block in blocks:
            if block["BlockType"] != "TABLE":
                continue

            rows = self._extract_table_rows(block, block_map)
            for row in rows:
                if not row:
                    continue

                # Identify CPT code in the row (5-digit numeric)
                cpt_code = None
                amount = None
                date = None

                for cell_text in row:
                    cell = cell_text.strip()
                    # CPT code: 5-digit number
                    if re.match(r"^\d{5}$", cell):
                        cpt_code = cell
                    # Amount: dollar figure
                    amount_match = re.search(r"\$?([\d,]+\.\d{2})", cell)
                    if amount_match and amount is None:
                        amount = self._parse_amount(amount_match.group(1))
                    # Date: MM/DD/YYYY or YYYY-MM-DD
                    if re.match(r"\d{1,2}/\d{1,2}/\d{4}|\d{4}-\d{2}-\d{2}", cell):
                        date = cell

                if cpt_code:
                    confidence = self._estimate_row_confidence(row)
                    line_items.append(
                        {
                            "line_number": line_number,
                            "cpt_code": cpt_code,
                            "description": "",  # never populated — AMA copyright
                            "quantity": 1,
                            "amount": amount or 0.0,
                            "date": date,
                            "confidence": confidence,
                            "source": source,
                        }
                    )
                    line_number += 1

        return line_items

    def _extract_table_rows(
        self, table_block: dict, block_map: dict
    ) -> list[list[str]]:
        rows = {}
        for rel in table_block.get("Relationships", []):
            if rel["Type"] == "CHILD":
                for cell_id in rel["Ids"]:
                    cell = block_map.get(cell_id)
                    if cell and cell["BlockType"] == "CELL":
                        row_idx = cell["RowIndex"]
                        col_idx = cell["ColumnIndex"]
                        text = self._get_text_from_block(cell, block_map)
                        if row_idx not in rows:
                            rows[row_idx] = {}
                        rows[row_idx][col_idx] = text

        return [
            [row.get(col, "") for col in sorted(row.keys())]
            for row in [rows[r] for r in sorted(rows.keys())]
        ]

    def _get_value_block(self, key_block: dict, block_map: dict):
        for rel in key_block.get("Relationships", []):
            if rel["Type"] == "VALUE":
                for val_id in rel["Ids"]:
                    return block_map.get(val_id)
        return None

    def _get_text_from_block(self, block: dict, block_map: dict) -> str:
        text = ""
        for rel in block.get("Relationships", []):
            if rel["Type"] == "CHILD":
                for child_id in rel["Ids"]:
                    child = block_map.get(child_id)
                    if child and child["BlockType"] == "WORD":
                        text += child.get("Text", "") + " "
        return text.strip()

    def _find_field(self, kv_pairs: list, keys: list) -> str | None:
        for kv in kv_pairs:
            for key in keys:
                if key in kv["key"]:
                    return kv["value"]
        return None

    def _parse_amount(self, value: str | None) -> float | None:
        if not value:
            return None
        cleaned = re.sub(r"[^\d.]", "", str(value))
        try:
            return float(cleaned)
        except ValueError:
            return None

    def _estimate_row_confidence(self, row: list[str]) -> float:
        """
        Estimate confidence for a line item row.
        In a real Textract response, confidence comes from the cell blocks.
        This is a placeholder that returns 0.95 for well-formed rows.
        """
        non_empty = [c for c in row if c.strip()]
        if len(non_empty) >= 3:
            return 0.95
        return 0.72
