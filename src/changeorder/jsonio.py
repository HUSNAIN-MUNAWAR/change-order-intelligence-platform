"""Exact Decimal JSON output, UTF-8, atomic replacement for file destinations."""

import os
import tempfile
from datetime import date
from pathlib import Path

import simplejson
from pydantic import BaseModel


def dumps(model: BaseModel | dict) -> str:
    def default(value):
        if isinstance(value, date):
            return value.isoformat()
        raise TypeError(f"Cannot serialize {type(value).__name__}")

    value = model.model_dump(mode="python") if isinstance(model, BaseModel) else model
    return (
        simplejson.dumps(
            value, use_decimal=True, default=default, indent=2, ensure_ascii=False, allow_nan=False
        )
        + "\n"
    )


def write_json(path: Path, model: BaseModel | dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=path.parent, delete=False
        ) as stream:
            temporary = Path(stream.name)
            stream.write(dumps(model))
        os.replace(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
