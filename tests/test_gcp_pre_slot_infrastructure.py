from pathlib import Path
import os
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]


class GcpPreSlotInfrastructureContracts(unittest.TestCase):
    def read(self, path):
        return (ROOT / path).read_text(encoding="utf-8")

    def test_cloud_build_uses_root_context_and_existing_dockerfile(self):
        script = self.read("scripts/gcp/build_test_image.sh")
        config = self.read("infrastructure/gcp/pre-slot-test/cloudbuild.yaml")
        self.assertIn('--config "${CONFIG}"', script)
        self.assertIn('--substitutions="_IMAGE=${IMAGE}" .', script)
        self.assertIn("--default-buckets-behavior=regional-user-owned-bucket", script)
        self.assertIn("infrastructure/gcp/pre-slot-test/Dockerfile", config)
        self.assertIn("      - .", config)
        self.assertNotIn("--file infrastructure/gcp/pre-slot-test/Dockerfile .", script)

    def test_cloud_run_health_endpoint_is_included_in_runner(self):
        runner = self.read("scripts/gcp/pre_slot_cloud_runner.py")
        self.assertIn('environ.get("REQUEST_METHOD") == "GET"', runner)
        self.assertIn('environ.get("PATH_INFO") == "/healthz"', runner)
        self.assertIn('"READY_TEST_ONLY"', runner)

    def test_terraform_state_uses_gcs_backend_and_local_files_are_ignored(self):
        versions = self.read("infrastructure/gcp/pre-slot-test/versions.tf")
        ignore = self.read(".gitignore")
        script = self.read("scripts/gcp/deploy_test_only.sh")
        self.assertIn('backend "gcs"', versions)
        for pattern in ("*.tfstate", "*.tfvars", "*.tfplan", "**/.terraform/"):
            self.assertIn(pattern, ignore)
        self.assertIn("TF_STATE_BUCKET", script)
        self.assertIn("plan -out=tfplan", script)
        self.assertIn("apply is intentionally not supported", script)
        self.assertIn("enable_test_scheduler = ${ENABLE_TEST_SCHEDULER}", script)
        
    def test_state_bucket_bootstrap_is_private_uniform_versioned(self):
        script = self.read("scripts/gcp/bootstrap_state_bucket.sh")
        self.assertIn("--uniform-bucket-level-access", script)
        self.assertIn("--public-access-prevention", script)
        self.assertIn("--versioning", script)
        self.assertNotIn("--lifecycle-file", script)
        self.assertIn("EXPECTED_PROJECT_NUMBER", script)
        self.assertIn("BUCKET_PROJECT_NUMBER", script)
        self.assertEqual(script.count("--raw --format=\'value(projectNumber)\'"), 2)
        self.assertIn("does not match TEST_ONLY project", script)

    def test_existing_foreign_state_bucket_is_rejected_before_any_mutation(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            bin_dir = root / "bin"
            bin_dir.mkdir()
            call_log = root / "calls.log"
            fake = bin_dir / "gcloud"
            fake.write_text("""#!/usr/bin/env bash
echo "$*" >> "$GCLOUD_CALL_LOG"
case "$*" in
  "projects describe "*) echo 123456 ;;
  "storage buckets describe "*)
    if [[ "$*" != *" --raw "* ]]; then echo "missing --raw" >&2; exit 10; fi
    echo 999999 ;;
  *) echo "unexpected mutating command: $*" >&2; exit 9 ;;
esac
""", encoding="utf-8")
            fake.chmod(0o755)
            env = os.environ.copy()
            env.update({
                "PATH": str(bin_dir) + os.pathsep + env.get("PATH", ""),
                "GCLOUD_CALL_LOG": str(call_log),
                "PROJECT_ID": "market-test-only-123",
                "TF_STATE_BUCKET": "existing-foreign-state-bucket",
            })
            result = subprocess.run(
                ["bash", str(ROOT / "scripts/gcp/bootstrap_state_bucket.sh")],
                text=True, capture_output=True, env=env, check=False,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("does not match TEST_ONLY project", result.stderr)
            calls = call_log.read_text(encoding="utf-8").splitlines()
            self.assertEqual(len(calls), 2)
            self.assertTrue(calls[0].startswith("projects describe "))
            self.assertTrue(calls[1].startswith("storage buckets describe "))
            self.assertFalse(any("services enable" in call or "buckets update" in call for call in calls))

    def test_existing_same_project_state_bucket_updates_after_owner_check(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            bin_dir = root / "bin"
            bin_dir.mkdir()
            call_log = root / "calls.log"
            fake = bin_dir / "gcloud"
            fake.write_text("""#!/usr/bin/env bash
echo "$*" >> "$GCLOUD_CALL_LOG"
case "$*" in
  "projects describe "*) echo 123456 ;;
  "storage buckets describe "*)
    if [[ "$*" != *" --raw "* ]]; then echo "missing --raw" >&2; exit 10; fi
    echo 123456 ;;
  "services enable "*|"storage buckets update "*) exit 0 ;;
  *) echo "unexpected command: $*" >&2; exit 9 ;;
esac
""", encoding="utf-8")
            fake.chmod(0o755)
            env = os.environ.copy()
            env.update({
                "PATH": str(bin_dir) + os.pathsep + env.get("PATH", ""),
                "GCLOUD_CALL_LOG": str(call_log),
                "PROJECT_ID": "market-test-only-123",
                "TF_STATE_BUCKET": "existing-test-only-state-bucket",
            })
            result = subprocess.run(
                ["bash", str(ROOT / "scripts/gcp/bootstrap_state_bucket.sh")],
                text=True, capture_output=True, env=env, check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            calls = call_log.read_text(encoding="utf-8").splitlines()
            self.assertTrue(any("storage buckets update" in call for call in calls))
            self.assertFalse(any("storage buckets create" in call for call in calls))

    def test_scheduler_only_updates_do_not_rewrite_implicit_service_scaling(self):
        tf = self.read("infrastructure/gcp/pre-slot-test/main.tf")
        self.assertIn("ignore_changes = [scaling]", tf)
        self.assertIn("max_instance_count = 1", tf)
        self.assertIn("max_instance_request_concurrency = 1", tf)

    def test_runtime_iam_and_scheduler_audience_are_narrow_and_aligned(self):
        tf = self.read("infrastructure/gcp/pre-slot-test/main.tf")
        runner = self.read("scripts/gcp/pre_slot_cloud_runner.py")
        self.assertIn("custom_audiences    = [local.runner_audience]", tf)
        self.assertIn("audience              = local.runner_audience", tf)
        self.assertIn('role     = "roles/run.invoker"', tf)
        self.assertIn('member   = "serviceAccount:', tf)
        self.assertNotIn('member   = "allUsers"', tf)
        self.assertIn('"storage.objects.create"', tf)
        self.assertIn('"storage.objects.get"', tf)
        self.assertIn('"storage.objects.delete"', tf)
        self.assertNotIn('"storage.objects.update"', tf)
        self.assertIn("if_generation_match=0", runner)
        self.assertIn("generation=generation", runner)
        self.assertIn("if_generation_match=generation", runner)
        self.assertNotIn("github_app_private_key", runner.lower())
        self.assertNotIn("google_docs_credentials", runner.lower())

    def test_evidence_bucket_is_private_and_expires_after_14_days(self):
        tf = self.read("infrastructure/gcp/pre-slot-test/main.tf")
        self.assertIn("uniform_bucket_level_access = true", tf)
        self.assertIn('public_access_prevention    = "enforced"', tf)
        self.assertIn("retention_duration_seconds = 0", tf)
        self.assertIn("age = 14", tf)
        self.assertIn("retention_days = 14", tf)

    def test_scheduler_is_disabled_by_default_and_has_explicit_second_stage(self):
        variables = self.read("infrastructure/gcp/pre-slot-test/variables.tf")
        terraform = self.read("infrastructure/gcp/pre-slot-test/main.tf")
        deploy = self.read("scripts/gcp/deploy_test_only.sh")
        docs = self.read("docs/gcp-test-only-runner.md")
        self.assertIn("default     = false", variables)
        self.assertIn("var.enable_test_scheduler ? local.slots : {}", terraform)
        self.assertIn('ENABLE_TEST_SCHEDULER="${ENABLE_TEST_SCHEDULER:-false}"', deploy)
        self.assertIn("ENABLE_TEST_SCHEDULER=true", docs)
        self.assertIn("zero** Cloud Scheduler jobs", docs)
        self.assertIn("exactly three weekday TEST_ONLY jobs", docs)

    def test_docker_smoke_and_infrastructure_contracts_are_in_ci(self):
        workflow = self.read(".github/workflows/gcp-test-only-infrastructure-ci.yml")
        self.assertIn("docker build", workflow)
        self.assertIn("/healthz", workflow)
        self.assertIn(" validate", workflow)
        self.assertIn("tests.test_gcp_pre_slot_infrastructure", workflow)


if __name__ == "__main__":
    unittest.main()
