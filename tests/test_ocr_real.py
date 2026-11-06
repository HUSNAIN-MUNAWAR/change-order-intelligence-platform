from pathlib import Path

import pytest

from changeorder import readers
from changeorder.ocr import OCRError, ocr_status, prepare_image, recognize_image, tesseract_command
from changeorder.pipeline import extract
from changeorder.readers import InputError, ReaderOptions, read_file


@pytest.fixture
def real_ocr():
    status = ocr_status()
    if not status.available:
        pytest.skip(status.message)
    return status


@pytest.mark.ocr
@pytest.mark.parametrize("filename", ["13_scanned.pdf", "15_noisy.png", "17_clear.jpg"])
def test_genuine_ocr_extracts_known_source_facts(real_ocr, documents, filename):
    result = extract(documents.parent / "ocr" / filename)
    assert result.status == "success"
    assert result.data.change_order_number.value == "CO-003"
    assert result.data.project_name.value == "Harbor Warehouse"
    assert result.data.final_amount.value == 6400
    assert result.data.currency.value == "EUR"
    assert result.data.approval_status.value == "approved"
    assert result.source.pages[0].text_origin == "ocr"
    assert 0 <= result.source.pages[0].ocr_quality <= 1
    native = extract(documents / "03_digital.pdf")
    assert result.data.total_change_amount.confidence < native.data.total_change_amount.confidence
    for field in (result.data.change_order_number, result.data.total_change_amount):
        ev = field.evidence[0]
        assert ev.page == 1 and ev.text_origin == "ocr"
        assert result.source.pages[0].raw_text[ev.char_start : ev.char_end] == ev.text


@pytest.mark.ocr
def test_mixed_pdf_ocr_runs_only_on_the_scanned_page(real_ocr, monkeypatch, documents):
    actual = readers._ocr_page
    calls = []

    def traced(page, options):
        calls.append(page.number + 1)
        return actual(page, options)

    monkeypatch.setattr(readers, "_ocr_page", traced)
    result = extract(documents.parent / "ocr" / "14_mixed.pdf")
    assert result.status == "success" and calls == [2]
    assert [page.text_origin for page in result.source.pages] == ["native", "ocr"]
    assert {ev.page for ev in result.data.change_order_number.evidence} == {1, 2}
    assert result.source.pages[1].native_text == ""


@pytest.mark.ocr
@pytest.mark.parametrize("filename", ["16_blank.pdf", "16_blank.png"])
def test_real_empty_ocr_is_never_success(real_ocr, documents, filename):
    result = extract(documents.parent / "ocr" / filename)
    assert result.status == "failed"
    assert any(issue.code == "OCR_NO_TEXT" for issue in result.issues)
    assert not any(page.raw_text.strip() for page in result.source.pages)


@pytest.mark.ocr
def test_genuine_engine_timeout_is_reported(real_ocr):
    from PIL import Image

    with pytest.raises(OCRError) as error:
        recognize_image(Image.new("RGB", (1500, 1500), "white"), timeout=0.000001)
    assert error.value.code == "OCR_FAILED"


def test_missing_executable_is_a_recoverable_mixed_page_error(monkeypatch, documents, tmp_path):
    monkeypatch.setenv("TESSERACT_CMD", str(tmp_path / "missing-tesseract.exe"))
    assert not ocr_status().available
    result = extract(documents.parent / "ocr" / "14_mixed.pdf")
    assert result.status == "partial" and result.data.change_order_number.value == "CO-003"
    assert any(issue.code == "OCR_UNAVAILABLE" for issue in result.issues)


def test_explicit_override_and_windows_install_discovery(monkeypatch, tmp_path):
    monkeypatch.setenv("TESSERACT_CMD", "explicit-override")
    assert tesseract_command() == "explicit-override"
    monkeypatch.delenv("TESSERACT_CMD")
    monkeypatch.setattr("changeorder.ocr.shutil.which", lambda name: None)
    monkeypatch.setenv("ProgramFiles", str(tmp_path))
    target = tmp_path / "Tesseract-OCR" / "tesseract.exe"
    target.parent.mkdir()
    target.touch()
    assert Path(tesseract_command()) == target


def test_non_destructive_preprocessing_honors_exif():
    from PIL import Image

    image = Image.new("RGB", (200, 100), (240, 240, 240))
    image.getexif()[274] = 6
    prepared = prepare_image(image)
    assert prepared.mode == "L" and prepared.size == (100, 200)


@pytest.mark.parametrize(
    ("name", "content", "code"),
    [("broken.png", b"not an image", "CORRUPT_IMAGE"), ("empty.jpg", b"", "EMPTY_INPUT")],
)
def test_unreadable_image_is_reported(tmp_path, name, content, code):
    path = tmp_path / name
    path.write_bytes(content)
    result = extract(path)
    assert result.status == "failed" and result.issues[0].code == code


def test_images_require_ocr_and_obey_pixel_limit(documents, monkeypatch, tmp_path):
    path = documents.parent / "ocr" / "17_clear.jpg"
    with pytest.raises(InputError) as failure:
        read_file(path, ReaderOptions(ocr="off"))
    assert failure.value.code == "OCR_DISABLED"
    with pytest.raises(InputError) as failure:
        read_file(path, ReaderOptions(max_ocr_pixels=100))
    assert failure.value.code == "INPUT_LIMIT"
    monkeypatch.setattr(
        readers, "recognize_image", lambda image, timeout: ("CHANGE ORDER\nCO Number: 3", 0.8)
    )
    misleading_name = tmp_path / "jpeg-content.png"
    misleading_name.write_bytes(path.read_bytes())
    source, _ = read_file(misleading_name)
    assert source.media_type == "image/jpeg"


def test_empty_ocr_response_preserves_explicit_warning(monkeypatch, documents):
    monkeypatch.setattr(readers, "_ocr_page", lambda page, options: ("", None))
    source, issues = read_file(documents.parent / "ocr" / "13_scanned.pdf")
    assert not source.pages[0].raw_text
    assert {issue.code for issue in issues} >= {"OCR_NO_TEXT", "NO_EXTRACTABLE_TEXT"}


@pytest.mark.ocr
def test_sparse_native_header_does_not_hide_full_scanned_page(real_ocr, documents, tmp_path):
    import pymupdf

    path = tmp_path / "sparse-layer.pdf"
    with pymupdf.open(documents.parent / "ocr" / "13_scanned.pdf") as pdf:
        pdf[0].insert_text((40, 20), "SYNTHETIC NATIVE HEADER - SCANNED DOCUMENT BELOW", fontsize=9)
        pdf.save(path)
    result = extract(path)
    assert result.status == "success" and result.source.pages[0].text_origin == "ocr"
    assert "SYNTHETIC NATIVE HEADER" in result.source.pages[0].native_text
    assert result.data.change_order_number.value == "CO-003"


def test_pdf_render_failure_is_recoverable_input_error():
    from types import SimpleNamespace

    class BrokenPage:
        rect = SimpleNamespace(width=612, height=792)

        def get_pixmap(self, **kwargs):
            raise RuntimeError("damaged image stream")

    with pytest.raises(InputError) as error:
        readers._ocr_page(BrokenPage(), ReaderOptions())
    assert error.value.code == "OCR_FAILED"
