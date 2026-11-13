"""结构化数据存储：SQLAlchemy 抽象（当前 SQLite，可切 MySQL）。

Milvus 存证据段落（文本 + 向量），SQLite 存权威结构化数据
（Investigation / SourceDocument / ExperimentalCondition / ReportedFinding）。
切换 MySQL 只需改 DATABASE_URL，无需改业务代码。
"""
from __future__ import annotations

from sqlalchemy import Float, ForeignKey, String, Text, create_engine
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
    sample_geometry: Mapped[str] = mapped_column(String(256))
    oxygen_value: Mapped[float | None] = mapped_column(Float, nullable=True)
    oxygen_unit: Mapped[str | None] = mapped_column(String(16), nullable=True)
    pressure_value: Mapped[float | None] = mapped_column(Float, nullable=True)
    pressure_unit: Mapped[str | None] = mapped_column(String(16), nullable=True)
    airflow_value: Mapped[float | None] = mapped_column(Float, nullable=True)
    airflow_unit: Mapped[str | None] = mapped_column(String(16), nullable=True)
    gravity_condition: Mapped[str] = mapped_column(String(64))


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


def get_session():
    return SessionLocal()
