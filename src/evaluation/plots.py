"""Plots generated exclusively from locked predictions and source windows."""
from __future__ import annotations

from pathlib import Path
import textwrap

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.metrics import confusion_matrix

from ..visuals.common import COLORS


def _save(fig, directory: Path, name: str, scope_note: str = "") -> str:
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{name}.png"
    if scope_note:
        fig.text(.01, .005, textwrap.fill(scope_note, width=170), fontsize=7, color="#4c5661", va="bottom")
    fig.tight_layout(rect=(0, .045 if scope_note else 0, 1, .94))
    fig.savefig(path, dpi=300, bbox_inches="tight")
    plt.close(fig)
    return path.as_posix()


def plot_model_comparisons(test_metrics: dict, class_names: list[str], directory: Path,
                           record_ids: list[str]) -> list[str]:
    model_names = list(test_metrics)
    paths = []
    colors = ["#427c8a", "#c18645", "#866aa3"]
    fig, ax = plt.subplots(figsize=(8, 4.8))
    bars = ax.bar(model_names, [test_metrics[name]["accuracy"] for name in model_names], color=colors)
    ax.bar_label(bars, fmt="%.3f", padding=3)
    ax.set_ylim(0, 1.05); ax.set_ylabel("Accuracy"); ax.set_xlabel("Model")
    ax.set_title("Test-set accuracy | subject-independent 44-record protocol")
    ax.tick_params(axis="x", rotation=12); ax.grid(axis="y", alpha=.2)
    scope = "MIT-BIH 1.0.0; locked test split; source records: " + ", ".join(record_ids) + "; no 102/104/107/217."
    paths.append(_save(fig, directory, "test_accuracy_comparison", scope))

    metric_names = ("precision", "recall", "f1")
    fig, axes = plt.subplots(1, len(metric_names), figsize=(15, 4.8), sharey=True)
    x = np.arange(len(model_names)); width = .78 / len(class_names)
    for ax, metric in zip(axes, metric_names):
        for class_id, group in enumerate(class_names):
            values = [test_metrics[name]["per_class"][group][metric] for name in model_names]
            ax.bar(x + (class_id - (len(class_names)-1)/2)*width, values, width,
                   label=group, color=COLORS.get(group, f"C{class_id}"))
        ax.set_xticks(x, model_names, rotation=12); ax.set_ylim(0, 1.05)
        ax.set_ylabel(metric.title()); ax.set_title(metric.title()); ax.grid(axis="y", alpha=.2)
    axes[-1].legend(title="True class", bbox_to_anchor=(1.02, 1), loc="upper left")
    fig.suptitle("Per-class precision, recall and F1 | locked test set")
    paths.append(_save(fig, directory, "test_precision_recall_f1_comparison", scope))

    fig, ax = plt.subplots(figsize=(8, 4.8))
    values = [test_metrics[name]["macro_f1"] for name in model_names]
    bars = ax.bar(model_names, values, color=colors); ax.bar_label(bars, fmt="%.3f", padding=3)
    ax.set_ylim(0, 1.05); ax.set_ylabel("Macro-F1"); ax.set_xlabel("Model")
    ax.set_title("Macro-F1 gives each class equal weight | locked test set")
    ax.tick_params(axis="x", rotation=12); ax.grid(axis="y", alpha=.2)
    paths.append(_save(fig, directory, "test_macro_f1_comparison", scope))
    return paths


def plot_confusion_matrices(test_frames: dict[str, pd.DataFrame], class_names: list[str], directory: Path) -> list[str]:
    paths = []
    labels = list(range(len(class_names)))
    for model, frame in test_frames.items():
        true = pd.Categorical(frame.true_aami_label, categories=class_names).codes
        pred = pd.Categorical(frame.predicted_aami_label, categories=class_names).codes
        matrix = confusion_matrix(true, pred, labels=labels)
        fig, ax = plt.subplots(figsize=(6, 5.2))
        image = ax.imshow(matrix, cmap="Blues")
        fig.colorbar(image, ax=ax, label="Beat count")
        for i in range(matrix.shape[0]):
            for j in range(matrix.shape[1]):
                ax.text(j, i, str(int(matrix[i, j])), ha="center", va="center",
                        color="white" if matrix[i, j] > matrix.max() * .55 else "black")
        ax.set_xticks(np.arange(len(class_names)), class_names)
        ax.set_yticks(np.arange(len(class_names)), class_names)
        ax.set_xlim(-.5, len(class_names)-.5)
        ax.set_ylim(len(class_names)-.5, -.5)
        ax.set_xlabel("Predicted AAMI class"); ax.set_ylabel("Reference AAMI class")
        ax.set_title(f"{model} | test confusion matrix | n={len(frame):,}")
        records = sorted(frame.record_id.astype(str).unique())
        paths.append(_save(fig, directory, f"test_confusion_matrix_{model}",
                           "MIT-BIH 1.0.0; test split records: " + ", ".join(records)))
    return paths


