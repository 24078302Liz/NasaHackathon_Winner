"""Compare experimental conditions before drawing cross-study conclusions."""
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

    # 1. Build structured comparison rows from SQLite condition and finding records.
    structured: list[dict] = []
    if len(selected) == 2:
        from app.retrieval.store import build_structured_comparison

        structured = build_structured_comparison(selected[0], selected[1])

    if len(selected) != 2 or any(not any(p.get("investigation_id") == iid for p in state.get("passages", [])) for iid in selected):
        state["answer"] = "Insufficient retrieved evidence for one or both investigations. Structured records alone do not establish a supported cross-study conclusion."
        state["comparison"] = structured
        state["citations"] = []
        state["evidence_status"] = "insufficient"
        return state

    # 2. Generate a cross-study explanation from retrieved passages.
    groups = _group_by_investigation(state.get("passages") or [])

    parts = []
    for iid, passages in groups.items():
        snippets = "\n\n".join(f"[{p['evidence_id']}] {p['text'][:600]}" for p in passages[:8])
        parts.append(f"Investigation {iid}:\n{snippets}")
    context = "\n\n".join(parts)

    target = " and ".join(selected)
    llm = get_llm(temperature=0.0)
    prompt = COMPARE_SYSTEM + "\n\nComparison targets: " + target + "\n\nEvidence passages:\n" + context
    try:
        raw = llm.invoke(prompt)
        answer = raw.content if hasattr(raw, "content") else str(raw)
    except Exception as exc:
        # Preserve structured rows when model generation fails or times out.
        answer = (
            "Cross-study explanation unavailable because the model failed or timed out. See the comparison field for structured records."
        )

    state["answer"] = answer
    state["comparison"] = structured  # Structured comparison rows (FR04).
    state["evidence_status"] = "sufficient"
    return state
