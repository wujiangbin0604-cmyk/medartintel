"""Prepare the original V6 ZIP with visible diagnostics and repeatable checks."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path, PurePosixPath
import shutil
import stat
import sys
import tempfile
import zipfile

V6_SHA256 = '56a3bee60380c06984a974ce6930913692dfc24665e73b2af407cfc1c5bf0362'
ARCHIVE_NAME = 'ECG-AI_Full_Server_V6_20261119.zip'


def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def relative_path(value):
    p = PurePosixPath(value)
    if not p.parts or p.is_absolute() or '..' in p.parts or '\\' in value or ':' in value:
        raise ValueError('Unsafe package path: ' + value)
    return p


def prepare(archive, target, expected=V6_SHA256, log=print):
    archive, target = Path(archive).absolute(), Path(target).absolute()
    log('[1/4] Checking ZIP: ' + str(archive))
    if not archive.is_file():
        raise ValueError('ZIP not found. Upload ' + ARCHIVE_NAME + ' to /tmp first.')
    if digest(archive) != expected:
        raise ValueError('ZIP SHA-256 mismatch. Re-upload the original complete ZIP; existing target was not changed.')
    log('[2/4] Checking ZIP CRC and file manifest')
    with zipfile.ZipFile(archive) as z:
        bad = z.testzip()
        if bad:
            raise ValueError('ZIP CRC failure: ' + bad)
        for info in z.infolist():
            p = relative_path(info.filename)
            if p.parts[0] != 'ecg-ai' or stat.S_ISLNK(info.external_attr >> 16):
                raise ValueError('Unexpected archive entry: ' + info.filename)
        manifest = json.loads(z.read('ecg-ai/DELIVERY_MANIFEST.json').decode('utf-8'))
        for row in manifest['files']:
            relative_path(row['path'])
        if target.exists():
            log('[3/4] Target already exists; checking it without overwriting: ' + str(target))
        else:
            parent = target.parent
            while not parent.exists():
                parent = parent.parent
            required = sum(i.file_size for i in z.infolist()) + 64 * 1024 * 1024
            if shutil.disk_usage(parent).free < required:
                raise ValueError('Insufficient free disk space for extraction; target was not created.')
            log('[3/4] Extracting to: ' + str(target))
            target.mkdir(parents=True)
            z.extractall(target)
    project = target / 'ecg-ai'
    log('[4/4] Verifying all ' + str(len(manifest['files'])) + ' payload files')
    problems = []
    for row in manifest['files']:
        path = project / row['path']
        try:
            path.resolve().relative_to(project.resolve())
        except ValueError:
            raise ValueError('File resolves outside the project: ' + row['path']) from None
        if not path.is_file() or digest(path) != row['sha256']:
            problems.append(row['path'])
    if problems:
        raise ValueError('Existing/extracted package is incomplete or changed (' + str(len(problems))
                         + ' files): ' + ', '.join(problems[:8])
                         + '. Use --target with a fresh directory; no existing file was overwritten.')
    log('PASS: complete package verified.')
    log('PROJECT=' + str(project))
    return project


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--archive', type=Path, default=Path('/tmp') / ARCHIVE_NAME)
    parser.add_argument('--target', type=Path, default=Path('/root/ecg-ai-v6-20261119'))
    parser.add_argument('--log', type=Path, default=Path(tempfile.gettempdir()) / 'ecg-v6-prepare.log')
    args = parser.parse_args(argv)
    try:
        stream = args.log.open('a', encoding='utf-8')
    except OSError as error:
        print('ERROR: cannot open log: ' + str(error), flush=True)
        return 1
    with stream:
        def log(message):
            stamp = datetime.now(timezone.utc).isoformat(timespec='seconds')
            line = stamp + ' ' + message
            print(line, flush=True)
            stream.write(line + '\n')
            stream.flush()
        log('START; log=' + str(args.log) + '; Python=' + sys.version.split()[0])
        try:
            prepare(args.archive, args.target, log=log)
        except Exception as error:
            log('ERROR: ' + type(error).__name__ + ': ' + str(error))
            return 1
        except KeyboardInterrupt:
            log('ERROR: interrupted; existing files retained.')
            return 130
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
