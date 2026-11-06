"""Evaluate manually reviewed external documents without using model output as labels."""

from __future__ import annotations

import argparse
import json
import platform
import time
from datetime import date
from decimal import Decimal
from pathlib import Path

from changeorder.pipeline import extract

ROOT = Path(__file__).resolve().parents[1]


def normalize(value):
    if isinstance(value, Decimal):
        return format(value, "f")
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, list):
        return [normalize(item) for item in value]
    return value


def evaluate(documents_dir: Path) -> dict:
    labels_dir = ROOT / "benchmarks" / "ground_truth"
    cases = []
    counts = {
        "annotated_fields": 0,
        "correct": 0,
        "predicted_non_null": 0,
        "expected_non_null": 0,
        "false_positives": 0,
        "unsupported_checked": 0,
        "unsupported_false_positives": 0,
    }
    for label_path in sorted(labels_dir.glob("*.json")):
        expected = json.loads(label_path.read_text(encoding="utf-8"))
        input_path = documents_dir / expected["filename"]
        if not input_path.exists():
            cases.append(
                {
                    "file": expected["filename"],
                    "split": expected["split"],
                    "status": "not_run",
                    "error": "Local source file is absent; download it according to sources.csv.",
                }
            )
            continue
        started = time.perf_counter()
        result = extract(input_path)
        elapsed_ms = round((time.perf_counter() - started) * 1000, 3)
        mismatches = []
        for name, truth in expected["fields"].items():
            actual = normalize(getattr(result.data, name).value)
            truth_normalized = normalize(truth)
            counts["annotated_fields"] += 1
            counts["expected_non_null"] += truth is not None
            counts["predicted_non_null"] += actual is not None
            same = actual == truth_normalized
            counts["correct"] += same
            counts["false_positives"] += actual is not None and truth is None
            if not same:
                mismatches.append({"field": name, "expected": truth_normalized, "actual": actual})
        for name in expected.get("unsupported_fields", []):
            counts["unsupported_checked"] += 1
            actual = normalize(getattr(result.data, name).value)
            counts["unsupported_false_positives"] += actual is not None
        cases.append(
            {
                "file": expected["filename"],
                "split": expected["split"],
                "status": result.status,
                "source_mode": sorted({page.text_origin for page in result.source.pages}),
                "processing_ms": elapsed_ms,
                "annotated_fields": len(expected["fields"]),
                "mismatches": mismatches,
                "issues": [issue.code for issue in result.issues],
                "sha256": result.source.sha256,
            }
        )
    annotated = counts["annotated_fields"]
    precision_denominator = counts["predicted_non_null"]
    recall_denominator = counts["expected_non_null"]
    precision = counts["correct"] / precision_denominator if precision_denominator else 0
    recall = counts["correct"] / recall_denominator if recall_denominator else 0
    return {
        "dataset": "external public documents with manually reviewed labels",
        "platform": platform.system(),
        "ground_truth_is_model_independent": True,
        "documents": len(cases),
        "counts": counts,
        "metrics": {
            "annotated_field_exact_match": counts["correct"] / annotated if annotated else 0,
            "field_precision": precision,
            "field_recall": recall,
            "field_f1": 2 * precision * recall / (precision + recall) if precision + recall else 0,
            "unsupported_field_false_positive_rate": counts["unsupported_false_positives"]
            / counts["unsupported_checked"]
            if counts["unsupported_checked"]
            else 0,
        },
        "split_counts": {
            split: sum(case.get("split") == split for case in cases)
            for split in {case.get("split") for case in cases}
        },
        "limitations": "One development document is currently available locally. It was inspected during a generalized extractor fix and is not held out. Public source availability and redistribution rights vary; candidate sources are documented separately and unclear documents are not copied into the repository.",
        "cases": cases,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--documents-dir", type=Path, required=True)
    parser.add_argument(
        "--output", type=Path, default=ROOT / "benchmarks" / "results" / "real-development.json"
    )
    args = parser.parse_args()
    report = evaluate(args.documents_dir)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, default=str) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "documents": report["documents"],
                "metrics": report["metrics"],
                "cases": report["cases"],
            },
            indent=2,
        )
    )
    return (
        0
        if all(
            case.get("status") != "not_run" and not case.get("mismatches")
            for case in report["cases"]
        )
        else 1
    )


if __name__ == "__main__":
    raise SystemExit(main())
