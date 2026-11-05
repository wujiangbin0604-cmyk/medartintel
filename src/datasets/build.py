"""Build reproducible 44-record MIT-BIH heartbeat datasets without training."""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime
import json
from pathlib import Path
import platform
import shutil
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
import wfdb

from ..analysis import primary_channel, summarize_labels
from ..download import prepare_data, sha256
from ..io import load_record
from ..labels import AAMI_MAP
from ..preprocessing.extraction import extract_record
from ..preprocessing.filters import FilterConfig
from ..preprocessing.normalization import fit_train_standardizer, transform
from ..preprocessing.splitting import SPLITS, annotation_census, lock_subject_split

PACED_RECORDS = ("102", "104", "107", "217")
BASE_GROUPS = ("N", "S", "V", "F", "Q")


def write_json(value, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")


def count_full_database(root: Path, names: list[str], annotations: list[pd.DataFrame]) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Return verified full-48 symbol and AAMI counts using the raw .atr files."""
    symbols: dict[str, Counter] = {}
    for name, frame in zip(names, annotations):
        symbols[name] = Counter(frame.symbol.tolist())
    excluded = set(PACED_RECORDS)
    for name in sorted(excluded):
        if name not in symbols:
            ann = wfdb.rdann(str(root / "data/mitdb" / name), "atr")
            symbols[name] = Counter(ann.symbol)
    official_names = (root / "data/mitdb/RECORDS").read_text(encoding="utf-8").split()
    if set(names) | excluded != set(official_names):
        raise AssertionError("Cannot account for the official 48-record list")
    rows = []
    for record_id in official_names:
        for symbol, count in symbols[record_id].items():
            rows.append({"record_id": record_id, "symbol": symbol, "count": int(count),
                         "aami_label": AAMI_MAP.get(symbol, ""),
                         "included_in_44_record_experiment": record_id not in excluded})
    per_record = pd.DataFrame(rows).sort_values(["record_id", "symbol"]).reset_index(drop=True)
    all48 = per_record.groupby("symbol", as_index=False).agg(count=("count", "sum"))
    all48["aami_label"] = all48.symbol.map(AAMI_MAP).fillna("")
    all48["annotation_kind"] = all48.aami_label.map(lambda x: "mapped_beat" if x else "non_beat_or_unmapped")
    all48 = all48.sort_values("count", ascending=False).reset_index(drop=True)
    per_record["annotation_kind"] = per_record.aami_label.map(lambda x: "mapped_beat" if x else "non_beat_or_unmapped")
    return all48, per_record


def _class_counts(metadata: pd.DataFrame, groups: tuple[str, ...]) -> pd.DataFrame:
    included = metadata[metadata.included]
    counts = included.mapped_label.value_counts().reindex(groups, fill_value=0)
    total = int(counts.sum())
    return pd.DataFrame({"aami_label": groups, "class_id": range(len(groups)),
                         "sample_count": [int(counts[g]) for g in groups],
                         "percentage": [float(counts[g] / total * 100) if total else 0 for g in groups]})


def verify_export(output: Path, metadata: pd.DataFrame, normalizer: dict, split_manifest: pd.DataFrame,
                  expected_length: int, raw_dir: Path, manifest: list[dict], groups: tuple[str, ...]) -> dict:
    included = metadata[metadata.included].copy()
    subject_sets: dict[str, set[str]] = {}
    seen_ids: set[str] = set()
    counts: dict[str, dict] = {}
    train_filtered = None
    train_ids = None
    for split in SPLITS:
        path = output / f"{split}.npz"
        part = included[included.split == split].sort_values("npz_row")
        with np.load(path, allow_pickle=False) as data:
            x, y = data["X"], data["y"]
            filtered = data["X_filtered"]
            if x.shape != (len(part), 1, expected_length) or filtered.shape != x.shape:
                raise AssertionError(f"{split}: window shape does not agree with metadata")
            if x.dtype != np.float32 or not np.isfinite(x).all() or not np.isfinite(filtered).all():
                raise AssertionError(f"{split}: non-finite or unexpected data dtype")
            if not np.array_equal(y, part.target_label.to_numpy(dtype=np.int64)):
                raise AssertionError(f"{split}: label mismatch")
            for key in ("sample_id", "record_id", "subject_id", "original_label", "mapped_label", "lead"):
                if not np.array_equal(data[key], part[key].astype(str).to_numpy()):
                    raise AssertionError(f"{split}: {key} mismatch")
            if not np.array_equal(data["annotation_sample"], part.annotation_sample.to_numpy(dtype=np.int64)):
                raise AssertionError(f"{split}: annotation sample mismatch")
            if not np.allclose(x, transform(filtered, normalizer), atol=1e-6, rtol=1e-6):
                raise AssertionError(f"{split}: normalization mismatch")
            ids = set(data["sample_id"].tolist())
            if len(ids) != len(part) or ids & seen_ids:
                raise AssertionError("Sample ID leakage or duplication")
            seen_ids.update(ids)
            subject_sets[split] = set(data["subject_id"].tolist())
            counts[split] = {g: int((part.mapped_label == g).sum()) for g in metadata.loc[metadata.is_target, "mapped_label"].drop_duplicates().tolist()}
            counts[split].update({"n_samples": len(part), "n_subjects": len(subject_sets[split]),
                                  "n_records": int(part.record_id.nunique())})
            if split == "train":
                train_filtered, train_ids = filtered.copy(), data["sample_id"].tolist()
                if not np.isclose(x.mean(dtype=np.float64), 0, atol=2e-6) or not np.isclose(x.std(dtype=np.float64), 1, atol=2e-6):
                    raise AssertionError("Training normalization is not standard normal")
    for first, second in (("train", "val"), ("train", "test"), ("val", "test")):
        if subject_sets[first] & subject_sets[second]:
            raise AssertionError("Subject leakage")
    if groups == ("N", "V"):
        for split in ("val", "test"):
            if counts[split].get("N", 0) == 0 or counts[split].get("V", 0) == 0:
                raise AssertionError(f"N/V holdout split {split} must contain both classes")
    pair_splits = split_manifest[split_manifest.record_id.isin(["201", "202"])].split.unique()
    if len(pair_splits) != 1 or len(split_manifest[split_manifest.record_id.isin(["201", "202"])]) != 2:
        raise AssertionError("201 and 202 must be assigned together")
    if set(split_manifest.loc[split_manifest.record_id.isin(["102", "104", "107", "217"]), "record_id"]):
        raise AssertionError("Paced records leaked into the 44-record experiment")
    if not set(split_manifest.loc[split_manifest.record_id.isin(["100", "200"]), "split"]) == {"train"}:
        raise AssertionError("Prior exploration records must remain training-only")
    refit = fit_train_standardizer(train_filtered, train_ids)
    for key in ("mean_mV", "std_mV", "fit_beat_count", "fit_value_count", "training_sample_ids_sha256"):
        if refit[key] != normalizer[key]:
            raise AssertionError("Normalization is not fitted from the exported training set")
    for row in manifest:
        if row["file"].endswith((".dat", ".hea", ".atr")) and sha256(raw_dir / row["file"]) != row["sha256"]:
            raise AssertionError(f"Raw file changed: {row['file']}")
    return {"passed": True, "official_record_count": 48, "included_record_count": 44,
            "excluded_paced_records": list(PACED_RECORDS), "subject_count": int(split_manifest.subject_id.nunique()),
            "split_counts": counts, "window_length": expected_length, "subject_overlap": 0,
            "record_201_202_same_split": True, "records_100_200_train_only": True,
            "normalizer_fitted_only_on_training_samples": True, "original_annotations_preserved": True,
            "original_raw_sha256_unchanged": True, "target_label_mapping": {g: i for i, g in enumerate(groups)},
            "classifier_trained": False, "test_used_for_selection": False}


def build(root: Path, output: Path, groups: tuple[str, ...] = ("N", "V"), offline: bool = False,
          seed: int = 20261027, split_path: Path | None = None) -> dict:
    root, output = root.resolve(), output.resolve()
    if len(set(groups)) != len(groups) or not {"N", "V"}.issubset(groups):
        raise ValueError("Target groups must include unique N and V labels")
    if any(group not in BASE_GROUPS for group in groups):
        raise ValueError(f"Unsupported AAMI group: {groups}")
    record_root = root / "data/mitdb"
    results_dir = root / "results/classification/dataset"
    results_dir.mkdir(parents=True, exist_ok=True)
    output.mkdir(parents=True, exist_ok=True)
    write_json({"status": "running_or_incomplete", "passed": False}, output / "verification.json")

    official, full_manifest = prepare_data(record_root, ["all"], offline=offline, workers=4, mirror="s3")
    if len(official) != 48:
        raise ValueError("Expected the official 48-record database")
    records = [name for name in official if name not in PACED_RECORDS]
    if len(records) != 44:
        raise AssertionError("44-record AAMI protocol list was not formed")
    eligible_manifest = [row for row in full_manifest if row["file"].split(".")[0] in records]
    census = annotation_census(record_root, records)
    selected_split_path = split_path or (output / "split_plan.json")
    split_manifest, plan = lock_subject_split(census, selected_split_path, eligible_manifest, seed)
    split_snapshot = output / "split_plan.json"
    if selected_split_path.resolve() != split_snapshot.resolve():
        if split_snapshot.exists() and sha256(split_snapshot) != sha256(selected_split_path):
            raise ValueError("Existing local split snapshot differs from the supplied locked plan")
        if not split_snapshot.exists():
            shutil.copyfile(selected_split_path, split_snapshot)
    split_manifest.to_csv(output / "split_manifest.csv", index=False, encoding="utf-8-sig")

    fs_config = FilterConfig()
    configuration = {"dataset_version": "mitdb44_" + "".join(groups).lower() + "_v1",
                     "created_at_Asia_Shanghai": datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(),
                     "database_version": "MIT-BIH Arrhythmia Database 1.0.0",
                     "official_records": official, "included_records": records, "excluded_paced_records": list(PACED_RECORDS),
                     "exclusion_basis": "Records 102,104,107,217 contain paced beats; analog tape fidelity limits common pacemaker artifact recognition; standard 44-record AAMI protocol exclusion.",
                     "seed": seed, "classes": list(groups), "class_to_id": {group: index for index, group in enumerate(groups)},
                     "full_aami_mapping": AAMI_MAP, "window_pre_s": .3, "window_post_s": .4,
                     "sample_rate_hz": 360, "window_length_samples": 253,
                     "lead_selection": "Use lead named MLII; otherwise use and record first actual lead",
                     "filter": fs_config.parameters(360), "filter_guard_s": fs_config.guard_s,
                     "normalization": "One global scalar z-score fitted only on included training windows",
                     "split_seed": seed, "split_ratios_by_subject": [.70, .15, .15],
                     "split_plan_path": str(selected_split_path.resolve()), "split_plan_sha256": sha256(selected_split_path),
                     "class_balance_method": "None; retain all eligible beats. Optional model class weights use training labels only.",
                     "test_policy": "Locked test data used once for final evaluation; never for fitting or model selection.",
                     "subject_id_rule": "Record-derived grouping key; 201 and 202 share subject_201_202",
                     "original_annotations_modified": False}
    write_json(configuration, output / "processing_config.json")

    metadata_frames, filtered_vectors, annotation_frames = [], [], []
    record_checks = []
    contexts = {}
    global_row = 0
    for record_id in records:
        print(f"Build {record_id}", flush=True)
        record, check = load_record(record_root, record_id)
        if record.fs != 360.:
            raise ValueError(f"{record_id}: expected 360 Hz; implicit resampling is disabled")
        assign = split_manifest.loc[split_manifest.record_id == record_id].iloc[0]
        table, values, raw_windows, filtered_signal, accepted_rows = extract_record(
            record, assign.split, assign.subject_id, fs_config, groups=groups, pre_s=.3, post_s=.4)
        table["global_row"] = -1
        table.loc[accepted_rows, "global_row"] = np.arange(global_row, global_row + len(values))
        global_row += len(values)
        metadata_frames.append(table)
        filtered_vectors.append(values)
        annotation_frames.append(record.annotations)
        channel = primary_channel(record)
        record_checks.append({**check, "record_id": record_id, "subject_id": assign.subject_id, "split": assign.split,
                              "selected_lead": record.leads[channel], "selected_channel": channel,
                              "included_samples": int(len(values))})
        if record_id in ("100", "200"):
            contexts[record_id] = {"record": record, "channel": channel, "filtered": filtered_signal}

    metadata = pd.concat(metadata_frames, ignore_index=True)
    filtered_windows = np.concatenate(filtered_vectors, axis=0).astype(np.float32, copy=False)
    included = metadata[metadata.included].sort_values("global_row")
    if not np.array_equal(included.global_row.to_numpy(dtype=int), np.arange(len(filtered_windows))):
        raise AssertionError("Feature row ordering drifted from source metadata")
    train = included[included.split == "train"]
    train_indices = train.global_row.to_numpy(dtype=int)
    normalizer = fit_train_standardizer(filtered_windows[train_indices], train.sample_id.tolist())
    normalizer.update({"training_subject_ids": sorted(train.subject_id.unique().tolist()),
                       "training_record_ids": sorted(train.record_id.unique().tolist())})
    write_json(normalizer, output / "normalization.json")
    metadata["npz_row"] = -1
    split_class_counts = []
    for split in SPLITS:
        part = metadata[metadata.included & (metadata.split == split)].sort_values("global_row")
        indices = part.global_row.to_numpy(dtype=int)
        raw = filtered_windows[indices, None, :]
        x = transform(raw, normalizer)
        metadata.loc[part.index, "npz_row"] = np.arange(len(part), dtype=int)
        payload = {"X": x, "X_filtered": raw, "y": part.target_label.to_numpy(dtype=np.int64),
                   "annotation_sample": part.annotation_sample.to_numpy(dtype=np.int64),
                   "fs_hz": np.array(360.), "class_names": np.array(groups), "center_index": np.array(108),
                   "relative_time_s": np.arange(-108, 145) / 360}
        for key in ("sample_id", "record_id", "subject_id", "original_label", "mapped_label", "lead"):
            payload[key] = part[key].astype(str).to_numpy(dtype=str)
        np.savez_compressed(output / f"{split}.npz", **payload)
        for group in groups:
            class_part = part[part.mapped_label == group]
            split_class_counts.append({"split": split, "aami_label": group, "class_id": groups.index(group),
                                       "sample_count": int(len(class_part)),
                                       "subject_count": int(class_part.subject_id.nunique()),
                                       "record_count": int(class_part.record_id.nunique())})

    metadata.drop(columns=["aux_note"], errors="ignore").to_csv(output / "metadata.csv", index=False, encoding="utf-8-sig")
    annotations = pd.concat(annotation_frames, ignore_index=True)
    tables = summarize_labels(annotations, records)
    all48_counts, record_symbol_counts = count_full_database(root, records, annotation_frames)
    all48_counts.to_csv(results_dir / "raw_symbol_counts_all48.csv", index=False, encoding="utf-8-sig")
    record_symbol_counts.to_csv(results_dir / "raw_symbol_counts_by_record_all48.csv", index=False, encoding="utf-8-sig")
    tables["raw_symbol_counts"].to_csv(results_dir / "raw_symbol_counts_44.csv", index=False, encoding="utf-8-sig")
    tables["aami_counts"].to_csv(results_dir / "aami_counts_44.csv", index=False, encoding="utf-8-sig")
    tables["aami_counts_by_record"].to_csv(results_dir / "aami_counts_by_record_44.csv", index=False, encoding="utf-8-sig")
    tables["label_mapping"].to_csv(results_dir / "label_mapping.csv", index=False, encoding="utf-8-sig")
    record_symbol_counts.to_csv(results_dir / "record_symbol_counts_all48.csv", index=False, encoding="utf-8-sig")
    pd.DataFrame(record_checks).to_csv(output / "record_checks.csv", index=False, encoding="utf-8-sig")
    pd.DataFrame(split_class_counts).to_csv(output / "split_class_counts.csv", index=False, encoding="utf-8-sig")
    metadata[metadata.included].groupby(["subject_id", "split", "mapped_label"]).size().reset_index(name="sample_count").to_csv(
        output / "subject_sample_counts.csv", index=False, encoding="utf-8-sig")
    metadata[metadata.included].groupby(["split", "lead"]).size().reset_index(name="sample_count").to_csv(
        output / "lead_sample_counts.csv", index=False, encoding="utf-8-sig")
    metadata.groupby(["split", "exclusion_reason"], dropna=False).size().reset_index(name="count").to_csv(
        output / "exclusion_counts.csv", index=False, encoding="utf-8-sig")
    class_counts = _class_counts(metadata, groups)
    class_counts.to_csv(output / "class_counts.csv", index=False, encoding="utf-8-sig")

    import sklearn
    import scipy
    environment = {"python": platform.python_version(), "numpy": np.__version__, "pandas": pd.__version__,
                   "wfdb": wfdb.__version__, "scipy": scipy.__version__, "scikit_learn": sklearn.__version__}
    write_json(environment, output / "environment.json")
    train_counts = train.mapped_label.value_counts()
    weights = {group: float(len(train) / (len(groups) * train_counts[group])) for group in groups}
    write_json({"source": "training labels only", "inverse_frequency_balanced_weights": weights,
                "applied_during_dataset_build": False}, output / "training_class_weights.json")
    from .plots import generate_dataset_figures
    figure_catalog = generate_dataset_figures(root, metadata, tables, record_symbol_counts, contexts, groups)
    task_tag = "".join(groups).lower()
    figure_catalog.to_csv(results_dir / f"figure_catalog_{task_tag}_44.csv", index=False, encoding="utf-8-sig")
    verification = verify_export(output, metadata, normalizer, split_manifest, 253, record_root, full_manifest, groups)
    verification.update({"target_class_counts": class_counts.to_dict(orient="records"),
                         "raw_symbols_recomputed_from_wfdb": True,
                         "raw_hashes": {row["file"]: row["sha256"] for row in full_manifest if row["file"].endswith((".dat", ".hea", ".atr"))},
                         "figure_count": len(figure_catalog), "figure_files": figure_catalog.file.tolist(),
                         "normalization_fit_sample_count": normalizer["fit_beat_count"],
                         "classifier_trained": False})
    write_json(verification, output / "verification.json")
    write_json(configuration, output / "processing_config.json")
    write_json({"official_record_count": 48, "included_record_count": 44, "excluded_paced_records": list(PACED_RECORDS),
                "split_plan_sha256": sha256(selected_split_path), "dataset_config_sha256": sha256(output / "processing_config.json"),
                "split_manifest_sha256": sha256(output / "split_manifest.csv"), "dataset_verification": verification,
                "figures": figure_catalog.file.tolist()}, results_dir / ("dataset_" + "".join(groups).lower() + "_44_verification.json"))
    print(json.dumps(verification, ensure_ascii=False, indent=2), flush=True)
    return verification


def main() -> None:
    parser = argparse.ArgumentParser(description="Build the AAMI 44-record dataset; no model training")
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--classes", nargs="+", choices=BASE_GROUPS, default=["N", "V"])
    parser.add_argument("--split-plan", type=Path)
    parser.add_argument("--seed", type=int, default=20261027)
    parser.add_argument("--offline", action="store_true")
    args = parser.parse_args()
    root = args.root.resolve()
    output = (args.output_dir if args.output_dir.is_absolute() else root / args.output_dir).resolve()
    split_plan = None if args.split_plan is None else (args.split_plan if args.split_plan.is_absolute() else root / args.split_plan).resolve()
    build(root, output, tuple(args.classes), args.offline, args.seed, split_plan)


if __name__ == "__main__":
    main()
