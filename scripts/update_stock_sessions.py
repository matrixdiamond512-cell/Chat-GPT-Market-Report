#!/usr/bin/env python3
"""Update Tokyo-open and U.S.-premarket stock session snapshots.

Writes data/stock-sessions.json and mirrors sessionAnalysis into data/stocks.json.
Uses Yahoo Finance chart endpoints as a no-key quote source. Each session keeps its
own data date and update timestamp so Tokyo and U.S. data are never relabeled as
being from the same market day.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import sys
import time
from datetime import datetime, time as dtime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import quote
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
SESSIONS_PATH = DATA_DIR / "stock-sessions.json"
STOCKS_PATH = DATA_DIR / "stocks.json"
JST = ZoneInfo("Asia/Tokyo")
NY = ZoneInfo("America/New_York")
UA = "Mozilla/5.0 (compatible; MarketReportBot/1.0; +GitHubActions)"

TOKYO_SYMBOLS = {
    "nikkei": ("^N225", "日経225"),
    "topix": ("^TOPX", "TOPIX"),
    "usdjpy": ("JPY=X", "USD/JPY"),
    "nikkei_fut_ref": ("NIY=F", "日経225先物（CME参考）"),
}
US_FUTURES = {
    "sp": ("ES=F", "S&P500先物"),
    "nasdaq": ("NQ=F", "Nasdaq100先物"),
    "dow": ("YM=F", "Dow先物"),
    "russell": ("RTY=F", "Russell2000先物"),
    "vix": ("^VIX", "VIX"),
    "us10y": ("^TNX", "米10年債利回り"),
    "dxy": ("DX-Y.NYB", "ドル指数"),
    "usdjpy": ("JPY=X", "USD/JPY"),
    "gold": ("GC=F", "Gold"),
    "wti": ("CL=F", "WTI"),
    "btc": ("BTC-USD", "BTCUSD"),
}
MEGACAPS = ["NVDA", "MSFT", "AAPL", "AMZN", "META", "GOOGL", "TSLA", "AVGO"]


def now_jst() -> datetime:
    return datetime.now(timezone.utc).astimezone(JST)


def iso_jst(dt: datetime | None = None) -> str:
    dt = dt or now_jst()
    return dt.astimezone(JST).isoformat(timespec="seconds")


def finite(v: Any) -> float | None:
    try:
        x = float(v)
        return x if math.isfinite(x) else None
    except (TypeError, ValueError):
        return None


def fmt_num(v: float | None, decimals: int = 2) -> str:
    if v is None:
        return "取得不能"
    if abs(v) >= 1000:
        return f"{v:,.{decimals}f}"
    return f"{v:.{decimals}f}"


def fmt_pct(v: float | None) -> str:
    if v is None:
        return ""
    return f"{v:+.2f}%"


def pct(a: float | None, b: float | None) -> float | None:
    if a is None or b in (None, 0):
        return None
    return (a / b - 1.0) * 100.0


def load_json(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return default


def save_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def fetch_chart(symbol: str, *, interval: str = "1m", range_: str = "1d", retries: int = 3) -> dict[str, Any]:
    encoded = quote(symbol, safe="")
    url = (
        f"https://query1.finance.yahoo.com/v8/finance/chart/{encoded}"
        f"?interval={interval}&range={range_}&includePrePost=true&events=div%2Csplits"
    )
    last_error: Exception | None = None
    for attempt in range(retries):
        try:
            req = Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
            with urlopen(req, timeout=15) as resp:
                payload = json.load(resp)
            result = payload.get("chart", {}).get("result") or []
            if not result:
                raise RuntimeError(payload.get("chart", {}).get("error") or "empty chart result")
            return normalize_chart(symbol, result[0])
        except Exception as exc:
            last_error = exc
            if attempt + 1 < retries:
                time.sleep(1.5 * (attempt + 1))
    raise RuntimeError(f"{symbol}: {last_error}")


def normalize_chart(symbol: str, result: dict[str, Any]) -> dict[str, Any]:
    meta = result.get("meta") or {}
    stamps = result.get("timestamp") or []
    quote_block = ((result.get("indicators") or {}).get("quote") or [{}])[0]
    closes = quote_block.get("close") or []
    opens = quote_block.get("open") or []
    volumes = quote_block.get("volume") or []
    points = []
    for i, ts in enumerate(stamps):
        c = finite(closes[i]) if i < len(closes) else None
        o = finite(opens[i]) if i < len(opens) else None
        vol = finite(volumes[i]) if i < len(volumes) else None
        if c is None and o is None:
            continue
        points.append({"ts": int(ts), "open": o, "close": c, "volume": vol})
    last_close = next((p["close"] for p in reversed(points) if p["close"] is not None), None)
    prev = finite(meta.get("regularMarketPreviousClose"))
    if prev is None:
        prev = finite(meta.get("chartPreviousClose"))
    return {
        "symbol": symbol,
        "currency": meta.get("currency") or "",
        "exchangeTimezoneName": meta.get("exchangeTimezoneName") or "UTC",
        "regularMarketPrice": finite(meta.get("regularMarketPrice")),
        "previousClose": prev,
        "last": last_close if last_close is not None else finite(meta.get("regularMarketPrice")),
        "points": points,
    }


def point_dt(point: dict[str, Any], tz: ZoneInfo) -> datetime:
    return datetime.fromtimestamp(point["ts"], timezone.utc).astimezone(tz)


def points_for_date(chart: dict[str, Any], tz: ZoneInfo, date_iso: str) -> list[dict[str, Any]]:
    return [p for p in chart.get("points", []) if point_dt(p, tz).date().isoformat() == date_iso]


def metric(label: str, value: str, change: str = "", note: str = "") -> dict[str, str]:
    return {"label": label, "value": value, "change": change, "note": note}


def safe_fetch(symbol: str) -> tuple[dict[str, Any] | None, str | None]:
    try:
        return fetch_chart(symbol), None
    except Exception as exc:
        return None, str(exc)


def tokyo_snapshot(existing: dict[str, Any]) -> dict[str, Any]:
    now = now_jst()
    date_iso = now.date().isoformat()
    errors: list[str] = []
    charts: dict[str, dict[str, Any]] = {}
    for key, (symbol, _) in TOKYO_SYMBOLS.items():
        data, err = safe_fetch(symbol)
        if data:
            charts[key] = data
        elif err:
            errors.append(err)

    nikkei_today = points_for_date(charts.get("nikkei", {}), JST, date_iso)
    topix_today = points_for_date(charts.get("topix", {}), JST, date_iso)
    fx_today = points_for_date(charts.get("usdjpy", {}), JST, date_iso)

    def cash_session(points: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return [p for p in points if dtime(9, 0) <= point_dt(p, JST).time() <= dtime(15, 30)]

    n_session = cash_session(nikkei_today)
    t_session = cash_session(topix_today)
    n_open = next((p.get("open") or p.get("close") for p in n_session if p.get("open") is not None or p.get("close") is not None), None)
    n_last = next((p.get("close") for p in reversed(n_session) if p.get("close") is not None), None)
    t_open = next((p.get("open") or p.get("close") for p in t_session if p.get("open") is not None or p.get("close") is not None), None)
    t_last = next((p.get("close") for p in reversed(t_session) if p.get("close") is not None), None)
    n_prev = charts.get("nikkei", {}).get("previousClose")
    t_prev = charts.get("topix", {}).get("previousClose")

    fx_open = None
    fx_last = None
    fx_window = [p for p in fx_today if dtime(8, 55) <= point_dt(p, JST).time() <= dtime(15, 30)]
    if fx_window:
        fx_open = next((p.get("close") for p in fx_window if p.get("close") is not None), None)
        fx_last = next((p.get("close") for p in reversed(fx_window) if p.get("close") is not None), None)

    metrics: list[dict[str, str]] = []
    if n_last is not None:
        metrics.append(metric("日経225", fmt_num(n_last), fmt_pct(pct(n_last, n_prev)), f"寄り値 {fmt_num(n_open)} / ギャップ {fmt_pct(pct(n_open, n_prev))} / 寄り後 {fmt_pct(pct(n_last, n_open))}"))
    if t_last is not None:
        metrics.append(metric("TOPIX", fmt_num(t_last), fmt_pct(pct(t_last, t_prev)), f"寄り値 {fmt_num(t_open)} / ギャップ {fmt_pct(pct(t_open, t_prev))} / 寄り後 {fmt_pct(pct(t_last, t_open))}"))
    if fx_last is not None:
        metrics.append(metric("USD/JPY", fmt_num(fx_last, 3), fmt_pct(pct(fx_last, fx_open)), f"08:55以降の変化 / 08:55近辺 {fmt_num(fx_open, 3)}"))
    fut = charts.get("nikkei_fut_ref")
    if fut and fut.get("last") is not None:
        metrics.append(metric("日経225先物（CME参考）", fmt_num(fut["last"]), fmt_pct(pct(fut["last"], fut.get("previousClose"))), "CME参考値。大阪取引所先物とは別銘柄として表示"))

    has_open = bool(n_session or t_session)
    status = "東京寄り付きデータ取得済み" if has_open else "取得不能（東京現物の当日寄り付きデータなし／休場または時間外）"
    insights: list[str] = []
    if n_open is not None and n_last is not None:
        gap = pct(n_open, n_prev)
        follow = pct(n_last, n_open)
        if gap is not None and follow is not None:
            if gap > 0 and follow > 0:
                insights.append("日経225はギャップアップ後も買いが継続。寄り付きの強さが維持されています。")
            elif gap > 0 and follow < 0:
                insights.append("日経225は高寄り後に失速。寄り天リスクを優先して確認します。")
            elif gap < 0 and follow < 0:
                insights.append("日経225はギャップダウン後も売りが継続。リスクオフの持続を確認します。")
            elif gap < 0 and follow > 0:
                insights.append("日経225は安寄り後に切り返し。悪材料の織り込み進展・買い戻しの可能性を確認します。")
    if n_last is not None and t_last is not None:
        n_chg, t_chg = pct(n_last, n_prev), pct(t_last, t_prev)
        if n_chg is not None and t_chg is not None:
            if n_chg > 0 and t_chg > 0:
                insights.append("日経225とTOPIXが同方向で、市場全体の方向は比較的整合的です。")
            elif n_chg * t_chg < 0:
                insights.append("日経225とTOPIXが逆方向。指数寄与度の偏りやセクターローテーションに注意します。")
    if fx_open is not None and fx_last is not None:
        fxc = pct(fx_last, fx_open)
        if fxc is not None:
            insights.append(f"USD/JPYは08:55以降 {fmt_pct(fxc)}。日本株の外需・先物方向との整合性を確認します。")
    if not insights:
        insights.append("当日寄り付きの1分足が取得できていないため、前日終値を寄り付きデータとして代用しません。")

    judgement = "寄り後15分の方向と日経225/TOPIXの一致を優先。高寄り・安寄りだけでは方向判定しません。"
    if has_open and n_open is not None and n_last is not None:
        follow = pct(n_last, n_open)
        if follow is not None and follow >= 0.15:
            judgement = "寄り後も買い優勢。先物・USD/JPY・TOPIXが追随する限り、東京時間は上方向を優先します。"
        elif follow is not None and follow <= -0.15:
            judgement = "寄り後は売り優勢。高寄りでも上昇継続とは見なさず、寄り天警戒を優先します。"

    return {
        "title": "東京市場 朝の寄り付き分析",
        "flag": "JP",
        "status": status,
        "dataDate": date_iso,
        "updatedAt": iso_jst(now),
        "source": "Yahoo Finance chart API（指数・FX・CME参考先物）",
        "metrics": metrics,
        "insights": insights,
        "judgement": judgement,
        "errors": errors[:6],
    }


def us_snapshot(existing: dict[str, Any]) -> dict[str, Any]:
    now = now_jst()
    now_ny = now.astimezone(NY)
    date_iso = now_ny.date().isoformat()
    errors: list[str] = []
    charts: dict[str, dict[str, Any]] = {}
    for key, (symbol, _) in US_FUTURES.items():
        data, err = safe_fetch(symbol)
        if data:
            charts[key] = data
        elif err:
            errors.append(err)

    metrics: list[dict[str, str]] = []
    for key in ["sp", "nasdaq", "dow", "russell", "vix", "us10y", "dxy", "usdjpy"]:
        data = charts.get(key)
        if not data or data.get("last") is None:
            continue
        label = US_FUTURES[key][1]
        decimals = 3 if key == "usdjpy" else 2
        value = fmt_num(data["last"], decimals)
        if key == "us10y":
            value += "%"
        metrics.append(metric(label, value, fmt_pct(pct(data["last"], data.get("previousClose"))), "前日通常取引終値比"))

    movers = []
    for symbol in MEGACAPS:
        data, err = safe_fetch(symbol)
        if err:
            errors.append(err)
            continue
        if not data:
            continue
        pts = points_for_date(data, NY, date_iso)
        pre = [p for p in pts if dtime(4, 0) <= point_dt(p, NY).time() < dtime(9, 30)]
        pre_last = next((p.get("close") for p in reversed(pre) if p.get("close") is not None), None)
        if pre_last is None:
            continue
        change = pct(pre_last, data.get("previousClose"))
        vol = sum(int(p.get("volume") or 0) for p in pre)
        movers.append({"symbol": symbol, "price": pre_last, "changePct": change, "volume": vol})

    movers.sort(key=lambda x: abs(x.get("changePct") or 0), reverse=True)
    insights: list[str] = []
    if movers:
        top = movers[:5]
        text = " / ".join(f"{x['symbol']} {fmt_pct(x['changePct'])}（出来高 {x['volume']:,}）" for x in top)
        insights.append("大型テック・主要株プレマーケット: " + text)
    else:
        insights.append("大型テックの当日プレマーケット1分足は取得不能（休場・時間外を含む）。通常取引終値で代用しません。")

    sp = charts.get("sp")
    nq = charts.get("nasdaq")
    ten = charts.get("us10y")
    if sp and nq:
        spc, nqc = pct(sp.get("last"), sp.get("previousClose")), pct(nq.get("last"), nq.get("previousClose"))
        if spc is not None and nqc is not None:
            if spc > 0 and nqc > 0:
                insights.append("S&P500先物とNasdaq100先物はともにプラス圏。NY寄り前の株式センチメントはリスクオン寄りです。")
            elif spc < 0 and nqc < 0:
                insights.append("S&P500先物とNasdaq100先物はともにマイナス圏。NY寄り前はリスクオフ寄りです。")
            else:
                insights.append("S&P500先物とNasdaq100先物が逆方向。大型テック偏重またはローテーションを確認します。")
    if ten and ten.get("last") is not None:
        insights.append(f"米10年債利回り {fmt_num(ten['last'])}%（前日比 {fmt_pct(pct(ten['last'], ten.get('previousClose')))}）。株先物との整合性を確認します。")

    is_premarket = dtime(4, 0) <= now_ny.time() < dtime(9, 30) and now_ny.weekday() < 5
    status = "米国プレマーケットデータ取得済み" if is_premarket and movers else "取得不能（当日プレマーケット時間外・休場、または株価データなし）"
    judgement = "指数先物・米金利・ドル・大型テックのプレマーケット出来高を組み合わせて判断します。"
    if sp and nq:
        spc, nqc = pct(sp.get("last"), sp.get("previousClose")), pct(nq.get("last"), nq.get("previousClose"))
        if spc is not None and nqc is not None:
            if spc >= 0.25 and nqc >= 0.25:
                judgement = "米株先物は明確に上方向。米金利急騰が伴わない限り、NY寄りはリスクオン継続を優先します。"
            elif spc <= -0.25 and nqc <= -0.25:
                judgement = "米株先物は明確に下方向。大型テックも追随する場合はNY寄りのリスクオフを優先します。"

    return {
        "title": "米国市場 プレマーケット分析",
        "flag": "US",
        "status": status,
        "dataDate": date_iso,
        "updatedAt": iso_jst(now),
        "source": "Yahoo Finance chart API（指数先物・金利・FX・大型株）",
        "metrics": metrics,
        "premarketMovers": movers[:8],
        "insights": insights,
        "judgement": judgement,
        "errors": errors[:10],
    }


def stock_row(stocks: dict[str, Any], market: str, pattern: str) -> list[Any] | None:
    rows = ((stocks.get("marketInternals") or {}).get(market) or {}).get("rows") or []
    for row in rows:
        if row and pattern.lower() in str(row[0]).lower():
            return row
    return None


def build_bridge(stocks: dict[str, Any], sessions: dict[str, Any]) -> dict[str, Any]:
    tokyo = sessions.get("tokyoOpen") or {}
    uspre = sessions.get("usPremarket") or {}
    sp_row = stock_row(stocks, "us", "S&P500")
    nas_row = stock_row(stocks, "us", "Nasdaq")

    def metric_text(session: dict[str, Any], label_contains: str) -> str:
        for m in session.get("metrics") or []:
            if label_contains.lower() in str(m.get("label", "")).lower():
                c = m.get("change") or ""
                return f"{m.get('label')} {m.get('value')} {c}".strip()
        return "取得不能"

    tokyo_text = f"{tokyo.get('dataDate','取得不能')} / {metric_text(tokyo, '日経225')} / {metric_text(tokyo, 'TOPIX')}"
    uspre_text = f"{uspre.get('dataDate','取得不能')} / {metric_text(uspre, 'S&P500先物')} / {metric_text(uspre, 'Nasdaq100先物')}"
    usclose_text = " / ".join([
        f"S&P500 {sp_row[2]}" if sp_row and len(sp_row) > 2 else "S&P500 取得不能",
        f"Nasdaq {nas_row[2]}" if nas_row and len(nas_row) > 2 else "Nasdaq 取得不能",
    ])

    conclusion = "東京寄り付きと米国プレマーケットの方向が同じかを確認し、NY通常取引へ引き継がれるかを判定します。"
    t_n = next((m for m in tokyo.get("metrics") or [] if m.get("label") == "日経225"), None)
    u_s = next((m for m in uspre.get("metrics") or [] if m.get("label") == "S&P500先物"), None)
    if t_n and u_s:
        def sign(text: str) -> int:
            text = str(text or "")
            if text.startswith("+"):
                return 1
            if text.startswith("-") or text.startswith("−"):
                return -1
            return 0
        a, b = sign(t_n.get("change")), sign(u_s.get("change"))
        if a and b and a == b:
            conclusion = "東京市場と米国株先物の方向が一致。日米で同じリスク選好が引き継がれている可能性が高まっています。"
        elif a and b and a != b:
            conclusion = "東京市場と米国株先物の方向が逆転。欧州時間の金利・為替・ニュースで市場テーマが変化した可能性を優先して確認します。"

    return {
        "title": "日米市場の引き継ぎ分析",
        "steps": [
            {"label": "東京市場", "text": tokyo_text},
            {"label": "米国プレマーケット", "text": uspre_text},
            {"label": "米国通常市場（直近終値）", "text": usclose_text},
        ],
        "conclusion": conclusion,
    }


def decide_mode(requested: str) -> str:
    if requested != "auto":
        return requested
    now = now_jst()
    hm = now.hour * 60 + now.minute
    if 8 * 60 + 45 <= hm <= 10 * 60:
        return "tokyo"
    if 20 * 60 <= hm <= 21 * 60 + 20:
        return "us"
    return "both"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["auto", "tokyo", "us", "both"], default=os.getenv("STOCK_SESSION_MODE", "auto"))
    args = parser.parse_args()
    mode = decide_mode(args.mode)

    stocks = load_json(STOCKS_PATH, {})
    stored = load_json(SESSIONS_PATH, {"schemaVersion": "1.0.0", "pageId": "stock-sessions", "sessionAnalysis": {}})
    sessions = stored.setdefault("sessionAnalysis", {})

    if mode in ("tokyo", "both"):
        sessions["tokyoOpen"] = tokyo_snapshot(sessions.get("tokyoOpen") or {})
    if mode in ("us", "both"):
        sessions["usPremarket"] = us_snapshot(sessions.get("usPremarket") or {})

    sessions["bridge"] = build_bridge(stocks, sessions)
    stored["schemaVersion"] = "1.1.0"
    stored["pageId"] = "stock-sessions"
    stored["updatedAt"] = iso_jst()
    stored["updateMode"] = mode
    stored["sourcePolicy"] = "セッション別に基準日・取得時刻を保持。前日終値で当日寄り付き/プレマーケットを代用しない。"
    save_json(SESSIONS_PATH, stored)

    if isinstance(stocks, dict) and stocks:
        stocks["sessionAnalysis"] = sessions
        stocks["sessionDataUpdatedAt"] = stored["updatedAt"]
        save_json(STOCKS_PATH, stocks)

    print(json.dumps({
        "ok": True,
        "mode": mode,
        "updatedAt": stored["updatedAt"],
        "tokyoStatus": (sessions.get("tokyoOpen") or {}).get("status"),
        "usStatus": (sessions.get("usPremarket") or {}).get("status"),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
