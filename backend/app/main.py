"""
main.py
-------
FastAPI application entry point for the AI PDF Chatbot backend.

Sprint 1 – FastAPI Foundation:
  * Application factory with lifespan context manager.
  * CORS middleware configured for Unity development.
  * GET /        → welcome message.
  * GET /health  → service health check.
  * Structured logging throughout.

Sprint 2 – PDF Ingestion:
  * PDF knowledge base loaded once at startup via pdf_reader.load_pdf().
  * Extracted text cached in memory for zero-latency access.
  * FileNotFoundError handled gracefully – server still starts.
"""

import logging
from contextlib import asynccontextmanager
from datetime import timezone, datetime
from typing import AsyncIterator

import uvicorn
from fastapi import FastAPI, Request, status, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import get_settings
from app.models import ErrorResponse, HealthResponse, WelcomeResponse, ChatRequest, ChatResponse
from app.utils import setup_logging, utc_now, sanitise_question
import app.pdf_reader as pdf_reader
import app.chatbot as chatbot

# ------------------------------------------------------------------ #
# Bootstrap logging before anything else runs.                        #
# get_settings() is safe to call here because the .env is at the      #
# project root and uvicorn is launched from that same directory.       #
# ------------------------------------------------------------------ #
_settings = get_settings()
setup_logging(_settings.LOG_LEVEL)

logger = logging.getLogger(__name__)


# ============================================================ #
# Lifespan – startup / shutdown hooks                           #
# ============================================================ #

@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """
    FastAPI lifespan context manager.

    Startup sequence
    ----------------
    1. Log application boot metadata.
    2. Load and cache the PDF knowledge base (Sprint 2).
       - FileNotFoundError → logged as CRITICAL; server still starts so
         the /health endpoint remains reachable for diagnostics.
       - Any other exception → re-raised, which aborts startup.

    Shutdown sequence
    -----------------
    1. Log shutdown message.
    Sprint 3+ will close any open HTTP clients here.
    """
    logger.info(
        "Starting %s v%s | debug=%s",
        _settings.APP_NAME,
        _settings.APP_VERSION,
        _settings.DEBUG,
    )
    logger.info("Allowed CORS origins: %s", _settings.ALLOWED_ORIGINS)

    # ---- Sprint 2: Load PDF knowledge base ------------------------- #
    try:
        pdf_reader.load_pdf(_settings.KNOWLEDGE_BASE_PATH)
    except FileNotFoundError as exc:
        # Non-fatal: log clearly and continue so /health stays up.
        logger.critical(
            "PDF knowledge base could not be loaded: %s  "
            "Chat endpoints will be unavailable until the file is present "
            "and the server is restarted.",
            exc,
        )
    except Exception as exc:
        # Fatal: unexpected error during PDF parsing – abort startup.
        logger.exception("Unexpected error while loading PDF: %s", exc)
        raise
    # ---------------------------------------------------------------- #

    # ---- Sprint 3+ hooks go here ----------------------------------- #
    # e.g. openrouter_client = httpx.AsyncClient(...)
    # ---------------------------------------------------------------- #

    yield  # Application is running

    logger.info("Shutting down %s …", _settings.APP_NAME)
    # ---- Sprint 3+ cleanup goes here ------------------------------- #
    # e.g. await openrouter_client.aclose()
    # ---------------------------------------------------------------- #


# ============================================================ #
# Application factory                                           #
# ============================================================ #

def create_app() -> FastAPI:
    """
    Construct and configure the FastAPI application.

    Returns:
        Configured FastAPI instance.
    """
    app = FastAPI(
        title=_settings.APP_NAME,
        version=_settings.APP_VERSION,
        description=_settings.APP_DESCRIPTION,
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        lifespan=lifespan,
    )

    # ---------------------------------------------------------------- #
    # CORS Middleware                                                    #
    # Allows Unity WebGL builds and the Unity editor to reach the API   #
    # during development.  Tighten allowed_origins before production.   #
    # ---------------------------------------------------------------- #
    app.add_middleware(
        CORSMiddleware,
        allow_origins=_settings.ALLOWED_ORIGINS,
        allow_credentials=True,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["*"],
    )

    # ---------------------------------------------------------------- #
    # Exception handlers                                               #
    # ---------------------------------------------------------------- #
    @app.exception_handler(HTTPException)
    async def http_exception_handler(
        request: Request, exc: HTTPException
    ) -> JSONResponse:
        if exc.status_code == 400:
            err_type = "bad_request"
        elif exc.status_code == 503:
            err_type = "service_unavailable"
        else:
            err_type = "http_error"

        error = ErrorResponse(
            error=err_type,
            detail=exc.detail,
            timestamp=utc_now(),
        )
        return JSONResponse(
            status_code=exc.status_code,
            content=error.model_dump(mode="json"),
        )

    @app.exception_handler(Exception)
    async def global_exception_handler(
        request: Request, exc: Exception
    ) -> JSONResponse:

        logger.exception(
            "Unhandled exception on %s %s",
            request.method,
            request.url.path,
        )
        error = ErrorResponse(
            error="internal_server_error",
            detail="An unexpected error occurred. Please try again later.",
            timestamp=utc_now(),
        )
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=error.model_dump(mode="json"),
        )

    # ---------------------------------------------------------------- #
    # Routes                                                            #
    # ---------------------------------------------------------------- #
    _register_routes(app)

    return app


