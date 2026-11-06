"""Reproducible, fully labeled synthetic evaluation; no API calls and no fabricated metrics."""

import argparse
import hashlib
import platform
from collections import Counter
from importlib.metadata import version
from pathlib import Path

import simplejson

from changeorder.jsonio import dumps, write_json
from changeorder.normalization import MONEY_FIELDS
from changeorder.pipeline import PipelineOptions, extract
from changeorder.readers import ReaderOptions
from changeorder.schemas import ChangeOrder, ExtractionResult

ROOT = Path(__file__).resolve().parents[1]


def plain(value):
    """Strip support wrappers for semantic value comparison, including nested cost items."""
    if isinstance(value, dict):
        if "confidence" in value and "value" in value:
            return plain(value["value"])
        return {name: plain(item) for name, item in value.items()}
    if isinstance(value, list):
        return [plain(item) for item in value]
    return value


def evaluate() -> dict:
    labels_path = ROOT / "examples" / "expected" / "labels.json"
    labels = simplejson.loads(labels_path.read_text(encoding="utf-8"), use_decimal=True)["cases"]
    counts = Counter()
    buckets = {name: Counter() for name in ["0.00-0.49", "0.50-0.69", "0.70-0.89", "0.90-1.00"]}
    cases = []
    for filename, expected in labels.items():
        path = ROOT / "examples" / "documents" / filename
        result = extract(path, options=PipelineOptions(reader=ReaderOptions(ocr="off")))
        serialized = dumps(result)
        ExtractionResult.model_validate_json(serialized)
        counts["schema_valid"] += 1
        fields = simplejson.loads(serialized, use_decimal=True)["data"]
        mismatches = []
        for name in ChangeOrder.model_fields:
            actual, truth = plain(fields[name]), expected["fields"].get(name)
            same = actual == truth
            counts["fields"] += 1
            counts["exact"] += same
            if actual is not None and same:
                counts["tp"] += 1
            if actual is not None and not same:
                counts["fp"] += 1
            if truth is not None and not same:
                counts["fn"] += 1
            if truth is None:
                counts["missing"] += 1
                counts["missing_fp"] += actual is not None
            if name in MONEY_FIELDS | {"schedule_impact"} and truth is not None:
                counts["numeric"] += 1
                counts["numeric_correct"] += same
            if actual is not None:
                confidence = float(fields[name]["confidence"])
                bucket = (
                    "0.00-0.49"
                    if confidence < 0.5
                    else "0.50-0.69"
                    if confidence < 0.7
                    else "0.70-0.89"
                    if confidence < 0.9
                    else "0.90-1.00"
                )
                buckets[bucket]["count"] += 1
                buckets[bucket]["correct"] += same
            if not same:
                mismatches.append({"field": name, "expected": truth, "actual": actual})
        missing_issues = sorted(
            set(expected.get("required_issues", [])) - {issue.code for issue in result.issues}
        )
        status_correct = result.status == expected["status"]
        counts["status_correct"] += status_correct
        counts["document_exact"] += not mismatches
        cases.append(
            {
                "file": filename,
                "sha256": result.source.sha256,
                "status": result.status,
                "expected_status": expected["status"],
                "status_correct": status_correct,
                "missing_required_issues": missing_issues,
                "mismatches": mismatches,
                "processing_ms": result.processing_ms,
                "issues": [issue.code for issue in result.issues],
            }
        )
    precision = counts["tp"] / (counts["tp"] + counts["fp"]) if counts["tp"] + counts["fp"] else 0
    recall = counts["tp"] / (counts["tp"] + counts["fn"]) if counts["tp"] + counts["fn"] else 0
    return {
        "dataset": "12 hand-authored synthetic cases; development set, not held out",
        "ground_truth_sha256": hashlib.sha256(labels_path.read_bytes()).hexdigest(),
        "configuration": {
            "ocr": "off",
            "llm": False,
            "date_order": "reject",
            "python": platform.python_version(),
            "platform": platform.system(),
            "dependencies": {name: version(name) for name in ("pydantic", "PyMuPDF", "simplejson")},
        },
        "documents": len(cases),
        "field_comparisons": counts["fields"],
        "counts": dict(counts),
        "metrics": {
            "field_precision": precision,
            "field_recall": recall,
            "field_f1": 2 * precision * recall / (precision + recall) if precision + recall else 0,
            "field_exact_match": counts["exact"] / counts["fields"],
            "document_exact_match": counts["document_exact"] / len(cases),
            "numeric_accuracy": counts["numeric_correct"] / counts["numeric"],
            "missing_field_false_positive_rate": counts["missing_fp"] / counts["missing"],
            "schema_validation_rate": counts["schema_valid"] / len(cases),
            "status_accuracy": counts["status_correct"] / len(cases),
        },
        "confidence_buckets": {
            name: {
                "count": bucket["count"],
                "correct": bucket["correct"],
                "accuracy": bucket["correct"] / bucket["count"] if bucket["count"] else None,
            }
            for name, bucket in buckets.items()
        },
        "mean_processing_ms": sum(case["processing_ms"] for case in cases) / len(cases),
        "limitations": "Small synthetic development benchmark with correlated fields. Exact match includes absent fields. Line item collection scored as one top-level field. Conflicts score the documented representative plus mandatory review issues, not an adjudicated true value. Confidence buckets are descriptive, not calibration evidence. OCR/live LLM accuracy is not measured here.",
        "cases": cases,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "examples" / "evaluation.json")
    args = parser.parse_args()
    report = evaluate()
    write_json(args.output, report)
    print(
        dumps(
            {
                key: report[key]
                for key in (
                    "documents",
                    "field_comparisons",
                    "metrics",
                    "confidence_buckets",
                    "mean_processing_ms",
                )
            }
        )
    )
    return int(
        any(
            case["mismatches"] or not case["status_correct"] or case["missing_required_issues"]
            for case in report["cases"]
        )
    )


if __name__ == "__main__":
    raise SystemExit(main())
