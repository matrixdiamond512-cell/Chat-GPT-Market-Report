"""Synthetic complete transaction; not evidence of live publication."""
import struct
import zlib
from reporting.context import ReportContext
from reporting.snapshot import Market, MarketDataSnapshot, plain
from reporting.report import REGISTRY, ReportObject, market_row, table_line
from reporting.gates import SOURCES, Transaction, body_hash


def png_bytes():
    def chunk(kind, data):
        return struct.pack('>I', len(data))+kind+data+struct.pack('>I', zlib.crc32(kind+data)&0xffffffff)
    return b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR', struct.pack('>IIBBBBB', 1, 1, 8, 2, 0, 0, 0))+chunk(b'IDAT', zlib.compress(b'\x00\xff\x00\x00'))+chunk(b'IEND', b'')


def objects():
    context = ReportContext.create('2026-10-01', '21:00', '2026-10-01T20:55:00+09:00', revision=2, previous_report_id='2026-10-01_16-00')
    values = {'gold': 4200, 'wti': 89.47, 'nikkei225_futures_ose': 69000, 'usdjpy': 158, 'eurusd': 1.1237, 'btcusd': 80000,
              'vix': 20, 'nikkei_vi': 20, 'fear_greed': 50, 'crypto_fear_greed': 50}
    markets = []
    for key, definition in SOURCES.items():
        if not definition.get('required'):
            continue
        source = definition['sources'][0]
        markets.append(Market(key, definition['marketType'], 'OSE' if key == 'nikkei225_futures_ose' else None,
                              '2026-12' if key == 'nikkei225_futures_ose' else None,
                              values[key], definition['unit'], 0, 0, 'FLAT', 'previous_close', '2026-10-01T20:50:00+09:00',
                              ({'id': source['id'], 'url': source.get('sourceUrl') or source['url']},), 'VALID', None, str(values[key])+definition['unit']))
    snapshot = MarketDataSnapshot.capture(context, markets, '2026-10-01T20:54:00+09:00')
    title = 'マーケットレポート｜2026/10/01（木）21:00'
    lines = [title]
    for heading in REGISTRY['required']:
        lines.append(heading)
        lines.extend(table_line(market_row(m)) for m in markets) if heading == '主要市場データ' else lines.append('fixture本文。')
    report = ReportObject.build(context, snapshot, title, '\n'.join(lines)+'\n')
    return context, snapshot, report


def docs(report):
    return dict(chat_text=report.full_text, saved_file_id='fixture-doc', read_file_id='fixture-doc', drive_url='https://docs.google.com/document/d/fixture-doc/edit',
                read_text=report.full_text, read_at='2026-10-01T21:01:00+09:00', read_success=True)


def png(tx):
    return dict(png_bytes=png_bytes(), file_id='fixture-png', read_file_id='fixture-png', filename=tx.context.report_id+'_r2.png', exists=True,
                read_at='2026-10-01T21:02:00+09:00', report_id=tx.context.report_id, revision=2, snapshot_id=tx.snapshot.snapshot_id, body_hash_value=body_hash(tx.report.full_text))


def manifest_tx():
    tx = Transaction.begin(*objects())
    return tx.verify_docs(**docs(tx.report)).verify_png(**png(tx)).create_manifest('2026-10-01T21:03:00+09:00')


def git(tx):
    data = tx.report.to_dict()
    return dict(canonical=data, index=data, latest=data, dashboard=data, existing_revision=1, commit_sha='a'*40)


def pages(tx):
    return dict(git_commit_sha='a'*40, pages_deployment_id='fixture-deployment', published_at='2026-10-01T21:04:00+09:00', verified_at='2026-10-01T21:05:00+09:00',
                portal_url='https://example.test/report', report_id=tx.context.report_id, revision=2, snapshot_id=tx.snapshot.snapshot_id, title=tx.report.title,
                full_text=tx.report.full_text, rows=plain(tx.report.market_data_table['rows']), png_hash=tx.evidence['G4']['png_hash'],
                controls={key: True for key in ('date_picker', 'time_tabs', 'prev', 'next', 'reload')}, console_errors=[],
                loading_timeout={'tested': True, 'error_visible': True, 'bounded_ms': 15000},
                mobile={'tested': True, 'viewport_width': 390, 'table_scrollable': True, 'columns_readable': True, 'body_overflow': False})
