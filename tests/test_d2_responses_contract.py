"""D2 Responses request/response contract -- in-memory payloads, zero network."""
import copy
import hashlib
import json
import unittest

from scripts.reporting.d2_responses_contract import (
    MODEL, ResponsesContractError, build_request, capture_response,
    estimate_usage_usd, response_format,
)
from test_shadow_worker_offline import fixture_context, fixture_snapshot, fixture_response
from scripts.reporting.d2_numeric_claims import _non_claim_tokens


def provider_fixture(context, snapshot):
    generated = fixture_response(context, snapshot)
    model_output = {name: generated[name] for name in (
        "report_id", "title", "full_text", "observations_used"
    )}
    body = model_output["full_text"]
    by_name = {m.instrument: m for m in snapshot.markets}
    claim_spans = []
    for hit in _non_claim_tokens(body, context, snapshot):
        # Fixture format is intentionally unambiguous: series: value unit.
        line = body[body.rfind("\n", 0, hit.start())+1:
                    (body.find("\n", hit.start()) if "\n" in body[hit.start():] else len(body))]
        series = line.split(":", 1)[0].strip()
        market = by_name[series]
        claim_spans.append({
            "start": hit.start(), "literal": hit.group(0),
            "series": series, "field": "priceValue",
            "source_id": market.source[0]["id"], "as_of": market.asOf
        })
    model_output["numeric_claims"] = claim_spans
    return {
        "id": "resp_test12345", "status": "completed",
        "model": MODEL, "error": None, "incomplete_details": None,
        "usage": {"input_tokens": 12000, "output_tokens": 4000,
                  "total_tokens": 16000},
        "output": [{
            "id": "msg_test12345", "type": "message", "role": "assistant",
            "status": "completed",
            "content": [{"type": "output_text", "text": json.dumps(
                model_output, ensure_ascii=False)}]
        }]
    }


