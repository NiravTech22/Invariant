# sheet-agent

A local automation agent: [Ollama](https://ollama.com) (tool-calling LLM) driving
four tool sets — Google Sheets, local Excel, Gmail and Google Calendar — from a
natural-language instruction on the command line.

Everything runs on your machine. The model is local; the only outbound traffic is
to Google's APIs when you use a Google-backed tool.

## Install

```bash
pip install -r requirements.txt        # add -dev for the test suite
ollama serve &                         # local model daemon
ollama pull qwen2.5:7b
```

## Authenticate (one-time, interactive)

Place your OAuth client secret at `credentials/credentials.json`, then:

```bash
python tools/google_auth.py
```

The Sheets, Gmail and Calendar APIs must each be enabled on the Google Cloud
project the client secret came from. `credentials/` is gitignored in full.
Local Excel tools need no authentication.

## Run

```bash
python agent.py "read test.xlsx and tell me the total amount and who spent the most"
python agent.py --dry-run "email the summary to alice@example.com"
python agent.py --no-stream "list my events tomorrow"
```

| Flag | Effect |
| --- | --- |
| `--model TAG` | Ollama model tag (default `qwen2.5:7b`) |
| `--max-turns N` | Cap on tool-calling turns (default 8) |
| `--dry-run` | Preview destructive tool calls without executing them |
| `--no-stream` | Disable token streaming |
| `--verbose` | Show retry attempts and full diagnostics |

## Tools

| Tool | Module | Effect |
| --- | --- | --- |
| `read_sheet` / `write_sheet` | `tools/sheets.py` | Google Sheets read / **overwrite** |
| `read_excel` / `write_excel` | `tools/excel.py` | Local `.xlsx` read / **overwrite** |
| `list_emails` / `send_email` | `tools/gmail.py` | Gmail metadata read / **send** |
| `list_events` / `create_event` / `delete_event` | `tools/calendar.py` | Calendar read / **create** / **delete** |

The five bolded tools are destructive or outward-facing. The system prompt
requires the model to state what it is about to do before calling them, unless
the instruction already approved that action. `--dry-run` blocks them outright.

`list_emails` returns only sender, subject, date and a 200-character snippet —
full message bodies never cross the tool boundary.

## Tests

```bash
pytest -q
```

The suite runs fully offline: Ollama and the Google APIs are mocked, so no
daemon, model or credentials are required.
