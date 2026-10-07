"""Strict Vision review provider contracts. Fixture mode is test-only."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol


REQUIRED_VISION_CHECKS = (
    'decorative_charts', 'gauges', 'invented_charts', 'people', 'title_correct',
    'date_correct', 'time_correct', 'required_sections_present', 'timeline_correct',
    'numbers_match', 'text_overflow', 'headings_match', 'major_typos',
)
VISION_VERDICTS = ('PASS', 'FAIL', 'UNCERTAIN')
FIXTURE_PROVIDER_ID = 'fixture-test-only'


class VisionProviderFailure(ValueError):
    def __init__(self, reason: str):
        self.reason = reason
        super().__init__(reason)


@dataclass(frozen=True)
class VisionReviewResult:
    checks: dict[str, str]

    @classmethod
    def parse(cls, value: object) -> 'VisionReviewResult':
        if not isinstance(value, dict) or set(value) != set(REQUIRED_VISION_CHECKS):
            raise VisionProviderFailure('VISION_OUTPUT_SCHEMA_INVALID')
        if any(type(value[name]) is not str or value[name] not in VISION_VERDICTS for name in REQUIRED_VISION_CHECKS):
            raise VisionProviderFailure('VISION_OUTPUT_SCHEMA_INVALID')
        return cls(dict(value))


class VisionProvider(Protocol):
    provider_id: str

    def review(self, image_path: Path, report: dict, spec: dict) -> VisionReviewResult: ...


class FixtureVisionProvider:
    """Deterministic fixture; it does not inspect the image and is never production evidence."""
    provider_id = FIXTURE_PROVIDER_ID

    def review(self, image_path: Path, report: dict, spec: dict) -> VisionReviewResult:
        del image_path, report, spec
        return VisionReviewResult.parse({name: 'PASS' for name in REQUIRED_VISION_CHECKS})


class ExternalVisionProvider:
    """Integration seam for a future approved provider; intentionally unconfigured."""

    def __init__(self, provider_id: str):
        self.provider_id = provider_id

    def review(self, image_path: Path, report: dict, spec: dict) -> VisionReviewResult:
        del image_path, report, spec
        raise VisionProviderFailure('VISION_PROVIDER_NOT_CONFIGURED')


VISION_RESPONSE_SCHEMA = {
    'type': 'object', 'additionalProperties': False,
    'required': list(REQUIRED_VISION_CHECKS),
    'properties': {name: {'type': 'string', 'enum': list(VISION_VERDICTS)} for name in REQUIRED_VISION_CHECKS},
}


def build_vision_prompt(report: dict, spec: dict) -> str:
    """Prompt for an external provider; source values are supplied as read-only evidence."""
    import json
    source = report.get('fullText') or report.get('full_text') or report.get('rawText') or report.get('body') or ''
    evidence = {'report_id': spec.get('report_id'), 'title': report.get('title'),
                'date': report.get('date') or report.get('report_date'),
                'time': report.get('time') or report.get('report_time'),
                'source_text': source, 'timeline': spec.get('timeline'),
                'required_sections': [panel.get('title') for panel in spec.get('panels', []) if isinstance(panel, dict)],
                'panels': spec.get('panels')}
    criteria = (
        'Inspect the supplied image against the source evidence only. Do not infer, repair, or guess text or values. '
        'Return exactly the required JSON object with one verdict per check: PASS, FAIL, or UNCERTAIN. '
        'Use UNCERTAIN whenever any visual evidence is unreadable or ambiguous. '
        'PASS means: no decorative charts, gauges, invented charts, people, overflow, or major typos; '
        'and the title, date, time, required sections, timeline, source numbers, and headings are correct. '
        'Do not add commentary or additional keys.'
    )
    return criteria + '\nSOURCE_EVIDENCE_JSON=' + json.dumps(evidence, ensure_ascii=False, sort_keys=True, separators=(',', ':'))
