#!/usr/bin/env python3
"""Repair missing Tokyo-market rows without relabelling stale data as current.

This is a post-processing layer for the stocks dashboard. It deliberately keeps
source dates independent:
- TOPIX / Growth Market 250: exact target-date daily rows from Kabutan.
- Nikkei VI: verified current-day value already acquired by the generic market
  data pipeline (Nikkei official source).
- Nikkei PER/EPS and Prime turnover: refreshed exact-date Japan close reference.
- Foreign-investor cash flow: latest verified JPX weekly observation from the
  Nikkei 225 supply/demand dataset, displayed with its actual weekly date.

No value is copied forward under a newer date. If an exact-date source cannot be
verified, the existing unavailable marker is retained.
"""
from __future__ import annotations

import datetime as dt
import html
import json
import re
import subprocess
import sys
import urllib.request
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STOCKS_PATH = ROOT / "data" / "stocks.json"
NIKKEI_METRICS_PATH = ROOT / "data" / "nikkei-metrics.json"
REFERENCE_PATH = ROOT / "data" / "market" / "japan-close-reference.json"
LATEST_PATH = ROOT / "data" / "market" / "latest.json"
NIKKEI_SD_PATH = ROOT / "data" / "nikkei225-supply-demand.json"
CAPTURE_SCRIPT = ROOT / "scripts" / "capture_japan_close_reference.py"
CORRECT_SCRIPT = ROOT / "scripts" / "correct_japan_close_reference.py"
JST = dt.timezone(dt.timedelta(hours=9))
UA = "Mozilla/5.0 (compatible; ChatGPT-Market-Report/1.0)"
UNAVAILABLE_PREFIX = "取得不能"

KABUTAN_INDEXES = {
    "TOPIX": ("0010", "株探 TOPIX 日次時系列"),
    "グロース250": ("0012", "株探 東証グロース市場250指数 日次時系列"),
}


def load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except Exception:
        return {}


def save_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def http_text(url: str) -> str:
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": UA,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "ja,en-US;q=0.8,en;q=0.7",
        },
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        raw = response.read()
        encoding = response.headers.get_content_charset() or "utf-8"
    text = raw.decode(encoding, errors="replace")
    text = re.sub(r"(?is)<script.*?</script>|<style.*?</style>", " ", text)
    text = re.sub(r"(?s)<[^>]+>", " ", text)
    return html.unescape(re.sub(r"\s+", " ", text)).strip()


def number(value: str) -> float:
    return float(value.replace(",", ""))


def fmt_signed(value: float, decimals: int = 2) -> str:
    return f"{value:+,.{decimals}f}"


def parse_kabutan_index(target: dt.date, code: str) -> dict[str, Any] | None:
    url = f"https://s.kabutan.jp/stocks/{code}/historical_prices/daily/"
    text = http_text(url)
    key = f"{target.month}/{target.day}"
    # Kabutan daily table columns:
    # date, open, high, low, close, change, change%, volume.
    pattern = re.compile(
        rf"(?:^|\s){re.escape(key)}\s+"
        r"([0-9,.]+)\s+([0-9,.]+)\s+([0-9,.]+)\s+([0-9,.]+)\s+"
        r"([+\-]?[0-9,.]+)\s+([+\-]?[0-9.]+)%\s+([0-9,]+)株"
    )
    match = pattern.search(text)
    if not match:
        return None
    return {
        "close": number(match.group(4)),
        "change": number(match.group(5)),
        "changePercent": number(match.group(6)),
        "date": target.isoformat(),
        "sourceUrl": url,
    }


def row_index(rows: list[Any], label: str) -> int | None:
    for index, row in enumerate(rows):
        if isinstance(row, list) and row and str(row[0]).strip() == label:
            return index
    return None


def patch_row(
    rows: list[Any],
    label: str,
    value: str,
    change: str,
    evaluation: str,
) -> None:
    row = [label, value, change, evaluation]
    index = row_index(rows, label)
    if index is None:
        rows.append(row)
    else:
        rows[index] = row


def is_unavailable(value: Any) -> bool:
    return str(value or "").startswith(UNAVAILABLE_PREFIX)


