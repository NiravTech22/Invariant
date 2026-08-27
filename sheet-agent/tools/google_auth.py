"""Shared OAuth flow for the Google-backed tools (Sheets, Gmail, Calendar).

A single cached token covers all three APIs, so the user authorises once.
`excel.py` deliberately does not use this module -- local spreadsheet work
needs no credentials at all.
"""

from __future__ import annotations

import os

# One combined scope list: re-authorising per-API would force the user through
# three consent screens and invalidate the previously cached token each time.
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/gmail.modify",
    "https://www.googleapis.com/auth/calendar",
]

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)

CREDENTIALS_DIR = os.path.join(_ROOT, "credentials")
CLIENT_SECRET_FILE = os.path.join(CREDENTIALS_DIR, "credentials.json")
TOKEN_FILE = os.path.join(CREDENTIALS_DIR, "token.json")


def get_credentials():
    """Return valid OAuth credentials, refreshing or prompting as needed."""
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow

    creds = None
    if os.path.exists(TOKEN_FILE):
        creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)

    if creds and creds.valid:
        return creds

    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
    else:
        if not os.path.exists(CLIENT_SECRET_FILE):
            raise FileNotFoundError(
                f"Missing OAuth client secret at {CLIENT_SECRET_FILE}. "
                "Download it from the Google Cloud Console and place it there."
            )
        flow = InstalledAppFlow.from_client_secrets_file(CLIENT_SECRET_FILE, SCOPES)
        creds = flow.run_local_server(port=0)

    os.makedirs(CREDENTIALS_DIR, exist_ok=True)
    with open(TOKEN_FILE, "w", encoding="utf-8") as fh:
        fh.write(creds.to_json())
    return creds


def get_service(api: str, version: str):
    """Build a Google API client for `api` using the shared credentials."""
    from googleapiclient.discovery import build

    return build(api, version, credentials=get_credentials(), cache_discovery=False)


if __name__ == "__main__":
    get_credentials()
    # Never print the token itself -- only that it was written.
    print(f"[auth] credentials cached at {TOKEN_FILE}")
