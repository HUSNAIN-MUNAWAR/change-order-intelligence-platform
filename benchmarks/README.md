# External Document Benchmark

This directory separates external-source research from the included synthetic fixtures.

The current external evaluation contains one downloaded public document from the City of Fresno. It is classified as **development data**, not held-out data, because its failure modes were inspected while implementing the generalized public-form layout patterns. The PDF is intentionally not stored in the repository because public downloadability does not establish redistribution rights.

## Reproduce

1. Review `sources.csv` and download only a source whose terms permit your intended local use.
2. Place the local file in a private directory outside the submission archive.
3. Review the original document and update a ground-truth JSON manually; never copy predicted output into the labels.
4. Run:

```powershell
python scripts/evaluate_real_documents.py --documents-dir tmp/real-research --output benchmarks/results/real-development.json
```

The evaluator reports only annotated fields, normalized exact match, field precision/recall/F1, unsupported-field false positives, source mode, status, processing time and per-document mismatches. It does not present this one development document as production accuracy.

## Dataset limitations

- One external document is not a statistically meaningful benchmark.
- No held-out external evaluation document is currently included; the supplied public URLs include guidance, templates and records with mixed access/reuse terms.
- The downloaded Fresno document is digitally generated/native text, not an OCR benchmark.
- Some facts are intentionally unannotated because the form layout or signature state does not support a reliable schema value.
- `sources.csv` records research candidates and rights uncertainty. Unclear documents are not redistributed in this repository.
