"""Validation-only integrated gradients from a frozen, real research checkpoint."""
from __future__ import annotations

import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import torch

from .controlled_imbalance import (ROOT, OUT, assert_protocol, build_model, logits_for,
                                    make_context, predict, read_json, sha, write_json)
from ..training.trainer import load_npz


def integrated_gradients(model, wave, context, target, steps=128):
    """Trapezoidal path integral of the target logit from zero-valued inputs."""
    if steps < 2:
        raise ValueError("At least two integration intervals required")
    model.eval()
    x = torch.as_tensor(wave, dtype=torch.float32).reshape(1, 1, -1)
    r = torch.as_tensor(context, dtype=torch.float32).reshape(1, -1)
    alphas = torch.linspace(0, 1, steps + 1)
    path_x = (alphas[:, None, None] * x).requires_grad_(True)
    path_r = (alphas[:, None] * r).requires_grad_(True)
    outputs = logits_for(model, path_x, path_r)[:, target]
    gx, gr = torch.autograd.grad(outputs.sum(), (path_x, path_r), allow_unused=True)
    weights = torch.ones(steps + 1); weights[[0, -1]] = .5
    attr_x = x[0] * (gx * weights[:, None, None]).sum(0) / steps
    attr_r = torch.zeros_like(r[0]) if gr is None else r[0] * (gr * weights[:, None]).sum(0) / steps
    difference = float((outputs[-1] - outputs[0]).detach())
    total = float(attr_x.sum().detach() + attr_r.sum().detach())
    return attr_x.detach().numpy().ravel(), attr_r.detach().numpy(), {
        "target_logit_difference": difference, "attribution_sum": total,
        "completeness_absolute_error": abs(total - difference),
        "completeness_relative_error": abs(total - difference) / max(abs(difference), 1e-6)}


def main():
    torch.set_num_threads(4)
    config, _ = assert_protocol()
    lock = read_json(OUT / "selection_locked.json")
    variant = next(v for v in config["variants"] if v["id"] == lock["selected_variant"])
    ordered = sorted(config["seeds"], key=lambda seed: (
        read_json(OUT / "runs" / variant["id"] / str(seed) / "val_metrics.json")["macro_f1"], seed))
    seed = ordered[len(ordered) // 2]
    folder = OUT / "runs" / variant["id"] / str(seed)
    checkpoint_path = folder / "best.pt"
    checkpoint = torch.load(checkpoint_path, weights_only=True, map_location="cpu")
    model = build_model(variant); model.load_state_dict(checkpoint["state_dict"])
    data = load_npz(ROOT / config["dataset"] / "val.npz")
    raw_rr, _ = make_context(data)
    normalizer = read_json(OUT / "rr_normalization.json")
    rr = ((raw_rr - np.array(normalizer["mean"])) / np.array(normalizer["scale"])).astype(np.float32)
    predictions, _ = predict(model, data["X"], rr)
    output = OUT / "explanations"; output.mkdir(exist_ok=True)
    figures = ROOT / "figures/final_optimization"; figures.mkdir(parents=True, exist_ok=True)
    fig, axes = plt.subplots(4, 2, figsize=(12, 10), gridspec_kw={"width_ratios": [4, 1.4]}, constrained_layout=True)
    rows = []
    for c, name in enumerate(config["class_names"]):
        # Fixed, transparent selection: middle NPZ row among each true class.
        candidates = np.flatnonzero(data["y"] == c)
        index = int(candidates[len(candidates) // 2])
        target = int(predictions[index])
        a64, _, _ = integrated_gradients(model, data["X"][index], rr[index], target, steps=64)
        attrs, timing_attrs, quality = integrated_gradients(model, data["X"][index], rr[index], target, steps=128)
        times = (np.arange(253) - 108) / 360
        ax = axes[c, 0]
        ax.plot(times, data["X_filtered"][index, 0], color="#303b51", linewidth=1)
        color_max = max(float(np.max(np.abs(attrs))), 1e-8)
        ax.scatter(times, data["X_filtered"][index, 0], c=attrs, cmap="coolwarm", vmin=-color_max, vmax=color_max, s=9)
        ax.axvline(0, color="#94a3b8", ls="--", lw=.7)
        ax.set(title=f"True {name} / predicted {config['class_names'][target]} · record {data['record_id'][index]} · sample {data['annotation_sample'][index]}",
               xlabel="Time relative to expert annotation (s)", ylabel="ECG (mV)")
        axes[c, 1].barh(["RR previous", "RR past mean", "RR / mean", "RR / preceding"], timing_attrs, color=["#d46a6a" if v >= 0 else "#517cbe" for v in timing_attrs])
        axes[c, 1].set_title("Timing logit attribution")
        axes[c, 1].axvline(0, color="#94a3b8", lw=.7)
        row = {"sample_id": str(data["sample_id"][index]), "record_id": str(data["record_id"][index]),
               "annotation_sample": int(data["annotation_sample"][index]), "true_class": name,
               "predicted_class": config["class_names"][target], "npz_row": index,
               "rr_attributions": timing_attrs.tolist(), "steps": 128,
               "wave_l1_change_64_to_128": float(np.abs(attrs - a64).sum()), **quality}
        rows.append(row)
        np.savez_compressed(output / f"class_{name}.npz", time_seconds=times,
                            waveform_mV=data["X_filtered"][index, 0], wave_attribution=attrs,
                            rr_raw=raw_rr[index], rr_attribution=timing_attrs)
    fig.suptitle(f"Integrated gradients · validation set · {variant['id']} · seed {seed}", fontsize=13)
    fig.supxlabel("Wave markers: red positive / blue negative target-logit contribution; color scale is separate for each case.", fontsize=9)
    fig.savefig(figures / "integrated_gradients.png", dpi=250); plt.close(fig)
    write_json(output / "manifest.json", {"variant": variant["id"], "seed": seed,
               "script_sha256": sha(Path(__file__)), "validation_npz_sha256": sha(ROOT / config["dataset"] / "val.npz"),
               "rr_normalizer_sha256": sha(OUT / "rr_normalization.json"),
               "checkpoint_sha256": sha(checkpoint_path), "selected_by": "validation mean; middle validation-ranked seed; middle row of each true validation class",
               "test_used_for_explanations": False, "attributed_output": "predicted-class logit",
               "baseline": "Zero normalized waveform and zero standardized timing = training means; not a physiological normal reference",
               "clinical_interpretation": "Attribution describes this checkpoint and reference; it does not establish physiological causality, P/QRS/T recognition or clinical knowledge.",
               "examples": rows})
    print(json.dumps({"variant": variant["id"], "seed": seed, "examples": rows}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
