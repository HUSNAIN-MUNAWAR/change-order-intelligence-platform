import json
from types import SimpleNamespace

import httpx
import pytest

from changeorder.llm_extractor import (
    LLMError,
    OpenAITransport,
    StructuredLLMExtractor,
    TransientLLMError,
)
from changeorder.pipeline import extract
from changeorder.readers import read_text


def response(field, raw, quote, page=None, confidence=1.0):
    return json.dumps(
        {
            "fields": [
                {
                    "field": field,
                    "raw_value": raw,
                    "quote": quote,
                    "page": page,
                    "model_confidence": confidence,
                }
            ]
        }
    )


def test_llm_supported_verbatim_description_and_confidence(offline):
    text = "CHANGE ORDER\nCO Number: 1\nProject: A\nThe requested work is to add a bypass valve."
    llm = StructuredLLMExtractor(
        lambda payload: response(
            "description", "add a bypass valve", "The requested work is to add a bypass valve."
        )
    )
    result = extract(text=text, options=offline, llm_extractor=llm)
    assert result.data.description.value == "add a bypass valve"
    assert result.data.description.method == "llm"
    assert result.data.description.confidence == 0.65
    assert result.llm_used


def test_llm_can_verify_semantic_amount_label_outside_deterministic_pattern():
    source = read_text(
        "CHANGE ORDER\nCO Number: 1\nProject: A\nPROPOSED CHANGE VALUE ........ USD 500"
    )
    llm = StructuredLLMExtractor(
        lambda payload: response(
            "proposed_amount", "USD 500", "PROPOSED CHANGE VALUE ........ USD 500"
        )
    )
    candidates, issues = llm.extract(source)
    assert not issues
    assert candidates[0].field == "proposed_amount" and candidates[0].value == 500


@pytest.mark.parametrize(
    ("field", "raw", "quote", "page"),
    [
        ("contractor", "Invented Company", "Project: A", None),
        ("total_change_amount", "9000", "Requested Amount: USD 9000", None),
        ("approval_status", "approved", "Approval Status: Not approved", None),
        ("total_change_amount", "100", "Invoice: USD 100", None),
        ("project_name", "A", "Project: A", 99),
        ("description", "Extra work", "This quote does not exist", None),
    ],
)
def test_unsupported_or_miscontextualized_llm_values_rejected(field, raw, quote, page):
    source = read_text(
        "CHANGE ORDER\nProject: A\nRequested Amount: USD 9000\nApproval Status: Not approved\nInvoice: USD 100"
    )
    llm = StructuredLLMExtractor(lambda payload: response(field, raw, quote, page))
    candidates, issues = llm.extract(source)
    assert not candidates
    assert issues[0].code == "LLM_UNSUPPORTED_VALUE"


def test_llm_cannot_change_strong_deterministic_value(offline):
    text = "CHANGE ORDER\nCO Number: 1\nProject: A\nContractor: Main Build\nA separate note mentions Backup Build."
    llm = StructuredLLMExtractor(
        lambda payload: response(
            "contractor", "Backup Build", "A separate note mentions Backup Build."
        )
    )
    result = extract(text=text, options=offline, llm_extractor=llm)
    assert result.data.contractor.value == "Main Build"
    assert result.data.contractor.validation == "conflict"
    assert result.data.contractor.alternatives[0].value == "Backup Build"


@pytest.mark.parametrize(
    "payload",
    [
        "not json",
        '{"fields": "wrong type"}',
        '{"fields": [{"field": "invented"}]}',
        '{"fields": [], "unexpected": 1}',
    ],
)
def test_malformed_llm_falls_back(payload, offline):
    llm = StructuredLLMExtractor(lambda document: payload)
    result = extract(
        text="CHANGE ORDER\nCO Number: 0001\nProject: A\nTotal Change Amount: USD 100",
        options=offline,
        llm_extractor=llm,
    )
    assert result.status == "partial"
    assert result.data.total_change_amount.value == 100
    assert any(issue.code == "LLM_FAILED" for issue in result.issues)


