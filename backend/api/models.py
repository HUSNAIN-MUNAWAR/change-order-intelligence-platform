"""Typed transport models; extraction payloads remain the canonical package schema."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from changeorder.schemas import ExtractionResult


class TransportModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ExtractionOptions(TransportModel):
    ocr: Literal["off", "auto", "force"] = Field(
        default="auto", description="Local OCR policy passed to the existing reader."
    )
    llm: bool = Field(
        default=False,
        description="Opt-in provider assistance. Document text may leave the local process when enabled.",
    )
    date_order: Literal["reject", "mdy", "dmy"] = Field(
        default="reject", description="How ambiguous numeric dates are handled."
    )


class HealthResponse(TransportModel):
    status: Literal["ok"]
    service: str
    pipeline_version: str


class OCRCapability(TransportModel):
    available: bool
    version: str | None
    languages: list[str]
    message: str


class LLMCability(TransportModel):
    available: bool
    configured: bool
    message: str


class CapabilitiesResponse(TransportModel):
    service: str
    supported_formats: list[str]
    supported_media_types: list[str]
    max_file_bytes: int
    max_batch_files: int
    max_batch_bytes: int
    max_pages: int
    ocr: OCRCapability
    llm: LLMCability
    extraction_options: list[str]


class BatchResponse(TransportModel):
    results: list[ExtractionResult]
    processed: int
    failed: int


class ErrorResponse(TransportModel):
    code: str
    message: str
    request_id: str
