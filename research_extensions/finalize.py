"""Finalize the current task after the already-running repeated-seed budget ends."""
from pathlib import Path
import json
import shutil
import subprocess
import sys
import time
from research_extensions.rhythm_fusion.src.data import BASE, ROOT


def check(name, command, cwd=ROOT):
    wrapper=[sys.executable,"-B",str(ROOT/"research_extensions/verify_command.py"),"--name",name,"--cwd",str(cwd),"--",*command]
    subprocess.run(wrapper,cwd=ROOT,check=True)


def main():
    completed=BASE/"results/cv_cpu_repeats_v1/COMPLETED.json"
    started=time.monotonic()
    while not completed.exists():
        if time.monotonic()-started>1800:
            raise TimeoutError("Repeated training has not completed; do not aggregate partial jobs")
        time.sleep(5)
    check("repeat_analysis",[sys.executable,"-B","-m","research_extensions.rhythm_fusion.src.analyze","--run","cv_cpu_repeats_v1"])
    old=BASE.parent/"uncertainty/results/cv_cpu_v1/summary.json"
    snapshot=old.with_name("summary_single_seed.json")
    if not snapshot.exists():shutil.copyfile(old,snapshot)
    check("merge_three_seeds",[sys.executable,"-B","-m","research_extensions.rhythm_fusion.src.merge_repeats"])
    check("stage_b_three_seeds",[sys.executable,"-B","-m","research_extensions.uncertainty.src.evaluate"])
    check("figures_three_seeds",[sys.executable,"-B","-m","research_extensions.rhythm_fusion.src.figures"])
    pytest_code="import torch,pytest; torch.set_num_threads(2); raise SystemExit(pytest.main(['tests','web/backend/tests','research_extensions/rhythm_fusion/tests','research_extensions/uncertainty/tests','-q','-p','no:cacheprovider','--basetemp=.test_tmp/rhythm_final_three_seeds','--junitxml=research_extensions/validation/pytest.xml']))"
    check("all_python_tests_final",[sys.executable,"-B","-c",pytest_code])
    check("browser_three_seeds",["cmd","/c","npx","playwright","test","--config","playwright.rhythm.config.ts"],ROOT/"web/frontend")
    check("protection_final",[sys.executable,"-B","-m","research_extensions.protect","verify"])
    check("innovation_report_final",[sys.executable,"-B","-m","research_extensions.rhythm_fusion.src.report"])
    print("FINALIZE COMPLETED: three seeds, Stage B, figures, Python, browser, protection and report",flush=True)


if __name__=="__main__":main()
