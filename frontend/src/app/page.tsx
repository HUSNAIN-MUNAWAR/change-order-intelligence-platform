"use client";

import {
  AlertTriangle,
  CheckCircle2,
  ChevronDown,
  Clipboard,
  Code2,
  Download,
  FileCheck2,
  FileImage,
  FileText,
  FolderOpen,
  Info,
  Layers3,
  Moon,
  PackageCheck,
  Play,
  RotateCcw,
  ShieldCheck,
  Sparkles,
  Sun,
  UploadCloud,
  XCircle,
} from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import type { LucideIcon } from "lucide-react";

import { extractBatch, extractDocument, getCapabilities } from "@/lib/api";
import {
  bytes,
  confidenceBand,
  displayValue,
  FIELD_GROUPS,
  labelFor,
  safeJsonDownload,
} from "@/lib/format";
import type {
  Capabilities,
  ExtractionOptions,
  ExtractionResult,
  ExtractedField,
  Issue,
  PageText,
} from "@/types";

type Stage = "idle" | "uploading" | "processing" | "complete" | "failed";

const DEFAULT_CAPABILITIES: Capabilities = {
  service: "sledge-change-order-intelligence",
  supported_formats: [".pdf", ".txt", ".png", ".jpg", ".jpeg"],
  supported_media_types: ["application/pdf", "text/plain", "image/png", "image/jpeg"],
  max_file_bytes: 20 * 1024 * 1024,
  max_batch_files: 8,
  max_batch_bytes: 40 * 1024 * 1024,
  max_pages: 100,
  ocr: { available: false, version: null, languages: [], message: "Checking local OCR availability…" },
  llm: { available: false, configured: false, message: "Checking optional AI availability…" },
  extraction_options: [],
};

function StatusChip({ stage }: { stage: Stage }) {
  const states: Record<Stage, { label: string; className: string }> = {
    idle: { label: "Ready", className: "text-slate-500 bg-slate-100" },
    uploading: { label: "Uploading", className: "text-amber-700 bg-amber-50" },
    processing: { label: "Processing", className: "text-blue-700 bg-blue-50" },
    complete: { label: "Complete", className: "text-emerald-700 bg-emerald-50" },
    failed: { label: "Failed", className: "text-rose-700 bg-rose-50" },
  };
  const state = states[stage];
  return <span className={`rounded-full px-2.5 py-1 text-[11px] font-bold uppercase tracking-wider ${state.className}`}>{state.label}</span>;
}

function ConfidenceBadge({ field }: { field: ExtractedField }) {
  const band = confidenceBand(field);
  const colors = {
    High: "text-emerald-700 bg-emerald-50 border-emerald-100",
    Medium: "text-amber-700 bg-amber-50 border-amber-100",
    Low: "text-rose-700 bg-rose-50 border-rose-100",
    Missing: "text-slate-500 bg-slate-100 border-slate-200",
    Conflicting: "text-violet-700 bg-violet-50 border-violet-100",
  };
  return <span className={`rounded-md border px-2 py-1 text-[10px] font-bold uppercase tracking-widest ${colors[band]}`}>{band} · {Math.round(field.confidence * 100)}%</span>;
}

