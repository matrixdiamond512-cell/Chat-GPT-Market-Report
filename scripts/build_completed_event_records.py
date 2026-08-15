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


def is_unemployment_claims(title: str) -> bool:
    lower = title.lower()
    return "失業保険" in title or "jobless claims" in lower or "unemployment claims" in lower


def is_unemployment_rate(title: str) -> bool:
    lower = title.lower()
    return "失業率" in title or "unemployment rate" in lower


def judgement(event: dict[str, Any], delta: float | None) -> str:
    if delta is None:
        return "判定不能"
    if abs(delta) < 1e-9:
        return "予想一致"
    category = clean(event.get("category"))
    title = clean(event.get("title"))
    if is_unemployment_claims(title) or is_unemployment_rate(title):
        return "上振れ（雇用弱）" if delta > 0 else "下振れ（雇用強）"
    if category == "inflation" or any(x in title for x in ("CPI", "PCE", "PPI", "物価")):
        return "上振れ（インフレ強）" if delta > 0 else "下振れ（インフレ鈍化）"
    if category == "employment" or any(x in title for x in ("雇用", "賃金")):
        return "上振れ（雇用強）" if delta > 0 else "下振れ（雇用弱）"
    if "GDP" in title or category == "growth":
        return "上振れ（景気強）" if delta > 0 else "下振れ（景気弱）"
    return "市場予想を上回る" if delta > 0 else "市場予想を下回る"


def next_day_implication(event: dict[str, Any], delta: float | None) -> str:
    """Return a restrained forward-looking implication only when the result/forecast comparison supports it."""
    if delta is None or abs(delta) < 1e-9:
        return ""

    title = clean(event.get("title"))
    lower = title.lower()
    category = clean(event.get("category"))
    country = clean(event.get("country"))

    if "原油在庫" in title or "crude oil inventories" in lower:
        if delta > 0:
            return "原油在庫が予想より多く、需給面ではWTIの上値を抑えやすい。翌日以降も在庫増が意識されるか、ガソリン・留出油在庫や生産量と合わせて確認。"
        return "原油在庫が予想より少なく、需給面ではWTIを支えやすい。翌日以降も在庫減少が継続するか、ガソリン・留出油在庫や生産量と合わせて確認。"

    if is_unemployment_claims(title):
        if delta > 0:
            return "失業保険申請件数の上振れは雇用の軟化を示し、利下げ期待を支えやすい。米金利・ドルの上値を抑え、金や金利敏感株には追い風になりやすいが、継続受給者数と次の雇用統計で確認。"
        return "失業保険申請件数の下振れは雇用の底堅さを示し、利下げ期待を後退させやすい。米金利・ドルを支え、金や金利敏感株には重荷になりやすいため、次の雇用統計で確認。"

    if is_unemployment_rate(title):
        if delta > 0:
            return "失業率の上振れは雇用の軟化を示し、利下げ期待を支えやすい。米金利・ドルには下押し要因、金や金利敏感株には支援材料になりやすい。"
        return "失業率の下振れは雇用の底堅さを示し、利下げ期待を後退させやすい。米金利・ドルの下支えになりやすく、金や金利敏感株には重荷。"

    if category == "inflation" or any(x in title for x in ("CPI", "PCE", "PPI", "物価")):
        if delta > 0:
            return "インフレ指標の上振れは利下げ期待を後退させやすく、翌日以降も金利高・ドル高圧力が残りやすい。株、とくに金利敏感なグロース株と金には逆風になりやすい。"
        return "インフレ指標の下振れは利下げ期待を支えやすく、翌日以降も米金利・ドルの上値を抑えやすい。金やグロース株には追い風になりやすいが、次の物価・雇用指標で確認。"

    if category == "employment" or any(x in title for x in ("雇用者数", "雇用統計", "賃金", "payroll", "employment change")):
        if delta > 0:
            return "雇用指標の上振れは景気の底堅さを示し、利下げ期待を後退させやすい。金利・ドルの下支えになりやすい一方、株は景気期待と金利上昇の綱引き。"
        return "雇用指標の下振れは労働市場の減速を示し、利下げ期待を支えやすい。金利・ドルには下押し要因だが、弱さが大きい場合は株に景気懸念が出るため次の雇用指標を確認。"

    growth_keywords = ("GDP", "小売売上高", "retail sales", "consumer sentiment", "consumer confidence", "PMI", "ISM")
    if category == "growth" or any(x.lower() in lower for x in growth_keywords):
        currency = "ポンド・英国金利" if country == "英国" else "ドル・米金利" if country == "米国" else "当該国通貨・金利"
        if delta > 0:
            return f"景気指標の上振れは景気の底堅さを示し、{currency}を支えやすい。翌日以降は金利上昇との綱引きになりやすく、次の景気・物価指標で持続性を確認。"
        return f"景気指標の下振れは景気減速を意識させ、{currency}の上値を抑えやすい。利下げ期待には追い風だが、弱さが続く場合は株に景気懸念が波及するため次の指標で確認。"

    rate_keywords = ("政策金利", "cash rate", "interest rate", "rate decision", "official bank rate")
    if any(x in lower for x in rate_keywords):
        if delta > 0:
            return "政策金利が予想より高く、金融政策は想定よりタカ派と受け止められやすい。翌日以降も当該国通貨・金利を支えやすく、声明と今後の利下げ・利上げ経路を確認。"
        return "政策金利が予想より低く、金融政策は想定よりハト派と受け止められやすい。翌日以降も当該国通貨・金利の上値を抑えやすく、声明と今後の政策経路を確認。"

    return ""


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
    initial, verified_conclusion, reaction_type = verified_reaction(event)
    implication = next_day_implication(event, delta) if actual_is_usable else ""
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
        "verified_market_reaction_conclusion": verified_conclusion,
        "market_reaction_conclusion": implication or verified_conclusion,
        "next_day_implication": implication,
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
    return {"schemaVersion": "1.1.0", "pageId": "completed-event-records",
            "generatedAt": now.isoformat(timespec="seconds"), "records": records}


def main() -> int:
    payload = build()
    OUTPUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"records": len(payload["records"]), "generatedAt": payload["generatedAt"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
