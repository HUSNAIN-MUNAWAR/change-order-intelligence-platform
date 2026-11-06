# Architecture Decisions

## Decision 1: Preserve the existing Python engine as the source of truth

The employer requirement is an extraction pipeline, and the current package already owns ingestion, OCR, candidate selection, validation, confidence, provenance and exact JSON serialization. The API and UI will call `changeorder.pipeline.extract`; they will not reimplement field parsing or maintain a second schema. This minimizes regression risk and preserves the 148-test baseline.

## Decision 2: Use FastAPI for the HTTP boundary

FastAPI provides typed request/response validation, generated OpenAPI documentation and a small stateless surface suitable for wrapping the existing synchronous engine. The backend remains thin: it validates transport concerns, writes an upload to a temporary directory, invokes the pipeline, and returns the validated `ExtractionResult`.

## Decision 3: Use Next.js App Router for the demonstration frontend

The requested enhancement is a professional, responsive document workspace. Next.js App Router with TypeScript provides a maintainable browser application, strict client-side types and a clear separation from Python. The frontend owns presentation and interaction only; extraction remains server-side.

## Decision 4: Keep frontend/backend communication explicit and versioned

The browser talks to `/api/v1/health`, `/api/v1/capabilities`, `/api/v1/extract` and `/api/v1/batch`. `ExtractionResult` is returned as the existing validated payload. A configurable `NEXT_PUBLIC_API_BASE_URL` supports local development without hard-coded deployment assumptions.

## Decision 5: Keep AI assistance optional and off by default

The deterministic local path is sufficient for the assessment and avoids transmitting document contents externally. The existing LLM adapter remains optional, evidence-gated and bounded. The UI exposes it only when the backend reports it as configured, and the API must disclose that enabling it may send text to the configured provider.

## Decision 6: Interpret confidence as heuristic support, not probability

The current confidence implementation combines method strength, parsing, agreement, OCR quality and conflict penalties. No calibration dataset exists. Labels such as High/Medium/Low describe this support score and must not be presented as statistically calibrated probabilities.

## Decision 7: Preserve backward compatibility

The existing field names, nested wrappers, Decimal values, evidence spans, issue codes and JSON version remain unchanged. Any additive transport metadata is kept outside `result.data`, and compatibility tests compare direct pipeline results with API responses for the same fixture.

## Decision 8: Treat external documents as provenance first

Public availability does not imply redistribution permission. External benchmark metadata will record URL, retrieval date, type, hash and rights. Documents with unclear redistribution terms will be referenced/downloaded for evaluation only where permitted, or left out of the archive with reproducible instructions.

## Decision 9: Prefer honest partial support over fabricated stages

The API and frontend expose only capabilities and processing states actually implemented. No progress percentages are inferred from elapsed time, and no document highlights are drawn unless coordinates exist. The current engine provides text-span evidence, so the UI displays exact snippets and page references.
