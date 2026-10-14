"""D1 offline/fake-data tests. Never connect to OpenAI or publication targets."""
import copy
from datetime import datetime
import unittest

from scripts.reporting.context import ReportContext
from scripts.reporting.snapshot import Market, MarketDataSnapshot
from scripts.reporting.shadow_worker import (
    ELIGIBILITY, LANE, MemoryEvidenceStore, OfflineShadowWorker,
    REGISTRY, REQUIRED_SIX, ShadowBlocked, sha256_bytes, json_bytes,
)
from scripts.reporting.report import REGISTRY as HEADING_REGISTRY


def fixture_context():
    return ReportContext.create(
        "2026-10-15", "16:00", "2026-10-15T16:00:00+09:00",
        previous_business_day="2026-10-14"
    )


def fixture_market(instrument, index, *, as_of="2026-10-15T15:45:00+09:00",
                   status="VALID", source_id=None):
    spec = REGISTRY[instrument]
    source = next(
        x for x in spec["sources"] if x.get("marketType") == spec["marketType"]
        and not x.get("referenceOnly")
    )
    return Market(
        instrument=instrument, marketType=spec["marketType"],
        venue=None, contractMonth=None, priceValue=100.0 + index,
        priceUnit=spec["unit"], changeValue=None, changePct=None,
        direction="UNKNOWN", comparisonBasis="", asOf=as_of,
        source=({"id": source_id or source["id"], "url": source.get("sourceUrl") or source["url"]},),
        status=status, unavailableReason=None,
        displayText=f"{100.0 + index} {spec['unit']}",
    )


def fixture_snapshot(context=None, *, markets=None, captured="2026-10-15T15:50:00+09:00"):
    context = context or fixture_context()
    if markets is None:
        markets = tuple(fixture_market(x, i) for i, x in enumerate(REQUIRED_SIX))
    return MarketDataSnapshot.capture(context, markets, captured)


def fixture_response(context, snapshot, *, suffix=""):
    dt = datetime.fromisoformat(context.report_date)
    title = f"マーケットレポート｜{dt:%Y/%m/%d}（{'月火水木金土日'[dt.weekday()]}）{context.report_time}"
    lines = [title]
    for heading in HEADING_REGISTRY["required"]:
        lines.extend([heading, "この節は無課金の試験用データです。正式な金融情報や売買判断ではありません。" * 8])
    for m in snapshot.markets:
        lines.append(f"{m.instrument}: {m.priceValue} {m.priceUnit} (テスト値)")
    lines.append(suffix)
    return {
        "response_id": "fixture-response-id", "status": "completed",
        "report_id": context.report_id, "title": title,
        "full_text": "\n".join(lines),
        "observations_used": [
            {"series": m.instrument, "value": m.priceValue, "unit": m.priceUnit}
            for m in snapshot.markets
        ],
        "usage": {"input_tokens": 300, "output_tokens": 450},
        "refusal": None
    }


class CorruptStore(MemoryEvidenceStore):
    def read(self, object_id):
        return super().read(object_id) + b"corruption"


