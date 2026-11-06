"""Transparent heuristic support scores; these are not calibrated probabilities."""

from .extraction import Candidate


def score(
    candidate: Candidate, *, conflict: bool = False, independent_methods: int = 1
) -> tuple[float, list[str]]:
    value = candidate.strength
    signals = [f"{candidate.method}_base={value:.2f}", "source_evidence_verified"]
    if candidate.field.endswith("amount") or candidate.field.endswith("date"):
        value += 0.03
        signals.append("typed_parse=+0.03")
    if independent_methods > 1:
        value += 0.03
        signals.append("independent_method_agreement=+0.03")
    if candidate.evidence.text_origin == "ocr":
        penalty = 0.18 + 0.20 * (
            1 - (candidate.ocr_quality if candidate.ocr_quality is not None else 0.5)
        )
        value -= penalty
        signals.append(f"ocr_penalty=-{penalty:.2f}")
    for note in candidate.notes:
        penalty = 0.15 if note == "ocr_label_repair" else 0.08
        value -= penalty
        signals.append(f"{note}=-{penalty:.2f}")
    if conflict:
        value = min(0.55, value - 0.35)
        signals.append("competing_values=-0.35; cap=0.55")
    return round(max(0, min(0.98, value)), 3), signals
