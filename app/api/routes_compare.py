"""对比路由：POST /api/compare。"""
from __future__ import annotations

import asyncio
import logging

from fastapi import APIRouter, HTTPException
from sqlalchemy import select

from app.agents.graph import compiled_graph
from app.agents.state import GraphState
from app.api.schemas import (
    CompareRequest,
    CompareResponse,
    ComparisonField,
    InvestigationComparison,
)
from app.retrieval.store import (
    ExperimentalCondition,
    Investigation,
    ReportedFinding,
    get_session,
)

router = APIRouter()
logger = logging.getLogger(__name__)

NOT_REPORTED = "Not reported in selected sources"
NOT_YET_EXTRACTED = "Not yet extracted"


def _joined(values: list[str]) -> str:
    cleaned = list(dict.fromkeys(value.strip() for value in values if value and value.strip()))
    return "; ".join(cleaned) if cleaned else NOT_YET_EXTRACTED


def _condition_value(value, unit: str | None) -> str:
    if value is None:
        return NOT_REPORTED
    return f"{value:g} {unit}".strip() if unit else f"{value:g}"


def _comparison_records(ids: list[str], passages: list[dict]) -> list[InvestigationComparison]:
    session = get_session()
    investigations = {
        row.investigation_id: row
        for row in session.scalars(
            select(Investigation).where(Investigation.investigation_id.in_(ids))
        ).all()
    }
    conditions = session.scalars(
        select(ExperimentalCondition).where(ExperimentalCondition.investigation_id.in_(ids))
    ).all()
    findings = session.scalars(
        select(ReportedFinding).where(ReportedFinding.investigation_id.in_(ids))
    ).all()
    conditions_by_id: dict[str, list[ExperimentalCondition]] = {iid: [] for iid in ids}
    findings_by_id: dict[str, list[ReportedFinding]] = {iid: [] for iid in ids}
    for condition in conditions:
        conditions_by_id[condition.investigation_id].append(condition)
    for finding in findings:
        findings_by_id[finding.investigation_id].append(finding)

    output = []
    for iid in ids:
        record = investigations[iid]
        tests = conditions_by_id[iid]
        study_findings = findings_by_id[iid]
        related_passages = [p for p in passages if p.get("investigation_id") == iid]
        evidence_for_test = {
            test_id: [
                p.get("evidence_id") for p in related_passages
                if p.get("test_id") == test_id and p.get("evidence_id")
            ]
            for test_id in {p.get("test_id") for p in related_passages if p.get("test_id")}
        }
        condition_evidence = list(dict.fromkeys(
            evidence_id for ids_for_test in evidence_for_test.values()
            for evidence_id in ids_for_test
        ))

        def field(name: str, value: str, evidence_ids: list[str] | None = None) -> ComparisonField:
            availability = (
                "reported" if value not in (NOT_REPORTED, NOT_YET_EXTRACTED)
                else "not_reported" if value == NOT_REPORTED
                else "not_yet_extracted"
            )
            return ComparisonField(
                name=name,
                value=value,
                availability=availability,
                evidence_ids=evidence_ids or [],
            )

        fields = [
            field("objective", record.objective),
            field("research_focus", record.research_focus),
            field("materials_or_fuels", _joined([t.material for t in tests]), condition_evidence),
            field("sample_geometry", _joined([t.sample_geometry for t in tests]), condition_evidence),
            field("oxygen_concentration", _joined([_condition_value(t.oxygen_value, t.oxygen_unit) for t in tests if t.oxygen_value is not None]), condition_evidence),
            field("pressure", _joined([_condition_value(t.pressure_value, t.pressure_unit) for t in tests if t.pressure_value is not None]), condition_evidence),
            field("airflow", _joined([_condition_value(t.airflow_value, t.airflow_unit) for t in tests if t.airflow_value is not None]), condition_evidence),
            field("gravity_condition", _joined([t.gravity_condition for t in tests]), condition_evidence),
            field("measurements", NOT_YET_EXTRACTED),
            field("reported_findings", _joined([f.finding_text for f in study_findings]), list(dict.fromkeys(
                evidence_id
                for finding in study_findings
                for evidence_id in (finding.supporting_evidence_ids or "").split(",")
                if evidence_id.strip()
            ))),
            field("limitations", _joined([f.limitations or "" for f in study_findings])),
        ]
        output.append(InvestigationComparison(
            investigation_id=iid,
            title=record.title,
            source_url=record.source_url,
            fields=fields,
        ))
    return output


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
    try:
        final = await compiled_graph.ainvoke(initial)
    except (TimeoutError, asyncio.TimeoutError) as exc:
        raise HTTPException(
            status_code=504,
            detail="The comparison service timed out. Your selections are unchanged; please retry.",
        ) from exc
    except Exception as exc:
        logger.exception("Comparison request failed")
        raise HTTPException(
            status_code=502,
            detail="The comparison service is temporarily unavailable. Please retry.",
        ) from exc

    return CompareResponse(
        answer=final.get("answer", ""),
        comparison=_comparison_records([req.id_a, req.id_b], final.get("passages", [])),
        citations=final.get("citations", []),
        evidence_status=final.get("evidence_status", "unknown"),
    )
