"""Concrete, fail-closed adapter for the existing canonical importer and Pages.

Production credentials are resolved only when explicitly constructing the
GitHub client. Unit tests inject in-memory collaborators and never touch live
services. The Drive importer is target-scoped and does not use the scheduled
three-day scan.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import base64
import os
from pathlib import Path
import time
from urllib.parse import quote

from .issuance_pipeline import IssuanceBlocked, PortalReadback


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _json_bytes(value: dict) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def _target_evidence_path(root: Path, report: dict) -> Path:
    return root / "data" / "report-evidence" / f"{report['date']}_{report['time'].replace(':', '-')}-r{report['revision']}.json"


def stage_pinned_evidence(root: Path, report: dict, evidence: dict) -> dict:
    """Create-only stage the already generation-pinned evidence for importer reuse."""
    envelope = evidence.get("evidence_object") or {}
    payload = envelope.get("bytes")
    if (envelope.get("environment") != "PRODUCTION" or type(envelope.get("generation")) is not int or
            envelope["generation"] <= 0 or envelope.get("generation_readback") != envelope.get("generation") or
            not isinstance(payload, str)):
        raise IssuanceBlocked("ISSUANCE_EVIDENCE_PIN_REQUIRED")
    raw = payload.encode("utf-8")
    digest = _sha(raw)
    if digest != envelope.get("object_sha256"):
        raise IssuanceBlocked("ISSUANCE_EVIDENCE_HASH_MISMATCH")
    try:
        decoded = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise IssuanceBlocked("ISSUANCE_EVIDENCE_INVALID") from exc
    if (decoded.get("evidenceId") != evidence.get("evidence_id") or
            decoded.get("reportId") != report.get("report_id") or
            decoded.get("revision") != report.get("revision") or
            (decoded.get("snapshot") or {}).get("snapshot_id") != report.get("snapshot_id")):
        raise IssuanceBlocked("ISSUANCE_EVIDENCE_IDENTITY_MISMATCH")
    path = _target_evidence_path(root, report)
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with path.open("xb") as handle:
            handle.write(raw)
    except FileExistsError:
        if path.is_symlink() or path.read_bytes() != raw:
            raise IssuanceBlocked("ISSUANCE_EVIDENCE_EXISTING_CONFLICT")
    except OSError as exc:
        raise IssuanceBlocked("ISSUANCE_EVIDENCE_STAGE_FAILED") from exc
    if path.read_bytes() != raw or _sha(path.read_bytes()) != digest:
        raise IssuanceBlocked("ISSUANCE_EVIDENCE_STAGE_READBACK_FAILED")
    return {"path": path, "generation": envelope["generation"], "sha256": digest}


class StrictGoogleDocsImporter:
    """Target-only bridge into `sync_reports_from_drive`'s strict validators."""

    def __init__(self, *, root: Path, docs_session, projection_runner=None):
        self.root = Path(root)
        self.docs_session = docs_session
        self.projection_runner = projection_runner or self._run_projection

    def _run_projection(self):
        import subprocess
        import sys
        for script in ("scripts/sync_latest_report_publication.py",
                       "scripts/build_reports.py", "scripts/verify_publication_consistency.py"):
            args = [sys.executable, script]
            if script.endswith("build_reports.py"):
                args.append("--canonical-only")
            subprocess.run(args, cwd=self.root, check=True)

    def import_exact(self, *, report: dict, docs, evidence: dict) -> tuple[dict, dict]:
        from scripts.sync_reports_from_drive import import_exact_issuance_doc
        staged = stage_pinned_evidence(self.root, report, evidence)
        canonical, receipt = import_exact_issuance_doc(
            self.root, report={**report, "evidence_id": evidence["evidence_id"]},
            docs=docs, session=self.docs_session,
        )
        if (canonical.get("report_id") != report.get("report_id") or
                canonical.get("revision") != report.get("revision") or
                canonical.get("bodyHash") != report.get("bodyHash") or
                canonical.get("sourceDocument", {}).get("id") != docs.document_id or
                canonical.get("sourceRevisionId") != docs.document_revision_id or
                receipt.get("evidenceId") != evidence.get("evidence_id") or
                receipt.get("snapshotId") != report.get("snapshot_id") or
                staged["sha256"] != evidence["evidence_object"].get("object_sha256")):
            raise IssuanceBlocked("STRICT_IMPORTER_READBACK_MISMATCH")
        self.projection_runner()
        return canonical, receipt


