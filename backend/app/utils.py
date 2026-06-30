"""
utils.py
--------
Shared utility helpers for the AI PDF Chatbot backend.

This module is intentionally thin in Phase 1.  Helper functions that are
needed by multiple routers / services (e.g. response builders, sanitisers,
timing decorators) live here so they are easy to import without creating
circular dependencies.
"""

import logging
import time
from datetime import datetime, timezone
from functools import wraps
from typing import Any, Callable

logger = logging.getLogger(__name__)


# ============================================================ #
# Logging helpers                                               #
# ============================================================ #

def setup_logging(log_level: str = "INFO") -> None:
    """
    Configure root logger with a consistent format.

    Call this once at application start-up (in main.py lifespan) so every
    module that does ``logging.getLogger(__name__)`` inherits the same
    handler and formatter.

    Args:
        log_level: One of DEBUG, INFO, WARNING, ERROR, CRITICAL.
    """
    numeric_level = getattr(logging, log_level.upper(), logging.INFO)
    logging.basicConfig(
        level=numeric_level,
        format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
    )
    logger.debug("Logging initialised at level: %s", log_level.upper())


# ============================================================ #
# Time helpers                                                  #
# ============================================================ #

def utc_now() -> datetime:
    """Return the current UTC datetime (timezone-aware)."""
    return datetime.now(timezone.utc)


def log_execution_time(func: Callable) -> Callable:
    """
    Decorator that logs the wall-clock execution time of any callable.

    Works with both regular functions and ``async`` coroutines.

    Example::

        @log_execution_time
        async def expensive_operation():
            ...
    """
    import asyncio

    @wraps(func)
    async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
        start = time.perf_counter()
        result = await func(*args, **kwargs)
        elapsed = (time.perf_counter() - start) * 1000
        logger.debug("%s completed in %.2f ms", func.__qualname__, elapsed)
        return result

    @wraps(func)
    def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
        start = time.perf_counter()
        result = func(*args, **kwargs)
        elapsed = (time.perf_counter() - start) * 1000
        logger.debug("%s completed in %.2f ms", func.__qualname__, elapsed)
        return result

    if asyncio.iscoroutinefunction(func):
        return async_wrapper
    return sync_wrapper


# ============================================================ #
# String helpers                                                #
# ============================================================ #

def sanitise_question(text: str) -> str:
    """
    Strip leading/trailing whitespace and collapse internal whitespace runs.

    This will be used by the chat endpoint (Phase 2+) to normalise user
    input before it is passed to the LLM.

    Args:
        text: Raw input string from the API consumer.

    Returns:
        Cleaned string.
    """
    import re
    return re.sub(r"\s+", " ", text.strip())
