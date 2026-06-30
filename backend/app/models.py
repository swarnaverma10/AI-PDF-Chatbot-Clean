"""
models.py
---------
Pydantic request and response models for the AI PDF Chatbot API.

All models use strict typing and include field-level documentation so that
FastAPI can auto-generate accurate OpenAPI / Swagger schemas.
"""

from datetime import datetime, timezone
from typing import Optional

from pydantic import BaseModel, Field


# ============================================================ #
# Base model – shared configuration for all models             #
# ============================================================ #

class _BaseSchema(BaseModel):
    """Common Pydantic configuration applied to every schema."""

    model_config = {
        # Populate from ORM attributes (useful in later phases).
        "from_attributes": True,
        # Keep field order as declared.
        "populate_by_name": True,
    }


# ============================================================ #
# Health                                                        #
# ============================================================ #

class HealthResponse(_BaseSchema):
    """Response body for GET /health."""

    status: str = Field(
        default="healthy",
        description="Current health status of the service.",
        examples=["healthy"],
    )
    version: str = Field(
        description="Running application version.",
        examples=["1.0.0"],
    )
    timestamp: datetime = Field(
        description="UTC timestamp of the health check.",
    )


# ============================================================ #
# Welcome                                                       #
# ============================================================ #

class WelcomeResponse(_BaseSchema):
    """Response body for GET /."""

    message: str = Field(
        description="Human-readable welcome message.",
        examples=["Welcome to the AI PDF Chatbot API!"],
    )
    version: str = Field(
        description="Running application version.",
        examples=["1.0.0"],
    )
    docs_url: str = Field(
        description="URL to the interactive API documentation.",
        examples=["/docs"],
    )


# ============================================================ #
# Chat  (stub – wired up in a later phase)                     #
# ============================================================ #

class ChatRequest(_BaseSchema):
    """Request body for the chat endpoint (Phase 2+)."""

    question: str = Field(
        min_length=1,
        max_length=2000,
        description="The user's question to be answered from the knowledge base.",
        examples=["What topics does the knowledge base cover?"],
    )
    session_id: Optional[str] = Field(
        default=None,
        description="Optional session identifier for multi-turn conversations.",
        examples=["sess_abc123"],
    )


class ChatResponse(_BaseSchema):
    """Response body for the chat endpoint (Phase 2+)."""

    answer: str = Field(
        description="The AI-generated answer based on the knowledge base.",
        examples=["The knowledge base covers the following topics…"],
    )
    session_id: Optional[str] = Field(
        default=None,
        description="Echo of the incoming session identifier.",
    )
    sources: list[str] = Field(
        default_factory=list,
        description="List of source references from the PDF (page numbers, sections, etc.).",
    )
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="UTC timestamp of the response.",
    )


# ============================================================ #
# Generic error                                                 #
# ============================================================ #

class ErrorResponse(_BaseSchema):
    """Standard error response returned on API errors."""

    error: str = Field(
        description="Short, machine-readable error code.",
        examples=["internal_server_error"],
    )
    detail: str = Field(
        description="Human-readable description of what went wrong.",
        examples=["An unexpected error occurred. Please try again later."],
    )
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="UTC timestamp of the error.",
    )
