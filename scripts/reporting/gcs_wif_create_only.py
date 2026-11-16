"""Create and read back one create-only WIF probe in the TEST ONLY bucket.

The object is intentionally retained: this identity has no delete permission.
"""
from __future__ import annotations

import hashlib
import json
import os
import re

PROJECT_ID = "market-report-test-only"
BUCKET_NAME = "market-report-test-only-mr-pre-slot-test-evidence"
OBJECT_PREFIX = "test-only/wif-connectivity/"
SERVICE_ACCOUNT_EMAIL = (
    "mr-pr188-evidence-test@market-report-test-only.iam.gserviceaccount.com"
)
WRITE_SCOPE = "https://www.googleapis.com/auth/devstorage.read_write"
EXPECTED_REF = "refs/heads/codex/0800-main-issuance-e2e-20261029"
EXPECTED_REPOSITORY = "matrixdiamond512-cell/Chat-GPT-Market-Report"


def _http_status(exc: Exception) -> int | None:
    code = getattr(exc, "code", None)
    if callable(code):
        code = code()
    if code is None:
        response = getattr(exc, "response", None)
        code = getattr(response, "status_code", None)
    try:
        return int(code) if code is not None else None
    except (TypeError, ValueError):
        return None


def create_and_readback_probe(
    client,
    principal_email: str,
    *,
    run_id: str,
    repository: str = EXPECTED_REPOSITORY,
    ref: str = EXPECTED_REF,
    commit_sha: str,
) -> dict:
    """Create one unique object with generation-match zero and verify exact bytes."""
    if principal_email != SERVICE_ACCOUNT_EMAIL:
        raise PermissionError("WIF_TEST_PRINCIPAL_MISMATCH")
    if repository != EXPECTED_REPOSITORY or ref != EXPECTED_REF:
        raise PermissionError("WIF_TEST_REPOSITORY_OR_REF_MISMATCH")
    if not re.fullmatch(r"[0-9]+", str(run_id)) or int(run_id) <= 0:
        raise ValueError("WIF_TEST_RUN_ID_INVALID")
    if not re.fullmatch(r"[0-9a-f]{40}", commit_sha):
        raise ValueError("WIF_TEST_COMMIT_SHA_INVALID")

    object_name = f"{OBJECT_PREFIX}{run_id}.json"
    payload = json.dumps(
        {
            "commit_sha": commit_sha,
            "purpose": "TEST_ONLY_WIF_CREATE_ONLY_PROBE",
            "ref": ref,
            "repository": repository,
            "run_id": str(run_id),
            "schema": "wif-create-only-probe/v1",
        },
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    expected_hash = hashlib.sha256(payload).hexdigest()
    blob = client.bucket(BUCKET_NAME).blob(object_name)
    created = True
    try:
        blob.upload_from_string(
            payload,
            content_type="application/json",
            if_generation_match=0,
        )
    except Exception as exc:
        if _http_status(exc) != 412:
            raise RuntimeError("WIF_TEST_CREATE_FAILED") from exc
        created = False

    try:
        blob.reload()
        generation = int(blob.generation)
        if generation <= 0:
            raise ValueError("WIF_TEST_GENERATION_INVALID")
        readback = blob.download_as_bytes(if_generation_match=generation)
    except ValueError:
        raise
    except Exception as exc:
        raise RuntimeError("WIF_TEST_READBACK_FAILED") from exc

    actual_hash = hashlib.sha256(readback).hexdigest()
    if readback != payload or actual_hash != expected_hash:
        reason = "WIF_TEST_EXISTING_OBJECT_CONFLICT" if not created else "WIF_TEST_READBACK_MISMATCH"
        raise ValueError(reason)
    return {
        "principal": principal_email,
        "bucket": BUCKET_NAME,
        "object": object_name,
        "created": created,
        "generation": generation,
        "sha256": actual_hash,
        "bytes": len(readback),
    }


def main() -> None:
    import google.auth
    from google.cloud import storage

    credentials, detected_project = google.auth.default(scopes=[WRITE_SCOPE])
    principal_email = getattr(credentials, "service_account_email", None)
    if principal_email != SERVICE_ACCOUNT_EMAIL:
        raise PermissionError("WIF_TEST_PRINCIPAL_MISMATCH")
    if detected_project and detected_project != PROJECT_ID:
        raise ValueError("WIF_TEST_PROJECT_MISMATCH")
    repository = os.environ.get("GITHUB_REPOSITORY", "")
    ref = os.environ.get("GITHUB_REF", "")
    if repository != EXPECTED_REPOSITORY or ref != EXPECTED_REF:
        raise PermissionError("WIF_TEST_REPOSITORY_OR_REF_MISMATCH")

    client = storage.Client(project=PROJECT_ID, credentials=credentials)
    result = create_and_readback_probe(
        client,
        principal_email,
        run_id=os.environ.get("GITHUB_RUN_ID", ""),
        repository=repository,
        ref=ref,
        commit_sha=os.environ.get("GITHUB_SHA", ""),
    )
    print(f"AUTHENTICATED_PRINCIPAL={result['principal']}")
    print(f"PROBE_OBJECT={result['object']}")
    print(f"CREATE_RESULT={'CREATED' if result['created'] else 'IDEMPOTENT_RETRY'}")
    print(f"READBACK_GENERATION={result['generation']}")
    print(f"READBACK_SHA256={result['sha256']}")
    print(f"READBACK_BYTES={result['bytes']}")
    print("DELETE_OPERATIONS=NONE")


if __name__ == "__main__":
    main()
