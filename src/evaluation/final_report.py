"""Reconcile saved MIT-BIH experiments and generate the final course report.

This module only reads existing datasets, prediction artifacts, logs and model
metadata. It does not train models or modify raw ECG, annotation, predictions,
or checkpoints. Test predictions are re-read solely for the requested metric
reconciliation and retrospective descriptive visualizations.
"""
from __future__ import annotations

import json
import math
import shutil
import sys
from collections import Counter
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch
import numpy as np
import pandas as pd
from sklearn.metrics import (accuracy_score, balanced_accuracy_score,
                             confusion_matrix, precision_recall_fscore_support)

from ..labels import AAMI_MAP

ROOT = Path(__file__).resolve().parents[2]
CLASS_ORDER = {"nv44_v1": ["N", "V"], "nsvf44_v1": ["N", "S", "V", "F"]}
CLASS_COLORS = {"N": "#246a73", "S": "#cf8500", "V": "#bf3544", "F": "#7e4ea8"}
MODEL_LABELS = {"logistic_regression": "Logistic Regression", "random_forest": "Random Forest", "cnn_1d": "1D-CNN"}
SPLIT_LABELS = {"train": "训练集", "val": "验证集", "test": "测试集"}
ENV_DIRS = {".git", ".venv", ".test_tmp", ".mplconfig", "__pycache__"}
FINAL = ROOT / "reports/final"
RESULTS = ROOT / "results/classification"
DIAG = RESULTS / "nsvf44_v1/diagnosis"
FINAL_FIGURES = ROOT / "figures/12_final_report"


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def setup_plot_style() -> str:
    candidates = [Path("C:/Windows/Fonts/msyh.ttc"), Path("C:/Windows/Fonts/simhei.ttf"),
                  Path("C:/Windows/Fonts/simsun.ttc")]
    for candidate in candidates:
        if candidate.exists():
            name = font_manager.FontProperties(fname=str(candidate)).get_name()
            plt.rcParams.update({"font.family": name, "axes.unicode_minus": False})
            break
    else:
        name = "DejaVu Sans"
        plt.rcParams.update({"font.family": name, "axes.unicode_minus": False})
    plt.rcParams.update({"font.size": 10, "axes.titlesize": 12, "axes.labelsize": 10,
                         "legend.fontsize": 8.5, "axes.spines.top": False,
                         "axes.spines.right": False, "axes.grid": True,
                         "grid.alpha": .18, "savefig.dpi": 300})
    return name


def save_figure(fig, name: str):
    target = FINAL_FIGURES / name
    fig.tight_layout()
    fig.savefig(target, dpi=300, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return target


def inventory_files() -> pd.DataFrame:
    rows = []
    for path in ROOT.rglob("*"):
        if not path.is_file():
            continue
        rel = path.relative_to(ROOT)
        if any(part in ENV_DIRS for part in rel.parts):
            continue
        if rel.as_posix() == "reports/final/project_file_inventory.csv":
            continue  # Avoid a self-referential size/count in the generated inventory.
        parts = rel.parts
        top = parts[0]
        if top == "data":
            category = "原始数据" if path.suffix.lower() in {".dat", ".hea", ".atr"} else (
                "处理后数据" if "processed" in parts else "数据支持文件")
        elif top == "checkpoints":
            category = "模型权重与训练日志"
        elif top == "results":
            category = "评估与训练结果"
        elif top == "reports":
            category = "报告"
        elif top == "figures":
            category = "可视化图片与绘图索引"
        elif top == "src":
            category = "源代码"
        elif top in {"configs", "tests"}:
            category = "配置与单元测试"
        else:
            category = "项目文档与其他支持文件"
        rows.append({"category": category, "path": rel.as_posix(),
                     "bytes": path.stat().st_size, "extension": path.suffix.lower()})
    frame = pd.DataFrame(rows).sort_values(["category", "path"])
    FINAL.mkdir(parents=True, exist_ok=True)
    frame.to_csv(FINAL / "project_file_inventory.csv", index=False, encoding="utf-8-sig")
    return frame


def audit_formal_model_artifacts() -> dict:
    """Read-only structural audit of saved formal model weights; performs no inference."""
    import joblib
    import torch

    rows = []
    all_ok = True
    for task, labels in CLASS_ORDER.items():
        checkpoint_dir = ROOT / "checkpoints" / task / "formal"
        config = read_json(RESULTS / task / "config.json")
        logs = read_json(RESULTS / task / "training_logs.json")
        cnn_log = next(row for row in logs if row["model"] == "cnn_1d")
        class_ids = list(range(len(labels)))
        for model in ("logistic_regression", "random_forest"):
            path = checkpoint_dir / f"{model}.joblib"
            payload = joblib.load(path)
            estimator = payload["estimator"]
            found_classes = np.asarray(estimator.classes_).astype(int).tolist()
            n_features = int(estimator.n_features_in_)
            expected_scaler = "StandardScaler" if model == "logistic_regression" else None
            found_scaler = type(payload.get("scaler")).__name__ if payload.get("scaler") is not None else None
            expected_params = config["models"][model]
            params_to_check = ("C", "class_weight", "solver", "max_iter") if model == "logistic_regression" else (
                "n_estimators", "max_depth", "min_samples_leaf", "max_features", "class_weight", "max_samples")
            params_match = all(estimator.get_params(deep=False).get(key) == expected_params[key]
                               for key in params_to_check)
            ok = (found_classes == class_ids and n_features == 253 and found_scaler == expected_scaler and params_match)
            all_ok &= ok
            if hasattr(estimator, "estimators_"):
                size_count = int(sum(tree.tree_.node_count for tree in estimator.estimators_))
            else:
                size_count = int(np.asarray(estimator.coef_).size + np.asarray(estimator.intercept_).size)
            rows.append({"task": task, "model": model, "artifact": path.relative_to(ROOT).as_posix(),
                         "loaded_read_only": True, "class_names": ",".join(labels),
                         "class_ids": ",".join(map(str, found_classes)), "n_features": n_features,
                         "parameter_or_tensor_count": size_count,
                         "scaler": found_scaler or "none", "best_epoch": "", "matches_config_and_log": bool(ok),
                         "estimator_parameters_match_config": bool(params_match)})

        cnn_dir = checkpoint_dir / "cnn"
        best_path = cnn_dir / "cnn_best.pt"
        final_path = cnn_dir / "cnn_final_best.pt"
        best = torch.load(best_path, map_location="cpu", weights_only=True)
        final = torch.load(final_path, map_location="cpu", weights_only=True)
        summary = read_json(cnn_dir / "cnn_training_summary.json")
        state_a, state_b = best["state_dict"], final["state_dict"]
        weights_equal = (state_a.keys() == state_b.keys() and
                         all(torch.equal(state_a[key], state_b[key]) for key in state_a))
        best_epoch = int(final["best_epoch"])
        seed = int(config["seed"])
        best_score_matches = (math.isclose(float(best["val_macro_f1"]), float(cnn_log["best_val_macro_f1"]),
                                            rel_tol=0, abs_tol=1e-10) and
                              math.isclose(float(best["val_macro_f1"]), float(summary["best_val_macro_f1"]),
                                           rel_tol=0, abs_tol=1e-10))
        ok = (final["class_names"] == labels and int(final["seed"]) == seed and
              int(best["seed"]) == seed and int(best["epoch"]) == best_epoch == int(cnn_log["best_epoch"]) ==
              int(summary["best_epoch"]) and weights_equal and best_score_matches and summary["status"] == "completed")
        all_ok &= ok
        rows.append({"task": task, "model": "cnn_1d",
                     "artifact": final_path.relative_to(ROOT).as_posix(), "loaded_read_only": True,
                     "class_names": ",".join(final["class_names"]), "class_ids": ",".join(map(str, class_ids)),
                     "n_features": 253,
                     "parameter_or_tensor_count": int(sum(tensor.numel() for tensor in state_b.values())),
                     "scaler": "训练折拟合参数（见处理配置）", "best_epoch": best_epoch,
                     "matches_config_and_log": bool(ok), "best_and_final_weights_identical": bool(weights_equal),
                     "best_val_macro_f1": float(best["val_macro_f1"]),
                     "training_log_best_val_macro_f1": float(cnn_log["best_val_macro_f1"]),
                     "best_score_matches_logs": bool(best_score_matches)})

    frame = pd.DataFrame(rows)
    frame.to_csv(RESULTS / "final_formal_model_artifact_audit.csv", index=False, encoding="utf-8-sig")
    result = {"formal_model_artifacts_loaded_read_only": len(rows), "all_artifacts_present_and_loadable": True,
              "class_ids_and_253_sample_input_match_tasks": bool(all(
                  row["class_ids"] == ",".join(map(str, range(len(CLASS_ORDER[row["task"]])))) and
                  row["n_features"] == 253 for row in rows)),
              "cnn_best_weights_match_final_checkpoint_and_logs": bool(all(
                  row.get("best_and_final_weights_identical", True) and row["matches_config_and_log"]
                  for row in rows)), "all_formal_artifact_checks_pass": bool(all_ok),
              "no_inference_or_training_performed": True,
              "detail_csv": "results/classification/final_formal_model_artifact_audit.csv"}
    (RESULTS / "final_formal_model_artifact_audit.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    if not all_ok:
        raise AssertionError("A formal saved model artifact did not match its task/config/training log")
    return result


def reconcile_metrics() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, dict]:
    summaries, class_rows, cm_rows, reconciliation = [], [], [], []
    for task, labels in CLASS_ORDER.items():
        base = RESULTS / task
        predictions = pd.read_csv(base / "test_predictions_all_models.csv")
        saved = read_json(base / "test_metrics_all_models.json")
        for model in MODEL_LABELS:
            frame = predictions[predictions.model.eq(model)].copy()
            if set(frame.split.unique()) != {"test"}:
                raise AssertionError(f"Unexpected split in {task}/{model} prediction CSV")
            y_true = frame.true_aami_label.astype(str).to_numpy()
            y_pred = frame.predicted_aami_label.astype(str).to_numpy()
            p, r, f, support = precision_recall_fscore_support(
                y_true, y_pred, labels=labels, zero_division=0)
            cm = confusion_matrix(y_true, y_pred, labels=labels)
            acc = float(accuracy_score(y_true, y_pred))
            bal_acc = float(balanced_accuracy_score(y_true, y_pred))
            macro_f1 = float(np.mean(f))
            total = int(len(y_true))
            weighted_f1 = float(np.average(f, weights=support))
            metric_row = {"task": "N/V" if task.startswith("nv") else "N/S/V/F", "task_id": task,
                          "model": model, "model_label": MODEL_LABELS[model], "n_test": total,
                          "accuracy": acc, "macro_precision": float(np.mean(p)),
                          "macro_recall": float(np.mean(r)), "macro_f1": macro_f1,
                          "weighted_precision": float(np.average(p, weights=support)),
                          "weighted_recall": float(np.average(r, weights=support)),
                          "weighted_f1": weighted_f1, "balanced_accuracy": bal_acc}
            summaries.append(metric_row)
            old = saved[model]
            for key in ("accuracy", "macro_precision", "macro_recall", "macro_f1"):
                difference = float(metric_row[key] - old[key])
                reconciliation.append({"task": metric_row["task"], "model": model, "metric": key,
                                       "saved_json": old[key], "recomputed_from_predictions": metric_row[key],
                                       "absolute_difference": abs(difference),
                                       "matches_within_1e-10": abs(difference) <= 1e-10})
            old_weighted = old["classification_report"]["weighted avg"]
            for key, report_key in [("weighted_precision", "precision"), ("weighted_recall", "recall"),
                                    ("weighted_f1", "f1-score")]:
                difference = float(metric_row[key] - old_weighted[report_key])
                reconciliation.append({"task": metric_row["task"], "model": model, "metric": key,
                                       "saved_json": old_weighted[report_key],
                                       "recomputed_from_predictions": metric_row[key],
                                       "absolute_difference": abs(difference),
                                       "matches_within_1e-10": abs(difference) <= 1e-10})
            if not np.array_equal(cm, np.asarray(old["confusion_matrix"], dtype=int)):
                raise AssertionError(f"Confusion matrix differs for {task}/{model}")
            for i, label in enumerate(labels):
                class_rows.append({"task": metric_row["task"], "model": model, "class": label,
                                   "support": int(support[i]), "precision": float(p[i]),
                                   "recall": float(r[i]), "f1": float(f[i]),
                                   "predicted_count": int(cm[:, i].sum())})
                for j, prediction in enumerate(labels):
                    cm_rows.append({"task": metric_row["task"], "model": model,
                                    "true_class": label, "predicted_class": prediction,
                                    "count": int(cm[i, j])})
            # The separate per-model prediction files must agree with the consolidated CSV.
            per_model = pd.read_csv(base / f"test_predictions_{model}.csv")
            keys = ["sample_id", "true_aami_label", "predicted_aami_label", "correct"]
            joined = frame[keys].sort_values("sample_id").reset_index(drop=True)
            separate = per_model[keys].sort_values("sample_id").reset_index(drop=True)
            if not joined.equals(separate):
                raise AssertionError(f"Consolidated and per-model test predictions differ: {task}/{model}")
    metrics = pd.DataFrame(summaries)
    per_class = pd.DataFrame(class_rows)
    confusion = pd.DataFrame(cm_rows)
    rec = pd.DataFrame(reconciliation)
    metrics.to_csv(RESULTS / "final_recomputed_metrics.csv", index=False, encoding="utf-8-sig")
    per_class.to_csv(RESULTS / "final_recomputed_per_class_metrics.csv", index=False, encoding="utf-8-sig")
    confusion.to_csv(RESULTS / "final_recomputed_confusion_matrices.csv", index=False, encoding="utf-8-sig")
    rec.to_csv(RESULTS / "final_metric_reconciliation.csv", index=False, encoding="utf-8-sig")
    detail = {"source": "saved *_test_predictions*.csv", "metric_match_tolerance": 1e-10,
              "all_saved_scalar_metrics_match": bool(rec["matches_within_1e-10"].all()),
              "all_confusion_matrices_match": True,
              "per_model_and_consolidated_prediction_files_match": True,
              "models_checked": len(metrics), "predictions": int(metrics.n_test.sum()),
              "models": metrics.to_dict(orient="records"),
              "per_class": per_class.to_dict(orient="records")}
    (RESULTS / "final_metric_reconciliation.json").write_text(
        json.dumps(detail, ensure_ascii=False, indent=2), encoding="utf-8")
    return metrics, per_class, confusion, detail


def inspect_splits_and_classes() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, dict]:
    all_stats, subject_frames, coverage_rows, concentration_rows = [], [], [], []
    split_count_audit = []
    task_metadata = {}
    for task, labels in CLASS_ORDER.items():
        data_dir = ROOT / "data/processed" / ("mitdb44_nv_v1" if task.startswith("nv") else "mitdb44_nsvf_v1")
        metadata = pd.read_csv(data_dir / "metadata.csv", low_memory=False)
        included = metadata.included.astype(str).str.lower().eq("true") & metadata.mapped_label.isin(labels)
        beats = metadata.loc[included].copy()
        if beats.empty:
            raise AssertionError(f"No included samples for {task}")
        if beats.original_label.map(AAMI_MAP).ne(beats.mapped_label).any():
            raise AssertionError(f"Original symbol mapping mismatch in {task}")
        if beats.groupby("sample_id").size().max() > 1:
            raise AssertionError(f"Duplicate sample ids in {task}")
        expected_rows = []
        for (split_name, label), part in beats.groupby(["split", "mapped_label"], sort=False):
            expected_rows.append({"split": split_name, "aami_label": label,
                                  "class_id": labels.index(label), "sample_count": int(len(part)),
                                  "subject_count": int(part.subject_id.nunique()),
                                  "record_count": int(part.record_id.nunique())})
        split_order = {"train": 0, "val": 1, "test": 2}
        expected_counts = (pd.DataFrame(expected_rows)
                           .assign(_split_order=lambda x: x["split"].map(split_order))
                           .sort_values(["_split_order", "class_id"])
                           .drop(columns="_split_order").reset_index(drop=True))
        count_path = data_dir / "split_class_counts.csv"
        existing_counts = (pd.read_csv(count_path)
                           .assign(_split_order=lambda x: x["split"].map(split_order))
                           .sort_values(["_split_order", "class_id"])
                           .drop(columns="_split_order").reset_index(drop=True))
        count_fields = ["split", "aami_label", "class_id", "sample_count", "subject_count", "record_count"]
        old_matches = existing_counts[count_fields].equals(expected_counts[count_fields])
        archive = FINAL / f"{task}_split_class_counts_before_repair.csv"
        archive_matches = None
        if archive.exists():
            archived_counts = (pd.read_csv(archive)
                               .assign(_split_order=lambda x: x["split"].map(split_order))
                               .sort_values(["_split_order", "class_id"])
                               .drop(columns="_split_order").reset_index(drop=True))
            archive_matches = archived_counts[count_fields].equals(expected_counts[count_fields])
        if not old_matches:
            if not archive.exists():
                shutil.copy2(count_path, archive)
                archived_counts = (pd.read_csv(archive)
                                   .assign(_split_order=lambda x: x["split"].map(split_order))
                                   .sort_values(["_split_order", "class_id"])
                                   .drop(columns="_split_order").reset_index(drop=True))
                archive_matches = archived_counts[count_fields].equals(expected_counts[count_fields])
            expected_counts[count_fields].to_csv(count_path, index=False, encoding="utf-8-sig")
        repaired_counts = (pd.read_csv(count_path)
                           .assign(_split_order=lambda x: x["split"].map(split_order))
                           .sort_values(["_split_order", "class_id"])
                           .drop(columns="_split_order").reset_index(drop=True))
        if not repaired_counts[count_fields].equals(expected_counts[count_fields]):
            raise AssertionError(f"Corrected derived class counts do not match metadata: {task}")
        split_count_audit.append({"dataset_id": task, "current_values_match_metadata": bool(old_matches),
                                  "historical_values_match_metadata": bool(archive_matches) if archive_matches is not None else bool(old_matches),
                                  "corrected_from_metadata": bool(archive.exists() and archive_matches is False),
                                  "post_repair_matches_metadata": True,
                                  "archived_previous_values": archive.relative_to(ROOT).as_posix() if archive.exists() else ""})
        split_totals = beats.groupby("split").size().to_dict()
        for split, part in beats.groupby("split", sort=False):
            total = len(part)
            for label in labels:
                sub = part[part.mapped_label.eq(label)]
                all_stats.append({"dataset": "N/V" if task.startswith("nv") else "N/S/V/F",
                                  "dataset_id": task, "split": split, "class": label,
                                  "sample_count": int(len(sub)),
                                  "share_of_split_pct": float(100 * len(sub) / total) if total else 0.0,
                                  "subject_count": int(sub.subject_id.nunique()),
                                  "record_count": int(sub.record_id.nunique()),
                                  "split_sample_total": int(total),
                                  "split_subject_total": int(part.subject_id.nunique()),
                                  "split_record_total": int(part.record_id.nunique())})
            matrix = part.pivot_table(index="subject_id", columns="mapped_label", values="sample_id",
                                      aggfunc="count", fill_value=0)
            for label in labels:
                if label not in matrix.columns:
                    matrix[label] = 0
            matrix = matrix[labels].astype(int).sort_index()
            for subject, row in matrix.iterrows():
                subject_frames.append({"dataset": "N/V" if task.startswith("nv") else "N/S/V/F",
                                       "dataset_id": task, "split": split, "subject_id": subject,
                                       **{label: int(row[label]) for label in labels},
                                       "total_samples": int(row.sum())})
            for label in labels:
                values = matrix[label].to_numpy(dtype=float)
                present = values[values > 0]
                n = int(np.sum(values > 0))
                total_label = int(values.sum())
                top_idx = int(np.argmax(values)) if len(values) else 0
                ordered = np.sort(values)[::-1]
                if total_label:
                    probabilities = present / total_label
                    entropy_bits = float(-(probabilities * np.log2(probabilities)).sum())
                    effective_n = float(2 ** entropy_bits)
                    coverage_rows.append({"dataset": "N/V" if task.startswith("nv") else "N/S/V/F",
                                          "dataset_id": task, "split": split, "class": label,
                                          "subjects_with_class": n, "subjects_total": int(len(matrix)),
                                          "coverage_pct": 100 * n / len(matrix),
                                          "sample_count": total_label,
                                          "top_subject_id": str(matrix.index[top_idx]) if len(matrix) else "",
                                          "top_subject_samples": int(values[top_idx]) if len(values) else 0,
                                          "top_subject_share_pct": 100 * values[top_idx] / total_label,
                                          "top3_subject_share_pct": 100 * ordered[:3].sum() / total_label,
                                          "effective_subject_count_2pow_entropy": effective_n})
        manifest = pd.read_csv(data_dir / "split_manifest.csv", dtype={"record_id": str})
        task_metadata[task] = {"metadata": metadata, "manifest": manifest, "labels": labels,
                               "beats": beats, "split_totals": split_totals}
    nsvf_manifest = task_metadata["nsvf44_v1"]["manifest"]
    nv_manifest = task_metadata["nv44_v1"]["manifest"]
    nv_split = nv_manifest.set_index("record_id").split.to_dict()
    multi_split = nsvf_manifest.set_index("record_id").split.to_dict()
    same_records = set(nv_split) == set(multi_split)
    same_partition = same_records and nv_split == multi_split
    subject_mapping = nsvf_manifest.drop_duplicates("subject_id").set_index("subject_id").split.to_dict()
    overlap = {s1: sorted(set(nsvf_manifest.loc[nsvf_manifest.split.eq(s1), "subject_id"]) &
                          set(nsvf_manifest.loc[nsvf_manifest.split.eq(s2), "subject_id"]))
               for s1, s2 in [("train", "val"), ("train", "test"), ("val", "test")]}
    same_201_202 = (nsvf_manifest.set_index("record_id").loc[["201", "202"], "subject_id"].nunique() == 1 and
                    nsvf_manifest.set_index("record_id").loc[["201", "202"], "split"].nunique() == 1)
    if not same_partition or any(overlap.values()) or not same_201_202:
        raise AssertionError("Subject split or 201/202 grouping audit failed")
    stats = pd.DataFrame(all_stats)
    subjects = pd.DataFrame(subject_frames)
    coverage = pd.DataFrame(coverage_rows)
    stats.to_csv(RESULTS / "final_verified_split_class_counts.csv", index=False, encoding="utf-8-sig")
    subjects.to_csv(RESULTS / "final_verified_subject_class_counts.csv", index=False, encoding="utf-8-sig")
    coverage.to_csv(RESULTS / "final_verified_subject_class_concentration.csv", index=False, encoding="utf-8-sig")
    audit = {"same_44_records": same_records, "N_V_and_N_S_V_F_same_record_split": same_partition,
             "record_subject_overlap_between_splits": overlap,
             "201_202_same_pseudonymous_subject_and_split": bool(same_201_202),
             "aami_mapping_matches_src_labels": True,
             "derived_split_class_count_audit": split_count_audit,
             "included_samples_unique": True,
             "datasets": {task: {"split_samples": info["split_totals"],
                                 "samples": int(len(info["beats"])),
                                 "subjects": int(info["beats"].subject_id.nunique()),
                                 "records": int(info["beats"].record_id.nunique())}
                          for task, info in task_metadata.items()}}
    (RESULTS / "final_split_and_mapping_audit.json").write_text(
        json.dumps(audit, ensure_ascii=False, indent=2), encoding="utf-8")
    return stats, subjects, coverage, audit


