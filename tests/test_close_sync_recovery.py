from __future__ import annotations

import datetime as dt
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch
from urllib.parse import parse_qs, unquote, urlparse

from scripts import sync_market_close_sheet as sync
from scripts import run_market_data_window as window
from scripts.write_market_data_to_sheets import SheetsClient
from tests.test_sync_market_close_sheet import FakeSheetsClient, snapshot, populate_import_tabs


class RangeTransportTests(unittest.TestCase):
    def setUp(self):
        self.session = Mock()
        self.session.request.return_value = SimpleNamespace(ok=True, content=b"{}", json=lambda: {})
        self.client = SheetsClient(self.session, "fixture")
        self.sheet = "終値 John's %20"

    def test_url_path_decodes_exactly_once_to_literal_a1(self):
        self.client.get_values(self.sheet, "A1:B2")
        url = self.session.request.call_args.args[1]
        self.assertEqual(unquote(urlparse(url).path.split("/values/")[1]), "'終値 John''s %20'!A1:B2")

    def test_json_range_is_literal_and_not_url_encoded(self):
        sync.batch_write_values(self.client, self.sheet, 3, {185: 123})
        body = self.session.request.call_args.kwargs["json"]
        self.assertEqual(body["data"][0]["range"], "'終値 John''s %20'!GD3")

    def test_query_range_decodes_exactly_once(self):
        sync.read_many_columns(self.client, self.sheet, [], {"日付": 0})
        url = self.session.request.call_args.args[1]
        self.assertEqual(parse_qs(urlparse(url).query)["ranges"], ["'終値 John''s %20'!A:A"])

    def test_url_update_and_append_keep_original_transport_contract(self):
        for operation in (self.client.update, self.client.append):
            operation(self.sheet, "A1", [[1]])
            url = self.session.request.call_args.args[1]
            path = unquote(urlparse(url).path)
            self.assertIn("'終値 John''s %20'!A1", path)


class FailureStatusTests(unittest.TestCase):
    def test_upstream_failure_makes_no_sheet_request_or_stale_payload_read(self):
        with TemporaryDirectory() as tmp:
            output = Path(tmp) / "status.json"
            upstream = Path(tmp) / "window.json"
            upstream.write_text(json.dumps({"failureCode": "ACQUISITION_EXPIRED"}))
            with patch.object(sync.sys, "argv", ["sync", "--upstream-outcome", "failure", "--window-status", str(upstream), "--latest", "does-not-exist", "--status-output", str(output)]), patch.object(sync, "SheetsClient") as client:
                self.assertEqual(sync.main(), 1)
            client.assert_not_called()
            result = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(result["failureCode"], "ACQUISITION_EXPIRED")
            self.assertEqual(result["stages"]["FETCH"], "NOT_RUN")
            self.assertEqual(result["stages"]["CLOSE_DATA_WRITE"], "NOT_RUN")
            self.assertEqual(result["stages"]["READBACK_VERIFY"], "NOT_RUN")

    def test_evidence_failure_does_not_relabel_successful_fetch(self):
        with TemporaryDirectory() as tmp:
            output = Path(tmp) / "status.json"
            upstream = Path(tmp) / "window.json"
            upstream.write_text(json.dumps({"failureCode": "EVIDENCE_BLOCKED", "acquisitionStatus": "READY"}))
            with patch.object(sync.sys, "argv", ["sync", "--upstream-outcome", "failure", "--window-status", str(upstream), "--status-output", str(output)]), patch.object(sync, "SheetsClient") as client:
                self.assertEqual(sync.main(), 1)
            client.assert_not_called()
            result = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(result["stages"]["FETCH"], "SUCCESS")
            self.assertEqual(result["stages"]["CLOSE_DATA_WRITE"], "NOT_RUN")
            self.assertEqual(result["failureCode"], "EVIDENCE_BLOCKED")

    def test_missing_credentials_are_auth_failure(self):
        with TemporaryDirectory() as tmp:
            output = Path(tmp) / "probe.json"
            with patch.object(sync.sys, "argv", ["sync", "--permission-probe", "--status-output", str(output)]), patch.dict(sync.os.environ, {"GOOGLE_SERVICE_ACCOUNT_JSON": ""}):
                self.assertEqual(sync.main(), 1)
            result = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(result["failureCode"], "AUTH_FAILED")
            self.assertEqual(result["stages"]["CLOSE_DATA_WRITE"], "NOT_RUN")

    def run_sync(self, client):
        now = dt.datetime(2026, 10, 1, 6, 35, tzinfo=sync.JST)
        payload = snapshot(dt.date(2026, 9, 30), now)
        populate_import_tabs(client, payload)
        return sync.close_row_sync(client, payload, now, sleep=lambda _: None)

    def test_readback_http_error_is_not_mislabelled_as_write_failure(self):
        client = FakeSheetsClient(dt.date(2026, 9, 30))
        original = sync.read_values
        def read(client, sheet, cells, option="FORMATTED_VALUE"):
            if sheet == "終値一覧" and cells == "A2:GD2" and option == "UNFORMATTED_VALUE":
                raise sync.SheetsSyncError("HTTP 503")
            return original(client, sheet, cells, option)
        with patch.object(sync, "read_values", side_effect=read):
            result = self.run_sync(client)
        self.assertEqual(result["failureCode"], "READBACK_FAILED")
        self.assertEqual(result["stages"]["CLOSE_DATA_WRITE"], "SUCCESS")

    def test_log_failure_preserves_primary_write_failure(self):
        client = FakeSheetsClient(dt.date(2026, 9, 30), write_failure=True)
        with patch.object(sync, "append_update_log", side_effect=sync.SheetsSyncError("HTTP 403 log")):
            result = self.run_sync(client)
        self.assertEqual(result["failureCode"], "WRITE_FAILED")
        self.assertEqual(result["stages"]["LOG"], "FAILED")
        self.assertEqual(result["stages"]["READBACK_VERIFY"], "NOT_RUN")

    def test_duplicate_target_dates_are_rejected_without_writes(self):
        client = FakeSheetsClient(dt.date(2026, 9, 30), dt.date(2026, 9, 30))
        before = [row[:] for row in client.data]
        result = self.run_sync(client)
        self.assertEqual(result["failureCode"], "VALIDATION_FAILED")
        self.assertEqual(client.data, before)

    def test_unsorted_dates_find_existing_target(self):
        target = dt.date(2026, 9, 30)
        self.assertEqual(sync.find_target_row(["日付", "2026/10/01", "2026/06/05", "2026/09/30"], target)[0], 4)

    def test_window_unhandled_failure_still_writes_current_diagnostic(self):
        with TemporaryDirectory() as tmp:
            output = Path(tmp) / "window.json"
            with patch.object(window.sys, "argv", ["window", "--slot", "08:00", "--times", "07:50", "--status-output", str(output)]), patch.object(window, "run_window", side_effect=OSError("git unavailable")):
                self.assertEqual(window.main(), 1)
            result = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(result["failureCode"], "WINDOW_FAILED")
            self.assertFalse(result["reportReady"])

    def test_late_start_remains_expired_without_fetch_or_retroactive_evidence(self):
        late = dt.datetime(2026, 11, 13, 11, 55, tzinfo=window.JST)
        with TemporaryDirectory() as tmp, patch.object(window, "ROOT", Path(tmp)), patch.object(window, "now_jst", return_value=late), patch.object(window, "run"), patch.object(window, "git_sync"), patch.object(window, "completed_times", return_value=set()), patch.object(window, "record_expired") as expired, patch.object(window, "record_evidence_readback"), patch.object(window, "perform_attempt") as fetch, patch.object(window, "freeze_slot_evidence") as freeze:
            args = SimpleNamespace(slot="08:00", times=["07:50"], trigger_source="test", max_catchup_minutes=180, mode="auto", recover_expired=True)
            code, result = window.run_window(args)
        self.assertEqual(code, 1)
        self.assertEqual(result["failureCode"], "ACQUISITION_EXPIRED")
        expired.assert_called_once()
        fetch.assert_not_called()
        freeze.assert_not_called()


