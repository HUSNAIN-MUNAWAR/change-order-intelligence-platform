import pymupdf
import pytest

from changeorder.readers import InputError, ReaderOptions, _ocr_page


def test_real_ocr_wrapper_reconstructs_lines_without_live_engine(monkeypatch, documents):
    import pytesseract

    captured = {}

    def recognize(image, **kwargs):
        captured["size"] = image.size
        captured.update(kwargs)
        return {
            "text": ["", "CHANGE", "ORDER", "CO:", "001"],
            "block_num": [0, 1, 1, 1, 1],
            "par_num": [0, 1, 1, 1, 1],
            "line_num": [0, 1, 1, 2, 2],
            "conf": [-1, 80, 90, 70, 80],
        }

    monkeypatch.setattr(pytesseract, "image_to_data", recognize)
    with pymupdf.open(documents / "03_digital.pdf") as doc:
        text, quality = _ocr_page(doc[0], ReaderOptions(max_ocr_pixels=2_000_000, ocr_timeout=7))
    assert text == "CHANGE ORDER\nCO: 001" and quality == 0.8
    assert captured["timeout"] == 7
    assert captured["size"][0] * captured["size"][1] <= 2_005_000


@pytest.mark.parametrize("kind", ["missing", "timeout", "engine_error"])
def test_real_ocr_wrapper_classifies_local_errors(monkeypatch, documents, kind):
    import pytesseract

    def fail(*args, **kwargs):
        if kind == "missing":
            raise pytesseract.TesseractNotFoundError()
        if kind == "engine_error":
            raise pytesseract.TesseractError(1, "simulated error")
        raise RuntimeError("simulated timeout")

    monkeypatch.setattr(pytesseract, "image_to_data", fail)
    with pymupdf.open(documents / "03_digital.pdf") as doc, pytest.raises(InputError) as error:
        _ocr_page(doc[0], ReaderOptions())
    assert error.value.code == ("OCR_UNAVAILABLE" if kind == "missing" else "OCR_FAILED")
