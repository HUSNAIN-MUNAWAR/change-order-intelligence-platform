from decimal import Decimal

import pytest
from pydantic import ValidationError

from changeorder.pipeline import extract
from changeorder.schemas import ChangeOrder, Evidence, ExtractedField


def test_wrapper_invariants_and_types():
    ev = Evidence(
        source="x",
        line_start=1,
        line_end=1,
        char_start=0,
        char_end=3,
        text="abc",
        text_origin="text",
    )
    with pytest.raises(ValidationError):
        ExtractedField[str](value="unsupported", confidence=0.9)
    with pytest.raises(ValidationError):
        ExtractedField[str](value=None, confidence=0.5)
    with pytest.raises(ValidationError):
        ExtractedField[str](
            value="abc", confidence=1.1, evidence=[ev], method="label", validation="valid"
        )
    with pytest.raises(ValidationError):
        ChangeOrder(
            change_order_number={
                "value": 15,
                "confidence": 0.8,
                "evidence": [ev],
                "method": "label",
                "validation": "valid",
            }
        )
    with pytest.raises(ValidationError):
        ChangeOrder(invented="no")
    with pytest.raises(ValidationError):
        Evidence(
            source="x",
            line_start=1,
            line_end=1,
            char_start=0,
            char_end=4,
            text="abc",
            text_origin="text",
        )


def test_financial_mismatches_reduce_confidence(offline):
    text = "CHANGE ORDER\nCO Number: 001\nProject: A\nPrevious Contract Amount: USD 100\nTotal Change Amount: USD 30\nRevised Contract Amount: USD 140\nDescription | Qty | Unit Price | Amount\nLabor | 2 | 10 | USD 25"
    result = extract(text=text, options=offline)
    assert {issue.code for issue in result.issues} >= {
        "CONTRACT_TOTAL_MISMATCH",
        "LINE_TOTAL_MISMATCH",
        "LINE_EXTENSION_MISMATCH",
    }
    assert result.data.total_change_amount.value == Decimal(30)
    assert result.data.total_change_amount.confidence <= 0.65
    assert result.data.line_items.value[0].amount.confidence <= 0.58
    assert result.consistency == "warning"


def test_conflicts_preserve_alternative(documents, offline):
    result = extract(documents / "06_conflict.txt", options=offline)
    field = result.data.total_change_amount
    assert field.validation == "conflict"
    assert field.value == 18000
    assert field.alternatives[0].value == 19500
    assert field.confidence <= 0.55


def test_mixed_currency_skips_arithmetic(offline):
    result = extract(
        text="CHANGE ORDER\nCO Number: 1\nProject: A\nPrevious Contract Amount: USD 100\nTotal Change Amount: EUR 20\nRevised Contract Amount: USD 120",
        options=offline,
    )
    assert result.data.currency.validation == "conflict"
    assert any(issue.code == "MIXED_CURRENCY" for issue in result.issues)
    assert not any(issue.code == "CONTRACT_TOTAL_MISMATCH" for issue in result.issues)


def test_invalid_amount_not_trusted(offline):
    result = extract(
        text="CHANGE ORDER\nCO Number: 1\nProject: A\nTotal Change Amount: USD 1O00",
        options=offline,
    )
    field = result.data.total_change_amount
    assert field.value is None and field.confidence == 0 and field.validation == "invalid"
    assert any(issue.code == "INVALID_AMOUNT" for issue in result.issues)


def test_date_order_and_approval_sequence(offline):
    result = extract(
        text="CHANGE ORDER\nCO Number: 1\nProject: A\nDocument Date: 2026-06-20\nApproval Date: 2026-06-19\nApproval Status: Pending",
        options=offline,
    )
    assert {issue.code for issue in result.issues} >= {"DATE_SEQUENCE", "APPROVAL_INCONSISTENT"}


def test_generic_total_and_final_disagreement_requires_review(offline):
    result = extract(
        text="CHANGE ORDER\nCO Number: 1\nProject: A\nTotal: USD 100\nFinal Amount: USD 120",
        options=offline,
    )
    assert result.data.total_change_amount.value == 100
    assert result.data.final_amount.value == 120
    assert any(issue.code == "TOTAL_ROLE_MISMATCH" for issue in result.issues)


def test_generic_total_checks_both_approved_and_final_roles(offline):
    result = extract(
        text=(
            "CHANGE ORDER\nCO Number: 1\nProject: A\n"
            "Total: USD 100\nFinal Amount: USD 100\nApproved Amount: USD 120"
        ),
        options=offline,
    )
    assert result.data.approved_amount.value == 120
    assert any(issue.code == "TOTAL_ROLE_MISMATCH" for issue in result.issues)


def test_contract_total_context_is_not_treated_as_change_amount(offline):
    result = extract(
        text=(
            "CHANGE ORDER\nCO Number: 1\nProject: A\nFINANCIAL SUMMARY\n"
            "Subtotal: USD 90\nTax Total: USD 10\n"
            "Current Contract Total: USD 110\nProposed Change Amount: USD 20"
        ),
        options=offline,
    )
    assert result.data.revised_contract_amount.value == 110
    assert result.data.total_change_amount.value == 20
    assert result.data.amount_basis.value == "proposed"


def test_credits_and_line_subtotal_are_validated(offline):
    result = extract(
        text=(
            "CHANGE ORDER\nCO Number: 1\nProject: A\nCredits/Deductions: (USD 20)\n"
            "Description | Qty | Unit Price | Amount\n"
            "Labor | 2 | USD 10 | USD 20\nSubtotal: USD 19\n"
            "Total Change Amount: USD 20"
        ),
        options=offline,
    )
    assert result.data.credits_deductions.value == Decimal("-20.00")
    assert any(issue.code == "LINE_SUBTOTAL_MISMATCH" for issue in result.issues)
