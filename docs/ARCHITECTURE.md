# Architecture

The browser is a presentation layer over a thin FastAPI transport. The Python package remains the single source of truth for document ingestion, OCR, extraction, validation, confidence, provenance and serialization.

## 1. High-level system architecture

```mermaid
flowchart LR
    U[User] --> F[Next.js App Router frontend]
    F --> A[FastAPI /api/v1]
    A --> P[changeorder.pipeline.extract]
    P --> R[readers.py]
    R --> N[PyMuPDF native reader]
    R --> O[Tesseract OCR when needed]
    P --> E[extraction.py candidates]
    P --> V[Pydantic validation and reconciliation]
    V --> C[confidence.py]
    V --> Q[provenance.py evidence]
    P -. opt-in .-> L[Optional LLM adapter]
    A --> J[Validated ExtractionResult JSON]
    J --> F
```

The API does not create a competing field schema. It validates transport options, invokes the existing pipeline and returns the package response.

## 2. Component dependencies

```mermaid
flowchart TD
    Main[backend.api.main] --> Services[backend.api.services]
    Main --> Caps[backend.api.capabilities]
    Services --> Pipeline[changeorder.pipeline]
    Pipeline --> Readers[changeorder.readers]
    Pipeline --> Extraction[changeorder.extraction]
    Pipeline --> LLM[changeorder.llm_extractor]
    Extraction --> Normalization[changeorder.normalization]
    Extraction --> Provenance[changeorder.provenance]
    Pipeline --> Validation[changeorder.validation]
    Validation --> Confidence[changeorder.confidence]
    Pipeline --> Schemas[changeorder.schemas]
    Pipeline --> JSON[changeorder.jsonio]
    Streamlit[streamlit_app.py] --> Demo[changeorder.demo]
    Demo --> Pipeline
```

## 3. Extraction request sequence

```mermaid
sequenceDiagram
    actor User
    participant UI as Next.js frontend
    participant API as FastAPI
    participant Engine as Python pipeline
    participant Reader as PDF/image/text reader
    participant OCR as Tesseract
    User->>UI: Select fixture or upload file
    UI->>API: POST multipart /api/v1/extract
    API->>API: Validate size, suffix, MIME and signature
    API->>Engine: extract(temp_path, PipelineOptions)
    Engine->>Reader: read_file()
    alt Native text is sufficient
        Reader-->>Engine: PageText(native)
    else Page is sparse/image-only
        Reader->>OCR: Render page and recognize locally
        OCR-->>Reader: OCR text and word quality
        Reader-->>Engine: PageText(ocr)
    end
    Engine->>Engine: Generate candidates and reconcile conflicts
    Engine->>Engine: Validate types, consistency, confidence and evidence
    Engine-->>API: ExtractionResult
    API-->>UI: Exact Decimal-safe JSON response
    UI-->>User: Fields, warnings, evidence, preview and download
```

The LLM branch is opt-in and evidence-gated; a provider failure falls back to deterministic candidates.

## 4. Document data flow

```mermaid
flowchart LR
    Bytes[Uploaded bytes] --> Bounds[Byte and content bounds]
    Bounds --> Pages[PageText raw/cleaned blocks]
    Pages --> Candidates[Label/title/table candidates]
    Candidates --> Parsed[Typed values: Decimal/date/identifier]
    Parsed --> Reconciled[Chosen value + alternatives]
    Reconciled --> Validated[ExtractedField wrappers]
    Validated --> Audited[Evidence + confidence + issues]
    Audited --> Result[ExtractionResult JSON]
```

Source spans are created from the actual page-local text; coordinates are not invented.

## 5. Processing states

```mermaid
stateDiagram-v2
    [*] --> Uploaded
    Uploaded --> Reading
    Reading --> OCRFallback: sparse/native text unavailable
    Reading --> Extracting: usable text
    OCRFallback --> Extracting: OCR text or recoverable warning
    Reading --> Failed: unsupported/corrupt/limit error
    OCRFallback --> Failed: OCR unavailable and no usable text
    Extracting --> Validating
    Validating --> Completed: no warnings/fatal issues
    Validating --> PartialSuccess: warnings/conflicts/missing review fields
    Validating --> Failed: no actionable change-order facts
```

The API currently reports the completed `ExtractionResult` status rather than fabricated percentage progress. The frontend shows only upload, processing, complete and failed transport states.

## 6. Core models and module relationships

```mermaid
classDiagram
    class ExtractionResult {
      status
      source
      data
      issues
      missing_fields
      processing_ms
    }
    class Source {
      identifier
      sha256
      pages
    }
    class PageText {
      page
      raw_text
      text_origin
      ocr_quality
    }
    class ChangeOrder
    class ExtractedField {
      value
      confidence
      evidence
      method
      validation
      alternatives
    }
    class Evidence {
      source
      page
      line_span
      char_span
      text
    }
    ExtractionResult *-- Source
    ExtractionResult *-- ChangeOrder
    Source *-- PageText
    ChangeOrder *-- ExtractedField
    ExtractedField *-- Evidence
```

The implementation types are Pydantic models in `src/changeorder/schemas.py`; the diagram shows the important relationships without duplicating every field.

## 7. Failure and fallback flow

```mermaid
flowchart TD
    Input[Input] --> Format{Supported and within limits?}
    Format -- no --> Error[Structured 4xx error or failed result]
    Format -- yes --> Native{Usable native text?}
    Native -- yes --> Extract[Deterministic candidate extraction]
    Native -- no --> OCR{OCR available/enabled?}
    OCR -- no --> Partial[Recoverable OCR warning or failed result]
    OCR -- yes --> ExtractOCR[OCR candidates with quality penalty]
    ExtractOCR --> Extract
    Extract --> Valid{Typed and evidence-backed?}
    Valid -- no --> Partial
    Valid -- yes --> Optional{LLM explicitly enabled?}
    Optional -- no --> JSON[Validated JSON]
    Optional -- yes --> Provider{Provider response valid and quoted?}
    Provider -- no --> JSONFallback[Deterministic JSON + recoverable LLM issue]
    Provider -- yes --> Merge[Evidence-gated candidate merge]
    Merge --> JSON
    JSONFallback --> Frontend[Frontend review]
    JSON --> Frontend
```

All failure paths preserve the distinction between unsupported input, recoverable processing warnings and fatal absence of actionable change-order facts.
