import hashlib
from pathlib import Path

import pymupdf
import pytest

from changeorder import readers
from changeorder.provenance import evidence, lines
from changeorder.readers import InputError, ReaderOptions, read_file, read_text


def test_utf8_text_exact_raw_and_hash(tmp_path):
    text = "  Change Order: 0001\r\nProject: Café\n"
    path = tmp_path / "source.txt"
    path.write_bytes(b"\xef\xbb\xbf" + text.encode())
    source, issues = read_file(path)
    assert not issues
    assert source.pages[0].raw_text == text
    assert source.pages[0].page is None
    assert source.sha256 == hashlib.sha256(path.read_bytes()).hexdigest()


def test_native_pdf_and_multi_page(documents):
    source, issues = read_file(documents / "04_multipage.pdf", ReaderOptions(ocr="off"))
    assert not issues
    assert [page.page for page in source.pages] == [1, 2]
    assert "CO-004" in source.pages[0].raw_text
    assert "15,300.00" in source.pages[1].raw_text
    assert source.metadata["title"]


def test_scan_without_ocr_is_explicit(documents):
    source, issues = read_file(
        documents.parent / "ocr" / "13_scanned.pdf", ReaderOptions(ocr="off")
    )
    assert not source.pages[0].raw_text.strip()
    assert {issue.code for issue in issues} >= {"OCR_DISABLED", "NO_EXTRACTABLE_TEXT"}


def test_ocr_path_preserves_native_text(monkeypatch, documents):
    monkeypatch.setattr(
        readers,
        "_ocr_page",
        lambda page, options: ("CHANGE ORDER\nCO Number: 003\nProject: Scan\n", 0.8),
    )
    source, issues = read_file(documents.parent / "ocr" / "13_scanned.pdf")
    assert source.pages[0].text_origin == "ocr"
    assert source.pages[0].native_text == ""
    assert source.pages[0].ocr_quality == 0.8
    assert issues[0].code == "OCR_USED"


def test_ocr_unavailable_does_not_disappear(monkeypatch, documents):
    def unavailable(page, options):
        raise InputError("OCR_UNAVAILABLE", "not installed")

    monkeypatch.setattr(readers, "_ocr_page", unavailable)
    _, issues = read_file(documents.parent / "ocr" / "13_scanned.pdf")
    assert any(issue.code == "OCR_UNAVAILABLE" for issue in issues)


def test_ocr_merge_preserves_native_text(monkeypatch, documents):
    native_source, _ = read_file(documents / "03_digital.pdf", ReaderOptions(ocr="off"))
    native_text = native_source.pages[0].raw_text
    monkeypatch.setattr(readers, "_needs_ocr", lambda page, native: True)
    monkeypatch.setattr(
        readers,
        "_ocr_page",
        lambda page, options: ("CHANGE ORDER\nAdditional scanned financial table\n", 0.81),
    )
    source, issues = read_file(documents / "03_digital.pdf")
    page = source.pages[0]
    assert native_text.strip() in page.raw_text
    assert "Additional scanned financial table" in page.raw_text
    assert page.native_text == native_text
    assert page.text_origin == "native"
    assert any(issue.code == "OCR_USED" for issue in issues)
    page_lines = lines(page)
    native_line = next(line for line in page_lines if "CHANGE ORDER" in line.raw)
    ocr_line = next(line for line in page_lines if "Additional scanned" in line.raw)
    assert evidence(source, page, native_line).text_origin == "native"
    assert evidence(source, page, ocr_line).text_origin == "ocr"


def test_large_embedded_image_can_trigger_ocr(monkeypatch):
    class MixedPage:
        rect = type("Rect", (), {"width": 100, "height": 100})()

        def get_image_info(self, hashes=False):
            return [{"bbox": (0, 0, 80, 80)}]

    assert readers._needs_ocr(MixedPage(), "native text " * 30)


@pytest.mark.parametrize(
    ("filename", "content", "code"),
    [
        ("empty.txt", b"", "EMPTY_INPUT"),
        ("bad.pdf", b"not a pdf", "CORRUPT_PDF"),
        ("bad.csv", b"hello", "UNSUPPORTED_FORMAT"),
        ("bad.txt", b"\xff", "TEXT_ENCODING"),
        ("null.txt", b"abc\0def", "BINARY_TEXT"),
    ],
)
def test_input_failures(tmp_path, filename, content, code):
    path = tmp_path / filename
    path.write_bytes(content)
    with pytest.raises(InputError) as failure:
        read_file(path)
    assert failure.value.code == code


def test_input_limits(documents):
    with pytest.raises(InputError, match="limit"):
        read_text("x" * 101, options=ReaderOptions(max_chars=100))
    with pytest.raises(InputError, match="limit"):
        read_file(documents / "04_multipage.pdf", ReaderOptions(max_pages=1))
    with pytest.raises(InputError, match="limit"):
        read_file(documents / "01_clean.txt", ReaderOptions(max_bytes=20))


def test_encrypted_pdf(tmp_path):
    path = tmp_path / "locked.pdf"
    with pymupdf.open() as doc:
        doc.new_page().insert_text((72, 72), "CHANGE ORDER")
        doc.save(path, encryption=pymupdf.PDF_ENCRYPT_AES_256, owner_pw="owner", user_pw="user")
    with pytest.raises(InputError) as error:
        read_file(Path(path))
    assert error.value.code == "ENCRYPTED_PDF"
