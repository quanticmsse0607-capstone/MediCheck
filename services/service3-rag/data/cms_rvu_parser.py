"""
cms_rvu_parser.py
CMS Physician Fee Schedule RVU File Parser

Parses the CMS PPRRVU fixed-width file into a clean CSV saved to
data/processed/. The processed file contains only the fields needed
for MediCheck's rate outlier detection module.

File layout source: RVU26B.pdf (CMS documentation, April 2026 release)
Verified against: PPRRVU2026_Apr_nonQPP.txt

To update for a new CMS release (e.g. RVU26C in July):
    1. Download the new PPRRVU file from cms.gov
    2. Place it in services/rag-service/data/raw/
    3. Run this script pointing at the new file
    4. The processed CSV will be regenerated automatically

IMPORTANT — AMA Copyright Compliance:
    CPT code descriptions (positions 7-57) are copyright 2026 American
    Medical Association. All rights reserved.
    The description field is read temporarily to skip the column during
    parsing. It is NEVER written to disk, logged, included in any API
    response, or passed to any downstream system.

Usage:
    python cms_rvu_parser.py
        --input  data/raw/PPRRVU2026_Apr_nonQPP.txt
        --output data/processed/medicare_rates.csv

    Or import and call directly:
        from data.cms_rvu_parser import parse_rvu_file
        df = parse_rvu_file("data/raw/PPRRVU2026_Apr_nonQPP.txt")
"""

import argparse
import logging
import sys
from pathlib import Path

import pandas as pd

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)s  %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

# ── Column layout ─────────────────────────────────────────────────────────────
# Verified against RVU26B.pdf and a live status-A record.
# Positions are 0-based (Python slice notation).
# The description field (7:57) is parsed but immediately discarded.

_COLS = [
    ("hcpcs_code",           0,   5),
    ("modifier",             5,   7),
    # Description 7:57 — AMA copyright, never stored
    ("status_code",         57,  58),
    ("work_rvu",            59,  65),
    ("non_facility_pe_rvu", 66,  72),
    ("facility_pe_rvu",     75,  81),
    ("malpractice_rvu",     84,  89),
    ("total_non_facility",  90,  96),
    ("total_facility",      96, 102),
    ("conversion_factor",  132, 140),
]

# Only status codes A, R, T have valid RVUs for Medicare payment
# Source: Attachment A, RVU26B.pdf
_PAYABLE = {"A", "R", "T"}


def parse_rvu_file(input_path: str | Path) -> pd.DataFrame:
    """
    Parse a CMS PPRRVU fixed-width file.

    Skips HDR header records, filters to payable status codes (A/R/T),
    converts RVU fields to float (treating NA as 0.0), and computes
    Medicare non-facility and facility rates in USD.

    Returns a DataFrame with columns:
        hcpcs_code, modifier, status_code,
        work_rvu, non_facility_pe_rvu, facility_pe_rvu,
        malpractice_rvu, total_non_facility, total_facility,
        conversion_factor, rate_non_facility, rate_facility
    """
    input_path = Path(input_path)
    if not input_path.exists():
        raise FileNotFoundError(f"Input file not found: {input_path}")

    logger.info(f"Reading: {input_path.name}")

    rows = []
    header_lines = 0
    short_lines = 0

    with open(input_path, encoding="latin-1") as f:
        for line in f:
            line = line.rstrip("\r\n")

            # Skip HDR header records (copyright notice at top of file)
            if line.startswith("HDR"):
                header_lines += 1
                continue

            # Skip lines too short to contain all required fields
            if len(line) < 140:
                short_lines += 1
                continue

            # Filter to payable status codes only — skip before extracting
            status = line[57:58].strip()
            if status not in _PAYABLE:
                continue

            # Extract all columns — description deliberately omitted
            row = {
                name: line[start:end].strip()
                for name, start, end in _COLS
            }
            rows.append(row)

    logger.info(
        f"Skipped {header_lines} HDR lines, "
        f"{short_lines} short lines. "
        f"Retained {len(rows):,} payable records."
    )

    if not rows:
        raise ValueError(
            "No payable records found. "
            "Verify the file is a valid CMS PPRRVU fixed-width file."
        )

    df = pd.DataFrame(rows)

    # ── Convert RVU and rate fields to float ──────────────────────────────────
    # CMS uses "NA" in facility/non-facility fields for codes that are
    # never performed in that setting. Treat as 0.0.
    numeric_cols = [
        "work_rvu",
        "non_facility_pe_rvu",
        "facility_pe_rvu",
        "malpractice_rvu",
        "total_non_facility",
        "total_facility",
        "conversion_factor",
    ]
    for col in numeric_cols:
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0.0)

    # ── Compute Medicare rates in USD ─────────────────────────────────────────
    # Formula per RVU26B.pdf:
    # Non-Facility Rate = Total Non-Facility RVUs x Conversion Factor
    # Facility Rate     = Total Facility RVUs     x Conversion Factor
    df["rate_non_facility"] = (
        df["total_non_facility"] * df["conversion_factor"]
    ).round(2)

    df["rate_facility"] = (
        df["total_facility"] * df["conversion_factor"]
    ).round(2)

    # ── Final column order ────────────────────────────────────────────────────
    df = df[[
        "hcpcs_code",
        "modifier",
        "status_code",
        "work_rvu",
        "non_facility_pe_rvu",
        "facility_pe_rvu",
        "malpractice_rvu",
        "total_non_facility",
        "total_facility",
        "conversion_factor",
        "rate_non_facility",
        "rate_facility",
    ]]

    logger.info(
        f"Parsed {len(df):,} records. "
        f"Non-facility rates range: "
        f"${df['rate_non_facility'].min():.2f} – "
        f"${df['rate_non_facility'].max():.2f}"
    )

    return df


def save_processed(df: pd.DataFrame, output_path: str | Path) -> None:
    """Save the processed DataFrame to CSV."""
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(output_path, index=False)
    logger.info(f"Saved {len(df):,} records to: {output_path}")


def get_medicare_rate(
    df: pd.DataFrame,
    cpt_code: str,
    setting: str = "non_facility",
    modifier: str = "",
) -> float | None:
    """
    Look up the Medicare rate for a CPT code from the processed DataFrame.

    Args:
        df:         Processed DataFrame from parse_rvu_file()
        cpt_code:   Five-character HCPCS/CPT code e.g. "99213"
        setting:    "non_facility" (default) or "facility"
        modifier:   Optional modifier e.g. "26" or "TC". Defaults to global.

    Returns:
        Rate in USD, or None if the code is not found.
    """
    mask = (
        (df["hcpcs_code"] == cpt_code.strip().upper()) &
        (df["modifier"] == modifier.strip().upper())
    )
    matches = df[mask]

    if matches.empty:
        return None

    rate_col = "rate_non_facility" if setting == "non_facility" else "rate_facility"
    return float(matches.iloc[0][rate_col])


# ── CLI entrypoint ────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Parse CMS PPRRVU file and save processed CSV."
    )
    parser.add_argument(
        "--input",
        default="data/raw/PPRRVU2026_Apr_nonQPP.txt",
        help="Path to raw PPRRVU .txt file",
    )
    parser.add_argument(
        "--output",
        default="data/processed/medicare_rates.csv",
        help="Path for processed CSV output",
    )
    args = parser.parse_args()

    try:
        df = parse_rvu_file(args.input)
        save_processed(df, args.output)
        print(f"\nDone. {len(df):,} payable records saved to {args.output}")
    except (FileNotFoundError, ValueError) as e:
        logger.error(str(e))
        sys.exit(1)


if __name__ == "__main__":
    main()
