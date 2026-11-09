"""Verify and overlay a server update; keep environment and runtime data in place."""
from __future__ import annotations

import argparse
from datetime import datetime
import hashlib
import json
from pathlib import Path
import shutil


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("target", type=Path, help="Existing ECG-AI project directory")
    parser.add_argument("--package", type=Path, default=Path(__file__).resolve().parent)
    parser.add_argument("--check", action="store_true", help="Verify without copying files")
    args = parser.parse_args()
    target, package = args.target.resolve(), args.package.resolve()
    if not (target / "web/backend/production.py").is_file() or not (target / "deploy/ubuntu22/compose.yaml").is_file():
        parser.error("Target must be the existing ECG-AI project root")
    payload = (package / "payload").resolve()
    manifest = json.loads((package / "update_manifest.json").read_text(encoding="utf-8"))
    entries = manifest["files"]
    names = set()
    for entry in entries:
        relative = Path(entry["path"])
        if relative.is_absolute() or ".." in relative.parts or entry["path"] in names:
            raise RuntimeError("Invalid or duplicate update path")
        names.add(entry["path"])
        source, destination = (payload / relative).resolve(), (target / relative).resolve()
        if not source.is_relative_to(payload) or not destination.is_relative_to(target):
            raise RuntimeError("Update path escapes project")
        if relative.name == ".env" or "runtime" in relative.parts or relative.suffix in {".sqlite3", ".npz", ".dat", ".atr", ".hea", ".pt", ".joblib"}:
            raise RuntimeError("Update contains protected data")
        if not source.is_file() or hashlib.sha256(source.read_bytes()).hexdigest() != entry["sha256"]:
            raise RuntimeError("Payload checksum mismatch: " + entry["path"])
    # Check the complete resulting deployment before copying anything. An older
    # server may not have launchers that were introduced after its initial ZIP.
    runtime_manifest_name = "deploy/ubuntu22/bundle_manifest.json"
    runtime_manifest_path = (payload if runtime_manifest_name in names else target) / runtime_manifest_name
    runtime = json.loads(runtime_manifest_path.read_text(encoding="utf-8"))
    for entry in runtime["files"]:
        relative = Path(entry["path"])
        if relative.is_absolute() or ".." in relative.parts:
            raise RuntimeError("Invalid runtime artifact path")
        source_root = payload if entry["path"] in names else target
        source = (source_root / relative).resolve()
        if not source.is_relative_to(source_root) or not source.is_file():
            raise RuntimeError("Missing runtime artifact: " + entry["path"])
        if hashlib.sha256(source.read_bytes()).hexdigest() != entry["sha256"]:
            raise RuntimeError("Runtime checksum mismatch: " + entry["path"])
    if args.check:
        print(json.dumps({"verified_files": len(entries), "verified_runtime_files": len(runtime["files"]), "target": str(target)}, ensure_ascii=False))
        return
    backup = target.parent / ("." + target.name + "-update-backups") / datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    backup.mkdir(parents=True, exist_ok=False)
    created = []
    # Back up every file before starting the overlay.
    for entry in entries:
        relative = entry["path"]
        destination = target / relative
        if destination.exists():
            saved = backup / relative
            saved.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(destination, saved)
        else:
            created.append(relative)
    (backup / "update_backup.json").write_text(json.dumps({"target": str(target), "created_files": created, "files": list(names)}, ensure_ascii=False, indent=2), encoding="utf-8")
    for entry in entries:
        destination = target / entry["path"]
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(payload / entry["path"], destination)
    print(json.dumps({"updated_files": len(entries), "backup": str(backup), "target": str(target)}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
