"""Read-only project fingerprinting and manual paper synchronization reminders.

The only writes are paper/progress/sync_baseline.json and sync_diff.md.
No training, inference, paper edits, metric edits, or web service calls occur.
"""

from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import re
import sys


ROOT = Path(__file__).resolve().parents[2]
PROGRESS = ROOT / "paper/progress"
BASELINE = PROGRESS / "sync_baseline.json"
REPORT = PROGRESS / "sync_diff.md"
TZ = timezone(timedelta(hours=8))
SKIP_DIRS = {"__pycache__", "node_modules", "dist", ".git", ".umi", ".umi-production", ".cache"}
SOURCE_EXTS = {".py", ".tsx", ".ts", ".less", ".css", ".json"}
RESULT_EXTS = {".json", ".csv", ".log", ".txt"}


def relative(path: Path) -> str:
    return path.resolve().relative_to(ROOT).as_posix()


def safe_path(value: str) -> Path | None:
    path = (ROOT / value.strip().strip("`")).resolve()
    try:
        path.relative_to(ROOT)
    except ValueError:
        return None
    return path


def used_figures() -> list[dict[str, str]]:
    """Read source paths from the maintained figure index, not all screenshots."""
    index = ROOT / "paper/figures/figure_index.md"
    figures = []
    if not index.is_file():
        return figures
    for line in index.read_text(encoding="utf-8-sig").splitlines():
        if not line.startswith("|"):
            continue
        cells = [part.strip().strip("`") for part in line.split("|")[1:-1]]
        if len(cells) < 5 or not cells[0].isdigit():
            continue
        entry = {"number": cells[0], "caption": cells[1], "paper_copy": "paper/figures/" + cells[2],
                 "source": cells[3], "section": cells[4]}
        source = safe_path(cells[3])
        entry["source_file"] = relative(source) if source and source.is_file() else ""
        figures.append(entry)
    return figures


def selected_files(figures: list[dict[str, str]]) -> dict[Path, str]:
    selected: dict[Path, str] = {}

    def add(path: Path, kind: str) -> None:
        if path.is_file() and path.resolve().is_relative_to(ROOT):
            selected[path.resolve()] = kind

    def tree(directory: str, kind: str, extensions: set[str] | None = None) -> None:
        base = ROOT / directory
        if not base.is_dir():
            return
        # pruned walk avoids traversing node_modules or generated build trees
        import os
        for current, directories, names in os.walk(base):
            directories[:] = sorted(name for name in directories if name not in SKIP_DIRS)
            for name in sorted(names):
                path = Path(current) / name
                if extensions is None or path.suffix.lower() in extensions:
                    add(path, kind)

    tree("src", "experiment_source")
    tree("configs", "experiment_config")
    for dataset in ("mitdb44_nv_v1", "mitdb44_nsvf_v1"):
        base = ROOT / "data/processed" / dataset
        # No NPZ rewrites or training; metadata and manifests expose sample/split changes.
        if base.is_dir():
            for path in base.iterdir():
                if path.is_file() and path.suffix.lower() in {".json", ".csv"}:
                    add(path, "dataset_metadata")
    tree("results/classification", "experiment_results", RESULT_EXTS)
    for task in ("nv44_v1", "nsvf44_v1"):
        for name in ("logistic_regression.joblib", "random_forest.joblib", "cnn/cnn_final_best.pt"):
            add(ROOT / "checkpoints" / task / "formal" / name, "model_artifact")
    tree("web/backend", "web_backend", {".py", ".json"})
    tree("web/frontend/src", "web_frontend", SOURCE_EXTS)
    tree("web/frontend/tests", "web_test_source", {".ts", ".tsx"})
    tree("web/results", "deployment_validation", RESULT_EXTS)
    for path in (ROOT / "web/frontend").glob("*.ts"):
        add(path, "web_config")
    for value in ("requirements.txt", "requirements-lock.txt", "web/backend/requirements.txt",
                  "web/frontend/package.json", "web/frontend/package-lock.json",
                  "web/frontend/tsconfig.json", "web/frontend/.umirc.ts"):
        add(ROOT / value, "dependency_or_web_config")
    # Include actual retained test evidence; exclude continuously growing server logs.
    docs = ROOT / "web/docs"
    if docs.is_dir():
        for path in docs.rglob("*"):
            if path.is_file() and path.suffix.lower() in {".md", ".json", ".log"}:
                if not re.search(r"(?:live_server|server\.(?:stdout|stderr))", path.name):
                    add(path, "historical_web_evidence")
    for directory in (ROOT / "web/frontend").glob("test-results*"):
        add(directory / ".last-run.json", "historical_web_evidence")
    for entry in figures:
        add(ROOT / entry["paper_copy"], "paper_figure")
        if entry["source_file"]:
            kind = "used_screenshot" if entry["source_file"].startswith("web/") else "used_experiment_figure"
            add(ROOT / entry["source_file"], kind)
    for value in ("paper/figures/figure_index.md", "paper/draft/ECG_AI_课程论文初稿.md",
                  "paper/evidence/claim_evidence_map.csv", "paper/references/verified_references.md",
                  "paper/references/references_to_verify.md"):
        add(ROOT / value, "paper_source")
    return selected


