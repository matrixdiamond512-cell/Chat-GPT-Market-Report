"""Offline contract tests. Never call the paid OpenAI API."""
import json
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from scripts.reporting.d3_openai_transport import (
    FixedOpenAIHTTPS, LiveTransportBlocked, AuthorizedPaidAttempt,
    run_authorized_shadow_once,
)
from scripts.reporting.d2_private_store import LocalPrivateEvidenceStore

KEY = "sk-proj-offline-fixture-1234567890123456789"
PROJECT = "proj_offline_fixture"


class FakeHTTP:
    def __init__(self, body=b'{"object":"response.input_tokens","input_tokens":30}', status=200):
        self.body = body
        self.status = status

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self, _n):
        return self.body


class TestFixedTransport(unittest.TestCase):
    def test_refuse_invalid_credentials_before_network(self):
        with self.assertRaises(LiveTransportBlocked):
            FixedOpenAIHTTPS(api_key="", project_id=PROJECT)
        with self.assertRaises(LiveTransportBlocked):
            FixedOpenAIHTTPS(api_key=KEY, project_id="")
        with self.assertRaises(LiveTransportBlocked):
            FixedOpenAIHTTPS(api_key=KEY, project_id="other")

    def test_exact_endpoint_and_project_binding(self):
        captured = []
        def opener(request, timeout):
            captured.append((request, timeout))
            return FakeHTTP()
        client = FixedOpenAIHTTPS(api_key=KEY, project_id=PROJECT, opener=opener)
        raw = client.post("/v1/responses/input_tokens", {"model": "example"})
        self.assertIn(b'"input_tokens":30', raw)
        req, timeout = captured[0]
        self.assertEqual(req.full_url, "https://api.openai.com/v1/responses/input_tokens")
        self.assertEqual(req.get_header("Openai-project"), PROJECT)
        self.assertEqual(req.get_header("Authorization"), "Bearer " + KEY)
        self.assertEqual(timeout, 45)
        self.assertEqual(len(captured), 1)

    def test_no_external_url_and_no_automatic_retry(self):
        calls = []
        def fail(_request, timeout):
            calls.append(timeout)
            raise TimeoutError("ambiguous")
        client = FixedOpenAIHTTPS(api_key=KEY, project_id=PROJECT, opener=fail)
        with self.assertRaisesRegex(LiveTransportBlocked, "ENDPOINT_NOT_ALLOWED"):
            client.post("https://another-provider.example", {})
        self.assertEqual(calls, [])
        with self.assertRaisesRegex(LiveTransportBlocked, "NO_AUTOMATIC_RETRY"):
            client.post("/v1/responses", {"model": "x"})
        self.assertEqual(calls, [45])

    def test_no_unbounded_response(self):
        client = FixedOpenAIHTTPS(
            api_key=KEY, project_id=PROJECT,
            opener=lambda _req, timeout: FakeHTTP(b"x" * (2 * 1024 * 1024 + 1)))
        with self.assertRaisesRegex(LiveTransportBlocked, "SIZE_INVALID"):
            client.post("/v1/responses", {})


    def test_429_error_code_is_visible_without_logging_body_or_retry(self):
        import io
        from urllib.error import HTTPError
        calls = []
        error_body = b'{"error":{"code":"credit_balance_exhausted","message":"private detail"}}'
        def fail(request, timeout):
            calls.append(request.full_url)
            raise HTTPError(request.full_url, 429, "too many requests",
                            {}, io.BytesIO(error_body))
        client = FixedOpenAIHTTPS(api_key=KEY, project_id=PROJECT, opener=fail)
        with self.assertRaises(LiveTransportBlocked) as caught:
            client.post("/v1/responses", {"model":"fixture"})
        message = str(caught.exception)
        self.assertIn("OPENAI_HTTP_429_CODE_credit_balance_exhausted_NO_AUTOMATIC_RETRY",message)
        self.assertNotIn("private detail",message)
        self.assertNotIn(KEY,message)
        self.assertEqual(len(calls),1)

    def test_unknown_429_code_never_exposes_provider_message(self):
        import io
        from urllib.error import HTTPError
        def fail(request, timeout):
            raise HTTPError(request.full_url, 429, "quota",
                            {}, io.BytesIO(b'{"error":{"code":"INVALID secret message","message":"sensitive"}}'))
        client = FixedOpenAIHTTPS(api_key=KEY, project_id=PROJECT, opener=fail)
        with self.assertRaises(LiveTransportBlocked) as caught:
            client.post("/v1/responses",{"model":"fixture"})
        self.assertIn("HTTP_429_CODE_UNKNOWN_NO_AUTOMATIC_RETRY",str(caught.exception))
        self.assertNotIn("sensitive",str(caught.exception))


