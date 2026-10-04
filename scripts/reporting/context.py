"""Immutable target identity; execution timestamps never determine report dates."""
from dataclasses import dataclass, asdict
from datetime import date, datetime, timedelta, timezone
import re

JST = timezone(timedelta(hours=9))
SLOTS = ('08:00', '12:00', '16:00', '21:00')


def aware(value: str, *, date_boundary: bool = False) -> datetime:
    if date_boundary and re.fullmatch(r'\d{4}-\d{2}-\d{2}', value):
        return datetime.combine(date.fromisoformat(value), datetime.min.time(), JST)
    try:
        result = datetime.fromisoformat(value.replace('Z', '+00:00'))
    except (ValueError, TypeError) as exc:
        raise ValueError('timestamp must be ISO8601 with timezone') from exc
    if result.tzinfo is None or result.utcoffset() is None:
        raise ValueError('timestamp must include timezone')
    return result


def previous_weekday(day: date) -> date:
    day -= timedelta(days=1)
    while day.weekday() > 4:
        day -= timedelta(days=1)
    return day


@dataclass(frozen=True)
class ReportContext:
    report_date: str
    report_time: str
    report_id: str
    data_cutoff: str
    previous_report_id: str | None
    previous_business_day: str
    revision: int = 1
    mode: str = 'new'

    def __post_init__(self):
        if not re.fullmatch(r'\d{4}-\d{2}-\d{2}', self.report_date):
            raise ValueError('report_date must be explicit YYYY-MM-DD')
        day = date.fromisoformat(self.report_date)
        if self.report_time not in SLOTS or self.report_id != f'{self.report_date}_{self.report_time.replace(":", "-")}':
            raise ValueError('report identity/slot mismatch')
        if self.mode not in ('new', 'historical', 'recovery'):
            raise ValueError('unknown context mode')
        if self.mode == 'new' and day.weekday() > 4:
            raise ValueError('weekend new-report publication forbidden')
        if type(self.revision) is not int or self.revision < 1:
            raise ValueError('revision must be positive integer')
        cutoff = aware(self.data_cutoff)
        target = aware(f'{self.report_date}T{self.report_time}:00+09:00')
        if cutoff > target:
            raise ValueError('cutoff follows report target')
        previous = date.fromisoformat(self.previous_business_day)
        if previous >= day or previous.weekday() > 4:
            raise ValueError('invalid previous business day')
        if self.previous_report_id is not None:
            if not re.fullmatch(r'\d{4}-\d{2}-\d{2}_(08|12|16|21)-00', self.previous_report_id):
                raise ValueError('invalid previous report identity')
            previous_target = aware(self.previous_report_id.replace('_', 'T').rsplit('-', 1)[0]+':00:00+09:00')
            if previous_target >= target:
                raise ValueError('previous report must precede target')

    @classmethod
    def create(cls, report_date: str, report_time: str, data_cutoff: str, *, revision=1, mode='new', previous_report_id=None, previous_business_day=None):
        # Dates never default to now; persisted contexts can be restored directly.
        return cls(report_date, report_time, f'{report_date}_{report_time.replace(":", "-")}', data_cutoff,
                   previous_report_id, previous_business_day or previous_weekday(date.fromisoformat(report_date)).isoformat(), revision, mode)

    def to_dict(self):
        return asdict(self)


@dataclass(frozen=True)
class ExecutionContext:
    attempt_id: str
    execution_started_at: str
    saved_at: str | None = None
    published_at: str | None = None
    verified_at: str | None = None

    def __post_init__(self):
        if not self.attempt_id:
            raise ValueError('attempt_id required')
        started = aware(self.execution_started_at)
        prior = started
        for value in (self.saved_at, self.published_at, self.verified_at):
            if value is not None:
                timestamp = aware(value)
                if timestamp < prior:
                    raise ValueError('execution timestamps out of order')
                prior = timestamp
