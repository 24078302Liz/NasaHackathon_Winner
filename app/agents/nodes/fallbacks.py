"""Fallback responses for insufficient evidence and invalid questions."""
from __future__ import annotations

from app.agents.state import GraphState


def fallback_insufficient(state: GraphState) -> GraphState:
    state["answer"] = (
        "Insufficient evidence in the selected sources to answer this question. "
        "The missing evidence may include: no matching passages for the requested "
        "materials or experimental conditions."
    )
    state["evidence_status"] = "insufficient"
    state["citations"] = []
    state["error"] = None
    return state


def fallback_invalid(state: GraphState) -> GraphState:
    state["answer"] = (
        "Please enter a non-empty question about NASA microgravity combustion research."
    )
    state["evidence_status"] = "invalid"
    state["citations"] = []
    state["error"] = None
    return state
