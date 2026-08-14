"""Shared test fakes for sweep and bench tests."""

import json
from contextlib import contextmanager

import pytest


def make_sse(events, done=True):
    lines = []
    for event in events:
        lines.append("data: " + json.dumps(event))
        lines.append("")
    if done:
        lines.append("data: [DONE]")
    return lines


def chat_chunk(text):
    return {"choices": [{"delta": {"content": text}}]}


class FakeStreamResponse:
    def __init__(self, lines):
        self._lines = lines

    def raise_for_status(self):
        return None

    def iter_lines(self):
        yield from self._lines


class FakeStreamClient:
    """Duck-typed stand-in for httpx.Client streaming."""

    def __init__(self, lines):
        self._lines = lines
        self.requests = []
        self.closed = False

    @contextmanager
    def stream(self, method, url, json=None):
        self.requests.append({"method": method, "url": url, "json": json})
        yield FakeStreamResponse(self._lines)

    def close(self):
        self.closed = True


class FakeProc:
    """Stand-in for subprocess.Popen return value."""

    def __init__(self):
        self.terminated = False
        self.killed = False

    def terminate(self):
        self.terminated = True

    def wait(self, timeout=None):
        return 0

    def kill(self):
        self.killed = True


@pytest.fixture
def standard_events():
    return make_sse(
        [
            chat_chunk("Hello"),
            chat_chunk(" world"),
            {
                "usage": {"prompt_tokens": 12, "completion_tokens": 2},
                "timings": {"predicted_per_second": 25.0},
            },
        ]
    )
