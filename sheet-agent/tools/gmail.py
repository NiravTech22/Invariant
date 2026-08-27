"""Gmail tools.

Message bodies are never returned in full: only subject/sender/snippet
metadata crosses the tool boundary, so full email text cannot leak into
stdout, shell history, or CI logs.
"""

from __future__ import annotations

import base64
from email.message import EmailMessage
from typing import Any

from .google_auth import get_service


def list_emails(query: str = "", max_results: int = 10) -> dict[str, Any]:
    """List recent emails matching a Gmail search query (metadata only)."""
    svc = get_service("gmail", "v1")
    listing = (
        svc.users()
        .messages()
        .list(userId="me", q=query, maxResults=max_results)
        .execute()
    )

    out = []
    for ref in listing.get("messages", []):
        msg = (
            svc.users()
            .messages()
            .get(
                userId="me",
                id=ref["id"],
                format="metadata",
                metadataHeaders=["From", "Subject", "Date"],
            )
            .execute()
        )
        headers = {h["name"]: h["value"] for h in msg.get("payload", {}).get("headers", [])}
        out.append(
            {
                "id": msg.get("id"),
                "from": headers.get("From", ""),
                "subject": headers.get("Subject", ""),
                "date": headers.get("Date", ""),
                "snippet": (msg.get("snippet") or "")[:200],
            }
        )
    return {"query": query, "count": len(out), "messages": out}


def send_email(to: str, subject: str, body: str) -> dict[str, Any]:
    """Send an email from the authenticated account."""
    svc = get_service("gmail", "v1")
    msg = EmailMessage()
    msg["To"] = to
    msg["Subject"] = subject
    msg.set_content(body)

    raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
    sent = svc.users().messages().send(userId="me", body={"raw": raw}).execute()
    # Deliberately does not echo `body` back.
    return {"id": sent.get("id"), "to": to, "subject": subject, "status": "sent"}


GMAIL_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "list_emails",
            "description": (
                "List recent emails matching a Gmail search query. Returns "
                "sender, subject, date and a short snippet only."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Gmail search query, e.g. 'from:alice is:unread'.",
                    },
                    "max_results": {
                        "type": "integer",
                        "description": "Maximum number of messages to return.",
                    },
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "send_email",
            "description": (
                "Send an email. This is an outward-facing action that cannot be "
                "undone: state the recipient, subject and intent to the user "
                "before calling it unless they already approved sending."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "to": {"type": "string", "description": "Recipient email address."},
                    "subject": {"type": "string", "description": "Email subject line."},
                    "body": {"type": "string", "description": "Plain-text email body."},
                },
                "required": ["to", "subject", "body"],
            },
        },
    },
]

GMAIL_FUNCS = {"list_emails": list_emails, "send_email": send_email}
