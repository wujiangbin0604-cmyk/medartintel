import base64
import contextlib
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest

spec=importlib.util.spec_from_file_location('pathfix',Path(__file__).resolve().parents[1]/'deploy/update/linux_path_fix_template.py')
fix=importlib.util.module_from_spec(spec);spec.loader.exec_module(fix)


class LinuxPathFixTests(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory(prefix='ecg-linuxfix-test-');self.addCleanup(temp.cleanup)
        self.project=Path(temp.name)/'ecg-ai';self.project.mkdir()
        self.source='web/backend/rhythm_lab.py';self.put(self.source,b'old source')
        self.model='research_extensions/rhythm_fusion/results/cv_cpu_v1/fold0/seed20261118/A0/best.pt'
        self.put(self.model,b'original weights')
        entries=[{'model':'A0','checkpoint':r'results\cv_cpu_v1\fold0\seed20261118\A0\best.pt',
                  'sha256':fix.sha(b'original weights')} for _ in range(60)]
        self.put('research_extensions/rhythm_fusion/results/cv_cpu_v1/model_registry.json',json.dumps({'models':entries}).encode())
        self.put('deploy/ubuntu22/bundle_manifest.json',json.dumps({'files':[
            {'path':self.source,'bytes':10,'sha256':fix.sha(b'old source')}]}).encode())
        self.put('DELIVERY_MANIFEST.json',json.dumps({'files':[]}).encode())
        self.put('.env',b'KEEP_EXISTING_ENV=1')
        self.payload={self.source:{'base64':base64.b64encode(b'fixed source').decode(),
            'sha256':fix.sha(b'fixed source'),'original_sha256':fix.sha(b'old source')}}

    def put(self,path,data):
        p=self.project/path;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(data)

    def apply(self):
        with contextlib.redirect_stdout(io.StringIO()):return fix.apply(self.project,self.payload)

    def test_patch_refreshes_manifests_and_preserves_models_and_environment(self):
        result=self.apply();self.assertGreater(result['changed_files'],0)
        self.assertEqual((self.project/self.source).read_bytes(),b'fixed source')
        self.assertEqual((self.project/'.env').read_bytes(),b'KEEP_EXISTING_ENV=1')
        self.assertEqual((self.project/self.model).read_bytes(),b'original weights')
        row=json.loads((self.project/'deploy/ubuntu22/bundle_manifest.json').read_text())['files'][0]
        self.assertEqual(row['sha256'],fix.sha(b'fixed source'))
        backup=Path(result['backup']);self.assertEqual((backup/self.source).read_bytes(),b'old source')
        top=json.loads((self.project/'DELIVERY_MANIFEST.json').read_text())
        row=next(r for r in top['files'] if r['path']=='deploy/ubuntu22/bundle_manifest.json')
        self.assertEqual(row['sha256'],fix.sha((self.project/row['path']).read_bytes()))

    def test_repeat_patch_is_a_noop(self):
        self.apply();self.assertEqual(self.apply()['changed_files'],0)

    def test_locally_edited_source_is_preserved(self):
        self.put(self.source,b'local edit')
        before=(self.project/'deploy/ubuntu22/bundle_manifest.json').read_bytes()
        with self.assertRaisesRegex(ValueError,'refusing overwrite'):self.apply()
        self.assertEqual((self.project/self.source).read_bytes(),b'local edit')
        self.assertEqual((self.project/'deploy/ubuntu22/bundle_manifest.json').read_bytes(),before)

    def test_missing_model_stops_before_any_code_changes(self):
        (self.project/self.model).unlink()
        with self.assertRaisesRegex(ValueError,'Model missing'):self.apply()
        self.assertEqual((self.project/self.source).read_bytes(),b'old source')


if __name__=='__main__':unittest.main()
