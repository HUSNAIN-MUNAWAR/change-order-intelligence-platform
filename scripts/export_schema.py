"""Regenerate the machine-readable public JSON Schema from the Pydantic contract."""

from pathlib import Path

from changeorder.jsonio import write_json
from changeorder.schemas import ExtractionResult

if __name__ == "__main__":
    path = Path(__file__).resolve().parents[1] / "schema" / "extraction-result.schema.json"
    write_json(path, ExtractionResult.model_json_schema())
    print(path)
