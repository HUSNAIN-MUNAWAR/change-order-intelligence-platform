# Engineering TODO

Status key: `[ ]` not started, `[x]` completed only after its acceptance criteria pass, `[~]` in progress or blocked by the environment.

## P0 — Repository audit and baseline verification

- [x] Audit repository, manifests, schema, engine, UI, tests, scripts and CI. Files: `src/changeorder/*`, `tests/*`, `streamlit_app.py`, `scripts/*`, `pyproject.toml`, `README.md`. Outcome: actual architecture and risks recorded. Acceptance: audit is source-backed and names missing layers. Verify: `docs/BASELINE_AUDIT.md`.
- [x] Run original test suite before edits. Files: `tests/*`. Outcome: baseline captured. Acceptance: result is reproducible. Verify: `.\.venv\Scripts\python.exe -m pytest -q` => 148 passed.
- [x] Record non-Git working-tree limitation. Files: `docs/BASELINE_AUDIT.md`. Outcome: recovery/review limitation documented. Acceptance: no fabricated Git status. Verify: `git status --short --branch`.

## P1 — Architecture and API contract

- [x] Add a thin FastAPI application that calls `changeorder.pipeline.extract`. Files: `backend/*`, `pyproject.toml`. Outcome: versioned health, capabilities, extract and batch endpoints. Acceptance: API never duplicates extraction logic. Verify: API TestClient suite.
- [x] Add bounded API settings, safe uploads, structured request IDs, CORS and error mapping. Files: `backend/api/*`, `.env.example`. Outcome: safe stateless requests. Acceptance: limits, cleanup and content checks are tested. Verify: negative API tests.
- [x] Document request/response contract and compatibility. Files: `docs/API.md`, `schema/*`. Outcome: OpenAPI and examples match `ExtractionResult`. Acceptance: schema validation round-trip passes. Verify: generated OpenAPI/test fixtures.
- [x] Record architecture decisions. Files: `docs/DECISIONS.md`, `docs/ARCHITECTURE.md`. Outcome: rationale is resumable. Acceptance: decisions reflect implementation. Verify: documentation review.

## P2 — Backend extraction integration

- [x] Wire file and batch processing to the existing engine. Files: `backend/api/services/*`. Outcome: original validated output returned unchanged. Acceptance: API output equals direct pipeline output for fixtures. Verify: integration tests.
- [x] Expose genuinely detected OCR/LLM capabilities. Files: `backend/api/capabilities.py`. Outcome: no fabricated availability. Acceptance: values reflect local environment. Verify: capability tests.
- [x] Add structured logging without document-content leakage. Files: `backend/api/main.py`. Outcome: request, timing, page/error metadata. Acceptance: secrets and full text absent. Verify: API integration run and source review.

## P3 — Next.js frontend implementation

- [x] Create App Router TypeScript frontend with accessible design system. Files: `frontend/*`. Outcome: professional responsive workspace. Acceptance: strict typecheck, lint and production build pass. Verify: npm scripts.
- [x] Implement upload, settings, real processing states, document preview, evidence and field groups. Files: `frontend/src/*`. Outcome: controls have real API-backed behavior. Acceptance: no fake progress or unsupported options. Verify: browser test.
- [x] Implement JSON copy/download, batch results and examples backed by actual fixtures/API. Files: `frontend/src/*`, `backend/api/*`. Outcome: exported response matches API. Acceptance: schema-valid download matches backend response. Verify: Playwright.
- [x] Capture screenshots from the running frontend. Files: `docs/images/*`. Outcome: evidence of actual UI. Acceptance: screenshots are produced by browser test. Verify: `scripts/verify_frontend_browser.py`.

## P4 — Real-world dataset research

- [x] Verify the supplied public source URLs and permissions. Files: `benchmarks/sources.csv`, `benchmarks/README.md`. Outcome: source provenance and retrieval dates. Acceptance: no unclear document is redistributed. Verify: online source review and source manifest.
- [ ] Collect or link a diverse external document set where legally appropriate. Files: `benchmarks/sources.csv`, `benchmarks/documents/` only for permitted fixtures. Outcome: development/validation/held-out split. Acceptance: source types and rights recorded. Verify: manifest/hash check.

