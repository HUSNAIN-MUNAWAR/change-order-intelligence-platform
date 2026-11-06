# Core Extraction Intelligence Upgrade

Audit and verification date: 2026-11-07 (Asia/Karachi)

This report covers the deterministic extraction core only. No Next.js, CSS, Streamlit layout, or FastAPI architecture changes were made.

## A. Baseline

Before this upgrade, the existing suite passed 154 tests. Ruff checks and formatting were clean. The available measurements were:

- Synthetic fixtures: 12 documents, 372 field comparisons, exact field precision/recall/F1 of 1.0.
- Genuine local OCR fixtures: 4 positive documents, 124/124 field matches, 2/2 negative cases.
- External document: one manually reviewed Fresno public-record PDF, 9/9 annotated fields; development data, not held out.

The baseline was strong on its fixtures but did not exercise several semantic and mixed-source failure paths.

## B. Confirmed defects fixed

| Defect | Root cause | Correction | Regression coverage |
|---|---|---|---|
| Approved and final disagreement could be missed | `check_consistency` stopped after the first role comparison | Compare every available role against an explicit/generic stated total | `test_generic_total_checks_both_approved_and_final_roles` |
| Contract totals could fall through to a generic change total | Labels did not cover current/revised contract totals | Added semantic aliases and context-aware generic-total abstention | `test_contract_total_context_is_not_treated_as_change_amount` |
| OCR replaced native PDF text | The reader selected either native or OCR text | Conservatively merge duplicate-filtered OCR lines with native text | `test_ocr_merge_preserves_native_text` |
| Mixed pages with large images skipped OCR | `_needs_ocr` returned early on native character count | Inspect meaningful image coverage before the dense-text fast path | `test_large_embedded_image_can_trigger_ocr` |
| `CO-001` and construction change requests were under-recognized | Recognition was limited to `CHANGE ORDER`/some `CO` labels | Add construction-context variants and reject invoice-style references | `test_change_request_with_construction_facts_is_recognized`, `test_co_number_variant_needs_construction_context`, `test_invoice_with_co_reference_is_not_change_order` |
| Line-item subtotals were ignored | Table parsing only validated row extensions | Retain table state across pages and compare explicit subtotals to extracted rows | `test_credits_and_line_subtotal_are_validated` |
| Optional LLM evidence could not verify an unusual but explicit financial label | Protected fields required deterministic rediscovery inside the quote | Permit a bounded nearby-label semantic gate while retaining exact quote/value/type checks | `test_llm_can_verify_semantic_amount_label_outside_deterministic_pattern` |

## C. Algorithmic upgrades

### Financial semantics

The extractor now distinguishes current/revised contract totals from change totals, accepts common credits/deductions notation including parentheses and slash variants, and treats only truly generic `Total:` labels as context-sensitive. Generic totals near tax, subtotal, markup, retention, or contract-total context abstain with `AMBIGUOUS_AMOUNT_ROLE` rather than silently acquiring the change-total meaning. Explicit labels such as `Total Change Amount` and `Cost of this Change Order` retain their semantic priority.

Explicit line-item subtotals are checked against the extracted rows. Existing quantity-times-unit-price, line-total, contract-total, date-order, currency, and approval checks remain source-backed; no missing tax, markup, subtotal, or workflow amount is invented.

### Native/OCR fusion and evidence

PDF pages still use bounded PyMuPDF extraction and local Tesseract OCR. Image coverage is inspected even when a page has a native header. OCR lines are canonicalized and compared with native/previous OCR lines using exact or high-similarity duplicate checks. New OCR-only lines are appended, preserving the native text exactly.

The public `PageText` and `Evidence` schema is unchanged. Internal private origin ranges allow evidence created from a mixed page to report native or OCR origin for the actual span. Page, line, character offsets and verbatim quotations continue to refer to the merged page-local text.

### Classification, reconciliation, confidence, and LLM assistance

Recognition now combines change-order/request/directive headings, `PCO`/`CCD`, construction context, and `CO-001`/`CO #12` forms. Invoice, receipt, purchase-order, packing-slip, and expense-report headers are rejected even when they contain a `CO` reference.

