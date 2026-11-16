#!/usr/bin/env python3
"""Create-only TEST_ONLY acquisition evidence in GCS."""
from __future__ import annotations
import hashlib
import sys
from pathlib import Path

from google.cloud import storage


def main() -> int:
    if len(sys.argv) != 4:
        raise SystemExit("usage: write_test_only_close_evidence.py FILE BUCKET OBJECT_KEY")
    path, bucket_name, object_key = Path(sys.argv[1]), sys.argv[2], sys.argv[3]
    if not bucket_name.startswith("market-report-test-only-"):
        raise SystemExit("refusing to write outside the TEST_ONLY evidence bucket")
    if not path.is_file():
        raise SystemExit("evidence file missing")
    blob = storage.Client().bucket(bucket_name).blob(f"close-acquisition/{object_key}.json")
    blob.upload_from_filename(str(path), if_generation_match=0, content_type="application/json")
    generation = int(blob.generation)
    expected = path.read_bytes()
    readback = storage.Client().bucket(bucket_name).blob(blob.name, generation=generation).download_as_bytes(
        if_generation_match=generation
    )
    if readback != expected:
        raise SystemExit("TEST_ONLY evidence generation readback mismatch")
    digest = hashlib.sha256(readback).hexdigest()
    print(f"created-and-readback-verified gs://{bucket_name}/{blob.name} generation={generation} sha256={digest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