class TestD2Responses(unittest.TestCase):
    def setUp(self):
        self.ctx = fixture_context()
        self.snapshot = fixture_snapshot(self.ctx)
        self.response = provider_fixture(self.ctx, self.snapshot)

    def block(self, edit, fragment):
        response = copy.deepcopy(self.response)
        edit(response)
        with self.assertRaises(ResponsesContractError) as caught:
            capture_response(response, self.ctx, self.snapshot)
        self.assertIn(fragment, str(caught.exception))

    def test_request_strict_json_schema_and_zero_tools(self):
        r = build_request(self.ctx, self.snapshot,
                          instructions="JSONで記録済みの市場データのみ使う。")
        self.assertEqual(r["model"], MODEL)
        self.assertEqual(r["tools"], [])
        self.assertEqual(r["tool_choice"], "none")
        self.assertIs(r["store"], False)
        self.assertEqual(r["text"]["format"]["type"], "json_schema")
        self.assertIs(r["text"]["format"]["strict"], True)
        schema = r["text"]["format"]["schema"]
        self.assertIs(schema["additionalProperties"], False)
        self.assertEqual(set(schema["properties"]), set(schema["required"]))
        self.assertEqual(set(schema["properties"]["numeric_claims"]["items"]["properties"]),
                         set(schema["properties"]["numeric_claims"]["items"]["required"]))
        nested = schema["properties"]["observations_used"]["items"]
        self.assertIs(nested["additionalProperties"], False)
        self.assertEqual(set(nested["properties"]), set(nested["required"]))
        input_data = json.loads(r["input"])
        self.assertEqual(input_data["report_id"], self.ctx.report_id)
        self.assertEqual(input_data["snapshot"]["snapshot_id"], self.snapshot.snapshot_id)
        self.assertEqual(input_data["verified_numeric_source_bundle"]["snapshot_id"],
                         self.snapshot.snapshot_id)
        self.assertEqual(r, build_request(self.ctx,self.snapshot,
                            instructions="JSONで記録済みの市場データのみ使う。"))

    def test_exact_weekday_and_directions_are_anchored_for_historical_real_data(self):
        from pathlib import Path
        from scripts.reporting.context import ReportContext
        from scripts.reporting.snapshot import MarketDataSnapshot
        root = Path(__file__).resolve().parents[1]
        source = json.loads((root / "data/market/history/2026-10-14_21-00.json").read_text(encoding="utf-8"))
        ctx = ReportContext.create("2026-10-14", "21:00",
                                   "2026-10-14T21:00:00+09:00", mode="historical")
        snap = MarketDataSnapshot.from_acquisition(ctx, source)
        req = build_request(ctx, snap, instructions="事実のみを使う。")
        data = json.loads(req["input"])
        self.assertEqual(data["expected_title"], "マーケットレポート｜2026/10/14（水）21:00")
        self.assertIn(data["expected_title"], req["instructions"])
        directions = {x["series"]: x["direction"] for x in data["observed_directions"]}
        self.assertEqual(directions["gold"], "DOWN")
        self.assertEqual(directions["wti"], "UP")
        self.assertIn("矛盾する上昇・下落の断定を書かない", req["instructions"])
        self.assertFalse(req["store"])
        self.assertEqual(req["tools"], [])

    def test_capture_provider_raw_response_and_body_hash(self):
        r = capture_response(self.response, self.ctx, self.snapshot)
        self.assertEqual(r.response_id, "resp_test12345")
        self.assertEqual(r.model, MODEL)
        self.assertEqual(r.response_status, "completed")
        self.assertEqual(r.usage["total_tokens"], 16000)
        self.assertEqual(len(r.body_sha256), 64)
        self.assertIsNone(r.raw_response_sha256)
        self.assertEqual(len(r.normalized_response_sha256), 64)
        self.assertFalse(r.publishable)
        self.assertEqual(r.numeric_claims_checked, 6)
        self.assertEqual(len(r.numeric_audit_bundle_sha256), 64)
        self.assertEqual(str(estimate_usage_usd(r.usage)), "0.027")

    def test_exact_original_response_bytes_are_separately_verified(self):
        first = json.dumps(self.response, ensure_ascii=False,
                           separators=(",", ":")).encode("utf-8")
        second = json.dumps(self.response, ensure_ascii=False,
                            indent=2).encode("utf-8")
        a = capture_response(self.response, self.ctx, self.snapshot,
                             raw_response_bytes=first)
        b = capture_response(self.response, self.ctx, self.snapshot,
                             raw_response_bytes=second)
        self.assertEqual(a.raw_response_sha256, hashlib.sha256(first).hexdigest())
        self.assertEqual(b.raw_response_sha256, hashlib.sha256(second).hexdigest())
        self.assertNotEqual(a.raw_response_sha256, b.raw_response_sha256)
        self.assertEqual(a.normalized_response_sha256,
                         b.normalized_response_sha256)
        self.assertFalse(a.publishable)
        for payload, reason in (
            (bytes([0xff]), "RAW_RESPONSE_BYTES_INVALID"),
            (b'{"x":NaN}', "RAW_RESPONSE_BYTES_INVALID"),
            (b'{"id":"x","id":"y"}', "RAW_RESPONSE_BYTES_INVALID"),
            (json.dumps(dict(self.response, id="resp_changed12345")).encode(),
             "RAW_RESPONSE_OBJECT_MISMATCH"),
            (first.decode("utf-8"), "RAW_RESPONSE_BYTES_NOT_BYTES"),
        ):
            with self.subTest(reason=reason), self.assertRaises(ResponsesContractError) as caught:
                capture_response(self.response, self.ctx, self.snapshot,
                                 raw_response_bytes=payload)
            self.assertIn(reason, str(caught.exception))

    def test_provider_status_must_complete(self):
        for status in ("incomplete","queued","failed","in_progress","cancelled"):
            with self.subTest(status=status):
                self.block(lambda r: r.update(status=status), "NOT_COMPLETED")
        self.block(lambda r:r.update(incomplete_details={"reason":"max_output_tokens"}),
                   "ERROR_OR_INCOMPLETE")
        self.block(lambda r:r.update(error={"code":"internal_error"}),"ERROR_OR_INCOMPLETE")

    def test_response_id_model_usage_validation(self):
        self.block(lambda r:r.update(id="fake-id"),"ID_INVALID")
        self.block(lambda r:r.update(model="gpt-other"),"MODEL_MISMATCH")
        self.block(lambda r:r["usage"].update(total_tokens=1),"USAGE_INVALID")
        self.block(lambda r:r["usage"].update(output_tokens=-1),"USAGE_INVALID")
        self.block(lambda r:r["usage"].update(input_tokens=True),"USAGE_INVALID")

    def test_no_tool_calls_or_multiple_assistant_messages(self):
        self.block(lambda r:r["output"].append({
            "type":"web_search_call","status":"completed","id":"tool-1"}),"OUTPUT_COUNT")
        self.block(lambda r:r["output"][0].update(type="function_call"),"OUTPUT_NOT_COMPLETED")
        self.block(lambda r:r["output"][0].update(role="system"),"OUTPUT_NOT_COMPLETED")
        self.block(lambda r:r["output"][0]["content"].append({
            "type":"output_text","text":"{}"}),"OUTPUT_TEXT_CONTENT")
        self.block(lambda r:r["output"][0]["content"][0].update(type="refusal",
                    refusal="I cannot"),"REFUSAL")

    def test_malformed_or_duplicate_json_is_blocked(self):
        self.block(lambda r:r["output"][0]["content"][0].update(text="{"),
                   "OUTPUT_JSON_INVALID")
        self.block(lambda r:r["output"][0]["content"][0].update(
            text='{"report_id":"one","report_id":"two"}'),"OUTPUT_JSON_INVALID")
        self.block(lambda r:r["output"][0]["content"][0].update(
            text='{"value":NaN}'),"OUTPUT_JSON_INVALID")
        self.block(lambda r:r["output"][0]["content"][0].update(
            text='{"x":Infinity}'),"OUTPUT_JSON_INVALID")

    def test_wrong_report_id_or_claims_blocked(self):
        def mutate_output(r, fn):
            item = r["output"][0]["content"][0]
            x = json.loads(item["text"])
            fn(x)
            item["text"] = json.dumps(x, ensure_ascii=False)
        self.block(lambda r:mutate_output(r,lambda x:x.update(
            report_id="2026-10-15_12-00")), "REPORT_ID_MISMATCH")
        self.block(lambda r:mutate_output(r,lambda x:x["observations_used"][0].update(
            value=9999)), "SHADOW_VALIDATION_BLOCKED")
        self.block(lambda r:mutate_output(r,lambda x:x.pop("title")),
                   "OUTPUT_SCHEMA_VIOLATION")


    def mutate_body_output(self, change):
        raw = copy.deepcopy(self.response)
        item = raw["output"][0]["content"][0]
        body = json.loads(item["text"])
        change(body)
        item["text"] = json.dumps(body, ensure_ascii=False)
        return raw

    def test_unbound_prose_number_is_blocked(self):
        def change(o):
            o["full_text"] += "\\n値動きの予想は+987.65。"
        with self.assertRaisesRegex(ResponsesContractError,
                                    "NUMERIC_CLAIM_AUDIT_BLOCKED:NUMERIC_COVERAGE_INCOMPLETE"):
            capture_response(self.mutate_body_output(change), self.ctx, self.snapshot)

    def test_self_declared_false_claim_and_wrong_timestamp_blocked(self):
        for field, value, reason in [
            ("literal", "9999", "NUMERIC_SPAN_UNKNOWN_OR_DUPLICATED"),
            ("series", "invented-market", "NUMERIC_SOURCE_FIELD_UNVERIFIED"),
            ("field", "invented_price", "NUMERIC_SOURCE_FIELD_UNVERIFIED"),
            ("source_id", "fake-source", "NUMERIC_SOURCE_TIME_OR_ID_MISMATCH"),
            ("as_of", "2026-10-15T17:00:00+09:00", "NUMERIC_SOURCE_TIME_OR_ID_MISMATCH"),
            ("start", 0, "NUMERIC_SPAN_UNKNOWN_OR_DUPLICATED"),
        ]:
            def change(o):
                o["numeric_claims"][0][field] = value
            with self.subTest(field=field), self.assertRaisesRegex(
                    ResponsesContractError, reason):
                capture_response(self.mutate_body_output(change), self.ctx, self.snapshot)

    def test_duplicate_or_missing_claim_prevents_false_coverage(self):
        for change in (lambda o: o["numeric_claims"].pop(),
                       lambda o: o["numeric_claims"].append(
                           copy.deepcopy(o["numeric_claims"][0]))):
            with self.assertRaisesRegex(ResponsesContractError, "NUMERIC_CLAIM_AUDIT_BLOCKED"):
                capture_response(self.mutate_body_output(change), self.ctx, self.snapshot)

    def test_metadata_numbers_exempt_only_when_exact_title_or_instrument_label(self):
        self.assertEqual(capture_response(self.response, self.ctx, self.snapshot).numeric_claims_checked, 6)
        def inject(o):
            o["full_text"] += "\\n重要材料は2026/10/15の225日移動平均を参照。"
        with self.assertRaisesRegex(ResponsesContractError, "NUMERIC_COVERAGE_INCOMPLETE"):
            capture_response(self.mutate_body_output(inject), self.ctx, self.snapshot)

    def test_body_percent_unit_cannot_masquerade_as_price(self):
        def add_pct(o):
            old = o["full_text"]
            o["full_text"] = old.replace("gold: 100.0", "gold: 100.0%", 1)
        with self.assertRaisesRegex(ResponsesContractError, "NUMERIC_UNIT_CONFLICT"):
            capture_response(self.mutate_body_output(add_pct), self.ctx, self.snapshot)

    def test_cost_safety(self):
        with self.assertRaises(ResponsesContractError):
            estimate_usage_usd({"input_tokens": 12000, "output_tokens": True})
        with self.assertRaises(ResponsesContractError):
            build_request(self.ctx,self.snapshot,instructions="test",
                          max_output_tokens=4001)
        with self.assertRaises(ResponsesContractError):
            build_request(self.ctx,self.snapshot,instructions="test",
                          model="gpt-5.4-mini-2026-10-01")


if __name__ == "__main__":
    unittest.main()
