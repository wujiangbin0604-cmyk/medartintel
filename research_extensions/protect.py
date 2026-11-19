"""Snapshot and verify original artifacts without rewriting them."""
from pathlib import Path
import argparse
import hashlib
import json
import subprocess
from datetime import datetime

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "research_extensions/protection_manifest.json"


def sha256(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=["snapshot", "verify"])
    args = parser.parse_args()
    if args.action == "snapshot":
        if MANIFEST.exists():
            raise FileExistsError("Protection snapshot is immutable")
        paths = []
        for directory in ["checkpoints", "configs", "data/mitdb", "data/processed", "results", "reports", "paper"]:
            paths += [p for p in (ROOT / directory).rglob("*") if p.is_file() and "__pycache__" not in p.parts]
        value = {"created_at": datetime.now().astimezone().isoformat(),
                 "git_status_before": subprocess.check_output(["git", "status", "--short"], cwd=ROOT, text=True),
                 "git_head": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
                 "files": {p.relative_to(ROOT).as_posix(): sha256(p) for p in sorted(paths)}}
        MANIFEST.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"Protected {len(paths)} files")
    else:
        value = json.loads(MANIFEST.read_text(encoding="utf-8"))
        changed = [p for p, digest in value["files"].items() if not (ROOT / p).is_file() or sha256(ROOT / p) != digest]
        report = {"checked_files": len(value["files"]), "changed": changed, "passed": not changed}
        (MANIFEST.parent / "protection_verification.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(json.dumps(report))
        if changed:
            raise SystemExit(1)


if __name__ == "__main__":
    main()
