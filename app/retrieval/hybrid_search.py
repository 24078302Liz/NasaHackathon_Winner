"""混合检索：稠密（语义）+ 稀疏（BM25 关键词）双路召回 + RRF 重排。"""
from __future__ import annotations

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
    """把结构化过滤条件转成 Milvus 布尔表达式（确定性过滤，不依赖向量）。"""
    if not filters:
        return None
    parts: list[str] = []
    if filters.get("investigation_id"):
        ids = ",".join(f'"{i}"' for i in filters["investigation_id"])
        parts.append(f"investigation_id in [{ids}]")
    if filters.get("material"):
        parts.append(f'material == "{filters["material"]}"')
    if filters.get("research_focus"):
        parts.append(f'research_focus == "{filters["research_focus"]}"')
    if filters.get("gravity_condition"):
        parts.append(f'gravity_condition == "{filters["gravity_condition"]}"')
    return " and ".join(parts) if parts else None


def hybrid_search(
    query: str,
    filters: dict | None = None,
    top_k: int | None = None,
    rerank_k: int = 60,
):
    """返回命中段落列表（pymilvus 的 hits）。"""
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
        data=[query],  # BM25 function 按全文解析 query
        anns_field="sparse_vector",
        param={"metric_type": "IP"},
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
