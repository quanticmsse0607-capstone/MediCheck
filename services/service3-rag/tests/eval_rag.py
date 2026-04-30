"""
tests/eval_rag.py
RAG evaluation runner — Step 8, Sprint 5.

Sends each case from eval_set.json to POST /explain, records the response
and wall-clock latency, then writes eval_results.csv for manual scoring.

Usage:
    # With Service 3 running locally on port 5002:
    python tests/eval_rag.py

    # Against a deployed Render service:
    python tests/eval_rag.py --url https://medicheck-rag.onrender.com

Output:
    tests/eval_results.csv  — one row per case, ready for manual scoring
    Prints p50 and p95 latency to stdout when complete.
"""

import argparse
import csv
import json
import statistics
import time
from pathlib import Path

import requests

EVAL_SET_PATH = Path(__file__).parent / "eval_set.json"
RESULTS_PATH = Path(__file__).parent / "eval_results.csv"

CSV_HEADERS = [
    "case_id",
    "module",
    "description",
    "latency_ms",
    "status_code",
    "explanation",
    "citations",
    # Manual scoring columns — fill these in after reviewing responses
    "groundedness_score",   # 0-100: % of factual claims supported by retrieved context
    "citation_accurate",    # yes / no / partial
    "notes",
]


def load_eval_set() -> list[dict]:
    with open(EVAL_SET_PATH) as f:
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
            # Each case has exactly one error — extract its result
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
        "citation_accurate": "",
        "notes": "",
    }


def compute_percentiles(latencies: list[float]) -> tuple[float, float]:
    sorted_l = sorted(latencies)
    n = len(sorted_l)
    p50_idx = int(n * 0.50)
    p95_idx = min(int(n * 0.95), n - 1)
    return sorted_l[p50_idx], sorted_l[p95_idx]


def main(base_url: str) -> None:
    cases = load_eval_set()
    print(f"Loaded {len(cases)} evaluation cases from {EVAL_SET_PATH}")
    print(f"Target: {base_url}\n")

    results = []
    latencies = []

    for i, case in enumerate(cases, 1):
        print(f"[{i:02d}/{len(cases)}] {case['case_id']} ({case['module']})... ", end="", flush=True)
        row = run_case(case, base_url)
        results.append(row)

        if row["status_code"] == 200:
            latencies.append(row["latency_ms"])
            print(f"{row['latency_ms']} ms — OK")
        else:
            print(f"FAILED (status={row['status_code']})")

    with open(RESULTS_PATH, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_HEADERS)
        writer.writeheader()
        writer.writerows(results)

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

    print("\nNext: open eval_results.csv and fill in groundedness_score, citation_accurate, and notes columns.")
    print("Scoring guide:")
    print("  groundedness_score : 0-100 — what % of factual claims are supported by the retrieved context?")
    print("  citation_accurate  : yes / no / partial — does each cited source actually contain relevant content?")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="MediCheck RAG evaluation runner")
    parser.add_argument(
        "--url",
        default="http://localhost:5002",
        help="Base URL of Service 3 (default: http://localhost:5002)",
    )
    args = parser.parse_args()
    main(args.url)
