"""POST /chat — main RAG endpoint."""

from __future__ import annotations

import logging
import time

from fastapi import APIRouter, HTTPException, Request, status

from api.analytics import analytics
from api.cache import response_cache
from api.rate_limit import CHAT_LIMIT, limiter
from api.sanitize import sanitize_question
from api.schemas import ChatRequest, ChatResponse, SourceItem
from generation.generator import generate_answer
from generation.prompt import Turn
from retrieval.reranker import rerank
from retrieval.retriever import retrieve

logger = logging.getLogger(__name__)

router = APIRouter(tags=["chat"])


@router.post("/chat", response_model=ChatResponse, summary="Ask a tax question")
@limiter.limit(CHAT_LIMIT)
async def chat(request: Request, body: ChatRequest) -> ChatResponse:
    """Full RAG pipeline: sanitise → cache check → retrieve → rerank → generate.

    Rate limited to ``RATE_LIMIT_PER_MINUTE`` requests per IP.
    Repeated identical questions are served from a 5-min in-memory cache.
    Questions containing prompt-injection patterns are rejected with 400.
    """
    state = request.app.state
    request_id: str = request.headers.get("X-Request-ID", "-")
    start = time.monotonic()

    # ── 1. Sanitise ───────────────────────────────────────────────────────
    try:
        question = sanitize_question(body.question)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Question rejected: {exc}",
        ) from exc

    # ── 2. Cache lookup ───────────────────────────────────────────────────
    cached = response_cache.get(question)
    if cached is not None:
        latency_ms = (time.monotonic() - start) * 1000
        analytics.record_question(
            latency_ms=latency_ms,
            not_found=cached.not_found,
            cache_hit=True,
        )
        logger.info(
            "cache_hit request_id=%s question_len=%d latency_ms=%.1f",
            request_id,
            len(question),
            latency_ms,
        )
        return cached

    # ── 3. Session ────────────────────────────────────────────────────────
    session = state.session_store.get_or_create(body.session_id)
    history: list[Turn] = [
        Turn(role=t.role, content=t.content)
        for t in state.session_store.get_history(session.session_id)
    ]

    # ── 4. Retrieve ───────────────────────────────────────────────────────
    raw_results = retrieve(question, state.embedder, state.store)

    # ── 5. Rerank ─────────────────────────────────────────────────────────
    chunks = rerank(question, raw_results)

    # ── 6. Generate ───────────────────────────────────────────────────────
    result = generate_answer(question, chunks, history, state.llm_client)

    # ── 7. Update session ─────────────────────────────────────────────────
    state.session_store.add_turn(session.session_id, "user", question)
    state.session_store.add_turn(session.session_id, "assistant", result.answer)

    # ── 8. Build response ─────────────────────────────────────────────────
    is_out_of_scope = "I can only answer questions about Indian Income Tax" in result.answer
    response = ChatResponse(
        answer=result.answer,
        sources=[
            SourceItem(
                doc_title=s.doc_title,
                section_heading=s.section_heading,
                page_number=s.page_number,
                filename=s.filename,
                assessment_year=s.assessment_year,
            )
            for s in result.sources
        ],
        session_id=session.session_id,
        not_found=result.not_found,
        needs_clarification=result.needs_clarification,
    )

    # ── 9. Cache (non-personalised, non-clarification answers only) ───────
    if not result.needs_clarification and not result.not_found:
        response_cache.set(question, response)

    # ── 10. Analytics + logging ───────────────────────────────────────────
    latency_ms = (time.monotonic() - start) * 1000
    analytics.record_question(
        latency_ms=latency_ms,
        not_found=result.not_found,
        out_of_scope=is_out_of_scope,
        cache_hit=False,
    )
    logger.info(
        "chat request_id=%s session_id=%s question_len=%d "
        "chunks=%d not_found=%s latency_ms=%.1f",
        request_id,
        session.session_id,
        len(question),
        len(chunks),
        result.not_found,
        latency_ms,
    )

    return response