function Evidence({ field }: { field: ExtractedField }) {
  if (!field.evidence?.length && !field.alternatives.length && !field.signals.length) return null;
  return (
    <details className="mt-3 border-t border-[var(--line)] pt-3">
      <summary className="flex cursor-pointer list-none items-center justify-between text-xs font-semibold text-[var(--muted)]">
        <span>Evidence & explanation</span><ChevronDown size={14} />
      </summary>
      <div className="mt-3 space-y-3">
        {field.evidence?.map((item, index) => (
          <div key={`${item.char_start}-${index}`} className="rounded-lg border border-[var(--line)] bg-black/[.025] p-3">
            <div className="mb-1 flex flex-wrap gap-2 text-[10px] font-bold uppercase tracking-wider text-[var(--muted)]">
              <span>{item.page ? `Page ${item.page}` : "Text source"}</span>
              <span>Lines {item.line_start}–{item.line_end}</span>
              <span>{item.text_origin}</span>
            </div>
            <p className="mono whitespace-pre-wrap text-xs leading-5 text-[var(--ink)]">{item.text}</p>
          </div>
        ))}
        {field.alternatives.map((alternative, index) => (
          <div key={index} className="rounded-lg border border-violet-200 bg-violet-50/50 p-3 text-xs">
            <div className="font-bold uppercase tracking-wider text-violet-700">Conflicting alternative</div>
            <div className="mt-1 text-[var(--ink)]">{displayValue(alternative.value)}</div>
            <div className="mt-1 text-[var(--muted)]">Method: {alternative.method}</div>
          </div>
        ))}
        {field.signals.length > 0 && <div className="mono text-[10px] leading-5 text-[var(--muted)]">{field.signals.join(" · ")}</div>}
      </div>
    </details>
  );
}

function FieldCard({ name, field }: { name: string; field: ExtractedField }) {
  const isLineItems = name === "line_items" && Array.isArray(field.value);
  return (
    <article className="field-card rounded-xl p-4">
      <div className="flex items-start justify-between gap-3">
        <div>
          <div className="text-[11px] font-bold uppercase tracking-widest text-[var(--muted)]">{labelFor(name)}</div>
          <div className={`mt-2 ${isLineItems ? "text-sm" : "text-[15px]"} font-semibold leading-6 text-[var(--ink)]`}>
            {isLineItems ? `${(field.value as unknown[]).length} extracted cost item(s)` : displayValue(field.value)}
          </div>
        </div>
        <ConfidenceBadge field={field} />
      </div>
      <div className="mt-3 flex flex-wrap gap-2 text-[10px] font-semibold uppercase tracking-wider text-[var(--muted)]">
        <span>{field.validation}</span><span>·</span><span>{field.method}</span>
      </div>
      {isLineItems && (
        <div className="mt-3 space-y-2">
          {(field.value as Array<Record<string, ExtractedField>>).map((item, index) => (
            <div key={index} className="rounded-lg border border-[var(--line)] p-3 text-xs">
              <div className="mb-2 font-bold text-[var(--ink)]">Item {index + 1} · {displayValue(item.description?.value)}</div>
              <div className="grid grid-cols-2 gap-2 text-[var(--muted)] sm:grid-cols-4">
                <span>Qty: {displayValue(item.quantity?.value)}</span><span>Unit: {displayValue(item.unit?.value)}</span><span>Rate: {displayValue(item.unit_price?.value)}</span><span>Amount: {displayValue(item.amount?.value)}</span>
              </div>
            </div>
          ))}
        </div>
      )}
      <Evidence field={field} />
    </article>
  );
}

function IssueList({ issues }: { issues: Issue[] }) {
  if (!issues.length) return <div className="rounded-xl border border-emerald-100 bg-emerald-50/70 p-4 text-sm text-emerald-800"><CheckCircle2 className="mr-2 inline" size={17} />No backend warnings for this result.</div>;
  return (
    <div className="space-y-2">
      {issues.map((issue, index) => (
        <div key={`${issue.code}-${index}`} className={`rounded-xl border p-4 ${issue.severity === "fatal_error" ? "border-rose-200 bg-rose-50/70" : issue.severity === "info" ? "border-sky-200 bg-sky-50/70" : "border-amber-200 bg-amber-50/70"}`}>
          <div className="flex items-start gap-3"><AlertTriangle size={17} className="mt-0.5 shrink-0" /><div><div className="text-xs font-bold uppercase tracking-wider">{issue.severity} · {issue.code}{issue.field ? ` · ${labelFor(issue.field)}` : ""}</div><p className="mt-1 text-sm leading-6">{issue.message}</p>{issue.evidence && <p className="mono mt-2 whitespace-pre-wrap text-xs opacity-75">{issue.evidence.text}</p>}</div></div>
        </div>
      ))}
    </div>
  );
}

