"""Extract and boot only the ZIP payload; uses current Python, not a claimed Linux test."""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
import time
import zipfile
from pathlib import Path
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[2]


def main():
    parser = argparse.ArgumentParser(); parser.add_argument("archive", type=Path); args = parser.parse_args()
    target_parent = ROOT / ".test_tmp"; target_parent.mkdir(exist_ok=True)
    target = Path(tempfile.mkdtemp(prefix="ubuntu22_bundle_", dir=target_parent))
    with zipfile.ZipFile(args.archive) as archive:
        assert archive.testzip() is None
        for name in archive.namelist():
            assert not name.startswith("/") and ".." not in Path(name).parts and "\\" not in name
        archive.extractall(target)
    package = target / "ecg-ai"
    env = dict(os.environ, ECG_HUNTER_DATABASE=str(package / "web/runtime/check.sqlite3"), ECG_LOG_LEVEL="WARNING", MPLBACKEND="Agg", PYTHONDONTWRITEBYTECODE="1")
    log = (target / "server.log").open("w", encoding="utf-8")
    process = subprocess.Popen([sys.executable, "-m", "uvicorn", "web.backend.production:app", "--host", "127.0.0.1", "--port", "8139", "--log-level", "warning"], cwd=package, env=env, stdout=log, stderr=log)
    try:
        for _ in range(120):
            if process.poll() is not None: raise RuntimeError((target / "server.log").read_text(encoding="utf-8"))
            try:
                with urlopen("http://127.0.0.1:8139/api/health", timeout=1): break
            except OSError: time.sleep(.25)
        else: raise RuntimeError("Extracted service did not start")
        result = subprocess.run([sys.executable, "deploy/ubuntu22/verify_bundle.py", "--api", "http://127.0.0.1:8139"], cwd=package, env=env, capture_output=True, text=True, encoding="utf-8")
        print(result.stdout)
        if result.returncode: raise RuntimeError(result.stderr)
        report = json.loads(result.stdout)
        report.update({"archive": str(args.archive), "extracted_to": str(package), "host_platform": sys.platform,
                       "linux_container_executed": False, "zip_crc_checked": True})
        (ROOT / "releases/package_validation.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    finally:
        process.terminate()
        try: process.wait(timeout=10)
        except subprocess.TimeoutExpired: process.kill(); process.wait()
        log.close()


if __name__ == "__main__": main()
