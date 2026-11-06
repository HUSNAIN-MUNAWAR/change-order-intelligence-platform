"""Bounded text/PDF ingestion with per-page optional local OCR."""

import hashlib
import math
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path

from .normalization import clean_text
from .ocr import OCRError, recognize_image
from .schemas import Issue, PageText, Source

SUPPORTED_SUFFIXES = {".txt", ".pdf", ".png", ".jpg", ".jpeg"}


class InputError(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class ReaderOptions:
    ocr: str = "auto"
    max_bytes: int = 20 * 1024 * 1024
    max_pages: int = 100
    max_chars: int = 500_000
    ocr_timeout: int = 25
    max_ocr_pixels: int = 20_000_000

    def __post_init__(self):
        if self.ocr not in {"off", "auto", "force"}:
            raise ValueError("ocr must be off, auto, or force")
        if (
            min(
                self.max_bytes,
                self.max_pages,
                self.max_chars,
                self.ocr_timeout,
                self.max_ocr_pixels,
            )
            <= 0
        ):
            raise ValueError("Reader limits must be positive")


def _ocr_page(page, options: ReaderOptions) -> tuple[str, float | None]:
    try:
        from PIL import Image
    except ImportError as exc:
        raise InputError(
            "OCR_UNAVAILABLE", "Install the ocr extra and the local Tesseract executable"
        ) from exc
    scale = min(200 / 72, math.sqrt(options.max_ocr_pixels / (page.rect.width * page.rect.height)))
    import pymupdf

    try:
        pixmap = page.get_pixmap(
            matrix=pymupdf.Matrix(scale, scale), alpha=False, colorspace=pymupdf.csRGB
        )
    except (RuntimeError, ValueError) as exc:
        raise InputError("OCR_FAILED", "PDF page could not be rendered for local OCR") from exc
    image = Image.frombytes("RGB", (pixmap.width, pixmap.height), pixmap.samples)
    try:
        return recognize_image(image, timeout=options.ocr_timeout)
    except OCRError as exc:
        raise InputError(exc.code, str(exc)) from exc


def _needs_ocr(page, native: str) -> bool:
    """Detect empty pages and large scanned images with only a sparse native header."""
    characters = sum(character.isalnum() for character in native)
    if characters < 30:
        return True
    if characters >= 150:
        return False
    try:
        import pymupdf

        area = page.rect.width * page.rect.height
        for item in page.get_image_info():
            intersection = pymupdf.Rect(item["bbox"]) & page.rect
            if area > 0 and intersection.width * intersection.height / area >= 0.65:
                return True
    except (RuntimeError, ValueError):
        pass  # Retain usable native text if image inspection is unavailable.
    return False


def _read_image(path: Path, payload: bytes, options: ReaderOptions) -> tuple[Source, list[Issue]]:
    if options.ocr == "off":
        raise InputError("OCR_DISABLED", "Image input requires local OCR; enable OCR to process it")
    try:
        from PIL import Image, UnidentifiedImageError
    except ImportError as exc:
        raise InputError("OCR_UNAVAILABLE", "Install the ocr extra for image input") from exc
    try:
        with Image.open(BytesIO(payload)) as image:
            if image.format not in {"PNG", "JPEG"}:
                raise InputError(
                    "UNSUPPORTED_FORMAT", "Only PNG and JPEG image content is supported"
                )
            image_format = image.format
            if image.width * image.height > options.max_ocr_pixels:
                raise InputError("INPUT_LIMIT", "Image exceeds configured OCR pixel limit")
            image.load()
            text, quality = recognize_image(image, timeout=options.ocr_timeout)
            size = {
                "width": str(image.width),
                "height": str(image.height),
                "preprocessing": "EXIF orientation; grayscale; autocontrast",
            }
    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError) as exc:
        raise InputError("CORRUPT_IMAGE", "Image could not be decoded safely") from exc
    except OCRError as exc:
        raise InputError(exc.code, str(exc)) from exc
    if len(text) > options.max_chars:
        raise InputError("INPUT_LIMIT", "OCR text exceeds configured character limit")
    source = Source(
        identifier=path.name,
        filename=path.name,
        media_type="image/png" if image_format == "PNG" else "image/jpeg",
        sha256=hashlib.sha256(payload).hexdigest(),
        byte_count=len(payload),
        metadata=size,
        pages=[
            PageText(
                page=1,
                raw_text=text,
                cleaned_text=clean_text(text),
                text_origin="ocr",
                ocr_quality=quality,
            )
        ],
    )
    issues = [
        Issue(
            code="OCR_USED",
            severity="info",
            message="Local Tesseract OCR used on image 1; review recognition errors",
        )
    ]
    if not text.strip():
        issues.append(
            Issue(
                code="OCR_NO_TEXT",
                severity="fatal_error",
                message="Local OCR recovered no text from the image",
            )
        )
    return source, issues


def read_text(
    text: str, identifier: str = "raw-text", options: ReaderOptions | None = None
) -> Source:
    options = options or ReaderOptions()
    if not text.strip():
        raise InputError("EMPTY_INPUT", "Input contains no text")
    if "\x00" in text:
        raise InputError("BINARY_TEXT", "Text input contains null bytes")
    payload = text.encode("utf-8")
    if len(text) > options.max_chars or len(payload) > options.max_bytes:
        raise InputError("INPUT_LIMIT", "Text exceeds configured character or byte limit")
    return Source(
        identifier=identifier,
        sha256=hashlib.sha256(payload).hexdigest(),
        media_type="text/plain",
        byte_count=len(payload),
        pages=[PageText(raw_text=text, cleaned_text=clean_text(text), text_origin="text")],
    )