class GitHubRestClient:
    """Minimal Git Database API client for one atomic, compare-and-swap commit."""

    API = "https://api.github.com"

    def __init__(self, *, repository: str, token: str, session=None):
        if not repository or "/" not in repository or not token:
            raise IssuanceBlocked("GITHUB_PUBLICATION_CREDENTIALS_REQUIRED")
        if session is None:
            import requests
            session = requests.Session()
        self.repository, self._session = repository, session
        self._headers = {"Accept": "application/vnd.github+json", "Authorization": f"Bearer {token}",
                         "X-GitHub-Api-Version": "2022-11-28"}

    def _request(self, method, path, *, expected=(200,), body=None):
        response = self._session.request(method, self.API + "/repos/" + self.repository + path,
                                         headers=self._headers, json=body, timeout=30)
        if response.status_code not in expected:
            raise IssuanceBlocked(f"GITHUB_{method}_FAILED:{response.status_code}")
        return response.json() if response.content else {}

    def publish_files(self, *, expected_head: str, files: dict[str, bytes], message: str) -> str:
        ref = self._request("GET", "/git/ref/heads/main")
        head = ref["object"]["sha"]
        if head != expected_head:
            raise IssuanceBlocked("GITHUB_MAIN_MOVED_RECONCILE_REQUIRED")
        unchanged = True
        for path, expected in files.items():
            response = self._session.request(
                "GET", self.API + "/repos/" + self.repository + "/contents/" + quote(path, safe="/") + f"?ref={head}",
                headers=self._headers, timeout=30,
            )
            if response.status_code == 404:
                unchanged = False
                break
            if response.status_code != 200:
                raise IssuanceBlocked(f"GITHUB_GET_FAILED:{response.status_code}")
            try:
                actual = base64.b64decode(response.json()["content"], validate=False)
            except (KeyError, ValueError, TypeError) as exc:
                raise IssuanceBlocked("GITHUB_FILE_READBACK_INVALID") from exc
            if actual != expected:
                unchanged = False
                break
        if unchanged:
            return head  # identical report/revision retry: no duplicate commit
        commit = self._request("GET", f"/git/commits/{head}")
        tree_entries = []
        for path, data in sorted(files.items()):
            if path.startswith("/") or ".." in Path(path).parts or "\\" in path:
                raise IssuanceBlocked("GITHUB_PATH_INVALID")
            blob = self._request("POST", "/git/blobs", expected=(201,), body={
                "content": data.decode("utf-8"), "encoding": "utf-8"})
            tree_entries.append({"path": path, "mode": "100644", "type": "blob", "sha": blob["sha"]})
        tree = self._request("POST", "/git/trees", expected=(201,), body={
            "base_tree": commit["tree"]["sha"], "tree": tree_entries})
        created = self._request("POST", "/git/commits", expected=(201,), body={
            "message": message, "tree": tree["sha"], "parents": [head]})
        self._request("PATCH", "/git/refs/heads/main", expected=(200,), body={
            "sha": created["sha"], "force": False})
        observed = self._request("GET", "/git/ref/heads/main")["object"]["sha"]
        if observed != created["sha"]:
            raise IssuanceBlocked("GITHUB_MAIN_COMMIT_READBACK_MISMATCH")
        return observed

    def verify_files(self, *, commit_sha: str, files: dict[str, bytes]) -> None:
        for path, expected in files.items():
            encoded_path = quote(path, safe="/")
            item = self._request("GET", f"/contents/{encoded_path}?ref={commit_sha}")
            try:
                actual = base64.b64decode(item["content"], validate=False)
            except (KeyError, ValueError, TypeError) as exc:
                raise IssuanceBlocked("GITHUB_FILE_READBACK_INVALID") from exc
            if actual != expected:
                raise IssuanceBlocked("GITHUB_FILE_READBACK_MISMATCH:" + path)

    def workflow_runs(self, workflow: str, head_sha: str):
        return self._request("GET", f"/actions/workflows/{quote(workflow, safe='')}/runs?head_sha={head_sha}&per_page=20")


