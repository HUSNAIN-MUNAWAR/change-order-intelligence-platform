"""Local recruiter demo. Run: python -m streamlit run streamlit_app.py"""

from pathlib import Path

import streamlit as st

from changeorder.demo import (
    FIELD_GROUPS,
    HIGH_CONFIDENCE,
    MEDIUM_CONFIDENCE,
    DemoInputError,
    DocumentInput,
    confidence_band,
    display_value,
    input_signature,
    json_payload,
    llm_configured,
    preview_pdf,
    process_document,
    summary,
    validate_inputs,
    zip_payload,
)
from changeorder.ocr import ocr_status
from changeorder.pipeline import PipelineOptions
from changeorder.readers import ReaderOptions
from changeorder.schemas import ChangeOrder, ExtractedField, ExtractionResult

ROOT = Path(__file__).resolve().parent
EXAMPLES = {
    "Digital PDF - Harbor Warehouse": "examples/documents/03_digital.pdf",
    "Scanned PDF - real local OCR": "examples/ocr/13_scanned.pdf",
    "Noisy scan - image OCR": "examples/ocr/15_noisy.png",
    "Clean text - Riverside Medical Center": "examples/documents/01_clean.txt",
    "Ambiguous dates and revisions": "examples/documents/11_ambiguous_revision.txt",
    "Conflicting change amounts": "examples/documents/06_conflict.txt",
}
CSS = """
<style>
.block-container {max-width: 1500px; padding-top: 3.5rem; padding-bottom: 3rem;}
h1 {letter-spacing: -.045em; font-weight: 750 !important; font-size: 2.15rem !important;}
h2, h3 {letter-spacing: -.02em;}
[data-testid="stMetric"] {background: #fff; border: 1px solid #e4e9f2; border-radius: 12px; padding: .8rem 1rem;}
[data-testid="stMetricValue"] {font-size: 1.55rem;}
[data-testid="stSidebar"] {border-right: 1px solid #e4e9f2;}
[data-testid="stImage"] img {border: 1px solid #dde3ee; border-radius: 8px;}
.eyebrow {color: #2563eb; font-size: .75rem; font-weight: 700; letter-spacing: .13em; margin-bottom: .25rem;}
.subtitle {color: #64748b; font-size: 1.05rem; margin-top: -.7rem; margin-bottom: 1.6rem;}
pre {white-space: pre-wrap; overflow-wrap: anywhere;}
</style>
"""


@st.cache_data(ttl=60, show_spinner=False)
def engine_status():
    # This cache holds only public engine availability, never uploaded document data.
    return ocr_status()


def show_evidence(field: ExtractedField):
    for item in field.evidence or []:
        location = f"Page {item.page}" if item.page is not None else "Text source"
        st.caption(f"{location} · lines {item.line_start}-{item.line_end} · {item.text_origin}")
        st.text(item.source)
        st.code(item.text, language=None)
    for alternative in field.alternatives:
        st.caption("Conflicting alternative")
        st.text(display_value(alternative.value))
        for item in alternative.evidence:
            st.caption(f"Page {item.page}" if item.page is not None else "Text source")
            st.code(item.text, language=None)
    if field.signals:
        st.caption("Confidence signals")
        st.text("\n".join(field.signals))


def show_field(name: str, field: ExtractedField, prefix: str = ""):
    label = name.replace("_", " ").capitalize()
    with st.container(border=True):
        value_col, support_col = st.columns([0.72, 0.28])
        with value_col:
            st.markdown(f"**{label}**")
            if name == "line_items" and field.value:
                st.text(f"{len(field.value)} cost items")
            else:
                st.text(display_value(field.value))
        with support_col:
            st.caption(
                f"{confidence_band(field.confidence, field.value is None)} · {field.confidence:.0%}"
            )
            st.badge(
                field.validation.upper(),
                color={
                    "valid": "green",
                    "warning": "orange",
                    "conflict": "red",
                    "invalid": "red",
                    "missing": "gray",
                }[field.validation],
            )
        if field.evidence or field.validation == "invalid":
            with st.expander(f"Evidence · {prefix}{label}"):
                show_evidence(field)
                if field.validation == "invalid":
                    st.caption(
                        "The labeled value could not be validated. See the validation summary for details."
                    )
        if name == "line_items" and field.value:
            for index, item in enumerate(field.value, 1):
                with st.expander(f"Cost item {index} · values and evidence"):
                    for leaf in ("description", "quantity", "unit", "unit_price", "amount"):
                        show_field(leaf, getattr(item, leaf), f"Item {index} ")


