from __future__ import annotations

import datetime as dt
import json
import unittest
from unittest.mock import patch
from urllib.parse import parse_qs, unquote, urlparse

from scripts import sync_market_close_sheet as close_sync


JST = dt.timezone(dt.timedelta(hours=9))
SHEET_ID = 1
BASE_HEADERS = [
    "日付", "Dow終値", "Dow前日比", "Dow騰落率", "Nasdaq終値", "Nasdaq前日比", "Nasdaq騰落率",
    "S&P500終値", "S&P500前日比", "S&P500騰落率", "Russell 2000終値", "Russell 2000前日比", "Russell 2000騰落率",
    "日経225終値", "日経225前日比", "日経225騰落率", "日経225先物大阪終値", "日経225先物大阪前日比", "日経225先物大阪騰落率",
    "USDJPY終値", "USDJPY前日比", "USDJPY騰落率", "EURUSD終値", "EURUSD前日比", "EURUSD騰落率",
    "ゴールド終値", "ゴールド前日比", "ゴールド騰落率", "WTI原油終値", "WTI原油前日比", "WTI原油騰落率",
    "BTCUSD終値", "BTCUSD前日比", "BTCUSD騰落率", "VIX終値", "VIX前日比", "VIX騰落率",
    "日経VI終値", "日経VI前日比", "日経VI騰落率", "FearGreed終値", "FearGreed前日比", "FearGreed判定",
    "米10年債利回り", "日本10年債利回り", "日経225予想EPS", "日経225予想PER", "登録日時",
    "USDJPY価格取得元", "USDJPY価格取得日時", "日経225寄与度取得元",
]
LOG_HEADERS = list(close_sync.LOG_HEADERS)
INPUT_HEADERS = list(close_sync.INPUT_HEADERS)


def col_number(label: str) -> int:
    result = 0
    for char in label:
        result = result * 26 + ord(char.upper()) - 64
    return result - 1


def col_label(index: int) -> str:
    return close_sync.letter_for_column(index)


