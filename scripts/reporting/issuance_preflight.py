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


class DefaultGoogleReadOnlyProbe:
    def __init__(self):
        import google.auth
        from google.auth.transport.requests import AuthorizedSession
        from google.cloud import storage
        scopes = ["https://www.googleapis.com/auth/drive.metadata.readonly",
                  "https://www.googleapis.com/auth/devstorage.read_only",
                  "https://www.googleapis.com/auth/cloud-platform.read-only"]
        raw = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON", "")
        if raw:
            from google.oauth2 import service_account
            credentials = service_account.Credentials.from_service_account_info(
                json.loads(raw), scopes=scopes)
            project = credentials.project_id
        else:
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
        frozen_at = aware(g2.get("frozen_at", ""))
        report_slot = aware(report["date"] + "T" + report["time"] + ":00+09:00")
        if report["time"] != "08:00" or frozen_at > report_slot:
            raise PreflightBlocked("G2_FREEZE_TIME_OR_SLOT_INVALID")
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
                "g2_bundle_sha256": g2_object["sha256"],
                "evidence_generation": evidence_object["generation"],
                "evidence_sha256": evidence_object["sha256"],
                "evidence_id": evidence["evidenceId"],
                "snapshot_id": evidence["snapshot"]["snapshot_id"]}
    except (PreflightBlocked, KeyError, TypeError, ValueError) as exc:
        return {"status": "BLOCKED", "reason": str(exc)}


def run_configuration_diagnostic(*, env=None) -> dict:
    """No-secret static diagnosis; never reports READY or contacts external services."""
    env = os.environ if env is None else env
    required = ("GITHUB_REPOSITORY", "REPORT_ISSUANCE_ENVIRONMENT",
                "REPORT_PAGES_BASE_URL", "REPORT_EVIDENCE_PROJECT_ID",
                "REPORT_EVIDENCE_BUCKET", "REPORT_ISSUANCE_CLAIM_BUCKET",
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
            protected_ready = protected_context and bool(reviewers)
            result["checks"]["protected_execution"] = {
                "status": "PASS" if protected_ready else "BLOCKED",
                "workflow_main_ref": env.get("GITHUB_REF") == "refs/heads/main",
                "environment_name_matches": env.get("REPORT_ISSUANCE_ENVIRONMENT") == "report-publication",
                "reviewer_gate_configured": bool(reviewers),
                "environment_required_reviewers": len(reviewers),
                "approval_for_current_run": "NOT_INFERRED",
                "approval_environment_variable_ignored": True,
                "write_gate_present": env.get("REPORT_ISSUANCE_WRITE_ENABLED") == "true",
            }
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
    result["checks"]["g2_evidence_binding"] = _validate_g2_evidence_binding(
        env=env, google_probe=google_probe) if google_probe is not None else {
            "status": "BLOCKED", "reason": "BLOCKED_G2_PRODUCER_MISSING"
        }
    # An object and matching hashes do not prove which actor produced it. No
    # trusted G2 producer is registered in this repository yet.
    result["checks"]["g2_producer_identity"] = {
        "status": "BLOCKED", "reason": "BLOCKED_G2_PRODUCER_MISSING",
        "producer_registered": False, "producer_identity_verified": False,
    }
    owner_path = Path(env.get("REPORT_ISSUANCE_OWNER_CONFIG_PATH",
                              Path(__file__).resolve().parents[2] / "config" / "issuance_ownership.json"))
    try:
        owner_config = json.loads(owner_path.read_text(encoding="utf-8"))
        owner = (owner_config.get("slotOwners") or {}).get("08:00")
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
    parser.add_argument("--mode", choices=("config", "authenticated-readonly"),
                        default="config")
    args = parser.parse_args(argv)
    if args.mode == "config":
        report = run_configuration_diagnostic()
        print(json.dumps(report, ensure_ascii=False, sort_keys=True))
        # Configuration diagnostics are informational and can never say READY.
        return 0
    # The protected Environment job provides separate read-only GitHub/Google identities.
    report = run_preflight()
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    return 0 if report["status"] == "READY" else 2


if __name__ == "__main__":
    raise SystemExit(main())
