# Current delivery

The final delivery includes the original deterministic extraction engine, operational local Tesseract OCR, the Streamlit demonstration, a thin FastAPI API and a Next.js workspace. See [README.md](README.md) for the current full-stack map, [PHASE2.md](PHASE2.md) for the OCR/Streamlit record, and [docs/FINAL_VERIFICATION.md](docs/FINAL_VERIFICATION.md) for the final evidence table. The record below is preserved as **historical Phase 1 evidence** where explicitly labeled.

# Original submission record (Phase 1)

Implemented and verified locally on November 6, 2026 (Asia/Karachi), using Python 3.13.9 on Windows. This directory is the complete source project. The adjacent `sledge-change-order-extractor.zip` is the submission archive; environments, caches, build output and credentials are excluded. [FILE_MANIFEST.txt](FILE_MANIFEST.txt) lists every submitted file with its full relative path, including every example output.

## Installation and execution

Exact PowerShell commands from the directory containing the extracted project:

```powershell
cd .\sledge-change-order-extractor
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev,llm,ocr]"
.\.venv\Scripts\python.exe -m changeorder.cli extract --input examples/documents/01_clean.txt --output result-text.json
.\.venv\Scripts\python.exe -m changeorder.cli extract --input examples/documents/03_digital.pdf --output result-pdf.json
.\.venv\Scripts\python.exe -m changeorder.cli batch --input-dir examples/documents --output-dir batch-results
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe scripts/evaluate_examples.py
```

The included batch intentionally returns exit 1 because the unrelated invoice must fail. Runtime-only installation is `python -m pip install -r requirements.txt`; the baseline requires no key or optional extras. See the README for macOS/Linux activation, raw text/stdin, OCR/date options and optional provider setup.

## Implemented system and artifact map

| Location | Content |
| --- | --- |
| `src/changeorder/` | Typed schemas, bounded readers, exact provenance, conservative normalization, deterministic candidates, optional structured LLM adapter, reconciliation, confidence, cross-field validation, JSON writer and CLI |
| `tests/` | Offline unit/integration/regression tests; real CLI subprocesses; mocked OCR/provider failures |
| `examples/documents/` | 12 explicitly synthetic documents, including two native PDFs (three pages) |
| `examples/pdf_sources/` | Reproducible source text for the native PDFs |
| `examples/ocr/` | Image-only PDF and the actual missing-Tesseract failure result from this environment |
| `examples/expected/labels.json` | Hand-authored ground truth, missing-value and required-warning expectations |
| `examples/outputs/` | Actual JSON for all 12 inputs and batch summary |
| `examples/evaluation.json` | Executed metrics, timings, dependencies, confidence buckets, per-case outcomes and dataset hashes |
| `examples/verification.json` | Verification record and measured coverage |
| `schema/` | Generated JSON Schema |
| `scripts/` | PDF fixture generation, running/evaluating examples, schema export and archive packaging |
| `.github/workflows/ci.yml` | Offline CI matrix for Windows/Linux and Python 3.11/3.13; configured, not executed remotely |
| `README.md`, `SCHEMA.md`, `APPROACH.md` | Reproducible usage, output contract and employer-facing technical write-up |

## Actual representative result

This is a compact projection of [the saved clean execution](examples/outputs/01_clean.txt.json), not the entire response:

```json
{
  "status": "success",
  "change_order_number": {"value": "CO-001", "confidence": 0.9},
  "total_change_amount": {
    "value": 12500.00,
    "confidence": 0.93,
    "evidence": [{
      "source": "01_clean.txt",
      "page": null,
      "line_start": 16,
      "line_end": 16,
      "char_start": 557,
      "char_end": 592,
      "text": "Total Change Amount: USD 12,500.00\n",
      "text_origin": "text"
    }],
    "method": "label",
    "validation": "valid"
  },
  "currency": {"value": "USD", "confidence": 0.9}
}
```

The full JSON has all 31 support-wrapped fields, raw/cleaned pages, missing fields, validation results, extraction methods, alternatives and document issues.

## Verification results

