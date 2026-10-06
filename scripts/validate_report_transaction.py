"""Read-only foundation entry point. Never saves, registers Git or deploys.

Input holds a persisted explicit context and snapshot plus original ReportObject
and observed evidence. Retry supplies the same context/snapshot, never latest.
"""
import argparse
import base64
import json
from pathlib import Path
from reporting.context import ReportContext, ExecutionContext
from reporting.snapshot import MarketDataSnapshot, plain
from reporting.report import ReportObject
from reporting.gates import GateFailure, Transaction


def validate(payload):
    execution = ExecutionContext(**payload['execution_context'])
    tx = Transaction.begin(ReportContext(**payload['context']), MarketDataSnapshot.restore(payload['snapshot']), ReportObject.restore(payload['report']))
    evidence = payload.get('evidence', {})
    if 'docs' in evidence:
        tx = tx.verify_docs(**evidence['docs'])
    if 'png' in evidence:
        png = dict(evidence['png'])
        png['png_bytes'] = base64.b64decode(png.pop('png_base64'), validate=True)
        tx = tx.verify_png(**png)
    if 'manifest_created_at' in evidence:
        tx = tx.create_manifest(evidence['manifest_created_at'])
    if 'git' in evidence:
        tx = tx.verify_git(**evidence['git'])
    if 'actions' in evidence:
        tx = tx.verify_actions(**evidence['actions'])
    if 'pages' in evidence:
        tx = tx.verify_pages(**evidence['pages'])
    if evidence.get('create_receipt'):
        tx = tx.create_receipt()
    return {'execution_context': plain(execution), 'passed': tx.passed, 'can_register_git': tx.can_register_git, 'can_deploy_pages': tx.can_deploy_pages,
            'manifest': plain(tx.manifest), 'receipt': plain(tx.receipt), 'evidence': plain(tx.evidence)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('input', type=Path)
    args = parser.parse_args()
    try:
        result = validate(json.loads(args.input.read_text(encoding='utf-8')))
    except (ValueError, KeyError, TypeError) as exc:
        print(json.dumps({'status': 'FAIL', 'gate': getattr(exc, 'gate', 'INPUT'), 'reason': str(exc),
                          'evidence': getattr(exc, 'evidence', None), 'can_register_git': False, 'can_deploy_pages': False}, ensure_ascii=False))
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
