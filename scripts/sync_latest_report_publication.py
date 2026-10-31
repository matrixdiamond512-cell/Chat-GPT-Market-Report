from __future__ import annotations

import datetime as dt
import json
import re
from pathlib import Path

from report_source_contract import heading, validate_saved_body
from report_identity import internal_report_key
from reporting.publication_eligibility import is_publication_eligible

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
    """Return a normalized heading only when the entire source line is heading-shaped."""
    text = str(line or "").strip()
    if not heading(text):
        return ""
    text = re.sub(r"^#{1,6}\s+", "", text)
    if text.startswith("【") and text.endswith("】"):
        text = text[1:-1].strip()
    text = re.sub(r"^\s*(?:第?\d{1,2}|[一二三四五六七八九十]+)\s*[．.、)）]\s*", "", text)
    return text.strip()


def sop_sections(full_text: str) -> list[tuple[str, str]]:
    """Extract heading-line bodies without treating incidental prose as headings."""
    sections: list[list[object]] = []
    for line in str(full_text or "").replace("\r", "").split("\n"):
        inline_label = re.match(r"^(結論|最終判断|まとめ)[：:]\s*(\S.*)$", line.strip())
        if inline_label:
            sections.append([inline_label.group(1), [inline_label.group(2)]])
            continue
        title = normalize_heading(line)
        if title:
            sections.append([title, []])
        elif sections:
            sections[-1][1].append(line)
    return [(str(title), "\n".join(body).strip()) for title, body in sections]


def sop_headings(full_text: str) -> list[str]:
    return [title for title, _ in sop_sections(full_text)]



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
    sections: list[tuple[str, str]] | None = None,
) -> None:
    matching = [body for title, body in (sections or []) if re.search(pattern, title)]
    if matching and any(len(re.sub(r"\s", "", body)) >= 24 for body in matching):
        return
    if matching:
        raise SystemExit(f"SOP fullText section is empty or substantively insufficient: {label}")
    if fields and has_structured_value(report, fields):
        return
    raise SystemExit(f"SOP fullText missing required section: {label}")



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

    sections = sop_sections(full_text)
    headings = [title for title, _ in sections]
    if len(headings) < 9:
        raise SystemExit(f"{slot} SOP fullText requires multiple explicit sections; found {len(headings)}")

    requirements = [
        (r"今日の相場テーマ", "今日の相場テーマ", ("theme",)),
        (r"主要市場データ|主要市場まとめ|市場データ一覧|主要6市場|6市場の(?:短期)?見通し", "主要市場データ", ("marketDataTable",)),
        (r"材料と値動きの整合性|価格の動きと材料の整合性", "材料と値動きの整合性", ("consistency",)),
        (r"(?:今日の)?主導市場|どの市場が主導", "主導市場", ("leadingMarket",)),
        (r"重要ニュース|重要ニュースと市場への伝播|昨夜のNY市場で何が起きたか", "重要ニュース", ("news",)),
        (r"クロスアセット資金フロー|金利・為替・クロスアセットの因果関係", "クロスアセット資金フロー", ("crossAssetFlow",)),
        (r"需給・ポジション", "需給・ポジション", ("positioning",)),
        (r"個別(?:市場)?見通し|(?:主要)?6市場の(?:個別|短期)?見通し", "個別市場見通し", ("markets",)),
        (r"シナリオ", "シナリオ", ("mainScenario", "alternativeScenario")),
        (r"崩れる条件", "シナリオが崩れる条件", ("breakConditions",)),
        (r"結論|最終判断", "結論", ()),
    ]
    for pattern, label, fields in requirements:
        require_semantic_section(report, headings, pattern, label, fields, sections)

    transition_patterns = {
        "08:00": r"前回(?:\d{2}:\d{2})?(?:版)?からの(?:主な)?変化|前回から市場解釈は変わったか|東京時間への引き継ぎ|次の時間帯への引き継ぎ|本日の監視順",
        "12:00": r"08:00からの(?:主な)?変化|欧州(?:・NY)?時間への引き継ぎ|次の時間帯への引き継ぎ",
        "16:00": r"12:00からの(?:主な)?変化|NY時間への引き継ぎ|次の時間帯への引き継ぎ",
        "21:00": r"16:00からの(?:主な)?変化|翌東京時間への引き継ぎ|NY時間への引き継ぎ|次の時間帯への引き継ぎ",
    }
    matching_transition_sections = [
        body for title, body in sections if re.search(transition_patterns[slot], title)
    ]
    if matching_transition_sections:
        if not any(len(re.sub(r"\s", "", body)) >= 24 for body in matching_transition_sections):
            raise SystemExit(
                f"{slot} SOP fullText transition section is empty or substantively insufficient"
            )
    elif slot == "08:00" and has_structured_value(report, ("changes",)):
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
    if report.get("sourceDocUrl") or report.get("sourceDocument"):
        # Native Docs use plain headings and may contain the market table only
        # in their original body. Validate the saved content without rewriting it.
        validate_saved_body(report)
        validate_sop_body(report)
        return
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
    if path.exists():
        from build_reports import _choose_canonical_update, validate_report as unwrap
        current = unwrap(load_json(path, {}), str(path))
        if _choose_canonical_update(current, report, str(path)) == "keep":
            return path
    else:
        from build_reports import _verified_source_revision
        _verified_source_revision(report)
    dump_json(path, report)
    return path


