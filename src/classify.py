"""Run a smoke test or one locked-split classification experiment.

Examples:
  python -m src.classify --task nv --smoke-test
  python -m src.classify --task nv
  python -m src.classify --task nsvf --smoke-test
  python -m src.classify --task nsvf
"""
from __future__ import annotations

import argparse
from datetime import datetime
import json
from pathlib import Path
import platform
import random
import time
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
import sklearn
import torch
from sklearn.model_selection import train_test_split

from .download import sha256
from .evaluation.metrics import make_prediction_frame, score_predictions, write_metrics
from .evaluation.plots import (plot_cnn_history, plot_confusion_matrices,
                               plot_model_comparisons, plot_probability_distributions,
                               plot_test_waveform_examples)
from .models.classifiers import HeartbeatCNN
from .training.trainer import (class_weights_from_training, fit_sklearn_baselines,
                               load_npz, predict_cnn, seed_everything, sklearn_predict,
                               train_cnn)

TASKS = {
    "nv": {"dataset": "data/processed/mitdb44_nv_v1", "class_names": ["N", "V"],
           "result": "results/classification/nv44_v1", "checkpoint": "checkpoints/nv44_v1"},
    "nsvf": {"dataset": "data/processed/mitdb44_nsvf_v1", "class_names": ["N", "S", "V", "F"],
             "result": "results/classification/nsvf44_v1", "checkpoint": "checkpoints/nsvf44_v1"},
}