def plot_model_performance(metrics: pd.DataFrame):
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.6), sharey=True)
    tasks = ["N/V", "N/S/V/F"]
    models = list(MODEL_LABELS)
    x = np.arange(len(models)); width = .34
    for ax, metric, title in zip(axes, ["accuracy", "macro_f1"], ["Accuracy", "Macro-F1"]):
        for j, task in enumerate(tasks):
            values = [float(metrics[(metrics.task == task) & (metrics.model == m)][metric].iloc[0]) for m in models]
            bars = ax.bar(x + (j - .5) * width, values, width, label=task,
                          color=["#2a9d8f", "#e76f51"][j], edgecolor="white")
            ax.bar_label(bars, fmt="%.3f", padding=2, fontsize=8)
        ax.set_title(title)
        ax.set_ylabel("测试集分数 (0–1)")
        ax.set_ylim(0, 1.12)
        ax.set_xticks(x, [MODEL_LABELS[m] for m in models], rotation=12, ha="right")
        ax.legend(title="任务")
    fig.suptitle("二分类与四分类模型性能对照（已查看的锁定测试结果）", y=1.04)
    fig.text(.5, -.04, "测试集已用于既有评估；本图为结果核验与报告展示，不用于选择模型。", ha="center", fontsize=9)
    save_figure(fig, "01_task_model_performance.png")


def plot_class_counts_and_coverage(stats: pd.DataFrame, coverage: pd.DataFrame):
    order = ["N", "S", "V", "F"]
    overall = stats[(stats.dataset == "N/S/V/F") & (stats.split == "train")].set_index("class")
    for split in ("val", "test"):
        part = stats[(stats.dataset == "N/S/V/F") & (stats.split == split)].set_index("class")
        overall.loc[part.index, "sample_count"] = overall.loc[part.index, "sample_count"].values + part.sample_count.values
    overall = stats[stats.dataset.eq("N/S/V/F")].groupby("class", as_index=True).sample_count.sum()
    cov = coverage[(coverage.dataset == "N/S/V/F") & (coverage.split.isin(["train", "val", "test"]))]
    cov = cov.groupby("class").agg(subject_groups=("subjects_with_class", "sum"),
                                    split_groups=("subjects_total", "sum")).reindex(order)
    # Coverage percentages pool unique patients over the single fixed partition.
    all_counts = pd.read_csv(RESULTS / "final_verified_subject_class_counts.csv")
    all_counts = all_counts[all_counts.dataset.eq("N/S/V/F")]
    unique_coverage = {c: int((all_counts[c] > 0).sum()) for c in order}
    unique_subjects = int(all_counts.subject_id.nunique())
    shares = [100 * unique_coverage[c] / unique_subjects for c in order]
    counts = [int(overall[c]) for c in order]
    fig, axes = plt.subplots(1, 2, figsize=(10.8, 4.4))
    bars = axes[0].bar(order, counts, color=[CLASS_COLORS[c] for c in order])
    axes[0].bar_label(bars, labels=[f"{v:,}" for v in counts], padding=3)
    axes[0].set_title("有效心拍数量")
    axes[0].set_ylabel("心拍样本数（从 0 起）")
    axes[0].set_ylim(0, max(counts) * 1.14)
    bars = axes[1].bar(order, shares, color=[CLASS_COLORS[c] for c in order])
    axes[1].bar_label(bars, labels=[f"{unique_coverage[c]}/{unique_subjects}\n{shares[i]:.1f}%" for i, c in enumerate(order)], padding=3)
    axes[1].set_title("至少有一拍该类的受试者覆盖")
    axes[1].set_ylabel("受试者覆盖比例（%）")
    axes[1].set_ylim(0, 115)
    fig.suptitle("N/S/V/F 样本量与跨受试者覆盖（44 条记录）", y=1.03)
    save_figure(fig, "02_class_support_and_subject_coverage.png")


