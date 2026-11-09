"""Read-only presentation of existing research artifacts; never fits a model."""
from __future__ import annotations

import csv
import json
from io import BytesIO
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RESULTS = ROOT / "results/classification"
REPORTS = {
    "experiment": "web/docs/site_reports/experiment_summary.md",
    "diagnosis": "web/docs/site_reports/four_class_failure_diagnosis.md",
    "final": "web/docs/site_reports/MIT_BIH_完整实验报告.md",
}


def csv_rows(path: Path) -> list[dict]:
    with path.open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


@lru_cache(maxsize=1)
def research_data() -> dict:
    files = {
        "metrics": "final_recomputed_metrics.csv",
        "confusion": "final_recomputed_confusion_matrices.csv",
        "per_class": "final_recomputed_per_class_metrics.csv",
        "splits": "final_verified_split_class_counts.csv",
        "subjects": "final_verified_subject_class_counts.csv",
        "subject_metrics": "final_subject_test_metrics_descriptive_only.csv",
        "concentration": "final_verified_subject_class_concentration.csv",
        "cv": "nsvf44_v1/diagnosis/group_cv_5fold/group_cv_fold_metrics.csv",
        "weights": "nsvf44_v1/diagnosis/weight_strategy_train_val_metrics.csv",
        "weight_classes": "nsvf44_v1/diagnosis/weight_strategy_class_metrics.csv",
    }
    data = {key: csv_rows(RESULTS / name) for key, name in files.items()}
    data["sources"] = {key: f"results/classification/{name}" for key, name in files.items()}
    data["histories"] = {}
    for task in ("nv", "nsvf"):
        folder = ROOT / f"checkpoints/{task}44_v1/formal/cnn"
        summary = json.loads((folder / "cnn_training_summary.json").read_text(encoding="utf-8"))
        data["histories"][task] = {
            "rows": csv_rows(folder / "cnn_training_history.csv"),
            "best_epoch": summary["best_epoch"],
            "source": f"checkpoints/{task}44_v1/formal/cnn/cnn_training_history.csv",
        }
    return data


@lru_cache(maxsize=1)
def gallery() -> list[dict]:
    purposes = {}
    for catalog in RESULTS.rglob("figure_catalog*.csv"):
        for row in csv_rows(catalog):
            purposes[row.get("file", "")] = row.get("purpose", "")
    items = []
    for index, path in enumerate(sorted((ROOT / "figures").rglob("*.png"))):
        relative = path.relative_to(ROOT).as_posix()
        group = path.parent.name
        report = "diagnosis" if "diagnos" in group else "experiment" if "classification" in group else "final"
        items.append({"id": str(index), "title": path.stem.replace("_", " "),
                      "category": group, "path": relative,
                      "description": purposes.get(relative) or f"已有科研图像：{path.stem.replace('_', ' ')}。完整图像及来源报告可在此查看。",
                      "url": f"/api/research/figures/{index}", "report": report})
    return items


def figure_path(figure_id: str) -> Path:
    match = next((row for row in gallery() if row["id"] == figure_id), None)
    if not match:
        raise KeyError("图像不存在，请刷新图库目录")
    path = (ROOT / match["path"]).resolve()
    if not path.is_relative_to((ROOT / "figures").resolve()) or not path.is_file():
        raise KeyError("图像文件缺失，请检查本地图像")
    return path


@lru_cache(maxsize=2)
def saved_predictions(task: str, model: str) -> list[dict]:
    return csv_rows(RESULTS / f"{task}44_v1/test_predictions_{model}.csv")


def error_cases(task: str, model: str, true_label: str, predicted_label: str, subject: str | None) -> dict:
    rows = [row for row in saved_predictions(task, model)
            if row["true_aami_label"] == true_label and row["predicted_aami_label"] == predicted_label
            and (not subject or row["subject_id"] == subject)]
    return {"count": len(rows), "rows": rows[:20], "limit": 20,
            "source": f"results/classification/{task}44_v1/test_predictions_{model}.csv",
            "scope": "测试集预测与误分类样本"}


@lru_cache(maxsize=24)
def figure_thumbnail(path: Path, modified_ns: int) -> bytes:
    from PIL import Image
    with Image.open(path) as original:
        preview = original.convert("RGB")
        preview.thumbnail((640, 440), Image.Resampling.LANCZOS)
        stream = BytesIO()
        preview.save(stream, format="PNG", optimize=True)
        return stream.getvalue()
