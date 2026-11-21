"""Exercise repeat preparation and the failure diagnostics users need over SSH."""
import contextlib
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest
import zipfile

MODULE_PATH = Path(__file__).resolve().parents[1] / 'deploy/ubuntu22/ecg_v6_prepare.py'
spec = importlib.util.spec_from_file_location('ecg_v6_prepare', MODULE_PATH)
prepare = importlib.util.module_from_spec(spec)
spec.loader.exec_module(prepare)


class PrepareV6Tests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='ecg-v6-prepare-test-')
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.archive = self.root / 'v6.zip'
        content = b'original application\n'
        manifest = {'files': [{'path': 'web/app.py', 'sha256': prepare.hashlib.sha256(content).hexdigest()}]}
        with zipfile.ZipFile(self.archive, 'w') as z:
            z.writestr('ecg-ai/web/app.py', content)
            z.writestr('ecg-ai/DELIVERY_MANIFEST.json', json.dumps(manifest))
        self.expected = prepare.digest(self.archive)
        self.target = self.root / 'release'

    def run_prepare(self):
        return prepare.prepare(self.archive, self.target, self.expected, log=lambda _: None)

    def test_first_prepare_extracts_and_verifies(self):
        project = self.run_prepare()
        self.assertEqual((project / 'web/app.py').read_bytes(), b'original application\n')

    def test_repeat_complete_target_preserves_config_and_files(self):
        project = self.run_prepare()
        config = project / '.env'
        config.write_text('KEEP_EXISTING_CONFIG=1')
        before = (project / 'web/app.py').stat().st_mtime_ns
        self.run_prepare()
        self.assertEqual(config.read_text(), 'KEEP_EXISTING_CONFIG=1')
        self.assertEqual((project / 'web/app.py').stat().st_mtime_ns, before)

    def test_partial_target_fails_without_overwriting(self):
        project = self.run_prepare()
        file = project / 'web/app.py'
        file.write_bytes(b'local changes')
        with self.assertRaisesRegex(ValueError, 'fresh directory'):
            self.run_prepare()
        self.assertEqual(file.read_bytes(), b'local changes')

    def test_wrong_zip_hash_does_not_create_target(self):
        with self.assertRaisesRegex(ValueError, 'SHA-256 mismatch'):
            prepare.prepare(self.archive, self.target, '0' * 64, log=lambda _: None)
        self.assertFalse(self.target.exists())

    def test_missing_zip_returns_error_and_records_log(self):
        log = self.root / 'prepare.log'
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = prepare.main(['--archive', str(self.root/'missing.zip'), '--target', str(self.target), '--log', str(log)])
        self.assertEqual(code, 1)
        self.assertIn('ZIP not found', out.getvalue())
        self.assertIn('ZIP not found', log.read_text(encoding='utf-8'))

    def test_unsafe_paths_rejected(self):
        for path in ('../old', '/root/old', 'C:/old', 'web\\old'):
            with self.subTest(path=path), self.assertRaises(ValueError):
                prepare.relative_path(path)


if __name__ == '__main__':
    unittest.main()