## P5 — Extraction algorithm improvements

- [x] Review failures on real documents before changing algorithms. Files: `src/changeorder/*`, benchmark outputs. Outcome: native public-form misses were reproduced and documented before generalized patterns were added. Acceptance: each change maps to a reproduced defect. Verify: `benchmarks/results/real-development.json`, `tests/test_public_form_layouts.py`.
- [x] Improve only generalizable candidate/layout/financial/OCR behavior proven necessary. Files: `src/changeorder/extraction.py`, `tests/test_public_form_layouts.py`. Outcome: better public-form performance without synthetic regressions. Acceptance: affected and full suites pass. Verify: pytest and Fresno development evaluation.
- [x] Keep confidence interpretation honest and evidence-gated. Files: `confidence.py`, docs/UI. Outcome: heuristic labels remain explicitly non-probabilistic and evidence-backed. Acceptance: conflicts/OCR lower support. Verify: `tests/test_confidence.py`, `tests/test_validation.py`, `README.md`.

## P6 — Unit and integration tests

- [x] Add API, schema compatibility, upload-security, batch-isolation and error tests. Files: `backend/tests/*`, `tests/*`. Outcome: executable backend coverage. Acceptance: all pass. Verify: pytest.
- [x] Add frontend helper/type/lint/build tests. Files: `frontend/src`, `frontend/*.config.*`. Outcome: typed UI checks pass. Acceptance: npm checks pass. Verify: npm scripts and Vitest.

## P7 — Full end-to-end browser validation

- [x] Run backend and frontend together against a real fixture. Files: `scripts/verify_frontend_browser.py`, `docs/images/*`. Outcome: UI/API/engine path proven. Acceptance: fixture extraction, evidence and JSON download work. Verify: Playwright/Edge report.
- [x] Validate desktop and mobile layout plus console/network cleanliness. Files: browser test/report. Outcome: responsive behavior. Acceptance: no horizontal overflow and no unexpected external requests. Verify: browser report. Tablet-specific automated coverage remains a future improvement.

## P8 — Security and license compliance

- [x] Run dependency, secret and code scans available in the environment. Files: `docs/COMPLIANCE.md`. Outcome: scoped results and unresolved issues. Acceptance: no unsupported zero-vulnerability claim. Verify: recorded commands/results.
- [x] Review Python, JavaScript, OCR, provider and dataset licenses. Files: `docs/COMPLIANCE.md`, `benchmarks/sources.csv`. Outcome: redistribution obligations and unresolved items documented. Acceptance: unclear external PDFs excluded. Verify: license inventory review.

## P9 — Engineering documentation

- [x] Rewrite README around verified implementation with clickable TOC and commands. Files: `README.md`. Outcome: recruiter-ready, accurate entry point. Acceptance: links point to existing headings/files. Verify: source/link review.
- [x] Add Mermaid architecture/data-flow/state/fallback diagrams. Files: `docs/ARCHITECTURE.md`. Outcome: diagrams match modules and states. Acceptance: valid Mermaid syntax. Verify: source review.
- [x] Keep `APPROACH.md` concise and assessment-focused; document failure modes. Files: `APPROACH.md`, `docs/*`. Outcome: recruiter can understand the approach quickly. Acceptance: no invented metrics. Verify: documentation review.

## P10 — Final clean-install and delivery audit

- [x] Re-run baseline, backend, frontend, OCR, synthetic and real-document checks. Files: `docs/FINAL_VERIFICATION.md`. Outcome: actual evidence table. Acceptance: each result has command/evidence or honest blocker. Verify: final report.
- [x] Verify clean installation, temporary cleanup, JSON downloads and packaging exclusions. Files: `scripts/package_submission.py`, `scripts/*`. Outcome: recoverable clean ZIP with backend, frontend and benchmark metadata included. Acceptance: no environments, secrets, caches or unlicensed documents. Verify: `docs/FINAL_VERIFICATION.md`, archive listing/integrity.
- [x] Update this checklist with only evidence-backed completions. Files: `TODO.md`. Outcome: resumable final state with the external-corpus gap intentionally remaining open. Acceptance: incomplete work remains unchecked. Verify: final review.