def report_publication_health(report: dict) -> tuple[str, bool, str]:
    """Never label a known reconstructed/unverified source as healthy."""
    state = str(report.get("report_status") or "").upper()
    if state == "RECONSTRUCTED_UNVERIFIED":
        return ("degraded", True, "REPORT_SOURCE_RECONSTRUCTED_UNVERIFIED")
    return ("ok", False, "")


def sync_dashboard(report: dict) -> None:
    dashboard = load_json(DASHBOARD, {})
    previous_report = dashboard.get("latestReport") if isinstance(dashboard.get("latestReport"), dict) else {}
    if not report.get("marketData"):
        # Keep the independent live market snapshot when the report source only
        # contains its original text and has no embedded market-data payload.
        snapshot = dashboard.get("marketData") or previous_report.get("marketData")
        if snapshot:
            dashboard["marketData"] = snapshot
    key = internal_report_key(report)
    data_as_of = f"{report['date']}T{report['time']}:00+09:00"

    # Scheduled recovery runs must be idempotent. If the exact same report is
    # already projected, do not create a timestamp-only dashboard commit.
    source_status, source_is_stale, source_stale_reason = report_publication_health(report)
    previous_status = str(dashboard.get("status") or "partial")
    previous_stale_reason = str(dashboard.get("staleReason") or "")
    if previous_stale_reason == "REPORT_SOURCE_RECONSTRUCTED_UNVERIFIED":
        # Clear only a status previously caused by the report source. Unknown
        # independent data completeness remains partial until separately verified.
        previous_status = "partial"
        previous_is_stale = False
        previous_stale_reason = ""
    else:
        previous_is_stale = bool(dashboard.get("isStale", False))
    status = "degraded" if source_status == "degraded" else (
        previous_status if previous_status in {"ok", "partial", "degraded"} else "partial"
    )
    is_stale = source_is_stale or previous_is_stale
    stale_reason = source_stale_reason or previous_stale_reason
    if (previous_report == report and dashboard.get("currentReportKey") == key
            and dashboard.get("status") == status
            and dashboard.get("isStale") is is_stale
            and dashboard.get("staleReason", "") == stale_reason):
        return

    now = dt.datetime.now(JST).replace(microsecond=0).isoformat()

    dashboard.setdefault("schemaVersion", "1.1.0")
    dashboard.setdefault("pageId", "dashboard")
    dashboard["generatedAt"] = now
    dashboard["publishedAt"] = now
    dashboard["dataAsOf"] = data_as_of
    dashboard["status"] = status
    dashboard["isStale"] = is_stale
    dashboard["staleReason"] = stale_reason
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


def select_same_slot_revision(reports: list[dict], source: str) -> dict:
    """Choose a verified newest revision for one slot, never an input-order winner.

    The canonical file and latest pointer can briefly carry different Drive
    modification revisions for the same source Doc. Sort by the existing
    monotonic revision contract, then apply the canonical conflict guard at
    every step. Newer revisions from another Doc or same-revision conflicts
    remain blocked.
    """
    if not reports:
        raise SystemExit(f"no report candidates for {source}")
    from build_reports import _choose_canonical_update, _revision_number

    ordered = sorted(
        enumerate(reports),
        key=lambda item: (
            _revision_number(item[1]) is not None,
            _revision_number(item[1]) if _revision_number(item[1]) is not None else -1,
            item[0],
        ),
    )
    selected = ordered[0][1]
    for _, candidate in ordered[1:]:
        if _choose_canonical_update(selected, candidate, source) == "write":
            selected = candidate
    return selected


def main() -> None:
    payload = load_json(LATEST, {})
    source_report = payload.get("latestReport") or payload.get("report") or payload
    if not isinstance(source_report, dict):
        raise SystemExit("data/latest-report.json does not contain a report object")

    # A direct canonical import may be newer than the latest pointer. Never
    # replay an older latest report over it, and never select a future slot.
    from build_reports import validate_report as unwrap, _choose_canonical_update
    report = source_report
    candidates = [
        unwrap(load_json(p, {}), str(p))
        for p in REPORTS_DIR.glob("*.json")
        if not p.name.startswith("_")
    ]
    candidates = [report for report in candidates if is_publication_eligible(report)]
    if is_publication_eligible(source_report):
        candidates.append(source_report)
    now = dt.datetime.now(JST)
    due = [r for r in candidates if dt.datetime.fromisoformat(f"{r['date']}T{r['time']}:00+09:00") <= now]
    if not due:
        raise SystemExit("no issued publication-eligible report source exists")
    newest = max((r["date"], r["time"]) for r in due)
    matching = [r for r in due if (r["date"], r["time"]) == newest]
    report = select_same_slot_revision(matching, str(newest))
    validate_report(report)
    report_path = sync_report_file(report)
    payload["latestReport"] = report
    payload["dataAsOf"] = f"{report['date']}T{report['time']}:00+09:00"
    dump_json(LATEST, payload)
    sync_dashboard(report)
    print(f"Synced {report['date']} {report['time']} -> {report_path.relative_to(ROOT)}, data/dashboard.json")


if __name__ == "__main__":
    main()