class TestShadowWorkerD1(unittest.TestCase):
    def setUp(self):
        self.context = fixture_context()
        self.snapshot = fixture_snapshot(self.context)
        self.engine = OfflineShadowWorker()

    def run_response(self, fn=None, **kw):
        return self.engine.run(
            self.context, self.snapshot,
            fn or (lambda request: fixture_response(self.context, self.snapshot)),
            **kw
        )

    def test_direct_fixture_validation(self):
        from scripts.reporting.shadow_worker import validate_mock_response
        body = validate_mock_response(fixture_response(self.context, self.snapshot),
                                      self.context, self.snapshot)
        self.assertGreaterEqual(len(body), 1200)

    def test_pass_is_non_public_and_immutable(self):
        result = self.run_response(shadow_run_id="test-run", attempt_id="test-attempt")
        self.assertEqual(result.status, "SHADOW_VALIDATED")
        self.assertEqual(result.record["lane"], LANE)
        self.assertEqual(result.record["eligibility"], ELIGIBILITY)
        self.assertEqual(result.record["validation"]["status"], "PASS")
        self.assertFalse(result.publishable)
        self.assertEqual(result.states, ("QUEUED", "CONTEXT_FROZEN", "SNAPSHOT_FROZEN",
            "REQUESTED", "RESPONSE_CAPTURED", "VALIDATED", "PRIVATE_STORED", "READBACK_VERIFIED"))
        self.assertEqual(result.record_sha256, sha256_bytes(self.engine.store.read(result.object_id)))
        self.assertEqual(result.record["producer"]["body_utf8_sha256"],
            sha256_bytes(result.record["body_text"].encode("utf-8")))
        self.assertEqual(self.engine.public_writes, 0)
        self.assertNotIn("producer-proof", result.object_id)

    def test_snapshot_unchanged_across_attempts(self):
        first = self.run_response(attempt_id="a1")
        second = self.run_response(attempt_id="a2")
        self.assertEqual(first.record["snapshot_id"], second.record["snapshot_id"])
        self.assertEqual(first.record["producer"]["request_sha256"],
                         second.record["producer"]["request_sha256"])
        self.assertEqual(first.status, "SHADOW_VALIDATED")
        self.assertEqual(second.status, "SHADOW_VALIDATED")

    def test_duplicate_attempt_fails_before_responder(self):
        self.run_response(attempt_id="a1")
        def forbidden(_):
            self.fail("responder must not be called")
        with self.assertRaisesRegex(ShadowBlocked, "DUPLICATE_ATTEMPT"):
            self.run_response(forbidden, attempt_id="a1")

    def test_timeout_unknown_prevents_blind_retry(self):
        def timeout(_):
            raise TimeoutError("uncertain provider state")
        first = self.run_response(timeout, attempt_id="unknown")
        self.assertEqual(first.status, "UNKNOWN_PROVIDER_RESULT")
        self.assertEqual(first.reason, "UNKNOWN_PROVIDER_RESULT")
        with self.assertRaisesRegex(ShadowBlocked, "REQUIRES_RECONCILIATION"):
            self.run_response(attempt_id="blind-retry")
        self.assertEqual(self.engine.public_writes, 0)

    def test_missing_required_market_never_calls_responder(self):
        self.snapshot = fixture_snapshot(self.context, markets=tuple(
            fixture_market(x, i) for i, x in enumerate(REQUIRED_SIX[:-1])))
        result = self.run_response(lambda _: self.fail("upstream call must be blocked"))
        self.assertEqual(result.status, "BLOCKED")
        self.assertEqual(result.reason, "REQUIRED_MARKET_MISSING")

    def test_future_observation_never_calls_responder(self):
        markets = [fixture_market(x, i) for i, x in enumerate(REQUIRED_SIX)]
        markets[0] = fixture_market(REQUIRED_SIX[0], 0, as_of="2026-10-15T16:00:01+09:00")
        self.snapshot = fixture_snapshot(self.context, markets=tuple(markets))
        result = self.run_response(lambda _: self.fail("must not call"))
        self.assertEqual(result.reason, "OBSERVATION_AFTER_CUTOFF_OR_MISSING")

    def test_stale_market_blocks_without_replacing_value(self):
        markets = [fixture_market(x, i) for i, x in enumerate(REQUIRED_SIX)]
        markets[1] = fixture_market(REQUIRED_SIX[1], 1, status="STALE")
        self.snapshot = fixture_snapshot(self.context, markets=tuple(markets))
        result = self.run_response(lambda _: self.fail("no call"))
        self.assertEqual(result.reason, "MARKET_UNVERIFIED_OR_STALE")

    def test_source_substitution_is_blocked(self):
        markets = [fixture_market(x, i) for i, x in enumerate(REQUIRED_SIX)]
        markets[0] = fixture_market(REQUIRED_SIX[0], 0, source_id="fake-source")
        self.snapshot = fixture_snapshot(self.context, markets=tuple(markets))
        self.assertEqual(self.run_response(lambda _: self.fail("no call")).reason,
                         "OBSERVATION_SOURCE_UNVERIFIED")

    def test_snapshot_capture_after_slot_is_blocked(self):
        self.snapshot = fixture_snapshot(self.context, captured="2026-10-15T16:01:00+09:00")
        self.assertEqual(self.run_response(lambda _: self.fail("no call")).reason,
                         "SNAPSHOT_AFTER_SLOT")

    def test_report_response_mismatch(self):
        for change, reason in (
            (lambda x: x.update({"report_id": "2026-10-15_12-00"}), "RESPONSE_REPORT_ID_MISMATCH"),
            (lambda x: x.update({"status": "incomplete"}), "RESPONSE_NOT_COMPLETED"),
            (lambda x: x.update({"refusal": "not allowed"}), "RESPONSE_NOT_COMPLETED"),
            (lambda x: x.pop("observations_used"), "RESPONSE_SCHEMA_MISMATCH"),
            (lambda x: x["observations_used"][0].update({"value": 999.99}),
             "INVENTED_OR_MISMATCHED_OBSERVATION"),
            (lambda x: x.update({"full_text": "short"}), "REPORT_BODY_OR_TITLE_INVALID"),
            (lambda x: x.update({"full_text": x["full_text"].replace("重要ニュース", "ニュース")}),
             "REQUIRED_SOP_HEADINGS_MISSING"),
        ):
            with self.subTest(reason=reason, change=change):
                engine = OfflineShadowWorker()
                def mock(_request):
                    x = fixture_response(self.context, self.snapshot)
                    change(x)
                    return x
                result = engine.run(self.context, self.snapshot, mock)
                self.assertEqual(result.status, "BLOCKED")
                self.assertEqual(result.reason, reason)
                self.assertEqual(engine.public_writes, 0)

    def test_hash_conflict_quarantines_both_attempts(self):
        prior = self.run_response(attempt_id="first")
        later = self.run_response(
            lambda _: fixture_response(self.context, self.snapshot, suffix="別の本文"),
            attempt_id="second"
        )
        self.assertEqual(later.status, "BLOCKED")
        self.assertEqual(later.reason, "SAME_REVISION_BODY_HASH_CONFLICT")
        self.assertTrue(self.engine.conflicted(self.context.report_id, self.context.revision))
        self.assertEqual(self.engine.effective_status(prior), "BLOCKED_CONFLICT")
        self.assertEqual(self.engine.effective_status(later), "BLOCKED_CONFLICT")
        self.assertNotEqual(prior.record_sha256, later.record_sha256)

    def test_readback_tampering_blocks(self):
        worker = OfflineShadowWorker(store=CorruptStore())
        result = worker.run(self.context, self.snapshot,
                            lambda _: fixture_response(self.context, self.snapshot))
        self.assertEqual(result.status, "BLOCKED")
        self.assertEqual(result.reason, "PRIVATE_READBACK_MISMATCH")
        self.assertEqual(worker.public_writes, 0)

    def test_no_external_producer_or_writer_dependencies(self):
        import ast
        from pathlib import Path
        path = Path(__file__).resolve().parents[1] / "scripts/reporting/shadow_worker.py"
        tree = ast.parse(path.read_text(encoding="utf-8"))
        imports = [
            node.module if isinstance(node, ast.ImportFrom) else x.name
            for node in ast.walk(tree) if isinstance(node, (ast.ImportFrom, ast.Import))
            for x in ([node] if isinstance(node, ast.ImportFrom) else node.names)
        ]
        self.assertFalse(any(x in ("requests", "httpx", "openai", "urllib", "googleapiclient")
                             for x in imports))
        text = path.read_text(encoding="utf-8")
        for term in ("putGitHubJsonFile_", "DriveApp.", "SpreadsheetApp.", "UrlFetchApp."):
            self.assertNotIn(term, text)


if __name__ == "__main__":
    unittest.main()
