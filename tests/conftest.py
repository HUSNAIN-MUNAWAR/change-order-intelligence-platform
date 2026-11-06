from pathlib import Path

import pytest

from changeorder.pipeline import PipelineOptions
from changeorder.readers import ReaderOptions

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def documents():
    return ROOT / "examples" / "documents"


@pytest.fixture
def offline():
    return PipelineOptions(reader=ReaderOptions(ocr="off"))
