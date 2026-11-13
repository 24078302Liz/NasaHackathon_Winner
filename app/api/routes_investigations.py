"""调查浏览路由：GET /api/investigations 与 /api/investigations/{id}。"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from sqlalchemy import select

from app.api.schemas import InvestigationDetail, InvestigationSummary
from app.retrieval.store import (
    ExperimentalCondition,
    Investigation,
    ReportedFinding,
    SourceDocument,
    get_session,
)

router = APIRouter()


def _summary(row: Investigation) -> InvestigationSummary:
    return InvestigationSummary(
        investigation_id=row.investigation_id,
        title=row.title,
        objective=row.objective,
        research_focus=row.research_focus,
        source_url=row.source_url,
        doi=row.doi,
    )


@router.get("/investigations", response_model=list[InvestigationSummary])
def list_investigations(research_focus: str | None = None):
    session = get_session()
    stmt = select(Investigation)
    if research_focus:
        stmt = stmt.where(Investigation.research_focus == research_focus)
    rows = session.scalars(stmt).all()
    return [_summary(r) for r in rows]


@router.get("/investigations/{investigation_id}", response_model=InvestigationDetail)
def get_investigation(investigation_id: str):
    session = get_session()
    row = session.get(Investigation, investigation_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Investigation not found")

    docs = session.scalars(
        select(SourceDocument).where(SourceDocument.investigation_id == investigation_id)
    ).all()
    tests = session.scalars(
        select(ExperimentalCondition).where(
            ExperimentalCondition.investigation_id == investigation_id
        )
    ).all()
    findings = session.scalars(
        select(ReportedFinding).where(ReportedFinding.investigation_id == investigation_id)
    ).all()

    return InvestigationDetail(
        investigation_id=row.investigation_id,
        title=row.title,
        objective=row.objective,
        research_focus=row.research_focus,
        source_url=row.source_url,
        doi=row.doi,
        documents=[
            {
                "document_id": d.document_id,
                "title": d.title,
                "source_url": d.source_url,
                "license_ref": d.license_ref,
            }
            for d in docs
        ],
        tests=[
            {
                "test_id": t.test_id,
                "material": t.material,
                "sample_geometry": t.sample_geometry,
                "oxygen_value": t.oxygen_value,
                "oxygen_unit": t.oxygen_unit,
                "pressure_value": t.pressure_value,
                "pressure_unit": t.pressure_unit,
                "airflow_value": t.airflow_value,
                "airflow_unit": t.airflow_unit,
                "gravity_condition": t.gravity_condition,
            }
            for t in tests
        ],
        findings=[
            {
                "finding_id": f.finding_id,
                "finding_text": f.finding_text,
                "limitations": f.limitations,
            }
            for f in findings
        ],
    )
