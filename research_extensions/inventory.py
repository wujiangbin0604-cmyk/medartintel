"""Deliver a reviewable file inventory, excluding pre-existing user changes."""
import csv
import json
from pathlib import Path
import subprocess
from research_extensions.protect import ROOT, sha256


def main():
    root=ROOT/"research_extensions"
    files={p for p in root.rglob("*") if p.is_file() and "__pycache__" not in p.parts
           and p.name not in ["DELIVERED_FILES.csv","baseline_generated_appData.json"] and ".sqlite3" not in p.name}
    previous=root/"DELIVERED_FILES.csv"
    if previous.is_file():
        with previous.open(encoding="utf-8-sig",newline="") as source:
            for row in csv.DictReader(source):
                path=(ROOT/row["path"]).resolve()
                if path.is_relative_to(ROOT.resolve()) and path.is_file() and path!=previous:
                    files.add(path)
    for args in [["git","diff","--name-only","-z"],["git","diff","--cached","--name-only","-z"],
                 ["git","ls-files","--others","--exclude-standard","-z","web","deploy"]]:
        for name in subprocess.check_output(args,cwd=ROOT).decode("utf-8").split("\0"):
            path=ROOT/name
            if (name.startswith(("web/","deploy/")) or name in ["README.md","SERVER_UPDATE.md","DEPLOY_LOCAL.md","DEPLOY_UBUNTU22.md",".dockerignore"]) and name!="web/frontend/src/.umi-production/appData.json" and path.is_file():files.add(path)
    with (root/"DELIVERED_FILES.csv").open("w",encoding="utf-8-sig",newline="") as f:
        writer=csv.DictWriter(f,fieldnames=["path","bytes","sha256"]);writer.writeheader()
        for path in sorted(files):writer.writerow({"path":path.relative_to(ROOT).as_posix(),"bytes":path.stat().st_size,"sha256":sha256(path)})
    print(f"Indexed {len(files)} delivered files; large generated data is local and gitignored")


if __name__=="__main__":main()