def show_preview(document: DocumentInput, result: ExtractionResult):
    st.subheader("Source document")
    st.text(document.safe_name)
    st.caption(f"{result.source.media_type} · {len(result.source.pages)} page(s) / source block(s)")
    suffix = Path(document.safe_name).suffix.lower()
    try:
        if suffix == ".pdf":
            page = st.selectbox(
                "Preview page",
                list(range(1, max(1, len(result.source.pages)) + 1)),
                key="preview_page",
            )
            cache_key = (result.source.sha256, page)
            if st.session_state.get("preview_key") != cache_key:
                png, _ = preview_pdf(document, page - 1)
                st.session_state.preview_png = png
                st.session_state.preview_key = cache_key
            st.image(st.session_state.preview_png, width="stretch")
            st.caption(
                "Original page preview. Evidence quotes refer to text spans; no bounding-box highlights are inferred."
            )
        elif suffix in {".png", ".jpg", ".jpeg"}:
            if result.source.pages:
                st.image(document.payload, width="stretch")
            else:
                st.info("Image preview unavailable. See the input errors.")
        else:
            text = result.source.pages[0].raw_text if result.source.pages else "No readable text."
            st.code(text, language=None)
    except DemoInputError as exc:
        st.info(str(exc))


def show_result(document: DocumentInput, result: ExtractionResult, show_raw: bool):
    counts = summary(result)
    if result.status == "failed":
        st.error("Extraction failed. The document could not provide usable change-order facts.")
    elif result.status == "partial":
        st.warning("Extraction completed with items requiring review.")
    else:
        st.success(
            "Extraction complete. Structured values and source evidence are ready to review."
        )
    metrics = st.columns(6)
    for column, label, value in zip(
        metrics,
        (
            "Extracted fields",
            "Missing fields",
            "Review fields",
            "Conflicts",
            "OCR pages",
            "Processing time",
        ),
        (
            counts["extracted"],
            counts["missing"],
            counts["review"],
            counts["conflicts"],
            counts["ocr_pages"],
            f"{result.processing_ms / 1000:.2f} s",
        ),
        strict=True,
    ):
        column.metric(label, value)
    st.caption(
        f"Counts cover {len(ChangeOrder.model_fields)} top-level fields. High >= {HIGH_CONFIDENCE:.0%}, medium >= {MEDIUM_CONFIDENCE:.0%}, low < {MEDIUM_CONFIDENCE:.0%}. Confidence is a heuristic support indicator, not a calibrated probability."
    )
    if result.issues:
        with st.expander(
            f"Validation summary · {len(result.issues)} message(s)",
            expanded=result.status != "success",
        ):
            for issue in result.issues:
                st.caption(
                    f"{issue.severity.upper()} · {issue.code}"
                    + (f" · {issue.field}" if issue.field else "")
                )
                st.text(issue.message)
                if issue.evidence:
                    st.code(issue.evidence.text, language=None)
    review_tab, json_tab = st.tabs(["Document Review", "JSON Output"])
    with review_tab:
        source_column, fields_column = st.columns([0.95, 1.05], gap="large")
        with source_column:
            show_preview(document, result)
        with fields_column:
            st.subheader("Extracted information")
            group = st.selectbox("Field group", list(FIELD_GROUPS), key="field_group")
            for name in FIELD_GROUPS[group]:
                show_field(name, getattr(result.data, name))
    with json_tab:
        payload = json_payload(result)
        st.download_button(
            "Download JSON",
            data=payload,
            file_name=f"{document.safe_name}.json",
            mime="application/json",
            on_click="ignore",
            type="primary",
        )
        st.caption(
            "Copy JSON using the copy button in the upper-right corner of the code block. This is the same validated response and exact Decimal JSON used by the CLI."
        )
        st.code(payload.decode("utf-8"), language="json")
    if show_raw:
        with st.expander("Raw extracted text", expanded=True):
            for page in result.source.pages:
                st.caption(
                    f"Page {page.page or 'text'} · {page.text_origin}"
                    + (
                        f" · Tesseract mean word score {page.ocr_quality:.1%}"
                        if page.ocr_quality is not None
                        else ""
                    )
                )
                st.code(page.raw_text, language=None)
            st.caption(
                "Word scores describe OCR recognition; field confidence also considers evidence, parsing, conflicts and validation."
            )


