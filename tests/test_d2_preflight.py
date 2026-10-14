"""D2 readiness tests. There is no API client, secret, web, or publisher."""
import copy
import inspect
import unittest

from scripts.reporting.d2_preflight import (
    REQUIRED_EVIDENCE, evaluate_d2_manifest, PreflightOutcome
)


def candidate():
    """Synthetic *review* manifest, not real approval or a price quote."""
    return {
        "schema_version": "market-report-d2-preflight/v1",
        "lane": "api-shadow", "run_mode": "shadow",
        "eligibility": "SHADOW_NOT_ELIGIBLE",
        "dry_run_only": True, "allow_publication": False,
        "report_id": "2026-10-15_16-00",
        "model_snapshot": "gpt-5.4-mini-2026-03-17",
        "external_tools": [], "web_search_calls": 0,
        "data_contract": "immutable-context-snapshot/v1",
        "response_contract": "shadow-responses-json/v2",
        "caps": {
            "max_input_tokens": 12000,
            "max_output_tokens": 4000,
            "max_attempts": 1, "max_runs": 1,
            "max_run_usd": "0.05", "max_month_usd": "1.00",
        },
        "price_quote": {
            "model": "gpt-5.4-mini-2026-03-17",
            "unit": "USD_PER_MILLION_TOKENS",
            "input_per_million": "0.75", "output_per_million": "4.50",
        },
        "timeout_policy": "UNKNOWN_STOP_NO_BLIND_RETRY",
        "store": {
            "access": "private", "readback": "byte_exact",
            "immutable_create": True, "retention_days": 30,
        },
        "attestation_refs": {key: "synthetic-review-ref/" + key for key in REQUIRED_EVIDENCE},
    }


