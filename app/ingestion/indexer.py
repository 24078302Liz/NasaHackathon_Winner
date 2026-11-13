"""写 Milvus + SQLite：证据段落向量化入库、结构化数据写入。"""
from __future__ import annotations

from app.retrieval.embedder import embedder
from app.retrieval.milvus_client import get_collection
from app.retrieval.store import Investigation, SourceDocument, get_session

# 三个调查的种子元数据。source_url 需在语料接入阶段按 NASA 官方资源人工核对（PRD 8）。
SEED_INVESTIGATIONS = [
    {
        "investigation_id": "BASS",
        "title": "Burning and Suppression of Solids (BASS)",
        "objective": (
            "Examine the burning and extinction characteristics of solid fuel samples in "
            "microgravity to guide strategies for extinguishing accidental fires in spacecraft."
        ),
        "research_focus": "fire suppression",
        "source_url": "https://www.nasa.gov/mission/station/research-explorer/investigation/",
        "doi": None,
    },
    {
        "investigation_id": "BASS-II",
        "title": "Burning and Suppression of Solids - II (BASS-II)",
        "objective": (
            "Examine burning and extinction characteristics of a wide variety of fuel samples "
            "in microgravity; guide strategies for materials flammability screening for spacecraft."
        ),
        "research_focus": "flammability",
        "source_url": "https://psi.nasa.gov/physci/repo/data/investigations/PSI-25",
        "doi": None,
    },
    {
        "investigation_id": "BASS-M",
        "title": "Burning and Suppression of Solids - Milliken (BASS-M)",
        "objective": (
            "Test flame-retardant-treated cotton textiles at various air flow rates in "
            "microgravity; evaluate self-extinguish behavior compared to terrestrial behavior."
        ),
        "research_focus": "flame retardant",
        "source_url": "https://www.nasa.gov/mission/station/research-explorer/investigation/",
        "doi": None,
    },
]


def seed_investigations() -> None:
    session = get_session()
    for s in SEED_INVESTIGATIONS:
        if session.get(Investigation, s["investigation_id"]) is None:
            session.add(Investigation(**s))
    session.commit()


def upsert_document(
    *,
    document_id: str,
    investigation_id: str,
    title: str,
    source_url: str,
    local_filename: str,
    retrieval_date: str,
    license_ref: str | None = None,
) -> None:
    session = get_session()
    existing = session.get(SourceDocument, document_id)
    if existing is None:
        session.add(
            SourceDocument(
                document_id=document_id,
                investigation_id=investigation_id,
                title=title,
                source_url=source_url,
                local_filename=local_filename,
                retrieval_date=retrieval_date,
                license_ref=license_ref,
            )
        )
    else:
        existing.investigation_id = investigation_id
        existing.title = title
        existing.source_url = source_url
        existing.local_filename = local_filename
        existing.retrieval_date = retrieval_date
        existing.license_ref = license_ref
    session.commit()


def insert_passages(passages: list[dict]) -> int:
    """向量化并写入 Milvus；sparse_vector 由 BM25 function 自动生成。"""
    if not passages:
        return 0
    col = get_collection()
    dense = embedder.encode([p["text"] for p in passages])

    rows = []
    for p, vec in zip(passages, dense):
        rows.append({
            "evidence_id": p["evidence_id"],
            "document_id": p["document_id"],
            "investigation_id": p["investigation_id"],
            "test_id": p.get("test_id"),
            "text": p["text"],
            "dense_vector": vec,
            "material": p.get("material"),
            "gravity_condition": p.get("gravity_condition"),
            "oxygen_value": p.get("oxygen_value"),
            "oxygen_unit": p.get("oxygen_unit"),
            "pressure_value": p.get("pressure_value"),
            "pressure_unit": p.get("pressure_unit"),
            "airflow_value": p.get("airflow_value"),
            "airflow_unit": p.get("airflow_unit"),
            "research_focus": p.get("research_focus"),
            "page": p.get("page"),
            "source_url": p.get("source_url"),
        })

    col.insert(rows)
    col.flush()
    return len(rows)
