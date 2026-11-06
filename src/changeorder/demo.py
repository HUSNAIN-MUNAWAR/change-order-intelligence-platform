"""Presentation adapters only. All extraction, validation and scoring stay in the pipeline."""

import hashlib
import json
import os
import tempfile
import zipfile
from dataclasses import asdict, dataclass
from datetime import date
from decimal import Decimal
from io import BytesIO
from pathlib import Path

from .jsonio import dumps
from .pipeline import PipelineOptions, extract
from .readers import SUPPORTED_SUFFIXES, ReaderOptions
from .schemas import ChangeOrder, ExtractionResult

HIGH_CONFIDENCE = 0.90
MEDIUM_CONFIDENCE = 0.70
MAX_BATCH_DOCUMENTS = 8
MAX_BATCH_BYTES = 40 * 1024 * 1024
FIELD_GROUPS = {
    "Document information": ("change_order_number", "document_title", "document_date", "revision"),
    "Project details": ("project_name", "project_number"),
    "Parties": ("contractor", "subcontractor", "owner", "architect_engineer"),
    "Scope of change": ("description", "reason", "discipline", "referenced_documents"),
    "Financial information": (
        "total_change_amount",
        "amount_basis",
        "currency",
        "requested_amount",
        "proposed_amount",
        "approved_amount",
        "final_amount",
        "previous_contract_amount",
        "revised_contract_amount",
        "credits_deductions",
        "line_items",
    ),
    "Schedule impact": ("schedule_impact", "schedule_unit", "proposed_completion_date"),
    "Approval details": ("approval_status", "approval_date", "approver_name"),
}


class DemoInputError(ValueError):
    """Safe user-facing input/preview error, without document contents or traceback."""


@dataclass(frozen=True)
class DocumentInput:
    name: str
    payload: bytes

    @property
    def safe_name(self) -> str:
        return Path(self.name.replace("\\", "/")).name or "upload.txt"


def validate_inputs(documents: list[DocumentInput]) -> None:
    if not documents:
        raise DemoInputError("Select an example or upload a document first.")
    if (
        len(documents) > MAX_BATCH_DOCUMENTS
        or sum(len(doc.payload) for doc in documents) > MAX_BATCH_BYTES
    ):
        raise DemoInputError("Use at most 8 documents and 40 MiB combined per run.")
    for document in documents:
        if Path(document.safe_name).suffix.lower() not in SUPPORTED_SUFFIXES:
            raise DemoInputError("Upload PDF, UTF-8 TXT, PNG or JPEG files.")
        if len(document.payload) > ReaderOptions().max_bytes:
            raise DemoInputError("Each document must be 20 MiB or smaller.")


def input_signature(documents: list[DocumentInput], options: PipelineOptions) -> str:
    digest = hashlib.sha256(json.dumps(asdict(options), sort_keys=True).encode())
    for document in documents:
        digest.update(json.dumps([document.safe_name, len(document.payload)]).encode())
        digest.update(document.payload)
    return digest.hexdigest()


def process_document(document: DocumentInput, options: PipelineOptions) -> ExtractionResult:
    validate_inputs([document])
    with tempfile.TemporaryDirectory(prefix="changeorder-") as directory:
        path = Path(directory) / document.safe_name
        path.write_bytes(document.payload)
        return extract(path, options=options)


def json_payload(result: ExtractionResult) -> bytes:
    return dumps(result).encode("utf-8")


def zip_payload(results: list[ExtractionResult]) -> bytes:
    buffer = BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for index, result in enumerate(results, 1):
            filename = Path(result.source.identifier.replace("\\", "/")).name
            archive.writestr(f"{index:02}_{filename}.json", json_payload(result))
    return buffer.getvalue()


def confidence_band(confidence: float, missing: bool = False) -> str:
    if missing:
        return "Missing"
    return (
        "High"
        if confidence >= HIGH_CONFIDENCE
        else "Medium"
        if confidence >= MEDIUM_CONFIDENCE
        else "Low"
    )


def display_value(value) -> str:
    if value is None:
        return "Not found"
    if isinstance(value, Decimal):
        return format(value, "f")
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, list):
        return "\n".join(display_value(item) for item in value)
    return str(value)


def summary(result: ExtractionResult) -> dict[str, int]:
    fields = [getattr(result.data, name) for name in ChangeOrder.model_fields]
    return {
        "extracted": sum(item.value is not None for item in fields),
        "missing": sum(item.value is None for item in fields),
        "review": sum(
            item.validation in {"warning", "conflict", "invalid"}
            or (item.value is not None and item.confidence < MEDIUM_CONFIDENCE)
            for item in fields
        ),
        "conflicts": sum(item.validation == "conflict" for item in fields),
        "ocr_pages": sum(page.text_origin == "ocr" for page in result.source.pages),
    }


def llm_configured() -> bool:
    import importlib.util

    return bool(
        os.environ.get("OPENAI_API_KEY")
        and os.environ.get("CHANGEORDER_LLM_MODEL")
        and importlib.util.find_spec("openai")
    )


def preview_pdf(document: DocumentInput, page: int = 0) -> tuple[bytes, int]:
    import pymupdf

    try:
        with pymupdf.open(stream=document.payload, filetype="pdf") as pdf:
            if pdf.needs_pass or len(pdf) > ReaderOptions().max_pages:
                raise DemoInputError("Preview is unavailable for encrypted or oversized PDFs.")
            if not 0 <= page < len(pdf):
                raise DemoInputError("Select an available page.")
            target = pdf[page]
            scale = min(
                1.5,
                1100 / max(1, target.rect.width),
                (4_000_000 / max(1, target.rect.width * target.rect.height)) ** 0.5,
            )
            return target.get_pixmap(matrix=pymupdf.Matrix(scale, scale), alpha=False).tobytes(
                "png"
            ), len(pdf)
    except (RuntimeError, ValueError) as exc:
        if isinstance(exc, DemoInputError):
            raise
        raise DemoInputError(
            "This PDF could not be previewed; extraction will report its input status."
        ) from exc
