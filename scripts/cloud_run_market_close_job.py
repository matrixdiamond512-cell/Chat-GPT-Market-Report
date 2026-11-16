#!/usr/bin/env python3
"""TEST_ONLY Cloud Run Job for market acquisition and isolated close-row sync."""
from __future__ import annotations

import datetime as dt
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
WORK = ROOT / "work"
JST = dt.timezone(dt.timedelta(hours=9))
ALLOWED_PROJECT = "market-report-test-only"
EVIDENCE_BUCKET = "MARKET_CLOSE_TEST_ONLY_EVIDENCE_BUCKET"
TEST_ONLY_SPREADSHEET_ID = "1C0U7JXZT7DMDvDSL8Ah9uVfLhncnCOffIgKl3n8Hk-w"
PERSISTENCE_STAGES = ("SHEETS_IMPORT", "CHATGPT_INPUT", "CLOSE_DATA_WRITE", "READBACK_VERIFY")


def classify_sync_result(
    return_code: int, summary: dict[str, Any], *, allow_skipped_imports: bool = False
) -> dict[str, Any]:
    """Keep market completeness separate from Sheets persistence success."""
    stages = summary.get("stages") if isinstance(summary.get("stages"), dict) else {}
    import_stages = {"SHEETS_IMPORT", "CHATGPT_INPUT"}
    failed = [
        stage for stage in PERSISTENCE_STAGES
        if stages.get(stage) != "SUCCESS"
        and not (allow_skipped_imports and stage in import_stages and stages.get(stage) == "SKIPPED")
    ]
    data_status = summary.get("status")
    return {
        "marketDataStatus": data_status if data_status in {"SUCCESS", "PARTIAL"} else "FAILED",
        "sheetsPersistenceStatus": "SUCCESS" if not failed else "FAILED",
        "failedPersistenceStages": failed,
        "syncReturnCode": return_code,
    }


def finalize_market_snapshot(snapshot_path: Path, now: dt.datetime, *, late_manual: bool) -> dict[str, Any]:
    """Stamp the completed snapshot with its actual generation time and mode."""
    snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))
    snapshot["generatedAt"] = now.astimezone(JST).replace(microsecond=0).isoformat()
    if late_manual:
        snapshot["cutoffStatus"] = "MISSED_MANUAL_TEST_ONLY"
        snapshot["acquisitionMode"] = "TEST_ONLY-MANUAL-LATE"
    snapshot_path.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return snapshot


def _required_env(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise RuntimeError(f"required environment variable {name} is missing")
    return value


def _run(
    script: str, *args: str, env: dict[str, str] | None = None, check: bool = True
) -> subprocess.CompletedProcess[str]:
    process_env = os.environ.copy()
    if env:
        process_env.update(env)
    return subprocess.run(
        [sys.executable, str(ROOT / "scripts" / script), *args],
        cwd=ROOT, env=process_env, check=check, text=True, capture_output=True,
    )


def merge_verified_28_rows_into_close_snapshot() -> dict[str, Any]:
    """Expose only exact-date verified report rows to the existing close writer."""
    contract = __import__("build_chatgpt_report_input")
    snapshot_path = ROOT / "data" / "market" / "latest.json"
    input_path = ROOT / "data" / "market" / "chatgpt-input.json"
    snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))
    market_input = json.loads(input_path.read_text(encoding="utf-8"))
    markets = snapshot.setdefault("markets", {})
    symbols = {
        "nikkei225_cash": "nikkei225",
    }
    for _, symbol_id, _, market_type, session in contract.ITEMS:
        item = (market_input.get("markets") or {}).get(symbol_id) or {}
        expected_date = str(item.get("expectedSessionDate") or "")
        if (
            item.get("verificationStatus") != "verified"
            or not expected_date
            or item.get("asOf") != expected_date
            or not item.get("sourceName")
            or not item.get("sourceUrl")
        ):
            continue
        market_id = symbols.get(symbol_id, symbol_id)
        markets[market_id] = {
            "id": market_id,
            "value": item.get("value"),
            "previousClose": item.get("previousClose"),
            "change": item.get("change"),
            "changePercent": item.get("changePercent"),
            "asOf": expected_date,
            "sessionDate": expected_date,
            "expectedSessionDate": expected_date,
            "fetchedAt": item.get("fetchedAt"),
            "sourceId": item.get("sourceId"),
            "sourceName": item.get("sourceName"),
            "sourceUrl": item.get("sourceUrl"),
            "marketType": market_type,
            "session": session,
            "verificationStatus": "verified",
            "fallbackUsed": False,
            "classification": item.get("classification") or "",
        }
    snapshot["reportDate"] = market_input.get("reportDate")
    snapshot["reportSlot"] = "08:00"
    snapshot_path.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return snapshot


