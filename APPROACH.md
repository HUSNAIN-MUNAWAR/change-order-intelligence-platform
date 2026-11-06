# Approach and failure modes

## Objective and scope

The assessment asks for messy construction change-order PDF/text to validated JSON with per-field confidence and a short explanation of failure modes. The schema, Python/PyMuPDF/Pydantic stack, optional Tesseract OCR and optional OpenAI adapter are implementation choices, not employer requirements. No employer documents were provided. Included fixtures and all measured accuracy results are synthetic.

## Pipeline and trade-offs

1. **Ingest bounded input.** UTF-8 text retains exact line endings; PDFs retain ordered page text and metadata. SHA-256 identifies original file bytes. Raw strings have a source identifier and null page numbers. Limits reject oversized files/page counts/text rather than silently truncating facts.
2. **Recover text conservatively.** PyMuPDF uses sorted reading order. Sparse pages optionally go through local Tesseract; native text remains available when OCR replaces it. A page failure generates an issue and usable pages continue. No usable text yields failed extraction.
3. **Generate candidates.** Explicit label aliases, titled identifiers, wrapped text blocks, amount/date parsers and simple delimited table structure produce typed values with exact raw spans. Normalization collapses horizontal whitespace and normalizes Unicode in the working view. Restricted `0/o` and `1/l` repairs affect labels only and receive a penalty; identifiers and money are never repaired.
4. **Optionally assist with an LLM.** The adapter requests strict schema output with raw values and exact quotes. Source content is untrusted data. Every quote must exist uniquely on its claimed page, contain the proposed raw value, and pass local normalization/schema validation. Financial, identifier, date, schedule and approval fields additionally require locally recognizable field context. This deliberately limits LLM recall on unlabeled financial prose; it preserves an auditable fallback. Model confidence is ignored. Three bounded attempts cover transient failures; malformed/nontransient responses fall back immediately without leaking provider error bodies.
5. **Reconcile, check, score.** Valid deterministic candidates outrank LLM candidates. Equal-strength conflicts retain the first source candidate as a review representative and expose distinct alternatives; the code never silently resolves ambiguity. Repeated equal values add evidence, not repeated-label score bonuses. Cross-field checks retain stated values and reduce confidence on inconsistency. Pydantic revalidates the complete result before exact Decimal JSON serialization.

This hybrid design offers a reproducible local baseline and an inspectable extension point without requiring cloud access. Its central trade-off is conservative coverage: unsupported layouts and semantics are withheld rather than guessed. Exact provenance does not prove semantic correctness, so accepted values can still require human review.

## Schema and normalization

The 31 optional top-level facts cover identification, parties, scope/references, financial roles, cost items, schedule and approval. Each populated value has typed evidence/confidence/method/validation; each cost-item leaf also has its own wrapper. Missing values are null with score zero and null evidence. Invalid label values are withheld with an invalid status and an issue carrying the source span. [SCHEMA.md](SCHEMA.md) documents every field and [the generated JSON Schema](schema/extraction-result.schema.json) exposes the wire contract; Python validators enforce additional wrapper invariants.

Money uses Decimal, signed values, valid thousands groups and parentheses. Explicit credits normalize negative. No currency default is assumed; a dollar sign alone is ambiguous. ISO and month-name dates parse directly. Ambiguous numeric dates return null unless `mdy`/`dmy` is explicitly configured, in which case the field remains reviewable. Leading zeros and identifier prefixes are retained. Multiline scope is preserved.

Requested/proposed/approved/final amounts remain separate. A generic stated change total takes precedence; otherwise total selection uses final > approved > proposed > requested and records `amount_basis`. This selection is not a claim that the document is approved. An explicit generic/final or generic/approved disagreement is warned. Signature labels never establish approval.

## Confidence policy

These are **heuristic support scores, not calibrated probabilities**. `confidence.py` contains the small auditable scoring function:

| Signal | Effect |
| --- | --- |
| Exact label candidate | Base 0.90 |
| Explicit title/identifier heading | Base 0.86 |
| Structured cost-table candidate | Base 0.78 |
| Accepted optional LLM candidate | Base 0.65; model score ignored |
| Successful parse for a field name ending in amount/date | +0.03 |
| Agreement from distinct extraction methods | +0.03; repeated labels alone add nothing |
| OCR origin | Subtract 0.18 + 0.20 x (1 - mean word score); unknown quality uses 0.5 |
| OCR label repair | -0.15 |
| Explicitly configured ambiguous date order | -0.08 |
| Competing supported values | -0.35 and cap at 0.55 |
| Cross-field mismatch | -0.20 and cap at 0.65 for affected fields |

Final scores are clamped to [0, 0.98] and rounded to three decimals. Method agreement is a modest corroborating signal from the same document, not statistical independence. Table leaves use 0.78 for native/text and 0.60 for OCR; their collection receives the normal candidate policy. A row extension mismatch also caps the affected row amount at 0.58. Multiple distinct failed consistency checks can reduce a field repeatedly. `signals` explains adjustments; `validation` independently identifies conflicts/invalid values. Missing values always score zero. Neither model confidence nor arithmetic agreement can make an unsupported value appear.

## Evidence and validation

Evidence contains source identity, actual PDF page or null, one-based lines, zero-based end-exclusive page-local character offsets, exact text, and native/OCR/text origin. Raw and cleaned page text are retained so consumers can verify every quoted slice. OCR evidence cites the recovered transcription; no claim is made that it matches the underlying pixels perfectly.

