"""Environment-driven API limits and transport settings."""

import os
from dataclasses import dataclass


def _positive_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None:
        return default
    try:
        value = int(raw)
    except ValueError as exc:
        raise RuntimeError(f"{name} must be an integer") from exc
    if value <= 0:
        raise RuntimeError(f"{name} must be positive")
    return value


@dataclass(frozen=True)
class Settings:
    max_file_bytes: int = _positive_int("CHANGEORDER_MAX_FILE_BYTES", 20 * 1024 * 1024)
    max_batch_files: int = _positive_int("CHANGEORDER_MAX_BATCH_FILES", 8)
    max_batch_bytes: int = _positive_int("CHANGEORDER_MAX_BATCH_BYTES", 40 * 1024 * 1024)
    max_pages: int = _positive_int("CHANGEORDER_MAX_PAGES", 100)
    max_chars: int = _positive_int("CHANGEORDER_MAX_CHARS", 500_000)
    max_ocr_pixels: int = _positive_int("CHANGEORDER_MAX_OCR_PIXELS", 20_000_000)
    ocr_timeout: int = _positive_int("CHANGEORDER_OCR_TIMEOUT", 25)
    processing_timeout_seconds: int = _positive_int("CHANGEORDER_PROCESSING_TIMEOUT", 120)
    cors_origins: tuple[str, ...] = tuple(
        origin.strip()
        for origin in os.environ.get(
            "CHANGEORDER_CORS_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000"
        ).split(",")
        if origin.strip()
    )


settings = Settings()
