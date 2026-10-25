"""Cloud Run process factory for the isolated shadow ingress.

The WSGI entrypoint is lazy so importing the module in CI or local tooling does
not discover credentials, construct a Storage client, or perform network I/O.
"""
from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from typing import Callable, Mapping

from scripts.report_continuity_ingress import create_app, single_binding_map


def build_app(environ: Mapping[str, str] | None = None, *,
              storage_client_factory: Callable[[], object] | None = None,
              clock: Callable[[], datetime] | None = None):
    env = os.environ if environ is None else environ
    audience = env.get("P1_OIDC_AUDIENCE", "")
    bindings_json = env.get("P1_SCHEDULER_BINDINGS_JSON", "")
    try:
        bindings = single_binding_map(json.loads(bindings_json))
    except (ValueError, TypeError, json.JSONDecodeError) as exc:
        raise RuntimeError("P1_SCHEDULER_BINDINGS_JSON is invalid") from exc

    enabled = env.get("SHADOW_STORAGE_ENABLED", "false").lower() == "true"
    if not enabled:
        def processor(identity, body):
            return {"status": "DISABLED", "publicationEligible": False,
                    "chatStatus": "UNKNOWN"}
    else:
        bucket_name = env.get("P1_GCS_BUCKET", "")
        if not bucket_name:
            raise RuntimeError("P1_GCS_BUCKET is required when storage is enabled")
        if storage_client_factory is None:
            from google.cloud.storage import Client
            storage_client_factory = Client
        from scripts.report_continuity_gcs import GcsShadowStorage
        from scripts.report_continuity_shadow import EvidenceWriter, JobCoordinator

        bucket = storage_client_factory().bucket(bucket_name)
        store = GcsShadowStorage(bucket, enabled=True)
        coordinator = JobCoordinator(
            EvidenceWriter(store, lambda: datetime.now(timezone.utc)), enabled=True)
        processor = lambda identity, body: coordinator.run(identity, body)

    return create_app(bindings=bindings, audience=audience, processor=processor, clock=clock)


_cached_app = None


def application(environ, start_response):
    global _cached_app
    if _cached_app is None:
        _cached_app = build_app()
    return _cached_app(environ, start_response)


app = application
