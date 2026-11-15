"""Milvus 连接与集合访问的单例封装。"""
from __future__ import annotations

from pymilvus import Collection, connections, utility

from app.config import settings
from app.retrieval import schema as milvus_schema


def connect() -> None:
    """幂等地建立到 Milvus 的连接。"""
    try:
        if not connections.has_connection(settings.milvus_alias):
            connections.connect(
                alias=settings.milvus_alias,
                host=settings.milvus_host,
                port=settings.milvus_port,
            )
    except Exception as exc:
        raise RuntimeError(
            f"Failed to connect to Milvus at {settings.milvus_host}:{settings.milvus_port}"
        ) from exc


def get_collection(name: str | None = None, create_if_missing: bool = True) -> Collection:
    """获取（必要时创建并加载）collection。

    检索/写入统一走这里；Milvus 未启动或集合不存在时给出明确错误。
    """
    name = name or settings.milvus_collection
    connect()
    if not utility.has_collection(name):
        if not create_if_missing:
            raise RuntimeError(
                f"Milvus collection '{name}' does not exist. Run `python scripts/ingest.py` first."
            )
        return milvus_schema.create_collection(name)
    col = Collection(name)
    milvus_schema.ensure_indexes(col)  # 幂等补建索引（修复历史 collection 缺 sparse 索引）
    col.load()
    return col
