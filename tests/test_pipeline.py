import json
from decimal import Decimal

import pytest
import simplejson
from conftest import ROOT

from changeorder.jsonio import dumps
from changeorder.pipeline import PipelineOptions, extract
from changeorder.schemas import ChangeOrder, ExtractionResult


def unwrap(value):
    if isinstance(value, dict):
        if "value" in value and "confidence" in value:
            return unwrap(value["value"])
        return {name: unwrap(item) for name, item in value.items()}
    if isinstance(value, list):
        return [unwrap(item) for item in value]
    return value


LABELS = simplejson.loads(
    (ROOT / "examples" / "expected" / "labels.json").read_text(encoding="utf-8"), use_decimal=True
)["cases"]


@pytest.mark.parametrize("filename", list(LABELS))
def test_all_labeled_examples_exact(filename, documents, offline):
    expected = LABELS[filename]
    result = extract(documents / filename, options=offline)
    assert result.status == expected["status"]
    assert {issue.code for issue in result.issues} >= set(expected.get("required_issues", []))
    serialized = dumps(result)
    ExtractionResult.model_validate_json(serialized)
    actual = simplejson.loads(serialized, use_decimal=True)["data"]
    assert {name: unwrap(actual[name]) for name in ChangeOrder.model_fields} == {
        name: expected["fields"].get(name) for name in ChangeOrder.model_fields
    }


def test_deterministic_results_and_exact_evidence(documents, offline):
    first = extract(documents / "04_multipage.pdf", options=offline)
    second = extract(documents / "04_multipage.pdf", options=offline)
    assert first.model_dump(exclude={"processing_ms"}) == second.model_dump(
        exclude={"processing_ms"}
    )

    def check_wrappers(value):
        if isinstance(value, dict):
            if "confidence" in value and "value" in value:
                assert 0 <= value["confidence"] <= 1
                for ev in value["evidence"] or []:
                    page = next(page for page in first.source.pages if page.page == ev["page"])
                    assert page.raw_text[ev["char_start"] : ev["char_end"]] == ev["text"]
                    assert ev["source"] == first.source.identifier
            for item in value.values():
                check_wrappers(item)
        elif isinstance(value, list):
            for item in value:
                check_wrappers(item)

    check_wrappers(first.data.model_dump())


def test_money_serializes_as_exact_number_and_not_string(offline):
    result = extract(
        text="CHANGE ORDER\nCO Number: 01\nProject: A\nTotal Change Amount: USD 99999999999999.99",
        options=offline,
    )
    serialized = dumps(result)
    actual = simplejson.loads(serialized, use_decimal=True)
    assert actual["data"]["total_change_amount"]["value"] == Decimal("99999999999999.99")
    assert not isinstance(json.loads(serialized)["data"]["total_change_amount"]["value"], str)


def test_raw_text_spans_no_fabricated_pages(offline):
    text = "  CHANGE ORDER\r\nCO Number:\t00004\r\nProject: X\n"
    result = extract(text=text, source_id="provided-text", options=offline)
    ev = result.data.change_order_number.evidence[0]
    assert ev.page is None and ev.line_start == 2
    assert text[ev.char_start : ev.char_end] == ev.text


def test_missing_optional_fields_do_not_make_success_impossible(offline):
    result = extract(
        text="CHANGE ORDER\nCO Number: 1\nProject: A\nTotal Change Amount: 0", options=offline
    )
    assert result.status == "success"
    assert "contractor" in result.missing_fields
    assert result.data.contractor.evidence is None


def test_configured_date_order_warns(offline):
    result = extract(
        text="CHANGE ORDER\nCO Number: 1\nProject: A\nTotal Change Amount: 0\nDocument Date: 06/07/2026",
        options=PipelineOptions(reader=offline.reader, date_order="mdy"),
    )
    assert result.data.document_date.value.isoformat() == "2026-06-07"
    assert result.data.document_date.validation == "warning"
    assert result.status == "partial"
