"""Reconciliation and explicit consistency checks; never repair source arithmetic."""

from collections import defaultdict
from decimal import Decimal

from pydantic import TypeAdapter, ValidationError

from .confidence import score
from .extraction import Candidate
from .schemas import ChangeOrder, Issue


def _candidate_evidence(candidate: Candidate):
    return candidate.evidence_spans or [candidate.evidence]


def reconcile(candidates: list[Candidate], issues: list[Issue]) -> ChangeOrder:
    grouped = defaultdict(list)
    for candidate in candidates:
        grouped[candidate.field].append(candidate)
    data = ChangeOrder()
    for name, options in grouped.items():
        if name not in ChangeOrder.model_fields:
            issues.append(
                Issue(
                    code="UNKNOWN_FIELD",
                    message="Extractor proposed a field outside the output schema",
                )
            )
            continue
        valid = []
        adapter = TypeAdapter(ChangeOrder.model_fields[name].annotation)
        for candidate in options:
            try:
                adapter.validate_python(
                    dict(
                        value=candidate.value,
                        confidence=0.5,
                        evidence=_candidate_evidence(candidate),
                        method=candidate.method,
                        validation="valid",
                    )
                )
                valid.append(candidate)
            except ValidationError:
                issues.append(
                    Issue(
                        code="SCHEMA_REJECTED",
                        message="Candidate failed field type/range validation",
                        field=name,
                        evidence=candidate.evidence,
                    )
                )
        if not valid:
            continue
        # Stable order resolves equal strength, with every distinct alternative disclosed.
        valid.sort(key=lambda candidate: candidate.strength, reverse=True)
        chosen = valid[0]
        agreeing = [candidate for candidate in valid if candidate.value == chosen.value]
        alternatives = []
        for other in valid:
            if other.value != chosen.value and not any(
                other.value == alt["value"] for alt in alternatives
            ):
                alternatives.append(
                    dict(
                        value=other.value,
                        evidence=_candidate_evidence(other),
                        method=other.method,
                    )
                )
        non_llm_evidence = {
            (ev.page, ev.char_start, ev.char_end, ev.text)
            for candidate in agreeing
            if candidate.method != "llm"
            for ev in _candidate_evidence(candidate)
        }
        independent_methods = set()
        for candidate in agreeing:
            if candidate.method == "llm" and any(
                (ev.page, ev.char_start, ev.char_end, ev.text) in non_llm_evidence
                for ev in _candidate_evidence(candidate)
            ):
                continue
            independent_methods.add(candidate.method)
        confidence, signals = score(
            chosen,
            conflict=bool(alternatives),
            independent_methods=len(independent_methods),
        )
        evs = []
        for candidate in agreeing:
            for candidate_evidence in _candidate_evidence(candidate):
                if candidate_evidence not in evs:
                    evs.append(candidate_evidence)
        validation = "conflict" if alternatives else ("warning" if chosen.notes else "valid")
        field = adapter.validate_python(
            dict(
                value=chosen.value,
                confidence=confidence,
                evidence=evs,
                method=chosen.method,
                validation=validation,
                signals=signals,
                alternatives=alternatives,
            )
        )
        setattr(data, name, field)
        if alternatives:
            issues.append(
                Issue(
                    code="CONFLICTING_VALUES",
                    message="Multiple supported values; strongest candidate retained with alternatives for review",
                    field=name,
                    evidence=chosen.evidence,
                )
            )
    # Specific financial roles remain independently available. A generic total takes precedence.
    if data.total_change_amount.value is not None:
        basis, origin = "stated_total", data.total_change_amount
    else:
        basis, origin = None, None
        for role in ("final", "approved", "proposed", "requested"):
            candidate = getattr(data, f"{role}_amount")
            if candidate.value is not None:
                basis, origin = role, candidate
                data.total_change_amount = candidate.model_copy(deep=True)
                break
    if origin is not None:
        data.amount_basis = TypeAdapter(
            ChangeOrder.model_fields["amount_basis"].annotation
        ).validate_python(
            dict(
                value=basis,
                confidence=origin.confidence,
                evidence=origin.evidence,
                method=origin.method,
                validation="warning" if origin.validation == "conflict" else origin.validation,
                signals=["amount_role_in_source"],
            )
        )
    for issue in issues:
        if (
            issue.field in ChangeOrder.model_fields
            and getattr(data, issue.field).value is None
            and issue.code
            in {
                "INVALID_AMOUNT",
                "INVALID_DATE",
                "AMBIGUOUS_DATE",
                "SCHEMA_REJECTED",
                "INVALID_IDENTIFIER",
                "INVALID_STATUS",
                "INVALID_SCHEDULE",
            }
        ):
            setattr(
                data,
                issue.field,
                TypeAdapter(ChangeOrder.model_fields[issue.field].annotation).validate_python(
                    {"validation": "invalid"}
                ),
            )
    return data


