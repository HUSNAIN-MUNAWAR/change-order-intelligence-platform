"""Run every demonstration independently; the deliberately unrelated case should fail."""

from pathlib import Path

from changeorder.cli import batch
from changeorder.pipeline import PipelineOptions
from changeorder.readers import ReaderOptions

ROOT = Path(__file__).resolve().parents[1]

if __name__ == "__main__":
    results = batch(
        ROOT / "examples" / "documents",
        ROOT / "examples" / "outputs",
        PipelineOptions(reader=ReaderOptions(ocr="off")),
    )
    print(
        {
            status: sum(result.status == status for result in results)
            for status in ("success", "partial", "failed")
        }
    )
