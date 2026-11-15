"""Pydantic request and response models."""
from __future__ import annotations

from pydantic import BaseModel


class SearchRequest(BaseModel):
    question: str


class CompareRequest(BaseModel):
    id_a: str
    id_b: str
    focus: str | None = None


class Evidence(BaseModel):
    """Fields shared by citations and retrieved evidence."""

    evidence_id: str
    document_id: str
    investigation_id: str
    text: str
    page: str | None = None
    section: str | None = None
    test_id: str | None = None
    source_url: str | None = None
    retrieval_score: float | None = None


class InvestigationRank(BaseModel):
    identity: str
    investigation_id: str = ""  # Compatibility with the frontend field name.
    rank: int
    hits: int
    best_score: float
    score_label: str
    matched_evidence_ids: list[str]
    relevance_explanation: str


class SearchResponse(BaseModel):
    question: str
    answer: str
    investigations: list[InvestigationRank]
    citations: list[Evidence]
    evidence: list[Evidence]
    evidence_status: str


class CompareResponse(BaseModel):
    answer: str
    comparison: list[dict]
    citations: list[Evidence]
    evidence_status: str


class InvestigationSummary(BaseModel):
    investigation_id: str
    title: str
    objective: str
    research_focus: str
    materials: list[str] = []
    source_url: str
    doi: str | None = None


class InvestigationDetail(InvestigationSummary):
    documents: list[dict]
    tests: list[dict]
    findings: list[dict]
