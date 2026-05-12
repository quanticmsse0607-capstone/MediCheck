"""
OCR service — local PDF extraction using pdfplumber.

Replaces AWS Textract with a free, local alternative.
No API key or cloud account required.

Fixes:
  1. Provider name — skips document titles, finds hospital name correctly
  2. Date — skips Bill Date/Service Period, uses first service date
  3. Duplicate line items — text fallback only runs when tables produce nothing
  4. Amounts — uses last dollar amount in row (Amount col, not Rate col)
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

            result["patient_name"] = self._extract_patient_name(full_text, all_tables)
            result["provider_name"] = self._extract_provider_name(full_text, all_tables)
            result["date_of_service"] = self._extract_date(full_text, all_tables)
            result["total_billed"] = self._extract_total(full_text)

            # Only run text fallback if tables produced no line items
            line_items = self._extract_line_items_from_tables(all_tables, source)
            if not line_items:
                line_items = self._extract_line_items_from_text(full_text, source)
            result["line_items"] = line_items

        return result

    # ── Patient name ───────────────────────────────────────────────────────────

    def _extract_patient_name(self, text: str, tables: list) -> str | None:
        # First try labelled fields in tables (most reliable)
        for table in tables:
            for row in table:
                cells = [str(c or "").strip() for c in row]
                for i, cell in enumerate(cells):
                    if re.match(r"patient\s*name[:\s]*$", cell, re.IGNORECASE):
                        if i + 1 < len(cells) and cells[i + 1]:
                            # Take first 3 words only
                            words = cells[i + 1].split()[:3]
                            return " ".join(words)
                    if re.match(r"member\s*name[:\s]*$", cell, re.IGNORECASE):
                        if i + 1 < len(cells) and cells[i + 1]:
                            words = cells[i + 1].split()[:3]
                            return " ".join(words)

        # Fallback — text pattern
        patterns = [
            r"Patient\s+Name[:\s]+([A-Z][a-zA-Z]+(?:\s+[A-Z][a-zA-Z]+){1,3})",
            r"Member\s+Name[:\s]+([A-Z][a-zA-Z]+(?:\s+[A-Z][a-zA-Z]+){1,3})",
        ]
        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                words = match.group(1).strip().split()[:3]
                return " ".join(words)
        return None

    # ── Provider name ──────────────────────────────────────────────────────────

    def _extract_provider_name(self, text: str, tables: list) -> str | None:
        """
        Provider name appears as a standalone all-caps line near the top
        e.g. METROPOLITAN HOSPITAL CENTER — not after a 'Provider:' label.
        Skip generic document titles like 'HOSPITAL SERVICES BILL'.
        """
        # Words that indicate a document title, not a provider name
        title_skip_words = [
            "BILL",
            "INVOICE",
            "STATEMENT",
            "SERVICES BILL",
            "EXPLANATION",
            "SUMMARY",
            "INFORMATION",
            "NOTICE",
            "RECEIPT",
            "RECORD",
        ]
        # Words that indicate a real provider name
        provider_keywords = [
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
            "ORTHOPEDIC",
        ]

        lines = [l.strip() for l in text.split("\n") if l.strip()]

        # First pass — all-caps line with provider keyword, no title words
        # Strip trailing date/phone/label that may appear on same line
        for line in lines[:15]:
            if len(line) < 5 or line.startswith("$"):
                continue
            # Strip common suffixes before evaluating
            clean_line = line
            for suffix in [
                r"\s+Bill\s+Date.*",
                r"\s+Phone.*",
                r"\s+Fax.*",
                r"\s+Tel.*",
                r"\s+\d{3}[\s.-]\d{3}.*",
                r"\s+\d{2}/\d{2}/\d{4}.*",
            ]:
                import re as _re

                clean_line = _re.split(suffix, clean_line, flags=_re.IGNORECASE)[0]
            clean_line = clean_line.strip()
            if clean_line != clean_line.upper():
                continue
            if any(w in clean_line for w in title_skip_words):
                continue
            if any(w in clean_line for w in provider_keywords):
                return clean_line[:80]

        # Second pass — mixed case with provider keyword, no colon
        for line in lines[:20]:
            if len(line) > 10 and ":" not in line and not line.startswith("$"):
                if any(w in line.upper() for w in provider_keywords):
                    if not any(w in line.upper() for w in title_skip_words):
                        return line[:80]

        # Third pass — labelled field
        patterns = [
            r"(?:Provider|Facility|Hospital)[:\s]+([A-Z][^\n]{5,60})",
            r"(?:From|Billed\s+by)[:\s]+([A-Z][^\n]{5,60})",
        ]
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(1).strip()[:80]

        return None

    # ── Date of service ────────────────────────────────────────────────────────

    def _extract_date(self, text: str, tables: list) -> str | None:
        """
        Use first service date from the service table.
        Skip: Bill Date, Service Period, Date of Birth, Account dates.
        """
        # Explicit label patterns first
        explicit_patterns = [
            r"Date\s+of\s+Service[:\s]+(\d{1,2}[/-]\d{1,2}[/-]\d{4})",
            r"Service\s+Date[:\s]+(\d{1,2}[/-]\d{1,2}[/-]\d{4})",
            r"\bDOS[:\s]+(\d{1,2}[/-]\d{1,2}[/-]\d{4})",
        ]
        for pattern in explicit_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(1).strip()

        # Fallback — first date not on a skip line
        skip_pattern = re.compile(
            r"bill\s+date|date\s+of\s+birth|\bdob\b|service\s+period|"
            r"\bbirth\b|account|period|through|thru|-\s+\d{2}/\d{2}/\d{4}",
            re.IGNORECASE,
        )
        for line in text.split("\n"):
            if skip_pattern.search(line):
                continue
            date_match = re.search(r"\b(\d{2}/\d{2}/\d{4})\b", line)
            if date_match:
                return date_match.group(1)

        return None

    # ── Total billed ───────────────────────────────────────────────────────────

    def _extract_total(self, text: str) -> float | None:
        patterns = [
            r"Total\s+Charges[:\s]+\$?([\d,]+\.\d{2})",
            r"Total\s+Billed[:\s]+\$?([\d,]+\.\d{2})",
            r"Total\s+Amount[:\s]+\$?([\d,]+\.\d{2})",
            r"Amount\s+Due[:\s]+\$?([\d,]+\.\d{2})",
        ]
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return self._parse_amount(match.group(1))
        return None

    # ── Line items from tables ─────────────────────────────────────────────────

    def _extract_line_items_from_tables(self, tables: list, source: str) -> list:
        """
        Extract line items from service charge tables only.
        Uses last dollar amount per row (Amount column, not Rate column).
        Deduplicates by CPT + date to prevent double extraction.
        """
        line_items = []
        line_number = 1
        seen_cpt_dates = set()

        for table in tables:
            if not table:
                continue
            if not self._is_service_table(table):
                continue

            # Skip header row
            rows = table[1:] if self._is_header_row(table[0]) else table

            for row in rows:
                if not row:
                    continue

                cells = [str(c or "").strip() for c in row]

                # Find CPT code — 5-digit number
                cpt_code = None
                for cell in cells:
                    if re.match(r"^\d{5}$", cell):
                        cpt_code = cell
                        break

                if not cpt_code:
                    continue

                # Use LAST dollar amount (Amount col comes after Rate col)
                all_amounts = []
                for cell in cells:
                    m = re.search(r"\$?([\d,]+\.\d{2})", cell)
                    if m:
                        parsed = self._parse_amount(m.group(1))
                        if parsed and parsed > 0:
                            all_amounts.append(parsed)
                amount = all_amounts[-1] if all_amounts else 0.0

                # Date
                date = None
                for cell in cells:
                    dm = re.search(r"\b(\d{1,2}/\d{1,2}/\d{4})\b", cell)
                    if dm:
                        date = dm.group(1)
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

                # Network status (for EOB)
                network_status = "in-network"
                for cell in cells:
                    if cell.upper() in ("OON", "OUT-OF-NETWORK", "NON-PARTICIPATING"):
                        network_status = "out-of-network"
                        break

                # Deduplicate
                dedup_key = (cpt_code, date or "nodate", source)
                if dedup_key in seen_cpt_dates:
                    continue
                seen_cpt_dates.add(dedup_key)

                item = {
                    "line_number": line_number,
                    "cpt_code": cpt_code,
                    "description": "",  # AMA copyright — never populated
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

    # ── Line items from text (fallback only) ───────────────────────────────────

    def _extract_line_items_from_text(self, text: str, source: str) -> list:
        """Only called when no tables produced line items."""
        line_items = []
        line_number = 1
        seen = set()

        for line in text.split("\n"):
            line = line.strip()
            if not line:
                continue

            cpt_match = re.search(r"\b(\d{5})\b", line)
            if not cpt_match:
                continue

            cpt_code = cpt_match.group(1)

            # Use last amount
            amounts = [
                self._parse_amount(m) for m in re.findall(r"\$?([\d,]+\.\d{2})", line)
            ]
            amounts = [a for a in amounts if a and a > 0]
            amount = amounts[-1] if amounts else 0.0

            date_match = re.search(r"\b(\d{1,2}/\d{1,2}/\d{4})\b", line)
            date = date_match.group(1) if date_match else None

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

    # ── Helpers ────────────────────────────────────────────────────────────────

    def _is_service_table(self, table: list) -> bool:
        """Only process tables that look like service charge tables."""
        if not table or not table[0]:
            return False
        header_text = " ".join(str(c or "").lower() for c in table[0])
        has_cpt = any(w in header_text for w in ["cpt", "code", "procedure"])
        has_amount = any(w in header_text for w in ["amount", "charge", "billed"])
        return has_cpt and has_amount

    def _is_header_row(self, row: list) -> bool:
        if not row:
            return False
        keywords = [
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
        row_text = " ".join(str(c or "").lower() for c in row)
        return any(kw in row_text for kw in keywords)

    def _parse_amount(self, value: str | None) -> float | None:
        if not value:
            return None
        cleaned = re.sub(r"[^\d.]", "", str(value))
        try:
            return float(cleaned) if cleaned else None
        except ValueError:
            return None

    def _estimate_confidence(self, cpt_code: str | None, amount: float | None) -> float:
        if cpt_code and amount and amount > 0:
            return 0.92
        if cpt_code:
            return 0.75
        return 0.50
