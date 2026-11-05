from __future__ import annotations

import logging
import re
import threading
from collections import OrderedDict
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd
import wfdb

from src.analysis import primary_channel
from src.io import ECGRecord, load_record
from src.preprocessing.filters import FilterConfig, filter_continuous
from src.preprocessing.normalization import transform
from src.labels import AAMI_MAP

from .model_registry import MODEL_IDS, TASKS, ModelRegistry

LOGGER = logging.getLogger("ecg_ai.data")
MAX_WINDOW_SECONDS = 30.0
MAX_POINTS = 18_000
PRE_SECONDS = 0.3
POST_SECONDS = 0.4


@dataclass
class SignalContext:
    record: ECGRecord
    channel: int
    lead_name: str
    filtered: np.ndarray
    safe: np.ndarray
    filter_config: FilterConfig


class ECGStore:
    """Allowlisted WFDB reader with small bounded caches; source files are read-only."""

    def __init__(self, root: Path):
        self.root = root.resolve()
        self.data_dir = self.root / "data/mitdb"
        self._lock = threading.RLock()
        self._records: OrderedDict[str, ECGRecord] = OrderedDict()
        self._signals: OrderedDict[str, SignalContext] = OrderedDict()
        self._summary_cache: list[dict] | None = None
        self._record_limit = 3
        self._signal_limit = 2
        self._record_ids = self._scan_records()
        self._manifest = self._load_manifest()
        self._normalizers = {task: self._json(self.root / spec["dataset"] / "normalization.json")
                             for task, spec in TASKS.items()}
        self._processing = {task: self._json(self.root / spec["dataset"] / "processing_config.json")
                            for task, spec in TASKS.items()}
        self._validate_preprocessing_compatibility()

    @staticmethod
    def _json(path: Path) -> dict:
        import json
        return json.loads(path.read_text(encoding="utf-8"))

    def _scan_records(self) -> list[str]:
        records = []
        for header in sorted(self.data_dir.glob("*.hea")):
            record_id = header.stem
            if re.fullmatch(r"\d{3}", record_id) and all((self.data_dir / f"{record_id}.{ext}").is_file()
                                                            for ext in ("dat", "atr")):
                records.append(record_id)
        if not records:
            raise FileNotFoundError(f"No complete MIT-BIH .dat/.hea/.atr records found in {self.data_dir}")
        return records

    def _load_manifest(self) -> dict[str, dict]:
        path = self.root / "data/processed/mitdb44_nsvf_v1/split_manifest.csv"
        frame = pd.read_csv(path, dtype={"record_id": str})
        return {str(row.record_id): {"subject_id": str(row.subject_id), "split": str(row.split)}
                for row in frame.itertuples(index=False)}

    def _validate_preprocessing_compatibility(self) -> None:
        first = self._processing["nv"]["filter"]
        second = self._processing["nsvf"]["filter"]
        for key in ("low_hz", "high_hz", "prototype_order", "guard_s", "method"):
            if first.get(key) != second.get(key):
                raise ValueError(f"N/V and N/S/V/F filter configurations differ at {key}")
        for task in TASKS:
            cfg = self._processing[task]
            if int(cfg["window_length_samples"]) != 253 or not np.isclose(cfg["window_pre_s"], PRE_SECONDS) or not np.isclose(cfg["window_post_s"], POST_SECONDS):
                raise ValueError(f"Unexpected saved model window configuration for {task}")

    def record_ids(self) -> list[str]:
        return list(self._record_ids)

    def _header(self, record_id: str):
        self._assert_allowlisted(record_id)
        return wfdb.rdheader(str(self.data_dir / record_id))

    def _assert_allowlisted(self, record_id: str) -> None:
        if record_id not in self._record_ids:
            raise KeyError(f"Record {record_id} is not in the local MIT-BIH allowlist")

    def get_record(self, record_id: str) -> ECGRecord:
        self._assert_allowlisted(record_id)
        with self._lock:
            cached = self._records.get(record_id)
            if cached is not None:
                self._records.move_to_end(record_id)
                return cached
            record, _ = load_record(self.data_dir, record_id)
            self._records[record_id] = record
            self._records.move_to_end(record_id)
            while len(self._records) > self._record_limit:
                evicted, _ = self._records.popitem(last=False)
                self._signals.pop(evicted, None)
            return record

    def signal_context(self, record_id: str) -> SignalContext:
        self._assert_allowlisted(record_id)
        with self._lock:
            cached = self._signals.get(record_id)
            if cached is not None:
                self._signals.move_to_end(record_id)
                return cached
            record = self.get_record(record_id)
            channel = primary_channel(record)
            lead = record.leads[channel]
            filter_cfg_json = self._processing["nsvf"]["filter"]
            cfg = FilterConfig(low_hz=float(filter_cfg_json["low_hz"]), high_hz=float(filter_cfg_json["high_hz"]),
                               prototype_order=int(filter_cfg_json["prototype_order"]), guard_s=float(filter_cfg_json["guard_s"]))
            filtered, safe = filter_continuous(record.signal[:, channel], record.fs, cfg)
            context = SignalContext(record, channel, lead, filtered, safe, cfg)
            self._signals[record_id] = context
            self._signals.move_to_end(record_id)
            while len(self._signals) > self._signal_limit:
                self._signals.popitem(last=False)
            return context

    def records(self) -> list[dict]:
        with self._lock:
            if self._summary_cache is not None:
                return [dict(item) for item in self._summary_cache]
        result = []
        for record_id in self._record_ids:
            header = self._header(record_id)
            annotations = wfdb.rdann(str(self.data_dir / record_id), "atr")
            groups: dict[str, int] = {}
            for symbol in annotations.symbol:
                group = AAMI_MAP.get(symbol)
                if group:
                    groups[group] = groups.get(group, 0) + 1
            manifest = self._manifest.get(record_id, {})
            ml2 = "MLII" in header.sig_name
            included = record_id in self._manifest
            result.append({"record_id": record_id, "sampling_frequency": float(header.fs),
                           "duration_seconds": float(header.sig_len / header.fs),
                           "sample_count": int(header.sig_len), "signal_names": list(header.sig_name),
                           "signal_units": list(header.units), "available_annotations": groups,
                           "annotation_count": len(annotations.sample), "dataset_split": manifest.get("split", "excluded_from_model_dataset"),
                           "subject_id": manifest.get("subject_id", f"subject_{record_id}"),
                           "model_inference_available": bool(included and ml2),
                           "model_inference_reason": None if included and ml2 else
                               ("此记录不属于当前 44 条模型训练数据" if not included else "记录缺少 MLII 导联")})
        with self._lock:
            self._summary_cache = result
        return [dict(item) for item in result]

    def record_detail(self, record_id: str) -> dict:
        self._assert_allowlisted(record_id)
        summary = next(item for item in self.records() if item["record_id"] == record_id)
        return dict(summary)

    def _lead_index(self, record: ECGRecord, lead_name: str | None) -> int:
        if lead_name is None:
            return primary_channel(record)
        if lead_name not in record.leads:
            raise ValueError(f"Lead {lead_name} is unavailable; record leads are {record.leads}")
        return record.leads.index(lead_name)

    def window(self, record_id: str, start_sec: float, duration_sec: float, lead_name: str | None = None,
               max_points: int = MAX_POINTS) -> dict:
        context = self.signal_context(record_id)
        record = context.record
        if not np.isfinite([start_sec, duration_sec]).all():
            raise ValueError("Time values must be finite")
        if duration_sec <= 0 or duration_sec > MAX_WINDOW_SECONDS:
            raise ValueError(f"duration_sec must be between 0 and {MAX_WINDOW_SECONDS:g} seconds")
        if start_sec < 0 or start_sec + duration_sec > record.duration + 1e-9:
            raise ValueError(f"Requested time window exceeds record duration ({record.duration:.3f} seconds)")
        if not 2 <= max_points <= MAX_POINTS:
            raise ValueError(f"max_points must be in [2, {MAX_POINTS}]")
        channel = self._lead_index(record, lead_name)
        unit = record.units[channel]
        if unit != "mV":
            raise ValueError(f"Cannot label physical unit {unit!r} as mV")
        start_sample = int(round(start_sec * record.fs))
        stop_sample = min(int(round((start_sec + duration_sec) * record.fs)), len(record.signal))
        indices = np.arange(start_sample, stop_sample, dtype=np.int64)
        values = record.signal[indices, channel]
        if len(indices) > max_points:
            stride = int(np.ceil(len(indices) / max_points))
            keep = np.unique(np.r_[np.arange(0, len(indices), stride), len(indices) - 1])
            indices, values = indices[keep], values[keep]
        points = [{"sample_index": int(sample), "time_seconds": float(sample / record.fs),
                   "amplitude_mv": float(value)} for sample, value in zip(indices, values)]
        return {"record_id": record_id, "lead_name": record.leads[channel], "sampling_frequency": record.fs,
                "unit": "mV", "start_seconds": float(start_sec), "end_seconds": float(stop_sample / record.fs),
                "start_sample": start_sample, "stop_sample_exclusive": stop_sample,
                "point_count": len(points), "points": points, "downsampled": len(indices) < stop_sample - start_sample}

    def annotations(self, record_id: str, start_sec: float, duration_sec: float,
                    task: str | None = None) -> list[dict]:
        context = self.signal_context(record_id)
        record = context.record
        if start_sec < 0 or duration_sec <= 0 or duration_sec > MAX_WINDOW_SECONDS or start_sec + duration_sec > record.duration + 1e-9:
            raise ValueError("Annotation time range is invalid or exceeds the 30-second query limit")
        start_sample = int(round(start_sec * record.fs))
        stop_sample = min(int(round((start_sec + duration_sec) * record.fs)), len(record.signal))
        part = record.annotations[(record.annotations["sample"] >= start_sample) &
                                  (record.annotations["sample"] < stop_sample)]
        labels = TASKS[task]["labels"] if task else None
        output = []
        for row in part.itertuples(index=False):
            mapped = str(row.aami_group) if row.aami_group else None
            output.append({"record_id": record_id, "annotation_sample": int(row.sample),
                           "time_seconds": float(row.time_s), "original_label": str(row.symbol),
                           "annotation_kind": str(row.annotation_kind), "aami_label": mapped,
                           "within_task": bool(mapped in labels) if labels else None,
                           "lead_name": context.lead_name})
        return output

    def beat(self, record_id: str, sample: int, task: str, require_model_eligibility: bool = True,
             lead_name: str | None = None) -> dict:
        context = self.signal_context(record_id)
        record = context.record
        if sample < 0 or sample >= len(record.signal):
            raise ValueError(f"annotation_sample must be within [0, {len(record.signal) - 1}]")
        matches = record.annotations[record.annotations["sample"].eq(sample)]
        if matches.empty:
            raise ValueError("annotation_sample does not match an expert annotation in this record")
        row = matches.iloc[0]
        if row.annotation_kind != "mapped_beat" or not row.aami_group:
            raise ValueError(f"Annotation {row.symbol!r} is not a mapped beat; non-beat/unknown labels are never inferred")
        labels = TASKS[task]["labels"]
        if row.aami_group not in labels:
            raise ValueError(f"该专家标注 {row.aami_group} 超出当前任务 {task} 的标签范围")
        manifest = self._manifest.get(record_id)
        if require_model_eligibility and not manifest:
            raise ValueError("此记录不属于当前 44 条模型训练数据，只能浏览波形")
        channel = self._lead_index(record, lead_name)
        selected_lead = record.leads[channel]
        if require_model_eligibility and selected_lead != "MLII":
            raise ValueError(f"模型只接受 MLII，当前导联为 {selected_lead}")
        if record.units[channel] != "mV":
            raise ValueError(f"Cannot label physical unit {record.units[channel]!r} as mV")
        pre = int(round(PRE_SECONDS * record.fs)); post = int(round(POST_SECONDS * record.fs))
        start, stop = sample - pre, sample + post + 1
        if start < 0 or stop > len(record.signal):
            raise ValueError("Heartbeat window crosses the record boundary")
        raw = record.signal[start:stop, channel]
        if channel == context.channel:
            filtered_all, safe_all = context.filtered, context.safe
        else:
            filtered_all, safe_all = filter_continuous(record.signal[:, channel], record.fs, context.filter_config)
        filtered = filtered_all[start:stop]
        if not np.isfinite(raw).all() or not np.isfinite(filtered).all() or not safe_all[start:stop].all():
            if not np.isfinite(raw).all() or not np.isfinite(filtered).all():
                raise ValueError("Heartbeat window overlaps a nonfinite signal gap")
        safe_window = bool(safe_all[start:stop].all())
        if require_model_eligibility and not safe_window:
            raise ValueError("Heartbeat window overlaps the 5-second training filter guard")
        if np.std(raw) <= 1e-8 or np.std(filtered) <= 1e-8:
            raise ValueError("Heartbeat window is flat and was excluded by the training data rules")
        target = record.annotations[(record.annotations["annotation_kind"] == "mapped_beat") &
                                    (record.annotations["aami_group"].isin(labels))]
        duplicate_target = bool(target["sample"].duplicated(keep=False).any() and
                                 sample in set(target.loc[target["sample"].duplicated(keep=False), "sample"]))
        if require_model_eligibility and duplicate_target:
            raise ValueError("Duplicate target beat position is excluded by the training data rules")
        inference_reason = None
        if not manifest:
            inference_reason = "此记录不属于当前 44 条模型训练数据，只能浏览波形"
        elif selected_lead != "MLII":
            inference_reason = f"模型只接受 MLII，当前导联为 {selected_lead}"
        elif not safe_window:
            inference_reason = "心拍窗口位于 5 秒双向滤波保护区内"
        elif duplicate_target:
            inference_reason = "重复标注样本位置按训练数据规则排除"
        relative = (np.arange(start, stop, dtype=np.int64) - sample) / record.fs
        return {"record_id": record_id, "subject_id": manifest["subject_id"] if manifest else f"subject_{record_id}",
                "dataset_split": manifest["split"] if manifest else "excluded_from_model_dataset",
                "annotation_sample": int(sample), "time_seconds": float(sample / record.fs),
                "lead_name": selected_lead, "sampling_frequency": record.fs, "unit": "mV",
                "original_label": str(row.symbol), "aami_label": str(row.aami_group),
                "task": task, "within_task": True, "window_start_sample": start,
                "window_stop_sample_exclusive": stop, "window_time_relative_seconds": relative.tolist(),
                "raw_amplitude_mv": raw.astype(float).tolist(), "filtered_amplitude_mv": filtered.astype(float).tolist(),
                "inference_eligible": inference_reason is None, "inference_unavailable_reason": inference_reason,
                "normalized_model_input": None}

    def normalized_input(self, task: str, beat: dict) -> np.ndarray:
        filtered = np.asarray(beat["filtered_amplitude_mv"], dtype=np.float32)[None, None, :]
        x = transform(filtered, self._normalizers[task])[0, 0]
        return np.asarray(x, dtype=np.float32)


