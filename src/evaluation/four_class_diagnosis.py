"""Patient-aware diagnosis of the existing N/S/V/F experiment.

Formal-test artifacts are read only for retrospective error summaries and ECG
examples. All new weight comparisons and grouped cross-validation use train and
validation partitions only. The grouped CV pool excludes the formal test set.
"""
from __future__ import annotations

import argparse
import json
import os
import textwrap
import time
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import torch
import wfdb
from joblib import load, dump
from PIL import Image
from sklearn.metrics import accuracy_score, confusion_matrix, f1_score, precision_score, recall_score
from sklearn.model_selection import StratifiedGroupKFold
from sklearn.preprocessing import StandardScaler
from torch.utils.data import DataLoader, TensorDataset

from ..labels import AAMI_MAP
from ..models.classifiers import HeartbeatCNN, make_logistic_regression, make_random_forest
from ..training.trainer import (class_weights_from_training, load_npz, predict_cnn,
                                seed_everything, train_cnn)

CLASSES = ("N", "S", "V", "F")
CLASS_IDS = {name: index for index, name in enumerate(CLASSES)}
SEED = 20261028
WEIGHT_CAP = 10.0
CV_FOLDS = 5


def _write_csv(frame: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(path, index=False, encoding="utf-8-sig")


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _split_data(path: Path) -> dict[str, np.ndarray]:
    return load_npz(path)


def _class_vector_metrics(y_true: np.ndarray, y_pred: np.ndarray) -> dict:
    labels_present = sorted(np.unique(y_true).astype(int).tolist())
    recalls = {}
    for class_id, name in enumerate(CLASSES):
        mask = y_true == class_id
        recalls[f"recall_{name}"] = float((y_pred[mask] == class_id).mean()) if mask.any() else np.nan
    return {
        "accuracy": float(accuracy_score(y_true, y_pred)),
        "macro_f1_present_classes": float(f1_score(y_true, y_pred, labels=labels_present,
                                                   average="macro", zero_division=0)),
        "supported_class_count": len(labels_present),
        **recalls,
    }


def build_subject_tables(root: Path, output_dir: Path) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    dataset = root / "data/processed/mitdb44_nsvf_v1"
    meta = pd.read_csv(dataset / "metadata.csv", usecols=[
        "record_id", "subject_id", "split", "annotation_index", "annotation_sample",
        "original_label", "mapped_label", "annotation_kind", "included", "exclusion_reason",
        "lead", "lead_channel", "window_start_sample", "window_stop_sample_exclusive",
        "center_index", "window_length", "target_label", "sample_id", "npz_row",
    ], keep_default_na=False, low_memory=False)
    included_mask = meta["included"].astype(str).str.casefold().eq("true")
    included = meta.loc[included_mask & meta["mapped_label"].isin(CLASSES)].copy()
    manifest = pd.read_csv(dataset / "split_manifest.csv", dtype={"record_id": str}, keep_default_na=False)
    subjects = (manifest.groupby(["subject_id", "split"], as_index=False)
                .agg(record_ids=("record_id", lambda s: ";".join(sorted(set(s.astype(str))))),
                     record_count=("record_id", "nunique")))
    counts = (included.groupby(["subject_id", "split", "mapped_label"]).size()
              .unstack("mapped_label", fill_value=0).reindex(columns=CLASSES, fill_value=0)
              .reset_index())
    subject_counts = subjects.merge(counts, on=["subject_id", "split"], how="left")
    subject_counts[list(CLASSES)] = subject_counts[list(CLASSES)].fillna(0).astype(int)
    subject_counts["total_samples"] = subject_counts[list(CLASSES)].sum(axis=1)
    for name in CLASSES:
        subject_counts[f"{name}_share_pct"] = np.where(
            subject_counts.total_samples > 0, subject_counts[name] / subject_counts.total_samples * 100, 0.0)
    split_order = {"train": 0, "val": 1, "test": 2}
    subject_counts["_split_order"] = subject_counts.split.map(split_order)
    subject_counts = subject_counts.sort_values(["_split_order", "subject_id"]).drop(columns="_split_order")
    _write_csv(subject_counts, output_dir / "subject_class_counts.csv")

    coverage_rows = []
    concentration_rows = []
    for split, frame in subject_counts.groupby("split", sort=False):
        for name in CLASSES:
            values = frame[name].to_numpy(dtype=np.int64)
            positives = values[values > 0]
            total = int(values.sum())
            positive_rows = frame.loc[frame[name] > 0, ["subject_id", name]].sort_values(name, ascending=False)
            top = positive_rows.iloc[0] if len(positive_rows) else None
            coverage_rows.append({
                "split": split, "class": name, "subjects_total": int(len(frame)),
                "subjects_with_class": int((values > 0).sum()),
                "subject_coverage_pct": float((values > 0).mean() * 100) if len(values) else 0.0,
                "sample_count": total,
                "top_subject_id": str(top.subject_id) if top is not None else "",
                "top_subject_samples": int(top[name]) if top is not None else 0,
                "top_subject_share_pct": float(top[name] / total * 100) if total and top is not None else 0.0,
                "positive_subject_min": int(positives.min()) if len(positives) else 0,
                "positive_subject_median": float(np.median(positives)) if len(positives) else 0.0,
                "positive_subject_max": int(positives.max()) if len(positives) else 0,
            })
    all_counts = (subject_counts.groupby("subject_id", as_index=False)[list(CLASSES)].sum())
    for name in CLASSES:
        values = all_counts[name].to_numpy(dtype=np.int64)
        positive = np.sort(values[values > 0])[::-1]
        shares = positive / max(int(values.sum()), 1)
        entropy = float(-(shares * np.log2(shares)).sum()) if len(shares) else 0.0
        concentration_rows.append({
            "class": name, "total_samples": int(values.sum()),
            "subjects_with_class": int((values > 0).sum()), "subjects_total": int(len(values)),
            "top_subject_id": str(all_counts.iloc[int(np.argmax(values))].subject_id),
            "top_subject_samples": int(values.max()), "top_subject_share_pct": float(values.max() / max(values.sum(), 1) * 100),
            "top3_subject_share_pct": float(positive[:3].sum() / max(values.sum(), 1) * 100),
            "effective_subject_count_2pow_entropy": float(2 ** entropy),
        })
    coverage = pd.DataFrame(coverage_rows)
    concentration = pd.DataFrame(concentration_rows)
    _write_csv(coverage, output_dir / "subject_class_coverage_by_split.csv")
    _write_csv(concentration, output_dir / "subject_class_concentration.csv")

    raw_subject = (meta[meta.annotation_kind.eq("mapped_beat")]
                   .groupby(["subject_id", "split", "original_label", "mapped_label"])
                   .size().rename("annotation_count").reset_index())
    _write_csv(raw_subject, output_dir / "subject_original_symbol_counts.csv")
    return subject_counts, coverage, concentration


def audit_preprocessing(root: Path, output_dir: Path) -> dict:
    dataset = root / "data/processed/mitdb44_nsvf_v1"
    metadata = pd.read_csv(dataset / "metadata.csv", low_memory=False, keep_default_na=False)
    included = metadata[metadata.included.astype(str).str.casefold().eq("true")].copy()
    expected = included.original_label.map(AAMI_MAP).fillna("")
    mismatches = int((expected.to_numpy() != included.mapped_label.to_numpy()).sum())
    expected_ids = included.mapped_label.map(CLASS_IDS).fillna(-1).astype(int)
    id_mismatches = int((expected_ids.to_numpy() != included.target_label.astype(int).to_numpy()).sum())
    window_pre = round(.3 * 360); window_post = round(.4 * 360)
    bounds_ok = ((included.window_start_sample.astype(int) == included.annotation_sample.astype(int) - window_pre)
                 & (included.window_stop_sample_exclusive.astype(int)
                    == included.annotation_sample.astype(int) + window_post + 1))
    length_ok = (included.window_length.astype(int) == window_pre + window_post + 1)
    center_ok = included.center_index.astype(int).eq(window_pre)
    split_manifest = pd.read_csv(dataset / "split_manifest.csv", dtype={"record_id": str}, keep_default_na=False)
    records = sorted(split_manifest.record_id.astype(str).unique())
    annotation_match = True; annotation_mismatch_count = 0; selected_lead_mismatch = []
    for record_id in records:
        ann = wfdb.rdann(str(root / "data/mitdb" / record_id), "atr")
        observed = metadata.loc[metadata.record_id.astype(str).eq(record_id)].sort_values("annotation_index")
        if not np.array_equal(np.asarray(ann.sample, dtype=np.int64), observed.annotation_sample.astype(np.int64).to_numpy()):
            annotation_match = False; annotation_mismatch_count += 1
        if list(ann.symbol) != observed.original_label.astype(str).tolist():
            annotation_match = False; annotation_mismatch_count += 1
        header = wfdb.rdheader(str(root / "data/mitdb" / record_id))
        lead_names = list(header.sig_name)
        expected_channel = lead_names.index("MLII") if "MLII" in lead_names else 0
        expected_lead = lead_names[expected_channel]
        used = included.loc[included.record_id.astype(str).eq(record_id)]
        if not used.empty and ((used.lead.astype(str) != expected_lead).any()
                               or (used.lead_channel.astype(int) != expected_channel).any()):
            selected_lead_mismatch.append(record_id)
    split_array_checks = []
    for split in ("train", "val", "test"):
        arr = load_npz(dataset / f"{split}.npz")
        rows = included[included.split.eq(split)].sort_values("npz_row")
        ok = (len(rows) == len(arr["y"])
              and np.array_equal(rows.sample_id.astype(str).to_numpy(), arr["sample_id"])
              and np.array_equal(rows.mapped_label.astype(str).to_numpy(), arr["mapped_label"])
              and np.array_equal(rows.target_label.astype(int).to_numpy(), arr["y"]))
        split_array_checks.append({"split": split, "matches_metadata": bool(ok), "samples": int(len(arr["y"]))})
    lead_counts = pd.read_csv(dataset / "lead_sample_counts.csv", keep_default_na=False)
    config = _load_json(dataset / "processing_config.json")
    subject_split = split_manifest.groupby("subject_id").split.nunique()
    record_pair = split_manifest[split_manifest.subject_id.eq("subject_201_202")].split.nunique() == 1
    result = {
        "official_record_count": int(len(records)), "all_included_samples_use_MLII": bool(set(lead_counts.lead.astype(str)) == {"MLII"}),
        "lead_selection_matches_header_policy": not selected_lead_mismatch,
        "lead_selection_mismatch_records": selected_lead_mismatch,
        "sampling_rates_hz": sorted(pd.to_numeric(metadata.fs_hz, errors="coerce").dropna().unique().tolist()),
        "all_labels_match_public_mapping": mismatches == 0, "label_mapping_mismatch_count": mismatches,
        "all_target_ids_match_N_S_V_F": id_mismatches == 0, "target_id_mismatch_count": id_mismatches,
        "all_original_annotations_match_WFDB_ATR": annotation_match, "annotation_mismatch_records_count": annotation_mismatch_count,
        "window_0p3s_before_0p4s_after_253_samples": bool(bounds_ok.all() and length_ok.all() and center_ok.all()),
        "window_boundary_mismatch_count": int((~(bounds_ok & length_ok & center_ok)).sum()),
        "all_NSVF_samples_have_beat_labels": bool(included.annotation_kind.eq("mapped_beat").all()
                                                  and included.mapped_label.isin(CLASSES).all()),
        "split_npz_order_and_labels_match_metadata": all(row["matches_metadata"] for row in split_array_checks),
        "split_array_checks": split_array_checks, "subject_overlap_count": int((subject_split > 1).sum()),
        "record_201_202_same_split": bool(record_pair),
        "filter_low_high_hz": [config.get("filter", {}).get("low_hz"), config.get("filter", {}).get("high_hz")],
        "normalizer_fit_split": _load_json(dataset / "normalization.json").get("fit_split"),
        "normalizer_fit_only_train": _load_json(dataset / "normalization.json").get("fit_split") == "train",
        "exclusion_counts": pd.read_csv(dataset / "exclusion_counts.csv").to_dict(orient="records"),
    }
    (output_dir / "preprocessing_audit.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return result


def audit_checkpoints(root: Path, output_dir: Path) -> dict:
    base = root / "checkpoints/nsvf44_v1/formal"
    lr = load(base / "logistic_regression.joblib")
    rf = load(base / "random_forest.joblib")
    cnn = torch.load(base / "cnn/cnn_best.pt", map_location="cpu", weights_only=False)
    result = {
        "logistic_regression_classes": lr["estimator"].classes_.astype(int).tolist(),
        "logistic_regression_scaler_features": int(lr["scaler"].n_features_in_),
        "random_forest_classes": rf["estimator"].classes_.astype(int).tolist(),
        "random_forest_trees": int(len(rf["estimator"].estimators_)),
        "cnn_class_count": int(cnn["class_count"]), "cnn_best_epoch": int(cnn["epoch"]),
        "cnn_state_tensors": int(len(cnn["state_dict"])),
        "checkpoints_loadable": True,
    }
    (output_dir / "checkpoint_audit.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    return result


def retrospective_test_diagnostics(root: Path, output_dir: Path, figure_dir: Path) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    result_dir = root / "results/classification/nsvf44_v1"
    per_subject_rows = []; error_rows = []; predictions = {}
    for model in ("logistic_regression", "random_forest", "cnn_1d"):
        frame = pd.read_csv(result_dir / f"test_predictions_{model}.csv", keep_default_na=False)
        saved_metrics = _load_json(result_dir / f"test_metrics_{model}.json")
        overall = confusion_matrix(frame.true_aami_label.map(CLASS_IDS),
                                   frame.predicted_aami_label.map(CLASS_IDS), labels=range(4))
        if overall.tolist() != saved_metrics["confusion_matrix"]:
            raise AssertionError(f"Saved test predictions do not match saved confusion matrix: {model}")
        predictions[model] = frame
        for subject_id, group in frame.groupby("subject_id", sort=True):
            y_true = group.true_aami_label.map(CLASS_IDS).to_numpy(dtype=int)
            y_pred = group.predicted_aami_label.map(CLASS_IDS).to_numpy(dtype=int)
            values = _class_vector_metrics(y_true, y_pred)
            row = {"model": model, "subject_id": subject_id, "records": ";".join(sorted(group.record_id.astype(str).unique())),
                   "sample_count": len(group), "supported_classes": ",".join(CLASSES[i] for i in sorted(np.unique(y_true))), **values}
            for i, name in enumerate(CLASSES):
                row[f"support_{name}"] = int((y_true == i).sum())
            per_subject_rows.append(row)
            matrix = confusion_matrix(y_true, y_pred, labels=range(4))
            for i, true_name in enumerate(CLASSES):
                for j, pred_name in enumerate(CLASSES):
                    if i != j and matrix[i, j]:
                        error_rows.append({"model": model, "subject_id": subject_id, "true_class": true_name,
                                           "predicted_class": pred_name, "count": int(matrix[i, j])})
    subject_metrics = pd.DataFrame(per_subject_rows)
    errors = pd.DataFrame(error_rows)
    _write_csv(subject_metrics, output_dir / "per_subject_test_metrics_descriptive_only.csv")
    _write_csv(errors, output_dir / "per_subject_test_error_directions_descriptive_only.csv")
    summaries = []
    for model, frame in predictions.items():
        counts = frame.predicted_aami_label.value_counts().reindex(CLASSES, fill_value=0)
        actual = frame.true_aami_label.value_counts().reindex(CLASSES, fill_value=0)
        for name in CLASSES:
            summaries.append({"model": model, "class": name, "true_count": int(actual[name]),
                              "predicted_count": int(counts[name]),
                              "true_share_pct": float(actual[name] / len(frame) * 100),
                              "predicted_share_pct": float(counts[name] / len(frame) * 100)})
    prediction_distribution = pd.DataFrame(summaries)
    _write_csv(prediction_distribution, output_dir / "test_prediction_class_shares_descriptive_only.csv")
    _plot_subject_metrics(subject_metrics, figure_dir)
    _plot_test_errors(root, predictions["cnn_1d"], output_dir, figure_dir)
    return subject_metrics, errors, prediction_distribution


def _plot_subject_metrics(frame: pd.DataFrame, figure_dir: Path) -> None:
    columns = ["accuracy", "macro_f1_present_classes", "recall_N", "recall_S", "recall_V", "recall_F"]
    labels = ["Accuracy", "Macro-F1\n(present classes)", "Recall N", "Recall S", "Recall V", "Recall F"]
    rows = frame.sort_values(["subject_id", "model"]).reset_index(drop=True)
    values = rows[columns].to_numpy(dtype=float)
    fig, ax = plt.subplots(figsize=(12, max(5, .42 * len(rows))))
    image = ax.imshow(np.ma.masked_invalid(values), cmap="viridis", vmin=0, vmax=1, aspect="auto")
    ax.set_xticks(range(len(columns)), labels)
    ax.set_yticks(range(len(rows)), [f"{r.subject_id} | {r.model}" for r in rows.itertuples()])
    ax.set_title("Per-subject performance | retrospective, already-viewed test set")
    ax.set_xlabel("Metric; class recall is blank when the subject has no reference samples in that class")
    for i in range(len(rows)):
        for j in range(len(columns)):
            val = values[i, j]
            ax.text(j, i, "—" if np.isnan(val) else f"{val:.2f}", ha="center", va="center",
                    color="white" if not np.isnan(val) and val < .65 else "black", fontsize=8)
    fig.colorbar(image, ax=ax, label="Score")
    fig.text(.01, .003, "MIT-BIH 1.0.0 | test predictions are retrospective diagnostics only; not used to tune weights or select models.", fontsize=8)
    fig.tight_layout(rect=(0, .025, 1, 1))
    figure_dir.mkdir(parents=True, exist_ok=True)
    fig.savefig(figure_dir / "per_subject_test_metrics_descriptive_only.png", dpi=300, bbox_inches="tight")
    plt.close(fig)


def _select_error_examples(frame: pd.DataFrame, true_name: str, pred_name: str, limit: int = 2) -> pd.DataFrame:
    rows = frame[(frame.true_aami_label == true_name) & (frame.predicted_aami_label == pred_name)]
    if rows.empty:
        return rows
    rows = rows.sort_values(["subject_id", "record_id", "annotation_sample"])
    chosen = rows.groupby("subject_id", sort=True, as_index=False).head(1)
    if len(chosen) < limit and len(rows) > len(chosen):
        # Deterministically choose a temporally distant additional sample from an already represented patient.
        for row_index in np.linspace(0, len(rows) - 1, num=min(limit, len(rows)), dtype=int):
            candidate = rows.iloc[row_index]
            if candidate.sample_id not in set(chosen.sample_id):
                chosen = pd.concat([chosen, candidate.to_frame().T], ignore_index=True)
                if len(chosen) >= limit:
                    break
    return chosen.head(limit)


def _plot_test_errors(root: Path, cnn_frame: pd.DataFrame, output_dir: Path, figure_dir: Path) -> None:
    cases = []
    for true_name, pred_name in (("N", "S"), ("F", "N"), ("F", "V")):
        selected = _select_error_examples(cnn_frame, true_name, pred_name)
        cases.extend(selected.to_dict(orient="records"))
    if not cases:
        return
    data = load_npz(root / "data/processed/mitdb44_nsvf_v1/test.npz")
    lookup = {str(sample_id): idx for idx, sample_id in enumerate(data["sample_id"])}
    relative_t = data["relative_time_s"]
    fig, axes = plt.subplots(len(cases), 1, figsize=(11, max(7, 2.1 * len(cases))), squeeze=False)
    saved_cases = []
    for ax, row in zip(axes[:, 0], cases):
        index = lookup.get(str(row["sample_id"]))
        if index is None:
            raise AssertionError(f"Test waveform row is absent from saved NPZ: {row['sample_id']}")
        waveform = data["X_filtered"][index, 0]
        ax.plot(relative_t, waveform, color="#2563a6", linewidth=1.05, label="filtered ECG (mV)")
        ax.axvline(0, color="#d62728", linestyle="--", linewidth=1.0, label="expert annotation")
        ax.set_ylabel("Amplitude (mV)"); ax.set_xlabel("Time from annotated beat (s)")
        ax.grid(alpha=.2)
        ax.set_title(f"CNN {row['true_aami_label']}→{row['predicted_aami_label']} | record {row['record_id']} | "
                     f"{row['subject_id']} | beat {int(row['annotation_sample'])} ({float(row['time_s']):.2f}s) | "
                     f"original symbol {row['original_label']}", fontsize=9)
        ax.legend(loc="upper right", fontsize=7)
        saved_cases.append({k: row[k] for k in ("sample_id", "record_id", "subject_id", "annotation_sample",
                                                 "time_s", "original_label", "true_aami_label",
                                                 "predicted_aami_label", "lead_name")})
    fig.suptitle("Representative CNN errors | previously viewed formal test set | descriptive only", y=1.002)
    fig.text(.01, .003, "253 samples, 0.3 s before and 0.4 s after annotation; MLII; filtered physical mV; no retraining or threshold selection.", fontsize=8)
    fig.tight_layout(rect=(0, .025, 1, .985))
    figure_dir.mkdir(parents=True, exist_ok=True)
    fig.savefig(figure_dir / "cnn_test_error_waveforms_descriptive_only.png", dpi=300, bbox_inches="tight")
    plt.close(fig)
    _write_csv(pd.DataFrame(saved_cases), output_dir / "cnn_test_error_waveform_cases_descriptive_only.csv")


def _weight_vectors(y_train: np.ndarray) -> dict[str, np.ndarray]:
    counts = np.bincount(y_train.astype(int), minlength=len(CLASSES)).astype(np.float64)
    if (counts == 0).any():
        raise ValueError(f"Training labels miss a required class: {counts.tolist()}")
    inverse = class_weights_from_training(y_train, len(CLASSES)).astype(np.float64)
    smooth = np.sqrt(inverse); smooth /= smooth.mean()
    capped = np.minimum(inverse, WEIGHT_CAP); capped /= capped.mean()
    return {
        "unweighted": np.ones(len(CLASSES), dtype=np.float32),
        "sqrt_inverse": smooth.astype(np.float32),
        "capped_inverse_10": capped.astype(np.float32),
        "full_inverse": inverse.astype(np.float32),
    }


def _strategy_metrics_row(strategy: str, split: str, y: np.ndarray, pred: np.ndarray,
                          probabilities: np.ndarray, weights: np.ndarray) -> tuple[dict, list[dict]]:
    result = _class_vector_metrics(y, pred)
    actual_counts = np.bincount(y, minlength=len(CLASSES))
    pred_counts = np.bincount(pred, minlength=len(CLASSES))
    row = {"strategy": strategy, "split": split, "sample_count": len(y), **result}
    class_rows = []
    for class_id, name in enumerate(CLASSES):
        truth = y == class_id; predicted = pred == class_id
        tp = int((truth & predicted).sum())
        support = int(truth.sum()); pred_count = int(predicted.sum())
        precision = tp / pred_count if pred_count else 0.0
        recall = tp / support if support else np.nan
        f1 = 2 * precision * recall / (precision + recall) if support and precision + recall else 0.0
        row[f"true_{name}"] = support; row[f"predicted_{name}"] = pred_count
        row[f"predicted_share_{name}"] = pred_count / len(pred) * 100
        row[f"true_share_{name}"] = support / len(y) * 100
        class_rows.append({"strategy": strategy, "split": split, "class": name,
                           "class_weight": float(weights[class_id]), "support": support,
                           "predicted_count": pred_count, "predicted_share_pct": pred_count / len(pred) * 100,
                           "true_share_pct": support / len(y) * 100,
                           "precision": precision, "recall": recall, "f1": f1,
                           "mean_true_class_probability": float(probabilities[truth, class_id].mean()) if support else np.nan})
    return row, class_rows


def run_weight_strategies(root: Path, output_dir: Path, figure_dir: Path) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    """Fit weight variants on train only and compare train/validation; never opens test.npz."""
    dataset = root / "data/processed/mitdb44_nsvf_v1"
    train = _split_data(dataset / "train.npz")
    val = _split_data(dataset / "val.npz")
    x_train, y_train = train["X"][:, 0, :], train["y"].astype(np.int64)
    x_val, y_val = val["X"][:, 0, :], val["y"].astype(np.int64)
    base_config = _load_json(root / "configs/multiclass_nsvf.json")
    seed = int(base_config["seed"])
    weight_map = _weight_vectors(y_train)
    logs = {}; rows = []; class_rows = []; val_predictions = []
    model_dir = output_dir / "weight_strategies"
    model_dir.mkdir(parents=True, exist_ok=True)
    for strategy, weights in weight_map.items():
        print(f"Weight strategy {strategy}: weights={weights.tolist()}", flush=True)
        model, history, summary = train_cnn(
            x_train, y_train, x_val, y_val, len(CLASSES), weights, seed,
            model_dir / strategy, epochs=int(base_config["cnn"]["epochs"]),
            patience=int(base_config["cnn"]["patience"]), batch_size=int(base_config["cnn"]["batch_size"]))
        logs[strategy] = {**summary, "weights": weights.tolist(), "epochs": history.to_dict(orient="records"),
                          "weight_formula": {
                              "unweighted": "w_c=1",
                              "sqrt_inverse": "sqrt(N/(K*n_c)), normalized to mean 1",
                              "capped_inverse_10": "min(N/(K*n_c), 10), then normalized to mean 1",
                              "full_inverse": "N/(K*n_c), current formal weighted CrossEntropyLoss",
                          }[strategy]}
        for split, x, y, source in (("train", x_train, y_train, train), ("val", x_val, y_val, val)):
            pred, prob = predict_cnn(model, x)
            row, details = _strategy_metrics_row(strategy, split, y, pred, prob, weights)
            rows.append(row); class_rows.extend(details)
            if split == "val":
                frame = pd.DataFrame({"strategy": strategy, "sample_id": source["sample_id"].astype(str),
                                      "record_id": source["record_id"].astype(str), "subject_id": source["subject_id"].astype(str),
                                      "true_class": [CLASSES[i] for i in y],
                                      "predicted_class": [CLASSES[i] for i in pred]})
                for class_id, name in enumerate(CLASSES):
                    frame[f"probability_{name}"] = prob[:, class_id]
                val_predictions.append(frame)
    summary_frame = pd.DataFrame(rows)
    class_frame = pd.DataFrame(class_rows)
    _write_csv(summary_frame, output_dir / "weight_strategy_train_val_metrics.csv")
    _write_csv(class_frame, output_dir / "weight_strategy_class_metrics.csv")
    _write_csv(pd.DataFrame([{"strategy": strategy, "class": name, "weight": float(weights[i])}
                             for strategy, weights in weight_map.items()
                             for i, name in enumerate(CLASSES)]), output_dir / "weight_strategy_vectors.csv")
    _write_csv(pd.concat(val_predictions, ignore_index=True), output_dir / "weight_strategy_validation_predictions.csv")
    (output_dir / "weight_strategy_training_log.json").write_text(
        json.dumps({"scope": "train and validation only; formal test not loaded",
                    "seed": seed, "best_checkpoint_selected_by": "validation Macro-F1",
                    "strategies": logs}, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    _plot_weight_strategies(summary_frame, class_frame, figure_dir)
    return summary_frame, class_frame, logs


def _plot_weight_strategies(metrics: pd.DataFrame, class_metrics: pd.DataFrame, figure_dir: Path) -> None:
    order = ["unweighted", "sqrt_inverse", "capped_inverse_10", "full_inverse"]
    labels = ["None", "sqrt inverse", "cap 10", "full inverse"]
    val = metrics[metrics.split.eq("val")].set_index("strategy").reindex(order)
    train = metrics[metrics.split.eq("train")].set_index("strategy").reindex(order)
    fig, axes = plt.subplots(1, 3, figsize=(17, 5.5))
    x = np.arange(len(order)); width = .35
    axes[0].bar(x - width / 2, train.accuracy, width, label="train accuracy", color="#91b7d4")
    axes[0].bar(x + width / 2, val.accuracy, width, label="validation accuracy", color="#277da1")
    axes[0].set_xticks(x, labels, rotation=20); axes[0].set_ylim(0, 1.05); axes[0].set_ylabel("Accuracy")
    axes[0].set_title("Accuracy (training is in-sample)"); axes[0].legend(fontsize=8); axes[0].grid(axis="y", alpha=.2)
    axes[1].bar(x - width / 2, train.macro_f1_present_classes, width, label="train Macro-F1", color="#f2cc8f")
    axes[1].bar(x + width / 2, val.macro_f1_present_classes, width, label="validation Macro-F1", color="#f8961e")
    axes[1].set_xticks(x, labels, rotation=20); axes[1].set_ylim(0, 1.05); axes[1].set_ylabel("Macro-F1")
    axes[1].set_title("Macro-F1 (mean over supported classes)"); axes[1].legend(fontsize=8); axes[1].grid(axis="y", alpha=.2)
    val_class = class_metrics[class_metrics.split.eq("val")]
    for class_index, name in enumerate(CLASSES):
        values = val_class[val_class["class"].eq(name)].set_index("strategy").reindex(order)
        axes[2].plot(labels, values.predicted_share_pct, marker="o", label=f"predicted {name}")
        axes[2].axhline(float(values.true_share_pct.iloc[0]), linestyle="--", linewidth=.8,
                        color=f"C{class_index}", alpha=.6)
    axes[2].set_ylabel("Validation predicted class share (%)")
    axes[2].set_title("Prediction share vs true share (dashed)"); axes[2].tick_params(axis="x", rotation=20)
    axes[2].legend(fontsize=8); axes[2].grid(alpha=.2)
    fig.suptitle("CNN class-weight strategies | train/validation only | no test data loaded")
    fig.text(.01, .005, "Weights use training labels only; model checkpoint is early-stopped on validation Macro-F1. Dashed class lines show the validation true share.", fontsize=8)
    fig.tight_layout(rect=(0, .04, 1, .93))
    figure_dir.mkdir(parents=True, exist_ok=True)
    fig.savefig(figure_dir / "cnn_weight_strategies_train_val.png", dpi=300, bbox_inches="tight")
    plt.close(fig)


def existing_cross_model_weight_reference(root: Path, output_dir: Path, figure_dir: Path) -> pd.DataFrame:
    """Summarize the already-completed LR/RF/CNN weighted-vs-unweighted validation ablation."""
    source = _load_json(root / "results/classification/nsvf44_v1/class_weight_validation_ablation.json")
    if source.get("test_partition_loaded") is not False:
        raise AssertionError("Existing validation weight reference is not test-free")
    rows = []
    for model in ("logistic_regression", "random_forest", "cnn_1d"):
        for condition, key in (("weighted", "weighted_baseline"), ("unweighted", "unweighted_ablation")):
            score = source[key][model]
            matrix = np.asarray(score["confusion_matrix"], dtype=np.int64)
            count = int(score["test_or_validation_sample_count"])
            row = {"model": model, "condition": condition, "sample_count": count,
                   "accuracy": score["accuracy"], "macro_f1": score["macro_f1"],
                   "macro_recall": score["macro_recall"]}
            for index, name in enumerate(CLASSES):
                item = score["per_class"][name]
                row[f"recall_{name}"] = item["recall"]
                row[f"precision_{name}"] = item["precision"]
                row[f"predicted_share_{name}"] = matrix[:, index].sum() / count * 100
                row[f"true_share_{name}"] = matrix[index, :].sum() / count * 100
            rows.append(row)
    frame = pd.DataFrame(rows)
    _write_csv(frame, output_dir / "existing_weighted_unweighted_validation_reference.csv")
    fig, axes = plt.subplots(1, 2, figsize=(12, 5))
    labels = [f"{r.model}\n{r.condition}" for r in frame.itertuples()]
    x = np.arange(len(frame)); width = .34
    for ax, name, color in ((axes[0], "S", "#f58518"), (axes[1], "F", "#72b7b2")):
        ax.bar(x - width / 2, frame[f"predicted_share_{name}"], width, label=f"predicted {name}", color=color)
        ax.bar(x + width / 2, frame[f"true_share_{name}"], width, label=f"true {name}", color=color, alpha=.35)
        ax.set_xticks(x, labels, rotation=20); ax.set_ylabel("Validation share (%)")
        ax.set_title(f"{name}: predictions vs true validation share"); ax.legend(); ax.grid(axis="y", alpha=.2)
    fig.suptitle("Existing weighted/unweighted LR, RF and CNN validation comparison | test not loaded")
    fig.text(.01, .005, "Reused the saved validation-only ablation; no new fit and no test metrics. Weight effects differ by model family.", fontsize=8)
    fig.tight_layout(rect=(0, .04, 1, .92))
    figure_dir.mkdir(parents=True, exist_ok=True)
    fig.savefig(figure_dir / "existing_model_weight_ablation_validation.png", dpi=300, bbox_inches="tight")
    plt.close(fig)
    return frame


def _normalize_from_train(x_train: np.ndarray, x_other: np.ndarray) -> tuple[np.ndarray, np.ndarray, dict]:
    mean = float(np.asarray(x_train, dtype=np.float64).mean())
    std = float(np.asarray(x_train, dtype=np.float64).std(ddof=0))
    if not np.isfinite(std) or std <= 1e-12:
        raise ValueError("Fold-specific standard deviation is invalid")
    return ((x_train - mean) / std).astype(np.float32), ((x_other - mean) / std).astype(np.float32), {"mean_mV": mean, "std_mV": std}


def _fit_cnn_epochs(x: np.ndarray, y: np.ndarray, weights: np.ndarray, seed: int, epochs: int) -> HeartbeatCNN:
    seed_everything(seed)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model = HeartbeatCNN(len(CLASSES)).to(device)
    optimizer = torch.optim.Adam(model.parameters(), lr=1e-3, weight_decay=1e-5)
    criterion = torch.nn.CrossEntropyLoss(weight=torch.as_tensor(weights, dtype=torch.float32, device=device))
    generator = torch.Generator().manual_seed(seed)
    loader = DataLoader(TensorDataset(torch.as_tensor(x[:, None, :], dtype=torch.float32),
                                      torch.as_tensor(y, dtype=torch.long)), batch_size=256,
                        shuffle=True, num_workers=0, generator=generator, drop_last=False)
    for epoch in range(epochs):
        model.train(); total = 0.0
        for batch_x, batch_y in loader:
            batch_x, batch_y = batch_x.to(device), batch_y.to(device)
            optimizer.zero_grad(set_to_none=True)
            loss = criterion(model(batch_x), batch_y); loss.backward(); optimizer.step()
            total += float(loss.detach()) * len(batch_y)
        print(f"  refit epoch {epoch + 1}/{epochs} loss={total / len(y):.5f}", flush=True)
    model.eval()
    return model


def run_group_cv(root: Path, output_dir: Path, figure_dir: Path) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    """Five-fold subject-grouped OOF CV on original train+val only; never opens test.npz."""
    dataset = root / "data/processed/mitdb44_nsvf_v1"
    arrays = []
    for split in ("train", "val"):
        with np.load(dataset / f"{split}.npz", allow_pickle=False) as values:
            arrays.append({key: values[key].copy() for key in
                           ("X_filtered", "y", "subject_id", "record_id", "sample_id", "annotation_sample")})
    x_raw = np.concatenate([a["X_filtered"][:, 0, :] for a in arrays]).astype(np.float32)
    y = np.concatenate([a["y"] for a in arrays]).astype(np.int64)
    groups = np.concatenate([a["subject_id"].astype(str) for a in arrays])
    record_ids = np.concatenate([a["record_id"].astype(str) for a in arrays])
    sample_ids = np.concatenate([a["sample_id"].astype(str) for a in arrays])
    annotation_samples = np.concatenate([a["annotation_sample"] for a in arrays])
    if set(groups) & set(pd.read_csv(dataset / "split_manifest.csv", dtype={"record_id": str})
                         .query("split == 'test'").subject_id.astype(str)):
        raise AssertionError("Cross-validation input includes a formal-test subject")
    config = _load_json(root / "configs/multiclass_nsvf.json")
    splitter = StratifiedGroupKFold(n_splits=CV_FOLDS, shuffle=True, random_state=SEED)
    folds = list(splitter.split(np.zeros(len(y), dtype=np.int8), y, groups))
    output_dir.mkdir(parents=True, exist_ok=True)
    predictions = {model: np.full(len(y), -1, dtype=np.int64)
                   for model in ("logistic_regression", "random_forest", "cnn_1d")}
    probabilities = {model: np.full((len(y), len(CLASSES)), np.nan, dtype=np.float32)
                     for model in predictions}
    assignments = np.full(len(y), -1, dtype=np.int8)
    fold_rows = []; fold_log = []
    subject_assignments = []
    for fold_num, (train_idx, val_idx) in enumerate(folds, 1):
        train_groups, val_groups = set(groups[train_idx]), set(groups[val_idx])
        if train_groups & val_groups:
            raise AssertionError(f"Patient leakage in outer fold {fold_num}")
        if (assignments[val_idx] >= 0).any():
            raise AssertionError(f"CV held-out subject/sample appears in multiple folds: {fold_num}")
        assignments[val_idx] = fold_num
        for subject_id in sorted(val_groups):
            subject_assignments.append({"subject_id": subject_id, "outer_fold": fold_num,
                                        "sample_count": int((groups == subject_id).sum())})
        y_train, y_val = y[train_idx], y[val_idx]
        if set(np.unique(y_train)) != set(range(len(CLASSES))):
            raise ValueError(f"Outer training fold {fold_num} misses a class")
        x_train_raw, x_val_raw = x_raw[train_idx], x_raw[val_idx]
        x_train, x_val, norm = _normalize_from_train(x_train_raw, x_val_raw)
        model_seed = SEED + fold_num
        print(f"Grouped CV fold {fold_num}/{CV_FOLDS}: train subjects={len(train_groups)}, "
              f"validation subjects={len(val_groups)}, support={np.bincount(y_val, minlength=4).tolist()}", flush=True)

        lr_config = dict(config["models"]["logistic_regression"])
        scaler = StandardScaler().fit(x_train)
        lr = make_logistic_regression(model_seed, config=lr_config)
        lr.fit(scaler.transform(x_train), y_train)
        lr_prob = np.zeros((len(val_idx), len(CLASSES)), dtype=np.float32)
        raw_prob = lr.predict_proba(scaler.transform(x_val)); lr_prob[:, lr.classes_.astype(int)] = raw_prob
        predictions["logistic_regression"][val_idx] = lr_prob.argmax(axis=1)
        probabilities["logistic_regression"][val_idx] = lr_prob

        rf = make_random_forest(model_seed, config=config["models"]["random_forest"])
        rf.fit(x_train, y_train)
        rf_prob = np.zeros((len(val_idx), len(CLASSES)), dtype=np.float32)
        raw_prob = rf.predict_proba(x_val); rf_prob[:, rf.classes_.astype(int)] = raw_prob
        predictions["random_forest"][val_idx] = rf_prob.argmax(axis=1)
        probabilities["random_forest"][val_idx] = rf_prob

        # Nested group-only stopping split, selected by held-out class coverage within outer-train.
        inner_splitter = StratifiedGroupKFold(n_splits=4, shuffle=True, random_state=model_seed)
        inner_candidates = list(inner_splitter.split(np.zeros(len(train_idx), dtype=np.int8),
                                                      y_train, groups[train_idx]))
        eligible = []
        for inner_id, (inner_train_local, inner_val_local) in enumerate(inner_candidates, 1):
            inner_train_classes = set(np.unique(y_train[inner_train_local]))
            inner_val_classes = set(np.unique(y_train[inner_val_local]))
            if inner_train_classes == set(range(len(CLASSES))):
                eligible.append((len(inner_val_classes), -inner_id, inner_id,
                                 inner_train_local, inner_val_local, inner_val_classes))
        if not eligible:
            raise ValueError(f"No inner grouped split keeps all classes in training for outer fold {fold_num}")
        _, _, inner_id, inner_train_local, inner_val_local, inner_val_classes = max(eligible)
        inner_train_raw, inner_val_raw, inner_norm = _normalize_from_train(
            x_train_raw[inner_train_local], x_train_raw[inner_val_local])
        inner_y_train, inner_y_val = y_train[inner_train_local], y_train[inner_val_local]
        inner_weights = class_weights_from_training(inner_y_train, len(CLASSES))
        inner_dir = output_dir / "cnn_inner_stopping" / f"fold_{fold_num}"
        _, inner_history, inner_summary = train_cnn(
            inner_train_raw, inner_y_train, inner_val_raw, inner_y_val, len(CLASSES), inner_weights,
            model_seed, inner_dir, epochs=int(config["cnn"]["epochs"]),
            patience=int(config["cnn"]["patience"]), batch_size=int(config["cnn"]["batch_size"]))
        best_epoch = max(1, int(inner_summary["best_epoch"]))
        outer_weights = class_weights_from_training(y_train, len(CLASSES))
        cnn = _fit_cnn_epochs(x_train, y_train, outer_weights, model_seed, best_epoch)
        cnn_dir = output_dir / "cnn_outer_refit" / f"fold_{fold_num}"
        cnn_dir.mkdir(parents=True, exist_ok=True)
        torch.save({"state_dict": cnn.state_dict(), "class_count": len(CLASSES), "best_epoch_from_inner_groups": best_epoch,
                    "seed": model_seed, "outer_train_subjects": sorted(train_groups)}, cnn_dir / "cnn_outer_refit.pt")
        cnn_pred, cnn_prob = predict_cnn(cnn, x_val)
        predictions["cnn_1d"][val_idx] = cnn_pred
        probabilities["cnn_1d"][val_idx] = cnn_prob
        fold_log.append({"fold": fold_num, "model_seed": model_seed,
                         "train_subjects": sorted(train_groups), "validation_subjects": sorted(val_groups),
                         "train_class_counts": np.bincount(y_train, minlength=4).tolist(),
                         "validation_class_counts": np.bincount(y_val, minlength=4).tolist(),
                         "normalizer_fit_on_outer_train_only": norm,
                         "inner_stopping_fold": inner_id,
                         "inner_train_subjects": sorted(set(groups[train_idx][inner_train_local])),
                         "inner_validation_subjects": sorted(set(groups[train_idx][inner_val_local])),
                         "inner_validation_class_coverage": [CLASSES[i] for i in sorted(inner_val_classes)],
                         "inner_normalizer_fit_on_inner_train_only": inner_norm,
                         "inner_best_epoch": best_epoch, "inner_best_validation_macro_f1": inner_summary["best_val_macro_f1"],
                         "inner_train_class_weights": inner_weights.tolist(),
                         "outer_train_class_weights": outer_weights.tolist()})
        for model_name, pred in (("logistic_regression", predictions["logistic_regression"][val_idx]),
                                 ("random_forest", predictions["random_forest"][val_idx]),
                                 ("cnn_1d", cnn_pred)):
            result = _class_vector_metrics(y_val, pred)
            cm = confusion_matrix(y_val, pred, labels=range(len(CLASSES)))
            row = {"model": model_name, "fold": fold_num, "validation_subject_count": len(val_groups),
                   "validation_record_count": len(set(record_ids[val_idx])),
                   "validation_sample_count": len(val_idx), "validation_subjects": ";".join(sorted(val_groups)),
                   **result}
            for i, name in enumerate(CLASSES):
                row[f"support_{name}"] = int((y_val == i).sum())
                row[f"predicted_{name}"] = int((pred == i).sum())
                row[f"recall_{name}"] = float((pred[y_val == i] == i).mean()) if (y_val == i).any() else np.nan
            row["confusion_matrix"] = json.dumps(cm.tolist())
            fold_rows.append(row)
        del cnn, lr, rf, scaler, inner_history
    if (assignments < 0).any() or any((pred < 0).any() for pred in predictions.values()):
        raise AssertionError("Some train/validation samples did not receive exactly one held-out fold prediction")
    fold_frame = pd.DataFrame(fold_rows)
    _write_csv(fold_frame, output_dir / "group_cv_fold_metrics.csv")
    _write_csv(pd.DataFrame(subject_assignments).sort_values("subject_id"), output_dir / "group_cv_subject_folds.csv")
    (output_dir / "group_cv_training_log.json").write_text(
        json.dumps({"scope": "original train+validation samples only; formal test not loaded",
                    "splitter": "StratifiedGroupKFold", "n_splits": CV_FOLDS, "seed": SEED,
                    "subjects": int(len(set(groups))), "samples": int(len(y)),
                    "strict_group_disjointness_checked": True, "folds": fold_log},
                   ensure_ascii=False, indent=2), encoding="utf-8")
    summary_rows = []
    for model_name in predictions:
        rows = fold_frame[fold_frame.model.eq(model_name)]
        oof = predictions[model_name]
        pooled = _class_vector_metrics(y, oof)
        summary_rows.append({"model": model_name, "folds": CV_FOLDS,
                             "accuracy_mean": float(rows.accuracy.mean()), "accuracy_std": float(rows.accuracy.std(ddof=1)),
                             "macro_f1_mean": float(rows.macro_f1_present_classes.mean()),
                             "macro_f1_std": float(rows.macro_f1_present_classes.std(ddof=1)),
                             "pooled_oof_accuracy": pooled["accuracy"],
                             "pooled_oof_macro_f1_present_classes": pooled["macro_f1_present_classes"],
                             **{f"recall_{name}_mean": float(rows[f"recall_{name}"].mean()) for name in CLASSES},
                             **{f"recall_{name}_std": float(rows[f"recall_{name}"].std(ddof=1)) for name in CLASSES},
                             **{f"support_{name}_total": int(np.bincount(y, minlength=4)[i]) for i, name in enumerate(CLASSES)}})
        pred_frame = pd.DataFrame({"fold": assignments, "sample_id": sample_ids, "record_id": record_ids,
                                   "subject_id": groups, "annotation_sample": annotation_samples,
                                   "true_class": [CLASSES[i] for i in y],
                                   "predicted_class": [CLASSES[i] for i in oof], "correct": oof == y})
        for class_id, name in enumerate(CLASSES):
            pred_frame[f"probability_{name}"] = probabilities[model_name][:, class_id]
        _write_csv(pred_frame, output_dir / f"group_cv_oof_predictions_{model_name}.csv")
    summary = pd.DataFrame(summary_rows)
    _write_csv(summary, output_dir / "group_cv_summary.csv")
    _plot_group_cv(fold_frame, figure_dir)
    return fold_frame, summary, {"folds": fold_log, "subjects": len(set(groups)), "samples": len(y)}


def _plot_group_cv(folds: pd.DataFrame, figure_dir: Path) -> None:
    models = ["logistic_regression", "random_forest", "cnn_1d"]
    fig, axes = plt.subplots(1, 2, figsize=(13, 5))
    x = np.arange(CV_FOLDS); width = .24
    for model_index, model in enumerate(models):
        frame = folds[folds.model.eq(model)].sort_values("fold")
        axes[0].bar(x + (model_index - 1) * width, frame.macro_f1_present_classes,
                    width, label=model)
        axes[1].bar(x + (model_index - 1) * width, frame.accuracy, width, label=model)
    for ax, title, ylabel in ((axes[0], "Macro-F1 by patient-held-out fold", "Macro-F1"),
                              (axes[1], "Accuracy by patient-held-out fold", "Accuracy")):
        ax.set_xticks(x, [f"Fold {i}" for i in range(1, CV_FOLDS + 1)])
        ax.set_ylim(0, 1.05); ax.set_ylabel(ylabel); ax.set_title(title); ax.grid(axis="y", alpha=.2); ax.legend(fontsize=8)
    fig.suptitle("Five-fold grouped CV | train + validation patients only | test set excluded")
    fig.text(.01, .005, "Outer folds are disjoint by subject. Macro-F1 averages classes present in each held-out fold; rare-class support varies by patient fold.", fontsize=8)
    fig.tight_layout(rect=(0, .04, 1, .92))
    figure_dir.mkdir(parents=True, exist_ok=True)
    fig.savefig(figure_dir / "group_cv_fold_metrics.png", dpi=300, bbox_inches="tight"); plt.close(fig)
    fig, axes = plt.subplots(len(models), CV_FOLDS, figsize=(14, 8), squeeze=False)
    for r, model in enumerate(models):
        frame = folds[folds.model.eq(model)].sort_values("fold")
        for c, row in enumerate(frame.itertuples()):
            cm = np.asarray(json.loads(row.confusion_matrix), dtype=float)
            den = cm.sum(axis=1, keepdims=True)
            normalized = np.divide(cm, den, out=np.zeros_like(cm), where=den > 0)
            ax = axes[r, c]; im = ax.imshow(normalized, vmin=0, vmax=1, cmap="Blues")
            ax.set_xticks(range(4), CLASSES); ax.set_yticks(range(4), CLASSES)
            ax.set_title(f"{model} | fold {row.fold}\nF support={getattr(row, 'support_F')}", fontsize=7)
            ax.set_xlabel("predicted"); ax.set_ylabel("true")
            for i in range(4):
                for j in range(4):
                    ax.text(j, i, f"{normalized[i,j]:.2f}\n({int(cm[i,j])})", ha="center", va="center", fontsize=6,
                            color="white" if normalized[i,j] > .55 else "black")
    fig.suptitle("Grouped CV row-normalized confusion matrices (cell counts shown)")
    fig.tight_layout(rect=(0, 0, 1, .96))
    fig.savefig(figure_dir / "group_cv_confusion_matrices.png", dpi=300, bbox_inches="tight"); plt.close(fig)


def repair_split_class_counts(dataset: Path, subject_counts: pd.DataFrame) -> pd.DataFrame:
    """Correct derived coverage fields without changing samples, labels, or split membership."""
    rows = []
    for split, group in subject_counts.groupby("split", sort=False):
        for class_id, name in enumerate(CLASSES):
            support = group[group[name] > 0]
            rows.append({"split": split, "aami_label": name, "class_id": class_id,
                         "sample_count": int(group[name].sum()),
                         "subject_count": int(support.subject_id.nunique()),
                         "record_count": int(support.record_count.sum())})
    frame = pd.DataFrame(rows)
    _write_csv(frame, dataset / "split_class_counts.csv")
    return frame


def _md_table(frame: pd.DataFrame, digits: int = 3) -> str:
    if frame.empty:
        return "_无可报告条目。_"
    view = frame.copy()
    for col in view.select_dtypes(include=["float"]).columns:
        view[col] = view[col].map(lambda x: "—" if pd.isna(x) else f"{x:.{digits}f}")
    headers = [str(c) for c in view.columns]
    lines = ["| " + " | ".join(headers) + " |", "| " + " | ".join("---" for _ in headers) + " |"]
    lines.extend("| " + " | ".join(str(x).replace("|", "\\|") for x in row) + " |"
                 for row in view.itertuples(index=False, name=None))
    return "\n".join(lines)


def _write_distribution_figures(subject_counts: pd.DataFrame, coverage: pd.DataFrame,
                                figure_dir: Path) -> list[dict]:
    figure_dir.mkdir(parents=True, exist_ok=True)
    plot = subject_counts.sort_values(["split", "subject_id"], key=lambda s: s.map({"train": 0, "val": 1, "test": 2}) if s.name == "split" else s)
    labels = [f"{row.subject_id} ({row.split})" for row in plot.itertuples()]
    values = plot[list(CLASSES)].to_numpy(dtype=float)
    fig, ax = plt.subplots(figsize=(9, max(10, .27 * len(plot))))
    image = ax.imshow(np.log10(values + 1), aspect="auto", cmap="magma")
    ax.set_yticks(np.arange(len(labels)), labels, fontsize=7)
    ax.set_xticks(np.arange(len(CLASSES)), CLASSES); ax.set_xlabel("AAMI class")
    ax.set_title("Included N/S/V/F beats per subject | log10(count + 1)")
    for r in range(values.shape[0]):
        for c in range(values.shape[1]):
            if values[r, c] > 0:
                ax.text(c, r, f"{int(values[r,c])}", ha="center", va="center", fontsize=6,
                        color="white" if np.log10(values[r,c] + 1) > 2.0 else "black")
    fig.colorbar(image, ax=ax, label="log10(count + 1)")
    fig.text(.01, .003, "MIT-BIH 1.0.0, 44 non-paced records; source patients 201 and 202 are one group; counts are post-preprocessing model samples.", fontsize=7)
    fig.tight_layout(rect=(0, .02, 1, 1))
    fig.savefig(figure_dir / "subject_class_counts_heatmap.png", dpi=300, bbox_inches="tight"); plt.close(fig)

    fig, axes = plt.subplots(2, 2, figsize=(14, 8))
    for ax, name in zip(axes.flat, CLASSES):
        frame = subject_counts.sort_values(name, ascending=False).head(14).sort_values(name)
        ax.barh(frame.subject_id, frame[name], color={"N": "#4c78a8", "S": "#f58518", "V": "#e45756", "F": "#72b7b2"}[name])
        ax.set_title(f"{name}: top patient supports")
        ax.set_xlabel("included samples across all splits")
        ax.set_ylabel("subject group")
        ax.grid(axis="x", alpha=.2)
    fig.suptitle("Patient concentration by class | all 44-record experiment groups")
    fig.text(.01, .003, "Counts are beat windows; the plot shows concentration, not population prevalence.", fontsize=8)
    fig.tight_layout(rect=(0, .02, 1, .94))
    fig.savefig(figure_dir / "top_subject_class_concentration.png", dpi=300, bbox_inches="tight"); plt.close(fig)
    return [
        {"file": "subject_class_counts_heatmap.png", "explanation": "每位受试者各类心拍支持数。使用 log10(count+1) 显示数量级，空格代表该受试者在该类没有可训练样本。"},
        {"file": "top_subject_class_concentration.png", "explanation": "各类别心拍最多的受试者，展示 F、S 等类别由少数患者主导的程度。"},
    ]


def _build_report(root: Path, out: Path, subject_counts: pd.DataFrame, coverage: pd.DataFrame,
                  concentration: pd.DataFrame, split_class_counts: pd.DataFrame,
                  subject_metrics: pd.DataFrame, errors: pd.DataFrame, prediction_shares: pd.DataFrame,
                  weight_metrics: pd.DataFrame, weight_classes: pd.DataFrame,
                  cross_model_weight_reference: pd.DataFrame,
                  cv_folds: pd.DataFrame, cv_summary: pd.DataFrame,
                  preprocess: dict, checkpoints: dict, plot_catalog: list[dict]) -> Path:
    overall = subject_counts.groupby("subject_id", as_index=False)[list(CLASSES)].sum()
    total_counts = {name: int(overall[name].sum()) for name in CLASSES}
    overall_total = sum(total_counts.values())
    distribution = pd.DataFrame([{"Class": name, "Included beats": total_counts[name],
                                  "Share %": total_counts[name] / overall_total * 100}
                                 for name in CLASSES])
    coverage_report = coverage[["split", "class", "subjects_with_class", "subjects_total", "subject_coverage_pct",
                                "sample_count", "top_subject_id", "top_subject_share_pct"]].copy()
    concentration_report = concentration[["class", "subjects_with_class", "top_subject_id", "top_subject_samples",
                                          "top_subject_share_pct", "top3_subject_share_pct",
                                          "effective_subject_count_2pow_entropy"]].copy()
    class_share = prediction_shares.pivot(index="model", columns="class", values="predicted_share_pct").reset_index()
    true_share = prediction_shares.groupby("class").true_share_pct.first().to_dict()
    class_share.insert(1, "validation true share", "")
    # Test proportions are retrospective context only; the detailed source table is explicitly marked descriptive.
    pred_test = prediction_shares.pivot(index="model", columns="class", values="predicted_share_pct").reset_index()
    metrics_report = subject_metrics[["model", "subject_id", "records", "sample_count", "accuracy",
                                      "macro_f1_present_classes", "supported_classes", "recall_N", "recall_S", "recall_V", "recall_F"]].copy()
    metrics_report = metrics_report.sort_values(["subject_id", "model"])
    error_summary = (errors.groupby(["model", "true_class", "predicted_class"], as_index=False)
                     .agg(error_count=("count", "sum"))
                     .sort_values(["model", "error_count"], ascending=[True, False]))
    weight_summary = weight_metrics[["strategy", "split", "accuracy", "macro_f1_present_classes", "predicted_share_N",
                                     "predicted_share_S", "predicted_share_V", "predicted_share_F"]].copy()
    cross_weight_report = cross_model_weight_reference[["model", "condition", "accuracy", "macro_f1",
                                                        "recall_S", "predicted_share_S", "recall_F",
                                                        "predicted_share_F"]].copy()
    cv_view = cv_summary[["model", "accuracy_mean", "accuracy_std", "macro_f1_mean", "macro_f1_std",
                          "pooled_oof_macro_f1_present_classes", "recall_N_mean", "recall_S_mean", "recall_V_mean", "recall_F_mean"]]
    cv_support = cv_folds[["model", "fold", "validation_subject_count", "validation_sample_count",
                           "support_N", "support_S", "support_V", "support_F", "macro_f1_present_classes"]].copy()
    test_subject_counts = subject_counts[subject_counts.split.eq("test")].sort_values("subject_id")[["subject_id", *CLASSES, "total_samples"]]
    findings = []
    train_coverage = coverage[coverage.split.eq("train")].set_index("class")
    val_coverage = coverage[coverage.split.eq("val")].set_index("class")
    test_coverage = coverage[coverage.split.eq("test")].set_index("class")
    findings.append(f"- N/S/V/F 样本量为 {total_counts['N']:,}/{total_counts['S']:,}/{total_counts['V']:,}/{total_counts['F']:,}；最少 F 占 {total_counts['F']/overall_total*100:.2f}%。")
    findings.append(f"- F 类仅由 {int(concentration.set_index('class').loc['F','subjects_with_class'])} 个受试者提供；最大单患者占该类 {float(concentration.set_index('class').loc['F','top_subject_share_pct']):.1f}%。")
    findings.append(f"- 测试集中 F 的 {int(test_coverage.loc['F','sample_count']):,} 拍中，{float(test_coverage.loc['F','top_subject_share_pct']):.1f}% 来自 {test_coverage.loc['F','top_subject_id']}；这组结果不能代表跨患者 F 泛化的稳定估计。")
    findings.append(f"- 验证集 S 有 {int(val_coverage.loc['S','sample_count']):,} 拍，但 {float(val_coverage.loc['S','top_subject_share_pct']):.1f}% 来自 {val_coverage.loc['S','top_subject_id']}；训练与验证患者的类别构成不同。")
    preprocess_ok = all([preprocess["all_labels_match_public_mapping"], preprocess["all_target_ids_match_N_S_V_F"],
                         preprocess["all_original_annotations_match_WFDB_ATR"], preprocess["window_0p3s_before_0p4s_after_253_samples"],
                         preprocess["all_included_samples_use_MLII"], preprocess["split_npz_order_and_labels_match_metadata"],
                         preprocess["subject_overlap_count"] == 0])
    weight_val = weight_metrics[weight_metrics.split.eq("val")].set_index("strategy")
    full_s = float(weight_val.loc["full_inverse", "predicted_share_S"])
    full_f = float(weight_val.loc["full_inverse", "predicted_share_F"])
    plain_s = float(weight_val.loc["unweighted", "predicted_share_S"])
    plain_f = float(weight_val.loc["unweighted", "predicted_share_F"])
    text = """# MIT-BIH N/S/V/F 四分类失败诊断

> 范围声明：正式测试集已在前一阶段被查看。本报告读取原有测试预测 CSV、混淆矩阵和波形，仅作回顾性错误分析；没有用测试集训练/调参、比较新权重或挑选方案。新增权重策略仅用既有 train/validation；分组交叉验证只用 train+validation（37 个受试者组），不打开 `test.npz`。这些 CV 是探索性稳定性诊断，模型设置和早停规则曾在此前训练过程中确定，因此不称为全新独立测试。

## 结论摘要

""" + "\n".join(findings) + f"""
- 预处理审计结果：{"标签/标注/窗口/导联/NPZ 对齐检查均通过" if preprocess_ok else "有检查未通过，见 `preprocessing_audit.json`"}。但发现并修正了派生统计 CSV 中 `subject_count`/`record_count` 对每个类别重复写入整个 split 记录数的代码错误；仅更新该汇总字段，没有改动样本、标签、划分、模型或原始文件。
- 类别权重影响具有模型依赖性：CNN 验证集全逆频率方案的 S/F 预测占比分别为 {full_s:.2f}%/{full_f:.2f}%，无权重为 {plain_s:.2f}%/{plain_f:.2f}%；同时少数类 Recall 的提高伴随 N 识别和少数类 Precision 的变化。随机森林原有验证结果没有出现相同方向的 S/F 过度预测。
- 所有新权重实验和 CV 不读取正式测试集。测试受试者指标及 ECG 错误图均在标题和文件名中标记为回顾性描述。

## 数据与患者间分布

四类有效窗口总计 {overall_total:,} 拍。这里的样本数指通过窗口与信号有效性规则、实际进入模型 NPZ 的心拍，而不是全部原始 annotation 数。

{_md_table(distribution)}

### 按划分统计的类别覆盖

`subjects_with_class / subjects_total` 是该划分中至少有一拍该类的患者覆盖率；患者 ID `subject_201_202` 合并了记录 201 与 202。

{_md_table(coverage_report)}

### 患者集中度

“有效受试者数”按心拍份额熵计算，用于描述分布集中度，不是独立样本数。

{_md_table(concentration_report)}

![受试者×类别支持数热力图](../../figures/11_four_class_diagnosis/subject_class_counts_heatmap.png)

![各类心拍的患者集中度](../../figures/11_four_class_diagnosis/top_subject_class_concentration.png)

患者间差异的主要事实：训练集 F 有 {int(train_coverage.loc['F','subjects_with_class'])}/{int(train_coverage.loc['F','subjects_total'])} 个受试者提供，且单个患者贡献 {float(train_coverage.loc['F','top_subject_share_pct']):.1f}%；验证集 S 由患者 232 主导；正式测试 F 几乎全部来自患者 208。这样的 split 使少数类性能很容易被一个患者的形态与信号特征主导。

## 逐受试者模型表现：锁定测试集回顾

本节仅描述已查看的正式测试预测，不用于选择模型或权重。每位患者的 Macro-F1 仅对该患者真实标签中出现的类别求平均；若该患者没有某类真实样本，该类 Recall 留空而不计算。

{_md_table(metrics_report)}

![受试者级测试指标热力图](../../figures/11_four_class_diagnosis/per_subject_test_metrics_descriptive_only.png)

### 测试集误分类方向

{_md_table(error_summary.head(24))}

CNN 测试标签支持与预测份额已保存于 `test_prediction_class_shares_descriptive_only.csv`。CNN 的主要误分方向包括 N→S、F→N、F→V；其中 F 来源受试者高度集中，因此波形对比用于查看实际例子，不代表完整的患者间机制。

![CNN 典型错误心拍波形](../../figures/11_four_class_diagnosis/cnn_test_error_waveforms_descriptive_only.png)

图中每个面板注明 record、subject、标注样本、时间、原始专家符号与 AAMI 真实/预测类别。曲线使用滤波后物理单位 mV，标注点为 t=0；测试波形只作已暴露数据的定性说明。

## 类别权重策略：train 拟合、validation 比较

比较同一固定 1D-CNN 架构与 seed 的四种训练损失权重：无权重；平滑逆频率 `sqrt(N/(K*n_c))`；将 mean-one inverse-balanced 向量截断至 10 后重新 mean-one；现有全逆频率 `N/(K*n_c)`。各权重只由 train 标签计算。检查点按 validation Macro-F1 早停，所以该验证比较属于探索性结果，validation 并非独立调参集。

{_md_table(weight_summary)}

### Validation 每类 Precision / Recall / F1 与预测占比

{_md_table(weight_classes[weight_classes.split.eq('val')][['strategy','class','class_weight','support','predicted_count','predicted_share_pct','precision','recall','f1']])}

### LR/RF 与 CNN 既有加权/无权重验证对照

下表直接复用此前保存的 validation-only 消融；该文件记录未加载 test。它用于判断权重效应是否跨模型一致，不是新拟合或模型选择。

{_md_table(cross_weight_report)}

![权重方案的训练与验证指标及预测份额](../../figures/11_four_class_diagnosis/cnn_weight_strategies_train_val.png)
![传统模型与 CNN 既有加权验证对照](../../figures/11_four_class_diagnosis/existing_model_weight_ablation_validation.png)

绝对权重不能单独证明原因；更强的证据是同一 CNN 与相同 train/validation 下的策略对照。如果全逆频率提升 S/F Recall，却显著提高少数类预测占比并压低 Precision，则“过度预测”是可观测的代价。平滑/截断方案应结合 Macro-F1、类别 Recall/Precision 与训练-验证差值判断，不按 Accuracy 单项选择。

## 严格受试者分组交叉验证

使用固定配置的五折 `StratifiedGroupKFold`，只输入原 train 与 validation 的 {int(cv_summary.iloc[0].get('cv_samples',0)):,} 拍、{int(cv_summary.iloc[0].get('subjects',0))} 个患者组；实际样本/患者总数以 `group_cv_training_log.json` 为准。外层每位患者只作一次 OOF 评估，外层训练与验证患者集合无交集。CNN 早停内层也按患者分组，并使用内层最佳 epoch 在完整外层训练组上重拟合。每折均只使用该折训练患者拟合标量归一化与类别权重。

{_md_table(cv_view)}

### 每折样本支持与 Macro-F1

{_md_table(cv_support)}

![五折患者分组 CV 指标](../../figures/11_four_class_diagnosis/group_cv_fold_metrics.png)

![五折患者分组 CV 混淆矩阵](../../figures/11_four_class_diagnosis/group_cv_confusion_matrices.png)

fold 间 F 的验证支持数差异很大；Macro-F1 与类别 Recall 的折间波动是稳定性信息，而非单个最高折表现。分层以心拍为辅助目标但不拆患者；患者组成不均仍然限制估计。由于现有训练配置/早停设计此前看过原验证集，本 CV 是严格无组泄漏的探索性结果，不可宣称为完全未触碰的外部验证。

## 预处理、导联、窗口与标签程序审计

| 检查项 | 结果 |
|---|---|
| WFDB 原始 annotation 样本位置与 symbol 对照 | {preprocess['all_original_annotations_match_WFDB_ATR']} |
| 显式 AAMI 映射与 N/S/V/F 整数标签对照 | {preprocess['all_labels_match_public_mapping']} / {preprocess['all_target_ids_match_N_S_V_F']} |
| 非心拍、Q 类、未知标注进入四分类 NPZ | 不进入；只保留在 metadata 与排除计数 |
| MLII 选择规则与实际使用导联 | {preprocess['lead_selection_matches_header_policy']} / MLII only = {preprocess['all_included_samples_use_MLII']} |
| 0.3 秒前、0.4 秒后，253 样本，中心索引 108 | {preprocess['window_0p3s_before_0p4s_after_253_samples']} |
| NPZ 顺序、标签与 metadata | {preprocess['split_npz_order_and_labels_match_metadata']} |
| 受试者交叉与 201/202 同组 | overlap={preprocess['subject_overlap_count']}；pair same split={preprocess['record_201_202_same_split']} |
| 归一化拟合分区 | {preprocess['normalizer_fit_split']} |
| 滤波通带 | {preprocess['filter_low_high_hz']} Hz，双向零相位离线滤波 |
| LR/RF/CNN 正式权重文件读取 | {checkpoints['checkpoints_loadable']}；CNN best epoch={checkpoints['cnn_best_epoch']} |

没有发现 AAMI 目标映射、专家标注位置、导联选择、窗口长度或 NPZ 行对齐的程序性不一致。发现的程序性统计问题限于 `split_class_counts.csv` 中 `subject_count`/`record_count` 字段：原代码对每类重复写了 split 总数；现已修复生成逻辑，并按现有 metadata 更新此派生表。该问题不影响模型使用的 `train/val/test.npz` 或实验指标。

## 发现分级与建议

### 已由实验支持的发现

- 类别明显不平衡，尤其 F 仅 {total_counts['F']:,} 个有效心拍、集中于 {int(concentration.set_index('class').loc['F','subjects_with_class'])} 位受试者；测试 F 几乎全来自一个患者。
- S/F 患者覆盖比总心拍数更关键：相同类别在 train/validation/test 的患者覆盖和患者占比变化明显。
- 全逆频率 CNN 验证时少数类 Recall 提高，但 N Recall/Macro-F1 与 Precision 会交换；CNN 与 RF 的响应不同，因此不能笼统归因为“所有类别权重都太大”。
- 逐拍窗口仅包含局部形态，不含显式前后 RR 或节律上下文；N→S 与 F→N/V 形态混淆在已查看预测中确实发生。
- 除 `split_class_counts.csv` 的统计字段外，源标注、标签映射、MLII、窗口与数据行对齐审计通过。

### 需要进一步验证的猜想

- 训练 F 主要来自患者 213，而留出 F 主要来自患者 208，模型可能把患者/记录特有形态学到为 F 判据；需要更多独立 F 患者或外部 ECG 数据验证。
- N→S 错误可能受 S/N 形态重叠、节律信息缺失、记录增益与患者差异共同影响；仅凭静态波形不能拆分其贡献。
- F 作为融合心拍本身包含不同形态成分，单个 253 点窗口可能不足以表征其与前后心拍的关系；需要对 beat-centered context/RR 特征做受试者分组实验。
- 全逆频率下 F 预测的校准可能不佳；本阶段未做阈值选择、概率校准或测试集优化。

### 数据本身的限制

- MIT-BIH 是有限的历史 Holter 数据库，受试者数量和罕见类别的患者覆盖有限；心拍数量不能替代独立受试者数量。
- 四类任务的患者切分沿用了 N/V 分区，未针对 S/F 覆盖设计；当前验证/测试留出的稀有类别支持数非常小且高度患者集中。
- AAMI N 是聚合组，包含多种原始 expert beat 符号；F/S 并非每位受试者均有标注。官方标签也不构成对每个心拍的临床诊断建议。
- 双向滤波是离线处理，部署到实时系统需重新设计因果滤波与延迟控制。

### 课程项目最值得实施的改进

1. 以患者为最小评估单位继续报告 Macro-F1、各类 Recall/Precision、患者覆盖和折间方差；保留现有测试结果为历史结果，后续只新增患者级外部或嵌套分组验证。
2. 优先增加 F 与 S 的患者多样性；课程项目可先使用固定手工权重方案做 train/validation 消融，并报告少数类 Precision/Recall 的取舍，不根据测试集选权重。
3. 对 F、S 比较单心拍与短序列/RR 上下文特征，以及 patient-balanced 的训练采样；只在训练折内部估计任何重采样和变换。
4. 加入按患者/记录的错误案例复核、置信度校准和敏感性分析；不要把更高 Accuracy 当作唯一成功标准。
5. 冻结当前已暴露的测试集结果，未来若需无偏最终评估，应收集未参与探索的新受试者或使用预先锁定的外部数据。

## 输出文件

- 受试者类计数/覆盖/集中度：`results/classification/nsvf44_v1/diagnosis/subject_*.csv`
- 患者级测试指标与误分类：`results/classification/nsvf44_v1/diagnosis/per_subject_test_*_descriptive_only.csv`
- 权重策略及训练日志：`results/classification/nsvf44_v1/diagnosis/weight_strategy_*.csv/json`
- 分组 CV 指标、OOF 预测、fold 患者清单：`results/classification/nsvf44_v1/diagnosis/group_cv_*`
- 诊断图片目录：`figures/11_four_class_diagnosis/`
- 完整诊断检查清单：`results/classification/nsvf44_v1/diagnosis/preprocessing_audit.json`
"""
    # Add explicit training/validation category-shares table without implying test selection.
    trainval_shares = weight_metrics[["strategy", "split", "accuracy", "macro_f1_present_classes",
                                      "recall_N", "recall_S", "recall_V", "recall_F"]]
    chart_section = "## 诊断图逐图说明\n\n"
    for entry in plot_catalog:
        chart_section += (f"- [`{entry['file']}`](../../figures/11_four_class_diagnosis/{entry['file']}) — "
                          f"{entry['explanation']}\n")
    text = text.replace("## 输出文件\n", chart_section + "\n## 输出文件\n")
    text = text.replace("### Validation 每类 Precision / Recall / F1 与预测占比", "### Train/validation 每类 Precision / Recall / F1 与预测占比")
    text = text.replace(_md_table(weight_classes[weight_classes.split.eq("val")][['strategy','class','class_weight','support','predicted_count','predicted_share_pct','precision','recall','f1']]),
                        _md_table(weight_classes[['strategy','split','class','class_weight','support','predicted_count','predicted_share_pct','precision','recall','f1']]))
    # Keep a concise OOF fold summary table and do not use test outputs in model selection.
    text = text.replace("### 每折样本支持与 Macro-F1", "### 每折样本支持与 Macro-F1")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text, encoding="utf-8")
    return out


def run(root: Path, skip_weights: bool = False, skip_cv: bool = False) -> Path:
    root = root.resolve()
    result_dir = root / "results/classification/nsvf44_v1/diagnosis"
    figure_dir = root / "figures/11_four_class_diagnosis"
    result_dir.mkdir(parents=True, exist_ok=True); figure_dir.mkdir(parents=True, exist_ok=True)
    print("Building subject class coverage tables...", flush=True)
    subject_counts, coverage, concentration = build_subject_tables(root, result_dir)
    split_counts = repair_split_class_counts(root / "data/processed/mitdb44_nsvf_v1", subject_counts)
    print("Auditing annotation, labels, leads, windows, splits and saved checkpoints...", flush=True)
    preprocess = audit_preprocessing(root, result_dir)
    checkpoints = audit_checkpoints(root, result_dir)
    if skip_weights:
        weight_metrics = pd.read_csv(result_dir / "weight_strategy_train_val_metrics.csv", keep_default_na=False)
        weight_classes = pd.read_csv(result_dir / "weight_strategy_class_metrics.csv", keep_default_na=False)
    else:
        print("Fitting CNN weight strategies on train only; comparing train/validation...", flush=True)
        weight_metrics, weight_classes, _ = run_weight_strategies(root, result_dir, figure_dir)
    if skip_cv:
        cv_dir = result_dir / "group_cv_5fold"
        fold_metrics = pd.read_csv(cv_dir / "group_cv_fold_metrics.csv", keep_default_na=False)
        cv_summary = pd.read_csv(cv_dir / "group_cv_summary.csv", keep_default_na=False)
        cv_meta = _load_json(cv_dir / "group_cv_training_log.json")
        cv_summary["cv_samples"] = int(cv_meta["samples"]); cv_summary["subjects"] = int(cv_meta["subjects"])
        _write_csv(cv_summary, result_dir / "group_cv_summary.csv")
    else:
        print("Running five-fold grouped CV on train+validation only; formal test is excluded...", flush=True)
        fold_metrics, cv_summary, cv_meta = run_group_cv(root, result_dir / "group_cv_5fold", figure_dir)
        cv_summary["cv_samples"] = int(cv_meta["samples"]); cv_summary["subjects"] = int(cv_meta["subjects"])
        _write_csv(cv_summary, result_dir / "group_cv_summary.csv")
    cross_weight_reference = existing_cross_model_weight_reference(root, result_dir, figure_dir)
    print("Reading saved formal-test predictions for retrospective per-subject errors only...", flush=True)
    subject_metrics, errors, prediction_shares = retrospective_test_diagnostics(root, result_dir, figure_dir)
    catalog = _write_distribution_figures(subject_counts, coverage, figure_dir)
    catalog.extend([
        {"file": "per_subject_test_metrics_descriptive_only.png", "explanation": "既有锁定测试集按受试者分解的 Accuracy、present-class Macro-F1 与 Recall；无该类样本时留空。仅回顾性诊断。"},
        {"file": "cnn_test_error_waveforms_descriptive_only.png", "explanation": "CNN 在已查看测试集上的 N→S、F→N 与 F→V 代表波形，仅用于错误归因。"},
        {"file": "cnn_weight_strategies_train_val.png", "explanation": "同一 CNN 的 train/validation 指标及预测类别占比，比较无权重、平方根平滑、10 倍截断和全逆频率。"},
        {"file": "group_cv_fold_metrics.png", "explanation": "train+validation 的五折患者分组 CV，每折 Macro-F1 与 Accuracy，展示受试者间波动。"},
        {"file": "group_cv_confusion_matrices.png", "explanation": "每个分组 CV 外折的行归一化混淆矩阵，同时标出原始计数和 F 支持数。"},
        {"file": "existing_model_weight_ablation_validation.png", "explanation": "复用既有验证集加权/无权重消融，比较 LR、RF、CNN 对 S/F 的预测份额变化。"},
    ])
    (result_dir / "figure_catalog.json").write_text(json.dumps(catalog, ensure_ascii=False, indent=2), encoding="utf-8")
    report = _build_report(root, root / "reports/classification/four_class_failure_diagnosis.md",
                           subject_counts, coverage, concentration, split_counts, subject_metrics,
                           errors, prediction_shares, weight_metrics, weight_classes, cross_weight_reference, fold_metrics,
                           cv_summary, preprocess, checkpoints, catalog)
    manifest = {"status": "completed", "seed_weight_strategy": int(_load_json(root / "configs/multiclass_nsvf.json")["seed"]),
                "seed_group_cv": SEED, "cv_folds": CV_FOLDS, "formal_test_used_for_training_or_tuning": False,
                "formal_test_used_for_retrospective_subject_metrics_and_waveform_examples": True,
                "weight_training_inputs": ["train.npz", "val.npz"],
                "group_cv_inputs": ["train.npz", "val.npz"], "group_cv_subject_count": cv_meta["subjects"],
                "group_cv_sample_count": cv_meta["samples"], "report": report.relative_to(root).as_posix(),
                "diagnosis_figure_count": len(catalog), "preprocessing_audit": preprocess,
                "checkpoint_audit": checkpoints}
    (result_dir / "diagnosis_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    verification = verify_diagnosis(root)
    (result_dir / "diagnosis_verification.json").write_text(
        json.dumps(verification, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"status": "completed", "report": str(report), "results": str(result_dir),
                      "figures": str(figure_dir), "figure_count": len(catalog),
                      "test_data_used_for_new_fits": False, "verification_passed": verification["passed"]},
                     ensure_ascii=False, indent=2), flush=True)
    return report


def verify_diagnosis(root: Path) -> dict:
    """Verify generated artifacts, test isolation, patient grouping and report links."""
    root = root.resolve(); base = root / "results/classification/nsvf44_v1/diagnosis"
    figure_dir = root / "figures/11_four_class_diagnosis"
    report = root / "reports/classification/four_class_failure_diagnosis.md"
    subject_table = pd.read_csv(base / "subject_class_counts.csv", keep_default_na=False)
    coverage = pd.read_csv(base / "subject_class_coverage_by_split.csv", keep_default_na=False)
    split_counts = pd.read_csv(root / "data/processed/mitdb44_nsvf_v1/split_class_counts.csv")
    for row in split_counts.itertuples():
        frame = subject_table[subject_table.split.eq(row.split)]
        if int(frame[row.aami_label].sum()) != int(row.sample_count):
            raise AssertionError(f"Split class count mismatch: {row.split}/{row.aami_label}")
        if int((frame[row.aami_label] > 0).sum()) != int(row.subject_count):
            raise AssertionError(f"Class subject coverage mismatch: {row.split}/{row.aami_label}")
    trainval = []
    dataset = root / "data/processed/mitdb44_nsvf_v1"
    for split in ("train", "val"):
        with np.load(dataset / f"{split}.npz", allow_pickle=False) as part:
            trainval.append((part["sample_id"].astype(str).copy(), part["subject_id"].astype(str).copy()))
    expected_ids = set(np.concatenate([item[0] for item in trainval]))
    expected_subjects = set(np.concatenate([item[1] for item in trainval]))
    manifest = pd.read_csv(dataset / "split_manifest.csv", dtype={"record_id": str}, keep_default_na=False)
    test_subjects = set(manifest.loc[manifest.split.eq("test"), "subject_id"].astype(str))
    subject_folds = pd.read_csv(base / "group_cv_5fold/group_cv_subject_folds.csv", keep_default_na=False)
    if subject_folds.subject_id.duplicated().any() or set(subject_folds.subject_id.astype(str)) != expected_subjects:
        raise AssertionError("Grouped-CV subject assignment is incomplete or duplicated")
    if expected_subjects & test_subjects:
        raise AssertionError("Formal test subject entered grouped CV")
    expected_cv_ids = expected_ids
    for model in ("logistic_regression", "random_forest", "cnn_1d"):
        predictions = pd.read_csv(base / "group_cv_5fold" / f"group_cv_oof_predictions_{model}.csv",
                                  usecols=["sample_id", "subject_id", "fold", "true_class", "predicted_class"])
        if (len(predictions) != len(expected_cv_ids) or predictions.sample_id.duplicated().any()
                or set(predictions.sample_id.astype(str)) != expected_cv_ids):
            raise AssertionError(f"Grouped-CV OOF predictions do not cover train+validation exactly once: {model}")
        if set(predictions.subject_id.astype(str)) & test_subjects:
            raise AssertionError(f"Formal test subject leaked into OOF outputs: {model}")
    metrics = pd.read_csv(base / "per_subject_test_metrics_descriptive_only.csv")
    for name in CLASSES:
        support = metrics[f"support_{name}"]
        recall = metrics[f"recall_{name}"]
        if recall[support.eq(0)].notna().any() or recall[support.gt(0)].isna().any():
            raise AssertionError(f"Per-subject recall policy mismatch for class {name}")
    weight_log = _load_json(base / "weight_strategy_training_log.json")
    cv_log = _load_json(base / "group_cv_5fold/group_cv_training_log.json")
    existing_ablation = _load_json(root / "results/classification/nsvf44_v1/class_weight_validation_ablation.json")
    if ("not loaded" not in weight_log.get("scope", "").lower()
            or "not loaded" not in cv_log.get("scope", "").lower()):
        raise AssertionError("Weight/CV input scope declarations are missing")
    if existing_ablation.get("test_partition_loaded") is not False:
        raise AssertionError("Cross-model reference ablation accessed formal test data")
    catalog = _load_json(base / "figure_catalog.json")
    paths = sorted(figure_dir.glob("*.png"))
    if len(paths) != len(catalog):
        raise AssertionError(f"Diagnosis figure catalog mismatch: {len(paths)} vs {len(catalog)}")
    for path in paths:
        with Image.open(path) as image:
            dpi = image.info.get("dpi")
            if not dpi or dpi[0] < 299 or dpi[1] < 299:
                raise AssertionError(f"Diagnosis figure is not saved at 300 dpi: {path}")
    body = report.read_text(encoding="utf-8")
    missing_links = [entry["file"] for entry in catalog
                     if f"../../figures/11_four_class_diagnosis/{entry['file']}" not in body
                     or not (report.parent / "../../figures/11_four_class_diagnosis" / entry["file"]).resolve().is_file()]
    if missing_links:
        raise AssertionError(f"Missing or broken diagnosis report figure links: {missing_links}")
    return {"passed": True, "formal_test_used_for_new_fits": False,
            "test_predictions_used_descriptively_only": True,
            "train_validation_cv_samples": len(expected_cv_ids), "train_validation_subject_groups": len(expected_subjects),
            "test_subject_overlap_with_cv": 0, "all_oof_samples_covered_once_per_model": True,
            "per_subject_missing_class_recall_omitted": True, "corrected_split_class_coverage_verified": True,
            "figure_count": len(paths), "figure_minimum_dpi": 300,
            "report_figure_links_resolve": True, "weight_ablation_test_free": True}


def main() -> None:
    parser = argparse.ArgumentParser(description="Diagnose patient-dependent N/S/V/F failure without test tuning")
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument("--skip-weights", action="store_true", help="reuse saved weight-strategy outputs")
    parser.add_argument("--skip-cv", action="store_true", help="reuse saved grouped-CV outputs")
    args = parser.parse_args()
    run(args.root, skip_weights=args.skip_weights, skip_cv=args.skip_cv)


if __name__ == "__main__":
    main()