def reference_for(target_date: str) -> dict[str, Any]:
    reference = load_json(REFERENCE_PATH)
    if reference.get("dataDate") != target_date:
        reference = {}

    # A same-day partial file is not a terminal cache. Retry late-publishing
    # sources on every post-processing run while the reference is incomplete.
    if not reference or not bool(reference.get("complete")):
        for script in (CAPTURE_SCRIPT, CORRECT_SCRIPT):
            result = subprocess.run(
                [sys.executable, str(script), "--date", target_date],
                cwd=ROOT,
                text=True,
                capture_output=True,
                timeout=150,
                check=False,
            )
            if result.stdout.strip():
                print(result.stdout.strip())
            if result.returncode != 0:
                print(
                    f"{script.name} failed: {result.stderr.strip() or result.returncode}",
                    file=sys.stderr,
                )
                break
        refreshed = load_json(REFERENCE_PATH)
        if refreshed.get("dataDate") == target_date:
            reference = refreshed
    return reference


def ref_value(reference: dict[str, Any], label: str) -> tuple[str, str, str]:
    item = ((reference.get("items") or {}).get(label) or {})
    if not isinstance(item, dict):
        return "", "", ""
    return (
        str(item.get("value") or "").strip(),
        str(item.get("sourceName") or "公開ソース").strip(),
        str(item.get("date") or reference.get("dataDate") or "").strip(),
    )


def patch_reference_rows(rows: list[Any], reference: dict[str, Any], target_date: str, diagnostics: dict[str, str]) -> None:
    mapping = {
        "東証プライム売買代金": "東証プライム売買代金",
        "日経225予想PER": "日経225予想PER",
        "日経225予想EPS": "日経225予想EPS",
    }
    for row_label, ref_label in mapping.items():
        value, source, item_date = ref_value(reference, ref_label)
        if not value or item_date != target_date:
            diagnostics[row_label] = "exact-date reference unavailable"
            continue
        display = value
        if row_label == "東証プライム売買代金" and "兆" not in display and "億" not in display:
            display += " 兆円"
        patch_row(
            rows,
            row_label,
            display,
            "—",
            f"{source}の確定値。基準日 {item_date}。",
        )
        diagnostics[row_label] = "repaired from exact-date reference"


def patch_nikkei_vi(rows: list[Any], target_date: str, diagnostics: dict[str, str]) -> None:
    latest = load_json(LATEST_PATH)
    item = ((latest.get("markets") or {}).get("nikkei_vi") or {})
    if not isinstance(item, dict):
        diagnostics["日経VI"] = "market-data item missing"
        return
    asof = str(item.get("asOf") or "")[:10]
    if asof != target_date or item.get("verificationStatus") != "verified":
        diagnostics["日経VI"] = f"not verified for target date: {asof or 'none'}"
        return
    value = item.get("value")
    change = item.get("change")
    pct = item.get("changePercent")
    if value is None:
        diagnostics["日経VI"] = "verified item has no value"
        return
    change_text = "—"
    if change is not None and pct is not None:
        change_text = f"{float(change):+.2f}（{float(pct):+.2f}%）"
    source = str(item.get("sourceName") or "日経VI公式データ")
    patch_row(
        rows,
        "日経VI",
        f"{float(value):.2f}",
        change_text,
        f"{source}の確認済み値。基準日 {target_date}。",
    )
    diagnostics["日経VI"] = "repaired from verified generic market acquisition"


def patch_kabutan_indexes(rows: list[Any], target_date: str, diagnostics: dict[str, str]) -> None:
    target = dt.date.fromisoformat(target_date)
    for label, (code, source_name) in KABUTAN_INDEXES.items():
        try:
            item = parse_kabutan_index(target, code)
        except Exception as exc:
            diagnostics[label] = f"fetch failed: {type(exc).__name__}: {exc}"
            continue
        if not item:
            diagnostics[label] = "exact target-date row not found"
            continue
        patch_row(
            rows,
            label,
            f"{float(item['close']):,.2f}",
            f"{float(item['change']):+,.2f}（{float(item['changePercent']):+.2f}%）",
            f"{source_name}の対象日行。基準日 {target_date}。",
        )
        diagnostics[label] = "repaired from exact-date Kabutan index history"


