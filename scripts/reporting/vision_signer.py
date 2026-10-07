"""Create a source and image bound HMAC Vision review without publication effects."""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import hmac
import json
import os
from pathlib import Path
import tempfile
import uuid

from .infographic import (SourceLock, ValidationFailure, identity,
                          validate_image, validate_report, validate_spec,
                          vision_attestation_payload)
from .vision_provider import (FIXTURE_PROVIDER_ID, REQUIRED_VISION_CHECKS,
                              VisionProvider, VisionProviderFailure, VisionReviewResult)


NEGATIVE_CHECKS = {'decorative_charts', 'gauges', 'invented_charts', 'people', 'text_overflow', 'major_typos'}


class VisionSignerFailure(ValueError):
    def __init__(self, reason: str):
        self.reason = reason
        super().__init__(reason)


def _read_json(path: Path, reason: str) -> dict:
    try:
        value = json.loads(path.read_text(encoding='utf-8'))
    except (OSError, UnicodeError, json.JSONDecodeError):
        raise VisionSignerFailure(reason) from None
    if not isinstance(value, dict):
        raise VisionSignerFailure(reason)
    return value


def _image_digest(path: Path) -> tuple[bytes, str]:
    if not path.is_file() or path.stat().st_size == 0:
        raise VisionSignerFailure('IMAGE_NOT_FOUND')
    if path.suffix.lower() not in ('.png', '.jpg', '.jpeg'):
        raise VisionSignerFailure('UNSUPPORTED_IMAGE_FORMAT')
    content = path.read_bytes()
    if path.suffix.lower() == '.png':
        from .gates import GateFailure, validate_png
        try:
            validate_png(content)
        except GateFailure:
            raise VisionSignerFailure('INVALID_IMAGE_BYTES') from None
    elif not content.startswith(b'\xff\xd8\xff') or not content.endswith(b'\xff\xd9'):
        raise VisionSignerFailure('INVALID_IMAGE_BYTES')
    return content, hashlib.sha256(content).hexdigest()


