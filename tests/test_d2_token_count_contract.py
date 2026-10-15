"""Offline-only tests for official Responses input-token count request/response."""
from dataclasses import replace
import copy
import json
import unittest

from scripts.reporting.d2_responses_contract import build_request, MODEL
from scripts.reporting.d2_token_count_contract import (
    build_count_plan, review_count_fixture, InputCountBlocked, SCHEMA,
)
from test_shadow_worker_offline import fixture_context, fixture_snapshot


class TestD2TokenCountContract(unittest.TestCase):
    def setUp(self):
        context = fixture_context()
        snapshot = fixture_snapshot(context)
        self.req = build_request(
            context, snapshot, instructions="Use only the immutable snapshot.")
        self.plan = build_count_plan(self.req)

    def count(self, n=9000):
        return json.dumps({"object": "response.input_tokens",
                           "input_tokens": n}).encode("utf8")

    def test_exact_request_projection_including_schema_and_instructions(self):
        expected_keys = {"model", "instructions", "input", "tools",
                         "tool_choice", "text"}
        self.assertEqual(set(self.plan.payload), expected_keys)
        for key in expected_keys:
            self.assertEqual(self.plan.payload[key], self.req[key])
        self.assertEqual(self.plan.count_endpoint, "/v1/responses/input_tokens")
        self.assertEqual(self.plan.schema_version, SCHEMA)
        self.assertFalse(self.plan.api_send_allowed)

    def test_count_fixture_matches_but_never_authenticates(self):
        reviewed = review_count_fixture(self.plan, self.req, self.count())
        self.assertEqual(reviewed.input_tokens, 9000)
        self.assertEqual(reviewed.planned_cost_usd, "0.02475")
        self.assertEqual(reviewed.status, "OFFLINE_COUNT_SHAPE_PASS_NOT_ATTESTED")
        self.assertFalse(reviewed.provider_authenticated)
        self.assertFalse(reviewed.api_send_allowed)
        self.assertFalse(reviewed.publication_allowed)
        self.assertEqual(reviewed.create_request_sha256, self.plan.create_request_sha256)
        self.assertEqual(reviewed.count_request_sha256, self.plan.count_request_sha256)

    def test_exact_cap_can_pass_but_it_is_still_offline(self):
        check = review_count_fixture(self.plan, self.req, self.count(12000))
        self.assertEqual(check.planned_cost_usd, "0.027")
        self.assertFalse(check.api_send_allowed)

    def test_count_over_cap_rejected(self):
        with self.assertRaisesRegex(InputCountBlocked, "MODEL_INPUT_TOKEN_CAP_EXCEEDED"):
            review_count_fixture(self.plan, self.req, self.count(12001))

    def test_count_false_zero_and_boolean_edge_cases(self):
        reviewed = review_count_fixture(self.plan, self.req, self.count(0))
        self.assertEqual(reviewed.input_tokens, 0)
        for value in (True, False, "100", 100.0, None, -1):
            with self.subTest(value=value), self.assertRaises(InputCountBlocked):
                review_count_fixture(self.plan, self.req, self.count(value))

    def test_response_extra_field_and_bad_object_rejected(self):
        for record in (
            {"object": "not-a-token-count", "input_tokens": 1},
            {"object": "response.input_tokens", "input_tokens": 1, "model": MODEL},
            [1, 2],
        ):
            with self.subTest(record=record), self.assertRaisesRegex(
                    InputCountBlocked, "COUNT_RESPONSE_SCHEMA_INVALID"):
                review_count_fixture(self.plan, self.req,
                                     json.dumps(record).encode("utf8"))

    def test_bad_raw_response_duplicates_nan_and_utf8(self):
        for content in (
            b'{"object":"response.input_tokens","input_tokens":1,"input_tokens":999}',
            b'{"object":"response.input_tokens","input_tokens":NaN}',
            b'{"object":',
            b'\xff',
            b'',
        ):
            with self.subTest(content=content), self.assertRaises(InputCountBlocked):
                review_count_fixture(self.plan, self.req, content)

    def test_instructions_or_input_changed_since_count_are_rejected(self):
        for key in ("instructions", "input"):
            changed = copy.deepcopy(self.req)
            changed[key] += " changed"
            with self.subTest(key=key), self.assertRaisesRegex(
                    InputCountBlocked, "COUNT_REQUEST_CHANGED_AFTER_COUNT"):
                review_count_fixture(self.plan, changed, self.count())

    def test_output_schema_changed_after_count_is_rejected(self):
        changed = copy.deepcopy(self.req)
        changed["text"]["format"]["name"] = "bogus-format"
        with self.assertRaisesRegex(InputCountBlocked, "COUNT_REQUEST_CHANGED_AFTER_COUNT"):
            review_count_fixture(self.plan, changed, self.count())

    def test_max_output_token_change_after_count_is_rejected(self):
        changed = copy.deepcopy(self.req)
        changed["max_output_tokens"] = 3999
        with self.assertRaisesRegex(InputCountBlocked, "COUNT_REQUEST_CHANGED_AFTER_COUNT"):
            review_count_fixture(self.plan, changed, self.count())

    def test_unsupported_fields_or_tools_fail_closed(self):
        for key, value in (("tools", [{"type":"web_search"}]),
                           ("store", True), ("tool_choice", "auto"),
                           ("model", "random-model")):
            changed = copy.deepcopy(self.req)
            changed[key] = value
            with self.subTest(key=key), self.assertRaisesRegex(
                    InputCountBlocked, "CREATE_REQUEST_UNSAFE_OR_MISMATCH"):
                build_count_plan(changed)
        changed = copy.deepcopy(self.req)
        changed["previous_response_id"] = "resp_prior"
        with self.assertRaisesRegex(InputCountBlocked, "CREATE_REQUEST_SCHEMA_DRIFT"):
            build_count_plan(changed)

    def test_cap_budget_precheck_and_tampering_rejected(self):
        for args in (
            {"max_input_tokens": True}, {"max_input_tokens": 12001},
            {"max_input_tokens": 0}, {"max_run_usd": "0.0001"},
            {"max_run_usd": "0.000000001"}, {"max_run_usd": "NaN"},
            {"max_run_usd": "1e9"}, {"max_run_usd": "0"},
        ):
            with self.subTest(args=args), self.assertRaises(InputCountBlocked):
                build_count_plan(self.req, **args)
        forged = replace(self.plan, max_run_usd="0.0001")
        with self.assertRaisesRegex(InputCountBlocked, "COUNT_WORST_CASE_BUDGET_EXCEEDED"):
            review_count_fixture(forged, self.req, self.count())

    def test_count_payload_shallow_forgery_does_not_bind(self):
        forged = replace(self.plan, payload={"model": MODEL})
        with self.assertRaisesRegex(InputCountBlocked, "COUNT_REQUEST_CHANGED_AFTER_COUNT"):
            review_count_fixture(forged, self.req, self.count())

    def test_module_has_no_network_client_or_publisher(self):
        from pathlib import Path
        import ast
        from scripts.reporting import d2_token_count_contract
        tree = ast.parse(Path(d2_token_count_contract.__file__).read_text())
        imports = set()
        for item in ast.walk(tree):
            if isinstance(item, ast.Import):
                imports.update(x.name.split(".")[0] for x in item.names)
            if isinstance(item, ast.ImportFrom) and item.module:
                imports.add(item.module.split(".")[0])
        self.assertFalse(imports & {
            "openai", "requests", "urllib", "httpx", "socket", "subprocess",
            "googleapiclient"
        })


if __name__ == "__main__":
    unittest.main()