def read_file(path: Path, options: ReaderOptions | None = None) -> tuple[Source, list[Issue]]:
    options = options or ReaderOptions()
    if path.suffix.lower() not in SUPPORTED_SUFFIXES:
        raise InputError(
            "UNSUPPORTED_FORMAT", "Supported file extensions are .txt, .pdf, .png, .jpg and .jpeg"
        )
    try:
        if path.stat().st_size > options.max_bytes:
            raise InputError("INPUT_LIMIT", "Input exceeds configured byte limit")
        # Read one byte past the cap to enforce it even if the file grows after stat().
        with path.open("rb") as stream:
            payload = stream.read(options.max_bytes + 1)
    except OSError as exc:
        raise InputError(
            "FILE_READ_FAILED", f"Cannot read input file ({type(exc).__name__})"
        ) from exc
    if len(payload) > options.max_bytes:
        raise InputError("INPUT_LIMIT", "Input exceeds configured byte limit")
    if not payload:
        raise InputError("EMPTY_INPUT", "Input file is empty")
    if path.suffix.lower() in {".png", ".jpg", ".jpeg"}:
        return _read_image(path, payload, options)
    if path.suffix.lower() == ".txt":
        try:
            text = payload.decode("utf-8-sig")
        except UnicodeDecodeError as exc:
            raise InputError(
                "TEXT_ENCODING", "Text files must be UTF-8; convert legacy encodings explicitly"
            ) from exc
        source = read_text(text, path.name, options)
        source.filename = path.name
        source.sha256 = hashlib.sha256(payload).hexdigest()
        source.byte_count = len(payload)
        return source, []
    try:
        import pymupdf
    except ImportError as exc:
        raise InputError("PDF_DEPENDENCY", "Install PyMuPDF for PDF input") from exc
    try:
        document = pymupdf.open(stream=payload, filetype="pdf")
    except (RuntimeError, ValueError) as exc:
        raise InputError("CORRUPT_PDF", "PDF could not be opened") from exc
    issues = []
    source = Source(
        identifier=path.name,
        filename=path.name,
        media_type="application/pdf",
        sha256=hashlib.sha256(payload).hexdigest(),
        byte_count=len(payload),
    )
    with document:
        if document.needs_pass:
            raise InputError("ENCRYPTED_PDF", "Password-protected PDFs are unsupported")
        if document.is_repaired:
            issues.append(
                Issue(
                    code="PDF_REPAIRED",
                    message="PDF library repaired the file structure; review recovered content",
                )
            )
        if len(document) > options.max_pages:
            raise InputError("INPUT_LIMIT", "PDF exceeds configured page limit")
        source.metadata = {
            key: str(value) for key, value in (document.metadata or {}).items() if value
        }
        char_count = 0
        for number, page in enumerate(document, 1):
            try:
                native = page.get_text("text", sort=True)
            except (RuntimeError, ValueError):
                native = ""
                issues.append(
                    Issue(
                        code="PDF_PAGE_FAILED",
                        severity="recoverable_error",
                        message=f"Native text extraction failed on page {number}",
                    )
                )
            raw, origin, quality = native, "native", None
            sparse = _needs_ocr(page, native)
            if sparse or options.ocr == "force":
                if options.ocr == "off":
                    issues.append(
                        Issue(
                            code="OCR_DISABLED",
                            message=f"Page {number} has insufficient native text; OCR is disabled",
                        )
                    )
                else:
                    try:
                        ocr_text, quality = _ocr_page(page, options)
                        if ocr_text.strip() and (
                            options.ocr == "force" or len(ocr_text.strip()) > len(native.strip())
                        ):
                            raw, origin = ocr_text, "ocr"
                            issues.append(
                                Issue(
                                    code="OCR_USED",
                                    severity="info",
                                    message=f"Local OCR used on page {number}; review recognition errors",
                                )
                            )
                        else:
                            issues.append(
                                Issue(
                                    code="OCR_NO_TEXT",
                                    message=f"OCR recovered no additional text on page {number}",
                                )
                            )
                    except InputError as exc:
                        issues.append(
                            Issue(
                                code=exc.code,
                                severity="recoverable_error",
                                message=f"Page {number}: {exc}",
                            )
                        )
            char_count += len(raw) + (len(native) if origin == "ocr" else 0)
            if char_count > options.max_chars:
                raise InputError(
                    "INPUT_LIMIT", "Extracted PDF text exceeds configured character limit"
                )
            source.pages.append(
                PageText(
                    page=number,
                    raw_text=raw,
                    cleaned_text=clean_text(raw),
                    native_text=native if origin == "ocr" else None,
                    text_origin=origin,
                    ocr_quality=quality if origin == "ocr" else None,
                )
            )
    if not any(page.raw_text.strip() for page in source.pages):
        issues.append(
            Issue(
                code="NO_EXTRACTABLE_TEXT",
                severity="fatal_error",
                message="PDF contains no usable text; inspect OCR warnings",
            )
        )
    return source, issues