function SourcePreview({ file, result }: { file: File | null; result: ExtractionResult }) {
  const [page, setPage] = useState(1);
  const [zoom, setZoom] = useState("page-width");
  const pageData: PageText | undefined = result.source.pages[page - 1];
  const url = useMemo(() => (file ? URL.createObjectURL(file) : null), [file]);
  useEffect(() => () => { if (url) URL.revokeObjectURL(url); }, [url]);
  const suffix = file?.name.toLowerCase().split(".").pop();
  return (
    <section className="panel min-h-[560px] rounded-2xl p-5">
      <div className="flex items-center justify-between gap-3"><div><div className="eyebrow">SOURCE DOCUMENT</div><h2 className="mt-1 text-lg font-bold">{file?.name ?? result.source.identifier}</h2></div><FileCheck2 className="text-[var(--accent)]" size={22} /></div>
      <div className="mt-4 flex flex-wrap items-center gap-2 text-xs text-[var(--muted)]"><span>{result.source.media_type}</span><span>·</span><span>{result.source.pages.length} page(s)</span>{result.source.sha256 && <><span>·</span><span className="mono">{result.source.sha256.slice(0, 12)}…</span></>}</div>
      {result.source.pages.length > 1 && <div className="mt-4 flex items-center justify-between"><label className="text-xs font-semibold text-[var(--muted)]" htmlFor="preview-page">Page</label><select id="preview-page" value={page} onChange={(event) => setPage(Number(event.target.value))} className="rounded-lg border border-[var(--line)] bg-[var(--surface)] px-2 py-1 text-sm"><option value={1}>1</option>{result.source.pages.slice(1).map((_, index) => <option key={index + 2} value={index + 2}>{index + 2}</option>)}</select></div>}
      <div className="mt-4 overflow-hidden rounded-xl border border-[var(--line)] bg-[var(--canvas)]">
        {suffix === "pdf" && url ? <iframe title="PDF source preview" src={`${url}#page=${page}&zoom=${zoom}`} className="h-[620px] w-full" /> : suffix && ["png", "jpg", "jpeg"].includes(suffix) && url ? <img src={url} alt={`Preview of ${file?.name}`} className="max-h-[620px] w-full object-contain" /> : <pre className="mono max-h-[620px] overflow-auto whitespace-pre-wrap p-5 text-xs leading-6 text-[var(--ink)]">{pageData?.raw_text ?? "No readable source text."}</pre>}
      </div>
      {suffix === "pdf" && <div className="mt-3 flex items-center justify-between"><span className="text-xs text-[var(--muted)]">Original document preview. No unsupported highlights are inferred.</span><select aria-label="PDF zoom" value={zoom} onChange={(event) => setZoom(event.target.value)} className="rounded-lg border border-[var(--line)] bg-[var(--surface)] px-2 py-1 text-xs"><option value="page-width">Fit width</option><option value="100">100%</option><option value="150">150%</option></select></div>}
      <div className="mt-4 rounded-xl border border-[var(--line)] bg-[var(--surface)] p-4"><div className="flex items-center gap-2 text-xs font-bold uppercase tracking-wider text-[var(--muted)]"><Info size={14} /> Extracted text evidence</div><p className="mono mt-2 max-h-32 overflow-auto whitespace-pre-wrap text-xs leading-5 text-[var(--ink)]">{pageData?.raw_text ?? "No source text returned."}</p></div>
    </section>
  );
}

