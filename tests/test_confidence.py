from changeorder.confidence import score
from changeorder.extraction import Candidate
from changeorder.pipeline import extract
from changeorder.provenance import evidence, lines
from changeorder.readers import read_text


def test_confidence_decreases_for_conflict_and_ocr():
    source = read_text("CO Number: 001\n")
    page = source.pages[0]
    ev = evidence(source, page, lines(page)[0])
    regular = Candidate("change_order_number", "001", ev)
    assert score(regular)[0] > score(regular, conflict=True)[0]
    ocr = Candidate(
        "change_order_number", "001", ev.model_copy(update={"text_origin": "ocr"}), ocr_quality=0.4
    )
    assert score(ocr)[0] < score(regular)[0]
    assert score(regular, independent_methods=2)[0] > score(regular)[0]


def test_repeated_same_method_does_not_inflate_confidence(offline):
    once = extract(text="CHANGE ORDER\nCO Number: 001\nProject: A", options=offline)
    repeated = extract(
        text="CHANGE ORDER\nCO Number: 001\nCO Number: 001\nProject: A", options=offline
    )
    assert once.data.change_order_number.confidence == repeated.data.change_order_number.confidence


def test_missing_zero_and_noise_reduction(documents, offline):
    clean = extract(documents / "01_clean.txt", options=offline)
    noisy = extract(documents / "10_ocr_noise.txt", options=offline)
    assert noisy.data.change_order_number.confidence < clean.data.change_order_number.confidence
    assert noisy.status == "partial"
    missing = noisy.data.approval_date
    assert missing.value is None and missing.confidence == 0 and missing.evidence is None
