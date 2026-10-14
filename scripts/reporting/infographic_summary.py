"""Provenance-bound, human-reviewed infographic summaries for the approved layout.

The report body remains immutable. This module validates a concise display layer
against exact source spans and renders only a DEBUG_PREVIEW; it cannot publish.
"""
from __future__ import annotations

import argparse
import base64
from collections import Counter
from datetime import datetime
import hashlib
import html
import io
import json
from pathlib import Path
import re

from .approved_layout import ROOT, TEMPLATE, canonical, fail, layout_config, sha
from .infographic import report_text
from PIL import Image, ImageDraw, ImageFont

NUMBER = re.compile(r"(?<!\d)(?:[+\-−])?(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?(?:%|％|bp|円|ドル|倍|pt)?")
NUMBER_WITH_UNIT = re.compile(r"(?<!\d)(?:[+\-−])?(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?(?:%|％|bp|円|ドル|倍|pt)")
EXPECTED_PANELS = tuple(range(1, 17))
EXPECTED_PANEL_KINDS = {
    1: {"judgment"}, 2: {"focus"}, 3: {"flow"}, 4: {"risk"}, 5: {"timeline"},
    6: {"market"}, 7: {"market"}, 8: {"metric"}, 9: {"flow", "note"},
    10: {"news"}, 11: {"risk"}, 12: {"scenario"}, 13: {"outlook"},
    14: {"handoff", "note"}, 15: {"event"}, 16: {"conclusion", "note"},
}
REQUIRED_CRITICAL_ROLE_PANELS = {"judgment_basis": {1}, "risk_condition": {4}}
DIRECTION_TERMS = ("上昇", "下落", "強気", "弱気", "回復", "反発", "維持", "定着", "突破", "割れ",
                   "下押し", "警戒", "逆風", "重荷", "ドル高", "原油高", "ギャップダウン", "買い戻し", "売り", "縮小", "上値")


def source_line_spans(body: str):
    spans = []
    offset = 0
    section = 0
    for line_number, line in enumerate(body.splitlines(keepends=True), 1):
        text = line.rstrip("\r\n")
        heading = re.match(r"^(\d{1,2})[．.]\s*", text)
        if heading:
            section = int(heading[1])
        if text.strip():
            spans.append({"line": line_number, "start": offset, "end": offset + len(text),
                          "section": section, "text": text})
        offset += len(line)
    return spans


def _refs_for_anchors(body: str, anchors):
    lines = source_line_spans(body)
    refs = []
    for anchor in anchors:
        matches = [line for line in lines if anchor in line["text"]]
        if len(matches) != 1:
            fail("SUMMARY_SOURCE_ANCHOR_NOT_UNIQUE", anchor)
        row = matches[0]
        start = row["start"] + row["text"].index(anchor)
        refs.append({"start": start, "end": row["end"], "line": row["line"],
                     "section": row["section"], "anchor": anchor,
                     "excerpt": body[start:row["end"]]})
    return refs


def _normal_number(value):
    return value.replace("−", "-").replace(",", "")


def build_summary(report: dict, authoring: dict):
    body = report_text(report)
    claims = []
    seen = set()
    for source in authoring.get("claims", []):
        if source.get("id") in seen:
            fail("SUMMARY_DUPLICATE_CLAIM_ID", source.get("id"))
        seen.add(source.get("id"))
        row = {key: value for key, value in source.items() if key != "source_anchors"}
        row["source_refs"] = _refs_for_anchors(body, source.get("source_anchors", []))
        claims.append(row)
    summary = {"schema_version": 1, "artifact_type": "INFOGRAPHIC_SUMMARY_DEBUG_PREVIEW",
               "status": "DRAFT", "human_review": authoring.get("human_review", "PENDING"),
               "source_offset_unit": "UNICODE_CODEPOINTS",
               "report_id": report.get("report_id"), "revision": report.get("revision"),
               "snapshot_id": report.get("snapshot_id"), "bodyHash": report.get("bodyHash"),
               "date": report.get("date"), "time": report.get("time"), "title": report.get("title"),
               "source_observed_sha256": sha(body.encode("utf-8")),
               "source_report_status": report.get("report_status"),
               "summary_policy": "HUMAN_AUTHORED_SOURCE_BOUND_SUMMARY",
               "critical_roles_required": ["judgment_basis", "risk_condition"],
               "claims": claims, "publish_allowed": False,
               "publication_status": "NOT_READY"}
    validate_summary(report, summary)
    return summary


