"""Generate cited answers covering conditions, findings, and interpretation."""
from __future__ import annotations

from app.agents.prompts import GENERATE_ANSWER_SYSTEM
from app.agents.state import GraphState
from app.services.llm import get_llm


def generate_answer(state: GraphState) -> GraphState:
    passages = state.get("passages") or []
    snippets = "\n\n".join(
        f"[{p['evidence_id']}] (material: {p.get('material') or 'unknown'}) {p['text'][:800]}"
        for p in passages[:10]
    )

    llm = get_llm(temperature=0.0)
    prompt = (
        GENERATE_ANSWER_SYSTEM
        + "\n\nUser question: " + state["question"]
        + "\n\nEvidence passages:\n" + snippets
    )
    raw = llm.invoke(prompt)
    answer = raw.content if hasattr(raw, "content") else str(raw)

    state["answer"] = answer
    state["evidence_status"] = "sufficient"
    return state
