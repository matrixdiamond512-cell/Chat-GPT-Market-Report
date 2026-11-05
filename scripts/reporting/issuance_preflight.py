"""Read-only production readiness checks for the controlled issuance adapter."""
from __future__ import annotations

import argparse
from datetime import datetime, timedelta
import hashlib
import json
import os
import shutil
import subprocess
from pathlib import Path

from scripts.reporting.context import aware


class PreflightBlocked(RuntimeError):
    pass


class GitHubReadOnlyProbe:
    API = "https://api.github.com"

    def __init__(self, repository: str, token: str, session=None):
        if not repository or not token:
            raise PreflightBlocked("GITHUB_IDENTITY_NOT_CONFIGURED")
        if session is None:
            import requests
            session = requests.Session()
        self.repository, self.token, self.session = repository, token, session

    def get(self, path: str):
        response = self.session.get(self.API + "/repos/" + self.repository + path,
                                    headers={"Accept": "application/vnd.github+json",
                                             "Authorization": "Bearer " + self.token,
                                             "X-GitHub-Api-Version": "2022-11-28"}, timeout=20)
        if response.status_code != 200:
            raise PreflightBlocked("GITHUB_PREFLIGHT_GET_FAILED:" + str(response.status_code))
        return response.json()


def _environment_protection_result(*, repository, environment, branch_policies,
                                   expected_repository, current_ref, environment_name):
    """Return PASS only for explicit reviewer, self-review, admin and main-only rules."""
    reasons = []
    identity_ok = (repository.get("full_name", "").lower() ==
                   expected_repository.lower())
    if not identity_ok:
        reasons.append("ENVIRONMENT_REPOSITORY_MISMATCH")
    ref_is_main = current_ref == "refs/heads/main"
    if not ref_is_main:
        reasons.append("ENVIRONMENT_PREFLIGHT_NOT_ON_MAIN")
    name_ok = environment.get("name") == environment_name
    if not name_ok:
        reasons.append("ENVIRONMENT_NAME_MISMATCH")

    reviewer_rules = [rule for rule in environment.get("protection_rules", [])
                      if rule.get("type") == "required_reviewers"]
    reviewers = reviewer_rules[0].get("reviewers", []) if len(reviewer_rules) == 1 else []
    def valid_reviewer(row):
        reviewer = row.get("reviewer") or {}
        kind = row.get("type")
        has_id = isinstance(reviewer.get("id"), int) and reviewer["id"] > 0
        has_name = bool(reviewer.get("login") or reviewer.get("slug"))
        return kind in ("User", "Team") and (has_id or has_name)
    reviewers_ok = 1 <= len(reviewers) <= 6 and all(valid_reviewer(row) for row in reviewers)
    if not reviewers_ok:
        reasons.append("ENVIRONMENT_REQUIRED_REVIEWERS_INVALID")
    self_review_ok = (len(reviewer_rules) == 1 and
                      reviewer_rules[0].get("prevent_self_review") is True)
    if not self_review_ok:
        reasons.append("ENVIRONMENT_PREVENT_SELF_REVIEW_NOT_ENABLED")

    branch_policy = environment.get("deployment_branch_policy")
    custom_only = (isinstance(branch_policy, dict) and
                   branch_policy.get("custom_branch_policies") is True and
                   branch_policy.get("protected_branches") is False)
    entries = branch_policies.get("branch_policies", [])
    total = branch_policies.get("total_count", len(entries))
    main_only = (custom_only and total == 1 and len(entries) == 1 and
                 entries[0].get("name") == "main" and entries[0].get("type") != "tag")
    if not main_only:
        reasons.append("ENVIRONMENT_BRANCH_POLICY_NOT_MAIN_ONLY")

    admin_bypass = environment.get("can_admins_bypass")
    if admin_bypass is not False:
        reasons.append("ENVIRONMENT_ADMIN_BYPASS_ENABLED" if admin_bypass is True
                       else "ENVIRONMENT_ADMIN_BYPASS_UNKNOWN")

    return {
        "status": "PASS" if not reasons else "BLOCKED",
        "reason": ";".join(reasons) if reasons else None,
        "workflow_main_ref": ref_is_main,
        "repository_identity_match": identity_ok,
        "environment_name_matches": name_ok,
        "reviewer_gate_configured": reviewers_ok,
        "environment_required_reviewers": len(reviewers),
        "prevent_self_review": self_review_ok,
        "deployment_branch_main_only": main_only,
        "admin_bypass_disabled": admin_bypass is False,
        "approval_for_current_run": "NOT_INFERRED",
        "approval_environment_variable_ignored": True,
    }


