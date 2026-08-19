from __future__ import annotations

import datetime as dt
import json
import re
from pathlib import Path

from reconcile_latest_report_market_data import reconcile_report_market_data

ROOT = Path(__file__).resolve().parents[1]
LATEST = ROOT / "data/latest-report.json"
MARKET_SNAPSHOT = ROOT / "data/market/latest.json"
DASHBOARD = ROOT / "data/dashboard.json"
REPORTS_DIR = ROOT / "reports"
JST = dt.timezone(dt.timedelta(hours=9))
SOP_ENFORCE_FROM = "2026-08-13"
SOP_SLOTS = {"08:00", "12:00", "16:00", "21:00"}


def load_json(path: Path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default


def dump_json(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def normalize_heading(line: str) -> str:
    text = str(line or "").strip()
    m = re.match(r"^【\s*(.+?)\s*】$", text)
    if m:
        return m.group(1).strip()
    m = re.match(r"^\s*(?:第?\d{1,2}|[一二三四五六七八九十]+)\s*[．.、)）]\s*(.+?)\s*$", text)
    if m:
        return m.group(1).strip()
    return ""


def sop_headings(full_text: str) -> list[str]:
    return [h for line in str(full_text or "").replace("\r", "").split("\n") if (h := normalize_heading(line))]


def has_structured_value(report: dict, fields: tuple[str, ...]) -> bool:
    for field in fields:
        value = report.get(field)
        if isinstance(value, str) and value.strip():
            continue
        if isinstance(value, (list, dict)) and value:
            continue
        return False
    return True


def require_semantic_section(
    report: dict,
    headings: list[str],
    pattern: str,
    label: str,
    fields: tuple[str, ...] = (),
) -> None:
    if any(re.search(pattern, h) for h in headings):
        return
    if fields and has_structured_value(report, fields):
        return
    raise SystemExit(f"SOP fullText missing required section: {label}")


def _lines(value) -> list[str]:
    if isinstance(value, list):
        return [str(x).strip() for x in value if str(x).strip()]
    if isinstance(value, str) and value.strip():
        return [value.strip()]
    return []


def ensure_public_full_text(report: dict) -> None:
    """Build a readable portal body when upstream accidentally sends only a stub.

    The structured report fields remain the source. This is a publication fail-safe:
    it never invents prices or market facts, and it only activates when fullText is
    clearly too short to satisfy the established SOP.
    """
    current = str(report.get("fullText") or report.get("rawText") or report.get("body") or "").replace("\r", "").strip()
    if len(current) >= 1200:
        report["fullText"] = current
        return

    title = str(report.get("title") or "").strip()
    theme = str(report.get("theme") or "").strip()
    leading = str(report.get("leadingMarket") or "").strip()
    main_scenario = str(report.get("mainScenario") or "").strip()
    alt_scenario = str(report.get("alternativeScenario") or "").strip()
    breaks = str(report.get("breakConditions") or "").strip()

    sections: list[str] = [title] if title else []
    sections += ["【08:00結論】", main_scenario or theme or "構造化データに基づく市場判断。"]
    sections += ["【今日の相場テーマ】", theme or "構造化データ参照。"]

    changes = _lines(report.get("changes"))
    sections += ["【前回からの変化】"] + (["・" + x for x in changes] if changes else ["・構造化データ参照。"])

    table = report.get("marketDataTable") or {}
    rows = table.get("rows") if isinstance(table, dict) else []
    sections += ["【主要市場データ】"]
    if isinstance(rows, list) and rows:
        for row in rows:
            if not isinstance(row, dict):
                continue
            label = str(row.get("label") or row.get("item") or row.get("name") or "").strip()
            value = str(row.get("value") or "").strip()
            change = str(row.get("change") or "").strip() or "—"
            rate = str(row.get("rate") or row.get("changePercent") or "").strip() or "—"
            direction = str(row.get("direction") or "").strip() or "—"
            sections.append(f"{label}｜{value}｜{change}｜{rate}｜{direction}")

    consistency = _lines(report.get("consistency"))
    sections += ["【材料と値動きの整合性】"] + (["・" + x for x in consistency] if consistency else ["・構造化データ参照。"])
    sections += ["【今日の主導市場】", leading or "構造化データ参照。"]

    news = _lines(report.get("news"))
    sections += ["【重要ニュース】"] + (["・" + x for x in news] if news else ["・構造化データ参照。"])

    flows = _lines(report.get("crossAssetFlow"))
    sections += ["【クロスアセット資金フロー】"] + (["・" + x for x in flows] if flows else ["・構造化データ参照。"])

    positioning = _lines(report.get("positioning"))
    sections += ["【需給・ポジション】"] + (["・" + x for x in positioning] if positioning else ["・構造化データ参照。"])

    events = _lines(report.get("events"))
    sections += ["【今後の重要イベント】"] + (["・" + x for x in events] if events else ["・構造化データ参照。"])

    sections += ["【個別市場見通し】"]
    markets = report.get("markets")
    if isinstance(markets, list) and markets:
        for market in markets:
            if not isinstance(market, dict):
                continue
            name = str(market.get("name") or "").strip()
            direction = str(market.get("direction") or "").strip()
            price = str(market.get("price") or "").strip()
            outlook = str(market.get("outlook") or "").strip()
            sections.append(f"{name}：{direction}。{price}。{outlook}".strip())

    sections += ["【シナリオ】"]
    if main_scenario:
        sections.append("メイン：" + main_scenario)
    if alt_scenario:
        sections.append("代替：" + alt_scenario)

    sections += ["【シナリオが崩れる条件】", breaks or "構造化データ参照。"]

    handover = _lines(report.get("handover"))
    sections += ["【東京時間への引き継ぎ】"] + (["・" + x for x in handover] if handover else ["・構造化データ参照。"])
    sections += ["【最終判断】", main_scenario or theme or "構造化データに基づく市場判断。"]
    report["fullText"] = "\n".join(x for x in sections if str(x).strip()).strip()


def sanitize_public_full_text(report: dict) -> None:
    """Remove internal pipeline diagnostics from the public report body."""
    text = str(report.get("fullText") or "").replace("\r", "")
    if not text:
        return
    pattern = re.compile(r"\n*【(?:\d{2}:\d{2}\s*)?データ検証】\s*\n.*?(?=\n【[^\n]+】)", re.S)
    text = pattern.sub("\n", text, count=1)
    text = re.sub(r"\bverified\b", "検証済み", text, flags=re.I)
    report["fullText"] = text.strip()


def validate_sop_body(report: dict) -> None:
    date = str(report.get("date") or "")
    slot = str(report.get("time") or "")
    if date < SOP_ENFORCE_FROM or slot not in SOP_SLOTS:
        return

    full_text = str(report.get("fullText") or report.get("rawText") or report.get("body") or "").replace("\r", "").strip()
    if len(full_text) < 1200:
        raise SystemExit(f"{slot} SOP fullText is too short to be a complete report: {len(full_text)} chars")

    headings = sop_headings(full_text)
    if len(headings) < 9:
        raise SystemExit(f"{slot} SOP fullText requires multiple explicit sections; found {len(headings)}")

    requirements = [
        (r"今日の相場テーマ", "今日の相場テーマ", ("theme",)),
        (r"主要市場データ|主要市場まとめ", "主要市場データ", ("marketDataTable",)),
        (r"材料と値動きの整合性|価格の動きと材料の整合性", "材料と値動きの整合性", ("consistency",)),
        (r"(?:今日の)?主導市場|どの市場が主導", "主導市場", ("leadingMarket",)),
        (r"重要ニュース|重要ニュースと市場への伝播|昨夜のNY市場で何が起きたか", "重要ニュース", ("news",)),
        (r"クロスアセット資金フロー", "クロスアセット資金フロー", ("crossAssetFlow",)),
        (r"需給・ポジション", "需給・ポジション", ("positioning",)),
        (r"個別(?:市場)?見通し|6市場の(?:個別)?見通し", "個別市場見通し", ("markets",)),
        (r"シナリオ", "シナリオ", ("mainScenario", "alternativeScenario")),
        (r"崩れる条件", "シナリオが崩れる条件", ("breakConditions",)),
        (r"結論|最終判断", "結論", ()),
    ]
    for pattern, label, fields in requirements:
        require_semantic_section(report, headings, pattern, label, fields)

    transition_patterns = {
        "08:00": r"前回からの(?:主な)?変化|前回から市場解釈は変わったか|東京時間への引き継ぎ|本日の監視順",
        "12:00": r"08:00からの(?:主な)?変化|欧州時間への引き継ぎ|次の時間帯への引き継ぎ",
        "16:00": r"12:00からの(?:主な)?変化|NY時間への引き継ぎ|次の時間帯への引き継ぎ",
        "21:00": r"16:00からの(?:主な)?変化|翌東京時間への引き継ぎ|NY時間への引き継ぎ|次の時間帯への引き継ぎ",
    }
    if not any(re.search(transition_patterns[slot], h) for h in headings):
        if slot == "08:00" and has_structured_value(report, ("changes",)):
            pass
        else:
            raise SystemExit(f"{slot} SOP fullText missing time-slot transition/change section")

    public_forbidden = [r"\bverified\b", r"JSONにありません", r"構造化JSON", r"内部構造"]
    for pattern in public_forbidden:
        if re.search(pattern, full_text, flags=re.I):
            raise SystemExit(f"{slot} SOP fullText contains internal-only wording: {pattern}")


def validate_report(report: dict) -> None:
    for key in ("date", "time", "title"):
        if not report.get(key):
            raise SystemExit(f"latest report missing required field: {key}")
    if report.get("time") == "08:00":
        table = report.get("marketDataTable") or {}
        rows = table.get("rows") or []
        if len(rows) != 28:
            raise SystemExit(f"08:00 latest report requires 28 marketDataTable rows, got {len(rows)}")
    validate_sop_body(report)


def sync_report_file(report: dict) -> Path:
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    filename = f"{report['date']}_{report['time'].replace(':', '-')}.json"
    path = REPORTS_DIR / filename
    dump_json(path, report)
    return path


def sync_dashboard(report: dict) -> None:
    dashboard = load_json(DASHBOARD, {})
    now = dt.datetime.now(JST).replace(microsecond=0).isoformat()
    key = f"{report['date']} {report['time']}"
    data_as_of = f"{report['date']}T{report['time']}:00+09:00"

    dashboard.setdefault("schemaVersion", "1.1.0")
    dashboard.setdefault("pageId", "dashboard")
    dashboard["generatedAt"] = now
    dashboard["publishedAt"] = now
    dashboard["dataAsOf"] = data_as_of
    dashboard["status"] = "ok"
    dashboard["isStale"] = False
    dashboard["staleReason"] = ""
    dashboard["currentReportKey"] = key
    dashboard["latestReport"] = report

    sources = dashboard.get("sources")
    if not isinstance(sources, list):
        sources = []
    found = False
    for source in sources:
        if isinstance(source, dict) and source.get("id") == "MARKET_REPORTS_JSON":
            source["asOf"] = key
            source["status"] = "ok"
            found = True
            break
    if not found:
        sources.insert(0, {
            "id": "MARKET_REPORTS_JSON",
            "name": "マーケットレポート本文の構造化JSON",
            "path": "reports.json",
            "asOf": key,
            "status": "ok",
            "note": "data/latest-report.json を正本として reports.json と dashboard.json を自動同期。",
        })
    dashboard["sources"] = sources
    dump_json(DASHBOARD, dashboard)


def main() -> None:
    payload = load_json(LATEST, {})
    source_report = payload.get("latestReport") or payload.get("report") or payload
    if not isinstance(source_report, dict):
        raise SystemExit("data/latest-report.json does not contain a report object")

    report = json.loads(json.dumps(source_report, ensure_ascii=False))
    ensure_public_full_text(report)
    sanitize_public_full_text(report)
    validate_report(report)
    report_path = sync_report_file(report)
    sync_dashboard(report)
    print(f"Synced {report['date']} {report['time']} -> {report_path.relative_to(ROOT)}, data/dashboard.json")


if __name__ == "__main__":
    main()
