"""Create additional small synthetic OCR fixtures without changing the original examples."""

import random
from io import BytesIO
from pathlib import Path

import pymupdf
from PIL import Image, ImageDraw, ImageFilter, ImageOps

ROOT = Path(__file__).resolve().parents[1]
OCR = ROOT / "examples" / "ocr"


def main():
    with (
        pymupdf.open(ROOT / "examples/documents/03_digital.pdf") as native,
        pymupdf.open(OCR / "13_scanned.pdf") as scanned,
        pymupdf.open() as mixed,
    ):
        mixed.insert_pdf(native)
        mixed.insert_pdf(scanned)
        mixed.set_metadata(
            {
                "title": "Synthetic mixed native and scanned OCR fixture",
                "author": "Synthetic fixture; not supplied by Sledge",
            }
        )
        mixed.save(OCR / "14_mixed.pdf", deflate=True)
        pixels = scanned[0].get_pixmap(matrix=pymupdf.Matrix(2, 2)).tobytes("png")
    with Image.open(BytesIO(pixels)) as original:
        original.convert("RGB").save(OCR / "17_clear.jpg", quality=92, dpi=(144, 144))
        noisy = ImageOps.grayscale(original).point(lambda intensity: int(50 + intensity * 0.70))
        drawing = ImageDraw.Draw(noisy)
        rng = random.Random(15)
        for _ in range(2500):
            drawing.point(
                (rng.randrange(noisy.width), rng.randrange(noisy.height)),
                fill=rng.randrange(100, 235),
            )
        noisy = noisy.filter(ImageFilter.GaussianBlur(0.25)).rotate(
            0.5, resample=Image.Resampling.BICUBIC, expand=True, fillcolor=228
        )
        noisy.save(OCR / "15_noisy.png", optimize=True, dpi=(144, 144))
    blank = Image.new("RGB", (600, 800), "white")
    blank.save(OCR / "16_blank.png", optimize=True)
    with pymupdf.open() as blank_pdf:
        page = blank_pdf.new_page(width=300, height=400)
        page.insert_image(page.rect, filename=str(OCR / "16_blank.png"))
        blank_pdf.set_metadata({"title": "Synthetic blank image-only OCR failure fixture"})
        blank_pdf.save(OCR / "16_blank.pdf", deflate=True)
    print("Created mixed PDF, noisy PNG, clear JPEG, blank PNG and blank image-only PDF.")


if __name__ == "__main__":
    main()
