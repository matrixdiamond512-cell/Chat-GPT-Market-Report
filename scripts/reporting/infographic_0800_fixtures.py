"""Synthetic-only, source-complete contract fixture for the 08:00 fixed renderer."""
from __future__ import annotations

import hashlib
import json

from .infographic_0800_fixed import CONFIG


def build_synthetic_0800_source(*, snapshot_provenance: str = "SYNTHETIC_FIXTURE") -> dict:
    synthetic = snapshot_provenance == "SYNTHETIC_FIXTURE"
    report_id = "2099-01-01_08-00"
    report_datetime = "2099-01-01T08:00:00+09:00"
    title = "マーケットレポート｜2099/01/01（木）08:00"
    facts: list[dict] = []
    sections: list[dict] = []
    body_parts = [title]
    numeric_registry = []

    def add(section_id: str, text: str, fields: dict | None = None) -> str:
        fact_id = f"fixture:{section_id}:{len(facts) + 1:03d}"
        facts.append({"fact_id": fact_id, "section_id": section_id, "text": text,
                      "source_excerpt": text, "importance": "CRITICAL", "fields": fields or {}})
        body_parts.append(text)
        return fact_id

    for section in CONFIG["sections"]:
        section_id = section["id"]
        fact_ids: list[str] = []
        if section_id == "title_datetime":
            fact_ids.append(add(section_id, title))
        elif section_id == "overall_judgement":
            fact_ids.append(add(section_id, "中立〜やや慎重", {"role": "judgement"}))
            fact_ids.append(add(section_id, "米長期金利と原油価格が上値を抑えるため", {"role": "reason"}))
        elif section_id == "attention_points":
            for order, point in enumerate(("大阪日経225先物の回復", "米10年債利回り", "WTI原油の反発", "AI株の値動き", "SQ需給"), start=1):
                fact_ids.append(add(section_id, point, {"order": order}))
        elif section_id == "material_market_relation":
            fact_ids.append(add(section_id, "米長期金利上昇が米国株の上値を抑制", {
                "material": "米長期金利上昇", "affected_market": "米国株", "direction": "上値を抑制"}))
            fact_ids.append(add(section_id, "米国株は金利上昇で上値が重い", {
                "material": "金利上昇", "affected_market": "米国株", "direction": "上値が重い"}))
        elif section_id == "cross_asset_flow":
            fact_ids.append(add(section_id, "AI株→エネルギー株へ資金が移動し、AI株安がリスク選好を抑える", {
                "origin_asset": "AI株", "destination_asset": "エネルギー株", "direction": "資金が移動",
                "causal_link": "AI株安がリスク選好を抑える"}))
        elif section_id == "ny_timeline":
            for stage in section["stages"]:
                fact_ids.append(add(section_id, f"{stage}｜市場状況を確認", {"stage": stage}))
        elif section_id in ("ny_indices", "major_market_data"):
            names = (CONFIG["required_ny_index_labels"] if section_id == "ny_indices"
                     else CONFIG["required_market_data_labels"])
            for name in names:
                text = f"{name}｜100｜+1｜+1%｜上昇｜unit=fixture｜as_of=2026-10-08"
                fact_id = add(section_id, text, {"row": [name, "100", "+1", "+1%", "上昇"]})
                numeric_registry.append({"numeric_id": f"num:{fact_id}", "source_numeric_id": f"num:{fact_id}",
                                         "fact_id": fact_id, "value": "100", "unit": "fixture",
                                         "as_of": "2026-10-08", "source_excerpt": text,
                                         "as_of_source_excerpt": text})
        elif section_id == "six_market_outlook":
            for market in section["markets"]:
                text = f"{market}｜100 fixture｜基準時刻07:00 JST｜中立｜強気条件A｜弱気条件B"
                fact_id = f"fixture:{section_id}:{len(facts) + 1:03d}"
                fields = {"market": market, "current_value": "100 fixture", "current_value_as_of": "07:00 JST",
                          "current_value_numeric_id": f"num:{fact_id}", "judgement": "中立",
                          "bullish_condition": "強気条件A", "bearish_condition": "弱気条件B"}
                fact_id = add(section_id, text, fields)
                numeric_registry.append({"numeric_id": f"num:{fact_id}", "source_numeric_id": f"num:{fact_id}",
                                         "fact_id": fact_id, "value": "100", "unit": "fixture",
                                         "as_of": "07:00 JST", "source_excerpt": text,
                                         "as_of_source_excerpt": text})
        elif section_id == "news_materials":
            text = "合成ニュース｜07:00｜金｜価格反応を確認"
            fact_ids.append(add(section_id, text, {"headline": "合成ニュース", "time": "07:00",
                                                    "affected_market": "金", "price_reaction": "価格反応を確認"}))
        elif section_id == "scenario_analysis":
            for scenario in section["scenarios"]:
                fact_ids.append(add(section_id, f"{scenario}｜合成fixture条件", {"scenario": scenario}))
        elif section_id == "market_theme":
            fact_ids.append(add(section_id, "米長期金利の高止まりと株式市場の反応", {"role": "central_theme"}))
            fact_ids.append(add(section_id, "米長期金利の上昇が株式の上値を抑えるかを確認", {"role": "support"}))
        elif section_id == "ny_market_points":
            fact_ids.append(add(section_id, "米長期金利の動きが株式の重し"))
            fact_ids.append(add(section_id, "原油反落がインフレ懸念を一部緩和"))
        elif section_id == "positioning":
            fact_ids.append(add(section_id, "先物SQ需給を確認", {"category": "需給"}))
        elif section_id == "handover":
            for index, text in enumerate(("東京寄り付き後の日経先物", "米金利の推移"), start=1):
                fact_ids.append(add(section_id, text, {"order": index}))
        elif section_id == "top_three_conditions":
            for index, text in enumerate(("大阪日経225先物の水準", "米10年債利回りの方向", "WTI原油の反発有無"), start=1):
                fact_ids.append(add(section_id, text, {"order": index}))
        else:
            count = section.get("count", 1)
            for index in range(count):
                fact_ids.append(add(section_id, f"{section['title']}｜合成fixture {index + 1}"))
        if section_id in ("ny_indices", "major_market_data", "six_market_outlook"):
            fact_ids = [fact["fact_id"] for fact in facts if fact["section_id"] == section_id]
        sections.append({"section_id": section_id, "fact_ids": fact_ids})

    body_text = "\n".join(body_parts)
    body_hash = hashlib.sha256(body_text.encode("utf-8")).hexdigest()
    source_registry = json.loads(json.dumps(numeric_registry))
    source_registry_hash = hashlib.sha256(json.dumps(
        {"numeric_registry": source_registry}, ensure_ascii=False, sort_keys=True,
        separators=(",", ":")).encode("utf-8")).hexdigest()
    numeric_prevalidation = {"status": "PASS", "body_hash": body_hash,
                             "source_numeric_registry_sha256": source_registry_hash,
                             "source_registry_count": len(source_registry)}
    revision = "synthetic-fixture-revision-1"
    doc_id = "synthetic-fixture-doc"
    snapshot_identity = {"source_document_id": doc_id, "revision": revision, "body_hash": body_hash}
    snapshot_id = "docs-revision-sha256:" + hashlib.sha256(json.dumps(
        snapshot_identity, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
    created_at = "2099-01-01T07:59:00+09:00"
    updated_at = "2099-01-01T07:59:30+09:00"
    source = {
        "report_id": report_id, "report_datetime": report_datetime, "report_time": "08:00",
        "report_date": "2099-01-01", "revision": revision,
        "source_type": "SYNTHETIC_FIXTURE" if synthetic else "GOOGLE_DOCS",
        "source_document_id": doc_id, "source_snapshot_id": snapshot_id,
        "source_snapshot_identity": {"method": "SHA256_CANONICAL_SOURCE_ID_REVISION_BODY_HASH", **snapshot_identity},
        "source_created_at": created_at, "source_updated_at": updated_at,
        "source_persisted_after_report_time": False, "previous_close_table_rows": 28,
        "body_text": body_text, "full_text": body_text, "body_hash": body_hash,
        "title": title, "headline": "合成fixture・08:00固定構造確認", "sections": sections,
        "structured_facts": facts, "numeric_registry": numeric_registry,
        "numeric_registry_prevalidation": numeric_prevalidation,
        "source_numeric_registry_sha256": source_registry_hash,
        "source_numeric_registry": source_registry, "synthetic_fixture": synthetic,
        "template_mode": "08:00_FIXED_SINGLE_SHEET",
    }
    snapshot = {
        "snapshot_id": snapshot_id, "snapshot_provenance": snapshot_provenance,
        "report_id": report_id, "report_as_of": report_datetime,
        "source_document_id": doc_id, "source_document_revision": revision,
        "source_document_created_at": created_at, "source_document_updated_at": updated_at,
        "source_body_sha256": body_hash,
        "facts": [{key: fact[key] for key in ("fact_id", "section_id", "text", "source_excerpt")} for fact in facts],
        "numeric_registry": json.loads(json.dumps(numeric_registry)),
        "source_numeric_registry_sha256": source_registry_hash,
        "numeric_registry_prevalidation": numeric_prevalidation,
    }
    snapshot["snapshot_sha256"] = hashlib.sha256(json.dumps(
        snapshot, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
    source["market_data_snapshot"] = snapshot
    return source
