"""写 Milvus + SQLite：证据段落向量化入库、结构化数据写入。"""
from __future__ import annotations

import csv
import json
import re

from app.retrieval.embedder import embedder
from app.retrieval.milvus_client import get_collection
from app.retrieval.store import (
    ExperimentalCondition,
    Investigation,
    SourceDocument,
    get_session,
    upsert_conditions,
)

# 三个调查的种子元数据。source_url 需在语料接入阶段按 NASA 官方资源人工核对（PRD 8）。
SEED_INVESTIGATIONS = [
    {
        "investigation_id": "Fire-Incidents",
        "title": "Spacecraft Fire Incidents",
        "objective": (
            "Historical spacecraft fire and accident cases (Apollo 1, Apollo 13, Mir station fire) "
            "providing background for fire safety in spaceflight."
        ),
        "research_focus": "fire incidents",
        "source_url": "https://www.nasa.gov/",
        "doi": None,
    },
    {
        "investigation_id": "Fire-Equipment",
        "title": "Fire Safety Equipment",
        "objective": (
            "Fire detection and firefighting equipment for spacecraft: fire detectors, "
            "fireman air tanks, and fire-resistant attire."
        ),
        "research_focus": "fire safety equipment",
        "source_url": "https://www.nasa.gov/",
        "doi": None,
    },
    {
        "investigation_id": "Saffire",
        "title": "Spacecraft Fire Experiment (Saffire)",
        "objective": (
            "Large-scale fire-safety experiments on uncrewed ISS cargo vehicles studying "
            "flame spread and flammability in realistic spacecraft environments."
        ),
        "research_focus": "fire safety",
        "source_url": "https://psi.nasa.gov/physci/repo/data/investigations/PSI-98",
        "doi": None,
    },
    {
        "investigation_id": "FLEX",
        "title": "Flame Extinguishment Experiment (FLEX)",
        "objective": (
            "Study flame extinguishment of liquid fuel droplets in microgravity, "
            "including limiting oxygen indices and suppressant effectiveness."
        ),
        "research_focus": "fire suppression",
        "source_url": "https://psi.nasa.gov/physci/repo/data/investigations/PSI-69",
        "doi": None,
    },
    {
        "investigation_id": "SAME-R",
        "title": "Smoke Aerosol Measurement Experiment (SAME-R)",
        "objective": (
            "Measure smoke and aerosol properties produced by spacecraft materials "
            "burning in reduced gravity."
        ),
        "research_focus": "smoke aerosol",
        "source_url": "https://psi.nasa.gov/physci/repo/data/investigations/PSI-101",
        "doi": None,
    },
    {
        "investigation_id": "Combustion-Guide",
        "title": "Combustion in Reduced Gravity (ISS Researcher's Guide)",
        "objective": (
            "Overview of combustion research on the ISS, summarizing experiments including "
            "BASS, BASS-II, FLEX, Saffire, SLICE, BRE, and related microgravity combustion studies."
        ),
        "research_focus": "overview",
        "source_url": "https://www.nasa.gov/mission/station/research-explorer/investigation/",
        "doi": None,
    },
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

    col.upsert(rows)
    col.flush()
    return len(rows)


def _parse_number(s: str | None) -> float | None:
    """解析数值：处理范围 "21.5 - 21.7"（取中间值）、约数 "~ 21.5"、空值。"""
    if s is None:
        return None
    s = s.strip().replace("~", "").replace("≈", "").replace(",", "")
    if not s:
        return None
    m = re.match(r"^([\d.]+)\s*[-–]\s*([\d.]+)$", s)
    if m:
        return (float(m.group(1)) + float(m.group(2))) / 2
    try:
        return float(s)
    except ValueError:
        return None


COLUMN_KEYWORDS = {
    "sample": ("test #", "test number", "sample number", "sample #", "sample id"),
    "material": ("material", "sample type", "fuel"),
    "oxygen": ("o2", "oxygen", "o initial"),
    "airflow": ("air flow", "inlet velocity", "air display", "fan display", "velocity"),
    "pressure": ("pressure",),
    "thickness": ("thickness",),
    "length": ("length",),
    "width": ("width",),
}


def _norm_key(s: str) -> str:
    return (s or "").strip().lstrip("\ufeff").lower()


def _find_col(columns: list[str], keywords: tuple[str, ...]) -> str | None:
    """按关键词（小写子串）找列名，返回第一个匹配的列。"""
    for kw in keywords:
        for c in columns:
            if kw in _norm_key(c):
                return c
    return None


def parse_experiment_csv(
    path: str,
    *,
    investigation_id: str,
    gravity_condition: str = "microgravity",
) -> list[dict]:
    """解析 PSI 实验表 CSV，返回 ExperimentalCondition dict 列表。

    用关键词模糊匹配列名（不同实验的 CSV 列名不同），提取核心字段
    （material / oxygen / airflow / geometry），其余列存 extra_params JSON。
    """
    conditions: list[dict] = []
    with open(path, encoding="utf-8-sig", errors="replace", newline="") as f:
        reader = csv.DictReader(f)
        for raw in reader:
            row = {_norm_key(k): (v or "").strip() for k, v in raw.items()}
            cols = list(row.keys())

            sample_col = _find_col(cols, COLUMN_KEYWORDS["sample"])
            material_col = _find_col(cols, COLUMN_KEYWORDS["material"])
            airflow_col = _find_col(cols, COLUMN_KEYWORDS["airflow"])
            o2_col = _find_col(cols, COLUMN_KEYWORDS["oxygen"])
            pressure_col = _find_col(cols, COLUMN_KEYWORDS["pressure"])

            sample = row.get(sample_col or "", "")
            material = row.get(material_col or "", "")
            airflow = row.get(airflow_col or "", "")
            o2 = row.get(o2_col or "", "")
            pressure = row.get(pressure_col or "", "")

            if not sample or (not airflow and not o2 and not pressure):
                continue  # 跳过注释行

            o2_col_name = _norm_key(o2_col or "")
            oxygen_unit = (
                "%" if ("%" in o2_col_name or "percent" in o2_col_name or "by vol" in o2_col_name)
                else None
            )

            geom_parts = []
            for dim in ("thickness", "length", "width"):
                c = _find_col(cols, COLUMN_KEYWORDS[dim])
                v = row.get(c or "", "")
                if v:
                    geom_parts.append(f"{dim} {v}")
            geometry = ", ".join(geom_parts) if geom_parts else None

            mapped = {sample_col, material_col, airflow_col, o2_col, pressure_col}
            extra = {k: v for k, v in row.items() if v and k not in mapped}
            if o2 and ("-" in o2 or "~" in o2 or "≈" in o2):
                extra["oxygen raw"] = o2

            conditions.append({
                "test_id": f"{investigation_id}-{sample}",
                "investigation_id": investigation_id,
                "material": material or "Not reported",
                "sample_geometry": geometry,
                "oxygen_value": _parse_number(o2),
                "oxygen_unit": oxygen_unit,
                "pressure_value": _parse_number(pressure),
                "pressure_unit": None,
                "airflow_value": _parse_number(airflow),
                "airflow_unit": None,
                "gravity_condition": gravity_condition,
                "flow_direction": None,
                "extra_params": json.dumps(extra, ensure_ascii=False) if extra else None,
            })
    return conditions


def ingest_experiment_table(
    path: str,
    *,
    investigation_id: str,
    gravity_condition: str = "microgravity",
) -> int:
    """解析实验表 CSV 并写入 SQLite ExperimentalCondition 表。"""
    conditions = parse_experiment_csv(
        path,
        investigation_id=investigation_id,
        gravity_condition=gravity_condition,
    )
    return upsert_conditions(conditions)
