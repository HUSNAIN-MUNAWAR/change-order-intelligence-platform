"""Rebuild the clearly synthetic PDF fixtures. Requires the dev extra."""

from io import BytesIO
from pathlib import Path

import pymupdf
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas

ROOT = Path(__file__).resolve().parents[1]


def write_pdf(destination: Path, pages: list[str]) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    document = canvas.Canvas(str(destination), pagesize=(612, 792), invariant=1)
    document.setTitle("Synthetic change-order extraction fixture")
    document.setAuthor("Synthetic assessment fixture; not supplied by Sledge")
    for number, text in enumerate(pages, 1):
        document.setFillColorRGB(0.12, 0.20, 0.27)
        document.setFont("Helvetica-Bold", 11)
        document.drawString(48, 748, "SYNTHETIC TEST DOCUMENT - NOT SUPPLIED BY SLEDGE")
        document.setFillColorRGB(0, 0, 0)
        y = 710
        for line in text.strip().splitlines():
            document.setFont(
                "Helvetica-Bold" if line == "CHANGE ORDER" else "Helvetica",
                12 if line == "CHANGE ORDER" else 10,
            )
            if document.stringWidth(line) > 516:
                raise ValueError("Fixture line exceeds page width; wrap it in the source")
            document.drawString(48, y, line)
            y -= 24
        document.setFont("Helvetica", 9)
        document.drawString(
            48, 36, f"Synthetic construction document | Page {number} of {len(pages)}"
        )
        document.showPage()
    document.save()


def main():
    for stem in ("03_digital", "04_multipage"):
        text = (ROOT / "examples" / "pdf_sources" / f"{stem}.txt").read_text(encoding="utf-8")
        write_pdf(ROOT / "examples" / "documents" / f"{stem}.pdf", text.split("---PAGE---"))
    scan_dir = ROOT / "examples" / "ocr"
    scan_dir.mkdir(parents=True, exist_ok=True)
    digital = ROOT / "examples" / "documents" / "03_digital.pdf"
    with pymupdf.open(digital) as source:
        png = source[0].get_pixmap(matrix=pymupdf.Matrix(2, 2)).tobytes("png")
    scan = canvas.Canvas(str(scan_dir / "13_scanned.pdf"), pagesize=(612, 792), invariant=1)
    scan.drawImage(ImageReader(BytesIO(png)), 0, 0, width=612, height=792)
    scan.save()
    print("Created two native PDFs and one image-only OCR fixture.")


if __name__ == "__main__":
    main()
