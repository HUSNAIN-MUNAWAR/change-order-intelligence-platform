# API Contract

The backend is a thin HTTP boundary around the canonical `changeorder.pipeline.extract` function. It does not define a second extraction schema.

Start it from the repository root after installing the API extra:

```powershell
python -m uvicorn backend.api.main:app --reload --port 8000
```

The API is stateless in normal operation. Uploads are written to a private temporary directory and removed when processing completes. The default limits are 20 MiB per file, 8 files and 40 MiB per batch, 100 PDF pages, 500,000 extracted characters and a 120-second request budget; each is configurable through `CHANGEORDER_*` environment variables.

## Endpoints

### `GET /api/v1/health`

Returns `{ "status": "ok", "service": "...", "pipeline_version": "..." }`.

### `GET /api/v1/capabilities`

Reports supported formats and limits plus detected local Tesseract status and optional LLM configuration. Capability values are detected at request time; no unavailable mode is advertised as ready.

### `POST /api/v1/extract`

Multipart fields:

- `file`: one PDF, UTF-8 TXT, PNG or JPEG.
- `ocr`: `off`, `auto` or `force`.
- `llm`: `false` by default; enabling it may send document text to the configured provider.
- `date_order`: `reject`, `mdy` or `dmy`.

The successful response is the existing validated `ExtractionResult` JSON. Decimal amounts remain JSON numbers through the package serializer. Invalid uploads return a structured error with `code`, `message` and `request_id`.

### `POST /api/v1/batch`

Uses repeated `files` multipart fields and the same options. The response is `{ "results": [...], "processed": N, "failed": N }`; each item is an independent canonical `ExtractionResult`.

The generated OpenAPI document is available at `/docs` while the server is running.
