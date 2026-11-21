"""Run the Docker verifier against POSIX path semantics on every build host."""
import hashlib
import json
from pathlib import PurePosixPath
import unittest
from unittest.mock import Mock, patch

from deploy.ubuntu22 import verify_bundle


class PosixFiles(PurePosixPath):
    """A small POSIX filesystem; backslashes remain literal filename bytes."""
    files = {}

    def resolve(self):
        return self

    def is_file(self):
        return str(self) in self.files

    def read_bytes(self):
        try:
            return self.files[str(self)]
        except KeyError:
            raise FileNotFoundError(str(self)) from None

    def read_text(self, encoding='utf-8'):
        return self.read_bytes().decode(encoding)


class RegistryPortabilityTests(unittest.TestCase):
    def test_both_separator_styles_share_posix_components(self):
        from research_extensions.rhythm_fusion.src.artifact_paths import relative_artifact_path
        old=r'results\cv_cpu_v1\fold0\seed20261118\A0\best.pt'
        self.assertEqual(relative_artifact_path(old),PurePosixPath(old.replace('\\','/')))
        self.assertEqual(relative_artifact_path(old),relative_artifact_path(old.replace('\\','/')))

    def test_invalid_absolute_and_parent_paths_remain_rejected(self):
        from research_extensions.rhythm_fusion.src.artifact_paths import relative_artifact_path
        for value in ('../best.pt',r'..\best.pt','/app/best.pt',r'C:\models\best.pt','C:best.pt',r'\\host\share\best.pt',''):
            with self.subTest(value=value),self.assertRaises(ValueError):relative_artifact_path(value)

    def test_docker_verifier_reads_windows_registry_on_posix(self):
        checkpoint = b'checkpoint fixture'
        entries = [{'model':'A0', 'checkpoint':r'results\cv_cpu_v1\fold0\seed20261118\A0\best.pt',
                    'sha256':hashlib.sha256(checkpoint).hexdigest()} for _ in range(60)]
        base = '/app/research_extensions/rhythm_fusion/'
        PosixFiles.files = {
            base+'results/cv_cpu_v1/summary.json':json.dumps({'status':'completed','folds':[{}]*60,
                'config':{'seeds':[20261118,20261119,20261120]}}).encode(),
            base+'results/cv_cpu_v1/model_registry.json':json.dumps({'models':entries}).encode(),
            base+'results/cv_cpu_v1/fold0/seed20261118/A0/best.pt':checkpoint,
            base+'data/alignment.csv':b'sample_id\n',
            '/app/research_extensions/uncertainty/results/cv_cpu_v1/summary.json':json.dumps({
                'status':'completed','results':[{}]*24,'thresholds':[
                    {'calibration_subjects':['cal'],'evaluation_subjects':['eval']}]*120}).encode(),
        }
        bundle={'state_dict':{},'classes':['N','S','V','F'],'scaler':{'rhythm_median':[0]*7}}
        with patch.object(verify_bundle,'ROOT',PosixFiles('/app')), \
             patch('torch.load',return_value=bundle) as load, \
             patch('research_extensions.rhythm_fusion.src.models.make_model',return_value=Mock()):
            result=verify_bundle.verify_rhythm_artifacts()
        self.assertEqual(result['research_checkpoints'],60)
        self.assertEqual(load.call_count,60)
        self.assertNotIn('\\',str(load.call_args.args[0]))


if __name__=='__main__':unittest.main()
