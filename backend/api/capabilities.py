"""Capability detection used by both the API and the frontend."""

import importlib.util
import os

from changeorder.ocr import ocr_status

from .config import settings
from .models import CapabilitiesResponse, LLMCability, OCRCapability


def capabilities() -> CapabilitiesResponse:
    ocr = ocr_status()
    llm_sdk = importlib.util.find_spec("openai") is not None
    llm_configured = bool(os.environ.get("OPENAI_API_KEY") and os.environ.get("CHANGEORDER_LLM_MODEL"))
    return CapabilitiesResponse(
        service="sledge-change-order-intelligence",
        supported_formats=[".pdf", ".txt", ".png", ".jpg", ".jpeg"],
        supported_media_types=["application/pdf", "text/plain", "image/png", "image/jpeg"],
        max_file_bytes=settings.max_file_bytes,
        max_batch_files=settings.max_batch_files,
        max_batch_bytes=settings.max_batch_bytes,
        max_pages=settings.max_pages,
        ocr=OCRCapability(
            available=ocr.available,
            version=ocr.version,
            languages=list(ocr.languages),
            message=ocr.message,
        ),
        llm=LLMCability(
            available=llm_sdk and llm_configured,
            configured=llm_configured,
            message=(
                "Optional structured provider assistance is configured."
                if llm_sdk and llm_configured
                else "Optional AI assistance is unavailable; local deterministic extraction remains available."
            ),
        ),
        extraction_options=["ocr:off", "ocr:auto", "ocr:force", "date_order:reject", "date_order:mdy", "date_order:dmy"],
    )
