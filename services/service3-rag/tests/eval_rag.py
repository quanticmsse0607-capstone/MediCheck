"""
tests/eval_rag.py
RAG evaluation runner — Step 8, Sprint 5.

Sends each case from eval_set.json to POST /explain, records the response
and wall-clock latency, then runs LLM-as-judge groundedness scoring and
writes eval_results.csv for manual review of citation_accurate and notes.

Usage:
    # With Service 3 running locally on port 5002:
    python tests/eval_rag.py

    # Against a deployed Render service:
    python tests/eval_rag.py --url https://medicheck-rag.onrender.com

    # Skip LLM judge (raw responses only):
    python tests/eval_rag.py --no-judge

    # Re-run specific cases only (merges into existing CSV):
    python tests/eval_rag.py --cases eval_001,eval_002,eval_003

    # After filling citation_accurate manually, print all rubric metrics:
    python tests/eval_rag.py --summary

    # Change groundedness pass threshold (default 70):
    python tests/eval_rag.py --summary --threshold 80

Output:
    tests/eval_results.csv  — one row per case, groundedness_score auto-filled
    Prints p50/p95 latency, groundedness %, and citation accuracy % when complete.
"""

import argparse
import csv
import json
import os
import statistics
import time
from pathlib import Path

import requests
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")

EVAL_SET_PATH = Path(__file__).parent / "eval_set.json"
RESULTS_PATH = Path(__file__).parent / "eval_results.csv"
GROUNDEDNESS_THRESHOLD = 70  # scores >= this count as grounded for the % metric

CSV_HEADERS = [
    "case_id",
    "module",
    "description",
    "latency_ms",
    "status_code",
    "explanation",
    "citations",
    "groundedness_score",  # 0-100, auto-filled by LLM judge
    "judge_reason",  # LLM judge's one-sentence reasoning
    "citation_accurate",  # yes / no / partial — fill in manually
    "notes",  # manual
]

# LLM-as-judge prompt — evaluates whether the explanation's factual claims
# are grounded in what was provided, without fabricating extra facts.
JUDGE_PROMPT = """\
You are evaluating whether a medical billing explanation is factually grounded.

ERROR DESCRIPTION (the detected billing error passed to the system):
{description}

SYSTEM EXPLANATION (the RAG system's response to the patient):
{explanation}

Score the groundedness of this explanation from 0 to 100:
- 100: Every factual claim is consistent with the error description. No invented \
regulation names, dollar figures, or legal thresholds beyond what was provided.
- 50: Most claims are grounded but some are vague, imprecise, or mildly speculative.
- 0: The explanation fabricates specific facts not present in the input — e.g. invents \
statute names, cites wrong dollar amounts, or makes false legal claims.

Return ONLY a valid JSON object with no other text:
{{"score": <integer 0-100>, "reason": "<one sentence explaining the score>"}}"""


def load_eval_set() -> list[dict]:
    with open(EVAL_SET_PATH, encoding="utf-8") as f:
        data = json.load(f)
    return data["evaluation_cases"]


def run_case(case: dict, base_url: str) -> dict:
    url = f"{base_url.rstrip('/')}/explain"
    payload = case["payload"]

    start = time.perf_counter()
    try:
        response = requests.post(url, json=payload, timeout=30)
        elapsed_ms = (time.perf_counter() - start) * 1000
        status_code = response.status_code

        if status_code == 200:
            body = response.json()
            explanations = body.get("explanations", {})
            error_id = payload["errors"][0]["error_id"]
            result = explanations.get(error_id, {})
            explanation = result.get("explanation", "")
            citations = "; ".join(
                f"{c.get('source', '')} — {c.get('section', '')}"
                for c in result.get("citations", [])
            )
        else:
            explanation = f"ERROR: {response.text[:200]}"
            citations = ""

    except requests.Timeout:
        elapsed_ms = 30000
        status_code = 0
        explanation = "TIMEOUT"
        citations = ""
    except requests.ConnectionError as e:
        elapsed_ms = 0
        status_code = 0
        explanation = f"CONNECTION ERROR: {e}"
        citations = ""

    return {
        "case_id": case["case_id"],
        "module": case["module"],
        "description": case["description"],
        "latency_ms": round(elapsed_ms),
        "status_code": status_code,
        "explanation": explanation,
        "citations": citations,
        "groundedness_score": "",
        "judge_reason": "",
        "citation_accurate": "",
        "notes": "",
    }


