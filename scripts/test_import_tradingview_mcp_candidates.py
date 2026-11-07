from __future__ import annotations

import datetime as dt
import unittest

from scripts.import_tradingview_mcp_candidates import (
    CandidateImportError,
    HEADERS,
    FIELD_CONTRACT,
    normalize_snapshot,
    new_sheet_rows,
    append_idempotent_sheet_rows,
    report_ready_rows,
    reference_futures_rows,
    sheet_rows,
    verified_report_candidates,
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
        self.assertEqual(HEADERS[10], "Source Market Date")
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

    def test_report_feed_promotes_only_verified_rows_and_keeps_market_lineage(self) -> None:
        payload = normalize_snapshot(
            make_snapshot(), now=dt.datetime.fromisoformat("2026-10-11T18:00:00+00:00")
        )
        payload["candidates"][0].update(reviewStatus="VERIFIED", reviewBasis="official close")
        payload["candidates"][1].update(reviewStatus="CONFLICT", reviewBasis="official close differs")
        payload["candidates"][2].update(reviewStatus="PENDING", reviewBasis="close not confirmed")
        ready = verified_report_candidates(payload)
        rows = report_ready_rows(payload)

        self.assertEqual([item["id"] for item in ready], ["dow"])
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0][1], "dow")
        self.assertEqual(rows[0][2], payload["candidates"][0]["value"])
        self.assertEqual(rows[0][6], "2026-10-09")
        self.assertEqual(rows[0][8], "TradingView official MCP")
        self.assertEqual(rows[0][9], "official close")
        self.assertEqual(rows[0][10], "VERIFIED")

    def test_no_verified_candidates_produce_no_report_rows(self) -> None:
        payload = normalize_snapshot(
            make_snapshot(), now=dt.datetime.fromisoformat("2026-10-11T18:00:00+00:00")
        )
        self.assertEqual(report_ready_rows(payload), [])

    def test_five_futures_stay_separate_reference_values_without_settlement_claim(self) -> None:
        payload = normalize_snapshot(
            make_snapshot(), now=dt.datetime.fromisoformat("2026-10-11T18:00:00+00:00")
        )
        rows = reference_futures_rows(payload)
        self.assertEqual(len(rows), 5)
        self.assertEqual({row[1] for row in rows}, {
            "gold", "wti", "nikkei225_futures_ose", "cme_nikkei225_jpy", "cme_nikkei225_usd",
        })
        self.assertTrue(all(row[10] == "REFERENCE_ONLY" for row in rows))
        self.assertTrue(all("NOT_CONFIRMED" in row[11] for row in rows))
        self.assertFalse(any(item["id"] in {row[1] for row in rows} for item in verified_report_candidates(payload)))

    def test_report_tab_appends_once_and_checks_existing_identity_conflict(self) -> None:
        class FakeClient:
            def __init__(self):
                self.rows = []

            def ensure_sheets(self, names):
                return {name: 1 for name in names}

            def get_values(self, sheet, a1):
                return self.rows

            def update(self, sheet, cell, rows):
                self.rows = rows

            def append(self, sheet, a1, rows):
                self.rows.extend(rows)

        client = FakeClient()
        headers = ["Snapshot ID", "Report Field", "Observed Value"]
        row = ["tv-mcp-dow-20261011000000", "dow", 40000.0]
        first = append_idempotent_sheet_rows(client, "Report", headers, [row], "C")
        second = append_idempotent_sheet_rows(client, "Report", headers, [row], "C")
        self.assertEqual(first["rowsAppended"], 1)
        self.assertEqual(second["rowsAppended"], 0)
        self.assertEqual(len(client.rows), 2)
        with self.assertRaisesRegex(CandidateImportError, "different data"):
            append_idempotent_sheet_rows(
                client, "Report", headers,
                [["tv-mcp-dow-20261011000000", "dow", 39999.0]], "C",
            )


if __name__ == "__main__":
    unittest.main()
