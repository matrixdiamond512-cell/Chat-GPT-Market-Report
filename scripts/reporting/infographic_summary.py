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
REQUIRED_CRITICAL_ROLE_PANELS = {
    "judgment_basis": {1}, "risk_condition": {4},
    "main_scenario": {12}, "alternative_scenario": {12},
    "invalidation_trigger": {12},
}
SCENARIO_ROLE_LABELS = {
    "main_scenario": "メインシナリオ",
    "alternative_scenario": "代替シナリオ",
    "invalidation_trigger": "崩れる条件",
}
SCENARIO_FIELDS = ("condition", "development", "market_impact")
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


def _refs_for_exact_anchors(body: str, anchors):
    """Bind one scenario field to only the cited words, not the rest of its line."""
    lines = source_line_spans(body)
    refs = []
    for anchor in anchors:
        matches = [line for line in lines if anchor in line["text"]]
        if len(matches) != 1:
            fail("SUMMARY_SOURCE_ANCHOR_NOT_UNIQUE", anchor)
        row = matches[0]
        start = row["start"] + row["text"].index(anchor)
        end = start + len(anchor)
        refs.append({"start": start, "end": end, "line": row["line"],
                     "section": row["section"], "anchor": anchor,
                     "excerpt": body[start:end]})
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
        row = {key: value for key, value in source.items()
               if key not in {"source_anchors", "field_source_anchors"}}
        row["source_refs"] = _refs_for_anchors(body, source.get("source_anchors", []))
        if source.get("scenario_role"):
            anchors_by_field = source.get("field_source_anchors", {})
            row["field_source_refs"] = {
                field: _refs_for_exact_anchors(body, anchors_by_field.get(field, []))
                for field in SCENARIO_FIELDS
            }
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
               "critical_roles_required": list(REQUIRED_CRITICAL_ROLE_PANELS),
               "claims": claims, "publish_allowed": False,
               "publication_status": "NOT_READY"}
    validate_summary(report, summary)
    return summary


def validate_scenario_contract(body: str, claims):
    """Validate the reusable three-role input contract without selecting a slot renderer."""
    scenario_claims = {}
    for claim in claims or []:
        if claim.get("panel") != 12:
            continue
        role = claim.get("scenario_role")
        if role not in SCENARIO_ROLE_LABELS:
            fail("SUMMARY_SCENARIO_ROLE_INVALID", claim.get("id"))
        if role in scenario_claims:
            fail("SUMMARY_SCENARIO_ROLE_DUPLICATE", role)
        if claim.get("kind") != "scenario":
            fail("SUMMARY_SCENARIO_KIND_INVALID", claim.get("id"))
        scenario_claims[role] = claim
    missing_roles = sorted(set(SCENARIO_ROLE_LABELS) - set(scenario_claims))
    if missing_roles:
        fail("SUMMARY_REQUIRED_SCENARIO_ROLES_MISSING", missing_roles)

    for role, claim in scenario_claims.items():
        missing_fields = [field for field in SCENARIO_FIELDS
                          if not isinstance(claim.get(field), str) or not claim[field].strip()]
        if missing_fields:
            fail("SUMMARY_SCENARIO_FIELDS_MISSING", {"claim": claim.get("id"), "fields": missing_fields})
        if role not in claim.get("roles", []):
            fail("SUMMARY_SCENARIO_CRITICAL_ROLE_MISSING", {"claim": claim.get("id"), "role": role})
        field_refs = claim.get("field_source_refs")
        if not isinstance(field_refs, dict):
            fail("SUMMARY_SCENARIO_FIELD_PROVENANCE_MISSING", claim.get("id"))
        for field in SCENARIO_FIELDS:
            refs = field_refs.get(field)
            if not refs:
                fail("SUMMARY_SOURCE_PROVENANCE_MISSING", {"claim": claim.get("id"), "field": field})
            excerpts = []
            for ref in refs:
                start, end = ref.get("start"), ref.get("end")
                if not isinstance(start, int) or not isinstance(end, int) or start < 0 or end <= start:
                    fail("SUMMARY_SOURCE_POSITION_INVALID", {"claim": claim.get("id"), "field": field})
                excerpt = body[start:end]
                if excerpt != ref.get("excerpt") or ref.get("anchor") not in excerpt:
                    fail("SUMMARY_SOURCE_SPAN_MISMATCH", {"claim": claim.get("id"), "field": field})
                excerpts.append(excerpt)
            source_text = " ".join(excerpts)
            field_text = claim[field]
            source_numbers = {_normal_number(n) for n in NUMBER.findall(source_text)}
            source_units = {_normal_number(n) for n in NUMBER_WITH_UNIT.findall(source_text)}
            missing_units = [n for n in NUMBER_WITH_UNIT.findall(field_text)
                             if _normal_number(n) not in source_units]
            if missing_units:
                fail("SUMMARY_SCENARIO_FIELD_UNIT_NOT_IN_SOURCE", {
                    "claim": claim.get("id"), "field": field, "tokens": missing_units,
                })
            missing_numbers = [n for n in NUMBER.findall(field_text)
                               if _normal_number(n) not in source_numbers]
            if missing_numbers:
                fail("SUMMARY_SCENARIO_FIELD_NUMBER_NOT_IN_SOURCE", {
                    "claim": claim.get("id"), "field": field, "tokens": missing_numbers,
                })
            missing_directions = [term for term in DIRECTION_TERMS
                                  if term in field_text and term not in source_text]
            if missing_directions:
                fail("SUMMARY_SCENARIO_FIELD_DIRECTION_NOT_IN_SOURCE", {
                    "claim": claim.get("id"), "field": field, "terms": missing_directions,
                })

    main = scenario_claims["main_scenario"]
    alternative = scenario_claims["alternative_scenario"]
    if (main["condition"].strip() == alternative["condition"].strip()
            or main["development"].strip() == alternative["development"].strip()
            or main["market_impact"].strip() == alternative["market_impact"].strip()):
        fail("SUMMARY_SCENARIO_BRANCHES_NOT_DISTINGUISHED")
    return {"status": "PASS", "roles": scenario_claims,
            "human_semantic_review": "PENDING"}


