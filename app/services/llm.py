"""LLM 客户端封装：DeepSeek 经 OpenAI 兼容接口。"""
from __future__ import annotations

from langchain_openai import ChatOpenAI

from app.config import settings


def get_llm(
    *,
    model: str | None = None,
    temperature: float = 0.0,
    timeout: float | None = None,
) -> ChatOpenAI:
    """主模型：摘要 / 对比生成。"""
    return ChatOpenAI(
        model=model or settings.llm_model,
        api_key=settings.llm_api_key,
        base_url=settings.llm_base_url,
        temperature=temperature,
        timeout=timeout or settings.llm_timeout_seconds,
        max_retries=1,
    )


def get_small_llm(**kwargs) -> ChatOpenAI:
    """小模型：意图识别 / 证据打分（默认同 DeepSeek 低成本档，可单独配置）。"""
    return get_llm(model=settings.small_model, **kwargs)