Field parsers and Pydantic reject unsupported types, malformed dates/amounts, unknown properties, out-of-range confidence and unsupported null/evidence combinations. Cross-field checks compare cost rows with total, quantity x price with row amount, previous + change with revised contract, document/approval date order and explicit approval contradictions. Currency conflict skips financial arithmetic. A comparison may be inapplicable because taxes, partial tables, cumulative changes or revision history are not modeled; warnings disclose this rather than rewriting facts.

## Failure modes and mitigations

| Failure | Behavior / remaining limitation |
| --- | --- |
| Empty, binary, legacy-encoded text; bad/encrypted PDF; unsupported extension | Structured fatal issue, failed result; no fake success |
| Sparse/scanned page without Tesseract; OCR error/timeout | Explicit recoverable issue, preserve native/other pages; fail when no text remains |
| OCR glyph confusion | Penalize OCR and repaired labels; reject invalid money instead of changing O to 0 |
| Multicolumn, merged-cell, reordered or image-heavy tables | Basic reading order can lose associations; unsupported rows may be missing or trigger consistency warnings |
| Multiple totals, identifiers, revisions or dates | Preserve alternatives and lower confidence; do not infer revision precedence |
| Unrelated invoice or bare heading | Fail the document-context/actionable-fact gate; generic fields are withheld |
| Missing facts/approval | Null fields; core review-field gaps make extraction partial; signatures are not interpreted |
| LLM hallucination, wrong page/quote, numeric role confusion | Reject absent/ambiguous/nonverbatim evidence or unsupported protected field context |
| LLM timeout, rate limit, refusal, malformed JSON, unavailable network | Bounded retry or immediate deterministic fallback; no API key required for baseline |
| Semantically wrong but verbatim LLM narrative value | Can still pass evidence checks at a low base score; exact quotes do not establish correct role assignment |
| Formula mismatch / mixed currency | Report and reduce confidence or skip arithmetic; no invented balancing values |

## Measured verification

The pre-enhancement baseline was **148 passing tests in 10.58 seconds**. The final Python/API suite passes **154 tests**; the combined engine/API coverage run reports **93%**. Tests cover readers, normalization, exact spans, types, confidence, conflicts, public-form layouts, CLI/batch behavior, API uploads/errors and mocked provider failures. The live LLM path remains unmeasured.

The executed 12-document synthetic development benchmark matched **372/372** top-level fields: precision/recall/F1 1.000, numeric accuracy 1.000, missing-field false-positive rate 0, and schema validation 12/12. It produced six successes, five partial results and one expected failure for unrelated input. Exact per-case timings, dependencies, counts and confidence buckets are in [examples/evaluation.json](examples/evaluation.json). Conflict labels evaluate the documented representative plus mandatory review issues, not an adjudicated true amount. Missing fields contribute to exact match, and a whole cost collection counts as one field, so headline accuracy should be read alongside precision/recall and dataset size. No holdout or employer-owned documents were used. Perfect scores on these authored cases provide regression evidence, not a production accuracy estimate or confidence calibration.

## Phase 2: genuine OCR and local demonstration

The existing UB Mannheim Tesseract **v5.4.0.20240606** installation was found outside PATH and activated with English/OSD data. Portable discovery supports an explicit environment override, PATH and conventional Windows locations. Real OCR now handles image-only and mixed PDFs, sparse searchable headers over scanned bodies, and direct PNG/JPEG input. Grayscale/autocontrast and reliable EXIF orientation correction preserve fine characters; no default threshold/denoising or uncertain orientation guess is applied. OCR word geometry retains large gaps where available. Page rendering and recognition failures are recoverable when other pages remain usable. Raw/native text, origin and exact spans keep the existing schema and provenance contract.

The Streamlit app is a presentation layer over `pipeline.extract`, with temporary-file cleanup and per-session results rather than a shared document cache. Only an explicit extraction action invokes the pipeline. Source previews, grouped typed fields, heuristic bands, validation badges, alternatives and evidence share the CLI's schema; JSON copy/download uses the same exact Decimal serializer. Uploads are bounded and independent, with a batch ZIP option. The app binds locally; optional LLM transmission remains an explicit opt-in.

The final suite preserves the original behavior and adds API/public-layout regressions. The synthetic benchmark remains **372/372**. Four genuine OCR representations matched **124/124** fields and both blank cases failed correctly; these are related representations of one source, not a representative OCR corpus. One manually reviewed City of Fresno public change order matched **9/9 annotated fields** after a generalized form-layout improvement; it is development data, not held out. The Next.js frontend passes typecheck, lint, Vitest and production build, and a Playwright/Edge run verified the local API fixture, JSON download schema, mobile overflow and no external browser requests.

A real browser verified scanned PDF -> OCR -> fields -> evidence -> Streamlit -> copied/downloaded schema-valid JSON. Desktop/mobile layouts and absence of external app requests were checked, and a genuine screenshot is included in the README. Full results, limitations and changed files are in [PHASE2.md](PHASE2.md). Handwriting, arbitrary rotations/layouts, poor scans, revision precedence and production calibration remain limitations.

## Next improvements

First collect a permissioned, independently annotated corpus with unseen forms and adjudicated conflicts. Measure field accuracy and abstention coverage by document/OCR quality, keep a template-separated holdout, and calibrate confidence only with enough representative outcomes. Then add layout coordinates/table reconstruction, multilingual/rotated OCR evaluation and revision-aware financial semantics where errors justify them. A targeted LLM or vision stage should earn its cost through measured incremental recall while retaining the evidence gates. A hosted UI, database and deployment infrastructure do not advance this assessment's core objective.
