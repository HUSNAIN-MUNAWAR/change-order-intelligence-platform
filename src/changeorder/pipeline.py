"""Orchestrate ingestion, candidate extraction, reconciliation and validated output."""

import re
from dataclasses import dataclass, field
from pathlib import Path
from time import perf_counter

from .extraction import extract_candidates
from .llm_extractor import Extractor, LLMError, OpenAITransport, StructuredLLMExtractor
from .normalization import DateOrder
from .readers import InputError, ReaderOptions, read_file, read_text
from .schemas import ChangeOrder, ExtractionResult, Issue, Source
from .validation import check_consistency, reconcile


@dataclass(frozen=True)
class PipelineOptions:
    reader: ReaderOptions = field(default_factory=ReaderOptions)
    date_order: DateOrder = "reject"
    llm: bool = False

    def __post_init__(self):
        if self.date_order not in {"reject", "mdy", "dmy"}:
            raise ValueError("date_order must be reject, mdy, or dmy")


def extract(
    path: str | Path | None = None,
    *,
    text: str | None = None,
    source_id: str = "raw-text",
    options: PipelineOptions | None = None,
    llm_extractor: Extractor | None = None,
) -> ExtractionResult:
    """Return structured fatal/partial results for expected input and provider failures.

    Programming errors propagate; they are not mislabeled as successful extractions.
    """
    if (path is None) == (text is None):
        raise ValueError("Supply exactly one of path or text")
    started = perf_counter()
    options = options or PipelineOptions()
    source = Source(
        identifier=Path(path).name if path is not None else source_id, media_type="unknown"
    )
    issues = []
    data = ChangeOrder()
    consistency = "not_checked"
    llm_used = False
    try:
        if path is not None:
            source, issues = read_file(Path(path), options.reader)
        else:
            source = read_text(text, source_id, options.reader)
        if not any(issue.severity == "fatal_error" for issue in issues):
            candidates, extraction_issues = extract_candidates(source, options.date_order)
            issues.extend(extraction_issues)
            recognizable = any(
                re.search(
                    r"\bchange[ -]*[o0]rder\b|\bc\.?o\.?\s*(?:#|no\b|number\b|:)",
                    page.cleaned_text,
                    re.I,
                )
                for page in source.pages
            )
            if not recognizable:
                issues.append(
                    Issue(
                        code="NOT_CHANGE_ORDER",
                        severity="fatal_error",
                        message="No recognizable change-order context; generic project/invoice facts were not returned",
                    )
                )
            else:
                if options.llm or llm_extractor is not None:
                    try:
                        adapter = llm_extractor or StructuredLLMExtractor(OpenAITransport())
                        assisted, llm_issues = adapter.extract(source, options.date_order)
                        candidates.extend(assisted)
                        issues.extend(llm_issues)
                        llm_used = True
                    except LLMError as exc:
                        issues.append(
                            Issue(
                                code="LLM_CONFIGURATION",
                                severity="recoverable_error",
                                message=str(exc),
                            )
                        )
                data = reconcile(candidates, issues)
                consistency_issues, consistency = check_consistency(data)
                issues.extend(consistency_issues)
                if not any(
                    getattr(data, name).value is not None
                    for name in (
                        "change_order_number",
                        "description",
                        "total_change_amount",
                        "project_name",
                    )
                ):
                    issues.append(
                        Issue(
                            code="NO_CHANGE_ORDER_FACTS",
                            severity="fatal_error",
                            message="Change-order context exists but no actionable facts could be extracted",
                        )
                    )
    except InputError as exc:
        issues.append(Issue(code=exc.code, severity="fatal_error", message=str(exc)))
    missing = [name for name in ChangeOrder.model_fields if getattr(data, name).value is None]
    for name in ("change_order_number", "project_name", "total_change_amount"):
        if name in missing and not any(issue.severity == "fatal_error" for issue in issues):
            issues.append(
                Issue(
                    code="MISSING_CORE_FIELD",
                    field=name,
                    message="Core review field is absent or could not be validated",
                )
            )
    fatal = any(issue.severity == "fatal_error" for issue in issues)
    uncertain = any(issue.severity in {"warning", "recoverable_error"} for issue in issues) or any(
        getattr(data, name).validation in {"warning", "conflict", "invalid"}
        for name in ChangeOrder.model_fields
    )
    status = "failed" if fatal else ("partial" if uncertain else "success")
    # Validate the final object afresh, including any cross-field confidence reductions.
    return ExtractionResult.model_validate(
        dict(
            status=status,
            source=source,
            data=data.model_dump(),
            issues=issues,
            missing_fields=missing,
            consistency=consistency,
            llm_used=llm_used,
            processing_ms=round((perf_counter() - started) * 1000, 3),
        )
    )
