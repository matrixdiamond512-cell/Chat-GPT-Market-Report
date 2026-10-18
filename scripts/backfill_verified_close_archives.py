#!/usr/bin/env python3
"""Backfill *empty* closing-sheet cells from verified dated stocks archives.

No current quote fetch, no carry-forward, no fabricated source dates, no
overwriting non-empty cells or formulas. Dry-run is the default.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
from collections import defaultdict
from pathlib import Path
from typing import Any

try:
    from write_market_data_to_sheets import SheetsClient, create_authorized_session, load_service_account_info
except ModuleNotFoundError:
    from scripts.write_market_data_to_sheets import SheetsClient, create_authorized_session, load_service_account_info

ROOT = Path(__file__).resolve().parents[1]
ARCHIVE = ROOT / "data" / "history" / "stocks"
OUT = ROOT / "data" / "market" / "close-missing-backfill.json"
JST = dt.timezone(dt.timedelta(hours=9))
SHEET = "終値一覧"


def normal_date(value: Any) -> str | None:
    text = str(value or "")[:10]
    try:
        return dt.date.fromisoformat(text).isoformat()
    except ValueError:
        return None


def contribution_values(section: dict[str, Any]) -> dict[str, Any]:
    date = normal_date(section.get("asOf"))
    if not date or section.get("status") != "verified" or section.get("freshness") not in ("fresh", None):
        return {}
    top, bottom = section.get("top") or [], section.get("bottom") or []
    if len(top) != 5 or len(bottom) != 5:
        return {}
    # Index contributions must be end-of-day, never a 09:00 snapshot.
    timestamps = section.get("sourceAt") or {}
    for side in ("top", "bottom"):
        raw = str(timestamps.get(side) or "")
        try:
            timestamp = dt.datetime.fromisoformat(raw)
        except ValueError:
            return {}
        if timestamp.tzinfo is None:
            return {}
        local = timestamp.astimezone(JST)
        if local.date().isoformat() != date or (local.hour, local.minute) < (15, 30):
            return {}
    values: dict[str, Any] = {}
    seen: set[str] = set()
    for direction, items, sign in (("上位", top, 1), ("下位", bottom, -1)):
        for n, item in enumerate(items, start=1):
            code = str(item.get("code") or "").strip()
            name = str(item.get("shortName") or "").strip()
            if not name:
                name = re.sub(r"（[0-9A-Z]{4}）$", "", str(item.get("name") or "")).strip()
            try:
                contribution = float(str(item.get("contribution") or "").replace(",", ""))
            except ValueError:
                return {}
            if not re.fullmatch(r"(?:\d{4}|\d{3}[A-Z])", code) or not name or code in seen or contribution * sign <= 0:
                return {}
            seen.add(code)
            p = f"日経225寄与度{direction}{n}"
            values[p + "コード"] = code
            values[p + "銘柄"] = name
            values[p + "寄与度"] = contribution
    values["日経225寄与度基準日"] = date
    values["日経225寄与度取得日時"] = str(section.get("generatedAt") or section.get("updatedAt") or "")
    source = section.get("source") or {}
    values["日経225寄与度取得元"] = str(source.get("name") or source)[:250]
    return values


def sector_values(section: dict[str, Any], *, market: str) -> tuple[str | None, dict[str, Any]]:
    date = normal_date(section.get("asOf") or section.get("dataAsOf"))
    if not date or section.get("status") != "verified" or section.get("freshness") not in ("fresh", None):
        return None, {}
    gainers, losers = section.get("gainers") or [], section.get("losers") or []
    if len(gainers) != 5 or len(losers) != 5:
        return None, {}
    values: dict[str, Any] = {}
    for direction, items in (("上昇", gainers), ("下落", losers)):
        for i, item in enumerate(items, 1):
            if normal_date(item.get("asOf") or date) != date:
                return None, {}
            name = str(item.get("name") or "")
            change = str(item.get("change") or "")
            if not name or not re.fullmatch(r"[+-]?\d+(?:\.\d+)?%", change):
                return None, {}
            p = ("米国セクター" if market == "us" else "東京業種") + direction + str(i)
            values[p + "業種"] = name
            values[p + "騰落率"] = change
    values["セクター取得基準日"] = date
    values["米国セクター取得元" if market == "us" else "東京業種取得元"] = str(section.get("sourceLabel") or "stocks history archived verified sector")
    return date, values


def history_candidates(history_dir: Path) -> tuple[dict[tuple[str, str], dict[str, Any]], list[str]]:
    """Return only conflict-free (market, date) verified archived payloads."""
    found: dict[tuple[str, str], tuple[str, dict[str, Any]]] = {}
    conflicts: set[tuple[str, str]] = set()
    for path in sorted(history_dir.glob("????-??-??.json")):
        try:
            obj = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        contrib = ((obj.get("contributions") or {}).get("japan") or {})
        date = normal_date(contrib.get("asOf"))
        values = contribution_values(contrib)
        candidates = [(("contributions", date), values)] if date and values else []
        for market in ("us", "japan"):
            date, values = sector_values(((obj.get("sectors") or {}).get(market) or {}), market=market)
            if date and values:
                candidates.append((("sectors-" + market, date), values))
        for key, vals in candidates:
            # Acquisition timestamps and source labels may change across
            # snapshots of the *same* close. They are not price conflicts.
            core = {k: v for k, v in vals.items()
                    if not k.endswith("取得日時") and not k.endswith("取得元")}
            old = found.get(key)
            if old:
                old_core = {k: v for k, v in old[1].items()
                            if not k.endswith("取得日時") and not k.endswith("取得元")}
                if old_core != core:
                    conflicts.add(key)
                    continue
            found[key] = (str(path.relative_to(ROOT)), vals)
    return {key: {"sourcePath": path, "values": vals}
            for key, (path, vals) in found.items() if key not in conflicts}, ["/".join(key) for key in sorted(conflicts)]


def plan_blank_only_updates(
    rows: list[list[Any]], candidates: dict[tuple[str, str], dict[str, Any]]
) -> list[dict[str, Any]]:
    if not rows or not rows[0] or rows[0][0] != "日付":
        raise ValueError("終値一覧 header '日付' not found")
    headers = {h: j for j, h in enumerate(rows[0]) if h}
    dates = {}
    for i, row in enumerate(rows[1:], start=2):
        d = normal_date(str(row[0]).replace("/", "-")) if row else None
        if d:
            if d in dates:
                raise ValueError(f"Duplicate date {d} in Sheet rows {dates[d][0]} and {i}")
            dates[d] = (i, row)
    updates = []
    occupied = set()
    for (kind, date), record in sorted(candidates.items()):
        if date not in dates:
            continue
        row_no, row = dates[date]
        for header, value in record["values"].items():
            col = headers.get(header)
            if col is None or (col < len(row) and str(row[col]).strip()):
                continue
            # Different candidate families can share a metadata column. Do not
            # silently choose one of two source-provenance values.
            key = (row_no, col)
            if key in occupied:
                continue
            occupied.add(key)
            updates.append({
                "row": row_no, "col": col + 1,
                "header": header, "value": value,
                "marketDate": date, "sourcePath": record["sourcePath"],
            })
    return updates


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true", help="Write only previously blank cells (default dry-run)")
    args = parser.parse_args()
    checked_at = dt.datetime.now(JST).isoformat(timespec="seconds")
    candidates, conflicts = history_candidates(ARCHIVE)
    result: dict[str, Any] = {
        "status": "DRY_RUN", "checkedAt": checked_at, "candidateGroups": len(candidates),
        "conflictingGroups": conflicts, "planned": 0, "written": 0,
    }
    try:
        sheet_id = os.environ["MARKET_DATA_SPREADSHEET_ID"]
        secret = os.environ["GOOGLE_SERVICE_ACCOUNT_JSON"]
        client = SheetsClient(create_authorized_session(load_service_account_info(secret)), sheet_id)
        # FORMULA, not formatted values, preserves formulas returning "".
        url = client.base_url + "/values/" + client._range(SHEET, "A1:GD250") + "?valueRenderOption=FORMULA"
        raw = client._request("GET", url).get("values") or []
        plan = plan_blank_only_updates(raw, candidates)
        result["planned"] = len(plan)
        result["planBySource"] = dict(sorted((k, sum(1 for u in plan if u["sourcePath"] == k))
                                             for k in {u["sourcePath"] for u in plan}))
        if args.apply and plan:
            # Sparse range writes, not row rewrites. Re-read for receipt.
            for i in range(0, len(plan), 80):
                batch = plan[i:i + 80]
                response = client._request("POST", client.base_url + "/values:batchUpdate", json={
                    "valueInputOption": "RAW",
                    "data": [{"range": client._range(SHEET, f"{column_letter(u['col'])}{u['row']}"),
                              "values": [[u["value"]]]} for u in batch],
                })
                if int(response.get("totalUpdatedCells") or 0) != len(batch):
                    raise RuntimeError(f"Expected {len(batch)} updated cells; got {response.get('totalUpdatedCells')}")
                result["written"] += len(batch)
            result["status"] = "APPLIED"
            again = client._request("GET", url).get("values") or []
            for u in plan:
                row, col = u["row"] - 1, u["col"] - 1
                actual = again[row][col] if len(again) > row and len(again[row]) > col else None
                if str(actual) != str(u["value"]):
                    raise RuntimeError(f"Readback mismatch at {u['header']} {u['marketDate']}")
            result["verifiedReadback"] = len(plan)
        elif args.apply:
            result["status"] = "NO_NEW_DATA"
    except Exception as exc:  # noqa: BLE001
        result["status"] = "BLOCKED"
        result["reason"] = str(exc).splitlines()[0][:240]
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: result.get(k) for k in ("status", "candidateGroups", "planned", "written", "verifiedReadback", "reason")}, ensure_ascii=False))
    return 2 if result["status"] == "BLOCKED" else 0


def column_letter(n: int) -> str:
    text = ""
    while n:
        n, rem = divmod(n - 1, 26)
        text = chr(65 + rem) + text
    return text


if __name__ == "__main__":
    raise SystemExit(main())
