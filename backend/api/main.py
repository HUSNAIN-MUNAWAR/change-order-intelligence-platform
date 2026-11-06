"""Thin FastAPI transport around the existing change-order extraction package."""

from __future__ import annotations

import asyncio
import json
import logging
from contextlib import asynccontextmanager
from time import perf_counter
from uuid import uuid4

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from starlette.concurrency import run_in_threadpool

from changeorder.jsonio import dumps
from changeorder.schemas import ExtractionResult

from .capabilities import capabilities
from .config import settings
from .models import (
    BatchResponse,
    CapabilitiesResponse,
    ErrorResponse,
    ExtractionOptions,
    HealthResponse,
)
from .services import ApiInputError, process_upload, validate_upload

LOGGER = logging.getLogger("sledge.api")
logging.basicConfig(level=logging.INFO, format="%(message)s")


@asynccontextmanager
async def lifespan(_: FastAPI):
    LOGGER.info(json.dumps({"event": "api_started", "service": "sledge-change-order-intelligence"}))
    yield
    LOGGER.info(json.dumps({"event": "api_stopped", "service": "sledge-change-order-intelligence"}))


app = FastAPI(
    title="Sledge Change Order Intelligence API",
    version="1.0.0",
    description=(
        "Evidence-grounded construction change-order extraction. The API delegates document processing "
        "to the validated Python extraction engine and returns its canonical ExtractionResult contract."
    ),
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=list(settings.cors_origins),
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type", "X-Request-ID"],
)


@app.middleware("http")
async def request_context(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID") or uuid4().hex
    request.state.request_id = request_id
    started = perf_counter()
    try:
        response = await call_next(request)
    except Exception:
        LOGGER.exception(
            json.dumps(
                {"event": "request_error", "request_id": request_id, "path": request.url.path}
            )
        )
        raise
    response.headers["X-Request-ID"] = request_id
    LOGGER.info(
        json.dumps(
            {
                "event": "request_complete",
                "request_id": request_id,
                "method": request.method,
                "path": request.url.path,
                "status_code": response.status_code,
                "duration_ms": round((perf_counter() - started) * 1000, 3),
            }
        )
    )
    return response


def error_response(request: Request, error: ApiInputError) -> JSONResponse:
    request_id = (
        getattr(request.state, "request_id", None)
        or request.headers.get("X-Request-ID")
        or "generated-in-response"
    )
    payload = ErrorResponse(code=error.code, message=str(error), request_id=request_id).model_dump()
    return JSONResponse(status_code=error.status_code, content=payload)


def option_model(ocr: str, llm: bool, date_order: str) -> ExtractionOptions:
    try:
        return ExtractionOptions.model_validate({"ocr": ocr, "llm": llm, "date_order": date_order})
    except ValueError as exc:
        raise ApiInputError("INVALID_OPTIONS", "Invalid extraction options", 422) from exc


async def read_upload(upload: UploadFile) -> bytes:
    payload = await upload.read(settings.max_file_bytes + 1)
    if len(payload) > settings.max_file_bytes:
        raise ApiInputError(
            "INPUT_LIMIT", "The uploaded file exceeds the configured byte limit", 413
        )
    return payload


async def process_with_timeout(document, options: ExtractionOptions) -> ExtractionResult:
    try:
        return await asyncio.wait_for(
            run_in_threadpool(process_upload, document, options),
            timeout=settings.processing_timeout_seconds,
        )
    except TimeoutError as exc:
        raise ApiInputError(
            "PROCESSING_TIMEOUT", "Document processing exceeded the configured time limit", 408
        ) from exc


@app.get("/api/v1/health", response_model=HealthResponse, tags=["system"])
async def health() -> HealthResponse:
    return HealthResponse(
        status="ok", service="sledge-change-order-intelligence", pipeline_version="0.1.0"
    )


@app.get("/api/v1/capabilities", response_model=CapabilitiesResponse, tags=["system"])
async def get_capabilities() -> CapabilitiesResponse:
    return capabilities()


@app.post(
    "/api/v1/extract",
    response_model=ExtractionResult,
    responses={
        400: {"model": ErrorResponse},
        413: {"model": ErrorResponse},
        415: {"model": ErrorResponse},
        422: {"model": ErrorResponse},
        408: {"model": ErrorResponse},
    },
    tags=["extraction"],
    summary="Extract a validated change-order result from one document",
)
async def extract_document(
    request: Request,
    file: UploadFile = File(..., description="PDF, UTF-8 TXT, PNG or JPEG document"),  # noqa: B008
    ocr: str = Form("auto", description="OCR policy: off, auto or force"),
    llm: bool = Form(False, description="Opt-in optional provider assistance"),
    date_order: str = Form("reject", description="Ambiguous date policy: reject, mdy or dmy"),
):
    try:
        options = option_model(ocr, llm, date_order)
        document = validate_upload(file.filename, file.content_type, await read_upload(file))
        result = await process_with_timeout(document, options)
        LOGGER.info(
            json.dumps(
                {
                    "event": "document_processed",
                    "request_id": getattr(request.state, "request_id", None),
                    "filename": document.filename,
                    "pages": len(result.source.pages),
                    "status": result.status,
                    "llm_used": result.llm_used,
                }
            )
        )
        return Response(content=dumps(result), media_type="application/json")
    except ApiInputError as exc:
        return error_response(request, exc)


@app.post(
    "/api/v1/batch",
    response_model=BatchResponse,
    responses={
        400: {"model": ErrorResponse},
        413: {"model": ErrorResponse},
        415: {"model": ErrorResponse},
        422: {"model": ErrorResponse},
        408: {"model": ErrorResponse},
    },
    tags=["extraction"],
    summary="Process multiple documents independently",
)
async def extract_batch(
    request: Request,
    files: list[UploadFile] = File(..., description="Up to the configured batch file count"),  # noqa: B008
    ocr: str = Form("auto"),
    llm: bool = Form(False),
    date_order: str = Form("reject"),
):
    try:
        options = option_model(ocr, llm, date_order)
        if not files or len(files) > settings.max_batch_files:
            raise ApiInputError(
                "INPUT_LIMIT", f"Upload between 1 and {settings.max_batch_files} files", 413
            )
        documents = []
        total = 0
        for upload in files:
            payload = await read_upload(upload)
            total += len(payload)
            if total > settings.max_batch_bytes:
                raise ApiInputError(
                    "INPUT_LIMIT", "The batch exceeds the configured total byte limit", 413
                )
            documents.append(validate_upload(upload.filename, upload.content_type, payload))
        results = [await process_with_timeout(document, options) for document in documents]
        response = BatchResponse(
            results=results,
            processed=len(results),
            failed=sum(item.status == "failed" for item in results),
        )
        return Response(content=dumps(response), media_type="application/json")
    except ApiInputError as exc:
        return error_response(request, exc)


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    request_id = request.headers.get("X-Request-ID") or "generated-in-response"
    return JSONResponse(
        status_code=exc.status_code,
        content=ErrorResponse(
            code="HTTP_ERROR", message=str(exc.detail), request_id=request_id
        ).model_dump(),
    )
