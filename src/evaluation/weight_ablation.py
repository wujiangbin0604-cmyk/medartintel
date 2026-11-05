"""Validation-only class-weight ablation; never loads the test partition."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import textwrap

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from joblib import dump
from sklearn.preprocessing import StandardScaler

from ..classify import TASKS, validate_dataset
from ..models.classifiers import make_logistic_regression, make_random_forest
from ..training.trainer import load_npz, predict_cnn, seed_everything, sklearn_predict, train_cnn
from .metrics import score_predictions
from ..visuals.common import COLORS


def run(root: Path, task: str = "nsvf") -> Path:
    if task not in TASKS:
        raise ValueError(f"Unknown task: {task}")
    spec = TASKS[task]; class_names = spec["class_names"]
    result_dir = root / spec["result"]
    marker_path = result_dir / "experiment.json"
    marker = json.loads(marker_path.read_text(encoding="utf-8"))
    if marker.get("status") != "completed":
        raise RuntimeError("Formal experiment must be complete before the class-weight analysis")
    dataset_dir = root / spec["dataset"]
    data_info = validate_dataset(dataset_dir, class_names)
    training = load_npz(dataset_dir / "train.npz")
    validation = load_npz(dataset_dir / "val.npz")
    x_train, y_train = training["X"][:, 0, :], training["y"]
    x_val, y_val = validation["X"][:, 0, :], validation["y"]
    config_path = root / "configs" / ("binary_nv.json" if task == "nv" else "multiclass_nsvf.json")
    config = json.loads(config_path.read_text(encoding="utf-8"))
    seed_everything(int(config["seed"]))
    checkpoint_dir = root / spec["checkpoint"] / "weight_ablation"
    checkpoint_dir.mkdir(parents=True, exist_ok=True)
    ablated = {}

    lr_config = dict(config["models"]["logistic_regression"]); lr_config["class_weight"] = None
    scaler = StandardScaler().fit(x_train)
    lr = make_logistic_regression(int(config["seed"]), config=lr_config)
    lr.fit(scaler.transform(x_train), y_train)
    lr_info = {"estimator": lr, "scaler": scaler}
    dump({"estimator": lr, "scaler": scaler}, checkpoint_dir / "logistic_regression_unweighted.joblib", compress=3)
    pred, probability = sklearn_predict(lr_info, x_val)
    ablated["logistic_regression"] = score_predictions(y_val, pred, class_names)

    rf_config = dict(config["models"]["random_forest"]); rf_config["class_weight"] = None
    rf = make_random_forest(int(config["seed"]), config=rf_config)
    rf.fit(x_train, y_train)
    rf_info = {"estimator": rf, "scaler": None}
    dump({"estimator": rf, "scaler": None}, checkpoint_dir / "random_forest_unweighted.joblib", compress=3)
    pred, probability = sklearn_predict(rf_info, x_val)
    ablated["random_forest"] = score_predictions(y_val, pred, class_names)

    cnn, _, cnn_summary = train_cnn(x_train, y_train, x_val, y_val, len(class_names),
                                    np.ones(len(class_names), dtype=np.float32), int(config["seed"]),
                                    checkpoint_dir / "cnn_unweighted",
                                    epochs=int(config["cnn"]["epochs"]), patience=int(config["cnn"]["patience"]),
                                    batch_size=int(config["cnn"]["batch_size"]))
    pred, probability = predict_cnn(cnn, x_val)
    ablated["cnn_1d"] = score_predictions(y_val, pred, class_names)
    cnn_summary["ablation"] = "unweighted CrossEntropyLoss (all-one class weights)"

    weighted = {}
    for model_name in ("logistic_regression", "random_forest", "cnn_1d"):
        path = result_dir / f"val_metrics_{model_name}.json"
        weighted[model_name] = json.loads(path.read_text(encoding="utf-8"))
    output = {"task": task, "split": "validation only", "test_partition_loaded": False,
              "model_selection_or_test_metrics_affected": False,
              "class_weights_from_train_only": True, "weighted_baseline": weighted,
              "unweighted_ablation": ablated, "cnn_unweighted_training": cnn_summary,
              "dataset_hashes": data_info}
    out_path = result_dir / "class_weight_validation_ablation.json"
    out_path.write_text(json.dumps(output, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    rows = []
    for model_name in weighted:
        for group in class_names:
            for condition, values in (("weighted", weighted[model_name]), ("unweighted", ablated[model_name])):
                score = values["per_class"][group]
                rows.append({"model": model_name, "condition": condition, "class": group,
                             "precision": score["precision"], "recall": score["recall"],
                             "f1": score["f1"], "support": score["support"],
                             "accuracy": values["accuracy"], "macro_f1": values["macro_f1"]})
    frame = pd.DataFrame(rows)
    frame.to_csv(result_dir / "class_weight_validation_ablation.csv", index=False, encoding="utf-8-sig")
    image = render_saved_ablation(root, task)
    print(json.dumps({"saved": str(out_path), "figure": str(image), "test_partition_loaded": False,
                      "ablation_models": list(ablated)}, ensure_ascii=False, indent=2), flush=True)
    return out_path


def render_saved_ablation(root: Path, task: str) -> Path:
    spec = TASKS[task]; class_names = spec["class_names"]
    result_dir = root / spec["result"]
    frame = pd.read_csv(result_dir / "class_weight_validation_ablation.csv", keep_default_na=False)
    manifest = pd.read_csv(root / spec["dataset"] / "split_manifest.csv", keep_default_na=False)
    val_records = sorted(manifest.loc[manifest.split == "val", "record_id"].astype(str).unique())
    figure_dir = root / ("figures/09_multiclass_classification" if task == "nsvf" else "figures/08_binary_classification")
    fig, axes = plt.subplots(1, 2, figsize=(14, 5), sharey=True)
    models = list(frame.model.drop_duplicates()); x = np.arange(len(models)); width = .8/(2*len(class_names))
    for ax, metric in ((axes[0], "recall"), (axes[1], "f1")):
        for class_index, group in enumerate(class_names):
            for cond_index, condition in enumerate(("weighted", "unweighted")):
                offsets = (class_index*2+cond_index-(len(class_names)-.5))*width
                vals = [frame[(frame.model == model)&(frame.condition == condition)&(frame["class"] == group)][metric].iloc[0] for model in models]
                ax.bar(x+offsets, vals, width, color=COLORS.get(group, f"C{class_index}"),
                       alpha=1 if condition == "weighted" else .45,
                       label=f"{group} {condition}" if ax is axes[0] else None)
        ax.set_xticks(x, models, rotation=12); ax.set_ylim(0, 1.05)
        ax.set_ylabel(metric.title()); ax.set_title(f"Validation {metric.title()}"); ax.grid(axis="y", alpha=.2)
    axes[0].legend(ncols=2, fontsize=8, title="Class and weights")
    fig.suptitle("Class-weight ablation | validation only | no test data loaded")
    fig.text(.01, .005, textwrap.fill("MIT-BIH 1.0.0; validation record IDs: " + ", ".join(val_records) +
                                      "; weighted/unweighted comparisons use the same training seed and locked split.", 160),
             fontsize=7, color="#4c5661", va="bottom")
    figure_dir.mkdir(parents=True, exist_ok=True)
    image = figure_dir / "class_weight_validation_ablation.png"
    fig.tight_layout(rect=(0, .045, 1, .92)); fig.savefig(image, dpi=300, bbox_inches="tight"); plt.close(fig)
    return image


def main() -> None:
    parser = argparse.ArgumentParser(description="Compare weighted and unweighted models on validation only")
    parser.add_argument("--task", choices=TASKS, default="nsvf")
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument("--render-saved", action="store_true", help="Only render the saved validation ablation; do not fit or predict")
    options = parser.parse_args()
    if options.render_saved:
        print(render_saved_ablation(options.root.resolve(), options.task), flush=True)
    else:
        run(options.root.resolve(), options.task)


if __name__ == "__main__":
    main()
