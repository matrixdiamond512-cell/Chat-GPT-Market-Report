from __future__ import annotations

import datetime as dt
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
        self.data = [self.headers]
        if target is not None:
            self.data.append(self._row(target))
        if prior is not None:
            old = self._row(prior)
            self.data.append(old)
        self.import_rows = []
        self.log = [LOG_HEADERS]

    def _row(self, date: dt.date) -> list[object]:
        row: list[object] = [""] * 186
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
        markets[symbol] = {
            "value": 100.0, "previousClose": 99.0, "change": 1.0,
            "changePercent": 1.0 / 99 * 100, "asOf": dt.datetime.combine(target, dt.time(15, 0), JST).isoformat(),
            "fetchedAt": now.isoformat(), "sourceId": symbol + "_source", "sourceName": symbol + " source",
            "verificationStatus": "verified", "classification": "Neutral",
        }
    return {"generatedAt": now.isoformat(), "reportSlot": "08:00", "overallStatus": "verified", "missingRequired": [], "markets": markets}


def populate_import_tabs(client: FakeSheetsClient, payload: dict) -> None:
    headers = list(INPUT_HEADERS)
    client.import_rows = [headers]
    generated = payload["generatedAt"]
    for symbol, market in payload["markets"].items():
        client.import_rows.append([f"{generated}|{symbol}", generated, "08:00", "verified", symbol, symbol, "使用可", market.get("value")])


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
        self.assertTrue(client.data[1][25] in ("", None))
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
        with patch.object(close_sync, "REQUIRED_CLOSE_HEADERS", tuple(fields)):
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


if __name__ == "__main__":
    unittest.main()

