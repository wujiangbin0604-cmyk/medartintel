"""Repackage the original V6 payload with the verified Linux path repair."""
import argparse
import copy
import hashlib
import json
from pathlib import Path
import stat
import sys
import zipfile

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
PATCH_FILES=['research_extensions/rhythm_fusion/src/artifact_paths.py',
             'research_extensions/rhythm_fusion/src/analyze.py','research_extensions/uncertainty/src/evaluate.py',
             'deploy/ubuntu22/verify_bundle.py','web/backend/rhythm_lab.py','deploy/ubuntu22/bundle_manifest.json']


def main():
    p=argparse.ArgumentParser();p.add_argument('original',type=Path);p.add_argument('--patched-project',type=Path,required=True)
    p.add_argument('--fix-script',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    if a.output.exists():raise FileExistsError(a.output)
    digest=lambda data:hashlib.sha256(data).hexdigest()
    if digest(a.original.read_bytes())!='56a3bee60380c06984a974ce6930913692dfc24665e73b2af407cfc1c5bf0362':raise ValueError('Wrong original V6 ZIP')
    overrides={name:(a.patched_project/name).read_bytes() for name in PATCH_FILES}
    overrides['UPLOAD_SERVER_V6.md']=(ROOT/'SERVER_LINUX_FIX.md').read_bytes().replace(b'\r\n',b'\n')
    overrides['ecg_v6_linux_fix.py']=a.fix_script.read_bytes()
    with zipfile.ZipFile(a.original) as original:
        manifest=json.loads(original.read('ecg-ai/DELIVERY_MANIFEST.json'))
        rows={row['path']:row for row in manifest['files']}
        for name,data in overrides.items():
            if name not in rows:
                rows[name]={'path':name};manifest['files'].append(rows[name])
            rows[name].update(bytes=len(data),sha256=digest(data))
        manifest.update(date_Asia_Shanghai='2026-11-21',release='V6 complete paper and server, Linux path repair',
                        linux_path_fix='Readers normalize legacy Windows separators; new registries use POSIX paths')
        overrides['DELIVERY_MANIFEST.json']=(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n').encode('utf-8')
        original_names={info.filename.removeprefix('ecg-ai/') for info in original.infolist()}
        a.output.parent.mkdir(parents=True,exist_ok=True)
        with zipfile.ZipFile(a.output,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as target:
            for info in original.infolist():
                name=info.filename.removeprefix('ecg-ai/')
                target.writestr(copy.copy(info),overrides[name] if name in overrides else original.read(info.filename),compresslevel=6)
            for name in sorted(set(overrides)-original_names):
                info=zipfile.ZipInfo('ecg-ai/'+name,(2026,11,21,0,0,0));info.create_system=3
                info.external_attr=(stat.S_IFREG|0o644)<<16;info.compress_type=zipfile.ZIP_DEFLATED
                target.writestr(info,overrides[name],compresslevel=6)
    with zipfile.ZipFile(a.output) as target:
        assert target.testzip() is None
        for row in manifest['files']:assert digest(target.read('ecg-ai/'+row['path']))==row['sha256'],row['path']
        registry=json.loads(target.read('ecg-ai/research_extensions/rhythm_fusion/results/cv_cpu_v1/model_registry.json'))
        from research_extensions.rhythm_fusion.src.artifact_paths import relative_artifact_path
        for entry in registry['models']:
            name='ecg-ai/research_extensions/rhythm_fusion/'+relative_artifact_path(entry['checkpoint']).as_posix()
            assert digest(target.read(name))==entry['sha256']
    value=digest(a.output.read_bytes())
    a.output.with_suffix('.zip.sha256').write_text(value+'  '+a.output.name+'\n',encoding='ascii')
    result={'archive':str(a.output),'bytes':a.output.stat().st_size,'sha256':value,
            'payload_files':len(manifest['files']),'verified_registry_models':len(registry['models']),
            'original_models_and_paper_unchanged':True,'zip_crc_and_payload_hashes':'PASS'}
    a.output.with_suffix('.validation.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(result,ensure_ascii=False,indent=2))


if __name__=='__main__':main()
