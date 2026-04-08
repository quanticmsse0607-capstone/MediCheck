# Service 3 — Data Directory

This directory contains all source data and processed outputs for the MediCheck
RAG & Letter Service. It is organised into three areas: parser scripts, raw source
files, and processed outputs.

---

## Directory Structure

```
data/
├── cms_rvu_parser.py       # Parses CMS PPRRVU fixed-width file → medicare_rates.csv
├── cms_gpci_parser.py      # Applies GPCI locality adjustments → medicare_rates_{state}.csv
├── raw/                    # Source files (committed to repo — see below)
│   ├── PPRRVU2026_Apr_nonQPP.txt           # CMS Physician Fee Schedule RVU file
│   ├── GPCI2026.csv                        # Geographic Practice Cost Index file
│   ├── RVU26B.pdf                          # CMS file layout documentation
│   ├── icd_10_cm_october_2025_guidelines_0.pdf
│   ├── nsa-at-a-glance.pdf
│   ├── nsa-helping-consumers.pdf
│   ├── nsa-keyprotections_1.pdf
│   └── surprise-billing-requirements-final-rules-fact-sheet.pdf
└── processed/              # Generated outputs (committed to repo)
    ├── medicare_rates.csv          # National unadjusted Medicare rates
    ├── medicare_rates_sc.csv       # South Carolina locality-adjusted rates
    └── medicare_rates_nc.csv       # North Carolina locality-adjusted rates
```

---

## CMS Rate Files

### Source documents

