"""搜索路由：POST /api/search。"""
from __future__ import annotations

import asyncio
import logging

from fastapi import APIRouter, HTTPException
from sqlalchemy import select

from app.agents.graph import compiled_graph
from app.agents.state import GraphState
from app.api.schemas import EvidencePassage, RankedInvestigation, SearchRequest, SearchResponse
from app.retrieval.store import Investigation, get_session

router = APIRouter()
logger = logging.getLogger(__name__)

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
    try:
        final = await compiled_graph.ainvoke(initial)
    except (TimeoutError, asyncio.TimeoutError) as exc:
        raise HTTPException(
            status_code=504,
            detail="The research service timed out. Your question is unchanged; please retry.",
        ) from exc
    except Exception as exc:
        logger.exception("Search request failed")
        raise HTTPException(
            status_code=502,
            detail="The research service is temporarily unavailable. Please retry.",
        ) from exc

    passages = final.get("passages", [])
    evidence = [
        EvidencePassage(
            evidence_id=p.get("evidence_id", ""),
            document_id=p.get("document_id", ""),
            investigation_id=p.get("investigation_id", ""),
            test_id=p.get("test_id"),
            page=p.get("page"),
            source_url=p.get("source_url"),
            text=p.get("text", ""),
            retrieval_score=p.get("retrieval_score"),
        )
        for p in passages
        if p.get("evidence_id")
    ]

    ranks = final.get("ranked_investigations", [])
    ranked_ids = [item.get("investigation_id") for item in ranks if item.get("investigation_id")]
    session = get_session()
    records = session.scalars(
        select(Investigation).where(Investigation.investigation_id.in_(ranked_ids))
    ).all() if ranked_ids else []
    by_id = {record.investigation_id: record for record in records}
    ranked = []
    for rank, item in enumerate(ranks, start=1):
        iid = item.get("investigation_id")
        record = by_id.get(iid)
        if record is None:
            continue
        matching = [p for p in passages if p.get("investigation_id") == iid]
        hits = int(item.get("hits", len(matching)))
        best_score = float(item.get("best_score", 0.0))
        ranked.append(RankedInvestigation(
            investigation_id=iid,
            title=record.title,
            objective=record.objective,
            research_focus=record.research_focus,
            source_url=record.source_url,
            doi=record.doi,
            rank=rank,
            hits=hits,
            best_score=best_score,
            matched_evidence_ids=[p.get("evidence_id", "") for p in matching if p.get("evidence_id")],
            relevance_explanation=(
                f"Ranked by retrieved evidence: {hits} matching passage(s); "
                f"best retrieval score {best_score:.4f}. The score indicates retrieval relevance, "
                "not answer confidence or fire risk."
            ),
        ))

    return SearchResponse(
        question=question,
        answer=final.get("answer", ""),
        citations=final.get("citations", []),
        evidence=evidence,
        investigations=ranked,
        evidence_status=final.get("evidence_status", "unknown"),
    )
