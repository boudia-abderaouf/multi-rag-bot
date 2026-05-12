from __future__ import annotations

from fastapi import FastAPI

from api.routes.ask import router as ask_router
from api.routes.health import router as health_router
from api.routes.ingest import router as ingest_router


def register_routers(app: FastAPI) -> None:
    for router in (health_router, ask_router, ingest_router):
        app.include_router(router)