function ResultPanel({ result, file }: { result: ExtractionResult; file: File | null }) {
  const [group, setGroup] = useState("Document identity");
  const [jsonOpen, setJsonOpen] = useState(false);
  const json = safeJsonDownload(result);
  const fields = FIELD_GROUPS[group].filter((name) => name in result.data);
  async function copyJson() { await navigator.clipboard.writeText(json); }
  function downloadJson() { const link = document.createElement("a"); link.href = URL.createObjectURL(new Blob([json], { type: "application/json" })); link.download = `${result.source.identifier}.json`; link.click(); URL.revokeObjectURL(link.href); }
  return (
    <div className="mt-8 space-y-6">
      <div className="grid gap-4 sm:grid-cols-4">
        {([["Fields found", Object.values(result.data).filter((field) => field.value !== null).length.toString(), FileCheck2], ["Needs review", Object.values(result.data).filter((field) => field.validation === "warning" || field.validation === "conflict").length.toString(), AlertTriangle], ["OCR pages", result.source.pages.filter((page) => page.text_origin === "ocr").length.toString(), FileImage], ["Processing", `${(result.processing_ms / 1000).toFixed(2)}s`, Play]] as Array<[string, string, LucideIcon]>).map(([label, value, Icon]) => <div key={label} className="panel rounded-xl p-4"><Icon size={17} className="text-[var(--accent)]" /><div className="mt-3 text-2xl font-bold">{value}</div><div className="mt-1 text-xs font-semibold uppercase tracking-wider text-[var(--muted)]">{label}</div></div>)}
      </div>
      <div className="two-col grid grid-cols-[minmax(0,.95fr)_minmax(0,1.05fr)] gap-6">
        <SourcePreview key={result.source.identifier} file={file} result={result} />
        <section className="panel rounded-2xl p-5"><div className="flex flex-wrap items-end justify-between gap-3"><div><div className="eyebrow">VALIDATED EXTRACTION</div><h2 className="mt-1 text-lg font-bold">Structured fields</h2></div><StatusChip stage={result.status === "failed" ? "failed" : result.status === "partial" ? "processing" : "complete"} /></div><div className="mt-5"><label htmlFor="field-group" className="mb-2 block text-xs font-bold uppercase tracking-widest text-[var(--muted)]">Field group</label><select id="field-group" value={group} onChange={(event) => setGroup(event.target.value)} className="w-full rounded-xl border border-[var(--line)] bg-[var(--surface)] px-3 py-2.5 text-sm font-semibold">{Object.keys(FIELD_GROUPS).map((name) => <option key={name}>{name}</option>)}</select></div><div className="mt-4 space-y-3">{fields.map((name) => <FieldCard key={name} name={name} field={result.data[name]} />)}</div><p className="mt-4 text-[11px] leading-5 text-[var(--muted)]">Confidence is a heuristic support score, not a calibrated probability. Evidence snippets are returned by the backend and can be audited against the source page.</p></section>
      </div>
      <section className="panel rounded-2xl p-5"><div className="flex items-center gap-3"><ShieldCheck className="text-[var(--accent)]" size={20} /><div><div className="eyebrow">VALIDATION AND WARNINGS</div><h2 className="mt-1 text-lg font-bold">Backend review signals</h2></div></div><div className="mt-4"><IssueList issues={result.issues} /></div></section>
      <section className="panel rounded-2xl p-5"><div className="flex flex-wrap items-center justify-between gap-3"><div className="flex items-center gap-3"><Code2 className="text-[var(--accent)]" size={20} /><div><div className="eyebrow">JSON OUTPUT</div><h2 className="mt-1 text-lg font-bold">Canonical response</h2></div></div><div className="flex gap-2"><button type="button" onClick={() => void copyJson()} className="muted-button inline-flex items-center gap-2 rounded-lg px-3 py-2 text-xs font-bold"><Clipboard size={15} /> Copy</button><button type="button" onClick={downloadJson} className="accent-button inline-flex items-center gap-2 rounded-lg px-3 py-2 text-xs font-bold"><Download size={15} /> Download</button></div></div><button type="button" onClick={() => setJsonOpen(!jsonOpen)} className="mt-4 flex w-full items-center justify-between rounded-xl border border-[var(--line)] p-3 text-left text-xs font-semibold text-[var(--muted)]"><span>{jsonOpen ? "Hide formatted JSON" : "Show formatted JSON"}</span><ChevronDown size={15} className={jsonOpen ? "rotate-180" : ""} /></button>{jsonOpen && <pre className="mono mt-3 max-h-[460px] overflow-auto rounded-xl bg-slate-950 p-4 text-xs leading-5 text-slate-100">{json}</pre>}</section>
    </div>
  );
}

