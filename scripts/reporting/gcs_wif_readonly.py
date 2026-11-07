"""Read-only, exact-generation WIF smoke probe for the TEST ONLY Evidence bucket.

This module intentionally exposes no write, list, delete, or CLI override path.
"""
from __future__ import annotations

import hashlib
import re

PROJECT_ID = "market-report-test-only"
BUCKET_NAME = "market-report-test-only-mr-pre-slot-test-evidence"
OBJECT_NAME = (
    "test-only/08-00/evidence/sched-3e911c4c66c0e0786624d3e795332f15/"
    "18ef24a161408ece702d826966775ca7c0a1d98a7fb918966a6d58c9b12f8f01.json"
)
GENERATION = 1793227650462378
EXPECTED_SHA256 = "92124cb17b36a407d3597487a09cca852b72d50de6c7b4f7cc98d6fb958aede9"
SERVICE_ACCOUNT_EMAIL = (
    "mr-pr188-evidence-test@market-report-test-only.iam.gserviceaccount.com"
)
READ_SCOPE = "https://www.googleapis.com/auth/devstorage.read_only"


def read_pinned_test_object(
    client, principal_email: str, *, expected_sha256: str = EXPECTED_SHA256
) -> dict:
    """Read only the configured test object version and verify its exact bytes."""
    if principal_email != SERVICE_ACCOUNT_EMAIL:
        raise PermissionError("WIF_TEST_PRINCIPAL_MISMATCH")
    if not OBJECT_NAME.startswith("test-only/"):
        raise ValueError("WIF_TEST_OBJECT_OUTSIDE_TEST_PREFIX")
    if type(GENERATION) is not int or GENERATION <= 0:
        raise ValueError("WIF_TEST_GENERATION_INVALID")
    if not re.fullmatch(r"[0-9a-f]{64}", expected_sha256):
        raise ValueError("WIF_TEST_EXPECTED_HASH_INVALID")

    blob = client.bucket(BUCKET_NAME).blob(OBJECT_NAME, generation=GENERATION)
    try:
        blob.reload()
        actual_generation = int(blob.generation)
        if actual_generation != GENERATION:
            raise ValueError("WIF_TEST_GENERATION_MISMATCH")
        payload = blob.download_as_bytes(if_generation_match=GENERATION)
    except ValueError:
        raise
    except Exception as exc:
        raise RuntimeError("WIF_TEST_READ_FAILED") from exc

    actual_hash = hashlib.sha256(payload).hexdigest()
    if actual_hash != expected_sha256:
        raise ValueError("WIF_TEST_SHA256_MISMATCH")
    return {
        "principal": principal_email,
        "bucket": BUCKET_NAME,
        "object": OBJECT_NAME,
        "generation": actual_generation,
        "sha256": actual_hash,
        "bytes": len(payload),
    }


def main() -> None:
    import google.auth
    from google.cloud import storage

    credentials, detected_project = google.auth.default(scopes=[READ_SCOPE])
    principal_email = getattr(credentials, "service_account_email", None)
    if principal_email != SERVICE_ACCOUNT_EMAIL:
        raise PermissionError("WIF_TEST_PRINCIPAL_MISMATCH")
    if detected_project and detected_project != PROJECT_ID:
        raise ValueError("WIF_TEST_PROJECT_MISMATCH")
    client = storage.Client(project=PROJECT_ID, credentials=credentials)
    result = read_pinned_test_object(client, principal_email)
    print(f"AUTHENTICATED_PRINCIPAL={result['principal']}")
    print(f"READBACK_GENERATION={result['generation']}")
    print(f"READBACK_SHA256={result['sha256']}")
    print(f"READBACK_BYTES={result['bytes']}")
    print("GCS_WRITE_OPERATIONS=NONE")


if __name__ == "__main__":
    main()
