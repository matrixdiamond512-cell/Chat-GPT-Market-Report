"""Check that allowlist staging does not remove existing local UI dependencies."""
from __future__ import annotations
import argparse
from html.parser import HTMLParser
import json
from pathlib import Path
import re
from urllib.parse import unquote, urlsplit

class References(HTMLParser):
    def __init__(self):
        super().__init__(); self.paths = []
    def handle_starttag(self, tag, attrs):
        self.paths.extend(value for key, value in attrs if key in {"src", "href", "poster"} and value)

def verify(source: Path, site: Path):
    missing, baseline_missing = [], []
    checked = 0
    for path in site.rglob("*"):
        if path.suffix not in {".html", ".css", ".js"}:
            continue
        text = path.read_text(encoding="utf-8-sig")
        refs = []
        if path.suffix == ".html":
            parser = References(); parser.feed(text); refs.extend(parser.paths)
        if path.suffix == ".css":
            refs.extend(re.findall(r"url\(\s*[\"']?([^\"')\s]+)", text))
        # Existing literal data/image references used by the frontend, including
        # template URLs with a cache query. Dynamic folder URLs are checked via
        # their manifests and local browser smoke validation separately.
        if path.suffix == ".js":
            refs.extend(re.findall(r"[\"'`](data/[A-Za-z0-9_./-]+\.(?:json|csv)|images/[A-Za-z0-9_./-]+\.(?:png|svg|webp))(?=[?\"'`])", text))
        for value in refs:
            if "${" in value:
                continue
            parsed = urlsplit(value)
            if parsed.scheme or parsed.netloc or not parsed.path:
                continue
            relative = unquote(parsed.path)
            origin = source / path.relative_to(site).parent / relative
            target = site / path.relative_to(site).parent / relative
            if path.suffix == ".js" or relative.startswith("/"):
                origin, target = source / relative.lstrip("/"), site / relative.lstrip("/")
            if target.exists():
                checked += 1
            else:
                record = {"file": path.relative_to(site).as_posix(), "reference": value}
                (missing if origin.exists() else baseline_missing).append(record)
    return {"status": "PASS" if not missing else "FAIL", "checkedReferences": checked,
            "newlyMissing": missing, "alreadyMissingInSource": baseline_missing}

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--site", type=Path, required=True)
    args = parser.parse_args()
    result = verify(args.source.resolve(), args.site.resolve())
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["status"] == "PASS" else 1

if __name__ == "__main__":
    raise SystemExit(main())