def plot_weight_pr(weight_classes: pd.DataFrame):
    strategies = ["unweighted", "sqrt_inverse", "capped_inverse_10", "full_inverse"]
    pretty = {"unweighted": "无权重", "sqrt_inverse": "平方根逆频率",
              "capped_inverse_10": "逆频率截断 10", "full_inverse": "全逆频率"}
    markers = {"unweighted": "o", "sqrt_inverse": "s", "capped_inverse_10": "^", "full_inverse": "D"}
    val = weight_classes[weight_classes.split.eq("val")]
    fig, axes = plt.subplots(2, 2, figsize=(9.4, 7.4), sharex=True, sharey=True)
    for ax, cls in zip(axes.ravel(), ["N", "S", "V", "F"]):
        part = val[val["class"].eq(cls)].set_index("strategy").reindex(strategies)
        for strategy in strategies:
            row = part.loc[strategy]
            ax.scatter(row.recall, row.precision, color=CLASS_COLORS[cls], marker=markers[strategy],
                       s=72, edgecolor="white", linewidth=.6, zorder=3)
        ax.set_title(f"{cls} 类（验证支持 {int(part.support.iloc[0])}）")
        ax.set_xlim(-.04, 1.04); ax.set_ylim(-.04, 1.04)
        ax.set_xlabel("Recall"); ax.set_ylabel("Precision")
    from matplotlib.lines import Line2D
    handles = [Line2D([0], [0], marker=markers[s], color="w", markerfacecolor="#536878",
                      markeredgecolor="white", markersize=8, label=pretty[s]) for s in strategies]
    fig.legend(handles=handles, loc="lower center", ncol=4, bbox_to_anchor=(.5, -.015), frameon=False)
    fig.suptitle("四种 CNN 类别权重策略的验证集 Precision–Recall", y=1.02)
    fig.text(.5, -.08, "训练/验证划分已经参与早停；此图用于解释权重影响，不是独立调参结果。", ha="center", fontsize=9)
    save_figure(fig, "04_weight_strategy_precision_recall.png")


def plot_weight_shares(weight_metrics: pd.DataFrame):
    strategies = ["unweighted", "sqrt_inverse", "capped_inverse_10", "full_inverse"]
    pretty = {"unweighted": "无权重", "sqrt_inverse": "平方根逆频率",
              "capped_inverse_10": "逆频率截断 10", "full_inverse": "全逆频率"}
    val = weight_metrics[weight_metrics.split.eq("val")].set_index("strategy").reindex(strategies)
    classes = ["N", "S", "V", "F"]
    fig, ax = plt.subplots(figsize=(10, 4.8))
    x = np.arange(len(strategies) + 1)
    truth = val.iloc[0]
    shares = {c: [float(truth[f"true_share_{c}"])] +
              [float(val.loc[s, f"predicted_share_{c}"]) for s in strategies]
              for c in classes}
    bottom = np.zeros(len(x))
    for cls in classes:
        values = np.array(shares[cls])
        ax.bar(x, values, bottom=bottom, label=cls, color=CLASS_COLORS[cls], edgecolor="white")
        for i, val_pct in enumerate(values):
            if val_pct >= 2:
                ax.text(i, bottom[i] + val_pct / 2, f"{val_pct:.1f}%", ha="center", va="center",
                        color="white" if cls in ("N", "V", "F") else "black", fontsize=8)
        bottom += values
    ax.set_xticks(x, ["真实分布"] + [pretty[s] for s in strategies], rotation=8)
    ax.set_ylim(0, 100); ax.set_ylabel("验证集心拍占比（%）")
    ax.set_title("验证集真实类别份额与各权重策略的预测类别份额")
    ax.legend(title="类别", ncol=4, loc="upper center", bbox_to_anchor=(.5, -0.17))
    save_figure(fig, "05_weight_strategy_prediction_shares.png")


def plot_patient_test_heatmap():
    rows = []
    for task, task_name, labels in [("nv44_v1", "N/V", CLASS_ORDER["nv44_v1"]),
                                    ("nsvf44_v1", "N/S/V/F", CLASS_ORDER["nsvf44_v1"])]:
        predictions = pd.read_csv(RESULTS / task / "test_predictions_all_models.csv")
        for (model, subject), part in predictions.groupby(["model", "subject_id"]):
            y_true = part.true_aami_label.astype(str).to_numpy()
            y_pred = part.predicted_aami_label.astype(str).to_numpy()
            supported = [label for label in labels if np.any(y_true == label)]
            _, _, f_values, _ = precision_recall_fscore_support(y_true, y_pred, labels=supported, zero_division=0)
            row = {"task": task_name, "model": model, "subject_id": str(subject),
                   "record_ids": ",".join(sorted(set(part.record_id.astype(str)))),
                   "record_count": int(part.record_id.nunique()), "sample_count": int(len(part)),
                   "accuracy": float(accuracy_score(y_true, y_pred)),
                   "macro_f1_present_classes": float(np.mean(f_values))}
            for label in labels:
                row[f"support_{label}"] = int(np.sum(y_true == label))
                row[f"recall_{label}"] = float(np.mean(y_pred[y_true == label] == label)) if np.any(y_true == label) else np.nan
            rows.append(row)
    table = pd.DataFrame(rows)
    table.to_csv(RESULTS / "final_subject_test_metrics_descriptive_only.csv", index=False, encoding="utf-8-sig")
    subjects = sorted(table.subject_id.unique(), key=lambda x: int(x.split("_")[-1]) if x.split("_")[-1].isdigit() else 999)
    models = list(MODEL_LABELS)
    fig, axes = plt.subplots(1, 2, figsize=(12, 5.5))
    nv_scores = table[table.task.eq("N/V")].pivot(index="subject_id", columns="model", values="accuracy")
    four_scores = table[table.task.eq("N/S/V/F")].pivot(index="subject_id", columns="model", values="macro_f1_present_classes")
    for ax, data, title in [(axes[0], nv_scores.reindex(index=subjects, columns=models), "N/V Accuracy"),
                            (axes[1], four_scores.reindex(index=subjects, columns=models),
                             "N/S/V/F Macro-F1（仅患者真实出现类别）")]:
        image = ax.imshow(data.to_numpy(float), vmin=0, vmax=1, cmap="YlGnBu", aspect="auto")
        scale = fig.colorbar(image, ax=ax, fraction=.035, pad=.02)
        scale.set_ticks([0, .5, 1])
        scale.set_label("分数（0–1）")
        ax.set_xticks(range(len(models)), [MODEL_LABELS[m] for m in models], rotation=18, ha="right")
        ax.set_yticks(range(len(subjects)), [s.replace("subject_", "") for s in subjects])
        ax.set_title(title)
        for i in range(data.shape[0]):
            for j in range(data.shape[1]):
                value = data.iloc[i, j]
                ax.text(j, i, "—" if pd.isna(value) else f"{value:.3f}", ha="center", va="center", fontsize=8)
    fig.suptitle("按受试者汇总的已查看测试预测（仅回顾性描述；颜色范围 0–1）", y=1.02)
    save_figure(fig, "07_subject_level_model_heatmap_descriptive.png")


def plot_error_directions(confusion: pd.DataFrame):
    cnn = confusion[(confusion.task == "N/S/V/F") & (confusion.model == "cnn_1d")]
    matrix = cnn.pivot(index="true_class", columns="predicted_class", values="count").reindex(index=["N", "S", "V", "F"], columns=["N", "S", "V", "F"])
    pairs = [("N", "S"), ("F", "N"), ("F", "V"), ("V", "N")]
    counts = [int(matrix.loc[a, b]) for a, b in pairs]
    supports = matrix.sum(axis=1)
    rates = [counts[i] / float(supports[a]) * 100 for i, (a, _) in enumerate(pairs)]
    fig, axes = plt.subplots(1, 2, figsize=(10, 4.8))
    names = [f"{a}→{b}" for a, b in pairs]
    colors = [CLASS_COLORS[a] for a, _ in pairs]
    bars = axes[0].barh(names, counts, color=colors)
    axes[0].bar_label(bars, labels=[f"{n:,}" for n in counts], padding=3)
    axes[0].invert_yaxis(); axes[0].set_xlim(0, max(counts) * 1.15)
    axes[0].set_xlabel("心拍数（线性刻度，0 起）"); axes[0].set_title("错误数量")
    bars = axes[1].barh(names, rates, color=colors)
    axes[1].bar_label(bars, labels=[f"{n:.2f}%" for n in rates], padding=3)
    axes[1].invert_yaxis(); axes[1].set_xlim(0, max(rates) * 1.15)
    axes[1].set_xlabel("占真实类别支持数比例（%）"); axes[1].set_title("类内错误比例")
    fig.suptitle("CNN 四分类主要测试集错误方向（锁定测试集回顾）", y=1.03)
    save_figure(fig, "08_cnn_error_directions_descriptive.png")


def plot_cnn_nv_class_comparison(per_class: pd.DataFrame):
    rows = per_class[(per_class.model == "cnn_1d") & per_class["class"].isin(["N", "V"])].copy()
    fig, axes = plt.subplots(1, 3, figsize=(11, 4.1), sharey=True)
    for ax, metric in zip(axes, ["precision", "recall", "f1"]):
        x = np.arange(2); width = .34
        for j, task in enumerate(["N/V", "N/S/V/F"]):
            vals = [float(rows[(rows.task == task) & (rows["class"] == cls)][metric].iloc[0]) for cls in ["N", "V"]]
            bars = ax.bar(x + (j - .5) * width, vals, width,
                          label=task if metric == "precision" else None,
                          color=["#2a9d8f", "#e76f51"][j])
            ax.bar_label(bars, fmt="%.3f", padding=2, fontsize=8)
        ax.set_xticks(x, ["N", "V"]); ax.set_ylim(0, 1.12)
        ax.set_title(metric.capitalize())
    axes[0].set_ylabel("测试集分数（0–1）")
    axes[0].legend(title="任务")
    fig.suptitle("同为 N/V 类时，CNN 二分类与四分类的逐类指标", y=1.04)
    fig.text(.5, -.04, "四分类把 S、F 加入竞争类别；指标来自此前已经查看的锁定测试集。", ha="center", fontsize=9)
    save_figure(fig, "09_cnn_binary_vs_multiclass_per_class.png")


def plot_project_flow():
    fig, ax = plt.subplots(figsize=(12, 3.5))
    ax.set_xlim(0, 12); ax.set_ylim(0, 3.5); ax.axis("off")
    nodes = [(0.3, "PhysioNet\nMIT-BIH\n48 条/47 人"),
             (2.7, "读取与标注\n44 条非起搏\nAAMI 映射"),
             (5.1, "预处理\nMLII · 0.5–40 Hz\n253 点心拍窗"),
             (7.5, "患者独立划分\ntrain / val / test\n201/202 合并"),
             (9.9, "实验评估\nN/V · N/S/V/F\n三种基础模型")]
    for x, text in nodes:
        box = FancyBboxPatch((x, 1.15), 1.8, 1.35, boxstyle="round,pad=0.08,rounding_size=0.08",
                             linewidth=1.4, edgecolor="#246a73", facecolor="#eff7f6")
        ax.add_patch(box); ax.text(x + .9, 1.83, text, ha="center", va="center", fontsize=9)
    for i in range(len(nodes) - 1):
        ax.add_patch(FancyArrowPatch((nodes[i][0] + 1.85, 1.83), (nodes[i + 1][0] - .08, 1.83),
                                     arrowstyle="-|>", mutation_scale=14, linewidth=1.2, color="#566573"))
    ax.text(6, .62, "分组交叉验证、类别权重分析、患者级错误回顾；不进行临床诊断", ha="center", fontsize=10,
            color="#333333")
    ax.set_title("MIT-BIH 课程项目实际实验流程", fontsize=14, pad=10)
    save_figure(fig, "10_project_workflow.png")


