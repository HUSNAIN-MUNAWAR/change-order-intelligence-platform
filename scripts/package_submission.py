"""Package only reviewable source/documents/results, excluding environments and caches."""

import hashlib
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOP_LEVEL = {
    "README.md",
    "APPROACH.md",
    "SCHEMA.md",
    "TODO.md",
    "DELIVERY.md",
    "FILE_MANIFEST.txt",
    "pyproject.toml",
    "requirements.txt",
    ".env.example",
    ".gitignore",
    "streamlit_app.py",
    "PHASE2.md",
}
DIRECTORIES = {
    "backend",
    "benchmarks",
    "src",
    "tests",
    "scripts",
    "examples",
    "schema",
    ".github",
    ".streamlit",
    "docs",
    "frontend",
}
EXCLUDED_PARTS = {
    "__pycache__",
    ".next",
    ".turbo",
    "coverage",
    "node_modules",
}


def submission_files() -> list[Path]:
    files = [path for path in ROOT.iterdir() if path.is_file() and path.name in TOP_LEVEL]
    for name in sorted(DIRECTORIES):
        for path in (ROOT / name).rglob("*"):
            if (
                path.is_file()
                and not EXCLUDED_PARTS.intersection(path.parts)
                and not path.name.endswith((".pyc", ".pyo"))
                and path.name != "tsconfig.tsbuildinfo"
                and not any(part.endswith(".egg-info") for part in path.parts)
            ):
                files.append(path)
    return sorted(files, key=lambda path: path.relative_to(ROOT).as_posix())


def main():
    manifest_path = ROOT / "FILE_MANIFEST.txt"
    manifest_path.touch(exist_ok=True)
    manifest_path.write_text(
        "\n".join(path.relative_to(ROOT).as_posix() for path in submission_files()) + "\n",
        encoding="utf-8",
    )
    destination = ROOT.parent / f"{ROOT.name}.zip"
    with zipfile.ZipFile(destination, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in submission_files():
            archive.write(path, (Path(ROOT.name) / path.relative_to(ROOT)).as_posix())
    with zipfile.ZipFile(destination) as archive:
        bad = archive.testzip()
        if bad:
            raise RuntimeError(f"Archive failed integrity check: {bad}")
        names = archive.namelist()
    print(f"Created {destination.name}: {len(names)} files, {destination.stat().st_size:,} bytes")
    print(f"SHA-256: {hashlib.sha256(destination.read_bytes()).hexdigest()}")


if __name__ == "__main__":
    main()
