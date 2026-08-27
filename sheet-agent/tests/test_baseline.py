"""The known-good baseline from CLAUDE.md, as a repeatable offline check.

    python agent.py "read test.xlsx and tell me the total amount and who
    spent the most"

must (1) emit a `[tool] read_excel(...)` line and (2) report total 535 with
Bob as the highest spender, against the 3-row fixture.

The live model cannot be exercised without an Ollama daemon, so the model's
turns are scripted here. Everything downstream of the model -- the loop,
tool dispatch, argument parsing, real openpyxl file reading, and the tool
result fed back as a `role: tool` message -- is the real production code.
"""

from __future__ import annotations

import json

import agent
from tests.conftest import FakeOllamaClient, text_response, tool_response

BASELINE_INSTRUCTION = "read test.xlsx and tell me the total amount and who spent the most"

FINAL_ANSWER = "The total amount is 535. Bob spent the most, at 340."


def test_baseline_emits_read_excel_tool_call(baseline_xlsx, capsys):
    """(1) the run emits a [tool] read_excel(...) line."""
    client = FakeOllamaClient(
        [
            tool_response("read_excel", {"path": str(baseline_xlsx)}),
            text_response(FINAL_ANSWER),
        ]
    )

    agent.run_agent(BASELINE_INSTRUCTION, client=client)
    out = capsys.readouterr().out

    assert "[tool] read_excel(" in out, f"no read_excel tool line in output:\n{out}"


def test_baseline_reports_total_535_and_bob(baseline_xlsx, capsys):
    """(2) the answer carries total 535 and identifies Bob as highest."""
    client = FakeOllamaClient(
        [
            tool_response("read_excel", {"path": str(baseline_xlsx)}),
            text_response(FINAL_ANSWER),
        ]
    )

    answer = agent.run_agent(BASELINE_INSTRUCTION, client=client)

    assert "535" in answer
    assert "Bob" in answer


def test_baseline_tool_result_contains_correct_data(baseline_xlsx):
    """The data handed back to the model really sums to 535 with Bob highest.

    This is the load-bearing assertion: it reads the actual fixture through
    the actual tool, so a regression in read_excel or in the fixture fails
    here even if the scripted answer text still says 535.
    """
    client = FakeOllamaClient(
        [
            tool_response("read_excel", {"path": str(baseline_xlsx)}),
            text_response(FINAL_ANSWER),
        ]
    )

    agent.run_agent(BASELINE_INSTRUCTION, client=client)

    # Second model turn sees the tool output; pull it back out of the history.
    tool_messages = [m for m in client.last_messages if m.get("role") == "tool"]
    assert len(tool_messages) == 1
    payload = json.loads(tool_messages[0]["content"])

    assert "error" not in payload, payload
    rows = payload["rows"]
    assert payload["row_count"] == 3
    assert {r["Name"] for r in rows} == {"Alice", "Bob", "Carla"}

    total = sum(r["Amount"] for r in rows)
    top = max(rows, key=lambda r: r["Amount"])
    assert total == 535, f"expected total 535, got {total}"
    assert top["Name"] == "Bob", f"expected Bob highest, got {top['Name']}"
    assert top["Amount"] == 340


def test_baseline_model_receives_read_excel_schema(baseline_xlsx):
    """The model is actually offered read_excel, not just assumed to know it."""
    client = FakeOllamaClient(
        [
            tool_response("read_excel", {"path": str(baseline_xlsx)}),
            text_response(FINAL_ANSWER),
        ]
    )

    agent.run_agent(BASELINE_INSTRUCTION, client=client)

    offered = {t["function"]["name"] for t in client.calls[0]["tools"]}
    assert "read_excel" in offered
    # All four tool sets reach the model.
    assert {"read_sheet", "send_email", "list_events"} <= offered
