"""Connected G0–G8 gates. Consumers supply observed evidence; no network writes.

Passing fixtures proves the contracts, not enforcement in legacy publishers.
"""
from dataclasses import dataclass, replace
import difflib
import hashlib
import json
import math
from pathlib import Path
import re
import struct
import zlib
from .context import ReportContext, aware
from .snapshot import MarketDataSnapshot, FrozenMap, digest, freeze, plain
from .report import ReportObject, REGISTRY, parse_sections, market_row, table_line

POLICY = json.loads((Path(__file__).resolve().parents[2]/'config/market_data_validation.json').read_text(encoding='utf-8'))
SOURCES = json.loads((Path(__file__).resolve().parents[2]/'config/market_data_sources.json').read_text(encoding='utf-8'))['symbols']
UNRESOLVED = frozenset({'2026-10-02_21-00'})


class GateFailure(ValueError):
    def __init__(self, gate, reason, evidence=None):
        self.gate, self.reason = gate, reason
        self.evidence = evidence
        super().__init__(f'{gate} FAIL: {reason}')


def require(gate, condition, reason):
    if not condition:
        raise GateFailure(gate, reason)


def normalize(text):
    # Deliberately no strip(), punctuation removal or blank-line collapse.
    text = text.replace('\r\n', '\n')
    return text[:-1] if text.endswith('\n') else text


def normalization_evidence(text):
    normalized = normalize(text)
    return {'raw': text, 'normalized': normalized,
            'diff': ''.join(difflib.unified_diff(text.splitlines(keepends=True), normalized.splitlines(keepends=True), fromfile='original', tofile='normalized'))}


def body_hash(text):
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


def validate_png(data):
    """Validate chunk bounds, CRC, scanline bytes and required PNG structure."""
    require('G4', isinstance(data, bytes) and data.startswith(b'\x89PNG\r\n\x1a\n'), 'invalid PNG signature')
    offset, kinds, compressed, header = 8, [], bytearray(), None
    while offset < len(data):
        require('G4', offset+12 <= len(data), 'truncated PNG chunk')
        size = struct.unpack('>I', data[offset:offset+4])[0]
        kind = data[offset+4:offset+8]
        end = offset+12+size
        require('G4', end <= len(data), 'PNG chunk out of bounds')
        chunk = data[offset+8:offset+8+size]
        crc = struct.unpack('>I', data[offset+8+size:end])[0]
        require('G4', zlib.crc32(kind+chunk) & 0xffffffff == crc, 'PNG CRC mismatch')
        kinds.append(kind)
        if kind == b'IHDR':
            require('G4', len(kinds) == 1 and size == 13, 'invalid IHDR')
            header = struct.unpack('>IIBBBBB', chunk)
        if kind == b'IDAT':
            compressed.extend(chunk)
        if kind == b'IEND':
            require('G4', size == 0 and end == len(data), 'invalid IEND/trailing bytes')
        offset = end
    require('G4', header is not None and kinds[-1:] == [b'IEND'] and compressed and kinds.count(b'IHDR') == 1, 'incomplete PNG')
    width, height, depth, color, compression, filter_method, interlace = header
    require('G4', width > 0 and height > 0 and width*height <= 50_000_000, 'PNG dimensions invalid')
    # Unsupported encoding fails closed; never accepts a signature-only file.
    require('G4', depth == 8 and color in (0, 2, 4, 6) and compression == 0 and filter_method == 0 and interlace == 0, 'unsupported PNG encoding')
    channels = {0: 1, 2: 3, 4: 2, 6: 4}[color]
    stride = 1+width*channels
    try:
        decoder = zlib.decompressobj()
        decoded = decoder.decompress(bytes(compressed), stride*height+1)
    except zlib.error as exc:
        raise GateFailure('G4', f'invalid PNG compressed pixels: {exc}') from exc
    require('G4', decoder.eof and not decoder.unused_data and len(decoded) == stride*height, 'PNG pixel length mismatch')
    require('G4', all(decoded[i] <= 4 for i in range(0, len(decoded), stride)), 'invalid PNG filter')


