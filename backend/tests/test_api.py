import json
from pathlib import Path

from fastapi.testclient import TestClient

from backend.api.main import app
from changeorder.jsonio import dumps
from changeorder.pipeline import extract

ROOT = Path(__file__).resolve().parents[2]


def client():
    return TestClient(app)


def test_health_and_capabilities_are_typed():
    with client() as http:
        health = http.get("/api/v1/health")
        capabilities = http.get("/api/v1/capabilities")
    assert health.status_code == 200
    assert health.json()["status"] == "ok"
    assert capabilities.status_code == 200
    assert ".pdf" in capabilities.json()["supported_formats"]
    assert "ocr" in capabilities.json()


def test_extract_matches_canonical_pipeline_and_preserves_decimal_json():
    path = ROOT / "examples" / "documents" / "03_digital.pdf"
    expected = extract(path)
    with client() as http:
        response = http.post(
            "/api/v1/extract",
            files={"file": (path.name, path.read_bytes(), "application/pdf")},
            data={"ocr": "off", "llm": "false", "date_order": "reject"},
        )
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/json")
    actual = response.json()
    expected_payload = json.loads(dumps(expected))
    # Processing time is measured independently at the API boundary.
    actual.pop("processing_ms")
    expected_payload.pop("processing_ms")
    assert actual == expected_payload
    assert response.json()["data"]["total_change_amount"]["value"] == 6400


def test_batch_isolates_supported_and_unsupported_files():
    good = ROOT / "examples" / "documents" / "01_clean.txt"
    bad = ROOT / "examples" / "documents" / "12_unrelated.txt"
    with client() as http:
        response = http.post(
            "/api/v1/batch",
            files=[
                ("files", (good.name, good.read_bytes(), "text/plain")),
                ("files", (bad.name, bad.read_bytes(), "text/plain")),
            ],
            data={"ocr": "off", "llm": "false", "date_order": "reject"},
        )
    assert response.status_code == 200
    payload = response.json()
    assert payload["processed"] == 2
    assert [item["status"] for item in payload["results"]] == ["success", "failed"]


def test_rejects_mime_mismatch_and_path_traversal_filename():
    with client() as http:
        response = http.post(
            "/api/v1/extract",
            files={"file": ("../evil.pdf", b"not a pdf", "application/pdf")},
        )
    assert response.status_code == 415
    assert response.json()["code"] == "MIME_MISMATCH"


def test_rejects_unsupported_extension():
    with client() as http:
        response = http.post(
            "/api/v1/extract",
            files={"file": ("notes.exe", b"MZ", "application/octet-stream")},
        )
    assert response.status_code == 415
    assert response.json()["code"] == "UNSUPPORTED_FORMAT"
