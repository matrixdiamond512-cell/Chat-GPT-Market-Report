#!/usr/bin/env python3
"""Resolve a concurrent rebase for the shared stock aggregate.

The dedicated component JSON is authoritative for the collector that just
ran.  The aggregate is merged recursively so independent component updates
from another workflow are kept; when both writers changed the same scalar or
list, the already-published upstream value wins rather than overwriting a
newer observation with an older checkout.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any


def stage_json(stage: int, path: str) -> Any:
    result = subprocess.run(
        ["git", "show", f":{stage}:{path}"],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    if result.returncode:
        return None
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError:
        return None


def merge(base: Any, upstream: Any, incoming: Any) -> Any:
    if upstream == base:
        return incoming
    if incoming == base or upstream == incoming:
        return upstream
    if isinstance(base, dict) and isinstance(upstream, dict) and isinstance(incoming, dict):
        return {
            key: merge(base.get(key), upstream.get(key), incoming.get(key))
            for key in sorted(set(base) | set(upstream) | set(incoming))
        }
    # Lists and scalar collisions represent the same logical field.  Keep the
    # upstream value because it is already on public main and may be newer.
    return upstream


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: merge_stock_json_rebase.py <path>", file=sys.stderr)
        return 2
    path = sys.argv[1]
    base = stage_json(1, path)
    upstream = stage_json(2, path)
    incoming = stage_json(3, path)
    if not isinstance(upstream, (dict, list)) or not isinstance(incoming, (dict, list)):
        print(f"cannot resolve JSON stages for {path}", file=sys.stderr)
        return 1
    result = merge(base, upstream, incoming)
    Path(path).write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