class GitHubPagesVerifier:
    """Poll the existing Pages workflow and compare the actual public JSON body."""

    def __init__(self, *, github: GitHubRestClient, base_url: str, public_session=None,
                 poll_interval: float = 5, timeout: float = 900):
        if not base_url.startswith("https://"):
            raise IssuanceBlocked("PAGES_HTTPS_URL_REQUIRED")
        if public_session is None:
            import requests
            public_session = requests.Session()
        self.github, self.base_url, self._public = github, base_url.rstrip("/"), public_session
        self.poll_interval, self.timeout = poll_interval, timeout

    def verify(self, *, report: dict, commit_sha: str) -> tuple[str, str]:
        deadline = time.monotonic() + self.timeout
        run_id = None
        while time.monotonic() < deadline:
            runs = self.github.workflow_runs("deploy-pages.yml", commit_sha).get("workflow_runs", [])
            exact = [r for r in runs if r.get("head_sha") == commit_sha]
            if exact:
                run = sorted(exact, key=lambda row: row.get("run_number", 0), reverse=True)[0]
                run_id = str(run.get("id", ""))
                if run.get("status") == "completed":
                    if run.get("conclusion") != "success":
                        raise IssuanceBlocked("PAGES_DEPLOYMENT_FAILED")
                    break
            time.sleep(min(self.poll_interval, max(0, deadline - time.monotonic())))
        else:
            raise IssuanceBlocked("PAGES_DEPLOYMENT_TIMEOUT")
        path = f"reports/{report['date']}_{report['time'].replace(':', '-')}.json"
        response = self._public.get(self.base_url + "/" + path, timeout=30)
        if response.status_code != 200:
            raise IssuanceBlocked("PAGES_PUBLIC_REPORT_UNAVAILABLE")
        try:
            public = response.json()
        except Exception as exc:
            raise IssuanceBlocked("PAGES_PUBLIC_REPORT_INVALID_JSON") from exc
        if (public.get("fullText") != report.get("fullText") or
                public.get("bodyHash") != report.get("bodyHash") or
                public.get("report_id") != report.get("report_id") or
                public.get("revision") != report.get("revision")):
            raise IssuanceBlocked("PAGES_PUBLIC_BODY_MISMATCH")
        return run_id, self.base_url + "/" + path


