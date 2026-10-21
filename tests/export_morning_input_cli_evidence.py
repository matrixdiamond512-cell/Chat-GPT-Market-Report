import copy
import hashlib
import json
import shutil
from pathlib import Path
from test_morning_staging_bridge import MorningStagingBridgeTests

import argparse
parser = argparse.ArgumentParser(description='Export TEST_ONLY CLI subprocess evidence')
parser.add_argument('--output', type=Path, required=True)
root = parser.parse_args().output.resolve()
root.mkdir(exist_ok=True)
results = []
for case in ('success', 'missing_capture', 'tampered_body', 'reversed_time'):
    test = MorningStagingBridgeTests()
    test.setUp()
    try:
        original = copy.deepcopy(test.original_body_evidence)
        if case == 'missing_capture':
            original.pop('capturedAt')
        elif case == 'tampered_body':
            original['fullText'] += '改変'
        elif case == 'reversed_time':
            original['capturedAt'] = '2026-10-06T08:04:00+09:00'
        completed, output = test._run_input_preparation_cli(original=original)
        row = {'case': case, 'returncode': completed.returncode,
               'stdout': completed.stdout, 'stderr': completed.stderr,
               'output_exists': output.exists(), 'test_only': True}
        if case == 'success':
            assert completed.returncode == 0, row
            expected = {'summary.json', 'view.json', 'spec.json', 'input-manifest.json'}
            assert {p.name for p in output.iterdir()} == expected
            payloads = {p.name: json.loads(p.read_text(encoding='utf-8')) for p in output.iterdir()}
            manifest = payloads['input-manifest.json']
            assert json.loads(completed.stdout) == manifest
            assert manifest['original_body_captured_at'] == original['capturedAt']
            assert manifest['docs_saved_at'] == test.receipt['savedAt']
            for key in ('report_id', 'revision', 'snapshot_id'):
                assert manifest[key] == test.bound[key]
                for name in ('summary.json', 'view.json'):
                    assert payloads[name][key] == manifest[key], (name, key)
            assert payloads['spec.json']['snapshot_id'] == manifest['snapshot_id']
            assert manifest['bodyHash'] == original['bodyHash'] == test.receipt['bodyHash']
            assert payloads['summary.json']['bodyHash'] == manifest['bodyHash']
            assert payloads['view.json']['body_hash'] == manifest['bodyHash']
            canonical = json.dumps(payloads['summary.json'], ensure_ascii=False,
                                   sort_keys=True, separators=(',', ':'), allow_nan=False).encode('utf-8')
            assert hashlib.sha256(canonical).hexdigest() == manifest['summary_sha256']
            assert manifest['scenario_review'] == 'PENDING' and manifest['publish_allowed'] is False
            shutil.copytree(output, root / 'artifacts')
            shutil.copytree(test.root / 'cli-inputs', root / 'inputs')
            row['file_sha256'] = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in output.iterdir()}
            row['manifest'] = manifest
            row['identity_time_hash_checks'] = 'PASS'
        else:
            assert completed.returncode == 1 and not output.exists(), row
            reason = {'missing_capture': 'STAGING_PRE_SAVE_CAPTURE_TIME_INVALID',
                      'tampered_body': 'STAGING_PRE_SAVE_BODY_HASH_INVALID',
                      'reversed_time': 'STAGING_PRE_SAVE_CAPTURE_ORDER_INVALID'}[case]
            assert json.loads(completed.stdout)['reason'] == reason
        results.append(row)
    finally:
        test.tearDown()
(root / 'result.json').write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps(results, ensure_ascii=False, indent=2))
