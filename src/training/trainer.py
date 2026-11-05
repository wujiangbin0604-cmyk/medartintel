"""Training routines with validation-only early stopping and reproducible logs."""
from __future__ import annotations

import json
import os
import random
import time
from pathlib import Path

import numpy as np
import pandas as pd
import torch
from sklearn.metrics import f1_score
from sklearn.model_selection import train_test_split
from torch.utils.data import DataLoader, TensorDataset

from ..models.classifiers import HeartbeatCNN, make_logistic_regression, make_random_forest


def seed_everything(seed: int) -> None:
    os.environ["PYTHONHASHSEED"] = str(seed)
    os.environ["CUBLAS_WORKSPACE_CONFIG"] = ":4096:8"
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)
    torch.backends.cudnn.benchmark = False
    torch.backends.cudnn.deterministic = True
    torch.use_deterministic_algorithms(True, warn_only=True)


def load_npz(path: Path) -> dict:
    with np.load(path, allow_pickle=False) as values:
        return {key: values[key].copy() for key in values.files}


def class_weights_from_training(y: np.ndarray, class_count: int) -> np.ndarray:
    counts = np.bincount(np.asarray(y, dtype=np.int64), minlength=class_count)
    if (counts == 0).any():
        raise ValueError(f"Training split misses a required class: {counts.tolist()}")
    weights = len(y) / (class_count * counts.astype(np.float64))
    return weights.astype(np.float32)


def stratified_smoke_subset(x: np.ndarray, y: np.ndarray, max_items: int, seed: int) -> tuple[np.ndarray, np.ndarray]:
    if len(y) <= max_items:
        return np.arange(len(y)), np.arange(len(y))
    indices = np.arange(len(y))
    selected, _ = train_test_split(indices, train_size=max_items, stratify=y,
                                   random_state=seed, shuffle=True)
    return np.sort(selected), np.arange(len(y))


def fit_sklearn_baselines(x_train: np.ndarray, y_train: np.ndarray, seed: int,
                          output_dir: Path, smoke: bool = False,
                          model_config: dict | None = None) -> dict:
    from joblib import dump
    from sklearn.preprocessing import StandardScaler
    # Each heartbeat is a fixed vector. The scalar signal normalization was already
    # fitted using training beats only; feature scaling is also train-fitted here.
    output_dir.mkdir(parents=True, exist_ok=True)
    results = {}
    settings = model_config or {}
    for name, estimator in (("logistic_regression", make_logistic_regression(seed, smoke, settings.get("logistic_regression"))),
                            ("random_forest", make_random_forest(seed, smoke, settings.get("random_forest")))):
        start = time.perf_counter()
        if name == "logistic_regression":
            scaler = StandardScaler()
            scaled_train = scaler.fit_transform(x_train)
            estimator.fit(scaled_train, y_train)
            dump({"estimator": estimator, "scaler": scaler}, output_dir / f"{name}.joblib", compress=3)
        else:
            estimator.fit(x_train, y_train)
            dump({"estimator": estimator, "scaler": None}, output_dir / f"{name}.joblib", compress=3)
        elapsed = time.perf_counter() - start
        results[name] = {"estimator": estimator, "scaler": scaler if name == "logistic_regression" else None,
                         "fit_seconds": elapsed, "status": "completed"}
    return results


