"""应用配置：统一从环境变量 / .env 读取。

所有配置项在此集中定义，通过 `settings` 单例访问。
凭证一律走环境变量，不提交到 Git（见 .env.example）。
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

    # ── LLM（DeepSeek，OpenAI 兼容接口）──
    llm_base_url: str = "https://api.deepseek.com/v1"
    llm_api_key: str = ""
    llm_model: str = "deepseek-chat"        # 生成/摘要/对比 主模型
    small_model: str = "deepseek-chat"      # 意图识别 / 证据打分 小模型
    llm_timeout_seconds: float = 45.0
    cors_allowed_origins: list[str] = [
        "https://winner-flame-in-freefall.vercel.app",
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ]

    # ── Embedding（HuggingFace BGE）──
    embedding_model: str = "BAAI/bge-m3"
    embedding_dim: int = 1024
    embedding_device: str = "cpu"
    embedding_normalize: bool = True

    # ── Milvus ──
    milvus_host: str = "localhost"
    milvus_port: int = 19530
    milvus_collection: str = "flame_evidence"
    milvus_alias: str = "default"

    # ── 结构化存储（SQLite；经 SQLAlchemy 可切 MySQL）──
    database_url: str = "sqlite:///./data/flame.db"

    # ── 检索 ──
    top_k: int = 10
    retrieval_score_threshold: float = 0.0  # 段落检索分数低于此值视为弱证据


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
