"""Fail-closed pre-save/pre-render QA for new 08:00 report content."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
CONTRACT_PATH = ROOT / "config" / "infographic_0800_content_contract_v1.json"
CONTRACT = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
FIXED_CONFIG = json.loads((ROOT / "config" / "infographic_0800_fixed_v1.json").read_text(encoding="utf-8"))
SECTIONS = FIXED_CONFIG["sections"]
EXPECTED_SECTION_IDS = [item["id"] for item in SECTIONS]
EXPECTED_INDEX_LABELS = FIXED_CONFIG["required_ny_index_labels"]
EXPECTED_DATA_LABELS = FIXED_CONFIG["required_market_data_labels"]
EXPECTED_MARKETS = next(item["markets"] for item in SECTIONS if item["id"] == "six_market_outlook")
EXPECTED_TIMELINE_STAGES = next(item["stages"] for item in SECTIONS if item["id"] == "ny_timeline")
EXPECTED_SCENARIOS = next(item["scenarios"] for item in SECTIONS if item["id"] == "scenario_analysis")

PRODUCTION_GATES = (
    "SOURCE_INTEGRITY", "NUMERIC_INTEGRITY", "SNAPSHOT_INTEGRITY",
    "CONTENT_COMPLETENESS", "LAYOUT_INTEGRITY", "READABILITY_768", "VISUAL_REVIEW",
)


def canonical_sha256(value: Any) -> str:
    packed = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(packed.encode("utf-8")).hexdigest()


def provenance_banner(provenance: str) -> str:
    labels = {
        "LIVE_CAPTURED": "LIVE_CAPTURED",
        "SOURCE_RECONSTRUCTED": "SOURCE_RECONSTRUCTED",
        "SYNTHETIC_FIXTURE": "SYNTHETIC_FIXTURE",
    }
    if provenance not in labels:
        raise ValueError("SNAPSHOT_PROVENANCE_INVALID")
    return labels[provenance]


def evaluate_0800_production_candidate(source: dict[str, Any], gates: dict[str, str], *,
                                       image_sha256: str | None = None) -> dict[str, Any]:
    """Production is only a candidate for a fully validated LIVE_CAPTURED image."""
    provenance = (source.get("market_data_snapshot") or {}).get("snapshot_provenance")
    errors: list[str] = []
    if provenance != "LIVE_CAPTURED":
        errors.append("PROVENANCE_NOT_LIVE_CAPTURED")
    if source.get("source_type") != "GOOGLE_DOCS":
        errors.append("PRODUCTION_SOURCE_TYPE_NOT_GOOGLE_DOCS")
    if source.get("synthetic_fixture") is True or source.get("source_type") == "SYNTHETIC_FIXTURE":
        errors.append("SYNTHETIC_FIXTURE_PRODUCTION_FORBIDDEN")
    if not image_sha256:
        errors.append("INFOGRAPHIC_HASH_MISSING")
    for gate in PRODUCTION_GATES:
        if gates.get(gate) != "PASS":
            errors.append("PRODUCTION_GATE_NOT_PASS:" + gate)
    review = source.get("visual_review_attestation")
    if not isinstance(review, dict) or review.get("status") != "PASS" or review.get("verification_status") != "VERIFIED":
        errors.append("TRUSTED_VISUAL_REVIEW_MISSING")
    elif (review.get("report_id") != source.get("report_id")
          or review.get("body_sha256") != source.get("body_hash")
          or review.get("image_sha256") != image_sha256
          or review.get("template_id") != FIXED_CONFIG["template_id"]
          or not review.get("review_id") or not review.get("reviewed_at")
          or not (review.get("reviewer_id") or review.get("trusted_provider"))):
        errors.append("TRUSTED_VISUAL_REVIEW_IDENTITY_MISMATCH")
    return {"status": "PASS" if not errors else "BLOCKED", "production_candidate": not errors,
            "report_id": source.get("report_id"), "body_sha256": source.get("body_hash"),
            "image_sha256": image_sha256, "snapshot_provenance": provenance,
            "required_gates": list(PRODUCTION_GATES), "errors": errors}


def build_0800_generation_attestation(payload: dict[str, Any], qa: dict[str, Any]) -> dict[str, Any]:
    """Compact, identity-bound pre-save/pre-render result for downstream entry points."""
    facts = payload.get("structured_facts") or []
    numerics = payload.get("numeric_registry") or []
    snapshot = payload.get("market_data_snapshot") or {}
    attestation = {
        "contract_id": qa.get("contract_id"), "gate": qa.get("gate"), "status": qa.get("status"),
        "report_id": qa.get("report_id"), "body_sha256": qa.get("body_sha256"),
        "structured_source_sha256": canonical_sha256({"structured_facts": facts, "sections": payload.get("sections")}),
        "numeric_registry_sha256": canonical_sha256({"numeric_registry": numerics}),
        "snapshot_sha256": snapshot.get("snapshot_sha256"),
        "snapshot_provenance": snapshot.get("snapshot_provenance"),
        "fact_count": qa.get("fact_count", 0), "numeric_count": qa.get("numeric_count", 0),
        "validation_gates": qa.get("validation_gates", {}),
        "qa_result_sha256": "",
    }
    attestation["qa_result_sha256"] = canonical_sha256(attestation)
    return attestation


def write_0800_qa_evidence(payload: dict[str, Any], result: dict[str, Any], evidence_root: str | Path) -> Path:
    """Persist a nonproduction, no-overwrite, report-bound QA record under artifacts/."""
    root = Path(evidence_root).resolve()
    artifacts_root = (ROOT / "artifacts").resolve()
    if root != artifacts_root and artifacts_root not in root.parents:
        raise ValueError("QA_EVIDENCE_MUST_STAY_UNDER_ARTIFACTS")
    report_id = str(payload.get("report_id", ""))
    body_sha = str(result.get("generation_qa", {}).get("body_sha256", ""))
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}_08-00", report_id) or not re.fullmatch(r"[0-9a-f]{64}", body_sha):
        raise ValueError("QA_EVIDENCE_IDENTITY_INVALID")
    snapshot = payload.get("market_data_snapshot") or {}
    render = result.get("render_result") or {}
    evidence = {
        "record_type": "NONPRODUCTION_0800_GENERATION_QA",
        "report_id": report_id,
        "body_sha256": body_sha,
        "structured_source_sha256": canonical_sha256({"structured_facts": payload.get("structured_facts") or [],
                                                       "sections": payload.get("sections") or []}),
        "numeric_registry_sha256": canonical_sha256({"numeric_registry": payload.get("numeric_registry") or []}),
        "snapshot_sha256": snapshot.get("snapshot_sha256"),
        "qa_result": result.get("generation_qa"),
        "publication_receipt": result.get("generation_qa_attestation"),
        "validation_gates": render.get("validation_gates", result.get("required_validation_gates", {})),
        "infographic_sha256": render.get("image_sha256"),
        "snapshot_provenance": snapshot.get("snapshot_provenance"),
        "production_candidate": result.get("production_candidate", {"status": "BLOCKED", "production_candidate": False}),
    }
    directory = root / report_id
    directory.mkdir(parents=True, exist_ok=True)
    destination = directory / f"{body_sha}.json"
    with destination.open("x", encoding="utf-8", newline="\n") as stream:
        stream.write(json.dumps(evidence, ensure_ascii=False, indent=2) + "\n")
    return destination


def validate_0800_generation_contract(payload: dict[str, Any]) -> dict[str, Any]:
    """Validate draft body + structured facts before Docs save or image rendering.

    This gate intentionally does not fetch data, invent unavailable values, create a
    Google Doc, or render an image. It accepts a generation artifact only when every
    required item has an exact body-bound excerpt and stable fact identity.
    """
    errors: list[str] = []
    if not isinstance(payload, dict):
        payload = {}
        errors.append("GENERATION_PAYLOAD_INVALID")
    body = payload.get("body_text")
    if not isinstance(body, str) or not body.strip():
        errors.append("BODY_TEXT_MISSING")
        body = ""
    calculated_hash = hashlib.sha256(body.encode("utf-8")).hexdigest()
    if payload.get("body_hash") != calculated_hash:
        errors.append("BODY_HASH_MISMATCH")
    report_id = str(payload.get("report_id", ""))
    report_datetime = str(payload.get("report_datetime", ""))
    match = re.fullmatch(r"(\d{4}-\d{2}-\d{2})T08:00(?::00)?(?:\+09:00|\+0900)", report_datetime)
    if not match or report_id != f"{match.group(1)}_08-00":
        errors.append("REPORT_ID_OR_SLOT_MISMATCH")

    sections = payload.get("sections")
    if not isinstance(sections, list) or [item.get("section_id") for item in sections if isinstance(item, dict)] != EXPECTED_SECTION_IDS:
        errors.append("FIXED_08_SECTION_ORDER_MISMATCH")
        sections = sections if isinstance(sections, list) else []
    raw_facts = payload.get("structured_facts")
    if not isinstance(raw_facts, list) or not raw_facts:
        errors.append("STRUCTURED_FACTS_MISSING")
        raw_facts = []
    facts: dict[str, dict] = {}
    for fact in raw_facts:
        if not isinstance(fact, dict):
            errors.append("FACT_SHAPE_INVALID")
            continue
        fact_id = fact.get("fact_id")
        if not isinstance(fact_id, str) or not fact_id.strip() or fact_id in facts:
            errors.append("FACT_ID_MISSING_OR_DUPLICATE")
            continue
        excerpt = fact.get("source_excerpt")
        text = fact.get("text")
        if not isinstance(excerpt, str) or not excerpt or excerpt not in body or not isinstance(text, str) or not text or text not in excerpt:
            errors.append(f"FACT_SOURCE_BINDING_INVALID:{fact_id}")
        if fact.get("section_id") not in EXPECTED_SECTION_IDS:
            errors.append(f"FACT_SECTION_UNKNOWN:{fact_id}")
        if not isinstance(fact.get("fields", {}), dict):
            errors.append(f"FACT_FIELDS_INVALID:{fact_id}")
        facts[fact_id] = fact

    by_section: dict[str, list[dict]] = {section_id: [] for section_id in EXPECTED_SECTION_IDS}
    referenced: set[str] = set()
    for section in sections:
        if not isinstance(section, dict):
            errors.append("SECTION_SHAPE_INVALID")
            continue
        section_id = section.get("section_id")
        fact_ids = section.get("fact_ids")
        if not isinstance(fact_ids, list):
            errors.append(f"SECTION_FACT_IDS_INVALID:{section_id}")
            continue
        for fact_id in fact_ids:
            fact = facts.get(fact_id)
            if not fact:
                errors.append(f"SECTION_FACT_UNRESOLVED:{section_id}:{fact_id}")
                continue
            if fact.get("section_id") != section_id:
                errors.append(f"FACT_SECTION_LINK_MISMATCH:{fact_id}")
            by_section.setdefault(section_id, []).append(fact)
            referenced.add(fact_id)
    for fact_id in facts.keys() - referenced:
        errors.append(f"FACT_NOT_ASSIGNED_TO_SECTION:{fact_id}")

    def require_field(fact: dict, field_name: str, *, source_bound: bool = True) -> str:
        value = fact.get("fields", {}).get(field_name)
        fact_id = fact.get("fact_id", "unknown")
        if not isinstance(value, str) or not value.strip():
            errors.append(f"REQUIRED_FIELD_MISSING:{fact_id}:{field_name}")
            return ""
        if source_bound and value not in str(fact.get("source_excerpt", "")):
            errors.append(f"REQUIRED_FIELD_NOT_SOURCE_BOUND:{fact_id}:{field_name}")
        return value

    judgement = by_section.get("overall_judgement", [])
    if len(judgement) < 2 or {fact.get("fields", {}).get("role") for fact in judgement} < {"judgement", "reason"}:
        errors.append("OVERALL_JUDGEMENT_AND_REASON_REQUIRED")
    attention = by_section.get("attention_points", [])
    if len(attention) != 5 or [fact.get("fields", {}).get("order") for fact in attention] != [1, 2, 3, 4, 5]:
        errors.append("EXACTLY_FIVE_ATTENTION_POINTS_REQUIRED")
    theme = by_section.get("market_theme", [])
    if len(theme) < 2 or {fact.get("fields", {}).get("role") for fact in theme} < {"central_theme", "support"}:
        errors.append("MARKET_THEME_AND_SUPPORT_REQUIRED")
    if len(by_section.get("material_market_relation", [])) < 1:
        errors.append("MATERIAL_MARKET_RELATION_REQUIRED")
    for fact in by_section.get("material_market_relation", []):
        for key in ("material", "affected_market", "direction"):
            require_field(fact, key)
    timeline = by_section.get("ny_timeline", [])
    if [item.get("fields", {}).get("stage") for item in timeline] != EXPECTED_TIMELINE_STAGES:
        errors.append("FIVE_ORDERED_NY_TIMELINE_STAGES_REQUIRED")
    for label in EXPECTED_INDEX_LABELS:
        if not any((fact.get("fields", {}).get("row") or [None])[0] == label for fact in by_section.get("ny_indices", [])):
            errors.append(f"NY_INDEX_ROW_MISSING:{label}")
    for label in EXPECTED_DATA_LABELS:
        if not any((fact.get("fields", {}).get("row") or [None])[0] == label for fact in by_section.get("major_market_data", [])):
            errors.append(f"MARKET_DATA_ROW_MISSING:{label}")
    if len(by_section.get("ny_market_points", [])) < int(CONTRACT["generation_qa"]["minimum_counts"]["ny_market_points"]):
        errors.append("NY_MARKET_POINTS_INSUFFICIENT")
    for fact in by_section.get("cross_asset_flow", []):
        for key in ("origin_asset", "destination_asset", "direction", "causal_link"):
            require_field(fact, key)
    if len(by_section.get("cross_asset_flow", [])) < 1:
        errors.append("CROSS_ASSET_FLOW_REQUIRED")
    if len(by_section.get("positioning", [])) < 1:
        errors.append("POSITIONING_FACT_REQUIRED")
    for fact in by_section.get("positioning", []):
        require_field(fact, "category", source_bound=False)
    outlook = by_section.get("six_market_outlook", [])
    if [fact.get("fields", {}).get("market") for fact in outlook] != EXPECTED_MARKETS:
        errors.append("SIX_MARKET_OUTLOOK_COVERAGE_OR_ORDER_INVALID")
    for fact in outlook:
        for key in ("current_value", "current_value_as_of", "judgement", "bullish_condition", "bearish_condition"):
            require_field(fact, key)
    news = by_section.get("news_materials", [])
    if len(news) < int(CONTRACT["generation_qa"]["minimum_counts"]["news_materials"]):
        errors.append("AT_LEAST_ONE_NEWS_ITEM_REQUIRED")
    for fact in news:
        for key in ("headline", "time", "affected_market", "price_reaction"):
            require_field(fact, key)
    if [fact.get("fields", {}).get("scenario") for fact in by_section.get("scenario_analysis", [])] != EXPECTED_SCENARIOS:
        errors.append("FOUR_ORDERED_SCENARIO_FACTS_REQUIRED")
    if len(by_section.get("handover", [])) < int(CONTRACT["generation_qa"]["minimum_counts"]["handover"]):
        errors.append("NEXT_SLOT_HANDOVER_REQUIRED")
    if [fact.get("fields", {}).get("order") for fact in by_section.get("handover", [])] != list(range(1, len(by_section.get("handover", [])) + 1)):
        errors.append("HANDOVER_ORDER_INVALID")
    if len(by_section.get("top_three_conditions", [])) != 3 or [fact.get("fields", {}).get("order") for fact in by_section.get("top_three_conditions", [])] != [1, 2, 3]:
        errors.append("EXACTLY_THREE_ORDERED_TOP_CONDITIONS_REQUIRED")
    if len(by_section.get("final_summary", [])) < 1:
        errors.append("FINAL_SUMMARY_REQUIRED")

    numeric_registry = payload.get("numeric_registry")
    if not isinstance(numeric_registry, list) or not numeric_registry:
        errors.append("NUMERIC_REGISTRY_REQUIRED")
        numeric_registry = []
    seen_numeric_ids: set[str] = set()
    numeric_facts: set[str] = set()
    numeric_checks: list[dict[str, Any]] = []
    for entry in numeric_registry:
        if not isinstance(entry, dict):
            errors.append("NUMERIC_ENTRY_INVALID")
            continue
        numeric_id = entry.get("numeric_id")
        fact_id = entry.get("fact_id")
        fact = facts.get(fact_id)
        excerpt = entry.get("source_excerpt")
        value = str(entry.get("value", ""))
        unit = str(entry.get("unit", ""))
        as_of = str(entry.get("as_of", ""))
        as_of_excerpt = entry.get("as_of_source_excerpt")
        valid = bool(numeric_id and numeric_id not in seen_numeric_ids and fact and excerpt == fact.get("source_excerpt")
                     and excerpt in body and value and value in excerpt and as_of and isinstance(as_of_excerpt, str)
                     and as_of_excerpt in body and as_of in as_of_excerpt and (not unit or unit in excerpt))
        if not valid:
            errors.append(f"NUMERIC_REGISTRY_IDENTITY_INVALID:{numeric_id or fact_id}")
        if numeric_id:
            seen_numeric_ids.add(numeric_id)
        if fact_id:
            numeric_facts.add(str(fact_id))
        numeric_checks.append({"numeric_id": numeric_id, "fact_id": fact_id, "status": "PASS" if valid else "FAIL"})
    for fact in [*by_section.get("ny_indices", []), *by_section.get("major_market_data", [])]:
        row = fact.get("fields", {}).get("row")
        if not isinstance(row, list) or len(row) < 2 or not any(str(cell).strip() for cell in row[1:]):
            errors.append(f"NUMERIC_TABLE_ROW_VALUE_MISSING:{fact.get('fact_id')}")
        if fact.get("fact_id") not in numeric_facts:
            errors.append(f"NUMERIC_FACT_REGISTRY_LINK_MISSING:{fact.get('fact_id')}")
    for fact in outlook:
        number = re.search(r"[-+]?\d[\d,.]*(?:%|[A-Za-z/]+)?", str(fact.get("fields", {}).get("current_value", "")))
        numeric_id = fact.get("fields", {}).get("current_value_numeric_id")
        if number and not any(entry.get("numeric_id") == numeric_id and entry.get("fact_id") == fact.get("fact_id")
                              and number.group(0).rstrip("%") in str(entry.get("value", ""))
                              for entry in numeric_registry if isinstance(entry, dict)):
            errors.append(f"SIX_MARKET_CURRENT_VALUE_NUMERIC_LINK_MISSING:{fact.get('fact_id')}")

    # Reuse the same strict source/snapshot/numeric validators as the fixed renderer;
    # generation QA must not be weaker than the downstream artifact checks.
    strict_gates: dict[str, str] = {}
    try:
        from .infographic_0800_fixed import validate_0800_source
        source_validation = validate_0800_source(payload)
        strict_gates = source_validation.get("validation_gates", {})
        for gate in ("SOURCE_INTEGRITY", "NUMERIC_INTEGRITY", "SNAPSHOT_INTEGRITY", "CONTENT_COMPLETENESS"):
            if strict_gates.get(gate) != "PASS":
                errors.append("DOWNSTREAM_" + gate + "_NOT_PASS")
        if source_validation.get("errors"):
            errors.extend("SOURCE_VALIDATION:" + str(error) for error in source_validation["errors"])
    except (ImportError, ValueError, TypeError, KeyError) as exc:
        errors.append("STRICT_SOURCE_VALIDATOR_UNAVAILABLE:" + str(exc))

    status = "PASS" if not errors else "FAIL"
    return {
        "contract_id": CONTRACT["contract_id"], "gate": "PRE_SAVE_AND_PRE_RENDER_08_00_GENERATION_QA",
        "status": status, "report_id": report_id or None, "body_sha256": calculated_hash,
        "fact_count": len(facts), "numeric_count": len(numeric_checks),
        "required_section_ids": EXPECTED_SECTION_IDS, "missing_fact_ids": sorted(facts.keys() - referenced),
        "numeric_checks": numeric_checks, "errors": errors,
        "validation_gates": {"SOURCE_INTEGRITY": strict_gates.get("SOURCE_INTEGRITY", "NOT_RUN"),
                             "NUMERIC_INTEGRITY": strict_gates.get("NUMERIC_INTEGRITY", "NOT_RUN"),
                             "SNAPSHOT_INTEGRITY": strict_gates.get("SNAPSHOT_INTEGRITY", "NOT_RUN"),
                             "CONTENT_COMPLETENESS": strict_gates.get("CONTENT_COMPLETENESS", "NOT_RUN")},
        "side_effects": {"google_docs_write": False, "png_write": False, "external_api": False},
    }


def generate_0800_with_contract(payload: dict[str, Any], output_path: str | Path, *, draft_preview: bool = False) -> dict[str, Any]:
    """Contract gate first; never call the renderer if new-report QA fails."""
    qa = validate_0800_generation_contract(payload)
    if qa["status"] != "PASS":
        return {"status": "BLOCKED", "generation_qa": qa, "renderer_called": False, "png_written": False}
    from .infographic_0800_fixed import render_0800_fixed

    render_input = dict(payload)
    render_input["generation_qa_attestation"] = build_0800_generation_attestation(payload, qa)
    result = render_0800_fixed(render_input, output_path, draft_preview=draft_preview)
    required_gates = ("SOURCE_INTEGRITY", "NUMERIC_INTEGRITY", "SNAPSHOT_INTEGRITY",
                      "CONTENT_COMPLETENESS", "LAYOUT_INTEGRITY", "READABILITY_768")
    gates = result.get("validation_gates", {})
    gate_status = "PASS" if all(gates.get(name) == "PASS" for name in required_gates) else "FAIL"
    png_written = bool(result.get("output_path"))
    serializable_result = {key: value for key, value in result.items() if key != "image_bytes"}
    serializable_result["image_bytes_length"] = len(result.get("image_bytes") or b"")
    result_gates = {name: gates.get(name, "NOT_RUN") for name in (*PRODUCTION_GATES, "PRODUCTION_READY")}
    production = evaluate_0800_production_candidate(payload, result_gates,
                                                     image_sha256=result.get("image_sha256"))
    return {"status": "PASS" if gate_status == "PASS" and png_written else "BLOCKED",
            "generation_qa": qa, "renderer_called": True, "png_written": png_written,
            "generation_qa_attestation": render_input["generation_qa_attestation"],
            "required_validation_gates": {name: gates.get(name, "NOT_RUN") for name in required_gates},
            "production_candidate": production, "production_ready": production["status"],
            "render_result": serializable_result}
