"""
chatbot.py
----------
Chatbot service layer for the AI PDF Chatbot backend.

Sprint 3 – OpenRouter Integration:
  * get_answer(question) sends the PDF knowledge base + user question to
    OpenRouter via the official OpenAI Python SDK and returns the LLM answer.

Architecture
------------
* The OpenAI SDK is pointed at OpenRouter's base URL so we can swap models
  (GPT-4o, Claude, Mistral…) by changing a single .env variable.
* The PDF text cached by pdf_reader.load_pdf() is injected into the system
  prompt on every call.  This is intentionally simple and correct for a
  single-document knowledge base; chunked retrieval will be added later if
  the document grows beyond the model's context window.
* The function is synchronous (not async) because the OpenAI SDK's sync
  client uses httpx internally and is perfectly safe to call from FastAPI
  route handlers via a thread pool (asyncio.to_thread / run_in_executor).
  Keeping it sync avoids the complexity of managing an async client
  lifecycle outside of FastAPI's DI system.

Error handling
--------------
* AuthenticationError  → API key missing / revoked.
* APITimeoutError      → network too slow or model overloaded.
* APIConnectionError   → no internet / OpenRouter unreachable.
* RateLimitError       → quota exceeded.
* APIStatusError       → any other 4xx / 5xx from OpenRouter.

All errors are logged with full context and re-raised as a uniform
RuntimeError so callers (future route handlers) only need one except clause.
"""

import logging
import time

from openai import (
    APIConnectionError,
    APIStatusError,
    APITimeoutError,
    AuthenticationError,
    OpenAI,
    RateLimitError,
)

from app.config import get_settings
from app.pdf_reader import get_pdf_text

logger = logging.getLogger(__name__)

# ------------------------------------------------------------------ #
# Constants                                                            #
# ------------------------------------------------------------------ #

# Fallback answer when the model cannot find relevant content.
_NOT_FOUND_MSG = (
    "I couldn't find this information in the provided knowledge base."
)

# System prompt template.  The {pdf_text} placeholder is replaced at
# call-time with the cached PDF content.
_SYSTEM_PROMPT_TEMPLATE = """\
You are a helpful AI assistant for an AI knowledge base chatbot.

Your ONLY source of information is the PDF knowledge base text provided below.

Rules you MUST follow:
1. Answer questions SOLELY based on the content of the PDF knowledge base.
2. Do NOT use any external knowledge, training data, or assumptions beyond the provided text.
3. If the answer cannot be found in the PDF knowledge base, respond with EXACTLY:
   "{not_found}"
4. Keep answers clear, concise, and factually grounded in the provided text.
5. Do not mention that you are reading from a PDF or knowledge base in your answer.

--- PDF KNOWLEDGE BASE START ---
{pdf_text}
--- PDF KNOWLEDGE BASE END ---
""".format(
    not_found=_NOT_FOUND_MSG,
    pdf_text="{pdf_text}",   # left as a named placeholder for .format() below
)


# ============================================================ #
# Public API                                                    #
# ============================================================ #

