from __future__ import annotations

from pathlib import Path

from project_bootstrap import PROJECT_ROOT, configure_project_path

configure_project_path()

from config.settings import Settings, settings
from generation.openai_responder import OpenAIResponder
from retrieval.retriever import Retriever


def get_settings() -> Settings:
    return settings


def get_project_root() -> Path:
    return PROJECT_ROOT


def get_domains_dir() -> Path:
    return PROJECT_ROOT / "domains"


def get_retriever() -> Retriever:
    return Retriever()


def get_responder() -> OpenAIResponder:
    return OpenAIResponder.from_settings(settings)
