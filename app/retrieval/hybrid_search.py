"""Combine dense semantic retrieval and sparse BM25 retrieval with reciprocal-rank fusion."""
from __future__ import annotations

import json

from pymilvus import AnnSearchRequest, RRFRanker

from app.config import settings
from app.retrieval.embedder import embedder
from app.retrieval.milvus_client import get_collection

OUTPUT_FIELDS = [
    "evidence_id",
    "document_id",
    "investigation_id",
    "test_id",
    "text",
    "material",
    "gravity_condition",
    "oxygen_value",
    "oxygen_unit",
    "pressure_value",
    "pressure_unit",
    "airflow_value",
    "airflow_unit",
    "research_focus",
    "page",
    "source_url",
]


def build_filter_expr(filters: dict | None) -> str | None:
    """Build deterministic Milvus filter expressions from structured filters."""
    if not filters:
        return None
    parts: list[str] = []
    if filters.get("investigation_id"):
        values = filters["investigation_id"]
        if isinstance(values, str):
            values = [values]
        ids = ",".join(json.dumps(str(i)) for i in values)
        parts.append(f"investigation_id in [{ids}]")
    if filters.get("material"):
        parts.append(f'material == {json.dumps(str(filters["material"]))}')
    if filters.get("research_focus"):
        parts.append(f'research_focus == {json.dumps(str(filters["research_focus"]))}')
    if filters.get("gravity_condition"):
        parts.append(f'gravity_condition == {json.dumps(str(filters["gravity_condition"]))}')
    return " and ".join(parts) if parts else None


def hybrid_search(
    query: str,
    filters: dict | None = None,
    top_k: int | None = None,
    rerank_k: int = 60,
):
    """Return the retrieved pymilvus hits."""
    top_k = top_k or settings.top_k
    collection = get_collection()

    dense_vec = embedder.encode_query(query)
    expr = build_filter_expr(filters)

    dense_req = AnnSearchRequest(
        data=[dense_vec],
        anns_field="dense_vector",
        param={"metric_type": "COSINE", "params": {"nprobe": 16}},
        limit=top_k,
        expr=expr,
    )
    sparse_req = AnnSearchRequest(
        data=[query],  # BM25 processes the query text.
        anns_field="sparse_vector",
        param={"metric_type": "BM25"},  # BM25-generated fields require the BM25 metric.
        limit=top_k,
        expr=expr,
    )

    hits = collection.hybrid_search(
        reqs=[dense_req, sparse_req],
        rerank=RRFRanker(k=rerank_k),
        limit=top_k,
        output_fields=OUTPUT_FIELDS,
    )
    return hits[0] if hits else []
