"""Version-pinned official downloads, verified before raw file creation.

Existing raw files are only read and hashed, never replaced or edited.
"""
import hashlib
from http.client import IncompleteRead
import re
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

BASE_URL = "https://physionet.org/files/mitdb/1.0.0/"
S3_URL = "https://physionet-open.s3.amazonaws.com/mitdb/1.0.0/"


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def fetch_bytes(name, base_url=BASE_URL):
    url = base_url + name
    for attempt in range(5):
        try:
            request = urllib.request.Request(url, headers={"User-Agent": "MITBIH-Exploration/1.0"})
            with urllib.request.urlopen(request, timeout=60) as response:
                return response.read()
        except (OSError, TimeoutError, IncompleteRead):
            if attempt == 4:
                raise
            time.sleep(attempt + 1)


def ensure_file(directory, name, expected=None, offline=False, base_url=BASE_URL):
    target = directory / name
    if not target.exists():
        if offline:
            raise FileNotFoundError(f"Offline mode: missing {target}")
        payload = fetch_bytes(name, base_url)
        if expected and hashlib.sha256(payload).hexdigest() != expected:
            raise ValueError(f"Official SHA256 mismatch: {name}; no raw file created")
        temporary = target.with_name(target.name + ".part")
        temporary.write_bytes(payload)
        # A concurrently created raw file must not be replaced.
        try:
            try:
                with target.open("xb") as stream:
                    stream.write(temporary.read_bytes())
            except FileExistsError:
                # A concurrent verified downloader won; hash-check its file below.
                pass
        finally:
            temporary.unlink(missing_ok=True)
    actual = sha256(target)
    if expected and actual != expected:
        raise ValueError(f"Existing raw file has wrong SHA256: {target}; left untouched")
    return {"file": name, "url": BASE_URL + name, "download_endpoint": base_url + name, "bytes": target.stat().st_size,
            "sha256": actual, "official_sha256": expected or "", "verified": bool(expected)}


def prepare_data(directory, requested, offline=False, workers=1, mirror="physionet"):
    directory.mkdir(parents=True, exist_ok=True)
    manifest = [ensure_file(directory, "SHA256SUMS.txt", offline=offline)]
    expected = {}
    for line in (directory / "SHA256SUMS.txt").read_text(encoding="utf-8").splitlines():
        parts = line.split(maxsplit=1)
        if len(parts) == 2:
            expected[parts[1].lstrip("*").removeprefix("./")] = parts[0]
    manifest.append(ensure_file(directory, "RECORDS", expected.get("RECORDS"), offline))
    available = (directory / "RECORDS").read_text(encoding="utf-8").split()
    records = available if requested == ["all"] else list(dict.fromkeys(requested))
    if not records or any(not re.fullmatch(r"\d{3}", r) or r not in available for r in records):
        raise ValueError(f"Select records from the official RECORDS list: {available}")
    jobs = [f"{record}.{extension}" for record in records for extension in ("dat", "hea", "atr")]
    if mirror not in ("physionet", "s3"):
        raise ValueError("Use official physionet or s3 mirror")
    endpoint = BASE_URL if mirror == "physionet" else S3_URL
    def acquire(name):
        if name not in expected:
            raise ValueError(f"No official SHA256 entry for {name}")
        result = ensure_file(directory, name, expected[name], offline, endpoint)
        print(f"Verified {name} ({result['bytes']} bytes)", flush=True)
        return result
    if workers == 1:
        manifest.extend(acquire(name) for name in jobs)
    else:
        if not 1 <= workers <= 8:
            raise ValueError("Download workers must be in [1, 8]")
        with ThreadPoolExecutor(max_workers=workers) as pool:
            manifest.extend(pool.map(acquire, jobs))
    return records, manifest


if __name__ == '__main__':
    import argparse
    parser=argparse.ArgumentParser(description='Download and SHA256-verify official MIT-BIH files')
    parser.add_argument('--records',nargs='+',default=['all'])
    parser.add_argument('--workers',type=int,default=4)
    parser.add_argument('--mirror',choices=['physionet','s3'],default='s3')
    parser.add_argument('--offline',action='store_true')
    options=parser.parse_args()
    root=Path(__file__).resolve().parents[1]
    names,files=prepare_data(root/'data/mitdb',options.records,options.offline,options.workers,options.mirror)
    print(f'Verified {len(names)} records and {len(files)} files',flush=True)
