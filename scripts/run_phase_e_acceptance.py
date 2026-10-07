"""Offline Phase E acceptance; evidence outside repo, baseline never replaced."""
import argparse
import ast
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def protected_files():
    return {p.relative_to(ROOT).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in ROOT.rglob('*') if p.is_file() and '.git' not in p.parts
            and (p.suffix.lower() in ('.json', '.png') or 'publication-receipts' in p.parts)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--node', required=True)
    parser.add_argument('--evidence-dir', type=Path, required=True)
    args = parser.parse_args()
    evidence = args.evidence_dir.resolve()
    if evidence.is_relative_to(ROOT):
        raise ValueError('evidence directory must be outside repository')
    baseline = json.loads((evidence/'production-baseline.json').read_text(encoding='utf-8'))
    run_id = 'phase-e-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    scenario_root = evidence/'runs'/run_id
    scenario_root.mkdir(parents=True)
    before = protected_files()
    temp = evidence/'temp'; temp.mkdir(exist_ok=True)
    env = dict(os.environ, PYTHONUTF8='1', PYTHONDONTWRITEBYTECODE='1',
               PYTHONPATH=str(ROOT/'scripts')+os.pathsep+str(ROOT), TEMP=str(temp), TMP=str(temp))
    results = []

    def git(*arguments):
        return subprocess.check_output(['git', '-c', 'safe.directory='+ROOT.as_posix(), *arguments],
                                       cwd=ROOT, text=True, encoding='utf-8')

    def run(name, command, expected=0, state=None, known_failure=False, level='E2'):
        completed = subprocess.run(command, cwd=ROOT, env=env, capture_output=True,
                                   text=True, encoding='utf-8', errors='replace')
        (evidence/(name+'.log')).write_text(completed.stdout+completed.stderr, encoding='utf-8')
        output = json.loads(completed.stdout) if state else None
        matched = completed.returncode == expected and (state is None or output.get('state') == state)
        result = {'name': name, 'command': command, 'exit_code': completed.returncode, 'expected_exit': expected,
                  'status': 'FAIL' if known_failure else 'PASS' if matched else 'FAIL',
                  'matches_expected': matched, 'known_failure': known_failure,
                  'evidence_level': level, 'timestamp': datetime.now(timezone.utc).isoformat()}
        if state:
            result['expected_state'] = state; result['observed_state'] = output.get('state')
        results.append(result)
        print(name, result['status'], 'exit='+str(completed.returncode), flush=True)
        return output

    run('phase-e-tests', [sys.executable, '-B', '-m', 'unittest', 'tests.test_publisher', '-v'], level='E3')
    run('python-all-tests', [sys.executable, '-B', '-m', 'unittest', 'discover', '-s', 'tests', '-q'])
    run('foundation-script-tests', [sys.executable, '-B', '-m', 'unittest', 'scripts.test_resolve_market_report_slot',
                                  'scripts.test_run_market_data_window', 'scripts.test_reconcile_latest_report_market_data',
                                  'scripts.test_fetch_market_data', 'scripts.test_build_market_sheet_exports', '-q'])
    run('gas-narrative', [args.node, 'scripts/test_apps_script_narrative_report.js'])
    run('ui-foundation', [args.node, 'scripts/test_report_foundation_ui.js'])
    run('index-validator', [sys.executable, '-B', 'scripts/validate_report_index.py'])
    run('publication-consistency', [sys.executable, '-B', 'scripts/verify_publication_consistency.py'])
    run('legacy-market-structure', [sys.executable, '-B', 'scripts/validate_market_reports.py'], expected=1, known_failure=True)
    for day in ('2026-10-04', '2026-10-04T00:00:00+09:00'):
        run('receipt-boundary-'+('aware' if 'T' in day else 'date'),
            [sys.executable, '-B', 'scripts/validate_drive_publication_receipt.py', '--enforce-from', day])
    syntax_count = 0
    for source in list((ROOT/'scripts').rglob('*.py'))+list((ROOT/'tests').rglob('*.py')):
        ast.parse(source.read_text(encoding='utf-8-sig'), filename=str(source)); syntax_count += 1
    results.append({'name': 'python-syntax', 'status': 'PASS', 'matches_expected': True, 'files': syntax_count, 'evidence_level': 'E0'})

    sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT/'scripts'))
    from tests.publisher_fixture import payload, publication
    from tests.transaction_fixture import objects
    from reporting.report import ReportObject
    fixture_payload = payload()
    fixture = evidence/'publisher-input.json'
    fixture.write_text(json.dumps(fixture_payload, ensure_ascii=False, indent=2), encoding='utf-8')
    scenarios = {}
    for checkpoint in ('DOC_SAVED', 'PNG_SAVED', 'MANIFEST_READY'):
        label = checkpoint.lower()
        command = [sys.executable, '-B', 'scripts/publish_report_dry_run.py', str(fixture), '--dry-run',
                   '--fixture-dir', str(scenario_root/('publisher-fixture-'+label))]
        run(label+'-stop', command+['--stop-after', checkpoint], expected=2, state='STOPPED', level='E3')
        result = run(label+'-resume', command, state='GIT_REGISTERED', level='E3')
        again = run(label+'-repeat', command, state='GIT_REGISTERED', level='E3')
        scenarios[label] = {'counts': again['effect_counts'], 'same_manifest': result['manifest'] == again['manifest'],
                            'same_sha': result['git_commit_sha'] == again['git_commit_sha']}
    command = [sys.executable, '-B', 'scripts/publish_report_dry_run.py', str(fixture), '--dry-run',
               '--fixture-dir', str(scenario_root/'publisher-fixture-lost-git')]
    lost = run('git-response-lost', command+['--lose-response', 'git'], expected=1, state='UNKNOWN', level='E3')
    recovered = run('git-response-recovered', command, state='GIT_REGISTERED', level='E3')
    scenarios['lost_git'] = {'checkpoint_before': lost['journals'][0]['checkpoint'],
                             'counts_after': recovered['effect_counts']}
    observed = dict(fixture_payload, publication=publication(recovered, objects()[2]))
    publication_fixture = evidence/'publisher-publication-input.json'
    publication_fixture.write_text(json.dumps(observed, ensure_ascii=False, indent=2), encoding='utf-8')
    publication_command = [sys.executable, '-B', 'scripts/publish_report_dry_run.py', str(publication_fixture), '--dry-run',
                           '--fixture-dir', str(scenario_root/'publisher-fixture-lost-git')]
    run('before-receipt-stop', publication_command+['--stop-after', 'BEFORE_RECEIPT'], expected=2, state='STOPPED', level='E3')
    verified = run('receipt-resume-persisted-observations', command, state='VERIFIED', level='E3')
    repeated = run('receipt-repeat', command, state='VERIFIED', level='E3')
    scenarios['receipt'] = {'counts': repeated['effect_counts'], 'same_receipt': verified['receipt'] == repeated['receipt']}
    counts_before_receipt = dict(doc=1, png=1, manifest=1, git=1)
    scenario_ok = all(scenarios[k]['counts'] == counts_before_receipt and scenarios[k]['same_manifest']
                      and scenarios[k]['same_sha'] for k in ('doc_saved', 'png_saved', 'manifest_ready'))
    scenario_ok = scenario_ok and scenarios['lost_git']['counts_after'] == counts_before_receipt
    scenario_ok = scenario_ok and scenarios['receipt']['counts'] == dict(counts_before_receipt, receipt=1) and scenarios['receipt']['same_receipt']
    results.append({'name': 'scenario-idempotency-counts', 'status': 'PASS' if scenario_ok else 'FAIL',
                    'matches_expected': scenario_ok, 'evidence_level': 'E3'})
    (evidence/'scenario-results.json').write_text(json.dumps(scenarios, ensure_ascii=False, indent=2), encoding='utf-8')

    after = protected_files()
    mismatches = [key for key, value in baseline['files'].items() if after.get(key) != value]
    added = sorted(set(after)-set(baseline['files']))
    artifact_diff = git('diff', '--name-only', baseline['base'], '--', 'reports', 'reports.json', 'data',
                        'images/reports', 'publication-receipts', '.github', 'apps-script', 'assets')
    refs = git('show-ref')
    baseline_refs = dict(line.split(' ', 1)[::-1] for line in baseline['refs'].splitlines())
    current_refs = dict(line.split(' ', 1)[::-1] for line in refs.splitlines())
    protected_refs = {name: sha for name, sha in baseline_refs.items() if name.startswith('refs/remotes/') or name == 'refs/heads/main'}
    changed_refs = {name: {'before': sha, 'after': current_refs.get(name)} for name, sha in protected_refs.items() if current_refs.get(name) != sha}
    proof = {'status': 'PASS' if before == after and not mismatches and not added and not artifact_diff and not changed_refs else 'FAIL',
             'base': baseline['base'], 'head': git('rev-parse', 'HEAD').strip(), 'protected_files': len(after),
             'baseline_mismatches': mismatches, 'added_protected_files': added, 'before_after_unchanged': before == after,
             'protected_git_diff': artifact_diff, 'protected_ref_changes': changed_refs,
             'target_sha256': after['reports/2026-10-02_21-00.json'],
             'external_limit': 'No network/Drive/GitHub/Pages operation performed. Remote global state was not queried and cannot be certified unchanged by other actors.'}
    (evidence/'production-proof.json').write_text(json.dumps(proof, ensure_ascii=False, indent=2), encoding='utf-8')
    tests_added = sorted(node.name for node in ast.walk(ast.parse((ROOT/'tests/test_publisher.py').read_text(encoding='utf-8'))) if isinstance(node, ast.FunctionDef) and node.name.startswith('test_'))
    summary = {'run_id': run_id, 'scenario_root': str(scenario_root), 'at': datetime.now(timezone.utc).isoformat(),
               'commit': proof['head'], 'python': sys.version, 'phase_e_tests': tests_added, 'results': results,
               'scenarios': scenarios, 'production': proof,
               'NOT_RUN': ['real Drive Docs save/readback', 'real PNG render/save/readback', 'actual publication Git commit/push',
                           'Actions trigger / Pages deploy / live DOM', 'real Receipt', 'Phase F–H',
                           'unselected scripts/test_*.py outside the preserved foundation regression list'],
               'limits': ['E3 fixture behavior only; no E5 live publication claim.',
                          'First invocation used OS sandbox temp and failed with PermissionError; writable evidence temp resolves this infrastructure issue.',
                          'Known historical production structure FAIL is retained.']}
    (evidence/'acceptance.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding='utf-8')
    (evidence/'diff-stat.txt').write_text(git('diff', '--stat', baseline['base']), encoding='utf-8')
    (evidence/'git-status-short.txt').write_text(git('status', '--short'), encoding='utf-8')
    return 1 if proof['status'] != 'PASS' or any(not item['matches_expected'] for item in results) else 0


if __name__ == '__main__':
    raise SystemExit(main())
