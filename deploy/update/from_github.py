"""Update a Git clone or old ZIP deployment from an immutable GitHub snapshot.

Only runtime code, frontend and new research artifacts are overlaid. Existing
raw ECG, original formal models, environment and game volume remain in place.
Uses only the Python standard library (host Python 3.10 is sufficient).
"""
from __future__ import annotations

import argparse
import hashlib
from http.client import IncompleteRead
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
from urllib.request import Request, urlopen
import zipfile

REPOSITORY = "wujiangbin0604-cmyk/medartintel"


def download(url, destination):
    request = Request(url, headers={"User-Agent": "ECG-AI-updater", "Accept": "application/vnd.github+json"})
    for attempt in range(1, 4):
        try:
            with urlopen(request, timeout=180) as response, destination.open("wb") as output:
                shutil.copyfileobj(response, output)
            return
        except (OSError, EOFError, IncompleteRead):
            if attempt == 3:
                raise
            print(f"GitHub download interrupted; retry {attempt}/2", flush=True)
            time.sleep(attempt * 2)


def extract_snapshot(archive_path, destination):
    with zipfile.ZipFile(archive_path) as archive:
        for info in archive.infolist():
            path = (destination / info.filename).resolve()
            if not path.is_relative_to(destination.resolve()):
                raise ValueError("Archive path escapes temporary directory")
        archive.extractall(destination)
    roots = [p for p in destination.iterdir() if p.is_dir()]
    if len(roots) != 1:
        raise ValueError("Expected one GitHub snapshot root")
    return roots[0]


def make_package(snapshot, package, target=None):
    package.mkdir(parents=True, exist_ok=True)
    runtime = json.loads((snapshot / "deploy/ubuntu22/bundle_manifest.json").read_text(encoding="utf-8"))
    # Include the complete runtime closure, including src/, reports and figures
    # absent from some older ZIP deployments. Immutable original data/models
    # must already match; they are never overwritten by an update.
    paths = {e["path"] for e in runtime["files"]}
    paths.update({"deploy/ubuntu22/bundle_manifest.json", ".dockerignore", ".gitignore", ".gitattributes"})
    paths.update(p.relative_to(snapshot).as_posix() for p in (snapshot / "deploy/update").rglob("*") if p.is_file() and "__pycache__" not in p.parts)
    entries = []
    for name in sorted(paths):
        source = (snapshot / name).resolve()
        if not source.is_relative_to(snapshot.resolve()) or not source.is_file():
            raise ValueError("Missing or invalid snapshot artifact: " + name)
        content = source.read_bytes()
        # GitHub preserves blob bytes; normalize only the shell scripts' checkout convention.
        if source.suffix == ".sh":
            content = content.replace(b"\r\n", b"\n")
        if target is not None:
            destination = target / name
            if destination.is_file() and hashlib.sha256(destination.read_bytes()).digest() == hashlib.sha256(content).digest():
                continue
            research = source.suffix == ".pt" and name.startswith("research_extensions/rhythm_fusion/results/") and source.name == "best.pt"
            if source.suffix in {".dat", ".hea", ".atr", ".pt", ".joblib"} and not research:
                raise ValueError("Original model/ECG missing or changed; update stopped without overwriting it: " + name)
        path = package / "payload" / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        entries.append({"path": name, "sha256": hashlib.sha256(content).hexdigest(), "bytes": len(content)})
    (package / "update_manifest.json").write_text(json.dumps({"format": 1, "files": entries}, indent=2), encoding="utf-8")
    return len(entries)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("target", type=Path, help="Existing project root, e.g. /root/ecg-ai")
    parser.add_argument("--ref", default="main", help="GitHub branch or commit; resolved to a commit before downloading")
    parser.add_argument("--check", action="store_true", help="Download and validate without changing project files")
    args = parser.parse_args()
    target = args.target.resolve()
    if not (target / "web/backend/production.py").is_file() or not (target / "deploy/ubuntu22/compose.yaml").is_file():
        parser.error("Target must be the existing ECG-AI project root")
    # No credentials are needed for this public repository.
    request = Request(f"https://api.github.com/repos/{REPOSITORY}/commits/{args.ref}", headers={"User-Agent": "ECG-AI-updater"})
    with urlopen(request, timeout=30) as response:
        commit = json.load(response)["sha"]
    with tempfile.TemporaryDirectory(prefix="ecg-ai-github-update-") as temp:
        temporary = Path(temp)
        archive = temporary / "source.zip"
        download(f"https://codeload.github.com/{REPOSITORY}/zip/{commit}", archive)
        extracted = temporary / "source"
        extracted.mkdir()
        snapshot = extract_snapshot(archive, extracted)
        package = temporary / "package"
        count = make_package(snapshot, package, target)
        command = [sys.executable, str(snapshot / "deploy/update/apply_update.py"), str(target), "--package", str(package)]
        subprocess.run(command + ["--check"], check=True)
        if not args.check:
            subprocess.run(command, check=True)
        print(json.dumps({"commit": commit, "files": count, "check_only": args.check, "target": str(target)}), flush=True)
    if not args.check:
        print("Files updated and backed up. Next: sudo bash deploy/ubuntu22/deploy.sh", flush=True)


if __name__ == "__main__":
    main()
