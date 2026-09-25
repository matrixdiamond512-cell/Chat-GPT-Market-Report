#!/usr/bin/env python3
"""Wait for GitHub Pages and verify its report index, canonical files and images."""
from __future__ import annotations

import argparse
import hashlib
import json
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin, urlsplit, urlunsplit, parse_qsl, urlencode
from urllib.request import Request, urlopen


def fetch(url: str) -> tuple[int, bytes, str]:
    request = Request(url, headers={"Cache-Control": "no-cache", "Pragma": "no-cache", "User-Agent": "market-report-publication-check"})
    try:
        with urlopen(request, timeout=15) as response:
            return response.status, response.read(), response.headers.get("Content-Type", "")
    except HTTPError as exc:
        return exc.code, exc.read(), exc.headers.get("Content-Type", "")


def cache_busted(url: str) -> str:
    parts = urlsplit(url)
    query = dict(parse_qsl(parts.query, keep_blank_values=True))
    query["verify"] = str(time.time_ns())
    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query), parts.fragment))


def key(report: dict) -> tuple[str, str]:
    return str(report.get("date") or ""), str(report.get("time") or "")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--index", default="reports.json")
    parser.add_argument("--reports-dir", default="reports")
    parser.add_argument("--timeout-seconds", type=int, default=180)
    args = parser.parse_args()
    base = args.base_url.rstrip("/") + "/"
    expected = json.loads(Path(args.index).read_text(encoding="utf-8"))
    if not isinstance(expected, list) or not expected:
        raise SystemExit("local reports.json is empty or invalid")

    deadline = time.monotonic() + args.timeout_seconds
    latest_error = "public reports.json did not match this deployment"
    while time.monotonic() < deadline:
        try:
            status, body, _ = fetch(cache_busted(urljoin(base, "reports.json")))
            if status == 200:
                actual = json.loads(body.decode("utf-8"))
                if actual == expected:
                    break
                latest_error = f"public index is still stale: HTTP 200, {len(actual) if isinstance(actual, list) else 'invalid'} records"
            else:
                latest_error = f"public reports.json returned HTTP {status}"
        except (OSError, UnicodeError, json.JSONDecodeError, URLError) as exc:
            latest_error = str(exc)
        time.sleep(5)
    else:
        raise SystemExit(f"Pages index verification timed out: {latest_error}")

    for report in expected:
        date, slot = key(report)
        slot_id = f"{date}_{slot.replace(':', '-') }"
        local_path = Path(args.reports_dir) / f"{slot_id}.json"
        canonical = json.loads(local_path.read_text(encoding="utf-8"))
        if not canonical.get("date"):
            canonical = canonical.get("latestReport") or canonical.get("report")
        if canonical != report:
            raise SystemExit(f"local canonical report mismatch: {local_path}")
        if report.get("infographic"):
            image = report["infographic"]
            if image.get("slotKey") != slot_id or image.get("src") != f"images/reports/{slot_id}.png":
                raise SystemExit(f"image is linked to a different slot: {slot_id}")
            status, data, content_type = fetch(cache_busted(urljoin(base, image["src"])))
            digest = hashlib.sha256(data).hexdigest()
            if status != 200 or not content_type.lower().startswith("image/png") or digest != image.get("sha256"):
                raise SystemExit(f"public infographic does not match its source file: {slot_id} HTTP {status}")

    newest = expected[0]
    print(json.dumps({
        "status": "verified",
        "baseUrl": base,
        "reportCount": len(expected),
        "latestReport": f"{newest['date']} {newest['time']}",
        "verifiedInfographics": sum(bool(item.get("infographic")) for item in expected),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
