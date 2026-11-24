"""Exercise PowerShell's real environment selection without installing packages."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


@unittest.skipUnless(os.name == 'nt', 'Windows launcher')
class WindowsLauncherTests(unittest.TestCase):
    def launch(self, explicit=None):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            project = root / ('downloaded-project-' * 4)
            project.mkdir()
            shutil.copyfile(Path(__file__).parents[1] / 'start-local.ps1', project / 'start-local.ps1')
            capture = root / 'arguments.json'
            env = dict(os.environ, LOCALAPPDATA=str(root), ECG_CAPTURE=str(capture),
                       ECG_SCRIPT=str(project / 'start-local.ps1'))
            # Intercept only Python creation; the shipped launcher selects paths.
            wrapper = "function py { $args | ConvertTo-Json | Set-Content -Encoding UTF8 $env:ECG_CAPTURE; $global:LASTEXITCODE=73 }; try { & $env:ECG_SCRIPT -CheckOnly"
            if explicit:
                env['ECG_VENV'] = str(root / explicit)
                wrapper += ' -VenvPath $env:ECG_VENV'
            wrapper += ' } catch { exit 73 }'
            result = subprocess.run(['powershell', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-Command', wrapper], env=env,
                                    capture_output=True, encoding='utf-8', errors='replace')
            args = json.loads(capture.read_text(encoding='utf-8-sig')) if capture.exists() else None
            return result.returncode, args, str(root)

    def test_long_download_path_uses_short_environment(self):
        code, args, root = self.launch()
        self.assertEqual(code, 73)
        self.assertEqual(args[:3], ['-3.12', '-m', 'venv'])
        self.assertTrue(Path(args[-1]).is_absolute())
        self.assertTrue(Path(args[-1]).is_relative_to(Path(root) / 'ECG-AI' / 'venvs'))
        self.assertLessEqual(len(args[-1]), 85)

    def test_explicit_short_environment_is_used(self):
        code, args, root = self.launch('short')
        self.assertEqual(code, 73)
        self.assertEqual(Path(args[-1]), Path(root) / 'short')

    def test_too_long_override_stops_before_installation(self):
        code, args, _ = self.launch('too-long-' * 12)
        self.assertEqual(code, 73)
        self.assertIsNone(args)
