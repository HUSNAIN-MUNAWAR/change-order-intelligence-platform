"""Measure genuine local OCR on original, mixed, noisy and JPEG synthetic fixtures."""

import platform
from pathlib import Path

import simplejson
from evaluate_examples import plain

from changeorder.jsonio import dumps, write_json
from changeorder.ocr import ocr_status
from changeorder.pipeline import extract
from changeorder.schemas import ChangeOrder

ROOT = Path(__file__).resolve().parents[1]
OCR = ROOT / "examples" / "ocr"


def distance(first, second) -> int:
    previous = list(range(len(second) + 1))
    for row, item in enumerate(first, 1):
        current = [row]
        for column, other in enumerate(second, 1):
            current.append(
                min(current[-1] + 1, previous[column] + 1, previous[column - 1] + (item != other))
            )
        previous = current
    return previous[-1]


def main() -> int:
    engine = ocr_status()
    if not engine.available:
        print(engine.message)
        return 2
    labels = simplejson.loads(
        (ROOT / "examples/expected/labels.json").read_text(encoding="utf-8"), use_decimal=True
    )["cases"]["03_digital.pdf"]["fields"]
    native = extract(ROOT / "examples/documents/03_digital.pdf")
    target_text = " ".join(native.source.pages[0].raw_text.split())
    cases = []
    correct = 0
    for filename in ("13_scanned.pdf", "14_mixed.pdf", "15_noisy.png", "17_clear.jpg"):
        result = extract(OCR / filename)
        write_json(OCR / f"{filename}.result.json", result)
        actual = simplejson.loads(dumps(result), use_decimal=True)["data"]
        differences = []
        for name in ChangeOrder.model_fields:
            expected, value = labels.get(name), plain(actual[name])
            if expected == value:
                correct += 1
            else:
                differences.append({"field": name, "expected": expected, "actual": value})
        quality = []
        for page in result.source.pages:
            if page.text_origin != "ocr":
                continue
            recovered = " ".join(page.raw_text.split())
            quality.append(
                {
                    "page": page.page,
                    "word_error_rate": distance(target_text.split(), recovered.split())
                    / len(target_text.split()),
                    "character_error_rate": distance(target_text, recovered) / len(target_text),
                    "tesseract_mean_word_score": page.ocr_quality,
                }
            )
        (OCR / f"{filename}.raw.txt").write_text(
            "\n\n".join(
                f"PAGE {page.page} [{page.text_origin}]\n{page.raw_text}"
                for page in result.source.pages
            ),
            encoding="utf-8",
        )
        cases.append(
            {
                "file": filename,
                "status": result.status,
                "page_origins": [page.text_origin for page in result.source.pages],
                "field_comparisons": len(ChangeOrder.model_fields),
                "mismatches": differences,
                "text_quality": quality,
                "total_change_amount": result.data.total_change_amount.value,
                "total_field_confidence": result.data.total_change_amount.confidence,
                "native_total_field_confidence": native.data.total_change_amount.confidence,
                "processing_ms": result.processing_ms,
                "sha256": result.source.sha256,
            }
        )
    negatives = []
    for filename in ("16_blank.pdf", "16_blank.png"):
        result = extract(OCR / filename)
        write_json(OCR / f"{filename}.result.json", result)
        negatives.append(
            {
                "file": filename,
                "status": result.status,
                "issues": [issue.code for issue in result.issues],
                "expected_failure": result.status == "failed"
                and any(issue.code == "OCR_NO_TEXT" for issue in result.issues),
            }
        )
    comparisons = len(cases) * len(ChangeOrder.model_fields)
    report = {
        "engine": {"version": engine.version, "languages": list(engine.languages)},
        "platform": platform.system(),
        "python": platform.python_version(),
        "genuine_local_ocr": True,
        "network_api_used": False,
        "positive_documents": len(cases),
        "field_comparisons": comparisons,
        "field_matches": correct,
        "field_exact_match": correct / comparisons,
        "negative_cases_passed": sum(case["expected_failure"] for case in negatives),
        "mean_processing_ms": sum(case["processing_ms"] for case in cases) / len(cases),
        "cases": cases,
        "negative_cases": negatives,
        "limitations": "Four related, clearly synthetic representations of one source document, not four independent construction forms. Word/character error rates compare whitespace-normalized OCR with native PDF text. These results measure this small experiment, not production accuracy or confidence calibration. Real engine availability and timeout/missing-engine behavior are separately exercised in pytest.",
    }
    write_json(OCR / "evaluation.json", report)
    print(
        dumps(
            {
                key: report[key]
                for key in (
                    "engine",
                    "genuine_local_ocr",
                    "positive_documents",
                    "field_comparisons",
                    "field_matches",
                    "field_exact_match",
                    "negative_cases_passed",
                    "mean_processing_ms",
                )
            }
        )
    )
    return int(correct != comparisons or not all(case["expected_failure"] for case in negatives))


if __name__ == "__main__":
    raise SystemExit(main())
