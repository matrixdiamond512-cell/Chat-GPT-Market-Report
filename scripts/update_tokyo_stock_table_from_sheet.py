#!/usr/bin/env python3
"""Update only the completed Tokyo-market session.

Primary source:
- Google Sheets "終値一覧" when GitHub Actions credentials are configured.

Fallback source:
- data/market/japan-close-reference.json, refreshed on demand from public exact-date
  sources by capture_japan_close_reference.py.

Before the Tokyo close, the expected date is the previous Tokyo business day.
After the close, the expected date is the current business day. The U.S. side is
never modified by this script. Stale Japanese rows are never relabeled with a
newer date.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from typing import Any

from archive_stocks_snapshot import archive_snapshot
from write_market_data_to_sheets import (
    SheetsClient,
    create_authorized_session,
    load_service_account_info,
)

ROOT = Path(__file__).resolve().parents[1]
STOCKS_PATH = ROOT / "data" / "stocks.json"
NIKKEI_METRICS_PATH = ROOT / "data" / "nikkei-metrics.json"
REFERENCE_PATH = ROOT / "data" / "market" / "japan-close-reference.json"
CAPTURE_SCRIPT = ROOT / "scripts" / "capture_japan_close_reference.py"
JST = timezone(timedelta(hours=9))
DEFAULT_SPREADSHEET_ID = "1n2ACInX4pmK0TdijC8xaur2RIiNZyVa6GFTZAyofcuE"
SHEET_NAME = "終値一覧"
DATE_RE = re.compile(r"^(\d{4})[/-](\d{2})[/-](\d{2})")
UNAVAILABLE = "取得不能（対象日の確定値なし）"


def normalize_date(value: Any) -> str:
    match = DATE_RE.match(str(value or "").strip())
    return "-".join(match.groups()) if match else ""


def previous_weekday(day: date) -> date:
    day -= timedelta(days=1)
    while day.weekday() >= 5:
        day -= timedelta(days=1)
    return day


def expected_tokyo_date(now: datetime) -> str:
    override = os.getenv("TOKYO_MARKET_DATE", "").strip()
    if override:
        normalized = normalize_date(override)
        if not normalized:
            raise RuntimeError("TOKYO_MARKET_DATE is invalid")
        return normalized
    current = now.date()
    if current.weekday() < 5 and now.time() >= time(16, 0):
        return current.isoformat()
    return previous_weekday(current).isoformat()


def text(value: Any) -> str:
    return str(value or "").strip()


def numeric(value: Any, missing: str = UNAVAILABLE) -> str:
    raw = text(value)
    return raw if raw else missing


def percent(value: Any, missing: str = UNAVAILABLE) -> str:
    raw = text(value)
    if not raw:
        return missing
    if raw.endswith("%"):
        return raw
    try:
        number = float(raw.replace(",", ""))
        return f"{number:+.2f}%"
    except ValueError:
        return raw


def signed_number(value: Any, missing: str = "—") -> str:
    raw = text(value)
    if not raw:
        return missing
    try:
        number = float(raw.replace(",", ""))
        return f"{number:+,.2f}"
    except ValueError:
        return raw


def row_map(headers: list[Any], values: list[Any]) -> dict[str, Any]:
    return {
        str(header).strip(): values[index] if index < len(values) else ""
        for index, header in enumerate(headers)
        if str(header).strip()
    }


def evaluation(source: str, data_date: str, available: bool = True) -> str:
    if available:
        return f"{source}の確定値。基準日 {data_date}。"
    return f"取得不能（{source}で対象日の確定値を取得できず）。基準日 {data_date}。"


def metric_item(display: str, change: str, source: str, data_date: str) -> dict[str, str]:
    available = not display.startswith("取得不能")
    return {
        "raw": display,
        "display": display,
        "change": change,
        "evaluation": evaluation(source, data_date, available),
        "source": source,
    }


def find_existing_row(rows: list[Any], label: str, current_date: str, target_date: str) -> list[str] | None:
    if current_date != target_date:
        return None
    for row in rows:
        if isinstance(row, list) and row and str(row[0]).strip() == label:
            return [str(item) for item in row]
    return None


def unavailable_row(label: str, data_date: str, source: str = "公開ソース／終値一覧") -> list[str]:
    return [
        label,
        UNAVAILABLE,
        "—",
        evaluation(source, data_date, False),
    ]


def load_reference(target_date: str) -> dict[str, Any]:
    try:
        payload = json.loads(REFERENCE_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    if str(payload.get("dataDate") or "") != target_date:
        return {}
    return payload


def refresh_reference(target_date: str) -> dict[str, Any]:
    """Ensure an exact-date public reference exists.

    The capture script is intentionally allowed to produce a partial result.
    This updater then uses only exact-date items and marks the rest unavailable.
    """
    payload = load_reference(target_date)
    if payload:
        return payload

    result = subprocess.run(
        [sys.executable, str(CAPTURE_SCRIPT), "--date", target_date],
        cwd=ROOT,
        text=True,
        capture_output=True,
        timeout=120,
        check=False,
    )
    if result.stdout.strip():
        print(result.stdout.strip())
    if result.returncode != 0:
        message = result.stderr.strip() or f"exit code {result.returncode}"
        print(f"Public Tokyo close capture failed: {message}", file=sys.stderr)
        return {}
    return load_reference(target_date)


def reference_item(reference: dict[str, Any], label: str) -> tuple[str, str]:
    item = ((reference.get("items") or {}).get(label) or {})
    if not isinstance(item, dict):
        return "", ""
    value = text(item.get("value"))
    source = text(item.get("sourceName")) or "公開ソース"
    return value, source


def fetch_sheet_row(target_date: str) -> tuple[dict[str, Any] | None, str]:
    credentials_raw = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON", "").strip()
    if not credentials_raw:
        return None, "GOOGLE_SERVICE_ACCOUNT_JSON is not configured"

    spreadsheet_id = os.getenv("MARKET_DATA_SPREADSHEET_ID", DEFAULT_SPREADSHEET_ID).strip()
    try:
        client = SheetsClient(
            create_authorized_session(load_service_account_info(credentials_raw)),
            spreadsheet_id,
        )
        values = client.get_values(SHEET_NAME, "A:EZ")
    except Exception as exc:
        return None, f"Google Sheets read failed: {exc}"

    if len(values) < 2:
        return None, "終値一覧にデータ行がありません"

    headers = values[0]
    for raw_row in values[1:]:
        mapped = row_map(headers, raw_row)
        if normalize_date(mapped.get("日付")) == target_date:
            return mapped, ""
    return None, f"終値一覧に東京市場の対象日 {target_date} がありません"


def choose_value(
    selected: dict[str, Any] | None,
    sheet_key: str,
    reference: dict[str, Any],
    reference_label: str,
    *,
    kind: str = "numeric",
) -> tuple[str, str]:
    raw = text(selected.get(sheet_key)) if selected else ""
    if raw:
        if kind == "percent":
            return percent(raw), "終値一覧"
        return numeric(raw), "終値一覧"

    value, source = reference_item(reference, reference_label)
    if value:
        if kind == "percent":
            return percent(value), source
        return value, source
    return UNAVAILABLE, source or "公開ソース／終値一覧"


def main() -> int:
    now = datetime.now(JST).replace(microsecond=0)
    target_date = expected_tokyo_date(now)

    # Public exact-date reference is always available as an independent fallback.
    reference = refresh_reference(target_date)
    selected, sheet_error = fetch_sheet_row(target_date)
    if sheet_error:
        print(f"Tokyo close sheet unavailable; using public fallback where possible: {sheet_error}")

    stocks = json.loads(STOCKS_PATH.read_text(encoding="utf-8"))
    japan = stocks.setdefault("marketInternals", {}).setdefault("japan", {})
    old_rows = japan.get("rows") or []
    old_date = str((stocks.get("marketDates") or {}).get("japan") or japan.get("dataDate") or "")[:10]

    # Nikkei 225: exact-date public reference is sufficient to advance the Tokyo
    # market date even when the Google Sheet path is unavailable.
    sheet_nikkei_close = text(selected.get("日経225終値")) if selected else ""
    if sheet_nikkei_close:
        nikkei_close = numeric(sheet_nikkei_close)
        nikkei_source = "終値一覧"
        nikkei_change = signed_number(selected.get("日経225前日比"))
        nikkei_pct = percent(selected.get("日経225騰落率"), "—")
    else:
        nikkei_close, nikkei_source = reference_item(reference, "日経225現物")
        nikkei_close = nikkei_close or UNAVAILABLE
        nikkei_change = "—"
        nikkei_pct = "—"

    if nikkei_close.startswith("取得不能"):
        raise SystemExit(
            f"{target_date} の日経225確定値を終値一覧・公開ソースのどちらからも取得できません"
        )

    nikkei_change_display = (
        f"{nikkei_change}（{nikkei_pct}）"
        if nikkei_change != "—" or nikkei_pct != "—"
        else "—"
    )

    rows: list[list[str]] = [
        [
            "日経225",
            nikkei_close,
            nikkei_change_display,
            evaluation(nikkei_source, target_date, True),
        ]
    ]

    # These rows are preserved only when they already belong to the exact same
    # Tokyo date. Old rows are never carried forward under a newer date.
    for label in ("TOPIX", "グロース250"):
        rows.append(
            find_existing_row(old_rows, label, old_date, target_date)
            or unavailable_row(label, target_date)
        )

    nikkei_vi, nikkei_vi_source = choose_value(
        selected, "日経VI終値", reference, "日経VI"
    )
    nikkei_vi_change = signed_number(selected.get("日経VI前日比")) if selected else "—"
    nikkei_vi_pct = percent(selected.get("日経VI騰落率"), "—") if selected else "—"
    nikkei_vi_change_display = (
        f"{nikkei_vi_change}（{nikkei_vi_pct}）"
        if not nikkei_vi.startswith("取得不能")
        and (nikkei_vi_change != "—" or nikkei_vi_pct != "—")
        else "—"
    )
    rows.append([
        "日経VI",
        nikkei_vi,
        nikkei_vi_change_display,
        evaluation(nikkei_vi_source, target_date, not nikkei_vi.startswith("取得不能")),
    ])

    adv, adv_source = choose_value(
        selected,
        "東証プライム値上がり銘柄数",
        reference,
        "東証プライム値上がり銘柄数",
    )
    dec, dec_source = choose_value(
        selected,
        "東証プライム値下がり銘柄数",
        reference,
        "東証プライム値下がり銘柄数",
    )
    breadth_available = not adv.startswith("取得不能") and not dec.startswith("取得不能")
    breadth_source = adv_source if adv_source == dec_source else f"{adv_source} / {dec_source}"
    rows.append([
        "値上がり銘柄 / 値下がり銘柄",
        f"{adv} / {dec}" if breadth_available else UNAVAILABLE,
        "—",
        evaluation(breadth_source, target_date, breadth_available),
    ])

    trading_value, trading_source = choose_value(
        selected,
        "東証プライム売買代金",
        reference,
        "東証プライム売買代金",
    )
    if not trading_value.startswith("取得不能") and "兆" not in trading_value and "億" not in trading_value:
        trading_value += " 兆円"
    rows.append([
        "東証プライム売買代金",
        trading_value,
        "—",
        evaluation(trading_source, target_date, not trading_value.startswith("取得不能")),
    ])

    ratio, ratio_source = choose_value(
        selected,
        "東証プライム騰落レシオ",
        reference,
        "東証プライム25日騰落レシオ",
    )
    rows.append([
        "騰落レシオ（25日）",
        ratio,
        "—",
        evaluation(ratio_source, target_date, not ratio.startswith("取得不能")),
    ])

    per_value, per_source = choose_value(
        selected, "日経225予想PER", reference, "日経225予想PER"
    )
    eps, eps_source = choose_value(
        selected, "日経225予想EPS", reference, "日経225予想EPS"
    )
    dev25, dev25_source = choose_value(
        selected,
        "日経225_25日乖離率",
        reference,
        "日経225 25日移動平均乖離率",
        kind="percent",
    )
    dev200, dev200_source = choose_value(
        selected,
        "日経225_200日乖離率",
        reference,
        "日経225 200日移動平均乖離率",
        kind="percent",
    )

    rows.extend([
        [
            "日経225予想PER",
            per_value,
            "—",
            evaluation(per_source, target_date, not per_value.startswith("取得不能")),
        ],
        [
            "日経225予想EPS",
            eps,
            "—",
            evaluation(eps_source, target_date, not eps.startswith("取得不能")),
        ],
        [
            "日経225 25日乖離率",
            dev25,
            "—",
            evaluation(dev25_source, target_date, not dev25.startswith("取得不能")),
        ],
        [
            "日経225 200日乖離率",
            dev200,
            "—",
            evaluation(dev200_source, target_date, not dev200.startswith("取得不能")),
        ],
    ])

    overseas = find_existing_row(
        old_rows, "海外投資家動向（現物）", old_date, target_date
    )
    rows.append(overseas or unavailable_row("海外投資家動向（現物）", target_date))

    public_used = any(
        source not in ("終値一覧", "公開ソース／終値一覧")
        for source in (
            nikkei_source,
            nikkei_vi_source,
            adv_source,
            dec_source,
            trading_source,
            ratio_source,
            per_source,
            eps_source,
            dev25_source,
            dev200_source,
        )
    )
    source_mode = (
        "終値一覧＋公開ソース補完"
        if selected and public_used
        else "終値一覧"
        if selected
        else "公開ソース（exact-date fallback）"
    )

    japan.update({
        "title": "主要指数と市場内部（日本）",
        "flag": "JP",
        "columns": ["指標名", "終値", "前日比", "評価・概況"],
        "rows": rows,
        "dataDate": target_date,
        "updatedAt": now.isoformat(),
        "source": {
            "name": source_mode,
            "sheet": SHEET_NAME if selected else "",
            "reference": "data/market/japan-close-reference.json",
            "sheetStatus": "ok" if selected else sheet_error,
        },
    })
    stocks.setdefault("marketDates", {})["japan"] = target_date
    stocks.setdefault("marketUpdatedAt", {})["japan"] = now.isoformat()
    stocks["nikkeiMetricsAsOf"] = target_date
    stocks["sourceStatus"] = "米国市場と東京市場を独立更新・市場別基準日を明示"
    STOCKS_PATH.write_text(
        json.dumps(stocks, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    metrics_payload = {
        "schemaVersion": "2.1.0",
        "generatedAt": now.isoformat(),
        "dataAsOf": target_date,
        "sourceMode": source_mode,
        "sourceSheet": SHEET_NAME if selected else "",
        "reference": "data/market/japan-close-reference.json",
        "metrics": {
            "日経VI": metric_item(
                nikkei_vi, nikkei_vi_change_display, nikkei_vi_source, target_date
            ),
            "日経225予想PER": metric_item(
                per_value, "—", per_source, target_date
            ),
            "日経225予想EPS": metric_item(
                eps, "—", eps_source, target_date
            ),
            "日経225 25日乖離率": metric_item(
                dev25, "—", dev25_source, target_date
            ),
            "日経225 200日乖離率": metric_item(
                dev200, "—", dev200_source, target_date
            ),
        },
    }
    NIKKEI_METRICS_PATH.write_text(
        json.dumps(metrics_payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    snapshot = archive_snapshot(STOCKS_PATH)
    print(json.dumps({
        "tokyoMarketDate": target_date,
        "usMarketDateRetained": (stocks.get("marketDates") or {}).get("us"),
        "sourceMode": source_mode,
        "sheetStatus": "ok" if selected else sheet_error,
        "breadth": f"{adv} / {dec}" if breadth_available else UNAVAILABLE,
        "snapshot": str(snapshot.relative_to(ROOT)),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

