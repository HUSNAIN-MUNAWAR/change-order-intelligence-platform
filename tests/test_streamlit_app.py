from pathlib import Path

import pytest

pytest.importorskip("streamlit")
from streamlit.testing.v1 import AppTest

ROOT = Path(__file__).resolve().parents[1]


def app():
    return AppTest.from_file(str(ROOT / "streamlit_app.py"), default_timeout=60).run()


def test_initial_ui_requires_no_key_and_uses_real_example(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    a = app()
    assert not a.exception and not a.metric
    assert a.toggle(key="use_llm").disabled
    a.button(key="extract").click().run()
    assert not a.exception
    assert a.session_state["run"]["records"][0][1].data.change_order_number.value == "CO-003"
    assert len(a.get("download_button")) == 1


def test_display_reruns_do_not_repeat_pipeline(monkeypatch):
    from changeorder import demo

    actual = demo.process_document
    calls = []

    def counted(*args, **kwargs):
        calls.append(1)
        return actual(*args, **kwargs)

    monkeypatch.setattr(demo, "process_document", counted)
    a = app()
    assert not calls
    a.button(key="extract").click().run()
    a.selectbox(key="field_group").set_value("Financial information").run()
    a.checkbox(key="show_raw").check().run()
    assert len(calls) == 1 and not a.exception
    a.selectbox(key="example").set_value("Conflicting change amounts").run()
    assert "run" not in a.session_state and len(calls) == 1
    a.button(key="extract").click().run()
    assert len(calls) == 2
    assert a.session_state["run"]["records"][0][1].status == "partial"


def test_upload_mixed_batch_displays_failure_and_zip():
    a = app()
    a.radio(key="input_source").set_value("Upload documents").run()
    payload = (ROOT / "examples/documents/01_clean.txt").read_bytes()
    a.file_uploader[0].set_value(
        [("good.txt", payload, "text/plain"), ("corrupt.pdf", b"not a PDF", "application/pdf")]
    ).run()
    a.button(key="extract").click().run()
    assert not a.exception
    records = a.session_state["run"]["records"]
    assert [result.status for _, result in records] == ["success", "failed"]
    assert len(a.get("download_button")) == 2
    a.selectbox(key="document_result").set_value(1).run()
    assert not a.exception and a.error


@pytest.mark.ocr
def test_real_scanned_pdf_end_to_end_streamlit_display():
    from changeorder.ocr import ocr_status

    if not ocr_status().available:
        pytest.skip("Local Tesseract is unavailable")
    a = app()
    a.selectbox(key="example").set_value("Scanned PDF - real local OCR").run()
    a.button(key="extract").click().run()
    assert not a.exception
    result = a.session_state["run"]["records"][0][1]
    assert (
        result.source.pages[0].text_origin == "ocr"
        and result.data.total_change_amount.value == 6400
    )
    assert any(metric.label == "OCR pages" and metric.value == "1" for metric in a.metric)
    assert a.code[-1].language == "json"