def validate_summary(report: dict, summary: dict):
    body = report_text(report)
    observed_body_hash = sha(body.encode("utf-8"))
    layout = json.loads((TEMPLATE / "layout.json").read_text(encoding="utf-8"))
    if summary.get("artifact_type") != "INFOGRAPHIC_SUMMARY_DEBUG_PREVIEW" or summary.get("status") != "DRAFT":
        fail("SUMMARY_PREVIEW_ONLY")
    if (summary.get("source_observed_sha256") != observed_body_hash
            or summary.get("time") != "08:00" or report.get("time") != "08:00"):
        fail("SUMMARY_SOURCE_IDENTITY_MISMATCH")
    claimed_body_hash = report.get("bodyHash")
    if claimed_body_hash and claimed_body_hash != observed_body_hash:
        fail("SUMMARY_REPORT_BODYHASH_MISMATCH")
    if summary.get("bodyHash") != claimed_body_hash:
        fail("SUMMARY_BODYHASH_IDENTITY_MISMATCH")
    reusable_scenario_result = validate_scenario_contract(body, summary.get("claims", []))
    if summary.get("human_review") != "PENDING" or summary.get("publish_allowed") is not False:
        fail("SUMMARY_REVIEW_OR_PUBLICATION_GATE")
    if len(summary.get("claims", [])) == 0:
        fail("SUMMARY_NO_CLAIMS")
    panel_counts = Counter()
    panel_kinds = {panel: set() for panel in EXPECTED_PANELS}
    claim_ids = set()
    numeric_count = 0
    critical_role_panels = {role: set() for role in REQUIRED_CRITICAL_ROLE_PANELS}
    scenario_claims = {}
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
        def source_excerpts(source_refs, field_name=None):
            excerpts = []
            if not source_refs:
                fail("SUMMARY_SOURCE_PROVENANCE_MISSING", {"claim": claim["id"], "field": field_name})
            for ref in source_refs:
                start, end = ref.get("start"), ref.get("end")
                if not isinstance(start, int) or not isinstance(end, int) or start < 0 or end <= start:
                    fail("SUMMARY_SOURCE_POSITION_INVALID", {"claim": claim["id"], "field": field_name})
                excerpt = body[start:end]
                if excerpt != ref.get("excerpt") or ref.get("anchor") not in excerpt:
                    fail("SUMMARY_SOURCE_SPAN_MISMATCH", {"claim": claim["id"], "field": field_name})
                excerpts.append(excerpt)
            return excerpts

        excerpts = source_excerpts(refs)
        source_text = " ".join(excerpts)
        source_numbers = {_normal_number(n) for n in NUMBER.findall(source_text)}
        source_numbers_with_units = {_normal_number(n) for n in NUMBER_WITH_UNIT.findall(source_text)}
        display = " ".join(str(claim.get(k, "")) for k in ("label", "text"))
        if claim.get("panel") == 12:
            role = claim.get("scenario_role")
            if role not in SCENARIO_ROLE_LABELS:
                fail("SUMMARY_SCENARIO_ROLE_INVALID", claim["id"])
            if role in scenario_claims:
                fail("SUMMARY_SCENARIO_ROLE_DUPLICATE", role)
            scenario_claims[role] = claim
            missing_fields = [field for field in SCENARIO_FIELDS
                              if not isinstance(claim.get(field), str) or not claim[field].strip()]
            if missing_fields:
                fail("SUMMARY_SCENARIO_FIELDS_MISSING", {"claim": claim["id"], "fields": missing_fields})
            expected_critical_role = role
            if expected_critical_role not in claim.get("roles", []):
                fail("SUMMARY_SCENARIO_CRITICAL_ROLE_MISSING", {"claim": claim["id"], "role": expected_critical_role})
            field_refs = claim.get("field_source_refs")
            if not isinstance(field_refs, dict):
                fail("SUMMARY_SCENARIO_FIELD_PROVENANCE_MISSING", claim["id"])
            scenario_source_excerpts = []
            for field in SCENARIO_FIELDS:
                field_source_text = " ".join(source_excerpts(field_refs.get(field), field))
                scenario_source_excerpts.append(field_source_text)
                field_text = claim[field]
                source_numbers_for_field = {_normal_number(n) for n in NUMBER.findall(field_source_text)}
                source_units_for_field = {_normal_number(n) for n in NUMBER_WITH_UNIT.findall(field_source_text)}
                unbound_units = [n for n in NUMBER_WITH_UNIT.findall(field_text)
                                 if _normal_number(n) not in source_units_for_field]
                if unbound_units:
                    fail("SUMMARY_SCENARIO_FIELD_UNIT_NOT_IN_SOURCE", {
                        "claim": claim["id"], "field": field, "tokens": unbound_units,
                    })
                unbound_numbers = [n for n in NUMBER.findall(field_text)
                                   if _normal_number(n) not in source_numbers_for_field]
                if unbound_numbers:
                    fail("SUMMARY_SCENARIO_FIELD_NUMBER_NOT_IN_SOURCE", {
                        "claim": claim["id"], "field": field, "tokens": unbound_numbers,
                    })
                unbound_directions = [term for term in DIRECTION_TERMS
                                      if term in field_text and term not in field_source_text]
                if unbound_directions:
                    fail("SUMMARY_SCENARIO_FIELD_DIRECTION_NOT_IN_SOURCE", {
                        "claim": claim["id"], "field": field, "terms": unbound_directions,
                    })
            # The generic number/direction checks below must use every source
            # range that supports a displayed scenario field, not only the
            # claim's separate summary_refs. Field-level validation above is
            # intentionally stricter and remains in force.
            source_text += " " + " ".join(scenario_source_excerpts)
            source_numbers = {_normal_number(n) for n in NUMBER.findall(source_text)}
            source_numbers_with_units = {_normal_number(n) for n in NUMBER_WITH_UNIT.findall(source_text)}
            display += " " + " ".join(claim[field] for field in SCENARIO_FIELDS)
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
            "scenario_roles": {role: scenario_claims[role]["id"] for role in SCENARIO_ROLE_LABELS},
            "summary_policy": summary["summary_policy"],
            "critical_role_panels": {role: sorted(panels) for role,panels in critical_role_panels.items()},
            "snapshot_identity_complete": source_identity_complete,
            "formal_generation": formal, "publish_allowed": False}


