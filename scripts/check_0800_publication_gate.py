"""Check changed report artifacts before any writer workflow commits them."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from reporting.infographic_0800_publication_gate import report_rows, validate_0800_publication_report, verify_changed_0800_reports  # noqa: E402


def _git(*args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=ROOT, text=True, encoding="utf-8").strip()


def _base_json(base: str, path: str):
    try:
        raw = _git("show", f"{base}:{path}")
    except subprocess.CalledProcessError:
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return None


def verify_repo_changes(base: str = "HEAD", *, require_latest: bool = False) -> dict:
    paths = _git("diff", "--name-only", base, "--", "reports", "reports.json", "data/latest-report.json", "data/dashboard.json").splitlines()
    for entry in _git("status", "--short", "--", "reports", "reports.json", "data/latest-report.json", "data/dashboard.json").splitlines():
        candidate = entry[3:].strip() if len(entry) > 3 else ""
        if candidate and candidate not in paths:
            paths.append(candidate)
    changed_reports: list[dict] = []
    errors: list[str] = []
    for path_text in paths:
        path = ROOT / path_text
        if not path.is_file() or path.suffix.lower() != ".json":
            continue
        try:
            current = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            errors.append(f"{path_text}: JSON_INVALID:{exc}")
            continue
        before = _base_json(base, path_text)
        if path_text == "reports.json":
            result = verify_changed_0800_reports(before, current)
            errors.extend(result["errors"])
            changed_reports.extend(row for row in report_rows(current) if row.get("time") == "08:00")
        elif path_text.startswith("reports/"):
            rows = report_rows(current)
            for report in rows:
                if report.get("time") != "08:00":
                    continue
                report_result = validate_0800_publication_report(report)
                errors.extend(f"{path_text}: {error}" for error in report_result["errors"])
                changed_reports.append(report)
        else:
            candidates = report_rows(current)
            for report in candidates:
                if report.get("time") == "08:00":
                    report_result = validate_0800_publication_report(report)
                    errors.extend(f"{path_text}: {error}" for error in report_result["errors"])
                    changed_reports.append(report)
    latest_checked = False
    if require_latest:
        latest_path = ROOT / "data" / "latest-report.json"
        if latest_path.is_file():
            latest = json.loads(latest_path.read_text(encoding="utf-8"))
            latest = latest.get("latestReport") or latest.get("report") or latest
            if isinstance(latest, dict) and latest.get("time") == "08:00":
                latest_checked = True
                result = validate_0800_publication_report(latest)
                errors.extend("data/latest-report.json: " + error for error in result["errors"])
    return {"status": "PASS" if not errors else "BLOCKED", "base": base,
            "changed_paths": paths, "changed_0800_rows_checked": len(changed_reports),
            "latest_0800_checked": latest_checked, "errors": errors}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", default="HEAD", help="Git ref before the pending write")
    parser.add_argument("--require-latest-0800", action="store_true",
                        help="also require QA when current data/latest-report.json is an 08:00 report")
    args = parser.parse_args(argv)
    result = verify_repo_changes(args.base, require_latest=args.require_latest_0800)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
