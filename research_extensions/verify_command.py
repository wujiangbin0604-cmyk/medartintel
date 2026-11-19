"""Execute a check and persist exact command, output and exit status."""
import argparse
from datetime import datetime
import json
from pathlib import Path
import subprocess
import time

ROOT=Path(__file__).resolve().parents[1]


def main():
    p=argparse.ArgumentParser();p.add_argument("--name",required=True);p.add_argument("--cwd",default=str(ROOT));p.add_argument("command",nargs=argparse.REMAINDER)
    a=p.parse_args();command=a.command[1:] if a.command[:1]==["--"] else a.command
    target=ROOT/"research_extensions/validation";target.mkdir(exist_ok=True)
    start=time.perf_counter()
    with (target/f"{a.name}.txt").open("w",encoding="utf-8") as f:
        result=subprocess.run(command,cwd=a.cwd,stdout=f,stderr=subprocess.STDOUT)
    record={"command":command,"cwd":a.cwd,"exit_code":result.returncode,"elapsed_seconds":time.perf_counter()-start,
            "finished":datetime.now().astimezone().isoformat(),"output":f"{a.name}.txt"}
    (target/f"{a.name}.json").write_text(json.dumps(record,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps(record,ensure_ascii=False),flush=True)
    raise SystemExit(result.returncode)


if __name__=="__main__":main()
