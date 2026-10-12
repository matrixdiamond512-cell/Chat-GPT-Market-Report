"""Source-locked, fixed-grid renderer and fail-closed gate for 08:00 reports."""
from __future__ import annotations

import hashlib
import json
import re
import copy
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[2]
CONFIG_PATH = ROOT / "config" / "infographic_0800_fixed_v1.json"
SCHEMA_PATH = ROOT / "schemas" / "infographic-0800-fixed-source.schema.json"
SNAPSHOT_SCHEMA_PATH = ROOT / "schemas" / "market-data-snapshot.schema.json"
CONFIG = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
SCHEMA = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
SNAPSHOT_SCHEMA = json.loads(SNAPSHOT_SCHEMA_PATH.read_text(encoding="utf-8"))
WIDTH = CONFIG["canvas"]["width"]
DISPLAY_WIDTH = CONFIG["canvas"]["target_display_width"]
SCALE = DISPLAY_WIDTH / WIDTH
MARGIN = 12
GAP = 8
GRID_GAP = 10
BODY_SIZE = CONFIG["canvas"]["minimum_body_font_px"]
HEADING_SIZE = CONFIG["canvas"]["panel_heading_font_px"]
COLORS = {
    "navy": "#08295A", "navy2": "#0A4C93", "white": "#FFFFFF", "background": "#F2F7FB",
    "text": "#0D2D5D", "line": "#94B9DE", "blue": "#DDEEFF", "blue2": "#B7D9F4",
    "red": "#C42B32", "redbg": "#FFF0EF", "green": "#17804B", "greenbg": "#E6F5EC",
    "orange": "#F07822", "yellow": "#FFF3C5", "muted": "#496887",
}
EXPECTED_IDS = [item["id"] for item in CONFIG["sections"]]
SECTION_BY_ID = {item["id"]: item for item in CONFIG["sections"]}
FIXED_LAYOUT = CONFIG["fixed_layout"]
FIXED_ZONES = FIXED_LAYOUT["zones"]
EXPECTED_PANEL_IDS = [zone["section_id"] for zone in FIXED_ZONES]
EXPECTED_MARKETS = SECTION_BY_ID["six_market_outlook"]["markets"]
FONT_CANDIDATES = {
    False: ["C:/Windows/Fonts/meiryo.ttc", "C:/Windows/Fonts/YuGothR.ttc"],
    True: ["C:/Windows/Fonts/meiryob.ttc", "C:/Windows/Fonts/YuGothB.ttc"],
}


def _font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    for candidate in FONT_CANDIDATES[bold]:
        if Path(candidate).is_file():
            return ImageFont.truetype(candidate, size)
    raise RuntimeError("RENDER_FONT_UNAVAILABLE")


def _wrap(draw: ImageDraw.ImageDraw, value: str, font: ImageFont.FreeTypeFont, width: int) -> list[str]:
    lines: list[str] = []
    paragraphs = str(value).splitlines() or [""]
    for paragraph in paragraphs:
        current = ""
        for char in paragraph:
            test = current + char
            if current and draw.textlength(test, font=font) > width:
                lines.append(current)
                current = char
            else:
                current = test
        lines.append(current)
    return lines or [""]


def _fact_map(source: dict) -> dict[str, dict]:
    facts = source.get("structured_facts")
    result: dict[str, dict] = {}
    if not isinstance(facts, list):
        return result
    for fact in facts:
        if not isinstance(fact, dict) or not fact.get("fact_id") or fact["fact_id"] in result:
            return {}
        result[fact["fact_id"]] = fact
    return result


def _numbered_source_count(facts: list[dict]) -> int:
    count = 0
    for fact in facts:
        text = str(fact.get("text", ""))
        markers = re.findall(r"[①②③④⑤]", text)
        count += len(markers) if markers else 1
    return count


def _canonical_hash(value: dict) -> str:
    packed = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(packed.encode("utf-8")).hexdigest()


def _snapshot_integrity(source: dict, facts: dict[str, dict]) -> dict[str, Any]:
    snapshot = source.get("market_data_snapshot")
    failures: list[str] = []
    if not isinstance(snapshot, dict):
        return {"status": "FAIL", "errors": ["MARKET_DATA_SNAPSHOT_MISSING"]}
    for key in SNAPSHOT_SCHEMA["required"]:
        if key not in snapshot:
            failures.append(f"SNAPSHOT_FIELD_MISSING:{key}")
    known = set(SNAPSHOT_SCHEMA["properties"])
    failures.extend(f"SNAPSHOT_FIELD_UNEXPECTED:{key}" for key in snapshot if key not in known)
    provenance = snapshot.get("snapshot_provenance")
    if provenance not in ("LIVE_CAPTURED", "SOURCE_RECONSTRUCTED", "SYNTHETIC_FIXTURE"):
        failures.append("SNAPSHOT_PROVENANCE_INVALID")
    synthetic = source.get("synthetic_fixture") is True
    if synthetic != (provenance == "SYNTHETIC_FIXTURE" and source.get("source_type") == "SYNTHETIC_FIXTURE"):
        failures.append("SYNTHETIC_FIXTURE_PROVENANCE_MISMATCH")
    expected_fields = {
        "snapshot_id": source.get("source_snapshot_id"), "report_id": source.get("report_id"),
        "report_as_of": source.get("report_datetime"), "source_document_id": source.get("source_document_id"),
        "source_document_revision": source.get("revision"),
        "source_document_created_at": source.get("source_created_at"),
        "source_document_updated_at": source.get("source_updated_at"),
        "source_body_sha256": source.get("body_hash"),
    }
    for key, expected in expected_fields.items():
        if snapshot.get(key) != expected:
            failures.append(f"SNAPSHOT_SOURCE_BINDING_MISMATCH:{key}")
    numeric_registry = source.get("numeric_registry", [])
    if snapshot.get("numeric_registry") != numeric_registry:
        failures.append("SNAPSHOT_NUMERIC_REGISTRY_MISMATCH")
    source_registry = source.get("source_numeric_registry", [])
    source_registry_hash = _canonical_hash({"numeric_registry": source_registry})
    prevalidation = source.get("numeric_registry_prevalidation", {})
    if (source_registry_hash != source.get("source_numeric_registry_sha256")
            or source_registry_hash != prevalidation.get("source_numeric_registry_sha256")
            or prevalidation.get("status") != "PASS"
            or prevalidation.get("body_hash") != source.get("body_hash")):
        failures.append("UPSTREAM_NUMERIC_REGISTRY_PASS_EVIDENCE_INVALID")
    if (snapshot.get("source_numeric_registry_sha256") != source_registry_hash
            or snapshot.get("numeric_registry_prevalidation") != prevalidation):
        failures.append("SNAPSHOT_UPSTREAM_NUMERIC_REGISTRY_BINDING_MISMATCH")
    snapshot_facts = snapshot.get("facts")
    if not isinstance(snapshot_facts, list):
        failures.append("SNAPSHOT_FACTS_INVALID")
        snapshot_facts = []
    snapshot_fact_map = {item.get("fact_id"): item for item in snapshot_facts if isinstance(item, dict)}
    if set(snapshot_fact_map) != set(facts):
        failures.append("SNAPSHOT_FACT_ID_SET_MISMATCH")
    for fact_id, fact in facts.items():
        snap_fact = snapshot_fact_map.get(fact_id, {})
        for key in ("section_id", "text", "source_excerpt"):
            if snap_fact.get(key) != fact.get(key):
                failures.append(f"SNAPSHOT_FACT_MISMATCH:{fact_id}:{key}")
        if fact.get("source_excerpt") not in source.get("body_text", ""):
            failures.append(f"SNAPSHOT_FACT_NOT_SOURCE_BOUND:{fact_id}")
    hash_payload = {key: value for key, value in snapshot.items() if key != "snapshot_sha256"}
    if snapshot.get("snapshot_sha256") != _canonical_hash(hash_payload):
        failures.append("SNAPSHOT_SHA256_MISMATCH")
    return {"status": "PASS" if not failures else "FAIL", "errors": failures,
            "snapshot_id": snapshot.get("snapshot_id"), "snapshot_provenance": provenance,
            "snapshot_sha256": snapshot.get("snapshot_sha256"), "fact_count": len(snapshot_facts),
            "numeric_count": len(snapshot.get("numeric_registry", [])) if isinstance(snapshot.get("numeric_registry"), list) else 0}


