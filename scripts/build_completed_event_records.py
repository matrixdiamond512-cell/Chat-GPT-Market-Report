from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "data" / "events" / "completed.json"
OUTPUT = ROOT / "data" / "events" / "completed-records.json"
JST = ZoneInfo("Asia/Tokyo")


def clean(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def numeric(value: Any) -> tuple[float, str] | None:
    text = clean(value).replace(",", "")
    match = re.fullmatch(r"([+-]?\d+(?:\.\d+)?)\s*(%|K|M|B|T|万人|億ドル|pt)?", text, re.I)
    return (float(match.group(1)), (match.group(2) or "").lower()) if match else None


def compatible(actual: Any, forecast: Any) -> bool:
    a, f = numeric(actual), numeric(forecast)
    if not a or not f or a[1] != f[1]:
        return False
    if a[1] == "%" and abs(a[0] - f[0]) > 20:
        return False
    return True


def surprise(actual: Any, forecast: Any) -> tuple[str, float | None]:
    if not compatible(actual, forecast):
        return "取得不能", None
    a, f = numeric(actual), numeric(forecast)
    delta = a[0] - f[0]
    suffix = "pt" if a[1] == "%" else a[1]
    return f"{delta:+g}{suffix}", delta


def judgement(event: dict[str, Any], delta: float | None) -> str:
    if delta is None:
        return "判定不能"
    if abs(delta) < 1e-9:
        return "予想一致"
    category = clean(event.get("category"))
    title = clean(event.get("title"))
    if category == "inflation" or any(x in title for x in ("CPI", "PCE", "物価")):
        return "上振れ（インフレ強）" if delta > 0 else "下振れ（インフレ鈍化）"
    if category == "employment" or any(x in title for x in ("雇用", "失業", "賃金")):
        return "上振れ（雇用強）" if delta > 0 else "下振れ（雇用弱）"
    if "GDP" in title or category == "growth":
        return "上振れ（景気強）" if delta > 0 else "下振れ（景気弱）"
    return "市場予想を上回る" if delta > 0 else "市場予想を下回る"


def verified_reaction(event: dict[str, Any]) -> tuple[str, str, str]:
    reaction = event.get("marketReactionRecord") or {}
    initial = clean(reaction.get("initial"))
    conclusion = clean(reaction.get("conclusion"))
    reaction_type = clean(reaction.get("type"))
    return (initial or "反応確認困難", conclusion or "反応確認困難", reaction_type or "未判定")


def make_record(event: dict[str, Any], now: datetime) -> dict[str, Any] | None:
    if event.get("status") != "released" or int(event.get("importance") or 0) < 2:
        return None
    forecast = clean(event.get("forecast"))
    actual_raw = clean(event.get("actual"))
    actual_number = numeric(actual_raw)
    forecast_number = numeric(forecast)
    is_qualitative = event.get("resultType") == "qualitative"
    if not actual_raw or (not actual_number and not is_qualitative):
        return None
    actual_is_usable = is_qualitative or actual_number is not None and (forecast_number is None or compatible(actual_raw, forecast))
    diff_text, delta = surprise(actual_raw, forecast)
    actual = actual_raw if actual_is_usable else "取得不能"
    initial, conclusion, reaction_type = verified_reaction(event)
    source = event.get("resultSource") or event.get("officialSource") or {}
    return {
        "event_id": clean(event.get("id")),
        "release_datetime_jst": clean(event.get("datetimeJst")),
        "country": clean(event.get("country")) or "取得不能",
        "event_name": clean(event.get("title")) or "イベント名取得不能",
        "importance": int(event.get("importance") or 0),
        "previous": clean(event.get("previous")) or "取得不能",
        "forecast": forecast or "取得不能",
        "actual": actual,
        "surprise": diff_text if actual_is_usable else "取得不能",
        "result_judgement": judgement(event, delta) if actual_is_usable else "判定不能",
        "initial_market_reaction": initial,
        "market_reaction_conclusion": conclusion,
        "reaction_type": reaction_type,
        "details": clean(event.get("resultExplanation")) or "詳細情報なし",
        "related_markets": event.get("focusMarkets") or event.get("affectedMarkets") or [],
        "source": {"name": clean(source.get("name")), "url": clean(source.get("url"))},
        "updated_at": clean(event.get("updatedAt")) or now.isoformat(timespec="seconds"),
    }


def build(now: datetime | None = None) -> dict[str, Any]:
    now = now or datetime.now(JST)
    payload = json.loads(SOURCE.read_text(encoding="utf-8"))
    records = [record for event in payload.get("events", []) if (record := make_record(event, now))]
    records.sort(key=lambda row: row["release_datetime_jst"], reverse=True)
    return {"schemaVersion": "1.0.0", "pageId": "completed-event-records",
            "generatedAt": now.isoformat(timespec="seconds"), "records": records}


def main() -> int:
    payload = build()
    OUTPUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"records": len(payload["records"]), "generatedAt": payload["generatedAt"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
