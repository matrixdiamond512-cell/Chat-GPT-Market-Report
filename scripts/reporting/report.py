"""Original text is retained; structured fields never replace the source body."""
from dataclasses import dataclass
import json
from pathlib import Path
import re
from .context import ReportContext
from .snapshot import Market, MarketDataSnapshot, FrozenMap, freeze, plain

REGISTRY = json.loads((Path(__file__).resolve().parents[2]/'config/report_heading_registry.json').read_text(encoding='utf-8'))
ALIASES = {alias: canonical for canonical, aliases in REGISTRY['sections'].items() for alias in aliases}


def canonical_heading(line):
    text = line.strip()
    text = re.sub(r'^#{1,3}\s+', '', text)
    if text.startswith('【') and text.endswith('】'):
        text = text[1:-1].strip()
    text = re.sub(r'^\d{1,2}[．.]\s*', '', text)
    return ALIASES.get(text)


def parse_sections(full_text):
    sections = []
    current = None
    for line in full_text.replace('\r\n', '\n').split('\n'):
        heading = canonical_heading(line)
        if heading:
            if current:
                sections.append(current)
            current = {'heading': heading, 'original_heading': line, 'lines': []}
        elif current:
            current['lines'].append(line)
    if current:
        sections.append(current)
    return freeze(sections)


def market_row(m: Market):
    return freeze({k: plain(getattr(m, k)) for k in ('instrument', 'priceValue', 'priceUnit', 'changeValue', 'changePct', 'direction', 'status', 'unavailableReason', 'displayText')})


def table_line(row):
    # This exact serialized row must occur in the original market section;
    # generation consumes this contract, validation does not repair text.
    return ' | '.join(str(row[k]) if row[k] is not None else 'null' for k in
                      ('instrument', 'displayText', 'priceValue', 'priceUnit', 'changeValue', 'changePct', 'direction', 'status', 'unavailableReason'))


@dataclass(frozen=True)
class ReportObject:
    report_id: str
    report_date: str
    report_time: str
    revision: int | None
    snapshot_id: str | None
    title: str
    full_text: str
    sections: tuple
    market_data_table: FrozenMap
    markets: tuple[Market, ...]
    previous_report_id: str | None
    status: str

    def __post_init__(self):
        object.__setattr__(self, 'sections', freeze(self.sections))
        object.__setattr__(self, 'market_data_table', freeze(self.market_data_table))
        object.__setattr__(self, 'markets', tuple(self.markets))
        if not self.title or not isinstance(self.full_text, str) or not self.full_text.strip():
            raise ValueError('title and original full_text required')
        if self.report_id != f'{self.report_date}_{self.report_time.replace(":", "-")}':
            raise ValueError('report object identity mismatch')

    @classmethod
    def build(cls, context: ReportContext, snapshot: MarketDataSnapshot, title: str, full_text: str):
        snapshot.validate_context(context)
        return cls(context.report_id, context.report_date, context.report_time, context.revision, snapshot.snapshot_id,
                   title, full_text, parse_sections(full_text), freeze({'rows': [market_row(m) for m in snapshot.markets]}),
                   snapshot.markets, context.previous_report_id, 'DRAFT')

    def to_dict(self):
        return plain(self)

    @classmethod
    def restore(cls, value):
        data = dict(value)
        data['markets'] = tuple(Market(**m) for m in data['markets'])
        return cls(**data)


@dataclass(frozen=True)
class LegacyReport:
    report: ReportObject
    original: FrozenMap
    canonicalIdentity: str = 'UNKNOWN'
    publicationStatus: str = 'UNVERIFIED'
    reviewStatus: str = 'NEEDS_REVIEW'


def adapt_legacy(payload):
    report = payload.get('latestReport', payload)
    # A read adapter preserves raw legacy data. Missing numeric/snapshot fields
    # are unknown, never manufactured from body text or claimed publishable.
    day, slot = report['date'], report['time']
    full_text = report.get('fullText') or report.get('rawText') or report.get('body')
    if not isinstance(full_text, str) or not full_text.strip():
        raise ValueError('legacy body missing; restoration from summary forbidden')
    obj = ReportObject(f'{day}_{slot.replace(":", "-")}', day, slot, report.get('revision'), report.get('snapshot_id'),
                       report['title'], full_text, parse_sections(full_text), freeze(report.get('marketDataTable') or {}),
                       (), report.get('previous_report_id'), 'LEGACY_UNVERIFIED')
    return LegacyReport(obj, freeze(payload), 'UNRESOLVED' if obj.report_id == '2026-10-02_21-00' else 'UNKNOWN')
