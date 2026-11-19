"""Nested patient-separated ablations, resume complete jobs with provenance checks."""
import argparse
from datetime import datetime
import hashlib
import json
from pathlib import Path
import platform
import time
import numpy as np
import torch
from sklearn.model_selection import StratifiedGroupKFold
from research_extensions.protect import sha256
from src.training.trainer import seed_everything, class_weights_from_training
from src.evaluation.stability_audit import independent_score
from .data import BASE, ROOT, load, fit_scaler, transform
from .models import make_model, forward


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    tmp.replace(path)


def score(y, p, groups, classes):
    result = independent_score(y, p.argmax(1), classes)
    result["balanced_accuracy"] = float(np.mean([v["recall"] for v in result["per_class"].values() if v["support"]]))
    result["subject_count"] = len(set(groups))
    for i, c in enumerate(classes):
        result["per_class"][c]["subject_count"] = len(set(groups[y == i]))
    return result


def derangement(n, seed):
    if n < 2:
        raise ValueError("Need >=2 rows for shuffle")
    order = np.random.default_rng(seed).permutation(n)
    out = np.empty(n, dtype=int)
    out[order] = np.roll(order, 1)
    assert np.all(out != np.arange(n))
    return out


def partition(data, config):
    y, g = data["label"], data["subject_group"]
    outer = StratifiedGroupKFold(config["outer_folds"], shuffle=True, random_state=config["fold_seed"])
    folds = []
    for fold, (dev, evaluation) in enumerate(outer.split(np.zeros(len(y)), y, g)):
        inner = StratifiedGroupKFold(config["inner_folds"], shuffle=True, random_state=config["fold_seed"] + fold + 1)
        inner_parts = list(inner.split(np.zeros(len(dev)), y[dev], g[dev]))
        stop = dev[inner_parts[config["inner_stop_fold"]][1]]
        calibration = dev[inner_parts[config["inner_calibration_fold"]][1]]
        fit = np.setdiff1d(dev, np.r_[stop, calibration])
        parts = dict(fit=fit, stop=stop, calibration=calibration, evaluation=evaluation)
        sets = [set(g[v]) for v in parts.values()]
        assert all(not a & b for i, a in enumerate(sets) for b in sets[i + 1:])
        assert set(np.unique(y[fit])) == set(np.unique(y))
        folds.append(parts)
    return folds


def predict(model, name, x, r, device, batch=512):
    model.eval()
    with torch.inference_mode():
        return torch.cat([torch.softmax(forward(model, name, torch.from_numpy(x[i:i+batch]).to(device),
                                               torch.from_numpy(r[i:i+batch]).to(device)), dim=1).cpu()
                          for i in range(0, len(x), batch)]).numpy()


