"""Build a portable UTF-8 ZIP with a strict include list and artifact hashes."""
from __future__ import annotations

import hashlib
import json
import stat
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUTPUT = ROOT / "releases/ECG-AI_Ubuntu22_amd64.zip"


def selected_files():
    files = set()
    def tree(folder):
        for path in (ROOT / folder).rglob("*"):
            if path.is_file() and not set(path.parts) & {"__pycache__", "node_modules", ".umi", ".umi-production"} and path.suffix != ".pyc":
                files.add(path)
    for folder in ("src", "configs", "checkpoints", "results", "reports", "figures", "data/mitdb", "tests", "web/backend", "web/frontend/src", "web/frontend/public", "web/frontend/dist", "web/frontend/scripts", "web/frontend/tests", "web/docs/games", "web/docs/screenshots/heartbeat_hunter", "web/docs/screenshots/welcome_onboarding", "deploy/ubuntu22"):
        tree(folder)
    for dataset in ("mitdb44_nv_v1", "mitdb44_nsvf_v1"):
        for path in (ROOT / "data/processed" / dataset).iterdir():
            if path.is_file() and path.suffix in {".json", ".csv"} and path.name != "metadata.csv":
                files.add(path)
    for name in ("README.md", "DEPLOY_LOCAL.md", "DEPLOY_UBUNTU22.md", "compose.yaml", ".env.example", "start-local.ps1", "start-local.sh", "deploy/local.py", "requirements.txt", "requirements-lock.txt", ".dockerignore", "web/__init__.py", "web/docs/welcome_onboarding.md"):
        files.add(ROOT / name)
    for pattern in ("*.json", "*.ts", ".umirc.ts"):
        files.update((ROOT / "web/frontend").glob(pattern))
    excluded = {"bundle_manifest.json", "package_validation.json", ".env"}
    return sorted((p for p in files if p.name not in excluded), key=lambda p: p.relative_to(ROOT).as_posix())


def payload(path):
    data = path.read_bytes()
    if path.suffix == ".sh":
        data = data.replace(b"\r\n", b"\n")
    return data


def main():
    files = selected_files()
    assert all(p.is_file() and p.resolve().is_relative_to(ROOT) for p in files)
    paths = [p.relative_to(ROOT).as_posix() for p in files]
    assert len(paths) == len({p.casefold() for p in paths}), "Case-colliding paths"
    assert "web/frontend/dist/index.html" in paths and "deploy/ubuntu22/reference_predictions.json" in paths
    assert not any(".venv" in p.split("/") or "runtime" in p.split("/") or p.endswith(".npz") for p in paths)
    entries = [{"path": p.relative_to(ROOT).as_posix(), "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}
               for p in files if p.name != ".dockerignore" for data in [payload(p)]]
    levels = json.loads((ROOT / "web/backend/game_data/heartbeat_levels.json").read_text(encoding="utf-8"))
    manifest = {"format": 1, "target": "Ubuntu 22.04 amd64 host / Docker CPU", "python": "3.12", "record_count": len(list((ROOT / "data/mitdb").glob("*.hea"))),
                "game_levels": len(levels["levels"]), "files": entries,
                "excluded": ["Windows virtualenv", "node_modules", "training NPZ arrays", "large training metadata.csv", "existing SQLite sessions", "old screenshots and caches"]}
    manifest_path = ROOT / "deploy/ubuntu22/bundle_manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(OUTPUT, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6, allowZip64=True) as archive:
        for path in files + [manifest_path]:
            relative = path.relative_to(ROOT).as_posix()
            info = zipfile.ZipInfo("ecg-ai/" + relative, (2026, 11, 4, 0, 0, 0))
            info.create_system = 3
            info.external_attr = (stat.S_IFREG | (0o755 if path.suffix == ".sh" else 0o644)) << 16
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, payload(path))
    with zipfile.ZipFile(OUTPUT) as archive:
        bad = archive.testzip()
        assert bad is None, bad
    digest = hashlib.sha256(OUTPUT.read_bytes()).hexdigest()
    OUTPUT.with_suffix(".zip.sha256").write_text(f"{digest}  {OUTPUT.name}\n", encoding="ascii")
    print(json.dumps({"zip": str(OUTPUT), "zip_bytes": OUTPUT.stat().st_size, "files": len(files)+1,
                      "uncompressed_bytes": sum(e["bytes"] for e in entries), "sha256": digest}, ensure_ascii=False, indent=2))


if __name__ == "__main__": main()
