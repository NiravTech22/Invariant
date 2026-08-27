"""Regression tests for CLAUDE.md's non-negotiable safety rules.

These exist to make the safety rules fail loudly if a future refactor or
prompt edit quietly drops them.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

import agent

REPO_ROOT = Path(__file__).resolve().parent.parent


def test_destructive_tool_set_is_exactly_as_documented():
    assert agent.DESTRUCTIVE_TOOLS == {
        "send_email",
        "create_event",
        "delete_event",
        "write_sheet",
        "write_excel",
    }


def test_system_prompt_names_every_destructive_tool():
    for name in agent.DESTRUCTIVE_TOOLS:
        assert name in agent.SYSTEM_PROMPT, f"{name} missing from SYSTEM_PROMPT"


def test_system_prompt_requires_stating_action_before_taking_it():
    """The confirmation behaviour itself, not just the tool names."""
    prompt = agent.SYSTEM_PROMPT.lower()
    assert "before you call any of them" in prompt
    assert "state" in prompt
    # The pre-approval carve-out must survive too.
    assert "approved" in prompt


def test_destructive_tool_schemas_carry_a_warning():
    """Each destructive tool's own description warns the model."""
    schemas = {t["function"]["name"]: t["function"]["description"] for t in agent.ALL_TOOLS}
    for name in agent.DESTRUCTIVE_TOOLS:
        desc = schemas[name].lower()
        assert any(
            word in desc for word in ("overwrite", "cannot be undone", "before calling")
        ), f"{name} schema description lacks a destructive-action warning"


@pytest.mark.parametrize(
    "relpath", ["credentials/credentials.json", "credentials/token.json"]
)
def test_credentials_are_gitignored(relpath):
    """Verified against real git, not by reading .gitignore text."""
    target = REPO_ROOT / relpath
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text('{"placeholder": "not-a-real-secret"}')

    result = subprocess.run(
        ["git", "check-ignore", "-q", str(target)],
        cwd=REPO_ROOT,
        capture_output=True,
    )
    assert result.returncode == 0, f"{relpath} is NOT gitignored -- credentials could leak"


def test_no_credential_files_are_tracked_by_git():
    tracked = subprocess.run(
        ["git", "ls-files"], cwd=REPO_ROOT, capture_output=True, text=True
    ).stdout
    for bad in ("credentials.json", "token.json"):
        assert bad not in tracked, f"{bad} is tracked by git"
