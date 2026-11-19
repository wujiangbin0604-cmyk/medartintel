"""An update can add research checkpoints while protecting original artifacts."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

APPLIER = Path(__file__).resolve().parents[1] / "apply_update.py"


class ResearchUpdateTests(unittest.TestCase):
    def test_verify_bundle_cli_imports_project_in_isolated_python(self):
        verifier=Path(__file__).resolve().parents[2]/"ubuntu22/verify_bundle.py"
        result=subprocess.run([sys.executable,"-I",str(verifier),"--files-only"],cwd=verifier.parents[2],capture_output=True,text=True)
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertEqual(json.loads(result.stdout)["research_checkpoints"],60)

    def test_github_package_includes_missing_runtime_source(self):
        from deploy.update.from_github import make_package
        with tempfile.TemporaryDirectory(prefix="ecg-snapshot-") as temp:
            base=Path(temp);source=base/"snapshot";target=base/"target";package=base/"package"
            target.mkdir();(source/"deploy/ubuntu22").mkdir(parents=True);(source/"deploy/update").mkdir();(source/"src").mkdir()
            content=b"new runtime source"
            (source/"src/runtime.py").write_bytes(content)
            runtime={"files":[{"path":"src/runtime.py","sha256":hashlib.sha256(content).hexdigest()}]}
            (source/"deploy/ubuntu22/bundle_manifest.json").write_text(json.dumps(runtime))
            for name in [".dockerignore",".gitignore",".gitattributes"]:(source/name).write_bytes(b"")
            self.assertGreater(make_package(source,package,target),0)
            self.assertEqual((package/"payload/src/runtime.py").read_bytes(),content)

    def test_github_noop_package_can_validate_current_checkout(self):
        from deploy.update.from_github import make_package
        import shutil
        with tempfile.TemporaryDirectory(prefix="ecg-snapshot-") as temp:
            base=Path(temp);source=base/"snapshot";target=base/"target";package=base/"package"
            (source/"deploy/ubuntu22").mkdir(parents=True);(source/"deploy/update").mkdir()
            (source/"deploy/ubuntu22/bundle_manifest.json").write_text('{"files":[]}')
            for name in [".dockerignore",".gitignore",".gitattributes"]:(source/name).write_bytes(b"")
            shutil.copytree(source,target)
            self.assertEqual(make_package(source,package,target),0)
            self.assertEqual(json.loads((package/"update_manifest.json").read_text())["files"],[])

    def apply(self, relative, existing=None):
        with tempfile.TemporaryDirectory(prefix="ecg-research-update-") as temp:
            base = Path(temp); target = base / "existing"; package = base / "package"; payload = package / "payload"
            for name in ["web/backend/production.py", "deploy/ubuntu22/compose.yaml"]:
                p = target / name; p.parent.mkdir(parents=True, exist_ok=True); p.write_text("", encoding="utf-8")
            original = target / "checkpoints/original.pt"; original.parent.mkdir(); original.write_bytes(b"original-model")
            (target / ".env").write_bytes(b"existing-env")
            if existing is not None:
                p = target / relative; p.parent.mkdir(parents=True, exist_ok=True); p.write_bytes(existing)
            contents = {relative: b"new-research-model"}
            entries = [{"path":p,"sha256":hashlib.sha256(c).hexdigest()} for p,c in contents.items()]
            contents["deploy/ubuntu22/bundle_manifest.json"] = json.dumps({"files":entries}).encode()
            for name,content in contents.items():
                p = payload / name; p.parent.mkdir(parents=True, exist_ok=True); p.write_bytes(content)
            (package / "update_manifest.json").write_text(json.dumps({"files":[{"path":p,"sha256":hashlib.sha256(c).hexdigest()} for p,c in contents.items()]}))
            result = subprocess.run([sys.executable,str(APPLIER),str(target),"--package",str(package)],capture_output=True,text=True)
            self.assertEqual(original.read_bytes(),b"original-model")
            self.assertEqual((target/".env").read_bytes(),b"existing-env")
            if result.returncode == 0:
                self.assertEqual((target/relative).read_bytes(),b"new-research-model")
                self.assertTrue(list(base.glob(".existing-update-backups/*/update_backup.json")))
            elif existing is not None:
                self.assertEqual((target/relative).read_bytes(),existing)
            return result

    def test_new_research_checkpoint_is_installed(self):
        result=self.apply("research_extensions/rhythm_fusion/results/cv_cpu_v1/fold0/seed1/A2/best.pt")
        self.assertEqual(result.returncode,0,result.stderr)

    def test_original_formal_model_is_rejected(self):
        result=self.apply("checkpoints/new.pt")
        self.assertNotEqual(result.returncode,0)
        self.assertIn("protected data",result.stderr)

    def test_different_existing_research_checkpoint_is_preserved(self):
        result=self.apply("research_extensions/rhythm_fusion/results/cv_cpu_v1/fold0/seed1/A2/best.pt",b"frozen-model")
        self.assertNotEqual(result.returncode,0)
        self.assertIn("new experiment directory",result.stderr)


if __name__ == "__main__":unittest.main()
