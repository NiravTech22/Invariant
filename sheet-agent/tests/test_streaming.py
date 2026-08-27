"""Streaming output (gap 3)."""

from __future__ import annotations

import agent
from tests.conftest import (
    FakeOllamaClient,
    stream_text,
    text_response,
    tool_response,
)


def test_streaming_is_requested_by_default():
    client = FakeOllamaClient([stream_text("hi")])
    agent.run_agent("q", client=client)
    assert client.calls[0].get("stream") is True


def test_no_stream_does_not_request_streaming():
    client = FakeOllamaClient([text_response("hi")])
    agent.run_agent("q", client=client, stream=False)
    assert not client.calls[0].get("stream")


def test_chunks_are_printed_as_they_arrive(capsys):
    """The whole point of the gap: output appears progressively."""
    client = FakeOllamaClient([stream_text("The total ", "is 535. ", "Bob spent most.")])
    agent.run_agent("q", client=client)

    out = capsys.readouterr().out
    assert "The total is 535. Bob spent most." in out


def test_streamed_chunks_are_reassembled_into_the_return_value():
    """run_agent still returns the complete answer, streamed or not."""
    client = FakeOllamaClient([stream_text("535", " and ", "Bob")])
    assert agent.run_agent("q", client=client) == "535 and Bob"


def test_streaming_and_non_streaming_return_the_same_answer():
    streamed = agent.run_agent(
        "q", client=FakeOllamaClient([stream_text("a", "b", "c")]), stream=True
    )
    plain = agent.run_agent(
        "q", client=FakeOllamaClient([text_response("abc")]), stream=False
    )
    assert streamed == plain == "abc"


def test_tool_call_turn_prints_no_partial_prose(capsys, baseline_xlsx):
    """A turn that resolves to a tool call must not leak scratch text."""
    tool_chunk = tool_response("read_excel", {"path": str(baseline_xlsx)}, content="thinking")
    client = FakeOllamaClient([[tool_chunk], stream_text("535, Bob")])

    agent.run_agent("q", client=client)
    out = capsys.readouterr().out

    assert "thinking" not in out
    assert "[tool] read_excel(" in out
    assert "535, Bob" in out


def test_streamed_tool_calls_are_still_executed(baseline_xlsx):
    """Tool calls arriving over a stream drive the loop exactly as before."""
    tool_chunk = tool_response("read_excel", {"path": str(baseline_xlsx)})
    client = FakeOllamaClient([[tool_chunk], stream_text("done")])

    agent.run_agent("q", client=client)

    tool_messages = [m for m in client.last_messages if m.get("role") == "tool"]
    assert len(tool_messages) == 1
    assert "Bob" in tool_messages[0]["content"]


def test_main_does_not_double_print_streamed_answer(capsys, monkeypatch):
    """Streamed text is printed live; main() must not print it a second time."""
    monkeypatch.setattr(
        agent, "Client", lambda *a, **k: FakeOllamaClient([stream_text("unique-answer")])
    )
    agent.main(["do a thing"])

    assert capsys.readouterr().out.count("unique-answer") == 1


def test_main_prints_answer_once_with_no_stream(capsys, monkeypatch):
    monkeypatch.setattr(
        agent, "Client", lambda *a, **k: FakeOllamaClient([text_response("unique-answer")])
    )
    agent.main(["do a thing", "--no-stream"])

    assert capsys.readouterr().out.count("unique-answer") == 1
