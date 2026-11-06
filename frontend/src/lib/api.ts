import type {
  BatchResponse,
  Capabilities,
  ExtractionOptions,
  ExtractionResult,
} from "@/types";

const API_BASE = (process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000").replace(/\/$/, "");

interface ApiErrorPayload {
  code?: string;
  message?: string;
}

async function parseResponse<T>(response: Response): Promise<T> {
  const payload = (await response.json()) as T | ApiErrorPayload;
  if (!response.ok) {
    const error = payload as ApiErrorPayload;
    throw new Error(error.message ?? `Backend request failed (${response.status})`);
  }
  return payload as T;
}

function formData(files: File[], options: ExtractionOptions, fieldName: "file" | "files") {
  const form = new FormData();
  files.forEach((file) => form.append(fieldName, file, file.name));
  form.append("ocr", options.ocr);
  form.append("llm", String(options.llm));
  form.append("date_order", options.date_order);
  return form;
}

export async function getCapabilities(): Promise<Capabilities> {
  const response = await fetch(`${API_BASE}/api/v1/capabilities`, { cache: "no-store" });
  return parseResponse<Capabilities>(response);
}

export async function extractDocument(file: File, options: ExtractionOptions): Promise<ExtractionResult> {
  const response = await fetch(`${API_BASE}/api/v1/extract`, {
    method: "POST",
    body: formData([file], options, "file"),
  });
  return parseResponse<ExtractionResult>(response);
}

export async function extractBatch(files: File[], options: ExtractionOptions): Promise<BatchResponse> {
  const response = await fetch(`${API_BASE}/api/v1/batch`, {
    method: "POST",
    body: formData(files, options, "files"),
  });
  return parseResponse<BatchResponse>(response);
}

export function apiBaseUrl() {
  return API_BASE;
}
