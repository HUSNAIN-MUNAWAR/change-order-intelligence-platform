export type FieldValidation = "valid" | "missing" | "invalid" | "warning" | "conflict";
export type ExtractionMethod = "label" | "title" | "table" | "llm" | "missing";

export interface Evidence {
  source: string;
  page: number | null;
  line_start: number;
  line_end: number;
  char_start: number;
  char_end: number;
  text: string;
  text_origin: "native" | "ocr" | "text";
}

export interface ExtractedField<T = unknown> {
  value: T | null;
  confidence: number;
  evidence: Evidence[] | null;
  method: ExtractionMethod;
  validation: FieldValidation;
  signals: string[];
  alternatives: Array<{ value: unknown; evidence: Evidence[]; method: ExtractionMethod }>;
}

export interface CostItem {
  description: ExtractedField<string>;
  quantity: ExtractedField<number>;
  unit: ExtractedField<string>;
  unit_price: ExtractedField<number>;
  amount: ExtractedField<number>;
}

export type ChangeOrder = Record<string, ExtractedField | ExtractedField<CostItem[]>>;

export interface PageText {
  page: number | null;
  raw_text: string;
  cleaned_text: string;
  native_text: string | null;
  text_origin: "native" | "ocr" | "text";
  ocr_quality: number | null;
}

export interface Source {
  identifier: string;
  filename: string | null;
  sha256: string | null;
  media_type: string;
  byte_count: number | null;
  metadata: Record<string, string>;
  pages: PageText[];
}

export interface Issue {
  code: string;
  severity: "info" | "warning" | "recoverable_error" | "fatal_error";
  message: string;
  field: string | null;
  evidence: Evidence | null;
}

export interface ExtractionResult {
  schema_version: "1.0";
  pipeline_version: string;
  status: "success" | "partial" | "failed";
  source: Source;
  data: ChangeOrder;
  issues: Issue[];
  missing_fields: string[];
  consistency: "passed" | "warning" | "not_checked";
  llm_used: boolean;
  processing_ms: number;
}

export interface Capabilities {
  service: string;
  supported_formats: string[];
  supported_media_types: string[];
  max_file_bytes: number;
  max_batch_files: number;
  max_batch_bytes: number;
  max_pages: number;
  ocr: { available: boolean; version: string | null; languages: string[]; message: string };
  llm: { available: boolean; configured: boolean; message: string };
  extraction_options: string[];
}

export interface ExtractionOptions {
  ocr: "off" | "auto" | "force";
  llm: boolean;
  date_order: "reject" | "mdy" | "dmy";
}

export interface BatchResponse {
  results: ExtractionResult[];
  processed: number;
  failed: number;
}
