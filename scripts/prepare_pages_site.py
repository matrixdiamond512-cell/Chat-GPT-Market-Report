#!/usr/bin/env python3
"""Stage a Pages artifact without serving source-only canonical reports."""
from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

from reporting.publication_eligibility import is_publication_eligible


def prepare_pages_site(source_root: Path, output_root: Path) -> list[str]:
    source = source_root.resolve()
    output = output_root.resolve()
    if source == output or source in output.parents:
        raise ValueError("Pages staging directory must be outside the repository")
    if output.exists():
        raise FileExistsError(f"Pages staging directory already exists: {output}")

    def ignore(directory: str, names: list[str]) -> set[str]:
        ignored = {".git", "node_modules", "__pycache__", ".pytest_cache"}
        return {name for name in names if name in ignored or name.startswith(".codex-temp-")}

    shutil.copytree(source, output, ignore=ignore)
    excluded: list[str] = []
    reports_dir = output / "reports"
    for path in sorted(reports_dir.glob("*.json")):
        report = json.loads(path.read_text(encoding="utf-8"))
        if not is_publication_eligible(report):
            excluded.append(path.name)
            path.unlink()
    return excluded


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    excluded = prepare_pages_site(Path(__file__).resolve().parents[1], args.output)
    print(json.dumps({"status": "PASS", "excludedCanonicalReports": excluded}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
