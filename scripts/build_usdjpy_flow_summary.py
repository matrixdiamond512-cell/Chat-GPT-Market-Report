from __future__ import annotations

import json
import math
from datetime import date, datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "usdjpy-flow-summary.json"
CONFIG = ROOT / "data" / "usdjpy-supply-demand.json"
MARKET = ROOT / "data" / "market" / "latest.json"
VOLUME = ROOT / "data" / "usdjpy-volume.json"
JST = ZoneInfo("Asia/Tokyo")


def load(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except Exception:
        return {}


def number(value: Any) -> float | None:
    try:
        parsed = float(value)
        return parsed if math.isfinite(parsed) else None
    except (TypeError, ValueError):
        return None


def clip(value: float) -> float:
    return float(max(-5, min(5, round(value))))


def direction(score: float | None) -> str:
    if score is None:
        return "unknown"
    if score > 0:
        return "usd_buy"
    if score < 0:
        return "usd_sell"
    return "neutral"


def driver(*, id: str, name: str, category: str, score: float | None, status: str,
           as_of: str = "", updated_at: str = "", value_text: str = "",
           source_name: str = "", source_url: str = "", frequency: str = "") -> dict[str, Any]:
    return {
        "id": id, "name": name, "category": category, "direction": direction(score),
        "score": score, "status": status, "asOf": as_of, "updatedAt": updated_at,
        "valueText": value_text, "sourceName": source_name, "sourceUrl": source_url,
        "frequency": frequency,
    }


def judgement(score: float | None, combined: bool = False) -> str:
    if score is None:
        return "判定保留"
    suffix = "優勢" if combined else ""
    if score >= 4:
        return f"強いドル買い{suffix}"
    if score >= 2:
        return f"ややドル買い{suffix}"
    if score <= -4:
        return f"強いドル売り{suffix}"
    if score <= -2:
        return f"ややドル売り{suffix}"
    return "中立"


def latest_volume(payload: dict[str, Any]) -> dict[str, Any]:
    rows = ((payload.get("data") or {}).get("records") or [])
    return rows[0] if rows and isinstance(rows[0], dict) else {}


def build_real(volume_payload: dict[str, Any], now: datetime) -> dict[str, Any]:
    row = latest_volume(volume_payload)
    price_change = number(row.get("priceChangePct"))
    vs_average = number(row.get("vs20Pct"))
    volume_score = None
    volume_status = "unavailable"
    volume_text = "価格方向と出来高の組み合わせを取得不能"
    if price_change is not None and vs_average is not None and volume_payload.get("status") == "ok":
        volume_status = "verified"
        if abs(price_change) < 0.01:
            volume_score = 0.0
        else:
            strength = 1.0 if vs_average >= 0 else 0.5
            volume_score = strength if price_change > 0 else -strength
        volume_text = f"価格 {price_change:+.2f}%／20日平均比 {vs_average:+.2f}%（方向は価格と併用）"

    today = now.date()
    last_day = (date(today.year + (today.month == 12), 1 if today.month == 12 else today.month + 1, 1) - date.resolution).day
    is_gotobi = today.day in {5, 10, 15, 20, 25, last_day}
    is_month_end = today.day == last_day
    drivers = [
        driver(id="tokyo_fix", name="仲値フロー", category="short_term_real_demand", score=None,
               status="unavailable", value_text="時刻別価格を取得できないため判定しません", frequency="intraday"),
        driver(id="tokyo_volume", name="東京市場出来高", category="short_term_real_demand", score=volume_score,
               status=volume_status, as_of=str(row.get("targetDate") or ""), updated_at=str(volume_payload.get("generatedAt") or ""),
               value_text=volume_text, source_name="日本銀行 外国為替市況（日次）",
               source_url=str((volume_payload.get("data") or {}).get("sourceUrl") or ""), frequency="daily"),
        driver(id="goto_day", name="ゴトー日", category="short_term_real_demand", score=0.0, status="verified",
               as_of=today.isoformat(), updated_at=now.isoformat(timespec="seconds"),
               value_text=("該当（仲値反応未確認のため加点なし）" if is_gotobi else "非該当"), frequency="calendar"),
        driver(id="capital_flow", name="当日企業・資本フロー", category="short_term_real_demand", score=None,
               status="unavailable", value_text="確認済み公開データなし", frequency="event"),
        driver(id="trade", name="貿易統計", category="structural_real_demand", score=None,
               status="unavailable", value_text="自動取得未接続（当日方向には代用しません）", frequency="monthly"),
        driver(id="outward_securities", name="対外証券投資", category="structural_real_demand", score=None,
               status="unavailable", value_text="自動取得未接続（為替ヘッジ不明）", frequency="weekly"),
        driver(id="inward_securities", name="対内証券投資", category="structural_real_demand", score=None,
               status="unavailable", value_text="自動取得未接続（為替ヘッジ不明）", frequency="weekly"),
        driver(id="month_end", name="月末・期末", category="structural_real_demand", score=0.0, status="verified",
               as_of=today.isoformat(), updated_at=now.isoformat(timespec="seconds"),
               value_text=("月末該当（方向確認なし・加点なし）" if is_month_end else "月末非該当"), frequency="calendar"),
    ]
    verified = [item for item in drivers if item["status"] == "verified" and item["score"] is not None]
    short = sum(item["score"] for item in verified if item["category"] == "short_term_real_demand")
    structural = sum(item["score"] for item in verified if item["category"] == "structural_real_demand")
    score = clip(short + structural) if len(verified) >= 3 else None
    return {"score": score, "judgement": judgement(score), "shortTermScore": clip(short),
            "structuralScore": clip(structural), "verifiedCount": len(verified), "drivers": drivers}


def build_speculative(config: dict[str, Any], now: datetime) -> dict[str, Any]:
    cftc = config.get("cftc") or {}
    try:
        cftc_age = (now.date() - date.fromisoformat(str(cftc.get("asOf") or ""))).days
    except ValueError:
        cftc_age = None
    cftc_status = (
        "verified" if cftc.get("status") == "verified" and cftc_age is not None and cftc_age <= 7
        else "stale" if cftc else "unavailable"
    )
    delta = number(cftc.get("netChange"))
    cftc_score = None
    if cftc_status == "verified" and delta is not None:
        magnitude = 2.0 if abs(delta) >= 100000 else 1.5 if abs(delta) >= 50000 else 1.0 if abs(delta) >= 20000 else 0.5 if abs(delta) >= 5000 else 0.0
        cftc_score = -magnitude if delta > 0 else magnitude if delta < 0 else 0.0

    tw = config.get("tradersWebFx") or {}
    levels = tw.get("keyLevels") or {}
    tw_verified = tw.get("status") == "confirmed"
    buys = levels.get("buyOrders") or []
    sells = levels.get("sellOrders") or []
    imbalance = len(buys) - len(sells)
    order_score = max(-1.0, min(1.0, imbalance * 0.5)) if tw_verified else None
    stops = levels.get("stops") or []
    stop_score = 0.0 if tw_verified and stops else None
    option = levels.get("optionAnalysis") or {}
    option_score = 0.0 if tw_verified and option.get("status") == "calculated" else None
    updated = str(tw.get("sourceUpdatedAt") or "")
    source_url = str(tw.get("url") or "")
    drivers = [
        driver(id="cftc", name="CFTC円先物", category="speculative", score=cftc_score, status=cftc_status,
               as_of=str(cftc.get("asOf") or ""), updated_at=str(cftc.get("checkedAt") or config.get("generatedAt") or ""),
               value_text=(f"円Net前週比 {delta:+,.0f}枚（USD/JPY方向へ符号反転）" + (f"／基準日から{cftc_age}日" if cftc_age is not None else "") if delta is not None else "前週比取得不能"),
               source_name=str(cftc.get("name") or "CFTC"), source_url=str(cftc.get("url") or ""), frequency="weekly"),
        driver(id="orders", name="オーダー", category="speculative", score=order_score,
               status="verified" if tw_verified else "stale" if tw else "unavailable", as_of=str(tw.get("sourceDate") or ""),
               updated_at=updated, value_text=(f"買い注文帯 {len(buys)}／売り注文帯 {len(sells)}（潜在需給）" if tw_verified else "確認不能"),
               source_name="Traders Web FX", source_url=source_url, frequency="intraday"),
        driver(id="stops", name="ストップ", category="speculative", score=stop_score,
               status="verified" if stop_score is not None else "unavailable", as_of=str(tw.get("sourceDate") or ""), updated_at=updated,
               value_text=(f"トリガー候補 {len(stops)}件（現方向への加点なし）" if stop_score is not None else "確認不能"),
               source_name="Traders Web FX", source_url=source_url, frequency="intraday"),
        driver(id="options", name="オプション・NYカット", category="speculative", score=option_score,
               status="verified" if option_score is not None else "unavailable", as_of=str(tw.get("sourceDate") or ""), updated_at=updated,
               value_text=(str(option.get("headline") or "方向保証なし・位置関係のみ確認") if option_score is not None else "確認不能"),
               source_name="Traders Web FX", source_url=source_url, frequency="intraday"),
        driver(id="short_reaction", name="金利と短期価格反応", category="speculative", score=None,
               status="unavailable", value_text="反応の因果確認データなし", frequency="intraday"),
    ]
    verified = [item for item in drivers if item["status"] == "verified" and item["score"] is not None]
    score = clip(sum(item["score"] for item in verified)) if len(verified) >= 2 else None
    return {"score": score, "judgement": judgement(score), "verifiedCount": len(verified), "drivers": drivers}


def relationship(real: float | None, spec: float | None) -> tuple[str, str]:
    if real is None or spec is None:
        return "判定保留", "実需または投機の確認済みカテゴリーが不足しているため、総合判定を保留します。"
    rd, sd = direction(real), direction(spec)
    if rd == "usd_buy" and sd == "usd_buy":
        return "一致", "実需・投機ともドル買い方向。需給の方向が一致しており、上昇方向の継続性が高まりやすい。"
    if rd == "usd_sell" and sd == "usd_sell":
        return "一致", "実需・投機ともドル売り方向。需給の方向が一致しており、下落方向の継続性が高まりやすい。"
    if rd == "usd_buy" and sd == "usd_sell":
        return "逆行", "実需はドル買い、投機はドル売り。実需が下値を支える一方、投機の戻り売りが上値を抑えやすい。"
    if rd == "usd_sell" and sd == "usd_buy":
        return "逆行", "投機はドル買い、実需はドル売り。短期上昇しても実需売りが上値を抑える可能性がある。"
    if rd == "neutral" and sd != "neutral":
        return "片側中立", f"実需は中立、投機は{'ドル買い' if sd == 'usd_buy' else 'ドル売り'}。現在は投機フローが価格形成を主導。"
    if sd == "neutral" and rd != "neutral":
        return "片側中立", f"投機は中立、実需は{'ドル買い' if rd == 'usd_buy' else 'ドル売り'}。現在は実需フローを優先して確認。"
    return "中立", "実需・投機とも中立圏で、確認済みフローに明確な方向差はありません。"


def session_comment(now: datetime) -> str:
    hour = now.hour
    if 7 <= hour < 15:
        return "東京時間は実需フローを優先監視。"
    if 15 <= hour < 21:
        return "ロンドン時間は投機・金利・ストップを優先監視。"
    return "NY時間は米金利・米指標・オプション・NYカット・ストップを優先監視。"


def build(now: datetime | None = None) -> dict[str, Any]:
    now = now or datetime.now(JST)
    previous = load(OUT)
    config, volume = load(CONFIG), load(VOLUME)
    real, spec = build_real(volume, now), build_speculative(config, now)
    combined_score = clip(real["score"] + spec["score"]) if real["score"] is not None and spec["score"] is not None else None
    rel, comment = relationship(real["score"], spec["score"])
    if real["score"] is None or spec["score"] is None:
        leader = "保留"
    elif abs(real["score"]) > abs(spec["score"]):
        leader = "実需"
    elif abs(spec["score"]) > abs(real["score"]):
        leader = "投機"
    else:
        leader = "拮抗"
    previous_scores = {
        "realDemand": (previous.get("realDemand") or {}).get("score"),
        "speculative": (previous.get("speculative") or {}).get("score"),
        "combined": (previous.get("combined") or {}).get("score"),
        "generatedAt": previous.get("generatedAt"),
    } if previous else None
    return {
        "schemaVersion": "1.0.0", "pageId": "usdjpy-flow-summary",
        "generatedAt": now.isoformat(timespec="seconds"), "status": "ok",
        "realDemand": real, "speculative": spec,
        "combined": {"score": combined_score, "judgement": judgement(combined_score, True),
                     "leadingFlow": leader, "relationship": rel, "sessionComment": session_comment(now), "comment": comment},
        "previous": previous_scores,
    }


def main() -> int:
    payload = build()
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"generatedAt": payload["generatedAt"], "real": payload["realDemand"]["score"],
                      "speculative": payload["speculative"]["score"], "combined": payload["combined"]["score"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
