"""Shared offline test doubles.

Nothing here touches the network: the Ollama client and the Google API
service builder are both replaced with in-process fakes, so the suite runs
with no daemon, no model and no credentials.
"""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

import pytest
from ollama import ChatResponse, Message

REPO_ROOT = Path(__file__).resolve().parent.parent


def make_tool_call(name: str, arguments: dict[str, Any]) -> Message.ToolCall:
    """Build a tool call in the exact shape ollama 0.6.2 produces."""
    return Message.ToolCall(
        function=Message.ToolCall.Function(name=name, arguments=arguments)
    )


def tool_response(name: str, arguments: dict[str, Any], content: str = "") -> ChatResponse:
    """A model turn that requests one tool call."""
    return ChatResponse(
        model="fake",
        message=Message(
            role="assistant", content=content, tool_calls=[make_tool_call(name, arguments)]
        ),
    )


def text_response(content: str) -> ChatResponse:
    """A model turn that returns a final plain-prose answer."""
    return ChatResponse(model="fake", message=Message(role="assistant", content=content))


class FakeOllamaClient:
    """Replays a scripted list of ChatResponse objects.

    Records every `chat()` kwarg so tests can assert on what the agent sent
    (tool schemas, message history, stream flag).
    """

    def __init__(self, script: list[Any]):
        self.script = list(script)
        self.calls: list[dict[str, Any]] = []

    def chat(self, **kwargs: Any) -> Any:
        self.calls.append(kwargs)
        if not self.script:
            raise AssertionError("FakeOllamaClient: chat() called more times than scripted")
        item = self.script.pop(0)
        if isinstance(item, Exception):
            raise item
        return item

    @property
    def last_messages(self) -> list[dict[str, Any]]:
        return self.calls[-1]["messages"]


@pytest.fixture
def baseline_xlsx(tmp_path: Path) -> Path:
    """A copy of the committed test.xlsx fixture, isolated per test."""
    dest = tmp_path / "test.xlsx"
    shutil.copy(REPO_ROOT / "test.xlsx", dest)
    return dest


class FakeGoogleRequest:
    def __init__(self, result: Any):
        self._result = result

    def execute(self) -> Any:
        return self._result
