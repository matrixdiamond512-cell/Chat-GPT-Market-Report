from __future__ import annotations

import json
import math
import re
import urllib.request
from io import BytesIO
from datetime import date, datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "usdjpy-flow-summary.json"
CONFIG = ROOT / "data" / "usdjpy-supply-demand.json"
MARKET = ROOT / "data" / "market" / "latest.json"
RATES = ROOT / "data" / "rates-bonds.json"
VOLUME = ROOT / "data" / "usdjpy-volume.json"
JST = ZoneInfo("Asia/Tokyo")
CUSTOMS_INDEX = "https://www.customs.go.jp/toukei/shinbun/happyou.htm"
MOF_WEEK_PDF = "https://www.mof.go.jp/policy/international_policy/reference/itn_transactions_in_securities/week.pdf"


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


def fetch_bytes(url: str) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": "WEB-Market-Report/1.0"})
    with urllib.request.urlopen(request, timeout=25) as response:
        return response.read()


def pdf_text(content: bytes) -> str:
    from pypdf import PdfReader
    return "\n".join(page.extract_text() or "" for page in PdfReader(BytesIO(content)).pages)


def parse_trade_pdf(text: str, as_of: str = "") -> dict[str, Any]:
    rows: list[list[str]] = []
    for line in text.splitlines():
        values = re.findall(r"-?[\d,]+(?:\.\d+)?", line)
        if not rows and len(values) == 3 and "," in values[0]:
            rows.append(values)
        elif len(rows) == 1 and len(values) == 3 and "," in values[0]:
            rows.append(values)
        elif len(rows) == 2 and len(values) >= 2 and "," in values[0]:
            rows.append(values)
            break
    if len(rows) < 3:
        raise ValueError("貿易統計PDFの総額を解析できません")
    exports = int(rows[0][0].replace(",", ""))
    imports = int(rows[1][0].replace(",", ""))
    displayed_balance = abs(int(rows[2][0].replace(",", "")))
    balance = exports - imports
    if abs(abs(balance) - displayed_balance) > 2:
        raise ValueError("貿易収支の検算に失敗しました")
    return {"asOf": as_of, "exports": exports, "imports": imports, "balance": balance}


def parse_securities_pdf(text: str) -> dict[str, Any]:
    month_numbers = {name: idx for idx, name in enumerate(("January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"), 1)}
    period_matches = re.findall(r"[A-Z][a-z]+\s+\d{1,2},\s*-\s*([A-Z][a-z]+)\s+(\d{1,2}),\s+(\d{4})", text)
    numeric = re.compile(r"^\s*[\d,]+(?:\s+\*)?(?:\s+-?[\d,]+(?:\s+\*)?){9,}\s*$")
    outward_part, inward_part = text.split("2．対内証券投資", 1)
    outward_rows = [line for line in outward_part.splitlines() if numeric.match(line)]
    inward_rows = [line for line in inward_part.splitlines() if numeric.match(line)]
    if not period_matches or not outward_rows or not inward_rows:
        raise ValueError("証券投資PDFの週次合計を解析できません")
    end_month, end_day, year = period_matches[-1]
    def total(row: str) -> int:
        return int(re.findall(r"-?[\d,]+", row)[-1].replace(",", ""))
    return {"asOf": f"{int(year):04d}-{month_numbers[end_month]:02d}-{int(end_day):02d}", "outward": total(outward_rows[-1]), "inward": total(inward_rows[-1])}


def fetch_official_flows() -> tuple[dict[str, Any], dict[str, Any]]:
    html = fetch_bytes(CUSTOMS_INDEX).decode("utf-8", errors="replace")
    match = re.search(r'href=["\']([^"\']*/(\d{6}5\.pdf))["\']', html, re.I)
    if not match:
        raise ValueError("最新の月次貿易統計PDFが見つかりません")
    trade_url = urllib.request.urljoin(CUSTOMS_INDEX, match.group(1))
    file_period = re.search(r"(\d{4})(\d{2})5\.pdf", trade_url)
    trade_as_of = f"{file_period.group(1)}-{file_period.group(2)}" if file_period else ""
    trade = parse_trade_pdf(pdf_text(fetch_bytes(trade_url)), trade_as_of)
    trade["sourceUrl"] = trade_url
    securities = parse_securities_pdf(pdf_text(fetch_bytes(MOF_WEEK_PDF)))
    securities["sourceUrl"] = MOF_WEEK_PDF
    return trade, securities


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


