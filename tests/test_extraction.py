from decimal import Decimal

from changeorder.pipeline import extract


def test_all_clean_sections(documents, offline):
    result = extract(documents / "01_clean.txt", options=offline)
    assert result.status == "success"
    assert result.data.change_order_number.value == "CO-001"
    assert result.data.architect_engineer.value == "Northline Design Group"
    assert result.data.total_change_amount.value == Decimal("12500")
    assert result.data.referenced_documents.value == ["E-201 Rev C", "RFI-087"]
    assert result.data.approval_status.value == "approved"


def test_wrapping_identifiers_and_role(documents, offline):
    data = extract(documents / "02_messy.txt", options=offline).data
    assert data.change_order_number.value == "0007-B"
    assert (
        data.description.value
        == "Reroute chilled water piping above the corridor ceiling.\nProvide two isolation valves and restore insulation."
    )
    assert data.amount_basis.value == "proposed"
    assert data.schedule_unit.value == "working_days"


def test_signature_label_is_not_approval(documents, offline):
    data = extract(documents / "09_missing_parties.txt", options=offline).data
    assert data.approval_status.value is None
    assert data.approver_name.value is None
    assert data.currency.value is None
    assert data.contractor.value is None


def test_requested_approved_and_subtotal_do_not_collide(offline):
    result = extract(
        text="CHANGE ORDER\nCO Number: 0005\nProject: A\nSubtotal: USD 5,000\nRequested Amount: USD 6,000\nApproved Amount: USD 5,500",
        options=offline,
    )
    assert result.data.requested_amount.value == 6000
    assert result.data.approved_amount.value == 5500
    assert result.data.total_change_amount.value == 5500
    assert result.data.amount_basis.value == "approved"
    assert result.data.total_change_amount.validation == "valid"


def test_unrelated_ids_and_currency_not_extracted(offline):
    result = extract(
        text="CHANGE ORDER\nProject: A\nInvoice Number: INV-1\nDrawing: A-002\nPage: 2\nInvoice value: EUR 500\nTotal Change Amount: 100",
        options=offline,
    )
    assert result.data.change_order_number.value is None
    assert result.data.currency.value is None
    assert result.data.total_change_amount.value == 100


def test_credit_and_items(documents, offline):
    credit = extract(documents / "07_credit.txt", options=offline).data
    assert credit.credits_deductions.value == -1200
    assert credit.revised_contract_amount.value == 48800
    result = extract(documents / "08_cost_items.txt", options=offline)
    assert result.consistency == "passed"
    assert len(result.data.line_items.value) == 3
    assert result.data.line_items.value[0].quantity.value == 20


def test_multi_page_evidence_and_duplicate_headers(documents, offline):
    result = extract(documents / "04_multipage.pdf", options=offline)
    assert result.data.change_order_number.validation == "valid"
    assert len(result.data.change_order_number.evidence) == 2
    assert result.data.total_change_amount.evidence[0].page == 2
    assert result.data.contractor.evidence[0].page == 1


def test_inline_fields_preserve_exact_source_offsets(offline):
    text = "CHANGE ORDER\nCO Number: 0003; Project Name: Field Office    Contractor: Apex Build\nTotal: USD 100"
    result = extract(text=text, options=offline)
    assert result.status == "success"
    assert result.data.project_name.value == "Field Office"
    assert result.data.contractor.value == "Apex Build"
    for field in (
        result.data.change_order_number,
        result.data.project_name,
        result.data.contractor,
    ):
        ev = field.evidence[0]
        assert ev.line_start == 2 and text[ev.char_start : ev.char_end] == ev.text


def test_blank_approver_does_not_consume_unknown_signature_label(offline):
    result = extract(
        text="CHANGE ORDER\nCO # 0004\nProject: A\nTotal: 50\nApproved By:\nSignature: __________",
        options=offline,
    )
    assert result.data.change_order_number.value == "0004"
    assert result.data.approver_name.value is None
    assert result.data.approval_status.value is None


def test_cost_row_currency_and_section_boundary(offline):
    text = "CHANGE ORDER\nCO Number: 1\nProject: A\nDescription: Replace valve.\nCOST BREAKDOWN\nDescription | Qty | Unit Price | Amount\nLabor | 2 | EUR 10 | USD 20\nTotal: USD 20"
    result = extract(text=text, options=offline)
    assert result.data.description.value == "Replace valve."
    assert result.data.currency.validation == "conflict"
    assert any(issue.code == "MIXED_CURRENCY" for issue in result.issues)


def test_dollar_only_table_currency_not_assumed(offline):
    result = extract(
        text="CHANGE ORDER\nCO Number: 1\nProject: A\nDescription | Amount\nLabor | $20\nTotal: 20",
        options=offline,
    )
    assert result.data.currency.value is None
    assert any(issue.code == "AMBIGUOUS_CURRENCY" for issue in result.issues)