def run_environment_gate(*, env=None, github=None) -> dict:
    """Read GitHub Environment controls and names only; never reads secret values."""
    env = os.environ if env is None else env
    repository = env.get("GITHUB_REPOSITORY", "")
    token = env.get("REPORT_PREFLIGHT_GITHUB_TOKEN", "")
    if github is None:
        try:
            github = GitHubReadOnlyProbe(repository, token)
        except PreflightBlocked as exc:
            return {"mode": "GITHUB_ENVIRONMENT_GATE", "status": "BLOCKED",
                    "reason": str(exc), "secrets_emitted": False}
    try:
        repo = github.get("")
        name = env.get("REPORT_ISSUANCE_ENVIRONMENT", "report-publication")
        environment = github.get("/environments/" + name)
        policies = github.get("/environments/" + name + "/deployment-branch-policies?per_page=100")
        secret_data = github.get("/environments/" + name + "/secrets?per_page=100")
        protection = _environment_protection_result(
            repository=repo, environment=environment, branch_policies=policies,
            expected_repository=repository, current_ref=env.get("GITHUB_REF", ""),
            environment_name=name)
        secret_names = sorted(row["name"] for row in secret_data.get("secrets", [])
                              if isinstance(row, dict) and isinstance(row.get("name"), str))
        inventory_complete = secret_data.get("total_count", len(secret_names)) == len(secret_names)
        return {"mode": "GITHUB_ENVIRONMENT_GATE", "status": protection["status"],
                "protection": protection,
                "environment_inventory": {
                    "status": "PASS" if inventory_complete else "BLOCKED",
                    "secret_names": secret_names, "variable_names": "NOT_READ",
                    "reason": "GitHub variable-list API returns values; values were not requested.",
                    "values_read_or_emitted": False},
                "secrets_emitted": False}
    except (PreflightBlocked, KeyError, TypeError, AttributeError) as exc:
        return {"mode": "GITHUB_ENVIRONMENT_GATE", "status": "BLOCKED",
                "reason": str(exc), "secrets_emitted": False}