def check_consistency(data: ChangeOrder) -> tuple[list[Issue], str]:
    issues = []
    checks = 0

    def warn(code: str, message: str, fields: list[str]):
        issues.append(Issue(code=code, message=message, field=fields[0]))
        for name in fields:
            item = getattr(data, name)
            if item.value is not None:
                # Replace the whole validated wrapper, avoiding transient invalid assignment states.
                update = dict(
                    confidence=round(min(0.65, max(0, item.confidence - 0.20)), 3),
                    signals=item.signals + [f"{code}=-0.20; cap=0.65"],
                    validation="conflict" if item.validation == "conflict" else "warning",
                )
                setattr(data, name, item.model_copy(update=update))

    total, previous, revised = (
        data.total_change_amount,
        data.previous_contract_amount,
        data.revised_contract_amount,
    )
    if data.amount_basis.value == "stated_total":
        for name in ("final_amount", "approved_amount"):
            specific = getattr(data, name)
            if specific.value is not None:
                checks += 1
                if specific.value != total.value:
                    warn(
                        "TOTAL_ROLE_MISMATCH",
                        "Stated total differs from the final/approved amount; both source values retained",
                        ["total_change_amount", name],
                    )
    if data.currency.validation == "conflict":
        issues.append(
            Issue(
                code="MIXED_CURRENCY",
                message="Financial arithmetic skipped because currency candidates conflict",
                field="currency",
            )
        )
    else:
        if total.value is not None and data.line_items.value:
            checks += 1
            item_sum = sum((item.amount.value for item in data.line_items.value), Decimal(0))
            if abs(total.value - item_sum) > Decimal("0.01"):
                warn(
                    "LINE_TOTAL_MISMATCH",
                    "Stated change total differs from extracted cost rows; taxes, markup or omitted rows may explain it",
                    ["total_change_amount", "line_items"],
                )
        if all(item.value is not None for item in (total, previous, revised)):
            checks += 1
            if abs(previous.value + total.value - revised.value) > Decimal("0.01"):
                warn(
                    "CONTRACT_TOTAL_MISMATCH",
                    "Previous contract plus this change differs from revised contract; cumulative changes may explain it",
                    ["total_change_amount", "previous_contract_amount", "revised_contract_amount"],
                )
    for item in data.line_items.value or []:
        if item.quantity.value is not None and item.unit_price.value is not None:
            checks += 1
            if abs(item.quantity.value * item.unit_price.value - item.amount.value) > Decimal(
                "0.01"
            ):
                warn(
                    "LINE_EXTENSION_MISMATCH",
                    "Quantity times unit price differs from stated row amount",
                    ["line_items"],
                )
                item.amount = item.amount.model_copy(
                    update={
                        "confidence": min(item.amount.confidence, 0.58),
                        "validation": "warning",
                        "signals": item.amount.signals + ["line_extension_mismatch"],
                    }
                )
    if data.document_date.value and data.approval_date.value:
        checks += 1
        if data.approval_date.value < data.document_date.value:
            warn(
                "DATE_SEQUENCE",
                "Approval date precedes document date; revision history may explain it",
                ["approval_date", "document_date"],
            )
    if data.approval_date.value and data.approval_status.value in {
        "rejected",
        "pending",
        "draft",
        "void",
    }:
        warn(
            "APPROVAL_INCONSISTENT",
            "Approval date coexists with a non-approved status",
            ["approval_status", "approval_date"],
        )
    return issues, "warning" if issues else ("passed" if checks else "not_checked")
