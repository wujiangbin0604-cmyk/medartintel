"""Run the shipped frontend, ECG data and saved models on a single origin."""
from __future__ import annotations

import argparse
import importlib.metadata
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def dependencies_ready() -> bool:
    # Persisted sklearn models require the original package version.
    required = {"scikit-learn": "1.9.1", "torch": "2.14.1"}
    try:
        for name in ("fastapi", "uvicorn", "wfdb", "numpy", "pandas", "scipy", "matplotlib", "joblib"):
            importlib.metadata.version(name)
        return all(importlib.metadata.version(name).split("+")[0] == version
                   for name, version in required.items())
    except importlib.metadata.PackageNotFoundError:
        return False


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--install", action="store_true", help="Install/repair pinned CPU runtime dependencies")
    parser.add_argument("--check", action="store_true", help="Verify artifacts and six models, then exit")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()
    if sys.version_info[:2] != (3, 12):
        parser.error("Python 3.12 is required by the shipped models; use Python 3.12 or Docker Compose.")
    if not 1 <= args.port <= 65535:
        parser.error("--port must be between 1 and 65535")
    os.chdir(ROOT)
    sys.path.insert(0, str(ROOT))
    for key, value in {"MPLBACKEND": "Agg", "MPLCONFIGDIR": str(ROOT / ".mplconfig"),
                       "OMP_NUM_THREADS": "2", "OPENBLAS_NUM_THREADS": "2", "MKL_NUM_THREADS": "2"}.items():
        os.environ.setdefault(key, value)
    if args.install or not dependencies_ready():
        print("Installing Python 3.12 runtime dependencies (first run requires internet).", flush=True)
        subprocess.run([sys.executable, "-m", "pip", "install", "--only-binary=:all:",
                        "-r", str(ROOT / "deploy/ubuntu22/requirements-runtime.txt")], check=True)
        subprocess.run([sys.executable, "-m", "pip", "install", "--no-deps", "--only-binary=:all:",
                        "--index-url", "https://download.pytorch.org/whl/cpu", "torch==2.14.1+cpu"], check=True)
        subprocess.run([sys.executable, "-m", "pip", "check"], check=True)
    from deploy.ubuntu22.verify_bundle import verify_files
    print(verify_files(), flush=True)
    if args.check:
        from web.backend.ecg_service import InferenceService
        status = InferenceService(ROOT).models.load_all()
        if not status["all_loaded"]:
            raise RuntimeError(f"Model load failure: {status}")
        print("Ready: all 6 models loaded; frontend and runtime artifacts verified.")
        return 0
    print(f"Open http://{'127.0.0.1' if args.host == '0.0.0.0' else args.host}:{args.port}/dashboard", flush=True)
    import uvicorn
    uvicorn.run("web.backend.production:app", host=args.host, port=args.port, workers=1)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