def patch_foreign_investors(rows: list[Any], diagnostics: dict[str, str]) -> None:
    supply = load_json(NIKKEI_SD_PATH)
    item = supply.get("foreignInvestors") or {}
    if not isinstance(item, dict) or item.get("status") != "verified":
        diagnostics["海外投資家動向（現物）"] = "verified JPX weekly flow unavailable"
        return
    asof = str(item.get("asOfDate") or "")[:10]
    cash = item.get("cashNet")
    if len(asof) != 10 or cash is None:
        diagnostics["海外投資家動向（現物）"] = "verified weekly flow missing date/value"
        return
    cash = float(cash)
    direction = "買い越し" if cash > 0 else "売り越し" if cash < 0 else "均衡"
    source = str(item.get("sourceName") or "JPX 投資部門別売買状況")
    patch_row(
        rows,
        "海外投資家動向（現物）",
        f"{cash:+,.2f}億円",
        "—",
        f"{source}の東証プライム現物・週次公表値。{direction}。基準週末 {asof}。日次値ではない。",
    )
    diagnostics["海外投資家動向（現物）"] = f"repaired from verified JPX weekly flow {asof}"


def patch_metrics_file(rows: list[Any], target_date: str) -> None:
    metrics = load_json(NIKKEI_METRICS_PATH)
    if not metrics:
        return
    entries = metrics.setdefault("metrics", {})
    for label in ("日経VI", "日経225予想PER", "日経225予想EPS"):
        idx = row_index(rows, label)
        if idx is None:
            continue
        row = rows[idx]
        if len(row) < 4 or is_unavailable(row[1]):
            continue
        entries[label] = {
            "raw": row[1],
            "display": row[1],
            "change": row[2],
            "evaluation": row[3],
            "source": row[3].split("の", 1)[0],
        }
    metrics["generatedAt"] = dt.datetime.now(JST).replace(microsecond=0).isoformat()
    metrics["dataAsOf"] = target_date
    metrics["sourceMode"] = "東京市場確定値統合（複数ソース・項目別基準日）"
    save_json(NIKKEI_METRICS_PATH, metrics)


def main() -> int:
    stocks = load_json(STOCKS_PATH)
    japan = ((stocks.get("marketInternals") or {}).get("japan") or {})
    rows = japan.get("rows") or []
    if not isinstance(rows, list) or not rows:
        raise SystemExit("Tokyo market rows are missing")
    target_date = str((stocks.get("marketDates") or {}).get("japan") or japan.get("dataDate") or "")[:10]
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", target_date):
        raise SystemExit("Tokyo market target date is invalid")

    diagnostics: dict[str, str] = {}
    reference = reference_for(target_date)
    patch_reference_rows(rows, reference, target_date, diagnostics)
    patch_nikkei_vi(rows, target_date, diagnostics)
    patch_kabutan_indexes(rows, target_date, diagnostics)
    patch_foreign_investors(rows, diagnostics)

    now = dt.datetime.now(JST).replace(microsecond=0).isoformat()
    japan["rows"] = rows
    japan["updatedAt"] = now
    source = japan.get("source") if isinstance(japan.get("source"), dict) else {}
    source.update({
        "name": "東京市場確定値統合（複数ソース・項目別基準日）",
        "reference": "data/market/japan-close-reference.json",
        "supportingData": [
            "data/market/latest.json（日経VI）",
            "株探 日次時系列（TOPIX・グロース250）",
            "data/nikkei225-supply-demand.json（海外投資家・週次）",
        ],
        "repairDiagnostics": diagnostics,
    })
    japan["source"] = source
    stocks.setdefault("marketUpdatedAt", {})["japan"] = now
    stocks["sourceStatus"] = "米国市場と東京市場を独立更新・項目別基準日を明示・欠損は複数ソースで補完"
    save_json(STOCKS_PATH, stocks)
    patch_metrics_file(rows, target_date)

    summary = {
        "targetDate": target_date,
        "diagnostics": diagnostics,
        "remainingUnavailable": [
            row[0]
            for row in rows
            if isinstance(row, list) and len(row) > 1 and is_unavailable(row[1])
        ],
    }
    print(json.dumps(summary, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
