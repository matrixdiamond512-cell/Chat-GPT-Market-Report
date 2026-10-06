import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'scripts'))
from reporting.snapshot import MarketDataSnapshot
from reporting.report import ReportObject, adapt_legacy, canonical_heading, REGISTRY
from tests.test_market_snapshot import context, market


class ObjectTests(unittest.TestCase):
    def test_legacy_adapter_preserves_unresolved_target(self):
        raw = {'latestReport': {'date': '2026-10-02', 'time': '21:00', 'title': 't', 'fullText': '原文。\n'}}
        old = adapt_legacy(raw)
        self.assertEqual(old.canonicalIdentity, 'UNRESOLVED')
        self.assertEqual(old.publicationStatus, 'UNVERIFIED')
        self.assertEqual(old.original['latestReport']['fullText'], '原文。\n')

    def test_numeric_schema_distinguishes_zero_and_null(self):
        zero = market(priceValue=0, changeValue=0, changePct=0, direction='FLAT')
        self.assertEqual(zero.priceValue, 0)
        with self.assertRaises(ValueError):
            market(priceValue='89.47ドル')
        unavailable = market(priceValue=None, changeValue=None, changePct=None, direction='UNKNOWN', status='UNAVAILABLE', unavailableReason='取得不能')
        self.assertIsNone(unavailable.priceValue)

    def test_display_is_not_numeric_or_outlook(self):
        m = market(displayText='表示89.47', outlook='強気')
        self.assertEqual((m.priceValue, m.direction, m.outlook), (89.47, 'DOWN', '強気'))

    def test_all_shared_heading_aliases(self):
        for canonical, aliases in REGISTRY['sections'].items():
            for alias in aliases:
                for spelling in (alias, '【'+alias+'】', '1．'+alias, '## '+alias):
                    self.assertEqual(canonical_heading(spelling), canonical)

    def test_original_full_text_preserved(self):
        text = ' 原文。\r\n\r\n主要市場データ\r\n89.47ドル\r\n'
        snapshot = MarketDataSnapshot.capture(context(), [market()], '2026-10-02T20:54:00+09:00')
        obj = ReportObject.build(context(), snapshot, 't', text)
        self.assertEqual(obj.full_text, text)
        self.assertEqual(obj, ReportObject.restore(obj.to_dict()))

    def test_real_preserved_21_fixture_remains_unresolved(self):
        import json
        path = Path(__file__).parent/'fixtures/2026-10-02_21-00.json'
        raw = json.loads(path.read_text(encoding='utf-8'))
        adapted = adapt_legacy(raw)
        self.assertEqual(adapted.report.full_text, raw['fullText'])
        self.assertEqual(adapted.canonicalIdentity, 'UNRESOLVED')
        self.assertEqual(adapted.reviewStatus, 'NEEDS_REVIEW')
