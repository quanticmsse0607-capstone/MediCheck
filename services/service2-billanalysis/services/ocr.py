"""
OCR service — local PDF extraction using pdfplumber + PyMuPDF.

Replaces AWS Textract with a free, local alternative.
No API key or cloud account required.

Extracts:
  - Key-value pairs (patient name, provider, date, total)
  - Table rows (line items with CPT codes, amounts, dates)
  - Confidence scores estimated from extraction quality

CPT code descriptions are NEVER populated — AMA copyright (agreed decision).
"""

import re
import io
import pdfplumber


class OCRService:

    def extract(self, file_bytes: bytes, source: str = "bill") -> dict:
        """
        Extract structured data from a PDF using pdfplumber.

        Args:
            file_bytes: Raw PDF bytes.
            source: 'bill' or 'eob' — tagged on every line item.

        Returns:
            dict with keys: patient_name, provider_name, date_of_service,
            total_billed, line_items (list of dicts).
        """
        result = {
            "patient_name": None,
            "provider_name": None,
            "date_of_service": None,
            "total_billed": None,
            "line_items": [],
        }

        with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
            full_text = ""
            all_tables = []

            for page in pdf.pages:
                text = page.extract_text() or ""
                full_text += text + "\n"
                tables = page.extract_tables() or []
                all_tables.extend(tables)

            result["patient_name"] = self._extract_patient_name(full_text)
            result["provider_name"] = self._extract_provider_name(full_text)
            result["date_of_service"] = self._extract_date(full_text)
            result["total_billed"] = self._extract_total(full_text)
            result["line_items"] = self._extract_line_items(all_tables, full_text, source)

        return result

    def _extract_patient_name(self, text: str) -> str | None:
        patterns = [
            r"Patient(?:\s+Name)?[:\s]+([A-Z][a-zA-Z]+(?:\s+[A-Z][a-zA-Z]+)+)",
            r"Member(?:\s+Name)?[:\s]+([A-Z][a-zA-Z]+(?:\s+[A-Z][a-zA-Z]+)+)",
            r"Name[:\s]+([A-Z][a-zA-Z]+(?:\s+[A-Z][a-zA-Z]+)+)",
        ]
        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                return match.group(1).strip()
        return None

    def _extract_provider_name(self, text: str) -> str | None:
        patterns = [
            r"(?:Provider|Facility|Hospital|Clinic|Center)[:\s]+([A-Z][^\n]{5,60})",
            r"(?:From|Billed by)[:\s]+([A-Z][^\n]{5,60})",
        ]
        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                return match.group(1).strip()
        lines = [l.strip() for l in text.split("\n") if l.strip()]
        for line in lines[:10]:
            if len(line) > 10 and line[0].isupper() and ":" not in line:
                if any(w in line.upper() for w in
                       ["HOSPITAL", "MEDICAL", "HEALTH", "CLINIC", "CENTER", "CARE"]):
                    return line
        return None

    def _extract_date(self, text: str) -> str | None:
        patterns = [
            r"(?:Date of Service|Service Date|DOS|Service Period)[:\s]+(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})",
            r"(?:Date of Service|Service Date|DOS)[:\s]+(\d{4}-\d{2}-\d{2})",
        ]
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(1).strip()
        date_match = re.search(r"\b(\d{1,2}/\d{1,2}/\d{4})\b", text)
        if date_match:
            return date_match.group(1)
        return None

    def _extract_total(self, text: str) -> float | None:
        patterns = [
            r"Total(?:\s+Charges?|\s+Billed|\s+Amount)?[:\s]+\$?([\d,]+\.\d{2})",
            r"Amount(?:\s+Due|\s+Billed)?[:\s]+\$?([\d,]+\.\d{2})",
            r"Balance(?:\s+Due)?[:\s]+\$?([\d,]+\.\d{2})",
        ]
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return self._parse_amount(match.group(1))
        return None

    def _extract_line_items(self, tables: list, full_text: str, source: str) -> list:
        line_items = []
        line_number = 1

        for table in tables:
            if not table:
                continue
            rows = table[1:] if self._is_header_row(table[0]) else table

            for row in rows:
                if not row:
                    continue
                cells = [str(cell or "").strip() for cell in row]
                cpt_code = None
                amount = None
                date = None
                quantity = 1
                network_status = None

                for cell in cells:
                    if re.match(r"^\d{5}$", cell):
                        cpt_code = cell
                    amount_match = re.search(r"\$?([\d,]+\.\d{2})", cell)
                    if amount_match and amount is None:
                        parsed = self._parse_amount(amount_match.group(1))
                        if parsed and parsed > 0:
                            amount = parsed
                    date_match = re.search(
                        r"\b(\d{1,2}/\d{1,2}/\d{4}|\d{4}-\d{2}-\d{2})\b", cell
                    )
                    if date_match and date is None:
                        date = date_match.group(1)
                    if re.match(r"^\d{1,2}$", cell) and cell not in ("", "0"):
                        try:
                            q = int(cell)
                            if 1 <= q <= 99:
                                quantity = q
                        except ValueError:
                            pass
                    if cell.upper() in ("IN", "OON", "OUT-OF-NETWORK",
                                        "IN-NETWORK", "NON-PARTICIPATING"):
                        network_status = cell.upper()

                if cpt_code:
                    item = {
                        "line_number": line_number,
                        "cpt_code": cpt_code,
                        "description": "",
                        "quantity": quantity,
                        "amount": amount or 0.0,
                        "date": date,
                        "confidence": self._estimate_confidence(cpt_code, amount),
                        "source": source,
                    }
                    if source == "eob":
                        item["network_status"] = network_status or "in-network"
                    line_items.append(item)
                    line_number += 1

        if not line_items:
            line_items = self._extract_from_text(full_text, source, line_number)

        return line_items

    def _extract_from_text(self, text: str, source: str, start_line: int = 1) -> list:
        line_items = []
        line_number = start_line

        for line in text.split("\n"):
            line = line.strip()
            if not line:
                continue
            cpt_match = re.search(r"\b(\d{5})\b", line)
            if not cpt_match:
                continue
            cpt_code = cpt_match.group(1)
            amounts = re.findall(r"\$?([\d,]+\.\d{2})", line)
            amount = self._parse_amount(amounts[-1]) if amounts else 0.0
            date_match = re.search(r"\b(\d{1,2}/\d{1,2}/\d{4})\b", line)
            date = date_match.group(1) if date_match else None

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

    def _is_header_row(self, row: list) -> bool:
        if not row:
            return False
        keywords = ["date", "service", "cpt", "code", "description",
                    "amount", "charge", "units", "rate", "billed"]
        row_text = " ".join(str(cell or "").lower() for cell in row)
        return any(kw in row_text for kw in keywords)

    def _parse_amount(self, value: str | None) -> float | None:
        if not value:
            return None
        cleaned = re.sub(r"[^\d.]", "", str(value))
        try:
            return float(cleaned)
        except ValueError:
            return None

    def _estimate_confidence(self, cpt_code: str | None, amount: float | None) -> float:
        if cpt_code and amount and amount > 0:
            return 0.92
        if cpt_code:
            return 0.75
        return 0.50