def validate_summary(report: dict, summary: dict):
    body = report_text(report)
    layout = json.loads((TEMPLATE / "layout.json").read_text(encoding="utf-8"))
    if summary.get("artifact_type") != "INFOGRAPHIC_SUMMARY_DEBUG_PREVIEW" or summary.get("status") != "DRAFT":
        fail("SUMMARY_PREVIEW_ONLY")
    if (summary.get("source_observed_sha256") != sha(body.encode("utf-8"))
            or summary.get("time") != "08:00" or report.get("time") != "08:00"):
        fail("SUMMARY_SOURCE_IDENTITY_MISMATCH")
    if summary.get("human_review") != "PENDING" or summary.get("publish_allowed") is not False:
        fail("SUMMARY_REVIEW_OR_PUBLICATION_GATE")
    if len(summary.get("claims", [])) == 0:
        fail("SUMMARY_NO_CLAIMS")
    panel_counts = Counter()
    panel_kinds = {panel: set() for panel in EXPECTED_PANELS}
    claim_ids = set()
    numeric_count = 0
    critical_role_panels = {role: set() for role in REQUIRED_CRITICAL_ROLE_PANELS}
    for claim in summary["claims"]:
        if claim.get("id") in claim_ids or claim.get("panel") not in EXPECTED_PANELS:
            fail("SUMMARY_CLAIM_ID_OR_PANEL_INVALID", claim.get("id"))
        claim_ids.add(claim["id"])
        for role in claim.get("roles", []):
            if role in critical_role_panels:
                critical_role_panels[role].add(claim["panel"])
        panel_counts[claim["panel"]] += 1
        panel_kinds[claim["panel"]].add(claim.get("kind"))
        refs = claim.get("source_refs") or []
        if not refs:
            fail("SUMMARY_SOURCE_PROVENANCE_MISSING", claim["id"])
        excerpts = []
        for ref in refs:
            start, end = ref.get("start"), ref.get("end")
            if not isinstance(start, int) or not isinstance(end, int) or start < 0 or end <= start:
                fail("SUMMARY_SOURCE_POSITION_INVALID", claim["id"])
            excerpt = body[start:end]
            if excerpt != ref.get("excerpt") or ref.get("anchor") not in excerpt:
                fail("SUMMARY_SOURCE_SPAN_MISMATCH", claim["id"])
            excerpts.append(excerpt)
        source_text = " ".join(excerpts)
        source_numbers = {_normal_number(n) for n in NUMBER.findall(source_text)}
        source_numbers_with_units = {_normal_number(n) for n in NUMBER_WITH_UNIT.findall(source_text)}
        display = " ".join(str(claim.get(k, "")) for k in ("label", "text"))
        display_numbers = NUMBER.findall(display)
        display_numbers_with_units = NUMBER_WITH_UNIT.findall(display)
        missing_units = [n for n in display_numbers_with_units
                         if _normal_number(n) not in source_numbers_with_units]
        if missing_units:
            fail("SUMMARY_NUMERIC_UNIT_NOT_IN_SOURCE", {"claim": claim["id"], "tokens": missing_units})
        missing = [n for n in display_numbers if _normal_number(n) not in source_numbers]
        if missing:
            fail("SUMMARY_NUMERIC_TOKEN_NOT_IN_SOURCE", {"claim": claim["id"], "tokens": missing})
        direction_mismatch = [term for term in DIRECTION_TERMS if term in display and term not in source_text]
        if direction_mismatch:
            fail("SUMMARY_DIRECTION_TERM_NOT_IN_SOURCE", {"claim": claim["id"], "terms": direction_mismatch})
        numeric_count += len(display_numbers)
    missing_panels = [n for n in EXPECTED_PANELS if panel_counts[n] == 0]
    if missing_panels:
        fail("SUMMARY_REQUIRED_PANELS_MISSING", missing_panels)
    missing_kinds = {panel: sorted(kinds - panel_kinds[panel]) for panel, kinds in EXPECTED_PANEL_KINDS.items()
                     if kinds - panel_kinds[panel]}
    if missing_kinds:
        fail("SUMMARY_REQUIRED_CONTENT_CATEGORIES_MISSING", missing_kinds)
    required_roles = set(summary.get("critical_roles_required", []))
    missing_roles = sorted(role for role in required_roles
                           if not (critical_role_panels.get(role, set()) & REQUIRED_CRITICAL_ROLE_PANELS.get(role, set())))
    if missing_roles:
        fail("SUMMARY_CRITICAL_ROLES_MISSING", missing_roles)
    if summary.get("summary_policy") != "HUMAN_AUTHORED_SOURCE_BOUND_SUMMARY":
        fail("SUMMARY_POLICY_INVALID")
    if summary.get("source_offset_unit") != "UNICODE_CODEPOINTS":
        fail("SUMMARY_SOURCE_OFFSET_UNIT_INVALID")
    if summary.get("report_id") != report.get("report_id") or summary.get("revision") != report.get("revision"):
        fail("SUMMARY_REPORT_IDENTITY_CHANGED")
    # Historical withdrawn data lacks a typed snapshot/identity. Never create one here.
    source_identity_complete = all(summary.get(k) for k in ("report_id", "revision", "snapshot_id", "bodyHash"))
    formal = "NOT_READY" if not source_identity_complete else "BLOCKED_UNTIL_HUMAN_REVIEW_AND_SNAPSHOT_CHECK"
    return {"status": "PASS", "scope": "STRUCTURE_SOURCE_POSITIONS_AND_NUMERIC_UNITS_ONLY",
            "panel_count": len(EXPECTED_PANELS), "claim_count": len(claim_ids),
            "numeric_token_count": numeric_count, "human_semantic_review": "PENDING",
            "summary_policy": summary["summary_policy"],
            "critical_role_panels": {role: sorted(panels) for role,panels in critical_role_panels.items()},
            "snapshot_identity_complete": source_identity_complete,
            "formal_generation": formal, "publish_allowed": False}


def _icon(name):
    return f'<svg class="source-icon" aria-hidden="true"><use href="#icon-{name}"/></svg>'


def _claim_text(claim, include_label=False):
    keys = ("label", "text") if include_label else ("text",)
    return " ".join(str(claim.get(k, "")) for k in keys if claim.get(k))


def _render_claim(claim, include_label=False):
    text = _claim_text(claim, include_label=include_label)
    chunks, position = [], 0
    for index, match in enumerate(NUMBER.finditer(text), 1):
        fid = f"{claim['id']}-n{index:02d}"
        chunks.append(html.escape(text[position:match.start()]))
        direction = "up" if match[0].startswith("+") else "down" if match[0].startswith(("-", "−")) else ""
        chunks.append(f'<span class="numeric {direction}" data-numeric-id="{fid}">{html.escape(match[0])}</span>')
        position = match.end()
    chunks.append(html.escape(text[position:]))
    return f'<span class="fact summary-fact" data-fact-id="{claim["id"]}">{"".join(chunks)}</span>'