def plot_cnn_history(history: pd.DataFrame, directory: Path, train_records: list[str], val_records: list[str]) -> list[str]:
    if history.empty:
        return []
    paths = []
    fig, ax = plt.subplots(figsize=(7.5, 4.8))
    ax.plot(history.epoch, history.train_loss, marker="o", label="Train loss")
    ax.plot(history.epoch, history.val_loss, marker="o", label="Validation loss")
    ax.set_xlabel("Epoch"); ax.set_ylabel("Weighted cross-entropy")
    ax.set_title("1D-CNN training and validation loss"); ax.legend(); ax.grid(alpha=.2)
    scope = "MIT-BIH 1.0.0; training records: " + ", ".join(train_records) + "; validation records: " + ", ".join(val_records)
    paths.append(_save(fig, directory, "cnn_train_validation_loss", scope))
    fig, ax = plt.subplots(figsize=(7.5, 4.8))
    ax.plot(history.epoch, history.val_macro_f1, marker="o", color="#866aa3", label="Validation macro-F1")
    ax.set_xlabel("Epoch"); ax.set_ylabel("Macro-F1"); ax.set_ylim(0, 1.02)
    ax.set_title("1D-CNN validation macro-F1 | early-stopping metric")
    ax.legend(); ax.grid(alpha=.2)
    paths.append(_save(fig, directory, "cnn_validation_macro_f1", scope))
    return paths


def plot_probability_distributions(test_frames: dict[str, pd.DataFrame], class_names: list[str], directory: Path) -> list[str]:
    paths = []
    for model, frame in test_frames.items():
        fig, axes = plt.subplots(1, len(class_names), figsize=(5*len(class_names), 4.5), squeeze=False)
        for class_id, group in enumerate(class_names):
            ax = axes[0, class_id]
            probability_col = f"probability_{group}"
            for true_group, color in zip(class_names, [COLORS.get(g, f"C{i}") for i, g in enumerate(class_names)]):
                values = frame.loc[frame.true_aami_label == true_group, probability_col].to_numpy()
                if len(values):
                    ax.hist(values, bins=np.linspace(0, 1, 21), histtype="step", density=False,
                            linewidth=1.6, color=color, label=f"True {true_group} (n={len(values)})")
            ax.set_xlabel(f"Predicted P({group})"); ax.set_ylabel("Test beats")
            ax.set_title(f"{model}: {group} probability"); ax.legend(fontsize=7); ax.grid(alpha=.15)
        fig.suptitle(f"Predicted probability distributions | {model} | locked test set")
        records = sorted(frame.record_id.astype(str).unique())
        paths.append(_save(fig, directory, f"test_probability_distribution_{model}",
                           "MIT-BIH 1.0.0; locked test records: " + ", ".join(records)))
    return paths


def _trace_group(ax, subset: pd.DataFrame, test_data: dict, seed: int, max_beats: int = 3) -> None:
    if subset.empty:
        ax.text(.5, .5, "No examples in this split", transform=ax.transAxes, ha="center", va="center")
        return
    selected = subset.sample(n=min(max_beats, len(subset)), random_state=seed).sort_values("sample_id")
    time_axis = test_data["relative_time_s"]
    indexed = pd.DataFrame({"sample_id": test_data["sample_id"].astype(str),
                            "row": np.arange(len(test_data["sample_id"]))}).set_index("sample_id").row
    for row in selected.itertuples():
        idx = int(indexed.loc[row.sample_id])
        trace = test_data["X_filtered"][idx, 0]
        ax.plot(time_axis, trace, linewidth=.85, alpha=.78,
                label=f"{row.record_id} {row.lead_name} {row.time_s:.1f}s")
    ax.axvline(0, color="#333333", linestyle="--", linewidth=.8, label="Expert annotation")
    ax.set_xlabel("Time relative to annotation (s)"); ax.set_ylabel("Filtered ECG (mV)")
    ax.grid(alpha=.16); ax.legend(fontsize=6, ncol=1)


def plot_test_waveform_examples(test_frames: dict[str, pd.DataFrame], test_data: dict,
                                class_names: list[str], directory: Path, seed: int) -> list[str]:
    paths = []
    for model, frame in test_frames.items():
        fig, axes = plt.subplots(len(class_names), 2, figsize=(12, max(5, 2.8*len(class_names))), squeeze=False)
        for row, group in enumerate(class_names):
            correct = frame[(frame.true_aami_label == group) & frame.correct]
            errors = frame[(frame.true_aami_label == group) & ~frame.correct]
            _trace_group(axes[row, 0], correct, test_data, seed+row)
            axes[row, 0].set_title(f"True {group} correctly classified (up to 3)")
            _trace_group(axes[row, 1], errors, test_data, seed+100+row)
            axes[row, 1].set_title(f"True {group} misclassified (up to 3)")
        fig.suptitle(f"{model} | representative correct/error ECG windows | locked test set")
        paths.append(_save(fig, directory, f"test_ecg_examples_{model}",
                           "MIT-BIH 1.0.0; ECG traces identify record, lead, and annotation time in the legend."))

    if set(class_names) == {"N", "V"}:
        for model, frame in test_frames.items():
            fig, axes = plt.subplots(1, 2, figsize=(12, 4.8))
            for ax, truth, pred in ((axes[0], "N", "V"), (axes[1], "V", "N")):
                subset = frame[(frame.true_aami_label == truth) & (frame.predicted_aami_label == pred)]
                _trace_group(ax, subset, test_data, seed+ord(truth), max_beats=8)
                ax.set_title(f"{truth} → {pred} errors (up to 8 of {len(subset)})")
            fig.suptitle(f"{model} | N/V directional test errors | each trace retains record/lead/time")
            paths.append(_save(fig, directory, f"test_directional_errors_{model}",
                               "MIT-BIH 1.0.0; each trace legend gives record, lead, and annotation time."))
    return paths