def sklearn_predict(model_info: dict, x: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    values = x
    if model_info.get("scaler") is not None:
        values = model_info["scaler"].transform(values)
    estimator = model_info["estimator"]
    probability = estimator.predict_proba(values)
    ordered = np.zeros((len(values), int(estimator.classes_.max()) + 1), dtype=np.float64)
    ordered[:, estimator.classes_.astype(int)] = probability
    return ordered.argmax(axis=1).astype(np.int64), ordered


def _f1_macro(logits: np.ndarray, y_true: np.ndarray, class_count: int) -> float:
    pred = logits.argmax(axis=1)
    return float(f1_score(y_true, pred, labels=list(range(class_count)), average="macro", zero_division=0))


def train_cnn(x_train: np.ndarray, y_train: np.ndarray, x_val: np.ndarray, y_val: np.ndarray,
              class_count: int, weights: np.ndarray, seed: int, output_dir: Path,
              epochs: int = 25, patience: int = 5, batch_size: int = 256,
              smoke: bool = False) -> tuple[HeartbeatCNN, pd.DataFrame, dict]:
    seed_everything(seed)
    output_dir.mkdir(parents=True, exist_ok=True)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model = HeartbeatCNN(class_count).to(device)
    optimizer = torch.optim.Adam(model.parameters(), lr=1e-3, weight_decay=1e-5)
    criterion = torch.nn.CrossEntropyLoss(weight=torch.as_tensor(weights, dtype=torch.float32, device=device))
    train_dataset = TensorDataset(torch.as_tensor(x_train[:, None, :], dtype=torch.float32),
                                  torch.as_tensor(y_train, dtype=torch.long))
    val_dataset = TensorDataset(torch.as_tensor(x_val[:, None, :], dtype=torch.float32),
                                torch.as_tensor(y_val, dtype=torch.long))
    generator = torch.Generator().manual_seed(seed)
    train_loader = DataLoader(train_dataset, batch_size=batch_size, shuffle=True, num_workers=0,
                              generator=generator, drop_last=False)
    val_loader = DataLoader(val_dataset, batch_size=512, shuffle=False, num_workers=0)
    history = []
    best_f1 = -1.0
    best_epoch = 0
    stale_epochs = 0
    best_path = output_dir / "cnn_best.pt"
    started = time.perf_counter()
    for epoch in range(1, epochs + 1):
        model.train(); train_loss_sum = 0.0; seen = 0
        for batch_x, batch_y in train_loader:
            batch_x, batch_y = batch_x.to(device), batch_y.to(device)
            optimizer.zero_grad(set_to_none=True)
            logits = model(batch_x)
            loss = criterion(logits, batch_y)
            loss.backward()
            optimizer.step()
            train_loss_sum += float(loss.detach()) * len(batch_y); seen += len(batch_y)
        train_loss = train_loss_sum / max(seen, 1)
        model.eval(); val_loss_sum = 0.0; val_logits = []; val_truth = []
        with torch.no_grad():
            for batch_x, batch_y in val_loader:
                batch_x, batch_y = batch_x.to(device), batch_y.to(device)
                logits = model(batch_x)
                val_loss_sum += float(criterion(logits, batch_y)) * len(batch_y)
                val_logits.append(logits.cpu().numpy()); val_truth.append(batch_y.cpu().numpy())
        logits = np.concatenate(val_logits); truth = np.concatenate(val_truth)
        val_loss = val_loss_sum / max(len(truth), 1)
        val_macro_f1 = _f1_macro(logits, truth, class_count)
        row = {"epoch": epoch, "train_loss": train_loss, "val_loss": val_loss,
               "val_macro_f1": val_macro_f1, "val_accuracy": float((logits.argmax(1) == truth).mean())}
        history.append(row)
        if val_macro_f1 > best_f1 + 1e-8:
            best_f1 = val_macro_f1; best_epoch = epoch; stale_epochs = 0
            torch.save({"state_dict": model.state_dict(), "epoch": epoch, "val_macro_f1": best_f1,
                        "class_count": class_count, "seed": seed}, best_path)
        else:
            stale_epochs += 1
        print(f"CNN epoch {epoch}/{epochs}: train_loss={train_loss:.5f} val_loss={val_loss:.5f} "
              f"val_macro_f1={val_macro_f1:.5f} best={best_f1:.5f}", flush=True)
        if stale_epochs >= patience:
            break
    checkpoint = torch.load(best_path, map_location=device, weights_only=False)
    model.load_state_dict(checkpoint["state_dict"])
    model.eval()
    history_frame = pd.DataFrame(history)
    history_frame.to_csv(output_dir / "cnn_training_history.csv", index=False, encoding="utf-8-sig")
    summary = {"status": "completed", "device": str(device), "epochs_ran": len(history),
               "best_epoch": best_epoch, "best_val_macro_f1": best_f1,
               "fit_seconds": time.perf_counter() - started, "early_stopping_metric": "validation macro-F1",
               "patience": patience, "batch_size": batch_size, "learning_rate": 1e-3,
               "optimizer": "Adam", "loss": "weighted CrossEntropyLoss", "training_class_weights": weights.tolist()}
    (output_dir / "cnn_training_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return model, history_frame, summary


def predict_cnn(model: HeartbeatCNN, x: np.ndarray, batch_size: int = 512) -> tuple[np.ndarray, np.ndarray]:
    device = next(model.parameters()).device
    loader = DataLoader(TensorDataset(torch.as_tensor(x[:, None, :], dtype=torch.float32)),
                        batch_size=batch_size, shuffle=False, num_workers=0)
    logits_list = []
    model.eval()
    with torch.no_grad():
        for (batch_x,) in loader:
            logits_list.append(model(batch_x.to(device)).cpu().numpy())
    logits = np.concatenate(logits_list)
    logits -= logits.max(axis=1, keepdims=True)
    probability = np.exp(logits); probability /= probability.sum(axis=1, keepdims=True)
    return probability.argmax(axis=1).astype(np.int64), probability
