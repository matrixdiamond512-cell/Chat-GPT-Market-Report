from __future__ import annotations

import datetime as dt
import unittest

from scripts.import_tradingview_mcp_candidates import (
    CandidateImportError,
    FIELD_CONTRACT,
    normalize_snapshot,
    new_sheet_rows,
    sheet_rows,
)


def make_snapshot() -> dict:
    retrieved = "2026-10-12T02:48:00+09:00"
    items = []
    for index, (item_id, contract) in enumerate(FIELD_CONTRACT.items()):
        items.append({
            "id": item_id,
            "symbol": contract["symbol"],
            "value": 100 + index,
            "unit": contract["unit"],
            "marketType": contract["marketType"],
            "session": contract["session"],
            "interval": "1D",
            "barAnchorUtc": "2026-10-11T00:00:00Z",
            "marketDate": "2026-10-10" if item_id == "btcusd" else "2026-10-09",
        })
    return {"retrievedAt": retrieved, "items": items}


class TradingViewMcpCandidateImportTests(unittest.TestCase):
    def test_normalizes_all_17_and_keeps_market_dates_distinct(self) -> None:
        normalized = normalize_snapshot(
            make_snapshot(),
            now=dt.datetime.fromisoformat("2026-10-11T18:00:00+00:00"),
        )

        self.assertEqual(normalized["candidateCount"], 17)
        self.assertFalse(normalized["automationEnabled"])
        self.assertFalse(normalized["publicPublicationEnabled"])
        self.assertEqual(
            {item["reviewStatus"] for item in normalized["candidates"]},
            {"CANDIDATE_CLOSE_AND_SESSION_REVIEW_REQUIRED"},
        )
        dates = {item["marketDate"] for item in normalized["candidates"]}
        self.assertEqual(dates, {"2026-10-09", "2026-10-10"})
        self.assertEqual(len(sheet_rows(normalized)), 17)
        self.assertEqual(
            normalized["candidates"][0]["snapshotId"],
            "tv-mcp-dow-20261011000000",
        )

    def test_repeat_import_adds_no_duplicate_rows(self) -> None:
        normalized = normalize_snapshot(
            make_snapshot(),
            now=dt.datetime.fromisoformat("2026-10-11T18:00:00+00:00"),
        )
        rows = sheet_rows(normalized)
        existing_ids = {str(row[0]) for row in rows}
        self.assertEqual(new_sheet_rows(rows, existing_ids), [])

    def test_rejects_an_incomplete_batch(self) -> None:
        snapshot = make_snapshot()
        snapshot["items"].pop()
        with self.assertRaisesRegex(CandidateImportError, "incomplete 17-field batch"):
            normalize_snapshot(snapshot)

    def test_rejects_duplicate_fields(self) -> None:
        snapshot = make_snapshot()
        snapshot["items"].append(dict(snapshot["items"][0]))
        with self.assertRaisesRegex(CandidateImportError, "duplicate report field"):
            normalize_snapshot(snapshot)

    def test_rejects_wrong_symbol_instead_of_relabeling(self) -> None:
        snapshot = make_snapshot()
        snapshot["items"][0]["symbol"] = "NYSE:DJI"
        with self.assertRaisesRegex(CandidateImportError, "symbol does not match"):
            normalize_snapshot(snapshot)

    def test_rejects_wrong_unit(self) -> None:
        snapshot = make_snapshot()
        snapshot["items"][0]["unit"] = "USD"
        with self.assertRaisesRegex(CandidateImportError, "unit does not match"):
            normalize_snapshot(snapshot)

    def test_rejects_nonfinite_value(self) -> None:
        snapshot = make_snapshot()
        snapshot["items"][0]["value"] = float("nan")
        with self.assertRaisesRegex(CandidateImportError, "finite number"):
            normalize_snapshot(snapshot)

    def test_market_date_validation_uses_item_market_timezone(self) -> None:
        snapshot = make_snapshot()
        nikkei = next(item for item in snapshot["items"] if item["id"] == "nikkei225_cash")
        nikkei["marketDate"] = "2026-10-12"
        normalized = normalize_snapshot(
            snapshot,
            now=dt.datetime.fromisoformat("2026-10-11T18:00:00+00:00"),
        )
        candidate = next(item for item in normalized["candidates"] if item["id"] == "nikkei225_cash")
        self.assertEqual(candidate["marketDate"], "2026-10-12")
        self.assertEqual(candidate["marketTimezone"], "Asia/Tokyo")

    def test_rejects_future_market_date(self) -> None:
        snapshot = make_snapshot()
        snapshot["items"][0]["marketDate"] = "2026-10-12"
        with self.assertRaisesRegex(CandidateImportError, "later than retrieval date"):
            normalize_snapshot(
                snapshot,
                now=dt.datetime.fromisoformat("2026-10-11T18:00:00+00:00"),
            )

    def test_rejects_naive_timestamps(self) -> None:
        snapshot = make_snapshot()
        snapshot["retrievedAt"] = "2026-10-12T02:48:00"
        with self.assertRaisesRegex(CandidateImportError, "include a timezone"):
            normalize_snapshot(snapshot)


if __name__ == "__main__":
    unittest.main()
