"""Local automation agent: an Ollama tool-calling loop over four tool sets."""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any

from ollama import Client

from tools.calendar import CALENDAR_FUNCS, CALENDAR_TOOLS
from tools.excel import EXCEL_FUNCS, EXCEL_TOOLS
from tools.gmail import GMAIL_FUNCS, GMAIL_TOOLS
from tools.retry import call_with_retry
from tools.sheets import SHEETS_FUNCS, SHEETS_TOOLS

ALL_TOOLS = SHEETS_TOOLS + EXCEL_TOOLS + GMAIL_TOOLS + CALENDAR_TOOLS
ALL_FUNCS: dict[str, Any] = {
    **SHEETS_FUNCS,
    **EXCEL_FUNCS,
    **GMAIL_FUNCS,
    **CALENDAR_FUNCS,
}

DEFAULT_MODEL = "qwen2.5:7b"
DEFAULT_HOST = "http://localhost:11434"
MAX_TURNS = 8

# Tools that change state the user cares about, or that reach outside this
# machine. The system prompt below is the guard-rail for these.
DESTRUCTIVE_TOOLS = {
    "send_email",
    "create_event",
    "delete_event",
    "write_sheet",
    "write_excel",
}

SYSTEM_PROMPT = """You are a local automation assistant with tools for Google \
Sheets, local Excel files, Gmail and Google Calendar.

Work from the tools' actual output. Never invent spreadsheet values, email \
contents or calendar entries -- if you need data, call the tool that reads it.

These tools change real data or send real messages: send_email, create_event, \
delete_event, write_sheet, write_excel. Before you call any of them, state \
plainly what you are about to do and what it will affect. If the user has \
already approved that specific action in their instruction, proceed and say \
what you are doing as you do it. Read-only tools need no such announcement.

When you have the answer, reply in plain prose. Be concise and specific."""


def _warn_retry(attempt: int, delay: float, exc: BaseException) -> None:
    """Tell the user a transient failure is being retried, on stderr."""
    print(
        f"[retry] attempt {attempt} failed ({type(exc).__name__}); "
        f"retrying in {delay:.0f}s",
        file=sys.stderr,
    )


def _parse_arguments(raw: Any) -> dict[str, Any]:
    """Coerce a tool call's arguments to a plain dict.

    ollama 0.6.2 hands back a Mapping, but a JSON string is tolerated so a
    differently-behaved model build cannot crash the loop.
    """
    if raw is None:
        return {}
    if isinstance(raw, str):
        return json.loads(raw) if raw.strip() else {}
    return dict(raw)


def run_tool(name: str, args: dict[str, Any]) -> str:
    """Execute a tool by name and return its result as a JSON string.

    Errors are returned to the model rather than raised, so that a single
    bad call does not abort the whole run.
    """
    func = ALL_FUNCS.get(name)
    if func is None:
        return json.dumps({"error": f"unknown tool: {name}"})
    try:
        return json.dumps(func(**args), default=str)
    except Exception as exc:
        return json.dumps({"error": f"{type(exc).__name__}: {exc}"})


def run_agent(
    instruction: str,
    model: str = DEFAULT_MODEL,
    max_turns: int = MAX_TURNS,
    client: Client | None = None,
) -> str:
    """Run the tool-calling loop until the model answers or turns run out."""
    client = client or Client(host=DEFAULT_HOST)
    messages: list[dict[str, Any]] = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": instruction},
    ]

    for _ in range(max_turns):
        response = call_with_retry(
            client.chat,
            model=model,
            messages=messages,
            tools=ALL_TOOLS,
            on_retry=_warn_retry,
        )
        message = response.message

        tool_calls = message.tool_calls or []
        if not tool_calls:
            return (message.content or "").strip()

        # Normalise arguments once. Most builds hand back a Mapping, but some
        # emit a JSON string; both must work everywhere below.
        parsed = [
            (call.function.name, _parse_arguments(call.function.arguments))
            for call in tool_calls
        ]

        messages.append(
            {
                "role": "assistant",
                "content": message.content or "",
                "tool_calls": [
                    {"function": {"name": name, "arguments": args}} for name, args in parsed
                ],
            }
        )

        for name, args in parsed:
            print(f"[tool] {name}({json.dumps(args, default=str)})")
            result = run_tool(name, args)
            messages.append({"role": "tool", "tool_name": name, "content": result})

    return "[agent] stopped: reached the maximum number of tool-calling turns."


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Local automation agent.")
    parser.add_argument("instruction", help="Natural-language instruction.")
    parser.add_argument("--model", default=DEFAULT_MODEL, help="Ollama model tag.")
    parser.add_argument(
        "--max-turns", type=int, default=MAX_TURNS, help="Max tool-calling turns."
    )
    ns = parser.parse_args(argv)

    print(run_agent(ns.instruction, model=ns.model, max_turns=ns.max_turns))
    return 0


if __name__ == "__main__":
    sys.exit(main())