def test_retry_budget_for_transient_failure():
    calls, sleeps = [], []

    def fail(payload):
        calls.append(payload)
        raise TransientLLMError("simulated rate limit")

    llm = StructuredLLMExtractor(fail, sleeper=sleeps.append)
    candidates, issues = llm.extract(read_text("CHANGE ORDER\nCO Number: 1"))
    assert len(calls) == 3 and sleeps == [0.5, 1]
    assert not candidates and issues[0].code == "LLM_FAILED"


def test_retry_then_success_and_input_bound():
    calls = []

    def intermittent(payload):
        calls.append(payload)
        if len(calls) < 2:
            raise TransientLLMError("timeout")
        return '{"fields": []}'

    llm = StructuredLLMExtractor(intermittent, sleeper=lambda duration: None)
    assert llm.extract(read_text("CHANGE ORDER")) == ([], [])
    assert len(calls) == 2
    limited = StructuredLLMExtractor(
        lambda payload: pytest.fail("Input limit must precede provider call"), max_chars=5
    )
    assert limited.extract(read_text("CHANGE ORDER"))[1][0].code == "LLM_INPUT_LIMIT"


def test_unique_quote_required():
    source = read_text("CHANGE ORDER\nAdd valves\nAdd valves")
    candidates, issues = StructuredLLMExtractor(
        lambda payload: response("description", "Add valves", "Add valves")
    ).extract(source)
    assert not candidates and issues


@pytest.mark.parametrize("raw", ["A", "bad", "Badly"])
def test_substrings_or_changed_case_are_not_verbatim_facts(raw):
    source = read_text("CHANGE ORDER\nThe note says Badly damaged ductwork.")
    quote = "The note says Badly damaged ductwork."
    # A whole source word is permitted; partial-word and changed-case values are not.
    candidates, issues = StructuredLLMExtractor(
        lambda payload: response("description", raw, quote)
    ).extract(source)
    if raw == "Badly":
        assert candidates[0].value == "Badly" and not issues
    else:
        assert not candidates and issues[0].code == "LLM_UNSUPPORTED_VALUE"


def test_environment_configuration_missing(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("CHANGEORDER_LLM_MODEL", raising=False)
    with pytest.raises(LLMError, match="Set"):
        OpenAITransport()


def test_transport_uses_installed_sdk_schema_and_no_sdk_retries(monkeypatch):
    import openai

    captured = {}

    def create(**kwargs):
        captured.update(kwargs)
        return SimpleNamespace(status="completed", output_text='{"fields": []}')

    def fake_client(**kwargs):
        captured["client"] = kwargs
        return SimpleNamespace(responses=SimpleNamespace(create=create))

    monkeypatch.setenv("OPENAI_API_KEY", "fake-offline-test-key")
    monkeypatch.setenv("CHANGEORDER_LLM_MODEL", "test-model")
    monkeypatch.setattr(openai, "OpenAI", fake_client)
    assert OpenAITransport()("source") == '{"fields": []}'
    assert captured["client"]["max_retries"] == 0
    assert captured["store"] is False
    assert captured["text"]["format"]["strict"] is True
    assert captured["text"]["format"]["schema"]["additionalProperties"] is False


@pytest.mark.parametrize("failure", ["timeout", "rate_limit", "server", "bad_request", "refusal"])
def test_provider_failure_classification(monkeypatch, failure):
    import openai

    request = httpx.Request("POST", "https://api.example.invalid")

    def create(**kwargs):
        if failure == "timeout":
            raise openai.APITimeoutError(request=request)
        if failure == "rate_limit":
            raise openai.RateLimitError(
                "rate limit", response=httpx.Response(429, request=request), body=None
            )
        if failure in {"server", "bad_request"}:
            raise openai.APIStatusError(
                "error",
                response=httpx.Response(500 if failure == "server" else 400, request=request),
                body=None,
            )
        return SimpleNamespace(status="completed", output_text="")

    monkeypatch.setenv("OPENAI_API_KEY", "fake-offline-test-key")
    monkeypatch.setenv("CHANGEORDER_LLM_MODEL", "test-model")
    monkeypatch.setattr(
        openai, "OpenAI", lambda **kwargs: SimpleNamespace(responses=SimpleNamespace(create=create))
    )
    expected = TransientLLMError if failure in {"timeout", "rate_limit", "server"} else LLMError
    with pytest.raises(expected):
        OpenAITransport()("source")
