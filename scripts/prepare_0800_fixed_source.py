"""Prepare a fixed-template candidate from a previously locked Google Docs body.

No network access, data enrichment, or inferred fact completion is performed.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from datetime import datetime
from pathlib import Path

from PIL import Image

from reporting.infographic_0800_fixed import CONFIG, render_0800_fixed


def _stable_id(section_id: str, excerpt: str, ordinal: int) -> str:
    digest = hashlib.sha256(f"{section_id}\0{ordinal}\0{excerpt}".encode("utf-8")).hexdigest()[:20]
    return f"fact:{section_id}:{digest}"


def _canonical_hash(value: dict) -> str:
    packed = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(packed.encode("utf-8")).hexdigest()


def prepare_candidate(body: str, locked: dict, structured: dict, prior_validation: dict | None = None,
                     close_table_qa: dict | None = None) -> dict:
    if locked.get("source") != "GOOGLE_DOCS" or locked.get("report_id") != "2026-10-09_08-00":
        raise ValueError("LOCKED_GOOGLE_DOCS_SOURCE_REQUIRED")
    if body != structured.get("full_text") or hashlib.sha256(body.encode("utf-8")).hexdigest() != locked.get("body_hash"):
        raise ValueError("LOCKED_BODY_HASH_OR_COPY_MISMATCH")
    source_facts = structured.get("facts", [])
    snapshot_components = {
        "source_document_id": locked.get("source_file_id", ""),
        "revision": locked.get("source_revision_id", ""),
        "body_hash": locked.get("body_hash", ""),
    }
    snapshot_payload = json.dumps(snapshot_components, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    source_snapshot_id = "docs-revision-sha256:" + hashlib.sha256(snapshot_payload.encode("utf-8")).hexdigest()
    source_by_section: dict[str, list[dict]] = {}
    for fact in source_facts:
        source_by_section.setdefault(fact.get("section", ""), []).append(fact)
    facts: list[dict] = []
    numeric_registry: list[dict] = []
    section_map: dict[str, list[str]] = {section["id"]: [] for section in CONFIG["sections"]}

    def append(section_id: str, text: str, excerpt: str, fields: dict | None = None, importance: str = "HIGH") -> str:
        if not excerpt or excerpt not in body or not text or text not in excerpt:
            raise ValueError(f"FACT_NOT_IN_LOCKED_BODY:{section_id}")
        fact_id = _stable_id(section_id, excerpt, len(facts) + 1)
        facts.append({"fact_id": fact_id, "section_id": section_id, "text": text,
                      "source_excerpt": excerpt, "importance": importance, "fields": fields or {}})
        section_map[section_id].append(fact_id)
        return fact_id

    title = next((line for line in body.splitlines() if line.strip()), "")
    append("title_datetime", title, title, {"datetime": "2026-10-09 08:00"}, "CRITICAL")

    direct_section_map = {
        "ny_market_points": "昨夜のNY市場",
        "cross_asset_flow": "クロスアセット資金フロー",
        "positioning": "需給・ポジション",
        "handover": "12:00への引き継ぎ",
        "final_summary": "結論",
    }
    for target_id, source_name in direct_section_map.items():
        candidates = source_by_section.get(source_name, [])
        if candidates:
            item = candidates[0]
            append(target_id, item["text"], item["source_excerpt"], importance=item.get("importance", "HIGH"))

    # The approved reference separates the broad theme from source-stated
    # observations. Keep these as exact substrings; do not infer arrows or
    # causal links not stated by the report.
    theme_source = next(iter(source_by_section.get("今日の相場テーマ", [])), None)
    if theme_source:
        theme_text = theme_source.get("text", "")
        headline = re.match(r"^(本日の中心テーマは.+?です。)", theme_text)
        if headline:
            append("market_theme", headline.group(1), theme_source["source_excerpt"],
                   importance=theme_source.get("importance", "HIGH"))
        for phrase in ("原油高によるインフレ懸念", "AI・半導体株の調整",
                       "米長期金利の高止まり", "AI・半導体関連の弱さが目立ちました"):
            if phrase in theme_text:
                append("material_market_relation", phrase, theme_source["source_excerpt"],
                       importance=theme_source.get("importance", "HIGH"))

    # Classify the three explicit clauses in the source NY paragraph into the
    # timeline panel. Do not synthesize the two absent stages.
    ny_source = next(iter(source_by_section.get("昨夜のNY市場", [])), None)
    if ny_source:
        for source_stage, stage in (("序盤", "開場"), ("中盤", "中盤"), ("終盤", "終盤")):
            clause = next((part.strip() for part in re.split(r"(?<=[。])", ny_source["text"])
                           if part.strip().startswith(source_stage)), None)
            if clause:
                append("ny_timeline", clause, ny_source["source_excerpt"],
                       {"stage": stage, "source_fact_id": ny_source.get("fact_id")},
                       ny_source.get("importance", "CRITICAL"))
    handover_source = next(iter(source_by_section.get("12:00への引き継ぎ", [])), None)
    if handover_source:
        append("ny_timeline", handover_source["text"], handover_source["source_excerpt"],
               {"stage": "東京時間／次時間帯への引継ぎ", "source_fact_id": handover_source.get("fact_id")},
               handover_source.get("importance", "HIGH"))

    # Reuse only exact source phrases when a required panel has a matching
    # statement elsewhere in the report; retain its original excerpt provenance.
    conclusion = next(iter(source_by_section.get("結論", [])), None)
    if conclusion and "慎重姿勢が優勢" in conclusion["text"]:
        append("overall_judgement", "慎重姿勢が優勢", conclusion["source_excerpt"], importance="CRITICAL")
    leadership = next(iter(source_by_section.get("今日の主導市場", [])), None)
    if leadership:
        append("attention_points", leadership["text"], leadership["source_excerpt"], importance="HIGH")

    # Reuse the already validated structured row facts and numeric registry.
    # This stage does not re-detect or recount the 28-row source table.
    ny_labels = set(CONFIG["required_ny_index_labels"])
    data_labels = set(CONFIG["required_market_data_labels"])
    source_registry = structured.get("numeric_registry", [])
    source_registry_hash = _canonical_hash({"numeric_registry": source_registry})
    registry_prevalidation = {
        "status": (prior_validation or {}).get("numeric_registry_identity", "NOT_PROVIDED"),
        "body_hash": (prior_validation or {}).get("body_hash", ""),
        "source_numeric_registry_sha256": source_registry_hash,
        "source_registry_count": len(source_registry),
    }
    table_section = "前営業日終値・主要市場データ"
    aggregate_table = next((item for item in source_facts
                            if item.get("section") == table_section and not item.get("label")), None)
    if not aggregate_table and (prior_validation or {}).get("numeric_registry_identity") == "PASS":
        raise ValueError("PREVALIDATED_28_ROW_SOURCE_FACT_MISSING")
    aggregate_excerpt = aggregate_table.get("source_excerpt", "") if aggregate_table else ""
    if aggregate_excerpt and aggregate_excerpt not in body:
        raise ValueError("PREVALIDATED_28_ROW_SOURCE_FACT_NOT_IN_BODY")
    passed_labels = set((close_table_qa or {}).get("labels", []))
    source_rows = [item for item in source_facts
                   if item.get("section") == table_section and item.get("label") in passed_labels]
    source_row_facts: dict[str, dict] = {}
    candidate_row_fact_ids: dict[str, str] = {}
    for item in source_rows:
        label = item.get("label", "")
        cells = [str(value).strip() for value in str(item.get("text", "")).split("|")]
        original_row_excerpt = item.get("source_excerpt", "")
        if (not original_row_excerpt or not label or label not in aggregate_excerpt
                or any(cell and cell not in aggregate_excerpt for cell in cells)):
            raise ValueError(f"PREVALIDATED_ROW_FACT_SOURCE_BINDING_INVALID:{label}")
        source_row_facts[label] = {"cells": cells, "original_fact_id": item.get("fact_id"),
                                   "original_excerpt": original_row_excerpt}
        if label in ny_labels:
            fact_id = append("ny_indices", label, aggregate_excerpt, {"row": cells, "source_fact_id": item.get("fact_id")}, "CRITICAL")
            candidate_row_fact_ids[label] = fact_id
            for entry in source_registry:
                if entry.get("source_excerpt") == original_row_excerpt and entry.get("instrument") == label:
                    numeric_registry.append({"numeric_id": entry.get("fact_id"), "source_numeric_id": entry.get("fact_id"),
                                             "fact_id": fact_id, "value": entry.get("value"), "unit": entry.get("unit", ""),
                                             "as_of": entry.get("as_of", ""), "source_excerpt": aggregate_excerpt,
                                             "as_of_source_excerpt": aggregate_excerpt})
        if label in data_labels:
            fact_id = append("major_market_data", label, aggregate_excerpt, {"row": cells, "source_fact_id": item.get("fact_id")}, "HIGH")
            candidate_row_fact_ids[label] = fact_id
            for entry in source_registry:
                if entry.get("source_excerpt") == original_row_excerpt and entry.get("instrument") == label:
                    numeric_registry.append({"numeric_id": entry.get("fact_id"), "source_numeric_id": entry.get("fact_id"),
                                             "fact_id": fact_id, "value": entry.get("value"), "unit": entry.get("unit", ""),
                                             "as_of": entry.get("as_of", ""), "source_excerpt": aggregate_excerpt,
                                             "as_of_source_excerpt": aggregate_excerpt})

    # Previously verified 28-row count is carried forward as evidence only.
    prior_rows = (close_table_qa or {}).get("actualRowCount", locked.get("previous_close_table_rows", 0))

    # The report's six outlook labels contain directions only. Do not turn the
    # previous-close table into a current-value column or invent conditions.
    outlook_facts = source_by_section.get("主要6市場の短期見通し", [])
    outlook_value_labels = {"金": "COMEX金先物", "WTI": "WTI原油",
                            "日経225先物": "日経225先物（大阪取引所）", "USD/JPY": "USD/JPY",
                            "EUR/USD": "EUR/USD", "BTCUSD": "BTCUSD"}
    source_link_fact_ids: dict[str, str] = {}
    for label in outlook_value_labels.values():
        source_row = source_row_facts.get(label)
        if not source_row:
            continue
        linked_id = candidate_row_fact_ids.get(label)
        if not linked_id:
            linked_id = source_row["original_fact_id"]
            facts.append({"fact_id": linked_id, "section_id": "market_data_source_link", "text": label,
                          "source_excerpt": aggregate_excerpt, "importance": "HIGH",
                          "fields": {"row": source_row["cells"], "source_fact_id": linked_id}})
        source_link_fact_ids[label] = linked_id
        if not any(entry.get("fact_id") == linked_id for entry in numeric_registry):
            for entry in source_registry:
                if entry.get("source_excerpt") == source_row["original_excerpt"] and entry.get("instrument") == label:
                    numeric_registry.append({"numeric_id": entry.get("fact_id"), "source_numeric_id": entry.get("fact_id"),
                                             "fact_id": linked_id, "value": entry.get("value"), "unit": entry.get("unit", ""),
                                             "as_of": entry.get("as_of", ""), "source_excerpt": aggregate_excerpt,
                                             "as_of_source_excerpt": aggregate_excerpt})
    for item in outlook_facts:
        text_body = item.get("text", "")
        if text_body.count("：") != 1:
            continue
        for market, name in (("金", "金"), ("WTI", "WTI原油"), ("日経225先物", "日経225先物（大阪取引所）"),
                             ("USD/JPY", "USD/JPY"), ("EUR/USD", "EUR/USD"), ("BTCUSD", "BTCUSD")):
            match = re.match(rf"^{re.escape(market)}：(.+?)[。]?$", text_body)
            if match:
                fields = {"market": name, "judgement": match.group(1).strip("。")}
                source_label = outlook_value_labels[market]
                source_row = source_row_facts.get(source_label)
                if source_row:
                    value_text = source_row["cells"][1]
                    fields["current_value"] = "取得不能" if "取得不能" in value_text else value_text
                    fields["current_value_source_fact_id"] = source_link_fact_ids.get(source_label, "")
                    fields["current_value_source_excerpt"] = aggregate_excerpt
                    matching_registry = next((entry for entry in numeric_registry
                                              if entry.get("source_excerpt") == aggregate_excerpt
                                              and entry.get("fact_id") == source_link_fact_ids.get(source_label)
                                              and str(entry.get("value", "")) in value_text), None)
                    if matching_registry:
                        fields["current_value_numeric_id"] = matching_registry["numeric_id"]
                        fields["current_value_as_of"] = matching_registry["as_of"]
                append("six_market_outlook", text_body, item["source_excerpt"],
                       fields)

    news = source_by_section.get("重要ニュース・イベント", [])
    for item in news:
        headline_source = item["text"].removesuffix("が中心材料。")
        headlines = [part.strip() for part in headline_source.split("、") if part.strip()]
        for headline in headlines:
            append("news_materials", headline, item["source_excerpt"], {"headline": headline,
                   "source_fact_id": item.get("fact_id")}, item.get("importance", "HIGH"))

    scenarios = (("メイン", "メインシナリオ"), ("代替", "代替シナリオ"), ("崩れる条件", "シナリオが崩れる条件"))
    for label, source_name in scenarios:
        items = source_by_section.get(source_name, [])
        if items:
            item = items[0]
            append("scenario_analysis", item["text"], item["source_excerpt"], {"scenario": label})

    sections = [{"section_id": section_id, "fact_ids": fact_ids} for section_id, fact_ids in section_map.items()]
    report_datetime = "2026-10-09T08:00:00+09:00"
    updated_at = locked.get("source_updated_at", "")
    persisted_after = False
    if updated_at:
        persisted_after = datetime.fromisoformat(updated_at.replace("Z", "+00:00")) > datetime.fromisoformat(report_datetime)

    snapshot = {
        "snapshot_id": source_snapshot_id,
        "snapshot_provenance": "SOURCE_RECONSTRUCTED",
        "report_id": locked["report_id"],
        "report_as_of": report_datetime,
        "source_document_id": locked.get("source_file_id", ""),
        "source_document_revision": locked.get("source_revision_id", ""),
        "source_document_created_at": locked.get("source_created_at", ""),
        "source_document_updated_at": locked.get("source_updated_at", ""),
        "source_body_sha256": locked["body_hash"],
        "facts": [{"fact_id": fact["fact_id"], "section_id": fact["section_id"],
                   "text": fact["text"], "source_excerpt": fact["source_excerpt"]} for fact in facts],
        "numeric_registry": numeric_registry,
        "source_numeric_registry_sha256": source_registry_hash,
        "numeric_registry_prevalidation": registry_prevalidation,
    }
    snapshot["snapshot_sha256"] = _canonical_hash(snapshot)

    return {
        "report_id": locked["report_id"], "report_datetime": report_datetime,
        "revision": locked.get("source_revision_id", ""), "source_type": "GOOGLE_DOCS",
        "source_document_id": locked.get("source_file_id", ""), "source_snapshot_id": source_snapshot_id,
        "source_snapshot_identity": {"method": "SHA256_CANONICAL_SOURCE_ID_REVISION_BODY_HASH",
                                     **snapshot_components},
        "source_created_at": locked.get("source_created_at", ""),
        "source_updated_at": locked.get("source_updated_at", ""),
        "market_data_snapshot": snapshot,
        "source_persisted_after_report_time": persisted_after,
        "previous_close_table_rows": prior_rows,
        "numeric_registry_prevalidation": registry_prevalidation,
        "source_numeric_registry_sha256": source_registry_hash,
        "source_numeric_registry": source_registry,
        "body_text": body, "body_hash": locked["body_hash"], "title": title,
        "sections": sections, "structured_facts": facts, "numeric_registry": numeric_registry,
        "source_selection": {"source": "GOOGLE_DOCS", "source_order": ["CHAT_TRANSCRIPT", "GOOGLE_DOCS", "CANONICAL_JSON"],
                             "body_preserved_exactly": True, "fallbacks_used": []},
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--body", type=Path, required=True)
    parser.add_argument("--source-lock", type=Path, required=True)
    parser.add_argument("--structured-source", type=Path, required=True)
    parser.add_argument("--prior-validation", type=Path, required=True,
                        help="Previously completed source/numeric validation evidence; never re-runs extraction.")
    parser.add_argument("--candidate-out", type=Path, required=True)
    parser.add_argument("--validation-out", type=Path, required=True)
    parser.add_argument("--visual-reference-check-out", type=Path, required=True)
    parser.add_argument("--close-table-qa", type=Path)
    parser.add_argument("--draft-preview", action="store_true",
                        help="Emit a local debug PNG with explicit missing-source labels; never READY.")
    parser.add_argument("--preview-png", type=Path)
    args = parser.parse_args()
    body = args.body.read_text(encoding="utf-8")
    locked = json.loads(args.source_lock.read_text(encoding="utf-8"))
    structured = json.loads(args.structured_source.read_text(encoding="utf-8"))
    prior_validation = json.loads(args.prior_validation.read_text(encoding="utf-8"))
    close_table_qa = json.loads(args.close_table_qa.read_text(encoding="utf-8")) if args.close_table_qa else None
    candidate = prepare_candidate(body, locked, structured, prior_validation, close_table_qa)
    if args.draft_preview and not args.preview_png:
        parser.error("--draft-preview requires --preview-png")
    result = render_0800_fixed(candidate, args.preview_png, draft_preview=args.draft_preview)
    args.candidate_out.parent.mkdir(parents=True, exist_ok=True)
    args.validation_out.parent.mkdir(parents=True, exist_ok=True)
    args.visual_reference_check_out.parent.mkdir(parents=True, exist_ok=True)
    args.candidate_out.write_text(json.dumps(candidate, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    artifact = {key: value for key, value in result.items() if key != "image_bytes"}
    artifact["source"] = "GOOGLE_DOCS"
    artifact["source_document_id"] = candidate["source_document_id"]
    artifact["source_updated_at"] = candidate["source_updated_at"]
    artifact["source_persisted_after_report_time"] = candidate["source_persisted_after_report_time"]
    if close_table_qa:
        artifact["previous_close_table_qa"] = close_table_qa
    reference_path = Path(__file__).resolve().parents[1] / CONFIG["reference_asset"]
    with Image.open(reference_path) as reference_image:
        reference_dimensions = list(reference_image.size)
    reference_result = result.get("visual_reference", {})
    png_path = Path(result["output_path"]) if result.get("output_path") else None
    png_dimensions = None
    if png_path and png_path.is_file():
        with Image.open(png_path) as candidate_image:
            png_dimensions = list(candidate_image.size)
    facts_by_section = {}
    for fact in candidate.get("structured_facts", []):
        facts_by_section.setdefault(fact.get("section_id"), []).append(fact)
    section_presence = []
    for section in CONFIG["sections"]:
        section_id = section["id"]
        bound_facts = facts_by_section.get(section_id, [])
        section_presence.append({"section_id": section_id, "title": section["title"],
                                 "source_bound_fact_count": len(bound_facts),
                                 "status": "PRESENT" if bound_facts else "SOURCE_GAP"})
    timeline_stages = {fact.get("fields", {}).get("stage") for fact in facts_by_section.get("ny_timeline", [])}
    outlooks = facts_by_section.get("six_market_outlook", [])
    outlook_fields = [fact.get("fields", {}) for fact in outlooks]
    news_fields = [fact.get("fields", {}) for fact in facts_by_section.get("news_materials", [])]
    evidence = {
        "section_presence": section_presence,
        "ny_timeline": {"required_stages": next(item["stages"] for item in CONFIG["sections"] if item["id"] == "ny_timeline"),
                        "source_bound_stages": [stage for stage in next(item["stages"] for item in CONFIG["sections"] if item["id"] == "ny_timeline") if stage in timeline_stages],
                        "missing_stages": [stage for stage in next(item["stages"] for item in CONFIG["sections"] if item["id"] == "ny_timeline") if stage not in timeline_stages]},
        "six_market_outlook": {"required_market_count": len(next(item["markets"] for item in CONFIG["sections"] if item["id"] == "six_market_outlook")),
                               "source_bound_market_count": len(outlooks),
                               "missing_current_value_count": sum(not item.get("current_value") for item in outlook_fields),
                               "missing_bullish_condition_count": sum(not item.get("bullish_condition") for item in outlook_fields),
                               "missing_bearish_condition_count": sum(not item.get("bearish_condition") for item in outlook_fields)},
        "cross_asset_causality": {"status": "SOURCE_BOUND" if facts_by_section.get("cross_asset_flow") else "SOURCE_GAP"},
        "news": {"source_bound_headline_count": len(news_fields),
                 "missing_time_count": sum(not item.get("time") for item in news_fields),
                 "missing_affected_market_count": sum(not item.get("affected_market") for item in news_fields),
                 "missing_price_reaction_count": sum(not item.get("price_reaction") for item in news_fields)},
        "top_three_conditions": {"source_bound_count": len(facts_by_section.get("top_three_conditions", [])),
                                 "source_gap": len(facts_by_section.get("top_three_conditions", [])) != 3},
    }
    gate_results = dict(result.get("validation_gates", {}))
    gate_results["CONTENT_COMPLETENESS"] = "PASS" if not result.get("validation", {}).get("errors") else "FAIL"
    gate_results["READABILITY_768"] = result.get("visual_qa", {}).get("status", "NOT_RUN")
    gate_results["PRODUCTION_READY"] = "BLOCKED" if result.get("status") != "READY" else "PASS"
    visual_check = {
        "status": gate_results.get("LAYOUT_INTEGRITY", "NOT_RUN"),
        "reference_asset": str(reference_path), "reference_dimensions_px": reference_dimensions,
        "reference_sha256": hashlib.sha256(reference_path.read_bytes()).hexdigest(),
        "candidate_image_sha256": result.get("image_sha256"),
        "candidate_dimensions_px": png_dimensions,
        "png_count": result.get("png_count", 0),
        "checks": {"single_png": "PASS" if result.get("png_count") == 1 else "FAIL",
                   "sixteen_zone_order": reference_result.get("sixteen_zone_order", "NOT_RUN"),
                   "four_row_grouping": reference_result.get("four_row_grouping", "NOT_RUN"),
                   "top_five_panels": reference_result.get("top_five_panels", "NOT_RUN"),
                   "middle_upper_three_panels": reference_result.get("middle_upper_three_panels", "NOT_RUN"),
                   "middle_lower_four_panels": reference_result.get("middle_lower_four_panels", "NOT_RUN"),
                   "bottom_four_panels": reference_result.get("bottom_four_panels", "NOT_RUN"),
                   "fixed_coordinates": reference_result.get("status", "NOT_RUN")},
        "visual_qa": result.get("visual_qa", {"status": "NOT_RUN"}),
        "reason": "Layout and content completeness are independent. Missing facts remain source-gap labels in their fixed zones.",
    }
    artifact["validation_gates"] = gate_results
    artifact["content_evidence"] = evidence
    artifact["rendered_section_presence"] = section_presence
    artifact["png_sha256"] = result.get("image_sha256")
    artifact["png_count"] = result.get("png_count", 0)
    artifact["snapshot_provenance"] = candidate["market_data_snapshot"]["snapshot_provenance"]
    artifact["snapshot_sha256"] = candidate["market_data_snapshot"]["snapshot_sha256"]
    artifact["market_data_snapshot"] = {key: candidate["market_data_snapshot"][key] for key in
                                         ("snapshot_id", "snapshot_provenance", "report_id", "report_as_of",
                                          "source_document_created_at", "source_document_updated_at", "source_body_sha256",
                                          "snapshot_sha256")}
    comparison_path = args.visual_reference_check_out.with_name("reference-vs-source-reconstructed.png")
    if png_path and png_path.is_file():
        thumb_width = 750
        grid_gap, title_height = 24, 48
        ref_height = round(reference_dimensions[1] * thumb_width / reference_dimensions[0])
        canvas = Image.new("RGB", (thumb_width * 2 + grid_gap,
                                    title_height + ref_height + 24), "#E7EDF4")
        draw = __import__("PIL.ImageDraw", fromlist=["ImageDraw"]).Draw(canvas)
        draw.text((12, 14), "APPROVED REFERENCE", fill="#08295A")
        draw.text((thumb_width + grid_gap + 12, 14), "SOURCE_RECONSTRUCTED • fixed single sheet", fill="#08295A")
        with Image.open(reference_path) as reference_image:
            ref = reference_image.convert("RGB").resize((thumb_width, ref_height), Image.Resampling.LANCZOS)
        with Image.open(png_path) as candidate_image:
            candidate_thumb = candidate_image.convert("RGB").resize((thumb_width, ref_height), Image.Resampling.LANCZOS)
        canvas.paste(ref, (0, title_height))
        canvas.paste(candidate_thumb, (thumb_width + grid_gap, title_height))
        comparison_path.parent.mkdir(parents=True, exist_ok=True)
        canvas.save(comparison_path, format="PNG", optimize=False, compress_level=9)
    artifact["visual_reference_comparison_path"] = str(comparison_path) if comparison_path.exists() else None
    args.validation_out.write_text(json.dumps(artifact, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    args.visual_reference_check_out.write_text(json.dumps(visual_check, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": result["status"], "errors": result.get("validation", {}).get("errors", result.get("errors", [])),
                      "candidate": str(args.candidate_out), "validation": str(args.validation_out),
                      "visual_reference_check": str(args.visual_reference_check_out),
                      "previous_close_table_rows": candidate["previous_close_table_rows"],
                      "png_written": bool(result.get("output_path"))}, ensure_ascii=False))
    return 0 if result["status"] in ("READY", "NOT_READY") and args.draft_preview else (0 if result["status"] == "READY" else 2)


if __name__ == "__main__":
    raise SystemExit(main())
