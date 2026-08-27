"""Google Calendar tools."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from .google_auth import get_service


def list_events(
    calendar_id: str = "primary", max_results: int = 10, time_min: str | None = None
) -> dict[str, Any]:
    """List upcoming calendar events."""
    svc = get_service("calendar", "v3")
    start = time_min or datetime.now(timezone.utc).isoformat()
    resp = (
        svc.events()
        .list(
            calendarId=calendar_id,
            timeMin=start,
            maxResults=max_results,
            singleEvents=True,
            orderBy="startTime",
        )
        .execute()
    )

    events = [
        {
            "id": e.get("id"),
            "summary": e.get("summary", ""),
            "start": e.get("start", {}).get("dateTime") or e.get("start", {}).get("date"),
            "end": e.get("end", {}).get("dateTime") or e.get("end", {}).get("date"),
        }
        for e in resp.get("items", [])
    ]
    return {"calendar_id": calendar_id, "count": len(events), "events": events}


def create_event(
    summary: str,
    start: str,
    end: str,
    calendar_id: str = "primary",
    description: str = "",
) -> dict[str, Any]:
    """Create a calendar event. `start`/`end` are RFC3339 timestamps."""
    svc = get_service("calendar", "v3")
    created = (
        svc.events()
        .insert(
            calendarId=calendar_id,
            body={
                "summary": summary,
                "description": description,
                "start": {"dateTime": start},
                "end": {"dateTime": end},
            },
        )
        .execute()
    )
    return {
        "id": created.get("id"),
        "summary": summary,
        "start": start,
        "end": end,
        "status": "created",
    }


def delete_event(event_id: str, calendar_id: str = "primary") -> dict[str, Any]:
    """Permanently delete a calendar event."""
    svc = get_service("calendar", "v3")
    svc.events().delete(calendarId=calendar_id, eventId=event_id).execute()
    return {"id": event_id, "calendar_id": calendar_id, "status": "deleted"}


CALENDAR_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "list_events",
            "description": "List upcoming events from a Google Calendar.",
            "parameters": {
                "type": "object",
                "properties": {
                    "calendar_id": {
                        "type": "string",
                        "description": "Calendar ID; defaults to 'primary'.",
                    },
                    "max_results": {
                        "type": "integer",
                        "description": "Maximum number of events to return.",
                    },
                    "time_min": {
                        "type": "string",
                        "description": "RFC3339 lower bound; defaults to now.",
                    },
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_event",
            "description": (
                "Create a calendar event. This modifies the user's real calendar: "
                "state the summary and times to the user before calling it unless "
                "they already approved creating it."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "summary": {"type": "string", "description": "Event title."},
                    "start": {"type": "string", "description": "RFC3339 start timestamp."},
                    "end": {"type": "string", "description": "RFC3339 end timestamp."},
                    "calendar_id": {"type": "string", "description": "Calendar ID."},
                    "description": {"type": "string", "description": "Event description."},
                },
                "required": ["summary", "start", "end"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "delete_event",
            "description": (
                "Permanently delete a calendar event. This cannot be undone: "
                "state which event you are deleting before calling it unless the "
                "user already approved the deletion."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "event_id": {"type": "string", "description": "ID of the event to delete."},
                    "calendar_id": {"type": "string", "description": "Calendar ID."},
                },
                "required": ["event_id"],
            },
        },
    },
]

CALENDAR_FUNCS = {
    "list_events": list_events,
    "create_event": create_event,
    "delete_event": delete_event,
}
