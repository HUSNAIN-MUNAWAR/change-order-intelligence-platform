"""CLI: JSON on stdout/files, concise diagnostics on stderr, explicit exit codes."""

import argparse
import logging
import sys
from pathlib import Path

from .jsonio import dumps, write_json
from .pipeline import PipelineOptions, extract
from .readers import ReaderOptions
from .schemas import ExtractionResult

LOGGER = logging.getLogger("changeorder")
EXIT_CODES = {"success": 0, "partial": 2, "failed": 1}


def _options(args) -> PipelineOptions:
    return PipelineOptions(
        reader=ReaderOptions(ocr=args.ocr), date_order=args.date_order, llm=args.llm
    )


def _report(result: ExtractionResult) -> None:
    LOGGER.warning(
        "%s: %s (%d issue(s), %.1f ms)",
        result.source.identifier,
        result.status,
        len(result.issues),
        result.processing_ms,
    )
    for issue in result.issues:
        if issue.severity != "info":
            LOGGER.warning(
                "  %s%s: %s", issue.code, f" [{issue.field}]" if issue.field else "", issue.message
            )


def _protect_input(input_path: Path, output_path: Path) -> None:
    if input_path.resolve() == output_path.resolve():
        raise ValueError("Output must not overwrite the input document")


def batch(input_dir: Path, output_dir: Path, options: PipelineOptions) -> list[ExtractionResult]:
    if not input_dir.is_dir():
        raise ValueError("Input directory does not exist")
    if input_dir.resolve() == output_dir.resolve():
        raise ValueError("Use separate input and output directories")
    paths = sorted(path for path in input_dir.iterdir() if path.is_file())
    if not paths:
        raise ValueError("Input directory contains no files")
    results = []
    for path in paths:
        destination = (
            output_dir / f"{path.name}.json"
        )  # retain extension to avoid same-stem collisions
        _protect_input(path, destination)
        result = extract(path, options=options)
        write_json(destination, result)
        _report(result)
        results.append(result)
    write_json(
        output_dir / "batch-summary.json",
        {
            "documents": [
                {"input": item.source.identifier, "status": item.status, "issues": len(item.issues)}
                for item in results
            ],
            "counts": {
                status: sum(item.status == status for item in results) for status in EXIT_CODES
            },
        },
    )
    return results


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Extract evidence-backed construction change-order JSON"
    )
    commands = parser.add_subparsers(dest="command", required=True)
    single = commands.add_parser(
        "extract", help="Process a PDF, UTF-8 text file, literal text or stdin"
    )
    inputs = single.add_mutually_exclusive_group(required=True)
    inputs.add_argument("--input", type=Path)
    inputs.add_argument("--text")
    inputs.add_argument("--stdin", action="store_true")
    single.add_argument("--output", type=Path)
    multiple = commands.add_parser("batch", help="Process each file independently (non-recursive)")
    multiple.add_argument("--input-dir", required=True, type=Path)
    multiple.add_argument("--output-dir", required=True, type=Path)
    for command in (single, multiple):
        command.add_argument("--ocr", choices=["off", "auto", "force"], default="auto")
        command.add_argument("--date-order", choices=["reject", "mdy", "dmy"], default="reject")
        command.add_argument(
            "--llm",
            action="store_true",
            help="Send source text to the configured optional provider",
        )
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.WARNING, format="%(message)s")
    try:
        if args.command == "batch":
            results = batch(args.input_dir, args.output_dir, _options(args))
            return (
                1
                if any(item.status == "failed" for item in results)
                else (2 if any(item.status == "partial" for item in results) else 0)
            )
        if args.input and args.output:
            _protect_input(args.input, args.output)
        text = sys.stdin.read(ReaderOptions().max_chars + 1) if args.stdin else args.text
        result = extract(
            args.input,
            text=text,
            source_id="stdin" if args.stdin else "raw-text",
            options=_options(args),
        )
        if args.output:
            write_json(args.output, result)
        else:
            sys.stdout.write(dumps(result))
        _report(result)
        return EXIT_CODES[result.status]
    except (OSError, ValueError) as exc:
        LOGGER.error("CLI error: %s", exc)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
