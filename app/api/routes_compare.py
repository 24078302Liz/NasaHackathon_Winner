"""对比路由：POST /api/compare。"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from sqlalchemy import select

from app.agents.graph import compiled_graph
from app.agents.state import GraphState
from app.api.schemas import CompareRequest, CompareResponse
from app.retrieval.store import Investigation, get_session

router = APIRouter()


@router.post("/compare", response_model=CompareResponse)
async def compare(req: CompareRequest):
    if not req.id_a or not req.id_b:
        raise HTTPException(status_code=422, detail="Both id_a and id_b are required.")
    if req.id_a == req.id_b:
        raise HTTPException(status_code=422, detail="id_a and id_b must be distinct.")

    session = get_session()
    existing = set(session.scalars(select(Investigation.investigation_id)).all())
    if req.id_a not in existing or req.id_b not in existing:
        raise HTTPException(status_code=404, detail="One or both investigations not found.")

    initial: GraphState = {
        # 直接注入对比意图，入口路由会跳到 retrieve_compare，跳过意图识别
        "question": req.focus or f"Compare {req.id_a} and {req.id_b}",
        "question_type": "compare",
        "selected_ids": [req.id_a, req.id_b],
        "retry_count": 0,
    }
    final = await compiled_graph.ainvoke(initial)

    return CompareResponse(
        answer=final.get("answer", ""),
        comparison=final.get("comparison", []),
        citations=final.get("citations", []),
        evidence_status=final.get("evidence_status", "unknown"),
    )
