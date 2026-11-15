"""Encode dense embeddings with HuggingFace BGE; default BGE-M3 uses 1024 dimensions."""
from __future__ import annotations

from app.config import settings


class Embedder:
    def __init__(self, model_name: str | None = None, device: str | None = None):
        self.model_name = model_name or settings.embedding_model
        self.device = device or settings.embedding_device
        self._model = None

    def _load(self):
        # Import sentence-transformers and its torch dependency lazily.
        # Other modules can load before the embedding package is installed.
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


# Shared embedder: ingestion and retrieval must use the same model and dimensions. Rebuild the collection when changing them.
embedder = Embedder()
