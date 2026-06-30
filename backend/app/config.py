"""
config.py
---------
Centralised configuration loader for the AI PDF Chatbot backend.
All environment variables are loaded from the .env file via python-dotenv
and exposed as a strongly-typed Settings object (Pydantic BaseSettings).
"""

import logging
from functools import lru_cache
from typing import List

from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)


class Settings(BaseSettings):
    """Application settings loaded from environment variables / .env file."""

    # ------------------------------------------------------------------ #
    # Application metadata
    # ------------------------------------------------------------------ #
    APP_NAME: str = "AI PDF Chatbot"
    APP_VERSION: str = "1.0.0"
    APP_DESCRIPTION: str = (
        "A FastAPI backend that answers questions from a PDF knowledge base "
        "using the OpenRouter API."
    )
    DEBUG: bool = False

    # ------------------------------------------------------------------ #
    # Server
    # ------------------------------------------------------------------ #
    HOST: str = "0.0.0.0"
    PORT: int = 8000

    # ------------------------------------------------------------------ #
    # CORS – origins that are allowed to reach the API.
    # In development we permit localhost (Unity editor default port) and
    # common browser-preview ports.  Set this to your production domain
    # in the .env file before deploying.
    # ------------------------------------------------------------------ #
    ALLOWED_ORIGINS: List[str] = [
        "http://localhost",
        "http://localhost:3000",
        "http://localhost:8080",   # Unity WebGL default dev server
        "http://127.0.0.1",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:8080",
    ]

    # ------------------------------------------------------------------ #
    # OpenRouter (wired up in a later phase)
    # ------------------------------------------------------------------ #
    OPENROUTER_API_KEY: str = ""
    OPENROUTER_BASE_URL: str = "https://openrouter.ai/api/v1"
    OPENROUTER_MODEL: str = "openai/gpt-3.5-turbo"

    # ------------------------------------------------------------------ #
    # PDF knowledge base (wired up in a later phase)
    # ------------------------------------------------------------------ #
    KNOWLEDGE_BASE_PATH: str = "knowledge_base/AI_Knowledge_Base.pdf"

    # ------------------------------------------------------------------ #
    # Logging
    # ------------------------------------------------------------------ #
    LOG_LEVEL: str = "INFO"
    
    # ---- Request Timeout (Phase 3+) ------------------------------------- #
    REQUEST_TIMEOUT: float = 30.0

    # Pydantic-settings v2 configuration
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """
    Return a cached singleton Settings instance.

    Using lru_cache ensures the .env file is read exactly once and the
    same object is reused across the entire application lifetime.
    """
    settings = Settings()
    logger.info(
        "Configuration loaded | app=%s version=%s debug=%s",
        settings.APP_NAME,
        settings.APP_VERSION,
        settings.DEBUG,
    )
    return settings


# Convenience alias – import this anywhere in the app.
settings: Settings = get_settings()
