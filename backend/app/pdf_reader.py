"""
pdf_reader.py
-------------
PDF reading service for the AI PDF Chatbot backend.

Sprint 2 – PDF Ingestion:
  * load_pdf()     – reads every page with pdfplumber, caches the result.
  * get_pdf_text() – returns the cached text (raises if not yet loaded).

Design decisions
----------------
* **Single load, in-memory cache**: the PDF is opened once at startup and
  the concatenated text is stored in a module-level variable.  Subsequent
  calls to get_pdf_text() are O(1) dictionary lookups with no I/O.
* **Thread-safety**: loading is triggered from the FastAPI lifespan hook
  which runs in a single-threaded startup phase, so no locking is needed.
* **Page separator**: pages are joined with a form-feed (\\f) so downstream
  code can split by page if needed, while the full text is still one string.
* **Graceful degradation**: a missing PDF raises FileNotFoundError (caught
  by the lifespan hook); an empty PDF logs a warning but does not crash.
"""

import logging
import os
from pathlib import Path

import pdfplumber

logger = logging.getLogger(__name__)

# ============================================================ #
# Module-level cache                                            #
# ============================================================ #

# Stores the full extracted text once load_pdf() has been called.
# None means "not yet loaded"; empty-string means "loaded but no text found".
_pdf_text: str | None = None

# Absolute path that was successfully loaded (used in log messages).
_loaded_path: str | None = None


# ============================================================ #
# Public API                                                    #
# ============================================================ #

def load_pdf(path: str) -> None:
    """
    Load and extract text from the PDF at *path* using pdfplumber.

    The extracted text is cached in module memory.  Calling this function
    a second time replaces the cached text (useful for hot-reloads in tests).

    Args:
        path: Filesystem path to the PDF file (absolute or relative to the
              working directory from which uvicorn is launched, i.e. the
              ``backend/`` directory).

    Raises:
        FileNotFoundError: If the file does not exist at *path*.
        RuntimeError:      If pdfplumber cannot open the file.
    """
    global _pdf_text, _loaded_path

    resolved = Path(path).resolve()
    logger.info("Loading PDF knowledge base from: %s", resolved)

    # ---- Guard: file must exist --------------------------------------- #
    if not resolved.is_file():
        logger.error(
            "PDF knowledge base not found at path: %s  "
            "Check KNOWLEDGE_BASE_PATH in your .env file.",
            resolved,
        )
        raise FileNotFoundError(
            f"PDF knowledge base not found: {resolved}\n"
            "Ensure the file exists and KNOWLEDGE_BASE_PATH is set correctly."
        )

    # ---- Extract text page-by-page ------------------------------------ #
    pages: list[str] = []

    try:
        with pdfplumber.open(str(resolved)) as pdf:
            total_pages = len(pdf.pages)
            logger.info("PDF opened successfully | pages=%d", total_pages)

            for page_num, page in enumerate(pdf.pages, start=1):
                page_text = page.extract_text() or ""
                pages.append(page_text)
                logger.debug(
                    "Page %d/%d extracted | chars=%d",
                    page_num,
                    total_pages,
                    len(page_text),
                )

    except Exception as exc:
        logger.exception("Failed to open or read PDF at %s", resolved)
        raise RuntimeError(
            f"Could not read PDF at {resolved}: {exc}"
        ) from exc

    # ---- Join pages with a form-feed separator ----------------------- #
    combined_text = "\f".join(pages)
    total_chars = len(combined_text.replace("\f", ""))

    # ---- Warn if no text was found ------------------------------------ #
    if not combined_text.strip():
        logger.warning(
            "PDF loaded but NO text was extracted from %s. "
            "The file may be scanned/image-based and require OCR.",
            resolved,
        )
    else:
        logger.info(
            "PDF text extraction complete | pages=%d | total_chars=%d",
            total_pages,
            total_chars,
        )

    # ---- Update cache ------------------------------------------------- #
    _pdf_text = combined_text
    _loaded_path = str(resolved)
    logger.info("PDF knowledge base cached in memory.")


def get_pdf_text() -> str:
    """
    Return the full extracted text of the PDF knowledge base.

    Must be called **after** :func:`load_pdf` has completed successfully
    (i.e., during or after the FastAPI startup lifespan hook).

    Returns:
        The complete text of the PDF, with pages separated by a form-feed
        character (``\\f``).  Never returns ``None``.

    Raises:
        RuntimeError: If :func:`load_pdf` has not been called yet.
    """
    if _pdf_text is None:
        raise RuntimeError(
            "PDF knowledge base has not been loaded yet. "
            "Ensure load_pdf() is called during application startup."
        )
    return _pdf_text


def get_pdf_page_count() -> int:
    """
    Return the number of pages that were extracted.

    Useful for health/debug endpoints.

    Returns:
        Number of pages (0 if no text was extracted).

    Raises:
        RuntimeError: If :func:`load_pdf` has not been called yet.
    """
    return get_pdf_text().count("\f") + 1 if get_pdf_text() else 0


def is_pdf_loaded() -> bool:
    """
    Return ``True`` if the PDF has been loaded and cached successfully.

    Safe to call at any time — does not raise.
    """
    return _pdf_text is not None
