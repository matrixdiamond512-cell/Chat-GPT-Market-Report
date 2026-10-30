"""Tests for restricted USDJPY Apps Script deployment target."""
import importlib.util
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('deploy_base', ROOT/'scripts'/'deploy_market_report_apps_script.py')
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

class UsdJpyScopedDeploymentTests(unittest.TestCase):
    def setUp(self):
        self.targets = mod.TARGET_FILES
        mod.TARGET_FILES = ('UsdJpyVolumeJsonFlexibleSync',)
    def tearDown(self):
        mod.TARGET_FILES = self.targets
    def test_only_one_named_file_changed(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            (root/'apps-script').mkdir()
            (root/'apps-script'/'UsdJpyVolumeJsonFlexibleSync.gs').write_text('new',encoding='utf-8')
            before=[
                {'name':'appsscript','type':'JSON','source':'{}'},
                {'name':'UsdJpyVolumeJsonFlexibleSync','type':'SERVER_JS','source':'old'},
                {'name':'MarketReportAutoPublish','type':'SERVER_JS','source':'production not overwritten'},
                {'name':'UsdJpyVolumePageAutoUpdate','type':'SERVER_JS','source':'schedule left alone'},
            ]
            after=mod.prepare_update(before,root)
            self.assertEqual(len(before),len(after))
            self.assertEqual([r['source'] for r in after],['{}','new','production not overwritten','schedule left alone'])
            self.assertNotEqual(mod.digest(before),mod.digest(after))
    def test_missing_target_fails(self):
        with self.assertRaisesRegex(ValueError,'missing required files'):
            mod.prepare_update([{'name':'appsscript','type':'JSON','source':'{}'}])
    def test_invalid_target_type_fails(self):
        with self.assertRaisesRegex(ValueError,'Unexpected Apps Script file type'):
            mod.prepare_update([{'name':'UsdJpyVolumeJsonFlexibleSync','type':'JSON','source':'{}'}])

if __name__ == '__main__':
    unittest.main()
