"""Read-only reconstruction of the existing experiments, not a new blind test.

Run ``python -B -m src.evaluation.stability_audit`` from the project root.
Original data, predictions and checkpoints are never rewritten.  A new output
directory is required on reruns so provenance cannot be silently replaced.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime
import gc
import hashlib
import json
from pathlib import Path
import platform
import sys
import time
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
import torch
import wfdb

from ..labels import AAMI_MAP
from ..models.classifiers import HeartbeatCNN
from ..preprocessing.filters import FilterConfig, filter_continuous
from ..preprocessing.normalization import fit_train_standardizer, transform
from ..training.trainer import class_weights_from_training, predict_cnn
from .metrics import make_prediction_frame, score_predictions


ROOT = Path(__file__).resolve().parents[2]
SPLITS = ("train", "val", "test")
TASKS = {"nv": ["N", "V"], "nsvf": ["N", "S", "V", "F"]}
HISTORICAL_LIMIT = (
    "原验证/测试集此前已经查看。本次为当前工件的回顾性重推与完整性复核，"
    "不是新的盲测、外部验证或独立泛化性能估计。历史CSV没有checkpoint哈希和"
    "不可变代码提交标识；数值复现支持当前工件一致性，不能完全重建历史选择过程。"
)


def file_sha256(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(chunk)
    return value.hexdigest()


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def write_json(path: Path, value: dict | list) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")


def require(condition: bool, explanation: str) -> None:
    if not condition:
        raise ValueError(explanation)


def independent_score(truth: np.ndarray, prediction: np.ndarray, classes: list[str]) -> dict:
    """Keep all declared labels, including classes absent in an individual patient."""
    truth = np.asarray(truth, dtype=np.int64)
    prediction = np.asarray(prediction, dtype=np.int64)
    k = len(classes)
    require(truth.shape == prediction.shape and truth.ndim == 1 and len(truth) > 0,
            "Invalid or empty metric arrays")
    require(bool(((truth >= 0) & (truth < k) & (prediction >= 0) & (prediction < k)).all()),
            "Unknown label code in metric arrays")
    matrix = np.bincount(truth * k + prediction, minlength=k * k).reshape(k, k)
    per_class = {}
    for index, label in enumerate(classes):
        tp = int(matrix[index, index])
        support = int(matrix[index].sum())
        predicted = int(matrix[:, index].sum())
        precision = tp / predicted if predicted else 0.0
        recall = tp / support if support else 0.0
        f1 = 2 * tp / (support + predicted) if support + predicted else 0.0
        per_class[label] = {"precision": precision, "recall": recall, "f1": f1,
                            "support": support, "predicted_count": predicted}
    return {"accuracy": float(np.trace(matrix) / len(truth)),
            "macro_f1": float(np.mean([v["f1"] for v in per_class.values()])),
            "balanced_accuracy_fixed_labels": float(np.mean([v["recall"] for v in per_class.values()])),
            "sample_count": len(truth), "per_class": per_class, "confusion_matrix": matrix.tolist()}


def exact_cross_split_duplicates(arrays: dict[str, dict], field: str) -> dict:
    """Detect byte-exact float32 windows; shape resemblance is a different claim."""
    previous: dict[bytes, tuple[str, str]] = {}
    pair_counts: Counter = Counter()
    examples = []
    for split in SPLITS:
        data = arrays[split]
        for sample_id, wave in zip(data["sample_id"], data[field]):
            digest = hashlib.sha256(np.asarray(wave, dtype="<f4").tobytes()).digest()
            before = previous.get(digest)
            if before is not None and before[0] != split:
                pair_counts[f"{before[0]}->{split}"] += 1
                if len(examples) < 20:
                    examples.append({"first_split": before[0], "first_sample_id": before[1],
                                     "second_split": split, "second_sample_id": str(sample_id),
                                     "sha256": digest.hex()})
            elif before is None:
                previous[digest] = (split, str(sample_id))
    return {"field": field, "cross_split_matching_window_count": sum(pair_counts.values()),
            "pair_counts": dict(pair_counts), "examples": examples,
            "definition": "SHA256 of canonical little-endian float32 full 253-point window bytes",
            "limit": "只检验精确数值重复；未穷举跨患者近似形态。不同患者相似形态不是同源窗口泄漏的充分证据。"}


def check_partition_overlap(arrays: dict[str, dict]) -> dict:
    output = {}
    for field in ("subject_id", "record_id", "sample_id"):
        intersections = {}
        for i, left in enumerate(SPLITS):
            for right in SPLITS[i + 1:]:
                intersection = sorted(set(arrays[left][field].astype(str)) & set(arrays[right][field].astype(str)))
                intersections[f"{left}:{right}"] = intersection
        output[field] = intersections
    # With disjoint records, neighbouring windows cannot share a raw recording
    # interval across sets, irrespective of their morphology correlation.
    output["same_record_cross_split_overlapping_intervals"] = 0
    for i, left in enumerate(SPLITS):
        for right in SPLITS[i + 1:]:
            common = set(arrays[left]["record_id"]) & set(arrays[right]["record_id"])
            for record in common:
                left_centers = np.sort(arrays[left]["annotation_sample"][arrays[left]["record_id"] == record])
                right_centers = np.sort(arrays[right]["annotation_sample"][arrays[right]["record_id"] == record])
                for center in left_centers:
                    lo = np.searchsorted(right_centers, center - 252)
                    hi = np.searchsorted(right_centers, center + 252, side="right")
                    output["same_record_cross_split_overlapping_intervals"] += int(hi - lo)
    output["grouping_scope"] = "记录导出的匿名患者键；201/202为已知同一患者并被合并。未通过生物识别验证其他潜在同源身份。"
    return output


def verify_raw_windows(root: Path, arrays: dict[str, dict], config: dict, source) -> list[dict]:
    settings = config["filter"]
    filter_config = FilterConfig(**{k: settings[k] for k in ("low_hz", "high_hz", "prototype_order", "guard_s")})
    require(np.allclose(filter_config.parameters(360)["sos"], settings["sos"], rtol=0, atol=1e-15),
            "Saved filter coefficients differ from current fixed filter")
    rows = []
    for split in SPLITS:
        data = arrays[split]
        for record_id in sorted(set(data["record_id"].astype(str))):
            for extension in ("hea", "dat", "atr"):
                source(root / "data/mitdb" / f"{record_id}.{extension}")
            record = wfdb.rdrecord(str(root / "data/mitdb" / record_id), physical=True)
            annotation = wfdb.rdann(str(root / "data/mitdb" / record_id), "atr")
            channel = record.sig_name.index("MLII") if "MLII" in record.sig_name else 0
            require(record.fs == 360 and record.units[channel] == "mV", "Unexpected raw signal calibration")
            indices = np.flatnonzero(data["record_id"] == record_id)
            centers = data["annotation_sample"][indices]
            original_indices = np.asarray([int(str(v).rsplit(":", 1)[1]) for v in data["sample_id"][indices]])
            require(np.array_equal(np.asarray(annotation.sample)[original_indices], centers),
                    f"Raw annotation positions do not match {record_id}")
            require(np.array_equal(np.asarray(annotation.symbol)[original_indices], data["original_label"][indices]),
                    f"Raw annotation symbols do not match {record_id}")
            filtered, safe = filter_continuous(record.p_signal[:, channel], record.fs, filter_config)
            locations = centers[:, None] + np.arange(-108, 145)[None, :]
            require(bool(safe[locations].all()), f"Unsafe/edge window entered {record_id}")
            reconstructed = filtered[locations].astype(np.float32)
            maximum = float(np.max(np.abs(reconstructed - data["X_filtered"][indices, 0, :])))
            require(maximum <= 1e-6, f"Full raw-filter replay differs for {record_id}: {maximum}")
            rows.append({"split": split, "record_id": record_id, "windows_checked": len(indices),
                         "fs_hz": record.fs, "lead": record.sig_name[channel],
                         "raw_annotation_positions_and_symbols_match": True,
                         "max_filtered_mV_absolute_difference": maximum})
        print(f"[stability-audit] raw replay {config['dataset_version']} {split} complete", flush=True)
    return rows


def audit_task(root: Path, task: str, output: Path, source) -> dict:
    classes = TASKS[task]
    dataset = root / f"data/processed/mitdb44_{task}_v1"
    result = root / f"results/classification/{task}44_v1"
    checkpoint_dir = root / f"checkpoints/{task}44_v1/formal/cnn"
    config = read_json(source(dataset / "processing_config.json"))
    normalizer = read_json(source(dataset / "normalization.json"))
    experiment_config = read_json(source(result / "config.json"))
    metadata = pd.read_csv(source(dataset / "metadata.csv"), keep_default_na=False, low_memory=False,
                           dtype={"record_id": str})
    manifest = pd.read_csv(source(dataset / "split_manifest.csv"), keep_default_na=False, dtype={"record_id": str})
    arrays = {}
    for split in SPLITS:
        with np.load(source(dataset / f"{split}.npz"), allow_pickle=False) as stored:
            arrays[split] = {key: stored[key] for key in stored.files}
    require(config["classes"] == classes and config["full_aami_mapping"] == AAMI_MAP, "Label configuration mismatch")
    require(manifest.groupby("subject_id").split.nunique().max() == 1, "Patient crosses partitions in manifest")
    pair = manifest[manifest.record_id.isin(["201", "202"])]
    require(len(pair) == 2 and pair.split.nunique() == 1 and pair.subject_id.nunique() == 1, "201/202 grouping error")
    require(set(manifest.record_id) == set(config["included_records"]) and len(manifest) == 44, "Record selection mismatch")
    split_rows = []
    normalization_rows = []
    for split, data in arrays.items():
        part = metadata[(metadata.included.astype(str).str.lower() == "true") & metadata.split.eq(split)].sort_values("npz_row")
        require(np.array_equal(part.npz_row, np.arange(len(part))), f"Metadata NPZ index gap in {split}")
        require(len(part) == len(data["y"]), f"Metadata row count differs in {split}")
        require(len(set(data["sample_id"])) == len(data["sample_id"]), f"Duplicate sample IDs within {split}")
        for key in ("sample_id", "record_id", "subject_id", "annotation_sample", "original_label", "mapped_label", "lead"):
            require(np.array_equal(part[key].to_numpy(), data[key]), f"Metadata/NPZ {key} mismatch in {split}")
        require(np.array_equal(part.target_label.to_numpy(dtype=np.int64), data["y"]), "Target code mismatch")
        require(np.array_equal(np.asarray(classes)[data["y"]], data["mapped_label"]), "Encoded label mismatch")
        require(all(AAMI_MAP[str(symbol)] == label for symbol, label in zip(data["original_label"], data["mapped_label"])),
                "Raw symbol mapping mismatch")
        require(data["class_names"].tolist() == classes and data["X"].shape == (len(part), 1, 253), "Array structure mismatch")
        require(float(data["fs_hz"]) == 360 and int(data["center_index"]) == 108, "Window convention mismatch")
        require(bool(np.isfinite(data["X"]).all() and np.isfinite(data["X_filtered"]).all()), "Nonfinite model input")
        require(set(part.record_id) == set(manifest[manifest.split.eq(split)].record_id), "Manifest/metadata mismatch")
        reconstructed = transform(data["X_filtered"], normalizer)
        difference = float(np.max(np.abs(reconstructed - data["X"])))
        require(difference == 0, f"Stored normalized X does not reconstruct in {split}")
        normalization_rows.append({"split": split, "normalized_input_max_abs_difference": difference})
        for label in classes:
            selected = data["mapped_label"] == label
            split_rows.append({"task": task, "split": split, "label": label, "sample_count": int(selected.sum()),
                               "sample_fraction": float(selected.mean()),
                               "subject_count": len(set(data["subject_id"][selected])),
                               "record_count": len(set(data["record_id"][selected]))})
    train = arrays["train"]
    recalculated = fit_train_standardizer(train["X_filtered"], train["sample_id"])
    require(normalizer["fit_split"] == "train", "Normalizer was not marked train fitted")
    for key in ("mean_mV", "std_mV"):
        require(abs(recalculated[key] - normalizer[key]) < 1e-12, f"Train-fitted normalization {key} differs")
    for key in ("fit_beat_count", "fit_value_count", "training_sample_ids_sha256"):
        require(recalculated[key] == normalizer[key], f"Normalizer training provenance {key} differs")
    overlap = check_partition_overlap(arrays)
    for field in ("subject_id", "record_id", "sample_id"):
        require(not any(overlap[field].values()), f"Cross-partition {field} overlap")
    exact_duplicates = [exact_cross_split_duplicates(arrays, field) for field in ("X_filtered", "X")]
    require(not any(row["cross_split_matching_window_count"] for row in exact_duplicates), "Exact waveform duplicates cross partitions")
    raw_rows = verify_raw_windows(root, arrays, config, source)
    original_weights = read_json(source(result / "training_class_weights.json"))
    weights = class_weights_from_training(train["y"], len(classes))
    require(np.array_equal(weights, np.asarray(original_weights["inverse_frequency_balanced_weights"], dtype=np.float32)),
            "Loss weights differ from train-label-only formula")
    summary = read_json(source(checkpoint_dir / "cnn_training_summary.json"))
    history = pd.read_csv(source(checkpoint_dir / "cnn_training_history.csv"))
    best_path = source(checkpoint_dir / "cnn_best.pt")
    final_path = source(checkpoint_dir / "cnn_final_best.pt")
    best = torch.load(best_path, map_location="cpu", weights_only=True)
    final = torch.load(final_path, map_location="cpu", weights_only=True)
    require(best["class_count"] == len(classes) and final["class_names"] == classes, "Checkpoint class order mismatch")
    same_tensors = set(best["state_dict"]) == set(final["state_dict"]) and all(
        torch.equal(best["state_dict"][key], final["state_dict"][key]) for key in best["state_dict"])
    require(same_tensors, "Best and final-best checkpoint tensors differ")
    best_epoch = int(history.iloc[int(history.val_macro_f1.to_numpy().argmax())].epoch)
    require(best_epoch == best["epoch"] == final["best_epoch"] == summary["best_epoch"], "Validation early stopping epoch mismatch")
    require(best["seed"] == final["seed"] == config["seed"] == experiment_config["seed"], "Checkpoint seed mismatch")
    require(final["dataset_config_hash"] == file_sha256(dataset / "processing_config.json"), "Checkpoint dataset hash mismatch")
    require(np.array_equal(weights, np.asarray(summary["training_class_weights"], dtype=np.float32)), "Training summary loss weights differ")
    model = HeartbeatCNN(len(classes))
    model.load_state_dict(final["state_dict"], strict=True)
    model.eval()
    partition_metrics = {}
    replay_rows = []
    patient_rows = []
    for split in ("val", "test"):
        data = arrays[split]
        old_frame = pd.read_csv(source(result / f"{split}_predictions_cnn_1d.csv"), keep_default_na=False, dtype={"record_id": str})
        require(len(old_frame) == len(data["y"]) and not old_frame.sample_id.duplicated().any(), "CSV size/IDs differ")
        for csv_key, npz_key in (("sample_id", "sample_id"), ("subject_id", "subject_id"), ("record_id", "record_id"),
                                 ("annotation_sample", "annotation_sample"), ("original_label", "original_label"),
                                 ("true_aami_label", "mapped_label"), ("lead_name", "lead")):
            require(np.array_equal(old_frame[csv_key], data[npz_key]), f"CSV/NPZ index or {csv_key} mismatch")
        probabilities = old_frame[[f"probability_{c}" for c in classes]].to_numpy(dtype=np.float64)
        require(bool(np.isfinite(probabilities).all()) and float(np.max(np.abs(probabilities.sum(1) - 1))) < 1e-6,
                "Invalid historical probabilities")
        old_pred = probabilities.argmax(1)
        require(np.array_equal(np.asarray(classes)[old_pred], old_frame.predicted_aami_label), "CSV argmax/class mapping mismatch")
        require(np.array_equal(data["y"] == old_pred, old_frame.correct.to_numpy()), "CSV correctness cache mismatch")
        with torch.inference_mode():
            pred, probability = predict_cnn(model, data["X"][:, 0, :], batch_size=512)
        require(not any(module.training for module in model.modules()), "Evaluation mode was lost")
        fresh = independent_score(data["y"], pred, classes)
        historical = independent_score(data["y"], old_pred, classes)
        saved_metrics = read_json(source(result / f"{split}_metrics_cnn_1d.json"))
        project_metrics = score_predictions(data["y"], pred, classes)
        for field in ("accuracy", "macro_f1"):
            require(abs(historical[field] - saved_metrics[field]) < 1e-12, "Independent/JSON metric mismatch")
            require(abs(fresh[field] - project_metrics[field]) < 1e-12, "Independent/project metric mismatch")
        maximum = float(np.max(np.abs(probability.astype(np.float64) - probabilities)))
        mismatches = int(np.count_nonzero(pred != old_pred))
        require(mismatches == 0 and maximum <= 1e-5, f"Checkpoint replay disagrees with historical output in {split}")
        frame = make_prediction_frame(data, data["y"], pred, probability, classes, "cnn_1d", split)
        frame.to_csv(output / f"{task}_{split}_cnn_replay_predictions.csv", index=False, encoding="utf-8-sig")
        partition_metrics[split] = {"original_saved_csv_recomputed": historical, "current_checkpoint_replay": fresh,
                                    "original_prediction_file_sha256": file_sha256(result / f"{split}_predictions_cnn_1d.csv"),
                                    "class_mismatches": mismatches, "max_probability_abs_difference": maximum,
                                    "inference_eval_mode_all_modules": True}
        for subject in sorted(set(data["subject_id"])):
            mask = data["subject_id"] == subject
            values = independent_score(data["y"][mask], pred[mask], classes)
            for label, metrics in values["per_class"].items():
                patient_rows.append({"task": task, "split": split, "subject_id": subject, "label": label,
                                     "patient_sample_count": int(mask.sum()), **metrics,
                                     "recall_undefined_if_support_zero": metrics["support"] == 0})
            for actual in range(len(classes)):
                for predicted in range(len(classes)):
                    if actual != predicted:
                        replay_rows.append({"task": task, "split": split, "subject_id": subject,
                                            "true_label": classes[actual], "predicted_label": classes[predicted],
                                            "count": values["confusion_matrix"][actual][predicted]})
        print(f"[stability-audit] {task} {split} replay: F1={fresh['macro_f1']:.9f}, mismatches={mismatches}, max_dp={maximum:.3g}", flush=True)
    pd.DataFrame(split_rows).to_csv(output / f"{task}_class_distribution.csv", index=False, encoding="utf-8-sig")
    pd.DataFrame(patient_rows).to_csv(output / f"{task}_patient_class_metrics.csv", index=False, encoding="utf-8-sig")
    pd.DataFrame(replay_rows).to_csv(output / f"{task}_patient_error_directions.csv", index=False, encoding="utf-8-sig")
    pd.DataFrame(raw_rows).to_csv(output / f"{task}_raw_filter_replay.csv", index=False, encoding="utf-8-sig")
    output_value = {"task": task, "class_names": classes, "class_distribution": split_rows,
                    "split_groups": {split: {"samples": len(data["y"]), "records": len(set(data["record_id"])),
                                               "patients": len(set(data["subject_id"]))} for split, data in arrays.items()},
                    "partition_overlap": overlap, "exact_waveform_duplicate_checks": exact_duplicates,
                    "metadata_npz_and_csv_alignment": "PASS: full sample IDs, original/mapped labels, encoded y, positions, leads and row order",
                    "normalization": {"saved": normalizer, "recomputed_train_only": recalculated,
                                      "split_reconstruction": normalization_rows},
                    "raw_filter_replay": {"records": len(raw_rows), "windows": sum(r["windows_checked"] for r in raw_rows),
                                          "max_mV_abs_difference": max(r["max_filtered_mV_absolute_difference"] for r in raw_rows)},
                    "training_weights": weights.tolist(),
                    "checkpoint": {"best_file_sha256": file_sha256(best_path), "final_file_sha256": file_sha256(final_path),
                                   "best_epoch": best_epoch, "all_best_and_final_tensors_identical": same_tensors,
                                   "dataset_hash_matches": True, "seed": best["seed"],
                                   "history_best_validation_macro_f1": float(history.val_macro_f1.max()),
                                   "historical_training_device": summary["device"], "replay_device": "cpu"},
                    "partition_metrics": partition_metrics,
                    "validation_test_macro_f1_gap": partition_metrics["test"]["current_checkpoint_replay"]["macro_f1"] -
                                                    partition_metrics["val"]["current_checkpoint_replay"]["macro_f1"],
                    "integrity_checks_passed": True, "historical_limit": HISTORICAL_LIMIT}
    write_json(output / f"{task}_audit.json", output_value)
    del arrays, model
    gc.collect()
    return output_value


def write_reports(root: Path, output: Path, audit: dict) -> None:
    nv = audit["tasks"]["nv"]
    multiclass = audit["tasks"]["nsvf"]
    errors = pd.read_csv(output / "nv_patient_error_directions.csv")
    total = int(errors.query("split == 'val' and true_label == 'N' and predicted_label == 'V'")["count"].sum())
    from_109 = int(errors.query("split == 'val' and subject_id == 'subject_109' and true_label == 'N' and predicted_label == 'V'")["count"].sum())
    lines = ["# CNN泛化与数据划分审计", "", f"实际运行：{audit['started_at_Asia_Shanghai']}；CPU，PyTorch线程数4。", "", HISTORICAL_LIMIT,
             "", "## 审计结论", "", "两任务完整性核验通过，未发现足以阻断后续受控训练的数据/索引/工件错误。原N/V差距在当前工件重推后仍存在，没有通过改标签、删患者或修改原结果消除。",
             f"N/V验证/测试Macro-F1分别为{nv['partition_metrics']['val']['current_checkpoint_replay']['macro_f1']:.9f} / {nv['partition_metrics']['test']['current_checkpoint_replay']['macro_f1']:.9f}。",
             f"已证实的分层现象：验证N→V误报共{total}拍，其中患者109贡献{from_109}拍（{from_109 / total:.2%}）。这解释误差分布的集中来源，尚不能证明具体生理、噪声或网络机制。",
             "", "## 数据组成与划分", "", "正式实验使用44条非起搏记录、43患者组；102/104/107/217排除，201/202同患者同分区。两任务复用同一31/6/6患者划分，属于患者独立划分，不是随机按心拍切分。",
             "", "|任务|分区|患者|记录|心拍|逐类拍数|", "|---|---|---:|---:|---:|---|"]
    for task, values in audit["tasks"].items():
        for split, counts in values["split_groups"].items():
            labels = ", ".join(f"{row['label']}={row['sample_count']}" for row in values["class_distribution"] if row["split"] == split)
            lines.append(f"|{task}|{split}|{counts['patients']}|{counts['records']}|{counts['samples']}|{labels}|")
    lines += ["", "## 用户要求的12项核验", "", "|序号|检查|实际证据与状态|", "|---:|---|---|"]
    checks = [
        ("标签定义", "通过：源码AAMI_MAP、配置、完整metadata/NPZ及CSV的原符号、类别编码、概率列顺序逐拍一致。"),
        ("预处理一致性", "通过：两任务全部有效心拍从原WFDB物理信号重新连续滤波截窗，与保存X_filtered比较；44条原始标注位置和符号逐拍复核。MLII/360Hz/253点一致。"),
        ("训练侧归一化", "通过：仅train的X_filtered重算μ、σ与训练ID哈希；全部train/val/test的标准化X精确重建，未逐患者或逐拍重新拟合。"),
        ("重复心拍或相邻相关片段", "通过有界检查：subject/record/sample_id交集均0，同一记录跨集合重叠区间0；全量X_filtered和X的跨集合精确波形哈希匹配均0。未穷举不同患者近似波形；自然形态相似不等同信息泄漏。"),
        ("分组划分", "通过：manifest与NPZ一致，201/202同组且同分区；31/6/6患者互斥。"),
        ("测试集参与选型", "源码与保存协议支持：训练配置固定，CNN按val早停，测试在拟合保存后加载；没有发现test选型代码。限制：CSV缺少不可变执行链，测试已有查看历史，不能证明全部人工历史决策从未受测试结果影响。"),
        ("CNN按验证指标选模型", "通过：训练history的最高val Macro-F1对应epoch与best、final、训练summary一致。"),
        ("权重/实验加载", "通过：best与final逐张量相同，类数/次序/seed/预处理配置SHA256相符；train标签重算损失权重一致；当前checkpoint重推与历史类别全量一致。"),
        ("指标计算一致", "通过：独立NumPy混淆矩阵计算、项目score_predictions、历史JSON/CSV及当前重推的Accuracy/Macro-F1一致；固定声明类别，zero_division=0。"),
        ("eval模式", "通过：当前模型及全部子模块eval，inference_mode执行；原predict_cnn源码也调用eval。不能从CSV单独证明历史进程状态。"),
        ("分布/数量差异", "已核查：见逐类分区表与患者覆盖CSV。NV的V占比接近，但患者109误报集中；四分类测试S仅10拍、F仅371拍，来源不足。"),
        ("索引/映射/缓存错位", "通过：metadata npz_row连续，sample_id唯一，NPZ行序、原始标注索引/位置/符号、y、CSV行序与correct/argmax逐拍匹配。")]
    for index, (name, evidence) in enumerate(checks, 1):
        lines.append(f"|{index}|{name}|{evidence}|")
    lines += ["", "## 原始结果与当前工件复验", "", "|任务|分区|历史Accuracy|复验Accuracy|历史Macro-F1|复验Macro-F1|类别不同数|概率最大绝对差|", "|---|---|---:|---:|---:|---:|---:|---:|"]
    for task, value in audit["tasks"].items():
        for split, comparison in value["partition_metrics"].items():
            old, fresh = comparison["original_saved_csv_recomputed"], comparison["current_checkpoint_replay"]
            lines.append(f"|{task}|{split}|{old['accuracy']:.9f}|{fresh['accuracy']:.9f}|{old['macro_f1']:.9f}|{fresh['macro_f1']:.9f}|{comparison['class_mismatches']}|{comparison['max_probability_abs_difference']:.3g}|")
    lines += ["", "## 已证实与尚未证实", "", "已证实：差距在当前正确加载的同一CNN复验中存在；标签、预处理、索引和指标口径一致；未发现患者/记录/心拍ID交叉或精确波形重复；患者109贡献98.65%的验证N→V误报。",
              "", "尚未证实：109的波形形态、噪声、幅值或特定网络表示哪个导致失败；不同患者的形态分布是否足以解释全部差距；任意未知患者上的性能。没有实施临床专家盲评、因果特征干预或新外部数据验证。",
              "", "仅以整体验证/测试分数反差不能判定过拟合、泄漏或时间退化。分层分析不是从正式评估删除109的依据；本轮保留全部原分区与标签。",
              "", "## 修复/后续决策", "", "无需修复原数据划分或替换历史模型，允许在保留基线及固定分区下开展独立配置的验证侧受控训练。尚未获得性能稳定性修复；后续实验无论指标升降均须保存，并将最终测试标为已查看测试集上的预先选定模型评估，不称新盲测。",
              "", "## 复现与工件", "", f"运行命令：`{audit['command']}`。", "", f"运行结果目录：`{output.relative_to(root).as_posix()}`；机器可读总表`audit_summary.json`，两任务明细`nv_audit.json`/`nsvf_audit.json`，逐拍重推CSV、患者错误表、类分布表、全量原始滤波复验表及输入SHA256清单均在该目录。",
              "", "首次运行目录必须不存在；复跑时用`--output results/stability_audit_另一次运行`，防止覆盖。已有原始数据、模型、训练日志、指标和预测均只读。"]
    (root / "reports/cnn_generalization_audit.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    short = ["# 模型稳定性审计", "", f"实际运行：{audit['started_at_Asia_Shanghai']}。", "", HISTORICAL_LIMIT,
             "", "本阶段为完整性与历史工件复验，不包含新训练。详细12项检查见[cnn_generalization_audit.md](cnn_generalization_audit.md)。",
             "", "## 状态", "", "- 两任务NPZ/metadata/原WFDB标注/CSV对齐、训练侧归一化、44记录原始信号滤波重建、患者互斥、精确重复检查及CNN工件重推通过。",
             "- 当前工件验证/测试预测类别与历史CSV全部相同，原始指标没有被重写。",
             f"- N/V验证—测试Macro-F1差距仍为{nv['validation_test_macro_f1_gap']:.6f}；患者109误报集中是真实分层观察，机制尚未证实。",
             f"- 四分类CNN测试Macro-F1为{multiclass['partition_metrics']['test']['current_checkpoint_replay']['macro_f1']:.6f}，仍有S/F失败；不能把完整性通过写成模型已经稳定。",
             "- 未发现阻断后续受控实验的完整性错误；没有新的盲测、外部验证或临床适用性证据。",
             "", "## 后续实验边界", "", "保持现有分区、标签、原模型与正式结果；改进只在独立目录配置和保存。训练/验证侧选型后冻结所选模型，再对已查看测试集作一次预定评估。所有候选结果应公开，不能用测试反复挑选或把困难患者移除。",
             "", f"机器可读证据：`{output.relative_to(root).as_posix()}/audit_summary.json`。"]
    (root / "reports/model_stability_audit.md").write_text("\n".join(short) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("results/stability_audit_20261116"))
    args = parser.parse_args()
    output = args.output if args.output.is_absolute() else ROOT / args.output
    require(output.resolve().is_relative_to((ROOT / "results").resolve()), "Audit output must be inside this project's results directory")
    output.mkdir(parents=True, exist_ok=False)
    torch.set_num_threads(4)
    torch.set_num_interop_threads(1)
    started = time.perf_counter()
    inventory = {}

    def source(path: Path) -> Path:
        name = path.relative_to(ROOT).as_posix()
        if name not in inventory:
            inventory[name] = {"bytes": path.stat().st_size, "sha256": file_sha256(path)}
        return path

    value = {"started_at_Asia_Shanghai": datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(),
             "command": "python -B -m src.evaluation.stability_audit --output " + str(args.output),
             "runtime": {"python": platform.python_version(), "numpy": np.__version__, "torch": torch.__version__,
                         "device": "cpu", "torch_threads": torch.get_num_threads()},
             "historical_limit": HISTORICAL_LIMIT, "tasks": {}}
    for relative in ("src/classify.py", "src/training/trainer.py", "src/models/classifiers.py", "src/labels.py",
                     "src/evaluation/metrics.py", "src/evaluation/stability_audit.py", "src/preprocessing/filters.py",
                     "src/preprocessing/splitting.py", "src/preprocessing/normalization.py", "src/preprocessing/extraction.py",
                     "src/datasets/build.py"):
        source(ROOT / relative)
    try:
        for task in TASKS:
            value["tasks"][task] = audit_task(ROOT, task, output, source)
        changed = [name for name, item in inventory.items() if file_sha256(ROOT / name) != item["sha256"]]
        require(not changed, f"Audit inputs changed during execution: {changed}")
        value.update({"all_integrity_checks_passed": True, "blocks_controlled_new_training": False,
                      "all_input_hashes_unchanged_after_audit": True, "source_count": len(inventory),
                      "elapsed_seconds": time.perf_counter() - started})
        write_json(output / "input_manifest.json", inventory)
        write_json(output / "audit_summary.json", value)
        write_json(output / "audit.json", {**value, "passed_integrity_checks": True, "blocking_issues": []})
        write_reports(ROOT, output, value)
        print(json.dumps({"all_integrity_checks_passed": True, "blocks_controlled_new_training": False,
                          "output": str(output), "elapsed_seconds": value["elapsed_seconds"]}, ensure_ascii=False), flush=True)
        return 0
    except Exception as error:
        value.update({"all_integrity_checks_passed": False, "blocks_controlled_new_training": True,
                      "failure": f"{type(error).__name__}: {error}", "elapsed_seconds": time.perf_counter() - started})
        write_json(output / "audit_failure.json", value)
        write_json(output / "audit.json", {**value, "passed_integrity_checks": False,
                                           "blocking_issues": [value["failure"]]})
        write_json(output / "input_manifest.json", inventory)
        raise


if __name__ == "__main__":
    sys.exit(main())
