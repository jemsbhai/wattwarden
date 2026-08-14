"""Tests for the measurement core: SSE parsing, token accounting, and
statistics. No live server involved; the HTTP client is a fake."""

import json
from contextlib import contextmanager

import pytest

from wattwarden.bench import (
    RequestMeasurement,
    measure_chat,
    parse_sse_events,
    summarize,
)


def _sse(events, done=True):
    lines = []
    for event in events:
        lines.append("data: " + json.dumps(event))
        lines.append("")
    if done:
        lines.append("data: [DONE]")
    return lines


def _chunk(text):
    return {"choices": [{"delta": {"content": text}}]}


class FakeResponse:
    def __init__(self, lines):
        self._lines = lines

    def raise_for_status(self):
        return None

    def iter_lines(self):
        yield from self._lines


class FakeClient:
    def __init__(self, lines):
        self._lines = lines
        self.last_request = None

    @contextmanager
    def stream(self, method, url, json=None):
        self.last_request = {"method": method, "url": url, "json": json}
        yield FakeResponse(self._lines)


def test_parse_sse_skips_noise_and_stops_at_done():
    lines = [
        "",
        ": comment",
        "event: message",
        'data: {"a": 1}',
        "data: [DONE]",
        'data: {"never": "reached"}',
    ]
    events = list(parse_sse_events(lines))
    assert events == [{"a": 1}]


def test_parse_sse_raises_on_malformed_json():
    with pytest.raises(json.JSONDecodeError):
        list(parse_sse_events(["data: {not json"]))


def test_measure_chat_counts_usage_and_flags():
    events = [
        _chunk("Hello"),
        _chunk(" world"),
        {"usage": {"prompt_tokens": 12, "completion_tokens": 2},
         "timings": {"predicted_per_second": 33.3}},
    ]
    client = FakeClient(_sse(events))
    m = measure_chat(
        "http://fake:8080",
        model="qwen2.5-1.5b-instruct-q4_0",
        messages=[{"role": "user", "content": "hi"}],
        max_tokens=8,
        seed=42,
        client=client,
    )
    assert m.input_tokens == 12
    assert m.output_tokens == 2
    assert m.server_timings == {"predicted_per_second": 33.3}
    assert client.last_request["json"]["stream"] is True
    assert client.last_request["json"]["seed"] == 42
    assert client.last_request["url"].endswith("/v1/chat/completions")


def test_measure_chat_falls_back_to_chunk_counting_without_usage():
    events = [_chunk("a"), _chunk("b"), _chunk("c")]
    client = FakeClient(_sse(events))
    m = measure_chat(
        "http://fake:8080",
        model="qwen2.5-1.5b-instruct-q4_0",
        messages=[{"role": "user", "content": "hi"}],
        max_tokens=8,
        client=client,
    )
    assert m.output_tokens == 3
    assert m.input_tokens == 0


def test_ttft_never_exceeds_e2e():
    events = [_chunk("x")]
    client = FakeClient(_sse(events))
    m = measure_chat(
        "http://fake:8080",
        model="qwen2.5-1.5b-instruct-q4_0",
        messages=[{"role": "user", "content": "hi"}],
        max_tokens=1,
        client=client,
    )
    assert 0.0 <= m.ttft_s <= m.e2e_s


def test_gen_rate_guards_degenerate_windows():
    m = RequestMeasurement(ttft_s=1.0, e2e_s=1.0, input_tokens=5, output_tokens=10)
    assert m.gen_tok_s == 0.0
    m2 = RequestMeasurement(ttft_s=1.0, e2e_s=3.0, input_tokens=5, output_tokens=10)
    assert m2.gen_tok_s == pytest.approx(5.0)


def test_summarize_known_values():
    ms = [
        RequestMeasurement(ttft_s=0.1, e2e_s=1.1, input_tokens=10, output_tokens=20),
        RequestMeasurement(ttft_s=0.3, e2e_s=1.3, input_tokens=10, output_tokens=20),
    ]
    s = summarize(ms)
    assert s["n"] == 2
    assert s["ttft_ms"]["mean"] == pytest.approx(200.0)
    assert s["ttft_ms"]["min"] == pytest.approx(100.0)
    assert s["ttft_ms"]["max"] == pytest.approx(300.0)
    assert s["gen_tok_s"]["mean"] == pytest.approx(20.0)
    assert s["output_tokens"]["stdev"] == 0.0


def test_summarize_rejects_empty_input():
    with pytest.raises(ValueError):
        summarize([])


def test_record_shape_is_json_serializable():
    m = RequestMeasurement(ttft_s=0.1, e2e_s=1.0, input_tokens=1, output_tokens=2)
    json.dumps(m.to_record())
