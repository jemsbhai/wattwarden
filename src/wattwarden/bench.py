"""Measurement core for the sweep driver.

Talks to a llama-server (or any OpenAI-compatible endpoint) over streaming
HTTP and measures, client-side: time to first token, end-to-end wall time,
and generated-token throughput. Server-reported extras (usage, timings)
are archived when present but the client-side clock is the measurement of
record, because it is the only one every backend provides identically.

No energy claims live here. This module measures time and tokens only.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from statistics import stdev
from typing import Any, Iterable, Iterator

import httpx

_EPSILON_S = 1e-9


@dataclass
class RequestMeasurement:
    """One measured chat completion."""

    ttft_s: float
    e2e_s: float
    input_tokens: int
    output_tokens: int
    server_usage: dict[str, Any] | None = None
    server_timings: dict[str, Any] | None = None

    @property
    def gen_tok_s(self) -> float:
        """Generation throughput over the post-first-token window."""
        window = self.e2e_s - self.ttft_s
        if window <= _EPSILON_S or self.output_tokens <= 0:
            return 0.0
        return self.output_tokens / window

    def to_record(self) -> dict[str, Any]:
        return {
            "ttft_s": self.ttft_s,
            "e2e_s": self.e2e_s,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "gen_tok_s": self.gen_tok_s,
            "server_usage": self.server_usage,
            "server_timings": self.server_timings,
        }


def parse_sse_events(lines: Iterable[str]) -> Iterator[dict[str, Any]]:
    """Yield decoded JSON events from an SSE line stream, stopping at DONE.

    Ignores blank lines, comments, and non-data fields. Malformed JSON in a
    data line raises: silent data corruption in a benchmark is worse than a
    failed run.
    """
    for line in lines:
        if not line:
            continue
        stripped = line.strip()
        if not stripped.startswith("data:"):
            continue
        payload = stripped[len("data:"):].strip()
        if payload == "[DONE]":
            return
        yield json.loads(payload)


def _delta_content(event: dict[str, Any]) -> str:
    choices = event.get("choices")
    if not isinstance(choices, list) or not choices:
        return ""
    delta = choices[0].get("delta")
    if not isinstance(delta, dict):
        return ""
    content = delta.get("content")
    return content if isinstance(content, str) else ""


def measure_chat(
    base_url: str,
    *,
    model: str,
    messages: list[dict[str, Any]],
    max_tokens: int,
    seed: int | None = None,
    temperature: float = 0.0,
    timeout_s: float = 300.0,
    client: Any | None = None,
) -> RequestMeasurement:
    """Run one streamed chat completion and measure it client-side.

    client is injectable for tests; anything exposing
    stream(method, url, json=...) as a context manager with
    raise_for_status() and iter_lines() works.
    """
    body: dict[str, Any] = {
        "model": model,
        "messages": messages,
        "max_tokens": max_tokens,
        "stream": True,
        "stream_options": {"include_usage": True},
        "temperature": temperature,
    }
    if seed is not None:
        body["seed"] = seed

    owned_client = client is None
    if client is None:
        client = httpx.Client(timeout=timeout_s)

    url = base_url.rstrip("/") + "/v1/chat/completions"
    ttft_s: float | None = None
    chunk_tokens = 0
    server_usage: dict[str, Any] | None = None
    server_timings: dict[str, Any] | None = None

    try:
        t_start = time.perf_counter()
        with client.stream("POST", url, json=body) as response:
            response.raise_for_status()
            for event in parse_sse_events(response.iter_lines()):
                content = _delta_content(event)
                if content and ttft_s is None:
                    ttft_s = time.perf_counter() - t_start
                if content:
                    chunk_tokens += 1
                usage = event.get("usage")
                if isinstance(usage, dict):
                    server_usage = usage
                timings = event.get("timings")
                if isinstance(timings, dict):
                    server_timings = timings
        e2e_s = time.perf_counter() - t_start
    finally:
        if owned_client:
            client.close()

    input_tokens = 0
    output_tokens = chunk_tokens
    if server_usage is not None:
        input_tokens = _usage_int(server_usage, "prompt_tokens", "input_tokens")
        reported_out = _usage_int(server_usage, "completion_tokens", "output_tokens")
        if reported_out > 0:
            output_tokens = reported_out

    return RequestMeasurement(
        ttft_s=ttft_s if ttft_s is not None else e2e_s,
        e2e_s=e2e_s,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        server_usage=server_usage,
        server_timings=server_timings,
    )


def _usage_int(usage: dict[str, Any], *keys: str) -> int:
    for key in keys:
        value = usage.get(key)
        if isinstance(value, int) and not isinstance(value, bool) and value >= 0:
            return value
    return 0


def summarize(measurements: list[RequestMeasurement]) -> dict[str, Any]:
    """Mean, sample standard deviation, min, and max per metric."""
    if not measurements:
        raise ValueError("summarize requires at least one measurement")

    def stats(values: list[float]) -> dict[str, float]:
        return {
            "mean": sum(values) / len(values),
            "stdev": stdev(values) if len(values) > 1 else 0.0,
            "min": min(values),
            "max": max(values),
        }

    return {
        "n": len(measurements),
        "ttft_ms": stats([m.ttft_s * 1000.0 for m in measurements]),
        "gen_tok_s": stats([m.gen_tok_s for m in measurements]),
        "e2e_s": stats([m.e2e_s for m in measurements]),
        "output_tokens": stats([float(m.output_tokens) for m in measurements]),
    }
