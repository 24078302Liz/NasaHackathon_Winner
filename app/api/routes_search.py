"""搜索路由：POST /api/search。"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.agents.graph import compiled_graph
from app.agents.state import GraphState
from app.api.schemas import SearchRequest, SearchResponse

router = APIRouter()

MAX_QUESTION_LEN = 500


def _build_evidence(passages: list[dict]) -> list[dict]:
    """把检索到的段落转成 Evidence 字段结构。"""
    return [
        {
            "evidence_id": p.get("evidence_id", ""),
            "document_id": p.get("document_id", ""),
            "investigation_id": p.get("investigation_id", ""),
            "text": p.get("text", ""),
            "page": p.get("page"),
            "section": None,
            "test_id": p.get("test_id"),
            "source_url": p.get("source_url"),
            "retrieval_score": p.get("retrieval_score"),
        }
        for p in passages
    ]


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
        question=question,
        answer=final.get("answer", ""),
        investigations=final.get("ranked_investigations", []),
        citations=final.get("citations", []),
        evidence=_build_evidence(final.get("passages", [])),
        evidence_status=final.get("evidence_status", "unknown"),
    )