def json_write(value: dict, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")


def validate_dataset(dataset_dir: Path, class_names: list[str]) -> dict:
    check_path = dataset_dir / "verification.json"
    if not check_path.exists():
        raise FileNotFoundError(f"Build dataset first: {check_path}")
    verification = json.loads(check_path.read_text(encoding="utf-8"))
    if not verification.get("passed") or verification.get("included_record_count") != 44:
        raise ValueError("The 44-record dataset integrity audit did not pass")
    config = json.loads((dataset_dir / "processing_config.json").read_text(encoding="utf-8"))
    if config["classes"] != class_names:
        raise ValueError(f"Dataset class order {config['classes']} does not match model order {class_names}")
    split = pd.read_csv(dataset_dir / "split_manifest.csv", keep_default_na=False, dtype={"record_id": str})
    if split.groupby("subject_id").split.nunique().max() != 1:
        raise AssertionError("Subject appears in multiple splits")
    pair = split[split.record_id.isin(["201", "202"])]
    if len(pair) != 2 or pair.split.nunique() != 1:
        raise AssertionError("Records 201 and 202 must remain in one split")
    return {"dataset_verification_sha256": sha256(check_path),
            "processing_config_sha256": sha256(dataset_dir / "processing_config.json"),
            "split_plan_sha256": sha256(dataset_dir / "split_plan.json"),
            "split_manifest_sha256": sha256(dataset_dir / "split_manifest.csv"),
            "dataset_samples": verification["split_counts"]}


def _smoke_arrays(train: dict, val: dict, class_count: int, seed: int,
                  train_limit: int = 3000, val_limit: int = 768) -> tuple[np.ndarray, ...]:
    train_y = train["y"]
    train_indices = np.arange(len(train_y))
    if len(train_y) > train_limit:
        selected, _ = train_test_split(train_indices, train_size=train_limit, stratify=train_y,
                                       random_state=seed, shuffle=True)
        train_indices = np.sort(selected)
    val_y = val["y"]
    val_indices = np.arange(len(val_y))
    if len(val_y) > val_limit:
        selected, _ = train_test_split(val_indices, train_size=val_limit, stratify=val_y,
                                       random_state=seed + 1, shuffle=True)
        val_indices = np.sort(selected)
    if set(np.unique(train_y[train_indices])) != set(range(class_count)):
        raise ValueError("Smoke-test training subset must retain every requested class")
    return (train["X"][train_indices, 0, :], train_y[train_indices],
            val["X"][val_indices, 0, :], val_y[val_indices], train_indices, val_indices)


def run_smoke(root: Path, task: str, config: dict, dataset_info: dict) -> dict:
    spec = TASKS[task]; names = spec["class_names"]; class_count = len(names)
    data_dir = root / spec["dataset"]
    train = load_npz(data_dir / "train.npz"); val = load_npz(data_dir / "val.npz")
    seed = int(config["seed"]); seed_everything(seed)
    xtr, ytr, xval, yval, train_idx, val_idx = _smoke_arrays(train, val, class_count, seed)
    weights = class_weights_from_training(ytr, class_count)
    checkpoint_dir = root / spec["checkpoint"] / "smoke_test"
    result_dir = root / spec["result"] / "smoke_test"
    result_dir.mkdir(parents=True, exist_ok=True)
    results = fit_sklearn_baselines(xtr, ytr, seed, checkpoint_dir, smoke=True, model_config=config["models"])
    from joblib import load
    smoke_metrics = {}
    for model_name in ("logistic_regression", "random_forest"):
        loaded = load(checkpoint_dir / f"{model_name}.joblib")
        estimator = loaded["estimator"]
        scaler = loaded["scaler"]
        model_info = {"estimator": estimator, "scaler": scaler}
        pred, prob = sklearn_predict(model_info, xval)
        if not np.isfinite(prob).all() or prob.shape != (len(yval), class_count):
            raise AssertionError(f"{model_name} smoke predictions invalid")
        smoke_metrics[model_name] = score_predictions(yval, pred, names)
        results[model_name]["smoke_validation_only"] = True
    cnn, history, cnn_result = train_cnn(xtr, ytr, xval, yval, class_count, weights,
                                         seed, checkpoint_dir / "cnn", epochs=1, patience=1,
                                         batch_size=128, smoke=True)
    pred, prob = predict_cnn(cnn, xval)
    if not np.isfinite(prob).all() or prob.shape != (len(yval), class_count):
        raise AssertionError("CNN smoke predictions invalid")
    smoke_metrics["cnn_1d"] = score_predictions(yval, pred, names)
    status = {"passed": True, "task": task, "smoke_test": True,
              "models_completed": ["logistic_regression", "random_forest", "cnn_1d"],
              "train_subset_count": int(len(ytr)), "validation_subset_count": int(len(yval)),
              "validation_only": True, "test_split_loaded": False,
              "class_weights_from_smoke_training_subset": weights.tolist(),
              "cnn": cnn_result, "validation_metrics_smoke_only_not_formal": smoke_metrics,
              "seed": seed, "device": str(next(cnn.parameters()).device),
              **dataset_info}
    json_write(status, result_dir / "verification.json")
    json_write(config, result_dir / "config.json")
    print(json.dumps(status, ensure_ascii=False, indent=2), flush=True)
    return status


def _load_formal_config(root: Path, task: str) -> dict:
    path = root / "configs" / ("binary_nv.json" if task == "nv" else "multiclass_nsvf.json")
    return json.loads(path.read_text(encoding="utf-8"))


def run_formal(root: Path, task: str, config: dict, dataset_info: dict) -> dict:
    spec = TASKS[task]; class_names = spec["class_names"]; class_count = len(class_names)
    dataset_dir = root / spec["dataset"]
    result_dir = root / spec["result"]
    checkpoint_dir = root / spec["checkpoint"] / "formal"
    result_dir.mkdir(parents=True, exist_ok=True); checkpoint_dir.mkdir(parents=True, exist_ok=True)
    smoke_path = root / spec["result"] / "smoke_test/verification.json"
    if not smoke_path.exists() or not json.loads(smoke_path.read_text(encoding="utf-8")).get("passed"):
        raise RuntimeError(f"Smoke Test must pass first: {smoke_path}")
    if task == "nsvf":
        binary_marker = root / TASKS["nv"]["result"] / "experiment.json"
        if not binary_marker.exists() or json.loads(binary_marker.read_text(encoding="utf-8")).get("status") != "completed":
            raise RuntimeError("Four-class training is gated until the N/V experiment completed and saved successfully")
    prior_run = result_dir / "experiment.json"
    if prior_run.exists() and json.loads(prior_run.read_text(encoding="utf-8")).get("status") == "completed":
        raise RuntimeError("This fixed test evaluation is already complete; use the saved metrics/predictions instead of evaluating again")

    seed = int(config["seed"]); seed_everything(seed)
    try:
        torch.set_num_threads(min(8, max(1, os_cpu_count())))
        torch.set_num_interop_threads(min(4, max(1, os_cpu_count())))
    except RuntimeError:
        pass
    train = load_npz(dataset_dir / "train.npz")
    val = load_npz(dataset_dir / "val.npz")
    x_train = train["X"][:, 0, :]; y_train = train["y"]
    x_val = val["X"][:, 0, :]; y_val = val["y"]
    counts = np.bincount(y_train, minlength=class_count)
    if (counts == 0).any():
        raise ValueError(f"Training data do not include every requested class: {counts.tolist()}")
    weights = class_weights_from_training(y_train, class_count)
    json_write({"source": "training labels only", "class_names": class_names,
                "counts": counts.tolist(), "inverse_frequency_balanced_weights": weights.tolist()},
               result_dir / "training_class_weights.json")
    run_config = {**config, "task": task, "class_names": class_names, "seed": seed,
                  "dataset_path": spec["dataset"], "checkpoint_dir": str(checkpoint_dir.relative_to(root)),
                  "started_at_Asia_Shanghai": datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(),
                  "dataset_artifact_hashes": dataset_info, "device": "cuda" if torch.cuda.is_available() else "cpu",
                  "class_weights_source": "training labels only", "test_loaded_before_fit_complete": False,
                  "test_usage": "Only after all model fits and checkpoints are saved; one final evaluation"}
    json_write(run_config, result_dir / "config.json")
    json_write({"status": "training", "task": task, "training_counts": counts.tolist()}, prior_run)

    started = time.perf_counter(); fit_logs = []
    fitted = fit_sklearn_baselines(x_train, y_train, seed, checkpoint_dir, smoke=False, model_config=config["models"])
    for model_name, values in fitted.items():
        fit_logs.append({"model": model_name, "status": values["status"], "fit_seconds": values["fit_seconds"],
                         "training_sample_count": len(y_train), "training_class_counts": counts.tolist(),
                         "selection": "fixed configuration; no test-based tuning"})
    cnn, history, cnn_info = train_cnn(x_train, y_train, x_val, y_val, class_count, weights,
                                       seed, checkpoint_dir / "cnn",
                                       epochs=int(config["cnn"]["epochs"]), patience=int(config["cnn"]["patience"]),
                                       batch_size=int(config["cnn"]["batch_size"]), smoke=False)
    fit_logs.append({"model": "cnn_1d", **cnn_info, "training_sample_count": len(y_train),
                     "training_class_counts": counts.tolist()})
    torch.save({"state_dict": cnn.state_dict(), "class_names": class_names, "seed": seed,
                "best_epoch": cnn_info["best_epoch"], "dataset_config_hash": dataset_info["processing_config_sha256"]},
               checkpoint_dir / "cnn" / "cnn_final_best.pt")
    (result_dir / "training_logs.json").write_text(json.dumps(fit_logs, ensure_ascii=False, indent=2), encoding="utf-8")
    json_write({"status": "trained_checkpoints_saved", "task": task,
                "fit_wall_seconds": time.perf_counter()-started,
                "all_model_checkpoints_saved_before_test": True}, prior_run)

    # The locked test partition is intentionally loaded only after every model has
    # finished fitting and its checkpoint has been written.
    test = load_npz(dataset_dir / "test.npz")
    x_test = test["X"][:, 0, :]; y_test = test["y"]
    model_outputs = {}
    for model_name, info in fitted.items():
        model_outputs[model_name] = sklearn_predict(info, x_test)
        val_pred, val_prob = sklearn_predict(info, x_val)
        val_frame = make_prediction_frame(val, y_val, val_pred, val_prob, class_names, model_name, "val")
        val_frame.to_csv(result_dir / f"val_predictions_{model_name}.csv", index=False, encoding="utf-8-sig")
        write_metrics(result_dir / f"val_metrics_{model_name}.json", score_predictions(y_val, val_pred, class_names))
    cnn_val_pred, cnn_val_prob = predict_cnn(cnn, x_val)
    val_frame = make_prediction_frame(val, y_val, cnn_val_pred, cnn_val_prob, class_names, "cnn_1d", "val")
    val_frame.to_csv(result_dir / "val_predictions_cnn_1d.csv", index=False, encoding="utf-8-sig")
    write_metrics(result_dir / "val_metrics_cnn_1d.json", score_predictions(y_val, cnn_val_pred, class_names))
    model_outputs["cnn_1d"] = predict_cnn(cnn, x_test)

    test_frames, test_metrics = {}, {}
    for model_name, (pred, prob) in model_outputs.items():
        frame = make_prediction_frame(test, y_test, pred, prob, class_names, model_name, "test")
        test_frames[model_name] = frame
        test_metrics[model_name] = score_predictions(y_test, pred, class_names)
        frame.to_csv(result_dir / f"test_predictions_{model_name}.csv", index=False, encoding="utf-8-sig")
        write_metrics(result_dir / f"test_metrics_{model_name}.json", test_metrics[model_name])
    pd.concat(test_frames.values(), ignore_index=True).to_csv(result_dir / "test_predictions_all_models.csv",
                                                              index=False, encoding="utf-8-sig")
    pd.concat([pd.read_csv(result_dir / f"val_predictions_{name}.csv", keep_default_na=False)
               for name in test_frames], ignore_index=True).to_csv(result_dir / "val_predictions_all_models.csv",
                                                                   index=False, encoding="utf-8-sig")

    # Independently recompute metrics from the saved CSV predictions before
    # producing summary figures or marking the experiment complete.
    metric_recheck = {}
    for model_name in test_frames:
        saved = pd.read_csv(result_dir / f"test_predictions_{model_name}.csv", keep_default_na=False)
        fresh = score_predictions(pd.Categorical(saved.true_aami_label, categories=class_names).codes,
                                  pd.Categorical(saved.predicted_aami_label, categories=class_names).codes,
                                  class_names)
        if not np.isclose(fresh["accuracy"], test_metrics[model_name]["accuracy"]):
            raise AssertionError(f"Saved prediction metrics cannot be reproduced for {model_name}")
        metric_recheck[model_name] = {"accuracy": fresh["accuracy"], "macro_f1": fresh["macro_f1"],
                                      "per_class": fresh["per_class"]}
    write_metrics(result_dir / "test_metrics_all_models.json", test_metrics)
    pd.DataFrame([{"model": model, "accuracy": values["accuracy"], "macro_precision": values["macro_precision"],
                   "macro_recall": values["macro_recall"], "macro_f1": values["macro_f1"],
                   **{f"{group}_{metric}": values["per_class"][group][metric]
                      for group in class_names for metric in ("precision", "recall", "f1", "support")}}
                  for model, values in test_metrics.items()]).to_csv(result_dir / "test_metrics_comparison.csv",
                                                                     index=False, encoding="utf-8-sig")

    figures_dir = root / "figures/08_binary_classification" if task == "nv" else root / "figures/09_multiclass_classification"
    figure_paths = []
    test_record_ids = sorted(test["record_id"].astype(str).unique().tolist())
    train_record_ids = sorted(train["record_id"].astype(str).unique().tolist())
    val_record_ids = sorted(val["record_id"].astype(str).unique().tolist())
    figure_paths += plot_model_comparisons(test_metrics, class_names, figures_dir, test_record_ids)
    figure_paths += plot_confusion_matrices(test_frames, class_names, figures_dir)
    figure_paths += plot_cnn_history(history, figures_dir, train_record_ids, val_record_ids)
    figure_paths += plot_probability_distributions(test_frames, class_names, figures_dir)
    figure_paths += plot_test_waveform_examples(test_frames, test, class_names, figures_dir, seed)
    figure_catalog = []
    for path in figure_paths:
        is_history = Path(path).stem.startswith("cnn_train_validation") or Path(path).stem.startswith("cnn_validation")
        figure_catalog.append({"file": Path(path).relative_to(root).as_posix(),
                               "split": "train+val" if is_history else "test",
                               "record_ids": train_record_ids + val_record_ids if is_history else test_record_ids,
                               "purpose": Path(path).stem.replace("_", " "), "dpi": 300})
    pd.DataFrame(figure_catalog).to_csv(result_dir / "figure_catalog.csv", index=False, encoding="utf-8-sig")
    summary = {"status": "completed", "task": task, "class_names": class_names,
               "train_samples": int(len(y_train)), "validation_samples": int(len(y_val)),
               "test_samples": int(len(y_test)), "test_metrics": test_metrics,
               "metrics_recomputed_from_saved_test_predictions": metric_recheck,
               "metrics_recomputed_match": True, "fit_logs": fit_logs,
               "checkpoint_files": [str(p.relative_to(root)) for p in checkpoint_dir.rglob("*") if p.is_file()],
               "prediction_files_saved": True, "confusion_matrix_figures_saved": True,
               "figure_count": len(figure_catalog), "figures": figure_catalog,
               "subject_split_sha256": dataset_info["split_plan_sha256"],
               "test_used_for_training_or_selection": False,
               "test_loaded_after_all_fits_and_checkpoints": True,
               "completed_at_Asia_Shanghai": datetime.now(ZoneInfo("Asia/Shanghai")).isoformat()}
    json_write(summary, prior_run)
    from .evaluation.report import generate_experiment_summary
    report_path = generate_experiment_summary(root)
    summary["report"] = str(report_path.relative_to(root))
    json_write(summary, prior_run)
    print(json.dumps(summary, ensure_ascii=False, indent=2), flush=True)
    return summary


def os_cpu_count() -> int:
    import os
    return os.cpu_count() or 1


def main() -> None:
    parser = argparse.ArgumentParser(description="Patient-independent N/V or N/S/V/F ECG heartbeat classification")
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--task", choices=TASKS, default="nv")
    parser.add_argument("--smoke-test", action="store_true", help="Run small data/model pipeline checks; does not load test set")
    args = parser.parse_args()
    root = args.root.resolve(); task = args.task
    config = _load_formal_config(root, task)
    spec = TASKS[task]; dataset_dir = root / spec["dataset"]
    dataset_info = validate_dataset(dataset_dir, spec["class_names"])
    if args.smoke_test:
        run_smoke(root, task, config, dataset_info)
    else:
        run_formal(root, task, config, dataset_info)


if __name__ == "__main__":
    main()
