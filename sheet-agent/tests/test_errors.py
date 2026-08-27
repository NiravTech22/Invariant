"""Setup errors vs ordinary tool failures (gap 4)."""

from __future__ import annotations

import json

import pytest

import agent
from tests.conftest import FakeOllamaClient, text_response, tool_response
from tools import google_auth
from tools.errors import ConfigurationError


def test_ordinary_tool_failure_still_goes_back_to_the_model():
    """Unchanged resilience: a bad call is the model's problem to handle."""
    client = FakeOllamaClient(
        [tool_response("read_excel", {"path": "nope.xlsx"}), text_response("handled")]
    )
    answer = agent.run_agent("read", client=client)

    payload = json.loads(client.last_messages[-1]["content"])
    assert "FileNotFoundError" in payload["error"]
    assert answer == "handled"


def test_bad_arguments_are_reported_to_the_model_not_crashed():
    client = FakeOllamaClient(
        [tool_response("read_excel", {"wrong_kwarg": 1}), text_response("retried")]
    )
    agent.run_agent("read", client=client)

    payload = json.loads(client.last_messages[-1]["content"])
    assert "invalid arguments for read_excel" in payload["error"]


def test_configuration_error_from_a_tool_propagates(monkeypatch):
    """A missing client secret must not be hidden inside a tool result."""
    def boom(**kwargs):
        raise ConfigurationError("no credentials", "run auth")

    monkeypatch.setitem(agent.ALL_FUNCS, "read_sheet", boom)

    with pytest.raises(ConfigurationError):
        agent.run_tool("read_sheet", {"spreadsheet_id": "x"})


def test_configuration_error_aborts_the_run_rather_than_looping(monkeypatch):
    def boom(**kwargs):
        raise ConfigurationError("no credentials", "run auth")

    monkeypatch.setitem(agent.ALL_FUNCS, "read_sheet", boom)
    client = FakeOllamaClient(
        [tool_response("read_sheet", {"spreadsheet_id": "x"}), text_response("unreachable")]
    )

    with pytest.raises(ConfigurationError):
        agent.run_agent("read my sheet", client=client)


def test_main_reports_setup_error_without_a_traceback(monkeypatch, capsys):
    def boom(**kwargs):
        raise ConfigurationError("no OAuth client secret at credentials/credentials.json",
                                 "Download it from the Google Cloud Console.")

    monkeypatch.setitem(agent.ALL_FUNCS, "read_sheet", boom)
    monkeypatch.setattr(
        agent,
        "Client",
        lambda *a, **k: FakeOllamaClient([[tool_response("read_sheet", {"spreadsheet_id": "x"})]]),
    )

    code = agent.main(["read my sheet"])
    err = capsys.readouterr().err

    assert code == 2, "setup failures need a distinct exit code"
    assert "[setup]" in err
    assert "Google Cloud Console" in err
    assert "Traceback" not in err


def test_unreachable_ollama_becomes_an_actionable_setup_error(monkeypatch, capsys):
    """The exact failure seen when the daemon is not running."""
    from tools import retry as retry_mod

    monkeypatch.setattr(retry_mod.time, "sleep", lambda d: None)

    class Dead:
        def chat(self, **kwargs):
            raise ConnectionError("Failed to connect to Ollama.")

    monkeypatch.setattr(agent, "Client", lambda *a, **k: Dead())

    code = agent.main(["read test.xlsx"])
    err = capsys.readouterr().err

    assert code == 2
    assert "cannot reach the Ollama daemon" in err
    assert "ollama serve" in err
    assert "Traceback" not in err


def test_missing_client_secret_raises_configuration_error(monkeypatch, tmp_path):
    monkeypatch.setattr(google_auth, "TOKEN_FILE", str(tmp_path / "token.json"))
    monkeypatch.setattr(google_auth, "CLIENT_SECRET_FILE", str(tmp_path / "credentials.json"))

    with pytest.raises(ConfigurationError) as excinfo:
        google_auth.get_credentials()

    assert "credentials.json" in str(excinfo.value)
    assert "Google Cloud Console" in excinfo.value.remedy


def test_configuration_error_message_includes_the_remedy():
    exc = ConfigurationError("thing is missing", "do this to fix it")
    msg = exc.user_message()
    assert "[setup] thing is missing" in msg
    assert "do this to fix it" in msg


def test_httpx_style_connect_error_is_also_handled(monkeypatch, capsys):
    """Regression: ollama leaks httpx.ConnectError on the streaming path.

    It does not subclass the builtin ConnectionError, so matching on that
    alone let a raw traceback through and skipped retry entirely.
    """
    from tools import retry as retry_mod

    monkeypatch.setattr(retry_mod.time, "sleep", lambda d: None)

    class ConnectError(Exception):
        """Same name and shape as httpx.ConnectError."""

    class Dead:
        def chat(self, **kwargs):
            raise ConnectError("[Errno 111] Connection refused")

    monkeypatch.setattr(agent, "Client", lambda *a, **k: Dead())

    code = agent.main(["read test.xlsx"])
    err = capsys.readouterr().err

    assert code == 2
    assert "cannot reach the Ollama daemon" in err
    assert "ollama serve" in err
    assert "Traceback" not in err


def test_httpx_style_connect_error_is_retried():
    """It must also count as transient, or streaming never retries."""
    from tools.retry import is_transient

    class ConnectError(Exception):
        pass

    assert is_transient(ConnectError("connection refused"))
