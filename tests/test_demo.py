from decimal import Decimal
from io import BytesIO
from pathlib import Path
from zipfile import ZipFile

import pytest
import simplejson

from changeorder import demo
from changeorder.demo import (
    FIELD_GROUPS,
    DemoInputError,
    DocumentInput,
    confidence_band,
    input_signature,
    json_payload,
    preview_pdf,
    process_document,
    summary,
    validate_inputs,
    zip_payload,
)
from changeorder.pipeline import PipelineOptions, extract
from changeorder.readers import ReaderOptions
from changeorder.schemas import ChangeOrder, ExtractionResult


def test_adapter_is_same_pipeline_and_json_as_cli(documents, offline):
    path = documents / "01_clean.txt"
    direct = extract(path, options=offline)
    adapted = process_document(DocumentInput(path.name, path.read_bytes()), offline)
    assert direct.model_dump(exclude={"processing_ms"}) == adapted.model_dump(
        exclude={"processing_ms"}
    )
    payload = json_payload(adapted)
    ExtractionResult.model_validate_json(payload)
    parsed = simplejson.loads(payload, use_decimal=True)
    assert parsed["data"]["total_change_amount"]["value"] == Decimal("12500.00")


def test_uploaded_input_temp_directory_is_cleaned(monkeypatch, offline):
    actual = demo.tempfile.TemporaryDirectory
    created = []

    def tracked(*args, **kwargs):
        directory = actual(*args, **kwargs)
        created.append(Path(directory.name))
        return directory

    monkeypatch.setattr(demo.tempfile, "TemporaryDirectory", tracked)
    document = DocumentInput("../../escape.txt", b"CHANGE ORDER\nCO Number: 1")
    result = process_document(document, offline)
    assert result.source.identifier == "escape.txt"
    assert len(created) == 1 and not created[0].exists()
    assert DocumentInput(r"C:\private\input.txt", b"").safe_name == "input.txt"


def test_batch_zip_contains_independent_valid_same_schema_results(documents, offline):
    good = documents / "01_clean.txt"
    results = [
        process_document(DocumentInput(good.name, good.read_bytes()), offline),
        process_document(DocumentInput("broken.pdf", b"bad pdf"), offline),
    ]
    with ZipFile(BytesIO(zip_payload(results))) as archive:
        assert archive.namelist() == ["01_01_clean.txt.json", "02_broken.pdf.json"]
        parsed = [
            ExtractionResult.model_validate_json(archive.read(name)) for name in archive.namelist()
        ]
    assert [result.status for result in parsed] == ["success", "failed"]


def test_no_unnecessary_processing_signature_changes_only_for_inputs_or_options(offline):
    docs = [DocumentInput("a.txt", b"one")]
    original = input_signature(docs, offline)
    assert input_signature(docs, offline) == original
    assert input_signature([DocumentInput("a.txt", b"two")], offline) != original
    assert input_signature(docs, PipelineOptions(reader=ReaderOptions(ocr="auto"))) != original


@pytest.mark.parametrize(
    "docs",
    [
        [],
        [DocumentInput("bad.csv", b"x")],
        [DocumentInput("big.txt", b"x" * (20 * 1024 * 1024 + 1))],
        [DocumentInput(f"{i}.txt", b"x") for i in range(9)],
    ],
)
def test_upload_bounds(docs):
    with pytest.raises(DemoInputError):
        validate_inputs(docs)


def test_field_groups_cover_unchanged_schema_and_confidence_thresholds(documents, offline):
    names = [name for group in FIELD_GROUPS.values() for name in group]
    assert len(names) == len(set(names)) and set(names) == set(ChangeOrder.model_fields)
    assert [confidence_band(value) for value in (0.9, 0.7, 0.699)] == ["High", "Medium", "Low"]
    assert confidence_band(0, missing=True) == "Missing"
    result = extract(documents / "06_conflict.txt", options=offline)
    counts = summary(result)
    assert counts["conflicts"] == 1 and counts["review"] >= 1
    assert counts["extracted"] + counts["missing"] == len(ChangeOrder.model_fields)


def test_preview_is_bounded_and_reports_corrupt_pdf(documents):
    path = documents / "04_multipage.pdf"
    png, count = preview_pdf(DocumentInput(path.name, path.read_bytes()), 1)
    assert png.startswith(b"\x89PNG") and count == 2
    with pytest.raises(DemoInputError):
        preview_pdf(DocumentInput("bad.pdf", b"bad"))
