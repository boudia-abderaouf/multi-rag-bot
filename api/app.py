from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.routes import register_routers
from config.settings import settings


def create_app() -> FastAPI:
    app = FastAPI(
        title="Multi RAG Bot API",
        version="0.1.0",
        summary="Backend HTTP API for the multi-domain RAG system.",
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.webapp_cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    register_routers(app)
    return app
