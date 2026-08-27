"""Tool-calling loop mechanics."""

from __future__ import annotations

import json

import agent
from tests.conftest import FakeOllamaClient, text_response, tool_response


def test_plain_answer_short_circuits_without_tools():
    client = FakeOllamaClient([text_response("  hello  ")])
    assert agent.run_agent("hi", client=client) == "hello"
    assert len(client.calls) == 1


def test_tool_result_is_fed_back_as_tool_role(baseline_xlsx):
    client = FakeOllamaClient(
        [tool_response("read_excel", {"path": str(baseline_xlsx)}), text_response("ok")]
    )
    agent.run_agent("read it", client=client)

    roles = [m["role"] for m in client.last_messages]
    assert roles == ["system", "user", "assistant", "tool"]
    assert client.last_messages[-1]["tool_name"] == "read_excel"


def test_unknown_tool_reports_error_to_model():
    client = FakeOllamaClient([tool_response("nope", {}), text_response("done")])
    agent.run_agent("go", client=client)

    payload = json.loads(client.last_messages[-1]["content"])
    assert "unknown tool" in payload["error"]


def test_tool_exception_is_returned_not_raised():
    """A failing tool must not abort the run."""
    client = FakeOllamaClient(
        [tool_response("read_excel", {"path": "missing.xlsx"}), text_response("recovered")]
    )
    answer = agent.run_agent("read missing", client=client)

    payload = json.loads(client.last_messages[-1]["content"])
    assert "FileNotFoundError" in payload["error"]
    assert answer == "recovered"


def test_string_arguments_are_parsed(baseline_xlsx):
    """Defensive: some model builds emit arguments as a JSON string."""
    resp = tool_response("read_excel", {})
    resp.message.tool_calls[0].function.arguments = json.dumps({"path": str(baseline_xlsx)})
    client = FakeOllamaClient([resp, text_response("ok")])

    agent.run_agent("read", client=client)
    payload = json.loads(client.last_messages[-1]["content"])
    assert payload["row_count"] == 3


def test_max_turns_is_enforced(baseline_xlsx):
    """A model that only ever calls tools must terminate, not loop forever."""
    client = FakeOllamaClient(
        [tool_response("read_excel", {"path": str(baseline_xlsx)}) for _ in range(3)]
    )
    answer = agent.run_agent("loop", client=client, max_turns=3)

    assert "maximum number of tool-calling turns" in answer
    assert len(client.calls) == 3


def test_system_prompt_is_first_message():
    client = FakeOllamaClient([text_response("hi")])
    agent.run_agent("q", client=client)

    first = client.calls[0]["messages"][0]
    assert first["role"] == "system"
    assert first["content"] == agent.SYSTEM_PROMPT
