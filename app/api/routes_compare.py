"""Comparison endpoint: POST /api/compare."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from sqlalchemy import select

from app.agents.graph import compiled_graph
from app.agents.state import GraphState
from app.api.schemas import CompareRequest, CompareResponse
from app.api.workflow import run_workflow
from app.retrieval.store import Investigation, get_session

router = APIRouter()


@router.post("/compare", response_model=CompareResponse)
async def compare(req: CompareRequest):
    if not req.id_a or not req.id_b:
        raise HTTPException(status_code=422, detail="Both id_a and id_b are required.")
    if req.id_a == req.id_b:
        raise HTTPException(status_code=422, detail="id_a and id_b must be distinct.")

    with get_session() as session:
        id_map = {i.lower(): i for i in session.scalars(select(Investigation.investigation_id)).all()}
    if req.id_a.lower() not in id_map or req.id_b.lower() not in id_map:
        raise HTTPException(status_code=404, detail="One or both investigations not found.")
    id_a = id_map[req.id_a.lower()]
    id_b = id_map[req.id_b.lower()]

    initial: GraphState = {
        # Inject comparison intent and IDs to skip query classification.
        "question": req.focus or f"Compare {id_a} and {id_b}",
        "question_type": "compare",
        "selected_ids": [id_a, id_b],
        "retry_count": 0,
    }
    final = await run_workflow(compiled_graph, initial)

    return CompareResponse(
        answer=final.get("answer", ""),
        comparison=final.get("comparison", []),
        citations=final.get("citations", []),
        evidence_status=final.get("evidence_status", "unknown"),
    )
