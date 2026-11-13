"""Pydantic 请求/响应模型。"""
from __future__ import annotations

from pydantic import BaseModel


class SearchRequest(BaseModel):
    question: str


class CompareRequest(BaseModel):
    id_a: str
    id_b: str
    focus: str | None = None


class Citation(BaseModel):
    evidence_id: str
    document_id: str
    investigation_id: str
    page: str | None = None
    source_url: str | None = None
    text: str


class SearchResponse(BaseModel):
    answer: str
    citations: list[Citation]
    investigations: list[dict]  # 排序后的调查摘要（含 hits / best_score）
    evidence_status: str


class CompareResponse(BaseModel):
    answer: str
    comparison: list[dict]
    citations: list[Citation]
    evidence_status: str


class InvestigationSummary(BaseModel):
    investigation_id: str
    title: str
    objective: str
    research_focus: str
    source_url: str
    doi: str | None = None


class InvestigationDetail(InvestigationSummary):
    documents: list[dict]
    tests: list[dict]
    findings: list[dict]