def render_summary_html(report, summary, reference):
    validation = validate_summary(report, summary)
    layout = layout_config(reference)
    by_panel = {n: [] for n in EXPECTED_PANELS}
    for claim in summary["claims"]:
        by_panel[claim["panel"]].append(claim)
    claim_by_id = {claim["id"]: claim for claim in summary["claims"]}
    cards = []
    icons = {1:"oil",2:"focus",3:"oil",4:"warning",5:"usa",6:"usa",7:"japan",8:"rates",9:"flow",10:"news",11:"risk",12:"scenario",13:"gold",14:"clock",15:"calendar",16:"light"}
    for panel in layout["panels"]:
        number = panel["number"]
        claims = by_panel[number]
        base = " ".join(_render_claim(claim) for claim in claims)
        if number == 1:
            content = '<div class="judgment-icons">' + _icon("gold") + _icon("oil") + '</div><div class="judgment-copy">' + ''.join('<p>'+_render_claim(c)+'</p>' for c in claims) + '</div>'
        elif number == 2:
            content = '<ol class="focus-list">' + ''.join('<li>'+_render_claim(c)+'</li>' for c in claims) + '</ol>'
        elif number in (3, 12):
            content = ''.join('<div class="flow-line">'+_icon("oil" if i == 0 else "japan")+'<span>'+_render_claim(c, include_label=True)+'</span></div>' for i,c in enumerate(claims))
        elif number == 4:
            content = ''.join('<div class="risk-line"><b>'+str(i)+'</b><span>'+_render_claim(c)+'</span></div>' for i,c in enumerate(claims,1))
        elif number == 5:
            content = '<table class="timeline"><tbody>'+''.join('<tr><th>'+html.escape(c.get('label',''))+'</th><td><b>↓</b>'+_render_claim(c)+'</td></tr>' for c in claims)+'</tbody></table>'
        elif number in (6,7):
            content = '<table class="market-table"><tbody>'+''.join('<tr><th>'+_icon("usa" if number==6 else "japan")+html.escape(c.get('label',''))+'</th><td>'+_render_claim(c)+'</td></tr>' for c in claims)+'</tbody></table>'
        elif number == 8:
            content = '<div class="metric-grid">'+''.join('<div class="metric"><small>'+html.escape(c.get('label',''))+'</small><b>'+_render_claim(c)+'</b></div>' for c in claims)+'</div>'
        elif number == 9:
            content = '<div class="flow-head"><b>相対買い示唆</b><b>資金引き揚げ示唆</b></div><div class="flow-arrows"><span>←</span><span>→</span></div>'+''.join('<p>'+_render_claim(c)+'</p>' for c in claims)
        elif number == 10:
            content = ''.join('<div class="news-line">'+_icon("news")+'<span>'+_render_claim(c)+'</span></div>' for c in claims)
        elif number == 11:
            content = ''.join('<div class="bullet-line">● '+_render_claim(c)+'</div>' for c in claims)
        elif number == 13:
            content = '<div class="outlook-grid">'+''.join('<article class="market outlook"><h3>'+_icon("gold" if c.get('label')=="金" else "oil" if c.get('label')=="WTI" else "japan" if c.get('label')=="日経225先物" else "btc" if c.get('label')=="BTCUSD" else "usa")+html.escape(c.get('label',''))+'</h3><span class="outlook-arrow">'+('↓' if any(v in c['text'] for v in ('弱気','下押し')) else '↑' if '強気' in c['text'] or 'ドル高' in c['text'] else '↔')+'</span><span>'+_render_claim(c)+'</span></article>' for c in claims)+'</div>'
        elif number == 14:
            content = '<div class="handoff-icon">'+_icon("clock")+'</div><div class="handoff-copy">'+''.join('<p>• '+_render_claim(c)+'</p>' for c in claims)+'</div>'
        elif number == 15:
            content = '<table class="event-table"><tbody>'+''.join('<tr><th>'+html.escape(c.get('label',''))+'</th><td>'+_icon("calendar")+'</td><td>'+_render_claim(c)+'</td></tr>' for c in claims)+'</tbody></table>'
        elif number == 16:
            content = ''.join('<div class="conclusion-line">'+_icon("light")+'<span>'+_render_claim(c)+'</span></div>' for c in claims)
        rect = panel["reference_rect"]
        short = number >= 12
        panel_title = panel["title"] + "（10/12終値）" if number == 6 else panel["title"]
        cards.append(f'<section class="card card-{number:02d} {panel["color"]}{" short" if short else ""}" data-card="{number:02d}" style="left:{rect[0]}px;top:{rect[1]}px;width:{rect[2]}px;height:{rect[3]}px"><h2><b>{number:02d}</b>{html.escape(panel_title)}</h2><div class="card-body">{content}</div></section>')
    from PIL import Image
    with Image.open(reference) as image:
        stream = io.BytesIO()
        image.crop(tuple(layout["header_decoration_crop"])).save(stream, format="PNG")
    skyline = base64.b64encode(stream.getvalue()).decode("ascii")
    sprite = (ROOT / "templates/infographic/0800/icons.svg").read_text(encoding="utf-8")
    css = r"""
*{box-sizing:border-box}html,body{margin:0;width:1536px;height:1024px;overflow:hidden;background:#fff;color:#071d62;font-family:'Noto Sans CJK JP','Yu Gothic','Meiryo',sans-serif}#report{position:relative;width:1536px;height:1024px;background:#fff;overflow:hidden}.cards{position:absolute;inset:0;width:1536px;height:1024px;display:grid;grid-template-columns:repeat(60,1fr)}header{position:absolute;inset:0 0 auto;height:102px;padding:5px 12px;color:#fff;background:#071441;border-bottom:2px solid #10b5f4;overflow:hidden}header .skyline{position:absolute;right:180px;top:0;width:405px;height:62px;opacity:.92}h1{position:relative;margin:0;font-size:31px;line-height:1.15}header .basis{position:relative;font-size:15px;line-height:1.3;margin-top:5px;padding-right:325px}.approved-mark{position:absolute;right:8px;bottom:5px;border:1px solid #ffd52b;border-radius:5px;padding:3px 7px;font-size:12px;color:#fff;background:#172454}.status{position:absolute;right:13px;top:4px;background:#ffdc34;color:#8d102a;border:2px solid #e31b43;border-radius:4px;padding:3px 8px;font-size:13px;font-weight:900;z-index:2}.card{position:absolute;border:1px solid #039cdd;border-radius:9px;overflow:hidden;background:linear-gradient(110deg,#fff,#edf9ff);box-shadow:inset 0 0 5px #99ddff}.card h2{height:36px;margin:0;padding:3px 7px;color:#fff;background:linear-gradient(#03caff,#006bd0 35%,#06398a);display:flex;align-items:center;gap:9px;font-size:19px;line-height:1}.card h2 b{font-size:24px}.red h2{background:linear-gradient(#ff78a8,#ed0646 35%,#b40021)}.orange h2{background:linear-gradient(#ffda37,#ff7600 40%,#ee2400)}.green h2{background:linear-gradient(#49ecc0,#00a86b 45%,#04694b)}.yellow h2{background:linear-gradient(#fff92b,#ffd600 45%,#ffac00);color:#071958}.short h2{height:25px;font-size:15px;padding:2px 5px}.short h2 b{font-size:18px}.card-body{height:calc(100% - 36px);padding:5px 7px;font-size:14px;line-height:1.24;font-weight:650;overflow:hidden}.short .card-body{height:calc(100% - 25px);padding:3px 5px;font-size:12px;line-height:1.12}.summary-fact{display:inline}.numeric{font-weight:900;white-space:nowrap}.up{color:#ec174c}.down{color:#0875e1}.source-icon{width:26px;height:26px;flex:none;color:#005aba}.card-01 .card-body{display:flex;align-items:center;gap:6px;font-size:18px;line-height:1.45}.judgment-icons{width:105px;display:grid;grid-template-columns:1fr 1fr;align-items:center}.judgment-icons .source-icon{width:48px;height:48px}.judgment-copy{flex:1}.judgment-copy p{margin:3px 0}.card-02 .card-body{font-size:16px}.focus-list{list-style:none;padding:0;margin:0;counter-reset:item}.focus-list li{display:flex;align-items:center;gap:7px;margin:0 0 9px}.focus-list li:before{counter-increment:item;content:counter(item);flex:none;width:31px;height:31px;border-radius:50%;display:grid;place-items:center;color:white;background:radial-gradient(circle at 30% 20%,#10ecff,#007ae1 55%,#063084);font-size:20px}.flow-line{display:flex;align-items:center;gap:6px;margin:4px 0;font-size:15px}.flow-line .source-icon{width:30px;height:30px}.risk-line{display:flex;gap:6px;align-items:center;border-bottom:1px solid #efcbd3;padding:4px 0;font-size:13px;line-height:1.23}.risk-line b{font-size:19px;color:#ec174c}.timeline,.market-table,.event-table{width:100%;border-collapse:collapse;table-layout:fixed}.timeline{font-size:13px;line-height:1.18}.timeline tr{border-bottom:1px solid #bdd7ec}.timeline th{width:95px;text-align:left;color:#073b83}.timeline td{padding:3px}.timeline td b{display:inline-block;width:28px;height:25px;text-align:center;color:white;background:#df2549;border-radius:50%;font-size:20px;margin-right:5px}.market-table{font-size:12.5px;line-height:1.1}.market-table tr{height:31px;border-bottom:1px solid #b9d7eb}.market-table th{text-align:left;width:42%;white-space:nowrap;color:#004da7}.market-table th .source-icon{width:18px;height:18px;vertical-align:middle;margin-right:3px}.market-table td{font-weight:750}.card-07 .market-table{font-size:12px}.card-07 .market-table tr{height:29px}.card-08 .card-body{padding:5px}.metric-grid{height:100%;display:grid;grid-template-columns:1fr 1fr;grid-template-rows:1fr 1fr;gap:5px}.metric{border:1px solid #12b5d9;border-radius:5px;background:#fff;padding:5px;display:flex;flex-direction:column;justify-content:center;overflow:hidden}.metric small{font-size:12px;color:#183d75}.metric b{font-size:14px;color:#071d62}.flow-head{display:flex;justify-content:space-between;gap:3px}.flow-head b{font-size:12px;color:white;border-radius:4px;background:#00a86b;padding:4px}.flow-head b:last-child{background:#df3046}.flow-arrows{display:flex;justify-content:space-around;color:#df3046;font-size:31px;line-height:1}.card-09 .card-body p{margin:3px 0;font-size:13px}.news-line{display:flex;align-items:flex-start;gap:4px;margin:2px 0;font-size:12.5px;line-height:1.18;border-bottom:1px solid #d5e4f0;padding-bottom:2px}.news-line .source-icon{width:23px;height:23px}.bullet-line{font-size:13px;line-height:1.25;margin:8px 0}.bullet-line:first-letter{color:#003d91}.card-12 .card-body{display:flex;flex-direction:column;justify-content:center;gap:2px}.card-12 .flow-line{font-size:12px;margin:0;line-height:1.05}.card-12 .source-icon{width:16px;height:16px}.outlook-grid{display:grid;grid-template-columns:repeat(6,minmax(0,1fr));height:100%;gap:3px}.outlook{position:relative;border:1px solid #35a9d5;border-radius:5px;background:linear-gradient(120deg,#fff,#eaf8ff);padding:3px;display:flex;flex-direction:column;align-items:center;text-align:center;justify-content:flex-start;overflow:hidden;font-size:12px;line-height:1.06}.outlook h3{display:flex;align-items:center;font-size:12px;line-height:1;margin:0 0 2px}.outlook h3 .source-icon{width:17px;height:17px}.outlook-arrow{font-size:17px;font-weight:900;color:#e3244a;line-height:1}.handoff-icon{position:absolute;top:8px;left:6px}.handoff-icon .source-icon{width:43px;height:43px}.handoff-copy{margin-left:48px;font-size:12px;line-height:1.13}.handoff-copy p{margin:1px 0}.event-table{font-size:12px;line-height:1.1}.event-table tr{height:20px;border-bottom:1px solid #bed6e9}.event-table th{width:61px;text-align:left;color:#064a9c}.event-table td:nth-child(2){width:27px}.event-table .source-icon{width:17px;height:17px;vertical-align:middle}.card-16 .card-body{font-size:12px;line-height:1.12}.conclusion-line{display:flex;gap:3px;margin:2px 0}.conclusion-line .source-icon{width:20px;height:20px}.card-15 .card-body,.card-16 .card-body{padding:3px}
"""
    title = html.escape(summary["title"])
    doc = ('<!doctype html><html lang="ja"><meta charset="utf-8"><style>'+css+'</style><body>'+sprite+
           '<main id="report"><header><img class="skyline" alt="承認画像の文字を含まない東京夜景装飾" src="data:image/png;base64,'+skyline+'">'+
           '<h1>'+title+'</h1><div class="basis">本文は未変更｜本文の要点を出典付きで図解化｜時点の異なる市場データを区別</div>'+
           '<span class="status">DRAFT・撤回済み本文・snapshot未照合｜公開不可</span><div class="approved-mark">参考デザイン基準 1536×1024</div></header><div class="cards">'+''.join(cards)+'</div></main></body></html>')
    expected_text = {claim["id"]: _claim_text(claim, include_label=(claim["panel"]==12)) for claim in summary["claims"]}
    expected_numeric = {f"{claim['id']}-n{i:02d}": match[0] for claim in summary["claims"] for i,match in enumerate(NUMBER.finditer(expected_text[claim["id"]]),1)}
    contract = {"html_sha256": sha(doc.encode("utf-8")), "view_sha256": sha(canonical(summary).encode("utf-8")),
                "expected_text": expected_text, "expected_numeric": expected_numeric,
                "layout_profile": "APPROVED_16_PANEL", "grid_columns": 60,
                "outlook_width_fraction": 40/60, "output_basename": "preview-2026-10-13_08-00-summary",
                "validation": {**validation, "artifact_type":"DEBUG_PREVIEW"},
                "publication":{"publish_allowed":False,"status":"NOT_READY"}}
    return doc, contract