class TestLiveGate(unittest.TestCase):
    def test_independent_authorizer_is_required_before_network(self):
        calls = []
        client = FixedOpenAIHTTPS(
            api_key=KEY, project_id=PROJECT,
            opener=lambda _req, timeout: calls.append(timeout))
        with tempfile.TemporaryDirectory(prefix="market-d3-") as directory:
            store = LocalPrivateEvidenceStore(Path(directory))
            with self.assertRaisesRegex(LiveTransportBlocked, "INDEPENDENT_APPROVER_REQUIRED"):
                run_authorized_shadow_once(
                    context=SimpleNamespace(report_id="2026-10-15_08-00"),
                    snapshot=SimpleNamespace(snapshot_id="frozen"), instructions="fixture",
                    private_store=store, client=client, external_authorizer=None)
        self.assertEqual(calls, [])

    def test_paid_request_needs_matching_external_receipt_and_is_single_use(self):
        urls = []
        count = b'{"object":"response.input_tokens","input_tokens":20}'
        model = b'{"status":"completed","id":"resp_offline_dummy"}'
        def opener(request, timeout):
            urls.append(request.full_url)
            if request.full_url.endswith("/input_tokens"):
                return FakeHTTP(count)
            return FakeHTTP(model)
        client = FixedOpenAIHTTPS(api_key=KEY, project_id=PROJECT, opener=opener)
        context = SimpleNamespace(report_id="2026-10-15_08-00")
        snapshot = SimpleNamespace(snapshot_id="snap_1234")
        fake_plan = SimpleNamespace(
            count_endpoint="/v1/responses/input_tokens",
            payload={"model":"offline"}, create_request_sha256="a"*64,
            count_request_sha256="b"*64)
        review = SimpleNamespace(
            raw_count_sha256="c"*64, planned_cost_usd="0.02")
        valid = AuthorizedPaidAttempt(
            report_id=context.report_id, snapshot_id=snapshot.snapshot_id,
            project_id=PROJECT, request_sha256="a"*64,
            count_response_sha256="c"*64,
            approved_run_usd="0.03", billing_receipt="signedbilling000001",
            approval_id="ownerapproved000001", sender_allowed=True,
        )
        with tempfile.TemporaryDirectory(prefix="market-d3-") as directory:
            store = LocalPrivateEvidenceStore(Path(directory))
            mocks = (
                patch("scripts.reporting.d3_openai_transport.build_request",
                      return_value={"model":"offline"}),
                patch("scripts.reporting.d3_openai_transport.build_count_plan",
                      return_value=fake_plan),
                patch("scripts.reporting.d3_openai_transport.review_count_fixture",
                      return_value=review),
                patch("scripts.reporting.d3_openai_transport.capture_response",
                      return_value=SimpleNamespace(
                          usage={"input_tokens":20,"output_tokens":2},
                          body_sha256="d"*64,response_id="resp_offline_dummy")),
                patch("scripts.reporting.d3_openai_transport.estimate_usage_usd",
                      return_value=Decimal("0.01")),
            )
            from contextlib import ExitStack
            with ExitStack() as st:
                for mock in mocks: st.enter_context(mock)
                # Incorrect external receipt: count may run, paid generation must not.
                with self.assertRaisesRegex(LiveTransportBlocked, "APPROVAL"):
                    run_authorized_shadow_once(
                        context=context, snapshot=snapshot, instructions="fixture",
                        private_store=store,client=client,
                        external_authorizer=lambda **_kwargs:
                            AuthorizedPaidAttempt(**{**valid.__dict__,"project_id":"proj_other"}))
                self.assertEqual(urls, ["https://api.openai.com/v1/responses/input_tokens"])
                result = run_authorized_shadow_once(
                    context=context, snapshot=snapshot,instructions="fixture",
                    private_store=store,client=client,
                    external_authorizer=lambda **_kwargs: valid)
                self.assertFalse(result.publishable)
                self.assertEqual(result.actual_model_cost_usd, "0.01")
                self.assertEqual(urls[-1], "https://api.openai.com/v1/responses")
                with self.assertRaisesRegex(Exception,"ALREADY_EXISTS"):
                    run_authorized_shadow_once(
                        context=context, snapshot=snapshot, instructions="fixture",
                        private_store=store,client=client,
                        external_authorizer=lambda **_kwargs: valid)
                self.assertEqual(urls.count("https://api.openai.com/v1/responses"), 1)


if __name__ == "__main__":
    unittest.main()