def main():
    st.set_page_config(page_title="Change Order Intelligence", page_icon="📄", layout="wide")
    st.markdown(CSS, unsafe_allow_html=True)
    st.markdown('<div class="eyebrow">LOCAL DOCUMENT WORKSPACE</div>', unsafe_allow_html=True)
    st.title("CHANGE ORDER INTELLIGENCE")
    st.markdown(
        '<div class="subtitle">Document Extraction &amp; Validation</div>', unsafe_allow_html=True
    )
    engine = engine_status()
    with st.sidebar:
        st.subheader("Extraction settings")
        st.caption("Automatic extraction uses the existing local pipeline.")
        use_ocr = st.toggle("Enable OCR for scanned pages", value=True, key="use_ocr")
        if engine.available:
            st.success("Local OCR ready")
            st.caption(engine.version)
            st.caption("Languages: " + ", ".join(engine.languages))
        else:
            st.warning(engine.message)
            st.caption("Native PDF and text extraction remain available.")
        configured = llm_configured()
        use_llm = st.toggle(
            "Optional LLM assistance", disabled=not configured, value=False, key="use_llm"
        )
        if not configured:
            st.caption(
                "LLM assistance is unavailable until the optional SDK, model and API credentials are configured in the server environment."
            )
        else:
            st.caption("Enabling assistance sends document text to your configured provider.")
        show_raw = st.checkbox("Display raw extracted text", key="show_raw")
        st.divider()
        st.caption(
            "Documents stay local unless you enable LLM assistance. No account or database is required."
        )
        if st.button("Clear session results"):
            for key in ("run", "preview_png", "preview_key"):
                st.session_state.pop(key, None)
    with st.container(border=True):
        st.subheader("Choose a document")
        source = st.radio(
            "Document source",
            ["Synthetic examples", "Upload documents"],
            horizontal=True,
            key="input_source",
        )
        documents = []
        if source == "Synthetic examples":
            selected = st.selectbox("Synthetic demo example", list(EXAMPLES), key="example")
            path = ROOT / EXAMPLES[selected]
            documents = [DocumentInput(path.name, path.read_bytes())]
            st.caption(
                "Included examples are synthetic construction documents. None were supplied by Sledge."
            )
        else:
            uploads = st.file_uploader(
                "Upload PDF, TXT, PNG or JPEG",
                type=["pdf", "txt", "png", "jpg", "jpeg"],
                accept_multiple_files=True,
                key="uploads",
            )
            documents = [DocumentInput(upload.name, upload.getvalue()) for upload in uploads]
            st.caption(
                "20 MiB per file · up to 8 files / 40 MiB combined. Each file is processed independently."
            )
        options = PipelineOptions(
            reader=ReaderOptions(ocr="auto" if use_ocr else "off"), llm=bool(configured and use_llm)
        )
        if documents:
            st.text(
                " · ".join(
                    f"{doc.safe_name} ({len(doc.payload) / 1024:.1f} KiB)" for doc in documents
                )
            )
        try:
            validate_inputs(documents)
            valid_input = True
        except DemoInputError as exc:
            valid_input = False
            if documents:
                st.warning(str(exc))
        signature = input_signature(documents, options)
        if st.session_state.get("run", {}).get("signature") != signature:
            st.session_state.pop("run", None)
        if st.button(
            "Extract Change Order", type="primary", disabled=not valid_input, key="extract"
        ):
            records = []
            with st.spinner("Reading document, extracting fields and validating evidence..."):
                for document in documents:
                    try:
                        result = process_document(document, options)
                        records.append((document, result))
                    except (OSError, DemoInputError):
                        st.error(
                            "The document could not be processed. Check the file type and size, then try again."
                        )
            if records:
                st.session_state.run = {
                    "signature": signature,
                    "records": records,
                    "zip": zip_payload([result for _, result in records]),
                }
    run = st.session_state.get("run")
    if run:
        records = run["records"]
        if len(records) > 1:
            st.download_button(
                "Download all JSON results (ZIP)",
                data=run["zip"],
                file_name="change-order-results.zip",
                mime="application/zip",
                on_click="ignore",
            )
            index = st.selectbox(
                "Document result",
                list(range(len(records))),
                key="document_result",
                format_func=lambda i: (
                    f"{i + 1}. {records[i][0].safe_name} - {records[i][1].status}"
                ),
            )
        else:
            index = 0
        show_result(*records[index], show_raw)
    else:
        st.info(
            "Choose an example or upload a document, then select Extract Change Order. Results include values, confidence, validation and source evidence."
        )


if __name__ == "__main__":
    main()
