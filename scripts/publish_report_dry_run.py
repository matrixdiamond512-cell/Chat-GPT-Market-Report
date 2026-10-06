"""Offline Phase E CLI; no live switch or production adapter exists."""
import argparse
import base64
import json
from pathlib import Path
from reporting.context import ReportContext
from reporting.snapshot import MarketDataSnapshot, plain
from reporting.report import ReportObject
from reporting.publisher import DryRunPublisher, FixtureStore, FixtureStop


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('input', type=Path, help='explicit frozen context/snapshot/report/PNG fixture')
    parser.add_argument('--dry-run', required=True, action='store_true')
    parser.add_argument('--fixture-dir', type=Path, required=True)
    parser.add_argument('--stop-after', choices=('DOC_SAVED', 'PNG_SAVED', 'MANIFEST_READY', 'BEFORE_RECEIPT'))
    parser.add_argument('--lose-response', choices=('doc', 'png', 'manifest', 'git', 'receipt'))
    args = parser.parse_args()
    store = None
    try:
        payload = json.loads(args.input.read_text(encoding='utf-8-sig'))
        context = ReportContext(**payload['context'])
        snapshot = MarketDataSnapshot.restore(payload['snapshot'])
        report = ReportObject.restore(payload['report'])
        png = base64.b64decode(payload['png_base64'], validate=True)
        store = FixtureStore(args.fixture_dir)
        publisher = DryRunPublisher(store)
        result = publisher.run(context, snapshot, report, png, now=payload['execution_at'],
                               publication=payload.get('publication'), stop_after=args.stop_after,
                               faults={'response_lost': args.lose_response})
        print(json.dumps(plain(result), ensure_ascii=False, indent=2))
        return 0
    except (ValueError, KeyError, TypeError, FixtureStop) as exc:
        rows = store.db.execute('SELECT transaction_id FROM transactions').fetchall() if store else []
        result = {'mode': 'OFFLINE_DRY_RUN', 'simulation': True,
                  'state': getattr(exc, 'state', 'STOPPED' if isinstance(exc, FixtureStop) else 'FAILED'),
                  'reason': str(exc), 'production_connected': False, 'push_allowed': False, 'deploy_allowed': False,
                  'journals': [plain(DryRunPublisher(store).result(row['transaction_id'])) for row in rows]}
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 2 if isinstance(exc, FixtureStop) else 1
    finally:
        if store:
            store.close()


if __name__ == '__main__':
    raise SystemExit(main())
