"""Shared LangGraph state types."""
from __future__ import annotations

from typing import Literal, TypedDict


class Passage(TypedDict, total=False):
    """One retrieved evidence passage from Milvus."""

    evidence_id: str
    document_id: str
    investigation_id: str
    test_id: str | None
    text: str
    page: str | None
    source_url: str | None
    retrieval_score: float
    material: str | None
    gravity_condition: str | None
    oxygen_value: float | None
    oxygen_unit: str | None
    pressure_value: float | None
    pressure_unit: str | None
    airflow_value: float | None
    airflow_unit: str | None
    research_focus: str | None


class GraphState(TypedDict, total=False):
    # Input
    question: str
    selected_ids: list[str]

    # Query analysis output
    question_type: Literal["search", "compare", "invalid"]
    filters: dict

    # Retrieval output
    passages: list[Passage]
    ranked_investigations: list[dict]

    # Evidence grading output
    evidence_grade: Literal["sufficient", "insufficient"]

    # Generation output
    answer: str
    citations: list[dict]
    evidence_status: str

    # Comparison output
    comparison: list[dict]

    # Control fields
    error: str | None
    retry_count: int