| File | Description | Source |
|---|---|---|
| `PPRRVU2026_Apr_nonQPP.txt` | CMS Physician Fee Schedule RVU file, April 2026 release, nonQPP version | [cms.gov/medicare/payment/fee-schedules/physician](https://www.cms.gov/medicare/payment/fee-schedules/physician) |
| `GPCI2026.csv` | Geographic Practice Cost Index file, April 2026 release | Same page as above, inside RVU26B.zip |
| `RVU26B.pdf` | File layout documentation for PPRRVU — defines column positions and status codes | Same page as above |

### What the PPRRVU file contains

The PPRRVU (Physician Practice Relative Value Units) file is a fixed-width text
file published quarterly by CMS. Each record represents one CPT/HCPCS procedure
code and contains:

- **HCPCS code** (positions 1–5) — the procedure code
- **Modifier** (positions 6–7) — e.g. 26 (professional component), TC (technical component)
- **Description** (positions 8–57) — **never stored — AMA copyright 2026**
- **Status code** (position 58) — whether the code is payable under Medicare
- **Work RVU** (positions 60–65) — physician work component
- **Non-Facility PE RVU** (positions 67–72) — practice expense, non-facility setting
- **Facility PE RVU** (positions 76–81) — practice expense, facility setting
- **Malpractice RVU** (positions 85–89) — malpractice expense component
- **Total Non-Facility RVUs** (positions 91–96) — sum of work + non-facility PE + MP
- **Total Facility RVUs** (positions 97–102) — sum of work + facility PE + MP
- **Conversion Factor** (positions 133–140) — dollar multiplier for 2026

The file contains approximately 19,000 records. Only records with status codes
`A` (Active), `R` (Restricted), or `T` (Injection) have valid RVUs for Medicare
payment. The parser filters to these 10,499 payable records.

> **AMA Copyright Notice:** CPT code descriptions are copyright 2026 American
> Medical Association. All rights reserved. The description field is read during
> parsing to advance the file pointer only. It is never stored, logged, written
> to disk, or included in any API response.

### What the GPCI file contains

The GPCI (Geographic Practice Cost Index) file maps each of the 109 CMS Medicare
payment localities to three geographic adjustment factors:

- **Work GPCI** — adjustment for physician work (with 1.0 floor applied for 2026)
- **PE GPCI** — adjustment for practice expense
- **MP GPCI** — adjustment for malpractice expense

South Carolina is a single locality (Locality 01). North Carolina is a single
locality (Locality 00).

### Rate calculation formula

The locality-adjusted Medicare payment amount is calculated per the formula
published in RVU26B.pdf:

```
Non-Facility Rate =
    [(Work RVU × Work GPCI) +
     (Non-Facility PE RVU × PE GPCI) +
     (Malpractice RVU × MP GPCI)]
    × Conversion Factor

Facility Rate =
    [(Work RVU × Work GPCI) +
     (Facility PE RVU × PE GPCI) +
     (Malpractice RVU × MP GPCI)]
    × Conversion Factor
```

**Note on Work GPCI floor:** Section 6207 of H.R.5371 extended the 1.0 work GPCI
floor through January 31, 2026. The GPCI file contains two work GPCI columns —
"with 1.0 floor" and "without 1.0 floor". The parser uses the "with floor" column
to reflect actual 2026 payment amounts.

### Verified sample rates (South Carolina, non-facility)

| CPT Code | Description | SC-Adjusted Rate | National Rate |
|---|---|---|---|
| 99213 | Office visit, established patient | $91.04 | $95.19 |
| 99215 | Office visit, high complexity | $184.36 | $192.39 |
| 29881 | Knee arthroscopy | $490.44 | $515.71 |

SC GPCIs: Work = 1.0, PE = 0.924, MP = 0.85

### Locality scope

The MVP covers South Carolina (demo scenarios A and B) and North Carolina
(demo scenario C). To add a new state, run `cms_gpci_parser.py` with the
appropriate `--state` flag — no code changes required.

---

## Parser Scripts

### `cms_rvu_parser.py`

Parses the PPRRVU fixed-width file into a clean CSV of national Medicare rates.

```bash
python data/cms_rvu_parser.py \
  --input data/raw/PPRRVU2026_Apr_nonQPP.txt \
  --output data/processed/medicare_rates.csv
```

**Key decisions:**
- Fixed-width parsing using verified column positions from RVU26B.pdf
- Filters to status codes A, R, T only — non-payable codes excluded
- Description field extracted then immediately discarded — AMA copyright compliance
- NA values in facility/non-facility fields treated as 0.0
- Both non-facility and facility rates computed in USD

### `cms_gpci_parser.py`

Applies GPCI locality adjustments to the national rates from `cms_rvu_parser.py`.

```bash
# South Carolina
python data/cms_gpci_parser.py \
  --rvu data/processed/medicare_rates.csv \
  --gpci data/raw/GPCI2026.csv \
  --state SC \
  --output data/processed/medicare_rates_sc.csv

# North Carolina
python data/cms_gpci_parser.py \
  --rvu data/processed/medicare_rates.csv \
  --gpci data/raw/GPCI2026.csv \
  --state NC \
  --output data/processed/medicare_rates_nc.csv
```

**Key decisions:**
- Uses "with 1.0 floor" work GPCI column per H.R.5371 extension
- Skips footer notes and header rows in GPCI CSV automatically
- State codes are case-insensitive
- Output includes both national and locality-adjusted rates for comparison

### Updating for new CMS quarterly releases

CMS publishes updated RVU files quarterly:

| Release | File prefix | Available |
|---|---|---|
| January 2026 | RVU26A | Current |
| April 2026 | RVU26B | Current (in use) |
| July 2026 | RVU26C | July 1, 2026 |
| October 2026 | RVU26D | October 1, 2026 |

To update: download the new PPRRVU file, place it in `data/raw/`, and re-run
both parsers with the updated filename. No code changes required unless CMS
changes the file layout — in that case update `_COLS` in `cms_rvu_parser.py`.

---

## RAG Knowledge Base Documents

These PDFs are committed to the repo and loaded by `ingest.py` to build the
ChromaDB vector store. They are the authoritative sources for MediCheck's
plain-language explanations and regulatory citations.

| File | Pages | Content | Detection module |
|---|---|---|---|
| `icd_10_cm_october_2025_guidelines_0.pdf` | 121 | ICD-10-CM official coding guidelines FY2026 | All modules |
| `nsa-at-a-glance.pdf` | 3 | No Surprises Act overview and key protections | Module 4 |
| `nsa-helping-consumers.pdf` | 11 | Action scenarios for NSA violations | Module 4 |
| `nsa-keyprotections_1.pdf` | 22 | Detailed consumer protections, cost sharing, emergency services | Module 4 |
| `surprise-billing-requirements-final-rules-fact-sheet.pdf` | 4 | Final rules — QPA disclosure and IDR process | Module 4 |

**Documents intentionally excluded:**

| File | Reason |
|---|---|
| `Requirements_Related_to_Surprise_Billing_Part1.pdf` | Image-based scanned PDF — no extractable text |
| `Requirements_Related_to_Surprise_Billing_Part2.pdf` | Image-based scanned PDF — no extractable text |
| NSA IDR process proposed rule | Outside MediCheck scope — IDR arbitration between providers and insurers |
| Prescription Drug interim final rule | Outside MediCheck scope — pharmacy claims not covered |

### Building the vector store

```bash
cd services/service3-rag
source venv/bin/activate   # Windows: venv\Scripts\activate

python ingest.py
```

Requires `OPENAI_API_KEY` in `.env`. Produces approximately 292 chunks embedded
with `text-embedding-3-small` and persisted to `data/chroma_db/`.

To rebuild from scratch:

```bash
python ingest.py --reset
```
