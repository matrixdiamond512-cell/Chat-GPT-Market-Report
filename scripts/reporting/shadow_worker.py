"""D1 offline shadow worker contract.

NO OpenAI API client, network request, Google/Sheets/GitHub publisher, scheduler,
filesystem write, secret or production-producer proof. The responder is a
caller-supplied test double. This module cannot publish any report.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import hashlib
import json
from pathlib import Path
from threading import Lock
import re
from typing import Callable
from uuid import uuid4

from .context import ReportContext, aware
from .snapshot import MarketDataSnapshot, digest, plain
from .report import REGISTRY as HEADING_REGISTRY, parse_sections

SCHEMA = "market-report-shadow/v1"
LANE = "api-shadow"
ELIGIBILITY = "SHADOW_NOT_ELIGIBLE"
REQUIRED_SIX = ("gold", "wti", "nikkei225_futures_ose", "usdjpy", "eurusd", "btcusd")
REGISTRY = json.loads(
    (Path(__file__).resolve().parents[2] / "config/market_data_sources.json").read_text(encoding="utf-8")
)["symbols"]


class ShadowBlocked(ValueError):
    """The worker must stop without contacting any provider or publisher."""


def sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def json_bytes(value) -> bytes:
    return json.dumps(
        value, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")


def freeze_shadow_input(context: ReportContext, snapshot: MarketDataSnapshot):
    """Validate the already acquired snapshot. Never fetch/recover missing data."""
    snapshot.validate_context(context)
    MarketDataSnapshot.restore(snapshot.to_dict())  # immutable digest check
    slot = aware(f"{context.report_date}T{context.report_time}:00+09:00")
    cutoff = aware(context.data_cutoff)
    if cutoff > slot or aware(snapshot.captured_at) > slot:
        raise ShadowBlocked("SNAPSHOT_AFTER_SLOT")
    by_name = {market.instrument: market for market in snapshot.markets}
    if not set(REQUIRED_SIX).issubset(by_name):
        raise ShadowBlocked("REQUIRED_MARKET_MISSING")
    for market in snapshot.markets:
        cfg = REGISTRY.get(market.instrument)
        if cfg is None or cfg["marketType"] != market.marketType or cfg["unit"] != market.priceUnit:
            raise ShadowBlocked("MARKET_TYPE_OR_UNIT_UNVERIFIED")
        if market.status != "VALID":
            raise ShadowBlocked("MARKET_UNVERIFIED_OR_STALE")
        if market.priceValue is None or market.asOf is None or aware(market.asOf) > cutoff:
            raise ShadowBlocked("OBSERVATION_AFTER_CUTOFF_OR_MISSING")
        # A matching source ID alone is insufficient: the URL must be one of
        # the independently configured endpoints for the same market type.
        allowed = set()
        for src in cfg["sources"]:
            if src.get("referenceOnly") or src.get("marketType") != market.marketType:
                continue
            for address in (src.get("url"), src.get("sourceUrl")):
                if isinstance(address, str) and address.startswith("https://"):
                    allowed.add((src["id"], address))
        if not market.source or not all(
            (src.get("id"), src.get("url")) in allowed
            for src in market.source
        ):
            raise ShadowBlocked("OBSERVATION_SOURCE_UNVERIFIED")
    return context.to_dict(), snapshot.to_dict()


@dataclass(frozen=True)
class ShadowResult:
    """A separate receipt. The immutable stored payload is never revised."""
    status: str
    reason: str
    attempt_id: str
    shadow_run_id: str
    report_id: str
    states: tuple[str, ...]
    object_id: str | None
    record_sha256: str | None
    record: dict

    @property
    def publishable(self) -> bool:
        return False


class MemoryEvidenceStore:
    """D1 fixture-only private store and in-memory atomic slot registry."""
    def __init__(self):
        self._objects: dict[str, bytes] = {}
        self._run_owner: dict[tuple, str] = {}
        self._attempts: set[tuple] = set()
        self._body_hashes: dict[tuple, str] = {}
        self._conflicted: set[tuple] = set()
        self._unknown: set[tuple] = set()
        self._lock = Lock()

    def claim_attempt(self, key: tuple, run_id: str, attempt_id: str) -> None:
        with self._lock:
            if key in self._unknown:
                raise ShadowBlocked("UNKNOWN_PROVIDER_RESULT_REQUIRES_RECONCILIATION")
            if key in self._run_owner and self._run_owner[key] != run_id:
                raise ShadowBlocked("DUPLICATE_SLOT")
            unique = key + (attempt_id,)
            if unique in self._attempts:
                raise ShadowBlocked("DUPLICATE_ATTEMPT")
            self._run_owner.setdefault(key, run_id)
            self._attempts.add(unique)

    def mark_unknown(self, key: tuple) -> None:
        with self._lock:
            self._unknown.add(key)

    def track_body(self, key: tuple, body_hash: str) -> bool:
        with self._lock:
            old = self._body_hashes.setdefault(key, body_hash)
            if old != body_hash:
                self._conflicted.add(key)
            return key not in self._conflicted

    def is_conflicted(self, key: tuple) -> bool:
        with self._lock:
            return key in self._conflicted

    def put_once(self, object_id: str, content: bytes) -> None:
        with self._lock:
            if object_id in self._objects:
                raise ShadowBlocked("STORAGE_OBJECT_ALREADY_EXISTS")
            self._objects[object_id] = bytes(content)

    def read(self, object_id: str) -> bytes:
        with self._lock:
            return self._objects[object_id]

class OfflineShadowWorker:
    """Synchronous D1 harness: only invokes injected in-process fixture callable."""

    def __init__(self, store: MemoryEvidenceStore | None = None):
        self.store = store if store is not None else MemoryEvidenceStore()
        self.public_writes = 0  # no writer is defined or reachable

    def conflicted(self, report_id: str, revision: int) -> bool:
        return self.store.is_conflicted((report_id, revision, LANE))

    def effective_status(self, result: ShadowResult) -> str:
        """Conflicting attempts are quarantined even if prior evidence is immutable."""
        return ("BLOCKED_CONFLICT" if self.conflicted(result.report_id, result.record["revision"])
                else result.status)

    def run(
        self,
        context: ReportContext,
        snapshot: MarketDataSnapshot,
        responder: Callable[[dict], dict],
        *,
        shadow_run_id: str | None = None,
        attempt_id: str | None = None,
        prompt: str = "offline shadow fixture prompt",
        model: str = "offline-fixture-model",
        created_at: str = "2026-10-15T00:00:00+09:00",
    ) -> ShadowResult:
        if not callable(responder):
            raise TypeError("D1 requires an injected offline responder")
        shadow_run_id = shadow_run_id or str(uuid4())
        attempt_id = attempt_id or str(uuid4())
        if not shadow_run_id or not attempt_id or not model or not prompt:
            raise ShadowBlocked("INVALID_RUN_ID_OR_CONFIG")
        key = (context.report_id, context.revision, LANE)
        self.store.claim_attempt(key, shadow_run_id, attempt_id)
        states = ["QUEUED"]
        record = {
            "schema_version": SCHEMA,
            "lane": LANE,
            "run_mode": "shadow",
            "eligibility": ELIGIBILITY,
            "shadow_run_id": shadow_run_id,
            "attempt_id": attempt_id,
            "report_id": context.report_id,
            "revision": context.revision,
            "context": None,
            "context_sha256": None,
            "snapshot_id": None,
            "snapshot_sha256": None,
            "cutoff": context.data_cutoff,
            "source_observations": [],
            "producer": {
                "provider": "OpenAI", "endpoint": "v1/responses",
                "model": model, "prompt_sha256": sha256_bytes(prompt.encode("utf-8")),
                "request_sha256": None, "response_id": None,
                "response_status": "unknown", "usage": None, "body_utf8_sha256": None
            },
            "body_text": None,
            "validation": {"status": "BLOCKED", "reasons": []},
            "created_at": created_at,
        }
        reason = ""
        final_status = "BLOCKED"
        try:
            aware(created_at)
            frozen_context, frozen_snapshot = freeze_shadow_input(context, snapshot)
            states.append("CONTEXT_FROZEN")
            record["context"] = frozen_context
            record["context_sha256"] = digest(frozen_context)
            states.append("SNAPSHOT_FROZEN")
            record["snapshot_id"] = snapshot.snapshot_id
            record["snapshot_sha256"] = digest(frozen_snapshot)
            record["source_observations"] = [
                {"series": m.instrument, "value": m.priceValue, "unit": m.priceUnit,
                 "source": plain(m.source), "as_of": m.asOf, "status": m.status}
                for m in snapshot.markets
            ]
            request = {"context": frozen_context, "snapshot": frozen_snapshot,
                       "prompt": prompt, "model": model}
            record["producer"]["request_sha256"] = sha256_bytes(json_bytes(request))
            states.append("REQUESTED")
            # No network client lives here; fixture callable is the only execution.
            reply = responder(json.loads(json_bytes(request)))
            states.append("RESPONSE_CAPTURED")
            full_text = validate_mock_response(reply, context, snapshot)
            record["producer"]["response_id"] = reply["response_id"]
            record["producer"]["response_status"] = reply["status"]
            record["producer"]["usage"] = reply["usage"]
            record["body_text"] = full_text
            body_hash = sha256_bytes(full_text.encode("utf-8"))
            record["producer"]["body_utf8_sha256"] = body_hash
            if not self.store.track_body(key, body_hash):
                raise ShadowBlocked("SAME_REVISION_BODY_HASH_CONFLICT")
            record["validation"] = {"status": "PASS", "reasons": []}
            states.append("VALIDATED")
            final_status = "SHADOW_VALIDATED"
        except TimeoutError:
            reason = "UNKNOWN_PROVIDER_RESULT"
            final_status = "UNKNOWN_PROVIDER_RESULT"
            self.store.mark_unknown(key)
        except (ShadowBlocked, ValueError, TypeError, KeyError, AttributeError) as exc:
            reason = str(exc) if isinstance(exc, ShadowBlocked) else "INVALID_INPUT_OR_RESPONSE"
            final_status = "BLOCKED"
        if reason:
            record["validation"] = {"status": "BLOCKED", "reasons": [reason]}
        record["states"] = states[:]
        object_id = f"shadow/{shadow_run_id}/{attempt_id}"
        content = json_bytes(record)
        expected_hash = sha256_bytes(content)
        self.store.put_once(object_id, content)
        states.append("PRIVATE_STORED")
        try:
            readback = self.store.read(object_id)
            if readback != content or sha256_bytes(readback) != expected_hash:
                reason = "PRIVATE_READBACK_MISMATCH"
                final_status = "BLOCKED"
            else:
                states.append("READBACK_VERIFIED")
        except (KeyError, ValueError):
            reason = "PRIVATE_READBACK_MISSING"
            final_status = "BLOCKED"
        return ShadowResult(
            final_status, reason, attempt_id, shadow_run_id,
            context.report_id, tuple(states), object_id, expected_hash, record
        )


def validate_mock_response(reply: dict, context: ReportContext, snapshot: MarketDataSnapshot) -> str:
    """Strict *fixture* output contract, not a claimed semantic AI-proof."""
    if not isinstance(reply, dict) or set(reply) != {
        "response_id", "status", "report_id", "title",
        "full_text", "observations_used", "usage", "refusal"
    }:
        raise ShadowBlocked("RESPONSE_SCHEMA_MISMATCH")
    if reply["refusal"] or reply["status"] != "completed" or not reply["response_id"]:
        raise ShadowBlocked("RESPONSE_NOT_COMPLETED")
    if reply["report_id"] != context.report_id:
        raise ShadowBlocked("RESPONSE_REPORT_ID_MISMATCH")
    title = f"マーケットレポート｜{datetime.fromisoformat(context.report_date):%Y/%m/%d}（" + (
        "月火水木金土日"[datetime.fromisoformat(context.report_date).weekday()]) + f"）{context.report_time}"
    text = reply["full_text"]
    if (not isinstance(text, str) or len(text) < 1200 or
            text.splitlines()[0].strip() != title or reply["title"] != title):
        raise ShadowBlocked("REPORT_BODY_OR_TITLE_INVALID")
    headings = {section["heading"] for section in parse_sections(text)}
    if not set(HEADING_REGISTRY["required"]).issubset(headings):
        raise ShadowBlocked("REQUIRED_SOP_HEADINGS_MISSING")
    usage = reply["usage"]
    if not isinstance(usage, dict) or set(usage) != {"input_tokens", "output_tokens"} or any(
        type(usage[k]) is not int or usage[k] < 0 for k in usage
    ):
        raise ShadowBlocked("USAGE_INVALID")
    observed = {market.instrument: market for market in snapshot.markets}
    citations = reply["observations_used"]
    if not isinstance(citations, list) or {m.instrument for m in snapshot.markets} - {
        item.get("series") for item in citations if isinstance(item, dict)
    }:
        raise ShadowBlocked("SIX_MARKET_CITATIONS_MISSING")
    seen = set()
    for item in citations:
        if not isinstance(item, dict) or set(item) != {"series", "value", "unit"}:
            raise ShadowBlocked("OBSERVATION_CITATION_SCHEMA_INVALID")
        series = item["series"]
        market = observed.get(series)
        if market is None or series in seen or type(item["value"]) not in (int, float) or (
            item["value"] != market.priceValue or item["unit"] != market.priceUnit
        ):
            raise ShadowBlocked("INVENTED_OR_MISMATCHED_OBSERVATION")
        seen.add(series)
    # Fixtures must actually include the observation values in the displayed body.
    # Additional prose numbers cannot be treated as verified by this D1 check;
    # complete claim-level verification remains a D2 prerequisite.
    for market in snapshot.markets:
        if not re.search(r"(?<![\d.])" + re.escape(str(market.priceValue)) + r"(?![\d.])", text):
            raise ShadowBlocked("OBSERVATION_VALUE_MISSING_FROM_BODY")
    return text