- **118 tests passed in 14.36 seconds.** Coverage: 870/918 statements, **94.77%** (95% rounded). Main-module subprocess execution is tested but not included in this in-process coverage collector.
- **Ruff lint and format checks passed.** No unfinished stubs or credential patterns were found in submitted source/documents.
- **Fresh baseline wheel installation passed** text and PDF extraction with `openai`, `pytesseract`, `PIL`, `pytest` and `reportlab` absent. This checks optional dependency separation and non-editable packaging.
- **All four fixture PDF pages rendered and visually inspected** with Poppler: one native single-page, two native multi-page and one image-only page. No clipped text or overlapping elements were found.
- **Native PDF, text, stdin, literal text and mixed batch commands executed.** One corrupt/unsupported batch file does not suppress successful document output. Source overwrite is rejected.
- **Actual OCR-unavailable behavior executed.** It reports `OCR_UNAVAILABLE` and `NO_EXTRACTABLE_TEXT`; it does not return empty success. OCR line construction, quality penalty and timeout/error classification are tested with offline doubles.
- **Installed OpenAI SDK adapter exercised with mocks**, including strict-schema request configuration, rate limits, timeout, server failures, refusal, malformed output and evidence rejection. No live API request was made.

## Measured synthetic evaluation

| Measure | Observed result |
| --- | --- |
| Documents | 12 synthetic development fixtures |
| Top-level exact matches | 372/372 |
| Non-null correct facts | 143; no false positives or missed labeled facts |
| Field precision / recall / F1 | 1.000 / 1.000 / 1.000 |
| Numeric matches | 29/29 |
| Missing-field false positives | 0/229 |
| Schema-valid outputs / expected statuses | 12/12 each |
| Outcomes | 6 success, 5 partial, 1 expected failure |
| Mean pipeline processing time | 31.40 ms in the recorded run; environment-dependent |
| Confidence buckets | 3 fields at 0.50-0.69, 20 at 0.70-0.89, 120 at 0.90-1.00; all matched these labels |

These are measured regression outcomes on an authored development set, not production accuracy or statistical calibration. Missing fields count toward exact match; line items are one top-level collection comparison. Conflicts test the disclosed representative plus mandatory warnings, not an independently adjudicated true amount. No unseen or employer-owned documents were evaluated, and no OCR/live LLM quality measurement was performed.

## Completed requirements audit

- [x] Focused modular Python package with reproducible local setup and CLI/library entry points.
- [x] Native/multipage PDFs, UTF-8 text files, multiline strings and stdin.
- [x] Optional page-level local OCR with explicit missing-engine/timeout behavior.
- [x] Original and cleaned text, source identity/hash, metadata and exact evidence spans.
- [x] All requested identification, party, scope, financial, schedule and approval fields supported where recognized.
- [x] Per-field typed values, evidence, extraction method, confidence and validation; safe nulls and zero missing confidence.
- [x] Exact Decimal financial parsing/serialization, explicit currency policy and cautious date parsing.
- [x] Requested/proposed/approved/final amount separation; no subtotal substitution or signature-label approval inference.
- [x] Candidate reconciliation with disclosed conflicts, alternatives and confidence reduction.
- [x] Optional strict-JSON LLM adapter, user-supplied configuration, bounded retries, hallucination/context rejection and deterministic fallback.
- [x] Field/schema checks plus financial, date and approval consistency warnings without source-value repair.
- [x] Explicit success/partial/failure states and warning/recoverable/fatal issue severities.
- [x] Independent batch outputs and meaningful exit codes.
- [x] Diverse labeled synthetic examples, real generated PDFs, saved outputs and expected failures.
- [x] Deterministic offline pytest coverage of extraction, errors, provenance, CLI and mocked integrations.
- [x] Executed evaluation with precision/recall/F1, exact/numeric accuracy, missing-field false positives, schema rate, confidence buckets and timing.
- [x] Complete README, output schema documentation and concise technical approach/failure-mode write-up.
- [x] Clean submission package without secrets, environments or unrelated services.

## Remaining optional setup and limitations

The final verification environment discovered and exercised local Tesseract; another machine may still need `TESSERACT_CMD` configured. Configure a supported model and credentials to run live LLM assistance. The baseline remains usable without either. Arbitrary forms, complicated tables, handwriting, multilingual content and revision precedence need further work; unsupported/ambiguous values may remain null or require review. Representative independently labeled real documents are needed for deployment-quality accuracy and confidence calibration.

The archive and local source are ready for review. No remote Git repository was created or published, and no submission message was sent. Upload the project to the repository/account you intend to share with the employer to obtain a public or invited-reviewer URL.