def llm_judge_score(description: str, explanation: str, api_key: str) -> tuple:
    """Ask GPT-4o-mini to score groundedness 0-100. Returns (score, reason)."""
    from openai import OpenAI

    client = OpenAI(api_key=api_key)
    prompt = JUDGE_PROMPT.format(description=description, explanation=explanation)
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
            max_tokens=150,
        )
        raw = response.choices[0].message.content.strip()
        parsed = json.loads(raw)
        return int(parsed["score"]), parsed.get("reason", "")
    except Exception as exc:
        return "", f"Judge error: {exc}"


def run_judge_pass(cases: list[dict], results: list[dict], api_key: str) -> list[dict]:
    """Score all successful cases using LLM-as-judge."""
    print("\nRunning LLM-as-judge groundedness scoring...")
    for i, (case, result) in enumerate(zip(cases, results), 1):
        if result["status_code"] != 200 or not result["explanation"]:
            continue
        description = case["payload"]["errors"][0]["description"]
        print(f"  [{i:02d}/{len(cases)}] {result['case_id']}... ", end="", flush=True)
        score, reason = llm_judge_score(description, result["explanation"], api_key)
        result["groundedness_score"] = score
        result["judge_reason"] = reason
        print(f"{score}/100")
    return results


def compute_percentiles(latencies: list) -> tuple:
    sorted_l = sorted(latencies)
    n = len(sorted_l)
    p50_idx = int(n * 0.50)
    p95_idx = min(int(n * 0.95), n - 1)
    return sorted_l[p50_idx], sorted_l[p95_idx]


def compute_summary(threshold: int) -> None:
    """Read eval_results.csv and print the three rubric metrics."""
    if not RESULTS_PATH.exists():
        print(f"No results file found at {RESULTS_PATH}. Run without --summary first.")
        return

    with open(RESULTS_PATH, encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))

    if not rows:
        print("Results file is empty.")
        return

    total = len(rows)
    successful = [r for r in rows if r["status_code"] == "200"]

    latencies = [int(r["latency_ms"]) for r in successful if r["latency_ms"]]
    if latencies:
        p50, p95 = compute_percentiles(latencies)
        print(f"\nLatency ({len(latencies)} calls):")
        print(f"  p50 : {p50} ms")
        print(f"  p95 : {p95} ms")

    scored = [r for r in rows if r.get("groundedness_score", "").strip() not in ("",)]
    if scored:
        scores = [int(r["groundedness_score"]) for r in scored]
        grounded = [s for s in scores if s >= threshold]
        pct = len(grounded) / len(scored) * 100
        print(f"\nGroundedness (threshold ≥ {threshold}/100, {len(scored)} scored):")
        print(f"  Grounded   : {len(grounded)}/{len(scored)} = {pct:.0f}%")
        print(f"  Mean score : {statistics.mean(scores):.0f}/100")
    else:
        print(
            "\nGroundedness: no scores in CSV — run without --no-judge to generate them."
        )

    filled = [
        r
        for r in rows
        if r.get("citation_accurate", "").strip().lower() in ("yes", "no", "partial")
    ]
    if filled:
        accurate = [
            r
            for r in filled
            if r["citation_accurate"].strip().lower() in ("yes", "partial")
        ]
        pct = len(accurate) / len(filled) * 100
        print(f"\nCitation Accuracy ({len(filled)}/{total} rows filled):")
        print(f"  Accurate (yes/partial) : {len(accurate)}/{len(filled)} = {pct:.0f}%")
        if len(filled) < total:
            print(f"  ({total - len(filled)} rows still blank)")
    else:
        print(
            f"\nCitation Accuracy: not yet filled — open eval_results.csv and complete the citation_accurate column."
        )
        print(
            "  Values: yes = citation points to a directly relevant passage; partial = tangentially relevant; no = incorrect."
        )


def load_existing_results() -> dict:
    """Load existing CSV into a dict keyed by case_id, preserving row order."""
    if not RESULTS_PATH.exists():
        return {}
    with open(RESULTS_PATH, encoding="utf-8-sig") as f:
        return {row["case_id"]: row for row in csv.DictReader(f)}


