from decimal import Decimal

from changeorder.pipeline import extract


def test_public_agency_form_layout_labels_are_extracted_without_special_case_values():
    text = """CONTRACT CHANGE ORDER NO. 6
PROJECT: TCC Park at MLK Magnet Core                                      SHEET      1 of 1
PROJECT I.D. PW00857
CONTRACTOR: Avison Construction, Inc.
Description:
Install temporary battery controllers for the irrigation system.
Increase in Contract Price........................................................................ $ 24,292.00
II. CONTRACT PRICE
Estimated Increase in Contract Price.......................................................... $ 112,478.32
Change In Contract Time........................................................................ 60 Days
Cost of this Change Order         $ 112,478.32 Increase
Original Contract Price              $ 8,646,293.00
Revised Contract Price               $ 10,992,895.24
"""

    result = extract(text=text)

    assert result.status == "partial"
    assert result.data.change_order_number.value == "6"
    assert result.data.project_name.value == "TCC Park at MLK Magnet Core"
    assert result.data.project_number.value == "PW00857"
    assert result.data.total_change_amount.value == Decimal("112478.32")
    assert result.data.previous_contract_amount.value == Decimal("8646293.00")
    assert result.data.revised_contract_amount.value == Decimal("10992895.24")
    assert result.data.schedule_impact.value == Decimal("60")
    assert result.data.schedule_unit.value == "days"
    assert result.data.total_change_amount.evidence[0].text.startswith("Cost of this Change Order")
