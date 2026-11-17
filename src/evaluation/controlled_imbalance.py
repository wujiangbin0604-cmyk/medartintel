"""Precommitted train/validation experiments and a separate, locked test phase.

Existing production models, data splits and formal results are never overwritten.
The historical test set is explicitly exploratory: it has already been inspected.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import time

import numpy as np
import pandas as pd
import torch
from torch import nn
from torch.nn import functional as F
from torch.utils.data import DataLoader, TensorDataset
import wfdb
from sklearn.preprocessing import StandardScaler

from ..labels import BEAT_ZH
from ..models.classifiers import HeartbeatCNN
from ..training.trainer import load_npz, seed_everything
from .metrics import score_predictions, make_prediction_frame

ROOT = Path(__file__).resolve().parents[2]
CONFIG = ROOT / "configs/controlled_imbalance_20261116.json"
OUT = ROOT / "results/controlled_imbalance_20261116"


def sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    temp.replace(path)


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


class ContextHeartbeatCNN(nn.Module):
    """Original morphology encoder plus a small timing-feature branch."""
    def __init__(self, classes: int = 4):
        super().__init__()
        self.features = HeartbeatCNN(classes).features
        self.timing = nn.Sequential(nn.Linear(4, 16), nn.ReLU())
        self.classifier = nn.Linear(80, classes)

    def forward(self, wave: torch.Tensor, context: torch.Tensor) -> torch.Tensor:
        return self.classifier(torch.cat([self.features(wave).squeeze(-1), self.timing(context)], dim=1))


def past_rr_features(positions: np.ndarray, targets: np.ndarray, fs: float) -> np.ndarray:
    """Use annotated beat timing at or before each target; never future timing."""
    positions = np.asarray(positions, dtype=np.int64)
    if len(positions) < 2 or fs <= 0 or np.any(np.diff(positions) <= 0):
        raise ValueError("RR positions must be distinct, increasing annotated beats")
    indices = np.searchsorted(positions, targets)
    if np.any(indices >= len(positions)) or not np.array_equal(positions[indices], targets):
        raise ValueError("Every target must match an expert beat position")
    intervals = np.diff(positions).astype(np.float64) / fs
    values = []
    for index in indices:
        previous = intervals[index - 1] if index else .8
        prior = intervals[index - 2] if index > 1 else previous
        local = float(intervals[max(0, index - 10):index].mean()) if index else .8
        values.append([previous, local, previous / max(local, 1e-6), previous / max(prior, 1e-6)])
    result = np.asarray(values, dtype=np.float32)
    if not np.isfinite(result).all():
        raise ValueError("Non-finite RR features")
    return result


def make_context(data: dict) -> tuple[np.ndarray, dict]:
    result = np.empty((len(data["y"]), 4), dtype=np.float32)
    records = data["record_id"].astype(str)
    source_hashes = {}
    for record in np.unique(records):
        stem = ROOT / "data/mitdb" / record
        ann = wfdb.rdann(str(stem), "atr")
        fs = float(wfdb.rdheader(str(stem)).fs)
        beat_positions = np.asarray([s for s, label in zip(ann.sample, ann.symbol) if label in BEAT_ZH])
        use = records == record
        result[use] = past_rr_features(beat_positions, data["annotation_sample"][use], fs)
        source_hashes[record] = {ext: sha(stem.with_suffix("." + ext)) for ext in ("hea", "atr")}
    return result, source_hashes


def focal_loss(logits: torch.Tensor, labels: torch.Tensor, alpha: torch.Tensor, gamma: float = 2.) -> torch.Tensor:
    logp = F.log_softmax(logits, dim=1).gather(1, labels[:, None]).squeeze(1)
    return (-alpha[labels] * (1 - logp.exp()).pow(gamma) * logp).sum() / alpha[labels].sum()


def build_model(variant: dict) -> nn.Module:
    return ContextHeartbeatCNN() if variant["context"] else HeartbeatCNN(4)


def logits_for(model: nn.Module, x: torch.Tensor, rr: torch.Tensor) -> torch.Tensor:
    return model(x, rr) if isinstance(model, ContextHeartbeatCNN) else model(x)


def predict(model: nn.Module, x: np.ndarray, rr: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    model.eval()
    chunks = []
    with torch.inference_mode():
        for i in range(0, len(x), 512):
            out = logits_for(model, torch.from_numpy(x[i:i + 512]), torch.from_numpy(rr[i:i + 512]))
            chunks.append(out.softmax(1).numpy())
    probability = np.concatenate(chunks)
    return probability.argmax(1), probability


def metrics(y: np.ndarray, pred: np.ndarray, names: list[str]) -> dict:
    result = score_predictions(y, pred, names)
    result["balanced_accuracy"] = result["macro_recall"]
    result["balanced_accuracy_definition"] = "Mean recall over the four predefined classes (all supported here)."
    return result


def protocol(config: dict) -> dict:
    data = ROOT / config["dataset"]
    files = [CONFIG, Path(__file__), ROOT / "src/models/classifiers.py", ROOT / "src/training/trainer.py",
             ROOT / "src/labels.py", data / "split_manifest.csv", data / "processing_config.json",
             data / "normalization.json", data / "train.npz", data / "val.npz", data / "test.npz"]
    return {"config": config, "environment": {"python": platform.python_version(), "torch": torch.__version__,
            "numpy": np.__version__, "device": "cpu"},
            "sources": {str(p.relative_to(ROOT)).replace('\\', '/'): sha(p) for p in files},
            "test_labels_used_for_selection": False}


def assert_protocol() -> tuple[dict, dict]:
    config = read_json(CONFIG)
    stored = read_json(OUT / "protocol.json")
    if protocol(config) != stored:
        raise RuntimeError("The precommitted source/config/data hashes changed; create a separate experiment instead")
    return config, stored


def train_one(config: dict, variant: dict, seed: int, arrays: dict, rr: dict) -> None:
    folder = OUT / "runs" / variant["id"] / str(seed)
    if (folder / "summary.json").is_file():
        print(f"Already completed: {variant['id']} seed={seed}", flush=True)
        return
    folder.mkdir(parents=True, exist_ok=True)
    seed_everything(seed)
    model = build_model(variant)
    y = arrays["train"]["y"]
    counts = np.bincount(y, minlength=4)
    inverse = len(y) / (4 * counts)
    alpha = np.sqrt(inverse); alpha /= alpha.mean()
    weights = torch.tensor(inverse ** variant.get("weight_power", 1.), dtype=torch.float32)
    focal_alpha = torch.tensor(alpha, dtype=torch.float32)
    optimizer = torch.optim.Adam(model.parameters(), lr=config["learning_rate"], weight_decay=config["weight_decay"])
    dataset = TensorDataset(torch.from_numpy(arrays["train"]["X"]), torch.from_numpy(rr["train"]), torch.from_numpy(y))
    loader = DataLoader(dataset, batch_size=config["batch_size"], shuffle=True,
                        generator=torch.Generator().manual_seed(seed), num_workers=0)
    history = []; best = -1.; stale = 0; started = time.perf_counter()
    write_json(folder / "config.json", {**config, "variant": variant, "seed": seed,
                                       "training_counts": counts.tolist(), "ce_weights": weights.tolist(),
                                       "focal_alpha": alpha.tolist(), "test_loaded": False})
    for epoch in range(1, config["epochs"] + 1):
        model.train(); losses = 0.; seen = 0
        for bx, br, by in loader:
            optimizer.zero_grad(set_to_none=True)
            out = logits_for(model, bx, br)
            loss = F.cross_entropy(out, by, weight=weights) if variant["loss"] == "weighted_ce" else focal_loss(out, by, focal_alpha, variant["gamma"])
            loss.backward(); optimizer.step()
            losses += float(loss.detach()) * len(by); seen += len(by)
        pred, _ = predict(model, arrays["val"]["X"], rr["val"])
        score = metrics(arrays["val"]["y"], pred, config["class_names"])
        history.append({"epoch": epoch, "mean_batch_loss_weighted_by_batch_size": losses / seen,
                        "val_macro_f1": score["macro_f1"], "val_balanced_accuracy": score["balanced_accuracy"]})
        if score["macro_f1"] > best + 1e-8:
            best = score["macro_f1"]; stale = 0
            torch.save({"state_dict": model.state_dict(), "best_epoch": epoch, "seed": seed,
                        "variant": variant, "class_names": config["class_names"],
                        "protocol_sha256": sha(OUT / "protocol.json")}, folder / "best.pt")
        else:
            stale += 1
        print(f"{variant['id']} seed={seed} epoch={epoch} valMacroF1={score['macro_f1']:.5f} best={best:.5f}", flush=True)
        if stale >= config["patience"]:
            break
    checkpoint = torch.load(folder / "best.pt", weights_only=True, map_location="cpu")
    model.load_state_dict(checkpoint["state_dict"])
    pred, prob = predict(model, arrays["val"]["X"], rr["val"])
    make_prediction_frame(arrays["val"], arrays["val"]["y"], pred, prob, config["class_names"], variant["id"], "val").to_csv(folder / "val_predictions.csv", index=False)
    write_json(folder / "val_metrics.json", metrics(arrays["val"]["y"], pred, config["class_names"]))
    pd.DataFrame(history).to_csv(folder / "training_history.csv", index=False)
    write_json(folder / "summary.json", {"variant": variant["id"], "seed": seed,
               "best_epoch": checkpoint["best_epoch"], "val_macro_f1": best,
               "epochs_ran": len(history), "fit_seconds": time.perf_counter() - started,
               "checkpoint_sha256": sha(folder / "best.pt"), "test_loaded": False,
               "parameters": sum(p.numel() for p in model.parameters()), "device": "cpu"})


def train() -> None:
    config = read_json(CONFIG)
    audit = read_json(ROOT / "results/stability_audit_20261116/audit.json")
    if not audit.get("passed_integrity_checks") or audit.get("blocking_issues"):
        raise RuntimeError("Stability/data-integrity audit has not cleared training")
    if (OUT / "test_evaluation.json").exists():
        raise RuntimeError("Test phase has started; training/configuration changes are closed")
    OUT.mkdir(parents=True, exist_ok=True)
    expected = protocol(config)
    if (OUT / "protocol.json").exists() and read_json(OUT / "protocol.json") != expected:
        raise RuntimeError("Precommitted experiment changed")
    write_json(OUT / "protocol.json", expected)
    arrays = {s: load_npz(ROOT / config["dataset"] / f"{s}.npz") for s in ("train", "val")}
    raw_rr = {}; sources = {}
    for split, data in arrays.items():
        raw_rr[split], sources[split] = make_context(data)
    scaler = StandardScaler().fit(raw_rr["train"])
    rr = {s: scaler.transform(v).astype(np.float32) for s, v in raw_rr.items()}
    write_json(OUT / "rr_normalization.json", {"mean": scaler.mean_.tolist(), "scale": scaler.scale_.tolist(),
               "fit_split": "train", "fit_count": len(raw_rr["train"]), "sources": sources})
    for variant in config["variants"]:
        for seed in config["seeds"]:
            train_one(config, variant, seed, arrays, rr)
    ranking = []
    for variant in config["variants"]:
        scores = [read_json(OUT / "runs" / variant["id"] / str(seed) / "val_metrics.json")["macro_f1"] for seed in config["seeds"]]
        ranking.append({"variant": variant["id"], "mean_val_macro_f1": float(np.mean(scores)),
                        "sample_sd": float(np.std(scores, ddof=1)), "seeds": config["seeds"]})
    selected = max(ranking, key=lambda r: r["mean_val_macro_f1"])["variant"]
    checkpoints = {f"{v['id']}/{s}": sha(OUT / "runs" / v["id"] / str(s) / "best.pt") for v in config["variants"] for s in config["seeds"]}
    write_json(OUT / "selection_locked.json", {"selected_variant": selected, "ranking": ranking,
               "checkpoint_hashes": checkpoints, "protocol_sha256": sha(OUT / "protocol.json"),
               "test_loaded": False, "selection_rule": config["selection"],
               "old_test_previously_viewed": True})
    print(f"Validation selection locked: {selected}; test not loaded by training stage", flush=True)


def final() -> None:
    config, _ = assert_protocol()
    lock = read_json(OUT / "selection_locked.json")
    if (OUT / "test_evaluation.json").exists():
        raise RuntimeError("Final test phase already executed/started; read its artifacts, do not rerun")
    for key, digest in lock["checkpoint_hashes"].items():
        if sha(OUT / "runs" / key / "best.pt") != digest:
            raise RuntimeError("Checkpoint changed after validation selection")
    write_json(OUT / "test_evaluation.json", {"status": "started", "selection_sha256": sha(OUT / "selection_locked.json"),
               "old_test_previously_viewed": True, "policy": config["test_policy"]})
    data = load_npz(ROOT / config["dataset"] / "test.npz")
    raw_rr, sources = make_context(data)
    normalizer = read_json(OUT / "rr_normalization.json")
    rr = ((raw_rr - np.array(normalizer["mean"])) / np.array(normalizer["scale"])).astype(np.float32)
    records = []
    for variant in config["variants"]:
        for seed in config["seeds"]:
            folder = OUT / "runs" / variant["id"] / str(seed)
            checkpoint = torch.load(folder / "best.pt", weights_only=True, map_location="cpu")
            model = build_model(variant); model.load_state_dict(checkpoint["state_dict"])
            pred, prob = predict(model, data["X"], rr)
            result = metrics(data["y"], pred, config["class_names"])
            write_json(folder / "test_metrics.json", result)
            make_prediction_frame(data, data["y"], pred, prob, config["class_names"], variant["id"], "test").to_csv(folder / "test_predictions.csv", index=False)
            records.append({"variant": variant["id"], "seed": seed, "macro_f1": result["macro_f1"],
                            "balanced_accuracy": result["balanced_accuracy"], "accuracy": result["accuracy"],
                            **{f"{c}_{m}": result["per_class"][c][m] for c in config["class_names"] for m in ("precision", "recall", "f1")}})
    pd.DataFrame(records).to_csv(OUT / "test_comparison.csv", index=False)
    write_json(OUT / "test_evaluation.json", {"status": "completed", "selection_sha256": sha(OUT / "selection_locked.json"),
               "runs": len(records), "selected_before_test": lock["selected_variant"],
               "test_annotation_sources": sources, "old_test_previously_viewed": True, "policy": config["test_policy"]})
    print(pd.DataFrame(records).to_string(index=False), flush=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage", choices=["train", "final"], required=True)
    args = parser.parse_args()
    config = read_json(CONFIG)
    torch.set_num_threads(config["cpu_threads"])
    try:
        torch.set_num_interop_threads(2)
    except RuntimeError:
        pass
    train() if args.stage == "train" else final()


if __name__ == "__main__":
    main()
