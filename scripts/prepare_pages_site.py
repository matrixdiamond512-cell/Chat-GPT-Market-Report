#!/usr/bin/env python3
"""Build Pages from an explicit allowlist, never from a repository copy."""
from __future__ import annotations
import argparse
import json
import shutil
from pathlib import Path, PurePosixPath
from reporting.publication_eligibility import is_publication_eligible

DEFAULT_POLICY = Path(__file__).resolve().parents[1] / "config/pages_public_files.json"

def checked_file(source, relative):
    name = PurePosixPath(relative)
    if name.is_absolute() or ".." in name.parts or "\\" in relative or ":" in relative:
        raise ValueError(f"unsafe public path: {relative}")
    path = source.joinpath(*name.parts)
    if not path.is_file() or path.is_symlink() or source not in path.resolve().parents:
        raise ValueError(f"missing or unsafe public file: {relative}")
    # Reject directory symlinks too, including ones resolving inside the repo.
    for parent in path.parents:
        if parent == source:
            break
        if parent.is_symlink():
            raise ValueError(f"symlink public path: {relative}")
    return path

def prepare_pages_site(source_root: Path, output_root: Path, policy_path: Path | None = None) -> list[str]:
    source, output = source_root.resolve(), output_root.resolve()
    if source == output or source in output.parents or output in source.parents:
        raise ValueError("Pages staging directory must be outside the repository")
    if output.exists():
        raise FileExistsError(f"Pages staging directory already exists: {output}")
    policy = json.loads((policy_path or source / "config/pages_public_files.json").read_text(encoding="utf-8"))
    if policy.get("schemaVersion") != 1:
        raise ValueError("unsupported Pages allowlist")
    allowed = set(policy["files"])
    for pattern in policy.get("collections", []):
        if not pattern.startswith("data/") or ".." in PurePosixPath(pattern).parts:
            raise ValueError("unsafe public collection")
        allowed.update(p.relative_to(source).as_posix() for p in source.glob(pattern) if p.is_file())
    archive = policy.get("archiveManifest")
    if archive:
        payload = json.loads(checked_file(source, archive).read_text(encoding="utf-8"))
        allowed.add(archive)
        for item in payload.get("files", []):
            name = item["path"]
            if not name.startswith("data/dashboard-drive-archive-") or not name.endswith(".json"):
                raise ValueError("archive manifest references a non-archive file")
            checked_file(source, name)
            allowed.add(name)
    excluded = []
    # The allowlist cannot override canonical publication eligibility.
    allowed = {p for p in allowed if not p.startswith("reports/")}
    for path in sorted((source / "reports").glob("*.json")):
        if path.name.startswith("_"):
            excluded.append(path.name)
            continue
        checked_file(source, path.relative_to(source).as_posix())
        report = json.loads(path.read_text(encoding="utf-8"))
        report = report.get("latestReport", report)
        if is_publication_eligible(report):
            allowed.add(path.relative_to(source).as_posix())
        else:
            excluded.append(path.name)
    # Validate all sources before writing any part of the artifact.
    files = [(name, checked_file(source, name)) for name in sorted(allowed)]
    output.mkdir(parents=True)
    for name, path in files:
        target = output / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, target)
    return excluded

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    excluded = prepare_pages_site(Path(__file__).resolve().parents[1], args.output)
    print(json.dumps({"status": "STAGED", "excludedCanonicalReports": excluded}, ensure_ascii=False))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
