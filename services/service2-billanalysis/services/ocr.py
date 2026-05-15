"""
OCR service — AWS Textract AnalyzeDocument API.

Replaces pdfplumber with ML-based extraction that handles any PDF layout
including scanned documents, varied bill formats, and non-standard layouts.

Textract free tier: 1,000 pages/month for 12 months.
AWS credentials read from environment variables (NFR-07).

CPT code descriptions are NEVER populated — AMA copyright (agreed decision).
"""

import re
import boto3
from flask import current_app


class OCRService:

    def __init__(self):
        self._client = None

    @property
    def client(self):
        if self._client is None:
            self._client = boto3.client(
                "textract",
                region_name=current_app.config.get("AWS_REGION", "us-east-1"),
                aws_access_key_id=current_app.config.get("AWS_ACCESS_KEY_ID"),
                aws_secret_access_key=current_app.config.get("AWS_SECRET_ACCESS_KEY"),
            )
        return self._client

    def extract(self, file_bytes: bytes, source: str = "bill") -> dict:
        """
        Extract structured data from a PDF using AWS Textract.
        Automatically converts PDF to image first (required for ReportLab
        and other vector PDFs that Textract cannot process directly).
        """
        result = {
            "patient_name": None,
            "provider_name": None,
            "date_of_service": None,
            "total_billed": None,
            "line_items": [],
        }

        textract_bytes = self._pdf_to_image_bytes(file_bytes)

        response = self.client.analyze_document(
            Document={"Bytes": textract_bytes},
            FeatureTypes=["TABLES", "FORMS"],
        )

        blocks = response.get("Blocks", [])
        block_map = {b["Id"]: b for b in blocks}

        kvs = self._extract_key_values(blocks, block_map)
        tables = self._extract_tables(blocks, block_map)

        lines = [b["Text"] for b in blocks if b["BlockType"] == "LINE"]
        full_text = "\n".join(lines)

        result["patient_name"] = self._find_patient_name(kvs, full_text)
        result["provider_name"] = self._find_provider_name(kvs, full_text)
        result["date_of_service"] = self._find_date(kvs, full_text)
        result["total_billed"] = self._find_total(kvs, full_text)

        line_items = self._extract_line_items_from_tables(tables, source)
        if not line_items:
            line_items = self._extract_line_items_from_text(full_text, source)
        result["line_items"] = line_items

        return result

    # ── PDF to image conversion ────────────────────────────────────

    def _pdf_to_image_bytes(self, file_bytes: bytes) -> bytes:
        """Convert first page of PDF to PNG for Textract."""
        import io

        try:
            from pdf2image import convert_from_bytes

            images = convert_from_bytes(file_bytes, dpi=300, first_page=1, last_page=1)
            if not images:
                return file_bytes
            img_bytes = io.BytesIO()
            images[0].save(img_bytes, format="PNG")
            return img_bytes.getvalue()
        except ImportError:
            return file_bytes
        except Exception:
            return file_bytes

    # ── Textract block parsing ─────────────────────────────────────

    def _extract_key_values(self, blocks, block_map) -> dict:
        kvs = {}
        key_blocks = [
            b
            for b in blocks
            if b["BlockType"] == "KEY_VALUE_SET" and "KEY" in b.get("EntityTypes", [])
        ]
        for key_block in key_blocks:
            key_text = self._get_text_from_relationships(key_block, block_map)
            value_block = self._get_value_block(key_block, block_map)
            if value_block:
                value_text = self._get_text_from_relationships(value_block, block_map)
                if key_text:
                    kvs[key_text.strip().lower()] = value_text.strip()
        return kvs

    def _get_value_block(self, key_block, block_map):
        for rel in key_block.get("Relationships", []):
            if rel["Type"] == "VALUE":
                for vid in rel["Ids"]:
                    return block_map.get(vid)
        return None

    def _get_text_from_relationships(self, block, block_map) -> str:
        text = ""
        for rel in block.get("Relationships", []):
            if rel["Type"] == "CHILD":
                for cid in rel["Ids"]:
                    child = block_map.get(cid, {})
                    if child.get("BlockType") == "WORD":
                        text += child.get("Text", "") + " "
        return text.strip()

    def _extract_tables(self, blocks, block_map) -> list:
        tables = []
        table_blocks = [b for b in blocks if b["BlockType"] == "TABLE"]
        for table_block in table_blocks:
            cells = {}
            for rel in table_block.get("Relationships", []):
                if rel["Type"] == "CHILD":
                    for cid in rel["Ids"]:
                        cell = block_map.get(cid, {})
                        if cell.get("BlockType") == "CELL":
                            row = cell.get("RowIndex", 0)
                            col = cell.get("ColumnIndex", 0)
                            text = self._get_text_from_relationships(cell, block_map)
                            cells[(row, col)] = text
            if not cells:
                continue
            max_row = max(r for r, c in cells)
            max_col = max(c for r, c in cells)
            table = []
            for r in range(1, max_row + 1):
                row = [cells.get((r, c), "") for c in range(1, max_col + 1)]
                table.append(row)
            tables.append(table)
        return tables

    # ── Field extraction ───────────────────────────────────────────

    def _find_patient_name(self, kvs: dict, text: str) -> str | None:
        name_keys = [
            "patient name",
            "patient",
            "member name",
            "member",
            "beneficiary",
            "insured",
            "subscriber",
        ]
        for k in name_keys:
            if k in kvs and kvs[k]:
                words = kvs[k].split()[:3]
                clean = []
                stop = {
                    "svc",
                    "dob",
                    "date",
                    "member",
                    "group",
                    "account",
                    "plan",
                    "id",
                    "phone",
                }
                for w in words:
                    if w.lower() in stop:
                        break
                    clean.append(w)
                if clean:
                    return " ".join(clean)
        patterns = [
            r"Patient\s*Name[:\s]+([A-Z][a-zA-Z'-]+(?:\s+[A-Z][a-zA-Z'-]+){1,3})",
            r"Patient[:\s]+([A-Z][a-zA-Z'-]+(?:\s+[A-Z][a-zA-Z'-]+){1,3})",
            r"Member\s*Name[:\s]+([A-Z][a-zA-Z'-]+(?:\s+[A-Z][a-zA-Z'-]+){1,3})",
            r"Member[:\s]+([A-Z][a-zA-Z'-]+(?:\s+[A-Z][a-zA-Z'-]+){1,3})",
            r"Beneficiary[:\s]+([A-Z][a-zA-Z'-]+(?:\s+[A-Z][a-zA-Z'-]+){1,3})",
        ]
        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                words = match.group(1).strip().split()[:3]
                return " ".join(words)
        return None

    def _find_provider_name(self, kvs: dict, text: str) -> str | None:
        provider_keys = [
            "provider",
            "facility",
            "hospital",
            "provider name",
            "facility name",
            "billed by",
            "from",
        ]
        for k in provider_keys:
            if k in kvs and kvs[k]:
                return kvs[k][:80]

        title_skip = {
            "BILL",
            "INVOICE",
            "STATEMENT",
            "SERVICES BILL",
            "EXPLANATION",
            "SUMMARY",
            "INFORMATION",
        }
        provider_kw = [
            "HOSPITAL",
            "MEDICAL",
            "HEALTH",
            "CLINIC",
            "CENTER",
            "CARE",
            "PHYSICIAN",
            "SURGERY",
            "ONCOLOGY",
            "CARDIOLOGY",
        ]

        lines = [l.strip() for l in text.split("\n") if l.strip()]
        for line in lines[:15]:
            if len(line) < 5 or line.startswith("$"):
                continue
            clean = line
            for suffix in [
                r"\s+Bill\s+Date.*",
                r"\s+Phone.*",
                r"\s+Fax.*",
                r"\s+\d{2}/\d{2}/\d{4}.*",
            ]:
                clean = re.split(suffix, clean, flags=re.IGNORECASE)[0].strip()
            if clean != clean.upper():
                continue
            if any(w in clean for w in title_skip):
                continue
            if any(w in clean for w in provider_kw):
                return clean[:80]

        visit_match = re.search(
            r"(?:Office|Lab|Urgent Care|ER|Emergency)\s+Visit\s+to\s+([^\n]{5,60})",
            text,
            re.IGNORECASE,
        )
        if visit_match:
            return visit_match.group(1).strip()[:80]

        skip_re = re.compile(
            r"^(office\s+visit|lab\s+visit|date|svc|\d{1,2}/\d{1,2})", re.IGNORECASE
        )
        for line in lines[:20]:
            if len(line) > 10 and ":" not in line and not line.startswith("$"):
                if skip_re.match(line):
                    continue
                if re.search(r"\$[\d,]+\.\d{2}", line):
                    continue
                if any(w in line.upper() for w in provider_kw):
                    return line[:80]
        return None

    def _find_date(self, kvs: dict, text: str) -> str | None:
        date_keys = [
            "date of service",
            "service date",
            "dos",
            "date(s) of service",
            "dates of service",
        ]
        for k in date_keys:
            if k in kvs and kvs[k]:
                return kvs[k]
        explicit = [
            r"Date\s*(?:of\s*Service|s\s*of\s*Service)[:\s]+([\w]+ \d{1,2},?\s*\d{4})",
            r"Date\s*(?:of\s*Service|s\s*of\s*Service)[:\s]+(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})",
            r"Service\s+Date[:\s]+(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})",
            r"\bDOS[:\s]+(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})",
        ]
        for pattern in explicit:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(1).strip()
        skip = re.compile(
            r"bill\s+date|date\s+of\s+birth|\bdob\b|service\s+period|"
            r"\bbirth\b|account|period|through|thru|age\s+\d+|"
            r"\b(19[5-9]\d|200\d|201\d)\b",
            re.IGNORECASE,
        )
        months = (
            r"January|February|March|April|May|June|July|August|"
            r"September|October|November|December"
        )
        for line in text.split("\n"):
            if skip.search(line):
                continue
            m = re.search(r"\b(\d{2}/\d{2}/\d{4})\b", line)
            if m:
                return m.group(1)
            m = re.search(
                rf"\b({months})\s+\d{{1,2}},?\s*\d{{4}}\b",
                line,
                re.IGNORECASE,
            )
            if m:
                return m.group(0).strip()
        return None

    def _find_total(self, kvs: dict, text: str) -> float | None:
        total_keys = [
            "total charges",
            "total billed",
            "total amount",
            "amount due",
            "balance due",
            "total",
        ]
        for k in total_keys:
            if k in kvs and kvs[k]:
                val = self._parse_amount(kvs[k])
                if val and val > 0:
                    return val
        patterns = [
            r"Total\s+Charges[:\s]+\$?([\d,]+\.\d{2})",
            r"Total\s+Billed[:\s]+\$?([\d,]+\.\d{2})",
            r"Total\s+Amount[:\s]+\$?([\d,]+\.\d{2})",
            r"Amount\s+Due[:\s]+\$?([\d,]+\.\d{2})",
            r"Balance\s+Due[:\s]+\$?([\d,]+\.\d{2})",
        ]
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                val = self._parse_amount(match.group(1))
                if val and val > 0:
                    return val
        return None

    # ── Line item extraction ───────────────────────────────────────

    def _extract_line_items_from_tables(self, tables: list, source: str) -> list:
        """
        Extract line items from Textract TABLE blocks.
        EOB: use first dollar amount (Billed column).
        Bill: use last dollar amount (Amount column, after Rate column).
        """
        line_items = []
        line_number = 1
        seen = set()

        for table in tables:
            if not table:
                continue
            if not self._is_service_table(table):
                continue

            rows = table[1:] if self._is_header_row(table[0]) else table

            for row in rows:
                if not row:
                    continue

                cells = [str(c or "").strip() for c in row]

                # CPT code — 5-digit number
                cpt_code = None
                for cell in cells:
                    if re.match(r"^\d{5}$", cell):
                        cpt_code = cell
                        break
                if not cpt_code:
                    continue

                # Collect all positive dollar amounts in the row
                all_amounts = []
                for cell in cells:
                    m = re.search(r"\$?([\d,]+\.\d{2})", cell)
                    if m:
                        val = self._parse_amount(m.group(1))
                        if val and val > 0:
                            all_amounts.append(val)

                # FIX: EOB uses first amount (Billed col)
                #      Bill uses last amount (Amount col after Rate col)
                if source == "eob":
                    amount = all_amounts[0] if all_amounts else 0.0
                else:
                    amount = all_amounts[-1] if all_amounts else 0.0

                # Date
                date = None
                for cell in cells:
                    dm = re.search(r"\b(\d{1,2}/\d{1,2}/\d{2,4})\b", cell)
                    if dm:
                        date = self._normalise_date(dm.group(1))
                        break

                # Quantity
                quantity = 1
                for cell in cells:
                    if re.match(r"^\d{1,2}$", cell) and cell not in ("", "0"):
                        try:
                            q = int(cell)
                            if 1 <= q <= 99:
                                quantity = q
                                break
                        except ValueError:
                            pass

                # Network status (EOB only)
                network_status = "in-network"
                for cell in cells:
                    if cell.upper() in ("OON", "OUT-OF-NETWORK", "NON-PARTICIPATING"):
                        network_status = "out-of-network"
                        break

                key = (cpt_code, date or "nodate")
                if key in seen:
                    continue
                seen.add(key)

                item = {
                    "line_number": line_number,
                    "cpt_code": cpt_code,
                    "description": "",
                    "quantity": quantity,
                    "amount": amount,
                    "date": date,
                    "confidence": self._estimate_confidence(cpt_code, amount),
                    "source": source,
                }
                if source == "eob":
                    item["network_status"] = network_status

                line_items.append(item)
                line_number += 1

        return line_items

    def _extract_line_items_from_text(self, text: str, source: str) -> list:
        """
        Fallback text extraction for bills with no table structure.
        EOB: use first amount (Billed col).
        Bill: use last amount (Amount col).
        """
        line_items = []
        line_number = 1
        seen = set()

        for line in text.split("\n"):
            line = line.strip()
            if not line:
                continue
            if re.search(
                r"insurance|adjustment|payment|contractual|\b2000\b|\b3000\b",
                line,
                re.IGNORECASE,
            ):
                continue

            cpt_match = re.search(r"\b(\d{5})\b", line)
            if not cpt_match:
                continue
            cpt_code = cpt_match.group(1)

            # Collect positive dollar amounts
            positive = []
            for m in re.finditer(r"\$?([\d,]+\.\d{2})", line):
                idx = m.start()
                if idx > 0 and line[idx - 1] == "-":
                    continue
                val = self._parse_amount(m.group(1))
                if val and val > 0:
                    positive.append(val)

            # FIX: EOB uses first amount, bill uses last amount
            if source == "eob":
                amount = positive[0] if positive else 0.0
            else:
                amount = positive[-1] if positive else 0.0

            date = None
            dm = re.search(r"\b(\d{1,2}/\d{1,2}/\d{2,4})\b", line)
            if dm:
                date = self._normalise_date(dm.group(1))

            key = (cpt_code, date or "nodate")
            if key in seen:
                continue
            seen.add(key)

            item = {
                "line_number": line_number,
                "cpt_code": cpt_code,
                "description": "",
                "quantity": 1,
                "amount": amount,
                "date": date,
                "confidence": self._estimate_confidence(cpt_code, amount),
                "source": source,
            }
            if source == "eob":
                network = "out-of-network" if "OON" in line.upper() else "in-network"
                item["network_status"] = network

            line_items.append(item)
            line_number += 1

        return line_items

    # ── Helpers ────────────────────────────────────────────────────

    def _is_service_table(self, table: list) -> bool:
        if not table or not table[0]:
            return False
        header = " ".join(str(c or "").lower() for c in table[0])
        has_cpt = any(w in header for w in ["cpt", "code", "procedure"])
        has_amount = any(w in header for w in ["amount", "charge", "billed", "bill"])
        has_date = any(w in header for w in ["date", "svc dt", "svc", "dos"])
        return has_cpt and (has_amount or has_date)

    def _is_header_row(self, row: list) -> bool:
        if not row:
            return False
        text = " ".join(str(c or "").lower() for c in row)
        return any(
            w in text
            for w in [
                "date",
                "service",
                "cpt",
                "code",
                "description",
                "amount",
                "charge",
                "units",
                "rate",
                "billed",
            ]
        )

    def _normalise_date(self, date_str: str) -> str:
        parts = date_str.split("/")
        if len(parts) == 3 and len(parts[2]) == 2:
            yr = int(parts[2])
            parts[2] = str(2000 + yr) if yr <= 50 else str(1900 + yr)
            return "/".join(parts)
        return date_str

    def _parse_amount(self, value: str | None) -> float | None:
        if not value:
            return None
        cleaned = re.sub(r"[^\d.]", "", str(value))
        try:
            return float(cleaned) if cleaned else None
        except ValueError:
            return None

    def _estimate_confidence(self, cpt_code, amount) -> float:
        if cpt_code and amount and amount > 0:
            return 0.95
        if cpt_code:
            return 0.80
        return 0.50
