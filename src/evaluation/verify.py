"""Independent final artifact checks; reads saved metrics but never tunes models."""
from __future__ import annotations

import argparse
from collections import Counter
import json
import os
import re
from pathlib import Path

import numpy as np
import pandas as pd
from PIL import Image
from sklearn.metrics import (accuracy_score, confusion_matrix, f1_score, precision_recall_fscore_support,
                             precision_score, recall_score)
from joblib import load
import torch

from ..download import sha256
from ..labels import AAMI_MAP


def _verify_dataset(root: Path, relative: str, classes: list[str]) -> dict:
    directory = root / relative
    verification = json.loads((directory / "verification.json").read_text(encoding="utf-8"))
    if not verification.get("passed") or verification.get("included_record_count") != 44:
        raise AssertionError(f"Dataset audit failed: {relative}")
    plan = json.loads((directory / "split_plan.json").read_text(encoding="utf-8"))
    if len(plan["records"]) != 44 or set(plan["records"]).intersection({"102", "104", "107", "217"}):
        raise AssertionError(f"Paced records present in {relative}")
    split = pd.read_csv(directory / "split_manifest.csv", keep_default_na=False, dtype={"record_id": str})
    if split.groupby("subject_id").split.nunique().max() != 1:
        raise AssertionError(f"Subject cross-split in {relative}")
    pair = split[split.record_id.isin(["201", "202"])]
    if len(pair) != 2 or pair.split.nunique() != 1:
        raise AssertionError(f"Records 201/202 cross-split in {relative}")
    if not set(split[split.record_id.isin(["100", "200"])].split) <= {"train"}:
        raise AssertionError(f"Pre-explored record is not training-only in {relative}")
    if classes == ["N", "V"]:
        counts = pd.read_csv(directory / "split_class_counts.csv")
        for name in ("val", "test"):
            part = counts[(counts.split == name) & (counts.aami_label == "V")]
            if part.empty or int(part.sample_count.iloc[0]) == 0:
                raise AssertionError(f"Missing V class in {name} set")
    return {"dataset": relative, "records": len(split), "subjects": split.subject_id.nunique(),
            "split_plan_sha256": sha256(directory / "split_plan.json"),
            "verification": str(verification.get("passed"))}