class DefaultGoogleReadOnlyProbe:
    def __init__(self):
        import google.auth
        from google.auth.transport.requests import AuthorizedSession
        from google.cloud import storage
        scopes = ["https://www.googleapis.com/auth/drive.metadata.readonly",
                  "https://www.googleapis.com/auth/devstorage.read_only",
                  "https://www.googleapis.com/auth/cloud-platform.read-only"]
        credentials, project = google.auth.default(scopes=scopes)
        expected_principal = os.environ.get("REPORT_ISSUANCE_READONLY_SERVICE_ACCOUNT", "")
        self.principal_email = getattr(credentials, "service_account_email", None)
        if not expected_principal:
            raise PreflightBlocked("GCP_READONLY_IDENTITY_NOT_CONFIGURED")
        if self.principal_email != expected_principal:
            raise PreflightBlocked("GCP_READONLY_IDENTITY_MISMATCH")
        self.session = AuthorizedSession(credentials)
        self.storage = storage.Client(project=project, credentials=credentials)
        self.project_id = project or getattr(credentials, "project_id", None)

    def request(self, *args, **kwargs):
        return self.session.request(*args, **kwargs)

    def get_exact_evidence(self, bucket: str, object_name: str, generation: str) -> bool:
        if not bucket or not object_name or not generation.isdigit():
            return False
        blob = self.storage.bucket(bucket).blob(object_name, generation=int(generation))
        blob.reload()
        return str(blob.generation) == generation

    def read_exact_json_object(self, bucket: str, object_name: str, generation: str) -> dict:
        if not bucket or not object_name or not generation.isdigit():
            raise PreflightBlocked("PINNED_GCS_OBJECT_REFERENCE_INVALID")
        blob = self.storage.bucket(bucket).blob(object_name, generation=int(generation))
        try:
            payload = blob.download_as_bytes(if_generation_match=int(generation))
            blob.reload()
        except Exception as exc:
            raise PreflightBlocked("PINNED_GCS_OBJECT_READ_FAILED") from exc
        if str(blob.generation) != generation:
            raise PreflightBlocked("PINNED_GCS_GENERATION_MISMATCH")
        try:
            data = json.loads(payload.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise PreflightBlocked("PINNED_GCS_OBJECT_JSON_INVALID") from exc
        if not isinstance(data, dict):
            raise PreflightBlocked("PINNED_GCS_OBJECT_NOT_JSON_OBJECT")
        created_at = getattr(blob, "time_created", None)
        return {"data": data, "generation": str(blob.generation),
                "created_at": created_at.isoformat() if created_at else None,
                "sha256": hashlib.sha256(payload).hexdigest()}


    def read_g2_creation_audit(self, *, bucket: str, object_name: str,
                               generation: str) -> dict | None:
        """Read the Cloud Audit Log record binding one GCS generation to its creator."""
        if not self.project_id or not bucket or not object_name or not generation.isdigit():
            raise PreflightBlocked("G2_CREATOR_AUDIT_TARGET_INVALID")
        resource_name = f"projects/_/buckets/{bucket}/objects/{object_name}"
        log_name = f"projects/{self.project_id}/logs/cloudaudit.googleapis.com%2Fdata_access"
        filters = [
            "logName=" + json.dumps(log_name),
            'protoPayload.serviceName="storage.googleapis.com"',
            'protoPayload.methodName="storage.objects.create"',
            "protoPayload.resourceName=" + json.dumps(resource_name),
            "protoPayload.response.generation=" + json.dumps(generation),
        ]
        response = self.request(
            "POST", "https://logging.googleapis.com/v2/entries:list",
            json={"resourceNames": [f"projects/{self.project_id}"],
                  "filter": " AND ".join(filters), "orderBy": "timestamp desc",
                  "pageSize": 20}, timeout=20)
        if response.status_code != 200:
            raise PreflightBlocked("G2_CREATOR_AUDIT_READ_FAILED:" + str(response.status_code))
        entries = response.json().get("entries", [])
        for entry in entries:
            payload = entry.get("protoPayload", {})
            response_object = payload.get("response", {})
            if (payload.get("resourceName") != resource_name or
                    str(response_object.get("generation", "")) != generation):
                continue
            return {
                "principal_email": (payload.get("authenticationInfo") or {}).get("principalEmail", ""),
                "resource_name": payload.get("resourceName", ""),
                "generation": str(response_object.get("generation", "")),
                "timestamp": entry.get("timestamp", ""),
            }
        return None

    def test_claim_permissions(self, bucket: str) -> dict:
        permissions = self.storage.bucket(bucket).test_iam_permissions(
            ["storage.objects.get", "storage.objects.create"])
        return {"read": "storage.objects.get" in permissions,
                "create": "storage.objects.create" in permissions}


def _chromium_runtime_ready() -> bool:
    node = shutil.which("node")
    if not node:
        return False
    try:
        result = subprocess.run([node, "-e", "process.stdout.write(require('playwright').chromium.executablePath())"],
                                capture_output=True, text=True, timeout=10, check=False)
    except (OSError, subprocess.TimeoutExpired):
        return False
    return result.returncode == 0 and bool(result.stdout.strip()) and Path(result.stdout.strip()).is_file()


def _validate_g2_evidence_binding(*, env, google_probe) -> dict:
    required = ("REPORT_ISSUANCE_REPORT_ID", "REPORT_ISSUANCE_REVISION",
                "REPORT_ISSUANCE_G2_BUNDLE_OBJECT", "REPORT_ISSUANCE_G2_BUNDLE_GENERATION",
                "REPORT_EVIDENCE_OBJECT", "REPORT_EVIDENCE_GENERATION")
    missing = [key for key in required if not env.get(key)]
    if missing:
        return {"status": "BLOCKED",
                "reason": "BLOCKED_G2_PRODUCER_MISSING" if any(
                    key.startswith("REPORT_ISSUANCE_G2_BUNDLE_") for key in missing)
                    else "G2_EVIDENCE_TARGET_INPUT_MISSING",
                "missing": missing}
    revision = env["REPORT_ISSUANCE_REVISION"]
    if not revision.isdigit() or int(revision) <= 0:
        return {"status": "BLOCKED", "reason": "G2_REVISION_INVALID"}
    bucket = env.get("REPORT_ISSUANCE_G2_BUNDLE_BUCKET") or env.get("REPORT_EVIDENCE_BUCKET", "")
    try:
        g2_object = google_probe.read_exact_json_object(
            bucket, env["REPORT_ISSUANCE_G2_BUNDLE_OBJECT"],
            env["REPORT_ISSUANCE_G2_BUNDLE_GENERATION"])
        evidence_object = google_probe.read_exact_json_object(
            env.get("REPORT_EVIDENCE_BUCKET", ""), env["REPORT_EVIDENCE_OBJECT"],
            env["REPORT_EVIDENCE_GENERATION"])
        bundle = g2_object["data"]
        g2 = bundle.get("g2") or {}
        report = g2.get("report") or {}
        ref = bundle.get("evidence_ref") or {}
        report_id = env["REPORT_ISSUANCE_REPORT_ID"]
        expected_revision = int(revision)
        if (report.get("report_id") != report_id or report.get("revision") != expected_revision or
                g2.get("report_id") != report_id or g2.get("revision") != expected_revision):
            raise PreflightBlocked("G2_REPORT_ID_OR_REVISION_MISMATCH")
        if (ref.get("object") != env["REPORT_EVIDENCE_OBJECT"] or
                str(ref.get("generation")) != env["REPORT_EVIDENCE_GENERATION"]):
            raise PreflightBlocked("G2_EVIDENCE_REFERENCE_MISMATCH")
        full_text = report.get("fullText")
        body_hash = hashlib.sha256(full_text.encode("utf-8")).hexdigest() if isinstance(full_text, str) else ""
        if (not body_hash or g2.get("body_hash") != body_hash or
                report.get("bodyHash") != body_hash):
            raise PreflightBlocked("G2_BODY_HASH_MISMATCH")
        if report["time"] != "08:00":
            raise PreflightBlocked("G2_FREEZE_TIME_OR_SLOT_INVALID")
        report_slot = aware(report["date"] + "T" + report["time"] + ":00+09:00")
        slot_end = report_slot + timedelta(minutes=40)
        frozen_at = aware(g2.get("frozen_at", ""))
        if not report_slot <= frozen_at <= slot_end:
            raise PreflightBlocked("G2_FREEZE_OUTSIDE_0800_WINDOW")
        review = g2.get("scenario_review") or {}
        reviewed_at = aware(review.get("reviewed_at", ""))
        if (review.get("report_id") not in (None, report_id) or
                review.get("body_hash") not in (None, body_hash) or
                not report_slot <= reviewed_at <= frozen_at):
            raise PreflightBlocked("G2_REVIEW_IDENTITY_OR_TIME_INVALID")
        if not g2_object.get("created_at"):
            raise PreflightBlocked("G2_BUNDLE_CREATION_TIME_UNKNOWN")
        g2_created_at = aware(g2_object["created_at"])
        if g2_created_at < frozen_at:
            raise PreflightBlocked("G2_BUNDLE_CREATED_BEFORE_FREEZE")
        if g2_created_at > slot_end:
            raise PreflightBlocked("G2_BUNDLE_CREATED_AFTER_REPORT_WINDOW")
        evidence = evidence_object["data"]
        if (evidence.get("reportId") != report_id or
                evidence.get("revision") != expected_revision or
                not evidence.get("evidenceId") or
                not (evidence.get("snapshot") or {}).get("snapshot_id")):
            raise PreflightBlocked("EVIDENCE_IDENTITY_MISMATCH")
        if not evidence_object.get("created_at"):
            raise PreflightBlocked("EVIDENCE_CREATION_TIME_UNKNOWN")
        if aware(evidence_object["created_at"]) > report_slot:
            raise PreflightBlocked("EVIDENCE_CREATED_AFTER_REPORT_SLOT")
        return {"status": "PASS", "report_id": report_id, "revision": expected_revision,
                "body_sha256": body_hash, "g2_frozen_at": g2["frozen_at"],
                "g2_bundle_generation": g2_object["generation"],
                "g2_bundle_created_at": g2_object["created_at"],
                "g2_window_end": slot_end.isoformat(),
                "g2_bundle_sha256": g2_object["sha256"],
                "evidence_generation": evidence_object["generation"],
                "evidence_sha256": evidence_object["sha256"],
                "evidence_id": evidence["evidenceId"],
                "snapshot_id": evidence["snapshot"]["snapshot_id"]}
    except (PreflightBlocked, KeyError, TypeError, ValueError) as exc:
        return {"status": "BLOCKED", "reason": str(exc)}


def _verify_g2_producer_identity(*, env, google_probe, binding) -> dict:
    """Require an observed Cloud Audit Log creator for the exact pinned object."""
    if not isinstance(binding, dict) or binding.get("status") != "PASS":
        return {"status": "BLOCKED", "reason": "G2_EVIDENCE_BINDING_NOT_VERIFIED"}
    required = ("REPORT_ISSUANCE_G2_PRODUCER_SERVICE_ACCOUNT",
                "REPORT_ISSUANCE_G2_BUNDLE_BUCKET", "REPORT_ISSUANCE_G2_BUNDLE_OBJECT",
                "REPORT_ISSUANCE_G2_BUNDLE_GENERATION")
    missing = [name for name in required if not env.get(name)]
    if missing:
        return {"status": "BLOCKED", "reason": "G2_PRODUCER_IDENTITY_CONFIG_MISSING",
                "missing": missing}
    reader = getattr(google_probe, "read_g2_creation_audit", None)
    if not callable(reader):
        return {"status": "BLOCKED", "reason": "G2_CREATOR_AUDIT_READER_UNAVAILABLE"}
    expected_generation = env["REPORT_ISSUANCE_G2_BUNDLE_GENERATION"]
    if str(binding.get("g2_bundle_generation", "")) != expected_generation:
        return {"status": "BLOCKED", "reason": "G2_AUDIT_GENERATION_BINDING_MISMATCH"}
    try:
        event = reader(bucket=env["REPORT_ISSUANCE_G2_BUNDLE_BUCKET"],
                       object_name=env["REPORT_ISSUANCE_G2_BUNDLE_OBJECT"],
                       generation=expected_generation)
    except (PreflightBlocked, OSError, ValueError) as exc:
        return {"status": "BLOCKED", "reason": str(exc)}
    if not isinstance(event, dict):
        return {"status": "BLOCKED", "reason": "G2_CREATOR_AUDIT_EVENT_NOT_FOUND"}
    expected_resource = (f"projects/_/buckets/{env['REPORT_ISSUANCE_G2_BUNDLE_BUCKET']}/objects/"
                         f"{env['REPORT_ISSUANCE_G2_BUNDLE_OBJECT']}")
    try:
        event_at = aware(event.get("timestamp", ""))
        frozen_at = aware(binding.get("g2_frozen_at", ""))
        window_end = aware(binding.get("g2_window_end", ""))
    except (ValueError, TypeError) as exc:
        return {"status": "BLOCKED", "reason": "G2_CREATOR_AUDIT_TIME_INVALID"}
    if (event.get("principal_email") != env["REPORT_ISSUANCE_G2_PRODUCER_SERVICE_ACCOUNT"] or
            event.get("generation") != expected_generation or
            event.get("resource_name") != expected_resource or
            not frozen_at <= event_at <= window_end):
        return {"status": "BLOCKED", "reason": "G2_CREATOR_AUDIT_IDENTITY_MISMATCH"}
    return {"status": "PASS", "producer_principal": event["principal_email"],
            "g2_object": env["REPORT_ISSUANCE_G2_BUNDLE_OBJECT"],
            "g2_generation": expected_generation,
            "g2_bundle_sha256": binding.get("g2_bundle_sha256")}


def run_configuration_diagnostic(*, env=None) -> dict:
    """No-secret static diagnosis; never reports READY or contacts external services."""
    env = os.environ if env is None else env
    required = ("GITHUB_REPOSITORY", "REPORT_ISSUANCE_ENVIRONMENT",
                "REPORT_PAGES_BASE_URL", "REPORT_EVIDENCE_PROJECT_ID",
                "REPORT_EVIDENCE_BUCKET", "REPORT_ISSUANCE_CLAIM_BUCKET",
                "REPORT_ISSUANCE_WIF_PROVIDER",
                "REPORT_ISSUANCE_READONLY_SERVICE_ACCOUNT",
                "REPORT_ISSUANCE_DOCS_FOLDER_ID", "REPORT_ISSUANCE_ROOT_FOLDER_ID")
    missing = [key for key in required if not env.get(key)]
    g2_reference_present = bool(env.get("REPORT_ISSUANCE_G2_BUNDLE_OBJECT") and
                                 env.get("REPORT_ISSUANCE_G2_BUNDLE_GENERATION"))
    return {"mode": "CONFIGURATION_DIAGNOSTIC", "status": "NOT_READY",
            "secrets_emitted": False,
            "checks": {
                "static_configuration": {"status": "PASS" if not missing else "BLOCKED",
                                         "missing": missing},
                "g2_producer": {"status": "BLOCKED",
                                "reason": "BLOCKED_G2_PRODUCER_MISSING",
                                "bundle_reference_present": g2_reference_present},
                "protected_environment": {"status": "NOT_RUN",
                                          "reason": "Configuration mode has no credentials"},
                "cloud_and_github_permissions": {"status": "NOT_RUN"},
                "pages_and_dom": {"status": "NOT_RUN"},
                "installed_apps_script_triggers": {"status": "UNKNOWN"},
            }}


def _read_only_pages_probe(url: str) -> bool:
    if not url.startswith("https://"):
        return False
    import requests
    response = requests.get(url, timeout=20, allow_redirects=True)
    return response.status_code == 200 and response.url.startswith("https://")


def run_preflight(*, env=None, github=None, google_probe=None, dom_runtime=None,
                  pages_probe=None) -> dict:
    """Inspect config and read permissions only; never call a write endpoint."""
    env = os.environ if env is None else env
    result = {"mode": "AUTHENTICATED_READ_ONLY", "checks": {}, "secrets_emitted": False}
    required = ("GITHUB_ACTIONS", "GITHUB_REF", "GITHUB_REPOSITORY",
                "REPORT_PREFLIGHT_GITHUB_TOKEN", "REPORT_PAGES_BASE_URL",
                "REPORT_ISSUANCE_ENVIRONMENT",
                "REPORT_ISSUANCE_WIF_PROVIDER",
                "REPORT_ISSUANCE_READONLY_SERVICE_ACCOUNT",
                "REPORT_EVIDENCE_PROJECT_ID", "REPORT_EVIDENCE_BUCKET",
                "REPORT_EVIDENCE_OBJECT", "REPORT_EVIDENCE_GENERATION",
                "REPORT_ISSUANCE_CLAIM_BUCKET", "REPORT_ISSUANCE_DOCS_FOLDER_ID",
                "REPORT_ISSUANCE_ROOT_FOLDER_ID")
    missing = [key for key in required if not env.get(key)]
    result["checks"]["configuration"] = {"status": "PASS" if not missing else "BLOCKED",
                                          "missing": missing}
    protected_context = (
        env.get("GITHUB_ACTIONS") == "true" and
        env.get("GITHUB_REF") == "refs/heads/main" and
        env.get("REPORT_ISSUANCE_ENVIRONMENT") == "report-publication"
    )
    result["checks"]["protected_execution"] = {
        "status": "UNKNOWN",
        "workflow_main_ref": env.get("GITHUB_REF") == "refs/heads/main",
        "environment_name_matches": env.get("REPORT_ISSUANCE_ENVIRONMENT") == "report-publication",
        "reviewer_gate_configured": False,
        # A workflow input/environment variable is never evidence of an
        # approved GitHub Environment deployment. Approval is not inferred.
        "approval_for_current_run": "NOT_INFERRED",
        "approval_environment_variable_ignored": True,
        "write_gate_present": env.get("REPORT_ISSUANCE_WRITE_ENABLED") == "true",
    }
    runtime_ready = _chromium_runtime_ready() if dom_runtime is None else bool(dom_runtime)
    result["checks"]["public_dom_runtime"] = {"status": "PASS" if runtime_ready else "BLOCKED",
                                                "node_playwright_chromium_ready": runtime_ready}
    if github is None:
        try:
            github = GitHubReadOnlyProbe(env.get("GITHUB_REPOSITORY", ""),
                                        env.get("REPORT_PREFLIGHT_GITHUB_TOKEN", ""))
        except PreflightBlocked as exc:
            result["checks"]["github"] = {"status": "BLOCKED", "reason": str(exc)}
    if github is not None:
        try:
            repo = github.get("")
            environment = github.get("/environments/report-publication")
            workflow = github.get("/actions/workflows/deploy-pages.yml")
            branch_policies = github.get(
                "/environments/report-publication/deployment-branch-policies?per_page=100")
            secret_data = github.get("/environments/report-publication/secrets?per_page=100")
            protection = _environment_protection_result(
                repository=repo, environment=environment, branch_policies=branch_policies,
                expected_repository=env.get("GITHUB_REPOSITORY", ""),
                current_ref=env.get("GITHUB_REF", ""),
                environment_name="report-publication")
            if not protected_context:
                protection["status"] = "BLOCKED"
                protection["reason"] = ";".join(filter(None, [protection.get("reason"),
                    "PREFLIGHT_NOT_RUNNING_IN_PROTECTED_MAIN_CONTEXT"]))
            identity_ok = protection["repository_identity_match"]
            baseline_ok = (identity_ok and repo.get("permissions", {}).get("push") is True
                           and workflow.get("state") == "active"
                           and protection["status"] == "PASS")
            result["checks"]["protected_execution"] = protection
            secret_names = sorted(row["name"] for row in secret_data.get("secrets", [])
                                  if isinstance(row, dict) and isinstance(row.get("name"), str))
            inventory_complete = secret_data.get("total_count", len(secret_names)) == len(secret_names)
            result["checks"]["environment_inventory"] = {
                "status": "UNKNOWN" if inventory_complete else "BLOCKED",
                "secret_names": secret_names, "variable_names": "NOT_READ",
                "reason": "GitHub variable-list API returns values; values were not requested.",
                "values_read_or_emitted": False}
            # Read-only API access cannot prove a write scope. Ignore self-attestation.
            result["checks"]["github"] = {"status": "UNKNOWN" if baseline_ok else "BLOCKED",
                "repository_identity_match": identity_ok,
                "repository_push_access": repo.get("permissions", {}).get("push") is True,
                "credential_contents_write_permission": "UNKNOWN",
                "contents_write_admin_attestation_present": False,
                "actions_workflow_read": workflow.get("state") == "active",
                "pages_workflow_active": workflow.get("state") == "active",
                "environment_protection": protection["status"],
                "environment_required_reviewers": protection["environment_required_reviewers"]}
        except (PreflightBlocked, KeyError, TypeError, AttributeError) as exc:
            result["checks"]["github"] = {"status": "BLOCKED", "reason": str(exc)}
            result["checks"]["protected_execution"] = {
                "status": "BLOCKED", "reason": str(exc),
                "approval_for_current_run": "NOT_INFERRED",
                "approval_environment_variable_ignored": True}
    if google_probe is None:
        try:
            google_probe = DefaultGoogleReadOnlyProbe()
        except Exception as exc:
            result["checks"]["google"] = {
                "status": "BLOCKED" if isinstance(exc, PreflightBlocked) else "UNKNOWN",
                "reason": str(exc) if isinstance(exc, PreflightBlocked) else type(exc).__name__,
            }
    if google_probe is not None:
        try:
            folder_states = []
            for folder_id in (env.get("REPORT_ISSUANCE_DOCS_FOLDER_ID", ""),
                              env.get("REPORT_ISSUANCE_ROOT_FOLDER_ID", "")):
                response = google_probe.request("GET", "https://www.googleapis.com/drive/v3/files/" + folder_id,
                    params={"fields": "id,mimeType,parents,trashed,capabilities(canAddChildren)"}, timeout=20)
                if not response.ok:
                    raise PreflightBlocked("DRIVE_FOLDER_READ_FAILED:" + str(response.status_code))
                folder_states.append(response.json())
            exact_read = google_probe.get_exact_evidence(
                env.get("REPORT_EVIDENCE_BUCKET", ""), env.get("REPORT_EVIDENCE_OBJECT", ""),
                env.get("REPORT_EVIDENCE_GENERATION", ""))
            claim_permissions = google_probe.test_claim_permissions(
                env.get("REPORT_ISSUANCE_CLAIM_BUCKET", ""))
            drive_ok = len(folder_states) == 2 and all(
                row.get("id") == expected_id and
                row.get("mimeType") == "application/vnd.google-apps.folder" and not row.get("trashed")
                for row, expected_id in zip(folder_states, (env.get("REPORT_ISSUANCE_DOCS_FOLDER_ID", ""),
                                                            env.get("REPORT_ISSUANCE_ROOT_FOLDER_ID", "")))
            ) and env.get("REPORT_ISSUANCE_ROOT_FOLDER_ID", "") in folder_states[0].get("parents", []) and \
                folder_states[0].get("capabilities", {}).get("canAddChildren") is True
            expected_principal = env.get("REPORT_ISSUANCE_READONLY_SERVICE_ACCOUNT", "")
            actual_principal = getattr(google_probe, "principal_email", None)
            identity_match = bool(expected_principal) and actual_principal == expected_principal
            google_ok = (drive_ok and exact_read and
                         claim_permissions.get("create") is True and identity_match)
            result["checks"]["google"] = {"status": "PASS" if google_ok else "BLOCKED",
                                            "authenticated_principal": actual_principal,
                                            "expected_principal_match": identity_match,
                                            "drive_folders_read": True,
                                            "docs_folder_can_add_children": drive_ok,
                                            "evidence_generation_read": bool(exact_read),
                                            "claim_read_permission": claim_permissions.get("read", False),
                                            "claim_create_permission": claim_permissions.get("create", False)}
        except Exception as exc:
            result["checks"]["google"] = {"status": "BLOCKED", "reason": str(exc)}
    result["checks"]["g2_evidence_binding"] = _validate_g2_evidence_binding(
        env=env, google_probe=google_probe) if google_probe is not None else {
            "status": "BLOCKED", "reason": "BLOCKED_G2_PRODUCER_MISSING"
        }
    result["checks"]["g2_producer_identity"] = (
        _verify_g2_producer_identity(env=env, google_probe=google_probe,
                                     binding=result["checks"]["g2_evidence_binding"])
        if google_probe is not None else
        {"status": "BLOCKED", "reason": "G2_CREATOR_AUDIT_READER_UNAVAILABLE"}
    )
    result["checks"]["g2_producer_identity"].setdefault(
        "producer_identity_verified",
        result["checks"]["g2_producer_identity"]["status"] == "PASS")
    owner_path = Path(env.get("REPORT_ISSUANCE_OWNER_CONFIG_PATH",
                              Path(__file__).resolve().parents[2] / "config" / "issuance_ownership.json"))
    owner = None
    try:
        owner_config = json.loads(owner_path.read_text(encoding="utf-8"))
        owner = (owner_config.get("slotOwners") or {}).get("08:00") if isinstance(owner_config, dict) else None
        owner_status = "PASS" if owner_config.get("schemaVersion") == 1 and owner == "g2_issuance_cli" else "BLOCKED"
        owner_reason = "" if owner_status == "PASS" else "ISSUANCE_OWNER_CONFLICT:08:00:" + str(owner)
    except (OSError, UnicodeError, json.JSONDecodeError, AttributeError) as exc:
        owner_status, owner_reason = "BLOCKED", "ISSUANCE_OWNER_CONFIG_UNAVAILABLE:" + type(exc).__name__
    result["checks"]["issuance_owner"] = {"status": owner_status, "owner": owner,
                                            "reason": owner_reason}
    if pages_probe is None:
        try:
            pages_ok = _read_only_pages_probe(env.get("REPORT_PAGES_BASE_URL", ""))
            result["checks"]["public_pages"] = {"status": "PASS" if pages_ok else "BLOCKED",
                                                "https_readback": pages_ok}
        except Exception as exc:
            result["checks"]["public_pages"] = {"status": "BLOCKED",
                                                "reason": type(exc).__name__}
    else:
        pages_ok = bool(pages_probe(env.get("REPORT_PAGES_BASE_URL", "")))
        result["checks"]["public_pages"] = {"status": "PASS" if pages_ok else "BLOCKED",
                                            "https_readback": pages_ok}
    statuses = [check.get("status") for check in result["checks"].values()]
    result["status"] = "READY" if statuses and all(status == "PASS" for status in statuses) else "NOT_READY"
    return result


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("config", "environment-gate", "authenticated-readonly"),
                        default="config")
    args = parser.parse_args(argv)
    if args.mode == "config":
        report = run_configuration_diagnostic()
        print(json.dumps(report, ensure_ascii=False, sort_keys=True))
        # Configuration diagnostics are informational and can never say READY.
        return 0
    if args.mode == "environment-gate":
        report = run_environment_gate()
        print(json.dumps(report, ensure_ascii=False, sort_keys=True))
        output_path = os.environ.get("GITHUB_OUTPUT")
        if output_path:
            with open(output_path, "a", encoding="utf-8") as output:
                output.write("ready=" + ("true" if report["status"] == "PASS" else "false") + "\n")
        # A blocked gate is a successful diagnostic job with auth explicitly skipped.
        return 0
    # The protected Environment job provides separate read-only GitHub/Google identities.
    report = run_preflight()
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    return 0 if report["status"] == "READY" else 2


if __name__ == "__main__":
    raise SystemExit(main())
