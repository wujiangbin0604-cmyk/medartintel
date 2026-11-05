from __future__ import annotations

import hashlib
import json
import logging
import threading
from dataclasses import dataclass
from pathlib import Path
from time import perf_counter

import joblib
import numpy as np
import torch

from src.models.classifiers import HeartbeatCNN

LOGGER = logging.getLogger("ecg_ai.models")
TASKS = {
    "nv": {
        "labels": ["N", "V"],
        "dataset": "data/processed/mitdb44_nv_v1",
        "checkpoint": "checkpoints/nv44_v1/formal",
        "results": "results/classification/nv44_v1",
    },
    "nsvf": {
        "labels": ["N", "S", "V", "F"],
        "dataset": "data/processed/mitdb44_nsvf_v1",
        "checkpoint": "checkpoints/nsvf44_v1/formal",
        "results": "results/classification/nsvf44_v1",
    },
}
MODEL_IDS = ("logistic_regression", "random_forest", "cnn_1d")


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


@dataclass
class ModelBundle:
    task: str
    model_id: str
    labels: list[str]
    model: object
    scaler: object | None
    model_version: str
    model_sha256: str
    checkpoint_path: str
    loaded: bool = True
    error: str | None = None


class ModelRegistry:
    """Load each saved experiment artifact once and preserve its training pipeline."""

    def __init__(self, root: Path):
        self.root = root.resolve()
        self._bundles: dict[tuple[str, str], ModelBundle] = {}
        self._status: dict[tuple[str, str], dict] = {}
        self._lock = threading.RLock()
        self.device = torch.device("cpu")

    def load_all(self) -> dict:
        with self._lock:
            for task, spec in TASKS.items():
                for model_id in MODEL_IDS:
                    key = (task, model_id)
                    if key in self._status:
                        continue
                    try:
                        self._bundles[key] = self._load_one(task, model_id, spec)
                        self._status[key] = self._describe(self._bundles[key])
                    except Exception as exc:  # Keep data browsing available and expose the exact failing model.
                        message = f"{type(exc).__name__}: {exc}"
                        LOGGER.exception("Unable to load model task=%s model=%s", task, model_id)
                        self._status[key] = {"task": task, "model_id": model_id, "loaded": False,
                                             "error": message, "labels": spec["labels"]}
            return self.status()

    def _load_one(self, task: str, model_id: str, spec: dict) -> ModelBundle:
        checkpoint_root = self.root / spec["checkpoint"]
        if model_id == "cnn_1d":
            path = checkpoint_root / "cnn" / "cnn_final_best.pt"
            if not path.is_file():
                raise FileNotFoundError(path)
            checkpoint = torch.load(path, map_location="cpu", weights_only=True)
            labels = list(spec["labels"])
            if checkpoint.get("class_names") != labels:
                raise ValueError(f"Checkpoint class order {checkpoint.get('class_names')} != {labels}")
            model = HeartbeatCNN(num_classes=len(labels))
            model.load_state_dict(checkpoint["state_dict"], strict=True)
            model.eval()
            return ModelBundle(task, model_id, labels, model, None, f"epoch-{checkpoint['best_epoch']}",
                               file_sha256(path), path.relative_to(self.root).as_posix())

        path = checkpoint_root / f"{model_id}.joblib"
        if not path.is_file():
            raise FileNotFoundError(path)
        payload = joblib.load(path)
        estimator = payload["estimator"]
        labels = list(spec["labels"])
        expected = list(range(len(labels)))
        actual = np.asarray(estimator.classes_, dtype=int).tolist()
        if actual != expected or int(estimator.n_features_in_) != 253:
            raise ValueError(f"Saved estimator classes/features invalid: classes={actual}, features={estimator.n_features_in_}")
        scaler = payload.get("scaler")
        if model_id == "logistic_regression" and scaler is None:
            raise ValueError("Logistic Regression StandardScaler is missing")
        if model_id == "random_forest" and scaler is not None:
            raise ValueError("Training Random Forest did not use a feature scaler")
        return ModelBundle(task, model_id, labels, estimator, scaler, "formal", file_sha256(path),
                           path.relative_to(self.root).as_posix())

    @staticmethod
    def _describe(bundle: ModelBundle) -> dict:
        return {"task": bundle.task, "model_id": bundle.model_id, "loaded": bundle.loaded,
                "labels": bundle.labels, "model_version": bundle.model_version,
                "model_sha256": bundle.model_sha256, "checkpoint_path": bundle.checkpoint_path,
                "input_length": 253, "device": "cpu", "probability_source": "model output; not clinically calibrated"}

    def status(self) -> dict:
        with self._lock:
            models = [self._status[key] for key in sorted(self._status)]
        return {"device": "cpu", "models": models,
                "all_loaded": bool(models) and all(item.get("loaded") for item in models)}

    def task_status(self, task: str) -> list[dict]:
        self.load_all()
        return [self._status[(task, model_id)] for model_id in MODEL_IDS]

    def predict(self, task: str, model_id: str, normalized_window: np.ndarray) -> tuple[str, dict[str, float], float, ModelBundle]:
        self.load_all()
        key = (task, model_id)
        status = self._status.get(key)
        if not status or not status.get("loaded"):
            raise RuntimeError(status.get("error", "Requested model is unavailable") if status else "Unknown model")
        bundle = self._bundles[key]
        x = np.asarray(normalized_window, dtype=np.float32).reshape(1, 253)
        started = perf_counter()
        if model_id == "cnn_1d":
            tensor = torch.from_numpy(x[:, None, :])
            with torch.inference_mode():
                logits = bundle.model(tensor).cpu().numpy()[0].astype(np.float64)
            logits -= logits.max()
            probability = np.exp(logits)
            probability /= probability.sum()
        else:
            features = bundle.scaler.transform(x) if bundle.scaler is not None else x
            probability = np.asarray(bundle.model.predict_proba(features)[0], dtype=np.float64)
        elapsed_ms = (perf_counter() - started) * 1000.0
        if probability.shape != (len(bundle.labels),) or not np.isfinite(probability).all():
            raise RuntimeError("Model produced invalid probability output")
        if np.any(probability < 0) or np.any(probability > 1) or not np.isclose(probability.sum(), 1, atol=1e-5):
            raise RuntimeError("Model probability output is outside the valid range")
        return bundle.labels[int(np.argmax(probability))], dict(zip(bundle.labels, map(float, probability))), elapsed_ms, bundle

