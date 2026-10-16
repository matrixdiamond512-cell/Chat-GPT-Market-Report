import copy
from io import BytesIO
import json
from pathlib import Path
import unittest
from PIL import Image

from morning_fixture import fixture, formal_contract_fixture, ROOT
from reporting.infographic import ValidationFailure
from reporting.morning_layout import validate_projection, render_html, build_manifest, sha, direction_class, change_class


class MorningLayoutTests(unittest.TestCase):
    def setUp(self):
        self.report, self.view = fixture()

    def invalid(self, reason, report=None, view=None, **kwargs):
        with self.assertRaises(ValidationFailure) as error:
            validate_projection(report or self.report, view or self.view, fixture=kwargs.pop('fixture',True), **kwargs)
        self.assertEqual(error.exception.reason, reason)

    def test_all_content_and_fixed_cards(self):
        doc, contract = render_html(self.report, self.view, fixture=True)
        self.assertEqual(doc.count('data-card='),16)
        self.assertIn('DRAFT / 合成データ・公開不可',doc)
        self.assertEqual(len(contract['expected_text']),len(self.view['facts']))
        self.assertIn('非常に長い合成ニュース',doc)
        self.assertIn('取得不能',doc)

    def test_card_sequence(self):
        self.view['cards'][1]['number']=1
        self.invalid('MORNING_CARD_SEQUENCE')

    def test_empty_card_cannot_pass(self):
        self.view['cards'][10]['paragraphs']=[]
        self.invalid('MORNING_REQUIRED_CARD_CONTENT')

    def test_three_scenario_paths(self):
        self.view['cards'][11]['chains'][2]['scenario']='upside'
        self.invalid('MORNING_SCENARIO_PATHS')

    def test_other_slots_rejected(self):
        for slot in ('12:00','16:00','21:00'):
            report=copy.deepcopy(self.report); report['time']=slot
            self.invalid('MORNING_SLOT_ONLY',report=report)

    def test_missing_snapshot_blocks_even_fixture(self):
        self.report.pop('snapshot')
        self.invalid('MARKET_DATA_SNAPSHOT_NOT_FOUND')

    def test_fixture_cannot_become_formal(self):
        self.invalid('FIXTURE_MODE_MISMATCH', fixture=False)

    def test_formal_requires_existing_spec(self):
        self.report['synthetic_fixture']=False; self.view['synthetic_fixture']=False
        self.invalid('CANONICAL_SPEC_REQUIRED',fixture=False)

    def test_source_digit_change(self):
        self.view['facts'][0]['text']+='9'
        self.invalid('MORNING_FACT_SOURCE_MISMATCH')

    def test_summary_may_omit_detail_while_body_remains_hash_bound(self):
        self.report['fullText']+='未表示の分析内容\n'
        from reporting.infographic import SourceLock
        self.view['body_hash']=SourceLock.create(self.report).sha256
        result=validate_projection(self.report,self.view,fixture=True)
        self.assertEqual(result['status'],'PASS')
        self.assertTrue(self.report['fullText'].endswith('未表示の分析内容\n'))

    def test_missing_market_field(self):
        self.view['cards'][12]['markets'][0]['rationale']={'ref':'absent'}
        self.invalid('MORNING_FACT_COVERAGE')

    def test_market_order(self):
        self.view['cards'][12]['markets'].reverse()
        self.invalid('MORNING_SIX_MARKETS')

    def test_timestamp_binding(self):
        self.view['cards'][12]['markets'][0]['asof']=self.view['cards'][12]['markets'][1]['asof']
        self.invalid('MORNING_MARKET_BINDING_MISMATCH')

    def test_wrong_source_section(self):
        self.view['facts'][0]['source_section']='総合判断'
        self.invalid('MORNING_FACT_SECTION_MISMATCH')

    def test_missing_root_snapshot_identity(self):
        report,view,spec=formal_contract_fixture()
        report.pop('snapshot_id')
        self.invalid('MORNING_REPORT_SNAPSHOT_ID_MISSING_OR_MISMATCH',report=report,view=view,fixture=False,spec=spec)

    def test_snapshot_numeric_drift(self):
        price=self.view['cards'][12]['markets'][0]['price']['ref']
        next(f for f in self.view['facts'] if f['id']==price)['snapshot_field']['field']='changePct'
        self.invalid('NUMERIC_DRIFT')

    def test_flow_basis_and_causal_labels(self):
        self.view['cards'][8]['flow']['basis']='measured'
        self.invalid('MORNING_FLOW_MEASUREMENT_UNLABELLED')
        self.view['cards'][8]['flow']['basis']='estimated'
        self.view['cards'][9]['chains'][0]['basis']='confirmed'
        self.invalid('MORNING_CAUSAL_LABEL_MISSING')

    def test_colors_are_separate_concepts(self):
        self.assertEqual(change_class('+1.23%'),'up')
        self.assertEqual(change_class('−1.23%'),'down')
        self.assertEqual(change_class('±0.00'),'flat')
        self.assertEqual(direction_class('中立〜やや弱気'),('down','↓'))
        doc,_=render_html(self.report,self.view,fixture=True)
        self.assertIn('class="inflow"',doc); self.assertIn('class="outflow"',doc)
        self.assertIn('class="transfer estimated"',doc)

    def test_formal_contract_calls_unchanged_gate(self):
        report,view,spec=formal_contract_fixture()
        result=validate_projection(report,view,spec=spec)
        self.assertEqual(result['canonical_spec_validation'],'PASS')
        spec['snapshot_id']='wrong'
        self.invalid('SNAPSHOT_ID_MISMATCH',report=report,view=view,fixture=False,spec=spec)

    def test_formal_projection_cannot_add_source_fact_outside_spec(self):
        report,view,spec=formal_contract_fixture()
        spec['panels'][0]['text']=''
        self.invalid('MORNING_FACT_OUTSIDE_VALIDATED_SPEC',report=report,view=view,fixture=False,spec=spec)

    def test_manifest_binding_and_debug_guard(self):
        png=BytesIO(); Image.new('RGB',(2,2),'white').save(png,format='PNG'); data=png.getvalue()
        _,contract=render_html(self.report,self.view,fixture=True)
        receipt={'status':'PASS','artifact_type':'DEBUG_PREVIEW','numeric_validation':'PASS','renderer_status':'PASS','html_sha256':contract['html_sha256'],
                 'view_sha256':contract['view_sha256'],'png_sha256':sha(data),'rendered_fact_ids':contract['validation']['required_fact_ids']}
        manifest=build_manifest(self.report,self.view,data,receipt,'fixture-drive',data,'fixture.png',fixture=True)
        self.assertEqual(manifest['artifact_type'],'DEBUG_PREVIEW')
        self.assertEqual(manifest['status'],'DRAFT')
        with self.assertRaises(ValidationFailure):
            build_manifest(self.report,self.view,data,receipt,'fixture-drive',data+b'changed','fixture.png',fixture=True)
        receipt['png_sha256']='0'*64
        with self.assertRaises(ValidationFailure):
            build_manifest(self.report,self.view,data,receipt,'fixture-drive',data,'fixture.png',fixture=True)

    def test_historical_inputs_stay_blocked(self):
        for day in ('2026-10-09','2026-10-12'):
            report=json.loads((ROOT/'reports'/f'{day}_08-00.json').read_text(encoding='utf-8'))
            report['synthetic_fixture']=False
            view=copy.deepcopy(self.view); view['synthetic_fixture']=False
            self.invalid('MARKET_DATA_SNAPSHOT_NOT_FOUND',report=report,view=view,fixture=False)


if __name__ == '__main__':
    unittest.main()
