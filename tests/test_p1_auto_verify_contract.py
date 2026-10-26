import json
from pathlib import Path
import unittest

from scripts.p1_auto_verify_contract import evaluate_one_shot

JOB = "slot-0800-t13"
DATE = "2026-10-27"
ATTEMPT = "2026-10-26T22:47:01Z"


def ingress_record(*, http=200, oidc="PASS", job="PASS", schedule="PASS",
                   date=DATE, time="07:47", job_id=JOB):
    return {
        "event": "P1_INGRESS_RESULT",
        "jobId": job_id,
        "httpStatus": http,
        "oidcResult": oidc,
        "jobNameResult": job,
        "scheduleTimeResult": schedule,
        "schedulerDateJst": date,
        "schedulerTimeJst": time,
    }


def observation(*, http=200, oidc="PASS", job="PASS", schedule="PASS",
                schedule_date=DATE, schedule_time="07:47", code=0,
                attempt=ATTEMPT, target="PAUSED", watchdog="PAUSED",
                logs=True):
    events = [ingress_record(http=http, oidc=oidc, job=job, schedule=schedule,
                             date=schedule_date, time=schedule_time)]
    return evaluate_one_shot(
        expected_date_jst=DATE, expected_job_id=JOB, events=events,
        http_status=http, scheduler_status_code=code,
        scheduler_last_attempt_time=attempt,
        target_state_after_pause=target,
        watchdog_state_after_pause=watchdog,
        logs_read=logs,
    )


class OneShotVerificationContractTests(unittest.TestCase):
    def test_normal_single_scheduler_run_passes_only_after_both_pause_readbacks(self):
        result = observation()
        self.assertEqual(result["overall"], "PASS")
        self.assertTrue(all(value == "PASS" for value in result["checks"].values()))

    def test_manual_off_schedule_400_is_fail_even_when_oidc_and_job_pass(self):
        result = observation(http=400, schedule="FAIL")
        self.assertEqual(result["checks"]["oidc"], "PASS")
        self.assertEqual(result["checks"]["jobName"], "PASS")
        self.assertEqual(result["checks"]["scheduleTime"], "FAIL")
        self.assertEqual(result["overall"], "FAIL")

    def test_oidc_pass_is_not_misclassified_when_job_header_is_unlisted(self):
        events = [ingress_record(http=403, oidc="PASS", job="FAIL",
                                 schedule="INCOMPLETE", job_id="UNLISTED")]
        result = evaluate_one_shot(
            expected_date_jst=DATE, expected_job_id=JOB, events=events,
            http_status=403, scheduler_status_code=0,
            scheduler_last_attempt_time=ATTEMPT,
            target_state_after_pause="PAUSED",
            watchdog_state_after_pause="PAUSED", logs_read=True,
        )
        self.assertEqual(result["checks"]["oidc"], "PASS")
        self.assertEqual(result["checks"]["jobName"], "FAIL")
        self.assertEqual(result["overall"], "FAIL")

    def test_processor_failure_still_requires_and_records_successful_stop(self):
        result = observation(http=500)
        self.assertEqual(result["checks"]["targetPauseReadback"], "PASS")
        self.assertEqual(result["overall"], "FAIL")

    def test_stop_readback_failure_is_blocked_even_if_request_passed(self):
        result = observation(target="ACTIVE")
        self.assertEqual(result["overall"], "BLOCKED")
        self.assertEqual(result["checks"]["targetPauseReadback"], "BLOCKED")

    def test_missing_run_evidence_is_incomplete_not_pass(self):
        result = evaluate_one_shot(
            expected_date_jst=DATE, expected_job_id=JOB, events=[],
            http_status=None, scheduler_status_code=None,
            scheduler_last_attempt_time=None, target_state_after_pause="PAUSED",
            watchdog_state_after_pause="PAUSED", logs_read=True,
        )
        self.assertEqual(result["overall"], "INCOMPLETE")
        self.assertEqual(result["checks"]["scheduleTime"], "INCOMPLETE")

    def test_previous_business_day_cannot_satisfy_todays_run(self):
        stale = ingress_record(date="2026-10-26", time="07:47")
        result = evaluate_one_shot(
            expected_date_jst=DATE, expected_job_id=JOB,
            events=[stale],
            http_status=200, scheduler_status_code=0,
            scheduler_last_attempt_time=ATTEMPT,
            target_state_after_pause="PAUSED",
            watchdog_state_after_pause="PAUSED", logs_read=True,
        )
        self.assertEqual(result["checks"]["scheduleTime"], "FAIL")
        self.assertEqual(result["overall"], "FAIL")

    def test_repeated_identical_fixed_configuration_is_scoped_by_run_date(self):
        days = ("2026-10-26", "2026-10-27")
        results = []
        for day, attempt in zip(days, ("2026-10-25T22:47:00Z", ATTEMPT)):
            events = [ingress_record(date=day)]
            results.append(evaluate_one_shot(
                expected_date_jst=day, expected_job_id=JOB, events=events,
                http_status=200, scheduler_status_code=0,
                scheduler_last_attempt_time=attempt,
                target_state_after_pause="PAUSED",
                watchdog_state_after_pause="PAUSED", logs_read=True,
            )["overall"])
        self.assertEqual(results, ["PASS", "PASS"])



class OneShotWorkflowDefinitionTests(unittest.TestCase):
    def test_safety_pauses_both_scheduler_jobs_before_log_collection(self):
        root = Path(__file__).resolve().parents[1]
        definition = (root / "cloud" / "workflows" / "p1-one-shot-auto-verify.yaml").read_text(encoding="utf-8")
        self.assertLess(definition.index("pause_target:"), definition.index("read_target_after_pause:"))
        self.assertLess(definition.index("read_target:"), definition.index("pause_watchdog:"))
        self.assertLess(definition.index("pause_watchdog:"), definition.index("read_watchdog_after_pause:"))
        self.assertLess(definition.index("read_watchdog_after_pause:"), definition.index("query_logs:"))
        self.assertIn("targetReadback", definition)
        self.assertIn("watchdogReadback", definition)
        self.assertIn("call: sys.log", definition)
        self.assertIn("return: ${record}", definition)

    def test_config_is_preparation_only_and_does_not_enable_storage_writes(self):
        root = Path(__file__).resolve().parents[1]
        config = json.loads((root / "config" / "p1-one-shot-auto-verify.json").read_text(encoding="utf-8"))
        self.assertFalse(config["apply"])
        self.assertTrue(config["oneShotTrial"]["pausePrimaryFirst"])
        self.assertTrue(config["oneShotTrial"]["requirePauseReadback"])
        self.assertFalse(config["oneShotTrial"]["storageWriteRequired"])
        self.assertEqual(config["result"]["statuses"], ["PASS", "FAIL", "BLOCKED", "INCOMPLETE"])

if __name__ == "__main__":
    unittest.main()