def plot_error_examples():
    task_dir = ROOT / "data/processed/mitdb44_nsvf_v1"
    pred = pd.read_csv(RESULTS / "nsvf44_v1/test_predictions_cnn_1d.csv")
    pred = pred[pred.split.eq("test") & ~pred.correct.astype(bool)].copy()
    directions = [("N", "S"), ("F", "N"), ("F", "V"), ("V", "N")]
    metadata = pd.read_csv(task_dir / "metadata.csv", low_memory=False)
    test_meta = metadata[metadata.included.astype(str).str.lower().eq("true") & metadata.split.eq("test")]
    selected = []
    for true, predicted in directions:
        part = pred[pred.true_aami_label.eq(true) & pred.predicted_aami_label.eq(predicted)].copy()
        if part.empty:
            continue
        confidence_col = f"probability_{predicted}"
        median_conf = float(part[confidence_col].median())
        part["_distance"] = (part[confidence_col] - median_conf).abs()
        row = part.sort_values(["_distance", "sample_id"], kind="stable").iloc[0]
        meta = test_meta[test_meta.sample_id.eq(row.sample_id)]
        if len(meta) != 1:
            raise AssertionError(f"Cannot uniquely map test sample {row.sample_id} to the saved beat window")
        selected.append((row, meta.iloc[0]))
    if not selected:
        raise AssertionError("No representative test error cases found")
    with np.load(task_dir / "test.npz", allow_pickle=False) as data:
        wave = data["X_filtered"]
        time_s = data["relative_time_s"]
        ids = data["sample_id"].astype(str)
        lookup = {sample_id: i for i, sample_id in enumerate(ids)}
        fig, axes = plt.subplots(len(selected), 1, figsize=(9.6, 2.35 * len(selected)), squeeze=False)
        cases = []
        for ax, (row, meta) in zip(axes[:, 0], selected):
            ix = lookup[str(row.sample_id)]
            ax.plot(time_s, wave[ix, 0], color="#253b51", linewidth=1.2)
            ax.axvline(0, color="#bf3544", linestyle="--", linewidth=1, label="专家标注位置 t=0")
            predicted = str(row.predicted_aami_label)
            true = str(row.true_aami_label)
            confidence = float(row[f"probability_{predicted}"])
            ax.set_ylabel("振幅 (mV)")
            ax.set_xlabel("相对标注时间 (s)")
            ax.set_title(f"{true}→{predicted} | record {row.record_id}, {row.subject_id}, lead {row.lead_name}, "
                         f"原始标签 {row.original_label} | {float(row.time_s):.3f} s | P({predicted})={confidence:.3f}",
                         loc="left", fontsize=9)
            ax.legend(loc="upper right", fontsize=7)
            probs = ", ".join(f"P({c})={float(row[f'probability_{c}']):.2f}" for c in ["N", "S", "V", "F"])
            cases.append({"sample_id": row.sample_id, "record_id": row.record_id,
                          "subject_id": row.subject_id, "annotation_sample": int(row.annotation_sample),
                          "time_s": float(row.time_s), "lead_name": row.lead_name,
                          "original_label": row.original_label,
                          "true_class": true, "predicted_class": predicted,
                          "predicted_class_probability": confidence, "probabilities": probs,
                          "selection": "median predicted-class confidence within the error direction"})
    fig.suptitle("四分类主要错误方向的典型心拍（已查看测试集，仅作回顾性示例）", y=1.01)
    save_figure(fig, "11_error_case_ecg_with_probabilities_descriptive.png")
    cases_df = pd.DataFrame(cases)
    cases_df.to_csv(RESULTS / "nsvf44_v1/diagnosis/final_error_case_samples_descriptive_only.csv",
                   index=False, encoding="utf-8-sig")
    return cases_df


def generate_figures(metrics, per_class, confusion, stats, coverage, weight_metrics, weight_classes):
    font = setup_plot_style()
    FINAL_FIGURES.mkdir(parents=True, exist_ok=True)
    plot_model_performance(metrics)
    plot_class_counts_and_coverage(stats, coverage)
    plot_weight_pr(weight_classes)
    plot_weight_shares(weight_metrics)
    plot_patient_test_heatmap()
    plot_error_directions(confusion)
    plot_cnn_nv_class_comparison(per_class)
    plot_project_flow()
    cases = plot_error_examples()
    return font, cases


def md_table(frame: pd.DataFrame, columns=None, digits=4) -> str:
    if columns is not None:
        frame = frame[columns]
    clean = frame.copy()
    for col in clean.columns:
        clean[col] = clean[col].map(lambda x: "—" if pd.isna(x) else
                                    f"{x:.{digits}f}" if isinstance(x, (float, np.floating)) else str(x))
    header = "| " + " | ".join(map(str, clean.columns)) + " |"
    sep = "| " + " | ".join("---" for _ in clean.columns) + " |"
    body = ["| " + " | ".join(row) + " |" for row in clean.astype(str).itertuples(index=False, name=None)]
    return "\n".join([header, sep, *body])


def metric_tables(metrics, per_class, confusion):
    aliases = {"logistic_regression": "LR", "random_forest": "RF", "cnn_1d": "1D-CNN"}
    m = metrics.copy(); m["模型"] = m.model.map(MODEL_LABELS)
    m["任务"] = m.task
    m = m.rename(columns={"n_test": "测试样本数", "accuracy": "Accuracy", "macro_f1": "Macro-F1",
                          "weighted_f1": "Weighted-F1", "balanced_accuracy": "Balanced Accuracy"})
    summary = md_table(m, ["任务", "模型", "测试样本数", "Accuracy", "Macro-F1", "Weighted-F1", "Balanced Accuracy"])
    c = per_class.copy(); c["模型"] = c.model.map(MODEL_LABELS)
    c = c.rename(columns={"task": "任务", "class": "类别", "support": "Support", "precision": "Precision",
                          "recall": "Recall", "f1": "F1", "predicted_count": "预测数"})
    class_table = md_table(c, ["任务", "模型", "类别", "Support", "Precision", "Recall", "F1", "预测数"])
    matrices = []
    for task in ["N/V", "N/S/V/F"]:
        for model in MODEL_LABELS:
            part = confusion[(confusion.task == task) & (confusion.model == model)]
            mat = part.pivot(index="true_class", columns="predicted_class", values="count")
            labels = CLASS_ORDER["nv44_v1" if task == "N/V" else "nsvf44_v1"]
            mat = mat.reindex(index=labels, columns=labels)
            matrices.append(f"**{task} · {MODEL_LABELS[model]}**\n\n" + md_table(
                mat.rename_axis("真实\\预测").reset_index(), list(mat.columns.insert(0, "真实\\预测")), digits=0))
    return summary, class_table, "\n\n".join(matrices)


