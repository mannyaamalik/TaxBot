"""Pydantic request/response schemas for the TaxBot API."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=2000)
    session_id: str | None = None
    language: Literal["en", "hi"] = "en"


class SourceItem(BaseModel):
    doc_title: str
    section_heading: str
    page_number: int
    filename: str
    assessment_year: str


class ChatResponse(BaseModel):
    answer: str
    sources: list[SourceItem]
    session_id: str
    not_found: bool
    needs_clarification: bool = False


class IngestResponse(BaseModel):
    job_id: str
    status: Literal["queued", "running", "done", "failed"]
    filename: str
    chunks_added: int | None = None
    error: str | None = None


class HealthResponse(BaseModel):
    status: Literal["ok"] = "ok"
    total_chunks: int
    active_ingest_jobs: int
    active_sessions: int


class ReadyResponse(BaseModel):
    ready: bool
    reason: str = ""


class FeedbackRequest(BaseModel):
    message_id: str
    session_id: str
    question: str = ""
    answer: str = ""
    feedback: Literal["up", "down"]


class AnalyticsResponse(BaseModel):
    questions_total: int
    not_found_total: int
    out_of_scope_total: int
    cache_hits: int
    feedback_up: int
    feedback_down: int
    avg_latency_ms: float
    p95_latency_ms: float
