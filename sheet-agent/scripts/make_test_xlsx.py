"""Regenerate test.xlsx, the fixture behind the known-good baseline.

Alice 120 + Bob 340 + Carla 75 = 535, with Bob the highest spender.
"""

import os

import openpyxl

ROWS = [("Name", "Amount"), ("Alice", 120), ("Bob", 340), ("Carla", 75)]


def main() -> str:
    book = openpyxl.Workbook()
    ws = book.active
    ws.title = "Expenses"
    for row in ROWS:
        ws.append(list(row))

    dest = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "test.xlsx")
    book.save(dest)
    return dest


if __name__ == "__main__":
    print(f"[fixture] wrote {main()}")
