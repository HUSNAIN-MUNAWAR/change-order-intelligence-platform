# Output contract, version 1.0

Phase 2 preserves this contract and its Pydantic schemas unchanged. PNG/JPEG inputs reuse `source.pages` with one logical image page (`page: 1`), `text_origin: "ocr"` and an image media type; PDF pages and raw text references retain their original meanings. Existing flexible metadata records image dimensions/preprocessing. No UI-specific output fields are added.

`ExtractionResult` in `src/changeorder/schemas.py` is the source of truth. Unknown properties are forbidden throughout the Pydantic models. Regenerate JSON Schema with `python scripts/export_schema.py`.

## Envelope

| Property | Meaning |
| --- | --- |
| `schema_version`, `pipeline_version` | Versioned output contract and implementation |
| `status` | `success`, `partial` (review required), or `failed` |
| `source` | Identifier, filename, SHA-256, media type, original byte count, PDF metadata, text pages |
| `data` | The 31 fields below, always present as support wrappers |
| `issues` | Code, severity, message, optional affected field and exact evidence |
| `missing_fields` | Names of all absent/invalid top-level values |
| `consistency` | `passed` for executed checks, `warning`, or `not_checked` |
| `llm_used` | Optional adapter ran; does not imply its values were accepted or its request succeeded |
| `processing_ms` | Measured wall time for this invocation, including ingestion; excludes CLI output writing |

Issue severities are `info`, `warning`, `recoverable_error`, `fatal_error`. A recoverable stage failure yields partial extraction when usable facts remain. File/format failures, unreadable inputs and unrecognized documents yield failed JSON. Unexpected programming exceptions propagate from the library.

Each page has `raw_text`, `cleaned_text`, `page`, `text_origin` (`text`, `native`, `ocr`), optional `native_text` when OCR replaced the PDF layer, and optional `ocr_quality`. Quality is the mean recognized Tesseract word score, not a probability of correctness. Text input has one source block with a null page number, even if it contains form-feed characters.

## Support wrapper

All fields contain `value`, `confidence` in [0,1], nullable `evidence` (a list of exact spans), `method` (`label`, `title`, `table`, `llm`, `missing`), `validation`, `signals` and `alternatives`. Alternatives contain the other typed value, supporting evidence and method. Missing values must have confidence 0, null evidence and method `missing`. Non-null values require nonempty evidence and a valid/warning/conflict status. These cross-property invariants are enforced by Python validators; generated JSON Schema alone does not express all invariants.

Validation statuses: `valid` (type/parser accepted), `warning` (normalization or consistency review), `conflict` (multiple distinct supported candidates), `missing` (no usable value), `invalid` (a label was found but its value failed parsing/schema validation). Valid means accepted by these checks, not verified against the physical world.

Each evidence span includes the actual source identifier, actual PDF page or null, one-based line start/end, zero-based page-local character start/end (exclusive), exact raw text, and origin. Evidence references the selected OCR transcription when OCR is used, not pixels or invented ground truth. Bounding boxes are not currently returned.

## Fields

| Fields | Value type and policy |
| --- | --- |
| `change_order_number`, `project_number`, `revision` | String; leading zeros, punctuation and prefixes retained; explicit label/context required |
| `project_name`, `document_title` | String |
| `document_date`, `approval_date`, `proposed_completion_date` | ISO `YYYY-MM-DD`; four-digit years only; ambiguous numeric dates withheld by default |
| `contractor`, `subcontractor`, `owner`, `architect_engineer` | String |
| `description`, `reason`, `discipline` | String; useful line breaks retained in multiline descriptions/reasons |
| `referenced_documents` | List of strings, split only at semicolons, commas or line breaks |
| `total_change_amount` | Decimal money; explicit generic total first, otherwise final > approved > proposed > requested |
| `requested_amount`, `proposed_amount`, `approved_amount`, `final_amount` | Separate Decimal money values; different roles are not automatically contradictions |
| `amount_basis` | `stated_total`, `requested`, `proposed`, `approved`, `final`; source-supported role of the selected total |
| `currency` | Explicit normalized ISO code; supported set: USD, CAD, AUD, EUR, GBP, AED, PKR, INR, NZD, JPY, CHF. US$/C$/A$/EUR symbol/GBP symbol also supported. Bare `$` is ambiguous |
| `previous_contract_amount`, `revised_contract_amount` | Decimal money as stated; no automatic correction |
| `credits_deductions` | Decimal money, normalized negative for an explicit credit/deduction label |
| `line_items` | Nullable list of `CostItem` records described below |
| `schedule_impact` | Signed Decimal duration; explicit no change becomes zero; no unit inferred |
| `schedule_unit` | `days`, `calendar_days`, `working_days`, `weeks`, `hours`; business days normalize to working days |
| `approval_status` | `approved`, `pending`, `proposed`, `requested`, `rejected`, `draft`, `void`; explicit supported status only |
| `approver_name` | String from an explicit supported label; signature labels never establish approval |

Money accepts signed decimal-point notation, valid comma/space thousands groups and parentheses for deductions. Precision: at most 18 digits and two fractional digits. Duration/quantity permit at most four fractional digits; durations are bounded to an absolute 100,000. Unsupported decimal-comma formats are rejected. No automatic OCR repair changes a monetary value or identifier.

Each `CostItem` has `description`, optional `quantity`, optional `unit`, optional `unit_price`, and `amount`. Every leaf is a support wrapper with its own confidence and exact row evidence; the collection also carries a score/evidence. Simple table extraction never treats subtotal/tax/markup rows as change totals. Collection evidence starts at its first row; all row evidence is available on the individual items.

The JSON writer preserves exact Decimal number tokens. The Pydantic input schema can accept decimal strings as well as numbers, but this application's public writer emits numbers. Downstream binary floating-point readers may still lose precision; parse Decimal when exact money matters.