class ProbeTests(unittest.TestCase):
    def client(self, *, write_error=False, read_error=False, delete_error=False):
        client = Mock()
        client.base_url = "https://fixture"
        client._range.side_effect = SheetsClient._range
        client.sheet_map.return_value = {"終値一覧": 1}
        def request(method, url, **kwargs):
            body = kwargs.get("json", {})
            if "addSheet" in body.get("requests", [{}])[0]:
                return {"replies": [{"addSheet": {"properties": {"sheetId": 12345}}}]}
            if url.endswith("/values:batchUpdate"):
                if write_error:
                    raise sync.SheetsSyncError("HTTP 403")
                client.probe_values = [entry["values"][0][0] for entry in body["data"]]
            if method == "GET":
                if read_error:
                    raise sync.SheetsSyncError("HTTP 403")
                return {"values": [client.probe_values]}
            if "deleteSheet" in body.get("requests", [{}])[0] and delete_error:
                raise sync.SheetsSyncError("HTTP 403 delete")
            return {}
        client._request.side_effect = request
        return client

    def test_success_deletes_only_created_tab_and_reads_back_deletion(self):
        client = self.client()
        result = sync.permission_probe(client)
        self.assertEqual(result["status"], "SUCCESS")
        self.assertEqual(result["cleanup"], "SUCCESS")
        client.sheet_map.assert_called_once()
        requests = [c.kwargs.get("json", {}).get("requests") for c in client._request.call_args_list]
        self.assertIn([{"deleteSheet": {"sheetId": 12345}}], requests)
        self.assertEqual(result["reportCellsModified"], 0)

    def test_write_denied_still_cleans_up(self):
        result = sync.permission_probe(self.client(write_error=True))
        self.assertEqual(result["failureCode"], "WRITE_FAILED")
        self.assertEqual(result["cleanup"], "SUCCESS")

    def test_read_denied_is_readback_failure(self):
        result = sync.permission_probe(self.client(read_error=True))
        self.assertEqual(result["failureCode"], "READBACK_FAILED")
        self.assertEqual(result["cleanup"], "SUCCESS")

    def test_cleanup_denied_cannot_be_success(self):
        result = sync.permission_probe(self.client(delete_error=True))
        self.assertEqual(result["status"], "FAILED")
        self.assertEqual(result["cleanup"], "FAILED")


if __name__ == "__main__":
    unittest.main()
