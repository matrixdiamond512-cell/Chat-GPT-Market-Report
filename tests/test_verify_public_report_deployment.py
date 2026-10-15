from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import verify_public_report_deployment as verifier  # noqa: E402


class FakeClock:
    def __init__(self) -> None:
        self.value = 0.0

    def monotonic(self) -> float:
        return self.value

    def sleep(self, seconds: float) -> None:
        self.value += seconds


class RemovedCanonicalRetryTests(unittest.TestCase):
    def test_waits_for_pages_edge_cache_to_return_404(self) -> None:
        clock = FakeClock()
        responses = [(200, b"stale edge response", "application/json"), (404, b"", "text/html")]
        with (
            patch.object(verifier, "fetch", side_effect=responses) as fetch,
            patch.object(verifier.time, "monotonic", side_effect=clock.monotonic),
            patch.object(verifier.time, "sleep", side_effect=clock.sleep),
        ):
            status = verifier.wait_for_removed_canonical(
                "https://example.test/reports/archived.json",
                timeout_seconds=30,
            )
        self.assertEqual(status, 404)
        self.assertEqual(fetch.call_count, 2)

    def test_keeps_failure_when_pages_continues_to_serve_archived_report(self) -> None:
        clock = FakeClock()
        with (
            patch.object(verifier, "fetch", return_value=(200, b"still public", "application/json")) as fetch,
            patch.object(verifier.time, "monotonic", side_effect=clock.monotonic),
            patch.object(verifier.time, "sleep", side_effect=clock.sleep),
        ):
            status = verifier.wait_for_removed_canonical(
                "https://example.test/reports/archived.json",
                timeout_seconds=10,
            )
        self.assertEqual(status, 200)
        self.assertEqual(fetch.call_count, 2)


if __name__ == "__main__":
    unittest.main()
