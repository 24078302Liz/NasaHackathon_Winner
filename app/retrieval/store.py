"""结构化数据存储：SQLAlchemy 抽象（当前 SQLite，可切 MySQL）。

Milvus 存证据段落（文本 + 向量），SQLite 存权威结构化数据
（Investigation / SourceDocument / ExperimentalCondition / ReportedFinding）。
切换 MySQL 只需改 DATABASE_URL，无需改业务代码。
"""
from __future__ import annotations

from sqlalchemy import Float, ForeignKey, String, Text, create_engine, select
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker

from app.config import settings


class Base(DeclarativeBase):
    pass


class Investigation(Base):
    __tablename__ = "investigations"

    investigation_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    title: Mapped[str] = mapped_column(String(256))
    objective: Mapped[str] = mapped_column(Text)
    research_focus: Mapped[str] = mapped_column(String(128))
    source_url: Mapped[str] = mapped_column(String(512))
    doi: Mapped[str | None] = mapped_column(String(128), nullable=True)


class SourceDocument(Base):
    __tablename__ = "source_documents"

    document_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    investigation_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("investigations.investigation_id")
    )
    title: Mapped[str] = mapped_column(String(256))
    source_url: Mapped[str] = mapped_column(String(512))
    local_filename: Mapped[str] = mapped_column(String(256))
    retrieval_date: Mapped[str] = mapped_column(String(32))
    license_ref: Mapped[str | None] = mapped_column(String(256), nullable=True)


class ExperimentalCondition(Base):
    __tablename__ = "experimental_conditions"

    test_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    investigation_id: Mapped[str] = mapped_column(String(64))
    material: Mapped[str] = mapped_column(String(128))
    sample_geometry: Mapped[str | None] = mapped_column(String(256), nullable=True)
    oxygen_value: Mapped[float | None] = mapped_column(Float, nullable=True)
    oxygen_unit: Mapped[str | None] = mapped_column(String(16), nullable=True)
    pressure_value: Mapped[float | None] = mapped_column(Float, nullable=True)
    pressure_unit: Mapped[str | None] = mapped_column(String(16), nullable=True)
    airflow_value: Mapped[float | None] = mapped_column(Float, nullable=True)
    airflow_unit: Mapped[str | None] = mapped_column(String(16), nullable=True)
    gravity_condition: Mapped[str] = mapped_column(String(64))
    flow_direction: Mapped[str | None] = mapped_column(String(32), nullable=True)
    extra_params: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON 存实验特定参数


class ReportedFinding(Base):
    __tablename__ = "reported_findings"

    finding_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    investigation_id: Mapped[str] = mapped_column(String(64))
    test_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    finding_text: Mapped[str] = mapped_column(Text)
    supporting_evidence_ids: Mapped[str] = mapped_column(Text)  # 逗号分隔的 evidence_id
    limitations: Mapped[str | None] = mapped_column(Text, nullable=True)


_connect_args = (
    {"check_same_thread": False}
    if settings.database_url.startswith("sqlite")
    else {}
)
engine = create_engine(settings.database_url, connect_args=_connect_args, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


def init_db() -> None:
    """创建表；SQLite 场景自动创建数据库文件所在目录（避免 data/ 不存在时报错）。"""
    if settings.database_url.startswith("sqlite:///"):
        import os

        db_path = settings.database_url[len("sqlite:///"):]
        parent = os.path.dirname(db_path)
        if parent:
            os.makedirs(parent, exist_ok=True)
    Base.metadata.create_all(engine)
    _migrate_schema(engine)


def _migrate_schema(engine) -> None:
    """轻量迁移：为已存在的表补缺失列（SQLite 的 create_all 不会改已有表）。"""
    from sqlalchemy import inspect, text

    inspector = inspect(engine)
    if "experimental_conditions" not in inspector.get_table_names():
        return
    existing = {c["name"] for c in inspector.get_columns("experimental_conditions")}
    with engine.connect() as conn:
        for col, dtype in (("flow_direction", "VARCHAR(32)"), ("extra_params", "TEXT")):
            if col not in existing:
                conn.execute(text(f"ALTER TABLE experimental_conditions ADD COLUMN {col} {dtype}"))
        conn.commit()


def get_session():
    return SessionLocal()


NOT_REPORTED = "Not reported in selected sources"


def _fmt_measure(value, unit) -> str | None:
    if value is None:
        return None
    return f"{value} {unit}" if unit else str(value)


def build_structured_comparison(id_a: str, id_b: str) -> list[dict]:
    """生成两个调查的结构化对比行（FR04），缺失字段标 Not reported。

    返回列表，每行 {dimension, <id_a>: 值, <id_b>: 值}。
    """
    session = get_session()
    inv_a = session.get(Investigation, id_a)
    inv_b = session.get(Investigation, id_b)
    conds_a = session.scalars(
        select(ExperimentalCondition).where(ExperimentalCondition.investigation_id == id_a)
    ).all()
    conds_b = session.scalars(
        select(ExperimentalCondition).where(ExperimentalCondition.investigation_id == id_b)
    ).all()
    findings_a = session.scalars(
        select(ReportedFinding).where(ReportedFinding.investigation_id == id_a)
    ).all()
    findings_b = session.scalars(
        select(ReportedFinding).where(ReportedFinding.investigation_id == id_b)
    ).all()

    def materials(conds):
        ms = sorted({c.material for c in conds if c.material})
        return ", ".join(ms) if ms else NOT_REPORTED

    def agg(conds, field, unit_field):
        vals = []
        seen = set()
        for c in conds:
            v = _fmt_measure(getattr(c, field), getattr(c, unit_field))
            if v and v not in seen:
                seen.add(v)
                vals.append(v)
        if not vals:
            return NOT_REPORTED
        if len(vals) > 5:
            return ", ".join(vals[:5]) + f" 等 {len(vals)} 个值"
        return ", ".join(vals)

    def findings_text(findings):
        if not findings:
            return NOT_REPORTED
        return "; ".join(f.finding_text for f in findings)

    return [
        {"dimension": "objectives",
         id_a: inv_a.objective if inv_a else NOT_REPORTED,
         id_b: inv_b.objective if inv_b else NOT_REPORTED},
        {"dimension": "fuels / materials",
         id_a: materials(conds_a), id_b: materials(conds_b)},
        {"dimension": "oxygen concentration",
         id_a: agg(conds_a, "oxygen_value", "oxygen_unit"),
         id_b: agg(conds_b, "oxygen_value", "oxygen_unit")},
        {"dimension": "pressure",
         id_a: agg(conds_a, "pressure_value", "pressure_unit"),
         id_b: agg(conds_b, "pressure_value", "pressure_unit")},
        {"dimension": "airflow",
         id_a: agg(conds_a, "airflow_value", "airflow_unit"),
         id_b: agg(conds_b, "airflow_value", "airflow_unit")},
        {"dimension": "findings",
         id_a: findings_text(findings_a), id_b: findings_text(findings_b)},
    ]


def upsert_conditions(conditions: list[dict]) -> int:
    """写入/更新实验条件记录（幂等，按 test_id upsert，批内去重）。"""
    session = get_session()
    seen: dict[str, dict] = {}
    for c in conditions:
        seen[c["test_id"]] = c  # 同 test_id 保留最后一条
    for c in seen.values():
        existing = session.get(ExperimentalCondition, c["test_id"])
        if existing is None:
            session.add(ExperimentalCondition(**c))
        else:
            for k, v in c.items():
                setattr(existing, k, v)
    session.commit()
    return len(seen)
