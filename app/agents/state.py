"""LangGraph 共享状态定义。"""
from __future__ import annotations

from typing import Literal, TypedDict


class Passage(TypedDict, total=False):
    """一条证据段落（来自 Milvus 检索命中）。"""

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
    # 输入
    question: str
    selected_ids: list[str]

    # analyze_query 输出
    question_type: Literal["search", "compare", "invalid"]
    filters: dict

    # retrieve 输出
    passages: list[Passage]
    ranked_investigations: list[dict]

    # grade_evidence 输出
    evidence_grade: Literal["sufficient", "insufficient"]

    # generate 输出
    answer: str
    citations: list[dict]
    evidence_status: str

    # compare 输出
    comparison: list[dict]

    # 控制
    error: str | None
    retry_count: int