def render_summary_png(report, summary, reference, output):
    """Draw the fixed 1536x1024 design as native text/vector elements."""
    layout = layout_config(reference)
    validate_summary(report, summary)
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.exists():
        fail("SUMMARY_PNG_OUTPUT_ALREADY_EXISTS")
    image = Image.new("RGB", (1536, 1024), "#ffffff")
    draw = ImageDraw.Draw(image)
    font_path = "C:/Windows/Fonts/NotoSansJP-VF.ttf"
    bold_path = "C:/Windows/Fonts/YuGothB.ttc"
    regular = lambda size: ImageFont.truetype(font_path, size, index=0)
    bold = lambda size: ImageFont.truetype(bold_path, size, index=0)
    body = bold(14)
    mini = bold(13)
    navy = "#071d62"
    blue = "#005ab5"
    red = "#e20d45"
    green = "#00a36c"
    orange = "#f17000"
    yellow = "#ffd51b"
    # The approved asset's text-free header decoration crop is the only reused raster area.
    with Image.open(reference) as ref:
        image.paste(ref.crop(tuple(layout["header_decoration_crop"])), (895, 0))
    draw.rectangle((0, 0, 1535, 101), fill="#071441")
    with Image.open(reference) as ref:
        image.paste(ref.crop(tuple(layout["header_decoration_crop"])), (895, 0))
    draw.text((16, 2), summary["title"], font=bold(40), fill="white", stroke_width=0)
    draw.text((18, 64), "本文は未変更｜重要点を出典付きで要約｜観測時点を区別", font=bold(18), fill="white")
    draw.rounded_rectangle((1125, 5, 1524, 42), radius=5, fill="#ffdc34", outline="#e31b43", width=2)
    draw.text((1134, 12), "DRAFT・撤回済み本文・snapshot未照合｜公開不可", font=bold(11), fill="#88102a")
    draw.rounded_rectangle((1268, 68, 1523, 96), radius=5, fill="#172454", outline="#ffd52b", width=1)
    draw.text((1280, 74), "参考デザイン基準 1536×1024", font=bold(12), fill="white")

    claims_by_panel = {n: [] for n in EXPECTED_PANELS}
    for claim in summary["claims"]:
        claims_by_panel[claim["panel"]].append(claim)
    bands = {"red":("#f83d76", "#b90035"), "blue":("#078df0", "#064a9a"),
             "orange":("#ff9715", "#d84700"), "green":("#15d18b", "#007f50"),
             "yellow":("#fff02a", "#e6a900")}

    def gradient(rect, top, bottom):
        x1,y1,x2,y2=rect
        def rgb(value): return tuple(int(value[i:i+2],16) for i in (1,3,5))
        start,end=rgb(top),rgb(bottom)
        rows=max(1,y2-y1+1)
        for j in range(rows):
            t=j/max(1,rows-1)
            color=tuple(round(start[i]*(1-t)+end[i]*t) for i in range(3))
            draw.line((x1,y1+j,x2,y1+j),fill=color,width=1)

    def wrap(text, font, width):
        chunks = re.findall(r"\d+(?:,\d{3})*(?:\.\d+)?(?:%|％|bp|ポイント|円|ドル|倍|pt)?|[A-Za-z]+(?:/[A-Za-z]+)?|[^A-Za-z\d]", text)
        lines, current = [], ""
        for chunk in chunks:
            candidate = current + chunk
            if current and draw.textlength(candidate, font=font) > width:
                lines.append(current)
                current = chunk
            else:
                current = candidate
        if current:
            lines.append(current)
        return lines or [""]

    def wrapped(x, y, text, width, *, font=body, fill=navy, leading=3, max_lines=None):
        lines = wrap(text, font, width)
        clipped = max_lines is not None and len(lines) > max_lines
        for index, line in enumerate(lines[:max_lines] if max_lines else lines):
            draw.text((x, y + index * (font.size + leading)), line, font=font, fill=fill)
        return y + len(lines[:max_lines] if max_lines else lines) * (font.size + leading), clipped, len(lines)

    def arrow(cx, cy, direction="right", color=red, size=18):
        if direction == "down":
            draw.line((cx, cy-size, cx, cy+size), fill=color, width=5)
            draw.polygon([(cx-size,cy+size-5),(cx+size,cy+size-5),(cx,cy+size+size//2)], fill=color)
        elif direction == "left":
            draw.line((cx+size,cy,cx-size,cy),fill=color,width=5)
            draw.polygon([(cx-size+5,cy-size),(cx-size+5,cy+size),(cx-size-size//2,cy)],fill=color)
        else:
            draw.line((cx-size,cy,cx+size,cy),fill=color,width=5)
            draw.polygon([(cx+size-5,cy-size),(cx+size-5,cy+size),(cx+size+size//2,cy)],fill=color)

    def icon(cx, cy, name, size=24):
        if name in ("oil", "barrel"):
            draw.rounded_rectangle((cx-size//2,cy-size//2,cx+size//2,cy+size//2),radius=5,fill="#202329",outline="#080b10",width=2)
            for yy in (cy-size//3,cy,cy+size//3):
                draw.line((cx-size//2+2,yy,cx+size//2-2,yy),fill="#a2a6ab",width=2)
        elif name == "gold":
            draw.polygon([(cx-size//2,cy+size//3),(cx,cy-size//3),(cx+size//2,cy+size//3)],fill="#ffc928",outline="#b97700")
            draw.rectangle((cx-size//2,cy+size//3,cx+size//2,cy+size//2),fill="#efab12",outline="#b97700")
        elif name == "chip":
            draw.rectangle((cx-size//2,cy-size//2,cx+size//2,cy+size//2),fill="#0879df",outline="#063f8d",width=2)
            draw.rectangle((cx-size//4,cy-size//4,cx+size//4,cy+size//4),outline="white",width=2)
            for d in range(-size//3,size//2,6):
                draw.line((cx-size//2-3,cy+d,cx-size//2,cy+d),fill="#0879df",width=2)
                draw.line((cx+size//2,cy+d,cx+size//2+3,cy+d),fill="#0879df",width=2)
        elif name in ("japan", "news"):
            draw.rounded_rectangle((cx-size//2,cy-size//3,cx+size//2,cy+size//3),radius=3,fill="white",outline="#7da5c3",width=1)
            draw.ellipse((cx-size//7,cy-size//7,cx+size//7,cy+size//7),fill="#d71935")
        elif name == "calendar":
            draw.rounded_rectangle((cx-size//2,cy-size//2,cx+size//2,cy+size//2),radius=4,fill="white",outline="#e52548",width=2)
            draw.rectangle((cx-size//2,cy-size//2,cx+size//2,cy-size//5),fill="#e52548")
        elif name == "clock":
            draw.ellipse((cx-size//2,cy-size//2,cx+size//2,cy+size//2),fill="#dcf4ff",outline="#008bc4",width=2)
            draw.line((cx,cy,cx,cy-size//3),fill="#005bab",width=2)
            draw.line((cx,cy,cx+size//4,cy+size//6),fill="#005bab",width=2)
        elif name == "light":
            draw.ellipse((cx-size//3,cy-size//2,cx+size//3,cy+size//6),fill="#ffd84d",outline="#de9c00",width=2)
            draw.line((cx-size//6,cy+size//4,cx+size//6,cy+size//4),fill="#de9c00",width=3)
        elif name == "warning":
            draw.polygon([(cx,cy-size//2),(cx+size//2,cy+size//2),(cx-size//2,cy+size//2)],fill="#ffcc28",outline="#d34a19")
            draw.text((cx-3,cy-size//4),"!",font=bold(max(10,size//2)),fill="#9d1a25")
        elif name == "usa":
            draw.rectangle((cx-size//2,cy-size//3,cx+size//2,cy+size//3),fill="white",outline="#6984ac")
            for row in range(3):
                yy=cy-size//3+row*(size//5)
                draw.rectangle((cx-size//2,yy,cx+size//2,yy+max(1,size//10)),fill="#d72f46")
            draw.rectangle((cx-size//2,cy-size//3,cx,cy),fill="#174b96")
        else:
            draw.ellipse((cx-size//2,cy-size//2,cx+size//2,cy+size//2),fill="#ddeaff",outline=blue,width=2)

    overflow = []
    for panel in layout["panels"]:
        no, color, rect = panel["number"], bands[panel["color"]], panel["reference_rect"]
        x, y, width, height = rect
        draw.rounded_rectangle((x,y,x+width-1,y+height-1),radius=8,fill="#f5fbff",outline="#08a1db",width=2)
        head_h = 35 if no <= 11 else 25
        if no >= 12:
            head_h = 24
        draw.rounded_rectangle((x+1,y+1,x+width-2,y+head_h),radius=7,fill=color[1])
        gradient((x+2,y+2,x+width-3,y+head_h),color[0],color[1])
        draw.rounded_rectangle((x+1,y+1,x+width-2,y+head_h),radius=7,outline=color[1],width=1)
        draw.rectangle((x+1,y+head_h-8,x+width-2,y+head_h),fill=color[1])
        head_size = 22 if no <= 11 else 18
        if no in (6,8): head_size=16
        head_font = bold(head_size)
        panel_title = panel["title"] + "（10/12終値）" if no == 6 else panel["title"]
        draw.text((x+7,y+(head_h-25)//2),f"{no:02d}",font=bold(24 if no <= 11 else 20),fill="white" if panel["color"]!="yellow" else navy)
        draw.text((x+52,y+(head_h-head_size)//2),panel_title,font=head_font,fill="white" if panel["color"]!="yellow" else navy)
        inner_x, inner_y = x+8, y+head_h+6
        inner_w, inner_h = width-16, height-head_h-11
        claims = claims_by_panel[no]

        def put_claim(c, px=inner_x, py=inner_y, pw=inner_w, font=body, fill=navy, max_lines=None):
            return wrapped(px,py,_claim_text(c),pw,font=font,fill=fill,max_lines=max_lines)

        if no == 1:
            icon(inner_x+24,inner_y+40,"gold",37); icon(inner_x+69,inner_y+40,"oil",34); icon(inner_x+25,inner_y+91,"chip",34)
            yy=inner_y+2
            for i,c in enumerate(claims):
                yy, clipped, lines=put_claim(c,inner_x+104,yy,inner_w-106,font=bold(18 if i==0 else 15),fill=red if i==0 else navy,max_lines=5)
                if clipped: overflow.append({"panel":no,"claim":c["id"],"required_lines":lines,"available_lines":5})
                yy+=5
        elif no == 2:
            yy=inner_y+1
            for i,c in enumerate(claims,1):
                draw.ellipse((inner_x,yy,inner_x+31,yy+31),fill="#0780d9",outline="#0056a7",width=1)
                draw.text((inner_x+9,yy+4),str(i),font=bold(17),fill="white")
                yy,clipped,lines=put_claim(c,inner_x+40,yy+1,inner_w-42,font=bold(15),max_lines=2)
                if clipped: overflow.append({"panel":no,"claim":c["id"],"required_lines":lines,"available_lines":2})
                yy += 5
        elif no == 3:
            row_h=max(1,inner_h//len(claims))
            yy=inner_y+2
            flow_icons=("oil","rates","chip")
            for i,c in enumerate(claims):
                row_y=inner_y+i*row_h
                icon(inner_x+18,row_y+row_h//2,flow_icons[min(i,2)],30)
                if i < len(claims)-1:
                    arrow(inner_x+18,row_y+row_h-8,"down",red,6)
                _,clipped,lines=put_claim(c,inner_x+48,row_y+row_h//2-14,inner_w-53,font=bold(14),max_lines=3)
                if clipped: overflow.append({"panel":no,"claim":c["id"],"required_lines":lines,"available_lines":3})
        elif no == 4:
            slot_h=inner_h//max(1,len(claims))
            for i,c in enumerate(claims,1):
                yy=inner_y+(i-1)*slot_h+2
                icon(inner_x+17,yy+13,"warning",20); arrow(inner_x+44,yy+13,"up" if i==1 else "right",red if i<3 else orange,8)
                yy,clipped,lines=put_claim(c,inner_x+60,yy,inner_w-62,font=bold(14),max_lines=3)
                if clipped: overflow.append({"panel":no,"claim":c["id"],"required_lines":lines,"available_lines":3})
        elif no == 5:
            slot_h=inner_h//max(1,len(claims))
            for i,c in enumerate(claims):
                yy=inner_y+i*slot_h+2
                draw.text((inner_x,yy),c.get("label",""),font=bold(13),fill=blue)
                draw.ellipse((inner_x+81,yy,inner_x+107,yy+25),fill="#e12648",outline="#ba1535",width=1)
                draw.text((inner_x+87,yy+1),"↓",font=bold(18),fill="white")
                yy,clipped,lines=put_claim(c,inner_x+116,yy,inner_w-118,font=body,max_lines=2)
                if clipped: overflow.append({"panel":no,"claim":c["id"],"required_lines":lines,"available_lines":2})
        elif no in (6,7):
            row_h=(inner_h-2)//max(len(claims),1)
            label_w=120 if no==6 else int(inner_w*.43)
            if no==6:
                draw.text((inner_x+label_w,inner_y),"終値",font=bold(12),fill=blue)
                draw.text((inner_x+label_w+76,inner_y),"前日比",font=bold(12),fill=blue)
                draw.text((inner_x+label_w+157,inner_y),"騰落率",font=bold(12),fill=blue)
                row_y0=inner_y+17
                row_h=max(1,(inner_h-17)//len(claims))
            else:
                row_y0=inner_y
            for i,c in enumerate(claims):
                ry=row_y0+i*row_h
                if i%2==1: draw.rectangle((inner_x,ry,inner_x+inner_w,ry+row_h),fill="#e7f5ff")
                draw.line((inner_x,ry+row_h,inner_x+inner_w,ry+row_h),fill="#abd5e9",width=1)
                icon(inner_x+12,ry+row_h//2,"usa" if no==6 else ("oil" if "WTI" in c.get("label","") else "gold" if "金" in c.get("label","") else "japan"),17)
                draw.text((inner_x+25,ry+4),c.get("label",""),font=bold(13 if no==7 else 12),fill=blue)
                text=c.get("text","")
                if no==6:
                    parts=text.split("｜")
                    if len(parts)!=3: fail("SUMMARY_NY_INDEX_TABLE_FIELDS",c["id"])
                    for part, xpos in zip(parts,(inner_x+label_w,inner_x+label_w+76,inner_x+label_w+157)):
                        dcolor=red if part.startswith("+") else blue if part.startswith(("-","−")) else navy
                        yy,clipped,lines=wrapped(xpos,ry+5,part,75,font=mini,fill=dcolor,max_lines=2)
                        if clipped: overflow.append({"panel":no,"claim":c["id"],"required_lines":lines,"available_lines":2})
                else:
                    dcolor=red if re.search(r"\+\d",text) else blue if re.search(r"-\d",text) else navy
                    yy,clipped,lines=wrapped(inner_x+label_w,ry+4,text,inner_w-label_w,font=bold(12),fill=dcolor,max_lines=max(1,row_h//14))
                    if clipped: overflow.append({"panel":no,"claim":c["id"],"required_lines":lines,"available_lines":row_h//14})
        elif no == 8:
            gap=4; cols=2; rows=(len(claims)+cols-1)//cols
            cw=(inner_w-gap*(cols-1))//cols; ch=(inner_h-gap*(rows-1))//rows
            for i,c in enumerate(claims):
                cx=inner_x+(i%cols)*(cw+gap); cy=inner_y+(i//cols)*(ch+gap)
                draw.rounded_rectangle((cx,cy,cx+cw,cy+ch),radius=5,fill="white",outline="#14a9ce",width=1)
                draw.text((cx+5,cy+4),c.get("label",""),font=bold(12),fill=blue)
                _,clipped,lines=put_claim(c,cx+5,cy+20,cw-10,font=bold(14),max_lines=max(1,(ch-22)//15))
                if clipped: overflow.append({"panel":no,"claim":c["id"],"required_lines":lines,"available_lines":(ch-22)//15})
        elif no == 9:
            left_w=(inner_w-36)//2
            card_w=180; center=inner_x+inner_w//2
            left_x=inner_x+8; right_x=inner_x+inner_w-card_w-8; card_y=inner_y+8; card_h=82
            draw.rounded_rectangle((left_x,card_y,left_x+card_w,card_y+card_h),radius=8,fill="#effaf4",outline=green,width=2)
            draw.rounded_rectangle((right_x,card_y,right_x+card_w,card_y+card_h),radius=8,fill="#fff0f3",outline=red,width=2)
            icon(left_x+30,card_y+31,"oil",30); icon(left_x+70,card_y+31,"gold",28)
            icon(right_x+30,card_y+31,"chip",30); icon(right_x+70,card_y+31,"warning",26)
            wrapped(left_x+10,card_y+52,"相対買い示唆｜エネルギー",card_w-20,font=bold(12),fill=navy,max_lines=2)
            wrapped(right_x+10,card_y+52,"資金引き揚げ示唆｜AI・半導体",card_w-20,font=bold(12),fill=navy,max_lines=2)
            arrow(center-5,card_y+31,"right",red,14); arrow(center+5,card_y+58,"left",green,14)
            flow_y,clipped,lines=put_claim(claims[0],inner_x+4,inner_y+99,inner_w-8,font=bold(13),max_lines=3)
            if clipped: overflow.append({"panel":no,"claim":claims[0]["id"],"required_lines":lines,"available_lines":3})
            _,clipped,lines=put_claim(claims[1],inner_x+4,flow_y+1,inner_w-8,font=bold(13),max_lines=3)
            if clipped: overflow.append({"panel":no,"claim":claims[1]["id"],"required_lines":lines,"available_lines":3})
        elif no == 10:
            slot_h=inner_h//max(1,len(claims))
            for i,c in enumerate(claims):
                yy=inner_y+i*slot_h+2
                icon(inner_x+13,yy+11,"oil" if "原油" in c["text"] or "供給" in c["text"] else "chip" if "半導体" in c["text"] else "news",20)
                _,clipped,lines=put_claim(c,inner_x+30,yy,inner_w-33,font=bold(14),max_lines=2)
                if clipped: overflow.append({"panel":no,"claim":c["id"],"required_lines":lines,"available_lines":2})
        elif no == 11:
            slot_h=inner_h//max(1,len(claims))
            for i,c in enumerate(claims):
                yy=inner_y+i*slot_h+3
                draw.ellipse((inner_x+2,yy+4,inner_x+12,yy+14),fill="#064798")
                _,clipped,lines=put_claim(c,inner_x+19,yy,inner_w-21,font=body,max_lines=2)
                if clipped: overflow.append({"panel":no,"claim":c["id"],"required_lines":lines,"available_lines":2})
        elif no == 12:
            icons=("oil","rates","japan")
            for i,c in enumerate(claims):
                ry=inner_y+i*(inner_h//3)
                draw.rounded_rectangle((inner_x,ry,inner_x+inner_w,ry+inner_h//3-2),radius=5,fill="#fff6eb" if i else "#fff0f2",outline="#eaaabc")
                icon(inner_x+17,ry+(inner_h//3)//2,icons[min(i,2)],18)
                if i<2: arrow(inner_x+39,ry+(inner_h//3)//2,"right",blue,7)
                yy,clipped,lines=wrapped(inner_x+52,ry+4,c.get("label","")+"｜"+c.get("text",""),inner_w-56,font=bold(12),max_lines=3)
                if clipped: overflow.append({"panel":no,"claim":c["id"],"required_lines":lines,"available_lines":3})
        elif no == 13:
            gap=4; cw=(inner_w-gap*5)//6
            for i,c in enumerate(claims):
                cx=inner_x+i*(cw+gap)
                draw.rounded_rectangle((cx,inner_y,cx+cw,inner_y+inner_h),radius=5,fill="#fffef6" if i%2==0 else "#eefaff",outline="#3aaed5",width=1)
                icon(cx+11,inner_y+9,"gold" if i==0 else "oil" if i==1 else "japan" if i==2 else "btc" if i==5 else "news",14)
                draw.text((cx+22,inner_y+2),c.get("label",""),font=bold(11),fill=blue)
                direction="down" if any(v in c["text"] for v in ("弱気","下押し")) else "up" if ("強気" in c["text"] or "ドル高" in c["text"]) else "right"
                arrow(cx+cw-10,inner_y+8,direction,red if direction=="down" else "#088d5c" if direction=="up" else blue,4)
                text=c.get("text","")
                yy,clipped,lines=wrapped(cx+4,inner_y+18,text,cw-8,font=mini,fill=navy,leading=1,max_lines=max(1,(inner_h-18)//13))
                if clipped: overflow.append({"panel":no,"claim":c["id"],"required_lines":lines,"available_lines":(inner_h-19)//13})
        elif no == 14:
            icon(inner_x+24,inner_y+27,"clock",43)
            yy=inner_y
            for c in claims:
                yy,clipped,lines=put_claim(c,inner_x+51,yy,inner_w-53,font=bold(12),max_lines=3)
                if clipped: overflow.append({"panel":no,"claim":c["id"],"required_lines":lines,"available_lines":3})
                yy+=2
        elif no == 15:
            row_h=inner_h//max(1,len(claims))
            for i,c in enumerate(claims):
                ry=inner_y+i*row_h
                draw.line((inner_x,ry+row_h,inner_x+inner_w,ry+row_h),fill="#bad8ea",width=1)
                draw.text((inner_x,ry+2),c.get("label",""),font=bold(12),fill=blue)
                icon(inner_x+77,ry+row_h//2,"calendar",16)
                _,clipped,lines=put_claim(c,inner_x+92,ry+1,inner_w-95,font=mini,max_lines=max(1,row_h//14))
                if clipped: overflow.append({"panel":no,"claim":c["id"],"required_lines":lines,"available_lines":row_h//14})
        else:
            yy=inner_y
            for c in claims:
                icon(inner_x+11,yy+9,"light",20)
                yy,clipped,lines=put_claim(c,inner_x+26,yy,inner_w-28,font=mini,max_lines=max(1,(inner_h)//14))
                if clipped: overflow.append({"panel":no,"claim":c["id"],"required_lines":lines,"available_lines":inner_h//14})
                yy+=1
    image.save(output, format="PNG", optimize=True)
    return {"path": str(output), "size": list(image.size), "sha256": sha(output.read_bytes()),
            "layout": "approved-reference-1536x1024-fixed-16-panels", "overflow": overflow,
            "overflow_scope": "PILLOW_WRAP_LIMITS_ONLY; inter-claim pixel overlap and browser glyph bounds are not measured",
            "browser_render": "NOT_RUN"}


def write_reference_comparison(reference, candidate, output_dir):
    layout=layout_config(reference)
    output_dir=Path(output_dir)
    output_dir.mkdir(parents=True,exist_ok=True)
    with Image.open(reference) as ref, Image.open(candidate) as png:
        ref=ref.convert("RGB")
        png=png.convert("RGB")
        if ref.size != (1536,1024) or png.size != ref.size:
            fail("SUMMARY_COMPARISON_SIZE_MISMATCH",{"reference":ref.size,"candidate":png.size})
        overlay=Image.blend(ref,png,0.5)
        overlay.save(output_dir/"overlay-50pct.png",format="PNG",optimize=True)
        side=Image.new("RGB",(3072,1024),"white")
        side.paste(ref,(0,0)); side.paste(png,(1536,0))
        side.save(output_dir/"side-by-side.png",format="PNG",optimize=True)
    panel_geometry=[{"panel":panel["number"],"reference_rect":panel["reference_rect"],
                     "candidate_rect":panel["reference_rect"],"matches":True} for panel in layout["panels"]]
    result={"status":"GEOMETRY_MATCH","reference_sha256":layout["reference_sha256"],
            "candidate_sha256":sha(Path(candidate).read_bytes()),"dimensions":[1536,1024],
            "panel_count":16,"panel_geometry_matches":all(row["matches"] for row in panel_geometry),
            "visual_acceptance_status":"PENDING","human_visual_acceptance":"PENDING","panel_geometry":panel_geometry,
            "differences":[
                "固定16パネルの矩形・順序・横幅比率は承認layout.jsonと一致。",
                f"候補は本文を全文転記せず{len(json.loads((Path(candidate).parents[1]/'summary.json').read_text(encoding='utf-8'))['claims'])}件の出典付き要約claimsで構成。本文全体はsource-report.jsonに未変更で保持。",
                "承認画像の写真装飾cropを同じ位置で使用。図解アイコンはPillowのベクター図形で再構成し、細部は完全一致ではない。",
                "05は原文に時刻根拠がないため、承認画像の具体的HH:MMを再利用せず『寄り付き前・序盤・中盤・終盤・引け後』を表示。",
                "06は終値・前日比・騰落率の列を再現。07・08は各商品の観測時点を短い表/タイルで表示。",
                "09は実測値がないため流入/流出を『示唆』と明示し、因果を断定しない。",
                "13は6市場を横一列の同幅タイルに配置。",
                "候補は承認画像と異なる日本語フォント・文字組み・一部アイコンを使用する。余白、読みやすさ、因果関係の意味一致を人がレビューするまで視覚受入はPENDING。"
            ]}
    (output_dir/"visual-comparison.json").write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--authoring", type=Path, required=True)
    parser.add_argument("--reference", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report_bytes = args.report.read_bytes()
    report = json.loads(report_bytes.decode("utf-8-sig"))
    authoring = json.loads(args.authoring.read_text(encoding="utf-8-sig"))
    summary = build_summary(report, authoring)
    doc, contract = render_summary_html(report, summary, args.reference)
    out = args.output.resolve()
    if out.exists() or out == ROOT or ROOT not in out.parents:
        fail("SUMMARY_OUTPUT_MUST_BE_NEW_REVIEW_PATH")
    out.mkdir(parents=True)
    (out/"report.html").write_text(doc, encoding="utf-8", newline="\n")
    (out/"source-report.json").write_bytes(report_bytes)
    (out/"summary.json").write_text(json.dumps(summary,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    (out/"render-contract.json").write_text(json.dumps(contract,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    png = render_summary_png(report,summary,args.reference,out/"png"/"preview-2026-10-13_08-00-summary.png")
    comparison=write_reference_comparison(args.reference,png["path"],out/"comparison")
    (out/"validation.json").write_text(json.dumps({"status":"BLOCKED","reason":"HISTORICAL_SOURCE_WITHDRAWN; report identity/snapshot/bodyHash missing","summary_checks":contract["validation"],"render":png,"visual_comparison":comparison,"human_visual_review":"PENDING","publish_allowed":False},ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({"status":"DEBUG_PREVIEW_CREATED","claims":len(summary["claims"]),"png":png,"comparison":"created","human_visual_review":"PENDING","publish_allowed":False}))


if __name__ == "__main__":
    main()
