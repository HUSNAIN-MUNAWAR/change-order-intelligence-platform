"""Label/structure candidates. No document values are completed from outside knowledge."""

import re
from dataclasses import dataclass
from dataclasses import field as dc_field
from decimal import Decimal

from .normalization import (
    MONEY_FIELDS,
    DateOrder,
    ParseError,
    clean_line,
    currency_codes,
    parse_money,
    parse_value,
)
from .provenance import Line, evidence, lines
from .schemas import CostItem, Evidence, ExtractedField, Issue, Source

# Aliases are intentionally anchored to labels, never arbitrary bare numbers.
LABELS = {
    "change_order_number": r"(?:change[ -]*order|c\.?o\.?)\s*(?:number|no\.?|#)|(?:change[ -]*order|co)",
    "project_name": r"project name|project",
    "project_number": r"project (?:number|no\.?|id|#)|job (?:number|no\.?|#)",
    "document_title": r"document title|title",
    "document_date": r"document date|change order date|date issued|date",
    "revision": r"revision(?: id| number| no\.?)?|rev\.?",
    "contractor": r"general contractor|contractor",
    "subcontractor": r"subcontractor",
    "owner": r"owner(?: / client)?|client",
    "architect_engineer": r"architect(?: / engineer)?|engineer|architect/engineer",
    "description": r"description(?: of change)?|scope(?: of (?:work|change))?|change description",
    "reason": r"reason(?: for change)?|justification",
    "discipline": r"affected (?:work|discipline)|discipline|trade",
    "referenced_documents": r"referenced (?:drawings|documents)|references|drawings",
    "total_change_amount": r"total change(?: order)? amount|change order total|total change|net change(?: amount)?|amount of (?:this )?change|change amount|total amount|grand total|total",
    "requested_amount": r"requested(?: change)? amount|amount requested",
    "proposed_amount": r"proposed(?: change)? amount|amount proposed",
    "approved_amount": r"approved(?: change)? amount|amount approved",
    "final_amount": r"final(?: change)? amount|final change order total",
    "currency": r"currency",
    "previous_contract_amount": r"previous contract (?:amount|sum)|original contract (?:amount|sum)|contract amount before change",
    "revised_contract_amount": r"revised contract (?:amount|sum)|new contract (?:amount|sum)",
    "credits_deductions": r"credits?(?: / deductions?)?|deductions?",
    "schedule_impact": r"schedule (?:impact|extension)|time (?:impact|extension)|contract time adjustment",
    "schedule_unit": r"schedule unit|unit of schedule impact",
    "proposed_completion_date": r"proposed completion date|revised completion date",
    "approval_status": r"approval status|status",
    "approval_date": r"approval date|date approved",
    "approver_name": r"approver(?: name)?|approved by",
}
PATTERNS = [
    (name, re.compile(r"^(?:" + label + r")\s*(?::|=|\|)\s*(.*)$", re.I))
    for name, label in sorted(LABELS.items(), key=lambda item: len(item[1]), reverse=True)
]
MULTILINE = {"description", "reason", "referenced_documents"}


@dataclass
class Candidate:
    field: str
    value: object
    evidence: Evidence
    method: str = "label"
    strength: float = 0.90
    notes: list[str] = dc_field(default_factory=list)
    ocr_quality: float | None = None


def match_label(text: str):
    # Public-agency forms frequently place the value after dotted leaders or
    # in a heading rather than after a colon. These patterns remain anchored
    # to semantic labels and capture only the value-bearing portion.
    special_patterns = (
        (
            "change_order_number",
            re.compile(r"^(?:contract\s+)?change\s+order\s+(?:no\.?|number|#)\s+([A-Za-z0-9][\w./#-]*)$", re.I),
        ),
        (
            "project_number",
            re.compile(r"^project\s+i\.?d\.?\s*[:.]?\s*([A-Za-z0-9][\w./#-]*)$", re.I),
        ),
        (
            "total_change_amount",
            re.compile(
                r"^(?:cost\s+of\s+this\s+change\s+order|increase\s+to\s+contract\s+price|estimated\s+increase\s+in\s+contract\s+price|increase\s+in\s+contract\s+price)\s*(?:[.…]+\s*)*\$?\s*([+-]?\d[\d,]*(?:\.\d{1,2})?)(?:\s+(?:increase|decrease))?",
                re.I,
            ),
        ),
        (
            "previous_contract_amount",
            re.compile(r"^original\s+contract\s+price\s*\$?\s*([+-]?\d[\d,]*(?:\.\d{1,2})?)", re.I),
        ),
        (
            "revised_contract_amount",
            re.compile(r"^revised\s+contract\s+price\s*\$?\s*([+-]?\d[\d,]*(?:\.\d{1,2})?)", re.I),
        ),
        (
            "schedule_impact",
            re.compile(
                r"^change\s+in\s+contract\s+time\s*(?:[.…]+\s*)*(\d+(?:\.\d+)?)\s*(days?|weeks?|hours?)\b",
                re.I,
            ),
        ),
    )
    for name, pattern in special_patterns:
        match = pattern.match(text)
        if match:
            value = match[1]
            if name == "schedule_impact":
                value = f"{match[1]} {match[2]}"
            return name, value, False
    inline_project = re.search(r"\bproject\s+i\.?d\.?\s*[:.]?\s*([A-Za-z0-9][\w./#-]*)", text, re.I)
    if inline_project:
        return "project_number", inline_project[1], False
    for name, pattern in PATTERNS:
        match = pattern.fullmatch(text)
        if match:
            return name, match[1], False
    # Restricted OCR repair applies to the label only, never identifiers or amounts.
    if ":" in text:
        label, value = text.split(":", 1)
        repaired = label.replace("0", "o").replace("1", "l") + ":" + value
        if repaired != text:
            for name, pattern in PATTERNS:
                match = pattern.fullmatch(repaired)
                if match:
                    return name, match[1], True
    return None


