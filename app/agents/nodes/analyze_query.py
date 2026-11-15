"""Classify queries and extract filters and investigation IDs."""
from __future__ import annotations

import json
import re

from app.agents.prompts import QUERY_ANALYSIS_SYSTEM
from app.agents.state import GraphState
from app.services.llm import get_small_llm

VALID_INVESTIGATION_IDS = {"BASS", "BASS-II", "BASS-M", "Saffire"}


def _parse_json(text: str) -> dict:
    """Extract a JSON object from model output, tolerating surrounding text."""
    text = text.strip()
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            pass
    return {}


def analyze_query(state: GraphState) -> GraphState:
    question = state["question"]

    llm = get_small_llm(temperature=0.0)
    raw = llm.invoke(QUERY_ANALYSIS_SYSTEM + "\n\nUser question: " + question)
    content = raw.content if hasattr(raw, "content") else str(raw)
    parsed = _parse_json(content)

    qtype = parsed.get("question_type", "search")
    if qtype not in ("search", "compare", "invalid"):
        qtype = "search"

    filters = parsed.get("filters") or {}
    selected_ids = [i for i in (parsed.get("selected_ids") or []) if i in VALID_INVESTIGATION_IDS]

    if qtype == "compare" and len(selected_ids) != 2:
        # Fall back to search when a comparison lacks two valid investigation IDs.
        qtype = "search"

    state["question_type"] = qtype
    state["filters"] = filters
    state["selected_ids"] = selected_ids
    return state
