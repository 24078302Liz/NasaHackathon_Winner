"""Pydantic 请求/响应模型。"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


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
    section: str | None = None
    test_id: str | None = None
    source_url: str | None = None
    text: str
    retrieval_score: float | None = None


class EvidencePassage(Citation):
    """A retrieved, inspectable evidence passage, whether or not cited in prose."""


class RankedInvestigation(BaseModel):
    investigation_id: str
    title: str
    objective: str
    research_focus: str
    source_url: str
    doi: str | None = None
    rank: int
    hits: int
    best_score: float
    score_label: str = "retrieval relevance (not confidence or risk)"
    matched_evidence_ids: list[str] = Field(default_factory=list)
    relevance_explanation: str


class SearchResponse(BaseModel):
    question: str
    answer: str
    citations: list[Citation]
    evidence: list[EvidencePassage]
    investigations: list[RankedInvestigation]
    evidence_status: str


class ComparisonField(BaseModel):
    name: str
    value: str
    unit: str | None = None
    availability: Literal["reported", "not_reported", "not_yet_extracted"]
    evidence_ids: list[str] = Field(default_factory=list)


class InvestigationComparison(BaseModel):
    investigation_id: str
    title: str
    source_url: str
    fields: list[ComparisonField]


class CompareResponse(BaseModel):
    answer: str
    comparison: list[InvestigationComparison]
    citations: list[Citation]
    evidence_status: str


class InvestigationSummary(BaseModel):
    investigation_id: str
    title: str
    objective: str
    research_focus: str
    materials: list[str] = Field(default_factory=list)
    source_url: str
    doi: str | None = None


class SourceDocumentRecord(BaseModel):
    document_id: str
    title: str
    source_url: str
    local_filename: str
    retrieval_date: str
    license_ref: str | None = None


class ExperimentalConditionRecord(BaseModel):
    test_id: str
    material: str
    sample_geometry: str
    oxygen_value: float | None = None
    oxygen_unit: str | None = None
    pressure_value: float | None = None
    pressure_unit: str | None = None
    airflow_value: float | None = None
    airflow_unit: str | None = None
    gravity_condition: str


class ReportedFindingRecord(BaseModel):
    finding_id: str
    test_id: str | None = None
    finding_text: str
    supporting_evidence_ids: list[str] = Field(default_factory=list)
    limitations: str | None = None


class InvestigationDetail(InvestigationSummary):
    documents: list[SourceDocumentRecord]
    tests: list[ExperimentalConditionRecord]
    findings: list[ReportedFindingRecord]
