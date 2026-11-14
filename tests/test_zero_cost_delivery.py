"""Synthetic/offline contracts; never evidence of real scheduled publication."""
import hashlib
from contextlib import closing
import json
from pathlib import Path
import shutil
import socket
import sqlite3
import struct
import sys
import tempfile
import unittest
from unittest.mock import patch
import zlib

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import run_report_delivery as delivery
from persist_report_slot_evidence import persist_slot_evidence
from reporting.publication_evidence import verify_slot_evidence
from report_source_contract import title_for
from verify_zero_cost_delivery import check

ROOT = Path(__file__).resolve().parents[1]


def write(path, obj):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(obj,ensure_ascii=False),encoding='utf-8')


def png():
    def chunk(kind,data):
        return struct.pack('>I',len(data))+kind+data+struct.pack('>I',zlib.crc32(kind+data)&0xffffffff)
    return b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('>IIBBBBB',1,1,8,2,0,0,0))+chunk(b'IDAT',zlib.compress(b'\0\0\0\0'))+chunk(b'IEND',b'')


class DeliveryTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.root=Path(self.temp.name)
        for name in ['report_delivery_policy.json','report_schedule.json']:
            target=self.root/'config'/name
            target.parent.mkdir(exist_ok=True)
            shutil.copyfile(ROOT/'config'/name,target)
        self.bundle=self.root/'input'
        self.bundle.mkdir()
        self.key='2026-11-12_12-00'
        self.body=self.valid_body('12:00')
        self.report={'date':'2026-11-12','time':'12:00','title':title_for('2026-11-12','12:00'),
            'revision':1,'fullText':self.body,'bodyHash':delivery.digest(self.body.encode()),
            'sourceRevisionId':'synthetic-doc-rev','report_status':'DOC_READBACK_PASS',
            'sourceDocument':{'id':'synthetic-doc','url':'https://docs.google.com/document/d/synthetic-doc/edit'}}
        market={'generatedAt':'2026-11-12T11:50:00+09:00','reportDate':'2026-11-12','reportSlot':'12:00','overallStatus':'verified',
            'markets':{'USDJPY':{'id':'USDJPY','marketType':'FX','unit':'JPY','value':157.8,'change':0.0,'changePercent':0.0,
            'comparisonBasis':'previous_close','asOf':'2026-11-12T11:49:00+09:00','sourceId':'synthetic-source',
            'sourceUrl':'https://example.test/usdjpy','verificationStatus':'verified','freshnessStatus':'fresh','displayValue':'157.8'}}}
        write(self.root/'market.json',market)
        evidence,_=persist_slot_evidence('2026-11-12','12:00',self.root/'market.json',self.root/'evidence')
        shutil.copyfile(evidence,self.bundle/'evidence.json')
        self.drive={'id':'synthetic-doc','mimeType':'application/vnd.google-apps.document','parents':['synthetic-month'],
            'createdTime':'2026-11-12T12:02:00+09:00','modifiedTime':'2026-11-12T12:03:00+09:00'}
        receipt=verify_slot_evidence(self.report,self.bundle/'evidence.json',self.drive,'synthetic-doc-rev')
        self.report['publicationEvidence']={k:receipt[k] for k in ['evidenceId','snapshotId','contextHash','snapshotHash','bodyHash','documentRevisionId']}
        write(self.bundle/'report.json',self.report)
        write(self.bundle/'receipt.json',receipt)
        write(self.bundle/'drive-file.json',self.drive)
        write(self.bundle/'bundle.json',{'bodyMonthFolderId':'synthetic-month'})
        self.image=png()
        (self.bundle/'infographic.png').write_bytes(self.image)
        self.manifest={'report_id':self.key,'revision':1,'snapshot_id':receipt['snapshotId'],'body_hash':self.report['bodyHash'],
            'png_sha256':delivery.digest(self.image),'png_filename':f'マーケットレポート_{self.key}.png'}
        write(self.bundle/'infographic-manifest.json',self.manifest)

    def valid_body(self,slot):
        headings=['今日の相場テーマ','主要市場データ','材料と値動きの整合性','主導市場','重要ニュース',
            'クロスアセット資金フロー','需給・ポジション','6市場の個別見通し','メインシナリオ','崩れる条件','結論','08:00からの変化']
        paragraph='これは架空テスト専用。金 WTI原油 日経 USD/JPY EUR/USD BTC は実際の市場観測ではない。'*4
        return title_for('2026-11-12',slot)+'\n'+'\n'.join('【'+h+'】\n'+paragraph for h in headings)

    def tearDown(self):
        self.temp.cleanup()

    def run_candidate(self):
        with patch.object(socket.socket,'connect',side_effect=AssertionError('NETWORK_FORBIDDEN')):
            return delivery.run(self.key,self.bundle,self.root)

    def test_valid_bundle_is_shadow_only_and_idempotent(self):
        result=self.run_candidate()
        self.assertEqual(result['status'],'SHADOW_STAGED')
        self.assertEqual(result['overallAcceptance'],'NOT_VERIFIED')
        self.assertEqual(result['infographicVisualQA'],'BLOCKED_REFERENCE_IMAGE')
        self.assertEqual(result['productionWrites'],0)
        self.assertEqual(result,self.run_candidate())
        with closing(sqlite3.connect(self.root/'logs/report-delivery-shadow/journal.sqlite3')) as db:
            self.assertEqual(db.execute('select count(*) from artifacts').fetchone()[0],1)
            self.assertEqual(db.execute('select count(*) from events').fetchone()[0],1)
        for forbidden in ['reports','reports.json','data','publication-receipts']:
            self.assertFalse((self.root/forbidden).exists())

    def test_missing_body_or_image_waits_without_creating_content(self):
        for name in ['report.json','infographic.png']:
            with self.subTest(name=name):
                p=self.bundle/name;b=p.read_bytes();p.unlink()
                result=self.run_candidate()
                self.assertEqual(result['status'],'WAITING_FOR_SOURCE_ARTIFACT')
                self.assertIn(name,result['missing'])
                self.assertFalse(p.exists())
                p.write_bytes(b)

    def test_bad_hash_missing_snapshot_and_wrong_parent_are_blocked(self):
        original={p:p.read_bytes() for p in self.bundle.iterdir()}
        cases=[('report.json',{**self.report,'bodyHash':'0'*64},'SOURCE_BODY_HASH'),
            ('drive-file.json',{**self.drive,'parents':['wrong-month']},'MONTH_FOLDER'),
            ('evidence.json',{'schemaVersion':1,'evidenceStatus':'INVALID'},'SNAPSHOT'),
            ('infographic-manifest.json',{**self.manifest,'body_hash':'0'*64},'INFOGRAPHIC_SOURCE')]
        for name,data,reason in cases:
            with self.subTest(name=name):
                write(self.bundle/name,data)
                result=self.run_candidate()
                self.assertEqual(result['status'],'SHADOW_BLOCKED')
                self.assertIn(reason,result['reason'])
                for p,b in original.items():p.write_bytes(b)

    def test_image_byte_mutation_is_blocked(self):
        (self.bundle/'infographic.png').write_bytes(b'\x89PNG\r\n\x1a\n')
        self.assertEqual(self.run_candidate()['status'],'SHADOW_BLOCKED')

    def test_same_revision_changed_bundle_does_not_overwrite(self):
        self.assertEqual(self.run_candidate()['status'],'SHADOW_STAGED')
        write(self.bundle/'bundle.json',{'bodyMonthFolderId':'synthetic-month','changed':True})
        self.assertIn('SHADOW_SOURCE_ARCHIVE_CONFLICT',self.run_candidate()['reason'])

    def test_crash_rolls_back_and_retry_resumes_original(self):
        store=delivery._store
        def crash(*args):
            store(*args)
            raise ValueError('SYNTHETIC_CRASH_BEFORE_COMMIT')
        with patch.object(delivery,'_store',side_effect=crash):
            self.assertEqual(self.run_candidate()['status'],'SHADOW_BLOCKED')
        with closing(sqlite3.connect(self.root/'logs/report-delivery-shadow/journal.sqlite3')) as db:
            self.assertEqual(db.execute('select count(*) from artifacts').fetchone()[0],0)
        self.assertEqual(self.run_candidate()['status'],'SHADOW_STAGED')

    def test_missing_durable_image_is_not_silently_recreated(self):
        self.assertEqual(self.run_candidate()['status'],'SHADOW_STAGED')
        with closing(sqlite3.connect(self.root/'logs/report-delivery-shadow/journal.sqlite3')) as db:
            db.execute("DELETE FROM source_files WHERE name='infographic.png'")
            db.commit()
        self.assertIn('SHADOW_SOURCE_ARCHIVE_CONFLICT',self.run_candidate()['reason'])

    def test_source_change_during_validation_stops_commit(self):
        validate=delivery.validate_bundle
        def mutate(*args):
            result=validate(*args)
            write(self.bundle/'bundle.json',{'bodyMonthFolderId':'synthetic-month','raced':True})
            return result
        with patch.object(delivery,'validate_bundle',side_effect=mutate):
            result=self.run_candidate()
        self.assertIn('SOURCE_CHANGED_DURING_VALIDATION',result['reason'])
        with closing(sqlite3.connect(self.root/'logs/report-delivery-shadow/journal.sqlite3')) as db:
            self.assertEqual(db.execute('select count(*) from artifacts').fetchone()[0],0)

    def test_morning_table_gate_runs_before_receipt_or_image_acceptance(self):
        self.key='2026-11-12_08-00'
        self.report['time']='08:00'
        self.report['title']=title_for('2026-11-12','08:00')
        self.report['fullText']=self.body.replace('12:00','08:00').replace('08:00からの変化','東京時間への引き継ぎ')
        self.report['bodyHash']=delivery.digest(self.report['fullText'].encode())
        write(self.bundle/'report.json',self.report)
        result=self.run_candidate()
        self.assertIn('MORNING_CONTENT_QA_BLOCKED',result['reason'])
        qa=json.loads((self.root/'logs/report-delivery-shadow'/self.key/'morning-qa.json').read_text(encoding='utf-8'))
        self.assertFalse(qa['ready'])
        self.assertEqual(qa['expectedRowCount'],28)

    def test_parallel_writer_is_locked(self):
        self.run_candidate()
        with closing(sqlite3.connect(self.root/'logs/report-delivery-shadow/journal.sqlite3')) as db:
            db.execute('BEGIN IMMEDIATE')
            with self.assertRaises(sqlite3.OperationalError):self.run_candidate()
            db.rollback()
        self.assertEqual(self.run_candidate()['status'],'SHADOW_STAGED')

    def test_wrong_slot_and_weekend_are_rejected(self):
        result=delivery.run('2026-11-12_16-00',self.bundle,self.root)
        self.assertIn('SOURCE_IDENTITY_MISMATCH',result['reason'])
        with self.assertRaisesRegex(ValueError,'SLOT_NOT_CONFIGURED'):
            delivery.run('2026-11-14_08-00',self.bundle,self.root)
        with self.assertRaisesRegex(ValueError,'EXPLICIT_REPORT_ID_REQUIRED'):
            delivery.run('../reports',self.bundle,self.root)

    def test_billing_policy_fails_closed(self):
        write(self.root/'config/report_delivery_policy.json',{'mode':'shadow','changeId':'test'})
        self.assertEqual(self.run_candidate()['status'],'BLOCKED_COST_UNVERIFIED')


class CostTests(unittest.TestCase):
    def test_repo_has_no_enabled_ai_api_workflows(self):
        result=check()
        self.assertEqual(result['status'],'PASS_LOCAL_ONLY',result)
        self.assertEqual(len(result['retainedApiWorkflows']),4)

    def test_production_cost_is_not_asserted_from_local_pass(self):
        self.assertEqual(check(production=True)['status'],'BLOCKED_COST_UNVERIFIED')

    def test_one_reenabled_job_blocks_even_with_another_disabled_job(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            write(root/'config/report_delivery_policy.json',json.loads((ROOT/'config/report_delivery_policy.json').read_text(encoding='utf-8-sig')))
            workflow=root/'.github/workflows/test.yml';workflow.parent.mkdir(parents=True)
            workflow.write_text('name: test\non: workflow_dispatch\njobs:\n  disabled:\n    if: ${{ false }}\n    steps: []\n  live:\n    steps:\n      - run: curl https://api.openai.com/v1/responses\n',encoding='utf-8')
            self.assertEqual(check(root)['status'],'BLOCKED_COST_UNVERIFIED')


if __name__ == '__main__':unittest.main()