class InferenceService:
    def __init__(self, root: Path):
        self.root = root.resolve()
        self.store = ECGStore(self.root)
        self.models = ModelRegistry(self.root)

    def predict_beat(self, record_id: str, sample: int, task: str, model_id: str) -> dict:
        beat = self.store.beat(record_id, sample, task)
        # The reference label is not included in model input; only the filtered ECG window is transformed.
        normalized = self.store.normalized_input(task, beat)
        predicted, probabilities, latency, bundle = self.models.predict(task, model_id, normalized)
        return {"task": task, "model_id": model_id, "record_id": record_id,
                "annotation_sample": int(sample), "predicted_class": predicted,
                "class_probabilities": probabilities, "expert_label": beat["aami_label"],
                "prediction_matches_expert": bool(predicted == beat["aami_label"]),
                "inference_time_ms": float(latency), "model_version": bundle.model_version,
                "model_sha256": bundle.model_sha256, "preprocessing_version": "mitdb44_v1_filter_0.5-40_window_-0.3_+0.4_zscore_train",
                "prediction_source": "saved project model checkpoint", "lead_name": beat["lead_name"],
                "dataset_split": beat["dataset_split"], "probability_note": "模型输出概率，未经临床校准"}

    def compare(self, record_id: str, sample: int, task: str) -> dict:
        beat = self.store.beat(record_id, sample, task)
        normalized = self.store.normalized_input(task, beat)
        outputs = [self.predict_prepared(task, model_id, record_id, sample, beat, normalized)
                   for model_id in MODEL_IDS]
        classes = [item["predicted_class"] for item in outputs]
        return {"task": task, "record_id": record_id, "annotation_sample": int(sample),
                "expert_label": beat["aami_label"], "models": outputs,
                "all_models_agree": len(set(classes)) == 1,
                "agreement_statement": "三个模型对当前心拍预测一致。" if len(set(classes)) == 1 else "模型预测存在差异，见各模型结果与类别输出概率。",
                "probability_note": "模型输出概率，未经临床校准"}

    def predict_prepared(self, task: str, model_id: str, record_id: str, sample: int,
                         beat: dict, normalized: np.ndarray) -> dict:
        predicted, probabilities, latency, bundle = self.models.predict(task, model_id, normalized)
        return {"task": task, "model_id": model_id, "record_id": record_id,
                "annotation_sample": int(sample), "predicted_class": predicted,
                "class_probabilities": probabilities, "expert_label": beat["aami_label"],
                "prediction_matches_expert": bool(predicted == beat["aami_label"]),
                "inference_time_ms": float(latency), "model_version": bundle.model_version,
                "model_sha256": bundle.model_sha256, "preprocessing_version": "mitdb44_v1_filter_0.5-40_window_-0.3_+0.4_zscore_train",
                "prediction_source": "saved project model checkpoint", "lead_name": beat["lead_name"],
                "dataset_split": beat["dataset_split"], "probability_note": "模型输出概率，未经临床校准"}

    def batch(self, record_id: str, samples: list[int], task: str, model_ids: list[str]) -> list[dict]:
        if len(samples) > 128 or len(model_ids) > 3:
            raise ValueError("Batch limit is 128 annotations and three models")
        if len(set(samples)) != len(samples) or len(set(model_ids)) != len(model_ids):
            raise ValueError("annotation_samples and model_ids must be unique")
        outputs = []
        for sample in samples:
            beat = self.store.beat(record_id, sample, task)
            normalized = self.store.normalized_input(task, beat)
            for model_id in model_ids:
                outputs.append(self.predict_prepared(task, model_id, record_id, sample, beat, normalized))
        return outputs

