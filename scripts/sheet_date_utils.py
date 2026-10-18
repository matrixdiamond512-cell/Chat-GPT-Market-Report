"""Normalize date text and Google Sheets numeric date serials consistently."""
from __future__ import annotations

import datetime as dt
import math
import re
from typing import Any

SHEETS_EPOCH = dt.date(1899, 12, 30)


def parse_sheet_market_date(value: Any) -> str | None:
    """Return ISO market date without changing the stored Sheet cell.

    When Sheets values are read with valueRenderOption=FORMULA, a date cell can
    be a serial number (e.g. 46239), while text-typed rows stay "2026/08/05".
    Both forms represent the same date; simply str(value) is not sufficient.
    """
    if value is None or isinstance(value, bool):
        return None
    raw = str(value).strip()
    if not raw:
        return None
    if isinstance(value, (int, float)) or re.fullmatch(r"\d{5}(?:\.0+)?", raw):
        try:
            numeric = float(value)
            if not math.isfinite(numeric) or not numeric.is_integer() or numeric < 1 or numeric > 90000:
                return None
            return (SHEETS_EPOCH + dt.timedelta(days=int(numeric))).isoformat()
        except (OverflowError, TypeError, ValueError):
            return None
    # Accept exactly ISO / Japanese slash calendar date (optionally timestamp).
    candidate = raw[:10].replace("/", "-")
    try:
        return dt.date.fromisoformat(candidate).isoformat()
    except ValueError:
        return None
