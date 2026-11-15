"""Central application settings loaded from environment variables and .env.

Access settings through the shared settings instance.
Keep credentials in environment variables and out of Git; see .env.example.
"""
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # LLM (DeepSeek through an OpenAI-compatible API)
    llm_base_url: str = "https://api.deepseek.com/v1"
    llm_api_key: str = ""
    llm_model: str = "deepseek-chat"        # Answer and comparison generation model.
    small_model: str = "deepseek-chat"      # Query analysis and evidence grading model.
    llm_timeout_seconds: float = 45.0

    # ── Embedding（HuggingFace BGE）──
    embedding_model: str = "BAAI/bge-m3"
    embedding_dim: int = 1024
    embedding_device: str = "cpu"
    embedding_normalize: bool = True

    # Unstructured hosted API settings
    unstructured_api_key: str = ""
    unstructured_api_url: str = ""   # Empty uses the provider default endpoint.

    # ── Milvus ──
    milvus_host: str = "localhost"
    milvus_port: int = 19530
    milvus_collection: str = "flame_evidence"
    milvus_alias: str = "default"

    # Structured storage (SQLite by default; SQLAlchemy supports other databases)
    database_url: str = "sqlite:///./data/flame.db"

    # Retrieval
    top_k: int = 10
    retrieval_score_threshold: float = 0.0  # Scores below this threshold indicate weak evidence.


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
