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
        "reportId": f"{date}_08-00",
    }


def observation(*, http=200, oidc="PASS", job="PASS", schedule="PASS",
                schedule_date=DATE, schedule_time="07:47", code=0,
                attempt=ATTEMPT, target="PAUSED", watchdog="PAUSED",
                logs=True):
    events = [ingress_record(http=http, oidc=oidc, job=job, schedule=schedule,
                             date=schedule_date, time=schedule_time)]
    return evaluate_one_shot(
        expected_date_jst=DATE, expected_job_id=JOB, events=events,
        scheduler_status_code=code,
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
        self.assertEqual(result["checks"]["http"], "FAIL")
        self.assertEqual(result["overall"], "FAIL")

    def test_oidc_pass_is_not_misclassified_when_job_header_is_unlisted(self):
        events = [ingress_record(http=403, oidc="PASS", job="FAIL",
                                 schedule="INCOMPLETE", job_id="UNLISTED")]
        result = evaluate_one_shot(
            expected_date_jst=DATE, expected_job_id=JOB, events=events,
            scheduler_status_code=0,
            scheduler_last_attempt_time=ATTEMPT,
            target_state_after_pause="PAUSED",
            watchdog_state_after_pause="PAUSED", logs_read=True,
        )
        self.assertEqual(result["checks"]["oidc"], "INCOMPLETE")
        self.assertEqual(result["checks"]["jobName"], "INCOMPLETE")
        self.assertEqual(result["overall"], "INCOMPLETE")

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
            scheduler_status_code=None,
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
            scheduler_status_code=0,
            scheduler_last_attempt_time=ATTEMPT,
            target_state_after_pause="PAUSED",
            watchdog_state_after_pause="PAUSED", logs_read=True,
        )
        self.assertEqual(result["checks"]["scheduleTime"], "INCOMPLETE")
        self.assertEqual(result["overall"], "INCOMPLETE")

    def test_unrelated_request_http_status_is_never_borrowed(self):
        unrelated_job = ingress_record(http=200, date=DATE, time="07:46",
                                       job_id="other-job")
        wrong_day = ingress_record(http=200, date="2026-10-26", time="07:47")
        result = evaluate_one_shot(
            expected_date_jst=DATE, expected_job_id=JOB,
            events=[unrelated_job, wrong_day],
            scheduler_status_code=0,
            scheduler_last_attempt_time=ATTEMPT,
            target_state_after_pause="PAUSED",
            watchdog_state_after_pause="PAUSED", logs_read=True,
        )
        self.assertEqual(result["checks"]["http"], "INCOMPLETE")
        self.assertEqual(result["checks"]["logCorrelation"], "INCOMPLETE")
        self.assertEqual(result["overall"], "INCOMPLETE")

    def test_duplicate_exact_ingress_records_fail_correlation(self):
        duplicate = ingress_record(http=200)
        result = evaluate_one_shot(
            expected_date_jst=DATE, expected_job_id=JOB,
            events=[duplicate, duplicate],
            scheduler_status_code=0,
            scheduler_last_attempt_time=ATTEMPT,
            target_state_after_pause="PAUSED",
            watchdog_state_after_pause="PAUSED", logs_read=True,
        )
        self.assertEqual(result["checks"]["http"], "INCOMPLETE")
        self.assertEqual(result["checks"]["logCorrelation"], "FAIL")
        self.assertEqual(result["overall"], "FAIL")

    def test_log_delay_keeps_result_incomplete(self):
        result = observation(logs=False)
        self.assertEqual(result["checks"]["http"], "INCOMPLETE")
        self.assertEqual(result["checks"]["logs"], "INCOMPLETE")
        self.assertEqual(result["overall"], "INCOMPLETE")

    def test_repeated_identical_fixed_configuration_is_scoped_by_run_date(self):
        days = ("2026-10-26", "2026-10-27")
        results = []
        for day, attempt in zip(days, ("2026-10-25T22:47:00Z", ATTEMPT)):
            events = [ingress_record(date=day)]
            results.append(evaluate_one_shot(
                expected_date_jst=day, expected_job_id=JOB, events=events,
                scheduler_status_code=0,
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
        self.assertLess(definition.index("read_target_after_pause:"), definition.index("pause_watchdog:"))
        self.assertLess(definition.index("pause_watchdog:"), definition.index("read_watchdog_after_pause:"))
        self.assertLess(definition.index("read_watchdog_after_pause:"), definition.index("query_logs:"))
        self.assertIn("targetReadback", definition)
        self.assertIn('default(map.get(targetResponse.body, "state"), "UNKNOWN")', definition)
        self.assertIn('map.get(targetResponse.body, "lastAttemptTime")', definition)
        self.assertIn('default(map.get(targetResponse.body, ["status", "code"]), 0)', definition)
        self.assertIn("matchedIngressCount", definition)
        self.assertIn("expectedReportId", definition)
        self.assertIn('jsonPayload.event=', definition)
        self.assertNotIn("httpRequest", definition)
        self.assertIn('map.get(payload, "schedulerDateJst") == runDateJst', definition)
        self.assertIn('map.get(payload, "schedulerTimeJst") == expectedTimeJst', definition)
        self.assertNotIn('map.get(targetResponse.body, "state", "UNKNOWN")', definition)
        self.assertIn("watchdogReadback", definition)
        self.assertIn("call: sys.log", definition)
        self.assertIn("return: ${record}", definition)

    def test_pause_retry_loops_stop_after_confirmed_paused_readback(self):
        """Never call Scheduler jobs.pause repeatedly after a successful stop."""
        root = Path(__file__).resolve().parents[1]
        definition = (
            root / "cloud" / "workflows" / "p1-one-shot-auto-verify.yaml"
        ).read_text(encoding="utf-8")
        target_loop = definition.split("    - pause_target:\n", 1)[1].split(
            "    - target_pause_gate:\n", 1
        )[0]
        watchdog_loop = definition.split("    - pause_watchdog:\n", 1)[1].split(
            "    - format_last_attempt:\n", 1
        )[0]
        for fragment, job in ((target_loop, "target"),
                              (watchdog_loop, "watchdog")):
            with self.subTest(job=job):
                self.assertEqual(fragment.count("next: break"), 1)
                self.assertIn(
                    f'condition: ${{{job}Readback == "PAUSED"}}', fragment
                )
                self.assertIn(
                    f'${{if({job}Readback == "PAUSED" and '
                    f'{job}PauseCall == "FAILED", "ALREADY_PAUSED", '
                    f'{job}PauseCall)}}',
                    fragment,
                )
                self.assertLess(
                    fragment.index(f"read_{job}_after_pause:"),
                    fragment.index(f"exit_{job}_retry_if_paused:"),
                )

    def test_workflow_compiler_constraints_regression(self):
        """Guard GCP Workflows' 400-character expression and try/except structure."""
        import re
        root = Path(__file__).resolve().parents[1]
        source = (root / "cloud" / "workflows" /
                  "p1-one-shot-auto-verify.yaml").read_text(encoding="utf-8")
        for expression in re.findall(r"\$\{[^\n]*?\}", source):
            with self.subTest(expression=expression[:55]):
                self.assertLessEqual(len(expression) - 3, 400)
        target_read = source.split("            - read_target_after_pause:\n", 1)[1].split(
            "            - normalize_target_pause_result:\n", 1
        )[0]
        self.assertIn("                try:\n", target_read)
        self.assertIn("                except:\n", target_read)
        self.assertIn("                  as: readTargetError\n", target_read)
        self.assertIn("                  steps:\n", target_read)
        # Workflows expressions do not accept inline map literals, even
        # though YAML accepts an empty mapping in a normal assign step.
        self.assertNotIn(', {})}', source)
        self.assertIn('- emptyPayload: {}', source)
        self.assertIn('default(map.get(entry, "jsonPayload"), emptyPayload)', source)

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
