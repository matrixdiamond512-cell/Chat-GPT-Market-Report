"""Offline Python serialization vectors for detecting (not hiding) GAS drift.

Existing snapshot IDs stay unchanged. A divergent vector is an explicit BLOCKER
for production producer-proof signing until a versioned canonicalization contract
is agreed; this script never modifies report or snapshot data.
"""
import hashlib
import json

VECTORS = [
    {
        "id": "common-integer-japanese-null-arrays",
        "payload": {
            "report_id": "2026-10-15_16-00",
            "report_title": "マーケットレポート",
            "priceValue": 100,
            "status": None,
            "observations": [{"symbol": "金", "value": 1.25}, {"symbol": "ドル円", "value": -7}],
        },
        "expected_parity": True,
    },
    {
        "id": "decimal-exact-fraction",
        "payload": {"value": 12.5, "negative": -1, "offset": "2026-10-15T16:00:00+09:00"},
        "expected_parity": True,
    },
    {
        "id": "float-100-point-zero",
        "payload": {"priceValue": 100.0, "source": "official"},
        "expected_parity": False,
    },
    {
        "id": "negative-zero-float",
        "payload": {"value": -0.0},
        "expected_parity": False,
    },
    {
        "id": "scientific-exponent",
        "payload": {"value": 0.0000001},
        "expected_parity": False,
    },
]


def canonical_bytes(value):
    return json.dumps(
        value, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")


def main():
    rows = []
    for fixture in VECTORS:
        raw = canonical_bytes(fixture["payload"])
        rows.append({
            "id": fixture["id"], "payload": fixture["payload"],
            "expected_parity": fixture["expected_parity"],
            "python_canonical": raw.decode("utf-8"),
            "python_sha256": hashlib.sha256(raw).hexdigest(),
        })
    print(json.dumps({"schema_version": "d1-golden/v1", "vectors": rows},
                     ensure_ascii=False, separators=(",", ":")))


if __name__ == "__main__":
    main()
