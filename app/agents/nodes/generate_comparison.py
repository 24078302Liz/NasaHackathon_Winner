"""对比生成节点：条件差异优先于跨研究结论。"""
from __future__ import annotations

from app.agents.prompts import COMPARE_SYSTEM
from app.agents.state import GraphState
from app.services.llm import get_llm


def _group_by_investigation(passages: list[dict]) -> dict[str, list[dict]]:
    groups: dict[str, list[dict]] = {}
    for p in passages:
        iid = p.get("investigation_id") or "unknown"
        groups.setdefault(iid, []).append(p)
    return groups


def generate_comparison(state: GraphState) -> GraphState:
    groups = _group_by_investigation(state.get("passages") or [])
    selected = state.get("selected_ids") or []

    if len(selected) != 2 or any(not groups.get(iid) for iid in selected):
        state["answer"] = (
            "Insufficient evidence to compare both investigations from the selected sources. "
            "One or both investigations have no retrieved evidence passages."
        )
        state["comparison"] = []
        state["evidence_status"] = "insufficient"
        state["citations"] = []
        return state

    parts = []
    for iid in selected:
        passages = groups[iid]
        snippets = "\n\n".join(f"[{p['evidence_id']}] {p['text'][:600]}" for p in passages[:8])
        parts.append(f"调查 {iid}：\n{snippets}")
    context = "\n\n".join(parts)

    target = " 与 ".join(selected)
    llm = get_llm(temperature=0.0)
    prompt = COMPARE_SYSTEM + "\n\n对比目标：" + target + "\n\n证据段落：\n" + context
    raw = llm.invoke(prompt)
    answer = raw.content if hasattr(raw, "content") else str(raw)

    state["answer"] = answer
    state["comparison"] = []  # API 路由从结构化记录生成可比字段
    state["evidence_status"] = "sufficient"
    return state
