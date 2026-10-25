"""Cloud Run process factory for the isolated shadow ingress.

The WSGI entrypoint is lazy so importing the module does not discover
credentials, construct a Storage client, or perform network I/O.
"""
from __future__ import annotations

from datetime import datetime, timezone
from importlib import import_module
import json
import os
from typing import Callable, Mapping

from scripts.report_continuity_ingress import (
    SchedulerBinding, create_app, single_binding_map, verify_google_oidc,
)


def _configured_provider(spec: str) -> Callable:
    module_name, separator, attribute = spec.partition(":")
    if not separator or not module_name.startswith("scripts.") or not attribute:
        raise RuntimeError("P1_ACQUISITION_PROVIDER must be scripts.module:callable")
    provider = getattr(import_module(module_name), attribute, None)
    if not callable(provider):
        raise RuntimeError("P1_ACQUISITION_PROVIDER is not callable")
    return provider


def build_app(environ: Mapping[str, str] | None = None, *,
              storage_client_factory: Callable[[], object] | None = None,
              acquisition_provider: Callable | None = None,
              clock: Callable[[], datetime] | None = None,
              verifier=None):
    env = os.environ if environ is None else environ
    audience = env.get("P1_OIDC_AUDIENCE", "")
    bindings_json = env.get("P1_SCHEDULER_BINDINGS_JSON", "")
    try:
        bindings = single_binding_map(json.loads(bindings_json))
    except (ValueError, TypeError, json.JSONDecodeError) as exc:
        raise RuntimeError("P1_SCHEDULER_BINDINGS_JSON is invalid") from exc

    enabled = env.get("SHADOW_STORAGE_ENABLED", "false").lower() == "true"
    if not enabled:
        def processor(identity, trigger_body, binding):
            return {"status": "DISABLED", "publicationEligible": False,
                    "chatStatus": "UNKNOWN"}
    else:
        bucket_name = env.get("P1_GCS_BUCKET", "")
        if not bucket_name:
            raise RuntimeError("P1_GCS_BUCKET is required when storage is enabled")
        acquisition_provider = acquisition_provider or _configured_provider(
            env.get("P1_ACQUISITION_PROVIDER", ""))
        if storage_client_factory is None:
            from google.cloud.storage import Client
            storage_client_factory = Client
        from scripts.report_continuity_gcs import GcsShadowStorage
        from scripts.report_continuity_shadow import EvidenceWriter, JobCoordinator

        bucket = storage_client_factory().bucket(bucket_name)
        store = GcsShadowStorage(bucket, enabled=True)
        coordinator = JobCoordinator(
            EvidenceWriter(store, lambda: datetime.now(timezone.utc)), enabled=True)

        def processor(identity, trigger_body, binding: SchedulerBinding):
            # The fixed Scheduler body is a trigger only. The injected provider
            # performs a fresh, identity-bound source read for this attempt.
            data = acquisition_provider(identity, binding, trigger_body)
            if not isinstance(data, bytes) or not data or len(data) > 1024 * 1024:
                raise ValueError("INVALID_ACQUISITION_PAYLOAD")
            return coordinator.run(identity, data, attempt_minutes=binding.attempt_minutes)

    return create_app(bindings=bindings, audience=audience, processor=processor,
                      clock=clock, verifier=verifier or verify_google_oidc)


_cached_app = None


def application(environ, start_response):
    global _cached_app
    if _cached_app is None:
        _cached_app = build_app()
    return _cached_app(environ, start_response)


app = application