class FakeSheetsClient:
    def __init__(self, target: dt.date, prior: dt.date | None = None, *, write_failure: bool = False, corrupt_readback: bool = False):
        self.base_url = "https://fake/sheets"
        self.spreadsheet_id = "fake"
        self.write_failure = write_failure
        self.corrupt_readback = corrupt_readback
        self.headers = [""] * 186
        for index, header in enumerate(BASE_HEADERS):
            self.headers[index] = header
        self.headers[185] = "日経225寄与度取得元"
        extra_headers = [header for header in close_sync.SUPPLEMENTAL_FIELDS.values() if header not in BASE_HEADERS]
        for index, header in enumerate(extra_headers, start=len(BASE_HEADERS)):
            self.headers[index] = header
        self.headers.extend(["日経225_25日乖離率", "日経225_200日乖離率"])
        self.data = [self.headers]
        if target is not None:
            self.data.append(self._row(target))
        if prior is not None:
            old = self._row(prior)
            self.data.append(old)
        self.import_rows = []
        self.log = [LOG_HEADERS]

    def _row(self, date: dt.date) -> list[object]:
        row: list[object] = [""] * len(self.headers)
        row[0] = date.strftime("%Y/%m/%d")
        return row

    def sheet_map(self):
        return {"終値一覧": 1, "GitHub_Market_Import": 2, "ChatGPT_Market_Input": 3, "WEB_Data_Update_Log": 4}

    def _range(self, sheet_name, cells):
        return "'" + sheet_name.replace("'", "''") + "'!" + cells

    def append(self, sheet_name, cells, values):
        self.log.extend(values)

    def _parse_range(self, value):
        value = unquote(value)
        sheet, address = value.rsplit("!", 1)
        sheet = sheet.strip("'").replace("''", "'")
        return sheet, address

    def _matrix(self, sheet, address):
        if sheet == "WEB_Data_Update_Log":
            return self._slice(self.log, address)
        if sheet in ("GitHub_Market_Import", "ChatGPT_Market_Input"):
            return self._slice(self.import_rows, address)
        return self._slice(self.data, address)

    def _slice(self, matrix, address):
        left, right = (address.split(":", 1) + [address])[:2] if ":" in address else (address, address)
        import re
        start = re.match(r"([A-Z]+)(\d*)", left)
        end = re.match(r"([A-Z]+)(\d*)", right)
        c1, r1 = col_number(start.group(1)), int(start.group(2) or 1)
        c2, r2 = col_number(end.group(1)), int(end.group(2) or len(matrix))
        if not start.group(2):
            r1 = 1
        if not end.group(2):
            r2 = len(matrix)
        output = []
        for row_idx in range(max(0, r1 - 1), min(r2, len(matrix))):
            row = matrix[row_idx]
            output.append(list(row[c1 : c2 + 1]))
        while output and all(value in (None, "") for value in output[-1]):
            output.pop()
        while output and output[-1] == []:
            output.pop()
        if output:
            last = max((i for i, value in enumerate(output[-1]) if value not in (None, "")), default=-1)
            output[-1] = output[-1][: last + 1]
        return output

    def _request(self, method, url, **kwargs):
        parsed = urlparse(url)
        if method == "GET" and parsed.path.endswith("/values:batchGet"):
            params = parse_qs(parsed.query)
            ranges = params.get("ranges", [])
            return {"valueRanges": [{"values": self._matrix(*self._parse_range(item))} for item in ranges]}
        if method == "GET" and "/values/" in parsed.path:
            encoded = parsed.path.split("/values/", 1)[1]
            sheet, address = self._parse_range(encoded.split("?", 1)[0])
            values = self._matrix(sheet, address)
            if self.corrupt_readback and sheet == "終値一覧" and address.startswith("A2:GF2") and len(values) and len(values[0]) > 25:
                values[0][25] = -999
            return {"values": values}
        if method == "POST" and parsed.path.endswith("/values:batchUpdate"):
            if self.write_failure:
                raise close_sync.SheetsSyncError("simulated HTTP 500 write failure")
            body = kwargs.get("json") or {}
            for entry in body.get("data", []):
                sheet, address = self._parse_range(entry["range"])
                self._write(sheet, address, entry.get("values") or [])
            return {}
        if method == "POST" and parsed.path.endswith(":batchUpdate"):
            requests = (kwargs.get("json") or {}).get("requests") or []
            for request in requests:
                if "insertDimension" in request:
                    position = request["insertDimension"]["range"]["startIndex"]
                    self.data.insert(position, [""] * 186)
            return {}
        if method == "GET" and "/values/" in parsed.path and ":append" in parsed.path:
            return {}
        return {}

    def _write(self, sheet, address, values):
        if sheet == "WEB_Data_Update_Log":
            self.log.extend(values)
            return
        matrix = self.data if sheet == "終値一覧" else self.import_rows
        left, right = (address.split(":", 1) + [address])[:2] if ":" in address else (address, address)
        import re
        start = re.match(r"([A-Z]+)(\d+)", left)
        end = re.match(r"([A-Z]+)(\d+)", right)
        c1, r1 = col_number(start.group(1)), int(start.group(2))
        c2, r2 = col_number(end.group(1)), int(end.group(2))
        while len(matrix) < r2:
            matrix.append([""] * max(186, c2 + 1))
        for ridx, row in enumerate(values):
            target = matrix[r1 - 1 + ridx]
            if len(target) < c2 + 1:
                target.extend([""] * (c2 + 1 - len(target)))
            for cidx, value in enumerate(row):
                cell_index = c1 + cidx
                target[cell_index] = -999 if (self.corrupt_readback and sheet == "終値一覧" and cell_index == 25) else value