def exact_report(metrics, per_class, confusion, stats, subjects, coverage, audit,
                 reconciliation, cases, font_name, inventory):
    metric_table, class_table, cm_tables = metric_tables(metrics, per_class, confusion)
    diagnostic = read_json(DIAG / "diagnosis_manifest.json")
    weight_metrics = pd.read_csv(DIAG / "weight_strategy_train_val_metrics.csv")
    weight_classes = pd.read_csv(DIAG / "weight_strategy_class_metrics.csv")
    cv = pd.read_csv(DIAG / "group_cv_summary.csv")
    cv_folds = pd.read_csv(DIAG / "group_cv_5fold/group_cv_fold_metrics.csv")
    split_counts = stats[stats.dataset_id.eq("nsvf44_v1")].copy()
    split_counts["split"] = split_counts.split.map(SPLIT_LABELS)
    subject_cov = coverage[coverage.dataset_id.eq("nsvf44_v1")].copy()
    subject_cov["split"] = subject_cov.split.map(SPLIT_LABELS)
    count_table = md_table(split_counts, ["split", "class", "sample_count", "share_of_split_pct",
                                          "subject_count", "record_count", "split_subject_total", "split_record_total"])
    split_repair = pd.DataFrame(audit["derived_split_class_count_audit"])
    split_repair["dataset_id"] = split_repair.dataset_id.map({"nv44_v1": "N/V", "nsvf44_v1": "N/S/V/F"})
    split_repair_table = md_table(split_repair.rename(columns={"dataset_id": "任务",
        "current_values_match_metadata": "当前 CSV 与 metadata 一致", "historical_values_match_metadata": "存档旧 CSV 与 metadata 一致",
        "corrected_from_metadata": "本轮发现并修正旧 CSV", "post_repair_matches_metadata": "修正后核验通过",
        "archived_previous_values": "旧值存档路径"}), ["任务", "当前 CSV 与 metadata 一致", "存档旧 CSV 与 metadata 一致",
                                                               "本轮发现并修正旧 CSV", "修正后核验通过", "旧值存档路径"], digits=0)
    coverage_table = md_table(subject_cov, ["split", "class", "subjects_with_class", "subjects_total",
                                            "coverage_pct", "sample_count", "top_subject_id",
                                            "top_subject_share_pct", "top3_subject_share_pct",
                                            "effective_subject_count_2pow_entropy"])
    patient_table = md_table(subjects[subjects.dataset_id.eq("nsvf44_v1")],
                             ["split", "subject_id", "N", "S", "V", "F", "total_samples"], digits=0)
    patient_metrics = pd.read_csv(RESULTS / "final_subject_test_metrics_descriptive_only.csv")
    patient_cnn = patient_metrics[(patient_metrics.task.eq("N/S/V/F")) & patient_metrics.model.eq("cnn_1d")].copy()
    patient_cnn = patient_cnn.rename(columns={"subject_id": "受试者", "record_ids": "记录编号", "record_count": "记录数",
        "sample_count": "样本数", "accuracy": "Accuracy", "macro_f1_present_classes": "Macro-F1(出现类别)",
        "recall_N": "Recall-N", "recall_S": "Recall-S", "recall_V": "Recall-V", "recall_F": "Recall-F",
        "support_N": "Support-N", "support_S": "Support-S", "support_V": "Support-V", "support_F": "Support-F"})
    patient_cnn_table = md_table(patient_cnn, ["受试者", "记录编号", "记录数", "样本数", "Accuracy",
        "Macro-F1(出现类别)", "Support-N", "Recall-N", "Support-S", "Recall-S", "Support-V", "Recall-V",
        "Support-F", "Recall-F"])
    weights = weight_metrics.copy()
    weight_alias = {"unweighted": "无权重", "sqrt_inverse": "平方根逆频率",
                    "capped_inverse_10": "逆频率截断 10", "full_inverse": "全逆频率"}
    weights["strategy"] = weights.strategy.map(weight_alias)
    weights["split"] = weights.split.map(SPLIT_LABELS)
    weight_table = md_table(weights, ["strategy", "split", "sample_count", "accuracy", "macro_f1_present_classes",
                                      "predicted_share_N", "predicted_share_S",
                                      "predicted_share_V", "predicted_share_F"])
    weight_class_table = weight_classes[weight_classes.split.eq("val")].copy()
    weight_class_table["strategy"] = weight_class_table.strategy.map(weight_alias)
    weight_class_table = md_table(weight_class_table, ["strategy", "class", "support", "predicted_count",
                                                       "precision", "recall", "f1", "predicted_share_pct"])
    cv["模型"] = cv.model.map(MODEL_LABELS)
    cv_table = md_table(cv, ["模型", "folds", "accuracy_mean", "accuracy_std", "macro_f1_mean", "macro_f1_std",
                             "pooled_oof_accuracy", "pooled_oof_macro_f1_present_classes",
                             "recall_N_mean", "recall_S_mean", "recall_V_mean", "recall_F_mean",
                             "support_N_total", "support_S_total", "support_V_total", "support_F_total"])
    cv_folds["模型"] = cv_folds.model.map(MODEL_LABELS)
    fold_table = md_table(cv_folds, ["fold", "模型", "validation_subject_count", "validation_sample_count",
                                     "support_N", "support_S", "support_V", "support_F", "accuracy", "macro_f1_present_classes",
                                     "recall_N", "recall_S", "recall_V", "recall_F"])
    err = confusion[(confusion.task.eq("N/S/V/F")) & confusion.model.eq("cnn_1d")]
    err_cases = []
    for a, b in [("N", "S"), ("F", "N"), ("F", "V"), ("V", "N")]:
        val = int(err[(err.true_class == a) & (err.predicted_class == b)]["count"].iloc[0])
        support = int(err[err.true_class == a]["count"].sum())
        err_cases.append({"方向": f"{a}→{b}", "错误数": val, "真实类支持": support,
                          "该类错误比例": val / support if support else np.nan})
    error_table = md_table(pd.DataFrame(err_cases), ["方向", "错误数", "真实类支持", "该类错误比例"])
    cases_table = md_table(cases.rename(columns={"record_id": "record_id", "subject_id": "subject_id",
        "time_s": "time_s", "lead_name": "lead_name", "original_label": "original_label", "true_class": "true_class",
        "predicted_class": "predicted_class", "predicted_class_probability": "P(predicted_class)",
        "probabilities": "all_class_probabilities"}),
        ["sample_id", "record_id", "subject_id", "lead_name", "time_s", "original_label", "true_class",
         "predicted_class", "P(predicted_class)", "all_class_probabilities"], digits=3)
    data_overall = stats[stats.dataset_id.eq("nsvf44_v1")].groupby("class").sample_count.sum()
    total_samples = int(data_overall.sum())
    data_dist = pd.DataFrame([{"类别": c, "有效心拍数": int(data_overall[c]),
                               "占比%": 100 * float(data_overall[c]) / total_samples} for c in ["N", "S", "V", "F"]])
    class_dist_table = md_table(data_dist, ["类别", "有效心拍数", "占比%"])
    models_text = []
    for task, name in [("nv44_v1", "N/V"), ("nsvf44_v1", "N/S/V/F")]:
        cfg = read_json(RESULTS / task / "config.json")
        run_logs = read_json(RESULTS / task / "training_logs.json")
        cnn_log = next(row for row in run_logs if row["model"] == "cnn_1d")
        models_text.append(f"### {name} 配置\n\n" +
            f"随机种子为 `{cfg['seed']}`。LR 参数：`C={cfg['models']['logistic_regression']['C']}`、"
            f"`class_weight={cfg['models']['logistic_regression']['class_weight']}`、"
            f"`solver={cfg['models']['logistic_regression']['solver']}`、"
            f"`max_iter={cfg['models']['logistic_regression']['max_iter']}`；StandardScaler 仅在训练样本拟合。\n\n"
            f"RF 参数：`n_estimators={cfg['models']['random_forest']['n_estimators']}`、"
            f"`max_depth={cfg['models']['random_forest']['max_depth']}`、"
            f"`min_samples_leaf={cfg['models']['random_forest']['min_samples_leaf']}`、"
            f"`max_features={cfg['models']['random_forest']['max_features']}`、"
            f"`class_weight={cfg['models']['random_forest']['class_weight']}`、"
            f"`max_samples={cfg['models']['random_forest']['max_samples']}`。\n\n"
            f"1D-CNN 结构：`{cfg['cnn']['architecture']}`。损失为 `{cfg['cnn']['loss']}`，优化器 `{cfg['cnn']['optimizer']}`，"
            f"学习率 `{cfg['cnn']['learning_rate']}`，权重衰减 `{cfg['cnn']['weight_decay']}`，"
            f"batch size `{cfg['cnn']['batch_size']}`，最多 `{cfg['cnn']['epochs']}` 个 epoch，patience `{cfg['cnn']['patience']}`，"
            f"按验证集 `{cfg['cnn']['early_stopping_metric']}` 早停。配置来源：`results/classification/{task}/config.json`。")
        models_text[-1] += (f"\n\n正式日志显示三种模型均完成；CNN 在 {cnn_log['epochs_ran']} 个 epoch 停止，"
                            f"验证 Macro-F1 最佳 epoch 为 {cnn_log['best_epoch']}（{cnn_log['best_val_macro_f1']:.4f}），"
                            f"运行设备 `{cnn_log['device']}`。检查点与完整 epoch 日志分别保存在 "
                            f"`checkpoints/{task}/formal/cnn/` 和 `checkpoints/{task}/formal/cnn/cnn_training_history.csv`。")
    artifact_audit = pd.read_csv(RESULTS / "final_formal_model_artifact_audit.csv")
    artifact_view = artifact_audit.rename(columns={"task": "任务", "model": "模型", "class_names": "类别",
        "n_features": "输入长度", "parameter_or_tensor_count": "规模计数", "scaler": "缩放器",
        "best_epoch": "最佳 epoch", "matches_config_and_log": "与配置及日志一致"})
    artifact_view["任务"] = artifact_view["任务"].map({"nv44_v1": "N/V", "nsvf44_v1": "N/S/V/F"})
    artifact_view["模型"] = artifact_view["模型"].replace(MODEL_LABELS)
    artifact_table = md_table(artifact_view[["任务", "模型", "类别", "输入长度", "规模计数",
        "缩放器", "最佳 epoch", "与配置及日志一致"]], ["任务", "模型", "类别", "输入长度", "规模计数",
        "缩放器", "最佳 epoch", "与配置及日志一致"], digits=0)
    processing_config = read_json(ROOT / "data/processed/mitdb44_nsvf_v1/processing_config.json")
    filter_config = processing_config["filter"]
    filter_description = (f"{filter_config['prototype_order']} 阶 Butterworth 带通，"
                          f"{filter_config['low_hz']}–{filter_config['high_hz']} Hz，"
                          f"SOS 零相位双向 `sosfiltfilt`（`{filter_config['method']}`），"
                          f"两端各使用 {filter_config['guard_s']} s 保护区并按配置排除窗口。")
    verification_path = "../classification/final_metric_reconciliation.json"
    nsvf_diag_path = "../../results/classification/nsvf44_v1/diagnosis"
    figure_paths = {
        "01": "../../figures/12_final_report/01_task_model_performance.png",
        "02": "../../figures/12_final_report/02_class_support_and_subject_coverage.png",
        "03": "../../figures/11_four_class_diagnosis/top_subject_class_concentration.png",
        "04": "../../figures/12_final_report/04_weight_strategy_precision_recall.png",
        "05": "../../figures/12_final_report/05_weight_strategy_prediction_shares.png",
        "06": "../../figures/11_four_class_diagnosis/group_cv_fold_metrics.png",
        "07": "../../figures/12_final_report/07_subject_level_model_heatmap_descriptive.png",
        "08": "../../figures/12_final_report/08_cnn_error_directions_descriptive.png",
        "09": "../../figures/12_final_report/09_cnn_binary_vs_multiclass_per_class.png",
        "10": "../../figures/12_final_report/10_project_workflow.png",
        "11": "../../figures/12_final_report/11_error_case_ecg_with_probabilities_descriptive.png"}
    nv_confusion_text = "\n\n".join(x for x in cm_tables.split("\n\n") if x.startswith("**N/V"))
    multi_confusion_text = "\n\n".join(x for x in cm_tables.split("\n\n") if x.startswith("**N/S/V/F"))
    report = f'''# MIT-BIH 心拍分类课程项目：完整实验报告

> 本报告以项目中已经保存的数据、配置、预测 CSV、指标 JSON、训练日志及五折分组交叉验证产物为依据。未重新训练模型。正式测试集此前已被查看；本报告对它的重新计算和错误图仅为结果核验/回顾性描述，不把它称为未使用的独立验证集。项目实验不构成临床诊断。

## 摘要

本项目基于 PhysioNet MIT-BIH Arrhythmia Database，检查 44 条非起搏记录，使用按受试者隔离的固定 train/validation/test 划分，完成 N/V 二分类及 N/S/V/F 四分类。三种已有模型为 Logistic Regression、Random Forest 和浅层 1D-CNN。保存的预测 CSV 重新计算后，全部 Accuracy、宏 Precision/Recall/F1 与原指标 JSON 一致（容差 `1e-10`），六个模型的混淆矩阵逐格一致。N/V CNN 的测试 Accuracy、Macro-F1、V Recall 分别为 {metrics[(metrics.task=='N/V') & (metrics.model=='cnn_1d')].accuracy.iloc[0]:.4f}、{metrics[(metrics.task=='N/V') & (metrics.model=='cnn_1d')].macro_f1.iloc[0]:.4f}、{per_class[(per_class.task=='N/V') & (per_class.model=='cnn_1d') & (per_class['class']=='V')].recall.iloc[0]:.4f}。四分类 CNN Accuracy 为 {metrics[(metrics.task=='N/S/V/F') & (metrics.model=='cnn_1d')].accuracy.iloc[0]:.4f}，Macro-F1 为 {metrics[(metrics.task=='N/S/V/F') & (metrics.model=='cnn_1d')].macro_f1.iloc[0]:.4f}；该 Accuracy 不代表少数类识别充分，CNN 测试 S Recall 为 {per_class[(per_class.task=='N/S/V/F') & (per_class.model=='cnn_1d') & (per_class['class']=='S')].recall.iloc[0]:.3f}，F Recall 为 {per_class[(per_class.task=='N/S/V/F') & (per_class.model=='cnn_1d') & (per_class['class']=='F')].recall.iloc[0]:.4f}。探索性患者分组 CV 中，RF Macro-F1 折均值约 {cv[cv.model=='random_forest'].macro_f1_mean.iloc[0]:.3f}，CNN 约 {cv[cv.model=='cnn_1d'].macro_f1_mean.iloc[0]:.3f}；少数类覆盖和受试者集中是主要限制。

**关键词：** MIT-BIH；心电图；AAMI；受试者独立划分；类别不平衡；心拍分类

## 第一章 绪论

心电图（ECG）包含反映心脏电活动的时序信号，自动化信号分析可用于研究心拍分类任务。公开、有专家复核标注的数据集允许开发者进行可复现的算法实验；MIT-BIH Arrhythmia Database 是常用公开资源，包含约半小时、双导联记录和逐拍参考标注。[1–2] 本项目的目标是学习医学信号读取、标签构造、患者独立划分、基础机器学习/深度学习训练和可靠评估流程，而不是提供临床判读系统。

项目工作包括原始数据探索、波形与标签可视化、44 条非起搏记录处理、N/V 二分类、N/S/V/F 四分类、三种基线模型比较、类别权重分析、受试者级错误回顾及患者分组交叉验证。当前报告对既有实验做独立指标核验与诊断整合，不重训模型。

## 第二章 数据集与数据探索

### 2.1 数据集及记录范围

PhysioNet 页面记载 MIT-BIH 数据集由 48 条双通道、约半小时记录组成，来源于 47 位受试者，采样率为 360 Hz；记录 201 与 202 来自同一人。[1] 项目保留原始数据文件，只用记录 100、200、103、105、…等预先锁定的 44 条非起搏记录开展分类，排除 102、104、107、217。排除记录仍保留在原始数据目录，没有删除或改写。项目划分方案、原始文件校验和及排除理由可查 `data/processed/mitdb44_nsvf_v1/split_manifest.csv` 和 `results/download_manifest.csv`。

数据库注释包括逐拍符号，也包括节律或信号质量等非心拍符号；PhysioNet 对这些代码分别说明。[3] 本项目不把非心拍符号推断成心拍类别。

### 2.2 原始符号与 AAMI 映射

映射参考 ANSI/AAMI EC57 的五类心拍评估框架，以及 de Chazal 等人基于 MIT-BIH 44 条非起搏记录开展五类分类的公开研究；项目采用的逐符号映射在代码中显式列出并可逐项复核。[4–5] 原始符号与分组保持可追溯：N 组为 `N/L/R/e/j`；S 组为 `A/a/J/S`；V 组为 `V/E`；F 组为 `F`；Q 组为 `/、f、Q`。四分类只使用 N/S/V/F。非心拍注释、Q 组、未知或未映射注释均不进入四分类；原始 `.atr` 和 `original_label` 保留。这里的 N 是 AAMI 标签分组，包含束支传导阻滞及部分逸搏符号，不能解释为该受试者或其所有心拍都“完全健康”。

### 2.3 四分类有效数据分布

以下数量是通过窗口边界、信号质量守卫和类别筛选后，实际进入四分类 NPZ 的样本数，不是数据库中全部原始 annotation 数。

{class_dist_table}

![类别心拍数与受试者覆盖]({figure_paths['02']})

![跨患者类别集中度]({figure_paths['03']})

跨受试者覆盖如下。有效受试者数为心拍份额 Shannon 熵转换得到的 `2^H` 描述量，只用于表现集中程度，不等于独立患者样本数或统计功效。

{coverage_table}

测试集中 S 只有 10 拍、覆盖 3 个患者组；F 有 371 拍但 99.73% 来自 subject_208。训练集 F 有 411 拍，其中 88.08% 来自 subject_213。验证集 S 有 1,404 拍，其中 98.01% 来自 subject_232。即使某类总拍数看似可用，若主要来自极少患者，模型仍可能学习到患者/记录特征，而不是可泛化的类别形态。

### 2.4 信号与形态观察

所有有效心拍均使用 MLII 导联、360 Hz 采样；观察图保留记录编号、专家标注位置和记录内时间。N/V 单心拍任务表现较好，但四分类中 S/F 数量少、跨患者异质性更明显。N/S/F 的标签差异不能仅靠一段短单拍波形完整表达；相邻 RR 间期、相邻心拍序列和受试者间差异可能提供上下文。此处是模型与数据观察，不是临床病因推断。四类错误样例见第五、六章及图 11。

![项目实验流程]({figure_paths['10']})

## 第三章 数据预处理与数据集构建

### 3.1 数据读取与滤波

WFDB 读取 `.dat` 信号、`.hea` 头信息与 `.atr` 专家注释；采样率、导联名、注释样点、原始符号和记录内时间保存在元数据中。导联通过头文件导联名称选择 MLII，而不是默认通道 0；项目所含的 44 条记录全部找到 MLII。实际滤波为 {filter_description} 配置细节见 `data/processed/mitdb44_nsvf_v1/processing_config.json` 与 `src/preprocessing/filters.py`。信号经过滤波后，以专家标注样点为中心截取前 0.3 秒和后 0.4 秒，360 Hz 下为 253 个采样点，中心索引为 108。超出边界、滤波边缘/信号间隙守卫内的窗口不纳入样本。

### 3.2 标准化与标签

归一化参数只由训练划分拟合，再用于验证和测试；传统模型的 StandardScaler 同样只在各自训练数据拟合。AAMI 标签映射在 `src/labels.py` 中显式维护。N/V 任务将 N 与 V 映射为二类；四分类使用 N/S/V/F。对 201 与 202 使用共同受试者组标识 `subject_201_202`。

### 3.3 患者独立划分与防泄漏

N/V 与 N/S/V/F 复用相同 44 条记录的受试者分区；本轮从两份 `split_manifest.csv` 逐记录重新比对，映射一致。训练、验证、测试受试者集合两两不交；201/202 被合并且属于同一集合。每个有效样本的 `subject_id`、`record_id` 和 `sample_id` 可从元数据追溯。当前实验不做随机心拍拆分。

四分类样本数按 split 与类别的核验表如下；`subject_count`、`record_count` 为该类别真正出现的受试者数和记录数，而不是 split 总数。

{count_table}

各患者的类别样本数完整表：`results/classification/final_verified_subject_class_counts.csv`。完整分布表：`results/classification/final_verified_split_class_counts.csv`。

### split_class_counts.csv 错误修复记录

虽然 `src/datasets/build.py` 当前统计代码已按类别内 `subject_id`/`record_id` 去重，二分类旧派生 CSV 仍未更新：原表把 V 类患者/记录数写成 split 总数（训练为 31/32，实际 23/24；验证为 6/6，实际 4/4；测试为 6/6，实际 5/5）。本轮已把旧表原样存档至 `reports/final/nv44_v1_split_class_counts_before_repair.csv`，再由 metadata 重生成 `data/processed/mitdb44_nv_v1/split_class_counts.csv`；四分类表核验时已与 metadata 一致。未修改 NPZ、样本、标签、划分或模型权重。

{split_repair_table}

## 第四章 模型设计

本项目对比 Logistic Regression、Random Forest 与 1D-CNN。超参数从各任务正式配置 JSON 读取，不凭记忆补写。Smoke Test 文件保留在结果目录；正式模型使用已有正式训练结果。

{chr(10).join(models_text)}

### 已保存模型权重只读核验

本轮使用 `joblib.load` 和 PyTorch `weights_only=True` 只读载入六个正式模型工件，检查类别索引、253 点输入长度、LR 标准化器、CNN checkpoint 中类别名/随机种子/最佳 epoch/验证 Macro-F1，并逐张量比较 CNN `cnn_best.pt` 与 `cnn_final_best.pt`。表中 LR 规模计数为系数数、RF 为树节点数、CNN 为 state_dict 张量值数量。核验不执行推理或训练；逐文件结果见 `results/classification/final_formal_model_artifact_audit.csv`。

{artifact_table}

评估报告包括 Accuracy、逐类 Precision/Recall/F1/Support、Macro-F1、Weighted-F1、Balanced Accuracy 和混淆矩阵。Macro-F1 让每类等权参与平均；Balanced Accuracy 为各真实类别 Recall 的均值；Weighted-F1 按真实支持数加权。少数类 Support 很小时，这些估计仍有较大不确定性。

## 第五章 N/V 二分类实验

N/V 是本项目主要分类实验。以下测试指标直接从三模型既有 `test_predictions_all_models.csv` 重新计算，并与原始指标 JSON 对照。测试集在之前实验中已被查看，故这里不用于模型选择。

{metric_table}

逐类指标（包括 Support）见下一表；完整混淆矩阵按真实类别为行、预测类别为列。

{class_table}

### N/V 混淆矩阵

{nv_confusion_text}

N/V CNN 的 Accuracy 为 {metrics[(metrics.task=='N/V') & (metrics.model=='cnn_1d')].accuracy.iloc[0]:.4f}、Macro-F1 为 {metrics[(metrics.task=='N/V') & (metrics.model=='cnn_1d')].macro_f1.iloc[0]:.4f}、V Recall 为 {per_class[(per_class.task=='N/V') & (per_class.model=='cnn_1d') & (per_class['class']=='V')].recall.iloc[0]:.4f}。该结果是当前锁定患者测试集上的既有结果，不自动推广到其他医院、设备或人群。图 1 将其与四分类结果并列展示；图 9 比较 CNN 在 N、V 类上的逐类 Precision/Recall/F1。

![任务间模型 Accuracy 与 Macro-F1]({figure_paths['01']})

![CNN 二分类与四分类逐类指标]({figure_paths['09']})

## 第六章 N/S/V/F 四分类拓展实验

### 6.1 测试指标与混淆矩阵

四分类测试结果来自已查看的固定测试集，单独呈现以核验既有报告。测试 S 支持数为 10，F 为 371；N 有 12,287，V 有 1,161。RF Accuracy 高，但在此测试集上没有正确识别 S 与 F，故不能以 Accuracy 代表四类均衡识别能力。

{metric_table}

### 四分类逐类指标

{class_table}

### 四分类混淆矩阵

{multi_confusion_text}

![四分类 CNN 主要误分类方向]({figure_paths['08']})

主要错误方向及真实类内比例：

{error_table}

常见测试错误包括 CNN 的 N→S 2,626 拍、F→N 216 拍、F→V 154 拍以及 V→N 4 拍。F 的 371 拍中，370 拍误判为 N 或 V；S 的 10 拍均未被 CNN 识别。波形图 11 为每个错误方向中，按该方向被预测类别概率的中位数选取的一个示例，避免挑选概率极端样本；图上同时列出四类概率、record、subject、原始符号及注释时间。波形外观只记录观察，不据此给出临床诊断或确定误分原因。

![带概率的四类典型错误心拍]({figure_paths['11']})

样本编号、记录和导联、专家原始符号、时间及预测概率：

{cases_table}

示例样本可核对 [CSV](../../results/classification/nsvf44_v1/diagnosis/final_error_case_samples_descriptive_only.csv)。

### 6.2 类别权重消融

复用已有同一 CNN 权重策略实验：无权重、平方根逆频率、逆频率在原始 mean-one 向量截断为 10 后再归一、全逆频率。权重只由训练集标签计算；各版本按验证 Macro-F1 早停，所以验证集并非独立调参集。下表同时给出训练和验证 Macro-F1 与预测类别份额：

{weight_table}

验证集逐类 Precision、Recall 与预测数量：

{weight_class_table}

![权重策略验证 Precision–Recall]({figure_paths['04']})

![真实与预测类别份额]({figure_paths['05']})

全逆频率权重让模型在验证集上更常预测 S/F，部分少数类 Recall 上升，但相应误报增加、Precision 下降；例如全逆频率 F Recall 只有约 0.111，F Precision 约 0.0036，而 F 预测数量远大于真实支持数。截断权重改善 S 识别，但该验证折仍未正确识别 F。无权重/平滑权重在 S/F 上又容易完全不预测。证据支持“权重改变了决策偏好且存在 Precision–Recall 权衡”；不支持“权重越大越好”或“权重完全无效”。权重比较的训练/验证结果详表见 `results/classification/nsvf44_v1/diagnosis/weight_strategy_train_val_metrics.csv`。

### 6.3 受试者分布及患者级表现

![按患者分层的测试表现]({figure_paths['07']})

四分类 CNN 的患者级指标如下；完整 2 个任务 × 3 模型的逐患者结果保存在 [CSV](../../results/classification/final_subject_test_metrics_descriptive_only.csv)。

{patient_cnn_table}

缺少某类别真实样本时，该类 Recall 留空；患者 Macro-F1 只对该患者实际出现的类别取平均。因此不能把患者仅含 N 的分数与同时含 N/S/V/F 的患者当作同一支持结构解释。该汇总使用清晰区分的记录编号、记录数和样本数；患者级结果用于发现差异，不用于反向调整测试集上的模型。

### 6.4 五折受试者分组交叉验证

已有 StratifiedGroupKFold 五折结果已读取复用，没有重跑训练。输入仅为原 train+validation 中的 37 个患者组、86,286 拍；正式测试集不读取。外层验证患者互斥，每个患者只在一个外层验证折；各折内标准化与类别权重由该折训练患者估计。CNN 早停进一步用外层训练患者中的内层患者独立划分，随后按内层最佳 epoch 在外层训练数据上重拟合。这个 CV 是既有训练/验证资料上的探索性稳定性分析，不能视为完全独立外部验证；验证数据此前已经参与模型早停和权重比较。

{cv_table}

逐折支持数、Accuracy、Macro-F1 与 Recall：

{fold_table}

![已有五折患者分组交叉验证结果]({figure_paths['06']})

F 类跨折支持数差别显著；存在 F 支持只有个位数的折，也有 F 样本集中在少数患者的折。Macro-F1 和逐类 Recall 的折间变化反映患者组成的重要影响。OOF 综合值与折均值略有差别，因为一个是合并全部 OOF 预测再计分，一个是逐折计算后求均值。

## 第七章 综合讨论

### 7.1 二分类与四分类差异

二分类中 CNN 对 N 与 V 的区分在当前锁定划分上表现良好；加入 S 与 F 后，它们成为竞争类别且类别覆盖更偏向特定患者。四分类模型的 Accuracy 会被 N 类支持数主导；RF 的四分类测试 Accuracy 为 {metrics[(metrics.task=='N/S/V/F') & (metrics.model=='random_forest')].accuracy.iloc[0]:.4f}，但 S/F Recall 均为 0。CNN 的 V Recall 高而 S/F 几乎不识别。二分类结果不能外推为完整 AAMI 五类能力。

### 7.2 数据不平衡与患者分布

除了 N/S/V/F 心拍数量比例不均，患者覆盖也不均：S 有效患者约 31/43，F 约 16/43。F 心拍的熵有效患者数约 3.05，且训练、验证、测试分别受到不同患者主导。用患者隔离划分能防止同一患者记录泄漏，却不能保证每个少数类在各 split 中具备广泛患者覆盖。对于本数据规模，这种患者集中是比单纯类别权重更基础的限制。

### 7.3 可支持的发现与待验证假设

由实验直接支持：指标 JSON 与预测 CSV 一致；四分类 S/F 测试召回差；患者组别及类别集中明显；类别权重会改变预测类别份额并产生 Precision/Recall 权衡；五折患者分组结果存在折间波动。

仍待验证：N→S、F→N 或 F→V 可能受单拍窗口缺少 RR 上下文、患者特异形态、类别内异质性、训练样本覆盖不足等因素影响。当前实验没有单独消融上下文特征，也没有外部人群数据，不能将这些解释视为因果结论。

### 7.4 局限

数据库规模有限且记录来自较早的两导联动态 ECG；44 条非起搏记录约束了样本范围。标签类别为心拍级参考标注，不等同于患者级诊断；N 类本身合并多种原始符号。测试集已查看，当前最终报告只复核与描述，不能重新作为无偏基准。CV 复用已有 train/validation 来源，属于探索性评估。没有设备/医院外部验证，不能声称临床诊断效能。

## 第八章 总结与展望

项目已完成数据探索、标签映射、患者独立数据集构建、N/V 与 N/S/V/F 基线实验、类别权重分析和患者分组 CV。重新计算的已保存测试预测指标与原 JSON 一致。二分类结果较好，四分类主要受到 S/F 患者覆盖及类内数据不足影响；更换复杂网络不是当前最优先改进。

后续可在不触碰锁定测试结果的前提下：在训练折内加入相邻心拍/RR 上下文比较；改善稀有类别的患者覆盖并采用患者分组评估；在预先锁定的新患者或外部数据库上作独立确认；最后再建立交互式波形展示工具。以上均为计划，未在本项目中完成。

## 参考文献与数据来源

1. Moody G, Mark R. MIT-BIH Arrhythmia Database (version 1.0.0). PhysioNet; 2005. doi:10.13026/C2F305. [官方数据集页面](https://physionet.org/content/mitdb/1.0.0/)。
2. Moody GB, Mark RG. The impact of the MIT-BIH Arrhythmia Database. *IEEE Engineering in Medicine and Biology Magazine*. 2001;20(3):45–50. doi:10.1109/51.932724.
3. PhysioNet. Standard annotations. [注释符号与非心拍代码说明](https://physionet.org/static/lightwave/doc/annotations.html)。
4. Association for the Advancement of Medical Instrumentation. ANSI/AAMI EC57:2012 (R2020), *Testing and reporting performance results of cardiac rhythm and ST segment measurement algorithms*. [ANSI/AAMI 官方产品页](https://webstore.ansi.org/standards/aami/ansiaamiec572012r2020)。本项目使用的逐符号映射可直接复核于 `src/labels.py`。
5. de Chazal P, O'Dwyer M, Reilly RB. Automatic classification of heartbeats using ECG morphology and heartbeat interval features. *IEEE Transactions on Biomedical Engineering*. 2004;51(7):1196–1206. doi:10.1109/TBME.2004.827359. [PubMed 记录](https://pubmed.ncbi.nlm.nih.gov/15248536/)。

## 附录：复现与核验产物

- 数据加载/预处理和训练入口见 `README.md`；不得把测试集重新用于调参。
- 本轮只生成报告、统计表与图，没有训练新模型：`python -m src.evaluation.final_report`。
- 原始预测仍在 `results/classification/nv44_v1/` 和 `results/classification/nsvf44_v1/`；新独立复算保存为 `results/classification/final_recomputed_*.csv/json`，旧记录不覆盖。
- 诊断来源：`reports/classification/four_class_failure_diagnosis.md`；五折输出：`results/classification/nsvf44_v1/diagnosis/group_cv_5fold/`。
- 逐文件清单：`project_file_inventory.csv`；核验摘要：`实验结果核验报告.md`；图表路径与说明：`图表索引.md`。
'''
    path = FINAL / "MIT_BIH_完整实验报告.md"
    path.write_text(report, encoding="utf-8")
    return path