def build_real(volume_payload: dict[str, Any], market_payload: dict[str, Any], now: datetime,
               trade: dict[str, Any] | None = None, securities: dict[str, Any] | None = None) -> dict[str, Any]:
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
    open_price, close_price = number(row.get("open")), number(row.get("close"))
    fix_move = ((close_price / open_price) - 1) * 100 if open_price and close_price else None
    fix_score = 0.5 if fix_move is not None and fix_move > 0.03 else -0.5 if fix_move is not None and fix_move < -0.03 else 0.0 if fix_move is not None else None
    trade = trade or {}
    trade_balance = number(trade.get("balance"))
    trade_score = 1.0 if trade_balance is not None and trade_balance < 0 else -1.0 if trade_balance is not None and trade_balance > 0 else 0.0 if trade_balance is not None else None
    securities = securities or {}
    outward = number(securities.get("outward"))
    inward = number(securities.get("inward"))
    outward_score = 0.5 if outward is not None and outward > 0 else -0.5 if outward is not None and outward < 0 else 0.0 if outward is not None else None
    inward_score = -0.5 if inward is not None and inward > 0 else 0.5 if inward is not None and inward < 0 else 0.0 if inward is not None else None
    capital_signal = outward - inward if outward is not None and inward is not None else None
    capital_score = 0.5 if capital_signal is not None and capital_signal > 0 else -0.5 if capital_signal is not None and capital_signal < 0 else 0.0 if capital_signal is not None else None
    official_status = "stale" if trade.get("_stale") else "verified"
    securities_status = "stale" if securities.get("_stale") else "verified"
    if official_status == "stale": trade_score = None
    if securities_status == "stale":
        outward_score = inward_score = capital_score = None
    generated = now.isoformat(timespec="seconds")
    drivers = [
        driver(id="tokyo_fix", name="仲値フロー（東京価格代理）", category="short_term_real_demand", score=fix_score,
               status="calculated" if fix_score is not None else "unavailable", as_of=str(row.get("targetDate") or ""), updated_at=str(volume_payload.get("generatedAt") or ""),
               value_text=(f"東京市場の始値→終値 {open_price:.2f}→{close_price:.2f}（{fix_move:+.2f}%）。仲値実額ではなく価格代理" if fix_score is not None else "東京市場価格を取得できません"),
               source_name="日本銀行 外国為替市況（日次）", source_url=str((volume_payload.get("data") or {}).get("sourceUrl") or ""), frequency="daily proxy"),
        driver(id="tokyo_volume", name="東京市場出来高", category="short_term_real_demand", score=volume_score,
               status=volume_status, as_of=str(row.get("targetDate") or ""), updated_at=str(volume_payload.get("generatedAt") or ""),
               value_text=volume_text, source_name="日本銀行 外国為替市況（日次）",
               source_url=str((volume_payload.get("data") or {}).get("sourceUrl") or ""), frequency="daily"),
        driver(id="goto_day", name="ゴトー日", category="short_term_real_demand", score=0.0, status="verified",
               as_of=today.isoformat(), updated_at=now.isoformat(timespec="seconds"),
               value_text=("該当（仲値反応未確認のため加点なし）" if is_gotobi else "非該当"), frequency="calendar"),
        driver(id="capital_flow", name="企業・資本フロー（公表値代理）", category="short_term_real_demand", score=capital_score,
               status="calculated" if capital_score is not None else securities_status if securities else "unavailable", as_of=str(securities.get("asOf") or ""), updated_at=generated,
               value_text=(f"対外－対内ネット {capital_signal:+,.0f}億円。企業の当日実額ではなく週次資本フロー代理（為替ヘッジ不明）" if capital_signal is not None else "週次証券投資を取得できません"),
               source_name="財務省 対外及び対内証券投資", source_url=str(securities.get("sourceUrl") or ""), frequency="weekly proxy"),
        driver(id="trade", name="貿易統計", category="structural_real_demand", score=trade_score,
               status=official_status if trade_balance is not None else "unavailable", as_of=str(trade.get("asOf") or ""), updated_at=generated,
               value_text=(f"輸出 {trade.get('exports', 0)/1_000_000:.2f}兆円／輸入 {trade.get('imports', 0)/1_000_000:.2f}兆円／収支 {trade_balance/100:.0f}億円（構造要因）" if trade_balance is not None else "財務省貿易統計を取得できません"),
               source_name="財務省 貿易統計", source_url=str(trade.get("sourceUrl") or CUSTOMS_INDEX), frequency="monthly"),
        driver(id="outward_securities", name="対外証券投資", category="structural_real_demand", score=outward_score,
               status=securities_status if outward is not None else "unavailable", as_of=str(securities.get("asOf") or ""), updated_at=generated,
               value_text=(f"合計 {outward:+,.0f}億円（取得超は外貨需要候補、為替ヘッジ不明）" if outward is not None else "財務省週次統計を取得できません"),
               source_name="財務省 対外及び対内証券投資", source_url=str(securities.get("sourceUrl") or MOF_WEEK_PDF), frequency="weekly"),
        driver(id="inward_securities", name="対内証券投資", category="structural_real_demand", score=inward_score,
               status=securities_status if inward is not None else "unavailable", as_of=str(securities.get("asOf") or ""), updated_at=generated,
               value_text=(f"合計 {inward:+,.0f}億円（取得超は円需要候補、為替ヘッジ不明）" if inward is not None else "財務省週次統計を取得できません"),
               source_name="財務省 対外及び対内証券投資", source_url=str(securities.get("sourceUrl") or MOF_WEEK_PDF), frequency="weekly"),
        driver(id="month_end", name="月末・期末", category="structural_real_demand", score=0.0, status="verified",
               as_of=today.isoformat(), updated_at=now.isoformat(timespec="seconds"),
               value_text=("月末該当（方向確認なし・加点なし）" if is_month_end else "月末非該当"), frequency="calendar"),
    ]
    verified = [item for item in drivers if item["status"] in {"verified", "calculated"} and item["score"] is not None]
    substantive = [item for item in verified if item["frequency"] != "calendar"]
    short = sum(item["score"] for item in verified if item["category"] == "short_term_real_demand")
    structural = sum(item["score"] for item in verified if item["category"] == "structural_real_demand")
    score = clip(short + structural) if len(substantive) >= 3 else None
    return {"score": score, "judgement": judgement(score), "shortTermScore": clip(short),
            "structuralScore": clip(structural), "verifiedCount": len(substantive),
            "confirmedCount": len(verified), "minimumRequired": 3, "drivers": drivers}


