"""Retry/backoff behaviour (gap 2). No real sleeping occurs."""

from __future__ import annotations

import pytest

import agent
from tests.conftest import FakeOllamaClient, text_response, tool_response
from tools import retry as retry_mod
from tools.retry import call_with_retry, is_transient


class Recorder:
    """Stand-in for time.sleep that records the delays requested."""

    def __init__(self):
        self.delays: list[float] = []

    def __call__(self, delay: float) -> None:
        self.delays.append(delay)


def test_succeeds_without_retry_when_call_works():
    sleeper = Recorder()
    calls = []

    def ok():
        calls.append(1)
        return "fine"

    assert call_with_retry(ok, sleep=sleeper) == "fine"
    assert len(calls) == 1
    assert sleeper.delays == []


def test_transient_failure_is_retried_then_succeeds():
    sleeper = Recorder()
    attempts = {"n": 0}

    def flaky():
        attempts["n"] += 1
        if attempts["n"] < 3:
            raise ConnectionError("connection refused")
        return "recovered"

    assert call_with_retry(flaky, sleep=sleeper) == "recovered"
    assert attempts["n"] == 3
    assert sleeper.delays == [1.0, 2.0]


def test_backoff_is_exponential_and_capped():
    sleeper = Recorder()

    with pytest.raises(ConnectionError):
        call_with_retry(
            lambda: (_ for _ in ()).throw(ConnectionError("down")),
            attempts=6,
            max_delay=4.0,
            sleep=sleeper,
        )

    assert sleeper.delays == [1.0, 2.0, 4.0, 4.0, 4.0]


def test_exhausted_retries_reraise_the_original_exception():
    sleeper = Recorder()

    with pytest.raises(ConnectionError, match="still down"):
        call_with_retry(
            lambda: (_ for _ in ()).throw(ConnectionError("still down")), sleep=sleeper
        )
    assert len(sleeper.delays) == 3  # 4 attempts -> 3 sleeps


def test_non_transient_error_is_not_retried():
    """A real bug must surface immediately, not after 4 slow attempts."""
    sleeper = Recorder()
    attempts = {"n": 0}

    def broken():
        attempts["n"] += 1
        raise ValueError("bad argument")

    with pytest.raises(ValueError):
        call_with_retry(broken, sleep=sleeper)

    assert attempts["n"] == 1
    assert sleeper.delays == []


@pytest.mark.parametrize("status", [408, 429, 500, 502, 503, 504])
def test_retryable_http_statuses(status):
    class HttpErr(Exception):
        def __init__(self, code):
            self.status_code = code

    assert is_transient(HttpErr(status))


@pytest.mark.parametrize("status", [400, 401, 403, 404])
def test_client_errors_are_not_retried(status):
    class HttpErr(Exception):
        def __init__(self, code):
            self.status_code = code

    assert not is_transient(HttpErr(status))


def test_googleapiclient_style_status_is_detected():
    """HttpError keeps its status on .resp.status, not .status_code."""

    class Resp:
        status = 503

    class HttpError(Exception):
        resp = Resp()

    assert is_transient(HttpError())


def test_on_retry_callback_receives_attempt_and_delay():
    seen = []
    call_with_retry(
        _flaky_once(),
        sleep=lambda d: None,
        on_retry=lambda attempt, delay, exc: seen.append((attempt, delay, type(exc))),
    )
    assert seen == [(1, 1.0, ConnectionError)]


def _flaky_once():
    state = {"n": 0}

    def inner():
        state["n"] += 1
        if state["n"] == 1:
            raise ConnectionError("blip")
        return "ok"

    return inner


def test_agent_survives_transient_ollama_blip(baseline_xlsx, monkeypatch, capsys):
    """End-to-end: a dropped connection mid-run no longer kills the agent."""
    monkeypatch.setattr(retry_mod.time, "sleep", lambda d: None)

    client = FakeOllamaClient(
        [
            ConnectionError("Failed to connect to Ollama"),
            tool_response("read_excel", {"path": str(baseline_xlsx)}),
            text_response("The total amount is 535. Bob spent the most."),
        ]
    )
    answer = agent.run_agent("baseline", client=client)

    assert "535" in answer and "Bob" in answer
    assert "[retry]" in capsys.readouterr().err
