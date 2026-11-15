"""Retrieve passages and aggregate investigation rankings."""
from __future__ import annotations

from app.agents.state import GraphState, Passage
from app.config import settings
from app.retrieval.hybrid_search import hybrid_search


def _field(hit, name: str, default=None):
    ent = getattr(hit, "entity", None)
    if isinstance(ent, dict):
        return ent.get(name, default)
    if ent is not None and hasattr(ent, "get"):
        return ent.get(name, default)
    return default


def _score(hit) -> float:
    d = getattr(hit, "distance", None)
    try:
        return float(d) if d is not None else 0.0
    except (TypeError, ValueError):
        return 0.0


def _hit_to_passage(hit) -> Passage:
    return Passage(
        evidence_id=_field(hit, "evidence_id", ""),
        document_id=_field(hit, "document_id", ""),
        investigation_id=_field(hit, "investigation_id", ""),
        test_id=_field(hit, "test_id"),
        text=_field(hit, "text", ""),
        page=_field(hit, "page"),
        source_url=_field(hit, "source_url"),
        retrieval_score=_score(hit),
        material=_field(hit, "material"),
        gravity_condition=_field(hit, "gravity_condition"),
        oxygen_value=_field(hit, "oxygen_value"),
        oxygen_unit=_field(hit, "oxygen_unit"),
        pressure_value=_field(hit, "pressure_value"),
        pressure_unit=_field(hit, "pressure_unit"),
        airflow_value=_field(hit, "airflow_value"),
        airflow_unit=_field(hit, "airflow_unit"),
        research_focus=_field(hit, "research_focus"),
    )


def _rank_investigations(passages: list[Passage]) -> list[dict]:
    """Aggregate passages into the documented investigation ranking records.

    Fields: identity / rank / hits / best_score / score_label /
    matched_evidence_ids / relevance_explanation。
    """
    agg: dict[str, dict] = {}
    for p in passages:
        iid = p["investigation_id"]
        if not iid:
            continue
        a = agg.setdefault(iid, {
            "identity": iid,
            "hits": 0,
            "best_score": 0.0,
            "matched_evidence_ids": [],
            "snippets": [],
        })
        a["hits"] += 1
        a["best_score"] = max(a["best_score"], p["retrieval_score"])
        eid = p.get("evidence_id")
        if eid and eid not in a["matched_evidence_ids"]:
            a["matched_evidence_ids"].append(eid)
        snippet = (p.get("text") or "").strip()
        if snippet and len(a["snippets"]) < 2:
            a["snippets"].append(snippet[:120])

    ranked = sorted(agg.values(), key=lambda x: (-x["hits"], -x["best_score"]))
    result = []
    for rank, r in enumerate(ranked[:3], start=1):
        result.append({
            "identity": r["identity"],
            "investigation_id": r["identity"],  # Compatibility with the frontend field name.
            "rank": rank,
            "hits": r["hits"],
            "best_score": round(r["best_score"], 4),
            "score_label": "retrieval_score",  # Retrieval relevance, not probability.
            "matched_evidence_ids": r["matched_evidence_ids"],
            "relevance_explanation": " | ".join(r["snippets"]),
        })
    return result


def retrieve(state: GraphState) -> GraphState:
    hits = hybrid_search(
        query=state["question"],
        filters=state.get("filters"),
        top_k=settings.top_k,
    )
    passages = [_hit_to_passage(h) for h in hits]
    state["passages"] = passages
    state["ranked_investigations"] = _rank_investigations(passages)
    return state


def retrieve_compare(state: GraphState) -> GraphState:
    """Retrieve evidence separately for each selected investigation."""
    selected = state.get("selected_ids") or []
    passages: list[Passage] = []
    for iid in selected:
        hits = hybrid_search(
            query=state["question"],
            filters={"investigation_id": [iid]},
            top_k=settings.top_k,
        )
        passages.extend(_hit_to_passage(h) for h in hits)
    state["passages"] = passages
    state["ranked_investigations"] = _rank_investigations(passages)
    return state
