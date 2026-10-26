from pathlib import Path
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
        
    def test_state_bucket_bootstrap_is_private_uniform_versioned(self):
        script = self.read("scripts/gcp/bootstrap_state_bucket.sh")
        self.assertIn("--uniform-bucket-level-access", script)
        self.assertIn("--public-access-prevention", script)
        self.assertIn("--versioning", script)
        self.assertNotIn("--lifecycle-file", script)

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

    def test_docker_smoke_and_infrastructure_contracts_are_in_ci(self):
        workflow = self.read(".github/workflows/gcp-test-only-infrastructure-ci.yml")
        self.assertIn("docker build", workflow)
        self.assertIn("/healthz", workflow)
        self.assertIn(" validate", workflow)
        self.assertIn("tests.test_gcp_pre_slot_infrastructure", workflow)


if __name__ == "__main__":
    unittest.main()