def get_answer(question: str) -> str:
    """
    Generate an answer for *question* using the PDF knowledge base.

    The function:
    1. Fetches the cached PDF text from ``pdf_reader.get_pdf_text()``.
    2. Builds a system prompt that constrains the LLM to the PDF content.
    3. Sends the messages to OpenRouter via the OpenAI SDK.
    4. Returns the model's text response as a plain string.

    Args:
        question: The user's question (should already be sanitised by
                  the calling layer via ``utils.sanitise_question``).

    Returns:
        The LLM's answer as a string.  Never returns ``None``; on any
        failure a descriptive ``RuntimeError`` is raised instead.

    Raises:
        RuntimeError: Wraps all OpenAI / network errors with a
                      human-readable message and a structured log entry.
    """
    settings = get_settings()

    # ---- Guard: API key must be present ----------------------------- #
    if not settings.OPENROUTER_API_KEY:
        logger.error(
            "OPENROUTER_API_KEY is not set. "
            "Add it to your .env file before using the chat feature."
        )
        raise RuntimeError(
            "OpenRouter API key is missing. "
            "Set OPENROUTER_API_KEY in your .env file."
        )

    # ---- Guard: PDF must be loaded ---------------------------------- #
    try:
        pdf_text = get_pdf_text()
    except RuntimeError as exc:
        logger.error(
            "Cannot answer question – PDF knowledge base is not loaded: %s", exc
        )
        raise RuntimeError(
            "PDF knowledge base is not available. "
            "Ensure the server started correctly and the PDF file exists."
        ) from exc

    # ---- Build client (lightweight; no persistent connection pool) -- #
    client = OpenAI(
        api_key=settings.OPENROUTER_API_KEY,
        base_url=settings.OPENROUTER_BASE_URL,
        timeout=settings.REQUEST_TIMEOUT,
    )

    # ---- Compose messages ------------------------------------------- #
    system_prompt = _SYSTEM_PROMPT_TEMPLATE.format(pdf_text=pdf_text)

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user",   "content": question},
    ]

    logger.info(
        "Sending request to OpenRouter | model=%s | question_chars=%d | pdf_chars=%d",
        settings.OPENROUTER_MODEL,
        len(question),
        len(pdf_text),
    )

    start = time.perf_counter()

    # ---- Call OpenRouter -------------------------------------------- #
    try:
        response = client.chat.completions.create(
            model=settings.OPENROUTER_MODEL,
            messages=messages,  # type: ignore[arg-type]
        )

    except AuthenticationError as exc:
        logger.error(
            "OpenRouter authentication failed – check OPENROUTER_API_KEY. "
            "status=%s body=%s",
            exc.status_code,
            exc.body,
        )
        raise RuntimeError(
            "OpenRouter authentication failed. "
            "Verify that OPENROUTER_API_KEY is valid and has not expired."
        ) from exc

    except APITimeoutError as exc:
        elapsed = (time.perf_counter() - start) * 1000
        logger.error(
            "OpenRouter request timed out after %.0f ms (timeout=%.1fs). %s",
            elapsed,
            settings.REQUEST_TIMEOUT,
            exc,
        )
        raise RuntimeError(
            f"The request to OpenRouter timed out after {settings.REQUEST_TIMEOUT}s. "
            "Please try again in a moment."
        ) from exc

    except APIConnectionError as exc:
        logger.error(
            "Could not connect to OpenRouter at %s: %s",
            settings.OPENROUTER_BASE_URL,
            exc,
        )
        raise RuntimeError(
            "Could not reach the OpenRouter API. "
            "Check your internet connection and try again."
        ) from exc

    except RateLimitError as exc:
        logger.warning(
            "OpenRouter rate limit exceeded. status=%s body=%s",
            exc.status_code,
            exc.body,
        )
        raise RuntimeError(
            "OpenRouter rate limit exceeded. "
            "Please wait a moment before sending another request."
        ) from exc

    except APIStatusError as exc:
        logger.error(
            "OpenRouter returned an unexpected error. "
            "status=%s body=%s",
            exc.status_code,
            exc.body,
        )
        raise RuntimeError(
            f"OpenRouter returned an error (HTTP {exc.status_code}). "
            "Please try again later."
        ) from exc

    # ---- Extract answer --------------------------------------------- #
    elapsed = (time.perf_counter() - start) * 1000
    answer: str = response.choices[0].message.content or _NOT_FOUND_MSG
    answer = answer.strip()

    logger.info(
        "OpenRouter response received | model=%s | elapsed_ms=%.0f | "
        "prompt_tokens=%s | completion_tokens=%s | answer_chars=%d",
        response.model,
        elapsed,
        response.usage.prompt_tokens if response.usage else "n/a",
        response.usage.completion_tokens if response.usage else "n/a",
        len(answer),
    )

    return answer