def snapshot() -> dict:
    entries = {}
    errors = []
    figures = used_figures()
    for path, kind in sorted(selected_files(figures).items(), key=lambda item: str(item[0])):
        key = relative(path)
        try:
            stat_before = path.stat()
            digest = hashlib.sha256()
            with path.open("rb") as stream:
                for block in iter(lambda: stream.read(1024 * 1024), b""):
                    digest.update(block)
            stat_after = path.stat()
            if (stat_before.st_size, stat_before.st_mtime_ns) != (stat_after.st_size, stat_after.st_mtime_ns):
                errors.append(f"{key}: file changed while hashing; rerun after writing completes")
                continue
            entries[key] = {"sha256": digest.hexdigest(), "bytes": stat_after.st_size,
                            "mtime_ns": stat_after.st_mtime_ns, "kind": kind}
        except OSError as exc:
            errors.append(f"{key}: {type(exc).__name__}: {exc}")
    return {"schema_version": 1, "captured_at": datetime.now(TZ).isoformat(timespec="seconds"),
            "root": str(ROOT), "files": entries, "used_figures": figures, "errors": errors}


def screenshot_dependencies(source: str, candidates: set[str]) -> set[str]:
    shared = ("web/frontend/src/components/", "web/frontend/src/layouts/", "web/frontend/src/styles/",
              "web/frontend/src/utils/", "web/frontend/src/hooks/", "web/frontend/src/global")
    if "experiment" in source:
        pages = ("web/frontend/src/pages/experiments/",)
    elif "dashboard" in source:
        pages = ("web/frontend/src/pages/dashboard/",)
    elif "hunter" in source or "game" in source:
        pages = ("web/frontend/src/pages/interactive-lab/",)
    else:
        pages = ("web/frontend/src/pages/ai-detection/",)
    return {name for name in candidates if name.startswith(shared + pages)
            or name == "web/frontend/.umirc.ts" or name.startswith("web/backend/")}