Candidates retain all evidence spans for table collections. Reconciliation still preserves alternatives, but correlated LLM evidence is no longer counted as independent corroboration when it quotes the same deterministic source span. Confidence remains an explainable heuristic score, not a calibrated probability.

The optional LLM remains off by default, bounded to three attempts and evidence-gated. Protected fields require exact unique source quotations, typed normalization, and either deterministic role support or a nearby explicit semantic label. Blank signature sections cannot establish approval.

## D. Benchmark comparison

The same fixed fixtures were rerun after the upgrade. The results demonstrate compatibility and regression protection, not a claim of general-world accuracy:

| Evaluation | Before | After | Interpretation |
|---|---:|---:|---|
| Existing tests | 154 passed | 163 passed | 9 new regression tests added; 1 installed Starlette/httpx deprecation warning remains |
| Synthetic field comparisons | 372/372 | 372/372 | 1.0 precision, recall, F1, and exact match; synthetic only |
| Local OCR field comparisons | 124/124 | 124/124 | 2/2 negative cases; related fixtures, not independent real forms |
| Fresno development PDF | 9/9 | 9/9 | One native document, not held out; still reports review issues from source conflicts/arithmetic |

The latest local runs measured approximately 128.5 ms mean synthetic processing, 2,156.6 ms mean OCR processing, and 586.9 ms for the Fresno document. OCR timing is machine- and Tesseract-dependent and is not treated as a quality metric.

External research was refreshed against official public construction references, including [Caltrans change-order examples](https://dot.ca.gov/programs/construction/change-order-information/change-order-examples). The repository retains only source metadata and the locally evaluated development document; unclear redistribution terms are not treated as permission to package PDFs.

## E. Remaining weaknesses

- The external corpus remains one development document with no held-out real-document score; more independently annotated public records are required before calibration or generalization claims.
- Complex multi-column, handwriting, multilingual, and heavily degraded scans still need layout-specific evaluation.
- The public evidence contract exposes page-local text spans, not bounding boxes; the implementation therefore improves reading order conservatively without fabricating coordinates.
- OCR fusion can expose additional noisy candidates by design; low OCR quality and conflicts lower confidence and preserve review issues rather than being silently discarded.
- Confidence values remain heuristic support scores and are not probabilities.
- No live LLM-provider run is required or claimed; provider behavior remains optional and network-dependent.

## F. Exact file changes

- `src/changeorder/extraction.py`: semantic aliases, construction classification, generic-total context, cross-page table state, subtotal validation, and multi-span table evidence.
- `src/changeorder/readers.py`, `src/changeorder/provenance.py`, `src/changeorder/schemas.py`: bounded image-region OCR detection, native/OCR fusion, and internal span provenance with unchanged public models.
- `src/changeorder/validation.py`, `src/changeorder/confidence.py`: all-role financial checks, evidence-aware reconciliation, correlated-evidence handling, and explainable ambiguity penalties.
- `src/changeorder/llm_extractor.py`: nearby semantic-label verification for unusual layouts while retaining deterministic evidence gates.
- `src/changeorder/pipeline.py`: shared construction-document classifier.
- `tests/test_failures.py`, `tests/test_readers.py`, `tests/test_validation.py`, `tests/test_llm.py`: failing-first regressions for the confirmed defects.

No frontend or visual files were modified.

## G. Verification

Commands run from the repository root:

```text
.venv\Scripts\python.exe -m pytest -q
163 passed, 1 warning in 43.58s

.venv\Scripts\python.exe -m ruff check src backend tests scripts
All checks passed!

.venv\Scripts\python.exe -m ruff format --check src backend tests scripts
50 files already formatted

.venv\Scripts\python.exe scripts\evaluate_examples.py
12 documents, 372/372 field comparisons, all reported metrics 1.0

.venv\Scripts\python.exe scripts\evaluate_ocr.py
124/124 field matches, 2/2 negative cases, genuine local Tesseract

.venv\Scripts\python.exe scripts\evaluate_real_documents.py --documents-dir tmp\real-research --output benchmarks\results\real-development.json
1 development document, 9/9 annotated fields, no mismatches
```

The final Git diff was restricted to the extraction core, its regression tests, and this technical report/checklist update; no company email or company Git identity was used.
