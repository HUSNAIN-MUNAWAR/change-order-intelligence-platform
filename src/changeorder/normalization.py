"""Conservative formatting normalization and strict field-specific parsers."""

import re
import unicodedata
from datetime import date, datetime
from decimal import Decimal
from typing import Literal

DateOrder = Literal["reject", "mdy", "dmy"]
CURRENCIES = {"USD", "CAD", "AUD", "EUR", "GBP", "AED", "PKR", "INR", "NZD", "JPY", "CHF"}
MONEY_FIELDS = {
    "total_change_amount",
    "requested_amount",
    "proposed_amount",
    "approved_amount",
    "final_amount",
    "previous_contract_amount",
    "revised_contract_amount",
    "credits_deductions",
}
DATE_FIELDS = {"document_date", "approval_date", "proposed_completion_date"}


class ParseError(ValueError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


def clean_line(text: str) -> str:
    return re.sub(r"[^\S\n]+", " ", unicodedata.normalize("NFKC", text)).strip()


def clean_text(text: str) -> str:
    return "\n".join(clean_line(line) for line in text.splitlines())


def currency_codes(text: str) -> set[str]:
    upper = text.upper()
    codes = set(re.findall(r"\b(?:" + "|".join(sorted(CURRENCIES)) + r")\b", upper))
    for token, code in {
        "US$": "USD",
        "C$": "CAD",
        "A$": "AUD",
        "€": "EUR",
        "£": "GBP",
        "US DOLLARS": "USD",
    }.items():
        if token in upper:
            codes.add(code)
    return codes


def parse_money(text: str) -> Decimal:
    value = unicodedata.normalize("NFKC", text).strip().replace("−", "-")
    for token in sorted(CURRENCIES | {"US$", "C$", "A$", "US dollars"}, key=len, reverse=True):
        value = re.sub(re.escape(token), "", value, flags=re.I)
    value = re.sub(r"[$€£]", "", value).strip()
    negative = value.startswith("(") and value.endswith(")")
    if negative:
        value = value[1:-1].strip()
        if value.startswith(("-", "+")):
            raise ParseError("INVALID_AMOUNT", "Parenthesized amounts cannot also have a sign")
    value = re.sub(r"^([+-])\s+", r"\1", value)
    # Space thousands groups are accepted only in groups of three.
    if re.fullmatch(r"[+-]?\d{1,3}(?:\s+\d{3})+(?:\.\d{1,2})?", value):
        value = re.sub(r"\s", "", value)
    if not re.fullmatch(r"[+-]?(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d{1,2})?", value):
        raise ParseError(
            "INVALID_AMOUNT", "Expected one amount with decimal point and valid thousands groups"
        )
    result = Decimal(value.replace(",", "")) * (-1 if negative else 1)
    if abs(result) >= Decimal("10000000000000000"):
        raise ParseError("INVALID_AMOUNT", "Amount exceeds schema precision")
    return result.quantize(Decimal("0.01"))


def parse_date(text: str, order: DateOrder = "reject") -> tuple[date, list[str]]:
    value = text.strip()
    formats = ["%Y-%m-%d", "%B %d, %Y", "%b %d, %Y", "%B %d %Y", "%b %d %Y"]
    for fmt in formats:
        try:
            return datetime.strptime(value, fmt).date(), []
        except ValueError:
            pass
    match = re.fullmatch(r"(\d{1,2})[/-](\d{1,2})[/-](\d{4})", value)
    if not match:
        raise ParseError(
            "INVALID_DATE", "Expected ISO, month-name, or four-digit-year numeric date"
        )
    first, second, year = map(int, match.groups())
    ambiguous = first <= 12 and second <= 12 and first != second
    if ambiguous and order == "reject":
        raise ParseError("AMBIGUOUS_DATE", f"{value!r} needs an explicit date-order setting")
    month, day = (
        (second, first) if order == "dmy" or (order == "reject" and first > 12) else (first, second)
    )
    try:
        result = date(year, month, day)
    except ValueError as exc:
        raise ParseError("INVALID_DATE", "Date is outside the calendar") from exc
    return result, ["configured_date_order"] if ambiguous else []


def parse_value(field: str, raw: str, date_order: DateOrder = "reject"):
    value = "\n".join(clean_line(line) for line in raw.splitlines()).strip()
    if (
        not value
        or re.fullmatch(r"[_ .-]{3,}", value)
        or value.lower() in {"n/a", "na", "not provided", "tbd", "-"}
        or (value.lower() == "none" and field != "schedule_impact")
    ):
        raise ParseError("MISSING_VALUE", "Label has no supported value")
    if field in MONEY_FIELDS:
        number = parse_money(value)
        if field == "credits_deductions":
            number = -abs(number)
        return number, []
    if field in DATE_FIELDS:
        return parse_date(value, date_order)
    if field == "currency":
        codes = currency_codes(value)
        if len(codes) != 1:
            raise ParseError(
                "AMBIGUOUS_CURRENCY", "Currency must identify exactly one supported ISO currency"
            )
        return codes.pop(), []
    if field == "approval_status":
        aliases = {
            "accepted": "approved",
            "pending approval": "pending",
            "not approved": "pending",
            "submitted": "proposed",
            "denied": "rejected",
            "voided": "void",
        }
        status = aliases.get(value.lower(), value.lower())
        if status not in {
            "approved",
            "pending",
            "proposed",
            "requested",
            "rejected",
            "draft",
            "void",
        }:
            raise ParseError("INVALID_STATUS", "Approval requires an explicit supported status")
        return status, []
    if field == "schedule_impact":
        if re.fullmatch(r"(?:no (?:change|impact)|unchanged|none)", value, re.I):
            return Decimal(0), []
        match = re.fullmatch(
            r"([+-]?\d+(?:\.\d{1,4})?)\s*(?:(?:calendar|working|business)\s+)?(?:days?|weeks?|hours?)?",
            value,
            re.I,
        )
        if not match:
            raise ParseError("INVALID_SCHEDULE", "Expected a signed duration or explicit no change")
        number = Decimal(match[1])
        if abs(number) > 100000:
            raise ParseError("INVALID_SCHEDULE", "Duration is outside the supported range")
        return number, []
    if field == "schedule_unit":
        match = re.search(
            r"\b(?:(calendar|working|business)\s+)?(days?|weeks?|hours?)\b", value, re.I
        )
        if not match:
            raise ParseError("INVALID_SCHEDULE_UNIT", "No explicit duration unit")
        prefix, unit = match.groups()
        unit = unit.lower().rstrip("s") + "s"
        if prefix and unit == "days":
            unit = "calendar_days" if prefix.lower() == "calendar" else "working_days"
        return unit, []
    if field == "referenced_documents":
        return [part.strip() for part in re.split(r"[;,\n]", value) if part.strip()], []
    if field in {"change_order_number", "project_number", "revision"}:
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9 ._/#-]{0,79}", value):
            raise ParseError(
                "INVALID_IDENTIFIER", "Identifier contains unsupported characters or is too long"
            )
    return value, []
