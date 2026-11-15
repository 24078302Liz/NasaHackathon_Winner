"""FastAPI application entry point."""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import routes_compare, routes_investigations, routes_search
from app.retrieval.store import init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(title="Flame in Freefall API", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(routes_investigations.router, prefix="/api")
app.include_router(routes_search.router, prefix="/api")
app.include_router(routes_compare.router, prefix="/api")


@app.get("/health")
def health():
    return {"status": "ok"}
