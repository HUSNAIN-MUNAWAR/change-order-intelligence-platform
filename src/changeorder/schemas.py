"""Public output contract. Decimal amounts are serialized as exact JSON numbers by jsonio."""

from datetime import date
from decimal import Decimal
from typing import Annotated, Generic, Literal, TypeVar

from pydantic import BaseModel, ConfigDict, Field, PrivateAttr, StrictStr, model_validator

Money = Annotated[Decimal, Field(allow_inf_nan=False, max_digits=18, decimal_places=2)]
Number = Annotated[Decimal, Field(allow_inf_nan=False, max_digits=18, decimal_places=4)]
T = TypeVar("T")
Method = Literal["label", "title", "table", "llm", "missing"]


class Model(BaseModel):
    model_config = ConfigDict(extra="forbid", validate_assignment=True)


class Evidence(Model):
    source: str
    page: int | None = Field(default=None, ge=1)
    line_start: int = Field(ge=1)
    line_end: int = Field(ge=1)
    char_start: int = Field(ge=0)
    char_end: int = Field(ge=0)
    text: str
    text_origin: Literal["native", "ocr", "text"]

    @model_validator(mode="after")
    def ordered_span(self):
        if self.line_end < self.line_start or self.char_end <= self.char_start:
            raise ValueError("Evidence spans must be nonempty and ordered")
        if len(self.text) != self.char_end - self.char_start:
            raise ValueError("Evidence text must exactly cover its character span")
        return self


class Alternative(Model, Generic[T]):
    value: T
    evidence: list[Evidence] = Field(min_length=1)
    method: Method


class ExtractedField(Model, Generic[T]):
    value: T | None = None
    confidence: float = Field(default=0.0, ge=0.0, le=1.0, allow_inf_nan=False)
    evidence: list[Evidence] | None = None
    method: Method = "missing"
    validation: Literal["valid", "missing", "invalid", "warning", "conflict"] = "missing"
    signals: list[str] = Field(default_factory=list)
    alternatives: list[Alternative[T]] = Field(default_factory=list)

    @model_validator(mode="after")
    def supported_value(self):
        if self.value is None:
            if self.confidence != 0 or self.evidence is not None or self.method != "missing":
                raise ValueError(
                    "Null values require zero confidence, null evidence, missing method"
                )
            if self.validation not in {"missing", "invalid"}:
                raise ValueError("Null values must be missing or invalid")
        elif (
            not self.evidence
            or self.method == "missing"
            or self.validation in {"missing", "invalid"}
        ):
            raise ValueError(
                "Values require evidence, extraction method and usable validation status"
            )
        return self


class CostItem(Model):
    description: ExtractedField[StrictStr]
    quantity: ExtractedField[Number] = Field(default_factory=ExtractedField)
    unit: ExtractedField[StrictStr] = Field(default_factory=ExtractedField)
    unit_price: ExtractedField[Money] = Field(default_factory=ExtractedField)
    amount: ExtractedField[Money]


class ChangeOrder(Model):
    change_order_number: ExtractedField[StrictStr] = Field(default_factory=ExtractedField)
    project_name: ExtractedField[StrictStr] = Field(default_factory=ExtractedField)
    project_number: ExtractedField[StrictStr] = Field(default_factory=ExtractedField)
    document_title: ExtractedField[StrictStr] = Field(default_factory=ExtractedField)
    document_date: ExtractedField[date] = Field(default_factory=ExtractedField)
    revision: ExtractedField[StrictStr] = Field(default_factory=ExtractedField)
    contractor: ExtractedField[StrictStr] = Field(default_factory=ExtractedField)
    subcontractor: ExtractedField[StrictStr] = Field(default_factory=ExtractedField)
    owner: ExtractedField[StrictStr] = Field(default_factory=ExtractedField)
    architect_engineer: ExtractedField[StrictStr] = Field(default_factory=ExtractedField)
    description: ExtractedField[StrictStr] = Field(default_factory=ExtractedField)
    reason: ExtractedField[StrictStr] = Field(default_factory=ExtractedField)
    discipline: ExtractedField[StrictStr] = Field(default_factory=ExtractedField)
    referenced_documents: ExtractedField[list[StrictStr]] = Field(default_factory=ExtractedField)
    total_change_amount: ExtractedField[Money] = Field(default_factory=ExtractedField)
    requested_amount: ExtractedField[Money] = Field(default_factory=ExtractedField)
    proposed_amount: ExtractedField[Money] = Field(default_factory=ExtractedField)
    approved_amount: ExtractedField[Money] = Field(default_factory=ExtractedField)
    final_amount: ExtractedField[Money] = Field(default_factory=ExtractedField)
    amount_basis: ExtractedField[
        Literal["stated_total", "requested", "proposed", "approved", "final"]
    ] = Field(default_factory=ExtractedField)
    currency: ExtractedField[StrictStr] = Field(default_factory=ExtractedField)
    previous_contract_amount: ExtractedField[Money] = Field(default_factory=ExtractedField)
    revised_contract_amount: ExtractedField[Money] = Field(default_factory=ExtractedField)
    credits_deductions: ExtractedField[Money] = Field(default_factory=ExtractedField)
    line_items: ExtractedField[list[CostItem]] = Field(default_factory=ExtractedField)
    schedule_impact: ExtractedField[Number] = Field(default_factory=ExtractedField)
    schedule_unit: ExtractedField[
        Literal["days", "calendar_days", "working_days", "weeks", "hours"]
    ] = Field(default_factory=ExtractedField)
    proposed_completion_date: ExtractedField[date] = Field(default_factory=ExtractedField)
    approval_status: ExtractedField[
        Literal["approved", "pending", "proposed", "requested", "rejected", "draft", "void"]
    ] = Field(default_factory=ExtractedField)
    approval_date: ExtractedField[date] = Field(default_factory=ExtractedField)
    approver_name: ExtractedField[StrictStr] = Field(default_factory=ExtractedField)


class Issue(Model):
    code: str
    severity: Literal["info", "warning", "recoverable_error", "fatal_error"] = "warning"
    message: str
    field: str | None = None
    evidence: Evidence | None = None


class PageText(Model):
    page: int | None = Field(default=None, ge=1)
    raw_text: str
    cleaned_text: str
    native_text: str | None = None
    text_origin: Literal["native", "ocr", "text"]
    ocr_quality: float | None = Field(default=None, ge=0, le=1)
    # Internal-only ranges let evidence identify mixed native/OCR spans without
    # changing the serialized/public PageText contract.
    _origin_ranges: list[tuple[int, int, Literal["native", "ocr", "text"]]] = PrivateAttr(
        default_factory=list
    )


class Source(Model):
    identifier: str
    filename: str | None = None
    sha256: str | None = None
    media_type: str
    byte_count: int | None = None
    metadata: dict[str, str] = Field(default_factory=dict)
    pages: list[PageText] = Field(default_factory=list)


class ExtractionResult(Model):
    schema_version: Literal["1.0"] = "1.0"
    pipeline_version: str = "0.1.0"
    status: Literal["success", "partial", "failed"]
    source: Source
    data: ChangeOrder = Field(default_factory=ChangeOrder)
    issues: list[Issue] = Field(default_factory=list)
    missing_fields: list[str] = Field(default_factory=list)
    consistency: Literal["passed", "warning", "not_checked"] = "not_checked"
    llm_used: bool = False
    processing_ms: float = Field(ge=0)