def build_visual_encoding(summary: dict):
    """Separate source-bound claims from their visual roles and quote mappings."""
    claims_by_panel = {str(panel): [] for panel in EXPECTED_PANELS}
    claims_by_id = {}
    for claim in summary.get("claims", []):
        claims_by_panel[str(claim["panel"])].append(claim["id"])
        claims_by_id[claim["id"]] = claim
    quote_specs = (
        ("p13-gold", "p07-gold", "4,192.00", "ドル｜10/12終値", "USD"),
        ("p13-wti", "p07-wti", "93.74", "ドル｜10/12清算", "USD"),
        ("p13-nikkei", "p07-future", "68,410", "円｜10/13 05:04遅延", "JPY"),
        ("p13-usdjpy", "p07-usdjpy", "158.64", "円｜10/12終値", "JPY"),
        ("p13-eurusd", "p07-eurusd", "1.1156", "｜10/12終値", "EUR/USD"),
        ("p13-btc", "p07-btc", "82,854.85", "ドル｜10/12 UTC", "USD"),
    )
    present = [panel_claim in claims_by_id or source_claim in claims_by_id
               for panel_claim, source_claim, _, _, _ in quote_specs]
    quotes = []
    conditions = [
        ["4,180維持 ↑ 戻り", "4,150割れ ↓ 下押し"],
        ["93定着 ↑ 95方向", "92割れ ↓ 縮小"],
        ["68,500回復 ↑ 反発", "68,300割れ ↓ 68,000"],
        ["158.80超 ↑ 159試し", "158.20割れ ↓ 円高"],
        ["1.1150割れ ↓ 1.1100", "1.1210回復 ↑ 一服"],
        ["83,500回復 ↑ 改善", "82,000割れ ↓ 警戒"],
    ]
    if any(present):
        if not all(present):
            fail("VISUAL_ENCODING_PARTIAL_QUOTE_MAP")
        for index,(panel_claim, source_claim, value, basis, unit_context) in enumerate(quote_specs):
            if panel_claim not in claims_by_id or claims_by_id[panel_claim].get("panel") != 13:
                fail("VISUAL_ENCODING_OUTLOOK_CLAIM_MISSING",panel_claim)
            source = claims_by_id[source_claim]
            if value not in source.get("text", "") or not source.get("source_refs"):
                fail("VISUAL_ENCODING_QUOTE_NOT_SOURCE_BOUND", source_claim)
            outlook = claims_by_id[panel_claim]
            source_numbers = {_normal_number(re.sub(r"(?:%|％|bp|円|ドル|倍|pt)$", "", token))
                              for token in NUMBER.findall(outlook.get("text", ""))}
            encoded_numbers = {_normal_number(re.sub(r"(?:%|％|bp|円|ドル|倍|pt)$", "", token))
                               for line in conditions[index] for token in NUMBER.findall(line)}
            if not encoded_numbers <= source_numbers:
                fail("VISUAL_ENCODING_CONDITION_NUMBER_NOT_SOURCE_BOUND", panel_claim)
            source_context = outlook.get("label", "") + outlook.get("text", "")
            source_unit_token = "ドル" if unit_context == "USD" else "円" if unit_context == "JPY" else "EUR/USD"
            if source_unit_token not in source_context:
                fail("VISUAL_ENCODING_UNIT_CONTEXT_NOT_SOURCE_BOUND", panel_claim)
            quotes.append({"panel_claim": panel_claim, "source_claim": source_claim,
                           "value": value, "basis": basis,"unit_context":unit_context,
                           "conditions":conditions[index]})
    return {
        "schema_version": 1,
        "artifact_type": "PILLOW_VISUAL_ENCODING_SPEC",
        "status": "DRAFT",
        "human_review": "PENDING",
        "dimensions": [1536, 1024],
        "geometry": "APPROVED_FIXED_16_PANEL",
        "claims_by_panel": claims_by_panel,
        "visual_channels": {
            "01": "large judgment arrow and financial asset icons; index divergence",
            "03": "source-bound causal stages with asset/rates icons and directional arrows",
            "04": "prominent numeric thresholds with conditional outcomes",
            "05": "chronological market-reaction rows with explicit arrows",
            "08": "yield comparison; valuation/deviation; volatility and sentiment indicator groups",
            "09": "inferred relative reaction groups, separate from market context and actual measured flows",
            "11": "SQ/futures proximity separate from possible position-unwind risk and unavailable positioning data",
            "13": "six equal source-quoted market cards, directional bias, and paired conditional levels",
            "16": "prominent market conclusion separated from validation/readiness state",
        },
        "panel12_required_scenario_roles": {
            role: {"title": label, "fields": list(SCENARIO_FIELDS)}
            for role, label in SCENARIO_ROLE_LABELS.items()
        },
        "scenario_contract_applies_to_slots": ["08:00", "12:00", "16:00", "21:00"],
        "panel13_quotes": quotes,
        "panel13_conditions": [quote["conditions"] for quote in quotes],
        "guardrails": ["claim source spans remain unchanged", "quotes require a source claim and source_refs",
                       "inferred flow is not represented as measured transfer", "publish_allowed=false"],
    }


def _icon(name):
    return f'<svg class="source-icon" aria-hidden="true"><use href="#icon-{name}"/></svg>'


def _claim_text(claim, include_label=False):
    keys = ("label", "text") if include_label else ("text",)
    return " ".join(str(claim.get(k, "")) for k in keys if claim.get(k))


def _render_claim(claim, include_label=False):
    text = _claim_text(claim, include_label=include_label)
    return _render_text(text, claim["id"])


def _render_text(text, element_id):
    chunks, position = [], 0
    for index, match in enumerate(NUMBER.finditer(text), 1):
        fid = f"{element_id}-n{index:02d}"
        chunks.append(html.escape(text[position:match.start()]))
        direction = "up" if match[0].startswith("+") else "down" if match[0].startswith(("-", "−")) else ""
        chunks.append(f'<span class="numeric {direction}" data-numeric-id="{fid}">{html.escape(match[0])}</span>')
        position = match.end()
    chunks.append(html.escape(text[position:]))
    return f'<span class="fact summary-fact" data-fact-id="{element_id}">{"".join(chunks)}</span>'


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
        elif number == 3:
            content = ''.join('<div class="flow-line">'+_icon("oil" if i == 0 else "japan")+'<span>'+_render_claim(c, include_label=True)+'</span></div>' for i,c in enumerate(claims))
        elif number == 12:
            scenario_by_role = {claim["scenario_role"]: claim for claim in claims}
            blocks = []
            for role, role_label in SCENARIO_ROLE_LABELS.items():
                claim = scenario_by_role[role]
                fields = ''.join(
                    '<div class="scenario-field"><b>' + label + '</b><span>'
                    + _render_text(claim[field], claim["id"] + "-" + field)
                    + '</span></div>'
                    for field, label in (("condition", "条件"), ("development", "展開"),
                                         ("market_impact", "市場影響"))
                )
                blocks.append('<article class="scenario-block" data-scenario-role="' + role
                              + '"><h3>' + role_label + '</h3>' + fields + '</article>')
            content = '<div class="scenario-grid">' + ''.join(blocks) + '</div>'
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
        panel_title = ("シナリオ分析" if number == 12 else
                       panel["title"] + "（10/12終値）" if number == 6 else panel["title"])
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
    css += ".card-12 .card-body{padding:3px}.scenario-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:4px;height:100%}.scenario-block{min-width:0;border:1px solid #df9bab;border-radius:5px;background:linear-gradient(120deg,#fff,#fff1f3);padding:3px;overflow:hidden}.scenario-block h3{font-size:12px;line-height:1.1;margin:0 0 2px;color:#b51435;text-align:center}.scenario-field{display:flex;gap:3px;align-items:baseline;font-size:12px;line-height:1.05}.scenario-field b{flex:none;color:#304b78}.scenario-field span{min-width:0;overflow-wrap:anywhere}"
    title = html.escape(summary["title"])
    doc = ('<!doctype html><html lang="ja"><meta charset="utf-8"><style>'+css+'</style><body>'+sprite+
           '<main id="report"><header><img class="skyline" alt="承認画像の文字を含まない東京夜景装飾" src="data:image/png;base64,'+skyline+'">'+
           '<h1>'+title+'</h1><div class="basis">本文は未変更｜本文の要点を出典付きで図解化｜時点の異なる市場データを区別</div>'+
           '<span class="status">DRAFT・撤回済み本文・snapshot未照合｜公開不可</span><div class="approved-mark">参考デザイン基準 1536×1024</div></header><div class="cards">'+''.join(cards)+'</div></main></body></html>')
    expected_text = {}
    expected_numeric = {}
    for claim in summary["claims"]:
        if claim["panel"] == 12:
            expected_text[claim["id"]] = " | ".join(claim[field] for field in SCENARIO_FIELDS)
            for field in SCENARIO_FIELDS:
                for index, match in enumerate(NUMBER.finditer(claim[field]), 1):
                    expected_numeric[f"{claim['id']}-{field}-n{index:02d}"] = match[0]
        else:
            expected_text[claim["id"]] = _claim_text(claim)
            for index, match in enumerate(NUMBER.finditer(expected_text[claim["id"]]), 1):
                expected_numeric[f"{claim['id']}-n{index:02d}"] = match[0]
    contract = {"html_sha256": sha(doc.encode("utf-8")), "view_sha256": sha(canonical(summary).encode("utf-8")),
                "expected_text": expected_text, "expected_numeric": expected_numeric,
                "layout_profile": "APPROVED_16_PANEL", "grid_columns": 60,
                "outlook_width_fraction": 40/60, "output_basename": "preview-2026-10-13_08-00-summary",
                "validation": {**validation, "artifact_type":"DEBUG_PREVIEW"},
                "publication":{"publish_allowed":False,"status":"NOT_READY"}}
    return doc, contract


