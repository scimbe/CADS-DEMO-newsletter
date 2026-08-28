import json
import os

import pytest

from src import llm_narrative
from src.generate_report import load_dotenv, ROOT

FACTS = {
    "days": [
        {"date": "2026-08-28", "tmax": 23.7, "tmin": 17.3, "precip_mm": 10.9, "wind_max_kmh": 19.8},
    ],
    "highlights": [
        {"id": "hottest_day", "label": "Warmest day", "value": 23.7, "unit": "°C", "date": "2026-08-28"},
        {"id": "total_precip", "label": "Total precipitation", "value": 10.9, "unit": "mm"},
    ],
}


class _FakeMessage:
    def __init__(self, content):
        self.content = content


class _FakeChoice:
    def __init__(self, content):
        self.message = _FakeMessage(content)


class _FakeResponse:
    def __init__(self, content, resp_id="chatcmpl-fake-1"):
        self.choices = [_FakeChoice(content)]
        self.id = resp_id


class _FakeCompletions:
    def __init__(self, replies):
        self._replies = list(replies)
        self.calls = []

    def create(self, model, temperature, max_tokens, messages):
        self.calls.append({"model": model, "temperature": temperature, "max_tokens": max_tokens, "messages": messages})
        reply = self._replies.pop(0)
        if isinstance(reply, Exception):
            raise reply
        return _FakeResponse(reply)


class _FakeChat:
    def __init__(self, replies):
        self.completions = _FakeCompletions(replies)


class _FakeClient:
    def __init__(self, replies, base_url=None, api_key=None):
        self.chat = _FakeChat(replies)


def _install_fake_openai(monkeypatch, replies):
    def factory(base_url, api_key):
        return _FakeClient(replies, base_url=base_url, api_key=api_key)
    monkeypatch.setattr(llm_narrative, "OpenAI", factory)
    return factory


def test_generate_narrative_success_first_try(monkeypatch):
    good_reply = json.dumps({
        "selected_highlight_ids": ["hottest_day", "total_precip"],
        "narrative": "The warmest day reaches 23.7°C while total precipitation is 10.9mm.",
    })
    _install_fake_openai(monkeypatch, [good_reply])

    outcome = llm_narrative.generate_narrative(FACTS, api_base="http://fake/v1", api_key="k", model="local-devstral-small2")

    assert outcome.used_llm is True
    assert outcome.llm_fallback_used is False
    assert outcome.attempts == 1
    assert outcome.selected_highlight_ids == ["hottest_day", "total_precip"]
    assert "23.7" in outcome.narrative


def test_generate_narrative_retries_then_succeeds(monkeypatch):
    bad_reply = json.dumps({
        "selected_highlight_ids": ["hottest_day"],
        "narrative": "Expect a scorching 41.2°C heatwave.",  # fabricated number
    })
    good_reply = json.dumps({
        "selected_highlight_ids": ["hottest_day"],
        "narrative": "The warmest day reaches 23.7°C.",
    })
    _install_fake_openai(monkeypatch, [bad_reply, good_reply])

    outcome = llm_narrative.generate_narrative(FACTS, api_base="http://fake/v1", api_key="k", model="local-devstral-small2")

    assert outcome.used_llm is True
    assert outcome.llm_fallback_used is False
    assert outcome.attempts == 2
    assert outcome.narrative == "The warmest day reaches 23.7°C."


def test_generate_narrative_falls_back_after_two_guard_failures(monkeypatch):
    bad_reply_1 = json.dumps({"selected_highlight_ids": ["hottest_day"], "narrative": "A wild 99.9°C day."})
    bad_reply_2 = json.dumps({"selected_highlight_ids": ["hottest_day"], "narrative": "Also 88.8°C, invented."})
    _install_fake_openai(monkeypatch, [bad_reply_1, bad_reply_2])

    outcome = llm_narrative.generate_narrative(FACTS, api_base="http://fake/v1", api_key="k", model="local-devstral-small2")

    assert outcome.used_llm is False
    assert outcome.llm_fallback_used is True
    assert outcome.attempts == 2
    # deterministic fallback only ever uses top-2 highlight values
    assert "23.7" in outcome.narrative or "10.9" in outcome.narrative


def test_generate_narrative_falls_back_on_malformed_json_both_attempts(monkeypatch):
    _install_fake_openai(monkeypatch, ["not json at all", "still not json"])

    outcome = llm_narrative.generate_narrative(FACTS, api_base="http://fake/v1", api_key="k", model="local-devstral-small2")

    assert outcome.llm_fallback_used is True
    assert outcome.used_llm is False


def test_generate_narrative_handles_client_exception(monkeypatch):
    _install_fake_openai(monkeypatch, [RuntimeError("connection refused")])

    outcome = llm_narrative.generate_narrative(FACTS, api_base="http://fake/v1", api_key="k", model="local-devstral-small2")

    assert outcome.llm_fallback_used is True
    assert "connection refused" in outcome.guard_reason


def test_prompt_contains_facts_payload_and_hard_rules(monkeypatch):
    good_reply = json.dumps({"selected_highlight_ids": ["hottest_day"], "narrative": "23.7°C today."})
    factory = _install_fake_openai(monkeypatch, [good_reply])

    llm_narrative.generate_narrative(FACTS, api_base="http://fake/v1", api_key="k", model="local-devstral-small2")

    client = factory(base_url="http://fake/v1", api_key="k")
    # re-create isn't the same instance used internally, so instead inspect
    # via a fresh call and check the *shape* of what generate_narrative sends
    # by re-running with an inspectable client.
    replies = [good_reply]
    inspectable = _FakeClient(replies)
    monkeypatch.setattr(llm_narrative, "OpenAI", lambda base_url, api_key: inspectable)
    llm_narrative.generate_narrative(FACTS, api_base="http://fake/v1", api_key="k", model="local-devstral-small2")

    call = inspectable.chat.completions.calls[0]
    system_msg = call["messages"][0]["content"]
    user_msg = call["messages"][1]["content"]
    assert "STRICT JSON" in system_msg
    assert "Do NOT introduce any other number" in system_msg
    assert "23.7" in user_msg
    assert "hottest_day" in user_msg


@pytest.mark.live
def test_generate_narrative_live_real_litellm_call():
    """Makes one real call through litellm-proxy to local-devstral-small2.
    Manual/local only -- depends on the litellm-proxy + Ollama backend being
    up and the scoped demo key having remaining budget. Not run in the
    default `pytest` invocation; run explicitly with `pytest -m live`."""
    load_dotenv(ROOT / ".env")
    api_base = os.environ.get("LITELLM_API_BASE") or os.environ.get("LITELLM_BASE_URL")
    api_key = os.environ.get("LITELLM_API_KEY")
    model = os.environ.get("LITELLM_MODEL") or os.environ.get("LITELLM_DEFAULT_MODEL") or "local-devstral-small2"
    if not api_base or not api_key:
        pytest.skip("LITELLM_API_BASE/LITELLM_API_KEY not set (see .env.example)")

    outcome = llm_narrative.generate_narrative(FACTS, api_base=api_base, api_key=api_key, model=model)

    assert outcome.attempts >= 1
    assert outcome.narrative  # non-empty either way (LLM or fallback)
    if outcome.llm_fallback_used:
        pytest.fail(f"live LLM call fell back to deterministic template: {outcome.guard_reason}")
    assert outcome.used_llm is True
