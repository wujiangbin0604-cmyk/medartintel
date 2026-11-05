"""Metrics and traceable split predictions from saved model probabilities."""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import (accuracy_score, classification_report, confusion_matrix,
                             f1_score, precision_score, recall_score)


def score_predictions(y_true: np.ndarray, y_pred: np.ndarray, class_names: list[str]) -> dict:
    labels = list(range(len(class_names)))
    report = classification_report(y_true, y_pred, labels=labels, target_names=class_names,
                                   output_dict=True, zero_division=0)
    by_class = {name: {"precision": float(report[name]["precision"]),
                       "recall": float(report[name]["recall"]),
                       "f1": float(report[name]["f1-score"]),
                       "support": int(report[name]["support"])} for name in class_names}
    return {"accuracy": float(accuracy_score(y_true, y_pred)),
            "macro_precision": float(precision_score(y_true, y_pred, labels=labels, average="macro", zero_division=0)),
            "macro_recall": float(recall_score(y_true, y_pred, labels=labels, average="macro", zero_division=0)),
            "macro_f1": float(f1_score(y_true, y_pred, labels=labels, average="macro", zero_division=0)),
            "per_class": by_class,
            "confusion_matrix": confusion_matrix(y_true, y_pred, labels=labels).tolist(),
            "test_or_validation_sample_count": int(len(y_true)),
            "classification_report": report}


def make_prediction_frame(data: dict, y_true: np.ndarray, y_pred: np.ndarray, probability: np.ndarray,
                          class_names: list[str], model_name: str, split: str) -> pd.DataFrame:
    frame = pd.DataFrame({"model": model_name, "split": split, "sample_id": data["sample_id"].astype(str),
                          "record_id": data["record_id"].astype(str), "subject_id": data["subject_id"].astype(str),
                          "annotation_sample": data["annotation_sample"].astype(np.int64),
                          "time_s": data["annotation_sample"].astype(np.float64) / float(data["fs_hz"]),
                          "lead_name": data["lead"].astype(str),
                          "original_label": data["original_label"].astype(str),
                          "true_aami_label": np.asarray(class_names)[y_true],
                          "predicted_aami_label": np.asarray(class_names)[y_pred],
                          "correct": np.asarray(y_true) == np.asarray(y_pred)})
    for class_id, name in enumerate(class_names):
        frame[f"probability_{name}"] = probability[:, class_id]
    return frame


def write_metrics(path: Path, values: dict) -> None:
    path.write_text(json.dumps(values, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
