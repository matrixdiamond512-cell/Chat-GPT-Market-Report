"""Run strict new-report 08:00 content QA before the fixed renderer."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from reporting.infographic_0800_generation_contract import (  # noqa: E402
    ROOT as REPO_ROOT, generate_0800_with_contract, validate_0800_generation_contract,
    write_0800_qa_evidence,
)


def _under_artifacts(path: Path) -> bool:
    resolved = path.resolve()
    root = (REPO_ROOT / "artifacts").resolve()
    return resolved == root or root in resolved.parents


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True, type=Path, help="08:00 body plus structured facts and numeric registry")
    parser.add_argument("--qa-output", type=Path, help="write machine-readable QA result")
    parser.add_argument("--render-to", type=Path, help="optional new PNG path; renderer runs only after QA PASS")
    parser.add_argument("--evidence-dir", type=Path, default=REPO_ROOT / "artifacts" / "0800_qa_records",
                        help="nonproduction QA record root; must remain inside repository artifacts/")
    parser.add_argument("--draft-preview", action="store_true", help="render a clearly nonproduction preview")
    args = parser.parse_args(argv)
    if args.qa_output and not _under_artifacts(args.qa_output):
        parser.error("--qa-output must stay under repository artifacts/")
    if args.render_to and not _under_artifacts(args.render_to):
        parser.error("--render-to must stay under repository artifacts/")
    if not _under_artifacts(args.evidence_dir):
        parser.error("--evidence-dir must stay under repository artifacts/")
    payload = json.loads(args.source.read_text(encoding="utf-8-sig"))
    if args.render_to:
        result = generate_0800_with_contract(payload, args.render_to, draft_preview=args.draft_preview)
    else:
        qa = validate_0800_generation_contract(payload)
        result = {"status": "PASS" if qa["status"] == "PASS" else "BLOCKED",
                  "generation_qa": qa, "renderer_called": False, "png_written": False}
    serialized = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    try:
        evidence_path = write_0800_qa_evidence(payload, result, args.evidence_dir)
        result["qa_evidence_path"] = str(evidence_path)
        serialized = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    except (OSError, ValueError) as error:
        result["status"] = "BLOCKED"
        result["qa_evidence_error"] = str(error)
        serialized = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.qa_output:
        args.qa_output.parent.mkdir(parents=True, exist_ok=True)
        args.qa_output.write_text(serialized, encoding="utf-8")
    print(serialized, end="")
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
