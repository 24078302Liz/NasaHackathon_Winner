"""LLM client factories for DeepSeek through an OpenAI-compatible API."""
from __future__ import annotations

from langchain_openai import ChatOpenAI

from app.config import settings


def get_llm(
    *,
    model: str | None = None,
    temperature: float = 0.0,
    timeout: float | None = None,
) -> ChatOpenAI:
    """Create the model used for answers and comparisons."""
    return ChatOpenAI(
        model=model or settings.llm_model,
        api_key=settings.llm_api_key,
        base_url=settings.llm_base_url,
        temperature=temperature,
        timeout=timeout or settings.llm_timeout_seconds,
        max_retries=1,
    )


def get_small_llm(**kwargs) -> ChatOpenAI:
    """Create the configurable model used for query analysis and evidence grading."""
    return get_llm(model=settings.small_model, **kwargs)