@dataclass
class GitHubPortalPublisher:
    """Production PortalPublisher: exact import -> atomic main commit -> Pages readback."""
    importer: StrictGoogleDocsImporter
    github: GitHubRestClient
    pages: GitHubPagesVerifier
    expected_head: str
    environment: str = "TEST_ONLY"

    @classmethod
    def from_environment(cls, *, importer: StrictGoogleDocsImporter, expected_head: str):
        if os.environ.get("REPORT_ISSUANCE_WRITE_ENABLED") != "true":
            raise IssuanceBlocked("PRODUCTION_ISSUANCE_WRITE_NOT_ENABLED")
        if (os.environ.get("GITHUB_ACTIONS") != "true" or
                os.environ.get("GITHUB_REF") != "refs/heads/main" or
                os.environ.get("REPORT_ISSUANCE_APPROVED") != "true"):
            raise IssuanceBlocked("PROTECTED_MAIN_WORKFLOW_APPROVAL_REQUIRED")
        import subprocess
        if subprocess.check_output(["git", "branch", "--show-current"], cwd=importer.root, text=True).strip() != "main":
            raise IssuanceBlocked("ISSUANCE_REQUIRES_MAIN_CHECKOUT")
        local_head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=importer.root, text=True).strip()
        if local_head != expected_head:
            raise IssuanceBlocked("ISSUANCE_CHECKOUT_HEAD_MISMATCH")
        repository = os.environ.get("GITHUB_REPOSITORY", "")
        token = os.environ.get("REPORT_ISSUANCE_GITHUB_TOKEN", "")
        base_url = os.environ.get("REPORT_PAGES_BASE_URL", "")
        github = GitHubRestClient(repository=repository, token=token)
        return cls(importer, github, GitHubPagesVerifier(github=github, base_url=base_url), expected_head,
                   environment="PRODUCTION")

    def publish_and_readback(self, *, report: dict, docs, evidence: dict) -> PortalReadback:
        stage = "STRICT_IMPORTER"
        completed = []
        try:
            canonical, receipt = self.importer.import_exact(report=report, docs=docs, evidence=evidence)
            completed.append("STRICT_IMPORTER")
            receipt_bytes = _json_bytes(receipt)
            canonical_bytes = _json_bytes(canonical)
            paths = {
                f"reports/{report['date']}_{report['time'].replace(':', '-')}.json": canonical_bytes,
                f"publication-receipts/{report['date']}_{report['time'].replace(':', '-')}.json": receipt_bytes,
            }
            # Indexes are produced by the established projection scripts; include only
            # existing publication artifacts and never stage unrelated repository files.
            for relative in ("reports.json", "data/latest-report.json", "data/dashboard.json"):
                file_path = self.importer.root / relative
                if file_path.is_file():
                    paths[relative] = file_path.read_bytes()
            stage = "GITHUB_MAIN_COMMIT"
            commit_sha = self.github.publish_files(
                expected_head=self.expected_head, files=paths,
                message=f"Publish market report {report['report_id']} r{report['revision']}",
            )
            completed.append("GITHUB_MAIN_COMMIT")
            stage = "GITHUB_READBACK"
            self.github.verify_files(commit_sha=commit_sha, files=paths)
            completed.append("GITHUB_CANONICAL_AND_RECEIPT_READBACK")
            stage = "PAGES_DEPLOYMENT_AND_PUBLIC_READBACK"
            run_id, public_url = self.pages.verify(report=canonical, commit_sha=commit_sha)
            completed.append("PAGES_PUBLIC_BODY_READBACK")
            return PortalReadback(
                report_id=report["report_id"], revision=report["revision"],
                snapshot_id=evidence["snapshot"]["snapshot_id"], document_id=docs.document_id,
                document_revision_id=docs.document_revision_id, full_text=canonical["fullText"],
                body_hash=canonical["bodyHash"], status="PUBLISHED",
                canonical_commit_sha=commit_sha, receipt_sha256=_sha(receipt_bytes),
                pages_run_id=run_id, public_url=public_url, public_body_verified=True,
                environment=self.environment,
            )
        except IssuanceBlocked as exc:
            if exc.stage == "VALIDATION":
                exc.stage = stage
            if not exc.completed_stages:
                exc.completed_stages = tuple(completed)
            if stage == "PAGES_DEPLOYMENT_AND_PUBLIC_READBACK" and "GITHUB_CANONICAL_AND_RECEIPT_READBACK" in completed:
                exc.retryable = True
            elif stage == "GITHUB_READBACK":
                exc.retryable = False  # reconcile remote ref/files before any retry
            raise
        except Exception as exc:
            raise IssuanceBlocked(
                "ISSUANCE_FAILED_AFTER:" + type(exc).__name__, stage=stage,
                completed_stages=tuple(completed),
                retryable=(stage == "PAGES_DEPLOYMENT_AND_PUBLIC_READBACK" and
                           "GITHUB_CANONICAL_AND_RECEIPT_READBACK" in completed),
            ) from exc
