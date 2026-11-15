"""FastAPI application entry point."""
from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import Response

from app.api import routes_compare, routes_investigations, routes_search
from app.retrieval.store import init_db
from app.config import settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(title="Flame in Freefall API", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(routes_investigations.router, prefix="/api")
app.include_router(routes_search.router, prefix="/api")
app.include_router(routes_compare.router, prefix="/api")


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/api-config.js", include_in_schema=False)
def api_config():
    return Response("window.FLAME_SAME_ORIGIN = true;", media_type="application/javascript")


# Mount after API routes so a single server can serve both the UI and API.
frontend_dir = Path(__file__).resolve().parent.parent / "frontend"
if frontend_dir.is_dir():
    app.mount("/", StaticFiles(directory=frontend_dir, html=True), name="frontend")
