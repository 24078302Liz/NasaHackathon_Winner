"""Manage Milvus connections and collection access."""
from __future__ import annotations

from pymilvus import Collection, connections, utility

from app.config import settings
from app.retrieval import schema as milvus_schema


def connect() -> None:
    """Establish a Milvus connection if one does not already exist."""
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
    """Get a collection, optionally creating and loading it.

    Retrieval and ingestion share this function; missing infrastructure raises an explicit error.
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
    milvus_schema.ensure_indexes(col)  # Add missing indexes to existing collections.
    col.load()
    return col
