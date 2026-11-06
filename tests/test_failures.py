import pytest

from changeorder.pipeline import PipelineOptions, extract
from changeorder.readers import ReaderOptions


@pytest.mark.parametrize("text", ["", "   ", "\x00binary"])
def test_invalid_raw_text_failed(text, offline):
    result = extract(text=text, options=offline)
    assert result.status == "failed"
    assert any(issue.severity == "fatal_error" for issue in result.issues)
    assert result.data.total_change_amount.value is None


def test_non_change_order_does_not_leak_generic_fields(documents, offline):
    result = extract(documents / "12_unrelated.txt", options=offline)
    assert result.status == "failed"
    assert result.data.project_name.value is None
    assert result.data.total_change_amount.value is None


def test_heading_alone_is_not_success(offline):
    result = extract(text="CHANGE ORDER", options=offline)
    assert result.status == "failed"
    assert any(issue.code == "NO_CHANGE_ORDER_FACTS" for issue in result.issues)


def test_missing_input_and_scan_failure(tmp_path, documents, offline):
    missing = extract(tmp_path / "missing.pdf", options=offline)
    assert missing.status == "failed"
    assert missing.issues[0].code == "FILE_READ_FAILED"
    scan = extract(documents.parent / "ocr" / "13_scanned.pdf", options=offline)
    assert scan.status == "failed"
    assert any(issue.code == "NO_EXTRACTABLE_TEXT" for issue in scan.issues)


def test_llm_missing_configuration_preserves_baseline(monkeypatch, documents, offline):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("CHANGEORDER_LLM_MODEL", raising=False)
    result = extract(
        documents / "01_clean.txt", options=PipelineOptions(reader=offline.reader, llm=True)
    )
    assert result.status == "partial"
    assert result.data.change_order_number.value == "CO-001"
    assert not result.llm_used
    assert any(issue.code == "LLM_CONFIGURATION" for issue in result.issues)


def test_programming_errors_are_not_swallowed(offline):
    class BrokenExtractor:
        def extract(self, source, date_order):
            raise RuntimeError("bug in custom adapter")

    with pytest.raises(RuntimeError, match="bug"):
        extract(text="CHANGE ORDER\nCO Number: 1", options=offline, llm_extractor=BrokenExtractor())
    with pytest.raises(ValueError):
        extract()
    with pytest.raises(ValueError):
        ReaderOptions(max_pages=0)
