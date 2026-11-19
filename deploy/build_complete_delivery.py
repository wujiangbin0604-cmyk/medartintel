"""Build a new server ZIP plus the final V6 paper; never include local state."""
from __future__ import annotations
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import stat
import zipfile

ROOT = Path(__file__).resolve().parents[1]
NAME = 'ECG-AI_Full_Server_V6_20261119.zip'


def digest(data):
    return hashlib.sha256(data).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, required=True)
    args = parser.parse_args()
    dest = args.output_dir.resolve(); dest.mkdir(parents=True, exist_ok=True)
    output = dest / NAME
    if output.exists(): raise FileExistsError('Use a new output directory: ' + str(output))
    spec = importlib.util.spec_from_file_location('runtime_bundle', ROOT / 'deploy/ubuntu22/build_release.py')
    b = importlib.util.module_from_spec(spec); spec.loader.exec_module(b)
    files = list(b.selected_files())
    files.append(ROOT / 'deploy/ubuntu22/bundle_manifest.json')
    files.extend(p for p in (ROOT / 'deploy/update').rglob('*') if p.is_file() and '__pycache__' not in p.parts and p.suffix != '.pyc')
    files.extend(ROOT / p for p in [
        'deploy/validate_git_checkout.py', 'deploy/build_complete_delivery.py',
        'UPLOAD_SERVER_V6.md', 'paper/final/ECG_AI_课程论文_完整研究版V6.docx',
        'paper/final/ECG_AI_课程论文_完整研究版V6.pdf',
        'paper/qa/v6/final_quality_check.json', 'paper/qa/v6/integration_manifest.json'])
    files = sorted(set(files), key=lambda p:p.relative_to(ROOT).as_posix())
    assert all(p.is_file() and p.resolve().is_relative_to(ROOT) for p in files)
    entries = []
    with zipfile.ZipFile(output, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=6) as z:
        for path in files:
            rel = path.relative_to(ROOT).as_posix()
            assert path.name != '.env' and '.git' not in path.parts and 'node_modules' not in path.parts
            assert not path.suffix in {'.npz', '.sqlite', '.sqlite3', '.pyc'}
            data = b.payload(path)
            entries.append({'path':rel, 'bytes':len(data), 'sha256':digest(data)})
            info = zipfile.ZipInfo('ecg-ai/' + rel, (2026,11,19,0,0,0))
            info.create_system = 3
            info.external_attr = (stat.S_IFREG | (0o755 if path.suffix == '.sh' else 0o644)) << 16
            info.compress_type = zipfile.ZIP_DEFLATED
            z.writestr(info, data, compresslevel=6)
        manifest = {'date_Asia_Shanghai':'2026-11-19','release':'V6 complete paper and server',
                    'application_commit_base':'307d81c0b8776052b7a18dce8a767866eda468b8',
                    'archive_root':'ecg-ai','files':entries,
                    'records':48,'original_production_models':6,'research_models':60,
                    'requires_first_build_network':True,'includes_docker_image':False,
                    'excludes':['training NPZ','local virtualenv','node_modules','private .env','existing game database']}
        z.writestr('ecg-ai/DELIVERY_MANIFEST.json', json.dumps(manifest,ensure_ascii=False,indent=2).encode('utf-8'))
    with zipfile.ZipFile(output) as z:
        assert z.testzip() is None
        for row in entries:
            assert digest(z.read('ecg-ai/'+row['path'])) == row['sha256']
    archive_sha = digest(output.read_bytes())
    output.with_suffix('.zip.sha256').write_text(f'{archive_sha}  {output.name}\n',encoding='ascii')
    shutil.copy2(ROOT/'UPLOAD_SERVER_V6.md',dest/'UPLOAD_SERVER_V6.md')
    result = {'zip':str(output),'bytes':output.stat().st_size,'mib':round(output.stat().st_size/1024**2,2),
              'file_count':len(entries)+1,'sha256':archive_sha,'crc_and_all_payload_hashes_verified':True}
    (dest/'delivery_manifest.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(result,ensure_ascii=False,indent=2))


if __name__=='__main__':main()
