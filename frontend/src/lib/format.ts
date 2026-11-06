import type { ExtractedField } from "@/types";

export const FIELD_GROUPS: Record<string, string[]> = {
  "Document identity": ["change_order_number", "document_title", "document_date", "revision"],
  "Project information": ["project_name", "project_number", "description", "reason", "discipline", "referenced_documents"],
  "Contractor / owner": ["contractor", "subcontractor", "owner", "architect_engineer"],
  "Financial details": ["currency", "total_change_amount", "amount_basis", "requested_amount", "proposed_amount", "approved_amount", "final_amount", "previous_contract_amount", "revised_contract_amount", "credits_deductions", "line_items"],
  "Schedule changes": ["schedule_impact", "schedule_unit", "proposed_completion_date"],
  "Approval information": ["approval_status", "approval_date", "approver_name"],
};

export const FIELD_LABELS: Record<string, string> = {
  change_order_number: "Change order number",
  project_name: "Project name",
  project_number: "Project number",
  document_title: "Document title",
  document_date: "Document date",
  revision: "Revision",
  contractor: "Contractor",
  subcontractor: "Subcontractor",
  owner: "Owner",
  architect_engineer: "Architect / engineer",
  description: "Description",
  reason: "Reason",
  discipline: "Discipline",
  referenced_documents: "Referenced documents",
  total_change_amount: "Total change amount",
  requested_amount: "Requested amount",
  proposed_amount: "Proposed amount",
  approved_amount: "Approved amount",
  final_amount: "Final amount",
  amount_basis: "Amount basis",
  currency: "Currency",
  previous_contract_amount: "Previous contract amount",
  revised_contract_amount: "Revised contract amount",
  credits_deductions: "Credits / deductions",
  line_items: "Line items",
  schedule_impact: "Schedule impact",
  schedule_unit: "Schedule unit",
  proposed_completion_date: "Proposed completion date",
  approval_status: "Approval status",
  approval_date: "Approval date",
  approver_name: "Approver name",
};

export function labelFor(name: string) {
  return FIELD_LABELS[name] ?? name.replaceAll("_", " ");
}

export function confidenceBand(field: ExtractedField) {
  if (field.value === null) return "Missing";
  if (field.validation === "conflict") return "Conflicting";
  if (field.confidence >= 0.8) return "High";
  if (field.confidence >= 0.6) return "Medium";
  return "Low";
}

export function displayValue(value: unknown): string {
  if (value === null || value === undefined) return "Not found";
  if (Array.isArray(value)) return value.map(displayValue).join(", ");
  if (typeof value === "object") return `${Object.keys(value).length} items`;
  return String(value);
}

export function bytes(value: number) {
  if (value < 1024) return `${value} B`;
  if (value < 1024 * 1024) return `${(value / 1024).toFixed(1)} KB`;
  return `${(value / (1024 * 1024)).toFixed(1)} MB`;
}

export function safeJsonDownload(result: unknown) {
  return JSON.stringify(result, null, 2);
}
