"""Regression checks for updates applied to deployments without deploy/local.py."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import zipfile

ROOT = Path(__file__).resolve().parents[3]
APPLIER = ROOT / "deploy/update/apply_update.py"


class UpdatePackageTests(unittest.TestCase):
    def test_shipped_archive_contains_local_launcher(self):
        archive_path = Path(os.environ.get("ECG_UPDATE_ARCHIVE", ROOT / "releases/ECG-AI_Server_Update_20261109.zip"))
        with zipfile.ZipFile(archive_path) as archive:
            self.assertTrue("payload/deploy/local.py" in archive.namelist(), "Missing/invalid artifact: deploy/local.py")
            runtime = json.loads(archive.read("payload/deploy/ubuntu22/bundle_manifest.json"))
            entry = next(e for e in runtime["files"] if e["path"] == "deploy/local.py")
            self.assertEqual(hashlib.sha256(archive.read("payload/deploy/local.py")).hexdigest(), entry["sha256"])

    def check_missing_dependency(self, check_only):
        with tempfile.TemporaryDirectory(prefix="ecg-update-regression-") as folder:
            base = Path(folder)
            target, package = base / "existing", base / "package"
            for relative in ("web/backend/production.py", "deploy/ubuntu22/compose.yaml"):
                p = target / relative
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_text("", encoding="utf-8")
            (target / "README.md").write_text("original", encoding="utf-8")
            (target / ".env").write_text("existing-config", encoding="utf-8")
            payload = package / "payload"
            (payload / "deploy/ubuntu22").mkdir(parents=True)
            (payload / "README.md").write_text("updated", encoding="utf-8")
            runtime = {"files": [{"path": "deploy/local.py", "sha256": hashlib.sha256(b"launcher").hexdigest()}]}
            (payload / "deploy/ubuntu22/bundle_manifest.json").write_text(json.dumps(runtime), encoding="utf-8")
            files = [{"path": p.relative_to(payload).as_posix(), "sha256": hashlib.sha256(p.read_bytes()).hexdigest()} for p in payload.rglob("*") if p.is_file()]
            (package / "update_manifest.json").write_text(json.dumps({"files": files}), encoding="utf-8")
            args = [sys.executable, str(APPLIER), str(target), "--package", str(package)]
            result = subprocess.run(args + (["--check"] if check_only else []), capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0, "An update with a missing runtime dependency must be rejected")
            self.assertIn("Missing runtime artifact: deploy/local.py", result.stderr)
            self.assertEqual((target / "README.md").read_text(encoding="utf-8"), "original")
            self.assertEqual((target / ".env").read_text(encoding="utf-8"), "existing-config")
            self.assertFalse((base / ".existing-update-backups").exists())

    def test_check_rejects_missing_runtime_dependency(self):
        self.check_missing_dependency(check_only=True)

    def test_apply_rejects_missing_dependency_before_overwriting(self):
        self.check_missing_dependency(check_only=False)


if __name__ == "__main__":
    unittest.main()