class TestD2Preflight(unittest.TestCase):
    def setUp(self):
        self.plan = candidate()

    def check_block(self, mutate, reason):
        p = copy.deepcopy(self.plan)
        mutate(p)
        r = evaluate_d2_manifest(p)
        self.assertIsInstance(r, PreflightOutcome)
        self.assertIn(reason, r.blockers)
        self.assertFalse(r.api_send_allowed)
        self.assertFalse(r.publication_allowed)
        return r

    def test_missing_manifest_fails_closed(self):
        result = evaluate_d2_manifest()
        self.assertEqual(result.contract, "BLOCKED")
        self.assertIn("MISSING_MANIFEST", result.blockers)
        self.assertFalse(result.api_send_allowed)

    def test_fixture_contract_valid_but_not_externally_attested(self):
        result = evaluate_d2_manifest(self.plan)
        self.assertEqual(result.contract, "SPEC_CONTRACT_PASS")
        self.assertEqual(result.blockers, ("EXTERNAL_ATTESTATIONS_NOT_VERIFIED",))
        self.assertEqual(result.worst_case_usd, "0.027")
        self.assertFalse(result.api_send_allowed)
        self.assertFalse(result.publication_allowed)

    def test_budget_gates(self):
        self.check_block(lambda p: p["caps"].update(max_run_usd="0.02"),
                         "RUN_BUDGET_EXCEEDED")
        self.check_block(lambda p: p["caps"].update(max_month_usd="0.01"),
                         "MONTHLY_BUDGET_EXCEEDED")
        self.check_block(lambda p: p["caps"].update(max_attempts=2),
                         "ONE_MANUAL_ATTEMPT_REQUIRED")
        self.check_block(lambda p: p["caps"].update(max_runs=2),
                         "ONE_MANUAL_RUN_REQUIRED")
        self.check_block(lambda p: p["caps"].update(max_input_tokens=0),
                         "MAX_INPUT_NOT_POSITIVE_INTEGER")
        self.check_block(lambda p: p["caps"].update(max_output_tokens=True),
                         "MAX_OUTPUT_NOT_POSITIVE_INTEGER")
        self.check_block(lambda p: p["caps"].update(max_input_tokens=12001),
                         "MAX_INPUT_ABOVE_D2_SAFE_BOUND")
        self.check_block(lambda p: p["caps"].update(max_output_tokens=4001),
                         "MAX_OUTPUT_ABOVE_D2_SAFE_BOUND")
        self.check_block(lambda p: p["caps"].update(max_run_usd="0.0050000009"),
                         "RUN_CAP_NOT_APPROVED_DECIMAL_STRING")
        self.check_block(lambda p: p["price_quote"].update(input_per_million="-1"),
                         "INPUT_RATE_NOT_APPROVED_DECIMAL_STRING")
        self.check_block(lambda p: p["price_quote"].update(model="other"),
                         "RATE_MODEL_OR_UNIT_MISMATCH")
        self.check_block(lambda p: p["price_quote"].update(input_per_million="0.01"),
                         "INPUT_RATE_MISMATCH_PINNED_MODEL")
        self.check_block(lambda p: p["price_quote"].update(output_per_million="0.01"),
                         "OUTPUT_RATE_MISMATCH_PINNED_MODEL")

    def test_prohibit_publication_and_tool_use(self):
        self.check_block(lambda p: p.update(lane="chatgpt-task"), "SHADOW_LANE_REQUIRED")
        self.check_block(lambda p: p.update(allow_publication=True), "PUBLICATION_BOUNDARY_REQUIRED")
        self.check_block(lambda p: p.update(dry_run_only=False), "PUBLICATION_BOUNDARY_REQUIRED")
        self.check_block(lambda p: p.update(external_tools=["web_search"]), "MODEL_TOOL_CALLS_FORBIDDEN_IN_D2")
        self.check_block(lambda p: p.update(web_search_calls=3), "MODEL_TOOL_CALLS_FORBIDDEN_IN_D2")

    def test_contract_boundary(self):
        self.check_block(lambda p: p.update(schema_version="legacy"), "SCHEMA_VERSION_MISMATCH")
        self.check_block(lambda p: p.update(model_snapshot="gpt-5.4-mini-latest"),
                         "MODEL_SNAPSHOT_NOT_PINNED")
        self.check_block(lambda p: p.update(model_snapshot="gpt-5.4-mini"),
                         "MODEL_SNAPSHOT_NOT_PINNED")
        self.check_block(lambda p: p.update(model_snapshot="gpt-5.6-terra-2026-06-01"),
                         "MODEL_NOT_SUPPORTED_BY_D2_CONTRACT")
        self.check_block(lambda p: p.update(response_contract="strict-json-schema/v1"),
                         "STRICT_OUTPUT_CONTRACT_MISSING")
        self.check_block(lambda p: p.update(report_id="2026-99-99_16-00"),
                         "REPORT_ID_OR_SLOT_INVALID")
        self.check_block(lambda p: p.update(report_id="2026-10-15_18-00"),
                         "REPORT_ID_OR_SLOT_INVALID")
        self.check_block(lambda p: p.update(data_contract="mutable-latest"),
                         "IMMUTABLE_INPUT_CONTRACT_MISSING")
        self.check_block(lambda p: p.update(response_contract="plain-text"),
                         "STRICT_OUTPUT_CONTRACT_MISSING")
        self.check_block(lambda p: p.update(timeout_policy="retry-on-timeout"),
                         "UNKNOWN_PROVIDER_RESULT_POLICY_MISSING")

    def test_private_storage_policy(self):
        self.check_block(lambda p: p["store"].update(access="public"),
                         "PRIVATE_IMMUTABLE_STORE_CONTRACT_MISSING")
        self.check_block(lambda p: p["store"].update(immutable_create=False),
                         "PRIVATE_IMMUTABLE_STORE_CONTRACT_MISSING")
        self.check_block(lambda p: p["store"].update(readback="metadata"),
                         "PRIVATE_IMMUTABLE_STORE_CONTRACT_MISSING")
        self.check_block(lambda p: p["store"].update(retention_days=0),
                         "STORE_RETENTION_NOT_APPROVED")

    def test_independent_attestations_must_be_verified_offline_status_never_ready(self):
        for field in REQUIRED_EVIDENCE:
            self.check_block(lambda p, f=field: p["attestation_refs"].pop(f),
                             "MISSING_ATTESTATION_REF:" + field)
        # Even the full set of syntactically valid *unverified* references
        # cannot be upgraded to authorization by a user-controlled JSON file.
        result = evaluate_d2_manifest(self.plan)
        self.assertNotEqual(result.contract, "READY")
        self.assertFalse(result.api_send_allowed)

    def test_no_secrets_in_plan(self):
        self.check_block(lambda p: p.update(api_key="secret-not-actually-a-key"),
                         "CREDENTIAL_FIELD_IN_MANIFEST")
        self.check_block(lambda p: p["attestation_refs"].update(
            private_store="sk-proj-private-key-not-for-tests"), "CREDENTIAL_MATERIAL_IN_MANIFEST")

    def test_module_has_no_client_or_publication_code(self):
        import ast
        from pathlib import Path
        from scripts.reporting import d2_preflight
        code = Path(inspect.getfile(d2_preflight)).read_text(encoding="utf8")
        tree = ast.parse(code)
        roots = set()
        for n in ast.walk(tree):
            if isinstance(n, ast.Import):
                roots.update(x.name.split(".")[0] for x in n.names)
            if isinstance(n, ast.ImportFrom) and n.module:
                roots.add(n.module.split(".")[0])
        self.assertFalse(roots & {"openai", "requests", "urllib", "httpx",
                                  "subprocess", "socket", "googleapiclient"})
        for s in ("putGitHubJsonFile_", "DriveApp", "SpreadsheetApp", "UrlFetchApp"):
            self.assertNotIn(s, code)


if __name__ == "__main__":
    unittest.main()
