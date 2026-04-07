"""
cms_gpci_parser.py
CMS Geographic Practice Cost Index (GPCI) File Parser

Parses the CMS GPCI CSV file and computes locality-adjusted Medicare
rates by combining GPCI values with the national RVU data from
cms_rvu_parser.py.

File layout source: GPCI2026.csv (CMS, April 2026 release)
Three header rows, footer notes starting after data rows — both skipped.

The locality-adjusted payment formula per RVU26B.pdf:

    Non-Facility Rate =
        [(Work RVU * Work GPCI) +
         (Non-Facility PE RVU * PE GPCI) +
         (MP RVU * MP GPCI)] * Conversion Factor

    Facility Rate =
        [(Work RVU * Work GPCI) +
         (Facility PE RVU * PE GPCI) +
         (MP RVU * MP GPCI)] * Conversion Factor

Note on Work GPCI:
    The file contains two work GPCI columns — with and without the 1.0
    floor. The 1.0 floor was extended through January 31, 2026 per
    Section 6207 of H.R.5371. The "with floor" column is used here as
    it reflects actual 2026 payment amounts.

Usage:
    from data.cms_gpci_parser import load_gpci_file, compute_locality_rates

    gpci_df = load_gpci_file("data/raw/GPCI2026.csv")
    rates_df = compute_locality_rates(rvu_df, gpci_df, state="SC")
    rates_df.to_csv("data/processed/medicare_rates_sc.csv", index=False)

    Or use the CLI:
        python data/cms_gpci_parser.py
            --rvu   data/processed/medicare_rates.csv
            --gpci  data/raw/GPCI2026.csv
            --state SC
            --output data/processed/medicare_rates_locality.csv
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

# Column names after skipping the 3 header rows
_GPCI_COLUMNS = [
    "mac",
    "state",
    "locality_number",
    "locality_name",
    "work_gpci_no_floor",
    "work_gpci",       # with 1.0 floor — used for 2026 payments
    "pe_gpci",
    "mp_gpci",
]


def load_gpci_file(filepath: str | Path) -> pd.DataFrame:
    """
    Parse the CMS GPCI CSV file into a clean DataFrame.

    Skips 3 header rows and trailing footer notes.
    Returns one row per Medicare locality.

    Args:
        filepath: Path to GPCI2026.csv

    Returns:
        DataFrame with columns:
            mac, state, locality_number, locality_name,
            work_gpci_no_floor, work_gpci, pe_gpci, mp_gpci
    """
    filepath = Path(filepath)
    if not filepath.exists():
        raise FileNotFoundError(f"GPCI file not found: {filepath}")

    logger.info(f"Reading: {filepath.name}")

    # Read with 3 header rows skipped, no footer parsing
    df = pd.read_csv(
        filepath,
        skiprows=3,         # skip title row, blank row, column header row
        header=None,
        names=_GPCI_COLUMNS,
        dtype=str,
    )

    # Drop footer rows — these start with note text or are blank
    # A valid data row always has a numeric MAC in column 0
    df = df[pd.to_numeric(df["mac"], errors="coerce").notna()].copy()

    # Convert GPCI values to float
    for col in ["work_gpci_no_floor", "work_gpci", "pe_gpci", "mp_gpci"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    # Clean string fields
    df["state"] = df["state"].str.strip().str.upper()
    df["locality_number"] = df["locality_number"].str.strip().str.zfill(2)
    df["locality_name"] = df["locality_name"].str.strip()

    logger.info(f"Loaded {len(df)} localities across {df['state'].nunique()} states")

    return df


def compute_locality_rates(
    rvu_df: pd.DataFrame,
    gpci_df: pd.DataFrame,
    state: str = "SC",
    locality_number: str | None = None,
) -> pd.DataFrame:
    """
    Compute locality-adjusted Medicare rates for a given state/locality.

    Applies the full CMS payment formula:
        Non-Facility Rate =
            [(Work RVU * Work GPCI) +
             (Non-Facility PE RVU * PE GPCI) +
             (MP RVU * MP GPCI)] * Conversion Factor

    Args:
        rvu_df:          DataFrame from cms_rvu_parser.parse_rvu_file()
        gpci_df:         DataFrame from load_gpci_file()
        state:           Two-letter state code e.g. "SC"
        locality_number: Optional specific locality e.g. "01".
                         If None, uses the first locality found for the state.

    Returns:
        rvu_df with additional columns:
            locality_name, work_gpci, pe_gpci, mp_gpci,
            rate_non_facility_adj, rate_facility_adj
    """
    state = state.strip().upper()

    # Filter GPCI to the requested state/locality
    state_gpci = gpci_df[gpci_df["state"] == state]

    if state_gpci.empty:
        raise ValueError(f"No GPCI data found for state: {state}")

    if locality_number:
        locality_gpci = state_gpci[
            state_gpci["locality_number"] == locality_number.zfill(2)
        ]
        if locality_gpci.empty:
            raise ValueError(
                f"No GPCI data found for state {state}, "
                f"locality {locality_number}"
            )
    else:
        locality_gpci = state_gpci

    if len(locality_gpci) > 1:
        logger.info(
            f"Multiple localities found for {state} — "
            f"using first: {locality_gpci.iloc[0]['locality_name']}"
        )

    gpci_row = locality_gpci.iloc[0]
    work_gpci = gpci_row["work_gpci"]
    pe_gpci   = gpci_row["pe_gpci"]
    mp_gpci   = gpci_row["mp_gpci"]
    locality  = gpci_row["locality_name"]

    logger.info(
        f"Applying GPCIs for {locality} ({state}): "
        f"Work={work_gpci}, PE={pe_gpci}, MP={mp_gpci}"
    )

    df = rvu_df.copy()

    # Locality-adjusted non-facility rate
    df["rate_non_facility_adj"] = (
        (df["work_rvu"]            * work_gpci) +
        (df["non_facility_pe_rvu"] * pe_gpci)   +
        (df["malpractice_rvu"]     * mp_gpci)
    ) * df["conversion_factor"]
    df["rate_non_facility_adj"] = df["rate_non_facility_adj"].round(2)

    # Locality-adjusted facility rate
    df["rate_facility_adj"] = (
        (df["work_rvu"]        * work_gpci) +
        (df["facility_pe_rvu"] * pe_gpci)   +
        (df["malpractice_rvu"] * mp_gpci)
    ) * df["conversion_factor"]
    df["rate_facility_adj"] = df["rate_facility_adj"].round(2)

    # Tag with locality info
    df["locality_name"] = locality
    df["work_gpci"]     = work_gpci
    df["pe_gpci"]       = pe_gpci
    df["mp_gpci"]       = mp_gpci

    return df


def get_locality_rate(
    df: pd.DataFrame,
    cpt_code: str,
    setting: str = "non_facility",
    modifier: str = "",
) -> float | None:
    """
    Look up a locality-adjusted Medicare rate for a CPT code.

    Args:
        df:       DataFrame from compute_locality_rates()
        cpt_code: Five-character HCPCS/CPT code e.g. "99213"
        setting:  "non_facility" (default) or "facility"
        modifier: Optional modifier e.g. "26" or "TC"

    Returns:
        Locality-adjusted rate in USD, or None if not found.
    """
    mask = (
        (df["hcpcs_code"] == cpt_code.strip().upper()) &
        (df["modifier"].fillna("") == modifier.strip().upper())
    )
    matches = df[mask]
    if matches.empty:
        return None

    col = "rate_non_facility_adj" if setting == "non_facility" else "rate_facility_adj"
    return float(matches.iloc[0][col])


# ── CLI entrypoint ────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description=(
            "Compute locality-adjusted Medicare rates by combining "
            "the processed RVU file with GPCI values."
        )
    )
    parser.add_argument(
        "--rvu",
        default="data/processed/medicare_rates.csv",
        help="Path to processed RVU CSV from cms_rvu_parser.py",
    )
    parser.add_argument(
        "--gpci",
        default="data/raw/GPCI2026.csv",
        help="Path to raw GPCI CSV file",
    )
    parser.add_argument(
        "--state",
        default="SC",
        help="Two-letter state code e.g. SC, NC (default: SC)",
    )
    parser.add_argument(
        "--locality",
        default=None,
        help="Optional locality number e.g. 01 (default: first locality for state)",
    )
    parser.add_argument(
        "--output",
        default="data/processed/medicare_rates_locality.csv",
        help="Path for locality-adjusted output CSV",
    )
    args = parser.parse_args()

    try:
        rvu_df  = pd.read_csv(args.rvu)
        gpci_df = load_gpci_file(args.gpci)

        result = compute_locality_rates(
            rvu_df, gpci_df,
            state=args.state,
            locality_number=args.locality,
        )

        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        result.to_csv(output_path, index=False)

        logger.info(f"Saved {len(result):,} records to: {output_path}")
        print(f"\nDone. {len(result):,} locality-adjusted records saved to {output_path}")

    except (FileNotFoundError, ValueError) as e:
        logger.error(str(e))
        sys.exit(1)


if __name__ == "__main__":
    main()
