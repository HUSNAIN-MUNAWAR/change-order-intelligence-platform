from datetime import date
from decimal import Decimal

import pytest

from changeorder.normalization import ParseError, clean_text, parse_date, parse_money, parse_value


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("$12,500", "12500.00"),
        ("USD 12,500.00", "12500.00"),
        ("12,500.00", "12500.00"),
        ("($1,200.00)", "-1200.00"),
        ("USD - 1,200.00", "-1200.00"),
        ("1 200.25", "1200.25"),
        ("€ 100.10", "100.10"),
        ("−15.20", "-15.20"),
        ("0.01", "0.01"),
    ],
)
def test_money(raw, expected):
    assert parse_money(raw) == Decimal(expected)


@pytest.mark.parametrize(
    "raw",
    [
        "NaN",
        "Infinity",
        "12,50",
        "1O00",
        "12 50",
        "1.000,00",
        "1.234",
        "100 / 200",
        "(-10)",
        "10000000000000000",
    ],
)
def test_invalid_money(raw):
    with pytest.raises(ParseError):
        parse_money(raw)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("2026-06-15", date(2026, 6, 15)),
        ("June 15, 2026", date(2026, 6, 15)),
        ("6/15/2026", date(2026, 6, 15)),
        ("15/6/2026", date(2026, 6, 15)),
    ],
)
def test_dates(raw, expected):
    assert parse_date(raw)[0] == expected


def test_date_ambiguity_is_explicit():
    with pytest.raises(ParseError, match="date-order"):
        parse_date("06/07/2026")
    assert parse_date("06/07/2026", "mdy") == (date(2026, 6, 7), ["configured_date_order"])
    assert parse_date("06/07/2026", "dmy")[0] == date(2026, 7, 6)
    with pytest.raises(ParseError):
        parse_date("2026-02-30")


def test_normalization_retains_line_boundaries():
    assert (
        clean_text("  Scope:\t  Add lights\r\n  and    controls.\n\nEnd")
        == "Scope: Add lights\nand controls.\n\nEnd"
    )


def test_strict_currency_and_placeholder():
    with pytest.raises(ParseError):
        parse_value("currency", "$")
    assert parse_value("currency", "US dollars")[0] == "USD"
    with pytest.raises(ParseError):
        parse_value("approver_name", "____________________")
    assert parse_value("schedule_impact", "none")[0] == 0
