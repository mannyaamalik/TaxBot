"""TaxBot evaluation runner  (TASK-044 / TASK-045 / TASK-046 / TASK-047).

Runs every question in eval_dataset.json against a live TaxBot server
(POST /chat) and measures four dimensions:

  1. Answer accuracy    — expected keywords present in the answer
  2. Citation quality   — sources list is non-empty; every answer cites at least one source
  3. Refusal behaviour  — out-of-scope questions receive the correct refusal
  4. Latency           — wall-clock time per request; p50, p95, max reported

Outputs
-------
  • A per-question result table printed to stdout (colour-coded)
  • A category-level summary table
  • A failure report section listing every FAIL with the actual answer,
    so you can pinpoint chunking and prompt improvements
  • Exit code 0 if overall pass-rate ≥ PASS_RATE_THRESHOLD, else 1

Usage
-----
    # Start your server first:
    #   uvicorn api.main:app --reload
    #
    python scripts/evaluate.py
    python scripts/evaluate.py --url http://localhost:8000
    python scripts/evaluate.py --dataset scripts/eval_dataset.json
    python scripts/evaluate.py --no-color --output results/eval_2024.txt
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import httpx

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DEFAULT_URL = "http://localhost:8000"
DEFAULT_DATASET = Path(__file__).parent / "eval_dataset.json"
PASS_RATE_THRESHOLD = 0.80          # overall pass-rate required for exit 0
LATENCY_P95_LIMIT_MS = 15_000       # REQ-NFP-01

REFUSAL_PHRASES = [
    "I can only answer questions about Indian Income Tax and GST",
    "only answer questions about Indian Income Tax",
    "only help with questions about Indian Income Tax",
]

NOT_FOUND_PHRASES = [
    "I could not find an answer to this question in my knowledge base",
    "could not find an answer",
]

CLARIFICATION_PHRASES = [
    "To give you the most accurate answer, could you tell me",
    "could you tell me",
    "could you clarify",
    "which tax regime",
]

# ---------------------------------------------------------------------------
# ANSI colour helpers (gracefully disabled with --no-color)
# ---------------------------------------------------------------------------

_COLOUR_ENABLED = True


def _c(text: str, code: str) -> str:
    return f"\033[{code}m{text}\033[0m" if _COLOUR_ENABLED else text


def green(t: str) -> str:  return _c(t, "32")
def red(t: str) -> str:    return _c(t, "31")
def yellow(t: str) -> str: return _c(t, "33")
def cyan(t: str) -> str:   return _c(t, "36")
def bold(t: str) -> str:   return _c(t, "1")
def dim(t: str) -> str:    return _c(t, "2")


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass
class EvalCase:
    id: str
    category: str
    question: str
    expected_keywords: list[str]
    expected_source_keywords: list[str]
    expect_not_found: bool
    expect_refusal: bool
    expect_clarification: bool
    notes: str


@dataclass
class EvalResult:
    case: EvalCase
    # Raw API response
    answer: str = ""
    sources: list[dict[str, Any]] = field(default_factory=list)
    not_found: bool = False
    needs_clarification: bool = False
    latency_ms: float = 0.0
    http_error: str = ""
    # Verdict sub-scores
    keyword_hits: list[str] = field(default_factory=list)
    keyword_misses: list[str] = field(default_factory=list)
    source_keyword_hits: list[str] = field(default_factory=list)
    source_keyword_misses: list[str] = field(default_factory=list)
    has_sources: bool = False
    refusal_correct: bool = False
    not_found_correct: bool = False
    clarification_correct: bool = False
    # Overall
    passed: bool = False
    failure_reasons: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# API client
# ---------------------------------------------------------------------------

def call_chat(url: str, question: str, session_id: str, timeout: float = 30.0) -> dict[str, Any]:
    """POST /chat and return the parsed JSON response."""
    with httpx.Client(timeout=timeout) as client:
        resp = client.post(
            f"{url}/chat",
            json={"question": question, "session_id": session_id},
        )
        resp.raise_for_status()
        return resp.json()


# ---------------------------------------------------------------------------
# Scoring logic
# ---------------------------------------------------------------------------

def _contains_any(text: str, phrases: list[str]) -> bool:
    lower = text.lower()
    return any(p.lower() in lower for p in phrases)


def _keyword_score(answer: str, keywords: list[str]) -> tuple[list[str], list[str]]:
    """Return (hits, misses) for expected keywords against the answer text."""
    lower = answer.lower()
    hits = [kw for kw in keywords if kw.lower() in lower]
    misses = [kw for kw in keywords if kw.lower() not in lower]
    return hits, misses


def _source_keyword_score(
    sources: list[dict[str, Any]], expected: list[str]
) -> tuple[list[str], list[str]]:
    """Return (hits, misses) for expected source keywords against cited sources."""
    if not sources:
        return [], expected[:]
    combined = " ".join(
        f"{s.get('doc_title','')} {s.get('section_heading','')} {s.get('filename','')}".lower()
        for s in sources
    )
    hits = [kw for kw in expected if kw.lower() in combined]
    misses = [kw for kw in expected if kw.lower() not in combined]
    return hits, misses


def score_result(result: EvalResult) -> EvalResult:
    """Populate verdict fields and overall pass/fail on a completed EvalResult."""
    case = result.case
    answer = result.answer

    # HTTP errors are always failures
    if result.http_error:
        result.failure_reasons.append(f"HTTP error: {result.http_error}")
        result.passed = False
        return result

    # ── Out-of-scope refusal check ────────────────────────────────────────
    if case.expect_refusal:
        result.refusal_correct = _contains_any(answer, REFUSAL_PHRASES)
        if result.refusal_correct:
            result.passed = True
        else:
            result.failure_reasons.append(
                "Expected out-of-scope refusal but answer did not contain refusal phrase."
            )
            result.passed = False
        return result

    # ── Not-found check ───────────────────────────────────────────────────
    if case.expect_not_found:
        result.not_found_correct = result.not_found or _contains_any(answer, NOT_FOUND_PHRASES)
        if result.not_found_correct:
            result.passed = True
        else:
            result.failure_reasons.append(
                "Expected 'not found' response but got an answer."
            )
            result.passed = False
        return result

    # ── Clarification check ───────────────────────────────────────────────
    if case.expect_clarification:
        result.clarification_correct = (
            result.needs_clarification
            or _contains_any(answer, CLARIFICATION_PHRASES)
        )
        # Clarification questions are soft — they still count as PASS
        # even if the bot gave an answer (ambiguous questions can go either way)

    # ── Keyword accuracy ──────────────────────────────────────────────────
    result.keyword_hits, result.keyword_misses = _keyword_score(answer, case.expected_keywords)
    keyword_ratio = (
        len(result.keyword_hits) / len(case.expected_keywords)
        if case.expected_keywords else 1.0
    )

    # ── Citation presence ─────────────────────────────────────────────────
    result.has_sources = bool(result.sources) or "Sources:" in answer

    if not result.has_sources:
        result.failure_reasons.append("Answer contains no citations (Sources section missing).")

    # ── Source keyword matching ───────────────────────────────────────────
    if case.expected_source_keywords:
        result.source_keyword_hits, result.source_keyword_misses = _source_keyword_score(
            result.sources, case.expected_source_keywords
        )
        source_ratio = len(result.source_keyword_hits) / len(case.expected_source_keywords)
    else:
        source_ratio = 1.0

    # ── Missing keywords → failure reason ────────────────────────────────
    if result.keyword_misses:
        result.failure_reasons.append(
            f"Missing expected keywords: {result.keyword_misses}"
        )

    if result.source_keyword_misses:
        result.failure_reasons.append(
            f"Source metadata missing expected terms: {result.source_keyword_misses}"
        )

    # ── Overall verdict ───────────────────────────────────────────────────
    # Pass when:
    #   • ≥ 60% of expected keywords are present
    #   • At least one source is cited
    #   • Source keywords ≥ 50% hit rate (or none expected)
    keyword_pass = keyword_ratio >= 0.60
    citation_pass = result.has_sources
    source_kw_pass = source_ratio >= 0.50

    result.passed = keyword_pass and citation_pass and source_kw_pass
    return result


# ---------------------------------------------------------------------------
# Evaluation runner
# ---------------------------------------------------------------------------

def run_evaluation(
    url: str,
    dataset: list[EvalCase],
    verbose: bool = False,
) -> list[EvalResult]:
    """Call POST /chat for every case and return scored EvalResult list."""
    results: list[EvalResult] = []
    session_id = f"eval-session-{int(time.time())}"

    total = len(dataset)
    for i, case in enumerate(dataset, start=1):
        prefix = f"[{i:>2}/{total}] {case.id}"
        print(f"  {dim(prefix)}  {case.question[:70]}…", end="", flush=True)

        t0 = time.perf_counter()
        result = EvalResult(case=case)

        try:
            response = call_chat(url, case.question, session_id)
            result.latency_ms = (time.perf_counter() - t0) * 1000
            result.answer = response.get("answer", "")
            result.sources = response.get("sources", [])
            result.not_found = response.get("not_found", False)
            result.needs_clarification = response.get("needs_clarification", False)
        except httpx.ConnectError:
            result.http_error = f"Cannot connect to {url}"
            result.latency_ms = (time.perf_counter() - t0) * 1000
        except httpx.HTTPStatusError as exc:
            result.http_error = f"HTTP {exc.response.status_code}"
            result.latency_ms = (time.perf_counter() - t0) * 1000
        except Exception as exc:
            result.http_error = str(exc)
            result.latency_ms = (time.perf_counter() - t0) * 1000

        score_result(result)

        status = green("PASS") if result.passed else red("FAIL")
        lat = f"{result.latency_ms:>7.0f} ms"
        print(f"\r  {dim(prefix)}  {status}  {dim(lat)}")

        if verbose and not result.passed:
            for reason in result.failure_reasons:
                print(f"       {yellow('↳')} {reason}")

        results.append(result)

    return results


# ---------------------------------------------------------------------------
# Report builders
# ---------------------------------------------------------------------------

def _separator(width: int = 100) -> str:
    return "─" * width


def print_summary(results: list[EvalResult]) -> None:
    """Print category-level summary table."""
    from collections import defaultdict
    by_cat: dict[str, list[EvalResult]] = defaultdict(list)
    for r in results:
        by_cat[r.case.category].append(r)

    print()
    print(bold("┌── Category Summary " + "─" * 60))
    header = f"  {'Category':<25}  {'Total':>5}  {'Pass':>5}  {'Pass%':>6}  {'Avg ms':>8}"
    print(bold(header))
    print("  " + _separator(80))

    total_pass = sum(1 for r in results if r.passed)
    for cat in sorted(by_cat.keys()):
        cat_results = by_cat[cat]
        n = len(cat_results)
        p = sum(1 for r in cat_results if r.passed)
        pct = p / n * 100
        avg_ms = statistics.mean(r.latency_ms for r in cat_results)
        pct_str = f"{pct:.0f}%"
        colour = green if pct >= 80 else (yellow if pct >= 50 else red)
        print(f"  {cat:<25}  {n:>5}  {p:>5}  {colour(pct_str):>6}  {avg_ms:>8.0f}")

    print("  " + _separator(80))
    overall_pct = total_pass / len(results) * 100
    colour = green if overall_pct >= 80 else (yellow if overall_pct >= 50 else red)
    print(bold(f"  {'OVERALL':<25}  {len(results):>5}  {total_pass:>5}  {colour(f'{overall_pct:.0f}%'):>6}"))
    print()


def print_latency_report(results: list[EvalResult]) -> None:
    """Print latency statistics."""
    latencies = [r.latency_ms for r in results if not r.http_error]
    if not latencies:
        return

    latencies_sorted = sorted(latencies)
    p50 = statistics.median(latencies_sorted)
    p95_idx = max(0, int(len(latencies_sorted) * 0.95) - 1)
    p95 = latencies_sorted[p95_idx]
    p99_idx = max(0, int(len(latencies_sorted) * 0.99) - 1)
    p99 = latencies_sorted[p99_idx]
    mx = max(latencies_sorted)
    mn = min(latencies_sorted)

    p95_pass = p95 < LATENCY_P95_LIMIT_MS
    p95_colour = green if p95_pass else red

    print(bold("┌── Latency Report " + "─" * 62))
    print(f"  {'p50':<10} {p50:>10.0f} ms")
    print(f"  {'p95':<10} {p95_colour(f'{p95:>10.0f} ms')}  "
          f"{'(within limit)' if p95_pass else red(f'(exceeds {LATENCY_P95_LIMIT_MS} ms limit)')}")
    print(f"  {'p99':<10} {p99:>10.0f} ms")
    print(f"  {'max':<10} {mx:>10.0f} ms")
    print(f"  {'min':<10} {mn:>10.0f} ms")
    print()


def print_citation_report(results: list[EvalResult]) -> None:
    """Print citation quality statistics."""
    # Exclude refusal / not-found / out-of-scope cases
    answer_cases = [
        r for r in results
        if not r.case.expect_refusal and not r.case.expect_not_found
    ]
    if not answer_cases:
        return

    with_sources = sum(1 for r in answer_cases if r.has_sources)
    pct = with_sources / len(answer_cases) * 100
    colour = green if pct >= 90 else (yellow if pct >= 70 else red)

    print(bold("┌── Citation Quality " + "─" * 60))
    print(f"  Answers with citations:  {with_sources}/{len(answer_cases)}  {colour(f'{pct:.0f}%')}")

    # Source keyword coverage
    cases_with_src_kw = [r for r in answer_cases if r.case.expected_source_keywords]
    if cases_with_src_kw:
        avg_hit = statistics.mean(
            len(r.source_keyword_hits) / len(r.case.expected_source_keywords)
            for r in cases_with_src_kw
        ) * 100
        src_colour = green if avg_hit >= 70 else (yellow if avg_hit >= 50 else red)
        print(f"  Avg source keyword hit:  {src_colour(f'{avg_hit:.0f}%')}")
    print()


def print_refusal_report(results: list[EvalResult]) -> None:
    """Print refusal behaviour statistics."""
    refusal_cases = [r for r in results if r.case.expect_refusal]
    if not refusal_cases:
        return
    correct = sum(1 for r in refusal_cases if r.passed)
    pct = correct / len(refusal_cases) * 100
    colour = green if pct == 100 else (yellow if pct >= 50 else red)
    print(bold("┌── Refusal Behaviour " + "─" * 59))
    print(f"  Out-of-scope questions refused correctly: {correct}/{len(refusal_cases)}  {colour(f'{pct:.0f}%')}")
    print()


def print_failure_report(results: list[EvalResult]) -> None:
    """Print detailed failure breakdown for prompt/chunking diagnosis."""
    failures = [r for r in results if not r.passed]
    if not failures:
        print(bold(green("✓ No failures — all questions passed.")))
        return

    print(bold(red(f"┌── Failure Report ({len(failures)} failures) " + "─" * 48)))
    print(bold(red("  Use this section to identify chunking gaps and prompt weaknesses.")))
    print()

    for r in failures:
        case = r.case
        print(bold(f"  [{case.id}]  {case.category.upper()}"))
        print(f"  {bold('Q:')} {case.question}")
        print(f"  {bold('Notes:')} {case.notes}")

        if r.http_error:
            print(f"  {red('Error:')} {r.http_error}")
        else:
            # Truncate long answers for readability
            ans_preview = r.answer[:300].replace("\n", " ")
            if len(r.answer) > 300:
                ans_preview += "…"
            print(f"  {bold('Answer preview:')} {dim(ans_preview)}")
            print(f"  {bold('Sources returned:')} {len(r.sources)}")

        for reason in r.failure_reasons:
            print(f"  {yellow('↳')} {reason}")

        print()

    # ── Diagnosis hints ───────────────────────────────────────────────────
    all_missing_kw: list[str] = []
    for r in failures:
        all_missing_kw.extend(r.keyword_misses)

    if all_missing_kw:
        from collections import Counter
        common = Counter(all_missing_kw).most_common(10)
        print(bold("  ┌── Most Frequently Missing Keywords (chunking/ingestion gaps)"))
        for kw, count in common:
            bar = "█" * min(count, 20)
            print(f"    {count:>3}×  {kw:<30} {dim(bar)}")
        print()

    # ── Actionable hints ──────────────────────────────────────────────────
    no_source_failures = [r for r in failures if not r.has_sources and not r.case.expect_refusal]
    if no_source_failures:
        print(bold("  ┌── Questions that received an answer but no citations"))
        print(bold(yellow("  Prompt hint: Strengthen RULE 3 or lower similarity threshold.")))
        for r in no_source_failures:
            print(f"    • [{r.case.id}] {r.case.question[:70]}")
        print()

    refusal_failures = [r for r in failures if r.case.expect_refusal]
    if refusal_failures:
        print(bold("  ┌── Out-of-scope questions that were NOT refused"))
        print(bold(yellow("  Prompt hint: Strengthen RULE 4 (scope guard) in system prompt.")))
        for r in refusal_failures:
            print(f"    • [{r.case.id}] {r.case.question[:70]}")
        print()

    not_found_failures = [
        r for r in failures
        if not r.case.expect_refusal and r.keyword_misses
    ]
    if not_found_failures:
        print(bold("  ┌── Questions with missing keywords (KB coverage gaps)"))
        print(bold(yellow("  Chunking hint: Check whether source PDFs for these topics are ingested.")))
        for r in not_found_failures:
            print(f"    • [{r.case.id}] ({r.case.category}) {r.case.question[:60]}")
            print(f"      Missing: {r.keyword_misses}")
        print()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def load_dataset(path: Path) -> list[EvalCase]:
    with open(path, encoding="utf-8") as fh:
        raw = json.load(fh)
    cases = []
    for item in raw:
        cases.append(EvalCase(
            id=item["id"],
            category=item["category"],
            question=item["question"],
            expected_keywords=item.get("expected_keywords", []),
            expected_source_keywords=item.get("expected_source_keywords", []),
            expect_not_found=item.get("expect_not_found", False),
            expect_refusal=item.get("expect_refusal", False),
            expect_clarification=item.get("expect_clarification", False),
            notes=item.get("notes", ""),
        ))
    return cases


def main() -> int:
    global _COLOUR_ENABLED

    parser = argparse.ArgumentParser(
        description="Evaluate TaxBot answer quality against a ground-truth dataset.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--url", default=DEFAULT_URL, help="TaxBot server base URL")
    parser.add_argument("--dataset", default=str(DEFAULT_DATASET), help="Path to eval_dataset.json")
    parser.add_argument("--no-color", action="store_true", help="Disable ANSI colours")
    parser.add_argument("--verbose", action="store_true", help="Show failure reasons inline")
    parser.add_argument("--output", help="Also write full report to this file")
    parser.add_argument(
        "--ids", nargs="+", metavar="Q001",
        help="Run only the specified question IDs"
    )
    parser.add_argument(
        "--category", metavar="CATEGORY",
        help="Run only questions in this category"
    )
    args = parser.parse_args()

    if args.no_color:
        _COLOUR_ENABLED = False

    # ── Load dataset ──────────────────────────────────────────────────────
    dataset_path = Path(args.dataset)
    if not dataset_path.exists():
        print(f"ERROR: dataset not found at {dataset_path}", file=sys.stderr)
        return 1

    all_cases = load_dataset(dataset_path)

    # Optional filters
    if args.ids:
        all_cases = [c for c in all_cases if c.id in args.ids]
    if args.category:
        all_cases = [c for c in all_cases if c.category == args.category]

    if not all_cases:
        print("No questions matched the given filters.", file=sys.stderr)
        return 1

    # ── Connectivity check ────────────────────────────────────────────────
    print(bold(f"\n  TaxBot Evaluation  ·  {len(all_cases)} questions  ·  {args.url}\n"))
    try:
        with httpx.Client(timeout=5.0) as c:
            c.get(f"{args.url}/health").raise_for_status()
        print(f"  {green('✓')} Server reachable at {args.url}\n")
    except Exception as exc:
        print(f"  {red('✗')} Cannot reach server: {exc}")
        print(f"  Start the server with:  uvicorn api.main:app --reload\n",
              file=sys.stderr)
        return 1

    # ── Run evaluation ────────────────────────────────────────────────────
    results = run_evaluation(args.url, all_cases, verbose=args.verbose)

    # ── Print reports ─────────────────────────────────────────────────────
    print()
    print_summary(results)
    print_latency_report(results)
    print_citation_report(results)
    print_refusal_report(results)
    print_failure_report(results)

    # ── Overall verdict ───────────────────────────────────────────────────
    total = len(results)
    passed = sum(1 for r in results if r.passed)
    pass_rate = passed / total
    latencies = [r.latency_ms for r in results if not r.http_error]
    p95_ok = True
    if latencies:
        p95_idx = max(0, int(len(sorted(latencies)) * 0.95) - 1)
        p95 = sorted(latencies)[p95_idx]
        p95_ok = p95 < LATENCY_P95_LIMIT_MS

    accuracy_ok = pass_rate >= PASS_RATE_THRESHOLD
    overall_ok = accuracy_ok and p95_ok

    verdict = green("PASS") if overall_ok else red("FAIL")
    print(bold(f"  Overall verdict:  {verdict}"))
    print(f"  Pass rate:  {passed}/{total}  ({pass_rate * 100:.1f}%)"
          f"  {'≥' if accuracy_ok else '<'} {PASS_RATE_THRESHOLD * 100:.0f}% threshold")
    if not p95_ok:
        print(red(f"  p95 latency {p95:.0f} ms exceeds {LATENCY_P95_LIMIT_MS} ms limit"))
    print()

    # ── Optional file output ──────────────────────────────────────────────
    if args.output:
        _write_json_report(results, Path(args.output))
        print(f"  {dim(f'JSON report written to {args.output}')}")

    return 0 if overall_ok else 1


def _write_json_report(results: list[EvalResult], path: Path) -> None:
    """Serialise results to a machine-readable JSON file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    output = []
    for r in results:
        output.append({
            "id": r.case.id,
            "category": r.case.category,
            "question": r.case.question,
            "passed": r.passed,
            "failure_reasons": r.failure_reasons,
            "latency_ms": round(r.latency_ms, 1),
            "has_sources": r.has_sources,
            "keyword_hits": r.keyword_hits,
            "keyword_misses": r.keyword_misses,
            "source_keyword_hits": r.source_keyword_hits,
            "source_keyword_misses": r.source_keyword_misses,
            "refusal_correct": r.refusal_correct,
            "not_found_correct": r.not_found_correct,
            "needs_clarification": r.needs_clarification,
            "answer_preview": r.answer[:500],
            "http_error": r.http_error,
        })
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(output, fh, indent=2, ensure_ascii=False)


if __name__ == "__main__":
    sys.exit(main())