def snapshot(target: dt.date, now: dt.datetime, *, missing: str | None = None) -> dict:
    markets = {}
    for symbol in close_sync.PRICE_FIELDS:
        if symbol == missing:
            markets[symbol] = {"verificationStatus": "unavailable", "asOf": now.isoformat(), "value": None, "sourceId": symbol}
            continue
        close_time = dt.time(15, 50) if symbol == "nikkei_vi" else dt.time(15, 0)
        markets[symbol] = {
            "id": symbol, "value": 100.0, "previousClose": 99.0, "change": 1.0,
            "changePercent": 1.0 / 99 * 100, "asOf": dt.datetime.combine(target, close_time, JST).isoformat(),
            "fetchedAt": now.isoformat(), "sourceId": symbol + "_source", "sourceName": symbol + " source",
            "verificationStatus": "verified", "classification": "Neutral",
        }
        if symbol in {"usdjpy", "eurusd"}:
            markets[symbol].update({
                "sourceSeriesId": symbol + "_daily_close",
                "observationDefinition": "Synthetic daily spot bar close",
                "sessionCloseAt": dt.datetime.combine(target, close_time, JST).isoformat(),
                "marketType": "spot", "session": "daily_close",
                "unit": "JPY per USD" if symbol == "usdjpy" else "USD per EUR",
                "reportedDecimalPlaces": 2 if symbol == "usdjpy" else 5,
            })
        elif symbol == "us10y":
            markets[symbol].update({
                "sourceSeriesId": "daily_treasury_yield_curve:BC_10YEAR",
                "observationDefinition": "Treasury 10-year constant-maturity par yield",
                "sessionCloseAt": "15:30 America/New_York",
                "unit": "%", "reportedDecimalPlaces": 2, "marketType": "yield",
                "session": "daily_publication",
            })
    for symbol in close_sync.TECHNICAL_FIELDS:
        markets[symbol] = {
            "id": symbol, "value": 1.25,
            "asOf": dt.datetime.combine(target, dt.time(15, 0), JST).isoformat(),
            "fetchedAt": now.isoformat(), "sourceId": symbol + "_source", "sourceName": symbol + " source",
            "verificationStatus": "verified",
        }
    supplemental_values = {
        "nikkei225_eps": 3018.4,
        "nikkei225_per": 22.87,
        "nikkei225_pbr": 2.83,
        "tse_prime_advancers": 1194,
        "tse_prime_decliners": 331,
        "tse_prime_ad_ratio25": 91.18,
        "tse_prime_turnover": 7.8454,
        "tse_prime_volume": 2295.19,
    }
    for symbol, value in supplemental_values.items():
        markets[symbol] = {
            "id": symbol, "value": value,
            "asOf": dt.datetime.combine(target, dt.time(15, 0), JST).isoformat(),
            "fetchedAt": now.isoformat(), "sourceId": symbol + "_source", "sourceName": symbol + " source",
            "verificationStatus": "verified",
        }
        if symbol in {"nikkei225_eps", "nikkei225_per", "nikkei225_pbr"}:
            markets[symbol].update({
                "sourceSeriesId": symbol + "_index_based",
                "valuationBasis": "index_based",
                "observationDefinition": "Nikkei 225 index-based valuation",
            })
    return {"generatedAt": now.isoformat(), "reportSlot": "08:00", "overallStatus": "verified", "missingRequired": [], "markets": markets}


def populate_import_tabs(client: FakeSheetsClient, payload: dict) -> None:
    headers = list(INPUT_HEADERS)
    client.import_rows = [headers]
    generated = payload["generatedAt"]
    for symbol, market in payload["markets"].items():
        client.import_rows.append([
            f"{generated}|{symbol}", generated, "08:00", payload.get("overallStatus"), symbol, symbol,
            close_sync.use_policy(market), market.get("value"), market.get("asOf", ""), market.get("fetchedAt", ""),
            market.get("verificationStatus", ""), market.get("sourceName", ""),
        ])