def _label_strength(name: str, text: str) -> float:
    """Prefer explicit overall totals to repeated line-item price labels."""
    if name == "total_change_amount":
        lowered = text.lower()
        if "cost of this change order" in lowered:
            return 0.98
        if "increase to contract price" in lowered:
            return 0.95
        if "estimated increase in contract price" in lowered:
            return 0.76
        if "increase in contract price" in lowered:
            return 0.72
    return 0.90


def _table_field(value, ev):
    return ExtractedField(
        value=value,
        confidence=0.78 if ev.text_origin != "ocr" else 0.60,
        evidence=[ev],
        method="table",
        validation="valid",
        signals=["table_column"],
    )


def _logical_lines(page):
    """Split clearly separated inline labels while preserving exact physical line spans."""
    result = []
    for line in lines(page):
        cursor = 0
        for separator in re.finditer(r";\s*|\t+| {2,}|\s+\|\s+", line.raw):
            if match_label(clean_line(line.raw[separator.end() :])):
                raw = line.raw[cursor : separator.start()]
                if raw.strip():
                    result.append(
                        Line(
                            line.number,
                            line.start + cursor,
                            line.start + separator.start(),
                            raw,
                            clean_line(raw),
                        )
                    )
                cursor = separator.end()
        raw = line.raw[cursor:]
        if raw:
            result.append(Line(line.number, line.start + cursor, line.end, raw, clean_line(raw)))
    return result


