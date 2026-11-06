"""Read-only integrity audit of schema, saved provenance, documentation and packaged files."""

import json
import re
import zipfile
from pathlib import Path

from changeorder.schemas import ExtractionResult

ROOT = Path(__file__).resolve().parents[1]


def verify_spans(value, pages, source_id, input_path):
    if isinstance(value, dict):
        if {"char_start", "char_end", "text_origin", "text"} <= value.keys():
            page = pages[value["page"]]
            assert page.raw_text[value["char_start"] : value["char_end"]] == value["text"], (
                input_path
            )
            assert value["source"] == source_id, input_path
        for child in value.values():
            verify_spans(child, pages, source_id, input_path)
    elif isinstance(value, list):
        for child in value:
            verify_spans(child, pages, source_id, input_path)


def main():
    schema = json.loads(
        (ROOT / "schema" / "extraction-result.schema.json").read_text(encoding="utf-8")
    )
    assert schema == ExtractionResult.model_json_schema(), "Exported schema is stale"
    outputs = sorted((ROOT / "examples" / "outputs").glob("*.json"))
    checked = 0
    for path in outputs:
        if path.name == "batch-summary.json":
            continue
        result = ExtractionResult.model_validate_json(path.read_text(encoding="utf-8"))
        page_map = {page.page: page for page in result.source.pages}

        verify_spans(result.model_dump(), page_map, result.source.identifier, path)
        checked += 1
    assert checked == 12
    ocr_outputs = sorted((ROOT / "examples" / "ocr").glob("*.result.json"))
    for path in ocr_outputs:
        result = ExtractionResult.model_validate_json(path.read_text(encoding="utf-8"))
        verify_spans(
            result.model_dump(),
            {page.page: page for page in result.source.pages},
            result.source.identifier,
            path,
        )
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    snippet = json.loads(re.search(r"```json\n(.*?)\n```", readme, re.S)[1])
    actual = json.loads(
        (ROOT / "examples" / "outputs" / "01_clean.txt.json").read_text(encoding="utf-8")
    )
    assert snippet == actual["data"]["total_change_amount"], "README example differs from execution"
    manifest = (ROOT / "FILE_MANIFEST.txt").read_text(encoding="utf-8").splitlines()
    with zipfile.ZipFile(ROOT.parent / f"{ROOT.name}.zip") as archive:
        assert archive.testzip() is None
        assert set(archive.namelist()) == {f"{ROOT.name}/{name}" for name in manifest}
        for name in manifest:
            assert ".." not in Path(name).parts and not Path(name).is_absolute()
            assert not any(
                part in {".venv", "__pycache__", ".git", "tmp", "build"}
                for part in Path(name).parts
            )
            assert Path(name).name != ".env"
            payload = (ROOT / name).read_bytes()
            assert archive.read(f"{ROOT.name}/{name}") == payload, f"Stale archive member: {name}"
            if name.endswith((".py", ".md", ".json", ".txt", ".toml", ".yml")):
                assert not re.search(rb"sk-(?:proj-)?[A-Za-z0-9_-]{25,}", payload), (
                    f"Credential-like string: {name}"
                )
    print(
        f"Audit passed: 12 baseline and {len(ocr_outputs)} OCR outputs with exact provenance; matching README/schema; {len(manifest)} clean archive members identical to source."
    )


if __name__ == "__main__":
    main()
