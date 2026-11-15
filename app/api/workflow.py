"""Translate dependency failures into stable API responses."""
import asyncio
import logging

from fastapi import HTTPException

from app.config import settings

logger = logging.getLogger(__name__)


async def run_workflow(graph, initial):
    try:
        return await asyncio.wait_for(
            graph.ainvoke(initial), timeout=settings.workflow_timeout_seconds
        )
    except TimeoutError as exc:
        raise HTTPException(504, "Research request timed out. Please retry.") from exc
    except Exception as exc:
        logger.exception("Research workflow failed")
        raise HTTPException(
            502, "The research service is unavailable. Please retry."
        ) from exc
