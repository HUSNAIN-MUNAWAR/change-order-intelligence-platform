# Baseline Audit

> Historical snapshot from the earlier full-stack assessment work. It predates the current Git checkout and the core extraction upgrade. For the current extraction baseline, confirmed defects, fixes, and verification, see [`EXTRACTION_UPGRADE_REPORT.md`](EXTRACTION_UPGRADE_REPORT.md).

Audit date: 2026-11-06 (Asia/Karachi)

## Repository and working-tree state

- Project root: `E:\Remote Job  Task\sledge-change-order-extractor`
- The supplied directory is not a Git checkout (`git status` reports that no `.git` directory exists). No commit history or tracked/untracked comparison is therefore available.
- The repository contains generated local environments and caches (`.venv`, `tmp`, `build`, `.pytest_cache`, `.ruff_cache`). They are excluded from the intended submission package by existing ignore/package rules.
- Baseline command: `.\.venv\Scripts\python.exe -m pytest -q`
- Baseline result: **148 passed in 10.58s**

## Current architecture

```text
CLI / Streamlit demo
        |
        v
changeorder.pipeline.extract
        |
        +--> readers.py --------> PyMuPDF native text / local Tesseract OCR
        +--> extraction.py -----> label, title and table candidates
        +--> normalization.py --> dates, money, identifiers and text cleanup
        +--> validation.py -----> typed reconciliation and cross-field checks
        +--> confidence.py -----> deterministic heuristic support scores
        +--> provenance.py ------> exact page-local evidence spans
        +--> schemas.py ---------> validated JSON contract
        +--> llm_extractor.py ---> optional, evidence-gated provider adapter
```

The Python package under `src/changeorder` is the current single source of truth. `demo.py` handles upload bounds, temporary files, previews, batch ZIP output and display helpers. `streamlit_app.py` is a working demonstration UI, not an API layer.

## Existing capabilities verified from source and tests

- UTF-8 text, PDF, PNG and JPEG ingestion.
- Native PDF text extraction with page boundaries and deterministic source hashes.
- Automatic or forced local OCR through Tesseract, including OCR quality metadata and mixed native/OCR pages.
- Bounded bytes, pages, characters, OCR pixels and OCR timeout settings.
- Label/value, title, inline-field and simple table candidate extraction.
- Decimal money and numeric values, conservative date parsing, explicit ambiguity handling and ISO currency detection.
- Typed `ExtractionResult` schema with field-level value, confidence, evidence, method, validation, signals and alternatives.
- Exact source evidence spans with page/line/character offsets.
- Conflict preservation, financial role separation, consistency warnings and explicit missing fields.
- Optional OpenAI Responses API adapter with strict structured output, verbatim evidence checks, bounded retries and deterministic fallback.
- CLI single-file/stdin/batch modes and atomic JSON output.
- Streamlit single and multi-document demo, PDF/image/text preview, JSON/ZIP downloads, raw text view and local-only default behavior.
- Existing synthetic and OCR fixtures plus 148 passing tests.

## Missing capabilities relative to the assessment directive

- No FastAPI application or versioned HTTP contract.
- No Next.js/React/TypeScript frontend; only the legacy Streamlit demo exists.
- No backend API tests, frontend type/lint/build tests, or browser tests for the requested new application.
- No external real-document benchmark with manually reviewed ground truth and development/validation/held-out separation.
- No final verification report covering the new layers, security scans or license inventory.
- No documented compliance review of Python/JavaScript dependencies, Tesseract, optional provider, or external source documents.
- Existing README and delivery docs describe the earlier Streamlit implementation and must be updated to match the actual final system.
- Existing CI is Python-focused and does not yet verify a frontend or API.
- No Git metadata is available for change review or recovery; edits must preserve existing files and rely on the final archive and verification reports.

## Technical debt and risks

- Configuration is split between immutable reader/pipeline options and Streamlit constants; the API needs one bounded, environment-driven settings surface.
- `Source.media_type` starts as `unknown` for some failure paths; API error serialization should still be stable and safe.
- PDF/image validation currently relies mainly on suffix and decoder behavior; the API must add upload-size, filename, MIME/content and request-time safeguards.
- The deterministic extractor is intentionally label-driven and has limited layout/table awareness. Native PDF reading order and complex tables remain known limitations.
- Confidence values are heuristic support scores, not calibrated probabilities. This must remain explicit in the API and UI.
- Real-world accuracy cannot be inferred from the current synthetic or related OCR fixtures.
- Optional LLM use can transmit document text externally; it must remain opt-in and clearly disclosed.
- Browser automation and installed external tools may be environment-dependent; any unavailable check must be recorded rather than claimed.

## Dependencies

Direct Python dependencies declared in `pyproject.toml`: Pydantic 2, PyMuPDF and simplejson. Optional extras provide Tesseract bindings/Pillow, OpenAI, Streamlit, pytest/coverage/ruff and reportlab. `requirements.txt` delegates to the local package with `-e .`. No JavaScript dependencies currently exist.

## Components that must remain stable

- `src/changeorder/schemas.py` remains the canonical output contract unless a compatibility-preserving change is proven necessary.
- `src/changeorder/pipeline.py` remains the only extraction orchestration entry point.
- Reader limits, source evidence integrity, Decimal serialization, conflict alternatives and deterministic fallback behavior must not be weakened for UI convenience.
- Existing CLI, Streamlit and synthetic/OCR regression tests must continue to pass after the API and frontend are added.
