"""Safe upload validation and calls into the canonical extraction pipeline."""

from __future__ import annotations

import hashlib
import re
import tempfile
from dataclasses import dataclass
from pathlib import Path

from changeorder.pipeline import PipelineOptions, extract
from changeorder.readers import SUPPORTED_SUFFIXES, ReaderOptions
from changeorder.schemas import ExtractionResult

from .config import settings
from .models import ExtractionOptions


class ApiInputError(ValueError):
    def __init__(self, code: str, message: str, status_code: int = 400):
        super().__init__(message)
        self.code = code
        self.status_code = status_code


@dataclass(frozen=True)
class UploadedDocument:
    filename: str
    content_type: str | None
    payload: bytes


def safe_filename(filename: str | None) -> str:
    candidate = Path(filename or "upload").name.replace("\x00", "")
    candidate = re.sub(r"[^A-Za-z0-9._ -]", "_", candidate).strip(" .")
    if not candidate or candidate in {".", ".."}:
        raise ApiInputError("INVALID_FILENAME", "The uploaded filename is invalid", 400)
    return candidate[:180]


def _content_matches(filename: str, payload: bytes) -> bool:
    suffix = Path(filename).suffix.lower()
    if suffix == ".pdf":
        return payload.startswith(b"%PDF-")
    if suffix == ".png":
        return payload.startswith(b"\x89PNG\r\n\x1a\n")
    if suffix in {".jpg", ".jpeg"}:
        return payload.startswith(b"\xff\xd8\xff")
    if suffix == ".txt":
        try:
            payload.decode("utf-8-sig")
        except UnicodeDecodeError:
            return False
        return b"\x00" not in payload
    return False


def validate_upload(
    filename: str | None, content_type: str | None, payload: bytes
) -> UploadedDocument:
    name = safe_filename(filename)
    suffix = Path(name).suffix.lower()
    if suffix not in SUPPORTED_SUFFIXES:
        raise ApiInputError("UNSUPPORTED_FORMAT", "Supported files are PDF, TXT, PNG and JPEG", 415)
    if not payload:
        raise ApiInputError("EMPTY_INPUT", "The uploaded file is empty", 400)
    if len(payload) > settings.max_file_bytes:
        raise ApiInputError(
            "INPUT_LIMIT", "The uploaded file exceeds the configured byte limit", 413
        )
    if not _content_matches(name, payload):
        raise ApiInputError(
            "MIME_MISMATCH", "The filename extension does not match the file content", 415
        )
    allowed_types = {
        ".pdf": {"application/pdf", "application/octet-stream"},
        ".txt": {"text/plain", "application/octet-stream"},
        ".png": {"image/png", "application/octet-stream"},
        ".jpg": {"image/jpeg", "application/octet-stream"},
        ".jpeg": {"image/jpeg", "application/octet-stream"},
    }
    if content_type and content_type not in allowed_types[suffix]:
        raise ApiInputError(
            "MIME_MISMATCH", "The declared media type does not match the file extension", 415
        )
    return UploadedDocument(name, content_type, payload)


def pipeline_options(options: ExtractionOptions) -> PipelineOptions:
    return PipelineOptions(
        reader=ReaderOptions(
            ocr=options.ocr,
            max_bytes=settings.max_file_bytes,
            max_pages=settings.max_pages,
            max_chars=settings.max_chars,
            ocr_timeout=settings.ocr_timeout,
            max_ocr_pixels=settings.max_ocr_pixels,
        ),
        date_order=options.date_order,
        llm=options.llm,
    )


def process_upload(document: UploadedDocument, options: ExtractionOptions) -> ExtractionResult:
    """Write only to a private temporary directory and invoke the existing engine."""
    with tempfile.TemporaryDirectory(prefix="changeorder-api-") as directory:
        path = Path(directory) / document.filename
        path.write_bytes(document.payload)
        result = extract(path, options=pipeline_options(options))
    return result


def fingerprint(document: UploadedDocument) -> str:
    return hashlib.sha256(document.payload).hexdigest()
