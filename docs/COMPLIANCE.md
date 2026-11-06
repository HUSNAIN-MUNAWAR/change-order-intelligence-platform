# Security and Open-Source Compliance

Audit date: 2026-11-06 (Asia/Karachi)

## Security checks executed

| Check | Command | Result | Scope / note |
|---|---|---|---|
| Python lint | `python -m ruff check src backend tests scripts streamlit_app.py` | Pass | All configured Ruff checks passed. |
| Bandit high severity | `bandit -r backend src -lll -f json -o tmp/bandit-high.json` | Pass | 0 high-severity findings; 19 low-severity informational results remained in the report. |
| Bandit full default profile | `bandit -r backend src scripts` | Low findings | Test assertions, intentional OCR subprocess invocation, and a non-cryptographic fixture generator were reported; no medium/high finding. |
| Secret pattern scan | `rg` for private-key/API-token patterns excluding environments/caches | Pass | No secret-shaped token matched. `.env.example` contains empty variable names only. |
| npm production audit | `npm audit --omit=dev --json` | Pass | 0 production vulnerabilities across the reported production dependency graph. |
| npm full audit | `npm audit --json` | Review required | 11 findings reported in the installed development tree: 9 moderate and 2 critical, with fixes available through a major `eslint-config-next` change. Re-run after dependency upgrades before shipping development tooling. |
| pip-audit | `pip-audit --format json` | Inconclusive | The configured vulnerability service did not return within the available run window and the command was interrupted; no zero-vulnerability claim is made. |

## Upload and privacy controls

- The API accepts only `.pdf`, `.txt`, `.png`, `.jpg` and `.jpeg` and checks file signatures/content against the extension and declared media type.
- Per-file, batch, page, extracted-character, OCR-pixel and processing limits are configurable through `CHANGEORDER_*` settings.
- Filenames are reduced to a basename and safe characters before use; uploads are written to a private `TemporaryDirectory` and removed after processing.
- The API does not persist documents or use a database. Logs record request IDs, filenames, page counts, status and timing, not document text, API keys or full evidence.
- Local deterministic extraction is the default. Enabling the optional LLM path is explicit and only advertised when the SDK and credentials are configured; the UI discloses that document text may leave the local process.
- CORS defaults to the two local development origins and is configurable. Credentials are not enabled by default.

## Direct dependency inventory

Licenses should be confirmed from the exact installed lock/metadata before redistribution. The project does not vendor third-party packages.

| Component | Use | License/compliance note |
|---|---|---|
| Pydantic | Typed Python schema/validation | Permissive MIT-style license. |
| PyMuPDF | Native PDF reading/rendering | PyMuPDF distribution requires an AGPL-3.0-or-later or commercial licensing decision. Verify the applicable commercial/AGPL obligations for the intended distribution. |
| simplejson | Decimal-safe serialization | MIT license. |
| FastAPI / Starlette / Uvicorn | HTTP API | Permissive licenses; review exact installed metadata. |
| python-multipart / httpx | Multipart parsing and API tests | Permissive package licenses; review exact installed metadata. |
| pytesseract / Pillow | Local OCR adapter and image preparation | Package licenses are permissive; the separately installed Tesseract/Leptonica binaries have their own Apache/BSD and bundled-component notices. |
| OpenAI Python SDK | Optional provider adapter | Optional dependency only; review the exact SDK license and provider terms. No key is stored in the repository. |
| Next.js / React / React DOM | Frontend runtime | Permissive MIT licenses. |
| lucide-react | UI icons | ISC license. |
| Tailwind CSS / PostCSS adapter | Styling/build | Permissive MIT licenses. |
| TypeScript / ESLint / Vitest | Development tooling | Review exact package metadata; development-only packages are not shipped by the Python package. |

## Dataset and document rights

Public access is not treated as permission to redistribute. `benchmarks/sources.csv` records source URLs, retrieval dates, document types and rights uncertainty. The downloaded Fresno PDF remains in `tmp/real-research` and is excluded from the final archive. The AIA example is explicitly excluded because the source states one-time licensed use. Candidate documents with unclear terms are referenced only, not copied.

## Unresolved items

- The full npm development-tree audit needs a future dependency refresh that preserves the verified Next.js build.
- A successful online `pip-audit` run should be completed in an environment with vulnerability-service access.
- Exact license notices for the installed transitive JavaScript tree should be generated from the final lockfile before any public binary distribution.
