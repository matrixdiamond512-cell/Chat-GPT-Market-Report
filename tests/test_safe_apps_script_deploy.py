import importlib.util
import tempfile
import unittest
from pathlib import Path

MODULE_PATH = Path(__file__).resolve().parents[1] / 'scripts' / 'deploy_market_report_apps_script.py'
spec = importlib.util.spec_from_file_location('appssync', MODULE_PATH)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

class SourceSyncTests(unittest.TestCase):
    def test_existing_unrelated_files_are_preserved(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / 'apps-script').mkdir()
            remote = [{'name': 'appsscript', 'type': 'JSON', 'source': '{"timeZone":"Asia/Tokyo"}'},
                      {'name': 'OtherUnrelated', 'type': 'SERVER_JS', 'source': 'original'}]
            for name in mod.TARGET_FILES:
                (root / 'apps-script' / (name + '.gs')).write_text('// source for ' + name, encoding='utf-8')
                remote.append({'name': name, 'type': 'SERVER_JS', 'source': 'old', 'updateTime': 'read-only'})
            updated = mod.prepare_update(remote, root)
            self.assertEqual(updated[0]['source'], remote[0]['source'])
            self.assertEqual(updated[1]['source'], remote[1]['source'])
            self.assertFalse(any('updateTime' in row for row in updated))
            self.assertEqual(len(updated), len(remote))
            for name in mod.TARGET_FILES:
                self.assertEqual(next(x for x in updated if x['name']==name)['source'], '// source for ' + name)
            self.assertNotEqual(mod.digest(updated), mod.digest(remote))

    def test_missing_expected_project_files_fails_closed(self):
        with self.assertRaisesRegex(ValueError, 'missing required files'):
            mod.prepare_update([{'name': 'appsscript', 'type': 'JSON', 'source': '{}'}])

    def test_digest_is_stable_after_read_only_metadata_removed(self):
        files = [{'name':'Only', 'type':'SERVER_JS', 'source':'a', 'updateTime':'some timestamp'}]
        self.assertEqual(mod.digest(files), mod.digest(mod.canonical_files(files)))

if __name__ == '__main__':
    unittest.main()
