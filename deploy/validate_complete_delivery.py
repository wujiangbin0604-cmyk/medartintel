"""Verify and boot a newly extracted complete delivery, independent of source files."""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import subprocess
import sys
import tempfile
import zipfile

ROOT=Path(__file__).resolve().parents[1]


def main():
    p=argparse.ArgumentParser();p.add_argument('archive',type=Path);p.add_argument('--report',type=Path,required=True)
    a=p.parse_args();archive=a.archive.resolve();report=a.report.resolve();report.parent.mkdir(parents=True,exist_ok=True)
    expected=archive.with_suffix('.zip.sha256').read_text(encoding='ascii').split()[0]
    actual=hashlib.sha256(archive.read_bytes()).hexdigest();assert actual==expected
    dest=Path(tempfile.mkdtemp(prefix='ecg-v6-complete-'))
    with zipfile.ZipFile(archive) as z:
        assert z.testzip() is None
        for name in z.namelist():
            q=PurePosixPath(name)
            assert not q.is_absolute() and '..' not in q.parts and '\\' not in name and q.parts[0]=='ecg-ai'
        z.extractall(dest)
    checkout=dest/'ecg-ai'
    manifest=json.loads((checkout/'DELIVERY_MANIFEST.json').read_text(encoding='utf-8'))
    for row in manifest['files']:
        target=checkout/row['path']
        assert target.resolve().is_relative_to(checkout)
        assert hashlib.sha256(target.read_bytes()).hexdigest()==row['sha256'],row['path']
    run=subprocess.run([sys.executable,'-B',str(ROOT/'deploy/validate_git_checkout.py'),str(checkout),
                        '--port','8148','--report',str(report)],cwd=ROOT,encoding='utf-8',capture_output=True,text=True)
    report.with_suffix('.full_log.txt').write_text(run.stdout+run.stderr,encoding='utf-8')
    if run.returncode:raise RuntimeError(run.stdout+run.stderr)
    result=json.loads(report.read_text(encoding='utf-8'))
    result.update(archive=str(archive),archive_sha256=actual,zip_crc_checked=True,
                  delivery_payload_hashes_verified=len(manifest['files']),zip_payload_only=True)
    report.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(result,ensure_ascii=False,indent=2))


if __name__=='__main__':main()