def validate_0800_source(source: dict) -> dict[str, Any]:
    """Return source-completeness and numeric identity findings without repairs."""
    errors: list[str] = []
    warnings: list[str] = []
    if not isinstance(source, dict):
        return {"status": "NOT_READY", "errors": ["STRUCTURED_SOURCE_REQUIRED"], "missing_fact_ids": []}
    required_top = SCHEMA["required"]
    for key in required_top:
        if key not in source:
            errors.append(f"SOURCE_FIELD_MISSING:{key}")
    body = source.get("body_text")
    if not isinstance(body, str) or not body:
        errors.append("SOURCE_BODY_MISSING")
    elif hashlib.sha256(body.encode("utf-8")).hexdigest() != source.get("body_hash"):
        errors.append("BODY_HASH_MISMATCH")
    report_datetime = source.get("report_datetime", "")
    date_match = re.match(r"^(\d{4})-(\d{2})-(\d{2})T08:00(?::00)?(?:[+-]\d{2}:?\d{2}|Z)$", str(report_datetime))
    expected_report_id = f"{date_match.group(1)}-{date_match.group(2)}-{date_match.group(3)}_08-00" if date_match else None
    if not expected_report_id or source.get("report_id") != expected_report_id:
        errors.append("REPORT_ID_OR_08_00_DATETIME_MISMATCH")
    if date_match and isinstance(body, str) and body:
        source_title = next((line.strip() for line in body.splitlines() if line.strip()), "")
        title_match = re.match(r"^マーケットレポート｜(\d{4})/(\d{2})/(\d{2})（[^）]+）08:00$", source_title)
        expected_date = "-".join(date_match.groups())
        if (not title_match or "-".join(title_match.groups()) != expected_date
                or source.get("title") != source_title):
            errors.append("REPORT_TITLE_DATETIME_MISMATCH")
    is_synthetic = source.get("synthetic_fixture") is True
    if source.get("source_type") != "GOOGLE_DOCS" and not (
            is_synthetic and source.get("source_type") == "SYNTHETIC_FIXTURE"):
        errors.append("SOURCE_TYPE_MISMATCH")
    if not source.get("source_document_id"):
        errors.append("SOURCE_DOCUMENT_ID_MISSING")
    snapshot_identity = source.get("source_snapshot_identity", {})
    if not source.get("source_snapshot_id") or not isinstance(snapshot_identity, dict):
        errors.append("SOURCE_SNAPSHOT_ID_MISSING")
    else:
        snapshot_components = {"source_document_id": snapshot_identity.get("source_document_id", ""),
                              "revision": snapshot_identity.get("revision", ""),
                              "body_hash": snapshot_identity.get("body_hash", "")}
        snapshot_payload = json.dumps(snapshot_components, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        expected_snapshot_id = "docs-revision-sha256:" + hashlib.sha256(snapshot_payload.encode("utf-8")).hexdigest()
        if (snapshot_identity.get("method") != "SHA256_CANONICAL_SOURCE_ID_REVISION_BODY_HASH"
                or snapshot_components["source_document_id"] != source.get("source_document_id")
                or snapshot_components["revision"] != source.get("revision")
                or snapshot_components["body_hash"] != source.get("body_hash")
                or source.get("source_snapshot_id") != expected_snapshot_id):
            errors.append("SOURCE_SNAPSHOT_IDENTITY_MISMATCH")
    if not source.get("revision"):
        errors.append("SOURCE_REVISION_MISSING")
    if source.get("source_persisted_after_report_time") is True:
        warnings.append("SOURCE_UPDATED_AFTER_REPORT_TIME")
    if source.get("previous_close_table_rows") != 28:
        errors.append("PREVIOUS_CLOSE_TABLE_MUST_HAVE_28_ROWS")

    sections = source.get("sections")
    if not isinstance(sections, list) or [s.get("section_id") for s in sections if isinstance(s, dict)] != EXPECTED_IDS:
        errors.append("FIXED_SOURCE_SECTION_ORDER_MISMATCH")
        sections = sections if isinstance(sections, list) else []
    facts = _fact_map(source)
    if not facts:
        errors.append("FACT_ID_MISSING_DUPLICATE_OR_FACTS_EMPTY")
    missing_fact_ids: set[str] = set()
    referenced: dict[str, dict] = {}
    for section in sections:
        if not isinstance(section, dict):
            errors.append("SECTION_SHAPE_INVALID")
            continue
        section_id = section.get("section_id")
        fact_ids = section.get("fact_ids")
        if not isinstance(fact_ids, list) or not fact_ids:
            errors.append(f"SECTION_FACTS_MISSING:{section_id}")
            continue
        for fact_id in fact_ids:
            fact = facts.get(fact_id)
            if not fact:
                missing_fact_ids.add(str(fact_id))
                errors.append(f"FACT_ID_UNRESOLVED:{section_id}:{fact_id}")
                continue
            excerpt, text = fact.get("source_excerpt"), fact.get("text")
            if fact.get("section_id") != section_id or not isinstance(excerpt, str) or not excerpt or excerpt not in body or not isinstance(text, str) or text not in excerpt:
                errors.append(f"FACT_SOURCE_BINDING_INVALID:{fact_id}")
            referenced[fact_id] = fact

    by_section = {s.get("section_id"): [facts[fid] for fid in s.get("fact_ids", []) if fid in facts]
                  for s in sections if isinstance(s, dict)}
    timeline = by_section.get("ny_timeline", [])
    timeline_stages = [f.get("fields", {}).get("stage") for f in timeline]
    if timeline_stages != SECTION_BY_ID["ny_timeline"]["stages"]:
        errors.append("NY_TIMELINE_5_STAGE_SOURCE_FACTS_MISSING_OR_OUT_OF_ORDER")
    index_rows = [fact.get("fields", {}).get("row", []) for fact in by_section.get("ny_indices", [])]
    index_labels = {row[0] for row in index_rows if isinstance(row, list) and row}
    for label in CONFIG["required_ny_index_labels"]:
        if label not in index_labels:
            errors.append(f"NY_INDEX_SOURCE_ROW_MISSING:{label}")
    data_rows = [fact.get("fields", {}).get("row", []) for fact in by_section.get("major_market_data", [])]
    data_labels = {row[0] for row in data_rows if isinstance(row, list) and row}
    for label in CONFIG["required_market_data_labels"]:
        if label not in data_labels:
            errors.append(f"MAJOR_MARKET_DATA_SOURCE_ROW_MISSING:{label}")
    market_facts = by_section.get("six_market_outlook", [])
    market_fields = [f.get("fields", {}) for f in market_facts]
    if [f.get("market") for f in market_fields] != EXPECTED_MARKETS:
        errors.append("SIX_MARKET_ORDER_OR_COVERAGE_MISMATCH")
    for fact, fields in zip(market_facts, market_fields):
        for field in ("current_value", "judgement", "bullish_condition", "bearish_condition"):
            value = fields.get(field)
            if field == "current_value" and isinstance(value, str) and value.strip() and value not in fact.get("source_excerpt", ""):
                linked_fact = facts.get(fields.get("current_value_source_fact_id"), {})
                linked_ok = bool(linked_fact and linked_fact.get("section_id") == "major_market_data"
                                 or linked_fact and linked_fact.get("section_id") == "market_data_source_link")
                linked_excerpt = fields.get("current_value_source_excerpt", "")
                linked_ok = linked_ok and bool(linked_excerpt == linked_fact.get("source_excerpt")
                                                and linked_excerpt in body and value in linked_excerpt)
                numeric_id = fields.get("current_value_numeric_id")
                if numeric_id:
                    linked_ok = linked_ok and any(entry.get("numeric_id") == numeric_id
                                                  and entry.get("fact_id") == linked_fact.get("fact_id")
                                                  and str(entry.get("value", "")) in value
                                                  and entry.get("as_of") == fields.get("current_value_as_of")
                                                  for entry in source.get("numeric_registry", []) if isinstance(entry, dict))
                elif value != "取得不能":
                    linked_ok = False
                if not linked_ok:
                    errors.append(f"SIX_MARKET_REQUIRED_SOURCE_FIELD_MISSING:{fact.get('fact_id')}:{field}")
                else:
                    referenced[linked_fact["fact_id"]] = linked_fact
                continue
            if not isinstance(value, str) or not value.strip() or value not in fact.get("source_excerpt", ""):
                errors.append(f"SIX_MARKET_REQUIRED_SOURCE_FIELD_MISSING:{fact.get('fact_id')}:{field}")
    attention_count = _numbered_source_count(by_section.get("attention_points", []))
    if attention_count != 5:
        errors.append(f"ATTENTION_REQUIRED_FIVE_FACTS_MISSING:{attention_count}")
    if len(by_section.get("overall_judgement", [])) < 2:
        errors.append("OVERALL_JUDGEMENT_EVIDENCE_MISSING")
    if len(by_section.get("material_market_relation", [])) < 2:
        errors.append("MATERIAL_MARKET_RELATION_FACTS_MISSING")
    else:
        material_texts = [fact.get("text", "") for fact in by_section["material_market_relation"]]
        relation_terms = ("AI・半導体", "原油", "金利", "WTI", "日経")
        if not any(term in material_texts[-1] and any(term in text for text in material_texts[:-1])
                   for term in relation_terms):
            errors.append("MATERIAL_MARKET_RELATION_NO_SHARED_MARKET_TERM")
    flow_text = " ".join(fact.get("text", "") for fact in by_section.get("cross_asset_flow", []))
    flow_explicit = ("→" in flow_text or "⇒" in flow_text or "➜" in flow_text
                     or ("から" in flow_text and "へ移動" in flow_text)
                     or ("が" in flow_text and ("圧力" in flow_text or "懸念" in flow_text)))
    if not flow_explicit:
        errors.append("CROSS_ASSET_CAUSAL_LINK_MISSING")
    scenarios = [f.get("fields", {}).get("scenario") for f in by_section.get("scenario_analysis", [])]
    if scenarios != SECTION_BY_ID["scenario_analysis"]["scenarios"]:
        errors.append("SCENARIO_SOURCE_FACTS_INCOMPLETE_OR_OUT_OF_ORDER")
    if len(by_section.get("top_three_conditions", [])) != 3:
        errors.append("TOP_THREE_CONDITIONS_SOURCE_FACTS_INVALID")
    for fact in by_section.get("news_materials", []):
        fields = fact.get("fields", {})
        for key in ("headline", "time", "affected_market", "price_reaction"):
            value = fields.get(key)
            if not isinstance(value, str) or not value.strip() or value not in fact.get("source_excerpt", ""):
                errors.append(f"NEWS_REQUIRED_SOURCE_FIELD_MISSING:{fact.get('fact_id')}:{key}")

    numeric_registry = source.get("numeric_registry")
    numeric_checks = []
    if not isinstance(numeric_registry, list):
        errors.append("NUMERIC_REGISTRY_INVALID")
        numeric_registry = []
    elif not numeric_registry:
        errors.append("NUMERIC_REGISTRY_EMPTY")
    seen_numeric: set[str] = set()
    numeric_prevalidation = source.get("numeric_registry_prevalidation", {})
    upstream_numeric_pass = bool(
        numeric_prevalidation.get("status") == "PASS"
        and numeric_prevalidation.get("body_hash") == source.get("body_hash")
        and numeric_prevalidation.get("source_numeric_registry_sha256") == source.get("source_numeric_registry_sha256")
        and source.get("source_numeric_registry_sha256") == _canonical_hash({"numeric_registry": source.get("source_numeric_registry", [])})
    )
    for entry in numeric_registry:
        valid = isinstance(entry, dict)
        if not valid:
            errors.append("NUMERIC_REGISTRY_ENTRY_INVALID")
            continue
        numeric_id, fact_id = entry.get("numeric_id"), entry.get("fact_id")
        fact = facts.get(fact_id)
        excerpt = entry.get("source_excerpt")
        value = str(entry.get("value", ""))
        unit = str(entry.get("unit", ""))
        as_of_context = entry.get("as_of_source_excerpt", "")
        identity_ok = bool(numeric_id and numeric_id not in seen_numeric and fact and excerpt == fact.get("source_excerpt")
                  and excerpt in body and value and value in excerpt
                  and (upstream_numeric_pass or not unit.strip() or unit in excerpt)
                  and isinstance(as_of_context, str) and as_of_context in body
                  and (upstream_numeric_pass or str(entry.get("as_of", "")) in as_of_context))
        ok = identity_ok
        if numeric_id:
            seen_numeric.add(numeric_id)
        if not ok:
            errors.append(f"NUMERIC_IDENTITY_MISMATCH:{numeric_id or fact_id}")
        numeric_checks.append({"numeric_id": numeric_id, "source_numeric_id": entry.get("source_numeric_id"), "fact_id": fact_id, "value": value,
                               "unit": unit or None, "unit_status": "UNSPECIFIED" if not unit.strip() else "SOURCE_VERIFIED",
                               "as_of": entry.get("as_of"), "upstream_registry_status": "PASS" if upstream_numeric_pass else "NOT_PROVIDED",
                               "status": "PASS" if ok else "FAIL"})
    snapshot_check = _snapshot_integrity(source, facts)
    if snapshot_check["status"] != "PASS":
        errors.extend(snapshot_check["errors"])
    numeric_status = "FAIL" if any(item["status"] == "FAIL" for item in numeric_checks) else "PASS"
    source_error_prefixes = ("SOURCE_FIELD_MISSING", "SOURCE_BODY", "BODY_HASH", "REPORT_ID", "REPORT_TITLE",
                             "SOURCE_TYPE", "SOURCE_DOCUMENT", "SOURCE_SNAPSHOT", "SOURCE_REVISION",
                             "FIXED_SOURCE_SECTION_ORDER", "FACT_ID_MISSING", "FACT_SOURCE_BINDING", "FACT_ID_UNRESOLVED")
    source_integrity = "FAIL" if any(error.startswith(source_error_prefixes) for error in errors) else "PASS"
    completeness_prefixes = ("SECTION_FACTS_MISSING", "NY_TIMELINE_", "NY_INDEX_", "MAJOR_MARKET_DATA_",
                             "SIX_MARKET_", "SCENARIO_", "TOP_THREE_", "NEWS_REQUIRED_")
    completeness_prefixes += ("ATTENTION_REQUIRED_", "OVERALL_JUDGEMENT_EVIDENCE_", "MATERIAL_MARKET_RELATION_",
                              "CROSS_ASSET_CAUSAL_LINK_")
    completeness = "FAIL" if any(error.startswith(completeness_prefixes) for error in errors) else "PASS"
    gates = {
        "SOURCE_INTEGRITY": source_integrity,
        "NUMERIC_INTEGRITY": numeric_status,
        "SNAPSHOT_INTEGRITY": snapshot_check["status"],
        "CONTENT_COMPLETENESS": completeness,
        "LAYOUT_INTEGRITY": "NOT_RUN",
        "READABILITY_768": "NOT_RUN",
        "PRODUCTION_READY": "NOT_READY",
    }
    return {
        "status": "PASS" if not errors else "NOT_READY", "report_id": source.get("report_id"),
        "template_id": CONFIG["template_id"], "body_hash": source.get("body_hash"),
        "required_fact_ids": sorted(referenced), "missing_fact_ids": sorted(missing_fact_ids),
        "extra_fact_ids": sorted(set(facts) - set(referenced)), "numeric_checks": numeric_checks,
        "market_data_snapshot": snapshot_check, "validation_gates": gates,
        "warnings": warnings,
        "errors": errors,
    }


def _binding_source_status(fact: dict) -> str:
    if fact.get("preview_only"):
        return "MISSING_FROM_SOURCE"
    if fact.get("preview_missing_fields"):
        return "PARTIAL_SOURCE"
    if fact.get("preview_extracted"):
        return "EXTRACTED_FROM_SOURCE"
    return "SOURCE_BOUND"


def _binding_source_id(fact: dict) -> str | None:
    if fact.get("preview_only"):
        return None
    return fact.get("extracted_from_fact_id", fact.get("fact_id"))


def _draft_preview_source(source: dict) -> tuple[dict, list[str]]:
    """Add visible source-gap markers for fixed zones without changing source facts."""
    preview = copy.deepcopy(source)
    original_facts = {fact["fact_id"]: fact for fact in preview.get("structured_facts", [])
                      if isinstance(fact, dict) and fact.get("fact_id")}
    selected: dict[str, list[dict]] = {item["id"]: [] for item in CONFIG["sections"]}
    for section in preview.get("sections", []):
        sid = section.get("section_id")
        selected[sid] = [copy.deepcopy(original_facts[fid]) for fid in section.get("fact_ids", [])
                         if fid in original_facts]
    visible_missing: list[str] = []

    def marker(section_id: str, text: str, fields: dict | None = None) -> dict:
        marker_no = len(visible_missing) + 1
        visible_missing.append(f"{section_id}:{text}")
        return {"fact_id": f"preview-only:{section_id}:{marker_no:03d}", "section_id": section_id,
                "text": text, "source_excerpt": "", "importance": "NORMAL", "fields": fields or {},
                "preview_only": True, "preview_missing_fields": ["SOURCE_NOT_STATED"]}

    for item in CONFIG["sections"]:
        sid = item["id"]
        if sid == "title_datetime":
            continue
        if not selected.get(sid):
            selected[sid] = [marker(sid, "SOURCE GAP — 正式本文に明示なし")]

    while _numbered_source_count(selected.get("attention_points", [])) < 5:
        selected["attention_points"].append(marker("attention_points", "SOURCE GAP — 正式本文に明示なし"))

    stages = SECTION_BY_ID["ny_timeline"]["stages"]
    timeline_by_stage = {fact.get("fields", {}).get("stage"): fact for fact in selected["ny_timeline"]}
    for stage in stages:
        if stage not in timeline_by_stage:
            timeline_by_stage[stage] = marker("ny_timeline", "SOURCE GAP — 正式本文に明示なし", {"stage": stage})
    selected["ny_timeline"] = [timeline_by_stage[stage] for stage in stages]

    for sid, labels in (("ny_indices", CONFIG["required_ny_index_labels"]),
                        ("major_market_data", CONFIG["required_market_data_labels"])):
        existing = {fact.get("fields", {}).get("row", [None])[0] for fact in selected[sid]}
        for label in labels:
            if label not in existing:
                selected[sid].append(marker(sid, "SOURCE GAP — 正式本文に明示なし",
                                            {"row": [label, "SOURCE GAP", "", "", ""]}))
    for fact in selected["ny_indices"] + selected["major_market_data"]:
        row = fact.get("fields", {}).get("row")
        if isinstance(row, list):
            fact["fields"]["row"] = ["SOURCE GAP" if str(cell).startswith("取得不能（") else cell for cell in row]

    market_order = SECTION_BY_ID["six_market_outlook"]["markets"]
    outlook_by_market = {fact.get("fields", {}).get("market"): fact for fact in selected["six_market_outlook"]}
    for market in market_order:
        fact = outlook_by_market.get(market)
        if not fact:
            fact = marker("six_market_outlook", "SOURCE GAP — 正式本文に明示なし", {"market": market})
            outlook_by_market[market] = fact
        fields = fact.setdefault("fields", {})
        for key in ("current_value", "judgement", "bullish_condition", "bearish_condition"):
            if not str(fields.get(key, "")).strip():
                fields[key] = "SOURCE GAP"
                fact.setdefault("preview_missing_fields", []).append(key)
    selected["six_market_outlook"] = [outlook_by_market[market] for market in market_order]

    if len(selected.get("overall_judgement", [])) == 1:
        selected["overall_judgement"].append(marker("overall_judgement", "判断根拠の独立fact — 正式本文に明示なし"))
    if len(selected.get("material_market_relation", [])) < 2:
        selected["material_market_relation"].append(marker("material_market_relation", "SOURCE GAP — 影響市場または値動きの記載なし"))

    for fact in selected["news_materials"]:
        fields = fact.setdefault("fields", {})
        fields.setdefault("headline", fact.get("text", "SOURCE GAP"))
        for key in ("time", "affected_market", "price_reaction"):
            if not str(fields.get(key, "")).strip():
                fields[key] = "SOURCE GAP"
                fact.setdefault("preview_missing_fields", []).append(key)

    scenario_order = SECTION_BY_ID["scenario_analysis"]["scenarios"]
    scenario_aliases = {"代替シナリオ": "代替", "下振れ": "下振れ"}
    scenarios = {}
    for fact in selected["scenario_analysis"]:
        label = fact.get("fields", {}).get("scenario")
        if label in ("メイン", "代替", "上振れ", "崩れる条件"):
            scenarios[label] = fact
    selected["scenario_analysis"] = []
    for label in scenario_order:
        fact = scenarios.get(label)
        if fact is None and label == "代替":
            fact = scenarios.get("代替シナリオ")
        if fact is None:
            fact = marker("scenario_analysis", "SOURCE GAP — 正式本文に明示なし", {"scenario": label})
        selected["scenario_analysis"].append(fact)
    if len(selected["top_three_conditions"]) != 3:
        selected["top_three_conditions"] = [marker("top_three_conditions", "SOURCE GAP — 正式本文に明示なし")
                                             for _ in range(3)]

    section_records = []
    combined = dict(original_facts)
    for section in CONFIG["sections"]:
        sid = section["id"]
        if sid != "title_datetime" and not selected.get(sid):
            selected[sid] = [marker(sid, "SOURCE GAP — 正式本文に明示なし")]
        for fact in selected.get(sid, []):
            combined[fact["fact_id"]] = fact
        section_records.append({"section_id": sid, "fact_ids": [fact["fact_id"] for fact in selected.get(sid, [])]})
    preview["sections"] = section_records
    preview["structured_facts"] = list(combined.values())
    preview["_draft_preview"] = True
    preview["_preview_section_facts"] = selected
    return preview, visible_missing


def _fixed_row_index(section_id: str) -> int:
    for index, row in enumerate(FIXED_LAYOUT["rows"]):
        if section_id in row["section_ids"]:
            return index
    return -1


def _fixed_geometry_check(image_size: tuple[int, int], panels: list[dict]) -> dict[str, Any]:
    expected_size = tuple(CONFIG["visual_reference_contract"]["canvas_dimensions_px"])
    expected_ids = CONFIG["visual_reference_contract"]["panel_order"]
    got_ids = [panel["section_id"] for panel in panels]
    geometry_match = len(panels) == 16 and got_ids == expected_ids
    zone_by_id = {zone["section_id"]: zone for zone in FIXED_ZONES}
    for panel in panels:
        expected = zone_by_id.get(panel["section_id"])
        geometry_match = geometry_match and expected is not None and panel["bbox"] == [
            expected["x"], expected["y"], expected["x"] + expected["width"], expected["y"] + expected["height"]]
    rows_match = [row["section_ids"] for row in FIXED_LAYOUT["rows"]] == \
        CONFIG["visual_reference_contract"]["row_section_ids"]
    return {
        "single_sheet": "PASS" if image_size == expected_size else "FAIL",
        "one_png_required": CONFIG["fixed_layout"]["single_png_required"],
        "canvas_dimensions_match_reference": "PASS" if image_size == expected_size else "FAIL",
        "sixteen_zone_order": "PASS" if geometry_match else "FAIL",
        "four_row_grouping": "PASS" if rows_match else "FAIL",
        "top_five_panels": "PASS" if len(FIXED_LAYOUT["rows"][0]["section_ids"]) == 5 else "FAIL",
        "middle_upper_three_panels": "PASS" if len(FIXED_LAYOUT["rows"][1]["section_ids"]) == 3 else "FAIL",
        "middle_lower_four_panels": "PASS" if len(FIXED_LAYOUT["rows"][2]["section_ids"]) == 4 else "FAIL",
        "bottom_four_panels": "PASS" if len(FIXED_LAYOUT["rows"][3]["section_ids"]) == 4 else "FAIL",
        "geometry_status": "PASS" if image_size == expected_size and geometry_match and rows_match else "FAIL",
        "status": "NOT_RUN",
        "claim_scope": "Geometry is reported separately; visual fidelity also requires dedicated component, hierarchy, color, table, numbering, and flow checks.",
    }


def _timeline_display_text(text: str, stage: str) -> str:
    """Compact a source-bound timeline sentence without changing its stated event."""
    if text.startswith("SOURCE GAP"):
        return text
    value = text
    for prefix in ("序盤は", "中盤は", "終盤は", "東京時間は"):
        if value.startswith(prefix):
            value = value[len(prefix):]
            break
    substitutions = {
        "AI投資回収への懸念からNasdaq・SOXの下げが拡大。": "AI投資回収懸念でNasdaq・SOXの下げ拡大。",
        "30年債入札通過と長期金利低下でダウが持ち直した一方、Nasdaqは戻り切れませんでした。":
            "30年債入札通過・長期金利低下でダウ持ち直し。一方、Nasdaqは戻り切れず。",
        "SQ通過後の日経平均、半導体株、TOPIX、仲値後USD/JPY、WTI、米長期金利を確認。":
            "SQ後の日経平均・半導体株・TOPIX、仲値後USD/JPY、WTI、米長期金利を確認。",
    }
    return substitutions.get(value, value)


def _scenario_display_text(label: str, text: str) -> str:
    if text.startswith("SOURCE GAP"):
        return text
    value = text
    replacements = {
        "原油が再加速せず米長期金利が低下基調を維持すれば、SQ通過後は日経先物68,000円台後半で下げ渋る展開。":
            "原油再加速せず米長期金利低下なら、SQ後は日経先物68,000円台後半で下げ渋り。",
        "原油再急騰と米10年5.3%台回帰なら、AI・半導体売りが再加速し、日経先物68,000円割れを警戒。":
            "原油再急騰・米10年5.3%台回帰なら、AI・半導体売り再加速、日経先物68,000円割れ警戒。",
        "WTI一段高、米10年5.3%台再上昇、日経先物68,000円割れ、Nasdaq・SOX売り継続、BTC8万ドル割れ。":
            "WTI一段高／米10年5.3%台再上昇／日経先物68,000円割れ／Nasdaq・SOX売り継続／BTC8万ドル割れ。",
    }
    return replacements.get(value, value)


def _draw_fixed_zone(draw: ImageDraw.ImageDraw, zone: dict, section: dict, facts: list[dict],
                     bindings: list[dict], overflows: list[str]) -> None:
    x, y, width, height = zone["x"], zone["y"], zone["width"], zone["height"]
    x2, y2 = x + width, y + height
    section_id = zone["section_id"]
    heading_h = zone["heading_height"]
    body_size = zone["font_size"]
    body_font = _font(body_size)
    heading_font = _font(CONFIG["canvas"]["panel_heading_font_px"], True)
    draw.rectangle((x, y, x2, y2), fill=COLORS["white"], outline=COLORS["navy2"], width=2)
    draw.rectangle((x, y, x2, y + heading_h), fill=COLORS["navy"])
    heading = f"{zone['number']}. {section['title']}"
    heading_lines = _wrap(draw, heading, heading_font, width - 12)
    for candidate_size in range(heading_font.size - 1, 9, -1):
        candidate_font = _font(candidate_size, True)
        candidate_lines = _wrap(draw, heading, candidate_font, width - 12)
        if len(candidate_lines) * (candidate_font.size + 1) + 4 <= heading_h:
            heading_font, heading_lines = candidate_font, candidate_lines
            break
    if len(heading_lines) * (heading_font.size + 1) + 4 > heading_h:
        overflows.append(f"HEADING_OVERFLOW:{section_id}")
    for i, line in enumerate(heading_lines[:2]):
        draw.text((x + 6, y + 3 + i * (heading_font.size + 1)), line, font=heading_font, fill=COLORS["white"])
    left, top = x + zone["body_padding"], y + heading_h + zone.get("body_top_padding", 4)
    right, bottom = x2 - zone["body_padding"], y2 - zone.get("body_bottom_padding", 4)
    inner_width, inner_height = right - left, bottom - top
    line_gap = max(2, body_size // 7)
    line_height = body_size + line_gap
    count_before = len(bindings)

    def draw_lines(text: str, start_y: int, *, indent: int = 0, fill: str | None = None) -> int:
        lines = _wrap(draw, text, body_font, inner_width - indent - 2)
        available = max(0, bottom - start_y)
        fit_count = min(len(lines), available // line_height)
        for i, line in enumerate(lines[:fit_count]):
            draw.text((left + indent, start_y + i * line_height), line, font=body_font,
                      fill=fill or COLORS["text"])
        if fit_count < len(lines):
            overflows.append(f"TEXT_OVERFLOW:{section_id}:{len(lines)}>{fit_count}")
            draw.text((left + 2, max(top, bottom - min(16, inner_height))), "TEXT OVERFLOW",
                      font=_font(min(12, body_size), True), fill=COLORS["red"])
        return fit_count * line_height

    mode = zone["render_mode"]

    def bind(fact: dict, text: str, role: str) -> None:
        if not fact.get("preview_only"):
            bindings.append({"fact_id": _binding_source_id(fact), "source_status": _binding_source_status(fact),
                             "draw_call_text": text, "source_excerpt": fact.get("source_excerpt", ""), "role": role})

    def source_text(fact: dict) -> str:
        return str(fact.get("text", "SOURCE GAP — 正式本文に明示なし"))

    def draw_numbered(items: list[dict], *, limit: int | None = None, number_color: str | None = None,
                      gap: int = 2, max_lines: int | None = None) -> None:
        cursor = top
        number_color = number_color or COLORS["orange"]
        for index, fact in enumerate(items[:limit], 1):
            text = source_text(fact)
            lines = _wrap(draw, text, body_font, inner_width - 25)
            allowed = min(len(lines), max_lines) if max_lines is not None else len(lines)
            item_h = max(18, allowed * line_height)
            if cursor + item_h > bottom:
                overflows.append(f"TEXT_OVERFLOW:{section_id}:{index}")
                break
            draw.ellipse((left, cursor + 1, left + 19, cursor + 20), fill=number_color)
            num_font = _font(12, True)
            num_text = str(index)
            draw.text((left + 9 - draw.textlength(num_text, font=num_font) / 2, cursor + 2), num_text,
                      font=num_font, fill=COLORS["white"])
            for line_index, line in enumerate(lines[:allowed]):
                draw.text((left + 25, cursor + line_index * line_height), line, font=body_font, fill=COLORS["text"])
            cursor += item_h + gap
            bind(fact, text, "numbered_fact")

    def draw_bullets(items: list[dict], *, bullet: bool = True, accent: str | None = None) -> None:
        cursor = top
        for fact in items:
            text = source_text(fact)
            indent = 12 if bullet else 0
            lines = _wrap(draw, text, body_font, inner_width - indent)
            needed = len(lines) * line_height + 1
            if cursor + needed > bottom:
                overflows.append(f"TEXT_OVERFLOW:{section_id}:{len(lines)}")
                break
            if bullet:
                draw.ellipse((left + 1, cursor + max(4, body_size // 3), left + 7,
                              cursor + max(10, body_size // 3 + 6)), fill=accent or COLORS["navy2"])
            for line_index, line in enumerate(lines):
                draw.text((left + indent, cursor + line_index * line_height), line, font=body_font,
                          fill=accent if accent and not bullet else COLORS["text"])
            cursor += needed + 1
            bind(fact, text, "bullet_fact" if bullet else "text_fact")

    if mode == "ny_timeline":
        stages = SECTION_BY_ID["ny_timeline"]["stages"]
        facts_by_stage = {fact.get("fields", {}).get("stage"): fact for fact in facts}
        row_h = max(1, inner_height // len(stages))
        for index, stage in enumerate(stages):
            fact = facts_by_stage.get(stage)
            text = fact.get("text", "") if fact else "SOURCE GAP — 正式本文に明示なし"
            if fact and not fact.get("preview_only"):
                text = _timeline_display_text(text, stage)
            row_y = top + index * row_h
            stage_font = _font(12, True)
            display_stage = "東京へ" if stage.startswith("東京時間") else stage
            stage_w = min(inner_width, max(42, round(draw.textlength(display_stage, font=stage_font) + 8)))
            draw.rounded_rectangle((left, row_y, left + stage_w, row_y + 14), radius=4, fill=COLORS["navy2"])
            draw.text((left + 3, row_y + 1), display_stage, font=stage_font, fill=COLORS["white"])
            content_lines = _wrap(draw, text, body_font, inner_width - 2)
            max_fit = max(1, (row_h - 15) // line_height)
            for line_i, line in enumerate(content_lines[:max_fit]):
                draw.text((left + 2, row_y + 15 + line_i * line_height), line,
                          font=body_font, fill=COLORS["text"])
            if len(content_lines) > max_fit:
                overflows.append(f"TEXT_OVERFLOW:{section_id}:{stage}")
            if fact:
                bindings.append({"fact_id": _binding_source_id(fact), "source_status": _binding_source_status(fact),
                                 "draw_call_text": text, "source_excerpt": fact.get("source_excerpt", ""),
                                 "role": "timeline_stage"})
        return

    if mode in ("index_table", "categorized_table"):
        if section_id == "ny_indices":
            headers = ["指数", "終値", "前日比", "騰落率"]
            rows = [tuple((fact.get("fields", {}).get("row") or [""] * 5)[:4]) for fact in facts]
            _draw_fixed_table(draw, (left, top, right, bottom), headers, rows, body_font, bindings, facts, overflows, section_id)
        else:
            groups = CONFIG["market_data_groups"]
            gap = 4
            col_w = (inner_width - gap * (len(groups) - 1)) // len(groups)
            for group_index, group in enumerate(groups):
                gx = left + group_index * (col_w + gap)
                gy = top
                draw.rectangle((gx, gy, gx + col_w, gy + 19), fill=COLORS["blue"])
                draw.text((gx + 3, gy + 1), group["title"], font=_font(max(10, body_size), True), fill=COLORS["navy"])
                gy += 21
                group_facts = [fact for fact in facts if fact.get("fields", {}).get("row", [None])[0] in group["labels"]]
                for fact in group_facts:
                    row = fact.get("fields", {}).get("row", [])
                    label = str(row[0]) if row else ""
                    value = " / ".join(str(cell) for cell in row[1:])
                    label_w = min(92, round(col_w * 0.43))
                    label_lines = _wrap(draw, label, body_font, label_w - 3)
                    value_lines = _wrap(draw, value, body_font, col_w - label_w - 4)
                    row_lines = max(len(label_lines), len(value_lines), 1)
                    row_h = row_lines * line_height + 3
                    if gy + row_h > bottom:
                        overflows.append(f"TABLE_OVERFLOW:{section_id}:{label}")
                        draw.text((gx + 2, max(top, bottom - 12)), "TEXT OVERFLOW", font=_font(10, True), fill=COLORS["red"])
                        break
                    draw.rectangle((gx, gy, gx + col_w, gy + row_h),
                                   fill=COLORS["white"] if group_facts.index(fact) % 2 == 0 else "#EDF5FC")
                    for i, line in enumerate(label_lines):
                        draw.text((gx + 2, gy + 1 + i * line_height), line, font=body_font, fill=COLORS["text"])
                    for i, line in enumerate(value_lines):
                        draw.text((gx + label_w, gy + 1 + i * line_height), line, font=body_font, fill=COLORS["text"])
                    bindings.append({"fact_id": _binding_source_id(fact), "source_status": _binding_source_status(fact),
                                     "draw_call_text": " | ".join(str(cell) for cell in row),
                                     "source_excerpt": fact.get("source_excerpt", ""), "role": "market_data_row"})
                    gy += row_h
        return

    if mode == "six_market_table":
        headers = ["市場", "現在値", "判断", "強気条件", "弱気条件"]
        rows = []
        for fact in facts:
            fields = fact.get("fields", {})
            date = fields.get("current_value_as_of", "")
            value = str(fields.get("current_value", "SOURCE GAP"))
            if date and value not in ("SOURCE GAP", "取得不能"):
                value += f" ({str(date)[5:].replace('-', '/')})"
            rows.append((fields.get("market", ""), value, fields.get("judgement", "SOURCE GAP"),
                         fields.get("bullish_condition", "SOURCE GAP"), fields.get("bearish_condition", "SOURCE GAP")))
        _draw_fixed_table(draw, (left, top, right, bottom), headers, rows, body_font, bindings, facts, overflows, section_id)
        return

    if mode == "numbered_news":
        cursor = top
        for index, fact in enumerate(facts, 1):
            fields = fact.get("fields", {})
            headline = str(fields.get("headline") or fact.get("text", "SOURCE GAP"))
            def news_value(key: str) -> str:
                value = str(fields.get(key, ""))
                return "なし" if not value or value == "SOURCE GAP" else value
            detail = f"時刻:{news_value('time')} 市場:{news_value('affected_market')} 反応:{news_value('price_reaction')}"
            headline_lines = _wrap(draw, f"{index}. {headline}", body_font, inner_width - 3)
            detail_lines = _wrap(draw, detail, _font(max(10, body_size - 1)), inner_width - 3)
            needed = (len(headline_lines) + len(detail_lines)) * line_height + 1
            if cursor + needed > bottom:
                overflows.append(f"NEWS_OVERFLOW:{section_id}:{index}")
                break
            for i, line in enumerate(headline_lines):
                draw.text((left + 2, cursor + i * line_height), line, font=body_font,
                          fill=COLORS["orange"] if i == 0 else COLORS["text"])
            cursor += len(headline_lines) * line_height
            for i, line in enumerate(detail_lines):
                draw.text((left + 2, cursor + i * line_height), line, font=_font(max(10, body_size - 1), True),
                          fill=COLORS["muted"])
            cursor += len(detail_lines) * line_height + 1
            bind(fact, f"{index}. {headline} | {fields.get('time')} | {fields.get('affected_market')} | {fields.get('price_reaction')}", "news_item")
        return

    if mode == "scenario_color_rows":
        scenario_map = {fact.get("fields", {}).get("scenario"): fact for fact in facts}
        rows = [("上振れ", scenario_map.get("上振れ")), ("メイン", scenario_map.get("メイン")),
                ("代替", scenario_map.get("代替")), ("崩れる条件", scenario_map.get("崩れる条件"))]
        cursor = top
        row_colors = {"上振れ": COLORS["greenbg"], "メイン": COLORS["blue"],
                      "代替": COLORS["yellow"], "崩れる条件": COLORS["redbg"]}
        label_colors = {"上振れ": COLORS["green"], "メイン": COLORS["navy2"],
                        "代替": COLORS["orange"], "崩れる条件": COLORS["red"]}
        for label, fact in rows:
            text = _scenario_display_text(label, fact.get("text", "SOURCE GAP — 正式本文に明示なし") if fact else "SOURCE GAP — 正式本文に明示なし")
            label_w = min(84, max(62, round(inner_width * 0.18)))
            lines = _wrap(draw, text, body_font, inner_width - label_w - 6)
            compact_line_height = body_size
            height_needed = max(18, len(lines) * compact_line_height)
            if cursor + height_needed > bottom:
                overflows.append(f"SCENARIO_OVERFLOW:{label}")
                break
            draw.rounded_rectangle((left, cursor, right, cursor + height_needed - 1), radius=3,
                                   fill=row_colors[label])
            label_font = _font(11, True)
            draw.text((left + 3, cursor + 2), label, font=label_font, fill=label_colors[label])
            for i, line in enumerate(lines):
                draw.text((left + label_w, cursor + i * compact_line_height), line, font=body_font, fill=COLORS["text"])
            cursor += height_needed
            if fact:
                bind(fact, text, "scenario")
        return

    if mode in ("numbered_list_5", "numbered_list"):
        numbered_facts = facts
        if mode == "numbered_list_5" and facts:
            chunks = [part.strip(" 。、") for part in re.split(r"[①②③④⑤]\s*", source_text(facts[0])) if part.strip(" 。、")]
            if len(chunks) >= 2:
                numbered_facts = [{**facts[0], "text": item} for item in chunks[:5]] + facts[1:]
        draw_numbered(numbered_facts, limit=5 if mode == "numbered_list_5" else None,
                      gap=4 if mode == "numbered_list_5" else 2)
        return

    if mode == "judgement_card":
        fact = facts[0] if facts else {}
        text = source_text(fact)
        # Emphasis is visual only; the label is an exact source phrase, never inferred.
        label = text.splitlines()[0]
        label_font = _font(min(25, max(18, body_size + 7)), True)
        label_lines = _wrap(draw, label, label_font, inner_width - 16)
        label_height = len(label_lines) * (label_font.size + 2) + 8
        draw.rounded_rectangle((left, top, right, top + label_height), radius=7, fill=COLORS["redbg"],
                               outline=COLORS["line"], width=1)
        for i, line in enumerate(label_lines):
            draw.text((left + 8, top + 4 + i * (label_font.size + 2)), line, font=label_font, fill=COLORS["red"])
        cursor = top + label_height + 7
        evidence_items = ["\n".join(text.splitlines()[1:]).strip()] if len(text.splitlines()) > 1 else []
        evidence_items.extend(source_text(item) for item in facts[1:])
        for evidence in evidence_items:
            if not evidence:
                continue
            lines = _wrap(draw, evidence, body_font, inner_width - 12)
            if cursor + len(lines) * line_height > bottom:
                overflows.append(f"TEXT_OVERFLOW:{section_id}:evidence")
                break
            for i, wrapped in enumerate(lines):
                draw.ellipse((left + 2, cursor + i * line_height + 5, left + 8,
                              cursor + i * line_height + 11), fill=COLORS["navy2"])
                draw.text((left + 14, cursor + i * line_height), wrapped, font=body_font, fill=COLORS["text"])
            cursor += len(lines) * line_height
        bind(fact, text, "judgement_label_and_evidence")
        for evidence_fact in facts[1:]:
            bind(evidence_fact, source_text(evidence_fact), "judgement_evidence")
        return

    if mode == "theme_emphasis":
        fact = facts[0] if facts else {}
        text = source_text(fact)
        phrases = re.findall(r"「([^」]+)」", text)
        theme_lines = phrases if len(phrases) >= 2 else [text]
        theme_font = _font(body_size + 3, True)
        lines = []
        for phrase in theme_lines:
            lines.extend(_wrap(draw, phrase, theme_font, inner_width - 22))
        if len(lines) > 5:
            overflows.append(f"TEXT_OVERFLOW:{section_id}:theme")
        center_y = top + max(2, (inner_height - min(len(lines), 5) * (body_size + 4)) // 3)
        draw.rounded_rectangle((left, center_y - 5, right, center_y + min(len(lines), 5) * (body_size + 4) + 11),
                               radius=8, fill=COLORS["yellow"], outline=COLORS["orange"], width=2)
        for i, line in enumerate(lines[:5]):
            draw.text((left + 11, center_y + i * (body_size + 4)), line, font=theme_font,
                      fill=COLORS["navy"])
        bind(fact, text, "centered_theme")
        cursor = center_y + min(len(lines), 5) * (body_size + 4) + 16
        for fact in facts[1:]:
            subtext = source_text(fact)
            sublines = _wrap(draw, subtext, body_font, inner_width - 15)
            if cursor + len(sublines) * line_height > bottom:
                overflows.append(f"TEXT_OVERFLOW:{section_id}:supplement")
                break
            draw.ellipse((left + 2, cursor + 5, left + 8, cursor + 11), fill=COLORS["navy2"])
            for i, line in enumerate(sublines):
                draw.text((left + 14, cursor + i * line_height), line, font=body_font, fill=COLORS["text"])
            cursor += len(sublines) * line_height + 2
            bind(fact, subtext, "theme_support")
        return

    if mode == "cause_effect":
        if len(facts) < 2:
            overflows.append(f"SOURCE_GAP:{section_id}:material_or_market_side_missing")
            return
        causes, outcome = facts[:-1], facts[-1]
        cause_x, cause_w = left, min(118, round(inner_width * 0.43))
        result_x, result_w = cause_x + cause_w + 20, right - (cause_x + cause_w + 20)
        row_h = inner_height // max(1, len(causes))
        result_text = source_text(outcome)
        match_token = next((token for token in ("AI・半導体", "原油", "金利", "WTI", "日経")
                            if token in result_text and any(token in source_text(item) for item in causes)), None)
        matching_index = next((index for index, fact in enumerate(causes) if match_token and match_token in source_text(fact)), None)
        for index, fact in enumerate(causes):
            text = source_text(fact)
            row_y = top + index * row_h
            lines = _wrap(draw, text, body_font, cause_w - 8)
            box_h = min(row_h - 3, max(24, len(lines) * line_height + 4))
            if row_y + box_h > bottom or len(lines) * line_height + 4 > row_h:
                overflows.append(f"TEXT_OVERFLOW:{section_id}:material{index + 1}")
            draw.rounded_rectangle((cause_x, row_y + 1, cause_x + cause_w, row_y + box_h), radius=4, fill=COLORS["redbg"])
            for line_i, line in enumerate(lines[:max(1, (row_h - 4) // line_height)]):
                draw.text((cause_x + 4, row_y + 3 + line_i * line_height), line, font=body_font, fill=COLORS["red"])
            bind(fact, text, "material_source")
        result_lines = _wrap(draw, result_text, body_font, result_w - 10)
        result_h = min(inner_height, max(34, len(result_lines) * line_height + 12))
        result_y = top + max(0, (inner_height - result_h) // 2)
        draw.rounded_rectangle((result_x, result_y, right, result_y + result_h), radius=5, fill=COLORS["greenbg"])
        for line_i, line in enumerate(result_lines[:max(1, (result_h - 8) // line_height)]):
            draw.text((result_x + 5, result_y + 4 + line_i * line_height), line, font=body_font, fill=COLORS["green"])
        bind(outcome, result_text, "market_effect")
        if matching_index is not None:
            source_center_y = top + matching_index * row_h + row_h // 2
            target_center_y = result_y + result_h // 2
            arrow_start, arrow_end = cause_x + cause_w + 2, result_x - 4
            draw.line((arrow_start, source_center_y, arrow_end, target_center_y), fill=COLORS["red"], width=3)
            draw.polygon([(arrow_end - 2, target_center_y - 5), (arrow_end - 2, target_center_y + 5),
                          (arrow_end + 4, target_center_y)], fill=COLORS["red"])
            bindings.append({"fact_id": _binding_source_id(causes[matching_index]),
                             "source_status": _binding_source_status(causes[matching_index]),
                             "draw_call_text": source_text(causes[matching_index]) + " → " + result_text,
                             "source_excerpt": causes[matching_index].get("source_excerpt", "") + " | " + outcome.get("source_excerpt", ""),
                             "role": "cause_effect_relation"})
        else:
            overflows.append(f"SOURCE_RELATION_UNVERIFIED:{section_id}")
        return

    if mode == "causal_flow":
        cursor = top
        for fact in facts:
            text = source_text(fact)
            if "AI・半導体から一部資金流出" in text and "エネルギー・ディフェンシブへ移動" in text:
                flow_rows = [(["AI・半導体から一部資金流出", "エネルギー・ディフェンシブへ移動"], True),
                             (["原油上昇", "債券売り圧力"], True),
                             (["BTCも弱く、全面リスクオフではなく選別色が強い相場です。"], False)]
            else:
                source_parts = [part.strip() for part in re.split(r"\s*(?:→|⇒|➜)\s*", text) if part.strip()]
                flow_rows = [(source_parts if len(source_parts) > 1 else [text], len(source_parts) > 1)]
            for parts, has_arrow in flow_rows:
                max_lines = max((len(_wrap(draw, part, body_font, inner_width)) for part in parts), default=1)
                row_h = max(22, max_lines * line_height + 4)
                if cursor + row_h > bottom:
                    overflows.append(f"TEXT_OVERFLOW:{section_id}:flow")
                    break
                if len(parts) == 1:
                    lines = _wrap(draw, parts[0], body_font, inner_width - 12)
                    draw.ellipse((left + 1, cursor + 5, left + 7, cursor + 11), fill=COLORS["navy2"])
                    for i, line in enumerate(lines):
                        draw.text((left + 12, cursor + i * line_height), line, font=body_font, fill=COLORS["text"])
                else:
                    arrow_space = 14 if has_arrow else 0
                    box_w = max(1, (inner_width - arrow_space) // len(parts))
                    cursor_x = left
                    part_font = _font(max(10, body_size - 1), True)
                    for part_index, part in enumerate(parts):
                        text_lines = _wrap(draw, part, part_font, box_w - 8)
                        if len(text_lines) > 2:
                            overflows.append(f"TEXT_OVERFLOW:{section_id}:flow_node{part_index + 1}")
                        box_h = max(20, len(text_lines) * 12 + 4)
                        draw.rounded_rectangle((cursor_x, cursor + 2, cursor_x + box_w - 2, cursor + box_h), radius=4,
                                               fill=COLORS["redbg"] if part_index == 0 else COLORS["greenbg"])
                        for i, line in enumerate(text_lines[:2]):
                            draw.text((cursor_x + 4, cursor + 3 + i * 12), line, font=part_font, fill=COLORS["text"])
                        cursor_x += box_w
                        if has_arrow and part_index == 0:
                            arrow_x, arrow_y = cursor_x - 1, cursor + row_h // 2
                            draw.line((arrow_x, arrow_y, arrow_x + 7, arrow_y), fill=COLORS["red"], width=2)
                            draw.polygon([(arrow_x + 7, arrow_y - 3), (arrow_x + 7, arrow_y + 3),
                                          (arrow_x + 11, arrow_y)], fill=COLORS["red"])
                            cursor_x += arrow_space
                cursor += row_h + 3
            if any(has_arrow for _, has_arrow in flow_rows):
                bindings.append({"fact_id": _binding_source_id(fact), "source_status": _binding_source_status(fact),
                                 "draw_call_text": text, "source_excerpt": fact.get("source_excerpt", ""),
                                 "role": "causal_flow_arrow"})
            bind(fact, text, "causal_flow")
        return

    if mode == "position_groups":
        cursor = top
        for index, fact in enumerate(facts):
            text = source_text(fact)
            clauses = [part.strip() + ("。" if separator else "")
                       for part, separator in re.findall(r"([^。]+)(。?)", text) if part.strip()]
            if not clauses:
                clauses = [text]
            for clause in clauses:
                if "株価指数オプション" in clause or "SQ" in clause:
                    label = "SQ・オプション" if "USD/JPY" not in clause else "為替需給"
                elif "USD/JPY" in clause or "ドル買い" in clause:
                    label = "為替需給"
                elif "AI・半導体" in clause:
                    label = "株式需給"
                else:
                    label = "需給要因"
                lines = _wrap(draw, clause, body_font, inner_width - min(88, round(inner_width * 0.29)) - 6)
                label_w = min(88, round(inner_width * 0.29))
                height_needed = max(22, len(lines) * line_height + 2)
                if cursor + height_needed > bottom:
                    overflows.append(f"TEXT_OVERFLOW:{section_id}:position{index + 1}")
                    break
                fill = COLORS["blue"] if index % 2 == 0 else "#EDF5FC"
                draw.rounded_rectangle((left, cursor, right, cursor + height_needed), radius=3, fill=fill)
                draw.text((left + 3, cursor + 2), label, font=_font(11, True), fill=COLORS["navy2"])
                for i, line in enumerate(lines):
                    draw.text((left + label_w, cursor + i * line_height), line, font=body_font, fill=COLORS["text"])
                cursor += height_needed + 2
                bind(fact, clause, "position_group")
        return

    if mode == "watch_list":
        draw_bullets(facts, accent=COLORS["navy2"])
        return

    if mode == "top_three":
        draw_numbered(facts, limit=3, gap=2, number_color=COLORS["orange"], max_lines=1)
        return

    if mode == "summary_card":
        fact = facts[0] if facts else {}
        text = source_text(fact)
        label_font = _font(max(16, body_size + 5), True)
        label_lines = _wrap(draw, text.splitlines()[0], label_font, inner_width - 12)
        box_h = min(inner_height - 2, max(25, len(label_lines) * (label_font.size + 2) + 8))
        draw.rounded_rectangle((left, top, right, top + box_h), radius=5, fill=COLORS["redbg"])
        for i, line in enumerate(label_lines[:3]):
            draw.text((left + 5, top + 3 + i * (label_font.size + 2)), line, font=label_font, fill=COLORS["red"])
        if len(label_lines) > 3:
            overflows.append(f"TEXT_OVERFLOW:{section_id}:summary_label")
        remainder = "\n".join(text.splitlines()[1:]).strip()
        lines = _wrap(draw, remainder, body_font, inner_width - 4) if remainder else []
        cursor = top + box_h + 4
        for i, line in enumerate(lines):
            if cursor + line_height > bottom:
                overflows.append(f"TEXT_OVERFLOW:{section_id}:summary")
                break
            draw.text((left + 2, cursor), line, font=body_font, fill=COLORS["text"])
            cursor += line_height
        bind(fact, text, "summary_card")
        for extra in facts[1:]:
            draw_bullets([extra])
        return

    if mode == "theme_emphasis":
        return
    raise ValueError(f"UNSUPPORTED_0800_RENDER_MODE:{mode}")


def _draw_fixed_table(draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int], headers: list[str],
                      rows: list[tuple[str, ...]], body_font: ImageFont.FreeTypeFont,
                      bindings: list[dict], facts: list[dict], overflows: list[str], section_id: str) -> None:
    x1, y1, x2, y2 = box
    width = x2 - x1
    font_size = body_font.size
    if len(headers) == 5:
        weights = [1.0, 1.05, 1.0, 1.15, 1.15]
    elif len(headers) == 4:
        weights = [1.05, 1.2, 1.0, 1.0]
    else:
        weights = [1.0] * len(headers)
    col_widths = [int(width * weight / sum(weights)) for weight in weights]
    col_widths[-1] = width - sum(col_widths[:-1])
    header_h = max(17, font_size + 5)
    draw.rectangle((x1, y1, x2, y1 + header_h), fill=COLORS["blue"])
    cursor = y1 + header_h
    header_font = _font(max(10, font_size), True)
    current_x = x1
    for header, col_width in zip(headers, col_widths):
        lines = _wrap(draw, header, header_font, col_width - 3)
        if len(lines) > 1:
            overflows.append(f"TABLE_HEADER_WRAP:{section_id}:{header}")
        draw.text((current_x + 2, y1 + 1), lines[0], font=header_font, fill=COLORS["navy"])
        current_x += col_width
    row_step = font_size + max(2, font_size // 6)
    for row_index, row in enumerate(rows):
        wrapped = [_wrap(draw, str(cell), body_font, max(1, col_width - 4)) for cell, col_width in zip(row, col_widths)]
        row_lines = max((len(lines) for lines in wrapped), default=1)
        row_h = row_lines * row_step + 2
        if cursor + row_h > y2:
            overflows.append(f"TABLE_OVERFLOW:{section_id}:row{row_index + 1}")
            break
        draw.rectangle((x1, cursor, x2, cursor + row_h), fill=COLORS["white"] if row_index % 2 == 0 else "#EDF5FC")
        current_x = x1
        for col_index, (cell_lines, col_width) in enumerate(zip(wrapped, col_widths)):
            color = COLORS["text"]
            if col_index == 2 and len(row) > 2:
                cell = str(row[col_index])
                if any(token in cell for token in ("上昇", "強気", "支援")):
                    color = COLORS["green"]
                elif any(token in cell for token in ("下落", "弱気", "警戒")):
                    color = COLORS["red"]
            for line_index, line in enumerate(cell_lines):
                draw.text((current_x + 2, cursor + line_index * row_step), line, font=body_font, fill=color)
            current_x += col_width
        fact = facts[row_index] if row_index < len(facts) else None
        if fact and not fact.get("preview_only"):
            text = " | ".join(str(cell) for cell in row)
            bindings.append({"fact_id": _binding_source_id(fact), "source_status": _binding_source_status(fact),
                             "missing_fields": fact.get("preview_missing_fields", []), "draw_call_text": text,
                             "source_excerpt": fact.get("source_excerpt", ""), "role": "table_row"})
            fields = fact.get("fields", {})
            linked_id = fields.get("current_value_source_fact_id")
            if linked_id:
                value = str(fields.get("current_value", ""))
                if fields.get("current_value_as_of") and value not in ("SOURCE GAP", "取得不能"):
                    value += f" ({str(fields['current_value_as_of'])[5:].replace('-', '/')})"
                bindings.append({"fact_id": linked_id, "source_status": "SOURCE_BOUND", "draw_call_text": value,
                                 "source_excerpt": fields.get("current_value_source_excerpt", ""),
                                 "role": "six_market_current_value_source"})
        cursor += row_h


def render_0800_fixed(source: dict, output_path: str | Path | None = None, *, draft_preview: bool = False) -> dict[str, Any]:
    """Render the approved 16-zone 08:00 composition as exactly one PNG."""
    provenance = ((source.get("market_data_snapshot") or {}).get("snapshot_provenance"))
    # Every new LIVE_CAPTURED 08:00 image must carry a freshly recomputable
    # pre-render QA result. Historical SOURCE_RECONSTRUCTED DRAFTs remain available.
    if provenance == "LIVE_CAPTURED":
        from .infographic_0800_generation_contract import (
            build_0800_generation_attestation, validate_0800_generation_contract,
        )
        qa = validate_0800_generation_contract(source)
        expected_attestation = build_0800_generation_attestation(source, qa)
        supplied_attestation = source.get("generation_qa_attestation")
        if qa.get("status") != "PASS" or supplied_attestation != expected_attestation:
            return {"status": "BLOCKED", "infographic_status": "NOT_READY",
                    "validation": qa, "generation_qa_status": qa.get("status"),
                    "errors": ["PRE_RENDER_0800_QA_REQUIRED_OR_IDENTITY_MISMATCH"],
                    "image_bytes": None, "output_path": None, "production_eligible": False}
    validation = validate_0800_source(source)
    visible_missing: list[str] = []
    if validation["status"] != "PASS" and not draft_preview:
        return {"status": "NOT_READY", "infographic_status": "NOT_READY", "validation": validation,
                "image_bytes": None, "output_path": None}
    source, visible_missing = _draft_preview_source(source)
    facts = _fact_map(source)
    section_facts = {section["section_id"]: [facts[fid] for fid in section["fact_ids"] if fid in facts]
                     for section in source["sections"]}
    canvas = CONFIG["canvas"]
    image = Image.new("RGB", (canvas["width"], canvas["height"]), canvas["background"])
    draw = ImageDraw.Draw(image)
    draw.rectangle((0, 0, canvas["width"], canvas["header_height"]), fill=COLORS["navy"])
    title_fact = section_facts["title_datetime"][0]
    title = source.get("title", title_fact["text"])
    title_font = _font(44, True)
    while draw.textlength(title, font=title_font) > canvas["width"] - 420 and title_font.size > 28:
        title_font = _font(title_font.size - 2, True)
    draw.text((14, 5), title, font=title_font, fill=COLORS["white"])
    provenance_label = {
        "LIVE_CAPTURED": "LIVE_CAPTURED",
        "SOURCE_RECONSTRUCTED": "SOURCE_RECONSTRUCTED",
        "SYNTHETIC_FIXTURE": "SYNTHETIC_FIXTURE",
    }.get(source["market_data_snapshot"]["snapshot_provenance"])
    if provenance_label is None:
        return {"status": "BLOCKED", "infographic_status": "NOT_READY", "validation": validation,
                "errors": ["SNAPSHOT_PROVENANCE_INVALID"], "image_bytes": None, "output_path": None,
                "production_eligible": False}
    draw.text((canvas["width"] - 270, 12), provenance_label, font=_font(16, True), fill=COLORS["white"])
    theme_fact = section_facts.get("market_theme", [{}])[0]
    subtitle = theme_fact.get("text", "")
    subtitle_lines = _wrap(draw, subtitle, _font(21, True), canvas["width"] - 30)
    for index, line in enumerate(subtitle_lines[:2]):
        draw.text((14, 53 + index * 22), line, font=_font(21, True), fill=COLORS["white"])
    draw.text((canvas["width"] - 270, 79), "SOURCE GAP = 正式本文に明示なし", font=_font(11), fill=COLORS["white"])
    bindings: list[dict] = [{"fact_id": _binding_source_id(title_fact), "source_status": "SOURCE_BOUND",
                             "draw_call_text": title, "source_excerpt": title_fact.get("source_excerpt", ""), "role": "title"}]
    panels = []
    overflows: list[str] = []
    for zone in FIXED_ZONES:
        section_id = zone["section_id"]
        section = SECTION_BY_ID[section_id]
        box = [zone["x"], zone["y"], zone["x"] + zone["width"], zone["y"] + zone["height"]]
        panels.append({"section_id": section_id, "number": zone["number"], "bbox": box,
                       "row": _fixed_row_index(section_id), "font_size": zone["font_size"],
                       "minimum_font_size": zone["minimum_font_size"], "max_line_count": zone["maximum_line_count"]})
        _draw_fixed_zone(draw, zone, section, section_facts.get(section_id, []), bindings, overflows)
    overflow_zones = set()
    for error in overflows:
        if error.startswith("SCENARIO_OVERFLOW:"):
            overflow_zones.add("scenario_analysis")
        else:
            overflow_zones.update(section_id for section_id in EXPECTED_PANEL_IDS if section_id in error)
    for zone in FIXED_ZONES:
        if zone["section_id"] not in overflow_zones:
            continue
        x, y, width, height = zone["x"], zone["y"], zone["width"], zone["height"]
        badge_top = y + height - 20
        draw.rectangle((x + 1, badge_top, x + width - 1, y + height - 1), fill=COLORS["redbg"])
        draw.text((x + 5, badge_top + 2), "OVERFLOW — DRAFT INVALID", font=_font(12, True), fill=COLORS["red"])
    for section_id, items in section_facts.items():
        if section_id == "title_datetime":
            continue
        for fact in items:
            if fact.get("preview_only") and not any(fact.get("text") == label for label in visible_missing):
                # The preview list stores human-readable reasons, not marker identities.
                visible_missing.append(f"{section_id}:{fact.get('text', 'SOURCE GAP')}")
    image_bytes_io = __import__("io").BytesIO()
    image.save(image_bytes_io, format="PNG", optimize=False, compress_level=9)
    image_bytes = image_bytes_io.getvalue()
    image_hash = hashlib.sha256(image_bytes).hexdigest()
    required_ids = sorted(validation.get("required_fact_ids", []))
    rendered_ids = sorted({binding["fact_id"] for binding in bindings if binding.get("fact_id")})
    missing = sorted(set(required_ids) - set(rendered_ids))
    extra = sorted(set(rendered_ids) - set(required_ids))
    binding_by_id = {binding["fact_id"]: binding for binding in bindings if binding.get("fact_id")}
    numeric_checks = []
    for entry in source.get("numeric_registry", []):
        binding = binding_by_id.get(entry.get("fact_id"), {})
        rendered = str(binding.get("draw_call_text", ""))
        ok = bool(binding and str(entry.get("value", "")) in rendered
                  and entry.get("source_excerpt") in source.get("body_text", ""))
        numeric_checks.append({"numeric_id": entry.get("numeric_id"), "fact_id": entry.get("fact_id"),
                               "value": entry.get("value"), "unit": entry.get("unit"), "as_of": entry.get("as_of"),
                               "draw_call_text": rendered, "status": "PASS" if ok else "FAIL"})
    scaled = image.resize((DISPLAY_WIDTH, round(canvas["height"] * SCALE)), Image.Resampling.LANCZOS)
    pairwise_nonoverlap = all(
        a["bbox"][2] <= b["bbox"][0] or b["bbox"][2] <= a["bbox"][0]
        or a["bbox"][3] <= b["bbox"][1] or b["bbox"][3] <= a["bbox"][1]
        for idx, a in enumerate(panels) for b in panels[idx + 1:])
    reference = _fixed_geometry_check(image.size, panels)
    readability = all(zone["font_size"] >= zone["minimum_font_size"]
                      and zone["font_size"] * SCALE >= canvas["minimum_body_font_at_768_px"] for zone in FIXED_ZONES)
    validation_gates = dict(validation.get("validation_gates", {}))
    expected_modes = {
        "overall_judgement": "judgement_card", "attention_points": "numbered_list_5",
        "market_theme": "theme_emphasis", "material_market_relation": "cause_effect",
        "ny_timeline": "ny_timeline", "ny_indices": "index_table", "major_market_data": "categorized_table",
        "ny_market_points": "watch_list", "cross_asset_flow": "causal_flow", "positioning": "position_groups",
        "six_market_outlook": "six_market_table", "news_materials": "numbered_news",
        "scenario_analysis": "scenario_color_rows", "handover": "watch_list",
        "top_three_conditions": "top_three", "final_summary": "summary_card",
    }
    visual_components = {}
    for section_id, mode in expected_modes.items():
        zone = next(item for item in FIXED_ZONES if item["section_id"] == section_id)
        section_content = section_facts.get(section_id, [])
        role_names = {item.get("role") for item in bindings
                      if item.get("fact_id") in {fact.get("fact_id") for fact in section_content}}
        component_status = "PASS" if zone.get("render_mode") == mode and bool(section_content) else "FAIL"
        detail = {"render_mode": zone.get("render_mode"), "expected_mode": mode, "role_evidence": sorted(role_names),
                  "status": component_status}
        if section_id == "ny_timeline":
            detail["required_stage_count"] = 5
            detail["actual_stage_count"] = len(section_content)
            detail["status"] = "PASS" if component_status == "PASS" and len(section_content) == 5 else "FAIL"
        elif section_id == "six_market_outlook":
            detail["required_market_count"] = 6
            detail["actual_market_count"] = len(section_content)
            detail["status"] = "PASS" if component_status == "PASS" and len(section_content) == 6 else "FAIL"
        elif section_id == "attention_points":
            detail["required_numbered_slots"] = 5
            detail["displayed_numbered_slots"] = min(5, _numbered_source_count(section_content))
            detail["status"] = "PASS" if component_status == "PASS" and detail["displayed_numbered_slots"] == 5 else "FAIL"
        elif section_id == "scenario_analysis":
            detail["scenario_row_count"] = 4
            detail["status"] = "PASS" if component_status == "PASS" and len(section_content) == 4 else "FAIL"
        elif section_id == "top_three_conditions":
            detail["condition_count"] = len(section_content)
            detail["status"] = "PASS" if component_status == "PASS" and len(section_content) == 3 else "FAIL"
        elif section_id == "material_market_relation":
            detail["arrow_evidence"] = "cause_effect_relation" in role_names
            detail["status"] = "PASS" if component_status == "PASS" and detail["arrow_evidence"] else "FAIL"
        elif section_id == "cross_asset_flow":
            detail["arrow_evidence"] = "causal_flow_arrow" in role_names
            detail["status"] = "PASS" if component_status == "PASS" and detail["arrow_evidence"] else "FAIL"
        visual_components[section_id] = detail
    visual_fidelity = all(item["status"] == "PASS" for item in visual_components.values())
    reference["status"] = "PASS" if reference["geometry_status"] == "PASS" and visual_fidelity else "FAIL"
    reference["visual_components"] = visual_components
    validation_gates["LAYOUT_INTEGRITY"] = "PASS" if reference["status"] == "PASS" and pairwise_nonoverlap and not overflows else "FAIL"
    validation_gates["READABILITY_768"] = "PASS" if readability else "FAIL"
    review = source.get("visual_review_attestation")
    if isinstance(review, dict):
        review_identity_ok = (review.get("status") == "PASS"
                              and review.get("verification_status") == "VERIFIED"
                              and review.get("report_id") == source.get("report_id")
                              and review.get("body_sha256") == source.get("body_hash")
                              and review.get("image_sha256") == image_hash
                              and review.get("template_id") == CONFIG["template_id"]
                              and bool(review.get("reviewed_at"))
                              and bool(review.get("review_id"))
                              and bool(review.get("reviewer_id") or review.get("trusted_provider")))
        validation_gates["VISUAL_REVIEW"] = "PASS" if review_identity_ok else "FAIL"
    else:
        validation_gates["VISUAL_REVIEW"] = "NOT_RUN"
    snapshot_provenance = source["market_data_snapshot"]["snapshot_provenance"]
    production_checks = (validation_gates.get("SOURCE_INTEGRITY") == "PASS"
                         and validation_gates.get("NUMERIC_INTEGRITY") == "PASS"
                         and validation_gates.get("SNAPSHOT_INTEGRITY") == "PASS"
                         and validation_gates.get("CONTENT_COMPLETENESS") == "PASS"
                         and validation_gates.get("LAYOUT_INTEGRITY") == "PASS"
                         and validation_gates.get("READABILITY_768") == "PASS"
                         and validation_gates.get("VISUAL_REVIEW") == "PASS"
                         and snapshot_provenance == "LIVE_CAPTURED"
                         and source.get("source_type") == "GOOGLE_DOCS"
                         and source.get("synthetic_fixture") is not True
                         and validation["status"] == "PASS" and not draft_preview and not missing and not extra and not overflows
                         and all(item["status"] == "PASS" for item in numeric_checks))
    validation_gates["PRODUCTION_READY"] = "PASS" if production_checks else "BLOCKED"
    row_groups = {section_id: row["id"] for row in FIXED_LAYOUT["rows"] for section_id in row["section_ids"]}
    cards = []
    for zone in FIXED_ZONES:
        section_id = zone["section_id"]
        contract_section_id = zone.get("contract_section_id", section_id)
        zone_facts = section_facts.get(section_id, [])
        content_status = "SOURCE_GAP" if any(fact.get("preview_only") for fact in zone_facts) else "PRESENT"
        cards.append({"section_id": contract_section_id, "source_section_id": section_id,
                      "title": SECTION_BY_ID[section_id]["title"], "x": zone["x"], "y": zone["y"],
                      "width": zone["width"], "height": zone["height"],
                      "row_group": row_groups[section_id], "fixed_zone": True, "page": 1,
                      "render_mode": zone["render_mode"], "content_status": content_status,
                      **({"market_count": len(SECTION_BY_ID[section_id].get("markets", []))}
                         if section_id == "six_market_outlook" else {})})
    content_complete = validation_gates.get("CONTENT_COMPLETENESS") == "PASS"
    status = "READY" if production_checks else "NOT_READY"
    result = {
        "status": status, "infographic_status": status, "report_status": "UNCHANGED",
        "report_id": source["report_id"], "template_id": CONFIG["template_id"],
        "revision": source["revision"], "source_document_id": source["source_document_id"],
        "source_snapshot_id": source["source_snapshot_id"],
        "snapshot_provenance": source["market_data_snapshot"]["snapshot_provenance"],
        "provenance_banner": provenance_label,
        "snapshot_sha256": source["market_data_snapshot"]["snapshot_sha256"], "body_hash": source["body_hash"],
        "image_sha256": image_hash, "png_count": 1, "required_fact_ids": required_ids,
        "rendered_fact_ids": rendered_ids, "missing_fact_ids": missing, "extra_fact_ids": extra,
        "render_bindings": bindings, "numeric_checks": numeric_checks, "validation": validation,
        "validation_gates": validation_gates,
        "visual_qa": {"original_dimensions_px": list(image.size), "scaled_dimensions_px": list(scaled.size),
                       "native_width_px": image.width, "native_height_px": image.height,
                       "target_display_width_px": DISPLAY_WIDTH,
                       "readability_test_width_px": DISPLAY_WIDTH, "render_native_before_downscale": True,
                       "body_font_px_by_zone": {zone["section_id"]: zone["font_size"] for zone in FIXED_ZONES},
                       "minimum_body_font_at_768_px": canvas["minimum_body_font_at_768_px"],
                       "no_panel_overlap": pairwise_nonoverlap, "text_overflows": overflows,
                       "status": "PASS" if readability and not overflows and pairwise_nonoverlap else "FAIL"},
        "visual_reference": reference, "visual_fidelity": {"status": "PASS" if visual_fidelity else "FAIL",
                           "geometry_alone_sufficient": False, "components": visual_components},
        "layout": {"panels": panels, "cards": cards,
                       "panel_order": EXPECTED_PANEL_IDS, "rows": FIXED_LAYOUT["rows"],
                       "single_sheet": True, "pages": 1, "pagination_enabled": False,
                       "template_mode": "08:00_FIXED_SINGLE_SHEET"},
        "content_completeness": validation_gates.get("CONTENT_COMPLETENESS", "NOT_RUN"),
        "image_bytes": image_bytes,
        "artifact_type": "DEBUG_PREVIEW" if draft_preview else "SOURCE_RECONSTRUCTED_DRAFT",
        "draft_preview": draft_preview,
        "production_eligible": bool(production_checks),
        "preview_missing_source_fields": list(dict.fromkeys([*validation.get("errors", []), *visible_missing])),
        "errors": list(validation.get("errors", [])) + overflows,
    }
    if output_path is not None:
        destination = Path(output_path)
        if destination.exists():
            result["status"] = "FAILED_VALIDATION"
            result["errors"].append("OUTPUT_EXISTS_REFUSE_OVERWRITE")
            result["image_bytes"] = None
            return result
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(image_bytes)
        result["output_path"] = str(destination)
    return result
