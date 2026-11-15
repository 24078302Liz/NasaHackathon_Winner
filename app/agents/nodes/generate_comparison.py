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
    selected = state.get("selected_ids") or []

    # 1. 结构化对比行（纯代码，读 SQLite 的 ExperimentalCondition / ReportedFinding）
    structured: list[dict] = []
    if len(selected) == 2:
        from app.retrieval.store import build_structured_comparison

        structured = build_structured_comparison(selected[0], selected[1])

    # 2. LLM 基于检索证据生成跨研究结论文字
    groups = _group_by_investigation(state.get("passages") or [])

    parts = []
    for iid, passages in groups.items():
        snippets = "\n\n".join(f"[{p['evidence_id']}] {p['text'][:600]}" for p in passages[:8])
        parts.append(f"调查 {iid}：\n{snippets}")
    context = "\n\n".join(parts)

    target = " 与 ".join(selected)
    llm = get_llm(temperature=0.0)
    prompt = COMPARE_SYSTEM + "\n\n对比目标：" + target + "\n\n证据段落：\n" + context
    try:
        raw = llm.invoke(prompt)
        answer = raw.content if hasattr(raw, "content") else str(raw)
    except Exception as exc:
        # LLM 超时/失败时，结构化对比行（FR04 核心）仍然返回，结论文字降级
        answer = (
            "跨研究结论生成失败（LLM 不可用或超时）。结构化对比见 comparison 字段。"
        )

    state["answer"] = answer
    state["comparison"] = structured  # 结构化对比行（FR04）
    state["evidence_status"] = "sufficient"
    return state
