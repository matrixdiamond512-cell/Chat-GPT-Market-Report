"""Synthetic Publisher fixture; no production artifacts are generated."""
import base64
from reporting.snapshot import plain
from .transaction_fixture import objects, png_bytes, pages

NOW = '2026-10-01T21:03:00+09:00'


def payload():
    context, snapshot, report = objects()
    return {'context': context.to_dict(), 'snapshot': snapshot.to_dict(), 'report': report.to_dict(),
            'png_base64': base64.b64encode(png_bytes()).decode(), 'execution_at': NOW}


def publication(result, report):
    # Reuse the foundation DOM contract; never claim a real browser observation.
    class SyntheticTransaction:
        context = type('Context', (), {'report_id': report.report_id, 'revision': report.revision})()
        snapshot = type('Snapshot', (), {'snapshot_id': report.snapshot_id})()
        evidence = {'G4': {'png_hash': result['manifest']['png_hash']}}
    tx = SyntheticTransaction()
    tx.report = report
    observed = pages(tx)
    observed['git_commit_sha'] = result['git_commit_sha']
    return {'simulation': True, 'actions': {'commit_sha': result['git_commit_sha'], 'run_id': 'fixture-run', 'status': 'success'},
            'pages': plain(observed)}