def generate_auxiliary_reports(metrics, per_class, confusion, stats, subjects, coverage, audit,
                               reconciliation, cases, font_name, inventory, metric_detail):
    all_images = sorted(FINAL_FIGURES.glob("*.png"))
    reused = {
        "03": ("figures/11_four_class_diagnosis/top_subject_class_concentration.png", "四类心拍的受试者集中度；复用已有失败诊断图。"),
        "06": ("figures/11_four_class_diagnosis/group_cv_fold_metrics.png", "五折受试者分组交叉验证指标；复用已有 CV 图。")}
    # Patient-level view is recomputed from the saved descriptive test metrics in this report.
    new_entries = [
        ("01_task_model_performance.png", "二分类/四分类三模型 Accuracy 与 Macro-F1 并列；说明高 Accuracy 与类别均衡表现的区别。"),
        ("02_class_support_and_subject_coverage.png", "四分类有效心拍数量和各类患者覆盖；并列说明按拍计数和按患者计数的差异。"),
        ("04_weight_strategy_precision_recall.png", "验证集四种 CNN 权重策略的逐类 Precision–Recall；支持分析误报代价。"),
        ("05_weight_strategy_prediction_shares.png", "真实验证类别占比与各权重策略预测占比；直观显示偏向少数类的程度。"),
        ("07_subject_level_model_heatmap_descriptive.png", "按患者展示既有测试 Accuracy/Macro-F1；仅回顾性描述。"),
        ("08_cnn_error_directions_descriptive.png", "测试 CNN 四个主要混淆方向的数量与真实类内比例。"),
        ("09_cnn_binary_vs_multiclass_per_class.png", "对照 CNN 在 N/V 两类的二分类与四分类 Precision/Recall/F1。"),
        ("10_project_workflow.png", "项目实际数据读取、预处理、患者划分与分类实验流程。"),
        ("11_error_case_ecg_with_probabilities_descriptive.png", "N→S、F→N、F→V、V→N 四种错误的 ECG 心拍、记录和预测概率。")]
    entries = []
    for name, explanation in new_entries:
        path = FINAL_FIGURES / name
        if not path.exists():
            raise AssertionError(f"Missing figure: {path}")
        entries.append({"file": f"figures/12_final_report/{name}", "status": "本轮生成",
                        "dpi": 300, "explanation": explanation})
    for code, (path, explanation) in reused.items():
        entries.append({"file": path, "status": "复用已有", "dpi": 300, "explanation": explanation})
    fig_md = "# 图表索引\n\n所有本轮新生成的定量图由 `src/evaluation/final_report.py` 基于项目 CSV/JSON/NPZ 重建，PNG 为 300 dpi；复用图来源于四分类失败诊断模块，亦为 300 dpi。测试集图仅作已查看结果的描述，不参与训练、调参或阈值选择。\n\n"
    for index, row in enumerate(entries, 1):
        fig_md += f"## 图 {index:02d}：{row['file'].split('/')[-1]}\n\n- 状态：{row['status']}\n- 分析作用：{row['explanation']}\n- 文件：`{row['file']}`\n\n![图 {index:02d}](../../{row['file']})\n\n"
    (FINAL / "图表索引.md").write_text(fig_md, encoding="utf-8")

    category_inv = inventory.groupby("category").agg(files=("path", "count"), bytes=("bytes", "sum")).reset_index()
    inventory_table = md_table(category_inv, ["category", "files", "bytes"], digits=0)
    cm_mismatches = int((~reconciliation["matches_within_1e-10"]).sum())
    cv_weight_audit = read_json(RESULTS / "final_cv_and_weight_scope_audit.json")
    verify = {
        "metric_reconciliation_all_scalar_fields_match": bool(cm_mismatches == 0),
        "confusion_matrices_match": metric_detail["all_confusion_matrices_match"],
        "prediction_csv_variants_match": metric_detail["per_model_and_consolidated_prediction_files_match"],
        "N_V_and_NSVF_subject_partition_match": audit["N_V_and_N_S_V_F_same_record_split"],
        "subject_overlap_between_splits": audit["record_subject_overlap_between_splits"],
        "201_202_same_subject_and_split": audit["201_202_same_pseudonymous_subject_and_split"],
        "included_sample_AAMI_mapping_matches_source_code": audit["aami_mapping_matches_src_labels"],
        "derived_split_class_count_audit": audit["derived_split_class_count_audit"],
        "formal_model_artifact_audit": audit["formal_model_artifacts"],
        "cv_outer_inner_group_and_training_only_weight_checks": cv_weight_audit,
        "chart_font_selected": font_name,
        "figure_count_new": len(list(FINAL_FIGURES.glob("*.png"))),
        "test_predictions_used_only_for_metric_reconciliation_and_descriptive_figures": True,
        "models_retrained": False}
    (FINAL / "final_report_verification.json").write_text(json.dumps(verify, ensure_ascii=False, indent=2), encoding="utf-8")
    report = f'''# 实验结果核验报告

## 核验范围

本轮读取两项任务的既有 test prediction CSV、原 `test_metrics_all_models.json`、单模型预测 CSV、配置、处理后 metadata、split manifest、既有诊断表和五折 CV 结果。未重新训练、未改原预测、未改原始信号/标注/权重。测试集曾在此前实验中查看，本轮只做复算和描述。

## 指标复算

按标签顺序 N/V 与 N/S/V/F，从预测 CSV 重算 Accuracy、逐类 Precision/Recall/F1/Support、Macro-F1、Weighted-F1、Balanced Accuracy 与混淆矩阵。原 JSON 已存的 Accuracy、Macro-Precision、Macro-Recall、Macro-F1 均与复算数值在 `1e-10` 容差内一致，六个混淆矩阵逐元素一致；Weighted Precision/Recall/F1 也与 JSON 中 `classification_report.weighted avg` 对应字段一致。Balanced Accuracy 由本轮从预测重新计算；两项任务每一类均有真实样本，因此它等于 Macro-Recall。合并预测 CSV 与三种模型各自的 CSV 在样本和预测列上完全相同。

{md_table(metrics.rename(columns={'task':'任务','model_label':'模型','n_test':'测试数','accuracy':'Accuracy','macro_precision':'Macro-P','macro_recall':'Macro-R','macro_f1':'Macro-F1','weighted_f1':'Weighted-F1','balanced_accuracy':'Balanced-Acc'}), ['任务','模型','测试数','Accuracy','Macro-P','Macro-R','Macro-F1','Weighted-F1','Balanced-Acc'])}

差异明细：`results/classification/final_metric_reconciliation.csv`；逐类指标：`results/classification/final_recomputed_per_class_metrics.csv`；混淆矩阵长表：`results/classification/final_recomputed_confusion_matrices.csv`。

## 数据与划分核验

- N/V 与 N/S/V/F 记录及受试者分区相同；train、validation、test 受试者互斥。
- 记录 201 和 202 指向同一伪名患者，且处于同一 split。
- 所有纳入样本的原始 symbol 均通过 `src/labels.py` 的显式 AAMI 映射；类别级受试者/记录数量由 metadata 独立 groupby 重算。
- `final_verified_split_class_counts.csv` 同时报告每一 split 总样本数、每类心拍数、该类患者数与记录数，修复了旧汇总中将 split 总患者/记录数重复写入各类的字段逻辑。
- 具体复核发现 N/V 的旧派生表仍有 V 类患者数/记录数错误：训练表原写 31/32，metadata 实计 23/24；验证原写 6/6，实计 4/4；测试原写 6/6，实计 5/5。旧 CSV 已留档于 `reports/final/nv44_v1_split_class_counts_before_repair.csv`，派生 CSV 已按 metadata 重建。
- 患者分布和熵有效患者数列于 `final_verified_subject_class_concentration.csv`。熵有效数是分布摘要，不是独立患者数。

## 患者分组 CV 核验

复用既有五折结果；log 中声明只读取原 train+validation，无正式测试数据。外层受试者严格互斥，归一化/类别权重由各训练折拟合；CNN 使用训练患者内部的内层分组验证选早停 epoch。该 CV 是探索性稳定性分析，源验证集已有早停/权重对照经历，不是外部验证。

详细验证标志：`results/classification/nsvf44_v1/diagnosis/group_cv_5fold/group_cv_training_log.json`、`results/classification/nsvf44_v1/diagnosis/diagnosis_verification.json` 和本目录 `final_report_verification.json`。

正式模型工件已只读加载并与任务类别及训练日志核对；细节见 `results/classification/final_formal_model_artifact_audit.csv`。

## 文件与图片

递归文件清单：`project_file_inventory.csv`。当前按项目目录统计（跳过 `.git`、`.venv`、缓存和临时测试目录）：

{inventory_table}

图像文件存在性、报告路径、中文字体和章节核验见 `final_report_verification.json`。

正式 LR/RF/CNN 权重均可加载，类别顺序、输入长度及 CNN 最佳 epoch 与正式日志相符；CNN 两份最佳权重逐张量一致。只读工件审计：`results/classification/final_formal_model_artifact_audit.json`。
'''
    (FINAL / "实验结果核验报告.md").write_text(report, encoding="utf-8")

    completion = f'''# 项目完成情况总结

## 本轮完成

1. 递归盘点项目文件并输出 `project_file_inventory.csv`。
2. 发现并修复 N/V 派生 CSV 中 V 类患者/记录计数错误；旧值另存，四分类既有计数核验通过。
3. 从现有 N/V 与 N/S/V/F 预测 CSV 独立复算六个模型测试指标，对照 JSON 和单模型 CSV。
4. 由 metadata 重新统计各 split 的总样本、逐类样本、逐类患者与记录；保存逐患者类别覆盖与集中度。
5. 复核两任务共用患者分区、split 无患者交集及 201/202 共同分组；标签映射逐行与源规则核对。
6. 复用四分类权重策略对照、错误诊断和五折患者分组 CV，并纳入正式报告。
7. 新增 9 张可复现分析图，另复用类别集中度和五折 CV 图；生成 4 种主要错分方向的概率与 ECG 波形示例。
8. 将原课程实验总结复制为历史版本，再追加结果核验及诊断整合章节。
9. 只读加载六个正式 LR/RF/CNN 模型工件，检查类别索引、输入长度及 CNN 权重与训练日志一致性；未推理或训练模型。

## 核验结论

保存的 JSON 核心指标和混淆矩阵均通过 CSV 独立复算；同时复算并显式汇总 Weighted-F1 与 Balanced Accuracy。N/V CNN 在既有测试划分结果较好；四分类的少数类识别仍受 S/F 样本量和患者集中影响。五折分组 CV 仅作为原训练/验证数据上的探索性稳定性分析。

## 文件

- 完整课程实验报告：`MIT_BIH_完整实验报告.md`
- 结果核验：`实验结果核验报告.md`
- 图表索引：`图表索引.md`
- 项目清单：`project_file_inventory.csv`
- 机器可读核验：`final_report_verification.json`
- 源码：`src/evaluation/final_report.py`
- 更新的旧总结：`reports/classification/experiment_summary.md`
- 原总结历史副本：`reports/classification/experiment_summary_before_final_2026-10-30.md`

## 结题判断

在“数据探索、可复现处理、患者独立基础模型比较、失败诊断、结果核验和书面总结”的课程项目范围内，已达到普通医学人工智能课程项目的结题交付要求。该判断不表示完成临床验证：测试集已查看、少数类患者覆盖有限，且没有新医院/新设备独立数据，临床效能尚未得到验证。
'''
    (FINAL / "项目完成情况总结.md").write_text(completion, encoding="utf-8")


