"""Golden vectors for *new* versioned evidence, never live market data."""
from __future__ import annotations

from copy import deepcopy
from datetime import date
import hashlib
import hmac
import json

from .canonical_v2 import VERSION, canonical_v2_bytes, sha256_v2, tagged_v2
from .context import ReportContext
from .snapshot import Market, MarketDataSnapshot, digest

TEST_ONLY_KEY = b"golden-v2-test-key-not-for-production"


def vectors():
    return [
        {"id": "unicode-nulllist", "payload": {
            "title": "マーケットレポート｜金🚀", "null": None,
            "array": [1, True, None, "改行\nと 区切り"]}},
        {"id": "float-integral", "payload": {"priceValue": 100.0, "priceInt": 100}},
        {"id": "negative-zero", "payload": {"value": -0.0}},
        {"id": "scientific", "payload": {"value": 0.0000001, "negative": -7.5}},
        {"id": "timestamp-and-order", "payload": {
            "offset": "2026-10-15T16:00:00+09:00",
            "markets": [{"series": "gold", "value": 152.5}, {"series": "usdjpy", "value": 100.0}]}},
    ]


def evidence():
    context = ReportContext.create("2026-10-15", "16:00",
                                   "2026-10-15T16:00:00+09:00",
                                   previous_business_day="2026-10-14")
    markets = []
    numbers = (100.0, 70.25, 1e-7, 140.5, 1.25, 120.75)
    for index, instrument in enumerate(("gold", "wti", "nikkei225_futures_ose",
                                        "usdjpy", "eurusd", "btcusd")):
        markets.append(Market(
            instrument=instrument, marketType="test",
            venue=None, contractMonth=None, priceValue=numbers[index],
            priceUnit="test unit", changeValue=-0.0 if index == 0 else None,
            changePct=None, direction="FLAT" if index == 0 else "UNKNOWN",
            comparisonBasis="previous_close" if index == 0 else "",
            asOf="2026-10-15T15:45:00+09:00",
            source=({"id": "fixture", "url": "https://example.invalid/fixture"},),
            status="VALID", unavailableReason=None, displayText="試験データ"
        ))
    snapshot = MarketDataSnapshot.capture(
        context, tuple(markets), "2026-10-15T15:50:00+09:00")
    # Freeze legacy identity BEFORE creating new tagged v2 representation.
    legacy_id = snapshot.snapshot_id
    assert legacy_id == "snapshot-" + digest(snapshot.identity_payload())
    wrapped_context = tagged_v2(context.to_dict())
    wrapped_snapshot = tagged_v2(snapshot.to_dict())
    typed_snapshot_identity = deepcopy(wrapped_snapshot)
    del typed_snapshot_identity["snapshot_id"]
    proof = {
        "canonicalization_version": VERSION,
        "context": wrapped_context,
        "context_digest_v2": sha256_v2(wrapped_context),
        "snapshot": wrapped_snapshot,
        "snapshot_digest_v2": sha256_v2(typed_snapshot_identity),
    }
    return proof, legacy_id, snapshot.snapshot_id


def main():
    cases = []
    for vector in vectors():
        tagged = tagged_v2(vector["payload"])
        raw = canonical_v2_bytes(tagged)
        cases.append({
            "id": vector["id"],
            "tagged": tagged,
            "canonical_v2": raw.decode("utf-8"),
            "sha256_v2": hashlib.sha256(raw).hexdigest(),
            "test_hmac_sha256_v2": hmac.new(TEST_ONLY_KEY, raw, hashlib.sha256).hexdigest()
        })
    record, original_legacy_id, preserved_legacy_id = evidence()
    assert original_legacy_id == preserved_legacy_id
    print(json.dumps({
        "format": VERSION,
        "vectors": cases,
        "evidence": record,
        "legacy_snapshot_id": original_legacy_id,
        "legacy_id_unchanged": original_legacy_id == preserved_legacy_id
    }, ensure_ascii=False, allow_nan=False, separators=(",", ":")))


if __name__ == "__main__":
    main()