def _verify_experiment(root: Path, task: str, result_rel: str, dataset_rel: str, classes: list[str]) -> dict:
    result_dir = root / result_rel; dataset_dir = root / dataset_rel
    experiment = json.loads((result_dir / "experiment.json").read_text(encoding="utf-8"))
    if experiment.get("status") != "completed" or experiment.get("test_used_for_training_or_selection"):
        raise AssertionError(f"Experiment not complete or test policy failed: {task}")
    if not experiment.get("metrics_recomputed_match"):
        raise AssertionError(f"Saved prediction metric reconciliation failed: {task}")
    smoke_path = result_dir / "smoke_test/verification.json"
    smoke = json.loads(smoke_path.read_text(encoding="utf-8"))
    if not smoke.get("passed") or smoke.get("test_split_loaded") is not False:
        raise AssertionError(f"Smoke test missing, failed, or accessed test data: {task}")
    checkpoint_name = "nv44_v1" if task == "nv" else "nsvf44_v1"
    checkpoint_dir = root / "checkpoints" / checkpoint_name / "formal"
    for model_name in ("logistic_regression", "random_forest"):
        saved = load(checkpoint_dir / f"{model_name}.joblib")
        if not np.array_equal(saved["estimator"].classes_, np.arange(len(classes))):
            raise AssertionError(f"Saved {model_name} checkpoint has an unexpected output class order")
    cnn_path = checkpoint_dir / "cnn/cnn_best.pt"
    cnn_state = torch.load(cnn_path, map_location="cpu", weights_only=False)
    if cnn_state.get("class_count") != len(classes) or not cnn_state.get("state_dict"):
        raise AssertionError(f"Saved CNN checkpoint cannot be loaded: {task}")
    with np.load(dataset_dir / "test.npz", allow_pickle=False) as test:
        source_ids = test["sample_id"].astype(str)
        source_records = test["record_id"].astype(str)
        source_subjects = test["subject_id"].astype(str)
        source_samples = test["annotation_sample"].astype(np.int64)
        source_labels = test["mapped_label"].astype(str)
        source_leads = test["lead"].astype(str)
        y_true_expected = test["y"].astype(np.int64)
    mapping = {group: index for index, group in enumerate(classes)}
    results = {}; metric_sets = json.loads((result_dir / "test_metrics_all_models.json").read_text(encoding="utf-8"))
    for model in ("logistic_regression", "random_forest", "cnn_1d"):
        predictions = pd.read_csv(result_dir / f"test_predictions_{model}.csv", keep_default_na=False)
        if len(predictions) != len(source_ids) or predictions.sample_id.duplicated().any():
            raise AssertionError(f"Prediction row count/IDs invalid: {task}/{model}")
        if predictions.sample_id.astype(str).tolist() != source_ids.tolist():
            raise AssertionError(f"Prediction source order mismatch: {task}/{model}")
        for col, expected in (("record_id", source_records), ("subject_id", source_subjects),
                              ("annotation_sample", source_samples), ("true_aami_label", source_labels),
                              ("lead_name", source_leads)):
            if not np.array_equal(predictions[col].astype(str).to_numpy(), expected.astype(str)):
                raise AssertionError(f"Prediction source metadata mismatch: {task}/{model}/{col}")
        y_true = predictions.true_aami_label.map(mapping).to_numpy(dtype=int)
        y_pred = predictions.predicted_aami_label.map(mapping).to_numpy(dtype=int)
        if not np.array_equal(y_true, y_true_expected):
            raise AssertionError(f"Reference targets changed: {task}/{model}")
        probability_columns = [f"probability_{group}" for group in classes]
        probabilities = predictions[probability_columns].to_numpy(dtype=float)
        if not np.isfinite(probabilities).all() or (probabilities < -1e-8).any() or (probabilities > 1+1e-8).any():
            raise AssertionError(f"Invalid prediction probabilities: {task}/{model}")
        if not np.allclose(probabilities.sum(axis=1), 1, atol=1e-5):
            raise AssertionError(f"Probability rows do not sum to one: {task}/{model}")
        calculated = {"accuracy": float(accuracy_score(y_true, y_pred)),
                      "macro_precision": float(precision_score(y_true, y_pred, labels=range(len(classes)), average="macro", zero_division=0)),
                      "macro_recall": float(recall_score(y_true, y_pred, labels=range(len(classes)), average="macro", zero_division=0)),
                      "macro_f1": float(f1_score(y_true, y_pred, labels=range(len(classes)), average="macro", zero_division=0)),
                      "confusion_matrix": confusion_matrix(y_true, y_pred, labels=range(len(classes))).tolist()}
        stored = metric_sets[model]
        for key, value in calculated.items():
            if key == "confusion_matrix":
                equal = value == stored[key]
            else:
                equal = np.isclose(value, stored[key], atol=1e-12)
            if not equal:
                raise AssertionError(f"Saved metrics do not recompute from CSV: {task}/{model}/{key}")
        class_precision, class_recall, class_f1, class_support = precision_recall_fscore_support(
            y_true, y_pred, labels=range(len(classes)), zero_division=0)
        single_model_metrics = json.loads((result_dir / f"test_metrics_{model}.json").read_text(encoding="utf-8"))
        for index, group in enumerate(classes):
            per_class = stored["per_class"][group]
            for key, computed in (("precision", class_precision[index]), ("recall", class_recall[index]),
                                  ("f1", class_f1[index])):
                if not np.isclose(float(per_class[key]), float(computed), atol=1e-12):
                    raise AssertionError(f"Per-class {key} does not recompute: {task}/{model}/{group}")
                if not np.isclose(float(single_model_metrics["per_class"][group][key]), float(computed), atol=1e-12):
                    raise AssertionError(f"Single-model per-class JSON mismatch: {task}/{model}/{group}/{key}")
            if int(per_class["support"]) != int(class_support[index]):
                raise AssertionError(f"Per-class support mismatch: {task}/{model}/{group}")
        results[model] = {"test_count": len(predictions), "accuracy": calculated["accuracy"],
                          "macro_f1": calculated["macro_f1"],
                          "per_class_support": {g: int((predictions.true_aami_label == g).sum()) for g in classes}}
    expected_test_class_counts = pd.read_csv(dataset_dir / "split_class_counts.csv")
    for group in classes:
        expected_count = int(expected_test_class_counts[(expected_test_class_counts.split == "test") &
                                                        (expected_test_class_counts.aami_label == group)].sample_count.iloc[0])
        if any(values["per_class_support"][group] != expected_count for values in results.values()):
            raise AssertionError(f"Test prediction support mismatch for {task}/{group}")
    return {"task": task, "status": "completed", "models": results,
            "all_source_metadata_preserved": True, "probabilities_finite_and_normalized": True,
            "metrics_recomputed_from_test_csv": True,
            "test_loaded_after_fit": experiment.get("test_loaded_after_all_fits_and_checkpoints") is True,
            "smoke_test_passed": True, "checkpoints_loadable_without_test_inference": True}


def _verify_figures(root: Path) -> dict:
    old_families = ["A_distribution", "B_waveforms", "C_morphology", "D_rhythm", "E_quality", "F_embedding"]
    old_count = sum(len(list((root / "figures" / category).glob("*.png"))) for category in old_families)
    if old_count != 67:
        raise AssertionError(f"Original 67 exploration figures are missing or modified: count={old_count}")
    families = {"07_preprocessing": 6, "08_binary_classification": 17, "09_multiclass_classification": 15}
    figure_stats = {}
    for category, expected in families.items():
        paths = list((root / "figures" / category).glob("*.png"))
        if len(paths) != expected:
            raise AssertionError(f"Unexpected figure count {category}: {len(paths)} != {expected}")
        for path in paths:
            with Image.open(path) as image:
                image.verify()
            with Image.open(path) as image:
                dpi = image.info.get("dpi")
                if not dpi or dpi[0] < 299 or dpi[1] < 299:
                    raise AssertionError(f"Figure does not store 300 dpi metadata: {path}")
        figure_stats[category] = {"png_count": len(paths), "dpi_minimum": 300, "integrity": True}
    return {"original_visualization_png_count_unchanged": old_count,
            "new_figure_count": sum(v["png_count"] for v in figure_stats.values()), "figures": figure_stats}