@dataclass(frozen=True)
class Transaction:
    context: ReportContext
    snapshot: MarketDataSnapshot
    report: ReportObject | None = None
    passed: tuple[str, ...] = ()
    evidence: FrozenMap = FrozenMap(())
    manifest: FrozenMap | None = None
    receipt: FrozenMap | None = None

    def record(self, gate, evidence):
        expected = f'G{len(self.passed)}'
        require(gate, gate == expected, f'gate order violation; expected {expected}')
        records = plain(self.evidence)
        records[gate] = evidence
        return replace(self, passed=self.passed+(gate,), evidence=freeze(records))

    @classmethod
    def begin(cls, context, snapshot, report=None):
        tx = cls(context, snapshot, report)
        try:
            ReportContext(**context.to_dict())
        except (ValueError, TypeError) as exc:
            raise GateFailure('G0', str(exc)) from exc
        tx = tx.record('G0', context.to_dict())
        try:
            snapshot.validate_context(context)
            MarketDataSnapshot.restore(snapshot.to_dict())
        except (ValueError, TypeError) as exc:
            raise GateFailure('G1', str(exc)) from exc
        cutoff = aware(context.data_cutoff)
        required_series = {key for key, definition in SOURCES.items() if definition.get('required')}
        require('G1', required_series <= {m.instrument for m in snapshot.markets}, 'required market series missing')
        for market in snapshot.markets:
            require('G1', market.instrument in SOURCES, f'{market.instrument}: unknown market series')
            series = SOURCES[market.instrument]
            require('G1', market.marketType == series['marketType'] and market.priceUnit == series['unit'], f'{market.instrument}: marketType/unit substitution')
            if market.status in ('VALID', 'STALE'):
                observed = aware(market.asOf)
                require('G1', observed <= cutoff, f'{market.instrument}: quote after cutoff')
                policy = POLICY['symbols'].get(market.instrument, POLICY['defaults'])
                max_age = policy.get('staleHours', POLICY['defaults']['staleHours'])*3600
                if market.status == 'VALID':
                    require('G1', (cutoff-observed).total_seconds() <= max_age, f'{market.instrument}: stale quote marked VALID')
                if market.priceValue is not None:
                    require('G1', policy.get('min', float('-inf')) <= market.priceValue <= policy.get('max', float('inf')), f'{market.instrument}: price outside policy')
                if market.changePct is not None:
                    require('G1', abs(market.changePct) <= policy.get('maxChangePercent', float('inf')), f'{market.instrument}: changePct outside policy')
                if market.status == 'VALID':
                    displayed = [float(value.replace(',', '')) for value in re.findall(r'(?<![\d.])[+-]?\d[\d,]*(?:\.\d+)?', market.displayText)]
                    tolerance = 0.5*10**(-policy.get('decimalPlaces', 8))
                    require('G1', any(math.isclose(value, market.priceValue, rel_tol=0, abs_tol=tolerance) for value in displayed), f'{market.instrument}: displayText does not represent numeric price')
                require('G1', all(isinstance(source, FrozenMap) and source.get('id') and re.match(r'^https://', source.get('url', '')) for source in market.source), f'{market.instrument}: invalid source')
                allowed_sources = {s['id'] for s in series.get('sources', [])}
                require('G1', all(source['id'] in allowed_sources for source in market.source), f'{market.instrument}: source outside registry')
        tx = tx.record('G1', snapshot.to_dict())
        return tx if report is None else tx.attach_report(report)

    @property
    def can_generate_body(self):
        return self.passed == ('G0', 'G1') and self.report is None

    def generate_report(self, title, body_factory):
        require('G2', self.can_generate_body, 'G0/G1 must pass before body generation')
        # The producer sees only this context and frozen snapshot, never latest.
        full_text = body_factory(self.context, self.snapshot)
        return self.attach_report(ReportObject.build(self.context, self.snapshot, title, full_text))

    def attach_report(self, report):
        require('G2', self.passed == ('G0', 'G1'), 'G2 requires G0/G1')
        context, snapshot = self.context, self.snapshot
        tx = replace(self, report=report)
        expected = (context.report_id, context.report_date, context.report_time, context.revision, snapshot.snapshot_id, context.previous_report_id)
        actual = (report.report_id, report.report_date, report.report_time, report.revision, report.snapshot_id, report.previous_report_id)
        require('G2', actual == expected, 'ReportObject/context/snapshot identity mismatch')
        require('G2', report.report_id not in UNRESOLVED, 'canonical identity UNRESOLVED; NEEDS_REVIEW')
        require('G2', report.status == 'DRAFT', 'legacy/unverified objects cannot be published')
        require('G2', report.markets == snapshot.markets, 'ReportObject changed frozen markets')
        require('G2', report.sections == parse_sections(report.full_text), 'sections differ from original full_text')
        headings = {s['heading'] for s in report.sections}
        require('G2', set(REGISTRY['required']) <= headings, 'required sections missing')
        require('G2', all(any(s['heading'] == heading and any(line.strip() for line in s['lines']) for s in report.sections) for heading in REGISTRY['required']), 'required section content missing')
        require('G2', normalize(report.full_text).split('\n')[0] == report.title, 'title/body mismatch')
        require('G2', (context.report_date in report.title or context.report_date.replace('-', '/') in report.title)
                and context.report_time in report.title, 'title/context date or time mismatch')
        expected_table = freeze({'rows': [market_row(m) for m in snapshot.markets]})
        require('G2', report.market_data_table == expected_table, 'market table differs from snapshot')
        body_rows = '\n'.join(line for s in report.sections if s['heading'] == '主要市場データ' for line in s['lines'])
        require('G2', all(table_line(row) in body_rows.splitlines() for row in expected_table['rows']), 'body market section and typed table contradict')
        return tx.record('G2', {'report_id': report.report_id, 'revision': report.revision, 'body_hash': body_hash(report.full_text)})

    def verify_docs(self, *, chat_text, saved_file_id, read_file_id, drive_url, read_text, read_at, read_success):
        require('G3', self.passed == ('G0', 'G1', 'G2'), 'G3 requires a validated ReportObject')
        require('G3', bool(saved_file_id) and saved_file_id == read_file_id, 'Drive saved/read fileId mismatch')
        require('G3', re.fullmatch(r'https://docs.google.com/document/d/'+re.escape(saved_file_id)+r'(?:/.*)?', drive_url) is not None, 'Drive URL/fileId mismatch')
        require('G3', read_success is True, 'Drive readback unsuccessful')
        aware(read_at)
        require('G3', chat_text == self.report.full_text, 'original Chat text not preserved')
        require('G3', isinstance(read_text, str) and bool(read_text.strip()), 'empty Drive readback')
        evidence = {'saved_file_id': saved_file_id, 'read_file_id': read_file_id, 'drive_url': drive_url, 'read_at': read_at,
                    'chat': normalization_evidence(chat_text), 'drive': normalization_evidence(read_text)}
        if normalize(chat_text) != normalize(read_text):
            evidence['comparison_diff'] = ''.join(difflib.unified_diff(normalize(chat_text).splitlines(True), normalize(read_text).splitlines(True), fromfile='chat', tofile='drive'))
            raise GateFailure('G3', 'Drive whole text mismatch (punctuation/numbers significant)', evidence)
        return self.record('G3', evidence)

    def verify_png(self, *, png_bytes, file_id, read_file_id, filename, exists, read_at, report_id, revision, snapshot_id, body_hash_value):
        require('G4', self.passed == ('G0', 'G1', 'G2', 'G3'), 'PNG gate requires Docs full-text verification')
        require('G4', exists is True and bool(file_id) and file_id == read_file_id, 'Drive PNG missing/fileId mismatch')
        aware(read_at)
        expected = (self.context.report_id, self.context.revision, self.snapshot.snapshot_id, body_hash(self.report.full_text))
        require('G4', (report_id, revision, snapshot_id, body_hash_value) == expected, 'PNG report/revision/body/snapshot mismatch')
        require('G4', filename == f'マーケットレポート_{self.context.report_id}.png', 'PNG filename mismatch')
        validate_png(png_bytes)
        return self.record('G4', {'png_file_id': file_id, 'png_filename': filename, 'read_at': read_at,
                                'report_id': report_id, 'revision': revision, 'snapshot_id': snapshot_id,
                                'body_hash': body_hash_value, 'png_hash': hashlib.sha256(png_bytes).hexdigest()})

    def create_manifest(self, created_at):
        require('G5', self.passed == ('G0', 'G1', 'G2', 'G3', 'G4'), 'Manifest FAIL: prior gates incomplete; Git/Pages forbidden')
        aware(created_at)
        doc, png = self.evidence['G3'], self.evidence['G4']
        manifest = dict(report_id=self.context.report_id, report_date=self.context.report_date, report_time=self.context.report_time,
                        revision=self.context.revision, body_hash=body_hash(self.report.full_text), snapshot_id=self.snapshot.snapshot_id,
                        drive_file_id=doc['saved_file_id'], drive_url=doc['drive_url'], png_file_id=png['png_file_id'], png_filename=png['png_filename'],
                        png_hash=png['png_hash'], created_at=created_at, status='READY_FOR_PUBLICATION')
        manifest['manifest_id'] = 'manifest-'+digest(manifest)
        return replace(self.record('G5', manifest), manifest=freeze(manifest))

    @property
    def can_register_git(self):
        return self.manifest is not None and self.passed[:6] == ('G0', 'G1', 'G2', 'G3', 'G4', 'G5')

    @property
    def can_deploy_pages(self):
        return self.can_register_git and 'G6' in self.passed and self.evidence.get('ACTIONS', {}).get('status') == 'success'

    def verify_actions(self, *, commit_sha, run_id, status):
        require('ACTIONS', 'G6' in self.passed and 'G7' not in self.passed, 'Actions evidence must follow Git and precede Pages')
        require('ACTIONS', commit_sha == self.evidence['G6']['git_commit_sha'] and bool(run_id) and status == 'success', 'same-commit Actions success required')
        evidence = plain(self.evidence)
        evidence['ACTIONS'] = {'commit_sha': commit_sha, 'run_id': run_id, 'status': status}
        return replace(self, evidence=freeze(evidence))

    def verify_git(self, *, canonical, index, latest, dashboard, existing_revision, commit_sha, existing_report=None):
        require('G6', self.can_register_git, 'Git forbidden: validated Manifest required')
        require('G6', re.fullmatch(r'[0-9a-f]{40}', commit_sha) is not None, 'commit SHA required')
        expected = self.report.to_dict()
        require('G6', type(existing_revision) is int and 0 <= existing_revision <= self.context.revision, 'revision rollback refused')
        require('G6', existing_revision < self.context.revision or existing_report == expected, 'same-revision change/unknown overwrite refused')
        for name, projection in (('canonical', canonical), ('index', index), ('latest', latest), ('dashboard', dashboard)):
            require('G6', projection == expected, f'{name}: content/identity projection mismatch')
        return self.record('G6', {'git_commit_sha': commit_sha, 'report_hash': digest(expected), 'previous_revision': existing_revision})

    def verify_pages(self, *, git_commit_sha, pages_deployment_id, published_at, verified_at, portal_url,
                     report_id, revision, snapshot_id, title, full_text, rows, png_hash, controls, console_errors,
                     loading_timeout, mobile):
        require('G7', self.can_deploy_pages, 'Pages forbidden: G6 required')
        require('G7', git_commit_sha == self.evidence['G6']['git_commit_sha'] and bool(pages_deployment_id), 'Pages deployment commit mismatch/missing')
        require('G7', aware(verified_at) >= aware(published_at), 'Pages timestamp mismatch')
        require('G7', re.match(r'^https://', portal_url) is not None, 'public portal URL required')
        require('G7', (report_id, revision, snapshot_id) == (self.context.report_id, self.context.revision, self.snapshot.snapshot_id), 'DOM report identity mismatch')
        require('G7', title == self.report.title and normalize(full_text) == normalize(self.report.full_text), 'DOM title/body mismatch')
        require('G7', freeze(rows) == self.report.market_data_table['rows'], 'DOM numeric table/direction/reason mismatch (including erroneous 08)')
        require('G7', png_hash == self.evidence['G4']['png_hash'], 'DOM PNG mismatch')
        require('G7', all(controls.get(k) is True for k in ('date_picker', 'time_tabs', 'prev', 'next', 'reload')), 'DOM control test failed/unknown')
        require('G7', console_errors == [], 'DOM console errors/unknown')
        require('G7', loading_timeout.get('tested') is True and loading_timeout.get('error_visible') is True and loading_timeout.get('bounded_ms', 0) in range(1, 30001), 'loading timeout failed/untested')
        require('G7', mobile.get('tested') is True and 0 < mobile.get('viewport_width', 0) <= 480
                and mobile.get('table_scrollable') is True and mobile.get('columns_readable') is True
                and mobile.get('body_overflow') is False, 'mobile table failed/untested')
        return self.record('G7', {'git_commit_sha': git_commit_sha, 'pages_deployment_id': pages_deployment_id, 'published_at': published_at,
                                'verified_at': verified_at, 'portal_url': portal_url, 'dom_validation_status': 'PASS',
                                'controls': controls, 'loading_timeout': loading_timeout, 'mobile': mobile})

    def create_receipt(self):
        require('G8', self.passed == tuple(f'G{i}' for i in range(8)), 'Receipt forbidden before all public verification')
        public = self.evidence['G7']
        receipt = dict(report_id=self.context.report_id, revision=self.context.revision,
                       manifest_id=self.manifest['manifest_id'], manifest_hash=digest(self.manifest),
                       git_commit_sha=public['git_commit_sha'], pages_deployment_id=public['pages_deployment_id'],
                       published_at=public['published_at'], verified_at=public['verified_at'], portal_url=public['portal_url'],
                       dom_validation_status='PASS', final_status='VERIFIED')
        return replace(self.record('G8', receipt), receipt=freeze(receipt))
