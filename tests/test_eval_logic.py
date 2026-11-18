"""Unit tests for the evaluation script's scoring logic.

These tests run without a live server by exercising ``score_result`` directly.
They verify that the scoring rules produce the right verdict for every
response type: correct answer, missing keywords, missing citations,
correct refusal, incorrect refusal, and not-found.
"""

from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from scripts.evaluate import EvalCase, EvalResult, score_result


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _case(
    id: str = "Q001",
    category: str = "deductions",
    question: str = "What is the 80C limit?",
    expected_keywords: list[str] | None = None,
    expected_source_keywords: list[str] | None = None,
    expect_not_found: bool = False,
    expect_refusal: bool = False,
    expect_clarification: bool = False,
    notes: str = "",
) -> EvalCase:
    return EvalCase(
        id=id,
        category=category,
        question=question,
        expected_keywords=expected_keywords or [],
        expected_source_keywords=expected_source_keywords or [],
        expect_not_found=expect_not_found,
        expect_refusal=expect_refusal,
        expect_clarification=expect_clarification,
        notes=notes,
    )


def _result(case: EvalCase, answer: str = "", sources=None, **kwargs) -> EvalResult:
    r = EvalResult(case=case, answer=answer, sources=sources or [], **kwargs)
    return r


# ---------------------------------------------------------------------------
# 1. Correct answer with citations and all keywords → PASS
# ---------------------------------------------------------------------------


def test_full_hit_passes():
    case = _case(
        expected_keywords=["1,50,000", "80C"],
        expected_source_keywords=["income tax"],
    )
    result = _result(
        case,
        answer=(
            "Under Section 80C the limit is ₹1,50,000 per year [1].\n\n"
            "Sources:\n- [1] Income Tax Act 1961, Section 80C, Page 42"
        ),
        sources=[{"doc_title": "Income Tax Act 1961", "section_heading": "Section 80C",
                  "page_number": 42, "filename": "IT_Act.pdf", "assessment_year": "2024-25"}],
    )
    score_result(result)
    assert result.passed is True
    assert result.failure_reasons == []


# ---------------------------------------------------------------------------
# 2. Missing keywords → FAIL
# ---------------------------------------------------------------------------


def test_missing_keyword_fails():
    case = _case(expected_keywords=["1,50,000", "80C", "ELSS"])
    result = _result(
        case,
        answer="You can claim deductions under various sections.\n\nSources:\n- [1] IT Act, Sec 80, Page 1",
        sources=[{"doc_title": "IT Act", "section_heading": "", "page_number": 1,
                  "filename": "it.pdf", "assessment_year": "2024-25"}],
    )
    score_result(result)
    assert result.passed is False
    assert "1,50,000" in result.keyword_misses or "ELSS" in result.keyword_misses


# ---------------------------------------------------------------------------
# 3. Answer without Sources section → FAIL (citation missing)
# ---------------------------------------------------------------------------


def test_missing_sources_fails():
    case = _case(expected_keywords=["1,50,000"])
    result = _result(
        case,
        answer="The limit under 80C is ₹1,50,000 per year.",
        sources=[],   # API returned empty sources list
    )
    score_result(result)
    assert result.passed is False
    assert any("citation" in r.lower() or "sources" in r.lower() for r in result.failure_reasons)


# ---------------------------------------------------------------------------
# 4. Out-of-scope: correct refusal → PASS
# ---------------------------------------------------------------------------


def test_correct_refusal_passes():
    case = _case(expect_refusal=True)
    result = _result(
        case,
        answer="I can only answer questions about Indian Income Tax and GST.",
    )
    score_result(result)
    assert result.passed is True
    assert result.refusal_correct is True


# ---------------------------------------------------------------------------
# 5. Out-of-scope: bot answered instead of refusing → FAIL
# ---------------------------------------------------------------------------


