"""Repair the original V6 Linux path readers; models and results stay unchanged."""
import argparse
import base64
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import subprocess
import sys
from uuid import uuid4

PATCH_DATA = None  # Replaced with verified source payloads by the release builder.


def sha(data):
    return hashlib.sha256(data).hexdigest()


def json_bytes(value):
    return (json.dumps(value,ensure_ascii=False,indent=2)+'\n').encode('utf-8')


def choose_project():
    if (Path.cwd()/'research_extensions/rhythm_fusion/results/cv_cpu_v1/model_registry.json').is_file():
        return Path.cwd()
    candidates=[p for p in Path('/root').glob('ecg-ai-v6-*/ecg-ai')
                if (p/'deploy/ubuntu22/verify_bundle.py').is_file()]
    if not candidates:
        raise ValueError('No V6 project found. Run with --project /path/to/ecg-ai')
    return max(candidates,key=lambda p:p.parent.stat().st_ctime_ns)


def apply(project, payload):
    project=Path(project).resolve()
    print('PROJECT='+str(project),flush=True)
    runtime_path=project/'deploy/ubuntu22/bundle_manifest.json'
    runtime=json.loads(runtime_path.read_text(encoding='utf-8'))
    registry=json.loads((project/'research_extensions/rhythm_fusion/results/cv_cpu_v1/model_registry.json').read_text(encoding='utf-8'))
    if len(registry['models'])!=60:
        raise ValueError('Expected the complete V6 registry with 60 models')
    # Check the actual model files using portable separators before changing code.
    for entry in registry['models']:
        relative=PurePosixPath(entry['checkpoint'].replace('\\','/'))
        if relative.is_absolute() or '..' in relative.parts or ':' in entry['checkpoint']:
            raise ValueError('Unsafe registry path')
        base=(project/'research_extensions/rhythm_fusion').resolve()
        path=base.joinpath(*relative.parts).resolve()
        if not path.is_relative_to(base) or not path.is_file() or sha(path.read_bytes())!=entry['sha256']:
            raise ValueError('Model missing/changed: '+entry['checkpoint'])
    print('CHECKPOINTS_OK=60 (existing SHA-256 values unchanged)',flush=True)
    changes={}
    for name,item in payload.items():
        path=(project/name).resolve()
        if not path.is_relative_to(project):raise ValueError('Unsafe patch path')
        data=base64.b64decode(item['base64'],validate=True)
        if sha(data)!=item['sha256']:raise ValueError('Invalid patch payload')
        if path.exists():
            old=sha(path.read_bytes())
            if old not in (item['sha256'],item['original_sha256']):
                raise ValueError('Locally changed file, refusing overwrite: '+name)
            if old==item['sha256']:continue
        elif item['original_sha256'] is not None:
            raise ValueError('Required original file is missing: '+name)
        changes[name]=data
    delivery_path=project/'DELIVERY_MANIFEST.json'
    delivery=json.loads(delivery_path.read_text(encoding='utf-8')) if delivery_path.is_file() else None
    def update_entries(manifest, data_by_path):
        rows={row['path']:row for row in manifest['files']}
        for name,data in data_by_path.items():
            if name not in rows:
                row={'path':name};manifest['files'].append(row);rows[name]=row
            rows[name].update(bytes=len(data),sha256=sha(data))
    all_payload={name:base64.b64decode(item['base64']) for name,item in payload.items()}
    update_entries(runtime,all_payload)
    runtime_data=json_bytes(runtime)
    if runtime_path.read_bytes()!=runtime_data:changes['deploy/ubuntu22/bundle_manifest.json']=runtime_data
    if delivery is not None:
        update_entries(delivery,{**all_payload,'deploy/ubuntu22/bundle_manifest.json':runtime_data})
        delivery_data=json_bytes(delivery)
        if delivery_path.read_bytes()!=delivery_data:changes['DELIVERY_MANIFEST.json']=delivery_data
    if not changes:
        print('PATCH_ALREADY_APPLIED',flush=True)
        return {'changed_files':0,'checkpoints':60,'project':str(project)}
    backup=project.parent/('ecg-linux-path-backup-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'-'+uuid4().hex[:6])
    backup.mkdir()
    for name in changes:
        source=project/name
        if source.is_file():
            target=backup/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(source,target)
    for name,data in changes.items():
        target=project/name;target.parent.mkdir(parents=True,exist_ok=True)
        temporary=target.with_name(target.name+'.pathfix-'+uuid4().hex+'.tmp')
        temporary.write_bytes(data);os.replace(temporary,target)
    for name,data in changes.items():
        if sha((project/name).read_bytes())!=sha(data):raise RuntimeError('Post-write verification failed: '+name)
    print('BACKUP='+str(backup),flush=True)
    print('PATCH_OK; changed_files='+str(len(changes)),flush=True)
    return {'changed_files':len(changes),'checkpoints':60,'project':str(project),'backup':str(backup)}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project',type=Path)
    parser.add_argument('--rebuild',action='store_true',help='Rebuild and validate the repaired Docker deployment')
    args=parser.parse_args()
    if PATCH_DATA is None:raise ValueError('Use the generated ecg_v6_linux_fix.py delivery file')
    project=args.project if args.project else choose_project()
    apply(project,PATCH_DATA)
    if args.rebuild:
        subprocess.run(['bash','deploy/ubuntu22/deploy.sh'],cwd=project,check=True)


if __name__=='__main__':
    try:main()
    except Exception as error:
        print('ERROR: '+type(error).__name__+': '+str(error),file=sys.stderr,flush=True)
        raise SystemExit(1)
