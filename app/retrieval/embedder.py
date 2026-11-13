"""稠密向量编码：HuggingFace BGE（默认 BAAI/bge-m3，1024 维）。"""
from __future__ import annotations

from app.config import settings


class Embedder:
    def __init__(self, model_name: str | None = None, device: str | None = None):
        self.model_name = model_name or settings.embedding_model
        self.device = device or settings.embedding_device
        self._model = None

    def _load(self):
        # 延迟导入：sentence-transformers 会拉取 torch，
        # 未安装时不影响其他模块（如 FastAPI 路由）的导入。
        if self._model is None:
            from sentence_transformers import SentenceTransformer

            self._model = SentenceTransformer(self.model_name, device=self.device)
        return self._model

    def encode(self, texts: list[str]) -> list[list[float]]:
        model = self._load()
        embeddings = model.encode(
            texts,
            normalize_embeddings=settings.embedding_normalize,
            show_progress_bar=False,
        )
        return [e.tolist() for e in embeddings]

    def encode_query(self, text: str) -> list[float]:
        return self.encode([text])[0]


# 进程级单例：写入与查询必须使用同一个 embedder 与维度，切换模型需重建集合
embedder = Embedder()