def job(data, parts, config, fold, seed, name, output, smoke=False):
    seed_everything(seed)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    classes = ["N", "V"] if config["task"] == "nv" else ["N", "S", "V", "F"]
    scaler = fit_scaler(data["waveform"][parts["fit"]], data["rhythm_features"][parts["fit"]],
                        data["rhythm_valid_mask"][parts["fit"]], data["sample_id"][parts["fit"]])
    inputs = {}
    for j, (key, indices) in enumerate(parts.items()):
        x, r = transform(data["waveform"][indices], data["rhythm_features"][indices], data["rhythm_valid_mask"][indices], scaler)
        if name == "A3":
            r = r[derangement(len(r), config["fold_seed"] + fold * 100 + j)]
        inputs[key] = (x, r, data["label"][indices])
    model = make_model(name, len(classes)).to(device)
    weights = class_weights_from_training(inputs["fit"][2], len(classes)) if config["class_weight"] == "balanced_training_only" else np.ones(len(classes), np.float32)
    criterion = torch.nn.CrossEntropyLoss(weight=torch.tensor(weights, device=device))
    optimizer = torch.optim.Adam(model.parameters(), lr=config["learning_rate"], weight_decay=config["weight_decay"])
    fit_x, fit_r, fit_y = [torch.from_numpy(v).to(device) for v in inputs["fit"]]
    best, stale, history = -1., 0, []
    start = time.perf_counter()
    generator = torch.Generator().manual_seed(seed)
    output.mkdir(parents=True, exist_ok=True)
    for epoch in range(1, config["epochs"] + 1):
        model.train()
        permutation = torch.randperm(len(fit_y), generator=generator).to(device)
        losses = []
        for ids in permutation.split(config["batch_size"]):
            optimizer.zero_grad(set_to_none=True)
            logits = forward(model, name, fit_x[ids], fit_r[ids])
            loss = criterion(logits, fit_y[ids])
            if not torch.isfinite(loss):
                raise ValueError("Nonfinite training loss")
            loss.backward()
            optimizer.step()
            losses.append((float(loss.detach()), len(ids)))
        stop_p = predict(model, name, *inputs["stop"][:2], device)
        metric = score(inputs["stop"][2], stop_p, data["subject_group"][parts["stop"]], classes)["macro_f1"]
        history.append({"epoch": epoch, "fit_loss": sum(a*b for a,b in losses)/len(fit_y), "stop_macro_f1": metric,
                        "elapsed_seconds": time.perf_counter()-start})
        if metric > best + 1e-8:
            best, stale = metric, 0
            torch.save({"state_dict": model.state_dict(), "model_id": name, "classes": classes,
                        "scaler": scaler, "seed": seed, "fold": fold, "epoch": epoch,
                        "config": config, "selection_score": metric}, output / "best.pt")
        else:
            stale += 1
        write(output / "history.json", history)
        print(f"{config['experiment_id']} fold={fold} seed={seed} {name} epoch={epoch} stop-F1={metric:.4f} elapsed={time.perf_counter()-start:.1f}s", flush=True)
        if stale >= config["patience"]:
            break
    bundle = torch.load(output / "best.pt", map_location=device, weights_only=True)
    model.load_state_dict(bundle["state_dict"])
    eval_p = predict(model, name, *inputs["evaluation"][:2], device)
    cal_p = predict(model, name, *inputs["calibration"][:2], device)
    # Warmed single-beat latency; total transfer and model forward; no file loading.
    predict(model, name, inputs["evaluation"][0][:1], inputs["evaluation"][1][:1], device)
    latencies = []
    for _ in range(30):
        ts = time.perf_counter()
        predict(model, name, inputs["evaluation"][0][:1], inputs["evaluation"][1][:1], device)
        if device.type == "cuda":
            torch.cuda.synchronize()
        latencies.append((time.perf_counter()-ts)*1000)
    e, c = parts["evaluation"], parts["calibration"]
    np.savez_compressed(output / "predictions.npz", eval_indices=e, eval_probability=eval_p,
                        calibration_indices=c, calibration_probability=cal_p)
    result = {"status": "completed", "smoke": smoke, "model": name, "seed": seed, "fold": fold,
              "task": config["task"], "classes": classes, "config": config,
              "checkpoint_sha256": sha256(output / "best.pt"), "best_epoch": bundle["epoch"],
              "parameter_count": sum(p.numel() for p in model.parameters()), "fit_seconds": time.perf_counter()-start,
              "device": str(device), "latency_ms_median": float(np.median(latencies)), "latency_ms_p95": float(np.quantile(latencies, .95)),
              "latency_scope": "30 warmed batch=1 calls, CPU threads from config; transfer + forward + softmax; excludes IO",
              "class_weights": weights.tolist(),
              "partitions": {k: {"subjects": sorted(set(data["subject_group"][v])), "samples": len(v),
                                    "class_counts": np.bincount(data["label"][v], minlength=len(classes)).tolist()}
                             for k, v in parts.items()},
              "evaluation": score(data["label"][e], eval_p, data["subject_group"][e], classes)}
    write(output / "result.json", result)
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default=str(BASE / "configs/cv_cpu_v1.json"))
    parser.add_argument("--smoke", action="store_true")
    args = parser.parse_args()
    config = json.loads(Path(args.config).read_text(encoding="utf-8"))
    if args.smoke:
        config.update(experiment_id="smoke_v1", epochs=1, patience=1)
    torch.set_num_threads(config["threads"])
    data = load()
    if config["task"] == "nv":
        keep = np.isin(data["label"], [0, 2])
        data = {k: v[keep] for k, v in data.items()}
        data["label"] = (data["label"] == 2).astype(np.int64)
    folds = partition(data, config)
    if args.smoke:
        folds = [{k: v[:min(len(v), 1024)] for k, v in folds[0].items()}]
        # Deterministic label-stratified smoke fit keeps all classes, no smoke scores are scientific results.
        for key in folds[0]:
            original = partition(data, config)[0][key]
            folds[0][key] = np.sort(np.concatenate([original[data["label"][original] == i][:256] for i in range(len(np.unique(data["label"])))]))
    output = BASE / "results" / config["experiment_id"]
    output.mkdir(parents=True, exist_ok=True)
    source_files = [Path(__file__), Path(__file__).with_name("data.py"), Path(__file__).with_name("models.py")]
    fingerprint = {"config": config, "source_sha256": {p.name: sha256(p) for p in source_files},
                   "data_sha256": sha256(BASE / "data/development.npz")}
    if (output / "fingerprint.json").exists():
        if json.loads((output / "fingerprint.json").read_text(encoding="utf-8")) != fingerprint:
            raise ValueError("Run provenance changed; use a new experiment_id, never mix completed jobs")
    else:
        write(output / "fingerprint.json", fingerprint)
    write(output / "environment.json", {"python": platform.python_version(), "torch": torch.__version__,
                                        "device": "cuda" if torch.cuda.is_available() else "cpu", "threads": config["threads"],
                                        "started": datetime.now().astimezone().isoformat()})
    write(output / "folds.json", [{k: {"indices": v.tolist(), "subjects": sorted(set(data["subject_group"][v]))} for k,v in parts.items()} for parts in folds])
    for fold, parts in enumerate(folds):
        for seed in config["seeds"]:
            for name in config["models"]:
                target = output / f"fold{fold}" / f"seed{seed}" / name
                completed = target / "result.json"
                if completed.exists():
                    result = json.loads(completed.read_text(encoding="utf-8"))
                    assert result["checkpoint_sha256"] == sha256(target / "best.pt")
                    print(f"Verified completed: {target}", flush=True)
                    continue
                job(data, parts, config, fold, seed, name, target, smoke=args.smoke)
    write(output / "COMPLETED.json", {"status": "completed", "job_count": len(folds)*len(config["seeds"])*len(config["models"]), "smoke": args.smoke})


if __name__ == "__main__":
    main()
