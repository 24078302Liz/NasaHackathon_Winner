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

    parts = []
    for iid, passages in groups.items():
        snippets = "\n\n".join(f"[{p['evidence_id']}] {p['text'][:600]}" for p in passages[:8])
        parts.append(f"调查 {iid}：\n{snippets}")
    context = "\n\n".join(parts)

    target = " 与 ".join(state.get("selected_ids") or [])
    llm = get_llm(temperature=0.0)
    prompt = COMPARE_SYSTEM + "\n\n对比目标：" + target + "\n\n证据段落：\n" + context
    raw = llm.invoke(prompt)
    answer = raw.content if hasattr(raw, "content") else str(raw)

    state["answer"] = answer
    state["comparison"] = [{"raw": answer}]  # 结构化行由前端/后续解析
    state["evidence_status"] = "sufficient"
    return state
