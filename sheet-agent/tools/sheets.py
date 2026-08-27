"""Google Sheets tools."""

from __future__ import annotations

from typing import Any

from .google_auth import get_service


def read_sheet(spreadsheet_id: str, range: str = "A1:Z1000") -> dict[str, Any]:
    """Read a cell range from a Google Sheet."""
    svc = get_service("sheets", "v4")
    resp = (
        svc.spreadsheets()
        .values()
        .get(spreadsheetId=spreadsheet_id, range=range)
        .execute()
    )
    values = resp.get("values", [])
    return {
        "spreadsheet_id": spreadsheet_id,
        "range": resp.get("range", range),
        "row_count": len(values),
        "rows": values,
    }


def write_sheet(
    spreadsheet_id: str, range: str, values: list[list[Any]]
) -> dict[str, Any]:
    """Write values into a cell range of a Google Sheet (overwrites)."""
    svc = get_service("sheets", "v4")
    resp = (
        svc.spreadsheets()
        .values()
        .update(
            spreadsheetId=spreadsheet_id,
            range=range,
            valueInputOption="USER_ENTERED",
            body={"values": values},
        )
        .execute()
    )
    return {
        "spreadsheet_id": spreadsheet_id,
        "updated_range": resp.get("updatedRange", range),
        "updated_cells": resp.get("updatedCells", 0),
    }


SHEETS_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "read_sheet",
            "description": "Read a range of cells from a Google Sheet by spreadsheet ID.",
            "parameters": {
                "type": "object",
                "properties": {
                    "spreadsheet_id": {
                        "type": "string",
                        "description": "The Google Sheets spreadsheet ID.",
                    },
                    "range": {
                        "type": "string",
                        "description": "A1 notation range, e.g. 'Sheet1!A1:D20'.",
                    },
                },
                "required": ["spreadsheet_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "write_sheet",
            "description": (
                "Write values into a range of a Google Sheet. This OVERWRITES "
                "existing cell contents."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "spreadsheet_id": {"type": "string", "description": "Spreadsheet ID."},
                    "range": {"type": "string", "description": "A1 notation target range."},
                    "values": {
                        "type": "array",
                        "description": "Rows of cell values to write.",
                        "items": {"type": "array", "items": {}},
                    },
                },
                "required": ["spreadsheet_id", "range", "values"],
            },
        },
    },
]

SHEETS_FUNCS = {"read_sheet": read_sheet, "write_sheet": write_sheet}