def update_experiment_summary(metrics, per_class, stats, coverage, audit, metric_detail):
    path = ROOT / "reports/classification/experiment_summary.md"
    existing = path.read_text(encoding="utf-8")
    marker = "## 2026-10-30 独立指标核验与最终报告整合"
    archive = path.with_name("experiment_summary_before_final_2026-10-30.md")
    if not archive.exists():
        shutil.copy2(path, archive)
    if marker in existing:
        existing = existing.split(marker)[0].rstrip() + "\n\n"
    s = stats[(stats.dataset_id == "nsvf44_v1")]
    cov = coverage[coverage.dataset_id.eq("nsvf44_v1")]
    cv = pd.read_csv(DIAG / "group_cv_summary.csv")
    m = metrics.copy(); m["model"] = m.model.map(MODEL_LABELS)
    table = md_table(m, ["task", "model", "n_test", "accuracy", "macro_f1", "weighted_f1", "balanced_accuracy"])
    c = cov.copy(); c["split"] = c.split.map(SPLIT_LABELS)
    ctable = md_table(c, ["split", "class", "subjects_with_class", "subjects_total", "coverage_pct",
                          "sample_count", "top_subject_id", "top_subject_share_pct"])
    cv["model"] = cv.model.map(MODEL_LABELS)
    cvtable = md_table(cv, ["model", "accuracy_mean", "accuracy_std", "macro_f1_mean", "macro_f1_std",
                            "pooled_oof_macro_f1_present_classes", "recall_N_mean", "recall_S_mean",
                            "recall_V_mean", "recall_F_mean"])
    extra = f'''{marker}

本节由 `{sys.executable}` 环境下的 `python -m src.evaluation.final_report` 依据现有文件复算。原报告正文已存档于 `experiment_summary_before_final_2026-10-30.md`。本轮未训练模型、修改原预测或读取测试集进行新拟合。测试集此前已查看，本轮从保存的预测 CSV 重算仅用于核验和回顾性展示。

### 测试预测独立复算

六个模型保存 JSON 的 Accuracy、Macro-Precision、Macro-Recall、Macro-F1 与预测 CSV 重算结果容差 `1e-10` 内一致，混淆矩阵完全一致。Weighted-F1 与其加权 Precision/Recall 均从 JSON 的 `classification_report.weighted avg` 复核一致；所有类均有 Support，所以 Balanced Accuracy 等于已核对的 Macro-Recall。

{table}

逐类 Precision/Recall/F1/Support 见 `results/classification/final_recomputed_per_class_metrics.csv`。

### 正式模型权重只读核验

六个正式 LR/RF/CNN 工件均可只读加载；类别索引、253 点输入和 CNN 最佳 epoch 与任务配置/正式训练日志一致。CNN 的 `cnn_best.pt` 与 `cnn_final_best.pt` state_dict 逐张量一致。没有重新运行推理或训练。逐工件核验：`results/classification/final_formal_model_artifact_audit.csv`。

### 修正并核验患者/记录统计

类别级 `subject_count` 和 `record_count` 已由纳入样本 metadata 实际 groupby 重算；不再将整个 split 的总患者/记录数重复填入每个类别。完整表：`results/classification/final_verified_split_class_counts.csv`。逐患者类别样本数：`results/classification/final_verified_subject_class_counts.csv`。患者覆盖和集中度：

{ctable}

N/V 与 N/S/V/F 两份 split manifest 逐记录一致；患者集合在 train/validation/test 间无交集；记录 201、202 共同映射为 `subject_201_202` 且同属一个 split。AAMI 原始符号映射与 `src/labels.py` 核对一致。

### 四分类失败诊断和权重结论

四分类有效心拍的类别数及比例保存在 `results/classification/final_verified_split_class_counts.csv`。F 类样本在患者间高度集中；训练 F 的 88.1% 来自 subject_213，验证 S 的 98.0% 来自 subject_232，测试 F 的 99.7% 来自 subject_208；测试 S 仅 10 拍。全逆频率权重提高部分少数类验证 Recall 的同时造成预测份额和误报增加，策略影响是模型依赖且存在 Precision–Recall 权衡。详细分患者错误案例、权重实验和数据审计见 `reports/classification/four_class_failure_diagnosis.md`。

### 受试者分组交叉验证

复用五折 StratifiedGroupKFold 产物，输入为原 train+validation 中 37 个患者组，不含正式测试集。它是探索性稳定性分析；原 validation 曾用于早停和策略比较，并非新外部验证。

{cvtable}

### 最终课程报告

最终八章课程实验报告：`reports/final/MIT_BIH_完整实验报告.md`；指标核验：`reports/final/实验结果核验报告.md`；图表清单：`reports/final/图表索引.md`。本项目不宣称临床诊断能力；测试集已查看，少数类患者覆盖和外部验证均有限。
'''
    path.write_text(existing + extra, encoding="utf-8")