def main(
    base_url: str, run_judge: bool, threshold: int, case_filter: set | None = None
) -> None:
    all_cases = load_eval_set()
    cases = [c for c in all_cases if case_filter is None or c["case_id"] in case_filter]

    if case_filter:
        print(f"Running {len(cases)} of {len(all_cases)} cases (filtered by --cases)")
    else:
        print(f"Loaded {len(cases)} evaluation cases from {EVAL_SET_PATH}")
    print(f"Target: {base_url}\n")

    results = []
    latencies = []

    for i, case in enumerate(cases, 1):
        print(
            f"[{i:02d}/{len(cases)}] {case['case_id']} ({case['module']})... ",
            end="",
            flush=True,
        )
        row = run_case(case, base_url)
        results.append(row)

        if row["status_code"] == 200:
            latencies.append(row["latency_ms"])
            print(f"{row['latency_ms']} ms — OK")
        else:
            print(f"FAILED (status={row['status_code']})")

    if run_judge:
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            print("\nWARNING: OPENAI_API_KEY not set — skipping judge scoring.")
        else:
            results = run_judge_pass(cases, results, api_key)

    # Merge new results into existing CSV rows, preserving untouched cases
    existing = load_existing_results()
    new_by_id = {r["case_id"]: r for r in results}
    existing.update(new_by_id)
    # Write in original eval set order
    ordered = [existing[c["case_id"]] for c in all_cases if c["case_id"] in existing]

    with open(RESULTS_PATH, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_HEADERS)
        writer.writeheader()
        writer.writerows(ordered)

    print(f"\nResults written to {RESULTS_PATH}")
    print(f"Successful calls: {len(latencies)}/{len(cases)}")

    if latencies:
        p50, p95 = compute_percentiles(latencies)
        mean = statistics.mean(latencies)
        print(f"\nLatency summary (ms):")
        print(f"  p50  : {p50:.0f} ms")
        print(f"  p95  : {p95:.0f} ms")
        print(f"  mean : {mean:.0f} ms")
        print(f"  min  : {min(latencies):.0f} ms")
        print(f"  max  : {max(latencies):.0f} ms")

    if run_judge:
        scored = [r for r in results if r["groundedness_score"] != ""]
        if scored:
            scores = [r["groundedness_score"] for r in scored]
            grounded = [s for s in scores if s >= threshold]
            pct = len(grounded) / len(scored) * 100
            print(f"\nGroundedness (threshold ≥ {threshold}/100):")
            print(f"  Grounded : {len(grounded)}/{len(scored)} = {pct:.0f}%")
            print(f"  Mean     : {statistics.mean(scores):.0f}")
            print(f"  Min      : {min(scores)}")
            print(f"  Max      : {max(scores)}")

    print(
        "\nNext: open eval_results.csv, fill in citation_accurate (yes/no/partial) and notes columns."
    )
    print("Then run:  python tests/eval_rag.py --summary")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="MediCheck RAG evaluation runner")
    parser.add_argument(
        "--url",
        default="http://localhost:5002",
        help="Base URL of Service 3 (default: http://localhost:5002)",
    )
    parser.add_argument(
        "--no-judge",
        action="store_true",
        help="Skip LLM-as-judge groundedness scoring and leave groundedness_score blank",
    )
    parser.add_argument(
        "--summary",
        action="store_true",
        help="Read existing eval_results.csv and print all rubric metrics (no RAG calls)",
    )
    parser.add_argument(
        "--threshold",
        type=int,
        default=GROUNDEDNESS_THRESHOLD,
        help=f"Groundedness pass threshold 0-100; scores >= this count as grounded (default: {GROUNDEDNESS_THRESHOLD})",
    )
    parser.add_argument(
        "--cases",
        type=str,
        default=None,
        help="Comma-separated case IDs to run (e.g. eval_001,eval_002). Merges into existing CSV.",
    )
    args = parser.parse_args()
    if args.summary:
        compute_summary(args.threshold)
    else:
        case_filter = set(args.cases.split(",")) if args.cases else None
        main(
            args.url,
            run_judge=not args.no_judge,
            threshold=args.threshold,
            case_filter=case_filter,
        )
