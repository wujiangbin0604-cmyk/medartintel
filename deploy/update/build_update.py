"""Build an update from the runtime manifest, including all deployment launchers."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import stat
import zipfile

ROOT = Path(__file__).resolve().parents[2]
RUNTIME_MANIFEST = "deploy/ubuntu22/bundle_manifest.json"
CODE_PREFIXES = ("deploy/", "web/backend/", "web/frontend/", "web/docs/site_reports/")


def payload(path: Path) -> bytes:
    data = path.read_bytes()
    return data.replace(b"\r\n", b"\n") if path.suffix == ".sh" else data


def build(output: Path) -> dict:
    runtime = json.loads((ROOT / RUNTIME_MANIFEST).read_text(encoding="utf-8"))
    paths = {entry["path"] for entry in runtime["files"]
             if "/" not in entry["path"] or entry["path"].startswith(CODE_PREFIXES)}
    paths.update({RUNTIME_MANIFEST, ".dockerignore", ".gitignore", ".gitattributes"})
    paths.update(p.relative_to(ROOT).as_posix() for p in (ROOT / "deploy/update").rglob("*")
                 if p.is_file() and "__pycache__" not in p.parts and p.suffix != ".pyc")
    data = {}
    for relative in sorted(paths):
        path = (ROOT / relative).resolve()
        if not path.is_relative_to(ROOT) or not path.is_file():
            raise RuntimeError("Missing update source: " + relative)
        if path.name == ".env" or "runtime" in path.relative_to(ROOT).parts:
            raise RuntimeError("Protected runtime data in update")
        data[relative] = payload(path)
    # Refuse to publish sources that disagree with the runtime integrity manifest.
    for entry in runtime["files"]:
        if entry["path"] in data and hashlib.sha256(data[entry["path"]]).hexdigest() != entry["sha256"]:
            raise RuntimeError("Regenerate bundle_manifest.json first: " + entry["path"])
    manifest = {"format": 1, "date": "2026-11-09", "files": [
        {"path": relative, "bytes": len(content), "sha256": hashlib.sha256(content).hexdigest()}
        for relative, content in data.items()]}
    contents = {"payload/" + name: content for name, content in data.items()}
    contents["update_manifest.json"] = json.dumps(manifest, ensure_ascii=False, indent=2).encode("utf-8")
    for source, name in (("apply_update.py", "apply_update.py"),
                         ("update-server.sh", "update-server.sh"), ("README.md", "UPDATE.md")):
        contents[name] = payload(ROOT / "deploy/update" / source)
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
        for name, content in sorted(contents.items()):
            info = zipfile.ZipInfo(name, (2026, 11, 9, 0, 0, 0))
            info.create_system = 3
            info.external_attr = (stat.S_IFREG | (0o755 if name.endswith(".sh") else 0o644)) << 16
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, content)
    with zipfile.ZipFile(output) as archive:
        assert archive.testzip() is None
    digest = hashlib.sha256(output.read_bytes()).hexdigest()
    output.with_suffix(output.suffix + ".sha256").write_text(digest + "  " + output.name + "\n", encoding="ascii")
    return {"archive": str(output), "files": len(data), "bytes": output.stat().st_size, "sha256": digest}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "releases/ECG-AI_Server_Update_20261109.zip")
    args = parser.parse_args()
    print(json.dumps(build(args.output.resolve()), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
