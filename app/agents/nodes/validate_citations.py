"""引用校验节点（纯代码，不调 LLM）：确保每个 citation 可解析到真实段落。"""
from __future__ import annotations

import re

from app.agents.state import GraphState

CITATION_RE = re.compile(r"\[([^\]]+)\]")


def validate_citations(state: GraphState) -> GraphState:
    answer = state.get("answer") or ""
    passages = state.get("passages") or []

    by_id = {p["evidence_id"]: p for p in passages}

    citations: list[dict] = []
    seen: set[str] = set()
    for token in CITATION_RE.findall(answer):
        p = by_id.get(token)
        if p is None or p["evidence_id"] in seen:
            continue  # 无法解析的引用（潜在幻觉）直接丢弃
        seen.add(p["evidence_id"])
        citations.append({
            "evidence_id": p["evidence_id"],
            "document_id": p["document_id"],
            "investigation_id": p["investigation_id"],
            "page": p.get("page"),
            "source_url": p.get("source_url"),
            "text": p["text"][:300],
        })

    state["citations"] = citations
    return state
