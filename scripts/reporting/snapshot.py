"""Freeze the existing verified acquisition payload at the report boundary."""
from collections.abc import Mapping
from dataclasses import dataclass, fields
import hashlib
import json
import math
from .context import ReportContext, aware, JST


@dataclass(frozen=True)
class FrozenMap(Mapping):
    entries: tuple

    def __iter__(self):
        return (key for key, _ in self.entries)

    def __len__(self):
        return len(self.entries)

    def __getitem__(self, key):
        for name, value in self.entries:
            if name == key:
                return value
        raise KeyError(key)


def freeze(value):
    if isinstance(value, Mapping):
        return FrozenMap(tuple((str(k), freeze(v)) for k, v in sorted(value.items())))
    if isinstance(value, (list, tuple)):
        return tuple(freeze(v) for v in value)
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    raise ValueError('unsupported snapshot value')


def plain(value):
    if isinstance(value, Mapping):
        return {key: plain(value[key]) for key in value}
    if isinstance(value, tuple):
        return [plain(v) for v in value]
    if hasattr(value, '__dataclass_fields__'):
        return {f.name: plain(getattr(value, f.name)) for f in fields(value)}
    return value


def digest(value):
    return hashlib.sha256(json.dumps(plain(value), sort_keys=True, ensure_ascii=False, separators=(',', ':'), allow_nan=False).encode()).hexdigest()


@dataclass(frozen=True)
class Market:
    instrument: str
    marketType: str
    venue: str | None
    contractMonth: str | None
    priceValue: float | None
    priceUnit: str
    changeValue: float | None
    changePct: float | None
    direction: str
    comparisonBasis: str
    asOf: str | None
    source: tuple
    status: str
    unavailableReason: str | None
    displayText: str
    outlook: str | None = None

    def __post_init__(self):
        object.__setattr__(self, 'source', freeze(self.source))
        if not self.instrument or not self.marketType or not self.priceUnit:
            raise ValueError('instrument, marketType and priceUnit required')
        for value in (self.priceValue, self.changeValue, self.changePct):
            if value is not None and (type(value) not in (int, float) or not math.isfinite(value)):
                raise ValueError('market numeric fields must be finite numbers or null')
        if self.status not in ('VALID', 'UNAVAILABLE', 'STALE', 'N/A'):
            raise ValueError('unknown market status')
        if self.direction not in ('UP', 'DOWN', 'FLAT', 'UNKNOWN', 'N/A'):
            raise ValueError('unknown observed direction')
        if self.asOf is not None:
            aware(self.asOf)
        if self.status == 'UNAVAILABLE' and (self.priceValue is not None or not self.unavailableReason):
            raise ValueError('UNAVAILABLE requires null price and reason')
        if self.status == 'N/A' and self.priceValue is not None:
            raise ValueError('N/A cannot contain a price')
        if self.status in ('VALID', 'STALE') and (self.priceValue is None or not self.asOf or not self.source):
            raise ValueError('observations require price, asOf and source')
        if self.changeValue is not None or self.changePct is not None:
            if not self.comparisonBasis:
                raise ValueError('changes require comparison basis')
        signs = {0 if v == 0 else (1 if v > 0 else -1) for v in (self.changeValue, self.changePct) if v is not None}
        if len(signs) > 1:
            raise ValueError('change and changePct sign mismatch')
        if signs and self.direction != {1: 'UP', -1: 'DOWN', 0: 'FLAT'}[next(iter(signs))]:
            raise ValueError('numeric observed direction mismatch')

    @classmethod
    def from_acquisition(cls, value: dict):
        status = ('STALE' if value.get('freshnessStatus') == 'stale' else
                  'VALID' if value.get('verificationStatus') == 'verified' else 'UNAVAILABLE')
        change = value.get('change')
        pct = value.get('changePercent')
        observed = change if change is not None else pct
        direction = 'UNKNOWN' if observed is None else 'UP' if observed > 0 else 'DOWN' if observed < 0 else 'FLAT'
        return cls(value['id'], value['marketType'], value.get('venue'), value.get('contractMonth'),
                   value.get('value') if status != 'UNAVAILABLE' else None, value['unit'], change, pct, direction,
                   value.get('comparisonBasis') or ('previous_close' if value.get('previousClose') is not None else ''),
                   value.get('asOf') or None,
                   ({'id': value.get('sourceId'), 'url': value.get('sourceUrl'), 'reference': value.get('rawReference')},) if value.get('sourceId') else (),
                   status, (value.get('error') or value.get('lastError') or 'unverified acquisition') if status == 'UNAVAILABLE' else None,
                   str(value.get('displayValue') or '') if status != 'UNAVAILABLE' else str(value.get('error') or '取得不能'))


@dataclass(frozen=True)
class MarketDataSnapshot:
    snapshot_id: str
    report_id: str
    revision: int
    schema_version: int
    captured_at: str
    data_cutoff: str
    markets: tuple[Market, ...]

    def __post_init__(self):
        object.__setattr__(self, 'markets', tuple(self.markets))
        aware(self.captured_at)
        aware(self.data_cutoff)
        if not self.markets or any(not isinstance(m, Market) for m in self.markets):
            raise ValueError('typed markets required')
        if len({m.instrument for m in self.markets}) != len(self.markets):
            raise ValueError('duplicate market series')
        if self.snapshot_id != 'snapshot-'+digest(self.identity_payload()):
            raise ValueError('snapshot content identity mismatch')

    def identity_payload(self):
        return {f.name: getattr(self, f.name) for f in fields(self) if f.name != 'snapshot_id'}

    def validate_context(self, context: ReportContext):
        if (self.report_id, self.revision, self.data_cutoff) != (context.report_id, context.revision, context.data_cutoff):
            raise ValueError('snapshot/context identity mismatch')

    @classmethod
    def capture(cls, context: ReportContext, markets, captured_at: str):
        # No now(), fetch(), or latest.json lookup: retry reuses this result.
        payload = dict(report_id=context.report_id, revision=context.revision, schema_version=1,
                       captured_at=captured_at, data_cutoff=context.data_cutoff, markets=tuple(markets))
        return cls('snapshot-'+digest(payload), **payload)

    @classmethod
    def from_acquisition(cls, context: ReportContext, payload: dict):
        generated = aware(payload['generatedAt'])
        if generated.astimezone(JST).date().isoformat() != context.report_date or payload.get('reportSlot') != context.report_time:
            raise ValueError('cross-day/slot acquisition cannot bind to report')
        if payload.get('reportDate') not in (None, context.report_date):
            raise ValueError('acquisition reportDate mismatch')
        return cls.capture(context, [Market.from_acquisition(m) for m in payload['markets'].values()], payload['generatedAt'])

    def to_dict(self):
        return plain(self)

    @classmethod
    def restore(cls, value):
        data = dict(value)
        data['markets'] = tuple(Market(**m) for m in data['markets'])
        return cls(**data)
