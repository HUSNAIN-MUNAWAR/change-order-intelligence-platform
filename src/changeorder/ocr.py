"""Local Tesseract discovery, conservative image preparation and word-to-line reconstruction."""

import importlib.util
import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path


class OCRError(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class OCRStatus:
    available: bool
    version: str | None
    languages: tuple[str, ...]
    message: str


def tesseract_command() -> str:
    """Explicit override, PATH, then conventional Windows install directories."""
    if os.environ.get("TESSERACT_CMD"):
        return os.environ["TESSERACT_CMD"]
    located = shutil.which("tesseract")
    if located:
        return located
    candidates = []
    for variable in ("ProgramFiles", "ProgramFiles(x86)"):
        if os.environ.get(variable):
            candidates.append(Path(os.environ[variable]) / "Tesseract-OCR" / "tesseract.exe")
    if os.environ.get("LOCALAPPDATA"):
        root = Path(os.environ["LOCALAPPDATA"])
        candidates.extend(
            (
                root / "Programs" / "Tesseract-OCR" / "tesseract.exe",
                root / "Tesseract-OCR" / "tesseract.exe",
            )
        )
    return str(next((path for path in candidates if path.is_file()), "tesseract"))


def ocr_status() -> OCRStatus:
    if any(importlib.util.find_spec(name) is None for name in ("pytesseract", "PIL")):
        return OCRStatus(False, None, (), "Install the optional ocr dependencies.")
    command = tesseract_command()
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    try:
        version = subprocess.run(
            [command, "--version"],
            capture_output=True,
            text=True,
            timeout=5,
            creationflags=flags,
            check=True,
        )
        languages = subprocess.run(
            [command, "--list-langs"],
            capture_output=True,
            text=True,
            timeout=5,
            creationflags=flags,
            check=True,
        )
    except (OSError, subprocess.SubprocessError):
        return OCRStatus(
            False, None, (), "Tesseract is unavailable; install it or set TESSERACT_CMD."
        )
    available = tuple(
        line.strip()
        for line in languages.stdout.splitlines()
        if line.strip() and not line.startswith("List of")
    )
    version_line = (version.stdout or version.stderr).splitlines()[0]
    return OCRStatus(
        "eng" in available,
        version_line,
        available,
        "English local OCR is ready."
        if "eng" in available
        else "Install Tesseract English (eng) language data.",
    )


def prepare_image(image):
    """Honor EXIF orientation, convert to grayscale and stretch contrast without thresholding."""
    from PIL import ImageOps

    # Do not denoise/threshold by default: fine characters, decimals and table rules matter.
    return ImageOps.autocontrast(ImageOps.grayscale(ImageOps.exif_transpose(image)), cutoff=0)


def recognize_image(image, *, timeout: int = 25) -> tuple[str, float | None]:
    try:
        import pytesseract
    except ImportError as exc:
        raise OCRError(
            "OCR_UNAVAILABLE", "Install the ocr extra and the local Tesseract executable"
        ) from exc
    pytesseract.pytesseract.tesseract_cmd = tesseract_command()
    try:
        data = pytesseract.image_to_data(
            prepare_image(image), output_type=pytesseract.Output.DICT, timeout=timeout
        )
    except pytesseract.TesseractNotFoundError as exc:
        raise OCRError(
            "OCR_UNAVAILABLE", "Tesseract executable was not found; install it or set TESSERACT_CMD"
        ) from exc
    except (RuntimeError, pytesseract.TesseractError, OSError) as exc:
        raise OCRError("OCR_FAILED", "Local OCR failed or exceeded its time limit") from exc
    text_lines: dict[tuple, list[int]] = {}
    qualities = []
    for index, word in enumerate(data["text"]):
        if not word.strip():
            continue
        key = tuple(data[name][index] for name in ("block_num", "par_num", "line_num"))
        text_lines.setdefault(key, []).append(index)
        quality = float(data["conf"][index])
        if quality >= 0:
            qualities.append(min(1.0, quality / 100))
    result = []
    for indexes in text_lines.values():
        fragments = []
        previous = None
        for index in indexes:
            word = data["text"][index]
            separator = " "
            if previous is not None and "left" in data and "width" in data:
                gap = data["left"][index] - (data["left"][previous] + data["width"][previous])
                character_width = data["width"][previous] / max(1, len(data["text"][previous]))
                if gap > 3 * max(1, character_width):
                    separator = "   "
            fragments.append((separator if fragments else "") + word)
            previous = index
        result.append("".join(fragments))
    return "\n".join(result), (sum(qualities) / len(qualities) if qualities else None)
