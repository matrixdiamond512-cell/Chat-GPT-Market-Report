"""D2 Responses request/response contract -- in-memory payloads, zero network."""
import copy
import json
import unittest

from scripts.reporting.d2_responses_contract import (
    MODEL, ResponsesContractError, build_request, capture_response,
    estimate_usage_usd, response_format,
)
from test_shadow_worker_offline import fixture_context, fixture_snapshot, fixture_response


def provider_fixture(context, snapshot):
    generated = fixture_response(context, snapshot)
    model_output = {name: generated[name] for name in (
        "report_id", "title", "full_text", "observations_used"
    )}
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
        nested = schema["properties"]["observations_used"]["items"]
        self.assertIs(nested["additionalProperties"], False)
        self.assertEqual(set(nested["properties"]), set(nested["required"]))
        input_data = json.loads(r["input"])
        self.assertEqual(input_data["report_id"], self.ctx.report_id)
        self.assertEqual(input_data["snapshot"]["snapshot_id"], self.snapshot.snapshot_id)
        self.assertEqual(r, build_request(self.ctx,self.snapshot,
                            instructions="JSONで記録済みの市場データのみ使う。"))

    def test_capture_provider_raw_response_and_body_hash(self):
        r = capture_response(self.response, self.ctx, self.snapshot)
        self.assertEqual(r.response_id, "resp_test12345")
        self.assertEqual(r.model, MODEL)
        self.assertEqual(r.response_status, "completed")
        self.assertEqual(r.usage["total_tokens"], 16000)
        self.assertEqual(len(r.body_sha256), 64)
        self.assertEqual(len(r.raw_response_sha256), 64)
        self.assertFalse(r.publishable)
        self.assertEqual(str(estimate_usage_usd(r.usage)), "0.027")

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
