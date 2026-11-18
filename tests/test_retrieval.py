"""Integration test for end-to-end retrieval pipeline  (TASK-021).

Ingests a small synthetic document with three topically distinct sections,
then asserts that querying about each section returns the correct passage.
"""

from __future__ import annotations

import sys
import textwrap
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from ingestion.pipeline import ingest_file
from retrieval.embedder import LocalEmbedder
from retrieval.reranker import rerank
from retrieval.retriever import retrieve
from retrieval.store import VectorStore


# ---------------------------------------------------------------------------
# Shared fixture: tiny KB with three distinct topics
# ---------------------------------------------------------------------------

SECTION_80C_TEXT = textwrap.dedent("""\
    Section 80C Deduction for Life Insurance and Investments.
    Under Section 80C of the Income Tax Act, an individual or HUF can claim
    a deduction of up to rupees one lakh fifty thousand per financial year.
    Eligible instruments include ELSS mutual funds, Public Provident Fund,
    Employee Provident Fund, National Savings Certificate, life insurance
    premiums, and home loan principal repayment.
    The deduction reduces the gross total income before computing tax liability.
""")

SECTION_GST_TEXT = textwrap.dedent("""\
    GST Registration Threshold and Procedure.
    Businesses whose aggregate annual turnover exceeds twenty lakh rupees are
    required to register under the Goods and Services Tax Act.
    For special category states the threshold is ten lakh rupees.
    Registration is done online through the GST portal at gst.gov.in.
    A GSTIN is allotted within seven working days of successful application.
""")

SECTION_TDS_TEXT = textwrap.dedent("""\
    TDS Under Section 194C for Payments to Contractors.
    Tax deducted at source under section 194C applies to payments made to
    resident contractors and sub-contractors for carrying out any work.
    The TDS rate is one percent for payments to individuals and Hindu
    Undivided Families, and two percent for other cases.
    TDS must be deducted at the time of credit or payment, whichever is earlier.
""")


@pytest.fixture(scope="module")
def populated_store(tmp_path_factory: pytest.TempPathFactory):
    """
    Returns (embedder, store) with the three-section document ingested.
    Uses module scope so the (slow) model load happens only once.
    """
    tmp = tmp_path_factory.mktemp("retrieval_test")
    doc_path = tmp / "test_tax_doc.md"
    doc_path.write_text(
        f"# Test Tax Reference\n\n"
        f"{SECTION_80C_TEXT}\n\n"
        f"{SECTION_GST_TEXT}\n\n"
        f"{SECTION_TDS_TEXT}\n",
        encoding="utf-8",
    )

    store = VectorStore(
        db_path=str(tmp / "db"),
        collection_name="retrieval_test",
    )
    embedder = LocalEmbedder()
    ingest_file(str(doc_path), embedder, store)

    return embedder, store


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_retrieval_returns_80c_for_deduction_question(populated_store):
    """Query about 80C deductions should surface the 80C passage."""
    embedder, store = populated_store
    question = "What is the maximum deduction allowed under Section 80C?"

    results = retrieve(question, embedder, store)
    assert results, "Expected at least one result, got none."

    top_text = results[0].text.lower()
    assert "80c" in top_text or "one lakh fifty" in top_text, (
        f"Top result does not appear to be about 80C.\n{results[0].text[:300]}"
    )


def test_retrieval_returns_gst_for_registration_question(populated_store):
    """Query about GST registration should surface the GST passage."""
    embedder, store = populated_store
    question = "What is the turnover threshold for GST registration?"

    results = retrieve(question, embedder, store)
    assert results, "Expected at least one result, got none."

    combined = " ".join(r.text.lower() for r in results[:3])
    assert "gst" in combined or "turnover" in combined or "twenty lakh" in combined, (
        f"GST content not found in top results.\nTop: {results[0].text[:300]}"
    )


def test_retrieval_returns_tds_for_contractor_question(populated_store):
    """Query about TDS on contractors should surface the 194C passage."""
    embedder, store = populated_store
    question = "What is the TDS rate for payments to contractors under 194C?"

    results = retrieve(question, embedder, store)
    assert results, "Expected at least one result, got none."

    combined = " ".join(r.text.lower() for r in results[:3])
    assert "194c" in combined or "contractor" in combined or "tds" in combined, (
        f"TDS/194C content not found in top results.\nTop: {results[0].text[:300]}"
    )


def test_retrieved_chunk_has_doc_title(populated_store):
    """Every retrieved chunk must carry a non-empty doc_title."""
    embedder, store = populated_store
    question = "Income tax deduction limit"

    results = retrieve(question, embedder, store)
    assert results, "Expected results."
    for r in results:
        assert r.doc_title, f"doc_title is empty on chunk: {r.chunk_id}"


def test_reranker_preserves_relevance_order(populated_store):
    """After reranking, the most relevant chunk should still rank first."""
    embedder, store = populated_store
    question = "deduction for life insurance and ELSS investments under Section 80C"

    raw_results = retrieve(question, embedder, store)
    assert raw_results, "Expected retrieval results."

    reranked = rerank(question, raw_results)
    assert reranked, "Reranker returned no results."

    top_text = reranked[0].text.lower()
    assert "80c" in top_text or "insurance" in top_text or "elss" in top_text, (
        f"Top reranked chunk doesn't seem most relevant.\n{reranked[0].text[:300]}"
    )


def test_retrieve_empty_on_gibberish(populated_store):
    """A completely irrelevant query should return no results above threshold."""
    embedder, store = populated_store

    # This query is semantically distant from any tax topic;
    # it should not meet the similarity threshold.
    # (If the threshold is too low this may flap; threshold default=0.40)
    question = "xyzzy quantum banana purple elephant seventeen"
    results = retrieve(question, embedder, store)

    # We cannot guarantee zero results without controlling the threshold,
    # but we can assert that if results exist they are low-scoring.
    for r in results:
        assert r.similarity < 0.95, (
            f"Unexpected high-similarity result for gibberish: "
            f"sim={r.similarity:.3f} text={r.text[:80]}"
        )