# ============================================================ #
# Route registration                                            #
# ============================================================ #

def _register_routes(app: FastAPI) -> None:
    """Attach all route handlers to *app*."""

    @app.get(
        "/",
        response_model=WelcomeResponse,
        summary="Welcome",
        tags=["General"],
    )
    async def root() -> WelcomeResponse:
        """
        Welcome endpoint.

        Returns a friendly greeting and points consumers to the API docs.
        """
        logger.debug("GET / called")
        return WelcomeResponse(
            message=f"Welcome to the {_settings.APP_NAME} API!",
            version=_settings.APP_VERSION,
            docs_url="/docs",
        )

    @app.get(
        "/health",
        response_model=HealthResponse,
        summary="Health Check",
        tags=["General"],
    )
    async def health_check() -> HealthResponse:
        """
        Health-check endpoint.

        Returns ``{"status": "healthy"}`` together with the current
        application version and a UTC timestamp.  Use this endpoint for
        load-balancer / container orchestration health probes.

        The ``status`` field reflects PDF readiness:
        - ``"healthy"``         – server up, PDF loaded.
        - ``"degraded"``        – server up, PDF not yet loaded
                                  (missing file or startup error).
        """
        logger.debug("GET /health called")
        pdf_ready = pdf_reader.is_pdf_loaded()
        status_str = "healthy" if pdf_ready else "degraded"
        if not pdf_ready:
            logger.warning(
                "Health check returning 'degraded': PDF knowledge base is not loaded."
            )
        return HealthResponse(
            status=status_str,
            version=_settings.APP_VERSION,
            timestamp=utc_now(),
        )

    @app.post(
        "/chat",
        response_model=ChatResponse,
        summary="Chat with PDF Knowledge Base",
        tags=["Chat"],
        responses={
            status.HTTP_400_BAD_REQUEST: {"model": ErrorResponse},
            status.HTTP_503_SERVICE_UNAVAILABLE: {"model": ErrorResponse},
            status.HTTP_500_INTERNAL_SERVER_ERROR: {"model": ErrorResponse},
        },
    )
    async def chat(request: ChatRequest) -> ChatResponse:
        """
        Ask a question based on the cached PDF knowledge base.
        
        The endpoint will sanitise input, validate that it is not empty,
        and call the OpenRouter integration to produce a response.
        """
        import time
        import asyncio

        # Log incoming request (avoid raw print, print summary)
        logger.info(
            "POST /chat | question_len=%d | session_id=%s",
            len(request.question),
            request.session_id,
        )

        # Trim leading/trailing spaces and collapse whitespaces
        sanitised_question = sanitise_question(request.question)

        # Validate that the question is not empty
        if not sanitised_question:
            logger.warning("POST /chat | validation failed | empty question")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Question cannot be empty or whitespace-only.",
            )

        start_time = time.perf_counter()

        try:
            # Run the synchronous chatbot API call inside a thread pool
            # to keep the FastAPI main async event loop fully responsive.
            answer = await asyncio.to_thread(chatbot.get_answer, sanitised_question)

            elapsed = (time.perf_counter() - start_time) * 1000
            logger.info("POST /chat | success | elapsed_ms=%.2f", elapsed)

            return ChatResponse(
                answer=answer,
                session_id=request.session_id,
                sources=[],  # Sources to be implemented in a later phase if required
                timestamp=utc_now(),
            )

        except RuntimeError as exc:
            elapsed = (time.perf_counter() - start_time) * 1000
            logger.error(
                "POST /chat | chatbot/AI service error | elapsed_ms=%.2f | error=%s",
                elapsed,
                exc,
            )
            # Map all chatbot/pdf/API runtime errors to 503 Service Unavailable
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=str(exc),
            )

        except Exception as exc:
            elapsed = (time.perf_counter() - start_time) * 1000
            logger.exception(
                "POST /chat | unhandled exception | elapsed_ms=%.2f",
                elapsed,
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="An unexpected error occurred. Please try again later.",
            )


# ============================================================ #
# Application instance (module-level for uvicorn / gunicorn)   #
# ============================================================ #

app: FastAPI = create_app()


# ============================================================ #
# Development entry point                                       #
# ============================================================ #

if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host=_settings.HOST,
        port=_settings.PORT,
        reload=_settings.DEBUG,
        log_level=_settings.LOG_LEVEL.lower(),
    )
