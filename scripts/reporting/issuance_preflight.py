"""Read-only production readiness checks for the controlled issuance adapter."""
from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path


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


class DefaultGoogleReadOnlyProbe:
    def __init__(self):
        import google.auth
        from google.auth.transport.requests import AuthorizedSession
        from google.cloud import storage
        scopes = ["https://www.googleapis.com/auth/drive.metadata.readonly",
                  "https://www.googleapis.com/auth/devstorage.read_only",
                  "https://www.googleapis.com/auth/cloud-platform.read-only"]
        credentials, project = google.auth.default(scopes=scopes)
        self.session = AuthorizedSession(credentials)
        self.storage = storage.Client(project=project, credentials=credentials)

    def request(self, *args, **kwargs):
        return self.session.request(*args, **kwargs)

    def get_exact_evidence(self, bucket: str, object_name: str, generation: str) -> bool:
        if not bucket or not object_name or not generation.isdigit():
            return False
        blob = self.storage.bucket(bucket).blob(object_name, generation=int(generation))
        blob.reload()
        return str(blob.generation) == generation

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


def run_preflight(*, env=None, github=None, google_probe=None, dom_runtime=None) -> dict:
    """Inspect config and read permissions only; never call a write endpoint."""
    env = os.environ if env is None else env
    result = {"mode": "READ_ONLY", "checks": {}, "secrets_emitted": False}
    required = ("GITHUB_ACTIONS", "GITHUB_REF", "GITHUB_REPOSITORY",
                "REPORT_ISSUANCE_GITHUB_TOKEN", "REPORT_PAGES_BASE_URL",
                "REPORT_ISSUANCE_ENVIRONMENT",
                "REPORT_EVIDENCE_PROJECT_ID", "REPORT_EVIDENCE_BUCKET",
                "REPORT_EVIDENCE_OBJECT", "REPORT_EVIDENCE_GENERATION",
                "REPORT_ISSUANCE_CLAIM_BUCKET", "REPORT_ISSUANCE_DOCS_FOLDER_ID",
                "REPORT_ISSUANCE_ROOT_FOLDER_ID")
    missing = [key for key in required if not env.get(key)]
    result["checks"]["configuration"] = {"status": "PASS" if not missing else "BLOCKED",
                                          "missing": missing}
    result["checks"]["protected_execution"] = {
        "status": "PASS" if env.get("GITHUB_ACTIONS") == "true" and
        env.get("GITHUB_REF") == "refs/heads/main" and
        env.get("REPORT_ISSUANCE_ENVIRONMENT") == "report-publication" and
        env.get("REPORT_ISSUANCE_APPROVED") == "true" and
        env.get("REPORT_ISSUANCE_WRITE_ENABLED") == "true" else "BLOCKED",
        "approval_present": env.get("REPORT_ISSUANCE_APPROVED") == "true",
        "write_gate_present": env.get("REPORT_ISSUANCE_WRITE_ENABLED") == "true",
    }
    runtime_ready = _chromium_runtime_ready() if dom_runtime is None else bool(dom_runtime)
    result["checks"]["public_dom_runtime"] = {"status": "PASS" if runtime_ready else "BLOCKED",
                                                "node_playwright_chromium_ready": runtime_ready}
    if github is None:
        try:
            github = GitHubReadOnlyProbe(env.get("GITHUB_REPOSITORY", ""),
                                        env.get("REPORT_ISSUANCE_GITHUB_TOKEN", ""))
        except PreflightBlocked as exc:
            result["checks"]["github"] = {"status": "BLOCKED", "reason": str(exc)}
    if github is not None:
        try:
            repo = github.get("")
            environment = github.get("/environments/report-publication")
            workflow = github.get("/actions/workflows/deploy-pages.yml")
            rules = environment.get("protection_rules", [])
            reviewers = [x for rule in rules if rule.get("type") == "required_reviewers"
                         for x in rule.get("reviewers", [])]
            identity_ok = repo.get("full_name", "").lower() == env.get("GITHUB_REPOSITORY", "").lower()
            baseline_ok = (identity_ok and repo.get("permissions", {}).get("push") is True
                           and workflow.get("state") == "active" and bool(reviewers))
            # GitHub's read APIs do not expose the fine-grained token's exact
            # contents:write grant. Repository push access is evidence about
            # the principal, not proof about this credential's token scope.
            scope_attested = env.get("REPORT_ISSUANCE_CONTENTS_WRITE_VERIFIED") == "true"
            result["checks"]["github"] = {"status": ("PASS" if baseline_ok and scope_attested else
                                                              "UNKNOWN" if baseline_ok else "BLOCKED"),
                "repository_identity_match": identity_ok,
                "repository_push_access": repo.get("permissions", {}).get("push") is True,
                "credential_contents_write_permission": "ADMIN_ATTESTED" if scope_attested else "UNKNOWN",
                "contents_write_admin_attestation_present": scope_attested,
                "actions_workflow_read": workflow.get("state") == "active",
                "pages_workflow_active": workflow.get("state") == "active",
                "environment_required_reviewers": len(reviewers)}
        except (PreflightBlocked, KeyError, TypeError, AttributeError) as exc:
            result["checks"]["github"] = {"status": "BLOCKED", "reason": str(exc)}
    if google_probe is None:
        try:
            google_probe = DefaultGoogleReadOnlyProbe()
        except Exception as exc:
            result["checks"]["google"] = {"status": "UNKNOWN", "reason": type(exc).__name__}
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
            google_ok = drive_ok and exact_read and claim_permissions.get("create") is True
            result["checks"]["google"] = {"status": "PASS" if google_ok else "BLOCKED",
                                            "drive_folders_read": True,
                                            "docs_folder_can_add_children": drive_ok,
                                            "evidence_generation_read": bool(exact_read),
                                            "claim_read_permission": claim_permissions.get("read", False),
                                            "claim_create_permission": claim_permissions.get("create", False)}
        except Exception as exc:
            result["checks"]["google"] = {"status": "BLOCKED", "reason": str(exc)}
    statuses = [check.get("status") for check in result["checks"].values()]
    result["status"] = "READY" if statuses and all(status == "PASS" for status in statuses) else "NOT_READY"
    return result


def main() -> int:
    # The same Google principal must be configured for Drive and Storage. This
    # probe deliberately exposes no token, key material, or report contents.
    report = run_preflight()
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    return 0 if report["status"] == "READY" else 2


if __name__ == "__main__":
    raise SystemExit(main())