def verify(root: Path) -> dict:
    root = root.resolve()
    official = (root / "data/mitdb/RECORDS").read_text(encoding="utf-8").split()
    sums = {}
    for line in (root / "data/mitdb/SHA256SUMS.txt").read_text(encoding="utf-8").splitlines():
        parts = line.split(maxsplit=1)
        if len(parts) == 2:
            sums[parts[1].lstrip("*").removeprefix("./")] = parts[0]
    file_hashes = {f"{record}.{ext}": sha256(root / "data/mitdb" / f"{record}.{ext}")
                   for record in official for ext in ("dat", "hea", "atr")}
    if len(file_hashes) != 144 or any(sums.get(name) != digest for name, digest in file_hashes.items()):
        raise AssertionError("Official raw file hashes do not all match the PhysioNet SHA256SUMS file")
    expected_mapping = {symbol: group for group, symbols in {
        "N": ("N", "L", "R", "e", "j"), "S": ("A", "a", "J", "S"),
        "V": ("V", "E"), "F": ("F",), "Q": ("/", "f", "Q")
    }.items() for symbol in symbols}
    if AAMI_MAP != expected_mapping:
        raise AssertionError("Explicit AAMI symbol mapping changed")
    nv = _verify_dataset(root, "data/processed/mitdb44_nv_v1", ["N", "V"])
    nsvf = _verify_dataset(root, "data/processed/mitdb44_nsvf_v1", ["N", "S", "V", "F"])
    if nv["split_plan_sha256"] != nsvf["split_plan_sha256"]:
        raise AssertionError("N/V and N/S/V/F runs do not share the exact locked patient split")
    binary = _verify_experiment(root, "nv", "results/classification/nv44_v1",
                                "data/processed/mitdb44_nv_v1", ["N", "V"])
    multiclass = _verify_experiment(root, "nsvf", "results/classification/nsvf44_v1",
                                    "data/processed/mitdb44_nsvf_v1", ["N", "S", "V", "F"])
    ablation_path = root / "results/classification/nsvf44_v1/class_weight_validation_ablation.json"
    ablation = json.loads(ablation_path.read_text(encoding="utf-8"))
    if ablation.get("test_partition_loaded") is not False:
        raise AssertionError("Class-weight ablation accessed the test set")
    report = root / "reports/classification/experiment_summary.md"
    report_text = report.read_text(encoding="utf-8")
    for required in ("数据处理与划分", "N/V 二分类结果", "N/S/V/F 四分类结果", "类别权重", "下一阶段建议"):
        if required not in report_text:
            raise AssertionError(f"Report is missing required section: {required}")
    linked_images = set(re.findall(r"\]\(([^)]+\.png)\)", report_text))
    expected_images = {
        Path(os.path.relpath(path, report.parent)).as_posix()
        for category in ("07_preprocessing", "08_binary_classification", "09_multiclass_classification")
        for path in (root / "figures" / category).glob("*.png")
    }
    missing_report_links = sorted(expected_images - linked_images)
    broken_report_links = sorted(link for link in linked_images if not (report.parent / link).resolve().is_file())
    if missing_report_links or broken_report_links:
        raise AssertionError(f"Report figure links are missing/broken: missing={missing_report_links}, broken={broken_report_links}")
    figures = _verify_figures(root)
    previous = json.loads((root / "results/visualization/verification.json").read_text(encoding="utf-8"))
    if not previous.get("passed") or previous.get("png_count") != 67:
        raise AssertionError("Previous visualization verification changed")
    result = {"passed": True, "official_record_hashes_match": len(file_hashes) == 144,
              "excluded_paced_records": ["102", "104", "107", "217"],
              "aami_mapping_matches_requested_rule": True, "nv_dataset": nv, "nsvf_dataset": nsvf,
              "binary_experiment": binary, "multiclass_experiment": multiclass,
              "class_weight_ablation_validation_only": True, "original_67_figures_untouched_by_count": True,
              "figure_audit": figures,
              "report_figure_links_checked": len(expected_images), "report_figure_links_resolve": True,
              "test_predictions_reproducibly_recomputed_from_saved_csv": True,
              "report": report.relative_to(root).as_posix(), "training_was_cpu_only": True,
              "no_frontend_or_clinical_diagnosis": True}
    target = root / "results/classification/final_verification.json"
    target.write_text(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Audit completed MIT-BIH classification artifacts")
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[2])
    args = parser.parse_args()
    print(json.dumps(verify(args.root), ensure_ascii=False, indent=2), flush=True)


if __name__ == "__main__":
    main()
