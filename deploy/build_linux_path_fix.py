"""Create a tiny self-contained repair for existing original V6 deployments."""
import argparse
import base64
import hashlib
import json
from pathlib import Path
import zipfile

ROOT=Path(__file__).resolve().parents[1]
FILES=['research_extensions/rhythm_fusion/src/artifact_paths.py',
       'research_extensions/rhythm_fusion/src/analyze.py',
       'research_extensions/uncertainty/src/evaluate.py',
       'deploy/ubuntu22/verify_bundle.py','web/backend/rhythm_lab.py']


def main():
    p=argparse.ArgumentParser();p.add_argument('original_zip',type=Path);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    original=a.original_zip.read_bytes()
    if hashlib.sha256(original).hexdigest()!='56a3bee60380c06984a974ce6930913692dfc24665e73b2af407cfc1c5bf0362':
        raise ValueError('Expected original V6 ZIP')
    payload={}
    with zipfile.ZipFile(a.original_zip) as z:
        for name in FILES:
            data=(ROOT/name).read_bytes().replace(b'\r\n',b'\n')
            old=z.read('ecg-ai/'+name) if 'ecg-ai/'+name in z.namelist() else None
            payload[name]={'base64':base64.b64encode(data).decode('ascii'),
                           'sha256':hashlib.sha256(data).hexdigest(),
                           'original_sha256':hashlib.sha256(old).hexdigest() if old is not None else None}
    template=(ROOT/'deploy/update/linux_path_fix_template.py').read_text(encoding='utf-8')
    marker='PATCH_DATA = None  # Replaced with verified source payloads by the release builder.'
    assert template.count(marker)==1
    template=template.replace(marker,'PATCH_DATA = '+repr(payload))
    a.output.parent.mkdir(parents=True,exist_ok=True)
    a.output.write_text(template,encoding='utf-8',newline='\n')
    compile(template,str(a.output),'exec')
    print(json.dumps({'output':str(a.output),'bytes':a.output.stat().st_size,'payload_files':len(payload),
                      'sha256':hashlib.sha256(a.output.read_bytes()).hexdigest()}))


if __name__=='__main__':main()
