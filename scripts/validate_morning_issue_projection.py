"""Read-only bridge: G2 issuance artifact + independently authored view + canonical spec.

This is not a view generator; facts and original-text spans cannot be invented.
No PNG, Google Drive, or publication writes.
"""
import argparse
import json
from pathlib import Path
from reporting.infographic import ValidationFailure
from reporting.morning_layout import validate_projection
from preflight_morning_infographic import check as preflight_check

def validate_issuance_projection(report, view, spec):
    if report.get("evidence_stage") != "G2_DRAFT_NOT_SAVED" or report.get("validated_gates") != ["G0", "G1", "G2"]:
        raise ValidationFailure("G2_ISSUANCE_EVIDENCE_REQUIRED")
    if report.get("synthetic_fixture") or view.get("synthetic_fixture"):
        raise ValidationFailure("SYNTHETIC_PROJECTION_NOT_FORMAL")
    result = preflight_check(report, view)
    if result["status"] != "READY_FOR_CANONICAL_VALIDATION":
        raise ValidationFailure("ISSUANCE_PREFLIGHT_BLOCKED", result["missing_or_unverified"])
    if not isinstance(spec, dict):
        raise ValidationFailure("CANONICAL_SPEC_REQUIRED")
    # Authoritative original-text offsets, market numbers, and spec are all checked here.
    return validate_projection(report, view, fixture=False, spec=spec)

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--report", type=Path, required=True)
    p.add_argument("--view", type=Path, required=True)
    p.add_argument("--spec", type=Path, required=True)
    args = p.parse_args()
    try:
        def load(path):
            return json.loads(path.read_text(encoding="utf-8-sig"))
        report, view, spec = load(args.report), load(args.view), load(args.spec)
        result = validate_issuance_projection(report, view, spec)
        print(json.dumps({"status": "READY_FOR_RENDER_NOT_PUBLISHED",
                          "report_id": report["report_id"],
                          "snapshot_id": report["snapshot_id"],
                          "validation": result}, ensure_ascii=False, default=str))
        return 0
    except (ValidationFailure, OSError, ValueError, KeyError, TypeError) as exc:
        print(json.dumps({"status": "BLOCKED",
                          "reason": getattr(exc, "reason", str(exc))}, ensure_ascii=False))
        return 1

if __name__ == "__main__":
    raise SystemExit(main())
