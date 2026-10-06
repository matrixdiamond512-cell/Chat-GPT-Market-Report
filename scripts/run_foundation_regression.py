"""Reproducible read-only acceptance suite; production writers never run.

The unsafe-writer test operates only in a TemporaryDirectory. Outputs live
outside production artifact folders. Existing legacy validation failures are
recorded explicitly, never reclassified as passes.
"""
import argparse
import ast
import base64
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def production_files():
    paths = [ROOT/'reports.json']
    for folder in ('reports', 'data', 'images/reports', 'publication-receipts'):
        paths.extend(p for p in (ROOT/folder).rglob('*') if p.is_file())
    return {p.relative_to(ROOT).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths if p.is_file()}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--node', required=True)
    parser.add_argument('--evidence-dir', type=Path, required=True)
    args = parser.parse_args()
    evidence = args.evidence_dir.resolve(); evidence.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ, PYTHONPATH=str(ROOT/'scripts')+os.pathsep+str(ROOT), PYTHONUTF8='1', PYTHONDONTWRITEBYTECODE='1')
    before = production_files()
    results = []

    def run(name, command, expected=0, level='E2'):
        completed = subprocess.run(command, cwd=ROOT, env=env, text=True, encoding='utf-8', errors='replace', capture_output=True)
        (evidence/(name+'.log')).write_text(completed.stdout+completed.stderr, encoding='utf-8')
        result = {'name': name, 'command': command, 'exit_code': completed.returncode,
                  'status': 'PASS' if completed.returncode == expected and name != 'legacy-market-structure' else 'FAIL',
                  'command_status': 'PASS' if completed.returncode == 0 else 'FAIL',
                  'expected_exit': expected, 'matches_expected': completed.returncode == expected, 'evidence_level': level,
                  'timestamp': datetime.now(timezone.utc).isoformat()}
        results.append(result)
        print(name, result['status'], 'exit='+str(completed.returncode), flush=True)

    run('python-tests', [sys.executable, '-B', '-m', 'unittest', 'discover', '-s', 'tests', '-q'])
    run('legacy-script-tests', [sys.executable, '-B', '-m', 'unittest', 'scripts.test_resolve_market_report_slot',
                               'scripts.test_run_market_data_window', 'scripts.test_reconcile_latest_report_market_data',
                               'scripts.test_fetch_market_data', 'scripts.test_build_market_sheet_exports', '-q'])
    run('gas-narrative', [args.node, 'scripts/test_apps_script_narrative_report.js'])
    run('ui-foundation', [args.node, 'scripts/test_report_foundation_ui.js'])
    for file in ('assets/js/report-core-v3.js', 'assets/js/report-structured-enrichment.js', 'assets/js/morning-report-qa-gate.js', 'assets/js/report-markdown-fulltext-fix.js'):
        run('syntax-'+Path(file).stem, [args.node, '--check', file], level='E0')
    for file in ('apps-script/MarketReportContext.gs', 'apps-script/MarketReportWebSync.gs', 'apps-script/MarketReportStructuredImport.gs'):
        # Node's --check doesn't accept .gs; check an exact temporary copy.
        copy = evidence/(Path(file).stem+'.syntax.js'); copy.write_bytes((ROOT/file).read_bytes())
        run('syntax-'+Path(file).stem, [args.node, '--check', str(copy)], level='E0')
    syntax_count = 0
    for file in (ROOT/'scripts').rglob('*.py'):
        ast.parse(file.read_text(encoding='utf-8-sig'), filename=str(file)); syntax_count += 1
    results.append({'name': 'python-syntax', 'status': 'PASS', 'files': syntax_count, 'evidence_level': 'E0'})

    sys.path.insert(0, str(ROOT/'scripts')); sys.path.insert(0, str(ROOT))
    from tests.transaction_fixture import objects, docs, png, git, pages, manifest_tx
    from reporting.gates import Transaction
    c, s, r = objects(); tx = manifest_tx(); tx = tx.verify_git(**git(tx)).verify_actions(commit_sha='a'*40, run_id='fixture-run', status='success')
    image = png(tx); image['png_base64'] = base64.b64encode(image.pop('png_bytes')).decode()
    payload = {'execution_context': {'attempt_id': 'synthetic-acceptance', 'execution_started_at': '2026-10-01T21:00:00+09:00'},
               'context': c.to_dict(), 'snapshot': s.to_dict(), 'report': r.to_dict(),
               'evidence': {'docs': docs(r), 'png': image, 'manifest_created_at': '2026-10-01T21:03:00+09:00',
                            'git': git(tx), 'actions': {'commit_sha': 'a'*40, 'run_id': 'fixture-run', 'status': 'success'},
                            'pages': pages(tx), 'create_receipt': True}}
    fixture = evidence/'synthetic-transaction.json'; fixture.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')
    run('connected-cli', [sys.executable, '-B', 'scripts/validate_report_transaction.py', str(fixture)], level='E3')
    del payload['evidence']['png']; invalid = evidence/'synthetic-missing-png.json'; invalid.write_text(json.dumps(payload, ensure_ascii=False), encoding='utf-8')
    run('connected-cli-missing-png', [sys.executable, '-B', 'scripts/validate_report_transaction.py', str(invalid)], expected=1, level='E3')
    run('index-validator', [sys.executable, '-B', 'scripts/validate_report_index.py'])
    run('publication-consistency', [sys.executable, '-B', 'scripts/verify_publication_consistency.py'])
    run('legacy-market-structure', [sys.executable, '-B', 'scripts/validate_market_reports.py'], expected=1)
    for day in ('2026-10-04', '2026-10-04T00:00:00+09:00'):
        run('receipt-boundary-'+('date' if 'T' not in day else 'aware'), [sys.executable, '-B', 'scripts/validate_drive_publication_receipt.py', '--enforce-from', day])

    after = production_files()
    baseline = json.loads((evidence/'production-baseline.json').read_text(encoding='utf-8'))
    differences = [key for key in baseline if after.get(key) != baseline[key]]
    production = {'baseline_files': len(baseline), 'before_after_files': len(after), 'baseline_mismatches': differences,
                  'during_tests_unchanged': before == after}
    tracked_diff = subprocess.run(['git', 'diff', '--name-only', '600a533', '--', 'reports', 'reports.json', 'data', 'images/reports', 'publication-receipts'], cwd=ROOT, text=True, capture_output=True)
    production['git_base_artifact_diff'] = tracked_diff.stdout
    production['status'] = 'PASS' if not differences and before == after and tracked_diff.returncode == 0 and not tracked_diff.stdout.strip() else 'FAIL'
    (evidence/'production-proof.json').write_text(json.dumps(production, indent=2), encoding='utf-8')
    for p in (ROOT/'docs/project-control/spec-readbacks').glob('*.md'):
        local = (ROOT/'docs'/p.name).read_text(encoding='utf-8-sig').rstrip('\n')
        remote = p.read_text(encoding='utf-8-sig').rstrip('\n')
        results.append({'name': 'formal-readback-'+p.name, 'status': 'PASS' if local == remote else 'FAIL', 'evidence_level': 'E5',
                        'limit': 'readback collected 2026-10-04; not re-fetched in acceptance run'})
    summary = {'run_id': 'foundation-20261004-acceptance', 'at': datetime.now(timezone.utc).isoformat(),
               'python': sys.version, 'production': production, 'results': results,
               'limits': ['Synthetic Gates/CLI never certify a real publication.', 'Live E–H pipelines not modified.', 'Legacy market structure FAIL is preserved, not treated as PASS.']}
    (evidence/'acceptance.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding='utf-8')
    unexpected = [r for r in results if r.get('matches_expected') is False or (r['status'] == 'FAIL' and 'expected_exit' not in r)]
    return 1 if unexpected or production['status'] != 'PASS' else 0


if __name__ == '__main__':
    raise SystemExit(main())