def sign_review(report: dict, spec: dict, image_path: str | Path, source_document_id: str,
                drive_image_file_id: str, provider: VisionProvider) -> dict:
    """Review and sign a local artifact. Any non-PASS verdict is non-signable."""
    secret = os.environ.get('MARKET_REPORT_VISION_HMAC_KEY', '')
    trusted_provider = os.environ.get('MARKET_REPORT_TRUSTED_VISION_PROVIDER', '')
    if not secret or not trusted_provider:
        raise VisionSignerFailure('VISION_PROVIDER_NOT_CONFIGURED')
    secret_bytes = secret.encode('utf-8')
    if len(secret_bytes) < 32:
        raise VisionSignerFailure('VISION_ATTESTATION_KEY_INVALID')
    if provider.provider_id == FIXTURE_PROVIDER_ID and trusted_provider != FIXTURE_PROVIDER_ID:
        raise VisionSignerFailure('VISION_FIXTURE_PROVIDER_FORBIDDEN')
    if provider.provider_id != trusted_provider:
        raise VisionSignerFailure('VISION_PROVIDER_IDENTITY_MISMATCH')
    if not isinstance(source_document_id, str) or not source_document_id.strip():
        raise VisionSignerFailure('SOURCE_DOCUMENT_ID_REQUIRED')
    if not isinstance(drive_image_file_id, str) or not drive_image_file_id.strip():
        raise VisionSignerFailure('DRIVE_IMAGE_FILE_ID_REQUIRED')

    try:
        validate_report(report)
        validate_spec(report, spec)
        lock = SourceLock.create(report)
    except ValidationFailure as exc:
        raise VisionSignerFailure(exc.reason) from None
    actual_doc_id = (report.get('sourceDocument') or {}).get('id')
    if not actual_doc_id or actual_doc_id != source_document_id:
        raise VisionSignerFailure('SOURCE_DOCUMENT_ID_MISMATCH')

    image = Path(image_path)
    initial_bytes, initial_image_sha = _image_digest(image)
    # Provider receives a read-only snapshot so changes to the caller's file during review are detectable.
    with tempfile.TemporaryDirectory(prefix='vision-signer-', dir=Path(__file__).resolve().parents[2]) as temporary:
        snapshot = Path(temporary) / ('review-image' + image.suffix.lower())
        snapshot.write_bytes(initial_bytes)
        report_before = json.dumps(report, ensure_ascii=False, sort_keys=True, separators=(',', ':'))
        try:
            result = provider.review(snapshot, json.loads(report_before), json.loads(json.dumps(spec, ensure_ascii=False)))
            parsed = result if isinstance(result, VisionReviewResult) else VisionReviewResult.parse(result)
        except VisionProviderFailure as exc:
            raise VisionSignerFailure(exc.reason) from None
        except Exception:
            raise VisionSignerFailure('VISION_PROVIDER_ERROR') from None
        if SourceLock.create(report) != lock or json.dumps(report, ensure_ascii=False, sort_keys=True, separators=(',', ':')) != report_before:
            raise VisionSignerFailure('SOURCE_CHANGED_DURING_REVIEW')
        after_bytes, after_image_sha = _image_digest(image)
        if after_image_sha != initial_image_sha or after_bytes != initial_bytes:
            raise VisionSignerFailure('IMAGE_CHANGED_DURING_REVIEW')

    failed = [name for name in REQUIRED_VISION_CHECKS if parsed.checks[name] != 'PASS']
    if failed:
        if any(parsed.checks[name] == 'UNCERTAIN' for name in failed):
            raise VisionSignerFailure('VISION_REVIEW_UNCERTAIN')
        raise VisionSignerFailure('VISION_REVIEW_FAILED')

    checks = {name: (False if name in NEGATIVE_CHECKS else True) for name in REQUIRED_VISION_CHECKS}
    reviewed_at = datetime.now(timezone.utc).isoformat(timespec='seconds').replace('+00:00', 'Z')
    review = {
        'schema': 'market-report-vision-review/v1', 'status': 'VERIFIED',
        'provider': trusted_provider,
        'review_id': f"vr_{identity(report)}_{initial_image_sha[:12]}_{uuid.uuid4().hex[:12]}",
        'report_id': identity(report), 'title': report.get('title'),
        'source_sha256': lock.sha256, 'image_sha256': initial_image_sha,
        'source_document_id': source_document_id, 'drive_image_file_id': drive_image_file_id,
        'reviewed_at': reviewed_at, 'checks': checks,
    }
    review['signature'] = hmac.new(secret_bytes, vision_attestation_payload(review).encode('utf-8'), hashlib.sha256).hexdigest()
    try:
        validation = validate_image(report, spec, str(image), review)
    except ValidationFailure as exc:
        raise VisionSignerFailure(exc.reason) from None
    if validation.get('status') != 'PASS':
        raise VisionSignerFailure('VISION_ATTESTATION_NOT_TRUSTED')
    return review


def write_review(review: dict, output: str | Path) -> None:
    """Atomically create a new local review; never overwrite a prior artifact."""
    target = Path(output).resolve()
    root = Path(__file__).resolve().parents[2]
    try:
        relative = target.relative_to(root)
    except ValueError:
        relative = None
    if relative is not None and (relative.as_posix().lower() == 'reports.json'
            or any(part.lower() in {'reports', 'data', 'images', 'publication-receipts'} for part in relative.parts)):
        raise VisionSignerFailure('PROTECTED_OUTPUT_PATH')
    if target.exists():
        raise VisionSignerFailure('OUTPUT_ALREADY_EXISTS')
    serialized = json.dumps(review, ensure_ascii=False, indent=2) + '\n'
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix='.vision-review-', suffix='.tmp', dir=target.parent)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8', newline='\n') as stream:
            stream.write(serialized)
            stream.flush()
            os.fsync(stream.fileno())
        # Rename is exclusive on Windows; hard-link creation is exclusive on POSIX.
        try:
            if os.name == 'nt':
                os.rename(temporary, target)
            else:
                os.link(temporary, target)
        except FileExistsError:
            raise VisionSignerFailure('OUTPUT_ALREADY_EXISTS') from None
        except OSError:
            if target.exists():
                raise VisionSignerFailure('OUTPUT_ALREADY_EXISTS') from None
            raise VisionSignerFailure('OUTPUT_ATOMIC_CREATE_UNSUPPORTED') from None
    finally:
        try:
            os.unlink(temporary)
        except OSError:
            pass