export default function Page() {
  const [capabilities, setCapabilities] = useState<Capabilities>(DEFAULT_CAPABILITIES);
  const [files, setFiles] = useState<File[]>([]);
  const [result, setResult] = useState<ExtractionResult | null>(null);
  const [batchResults, setBatchResults] = useState<ExtractionResult[]>([]);
  const [activeBatch, setActiveBatch] = useState(0);
  const [stage, setStage] = useState<Stage>("idle");
  const [error, setError] = useState<string | null>(null);
  const [dragging, setDragging] = useState(false);
  const [darkMode, setDarkMode] = useState(false);
  const [showRaw, setShowRaw] = useState(false);
  const [options, setOptions] = useState<ExtractionOptions>({ ocr: "auto", llm: false, date_order: "reject" });
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => { getCapabilities().then(setCapabilities).catch(() => setError("Backend is not reachable. Start FastAPI on port 8000 to process documents.")); }, []);

  function acceptFiles(incoming: File[]) {
    setError(null);
    const allowed = capabilities.supported_formats.map((item) => item.slice(1));
    const invalid = incoming.find((file) => !allowed.includes(file.name.toLowerCase().split(".").pop() ?? ""));
    if (invalid) { setError(`${invalid.name} is not a supported document. Use PDF, TXT, PNG or JPEG.`); return; }
    if (incoming.some((file) => file.size > capabilities.max_file_bytes)) { setError(`Each file must be smaller than ${bytes(capabilities.max_file_bytes)}.`); return; }
    if (incoming.length > capabilities.max_batch_files) { setError(`Select no more than ${capabilities.max_batch_files} files.`); return; }
    if (incoming.reduce((total, file) => total + file.size, 0) > capabilities.max_batch_bytes) { setError(`The batch must be smaller than ${bytes(capabilities.max_batch_bytes)}.`); return; }
    setFiles(incoming); setResult(null); setBatchResults([]); setActiveBatch(0); setStage("idle");
  }

  async function loadExample(path: string, name: string) {
    try { const response = await fetch(path); const blob = await response.blob(); acceptFiles([new File([blob], name, { type: "text/plain" })]); } catch { setError("The selected example could not be loaded."); }
  }

  async function runExtraction() {
    if (!files.length) return;
    setError(null); setStage("uploading");
    try {
      setStage("processing");
      if (files.length === 1) { const single = await extractDocument(files[0], options); setResult(single); setBatchResults([]); }
      else { const batch = await extractBatch(files, options); setBatchResults(batch.results); setActiveBatch(0); setResult(batch.results[0] ?? null); }
      setStage("complete");
    } catch (caught) { setStage("failed"); setError(caught instanceof Error ? caught.message : "The backend could not process this document."); }
  }

  const activeFile = files[activeBatch] ?? files[0] ?? null;
  function reset() { setFiles([]); setResult(null); setBatchResults([]); setError(null); setStage("idle"); if (inputRef.current) inputRef.current.value = ""; }
  function selectBatch(index: number) { setActiveBatch(index); setResult(batchResults[index]); }

  return (
    <div className={darkMode ? "dark" : ""}>
      <div className="shell paper-grid min-h-screen">
        <header className="border-b border-[var(--line)] bg-[var(--surface)]/90 backdrop-blur"><div className="mx-auto flex max-w-[1480px] items-center justify-between px-5 py-4 lg:px-8"><div className="flex items-center gap-3"><div className="brand-mark flex h-10 w-10 items-center justify-center rounded-xl"><Layers3 size={21} /></div><div><div className="text-sm font-black tracking-[.08em]">SLEDGE</div><div className="text-[10px] font-bold uppercase tracking-[.16em] text-[var(--muted)]">Change Order Intelligence</div></div></div><div className="flex items-center gap-2"><span className="hidden text-xs font-semibold text-[var(--muted)] sm:inline">Evidence-grounded workspace</span><button type="button" onClick={() => setDarkMode(!darkMode)} aria-label="Toggle dark mode" className="muted-button rounded-lg p-2">{darkMode ? <Sun size={17} /> : <Moon size={17} />}</button></div></div></header>
        <main className="mx-auto max-w-[1480px] px-5 py-8 lg:px-8 lg:py-12">
          <div className="grid gap-8 lg:grid-cols-[260px_minmax(0,1fr)]">
            <aside className="space-y-5"><div><div className="eyebrow">DOCUMENT INTELLIGENCE</div><h1 className="mt-2 text-3xl font-black tracking-[-.04em] sm:text-4xl">SLEDGE<br /><span className="text-[var(--accent)]">CHANGE ORDER</span><br />INTELLIGENCE</h1><p className="mt-4 text-sm leading-6 text-[var(--muted)]">Evidence-grounded construction document extraction for fast, auditable review.</p></div><div className="panel rounded-2xl p-4"><div className="flex items-center gap-2 text-xs font-bold uppercase tracking-wider"><ShieldCheck size={16} className="text-emerald-600" /> Local-first processing</div><p className="mt-2 text-xs leading-5 text-[var(--muted)]">Documents stay in the local backend unless optional AI assistance is explicitly enabled.</p></div><div className="space-y-2 text-xs font-semibold text-[var(--muted)]"><div className="flex items-center gap-2"><CheckCircle2 size={15} className="text-emerald-600" /> Exact source evidence</div><div className="flex items-center gap-2"><CheckCircle2 size={15} className="text-emerald-600" /> Decimal-safe JSON</div><div className="flex items-center gap-2"><CheckCircle2 size={15} className="text-emerald-600" /> OCR uncertainty disclosed</div></div></aside>
            <div className="min-w-0 space-y-6">
              <section className="panel rounded-2xl p-5 lg:p-7"><div className="flex flex-wrap items-start justify-between gap-4"><div><div className="eyebrow">EXTRACTION WORKSPACE</div><h2 className="mt-1 text-2xl font-black tracking-[-.03em]">Review a change order</h2><p className="mt-2 max-w-2xl text-sm leading-6 text-[var(--muted)]">Upload a document, select the local processing policy, then inspect structured fields alongside the source and its exact evidence.</p></div><StatusChip stage={stage} /></div><div className={`dropzone mt-6 rounded-2xl p-7 text-center ${dragging ? "active" : ""}`} onDragOver={(event) => { event.preventDefault(); setDragging(true); }} onDragLeave={() => setDragging(false)} onDrop={(event) => { event.preventDefault(); setDragging(false); acceptFiles(Array.from(event.dataTransfer.files)); }}><UploadCloud className="mx-auto text-[var(--accent)]" size={30} /><h3 className="mt-3 text-sm font-bold">Drop documents here</h3><p className="mt-1 text-xs text-[var(--muted)]">PDF, TXT, PNG or JPEG · up to {bytes(capabilities.max_file_bytes)} per file</p><input ref={inputRef} type="file" multiple accept=".pdf,.txt,.png,.jpg,.jpeg" className="sr-only" onChange={(event) => acceptFiles(Array.from(event.target.files ?? []))} /><button type="button" onClick={() => inputRef.current?.click()} className="accent-button mt-5 inline-flex items-center gap-2 rounded-lg px-4 py-2.5 text-sm font-bold"><FolderOpen size={16} /> Choose files</button></div>{files.length > 0 && <div className="mt-4 space-y-2">{files.map((file, index) => <div key={`${file.name}-${file.lastModified}`} className="flex items-center justify-between rounded-xl border border-[var(--line)] px-4 py-3"><div className="flex min-w-0 items-center gap-3"><FileText size={17} className="shrink-0 text-[var(--accent)]" /><div className="min-w-0"><div className="truncate text-sm font-semibold">{file.name}</div><div className="text-xs text-[var(--muted)]">{bytes(file.size)} · {file.type || "file"}{batchResults[index] && ` · ${batchResults[index].status}`}</div></div></div>{batchResults[index] && <button type="button" onClick={() => selectBatch(index)} className="text-xs font-bold text-[var(--accent-deep)]">Review</button>}</div>)}</div>}</section>
              <section className="panel rounded-2xl p-5 lg:p-7"><div className="flex items-center gap-3"><Sparkles className="text-[var(--accent)]" size={20} /><div><div className="eyebrow">PROCESSING POLICY</div><h2 className="mt-1 text-lg font-bold">Extraction settings</h2></div></div><div className="mt-5 grid gap-4 md:grid-cols-3"><label className="rounded-xl border border-[var(--line)] p-4"><span className="block text-xs font-bold uppercase tracking-wider">OCR</span><select value={options.ocr} onChange={(event) => setOptions({ ...options, ocr: event.target.value as ExtractionOptions["ocr"] })} className="mt-3 w-full rounded-lg border border-[var(--line)] bg-[var(--surface)] px-2 py-2 text-sm"><option value="auto">Automatic fallback</option><option value="off">Disabled</option><option value="force" disabled={!capabilities.ocr.available}>Force OCR{!capabilities.ocr.available ? " · unavailable" : ""}</option></select><span className="mt-2 block text-[11px] leading-5 text-[var(--muted)]">{capabilities.ocr.available ? `Tesseract ${capabilities.ocr.version ?? "ready"}` : capabilities.ocr.message}</span></label><label className={`rounded-xl border border-[var(--line)] p-4 ${!capabilities.llm.available ? "opacity-65" : ""}`}><span className="block text-xs font-bold uppercase tracking-wider">Optional AI</span><span className="mt-3 flex items-center gap-3"><input type="checkbox" checked={options.llm} disabled={!capabilities.llm.available} onChange={(event) => setOptions({ ...options, llm: event.target.checked })} className="h-4 w-4 accent-[var(--accent)]" /><span className="text-sm font-semibold">Provider assistance</span></span><span className="mt-2 block text-[11px] leading-5 text-[var(--muted)]">{capabilities.llm.message}</span></label><label className="rounded-xl border border-[var(--line)] p-4"><span className="block text-xs font-bold uppercase tracking-wider">Ambiguous dates</span><select value={options.date_order} onChange={(event) => setOptions({ ...options, date_order: event.target.value as ExtractionOptions["date_order"] })} className="mt-3 w-full rounded-lg border border-[var(--line)] bg-[var(--surface)] px-2 py-2 text-sm"><option value="reject">Flag for review</option><option value="mdy">Month / day / year</option><option value="dmy">Day / month / year</option></select><span className="mt-2 block text-[11px] leading-5 text-[var(--muted)]">The original value and evidence are preserved.</span></label></div><label className="mt-4 flex items-center gap-3 text-sm text-[var(--muted)]"><input type="checkbox" checked={showRaw} onChange={(event) => setShowRaw(event.target.checked)} className="h-4 w-4 accent-[var(--accent)]" /> Show raw extracted text in the review below</label><div className="mt-5 flex flex-wrap gap-2"><button type="button" onClick={() => void runExtraction()} disabled={!files.length || stage === "processing" || stage === "uploading"} className="accent-button inline-flex items-center gap-2 rounded-lg px-5 py-3 text-sm font-bold disabled:cursor-not-allowed disabled:opacity-50"><Play size={16} /> {files.length > 1 ? `Process ${files.length} documents` : "Extract change order"}</button><button type="button" onClick={reset} className="muted-button inline-flex items-center gap-2 rounded-lg px-4 py-3 text-sm font-bold"><RotateCcw size={16} /> Reset</button></div>{stage === "processing" && <div className="mt-4 flex items-center gap-2 text-xs font-semibold text-[var(--muted)]"><span className="h-2 w-2 animate-pulse rounded-full bg-[var(--accent)]" /> Processing through the local reader, extractor and validator. Stage detail is reported only when the backend completes.</div>}</section>
              <section className="panel rounded-2xl p-5 lg:p-7"><div className="flex items-center gap-3"><PackageCheck className="text-[var(--accent)]" size={20} /><div><div className="eyebrow">DEMONSTRATION DOCUMENTS</div><h2 className="mt-1 text-lg font-bold">Start with an included fixture</h2></div></div><p className="mt-2 text-sm text-[var(--muted)]">These are clearly labeled synthetic fixtures from the repository, not customer documents or public benchmarks.</p><div className="mt-4 grid gap-3 sm:grid-cols-2"><button type="button" onClick={() => void loadExample("/examples/01_clean.txt", "01_clean.txt")} className="muted-button flex items-center justify-between rounded-xl p-4 text-left"><span><span className="block text-sm font-bold">Clean change order</span><span className="mt-1 block text-xs text-[var(--muted)]">Synthetic · complete fields</span></span><FileText size={18} className="text-[var(--accent)]" /></button><button type="button" onClick={() => void loadExample("/examples/06_conflict.txt", "06_conflict.txt")} className="muted-button flex items-center justify-between rounded-xl p-4 text-left"><span><span className="block text-sm font-bold">Conflicting amounts</span><span className="mt-1 block text-xs text-[var(--muted)]">Synthetic · review signal</span></span><AlertTriangle size={18} className="text-[var(--accent)]" /></button></div></section>
              {error && <div role="alert" className="rounded-xl border border-rose-200 bg-rose-50 p-4 text-sm text-rose-800"><XCircle className="mr-2 inline" size={17} />{error}</div>}
              {batchResults.length > 1 && <div className="panel rounded-xl p-4"><div className="mb-3 flex items-center gap-2 text-xs font-bold uppercase tracking-wider text-[var(--muted)]"><Layers3 size={15} /> Batch results</div><div className="flex flex-wrap gap-2">{batchResults.map((item, index) => <button type="button" key={item.source.identifier} onClick={() => selectBatch(index)} className={`rounded-lg border px-3 py-2 text-xs font-bold ${index === activeBatch ? "border-[var(--accent)] text-[var(--accent-deep)]" : "border-[var(--line)]"}`}>{item.source.identifier} · {item.status}</button>)}</div></div>}
              {result && <ResultPanel result={result} file={activeFile} />}
              {result && showRaw && <section className="panel rounded-2xl p-5"><div className="flex items-center gap-3"><FileText size={19} className="text-[var(--accent)]" /><div><div className="eyebrow">RAW EXTRACTED TEXT</div><h2 className="mt-1 text-lg font-bold">Backend source blocks</h2></div></div><div className="mt-4 space-y-4">{result.source.pages.map((page) => <div key={page.page ?? "text"}><div className="mb-2 text-xs font-bold uppercase tracking-wider text-[var(--muted)]">{page.page ? `Page ${page.page}` : "Text source"} · {page.text_origin}{page.ocr_quality !== null ? ` · OCR ${Math.round(page.ocr_quality * 100)}%` : ""}</div><pre className="mono max-h-64 overflow-auto whitespace-pre-wrap rounded-xl bg-slate-950 p-4 text-xs leading-5 text-slate-100">{page.raw_text}</pre></div>)}</div></section>}
            </div>
          </div>
        </main>
        <footer className="border-t border-[var(--line)] bg-[var(--surface)]/75"><div className="mx-auto flex max-w-[1480px] flex-wrap items-center justify-between gap-3 px-5 py-5 text-xs text-[var(--muted)] lg:px-8"><span>Local deterministic extraction · evidence before confidence</span><span>Pipeline v0.1.0 · API-backed workspace</span></div></footer>
      </div>
    </div>
  );
}
