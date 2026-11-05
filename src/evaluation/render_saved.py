"""Re-render experiment figures from saved outputs without refitting or predicting."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

from ..classify import TASKS
from ..training.trainer import load_npz
from .metrics import write_metrics
from .plots import (plot_cnn_history, plot_confusion_matrices,
                    plot_model_comparisons, plot_probability_distributions,
                    plot_test_waveform_examples)


def render(root: Path, task: str) -> dict:
    spec = TASKS[task]
    result_dir = root / spec["result"]
    marker_path = result_dir / "experiment.json"
    marker = json.loads(marker_path.read_text(encoding="utf-8"))
    if marker.get("status") != "completed":
        raise RuntimeError("Only completed, saved experiments can be re-rendered")
    class_names = marker["class_names"]
    metrics = json.loads((result_dir / "test_metrics_all_models.json").read_text(encoding="utf-8"))
    test_frames = {model: pd.read_csv(result_dir / f"test_predictions_{model}.csv", keep_default_na=False)
                   for model in ("logistic_regression", "random_forest", "cnn_1d")}
    dataset_dir = root / spec["dataset"]
    train = load_npz(dataset_dir / "train.npz")
    val = load_npz(dataset_dir / "val.npz")
    test = load_npz(dataset_dir / "test.npz")
    test_record_ids = sorted(set(test["record_id"].astype(str).tolist()))
    train_record_ids = sorted(set(train["record_id"].astype(str).tolist()))
    val_record_ids = sorted(set(val["record_id"].astype(str).tolist()))
    image_dir = root / ("figures/08_binary_classification" if task == "nv" else "figures/09_multiclass_classification")
    history_path = root / spec["checkpoint"] / "formal/cnn/cnn_training_history.csv"
    history = pd.read_csv(history_path)
    paths = []
    paths += plot_model_comparisons(metrics, class_names, image_dir, test_record_ids)
    paths += plot_confusion_matrices(test_frames, class_names, image_dir)
    paths += plot_cnn_history(history, image_dir, train_record_ids, val_record_ids)
    paths += plot_probability_distributions(test_frames, class_names, image_dir)
    paths += plot_test_waveform_examples(test_frames, test, class_names, image_dir, int(marker["fit_logs"][0].get("seed", 20261027)) if marker.get("fit_logs") else 20261027)
    entries = []
    for path in paths:
        is_history = Path(path).stem.startswith("cnn_train_validation") or Path(path).stem.startswith("cnn_validation")
        entries.append({"file": Path(path).relative_to(root).as_posix(),
                        "split": "train+val" if is_history else "test",
                        "record_ids": train_record_ids + val_record_ids if is_history else test_record_ids,
                        "purpose": Path(path).stem.replace("_", " "), "dpi": 300})
    pd.DataFrame(entries).to_csv(result_dir / "figure_catalog.csv", index=False, encoding="utf-8-sig")
    marker["figures"] = entries; marker["figure_count"] = len(entries)
    marker_path.write_text(json.dumps(marker, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"task": task, "figure_count": len(entries), "record_ids": test_record_ids,
            "predictions_refit": False, "test_metrics_recomputed": False}


def main() -> None:
    parser = argparse.ArgumentParser(description="Re-render saved classification artifacts; no model fitting or prediction")
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument("--task", choices=TASKS, required=True)
    args = parser.parse_args()
    print(json.dumps(render(args.root.resolve(), args.task), indent=2), flush=True)


if __name__ == "__main__":
    main()
