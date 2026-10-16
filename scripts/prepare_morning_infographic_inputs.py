"""Build source-bound 08:00 summary, view and spec review inputs.

This compiler does not invent report content. A human/assisted authoring file
supplies concise claims and panel references; anchors, offsets and snapshot
identity are resolved from the immutable report transaction. Human scenario
review remains a separate gate and no image or publication is produced here.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from bind_morning_report_evidence import assemble
from persist_report_slot_evidence import validate_stored_slot_evidence
from reporting.infographic import ValidationFailure, _headings, build_spec, validate_spec
from reporting.infographic_summary import build_summary, validate_summary
from reporting.morning_layout import validate_projection
from reporting.publication_evidence import validate_receipt
from reporting.report import canonical_heading
from run_morning_infographic_staging import validate_original_body_evidence


def _clean_heading(line: str) -> str:
    import re
    text = re.sub(r"^\s*#{1,6}\s*", "", line).strip(" \r\n【】")
    return re.sub(r"^\d{1,2}[．.、)]\s*", "", text)


def _section_matches(active: str | None, requested: str | None) -> bool:
    """Match scenario role headings to their shared canonical source heading."""
    if active == requested:
        return True
    scenario_sections = {"メインシナリオ", "代替シナリオ", "シナリオが崩れる条件"}
    return active == "シナリオ" and requested in scenario_sections


def build_view(report: dict, authoring: dict) -> dict:
    """Resolve exact source anchors in a panel skeleton into offset-bound facts."""
    body = report["fullText"]
    known_sections = _headings(body)
    lines = []
    active_section = None
    offset = 0
    for raw in body.splitlines(keepends=True):
        line = raw.rstrip("\r\n")
        heading = canonical_heading(line) or _clean_heading(line)
        if heading and heading in known_sections:
            active_section = heading
        elif line.strip():
            lines.append((offset, offset + len(line), active_section, line))
        offset += len(raw)

    facts = []
    seen = set()
    for source in authoring.get("facts", []):
        fact_id = source.get("id")
        anchor = source.get("source_anchor")
        section = source.get("source_section")
        if not fact_id or fact_id in seen or not isinstance(anchor, str) or not anchor.strip():
            raise ValidationFailure("MORNING_VIEW_AUTHORING_FACT_INVALID", fact_id)
        seen.add(fact_id)
        matches = []
        for start, _end, active, line in lines:
            if not _section_matches(active, section):
                continue
            cursor = 0
            while True:
                index = line.find(anchor, cursor)
                if index < 0:
                    break
                matches.append((start + index, start + index + len(anchor)))
                cursor = index + 1
        occurrence = source.get("source_anchor_occurrence")
        if len(matches) != 1:
            if (isinstance(occurrence, int) and not isinstance(occurrence, bool)
                    and 0 <= occurrence < len(matches)):
                matches = [matches[occurrence]]
            else:
                raise ValidationFailure("MORNING_VIEW_SOURCE_ANCHOR_NOT_UNIQUE", {
                    "fact": fact_id, "section": section, "matches": len(matches)})
        elif occurrence not in (None, 0):
            raise ValidationFailure("MORNING_VIEW_SOURCE_ANCHOR_NOT_UNIQUE", {
                "fact": fact_id, "section": section, "matches": len(matches),
                "occurrence": occurrence})
        start, end = matches[0]
        fact = {"id": fact_id, "text": body[start:end], "source_section": section,
                "start": start, "end": end}
        if source.get("snapshot_field") is not None:
            fact["snapshot_field"] = source["snapshot_field"]
        facts.append(fact)

    view = {key: value for key, value in authoring.items()
            if key not in {"known_sections", "facts", "schema_version"}}
    view.update({"report_id": report["report_id"], "time": report["time"],
                 "revision": report["revision"], "snapshot_id": report["snapshot_id"],
                 "body_hash": report["bodyHash"], "synthetic_fixture": False,
                 "facts": facts})
    return view


def prepare_inputs(*, report: dict, evidence_bytes: bytes, receipt: dict,
                   original_body_evidence: dict, summary_authoring: dict,
                   view_authoring: dict) -> tuple[dict, dict, dict, dict]:
    evidence = validate_stored_slot_evidence(evidence_bytes, report["date"], "08:00")
    validate_receipt(receipt, report)
    validate_original_body_evidence(original_body_evidence, report, evidence, receipt)
    if receipt.get("bodyHash") != original_body_evidence.get("bodyHash"):
        raise ValidationFailure("MORNING_INPUT_DOCS_HASH_DIFFERS_FROM_PRE_SAVE_BODY")
    captured_at = original_body_evidence.get("capturedAt")
    saved_at = receipt.get("savedAt")
    bound = assemble(report, evidence["context"], evidence["snapshot"])
    spec = build_spec(bound)
    validate_spec(bound, spec)
    view = build_view(bound, view_authoring)
    summary = build_summary(bound, summary_authoring)
    validate_summary(bound, summary)
    validate_projection(bound, view, fixture=False, spec=spec)
    return bound, summary, view, spec


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("report", "evidence", "receipt", "original-body-evidence",
                 "summary-authoring", "view-authoring", "output"):
        parser.add_argument("--" + name, type=Path, required=True)
    args = parser.parse_args()
    try:
        output = args.output.resolve()
        if output.exists():
            raise ValidationFailure("MORNING_INPUT_OUTPUT_EXISTS")
        report = json.loads(args.report.read_text(encoding="utf-8-sig"))
        receipt = json.loads(args.receipt.read_text(encoding="utf-8-sig"))
        original = json.loads(args.original_body_evidence.read_text(encoding="utf-8-sig"))
        summary_authoring = json.loads(args.summary_authoring.read_text(encoding="utf-8-sig"))
        view_authoring = json.loads(args.view_authoring.read_text(encoding="utf-8-sig"))
        _bound, summary, view, spec = prepare_inputs(
            report=report, evidence_bytes=args.evidence.read_bytes(), receipt=receipt,
            original_body_evidence=original, summary_authoring=summary_authoring,
            view_authoring=view_authoring)
        output.mkdir(parents=True)
        artifacts = {"summary.json": summary, "view.json": view, "spec.json": spec}
        for filename, payload in artifacts.items():
            (output / filename).write_text(
                json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        manifest = {
            "status": "READY_FOR_HUMAN_SCENARIO_REVIEW",
            "report_id": _bound["report_id"], "revision": _bound["revision"],
            "bodyHash": _bound["bodyHash"], "snapshot_id": _bound["snapshot_id"],
            "summary_sha256": hashlib.sha256(
                json.dumps(summary, ensure_ascii=False, sort_keys=True,
                           separators=(",", ":"), allow_nan=False).encode("utf-8")).hexdigest(),
            "scenario_review": "PENDING", "publish_allowed": False,
            "original_body_captured_at": captured_at,
            "docs_saved_at": saved_at,
            "source_offsets": "UNICODE_CODEPOINTS",
        }
        (output / "input-manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(manifest, ensure_ascii=False))
        return 0
    except (ValidationFailure, ValueError, KeyError, TypeError, OSError,
            json.JSONDecodeError) as exc:
        print(json.dumps({"status": "BLOCKED",
                          "reason": getattr(exc, "reason", str(exc))}, ensure_ascii=False))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
