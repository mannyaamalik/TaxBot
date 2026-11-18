"""GET /analytics and POST /feedback endpoints."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Request

from api.analytics import analytics
from api.rate_limit import ANALYTICS_LIMIT, limiter
from api.schemas import AnalyticsResponse, FeedbackRequest

logger = logging.getLogger(__name__)

router = APIRouter(tags=["analytics"])


@router.get("/analytics", response_model=AnalyticsResponse, summary="Usage analytics")
@limiter.limit(ANALYTICS_LIMIT)
async def get_analytics(request: Request) -> AnalyticsResponse:  # noqa: ARG001
    """Return in-process counters for questions, refusals, cache hits, and feedback."""
    return AnalyticsResponse(
        questions_total=analytics.questions_total,
        not_found_total=analytics.not_found_total,
        out_of_scope_total=analytics.out_of_scope_total,
        cache_hits=analytics.cache_hits,
        feedback_up=analytics.feedback_up,
        feedback_down=analytics.feedback_down,
        avg_latency_ms=round(analytics.avg_latency_ms, 1),
        p95_latency_ms=round(analytics.p95_latency_ms, 1),
    )


@router.post("/feedback", status_code=204, summary="Submit answer feedback")
async def post_feedback(body: FeedbackRequest) -> None:
    """Record a thumbs-up or thumbs-down for an assistant answer."""
    analytics.record_feedback(body.feedback)
    logger.info(
        "feedback session_id=%s message_id=%s type=%s",
        body.session_id,
        body.message_id,
        body.feedback,
    )