def build_speculative(config: dict[str, Any], now: datetime, market: dict[str, Any] | None = None,
                      rates: dict[str, Any] | None = None) -> dict[str, Any]:
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
    market = market or {}
    rates = rates or {}
    usd = ((market.get("markets") or {}).get("usdjpy") or {})
    usd_change = number(usd.get("changePercent"))
    rate_rows = rates.get("rates") or []
    us2 = next((x for x in rate_rows if x.get("name") == "米2年債利回り"), {})
    jp2 = next((x for x in rate_rows if x.get("name") == "日本2年国債利回り"), {})
    spread_change = None
    if number(us2.get("changeBp")) is not None and number(jp2.get("changeBp")) is not None:
        spread_change = number(us2.get("changeBp")) - number(jp2.get("changeBp"))
    reaction_score = None
    if usd_change is not None and spread_change is not None:
        price_sign = 1 if usd_change > 0.02 else -1 if usd_change < -0.02 else 0
        spread_sign = 1 if spread_change > 0.5 else -1 if spread_change < -0.5 else 0
        reaction_score = float(price_sign) if price_sign == spread_sign else 0.0
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
        driver(id="short_reaction", name="金利差と短期価格反応", category="speculative", score=reaction_score,
               status="calculated" if reaction_score is not None else "unavailable", as_of=str(usd.get("asOf") or ""), updated_at=str(usd.get("fetchedAt") or ""),
               value_text=(f"USD/JPY {usd_change:+.2f}%／米日2年金利変化差 {spread_change:+.1f}bp（同時反応の代理、因果断定なし）" if reaction_score is not None else "USD/JPYまたは米日2年金利の変化を取得できません"),
               source_name="市場価格・金利データ統合", source_url=str(usd.get("sourceUrl") or ""), frequency="daily proxy"),
    ]
    verified = [item for item in drivers if item["status"] in {"verified", "calculated"} and item["score"] is not None]
    score = clip(sum(item["score"] for item in verified)) if len(verified) >= 2 else None
    return {"score": score, "judgement": judgement(score), "verifiedCount": len(verified),
            "confirmedCount": len(verified), "minimumRequired": 2, "drivers": drivers}


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
    config, volume, market, rates = load(CONFIG), load(VOLUME), load(MARKET), load(RATES)
    trade: dict[str, Any] = {}
    securities: dict[str, Any] = {}
    fetch_error = ""
    try:
        trade, securities = fetch_official_flows()
    except Exception as exc:
        fetch_error = f"{type(exc).__name__}: {exc}"
        saved = previous.get("officialFlows") or {}
        trade = dict(saved.get("trade") or {})
        securities = dict(saved.get("securities") or {})
        if trade: trade["_stale"] = True
        if securities: securities["_stale"] = True
    real = build_real(volume, market, now, trade, securities)
    spec = build_speculative(config, now, market, rates)
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
        "officialFlows": {"trade": {k: v for k, v in trade.items() if k != "_stale"},
                          "securities": {k: v for k, v in securities.items() if k != "_stale"}},
        "diagnostics": {"officialFlowFetchError": fetch_error or None},
    }


def main() -> int:
    payload = build()
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"generatedAt": payload["generatedAt"], "real": payload["realDemand"]["score"],
                      "speculative": payload["speculative"]["score"], "combined": payload["combined"]["score"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