class CloseSyncTests(unittest.TestCase):
    def setUp(self):
        self.target = dt.date(2026, 9, 30)
        self.next_day = dt.datetime(2026, 10, 1, 6, 35, tzinfo=JST)
        self.prior = dt.date(2026, 9, 29)

    def run_sync(self, client, payload, now=None):
        populate_import_tabs(client, payload)
        return close_sync.close_row_sync(client, payload, now or self.next_day, sleep=lambda _: None)

    def test_1_missing_date_creates_one_row(self):
        client = FakeSheetsClient(self.target - dt.timedelta(days=1))
        result = self.run_sync(client, snapshot(self.target, self.next_day))
        self.assertTrue(result["inserted"])
        self.assertEqual(sum(close_sync.parse_sheet_date(row[0]) == self.target for row in client.data[1:]), 1)

    def test_2_existing_date_updates_same_row(self):
        client = FakeSheetsClient(self.target, self.prior)
        original_count = len(client.data)
        result = self.run_sync(client, snapshot(self.target, self.next_day))
        self.assertFalse(result["inserted"])
        self.assertEqual(len(client.data), original_count)
        self.assertEqual(result["row"], 2)

    def test_3_one_failed_symbol_does_not_discard_others(self):
        client = FakeSheetsClient(self.target, self.prior)
        result = self.run_sync(client, snapshot(self.target, self.next_day, missing="gold"))
        self.assertEqual(result["status"], "PARTIAL")
        self.assertTrue(str(client.data[1][25]).startswith("取得不能（"))
        self.assertEqual(client.data[1][28], 100.0)

    def test_4_write_failure_is_failed(self):
        client = FakeSheetsClient(self.target, self.prior, write_failure=True)
        result = self.run_sync(client, snapshot(self.target, self.next_day))
        self.assertEqual(result["status"], "FAILED", result)

    def test_5_readback_mismatch_is_failed(self):
        client = FakeSheetsClient(self.target, self.prior, corrupt_readback=True)
        result = self.run_sync(client, snapshot(self.target, self.next_day))
        self.assertEqual(result["status"], "FAILED", result)
        self.assertEqual(result["failedStage"], "READBACK_VERIFY")

    def test_6_all_required_fields_and_stages_yield_success(self):
        client = FakeSheetsClient(self.target, self.prior)
        payload = snapshot(self.target, self.next_day)
        fields = {field for item in close_sync.PRICE_FIELDS.values() for field in item if field}
        fields.update(close_sync.TECHNICAL_FIELDS.values())
        with patch.object(close_sync, "REQUIRED_CLOSE_HEADERS", tuple(fields)), patch.object(
            close_sync, "VALUATION_CLOSE_LIST_POLICY", {},
        ):
            result = self.run_sync(client, payload)
        self.assertEqual(result["status"], "SUCCESS")

    def test_7_saturday_uses_friday_without_saturday_row(self):
        friday = dt.date(2026, 10, 2)
        saturday_now = dt.datetime(2026, 10, 3, 6, 35, tzinfo=JST)
        client = FakeSheetsClient(friday, friday - dt.timedelta(days=1))
        payload = snapshot(friday, saturday_now)
        result = self.run_sync(client, payload, saturday_now)
        self.assertEqual(result["targetDate"], friday.isoformat())
        self.assertFalse(any(close_sync.parse_sheet_date(row[0]) == saturday_now.date() for row in client.data[1:]))

    def test_8_monday_uses_friday(self):
        friday = dt.date(2026, 10, 2)
        monday_now = dt.datetime(2026, 10, 5, 6, 35, tzinfo=JST)
        client = FakeSheetsClient(friday, friday - dt.timedelta(days=1))
        payload = snapshot(friday, monday_now)
        result = self.run_sync(client, payload, monday_now)
        self.assertEqual(result["targetDate"], friday.isoformat())

    def test_9_same_payload_twice_has_no_duplicate(self):
        client = FakeSheetsClient(self.target, self.prior)
        payload = snapshot(self.target, self.next_day)
        self.run_sync(client, payload)
        self.run_sync(client, payload)
        self.assertEqual(sum(close_sync.parse_sheet_date(row[0]) == self.target for row in client.data[1:]), 1)

    def test_10_historical_repair_fills_blanks_and_preserves_existing_values(self):
        client = FakeSheetsClient(self.target, self.prior)
        client.data[1][col_number("B")] = 88.0
        old_generated = dt.datetime(2026, 9, 30, 6, 30, tzinfo=JST)
        payload = snapshot(self.target, old_generated)
        with patch.object(close_sync, "REQUIRED_CLOSE_HEADERS", tuple(
            field for trio in close_sync.PRICE_FIELDS.values() for field in trio if field
        )):
            result = close_sync.close_row_sync(
                client, payload, self.next_day, verify_import_tabs=False,
                allow_historical=True, preserve_existing=True, sleep=lambda _: None,
            )
        self.assertEqual(client.data[1][col_number("B")], 88.0)
        self.assertEqual(client.data[1][col_number("AC")], 100.0)
        self.assertEqual(result["row"], 2)

    def test_11_historical_repair_does_not_insert_missing_rows(self):
        client = FakeSheetsClient(None)
        payload = snapshot(self.target, dt.datetime(2026, 9, 30, 6, 30, tzinfo=JST))
        result = close_sync.close_row_sync(
            client, payload, self.next_day, verify_import_tabs=False,
            allow_historical=True, preserve_existing=True, sleep=lambda _: None,
        )
        self.assertEqual(result["failedStage"], "HISTORY_SKIP")
        self.assertEqual(len(client.data), 1)

    def test_12_nikkei_vi_before_close_is_not_saved_as_close(self):
        market = {
            "id": "nikkei_vi", "verificationStatus": "verified", "value": 28.67,
            "asOf": "2026-10-09T10:13:00+09:00",
        }
        close_value, _, reason = close_sync.close_value_for_market(market, dt.date(2026, 10, 9))
        self.assertIsNone(close_value)
        self.assertIn("before the Japan cash-session close", reason)


    def test_us10y_exact_number_without_confirmed_lineage_is_still_conflict(self):
        market = {
            "value": 5.24,
            "sourceId": "us_treasury_yield_curve",
            "sourceSeriesId": "daily_treasury_yield_curve:BC_10YEAR",
            "observationDefinition": "Treasury 10-year constant-maturity par yield",
            "sessionCloseAt": "15:30 America/New_York",
            "unit": "%",
            "reportedDecimalPlaces": 2,
            "asOf": self.target.isoformat(),
        }
        decision = close_sync.reconcile_existing_us10y(5.24, self.target, market, None)
        self.assertEqual(decision["status"], "CONFLICT")
        self.assertEqual(decision["reason"], "EXISTING_PROVENANCE_UNAVAILABLE")

    def test_us10y_exact_value_requires_same_confirmed_series_and_cutoff(self):
        market = {
            "value": 5.24,
            "sourceId": "us_treasury_yield_curve",
            "sourceSeriesId": "daily_treasury_yield_curve:BC_10YEAR",
            "observationDefinition": "Treasury 10-year constant-maturity par yield",
            "sessionCloseAt": "15:30 America/New_York",
            "unit": "%",
            "reportedDecimalPlaces": 2,
            "asOf": self.target.isoformat(),
        }
        previous = {
            "sourceId": market["sourceId"],
            "sourceSeriesId": market["sourceSeriesId"],
            "observationDefinition": market["observationDefinition"],
            "sessionCloseAt": market["sessionCloseAt"],
            "unit": market["unit"],
            "reportedDecimalPlaces": 2,
            "storedValue": 5.24,
            "storedDecimalPlaces": 2,
            "lineageStatus": "CONFIRMED",
            "asOf": self.target.isoformat(),
        }
        decision = close_sync.reconcile_existing_us10y(5.24, self.target, market, previous)
        self.assertEqual(decision["status"], "EXACT_MATCH")
        self.assertEqual(decision["lineageStatus"], "CONFIRMED")
        self.assertTrue(decision["preserveExisting"])

    def test_us10y_rounding_match_requires_identical_lineage_and_preserves_precision(self):
        incoming = {
            "value": 5.24,
            "sourceId": "us_treasury_yield_curve",
            "sourceSeriesId": "daily_treasury_yield_curve:BC_10YEAR",
            "observationDefinition": "Treasury 10-year constant-maturity par yield",
            "sessionCloseAt": "15:30 America/New_York",
            "unit": "%",
            "reportedDecimalPlaces": 2,
            "asOf": self.target.isoformat(),
        }
        previous = {
            "sourceId": "us_treasury_yield_curve",
            "sourceSeriesId": "daily_treasury_yield_curve:BC_10YEAR",
            "observationDefinition": "Treasury 10-year constant-maturity par yield",
            "sessionCloseAt": "15:30 America/New_York",
            "unit": "%",
            "reportedDecimalPlaces": 3,
            "storedValue": 5.242,
            "storedDecimalPlaces": 3,
            "lineageStatus": "CONFIRMED",
            "asOf": self.target.isoformat(),
        }
        decision = close_sync.reconcile_existing_us10y(5.242, self.target, incoming, previous)
        self.assertEqual(decision["status"], "PRECISION_MATCH")
        self.assertTrue(decision["preserveExisting"])
        self.assertEqual(decision["sharedDecimalPlaces"], 2)

    def test_us10y_different_source_series_date_or_large_difference_conflicts(self):
        incoming = {
            "value": 5.24,
            "sourceId": "us_treasury_yield_curve",
            "sourceSeriesId": "daily_treasury_yield_curve:BC_10YEAR",
            "observationDefinition": "Treasury 10-year constant-maturity par yield",
            "sessionCloseAt": "15:30 America/New_York",
            "unit": "%",
            "reportedDecimalPlaces": 2,
            "asOf": self.target.isoformat(),
        }
        previous = {
            "sourceId": "us_treasury_yield_curve",
            "sourceSeriesId": "daily_treasury_yield_curve:BC_10YEAR",
            "observationDefinition": "Treasury 10-year constant-maturity par yield",
            "sessionCloseAt": "15:30 America/New_York",
            "unit": "%",
            "reportedDecimalPlaces": 3,
            "storedValue": 5.242,
            "storedDecimalPlaces": 3,
            "lineageStatus": "CONFIRMED",
            "asOf": self.target.isoformat(),
        }
        wrong_series = {**previous, "sourceSeriesId": "fred:DGS10"}
        self.assertEqual(close_sync.reconcile_existing_us10y(5.242, self.target, incoming, wrong_series)["status"], "CONFLICT")
        wrong_date = {**previous, "asOf": "2026-09-29"}
        self.assertEqual(close_sync.reconcile_existing_us10y(5.242, self.target, incoming, wrong_date)["status"], "CONFLICT")
        far_value = {**incoming, "value": 5.25}
        self.assertEqual(close_sync.reconcile_existing_us10y(5.242, self.target, far_value, previous)["status"], "CONFLICT")
        self.assertEqual(close_sync.reconcile_existing_us10y(5.242, self.target, incoming, None)["status"], "CONFLICT")

    def test_us10y_empty_cell_is_written_and_existing_unknown_value_stops_row_write(self):
        incoming = {
            "value": 5.24,
            "sourceId": "us_treasury_yield_curve",
            "sourceSeriesId": "daily_treasury_yield_curve:BC_10YEAR",
            "observationDefinition": "Treasury 10-year constant-maturity par yield",
            "sessionCloseAt": "15:30 America/New_York",
            "unit": "%",
            "reportedDecimalPlaces": 2,
            "asOf": self.target.isoformat(),
        }
        self.assertEqual(close_sync.reconcile_existing_us10y("", self.target, incoming, None)["status"], "WRITE")

        client = FakeSheetsClient(self.target, self.prior)
        client.data[1][col_number("AR")] = 5.242
        payload = snapshot(self.target, self.next_day)
        payload["markets"]["us10y"].update(incoming)
        result = self.run_sync(client, payload)
        self.assertEqual(result["failedStage"], "VALIDATE")
        self.assertEqual(client.data[1][col_number("AR")], 5.242)
        self.assertEqual(client.data[1][col_number("B")], "")
        self.assertEqual(result["reconciliations"][0]["status"], "CONFLICT")

    def test_us10y_rounding_match_logs_precision_status_and_keeps_stored_value(self):
        client = FakeSheetsClient(self.target, self.prior)
        client.data[1][col_number("AR")] = 5.242
        prior_record = {
            "symbol": "us10y",
            "sourceId": "us_treasury_yield_curve",
            "sourceSeriesId": "daily_treasury_yield_curve:BC_10YEAR",
            "observationDefinition": "Treasury 10-year constant-maturity par yield",
            "sessionCloseAt": "15:30 America/New_York",
            "unit": "%",
            "reportedDecimalPlaces": 3,
            "storedValue": 5.242,
            "storedDecimalPlaces": 3,
            "lineageStatus": "CONFIRMED",
            "asOf": self.target.isoformat(),
        }
        note = json.dumps({"marketData": [prior_record]}, ensure_ascii=False)
        client.log.append(["2026/10/01", "終値一覧", "saved", self.target.isoformat(), "1", "完了", "Treasury", note])
        payload = snapshot(self.target, self.next_day)
        payload["markets"]["us10y"].update({
            "value": 5.24,
            "sourceId": "us_treasury_yield_curve",
            "sourceSeriesId": "daily_treasury_yield_curve:BC_10YEAR",
            "observationDefinition": "Treasury 10-year constant-maturity par yield",
            "sessionCloseAt": "15:30 America/New_York",
            "unit": "%",
            "reportedDecimalPlaces": 2,
            "asOf": dt.datetime.combine(self.target, dt.time(15, 30), JST).isoformat(),
        })
        result = self.run_sync(client, payload)
        self.assertEqual(result["reconciliations"][0]["status"], "PRECISION_MATCH")
        self.assertEqual(client.data[1][col_number("AR")], 5.242)
        saved = json.loads(client.log[-1][7])["marketData"]
        us10y = next(item for item in saved if item["symbol"] == "us10y")
        self.assertEqual(us10y["storedValue"], 5.242)
        self.assertEqual(us10y["reconciliationStatus"], "PRECISION_MATCH")


    def test_index_based_valuation_is_not_mixed_into_weighted_average_close_columns(self):
        client = FakeSheetsClient(self.target, self.prior)
        payload = snapshot(self.target, self.next_day)
        payload["markets"]["tse_prime_turnover"]["verificationStatus"] = "reference_only"
        result = self.run_sync(client, payload)
        row = client.data[result["row"] - 1]
        for header in ("日経225予想EPS", "日経225予想PER", "日経225予想PBR"):
            self.assertTrue(str(row[client.headers.index(header)]).startswith("取得不能（"))
        self.assertEqual(row[client.headers.index("東証プライム値上がり銘柄数")], 1194)
        self.assertEqual(row[client.headers.index("東証プライム値下がり銘柄数")], 331)
        self.assertTrue(str(row[client.headers.index("東証プライム売買代金")]).startswith("取得不能（"))
        self.assertEqual(row[client.headers.index("東証プライム売買高")], 2295.19)
        valuation_symbols = {"nikkei225_eps", "nikkei225_per", "nikkei225_pbr"}
        valuation = {item["symbol"]: item for item in result["marketData"] if item["symbol"] in valuation_symbols}
        self.assertEqual(set(valuation), {"nikkei225_eps", "nikkei225_per", "nikkei225_pbr"})
        self.assertEqual(valuation["nikkei225_per"]["reconciliationStatus"], "DEFINITION_MISMATCH")
        self.assertEqual(valuation["nikkei225_pbr"]["reconciliationStatus"], "DEFINITION_MISMATCH")
        self.assertEqual(valuation["nikkei225_eps"]["reconciliationStatus"], "DEFINITION_PENDING")
        saved_symbols = {item["symbol"] for item in result["marketData"]}
        self.assertIn("tse_prime_advancers", saved_symbols)
        self.assertNotIn("tse_prime_turnover", saved_symbols)

    def test_weighted_average_per_pbr_are_eligible_but_eps_stays_blocked(self):
        client = FakeSheetsClient(self.target, self.prior)
        payload = snapshot(self.target, self.next_day)
        for symbol in ("nikkei225_per", "nikkei225_pbr"):
            payload["markets"][symbol]["valuationBasis"] = "weighted_average"
        result = self.run_sync(client, payload)
        row = client.data[result["row"] - 1]
        self.assertEqual(row[client.headers.index("日経225予想PER")], 22.87)
        self.assertEqual(row[client.headers.index("日経225予想PBR")], 2.83)
        self.assertTrue(str(row[client.headers.index("日経225予想EPS")]).startswith("取得不能（"))
        self.assertNotIn("nikkei225_eps", {item["symbol"] for item in result["marketData"] if item.get("valueSource") == "value"})

    def test_fx_existing_value_requires_same_confirmed_series_and_cutoff(self):
        incoming = {
            "value": 158.34,
            "sourceId": "boJ_reference",
            "sourceSeriesId": "boj:17h_mid",
            "observationDefinition": "Tokyo 17:00 bid/ask midpoint",
            "sessionCloseAt": "17:00 Asia/Tokyo",
            "unit": "JPY per USD",
            "reportedDecimalPlaces": 2,
            "asOf": self.target.isoformat(),
        }
        previous = {
            **incoming,
            "storedValue": 158.34,
            "valueDate": self.target.isoformat(),
            "lineageStatus": "CONFIRMED",
        }
        self.assertEqual(
            close_sync.reconcile_existing_fx(158.34, self.target, incoming, previous)["status"],
            "EXACT_MATCH",
        )
        other_cutoff = {**incoming, "sessionCloseAt": "17:00 America/New_York"}
        self.assertEqual(
            close_sync.reconcile_existing_fx(158.34, self.target, other_cutoff, previous)["status"],
            "CONFLICT",
        )
        self.assertEqual(
            close_sync.reconcile_existing_fx(158.34, self.target, incoming, None)["reason"],
            "EXISTING_PROVENANCE_UNAVAILABLE",
        )

    def test_fx_missing_cutoff_lineage_is_not_written_and_is_audited(self):
        client = FakeSheetsClient(self.target, self.prior)
        payload = snapshot(self.target, self.next_day)
        payload["markets"]["usdjpy"].pop("sessionCloseAt")
        result = self.run_sync(client, payload)
        row = client.data[result["row"] - 1]
        self.assertTrue(str(row[client.headers.index("USDJPY終値")]).startswith("取得不能（"))
        item = next(entry for entry in result["marketData"] if entry["symbol"] == "usdjpy")
        self.assertEqual(item["reconciliationStatus"], "DEFINITION_PENDING")
        self.assertIn("sourceSeriesId", item)
        self.assertEqual(item["observationDefinition"], "Synthetic daily spot bar close")
        self.assertEqual(
            next(entry for entry in result["reconciliations"] if entry["symbol"] == "usdjpy")["status"],
            "DEFINITION_PENDING",
        )

    def test_verified_supplemental_conflict_stops_before_any_row_write(self):
        client = FakeSheetsClient(self.target, self.prior)
        volume_column = client.headers.index(close_sync.SUPPLEMENTAL_FIELDS["tse_prime_volume"])
        client.data[1][volume_column] = 2000.0
        payload = snapshot(self.target, self.next_day)
        result = self.run_sync(client, payload)
        self.assertEqual(result["status"], "FAILED")
        self.assertEqual(result["failedStage"], "VALIDATE")
        self.assertEqual(client.data[1][volume_column], 2000.0)
        self.assertEqual(client.data[1][client.headers.index("Dow終値")], "")


if __name__ == "__main__":
    unittest.main()