def _run_optional(script: str, *args: str) -> dict[str, Any]:
    result = _run(script, *args, check=False)
    return {
        "status": "SUCCESS" if result.returncode == 0 else "FAILED",
        "returnCode": result.returncode,
        "stdout": result.stdout[-8000:],
        "stderr": result.stderr[-4000:],
    }


def run() -> dict[str, Any]:
    project_id = _required_env("GOOGLE_CLOUD_PROJECT")
    if project_id != ALLOWED_PROJECT:
        raise RuntimeError(f"Cloud Run acquisition is TEST_ONLY; project must be {ALLOWED_PROJECT}")
    if os.environ.get("MARKET_CLOSE_ENVIRONMENT") != "TEST_ONLY":
        raise RuntimeError("MARKET_CLOSE_ENVIRONMENT must equal TEST_ONLY")
    bucket = _required_env(EVIDENCE_BUCKET)
    if not bucket.startswith("market-report-test-only-"):
        raise RuntimeError("evidence bucket must be a dedicated TEST_ONLY bucket")

    report_date = os.environ.get("MARKET_CLOSE_REPORT_DATE", dt.datetime.now(JST).date().isoformat())
    selected_date = dt.date.fromisoformat(report_date)
    if selected_date != dt.datetime.now(JST).date():
        raise RuntimeError("TEST_ONLY Cloud Run acquisition is restricted to the current JST report date")
    input_path = Path(os.environ.get(
        "MARKET_CLOSE_TEST_ONLY_INPUT_JSON",
        str(ROOT / "config" / "test_only_morning_report_template.json"),
    ))
    if not input_path.is_file():
        raise RuntimeError("TEST_ONLY input report JSON does not exist")
    template_text = input_path.read_text(encoding="utf-8")
    report_payload = json.loads(template_text.replace("{{REPORT_DATE}}", report_date))
    report = report_payload.get("latestReport") or report_payload.get("report") or report_payload
    if not isinstance(report, dict) or report.get("date") != report_date or report.get("time") != "08:00":
        raise RuntimeError("TEST_ONLY input JSON must be a matching 08:00 report with 28 rows")
    rows = ((report.get("marketDataTable") or {}).get("rows") or [])
    if len(rows) != 28:
        raise RuntimeError("TEST_ONLY input JSON must contain the canonical 28 market rows")
    report_path = ROOT / "data" / "latest-report.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report_payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    WORK.mkdir(parents=True, exist_ok=True)
    market_latest = ROOT / "data" / "market" / "latest.json"
    market_input = {"reportDate": report_date, "reportSlot": "08:00", "markets": {}}
    if market_latest.is_file():
        prior_market = json.loads(market_latest.read_text(encoding="utf-8"))
        if prior_market.get("reportDate") == report_date and prior_market.get("reportSlot") == "08:00":
            market_input["markets"] = prior_market.get("markets") or {}
    market_input_path = WORK / "market-input.json"
    market_output_path = ROOT / "data" / "market" / "morning-reference.json"
    market_output_path.parent.mkdir(parents=True, exist_ok=True)
    market_input_path.write_text(json.dumps(market_input, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    run_id = os.environ.get("CLOUD_RUN_EXECUTION", "manual")
    late_manual = os.environ.get("MARKET_CLOSE_TEST_ONLY_LATE_RUN") == "1"
    idempotency_key = f"{report_date}:08:00" + (":TEST_ONLY-MANUAL-LATE" if late_manual else "")
    evidence_key = f"{report_date}-08-00-{run_id}" + ("-manual-late" if late_manual else "")

    # Collector stages write to the disposable container filesystem only.
    from repair_morning_daily_references import expected_prior_session
    expected_japan_session = expected_prior_session(dt.date.fromisoformat(report_date), "日経225現物").isoformat()
    japan_session_date = os.environ.get("MARKET_CLOSE_JAPAN_SESSION_DATE", expected_japan_session)
    if japan_session_date != expected_japan_session:
        raise RuntimeError(f"Japan session override {japan_session_date} does not match expected {expected_japan_session}")
    # Late manual validation is explicitly separated from the scheduled cutoff.
    late_manual = os.environ.get("MARKET_CLOSE_TEST_ONLY_LATE_RUN") == "1"
    if late_manual:
        if project_id != ALLOWED_PROJECT or os.environ.get("MARKET_CLOSE_ENVIRONMENT") != "TEST_ONLY":
            raise RuntimeError("late manual mode is restricted to the TEST_ONLY project")
        market_input["markets"] = {}
        market_latest.parent.mkdir(parents=True, exist_ok=True)
        market_latest.write_text(json.dumps(market_input, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    else:
        _run("run_market_data_acquisition.py", "--slot", "08:00", "--mode", "full", "--print-summary")
    japan_capture = _run_optional("capture_japan_close_reference.py", "--date", japan_session_date)
    morning_capture = _run_optional("fetch_morning_reference.py", "--report-date", report_date, "--slot", "08:00", "--input-path", str(market_input_path), "--output-path", str(market_output_path))
    rates_capture = _run_optional("build_rates_bonds_json.py")
    _run("repair_morning_daily_references.py")
    _run("apply_japan_close_reference.py")
    merge_verified_28_rows_into_close_snapshot()
    close_snapshot = finalize_market_snapshot(market_latest, dt.datetime.now(JST), late_manual=late_manual)
    report_payload_after_repair = json.loads((ROOT / "data" / "latest-report.json").read_text(encoding="utf-8"))
    report_after_repair = report_payload_after_repair.get("latestReport") or report_payload_after_repair.get("report") or report_payload_after_repair
    report_table = report_after_repair.get("marketDataTable") or {}
    report_table_date = report_table.get("dataDate") or report_after_repair.get("dataProvenance", {}).get("closeSheet", {}).get("dataDate")
    # A report is dated by its issue date; the close row is dated by the
    # verified market-session anchor. Do not compare those two dates.
    try:
        import sync_market_close_sheet as close_sync_module
        close_target_date = close_sync_module.resolve_target_date(close_snapshot, dt.datetime.now(JST))
        close_target_date_text = close_target_date.isoformat()
    except Exception:
        close_target_date_text = None
    close_sync_path = WORK / "close-sync-status.json"
    late_manual = os.environ.get("MARKET_CLOSE_TEST_ONLY_LATE_RUN") == "1"
    idempotency_key = f"{report_date}:08:00" + (":TEST_ONLY-MANUAL-LATE" if late_manual else "")
    sync_args = [
        "--latest", str(ROOT / "data" / "market" / "latest.json"),
        "--scheduled-time", "TEST_ONLY-MANUAL-LATE" if late_manual else "07:50",
        "--run-key", idempotency_key,
        "--status-output", str(close_sync_path),
        "--test-only-adc",
    ]
    if late_manual:
        # Manual-late mode validates this job's own TEST_ONLY write/readback;
        # copied IMPORTDATA tabs are not evidence for this fresh snapshot.
        sync_args.append("--skip-import-check")
    close_sync = _run(
        "sync_market_close_sheet.py",
        *sync_args,
        env={"MARKET_DATA_SPREADSHEET_ID": TEST_ONLY_SPREADSHEET_ID},
        check=False,
    )
    close_sync_status = json.loads(close_sync_path.read_text(encoding="utf-8")) if close_sync_path.is_file() else {}
    repaired_payload = json.loads((ROOT / "data" / "latest-report.json").read_text(encoding="utf-8"))
    repaired_report = repaired_payload.get("latestReport") or repaired_payload.get("report") or repaired_payload
    if not isinstance(repaired_report, dict):
        raise RuntimeError("repaired 08:00 report JSON is invalid")
    evidence_rows = repaired_report.get("dataProvenance", {}).get("dailyCloseRepair", {}).get("items", {})
    if len(evidence_rows) != 28:
        raise RuntimeError("close acquisition did not produce a full 28-row audit map")

    completed_market_input = {
        "reportDate": report_date,
        "reportSlot": "08:00",
        "markets": json.loads((ROOT / "data" / "market" / "latest.json").read_text(encoding="utf-8")).get("markets", {})
        if (ROOT / "data" / "market" / "latest.json").is_file() else {},
    }
    market_input_path.write_text(json.dumps(completed_market_input, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    _run("fetch_morning_reference.py", "--report-date", report_date, "--slot", "08:00", "--input-path", str(market_input_path), "--output-path", str(market_output_path))
    morning_reference = json.loads(market_output_path.read_text(encoding="utf-8")) if market_output_path.is_file() else {"items": {}}

    coverage_unavailable = repaired_report.get("dataProvenance", {}).get("dailyCloseRepair", {}).get("unavailable", {})
    sync_classification = classify_sync_result(close_sync.returncode, close_sync_status, allow_skipped_imports=late_manual)
    status = "verified" if not coverage_unavailable and sync_classification["marketDataStatus"] == "SUCCESS" and sync_classification["sheetsPersistenceStatus"] == "SUCCESS" else "partial"
    evidence = {
        "projectId": project_id,
        "environment": "TEST_ONLY",
        "reportDate": report_date,
        "reportSlot": "08:00",
        "evidenceBucket": bucket,
        "testOnlySpreadsheetId": TEST_ONLY_SPREADSHEET_ID,
        "idempotencyKey": idempotency_key,
        "overallStatus": status,
        **sync_classification,
        "cutoffStatus": "MISSED_MANUAL_TEST_ONLY" if late_manual else "SCHEDULED_CUTOFF_ENFORCED",
        "marketCount": sum(1 for item in evidence_rows.values() if item.get("dataDate") and item.get("status") != "unavailable"),
        "verifiedCount": sum(1 for item in evidence_rows.values() if item.get("dataDate") and item.get("status") == "verified"),
        "unavailableCount": len(coverage_unavailable),
        "rowCount": len(evidence_rows),
        "dataDateByLabel": {label: item.get("dataDate") for label, item in evidence_rows.items()},
        "expectedSessionDateByLabel": {
            label: item.get("expectedSessionDate")
            for label, item in ((repaired_report.get("dataProvenance", {}).get("morningCoverage", {}).get("items") or {}).items())
        },
        "sheetCloseTargetDate": close_target_date_text,
        "reportTableDataDate": report_table_date,
        "sourceByLabel": {label: item.get("source") or item.get("sourceName") for label, item in evidence_rows.items()},
        "unavailable": repaired_report.get("dataProvenance", {}).get("dailyCloseRepair", {}).get("unavailable", {}),
        "inputJsonSha256": __import__("hashlib").sha256(input_path.read_bytes()).hexdigest(),
        "outputJsonSha256": __import__("hashlib").sha256((ROOT / "data" / "latest-report.json").read_bytes()).hexdigest(),
        "coverage": repaired_report.get("dataProvenance", {}).get("morningCoverage"),
        "futuresReference": morning_reference.get("items", {}),
        "collectorStages": {
            "japanClose": japan_capture,
            "morningFutures": morning_capture,
            "rates": rates_capture,
        },
        "sheetsWrite": close_sync_status.get("stages", {}).get("CLOSE_DATA_WRITE", "UNKNOWN"),
        "sheetsReadback": close_sync_status.get("stages", {}).get("READBACK_VERIFY", "UNKNOWN"),
        "sheetsSyncStatus": close_sync_status,
        "sheetsSyncStdout": close_sync.stdout[-12000:],
        "sheetsSyncStderr": close_sync.stderr[-4000:],
        "publisher": "NOT_RUN",
        "timestamp": dt.datetime.now(JST).isoformat(),
    }
    evidence_path = ROOT / "logs" / "close-acquisition" / f"{report_date}-08-00-{run_id}{'-manual-late' if late_manual else ''}.json"
    evidence_path.parent.mkdir(parents=True, exist_ok=True)
    evidence_path.write_text(json.dumps(evidence, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    # Upload a create-only object. GCS object generation preconditions prevent
    # a retry from overwriting evidence for the same key.
    evidence_write = _run("write_test_only_close_evidence.py", str(evidence_path), bucket, evidence_key)
    evidence["evidenceObject"] = f"gs://{bucket}/close-acquisition/{evidence_key}.json"
    import re
    match = re.search(r"generation=(\d+) sha256=([0-9a-f]{64})", evidence_write.stdout)
    if not match:
        raise RuntimeError("TEST_ONLY GCS evidence writer did not return generation-pinned readback proof")
    evidence["evidenceObjectGeneration"] = int(match.group(1))
    evidence["evidenceObjectSha256"] = match.group(2)
    if sync_classification["sheetsPersistenceStatus"] != "SUCCESS":
        raise RuntimeError(
            "TEST_ONLY Sheets persistence failed at "
            + ", ".join(sync_classification["failedPersistenceStages"])
            + f"; evidence object generation {evidence['evidenceObjectGeneration']} was preserved"
        )
    return evidence


def main() -> int:
    try:
        result = run()
    except Exception as exc:
        print(json.dumps({"status": "FAILED", "error": f"{type(exc).__name__}: {exc}"}, ensure_ascii=False))
        return 1
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
