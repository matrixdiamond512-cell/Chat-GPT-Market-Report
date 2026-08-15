from __future__ import annotations

import datetime as dt
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LATEST = ROOT / "data/latest-report.json"
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


def require_heading(headings: list[str], pattern: str, label: str) -> None:
    rx = re.compile(pattern)
    if not any(rx.search(h) for h in headings):
        raise SystemExit(f"SOP fullText missing required section: {label}")


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

    common = [
        (r"今日の相場テーマ", "今日の相場テーマ"),
        (r"主要市場データ|主要市場まとめ", "主要市場データ"),
        (r"材料と値動きの整合性|価格の動きと材料の整合性", "材料と値動きの整合性"),
        (r"(?:今日の)?主導市場|どの市場が主導", "主導市場"),
        (r"重要ニュース|重要ニュースと市場への伝播", "重要ニュース"),
        (r"クロスアセット資金フロー", "クロスアセット資金フロー"),
        (r"需給・ポジション", "需給・ポジション"),
        (r"個別(?:市場)?見通し|6市場の(?:個別)?見通し", "個別市場見通し"),
        (r"シナリオ", "シナリオ"),
        (r"崩れる条件", "シナリオが崩れる条件"),
        (r"結論|最終判断", "結論"),
    ]
    for pattern, label in common:
        require_heading(headings, pattern, label)

    transition_patterns = {
        "08:00": r"前回からの(?:主な)?変化|東京時間への引き継ぎ|本日の監視順",
        "12:00": r"08:00からの(?:主な)?変化|欧州時間への引き継ぎ|次の時間帯への引き継ぎ",
        "16:00": r"12:00からの(?:主な)?変化|NY時間への引き継ぎ|次の時間帯への引き継ぎ",
        "21:00": r"16:00からの(?:主な)?変化|翌東京時間への引き継ぎ|NY時間への引き継ぎ|次の時間帯への引き継ぎ",
    }
    # Some morning documents use NY summary + monitoring order rather than a literal "前回からの変化" heading.
    if slot != "08:00" and not any(re.search(transition_patterns[slot], h) for h in headings):
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
    report = payload.get("latestReport") or payload.get("report") or payload
    if not isinstance(report, dict):
        raise SystemExit("data/latest-report.json does not contain a report object")
    validate_report(report)
    report_path = sync_report_file(report)
    sync_dashboard(report)
    print(f"Synced {report['date']} {report['time']} -> {report_path.relative_to(ROOT)}, data/dashboard.json")


if __name__ == "__main__":
    main()
