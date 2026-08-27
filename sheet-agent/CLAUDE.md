# sheet-agent — CLAUDE.md

## What this is
A local automation agent: Ollama (tool-calling LLM) driving four tool sets —
Google Sheets, local Excel (openpyxl), Gmail, and Google Calendar — via
natural-language instructions from a CLI.

## Location note
This agent lives in the `sheet-agent/` subdirectory of the Invariant
repository, not at the repository root. Paths below are relative to
`sheet-agent/`. It is self-contained: Invariant's own CI (`ruff`/`mypy`/
`pytest` over `invariant/` and `tests/`) does not reach into this directory,
and this agent's test suite does not import Invariant.

## Architecture
- `agent.py` — the tool-calling loop. Sends messages + `ALL_TOOLS` schema to
  Ollama, executes whatever tool the model requests via `run_tool()`, feeds
  the result back as a `role: tool` message, repeats until the model returns
  plain content or `max_turns` (default 8) is hit.
- `tools/sheets.py`, `tools/excel.py`, `tools/gmail.py`, `tools/calendar.py`
  — each exports a `*_TOOLS` list (OpenAI-style function schemas) and a
  `*_FUNCS` dict mapping name -> callable. `agent.py` merges all four.
- `tools/google_auth.py` — single shared OAuth flow for Sheets/Gmail/Calendar
  (`SCOPES` list). Token cached at `credentials/token.json`, client secret at
  `credentials/credentials.json`. `excel.py` needs no auth.
- `tools/errors.py` — `ConfigurationError` (setup problem, surfaced to the
  user and aborts the run) vs `ToolExecutionError` (ordinary tool failure,
  fed back to the model). See gap 4 below.
- `tools/retry.py` — `call_with_retry()`, exponential backoff around network
  calls. See gap 2 below.

## Environment (verified working, don't assume older/different)
- `ollama` Python package installed: **0.6.2** (requirements.txt says
  `>=0.3.0` — this is a wide range, verify any client API assumptions against
  the actually-installed version with `pip show ollama`, not the pin).
  Verified against 0.6.2: `Client.chat(model, messages, tools=, stream=)`
  returns a `ChatResponse` (or an iterator of them when `stream=True`), and
  `message.tool_calls[i].function.arguments` is already a **Mapping**, not a
  JSON string. `run_tool()` tolerates both.
- Model: `qwen2.5:7b` via local Ollama daemon (`ollama serve`, port 11434).
- OAuth client secret originates from Google Cloud Console, must have Sheets
  API, Gmail API, and Calendar API individually enabled on that project.

## Known good baseline (do not regress this)
`python agent.py "read test.xlsx and tell me the total amount and who spent
the most"` on a 3-row test sheet (Alice 120, Bob 340, Carla 75) correctly:
1. Emits a `[tool] read_excel(...)` line
2. Returns total 535 and identifies Bob as highest
Any refactor of `agent.py` or `tools/excel.py` must be re-verified against
this exact case before being considered done.

**How this is verified offline.** `tests/test_baseline.py` drives the real
`run_agent()` loop with a scripted fake Ollama client against the real
`test.xlsx`, asserting the `[tool] read_excel(...)` line, the arguments, the
535 total and Bob as highest. This covers the loop, tool dispatch, argument
parsing and result feedback on real data — everything except the live model's
own token generation. Run `pytest -q` for the offline check and the literal
CLI command above whenever a machine with the daemon is available.

`test.xlsx` is committed; regenerate it with
`python scripts/make_test_xlsx.py`.

**Not yet verified against a live model.** The container this agent was
hardened in has no Ollama binary, no daemon on port 11434 and no `qwen2.5:7b`,
so the literal CLI command above has never been run end to end against a real
model here. Everything below the model boundary is verified; whether
`qwen2.5:7b` still chooses `read_excel` for this phrasing is not. Run the
literal command on a machine with the daemon before trusting that half.

## Safety rules — non-negotiable
- Never commit `credentials/credentials.json` or `credentials/token.json`
  (already gitignored — verify this stays true after any `.gitignore` edit).
  `tests/test_safety.py` asserts this against real `git check-ignore`.
- Never log or print full email bodies, tokens, or OAuth secrets to stdout
  in a way that would land in shell history logging or CI output.
- `send_email`, `create_event`, `delete_event`, `write_sheet`, `write_excel`
  are destructive/outward-facing. The system prompt requires the model to
  state the action before taking it unless the user pre-approved — preserve
  this behavior in any prompt or tool-schema edit; do not silently drop it.
  `tests/test_safety.py` pins this clause in `SYSTEM_PROMPT` and pins the
  `DESTRUCTIVE_TOOLS` set.

## Commands
- Install: `pip install -r requirements.txt` (`-dev` for tests)
- Auth (one-time, interactive): `python tools/google_auth.py`
- Run: `python agent.py "<instruction>"`
- Test: `pytest -q` — fully offline, no daemon/model/credentials needed.

## Current known gaps (fix in priority order when asked to harden this repo)
1. ~~No automated tests~~ — **done.** Offline pytest suite; Ollama and the
   Google APIs are mocked.
2. ~~No retry/backoff around Ollama or Google API calls~~ — **done.**
   `tools/retry.py`, applied to the chat call and Google service builds.
3. ~~No streaming output~~ — **done.** Streaming on by default, `--no-stream`
   to disable.
4. ~~`run_tool()` swallows all exceptions~~ — **done.** `ConfigurationError`
   propagates to a clean user-facing message; other failures still go back to
   the model as JSON.
5. ~~No `--dry-run` mode~~ — **done.** Destructive tools are previewed, not
   executed.
