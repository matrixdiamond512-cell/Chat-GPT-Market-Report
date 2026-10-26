"""GCS SDK adapter for isolated P1 shadow evidence.

Construct only with an explicitly selected nonproduction bucket client. Importing
this module does not import the SDK, obtain credentials, or perform network I/O.
No bucket creation, deployment or public-report writer is provided.
"""
from datetime import datetime
import re
from typing import Any

from scripts.report_continuity_shadow import StoredObject

_KEY = re.compile(
    r"shadow/\d{4}-\d{2}-\d{2}_\d{2}-\d{2}/"
    r"(?:evidence|stages/evidence-readback/[0-9a-f]{64}|"
    r"attempts/t-(?:3|7|13)/(?:evidence|stages/evidence-readback/[0-9a-f]{64}))\Z"
)


class GcsShadowStorage:
    def __init__(self, bucket: Any, *, enabled: bool = False):
        self.bucket = bucket
        self.enabled = enabled

    def _check(self, key: str) -> None:
        if not self.enabled:
            raise RuntimeError("SHADOW_STORAGE_DISABLED")
        if not _KEY.fullmatch(key):
            raise ValueError("INVALID_SHADOW_OBJECT_KEY")

    @staticmethod
    def _stored(blob: Any, data: bytes) -> StoredObject:
        generation = int(blob.generation)
        created = blob.time_created
        if generation <= 0 or not isinstance(created, datetime) or created.tzinfo is None:
            raise ValueError("INVALID_STORAGE_SERVER_METADATA")
        return StoredObject(bytes(data), generation, created)

    def create(self, key: str, data: bytes) -> StoredObject:
        self._check(key)
        if len(data) > 1024 * 1024:
            raise ValueError("SHADOW_PAYLOAD_TOO_LARGE")
        blob = self.bucket.blob(key)
        try:
            blob.upload_from_string(bytes(data), content_type="application/octet-stream",
                                    if_generation_match=0, timeout=10, retry=None, checksum=None)
        except Exception as exc:
            code = getattr(exc, "code", None)
            if callable(code):
                code = code()
            if code == 412:
                raise FileExistsError(key) from exc
            raise
        return self._stored(blob, data)

    def read(self, key: str) -> StoredObject:
        self._check(key)
        metadata = self.bucket.get_blob(key, timeout=10, retry=None)
        if metadata is None:
            raise FileNotFoundError(key)
        generation = int(metadata.generation)
        if generation <= 0:
            raise ValueError("INVALID_STORAGE_SERVER_METADATA")
        pinned = self.bucket.blob(key, generation=generation)
        data = pinned.download_as_bytes(if_generation_match=generation, timeout=10, retry=None)
        return self._stored(metadata, data)
