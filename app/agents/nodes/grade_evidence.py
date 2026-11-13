"""证据充分性判断节点：规则优先，必要时小模型打分。"""
from __future__ import annotations

import json
import re

from app.agents.prompts import GRADE_SYSTEM
from app.agents.state import GraphState
from app.config import settings
from app.services.llm import get_small_llm


def _rule_grade(state: GraphState) -> str | None:
    """规则先行：命中为空或最高分过低 → 直接判不足；否则交给小模型细判。"""
    passages = state.get("passages") or []
    if not passages:
        return "insufficient"
    best = max(p["retrieval_score"] for p in passages)
    if best < settings.retrieval_score_threshold:
        return "insufficient"
    return None


def grade_evidence(state: GraphState) -> GraphState:
    rule = _rule_grade(state)
    if rule is not None:
        state["evidence_grade"] = rule
        return state

    passages = state.get("passages") or []
    snippets = "\n\n".join(f"[{p['evidence_id']}] {p['text'][:500]}" for p in passages[:8])

    llm = get_small_llm(temperature=0.0)
    raw = llm.invoke(
        GRADE_SYSTEM + "\n\n用户问题：" + state["question"] + "\n\n证据段落：\n" + snippets
    )
    text = raw.content if hasattr(raw, "content") else str(raw)

    grade = "sufficient"
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        try:
            data = json.loads(match.group(0))
            grade = data.get("grade", "sufficient")
        except json.JSONDecodeError:
            pass
    if grade not in ("sufficient", "insufficient"):
        grade = "sufficient"

    state["evidence_grade"] = grade
    return state