def write_report(current: dict, baseline: dict | None, baseline_updated: bool = False) -> int:
    lines = ["# 论文与项目同步差异报告", "", f"检查时间：{current['captured_at']}（Asia/Shanghai）。", "",
             "此检查只比较文件 SHA-256，不运行训练、推理、构建或测试，不自动改写论文、实验指标或图像。源码新增不等于功能完成；历史 passed 标记不等于本次测试。", ""]
    if current["errors"]:
        lines += ["## 读取异常", "", "存在读取/并发写入异常，本次结果不完整；基线未更新。", ""]
        lines += [f"- {item}" for item in current["errors"]] + [""]
    if baseline_updated:
        lines += ["## 基线已显式建立或更新", "", f"已记录 {len(current['files'])} 个关键文件。", "",
                  "后续默认运行仅比较该基线。更新基线不代表重新核验了改变后的科学结论；应先完成必要审阅，再用 `--baseline` 接受项目状态。", ""]
    elif baseline is None:
        lines += ["## 尚无基线", "", "未自动接受当前状态。先审阅项目，再显式执行 `check_paper_sync.py --baseline`。", ""]
    else:
        old, new = baseline["files"], current["files"]
        added = sorted(new.keys() - old.keys())
        removed = sorted(old.keys() - new.keys())
        changed = sorted(name for name in new.keys() & old.keys() if new[name]["sha256"] != old[name]["sha256"])
        affected = set(added + removed + changed)
        lines += [f"基线时间：{baseline.get('captured_at', '未记录')}。", "",
                  f"本次核对 {len(new)} 个文件；新增 {len(added)}，变更 {len(changed)}，删除 {len(removed)}。", ""]
        for title, names in (("新增文件", added), ("内容变更", changed), ("删除文件", removed)):
            lines += [f"## {title}", ""]
            lines += [f"- `{name}`（{(new.get(name) or old[name])['kind']}）" for name in names] if names else ["无。"]
            lines.append("")
        experiments = sorted(name for name in affected if (new.get(name) or old[name])["kind"] in {
            "experiment_source", "experiment_config", "dataset_metadata", "experiment_results", "model_artifact", "deployment_validation"})
        web = sorted(name for name in affected if (new.get(name) or old[name])["kind"] in {
            "web_backend", "web_frontend", "web_test_source", "web_config", "dependency_or_web_config", "historical_web_evidence"})
        lines += ["## 需要人工处理的论文影响", ""]
        if experiments:
            lines += ["- 实验、数据或部署验证证据发生变化：第二至五章及相关摘要、总结、表图、证据映射需复核。先重算和区分 train/validation/test/CV，再决定修改；本脚本保留原论文数字。"]
        if web:
            lines += ["- Web 源码、配置或验证证据发生变化：第六章及项目完成状态需审阅。核对实际接口、页面行为和带日期测试记录，不能根据新增文件直接写成已完成功能。"]
        if not experiments and not web:
            lines += ["未检出实验或 Web 证据的内容变化；这不代替科学复核或功能测试。"]
        lines.append("")
        lines += ["## 已用截图与对应页面", ""]
        notes = []
        for entry in current["used_figures"]:
            source = entry["source_file"]
            if not source.startswith("web/"):
                continue
            dependencies = screenshot_dependencies(source, affected)
            if source in affected or dependencies:
                notes += [f"- 图{entry['number']}（{entry['section']}）：`{source}` 的源图或关联页面/服务已有变化，需重新运行相应场景，核对并按需重新截图；更新论文副本 `{entry['paper_copy']}` 和图注日期。"]
                if dependencies:
                    notes += ["  关联变更：" + "、".join(f"`{name}`" for name in sorted(dependencies)[:8])
                              + (f"等，共{len(dependencies)}项。" if len(dependencies) > 8 else "。")]
        lines += notes or ["未发现已用截图的关联源码内容变化。已有截图仍是其记录日期的历史页面，不自动变为本次新截图。"]
        lines.append("")
    counts = Counter(entry["kind"] for entry in current["files"].values())
    lines += ["## 覆盖范围", "", "| 类型 | 文件数 |", "|---|---:|"]
    lines += [f"| {kind} | {count} |" for kind, count in sorted(counts.items())]
    lines += ["", "覆盖 src、configs、两数据集CSV/JSON、分类结果CSV/JSON/日志、六个正式模型、前后端源码/测试/配置/依赖、部署验证、保留的Web测试记录及正文图像索引指向的源图和论文副本。排除 node_modules、构建缓存、运行数据库和持续增长的服务日志。", "",
              "哈希检查不能发现未纳入清单的临时文件、运行时行为差异或外部数据变化，也不会自动校验所有PNG是否仍与文字一致。源码关联采用保守路径映射；关联提示需要人工判断。", ""]
    REPORT.write_text("\n".join(lines), encoding="utf-8")
    return 2 if current["errors"] or (baseline is None and not baseline_updated) else 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline", action="store_true", help="Explicitly accept current fingerprints as the baseline")
    args = parser.parse_args()
    PROGRESS.mkdir(parents=True, exist_ok=True)
    current = snapshot()
    previous = None
    if BASELINE.is_file():
        try:
            previous = json.loads(BASELINE.read_text(encoding="utf-8"))
            if previous.get("schema_version") != 1 or not isinstance(previous.get("files"), dict):
                raise ValueError("unsupported baseline structure")
        except (OSError, ValueError) as exc:
            print(f"Baseline unreadable: {exc}", file=sys.stderr)
            if not args.baseline:
                return 2
    updated = args.baseline and not current["errors"]
    if updated:
        BASELINE.write_text(json.dumps(current, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    status = write_report(current, previous, baseline_updated=updated)
    print(f"{'Baseline saved' if updated else 'Comparison complete'}: {len(current['files'])} files; report={REPORT}")
    return status


if __name__ == "__main__":
    raise SystemExit(main())
