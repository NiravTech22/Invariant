"""Sheets / Gmail / Calendar tools against a fake Google service.

`get_service` is patched per-module, so no credentials, no OAuth flow and no
network are involved.
"""

from __future__ import annotations

import base64

import pytest

from tests.conftest import FakeGoogleRequest
from tools import calendar as cal
from tools import gmail, sheets


class FakeSheets:
    def __init__(self, values):
        self._values = values
        self.updated: dict | None = None

    def spreadsheets(self):
        return self

    def values(self):
        return self

    def get(self, spreadsheetId, range):
        return FakeGoogleRequest({"range": range, "values": self._values})

    def update(self, spreadsheetId, range, valueInputOption, body):
        self.updated = {"range": range, "body": body}
        return FakeGoogleRequest(
            {"updatedRange": range, "updatedCells": sum(len(r) for r in body["values"])}
        )


def test_read_sheet_returns_rows(monkeypatch):
    fake = FakeSheets([["Name", "Amount"], ["Alice", "120"]])
    monkeypatch.setattr(sheets, "get_service", lambda *a, **k: fake)

    out = sheets.read_sheet("sid", "A1:B2")
    assert out["row_count"] == 2
    assert out["rows"][1] == ["Alice", "120"]


def test_write_sheet_sends_values(monkeypatch):
    fake = FakeSheets([])
    monkeypatch.setattr(sheets, "get_service", lambda *a, **k: fake)

    out = sheets.write_sheet("sid", "A1:B1", [["x", "y"]])
    assert fake.updated["body"]["values"] == [["x", "y"]]
    assert out["updated_cells"] == 2


class FakeGmail:
    def __init__(self):
        self.sent_raw: str | None = None

    def users(self):
        return self

    def messages(self):
        return self

    def list(self, userId, q, maxResults):
        return FakeGoogleRequest({"messages": [{"id": "m1"}]})

    def get(self, userId, id, format, metadataHeaders):
        return FakeGoogleRequest(
            {
                "id": id,
                "snippet": "S" * 500,
                "payload": {
                    "headers": [
                        {"name": "From", "value": "alice@example.com"},
                        {"name": "Subject", "value": "Lunch"},
                    ]
                },
            }
        )

    def send(self, userId, body):
        self.sent_raw = body["raw"]
        return FakeGoogleRequest({"id": "sent1"})


def test_list_emails_returns_metadata_only(monkeypatch):
    monkeypatch.setattr(gmail, "get_service", lambda *a, **k: FakeGmail())

    out = gmail.list_emails("is:unread")
    msg = out["messages"][0]
    assert msg["from"] == "alice@example.com"
    assert msg["subject"] == "Lunch"
    # Snippet is truncated and there is no body field at all.
    assert len(msg["snippet"]) == 200
    assert "body" not in msg


def test_send_email_does_not_echo_body(monkeypatch):
    fake = FakeGmail()
    monkeypatch.setattr(gmail, "get_service", lambda *a, **k: fake)

    out = gmail.send_email("bob@example.com", "Hi", "secret body text")

    assert out == {"id": "sent1", "to": "bob@example.com", "subject": "Hi", "status": "sent"}
    assert "secret body text" not in str(out)
    # It was still genuinely transmitted.
    assert "secret body text" in base64.urlsafe_b64decode(fake.sent_raw).decode()


class FakeCalendar:
    def __init__(self):
        self.deleted: dict | None = None
        self.inserted: dict | None = None

    def events(self):
        return self

    def list(self, **kwargs):
        return FakeGoogleRequest(
            {
                "items": [
                    {
                        "id": "e1",
                        "summary": "Standup",
                        "start": {"dateTime": "2026-01-01T09:00:00Z"},
                        "end": {"dateTime": "2026-01-01T09:15:00Z"},
                    }
                ]
            }
        )

    def insert(self, calendarId, body):
        self.inserted = body
        return FakeGoogleRequest({"id": "new1"})

    def delete(self, calendarId, eventId):
        self.deleted = {"calendarId": calendarId, "eventId": eventId}
        return FakeGoogleRequest({})


def test_list_events_flattens_times(monkeypatch):
    monkeypatch.setattr(cal, "get_service", lambda *a, **k: FakeCalendar())
    out = cal.list_events()
    assert out["events"][0]["summary"] == "Standup"
    assert out["events"][0]["start"] == "2026-01-01T09:00:00Z"


def test_create_and_delete_event(monkeypatch):
    fake = FakeCalendar()
    monkeypatch.setattr(cal, "get_service", lambda *a, **k: fake)

    cal.create_event("Review", "2026-01-02T10:00:00Z", "2026-01-02T11:00:00Z")
    assert fake.inserted["summary"] == "Review"

    out = cal.delete_event("e1")
    assert fake.deleted == {"calendarId": "primary", "eventId": "e1"}
    assert out["status"] == "deleted"


def test_all_google_tools_declare_schemas():
    """Schema names must match the callables README documents."""
    for tools, funcs in [
        (sheets.SHEETS_TOOLS, sheets.SHEETS_FUNCS),
        (gmail.GMAIL_TOOLS, gmail.GMAIL_FUNCS),
        (cal.CALENDAR_TOOLS, cal.CALENDAR_FUNCS),
    ]:
        assert {t["function"]["name"] for t in tools} == set(funcs)
