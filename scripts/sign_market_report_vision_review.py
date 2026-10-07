#!/usr/bin/env python3
"""Create a local signed Vision review. This command has no publication mode."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from reporting.infographic import identity  # noqa: E402
from reporting.vision_provider import (  # noqa: E402
    FIXTURE_PROVIDER_ID, ExternalVisionProvider, FixtureVisionProvider,
)
from reporting.vision_signer import VisionSignerFailure, _read_json, sign_review, write_review  # noqa: E402


def _local_output(path: Path) -> bool:
    resolved = path.resolve()
    try:
        relative = resolved.relative_to(ROOT.resolve())
    except ValueError:
        return True
    if relative.as_posix().lower() == 'reports.json':
        return False
    return not any(part.lower() in {'reports', 'data', 'images', 'publication-receipts'} for part in relative.parts)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--report', required=True)
    parser.add_argument('--spec', required=True)
    parser.add_argument('--image', required=True)
    parser.add_argument('--source-document-id', required=True)
    parser.add_argument('--drive-image-file-id', required=True)
    parser.add_argument('--output', required=True)
    parser.add_argument('--provider', choices=('fixture', 'external'), default='external')
    parser.add_argument('--test-only', action='store_true', help='Explicitly authorize the non-production fixture provider.')
    parser.add_argument('--dry-run', action='store_true', help='Required acknowledgement: output remains a local review file.')
    args = parser.parse_args(argv)
    if not args.dry_run:
        print(json.dumps({'status': 'NOT_RUN', 'reason': 'DRY_RUN_REQUIRED', 'production_write': False}))
        return 2
    output = Path(args.output)
    if not _local_output(output):
        print(json.dumps({'status': 'FAIL', 'reason': 'PROTECTED_OUTPUT_PATH', 'production_write': False}))
        return 2
    try:
        if args.provider == 'fixture' and not args.test_only:
            raise VisionSignerFailure('VISION_FIXTURE_PROVIDER_FORBIDDEN')
        if args.test_only and args.provider != 'fixture':
            raise VisionSignerFailure('VISION_FIXTURE_PROVIDER_FORBIDDEN')
        configured_provider = os.environ.get('MARKET_REPORT_TRUSTED_VISION_PROVIDER', '')
        if configured_provider == FIXTURE_PROVIDER_ID and args.provider == 'external':
            raise VisionSignerFailure('VISION_FIXTURE_PROVIDER_FORBIDDEN')
        report = _read_json(Path(args.report), 'REPORT_INPUT_INVALID')
        spec = _read_json(Path(args.spec), 'SPEC_INPUT_INVALID')
        report_id = identity(report)
        expected_name = f'マーケットレポート_{report_id}.vision-review.json'
        if output.name != expected_name:
            raise VisionSignerFailure('OUTPUT_NAME_MISMATCH')
        if args.provider == 'fixture':
            provider = FixtureVisionProvider()
        else:
            provider_id = configured_provider
            if not provider_id or provider_id == FIXTURE_PROVIDER_ID:
                raise VisionSignerFailure('VISION_FIXTURE_PROVIDER_FORBIDDEN' if provider_id == FIXTURE_PROVIDER_ID
                                          else 'VISION_PROVIDER_NOT_CONFIGURED')
            provider = ExternalVisionProvider(provider_id)
        review = sign_review(report, spec, args.image, args.source_document_id,
                             args.drive_image_file_id, provider,
                             allow_fixture_test_provider=args.test_only)
        write_review(review, output)
    except VisionSignerFailure as exc:
        print(json.dumps({'status': 'NOT_RUN' if exc.reason == 'VISION_PROVIDER_NOT_CONFIGURED' else 'FAIL',
                          'reason': exc.reason, 'production_write': False}, ensure_ascii=False))
        return 1
    except Exception:
        print(json.dumps({'status': 'FAIL', 'reason': 'SIGNING_FAILED', 'production_write': False}, ensure_ascii=False))
        return 1
    print(json.dumps({'status': 'PASS', 'report_id': review['report_id'], 'provider': review['provider'],
                      'source_sha256': review['source_sha256'], 'image_sha256': review['image_sha256'],
                      'signature_created': True, 'production_write': False,
                      'test_only': args.test_only, 'output': str(output)}, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
