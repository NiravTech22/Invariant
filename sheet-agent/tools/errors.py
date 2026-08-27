"""Error types that separate 'your setup is broken' from 'that call failed'.

A `ConfigurationError` means the agent cannot work until the user fixes
something -- a missing client secret, an unreachable model daemon. Retrying
or handing it to the model is pointless, so it travels up to the CLI and is
reported directly with a remedy.

Every other exception is an ordinary tool-level failure: a missing
spreadsheet, a bad range, a rejected recipient. Those are fed back to the
model, which can adapt or explain.
"""

from __future__ import annotations


class SheetAgentError(Exception):
    """Base class for this agent's own errors."""


class ConfigurationError(SheetAgentError):
    """The environment is not set up correctly; the user must intervene.

    `remedy` is a concrete next step shown to the user.
    """

    def __init__(self, message: str, remedy: str = ""):
        super().__init__(message)
        self.remedy = remedy

    def user_message(self) -> str:
        text = f"[setup] {self}"
        if self.remedy:
            text += f"\n        {self.remedy}"
        return text


class ToolExecutionError(SheetAgentError):
    """An ordinary tool failure, reported back to the model."""