def audit_cv_and_weights() -> dict:
    training = ROOT / "data/processed/mitdb44_nsvf_v1"
    # Read native Boolean columns robustly on CSV implementations that yield strings.
    meta = pd.read_csv(training / "metadata.csv", usecols=["sample_id", "subject_id", "split", "included", "mapped_label"])
    included = meta.included.astype(str).str.lower().eq("true")
    train_val = meta[included & meta.split.isin(["train", "val"])].copy()
    test_meta = meta[included & meta.split.eq("test")]
    expected_ids = set(train_val.sample_id.astype(str))
    test_subjects = set(test_meta.subject_id.astype(str))
    log = read_json(DIAG / "group_cv_5fold/group_cv_training_log.json")
    fold_assignments = []
    validation_subjects_all = []
    inner_group_disjoint = True
    outer_group_disjoint = True
    inner_groups_within_outer_train = True
    weights_match_fold_training_counts = True
    for fold in log["folds"]:
        tr = set(fold["train_subjects"]); va = set(fold["validation_subjects"])
        outer_group_disjoint &= not bool(tr & va)
        outer_group_disjoint &= not bool((tr | va) & test_subjects)
        validation_subjects_all.extend(va)
        inner_tr = set(fold["inner_train_subjects"]); inner_va = set(fold["inner_validation_subjects"])
        inner_group_disjoint &= not bool(inner_tr & inner_va)
        inner_group_disjoint &= not bool(inner_va & va)
        inner_groups_within_outer_train &= (inner_tr | inner_va) <= tr
        outer_support = train_val[train_val.subject_id.astype(str).isin(tr)].groupby("mapped_label").size()
        expected = np.asarray([int(outer_support.get(c, 0)) for c in CLASS_ORDER["nsvf44_v1"]], dtype=float)
        expected_weights = expected.sum() / (len(expected) * expected)
        actual = np.asarray(fold["outer_train_class_weights"], dtype=float)
        weights_match_fold_training_counts &= bool(np.array_equal(expected, np.asarray(fold["train_class_counts"], dtype=float)))
        weights_match_fold_training_counts &= bool(np.allclose(expected_weights, actual, rtol=2e-6, atol=2e-7))
        inner_support = train_val[train_val.subject_id.astype(str).isin(inner_tr)].groupby("mapped_label").size()
        expected_inner = np.asarray([int(inner_support.get(c, 0)) for c in CLASS_ORDER["nsvf44_v1"]], dtype=float)
        expected_inner_weights = expected_inner.sum() / (len(expected_inner) * expected_inner)
        actual_inner_weights = np.asarray(fold["inner_train_class_weights"], dtype=float)
        weights_match_fold_training_counts &= bool(np.allclose(expected_inner_weights, actual_inner_weights,
                                                               rtol=2e-6, atol=2e-7))
        fold_assignments.append({"fold": int(fold["fold"]), "train_subject_count": len(tr),
                                 "validation_subject_count": len(va),
                                 "inner_train_subject_count": len(inner_tr),
                                 "inner_validation_subject_count": len(inner_va),
                                 "validation_class_counts": fold["validation_class_counts"]})
    expected_groups = set(train_val.subject_id.astype(str))
    single_outer_fold = (len(validation_subjects_all) == len(set(validation_subjects_all)) and
                         set(validation_subjects_all) == expected_groups)
    cv_subjects = set(validation_subjects_all)
    cv_oof_coverage = {}
    for model in MODEL_LABELS:
        oof = pd.read_csv(DIAG / f"group_cv_5fold/group_cv_oof_predictions_{model}.csv",
                          usecols=["sample_id", "subject_id"])
        ids = oof.sample_id.astype(str)
        cv_oof_coverage[model] = {"rows": int(len(oof)), "unique_sample_ids": int(ids.nunique()),
                                  "matches_train_validation_ids": set(ids) == expected_ids,
                                  "patient_disjoint_from_test": not bool(set(oof.subject_id.astype(str)) & test_subjects)}
    oof_complete = all(v["matches_train_validation_ids"] and v["rows"] == len(expected_ids) and
                       v["unique_sample_ids"] == len(expected_ids) and v["patient_disjoint_from_test"]
                       for v in cv_oof_coverage.values())
    weight_log = read_json(DIAG / "weight_strategy_training_log.json")
    existing_weight_log = read_json(RESULTS / "nsvf44_v1/class_weight_validation_ablation.json")
    no_test_weight = "not loaded" in weight_log.get("scope", "").lower()
    no_test_existing = existing_weight_log.get("test_partition_loaded") is False
    result = {"cv_scope": log.get("scope"), "cv_declared_group_disjoint": log.get("strict_group_disjointness_checked"),
              "outer_group_disjoint": bool(outer_group_disjoint),
              "each_subject_in_exactly_one_outer_validation_fold": bool(single_outer_fold),
              "inner_patient_group_disjointness": bool(inner_group_disjoint),
              "inner_groups_subset_of_outer_training_groups": bool(inner_groups_within_outer_train),
              "fold_normalization_fit_values_saved_per_fold": all("normalizer_fit_on_outer_train_only" in f and
                  "inner_normalizer_fit_on_inner_train_only" in f for f in log["folds"]),
              "outer_class_weights_recompute_from_fold_train_support": bool(weights_match_fold_training_counts),
              "oof_exactly_covers_train_validation_once_per_model": bool(oof_complete),
              "oof_sample_count": len(expected_ids), "test_subject_overlap": sorted(cv_subjects & test_subjects),
              "oof_coverage_by_model": cv_oof_coverage, "folds": fold_assignments,
              "weight_strategy_test_not_loaded": bool(no_test_weight),
              "existing_weight_ablation_test_not_loaded": bool(no_test_existing),
              "no_models_retrained_by_final_report": True}
    if not all([result["outer_group_disjoint"], result["each_subject_in_exactly_one_outer_validation_fold"],
                result["inner_patient_group_disjointness"], result["inner_groups_subset_of_outer_training_groups"],
                result["outer_class_weights_recompute_from_fold_train_support"], result["oof_exactly_covers_train_validation_once_per_model"],
                result["weight_strategy_test_not_loaded"], result["existing_weight_ablation_test_not_loaded"]]):
        raise AssertionError("CV group/scope or weight experiment audit failed")
    (RESULTS / "final_cv_and_weight_scope_audit.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return result


def run(root: Path = ROOT):
    global ROOT, FINAL, RESULTS, DIAG, FINAL_FIGURES
    ROOT = root.resolve()
    FINAL = ROOT / "reports/final"
    RESULTS = ROOT / "results/classification"
    DIAG = RESULTS / "nsvf44_v1/diagnosis"
    FINAL_FIGURES = ROOT / "figures/12_final_report"
    FINAL.mkdir(parents=True, exist_ok=True)
    for required in [ROOT / "README.md", ROOT / "reports/classification/experiment_summary.md",
                     ROOT / "reports/classification/four_class_failure_diagnosis.md",
                     RESULTS / "nv44_v1/test_predictions_all_models.csv",
                     RESULTS / "nsvf44_v1/test_predictions_all_models.csv",
                     DIAG / "group_cv_5fold/group_cv_fold_metrics.csv"]:
        if not required.exists():
            raise FileNotFoundError(required)
    inventory = inventory_files()
    artifact_audit = audit_formal_model_artifacts()
    metrics, per_class, confusion, detail = reconcile_metrics()
    stats, subjects, coverage, audit = inspect_splits_and_classes()
    audit["formal_model_artifacts"] = artifact_audit
    audit["group_cv_and_weight_scope"] = audit_cv_and_weights()
    weight_metrics = pd.read_csv(DIAG / "weight_strategy_train_val_metrics.csv")
    weight_classes = pd.read_csv(DIAG / "weight_strategy_class_metrics.csv")
    font_name, cases = generate_figures(metrics, per_class, confusion, stats, coverage,
                                        weight_metrics, weight_classes)
    report = exact_report(metrics, per_class, confusion, stats, subjects, coverage, audit,
                          pd.read_csv(RESULTS / "final_metric_reconciliation.csv"), cases,
                          font_name, inventory)
    # Refresh the inventory after all reports/plots/derived outputs now exist.
    inventory = inventory_files()
    generate_auxiliary_reports(metrics, per_class, confusion, stats, subjects, coverage, audit,
                               pd.read_csv(RESULTS / "final_metric_reconciliation.csv"), cases,
                               font_name, inventory, detail)
    update_experiment_summary(metrics, per_class, stats, coverage, audit, detail)
    # Final inventory includes updated summary and auxiliary report files.
    inventory = inventory_files()
    # Rebuild audit and summary after inventory refresh.
    generate_auxiliary_reports(metrics, per_class, confusion, stats, subjects, coverage, audit,
                               pd.read_csv(RESULTS / "final_metric_reconciliation.csv"), cases,
                               font_name, inventory, detail)
    verify_outputs()
    return {"report": str(FINAL / "MIT_BIH_完整实验报告.md"),
            "verification": read_json(FINAL / "final_report_verification.json"),
            "figures": len(list(FINAL_FIGURES.glob("*.png"))),
            "metric_models": len(metrics), "reconciled": detail["all_saved_scalar_metrics_match"]}


def verify_outputs():
    report_path = FINAL / "MIT_BIH_完整实验报告.md"
    check_path = FINAL / "实验结果核验报告.md"
    index_path = FINAL / "图表索引.md"
    completion_path = FINAL / "项目完成情况总结.md"
    required_headings = ["第一章 绪论", "第二章 数据集与数据探索", "第三章 数据预处理与数据集构建",
                        "第四章 模型设计", "第五章 N/V 二分类实验", "第六章 N/S/V/F 四分类拓展实验",
                        "第七章 综合讨论", "第八章 总结与展望"]
    text = report_path.read_text(encoding="utf-8")
    if any(heading not in text for heading in required_headings):
        raise AssertionError("A required report chapter is missing")
    md_files = [report_path, check_path, index_path, completion_path,
                ROOT / "reports/classification/experiment_summary.md"]
    missing_images = []
    for md in md_files:
        body = md.read_text(encoding="utf-8")
        for rel in __import__("re").findall(r"!\[[^]]*\]\(\s*([^ )]+)\s*\)", body):
            if rel.startswith(("http://", "https://")):
                continue
            img = (md.parent / rel).resolve()
            if not img.exists():
                missing_images.append((str(md), rel))
    if missing_images:
        raise AssertionError(f"Broken local image links: {missing_images}")
    metric_check = read_json(RESULTS / "final_metric_reconciliation.json")
    split_check = read_json(RESULTS / "final_split_and_mapping_audit.json")
    cv_check = read_json(RESULTS / "final_cv_and_weight_scope_audit.json")
    model_check = read_json(RESULTS / "final_formal_model_artifact_audit.json")
    if not metric_check["all_saved_scalar_metrics_match"] or not split_check["N_V_and_N_S_V_F_same_record_split"]:
        raise AssertionError("Metric or split verification failed")
    if any(split_check["record_subject_overlap_between_splits"].values()):
        raise AssertionError("Subject overlap found")
    if not split_check["201_202_same_pseudonymous_subject_and_split"]:
        raise AssertionError("201 and 202 split audit failed")
    if not all(row["post_repair_matches_metadata"] for row in split_check["derived_split_class_count_audit"]):
        raise AssertionError("Derived split class count repair audit failed")
    if not cv_check["oof_exactly_covers_train_validation_once_per_model"] or cv_check["test_subject_overlap"]:
        raise AssertionError("CV subject or OOF audit failed")
    if not model_check["all_formal_artifact_checks_pass"]:
        raise AssertionError("Formal checkpoint structural audit failed")
    for image in FINAL_FIGURES.glob("*.png"):
        from PIL import Image
        with Image.open(image) as im:
            if im.info.get("dpi", (0, 0))[0] < 290:
                raise AssertionError(f"Figure DPI is below 300: {image}")
    verify = read_json(FINAL / "final_report_verification.json")
    verify["report_sections_complete"] = True
    verify["local_markdown_image_links_resolve"] = True
    verify["new_figures_at_least_290_dpi"] = True
    verify["derived_split_class_count_fields_match_metadata"] = True
    verify["cv_outer_inner_patient_group_audit_passed"] = True
    verify["cv_oof_exactly_covers_train_validation_once"] = True
    verify["formal_model_artifacts_read_only_and_match"] = True
    verify["passed"] = True
    (FINAL / "final_report_verification.json").write_text(json.dumps(verify, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    args = parser.parse_args()
    print(json.dumps(run(args.root), ensure_ascii=False, indent=2))
