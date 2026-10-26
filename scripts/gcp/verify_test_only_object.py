"""Independent generation-pinned readback for a TEST_ONLY GCS evidence object."""
from __future__ import annotations

import argparse
import hashlib
import sys

from google.cloud import storage


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--bucket", required=True)
    parser.add_argument("--object", required=True)
    parser.add_argument("--generation", required=True, type=int)
    parser.add_argument("--sha256", required=True)
    args = parser.parse_args()
    if args.generation <= 0 or len(args.sha256) != 64:
        parser.error("generation must be positive and sha256 must contain 64 hex characters")

    blob = storage.Client().bucket(args.bucket).blob(args.object, generation=args.generation)
    payload = blob.download_as_bytes(if_generation_match=args.generation)
    actual = hashlib.sha256(payload).hexdigest()
    if actual != args.sha256.lower():
        print("FAIL: pinned object bytes do not match expected SHA-256", file=sys.stderr)
        return 1
    print(f"PASS_EXACT_GENERATION_READBACK gs://{args.bucket}/{args.object}#{args.generation}")
    print(f"sha256={actual} bytes={len(payload)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