def extract_candidates(
    source: Source, date_order: DateOrder = "reject"
) -> tuple[list[Candidate], list[Issue]]:
    candidates: list[Candidate] = []
    issues: list[Issue] = []
    items: list[CostItem] = []
    item_evidence: list[Evidence] = []
    for page in source.pages:
        page_lines = _logical_lines(page)
        consumed: set[int] = set()
        table_columns = None
        for index, line in enumerate(page_lines):
            if index in consumed or not line.clean:
                continue
            text = line.clean
            parts = [
                part.strip()
                for part in re.split(r"\s*\|\s*|\t+| {2,}", line.raw.strip())
                if part.strip()
            ]
            lower_parts = [part.lower() for part in parts]
            if (
                len(parts) >= 2
                and lower_parts[0] in {"description", "item", "cost item"}
                and lower_parts[-1] in {"amount", "total", "cost"}
            ):
                table_columns = lower_parts
                continue
            if table_columns and len(parts) == len(table_columns) and not match_label(text):
                if parts[0].lower() not in {"subtotal", "total", "tax", "markup", "grand total"}:
                    ev = evidence(source, page, line)
                    try:
                        amount = parse_money(parts[-1])
                        item = CostItem(
                            description=_table_field(parts[0], ev), amount=_table_field(amount, ev)
                        )
                        for column, raw in zip(table_columns[1:-1], parts[1:-1], strict=True):
                            if column in {"qty", "quantity"}:
                                if not re.fullmatch(r"\d+(?:\.\d{1,4})?", raw):
                                    raise ParseError("INVALID_QUANTITY", "Invalid table quantity")
                                item.quantity = _table_field(Decimal(raw), ev)
                            elif column in {"unit", "uom"}:
                                item.unit = _table_field(raw, ev)
                            elif column in {"rate", "unit price", "unit cost"}:
                                item.unit_price = _table_field(parse_money(raw), ev)
                        items.append(item)
                        item_evidence.append(ev)
                        money_text = " ".join(
                            parts[column]
                            for column, label in enumerate(table_columns)
                            if column == len(parts) - 1
                            or label in {"rate", "unit price", "unit cost"}
                        )
                        for code in sorted(currency_codes(money_text)):
                            candidates.append(
                                Candidate(
                                    "currency",
                                    code,
                                    ev,
                                    "table",
                                    0.78,
                                    ocr_quality=page.ocr_quality,
                                )
                            )
                        if "$" in money_text and not currency_codes(money_text):
                            issues.append(
                                Issue(
                                    code="AMBIGUOUS_CURRENCY",
                                    message="Dollar symbols in a cost row do not establish an ISO currency",
                                    field="currency",
                                    evidence=ev,
                                )
                            )
                        continue
                    except (ParseError, ValueError) as exc:
                        issues.append(
                            Issue(
                                code="INVALID_LINE_ITEM",
                                message=f"Cost row could not be parsed: {exc}",
                                field="line_items",
                                evidence=ev,
                            )
                        )
                table_columns = None
            elif table_columns:
                table_columns = None
            match = match_label(text)
            if not match:
                short_id = re.fullmatch(
                    r"c\.?o\.?\s*(?:#|no\.?)\s*([A-Za-z0-9][\w./#-]*)", text, re.I
                )
                if short_id:
                    candidates.append(
                        Candidate(
                            "change_order_number",
                            short_id[1],
                            evidence(source, page, line),
                            "title",
                            0.86,
                            ocr_quality=page.ocr_quality,
                        )
                    )
                    continue
                heading = re.fullmatch(
                    r"((?:proposed |requested |draft )?change[ -]*[o0]rder)(?:\s+(?:no\.?\s*|#\s*)?([A-Za-z0-9][\w./#-]*))?",
                    text,
                    re.I,
                )
                if heading:
                    ev = evidence(source, page, line)
                    candidates.append(
                        Candidate(
                            "document_title",
                            heading[1],
                            ev,
                            "title",
                            0.86,
                            ocr_quality=page.ocr_quality,
                        )
                    )
                    if heading[2]:
                        candidates.append(
                            Candidate(
                                "change_order_number",
                                heading[2],
                                ev,
                                "title",
                                0.86,
                                ocr_quality=page.ocr_quality,
                            )
                        )
                continue
            name, raw, repaired = match
            last = line
            fragments = [raw] if raw.strip() else []
            # Single-line values may be wrapped directly below their label.
            for nxt in range(
                index + 1, min(len(page_lines), index + (16 if name in MULTILINE else 2))
            ):
                following = page_lines[nxt]
                if (
                    not following.clean
                    or match_label(following.clean)
                    or re.match(r"^[A-Za-z][\w /()-]{0,60}\s*:", following.clean)
                    or following.clean.upper()
                    in {
                        "FINANCIAL",
                        "COST SUMMARY",
                        "COST BREAKDOWN",
                        "SIGNATURES",
                        "APPROVALS",
                        "SCHEDULE",
                    }
                    or re.match(
                        r"^(?:page\s+\d|change[ -]*order\b|synthetic\b)", following.clean, re.I
                    )
                ):
                    break
                if fragments and name not in MULTILINE:
                    break
                if "|" in following.raw:
                    break
                fragments.append(following.clean)
                last = following
                consumed.add(nxt)
            ev = evidence(source, page, line, last)
            raw = "\n".join(fragments)
            notes = ["ocr_label_repair"] if repaired else []
            try:
                value, parsing_notes = parse_value(name, raw, date_order)
                notes += parsing_notes
                if name == "project_name":
                    value = re.sub(r"\s+SHEET\s+\d+\s+OF\s+\d+\s*$", "", str(value), flags=re.I)
                candidates.append(
                    Candidate(
                        name,
                        value,
                        ev,
                        strength=_label_strength(name, line.clean),
                        notes=notes,
                        ocr_quality=page.ocr_quality,
                    )
                )
                if notes:
                    issues.append(
                        Issue(
                            code="NORMALIZATION_REVIEW",
                            message="Review normalization signals: " + ", ".join(notes),
                            field=name,
                            evidence=ev,
                        )
                    )
                if name in MONEY_FIELDS:
                    for code in sorted(currency_codes(raw)):
                        candidates.append(
                            Candidate(
                                "currency",
                                code,
                                ev,
                                notes=notes.copy(),
                                ocr_quality=page.ocr_quality,
                            )
                        )
                    if "$" in raw and not currency_codes(raw):
                        issues.append(
                            Issue(
                                code="AMBIGUOUS_CURRENCY",
                                message="Dollar symbol does not establish USD/CAD/AUD; currency left unset unless explicitly supported elsewhere",
                                field="currency",
                                evidence=ev,
                            )
                        )
                if name == "schedule_impact":
                    try:
                        unit, _ = parse_value("schedule_unit", raw, date_order)
                        candidates.append(
                            Candidate(
                                "schedule_unit",
                                unit,
                                ev,
                                notes=notes.copy(),
                                ocr_quality=page.ocr_quality,
                            )
                        )
                    except ParseError:
                        pass
            except ParseError as exc:
                if exc.code != "MISSING_VALUE":
                    issues.append(Issue(code=exc.code, message=str(exc), field=name, evidence=ev))
    if items:
        # The collection carries source evidence and each leaf carries its own evidence/score.
        candidates.append(Candidate("line_items", items, item_evidence[0], "table", 0.78))
    return candidates, issues
