"""Local automation agent: an Ollama tool-calling loop over four tool sets."""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any, Callable, Iterable

from ollama import Client, Message

from tools.calendar import CALENDAR_FUNCS, CALENDAR_TOOLS
from tools.errors import ConfigurationError
from tools.excel import EXCEL_FUNCS, EXCEL_TOOLS
from tools.gmail import GMAIL_FUNCS, GMAIL_TOOLS
from tools.retry import call_with_retry, is_connection_failure
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


def _guard_connection(fn: Callable[..., Any]) -> Callable[..., Any]:
    """Turn an unreachable Ollama daemon into an actionable setup error.

    Retry has already exhausted its attempts by the time this fires, so the
    daemon really is down rather than briefly unavailable.
    """

    def wrapper(*args: Any, **kwargs: Any) -> Any:
        try:
            return fn(*args, **kwargs)
        except Exception as exc:
            if not is_connection_failure(exc):
                raise
            raise ConfigurationError(
                f"cannot reach the Ollama daemon: {exc}",
                "Start it with `ollama serve`, then confirm the model is "
                "installed with `ollama list`.",
            ) from exc

    return wrapper


def _collect_stream(chunks: Iterable[Any]) -> Message:
    """Consume a streaming chat response, printing content as it arrives.

    Returns a single reassembled Message so the caller cannot tell the
    difference between a streamed and a non-streamed turn.
    """
    parts: list[str] = []
    tool_calls: list[Any] = []
    printed = False

    for chunk in chunks:
        msg = chunk.message
        if msg.tool_calls:
            tool_calls.extend(msg.tool_calls)
        piece = msg.content or ""
        if piece:
            parts.append(piece)
            # Only stream prose. A turn that turns out to be a tool call
            # prints nothing, so the [tool] line stays the first thing seen.
            if not tool_calls:
                print(piece, end="", flush=True)
                printed = True

    if printed:
        print()

    return Message(
        role="assistant",
        content="".join(parts),
        tool_calls=tool_calls or None,
    )


def _chat(
    client: Client, model: str, messages: list[dict[str, Any]], stream: bool
) -> Message:
    """One model turn, with retry, streamed or not.

    Retry wraps the whole turn rather than the token iterator: a stream that
    breaks halfway is restarted from scratch, so partial text is never
    duplicated into the transcript.
    """
    if not stream:
        response = _guard_connection(call_with_retry)(
            client.chat,
            model=model,
            messages=messages,
            tools=ALL_TOOLS,
            on_retry=_warn_retry,
        )
        return response.message

    def _streamed() -> Message:
        chunks = client.chat(
            model=model, messages=messages, tools=ALL_TOOLS, stream=True
        )
        return _collect_stream(chunks)

    return _guard_connection(call_with_retry)(_streamed, on_retry=_warn_retry)


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


def run_tool(name: str, args: dict[str, Any], dry_run: bool = False) -> str:
    """Execute a tool by name and return its result as a JSON string.

    Ordinary failures are returned to the model rather than raised, so a
    single bad call does not abort the run. `ConfigurationError` is the
    exception: it means the setup itself is broken, so it propagates to the
    CLI to be reported to the user.

    With `dry_run`, destructive tools are previewed instead of executed.
    Read-only tools still run, so the model can gather the data it needs to
    describe what the destructive call would do.
    """
    func = ALL_FUNCS.get(name)
    if func is None:
        return json.dumps({"error": f"unknown tool: {name}"})

    if dry_run and name in DESTRUCTIVE_TOOLS:
        # Intercept before execution, and tell the model plainly that
        # nothing happened so it does not report the action as done.
        print(f"[dry-run] would call {name}({json.dumps(args, default=str)})")
        return json.dumps(
            {
                "dry_run": True,
                "would_execute": name,
                "arguments": args,
                "note": (
                    "DRY RUN: this action was NOT performed. Tell the user what "
                    "would have happened; do not claim it was done."
                ),
            },
            default=str,
        )

    try:
        return json.dumps(func(**args), default=str)
    except ConfigurationError:
        # The environment is broken, not the call. Handing this to the model
        # would let it "explain around" a problem only the user can fix, so
        # it propagates to the CLI instead.
        raise
    except TypeError as exc:
        # Wrong/missing arguments from the model: recoverable, tell it so.
        return json.dumps({"error": f"invalid arguments for {name}: {exc}"})
    except Exception as exc:
        return json.dumps({"error": f"{type(exc).__name__}: {exc}"})


def run_agent(
    instruction: str,
    model: str = DEFAULT_MODEL,
    max_turns: int = MAX_TURNS,
    client: Client | None = None,
    stream: bool = True,
    dry_run: bool = False,
) -> str:
    """Run the tool-calling loop until the model answers or turns run out."""
    client = client or Client(host=DEFAULT_HOST)
    system_prompt = SYSTEM_PROMPT
    if dry_run:
        # Added to, never replacing, the standing confirmation rule above.
        system_prompt += (
            "\n\nDRY RUN MODE: destructive tools will not actually run. "
            "Describe what would happen; never claim an action was completed."
        )

    messages: list[dict[str, Any]] = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": instruction},
    ]

    for _ in range(max_turns):
        message = _chat(client, model, messages, stream=stream)

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
            # Under dry run a destructive call prints its own [dry-run] line;
            # a [tool] line here would read as though it had executed.
            if not (dry_run and name in DESTRUCTIVE_TOOLS):
                print(f"[tool] {name}({json.dumps(args, default=str)})")
            result = run_tool(name, args, dry_run=dry_run)
            messages.append({"role": "tool", "tool_name": name, "content": result})

    return "[agent] stopped: reached the maximum number of tool-calling turns."


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Local automation agent.")
    parser.add_argument("instruction", help="Natural-language instruction.")
    parser.add_argument("--model", default=DEFAULT_MODEL, help="Ollama model tag.")
    parser.add_argument(
        "--max-turns", type=int, default=MAX_TURNS, help="Max tool-calling turns."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview destructive tool calls without executing them.",
    )
    parser.add_argument(
        "--no-stream",
        action="store_true",
        help="Print the answer only when generation finishes, instead of streaming it.",
    )
    ns = parser.parse_args(argv)

    stream = not ns.no_stream
    if ns.dry_run:
        print("[dry-run] destructive tools will be previewed, not executed.")
    try:
        answer = run_agent(
            ns.instruction,
            model=ns.model,
            max_turns=ns.max_turns,
            stream=stream,
            dry_run=ns.dry_run,
        )
    except ConfigurationError as exc:
        # A setup problem is the user's to fix: show the remedy, not a
        # traceback, and exit with a code that distinguishes it from a
        # normal failure.
        print(exc.user_message(), file=sys.stderr)
        return 2
    # While streaming the prose has already been printed token by token;
    # printing the return value again would duplicate it.
    if not stream and answer:
        print(answer)
    return 0


if __name__ == "__main__":
    sys.exit(main())
