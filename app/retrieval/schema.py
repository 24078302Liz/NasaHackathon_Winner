"""Milvus collection schema：证据段落 + 稠密/稀疏双向量 + 结构化过滤字段。

- dense_vector：BGE 稠密向量（语义）
- sparse_vector：Milvus 内置 BM25 function 自动生成（关键词）
- 结构化实验条件：数值与单位分列，避免单位丢失（PRD 9）；可空字段用 nullable=True，
  未报告的条件存 null 而不是编造的默认值。
"""
from __future__ import annotations

from pymilvus import (
    Collection,
    CollectionSchema,
    DataType,
    FieldSchema,
    Function,
    FunctionType,
)

from app.config import settings

DENSE_INDEX_PARAMS = {"M": 16, "efConstruction": 200}
SPARSE_INDEX_PARAMS = {"index_type": "SPARSE_INVERTED_INDEX", "metric_type": "BM25"}


def ensure_indexes(col: Collection) -> None:
    """确保 dense 与 sparse 索引存在（幂等）。

    注意：BM25 function 的输出字段，索引 metric_type 必须是 BM25（不是 IP）。
    """
    existing = {idx.field_name for idx in col.indexes}
    if "dense_vector" not in existing:
        col.create_index(
            "dense_vector",
            {"index_type": "HNSW", "metric_type": "COSINE", "params": DENSE_INDEX_PARAMS},
        )
    if "sparse_vector" not in existing:
        col.create_index("sparse_vector", SPARSE_INDEX_PARAMS)


def create_collection(name: str | None = None) -> Collection:
    name = name or settings.milvus_collection

    fields = [
        FieldSchema(name="evidence_id", dtype=DataType.VARCHAR, is_primary=True, max_length=64),
        FieldSchema(name="document_id", dtype=DataType.VARCHAR, max_length=64),
        FieldSchema(name="investigation_id", dtype=DataType.VARCHAR, max_length=64),
        FieldSchema(name="test_id", dtype=DataType.VARCHAR, max_length=64, nullable=True),
        # 文本字段开启 analyzer，供 BM25 function 生成稀疏向量
        FieldSchema(name="text", dtype=DataType.VARCHAR, max_length=8192, enable_analyzer=True),
        FieldSchema(name="dense_vector", dtype=DataType.FLOAT_VECTOR, dim=settings.embedding_dim),
        FieldSchema(name="sparse_vector", dtype=DataType.SPARSE_FLOAT_VECTOR),
        # 结构化实验条件（数值 + 单位分列；未报告存 null）
        FieldSchema(name="material", dtype=DataType.VARCHAR, max_length=128, nullable=True),
        FieldSchema(name="gravity_condition", dtype=DataType.VARCHAR, max_length=64, nullable=True),
        FieldSchema(name="oxygen_value", dtype=DataType.FLOAT, nullable=True),
        FieldSchema(name="oxygen_unit", dtype=DataType.VARCHAR, max_length=16, nullable=True),
        FieldSchema(name="pressure_value", dtype=DataType.FLOAT, nullable=True),
        FieldSchema(name="pressure_unit", dtype=DataType.VARCHAR, max_length=16, nullable=True),
        FieldSchema(name="airflow_value", dtype=DataType.FLOAT, nullable=True),
        FieldSchema(name="airflow_unit", dtype=DataType.VARCHAR, max_length=16, nullable=True),
        FieldSchema(name="research_focus", dtype=DataType.VARCHAR, max_length=128, nullable=True),
        # provenance（溯源）
        FieldSchema(name="page", dtype=DataType.VARCHAR, max_length=64, nullable=True),
        FieldSchema(name="source_url", dtype=DataType.VARCHAR, max_length=512, nullable=True),
    ]

    bm25 = Function(
        name="text_bm25",
        function_type=FunctionType.BM25,
        input_field_names=["text"],
        output_field_names=["sparse_vector"],
    )

    schema = CollectionSchema(
        fields=fields,
        description="Flame in Freefall evidence passages (hybrid search)",
        functions=[bm25],
    )
    col = Collection(name=name, schema=schema)

    ensure_indexes(col)
    col.load()
    return col
