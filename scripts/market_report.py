"""Market report validation CLI. All publication commands are dry-run only."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
from reporting.infographic import (  # noqa: E402
    ValidationFailure, build_generation_prompt, build_spec, completion_gate, result,
    validate_image, validate_market_data, validate_publication_evidence, validate_report, validate_spec,
)


def read_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def emit(value, output=None):
    serialized = json.dumps(value, ensure_ascii=False, indent=2)
    if output:
        path = Path(output)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(serialized + '\n', encoding='utf-8')
    print(serialized)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    p = commands.add_parser('validate-report')
    p.add_argument('--report', required=True, type=Path)
    p.add_argument('--report-id')
    p.add_argument('--output', type=Path)
    p = commands.add_parser('build-infographic-spec')
    p.add_argument('--report', required=True, type=Path)
    p.add_argument('--output', required=True, type=Path)
    p = commands.add_parser('validate-infographic-spec')
    p.add_argument('--report', required=True, type=Path)
    p.add_argument('--spec', required=True, type=Path)
    p.add_argument('--output', type=Path)
    p = commands.add_parser('build-infographic-prompt')
    p.add_argument('--report', required=True, type=Path)
    p.add_argument('--spec', required=True, type=Path)
    p.add_argument('--output', type=Path)
    p = commands.add_parser('validate-image')
    p.add_argument('--report', required=True, type=Path)
    p.add_argument('--spec', required=True, type=Path)
    p.add_argument('--image', required=True, type=Path)
    p.add_argument('--vision-review', type=Path)
    p.add_argument('--output', type=Path)
    p = commands.add_parser('full-validation')
    p.add_argument('--report-id', required=True)
    p.add_argument('--report', type=Path)
    p.add_argument('--spec', type=Path)
    p.add_argument('--image', type=Path)
    p.add_argument('--vision-review', type=Path)
    p.add_argument('--dry-run', action='store_true', required=True)
    p.add_argument('--output', type=Path)
    p = commands.add_parser('publish')
    p.add_argument('--report', required=True, type=Path)
    p.add_argument('--spec', required=True, type=Path)
    p.add_argument('--image', required=True, type=Path)
    p.add_argument('--vision-review', type=Path)
    p.add_argument('--evidence', type=Path, help='captured readback evidence for Docs/Drive/GitHub/receipt/Portal')
    p.add_argument('--dry-run', action='store_true', required=True)
    p.add_argument('--force', action='store_true')
    p.add_argument('--output', type=Path)

    args = parser.parse_args(argv)
    try:
        report = read_json(args.report) if getattr(args, 'report', None) else None
        if args.command == 'validate-report':
            value = {'report_id': None}
            try:
                value['market_data'] = validate_market_data(report)
                value['body'] = validate_report(report)
                value['report_id'] = value['body']['report_id']
                value['status'] = 'PASS' if value['market_data']['status'] == 'PASS' else 'WATCH'
                if value['status'] != 'PASS':
                    value['failure_reason'] = 'MARKET_DATA_NOT_PASS'
                    emit(value, args.output)
                    return 1
            except ValidationFailure as exc:
                value.update({'status': 'FAIL', 'failure_reason': exc.reason, 'details': exc.details})
                raise ValidationFailure(exc.reason, value)
            if args.report_id and value['report_id'] != args.report_id:
                raise ValidationFailure('REPORT_ID_MISMATCH')
        elif args.command == 'build-infographic-spec':
            value = build_spec(report)
            emit(value, args.output)
            return 0
        elif args.command == 'validate-infographic-spec':
            value = validate_spec(report, read_json(args.spec))
        elif args.command == 'build-infographic-prompt':
            value = {'status': 'PASS', 'prompt': build_generation_prompt(report, read_json(args.spec))}
        elif args.command == 'validate-image':
            value = validate_image(report, read_json(args.spec), str(args.image), read_json(args.vision_review) if args.vision_review else None)
        elif args.command == 'full-validation':
            rid = args.report_id
            if report is None:
                path = ROOT/'reports'/f'{rid}.json'
                report = read_json(path) if path.is_file() else None
            stages = {name: 'NOT_RUN' for name in ('market_data', 'report_body', 'infographic', 'google_docs', 'drive_image', 'github', 'receipt', 'portal')}
            failures = []
            pre_status = 'NOT_RUN'
            post_status = 'NOT_RUN'
            value = {'report_id': rid, 'dry_run': True, 'stages': stages, 'overall': 'INCOMPLETE', 'failure_reasons': failures}
            if args.output is None:
                args.output = ROOT/'validation'/rid/'full_validation.json'
            try:
                if report is None:
                    raise ValidationFailure('SOURCE_REPORT_NOT_FOUND')
                report_result = validate_report(report)
                if report_result['report_id'] != rid:
                    raise ValidationFailure('REPORT_ID_MISMATCH')
                stages['report_body'] = 'PASS'
            except ValidationFailure as exc:
                failures.append(exc.reason)
                stages['report_body'] = 'FAIL'
                value['body_validation'] = {'status': 'FAIL', 'failure_reason': exc.reason, 'details': exc.details}
            if report is not None:
                try:
                    value['market_data_validation'] = validate_market_data(report)
                    stages['market_data'] = value['market_data_validation']['status']
                    if stages['market_data'] != 'PASS':
                        failures.append('MARKET_DATA_NOT_PASS')
                except ValidationFailure as exc:
                    failures.append(exc.reason)
                    stages['market_data'] = 'FAIL'
                    value['market_data_validation'] = {'status': 'FAIL', 'failure_reason': exc.reason, 'details': exc.details}
            spec_path = args.spec or ROOT/'validation'/rid/'infographic_spec.json'
            if report is not None and stages['report_body'] == 'PASS' and stages['market_data'] == 'PASS' and spec_path.is_file():
                try:
                    spec_result = validate_spec(report, read_json(spec_path))
                    pre_status = 'PASS'
                except ValidationFailure as exc:
                    failures.append(exc.reason)
                    pre_status = 'FAIL'
                    stages['infographic'] = 'FAIL'
            elif not spec_path.is_file():
                failures.append('INFOGRAPHIC_SPEC_NOT_FOUND')
            if report is not None and pre_status == 'PASS' and args.image:
                try:
                    img_result = validate_image(report, read_json(spec_path), str(args.image), read_json(args.vision_review) if args.vision_review else None)
                    post_status = img_result['status']
                    stages['infographic'] = img_result['status']
                    if img_result.get('failure_reason'):
                        failures.append(img_result['failure_reason'])
                except ValidationFailure as exc:
                    failures.append(exc.reason)
                    stages['infographic'] = 'FAIL'
                    post_status = 'FAIL'
            elif pre_status == 'PASS':
                failures.append('POST_GENERATION_IMAGE_NOT_PROVIDED')
            value.update({'body_validation': value.get('body_validation', locals().get('report_result')),
                          'infographic_validation': {'pre_generation': {'status': pre_status, 'result': locals().get('spec_result')},
                                                     'post_generation': {'status': post_status, 'result': locals().get('img_result')}},
                          'image_validation': locals().get('img_result')})
            value['overall'] = completion_gate(stages)
            value['side_effects_performed'] = False
            audit_dir = ROOT/'validation'/rid
            audit_dir.mkdir(parents=True, exist_ok=True)
            if spec_path.is_file() and spec_path.resolve() != (audit_dir/'infographic_spec.json').resolve():
                (audit_dir/'infographic_spec.json').write_bytes(spec_path.read_bytes())
            stamp = datetime.now(timezone.utc).isoformat()
            (audit_dir/'report_validation.json').write_text(json.dumps({'run_at': stamp, 'market_data': value.get('market_data_validation'),
                                                                        'report_body': value.get('body_validation')}, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
            (audit_dir/'pre_validation.json').write_text(json.dumps({'run_at': stamp, 'status': pre_status,
                                                                     'failure_reasons': failures, 'report_id': rid}, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
            if locals().get('spec_result') is not None:
                (audit_dir/'pre_validation_result.json').write_text(json.dumps(spec_result, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
            if locals().get('img_result') is not None:
                (audit_dir/'post_validation.json').write_text(json.dumps(img_result, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
            (audit_dir/'publication_validation.json').write_text(json.dumps({'run_at': stamp, 'stages': stages,
                                                                             'overall': value['overall'], 'side_effects_performed': False}, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
        elif args.command == 'publish':
            value = {'report_id': None, 'mode': 'DRY_RUN', 'production_connected': False, 'side_effects_performed': False,
                     'stages': {name: 'NOT_RUN' for name in ('market_data', 'report_body', 'infographic', 'google_docs', 'drive_image', 'github', 'receipt', 'portal')}}
            try:
                value['market_data_validation'] = validate_market_data(report)
                value['stages']['market_data'] = value['market_data_validation']['status']
                if value['stages']['market_data'] != 'PASS':
                    raise ValidationFailure('MARKET_DATA_NOT_PASS')
                body = validate_report(report)
                rid = body['report_id']; value['report_id'] = rid
                value['stages']['report_body'] = 'PASS'
                validated_spec = read_json(args.spec)
                value['infographic_validation'] = validate_spec(report, validated_spec)
                image = validate_image(report, read_json(args.spec), str(args.image), read_json(args.vision_review) if args.vision_review else None)
                value['stages']['infographic'] = image['status']
                if args.evidence:
                    observed = read_json(args.evidence)
                    value['readback_claims_validation'] = validate_publication_evidence(report, observed, image_sha256=image['image_sha256'])
                    value['failure_reason'] = 'LIVE_READBACK_ADAPTERS_NOT_CONFIGURED'
                else:
                    value['failure_reason'] = 'PUBLICATION_READBACK_EVIDENCE_NOT_PROVIDED'
                if args.force and any(status != 'PASS' for status in value['stages'].values()):
                    value['validation_status'] = 'OVERRIDDEN'
                value['overall'] = completion_gate(value['stages'])
                value['publish_allowed'] = False
                value['live_adapters_configured'] = False
            except ValidationFailure as exc:
                value['failure_reason'] = exc.reason
                value['details'] = exc.details
                value['overall'] = 'INCOMPLETE'
                value['publish_allowed'] = False
                if args.force:
                    value['validation_status'] = 'OVERRIDDEN'
        emit(value, getattr(args, 'output', None))
        return 0 if value.get('status') == 'PASS' or value.get('overall') == 'COMPLETE' else 1
    except (ValidationFailure, ValueError, KeyError, TypeError, OSError, json.JSONDecodeError) as exc:
        reason = exc.reason if isinstance(exc, ValidationFailure) else 'INPUT_INVALID'
        value = result('FAIL', reason, getattr(exc, 'details', str(exc)))
        emit(value, getattr(args, 'output', None))
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
