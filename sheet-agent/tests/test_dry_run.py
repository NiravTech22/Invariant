"""--dry-run previews destructive calls without performing them (gap 5)."""

from __future__ import annotations

import json

import pytest

import agent
from tests.conftest import FakeOllamaClient, text_response, tool_response
from tools.excel import read_excel


@pytest.mark.parametrize("tool_name", sorted(agent.DESTRUCTIVE_TOOLS))
def test_every_destructive_tool_is_intercepted(tool_name, monkeypatch):
    """No destructive tool may execute under dry run."""
    executed = []
    monkeypatch.setitem(
        agent.ALL_FUNCS, tool_name, lambda **kw: executed.append(tool_name)
    )

    payload = json.loads(agent.run_tool(tool_name, {}, dry_run=True))

    assert executed == [], f"{tool_name} executed during a dry run"
    assert payload["dry_run"] is True
    assert payload["would_execute"] == tool_name


def test_dry_run_does_not_modify_a_real_file(baseline_xlsx):
    """The strongest check: the fixture on disk is untouched."""
    before = read_excel(str(baseline_xlsx))

    agent.run_tool(
        "write_excel",
        {"path": str(baseline_xlsx), "rows": [["Name", "Amount"], ["Mallory", 9999]]},
        dry_run=True,
    )

    assert read_excel(str(baseline_xlsx)) == before
    assert before["row_count"] == 3


def test_without_dry_run_the_write_really_happens(baseline_xlsx):
    """Guards against the preview silently disabling writes for everyone."""
    agent.run_tool(
        "write_excel",
        {"path": str(baseline_xlsx), "rows": [["Name", "Amount"], ["Mallory", 9999]]},
    )
    assert read_excel(str(baseline_xlsx))["rows"] == [{"Name": "Mallory", "Amount": 9999}]


def test_read_only_tools_still_execute_under_dry_run(baseline_xlsx):
    """The model still needs real data to describe what would happen."""
    payload = json.loads(
        agent.run_tool("read_excel", {"path": str(baseline_xlsx)}, dry_run=True)
    )
    assert payload["row_count"] == 3
    assert "dry_run" not in payload


def test_model_is_told_the_action_did_not_happen(baseline_xlsx):
    payload = json.loads(
        agent.run_tool("send_email", {"to": "a@b.c", "subject": "s", "body": "b"}, dry_run=True)
    )
    assert "NOT performed" in payload["note"]
    assert "do not claim it was done" in payload["note"]


def test_dry_run_prints_a_preview_line(capsys):
    agent.run_tool("delete_event", {"event_id": "e1"}, dry_run=True)
    out = capsys.readouterr().out
    assert "[dry-run] would call delete_event(" in out
    assert "e1" in out


def test_dry_run_flows_through_the_agent_loop(baseline_xlsx, capsys):
    client = FakeOllamaClient(
        [
            [tool_response("write_excel", {"path": str(baseline_xlsx), "rows": [["x"]]})],
            text_response("I would overwrite the sheet."),
        ]
    )
    before = read_excel(str(baseline_xlsx))

    agent.run_agent("overwrite it", client=client, dry_run=True)

    assert read_excel(str(baseline_xlsx)) == before
    assert "[dry-run] would call write_excel(" in capsys.readouterr().out


def test_dry_run_augments_but_never_replaces_the_safety_prompt():
    """The standing confirmation rule must survive dry-run mode."""
    client = FakeOllamaClient([text_response("ok")])
    agent.run_agent("q", client=client, dry_run=True)

    system = client.calls[0]["messages"][0]["content"]
    assert agent.SYSTEM_PROMPT in system, "dry run replaced the safety prompt"
    assert "DRY RUN MODE" in system


def test_cli_flag_enables_dry_run(monkeypatch, capsys, baseline_xlsx):
    client = FakeOllamaClient(
        [
            [tool_response("write_excel", {"path": str(baseline_xlsx), "rows": [["x"]]})],
            text_response("would have written"),
        ]
    )
    monkeypatch.setattr(agent, "Client", lambda *a, **k: client)
    before = read_excel(str(baseline_xlsx))

    assert agent.main(["overwrite the sheet", "--dry-run"]) == 0

    out = capsys.readouterr().out
    assert "[dry-run] destructive tools will be previewed" in out
    assert read_excel(str(baseline_xlsx)) == before


def test_dry_run_does_not_print_a_misleading_tool_line(baseline_xlsx, capsys):
    """A [tool] line would suggest the destructive call actually ran."""
    client = FakeOllamaClient(
        [
            [tool_response("write_excel", {"path": str(baseline_xlsx), "rows": [["x"]]})],
            text_response("done"),
        ]
    )
    agent.run_agent("overwrite", client=client, dry_run=True)

    out = capsys.readouterr().out
    assert "[dry-run] would call write_excel(" in out
    assert "[tool] write_excel(" not in out


def test_read_only_tools_still_log_a_tool_line_under_dry_run(baseline_xlsx, capsys):
    client = FakeOllamaClient(
        [
            [tool_response("read_excel", {"path": str(baseline_xlsx)})],
            text_response("done"),
        ]
    )
    agent.run_agent("read", client=client, dry_run=True)

    assert "[tool] read_excel(" in capsys.readouterr().out