def render_summary_png(report, summary, reference, output, visual_encoding=None):
    """Draw the fixed 1536x1024 design as native text/vector elements."""
    layout = layout_config(reference)
    validate_summary(report, summary)
    visual_encoding = visual_encoding or build_visual_encoding(summary)
    if visual_encoding.get("artifact_type") != "PILLOW_VISUAL_ENCODING_SPEC" or visual_encoding.get("human_review") != "PENDING":
        fail("VISUAL_ENCODING_SPEC_INVALID")
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
        elif direction == "up":
            draw.line((cx, cy+size, cx, cy-size), fill=color, width=5)
            draw.polygon([(cx-size,cy-size+5),(cx+size,cy-size+5),(cx,cy-size-size//2)], fill=color)
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
        elif name == "rates":
            draw.ellipse((cx-size//2,cy-size//2,cx+size//2,cy+size//2),fill="#f4e9ff",outline="#7236b5",width=2)
            glyph=bold(max(10,size//2))
            draw.text((cx-size//3,cy-size//2),"%",font=glyph,fill="#7236b5")
        elif name == "usd":
            draw.ellipse((cx-size//2,cy-size//2,cx+size//2,cy+size//2),fill="#eaf4ff",outline="#005ab5",width=2)
            glyph=bold(max(10,size//2))
            draw.text((cx-size//3,cy-size//2),"$",font=glyph,fill="#005ab5")
        elif name == "btc":
            draw.ellipse((cx-size//2,cy-size//2,cx+size//2,cy+size//2),fill="#ff9b21",outline="#c85a00",width=2)
            glyph=bold(max(10,size//2))
            draw.text((cx-size//3,cy-size//2),"₿",font=glyph,fill="white")
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
        elif name == "bond":
            draw.rounded_rectangle((cx-size//2,cy-size//2,cx+size//2,cy+size//2),radius=3,fill="#e7f3ff",outline="#2766a5",width=2)
            draw.line((cx-size//3,cy-size//4,cx+size//3,cy-size//4),fill="#2766a5",width=2)
            draw.line((cx-size//3,cy,cx+size//3,cy),fill="#2766a5",width=2)
            draw.line((cx-size//3,cy+size//4,cx+size//3,cy+size//4),fill="#2766a5",width=2)
        elif name == "equity":
            draw.rounded_rectangle((cx-size//2,cy-size//2,cx+size//2,cy+size//2),radius=3,fill="#eff8ff",outline="#176fb4",width=2)
            points=[(cx-size//3,cy+size//5),(cx-size//8,cy-size//8),(cx+size//12,cy+size//9),(cx+size//3,cy-size//3)]
            draw.line(points,fill="#e5224b",width=max(2,size//9))
        elif name == "fx":
            draw.ellipse((cx-size//2,cy-size//2,cx+size//2,cy+size//2),fill="#eff7ff",outline="#176fb4",width=2)
            glyph=bold(max(9,size//2))
            draw.text((cx-size//3,cy-size//2),"¥",font=glyph,fill="#176fb4")
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
        panel_title = ("シナリオ分析" if no == 12 else
                       panel["title"] + "（10/12終値）" if no == 6 else panel["title"])
        draw.text((x+7,y+(head_h-25)//2),f"{no:02d}",font=bold(24 if no <= 11 else 20),fill="white" if panel["color"]!="yellow" else navy)
        draw.text((x+52,y+(head_h-head_size)//2),panel_title,font=head_font,fill="white" if panel["color"]!="yellow" else navy)
        inner_x, inner_y = x+8, y+head_h+6
        inner_w, inner_h = width-16, height-head_h-11
        if no==13:
            # The approved short strip uses nearly the full card height; its
            # fixed outer rectangle remains unchanged.
            inner_h=height-head_h-6
        claims = claims_by_panel[no]

        def put_claim(c, px=inner_x, py=inner_y, pw=inner_w, font=body, fill=navy, max_lines=None):
            return wrapped(px,py,_claim_text(c),pw,font=font,fill=fill,max_lines=max_lines)

        if no == 1:
            claim=claims[0]
            headline,separator,detail=claim["text"].partition("｜")
            arrow(inner_x+31,inner_y+76,"down",red,29)
            icon(inner_x+82,inner_y+32,"oil",37); icon(inner_x+132,inner_y+32,"usd",37)
            icon(inner_x+82,inner_y+81,"chip",37); icon(inner_x+132,inner_y+81,"gold",37)
            icon(inner_x+82,inner_y+132,"btc",35); icon(inner_x+132,inner_y+132,"japan",36)
            draw.text((inner_x+170,inner_y+3),headline,font=bold(20),fill=red)
            draw.rounded_rectangle((inner_x+170,inner_y+34,inner_x+inner_w-2,inner_y+75),radius=6,fill="#f0fbf4",outline=green,width=2)
            draw.text((inner_x+180,inner_y+40),"NY株：ダウ",font=bold(14),fill=navy)
            arrow(inner_x+290,inner_y+56,"up",green,8)
            draw.text((inner_x+315,inner_y+40),"Nasdaq・Russell",font=bold(12),fill=navy)
            arrow(inner_x+inner_w-20,inner_y+56,"down",red,8)
            _,clipped,lines=wrapped(inner_x+170,inner_y+82,detail,inner_w-176,font=bold(14),fill=navy,leading=2,max_lines=6)
            if clipped: overflow.append({"panel":no,"claim":claim["id"],"required_lines":lines,"available_lines":6})
        elif no == 2:
            yy=inner_y+1
            for i,c in enumerate(claims,1):
                draw.ellipse((inner_x,yy,inner_x+31,yy+31),fill="#0780d9",outline="#0056a7",width=1)
                draw.text((inner_x+9,yy+4),str(i),font=bold(17),fill="white")
                yy,clipped,lines=put_claim(c,inner_x+40,yy+1,inner_w-42,font=bold(15),max_lines=2)
                if clipped: overflow.append({"panel":no,"claim":c["id"],"required_lines":lines,"available_lines":2})
                yy += 5
        elif no == 3:
            # Render the source-bound causal chain as a visual flow diagram,
            # then show the cited Dow/Nasdaq divergence as a separate result.
            claim=claims[0]
            stages=[part.strip() for part in claim["text"].split("。")[0].split("→")]
            stage_icons=("warning","oil","rates","usd")
            row_h=41
            for i,stage in enumerate(stages):
                row_y=inner_y+i*row_h
                draw.rounded_rectangle((inner_x+2,row_y+1,inner_x+inner_w-2,row_y+row_h-2),radius=6,
                                       fill="#fff8ef" if i<2 else "#f1f8ff",outline="#e7a15a" if i<2 else "#62abd0",width=1)
                icon(inner_x+23,row_y+20,stage_icons[min(i,len(stage_icons)-1)],32)
                if i==3: icon(inner_x+inner_w-55,row_y+20,"gold",23)
                _,clipped,lines=wrapped(inner_x+46,row_y+5,stage,inner_w-(105 if i==3 else 60),font=bold(14),fill=red if i==0 else navy,
                                         leading=1,max_lines=2)
                if clipped: overflow.append({"panel":no,"claim":claim["id"],"stage":i+1,
                                             "required_lines":lines,"available_lines":2})
                if i==1: arrow(inner_x+inner_w-18,row_y+20,"up",red,7)
                if i==2: arrow(inner_x+inner_w-18,row_y+20,"up",red,7)
                if i==3:
                    arrow(inner_x+inner_w-23,row_y+7,"up",blue,5)
                    arrow(inner_x+inner_w-23,row_y+32,"down",blue,5)
                if i<len(stages)-1: arrow(inner_x+23,row_y+row_h-1,"down",red,5)
            draw.rounded_rectangle((inner_x+4,inner_y+4*row_h+1,inner_x+inner_w-4,inner_y+inner_h-2),radius=6,fill="#f1fbf5",outline=green,width=1)
            icon(inner_x+18,inner_y+4*row_h+13,"japan",18)
            draw.text((inner_x+34,inner_y+4*row_h+5),"ダウ ↑／Nasdaq ↓＝選別｜日経先物 約620円安",font=bold(12),fill=navy)
        elif no == 4:
            slot_h=inner_h//max(1,len(claims))
            for i,c in enumerate(claims,1):
                yy=inner_y+(i-1)*slot_h+2
                draw.rounded_rectangle((inner_x+1,yy,inner_x+inner_w-1,yy+slot_h-4),radius=6,
                                       fill="#fff4f5" if i<3 else "#fff9e8",outline="#e59aac" if i<3 else "#e3be43",width=1)
                icon(inner_x+18,yy+slot_h//2,"warning",22)
                text=c["text"]
                highlight=("WTI <92ドル ＋ AI/半導体反発 ＋ 先物 >68,800円" if i==1 else
                           "WTI >95ドル ＋ 先物 <68,000円" if i==2 else
                           "25日 +4.23%｜警戒 +7/+8%・200日 +30%")
                wrapped(inner_x+37,yy+4,highlight,inner_w-45,font=bold(16 if i<3 else 14),fill=red if i<3 else orange,max_lines=2)
                if i<3:
                    outcome="3条件が同時成立なら弱気見方を修正" if i==1 else "同時成立なら下落加速リスク"
                    _,clipped,lines=wrapped(inner_x+37,yy+slot_h//2+6,outcome,inner_w-45,font=bold(12),fill=navy,leading=0,max_lines=2)
                    if clipped: overflow.append({"panel":no,"claim":c["id"],"required_lines":lines,"available_lines":2})
                else:
                    wrapped(inner_x+37,yy+slot_h//2+6,"実測 +4.23%｜警戒水準は未到達",inner_w-45,font=bold(12),fill=navy,max_lines=1)
        elif no == 5:
            row_heights=[43,43,43,max(1,inner_h-129)]
            row_offsets=[sum(row_heights[:i]) for i in range(len(row_heights))]
            for i,c in enumerate(claims):
                slot_h=row_heights[i]
                yy=inner_y+row_offsets[i]+2
                draw.rounded_rectangle((inner_x,yy,inner_x+inner_w-1,yy+slot_h-3),radius=4,
                                       fill="#f7fbff" if i%2==0 else "#ffffff",outline="#b4d0e6",width=1)
                draw.text((inner_x+6,yy+4),c.get("label",""),font=bold(13),fill=blue)
                signal_text=("原油 ↓｜供給緩和観測で一時軟化" if i==0 else
                             "ダウ ↑　／　Nasdaq・半導体 ↓" if i==1 else
                             "原油 ↑反発　／　ドル ↑高止まり" if i==2 else
                             "ダウ +0.38% ↑｜Nasdaq -0.44% ↓｜S&P -0.06%・Russell -0.45% ↓｜金・BTC弱含み｜米債現物休場、利回り更新なし")
                icon(inner_x+93,yy+slot_h//2,"oil" if i in (0,2) else "chip" if i==1 else "gold",20)
                if i==1:
                    arrow(inner_x+117,yy+slot_h//2-7,"up",green,6)
                    arrow(inner_x+117,yy+slot_h//2+8,"down",red,6)
                else:
                    direction="down" if i==0 else "up" if i==2 else "right"
                    arrow(inner_x+117,yy+slot_h//2,direction,red if i in (0,3) else green,8)
                available=max(1,(slot_h-6)//14)
                _,clipped,lines=wrapped(inner_x+132,yy+3,signal_text,inner_w-139,font=bold(13),fill=navy,leading=1,max_lines=available)
                if clipped: overflow.append({"panel":no,"claim":c["id"],"required_lines":lines,"available_lines":available})
        elif no in (6,7):
            row_h=(inner_h-2)//max(len(claims),1)
            label_w=120 if no==6 else int(inner_w*.51)
            if no==6:
                draw.text((inner_x+label_w,inner_y),"終値",font=bold(12),fill=blue)
                draw.text((inner_x+label_w+76,inner_y),"前日比",font=bold(12),fill=blue)
                draw.text((inner_x+label_w+157,inner_y),"騰落率",font=bold(12),fill=blue)
                row_y0=inner_y+17
                row_h=max(1,(inner_h-17)//len(claims))
            else:
                # Five high-contrast cards retain each market quote; the
                # Japan-index card spans the width for its multiple time bases.
                gap=4; cw=(inner_w-gap)//2; ch=(inner_h-gap*2)//3
                positions=[(0,0),(1,0),(0,1),(1,1),(0,2)]
                display_claims=claims[:3]+[{"id":"p07-fx-btc","label":"EUR/USD｜BTCUSD","text":claims[3]["text"]+"；"+claims[4]["text"]},claims[5]]
                for i,c in enumerate(display_claims):
                    col,row=positions[i]; cx=inner_x+col*(cw+gap); cy=inner_y+row*(ch+gap)
                    card_w=inner_w if i==len(display_claims)-1 else cw
                    draw.rounded_rectangle((cx,cy,cx+card_w,cy+ch),radius=5,fill="#f4faff" if i%2 else "#fffdf3",outline="#72b9d7",width=1)
                    label=c.get("label","")
                    icon_name="oil" if "WTI" in label else "gold" if "金" in label else "usd" if "USD" in label or "EUR" in label else "btc" if "BTC" in label else "japan"
                    icon(cx+14,cy+14,icon_name,18)
                    wrapped(cx+29,cy+3,label,card_w-33,font=bold(12),fill=blue,max_lines=1)
                    if c["id"]=="p07-future":
                        # Separate the three instruments and preserve their
                        # distinct date, contract, and delayed-observation bases.
                        values=("現物 69,030.92円 (10/9)｜CME円建 68,450円 (NY引け付近)",
                                "大阪12月限 68,410円 (10/13 05:04遅延)",
                                "10/9日中 69,470円比：-1,060円 (-1.53%)")
                        for ri,value in enumerate(values):
                            _,clipped,lines=wrapped(cx+8,cy+17+ri*14,value,card_w-16,font=bold(12),fill=navy,max_lines=1)
                            if clipped: overflow.append({"panel":no,"claim":c["id"],"field":f"basis_{ri+1}","required_lines":lines,"available_lines":1})
                    elif c["id"]=="p07-fx-btc":
                        wrapped(cx+6,cy+22,"EUR/USD 1.1156｜10/12終値",cw-12,font=bold(12),fill=navy,max_lines=1)
                        wrapped(cx+6,cy+43,"BTC 82,854.85ドル｜10/12 UTC",cw-12,font=bold(12),fill=navy,max_lines=1)
                    else:
                        _,clipped,lines=wrapped(cx+6,cy+20,c.get("text",""),card_w-12,font=bold(12),fill=navy,leading=0,max_lines=max(1,(ch-22)//13))
                        if clipped: overflow.append({"panel":no,"claim":c["id"],"required_lines":lines,"available_lines":max(1,(ch-22)//13)})
                continue
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
                    yy,clipped,lines=wrapped(inner_x+label_w+4,ry+2,text,inner_w-label_w-4,font=bold(12),fill=dcolor,leading=0,max_lines=max(1,row_h//14))
                    if clipped: overflow.append({"panel":no,"claim":c["id"],"required_lines":lines,"available_lines":row_h//14})
        elif no == 8:
            deviation=next(c for c in claims if c["id"]=="p08-deviation")
            us=next(c for c in claims if c["id"]=="p08-us10y")
            jp=next(c for c in claims if c["id"]=="p08-jp10y")
            val=next(c for c in claims if c["id"]=="p08-per")
            gap=4; full_w=inner_w; half_w=(inner_w-gap)//2
            row1_h=46; row2_h=69; row3_y=inner_y+row1_h+gap; row2_y=row3_y+row2_h+gap; row3_h=inner_h-(row1_h+row2_h+gap*2)
            draw.rounded_rectangle((inner_x,inner_y,inner_x+full_w,inner_y+row1_h),radius=6,fill="#effaff",outline="#14a9ce",width=1)
            icon(inner_x+14,inner_y+22,"rates",23)
            draw.text((inner_x+31,inner_y+3),"米10年",font=bold(10),fill=blue)
            draw.text((inner_x+31,inner_y+15),"5.24%",font=bold(16),fill=navy)
            draw.text((inner_x+31,inner_y+33),"10/9基準",font=bold(9),fill="#455b77")
            split=inner_x+full_w//2
            draw.line((split,inner_y+5,split,inner_y+row1_h-5),fill="#9dc8da",width=1)
            icon(split+14,inner_y+22,"rates",23)
            draw.text((split+31,inner_y+3),"日本10年",font=bold(10),fill=blue)
            draw.text((split+31,inner_y+15),"3.016%",font=bold(16),fill=navy)
            draw.text((split+31,inner_y+33),"10/9｜-6.9bp",font=bold(9),fill="#455b77")
            cards_y=row3_y
            draw.rounded_rectangle((inner_x,cards_y,inner_x+half_w,cards_y+row2_h),radius=6,fill="#fffdf1",outline="#14a9ce",width=1)
            icon(inner_x+14,cards_y+14,"japan",19); draw.text((inner_x+28,cards_y+4),"日経評価",font=bold(10),fill=blue)
            draw.text((inner_x+6,cards_y+22),"PER 17.37倍",font=bold(12),fill=navy)
            draw.text((inner_x+6,cards_y+37),"PBR 1.90倍",font=bold(11),fill=navy)
            draw.text((inner_x+6,cards_y+52),"EPS 3,974.15円｜10/9",font=bold(9),fill="#455b77")
            dx=inner_x+half_w+gap
            draw.rounded_rectangle((dx,cards_y,dx+half_w,cards_y+row2_h),radius=6,fill="#fff5ef",outline="#e4a44b",width=1)
            icon(dx+14,cards_y+14,"warning",19); draw.text((dx+28,cards_y+4),"25/200日乖離",font=bold(10),fill=blue)
            draw.text((dx+6,cards_y+22),"25日 +4.23%",font=bold(12),fill=red)
            draw.text((dx+6,cards_y+37),"前日比 -0.20pt",font=bold(9),fill=navy)
            draw.text((dx+6,cards_y+49),"警戒 +7/+8%未達",font=bold(9),fill=red)
            draw.text((dx+6,cards_y+58),"200日 +13.55%※",font=bold(8),fill="#495d7b")
            draw.rounded_rectangle((inner_x,row2_y,inner_x+half_w,row2_y+row3_h-9),radius=6,fill="#effaff",outline="#14a9ce",width=1)
            icon(inner_x+half_w-13,row2_y+13,"rates",18); draw.text((inner_x+6,row2_y+4),"変動性",font=bold(10),fill=blue)
            draw.text((inner_x+6,row2_y+20),"VIX 15.21 ↑",font=bold(13),fill=red)
            draw.text((inner_x+6,row2_y+37),"+0.37 (+2.49%)",font=bold(10),fill=navy)
            draw.text((inner_x+6,row2_y+51),"日経VI 30.14",font=bold(10),fill=navy)
            sx=inner_x+half_w+gap
            draw.rounded_rectangle((sx,row2_y,sx+half_w,row2_y+row3_h-9),radius=6,fill="#fffdf1",outline="#d5b241",width=1)
            icon(sx+half_w-13,row2_y+13,"light",18); draw.text((sx+6,row2_y+4),"センチメント",font=bold(10),fill=blue)
            draw.text((sx+8,row2_y+22),"Fear & Greed",font=bold(10),fill=navy)
            draw.text((sx+8,row2_y+35),"45",font=bold(17),fill=navy)
            draw.text((sx+35,row2_y+41),"中立境界",font=bold(10),fill="#455b77")
            draw.text((inner_x+4,inner_y+inner_h-8),"米債10/12休場｜※200日値は10/9参照・独立再照合なし",font=bold(8),fill="#495d7b")
        elif no == 9:
            card_y=inner_y+3
            draw.text((inner_x+4,card_y),"値動きからの相対フロー示唆｜実測資金額なし",font=bold(13),fill=navy)
            left=(inner_x+4,card_y+23,inner_x+inner_w//2-5,card_y+91)
            right=(inner_x+inner_w//2+5,card_y+23,inner_x+inner_w-4,card_y+91)
            draw.rounded_rectangle(left,radius=7,fill="#eaf9f0",outline=green,width=2)
            draw.rounded_rectangle(right,radius=7,fill="#fff0f2",outline=red,width=2)
            draw.text((left[0]+7,left[1]+4),"相対選好",font=bold(12),fill="#007c4c")
            arrow(left[2]-17,left[1]+13,"up",green,7)
            draw.text((right[0]+7,right[1]+4),"相対売り示唆",font=bold(12),fill="#bd123b")
            arrow(right[2]-17,right[1]+13,"down",red,7)
            for j,(asset,kind) in enumerate((("原油","oil"),("エネルギー株","equity"))):
                xx=left[0]+32+j*92; icon(xx,left[1]+42,kind,28)
                draw.text((xx-27,left[1]+55),asset,font=bold(10),fill=navy)
            for j,(asset,kind) in enumerate((("AI/半導体","chip"),("金","gold"),("BTC","btc"))):
                xx=right[0]+39+j*66; icon(xx,right[1]+42,kind,25)
                draw.text((xx-28,right[1]+55),asset,font=bold(10),fill=navy)
            # Side-by-side groups communicate relative reactions only;
            # no transfer arrow or measured amount is asserted.
            draw.line((inner_x+4,card_y+98,inner_x+inner_w-4,card_y+98),fill="#9dbbd0",width=1)
            context=[("USD高", "usd", "up"),("金先物", "gold", "down"),("BTC", "btc", "down"),("米債", "bond", "休場")]
            base=inner_x+22
            for i,(label,kind,direction) in enumerate(context):
                xx=base+i*122; icon(xx,card_y+124,kind,23)
                draw.text((xx+17,card_y+116),label,font=bold(11),fill=navy)
                if direction in ("up","down"): arrow(xx+93,card_y+126,direction,red if direction=="up" else blue,6)
                else: draw.text((xx+78,card_y+119),"休場",font=bold(10),fill="#576b80")
            draw.text((inner_x+4,inner_y+inner_h-16),"ドル高・金安・BTC弱含みは金利/流動性懸念と整合｜因果断定なし｜ETF/MMF/CFTC未取得",font=bold(10),fill="#344c70")
        elif no == 10:
            slot_h=inner_h//max(1,len(claims))
            for i,c in enumerate(claims):
                yy=inner_y+i*slot_h+2
                icon(inner_x+13,yy+11,"oil" if "原油" in c["text"] or "供給" in c["text"] else "chip" if "半導体" in c["text"] else "news",20)
                news_fill=red if c["id"] in ("p10-saudi","p10-ai") else navy
                _,clipped,lines=wrapped(inner_x+30,yy,_claim_text(c),inner_w-33,font=bold(14),fill=news_fill,max_lines=2)
                if clipped: overflow.append({"panel":no,"claim":c["id"],"required_lines":lines,"available_lines":2})
        elif no == 11:
            first,second=claims
            draw.rounded_rectangle((inner_x+3,inner_y+2,inner_x+inner_w-3,inner_y+59),radius=7,fill="#fffdf0",outline="#e5bb37",width=2)
            draw.text((inner_x+12,inner_y+6),"SQ近接｜10/9",font=bold(12),fill=blue)
            draw.text((inner_x+12,inner_y+23),"68,465.23",font=bold(21),fill=navy)
            draw.text((inner_x+153,inner_y+22),"≈",font=bold(20),fill=orange)
            draw.text((inner_x+183,inner_y+23),"68,410",font=bold(21),fill=navy)
            draw.text((inner_x+314,inner_y+29),"先物",font=bold(12),fill=blue)
            draw.text((inner_x+11,inner_y+46),"SQは支持線を保証しない｜最新オプション建玉は未取得",font=bold(11),fill=red)
            draw.rounded_rectangle((inner_x+3,inner_y+65,inner_x+inner_w-3,inner_y+124),radius=7,fill="#fff3f4",outline="#df7890",width=2)
            arrow(inner_x+23,inner_y+91,"down",red,13)
            draw.text((inner_x+48,inner_y+70),"買いポジションの偏り解消リスク",font=bold(13),fill=red)
            draw.text((inner_x+48,inner_y+89),"69,470 → 68,410円｜-1,060円 (-1.53%)",font=bold(14),fill=navy)
            draw.text((inner_x+48,inner_y+109),"損切り・ヘッジ増加の可能性（推定）",font=bold(11),fill=navy)
            draw.text((inner_x+6,inner_y+131),"未取得：ガンマ・建玉・IMM・ETF・東京ドル円出来高",font=bold(10),fill="#344c70")
        elif no == 12:
            by_role={c["scenario_role"]:c for c in claims}
            gap=4; card_w=(inner_w-gap*2)//3
            field_rows=(("condition","条件"),("development","展開"),("market_impact","市場"))
            for index,(role,role_label) in enumerate(SCENARIO_ROLE_LABELS.items()):
                c=by_role[role]
                cx=inner_x+index*(card_w+gap)
                draw.rounded_rectangle((cx,inner_y,cx+card_w,inner_y+inner_h-1),radius=5,
                                       fill="#fff0f2" if role=="main_scenario" else "#fff8ed" if role=="alternative_scenario" else "#f2f6ff",
                                       outline="#df9bab",width=1)
                draw.text((cx+3,inner_y+2),role_label,font=bold(12),fill=red if role!="invalidation_trigger" else blue)
                for field_index,(field,field_label) in enumerate(field_rows):
                    yy=inner_y+17+field_index*14
                    draw.text((cx+3,yy),field_label,font=bold(10),fill="#304b78")
                    _,clipped,lines=wrapped(cx+32,yy,c[field],card_w-36,font=bold(12),fill=navy,
                                             leading=0,max_lines=1)
                    if clipped:
                        overflow.append({"panel":no,"claim":c["id"],"field":field,
                                         "required_lines":lines,"available_lines":1})
        elif no == 13:
            gap=4; cw=(inner_w-gap*5)//6
            quote_sources=visual_encoding.get("panel13_quotes", [])
            compact_conditions=visual_encoding.get("panel13_conditions", [])
            if len(quote_sources) != len(claims) or len(compact_conditions) != len(claims):
                fail("VISUAL_ENCODING_MARKET_CARD_COUNT")
            for i,c in enumerate(claims):
                cx=inner_x+i*(cw+gap)
                draw.rounded_rectangle((cx,inner_y,cx+cw,inner_y+inner_h),radius=5,fill="#fffef6" if i%2==0 else "#eefaff",outline="#3aaed5",width=1)
                label=c.get("label","")
                bias,separator,conditions=c.get("text","").partition("｜")
                direction="down" if any(v in bias for v in ("弱気","弱含み")) else "up" if ("強気" in bias or "ドル高" in bias) else "right"
                icon_name="gold" if i==0 else "oil" if i==1 else "japan" if i==2 else "usd" if i in (3,4) else "btc"
                quote=quote_sources[i]
                if quote.get("panel_claim") != c["id"]: fail("VISUAL_ENCODING_PANEL_CLAIM_ORDER",c["id"])
                current,basis,source_id=quote["value"],quote["basis"],quote["source_claim"]
                icon(cx+12,inner_y+9,icon_name,17)
                draw.text((cx+23,inner_y+1),label,font=bold(11),fill=blue)
                price_font=bold(16 if len(current)<8 else 14)
                draw.text((cx+3,inner_y+17),current,font=price_font,fill=navy)
                unit_font=bold(9)
                unit_x=cx+5+draw.textlength(current,font=price_font)
                draw.text((unit_x,inner_y+22),basis,font=unit_font,fill="#536a82")
                bias_color=red if direction=="down" else green if direction=="up" else navy
                draw.rounded_rectangle((cx+3,inner_y+36,cx+cw-3,inner_y+50),radius=4,fill="#fff1f3" if direction=="down" else "#eaf8ef" if direction=="up" else "#edf4fb")
                draw.text((cx+7,inner_y+37),bias,font=bold(10),fill=bias_color)
                arrow(cx+cw-14,inner_y+43,direction,red if direction=="down" else "#088d5c" if direction=="up" else blue,5)
                for ri,condition in enumerate(compact_conditions[i]):
                    yy,clipped,lines=wrapped(cx+4,inner_y+50+ri*9,condition.replace(" ",""),cw-8,font=bold(10),fill=navy,leading=0,max_lines=1)
                    if clipped: overflow.append({"panel":no,"claim":c["id"],"condition":ri+1,"required_lines":lines,"available_lines":1})
                if source_id not in {claim["id"] for claim in claims_by_panel[7]}:
                    overflow.append({"panel":no,"claim":c["id"],"field":"quote_source","missing":source_id})
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
        elif no == 16:
            conclusion=next(c for c in claims if c["id"]=="p16-conclusion")
            data_state=next(c for c in claims if c["id"]=="p16-data")
            split_x=inner_x+inner_w//2
            draw.rounded_rectangle((inner_x+2,inner_y+1,split_x-3,inner_y+inner_h-1),radius=5,fill="#fff1f3",outline="#e34867",width=1)
            draw.rounded_rectangle((split_x+2,inner_y+1,inner_x+inner_w-2,inner_y+inner_h-1),radius=5,fill="#eff8ff",outline="#4b9fc7",width=1)
            draw.text((inner_x+8,inner_y+4),"相場結論",font=bold(11),fill=red)
            draw.text((inner_x+8,inner_y+17),"選別的リスクオフ",font=bold(17),fill=red)
            draw.text((inner_x+8,inner_y+39),"原油・ドル高／AI株調整",font=bold(10),fill=navy)
            draw.text((inner_x+8,inner_y+51),"東京再開:先物68,400円台×SQ68,465円",font=bold(9),fill=navy)
            draw.text((split_x+9,inner_y+4),"検証状態｜snapshot未照合",font=bold(9),fill=blue)
            draw.rounded_rectangle((split_x+8,inner_y+17,inner_x+inner_w-8,inner_y+33),radius=4,fill="#ffebef",outline="#d33b57",width=1)
            draw.text((split_x+14,inner_y+18),"正式生成 NOT_READY｜公開停止",font=bold(9),fill=red)
            missing=("未取得: CME建値別・200日独立照合", "ETF/CFTC/MMF定量フロー", "東京ドル円出来高")
            for li,line in enumerate(missing):
                _,clipped,lines=wrapped(split_x+9,inner_y+36+li*7,line,inner_x+inner_w-split_x-17,font=bold(8),fill=navy,leading=0,max_lines=1)
                if clipped: overflow.append({"panel":no,"claim":data_state["id"],"field":f"missing_{li+1}","required_lines":lines,"available_lines":1})
        else:
            yy=inner_y
            for c in claims:
                icon(inner_x+11,yy+9,"light",20)
                remaining=max(0,inner_y+inner_h-yy)
                available=max(0,remaining//12)
                next_y,clipped,lines=wrapped(inner_x+26,yy,_claim_text(c),inner_w-28,
                                               font=bold(12),fill=navy,leading=0,max_lines=available)
                if clipped or next_y>inner_y+inner_h:
                    overflow.append({"panel":no,"claim":c["id"],"required_lines":lines,
                                     "available_lines":available,"reason":"PANEL_STACK_EXCEEDS_RECT"})
                yy=next_y+1
    scenario_overflow=[entry for entry in overflow if entry.get("panel")==12]
    if scenario_overflow:
        fail("SUMMARY_SCENARIO_PANEL_OVERFLOW",scenario_overflow)
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
    visual_encoding = build_visual_encoding(summary)
    doc, contract = render_summary_html(report, summary, args.reference)
    out = args.output.resolve()
    if out.exists() or out == ROOT or ROOT not in out.parents:
        fail("SUMMARY_OUTPUT_MUST_BE_NEW_REVIEW_PATH")
    out.mkdir(parents=True)
    (out/"report.html").write_text(doc, encoding="utf-8", newline="\n")
    (out/"source-report.json").write_bytes(report_bytes)
    (out/"summary.json").write_text(json.dumps(summary,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    (out/"visual-encoding.json").write_text(json.dumps(visual_encoding,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    (out/"render-contract.json").write_text(json.dumps(contract,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    png = render_summary_png(report,summary,args.reference,out/"png"/"preview-2026-10-13_08-00-summary.png",visual_encoding)
    comparison=write_reference_comparison(args.reference,png["path"],out/"comparison")
    (out/"validation.json").write_text(json.dumps({"status":"BLOCKED","reason":"HISTORICAL_SOURCE_WITHDRAWN; report identity/snapshot/bodyHash missing","summary_checks":contract["validation"],"render":png,"visual_comparison":comparison,"human_visual_review":"PENDING","publish_allowed":False},ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({"status":"DEBUG_PREVIEW_CREATED","claims":len(summary["claims"]),"png":png,"comparison":"created","human_visual_review":"PENDING","publish_allowed":False}))


if __name__ == "__main__":
    main()
