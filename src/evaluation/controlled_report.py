"""Summarize completed locked experiments; never trains or selects on test.

Only run after controlled_imbalance --stage final has completed. All aggregates
use the three predeclared seeds (sample SD, ddof=1), not repeated patient counts.
"""
from __future__ import annotations

import argparse
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
from zoneinfo import ZoneInfo

os.environ.setdefault("MPLCONFIGDIR", str(Path(__file__).resolve().parents[2] / ".mplconfig"))
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from .stability_audit import independent_score


ROOT = Path(__file__).resolve().parents[2]
DIRECTORY = ROOT / "results/controlled_imbalance_20261116"
FIGURES = ROOT / "figures/final_optimization"
CLASSES = ["N", "S", "V", "F"]
LABELS = {"ce_inverse": "CE inverse", "ce_sqrt": "CE sqrt",
          "focal_sqrt": "Focal sqrt", "focal_sqrt_rr": "Focal sqrt + RR"}
COLORS = ["#55738c", "#d49435", "#4b9690", "#8664a5"]
METRICS = ["accuracy", "macro_f1", "balanced_accuracy"] + [
    f"{label}_{metric}" for label in CLASSES for metric in ("precision", "recall", "f1")]


def sha(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def require(condition: bool, explanation: str) -> None:
    if not condition:
        raise ValueError(explanation)


def verify_completed() -> tuple[dict, dict, dict]:
    final = DIRECTORY / "test_evaluation.json"
    if not final.exists() or read_json(final).get("status") != "completed":
        raise FileNotFoundError("Final test phase is not complete; no scientific report was generated")
    protocol = read_json(DIRECTORY / "protocol.json")
    config = protocol["config"]
    locked = read_json(DIRECTORY / "selection_locked.json")
    evaluation = read_json(final)
    require(evaluation["selection_sha256"] == sha(DIRECTORY / "selection_locked.json"), "Selection changed after test")
    require(locked["protocol_sha256"] == sha(DIRECTORY / "protocol.json"), "Protocol changed after selection")
    require(evaluation["selected_before_test"] == locked["selected_variant"], "Selected variant is inconsistent")
    require(evaluation["runs"] == len(config["variants"]) * len(config["seeds"]), "Test run count incomplete")
    require(locked["test_loaded"] is False and locked["old_test_previously_viewed"] is True, "Invalid evaluation provenance")
    for path, digest in protocol["sources"].items():
        require(sha(ROOT / path) == digest, f"Frozen source/config/data changed: {path}")
    for key, digest in locked["checkpoint_hashes"].items():
        require(sha(DIRECTORY / "runs" / key / "best.pt") == digest, f"Frozen checkpoint changed: {key}")
    return config, locked, evaluation


def flatten_metrics(score: dict) -> dict:
    return {"accuracy": score["accuracy"], "macro_f1": score["macro_f1"],
            "balanced_accuracy": score["balanced_accuracy_fixed_labels"],
            **{f"{label}_{metric}": score["per_class"][label][metric]
               for label in CLASSES for metric in ("precision", "recall", "f1")}}


def score_frame(frame: pd.DataFrame) -> tuple[dict, np.ndarray, np.ndarray]:
    mapping = {label: index for index, label in enumerate(CLASSES)}
    require(set(frame.true_aami_label).issubset(mapping) and set(frame.predicted_aami_label).issubset(mapping),
            "Unknown predicted/true class")
    truth = frame.true_aami_label.map(mapping).to_numpy(dtype=np.int64)
    prediction = frame.predicted_aami_label.map(mapping).to_numpy(dtype=np.int64)
    probs = frame[[f"probability_{c}" for c in CLASSES]].to_numpy(dtype=np.float64)
    require(bool(np.isfinite(probs).all()) and float(np.max(np.abs(probs.sum(1) - 1))) < 1e-6,
            "Invalid probability array")
    require(np.array_equal(probs.argmax(1), prediction), "Probability/label mismatch")
    require(not frame.sample_id.duplicated().any(), "Repeated sample identifier")
    require(np.array_equal(frame.correct.to_numpy(), truth == prediction), "Incorrect cached correctness column")
    return independent_score(truth, prediction, CLASSES), truth, prediction


def load_results(config: dict, locked: dict) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    runs, classes, errors, confusions = [], [], [], []
    references = {}
    for variant in config["variants"]:
        identifier = variant["id"]
        for seed in config["seeds"]:
            directory = DIRECTORY / "runs" / identifier / str(seed)
            summary = read_json(directory / "summary.json")
            for split in ("val", "test"):
                frame = pd.read_csv(directory / f"{split}_predictions.csv", keep_default_na=False, dtype={"record_id": str})
                score, truth, prediction = score_frame(frame)
                comparison = frame[["sample_id", "record_id", "subject_id", "annotation_sample", "original_label", "true_aami_label"]]
                if split not in references:
                    references[split] = comparison
                else:
                    require(comparison.equals(references[split]), f"Evaluation rows/labels differ: {identifier}/{seed}/{split}")
                saved = read_json(directory / f"{split}_metrics.json")
                for metric in ("accuracy", "macro_f1"):
                    require(abs(score[metric] - saved[metric]) < 1e-12, f"Independent metrics differ: {identifier}/{seed}/{split}")
                require(score["confusion_matrix"] == saved["confusion_matrix"], "Saved confusion differs")
                runs.append({"variant": identifier, "seed": seed, "split": split,
                             "selected_by_validation": identifier == locked["selected_variant"],
                             "best_epoch": summary["best_epoch"], "epochs_ran": summary["epochs_ran"],
                             "fit_seconds": summary["fit_seconds"], "parameters": summary["parameters"],
                             "sample_count": len(frame), "patient_count": frame.subject_id.nunique(),
                             **flatten_metrics(score)})
                for label in CLASSES:
                    classes.append({"variant": identifier, "seed": seed, "split": split, "label": label,
                                    **score["per_class"][label]})
                matrix = np.asarray(score["confusion_matrix"])
                for actual, label in enumerate(CLASSES):
                    for predicted, predicted_label in enumerate(CLASSES):
                        confusions.append({"variant": identifier, "seed": seed, "split": split,
                                           "true_label": label, "predicted_label": predicted_label,
                                           "count": int(matrix[actual, predicted]), "true_support": int(matrix[actual].sum()),
                                           "within_true_fraction": float(matrix[actual, predicted] / matrix[actual].sum())})
                for subject, part in frame.groupby("subject_id", sort=True):
                    positions = part.index.to_numpy()
                    patient = independent_score(truth[positions], prediction[positions], CLASSES)
                    for label in CLASSES:
                        for predicted_label in CLASSES:
                            if label != predicted_label:
                                count = patient["confusion_matrix"][CLASSES.index(label)][CLASSES.index(predicted_label)]
                                errors.append({"variant": identifier, "seed": seed, "split": split, "subject_id": subject,
                                               "records": ";".join(sorted(part.record_id.unique())), "true_label": label,
                                               "predicted_label": predicted_label, "count": count,
                                               "true_support": patient["per_class"][label]["support"],
                                               "predicted_count": patient["per_class"][predicted_label]["predicted_count"]})
    return pd.DataFrame(runs), pd.DataFrame(classes), pd.DataFrame(errors), pd.DataFrame(confusions)


def aggregate_runs(runs: pd.DataFrame, config: dict) -> pd.DataFrame:
    rows = []
    for variant in config["variants"]:
        for split in ("val", "test"):
            part = runs[runs.variant.eq(variant["id"]) & runs.split.eq(split)]
            require(set(part.seed) == set(config["seeds"]), "A predeclared seed is missing")
            row = {"variant": variant["id"], "split": split, "seeds": len(part),
                   "selected_by_validation": bool(part.selected_by_validation.all()),
                   "sample_count_per_seed": int(part.sample_count.iloc[0]),
                   "patients_per_seed": int(part.patient_count.iloc[0]),
                   "parameters": int(part.parameters.iloc[0])}
            for metric in METRICS:
                row[f"{metric}_mean"] = float(part[metric].mean())
                row[f"{metric}_sample_sd"] = float(part[metric].std(ddof=1))
            rows.append(row)
    return pd.DataFrame(rows)


def aggregate_classes(class_runs: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for (variant, split, label), part in class_runs.groupby(["variant", "split", "label"], sort=False):
        require(part.support.nunique() == 1, "Class support changed across seeds")
        row = {"variant": variant, "split": split, "label": label, "seeds": len(part),
               "support_per_seed": int(part.support.iloc[0])}
        for metric in ("precision", "recall", "f1", "predicted_count"):
            row[f"{metric}_mean"] = float(part[metric].mean())
            row[f"{metric}_sample_sd"] = float(part[metric].std(ddof=1))
        rows.append(row)
    return pd.DataFrame(rows)


def paired_ablations(runs: pd.DataFrame, config: dict) -> pd.DataFrame:
    pairs = [("ce_inverse", "ce_sqrt", "weight_smoothing"),
             ("ce_sqrt", "focal_sqrt", "focal_modulation"),
             ("focal_sqrt", "focal_sqrt_rr", "rr_branch_package")]
    rows = []
    for before, after, factor in pairs:
        for split in ("val", "test"):
            left = runs[runs.variant.eq(before) & runs.split.eq(split)].set_index("seed").loc[config["seeds"]]
            right = runs[runs.variant.eq(after) & runs.split.eq(split)].set_index("seed").loc[config["seeds"]]
            for metric in METRICS:
                delta = right[metric] - left[metric]
                rows.append({"factor": factor, "before": before, "after": after, "split": split, "metric": metric,
                             "paired_seed_count": len(delta), "mean_delta": float(delta.mean()),
                             "sample_sd_of_paired_delta": float(delta.std(ddof=1)),
                             **{f"delta_seed_{seed}": float(delta.loc[seed]) for seed in config["seeds"]}})
    return pd.DataFrame(rows)


def historical_rows() -> pd.DataFrame:
    rows = []
    original = ROOT / "results/classification/nsvf44_v1"
    audit = read_json(ROOT / "results/stability_audit_20261116/nsvf_audit.json")
    for model in ("logistic_regression", "random_forest", "cnn_1d"):
        for split in ("val", "test"):
            stored = read_json(original / f"{split}_metrics_{model}.json")
            rows.append({"kind": "original_saved", "model": model, "split": split, "seed_count": 1,
                         "accuracy": stored["accuracy"], "macro_f1": stored["macro_f1"],
                         "balanced_accuracy": stored["macro_recall"],
                         **{f"{label}_{metric}": stored["per_class"][label][metric]
                            for label in CLASSES for metric in ("precision", "recall", "f1")}})
    for split, value in audit["partition_metrics"].items():
        rows.append({"kind": "current_original_checkpoint_replay", "model": "cnn_1d", "split": split,
                     "seed_count": 1, **flatten_metrics(value["current_checkpoint_replay"])})
    return pd.DataFrame(rows)


def audit_explanations(config: dict, locked: dict) -> pd.DataFrame:
    """Check stored IG arrays and provenance without changing root-owned outputs."""
    folder = DIRECTORY / "explanations"
    manifest = read_json(folder / "manifest.json")
    require(manifest["variant"] == locked["selected_variant"] and manifest["test_used_for_explanations"] is False,
            "Explanation selection or split provenance mismatch")
    ranking = sorted((read_json(DIRECTORY / "runs" / manifest["variant"] / str(seed) / "val_metrics.json")["macro_f1"], seed)
                     for seed in config["seeds"])
    require(manifest["seed"] == ranking[len(ranking) // 2][1], "IG seed is not the middle validation-ranked seed")
    for key, path in (("script_sha256", ROOT / "src/evaluation/final_explanations.py"),
                      ("validation_npz_sha256", ROOT / config["dataset"] / "val.npz"),
                      ("rr_normalizer_sha256", DIRECTORY / "rr_normalization.json"),
                      ("checkpoint_sha256", DIRECTORY / "runs" / manifest["variant"] / str(manifest["seed"]) / "best.pt")):
        require(sha(path) == manifest[key], f"IG source hash mismatch: {key}")
    predictions = pd.read_csv(DIRECTORY / "runs" / manifest["variant"] / str(manifest["seed"]) / "val_predictions.csv")
    rows = []
    with np.load(ROOT / config["dataset"] / "val.npz", allow_pickle=False) as data:
        for example in manifest["examples"]:
            index = example["npz_row"]
            label = example["true_class"]
            candidates = np.flatnonzero(data["y"] == CLASSES.index(label))
            require(index == int(candidates[len(candidates) // 2]), "IG case was not the middle true-class row")
            require(str(data["sample_id"][index]) == example["sample_id"], "IG sample identity mismatch")
            require(predictions.iloc[index].predicted_aami_label == example["predicted_class"], "IG target differs from saved validation prediction")
            with np.load(folder / f"class_{label}.npz", allow_pickle=False) as stored:
                require(all(bool(np.isfinite(stored[key]).all()) for key in stored.files), "Nonfinite IG arrays")
                require(np.array_equal(stored["waveform_mV"], data["X_filtered"][index, 0]), "IG displayed waveform differs from validation data")
                total = float(stored["wave_attribution"].sum() + stored["rr_attribution"].sum())
                require(abs(total - example["attribution_sum"]) < 2e-6, "IG signed attribution sum mismatch")
                require(np.array_equal(stored["rr_attribution"], np.asarray(example["rr_attributions"], dtype=np.float32)), "IG RR attribution mismatch")
                wave_l1 = float(np.abs(stored["wave_attribution"]).sum())
                absolute_error = abs(example["attribution_sum"] - example["target_logit_difference"])
                require(abs(absolute_error - example["completeness_absolute_error"]) < 1e-9, "IG completeness arithmetic mismatch")
                rows.append({"variant": manifest["variant"], "seed": manifest["seed"], "split": "val",
                             "sample_id": example["sample_id"], "true_class": label,
                             "predicted_class": example["predicted_class"], "steps": example["steps"],
                             "target_logit_difference": example["target_logit_difference"],
                             "attribution_sum": example["attribution_sum"],
                             "completeness_absolute_error": absolute_error,
                             "completeness_relative_error": example["completeness_relative_error"],
                             "wave_attribution_l1": wave_l1,
                             "wave_l1_change_64_to_128": example["wave_l1_change_64_to_128"],
                             "relative_wave_l1_change_64_to_128": example["wave_l1_change_64_to_128"] / max(wave_l1, 1e-12),
                             "finite_arrays": True, "manifest_sha256": sha(folder / "manifest.json")})
    require(len(rows) == 4 and {row["true_class"] for row in rows} == set(CLASSES), "IG class coverage incomplete")
    return pd.DataFrame(rows)


def save_figure(fig, filename: str, footer: str) -> None:
    fig.text(.015, .012, footer, ha="left", va="bottom", fontsize=8, color="#4c5965")
    fig.tight_layout(rect=(0, .065, 1, .965))
    fig.savefig(FIGURES / filename, dpi=300, facecolor="white", bbox_inches="tight")
    plt.close(fig)


def draw_figures(aggregate: pd.DataFrame, confusions: pd.DataFrame, distribution: pd.DataFrame,
                 ablations: pd.DataFrame, selected: str, config: dict) -> list[str]:
    FIGURES.mkdir(parents=True, exist_ok=True)
    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 10,
                         "axes.spines.top": False, "axes.spines.right": False,
                         "axes.grid": False, "axes.titleweight": "bold"})
    identifiers = [v["id"] for v in config["variants"]]
    labels = [LABELS[i] + (" *" if i == selected else "") for i in identifiers]
    footer = "MIT-BIH fixed patient split | mean +/- sample SD over 3 seeds | * selected by mean validation Macro-F1; old test already viewed"
    names = []
    fig, axes = plt.subplots(1, 2, figsize=(12, 5))
    for ax, metric, title in zip(axes, ("macro_f1", "balanced_accuracy"), ("Macro-F1", "Balanced accuracy")):
        x = np.arange(len(identifiers))
        for offset, split, color in ((-.16, "val", "#5a7b95"), (.16, "test", "#a277aa")):
            part = aggregate[aggregate.split.eq(split)].set_index("variant").loc[identifiers]
            ax.bar(x + offset, part[f"{metric}_mean"], .3, yerr=part[f"{metric}_sample_sd"],
                   color=color, alpha=.9, capsize=4, label="Validation" if split == "val" else "Previously viewed test")
        ax.set_xticks(x, labels, rotation=14, ha="right"); ax.set_ylim(0, 1)
        ax.set_ylabel(title); ax.set_title(title); ax.legend(fontsize=8); ax.grid(axis="y", alpha=.2)
    fig.suptitle("Controlled four-class experiments: all predeclared variants", fontsize=14)
    names.append("controlled_overall.png"); save_figure(fig, names[-1], footer)

    fig, axes = plt.subplots(1, 3, figsize=(13, 4.8), sharey=True)
    test = aggregate[aggregate.split.eq("test")].set_index("variant").loc[identifiers]
    x = np.arange(len(identifiers))
    for ax, label in zip(axes, ("S", "F", "V")):
        for offset, metric, color in ((-.22, "precision", "#527b96"), (0, "recall", "#ca9549"), (.22, "f1", "#578f87")):
            ax.bar(x + offset, test[f"{label}_{metric}_mean"], .2,
                   yerr=test[f"{label}_{metric}_sample_sd"], capsize=3, color=color, label=metric.capitalize())
        ax.set_xticks(x, labels, rotation=25, ha="right"); ax.set_ylim(0, 1); ax.grid(axis="y", alpha=.2)
        ax.set_title(f"{label}: test support = {int(distribution[(distribution.split == 'test') & (distribution.label == label)].sample_count.iloc[0])}")
    axes[0].set_ylabel("Per-class score"); axes[-1].legend(fontsize=8)
    lower = min(float((test[f"{label}_{metric}_mean"] - test[f"{label}_{metric}_sample_sd"]).min())
                for label in ("S", "F", "V") for metric in ("precision", "recall", "f1"))
    upper = max(float((test[f"{label}_{metric}_mean"] + test[f"{label}_{metric}_sample_sd"]).max())
                for label in ("S", "F", "V") for metric in ("precision", "recall", "f1"))
    axes[-1].set_ylim(min(0, lower) - .02, max(1, upper) + .02)
    for ax in axes:
        ax.axhline(0, color="#71808b", linewidth=.7)
    fig.suptitle("Minority-class trade-offs on the previously viewed test set", fontsize=14)
    names.append("controlled_minority_tradeoffs.png"); save_figure(fig, names[-1], footer)

    fig, axes = plt.subplots(2, 2, figsize=(10, 8))
    for ax, identifier in zip(axes.ravel(), identifiers):
        part = confusions[confusions.variant.eq(identifier) & confusions.split.eq("test")]
        probabilities = part.pivot_table(index="true_label", columns="predicted_label", values="within_true_fraction", aggfunc="mean").reindex(index=CLASSES, columns=CLASSES).to_numpy()
        counts = part.pivot_table(index="true_label", columns="predicted_label", values="count", aggfunc="mean").reindex(index=CLASSES, columns=CLASSES).to_numpy()
        ax.imshow(probabilities, vmin=0, vmax=1, cmap="Blues")
        for i in range(4):
            for j in range(4):
                ax.text(j, i, f"{probabilities[i,j]:.1%}\n({counts[i,j]:.1f})", ha="center", va="center", fontsize=8,
                        color="white" if probabilities[i,j] > .5 else "#233746")
        ax.set_xticks(range(4), CLASSES); ax.set_yticks(range(4), CLASSES)
        ax.set_xlabel("Predicted"); ax.set_ylabel("True"); ax.set_title(LABELS[identifier] + (" *" if identifier == selected else ""))
    fig.suptitle("Previously viewed test confusion: mean row fraction and mean count", fontsize=14)
    names.append("controlled_confusion.png"); save_figure(fig, names[-1], "Same test beats reused across 3 seeds; parenthesized counts are means, not independent pooled sample counts. * validation-selected")

    fig, axes = plt.subplots(1, 2, figsize=(11, 4.6))
    x = np.arange(3); bottom = np.zeros(3)
    for label, color in zip(CLASSES, COLORS):
        part = distribution[distribution.label.eq(label)].set_index("split").loc[["train", "val", "test"]]
        axes[0].bar(x, part.sample_count, .62, label=label, color=color)
        axes[1].bar(x, part.sample_fraction, .62, bottom=bottom, label=label, color=color)
        bottom += part.sample_fraction.to_numpy()
    axes[0].clear()
    for i, label in enumerate(CLASSES):
        part = distribution[distribution.label.eq(label)].set_index("split").loc[["train", "val", "test"]]
        bars = axes[0].bar(x + (i - 1.5) * .17, part.sample_count, .16, label=label, color=COLORS[i])
        axes[0].bar_label(bars, fontsize=8, padding=2)
    axes[0].set_yscale("log"); axes[0].set_ylabel("Beat count (log scale)"); axes[0].set_ylim(1, 180000)
    axes[1].set_ylabel("Within-partition fraction"); axes[1].set_ylim(0, 1.05)
    for ax in axes:
        ax.set_xticks(x, ["Train (31 patients)", "Validation (6)", "Test (6)"]); ax.legend(ncol=4, fontsize=8)
    fig.suptitle("Fixed four-class data: sample frequency does not equal patient diversity", fontsize=13)
    names.append("controlled_distribution.png"); save_figure(fig, names[-1], "Original class labels and patient split are unchanged. Test S=10; F=371; F source is concentrated in one patient.")

    fig, axes = plt.subplots(1, 2, figsize=(12, 4.8), sharey=True)
    factors = ["weight_smoothing", "focal_modulation", "rr_branch_package"]
    for ax, split in zip(axes, ("val", "test")):
        for offset, metric, color in ((-.23, "macro_f1", "#597f99"), (0, "S_f1", "#d09942"), (.23, "F_f1", "#8b69a8")):
            part = ablations[(ablations.split == split) & (ablations.metric == metric)].set_index("factor").loc[factors]
            ax.bar(np.arange(3) + offset, part.mean_delta, .2, yerr=part.sample_sd_of_paired_delta,
                   capsize=3, color=color, label=metric)
        ax.axhline(0, color="#344956", linewidth=.8)
        ax.set_xticks(range(3), ["Weight smoothing", "Focal modulation", "RR branch package"], rotation=12, ha="right")
        ax.set_title("Validation" if split == "val" else "Previously viewed test"); ax.legend(fontsize=8)
    axes[0].set_ylabel("Paired seed change (after - before)")
    fig.suptitle("Adjacent controlled comparisons: observed trade-offs, no test reselection", fontsize=14)
    names.append("controlled_paired_ablation.png"); save_figure(fig, names[-1], "Mean +/- sample SD of paired seed differences (n=3). RR comparison adds both timing information and a small trainable branch.")
    return names


def mean_sd(row, metric: str) -> str:
    return f"{row[f'{metric}_mean']:.4f}±{row[f'{metric}_sample_sd']:.4f}"


def write_report(config: dict, locked: dict, evaluation: dict, aggregate: pd.DataFrame, class_aggregate: pd.DataFrame,
                 historical: pd.DataFrame, errors: pd.DataFrame, ablations: pd.DataFrame,
                 distribution: pd.DataFrame, figures: list[str], explanations: pd.DataFrame) -> None:
    selected = locked["selected_variant"]
    now = datetime.now(ZoneInfo("Asia/Shanghai")).isoformat()
    lines = ["# 类别不平衡受控实验报告", "", f"报告实际生成时间：{now}。所有数值来自已完成的12组真实训练及冻结后的测试阶段。",
             "", "## 协议与证据范围", "", "保持44条非起搏记录、43患者组及原31/6/6患者分区，固定253点单导联窗口、原训练侧标量归一化和原标签；不删除困难患者、不改测试标签。训练开始前冻结协议、源码和数据SHA256，训练先经稳定性审计放行。",
             "", "4方案×3随机种子（20261027、20261116、20261117）；每方案最多25轮、patience=5，以验证四类Macro-F1早停。所有3seed均保留，没有按测试结果挑seed。各方案以三seed平均验证Macro-F1选型，配置顺序处理完全同分；选型和全部checkpoint哈希在test前锁定。训练阶段不加载测试数组/标签参与选型，仅读取test.npz字节保存SHA256。",
             "", f"验证锁定方案：**{selected}**。测试阶段状态：{evaluation['status']}，共{evaluation['runs']}组。对所有预声明方案的评估处于同一个最终冻结阶段；测试后不再调参或重新选型。",
             "", "原测试集此前已经查看，本轮只是既定测试集上的探索性复用，不能写作新盲测、外部验证或临床证据。三seed的±是样本标准差（ddof=1），反映训练随机性；不是患者层面的标准误、置信区间或显著性检验。",
             "", "## 方案与研究问题", "", "|方案|损失与权重|额外输入/结构|预定比较|", "|---|---|---|---|",
             "|ce_inverse|原逆频率加权交叉熵|原三层1D-CNN|保留原方法的三seed重新训练基线|",
             "|ce_sqrt|逆频率权重开平方；加权均值CE|同一波形CNN|与ce_inverse比较权重平滑|",
             "|focal_sqrt|sqrt逆频率alpha，gamma=2；按batch的alpha总和归一化|同一波形CNN|与ce_sqrt比较focal调制|",
             "|focal_sqrt_rr|同一focal损失|波形编码器＋4维过去RR输入＋16维分支|与focal_sqrt比较RR分支方案|",
             "", "CE的权重和focal的alpha采用相同加权均值口径；alpha全局归一化仅作共同尺度变换。过去RR由原始合法心拍标注位置计算，不用类别标签或未来RR；包括上一RR、过去最多10个RR均值及两个比值，StandardScaler仅在训练样本拟合。记录首拍无过去间隔时使用预设0.8 s，不过本实验有效窗口有5 s边缘保护。",
             "", "RR方案同时增加上下文输入与可训练分支/参数，因此可评价整个方案，不能排除容量变化的贡献。全部方案仍依赖专家心拍定位，不是任意未标注ECG的独立检测器。",
             "", "## 固定样本分布", "", "|分区|N|S|V|F|", "|---|---:|---:|---:|---:|"]
    for split in ("train", "val", "test"):
        row = distribution[distribution.split.eq(split)].set_index("label")
        lines.append(f"|{split}|" + "|".join(str(int(row.loc[c, "sample_count"])) for c in CLASSES) + "|")
    lines += ["", "验证S高度集中于患者232，测试F几乎由患者208贡献；测试S只有10拍，1拍变化即可影响召回0.10。三seed不能增加独立患者数量。详见`results/stability_audit_20261116/nsvf_class_distribution.csv`及本轮患者错误来源汇总。",
              "", "## 原始实验、当前工件复验与新训练", "", "|证据阶段|模型|分区|Accuracy|Macro-F1|Balanced Accuracy|", "|---|---|---|---:|---:|---:|"]
    for row in historical.itertuples():
        kind = "原始保存实验（1seed）" if row.kind == "original_saved" else "原工件当前重推（无重新训练）"
        lines.append(f"|{kind}|{row.model}|{row.split}|{row.accuracy:.4f}|{row.macro_f1:.4f}|{row.balanced_accuracy:.4f}|")
    fresh_baseline = read_json(DIRECTORY / "runs/ce_inverse/20261027/val_metrics.json")["macro_f1"]
    old_baseline = float(historical[(historical.kind == "original_saved") & historical.model.eq("cnn_1d") & historical.split.eq("val")].macro_f1.iloc[0])
    lines += ["", "以上原始结果及重推不是本轮12组新训练之一；下表ce_inverse是同方法多seed重训，不能把三个seed称为三次独立患者验证。N/V任务的0.9865不参与四分类表的排名或直接差值计算。",
              "", f"相同seed=20261027的新ce_inverse验证Macro-F1为{fresh_baseline:.6f}，历史CNN为{old_baseline:.6f}。当前训练使用4个CPU线程，历史运行线程或数值执行环境可能不同；同一算法和seed不保证跨执行环境的训练轨迹逐位一致。未开展机制分解，不能把差别确定归因于线程或据此断言旧结果错误。原checkpoint本轮全量推理复验一致与新模型重新训练是两类证据。",
              "", "## 12组新实验的三seed汇总", "", "|方案|分区|Accuracy|Macro-F1|Balanced Accuracy|参数量|验证选定|", "|---|---|---:|---:|---:|---:|---|"]
    for _, row in aggregate.iterrows():
        lines.append(f"|{row['variant']}|{row['split']}|{mean_sd(row,'accuracy')}|{mean_sd(row,'macro_f1')}|{mean_sd(row,'balanced_accuracy')}|{int(row['parameters'])}|{'是' if row['selected_by_validation'] else '否'}|")
    lines += ["", "## 各类Precision、Recall与F1", "", "|方案|分区|类别|每seed支持数|Precision|Recall|F1|", "|---|---|---|---:|---:|---:|---:|"]
    for _, row in class_aggregate.iterrows():
        lines.append(f"|{row['variant']}|{row['split']}|{row['label']}|{int(row['support_per_seed'])}|{mean_sd(row,'precision')}|{mean_sd(row,'recall')}|{mean_sd(row,'f1')}|")
    lines += ["", "## 相邻因素比较", "", "下表为同seed的after−before差值再求均值和样本标准差，不按测试分数重排方案。", "", "|因素|分区|ΔMacro-F1|ΔS F1|ΔF F1|ΔV F1|ΔAccuracy|", "|---|---|---:|---:|---:|---:|---:|"]
    for factor in ("weight_smoothing", "focal_modulation", "rr_branch_package"):
        for split in ("val", "test"):
            part = ablations[(ablations.factor == factor) & (ablations.split == split)].set_index("metric")
            cells = [f"{part.loc[m,'mean_delta']:+.4f}±{part.loc[m,'sample_sd_of_paired_delta']:.4f}" for m in ("macro_f1", "S_f1", "F_f1", "V_f1", "accuracy")]
            lines.append(f"|{factor}|{split}|" + "|".join(cells) + "|")
    selected_rows = aggregate[aggregate.variant.eq(selected)].set_index("split")
    base = aggregate[aggregate.variant.eq("ce_inverse")].set_index("split")
    lines += ["", "## 预定方案的观察与取舍", "", f"根据验证均值预先选定{selected}：验证Macro-F1={mean_sd(selected_rows.loc['val'],'macro_f1')}，已查看测试Macro-F1={mean_sd(selected_rows.loc['test'],'macro_f1')}。",
              f"相对本轮ce_inverse三seed基线，测试Macro-F1均值差为{selected_rows.loc['test','macro_f1_mean'] - base.loc['test','macro_f1_mean']:+.4f}，Accuracy均值差为{selected_rows.loc['test','accuracy_mean'] - base.loc['test','accuracy_mean']:+.4f}。这些是固定患者分区的描述性变化，不能解释为总体人群保证。"]
    for split in ("val", "test"):
        row = selected_rows.loc[split]
        lines.append(f"{split}侧所选方案S Precision/Recall/F1均值={row['S_precision_mean']:.4f}/{row['S_recall_mean']:.4f}/{row['S_f1_mean']:.4f}；F为{row['F_precision_mean']:.4f}/{row['F_recall_mean']:.4f}/{row['F_f1_mean']:.4f}；V Recall/F1为{row['V_recall_mean']:.4f}/{row['V_f1_mean']:.4f}。")
    lines += ["", f"**不能认为S/F识别问题已经解决。** 所选方案测试S Precision仅{selected_rows.loc['test','S_precision_mean']:.4f}，召回提高仍伴随大量误报。相对新ce_inverse，F F1从{mean_sd(base.loc['test'],'F_f1')}下降到{mean_sd(selected_rows.loc['test'],'F_f1')}，F Recall从{base.loc['test','F_recall_mean']:.4f}下降至{selected_rows.loc['test','F_recall_mean']:.4f}。该退步与总体Macro-F1提高同时存在；不能只报道整体分数或F Precision而省略F漏分。",
              "", f"Focal调制单独加入sqrt-CE后的测试Macro-F1均值变化为{float(ablations[(ablations.factor=='focal_modulation') & (ablations.split=='test') & (ablations.metric=='macro_f1')].mean_delta.iloc[0]):+.4f}，本轮没有显示其单独带来整体改进；RR分支的相邻比较也不能推出所有类别同步改善。"]
    lines += ["", "少数类召回、Precision、F1和总体误报必须共同评价；如果某项均值提高而另一项下降，应按上述完整表格保留，不以单个最好seed或单类召回替代总体结果。测试分数不用于重命名优胜方案，也不触发替换线上六模型。",
              "", "## 错误与患者来源", "", "下面列所选方案每个错误方向按三seed平均次数最多的患者。次数是相同样本的多模型输出均值，不能相加为新增独立患者证据。", "", "|分区|错误方向|主要来源患者|平均错误拍数|该类患者支持数|", "|---|---|---|---:|---:|"]
    for split in ("val", "test"):
        for true_label in CLASSES:
            part = errors[(errors.variant == selected) & (errors.split == split) & (errors.true_label == true_label)]
            by = part.groupby(["predicted_label", "subject_id"], sort=False).agg(mean_count=("count", "mean"), support=("true_support", "first")).reset_index()
            for predicted_label in CLASSES:
                direction = by[by.predicted_label.eq(predicted_label)]
                if direction.empty or direction.mean_count.max() == 0:
                    continue
                top = direction.loc[direction.mean_count.idxmax()]
                lines.append(f"|{split}|{true_label}→{predicted_label}|{top['subject_id']}|{top['mean_count']:.2f}|{int(top['support'])}|")
    lines += ["", "患者来源表支持错误分布诊断，不证明模型依据某个特定P波、QRS机制或患者身份做判断。S/F稀有且患者覆盖不足，没有通过loss设置增加患者来源；引入RR后仍需外部患者、自动定位误差与概率校准验证。",
              "", "## 验证侧积分梯度数值核验", "",
              f"所选方案的解释使用验证Macro-F1居中seed={int(explanations.seed.iloc[0])}，每个真实类别固定取NPZ中间行；未按测试表现或归因外观挑样本。四例恰好均分类正确，不能代表全部错误或总体解释质量。归因目标为预测类logit，相对于零标准化波形与零标准化RR；它们对应训练统计参考，并不代表生理正常ECG。",
              f"采用128区间梯形积分，并保留64→128步波形归因变化。四例完整性绝对误差为{explanations.completeness_absolute_error.min():.6f}—{explanations.completeness_absolute_error.max():.6f} logit，相对误差{100*explanations.completeness_relative_error.min():.3f}%—{100*explanations.completeness_relative_error.max():.3f}%；波形归因L1变化相对于128步L1总量约{100*explanations.relative_wave_l1_change_64_to_128.min():.2f}%—{100*explanations.relative_wave_l1_change_64_to_128.max():.2f}%。所有保存数组均有限，来源哈希、样本身份、波形与有符号归因和均复核一致。",
              "数值误差小仅支持这四例的离散积分近似，不能证明参考选择合理、归因具有因果忠实性或模型掌握临床知识；不同案例使用独立波形色标，不能直接比较颜色强度。归因总和为负也不等于分类错误，只表示目标logit低于所选参考输入的该类logit。",
              "", "## 图表与可复现工件", ""]
    for name in figures:
        lines.append(f"![{name}](../figures/final_optimization/{name})")
        lines.append("")
    lines += ["运行命令：`python -B -m src.evaluation.controlled_report`。脚本只在test_evaluation状态completed后读取真实结果、核验冻结哈希并生成本报告，不执行训练或测试。",
              "", "主要CSV：`controlled_run_summary.csv`、`controlled_aggregate_summary.csv`、`controlled_class_run_summary.csv`、`controlled_class_summary.csv`、`controlled_ablation_summary.csv`、`controlled_error_summary.csv`、`controlled_confusion_summary.csv`、`controlled_historical_summary.csv`。均位于`results/controlled_imbalance_20261116/`。",
              "", "正式原实验与线上6模型工件保持保留；本轮新的RR模型是探索性实验工件，需要独立部署适配与验证后才能考虑上线。"]
    (ROOT / "reports/imbalance_experiments.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check-only", action="store_true", help="Check completeness/provenance without writing outputs")
    args = parser.parse_args()
    try:
        config, locked, evaluation = verify_completed()
    except FileNotFoundError as error:
        print(f"PENDING: {error}", flush=True)
        return 2
    if args.check_only:
        print("Completed frozen inputs and all checkpoint hashes verified", flush=True)
        return 0
    runs, class_runs, errors, confusions = load_results(config, locked)
    aggregate = aggregate_runs(runs, config)
    by_variant = aggregate[aggregate.split.eq("val")].set_index("variant")
    expected_selected = max((v["id"] for v in config["variants"]),
                            key=lambda name: by_variant.loc[name, "macro_f1_mean"])
    require(expected_selected == locked["selected_variant"], "Stored validation selection does not match independent recomputation")
    class_aggregate = aggregate_classes(class_runs)
    ablations = paired_ablations(runs, config)
    historical = historical_rows()
    explanations = audit_explanations(config, locked)
    distribution = pd.read_csv(ROOT / "results/stability_audit_20261116/nsvf_class_distribution.csv")
    outputs = {"controlled_run_summary": runs, "controlled_aggregate_summary": aggregate,
               "controlled_class_run_summary": class_runs, "controlled_class_summary": class_aggregate,
               "controlled_error_summary": errors, "controlled_confusion_summary": confusions,
               "controlled_ablation_summary": ablations, "controlled_historical_summary": historical,
               "controlled_explanation_summary": explanations}
    for name, frame in outputs.items():
        frame.to_csv(DIRECTORY / f"{name}.csv", index=False, encoding="utf-8-sig")
    figures = draw_figures(aggregate, confusions, distribution, ablations, locked["selected_variant"], config)
    write_report(config, locked, evaluation, aggregate, class_aggregate, historical, errors, ablations, distribution, figures, explanations)
    print(aggregate[["variant", "split", "macro_f1_mean", "macro_f1_sample_sd", "selected_by_validation"]].to_string(index=False), flush=True)
    print("Report generated from completed locked experiments; no training or test inference executed.", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
