"""搜索路由：POST /api/search。"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.agents.graph import compiled_graph
from app.agents.state import GraphState
from app.api.schemas import SearchRequest, SearchResponse

router = APIRouter()

MAX_QUESTION_LEN = 500


@router.post("/search", response_model=SearchResponse)
async def search(req: SearchRequest):
    question = (req.question or "").strip()
    if not question:
        raise HTTPException(status_code=422, detail="Question must not be empty.")
    if len(question) > MAX_QUESTION_LEN:
        raise HTTPException(
            status_code=422, detail=f"Question too long (max {MAX_QUESTION_LEN})."
        )

    initial: GraphState = {"question": question, "retry_count": 0}
    final = await compiled_graph.ainvoke(initial)

    return SearchResponse(
        answer=final.get("answer", ""),
        citations=final.get("citations", []),
        investigations=final.get("ranked_investigations", []),
        evidence_status=final.get("evidence_status", "unknown"),
    )
