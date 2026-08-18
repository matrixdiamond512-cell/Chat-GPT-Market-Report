#!/usr/bin/env python3
"""Repair Tokyo Prime turnover from the dated Traders Web close commentary.

The source is accepted only when the page explicitly contains the target Tokyo
session date and a post-close (15:00 or later) block. Composite Japanese units
such as "9兆1900億円" are normalized to trillion yen. No older observation is
carried forward under a newer date.
"""
from __future__ import annotations

import datetime as dt
import html
import json
import re
import urllib.request
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STOCKS_PATH = ROOT / "data" / "stocks.json"
WADAI_URL = "https://www.traders.co.jp/market_jp/wadai"
JST = dt.timezone(dt.timedelta(hours=9))
UA = "Mozilla/5.0 (compatible; ChatGPT-Market-Report/1.0)"


def load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except Exception:
        return {}


def save_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def fetch_text(url: str) -> str:
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": UA,
            "Accept": "text/html,application/xhtml+xml",
            "Accept-Language": "ja,en-US;q=0.7,en;q=0.5",
            "Cache-Control": "no-cache",
            "Pragma": "no-cache",
        },
    )
    with urllib.request.urlopen(request, timeout=35) as response:
        raw = response.read()
        encoding = response.headers.get_content_charset() or "utf-8"
    source = raw.decode(encoding, errors="replace")
    source = re.sub(r"(?is)<script.*?</script>|<style.*?</style>", " ", source)
    return html.unescape(re.sub(r"\s+", " ", re.sub(r"(?s)<[^>]+>", " ", source))).strip()


def parse_turnover(target: dt.date) -> tuple[float, str] | None:
    text = fetch_text(WADAI_URL)
    date_key = target.strftime("%Y/%m/%d")
    timestamp_re = re.compile(rf"{re.escape(date_key)}\s+(1[5-9]|2[0-3]):([0-5]\d)")
    starts = [m.start() for m in timestamp_re.finditer(text)]
    if not starts:
        return None

    # Prefer a post-close commentary block containing the Tokyo Prime turnover.
    for start in starts:
        block = text[start : start + 5000]
        marker = block.find("東証プライムの売買代金")
        if marker < 0:
            marker = block.find("東証プライム売買代金")
        if marker < 0:
            continue
        segment = block[marker : marker + 260]

        composite = re.search(r"売買代金(?:は)?(?:概算で)?\s*([0-9]+(?:\.[0-9]+)?)兆\s*([0-9,]+)?億円", segment)
        if composite:
            trillion = float(composite.group(1))
            hundred_million = float((composite.group(2) or "0").replace(",", ""))
            return trillion + hundred_million / 10000.0, date_key

        trillion_match = re.search(r"売買代金(?:は)?(?:概算で)?\s*([0-9]+(?:\.[0-9]+)?)兆円", segment)
        if trillion_match:
            return float(trillion_match.group(1)), date_key

        billion_match = re.search(r"売買代金(?:は)?(?:概算で)?\s*([0-9,]+(?:\.[0-9]+)?)億円", segment)
        if billion_match:
            return float(billion_match.group(1).replace(",", "")) / 10000.0, date_key
    return None


def patch_row(rows: list[Any], target: dt.date, value: float) -> None:
    display = f"{value:.4f}".rstrip("0").rstrip(".") + " 兆円"
    replacement = [
        "東証プライム売買代金",
        display,
        "—",
        f"トレーダーズ・ウェブ 後場概況の確定値。基準日 {target.isoformat()}。",
    ]
    for index, row in enumerate(rows):
        if isinstance(row, list) and row and str(row[0]).strip() == "東証プライム売買代金":
            rows[index] = replacement
            return
    rows.append(replacement)


def main() -> int:
    stocks = load_json(STOCKS_PATH)
    japan = ((stocks.get("marketInternals") or {}).get("japan") or {})
    rows = japan.get("rows") or []
    target_text = str((stocks.get("marketDates") or {}).get("japan") or japan.get("dataDate") or "")[:10]
    try:
        target = dt.date.fromisoformat(target_text)
    except ValueError:
        raise SystemExit("invalid Tokyo target date")
    if not isinstance(rows, list):
        raise SystemExit("Tokyo rows missing")

    diagnostics: dict[str, str] = {}
    try:
        parsed = parse_turnover(target)
    except Exception as exc:
        parsed = None
        diagnostics["東証プライム売買代金-wadai"] = f"{type(exc).__name__}: {exc}"

    if parsed is not None:
        value, _ = parsed
        patch_row(rows, target, value)
        diagnostics["東証プライム売買代金"] = "repaired from exact-date Traders Web post-close commentary"
    else:
        diagnostics["東証プライム売買代金"] = "exact-date Traders Web post-close turnover unavailable"

    now = dt.datetime.now(JST).replace(microsecond=0).isoformat()
    japan["rows"] = rows
    japan["updatedAt"] = now
    source = japan.get("source") if isinstance(japan.get("source"), dict) else {}
    prior = source.get("repairDiagnostics") if isinstance(source.get("repairDiagnostics"), dict) else {}
    prior.update(diagnostics)
    source["repairDiagnostics"] = prior
    supporting = source.get("supportingData") if isinstance(source.get("supportingData"), list) else []
    if "トレーダーズ・ウェブ マーケットの話題（東証プライム売買代金）" not in supporting:
        supporting.append("トレーダーズ・ウェブ マーケットの話題（東証プライム売買代金）")
    source["supportingData"] = supporting
    japan["source"] = source
    stocks.setdefault("marketUpdatedAt", {})["japan"] = now
    save_json(STOCKS_PATH, stocks)
    print(json.dumps({"targetDate": target_text, "diagnostics": diagnostics}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
