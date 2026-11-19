"""Boot an exported/clean Git checkout without using ignored project artifacts."""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from urllib.request import urlopen


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("checkout",type=Path);p.add_argument("--port",type=int,default=8145);p.add_argument("--report",type=Path,required=True)
    a=p.parse_args();checkout=a.checkout.resolve();report=a.report.resolve();report.parent.mkdir(parents=True,exist_ok=True)
    forbidden=[checkout/".venv",checkout/"web/frontend/node_modules",checkout/"data/processed/mitdb44_nsvf_v1/train.npz",checkout/"research_extensions/rhythm_fusion/data/development.npz"]
    if any(path.exists() for path in forbidden):raise RuntimeError("Validation checkout contains ignored dependencies/data")
    env=dict(os.environ,PYTHONDONTWRITEBYTECODE="1",OMP_NUM_THREADS="2",MKL_NUM_THREADS="2",OPENBLAS_NUM_THREADS="2",MPLBACKEND="Agg",ECG_LOG_LEVEL="WARNING",ECG_HUNTER_DATABASE=str(checkout/"web/runtime/clone-validation.sqlite3"))
    env.pop("PYTHONPATH",None)
    check=subprocess.run([sys.executable,"-B","deploy/local.py","--check"],cwd=checkout,env=env,capture_output=True,text=True,encoding="utf-8")
    report.with_suffix(".check.txt").write_text(check.stdout+check.stderr,encoding="utf-8")
    if check.returncode:raise RuntimeError(check.stdout+check.stderr)
    # Resolve all project imports in a new interpreter with only this checkout at cwd.
    code="import pathlib,web.backend.app,research_extensions.rhythm_fusion.src.models; root=pathlib.Path.cwd(); assert pathlib.Path(web.backend.app.__file__).resolve().is_relative_to(root); assert pathlib.Path(research_extensions.rhythm_fusion.src.models.__file__).resolve().is_relative_to(root); print(root)"
    imports=subprocess.run([sys.executable,"-B","-c",code],cwd=checkout,env=env,capture_output=True,text=True,encoding="utf-8",check=True)
    log=report.with_suffix(".server.txt").open("w",encoding="utf-8")
    process=subprocess.Popen([sys.executable,"-B","deploy/local.py","--host","127.0.0.1","--port",str(a.port)],cwd=checkout,env=env,stdout=log,stderr=log)
    try:
        base=f"http://127.0.0.1:{a.port}"
        for _ in range(120):
            if process.poll() is not None:raise RuntimeError("Clean checkout server exited")
            try:
                with urlopen(base+"/api/health",timeout=1):break
            except OSError:time.sleep(.25)
        else:raise RuntimeError("Clean checkout did not start")
        test=subprocess.run([sys.executable,"-B","deploy/ubuntu22/verify_bundle.py","--api",base],cwd=checkout,env=env,capture_output=True,text=True,encoding="utf-8")
        report.with_suffix(".api.txt").write_text(test.stdout+test.stderr,encoding="utf-8")
        if test.returncode:raise RuntimeError(test.stdout+test.stderr)
        result=json.loads(test.stdout)
        result.update(checkout=str(checkout),project_import_root=imports.stdout.strip(),host_platform=sys.platform,
                      uses_ignored_training_npz=False,uses_source_worktree=False,dependency_environment="existing verified Python 3.12 environment; dependencies not reinstalled in checkout",
                      linux_container_executed=False)
        report.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding="utf-8")
        print(json.dumps(result,ensure_ascii=False,indent=2),flush=True)
    finally:
        process.terminate()
        try:process.wait(timeout=10)
        except subprocess.TimeoutExpired:process.kill();process.wait()
        log.close()


if __name__=="__main__":main()
