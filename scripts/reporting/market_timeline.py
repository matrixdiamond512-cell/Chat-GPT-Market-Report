"""Extract explicitly labeled market events from a saved report body."""
from __future__ import annotations

import re

SLOT_HEADINGS = {
    "08:00": re.compile(r"(?:昨夜NY市場|NY市場).*時系列"),
    "12:00": re.compile(r"東京前場の時系列|東京市場.*前場.*時系列|前場の時系列"),
    "16:00": re.compile(r"東京市場.*時系列"),
    "21:00": re.compile(r"欧州市場.*時系列|欧州.*時系列.*反応"),
}
PHASES = {
    "08:00": (("NY開場前", "NY開場前"), ("寄り付き", "寄り付き"), ("序盤", "序盤"),
              ("中盤", "中盤"), ("終盤・引け", "終盤|引け"), ("東京への引き継ぎ", "東京")),
    "12:00": (("寄り付き前", "寄り付き前"), ("寄り付き", "寄り付き"), ("前場序盤", "序盤"),
              ("中盤", "中盤"), ("前引け", "前引け")),
    "16:00": (("午前の振り返り", "午前|前場"), ("後場開始", "後場開始|後場序盤|後場.*再開"),
              ("後場中盤", "後場中盤"), ("大引け", "大引け"), ("欧州への引き継ぎ", "欧州")),
    "21:00": (("欧州開場前", "欧州開場前"), ("寄り付き", "欧州寄り付き|寄り付き"),
              ("序盤", "欧州序盤|序盤"), ("中盤", "欧州中盤|中盤"),
              ("NYへの引き継ぎ", "NY開場前|NYへの引き継ぎ")),
}
TIME = re.compile(r"(?:\d{1,2}[/-]\d{1,2}\s*)?\d{1,2}[:：]\d{2}(?:\s*[–—~〜-]\s*\d{1,2}[:：]\d{2})?(?:\s*JST)?")
LABELS = ("出来事", "反応", "意味", "出典", "次の注目点", "次は")


def _phase(slot: str, label: str) -> str:
    if slot == "16:00" and re.search(r"午前|前場", label) and re.search(r"振り返|前引け|序盤|寄り付き", label):
        return "午前の振り返り"
    if slot == "16:00" and "寄り付き前" in label:
        return "午前の振り返り"
    for phase, pattern in PHASES[slot]:
        if re.search(pattern, label):
            return phase
    return ""


def _event(line: str, slot: str) -> dict | None:
    text = re.sub(r"\s+", " ", line).strip()
    if not text or re.search(r"改訂追補|この時系列は|以下は.*時系列|まとめ：|結論：", text):
        return None
    if re.search(r"未発表|発表予定|発表前", text) and not re.search(r"発表された|発表後", text):
        return None
    markers = []
    for label in LABELS:
        marker = "次は" if label == "次は" else f"{label}："
        index = text.find(marker)
        if index >= 0:
            markers.append((index, label, marker))
    markers.sort()
    labels = [item[1] for item in markers]
    if not all(label in labels for label in ("出来事", "反応", "意味", "出典")):
        return None

    def value(label: str) -> str:
        index = next((i for i, item in enumerate(markers) if item[1] == label), -1)
        if index < 0:
            return ""
        start, _, marker = markers[index]
        end = markers[index + 1][0] if index + 1 < len(markers) else len(text)
        return text[start + len(marker):end].strip().rstrip("。；;")

    prefix = re.sub(r"[｜|／/]$", "", text[:markers[labels.index("出来事")][0]].strip()).strip()
    phase = _phase(slot, prefix)
    if not phase:
        return None
    timestamp = TIME.search(prefix)
    observed = TIME.search(value("反応"))
    next_watch = value("次の注目点") or value("次は")
    if not all((value("出来事"), value("反応"), value("意味"), value("出典"), next_watch)):
        return None
    return {
        "phase": phase,
        "timeLabel": prefix or "時刻記載なし",
        "occurredAt": timestamp.group(0) if timestamp else None,
        "timePrecision": "source-stated" if timestamp else "time-not-recorded",
        "reactionObservedAt": observed.group(0) if observed else None,
        "event": value("出来事"),
        "reaction": value("反応"),
        "meaning": value("意味"),
        "nextWatch": next_watch,
        "sources": [value("出典")],
    }


def parse_saved_timeline(report: dict) -> dict | None:
    """Extract source-labeled events and bind them to the exact saved body."""
    slot = str(report.get("time") or "")
    body = str(report.get("fullText") or report.get("rawText") or "").replace("\r", "")
    pattern = SLOT_HEADINGS.get(slot)
    if not pattern or not body:
        return None
    lines = body.split("\n")
    start = next((i for i, line in enumerate(lines) if pattern.search(line.strip())), -1)
    if start < 0:
        return None
    section = []
    for line in lines[start + 1:]:
        if re.match(r"^\s*\d{1,2}[.．、]", line):
            break
        section.append(line)
    events = [event for line in section if (event := _event(line, slot))]
    if not events:
        return None
    amendment_text = "\n".join([lines[start], *section])
    amendment = re.search(r"改訂追補[：:]?\s*(\d{4}/\d{1,2}/\d{1,2})|(\d{4}/\d{1,2}/\d{1,2})改訂追補", amendment_text)
    return {
        "schemaVersion": "market-timeline/v1",
        "reportId": f"{report.get('date')}_{slot.replace(':', '-')}",
        "reportDate": report.get("date"),
        "reportTime": slot,
        "reportRevision": report.get("revision"),
        "sourceBodyHash": report.get("bodyHash"),
        "sourceDocumentRevisionId": report.get("sourceRevisionId"),
        "evidenceStatus": "AFTER_ISSUANCE_AMENDMENT" if amendment else "DERIVED_FROM_SAVED_BODY",
        "amendmentDate": (amendment.group(1) or amendment.group(2)) if amendment else None,
        "publicationStatus": report.get("report_status", "UNKNOWN"),
        "publicationEvidenceId": (report.get("publicationEvidence") or {}).get("evidenceId"),
        "snapshotId": (report.get("publicationEvidence") or {}).get("snapshotId"),
        "snapshotHash": (report.get("publicationEvidence") or {}).get("snapshotHash"),
        "sourceDocumentId": (report.get("sourceDocument") or {}).get("id"),
        "events": events,
    }