def test_missed_refusal_fails():
    case = _case(expect_refusal=True)
    result = _result(
        case,
        answer="The repo rate is 6.5% as set by RBI.\n\nSources:\n- [1] Some doc",
    )
    score_result(result)
    assert result.passed is False
    assert result.refusal_correct is False


# ---------------------------------------------------------------------------
# 6. Not-found: correct not-found response → PASS
# ---------------------------------------------------------------------------


def test_correct_not_found_passes():
    case = _case(expect_not_found=True)
    result = _result(
        case,
        answer="I could not find an answer to this question in my knowledge base. "
               "Please consult a qualified tax professional.",
        not_found=True,
    )
    score_result(result)
    assert result.passed is True
    assert result.not_found_correct is True


# ---------------------------------------------------------------------------
# 7. HTTP error → FAIL
# ---------------------------------------------------------------------------


def test_http_error_fails():
    case = _case(expected_keywords=["1,50,000"])
    result = _result(case, http_error="HTTP 500")
    score_result(result)
    assert result.passed is False
    assert any("HTTP" in r for r in result.failure_reasons)


# ---------------------------------------------------------------------------
# 8. Partial keyword match above 60% threshold → PASS
# ---------------------------------------------------------------------------


def test_partial_keyword_hit_above_threshold_passes():
    # 4 expected, 3 hit (75%) → above 60% → pass
    case = _case(
        expected_keywords=["80C", "1,50,000", "ELSS", "PPF"],
        expected_source_keywords=[],
    )
    result = _result(
        case,
        answer="Section 80C: limit ₹1,50,000. ELSS qualifies. [1]\n\nSources:\n- [1] IT Act",
        sources=[{"doc_title": "IT Act", "section_heading": "", "page_number": 1,
                  "filename": "it.pdf", "assessment_year": "2024-25"}],
    )
    score_result(result)
    # 3/4 = 75% > 60% → should pass
    assert result.passed is True


# ---------------------------------------------------------------------------
# 9. Partial keyword match below 60% threshold → FAIL
# ---------------------------------------------------------------------------


def test_partial_keyword_hit_below_threshold_fails():
    # 5 expected, 1 hit (20%) → below 60% → fail
    case = _case(
        expected_keywords=["80C", "1,50,000", "ELSS", "PPF", "NSC"],
    )
    result = _result(
        case,
        answer="You can invest in 80C instruments.\n\nSources:\n- [1] IT Act",
        sources=[{"doc_title": "IT Act", "section_heading": "", "page_number": 1,
                  "filename": "it.pdf", "assessment_year": "2024-25"}],
    )
    score_result(result)
    assert result.passed is False


# ---------------------------------------------------------------------------
# 10. Clarification expected — answer is still a pass if clarification detected
# ---------------------------------------------------------------------------


def test_clarification_detected_passes():
    case = _case(expect_clarification=True, expected_keywords=[])
    result = _result(
        case,
        answer=(
            "To give you the most accurate answer, could you tell me: "
            "are you filing under the old or new tax regime?"
        ),
        needs_clarification=True,
    )
    score_result(result)
    assert result.clarification_correct is True


# ---------------------------------------------------------------------------
# 11. Source keyword miss still allows pass if keyword hits are strong
# ---------------------------------------------------------------------------


def test_source_keyword_miss_causes_fail():
    case = _case(
        expected_keywords=["10%", "LTCG"],
        expected_source_keywords=["capital gains", "section 112A"],
    )
    result = _result(
        case,
        answer="LTCG at 10% under section 112A [1].\n\nSources:\n- [1] Budget doc",
        sources=[{"doc_title": "Budget Document", "section_heading": "",
                  "page_number": 1, "filename": "budget.pdf", "assessment_year": "2024-25"}],
    )
    score_result(result)
    # source_keyword_misses will include "capital gains" and "section 112A"
    # → source_ratio = 0% < 50% → FAIL
    assert result.passed is False
    assert result.source_keyword_misses  # at least one miss
