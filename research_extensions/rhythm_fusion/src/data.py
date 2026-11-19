"""Past-only rhythm features, independent of beat class and target selection."""
from pathlib import Path
import json
import numpy as np
import wfdb
from src.preprocessing.splitting import subject_id
from research_extensions.protect import sha256

ROOT = Path(__file__).resolve().parents[3]
BASE = ROOT / "research_extensions/rhythm_fusion"
NAMES = ["current_rr_s", "previous_rr_s", "current_over_previous", "current_over_history_median",
         "history5_median_s", "history5_mad_s", "relative_change_from_history"]
# WFDB QRS/beat symbols; never target-filter this event sequence. !, x, |, + are not QRS beats.
BEAT_SYMBOLS = frozenset("NLRBAaJSV rFejnE/fQ?".replace(" ", ""))


def rhythm_at(beat_positions, current_sample, fs=360.):
    """Return seven features/masks and <=5 previous RR intervals, all in seconds.

    History excludes current RR. MAD is median(abs(RR - median(RR))), unscaled.
    Missing entries are NaN until training-only imputation. No symbols enter here.
    """
    positions = np.asarray(beat_positions, dtype=np.int64)
    if positions.ndim != 1 or np.any(np.diff(positions) <= 0) or fs <= 0:
        raise ValueError("Strictly increasing within-record beat positions and positive fs required")
    end = np.searchsorted(positions, current_sample, side="right")
    if not end or positions[end - 1] != current_sample:
        raise ValueError("Requested position is not an expert QRS beat event")
    rr = np.diff(positions[max(0, end - 7):end]) / fs
    current = rr[-1] if len(rr) else np.nan
    previous = rr[-2] if len(rr) >= 2 else np.nan
    history = rr[:-1][-5:]
    median = np.median(history) if len(history) else np.nan
    mad = np.median(np.abs(history - median)) if len(history) >= 2 else np.nan
    values = np.array([current, previous, current / previous, current / median,
                       median, mad, (current - median) / median], dtype=np.float32)
    return values, np.isfinite(values).astype(np.float32), history.astype(np.float32)


def event_positions(samples, symbols):
    """The only use of symbols: fixed event-type inclusion, never class-valued features."""
    samples = np.asarray(samples, dtype=np.int64)
    keep = np.array([s in BEAT_SYMBOLS for s in symbols])
    positions = samples[keep]
    if np.any(np.diff(positions) <= 0):
        raise ValueError("Duplicate or out-of-order beat events require explicit adjudication")
    return positions


def fit_scaler(waveform, rhythm, mask, sample_ids):
    filled = np.where(mask > 0, rhythm, np.nan).astype(np.float64)
    median = np.array([np.median(col[np.isfinite(col)]) if np.isfinite(col).any() else 0.
                       for col in filled.T])
    imputed = np.where(mask > 0, rhythm, median)
    return {"wave_mean": float(waveform.mean(dtype=np.float64)),
            "wave_std": max(float(waveform.std(dtype=np.float64)), 1e-8),
            "rhythm_median": median.tolist(), "rhythm_mean": imputed.mean(0).tolist(),
            "rhythm_std": np.maximum(imputed.std(0), 1e-8).tolist(),
            "fit_sample_count": len(sample_ids),
            "fit_sample_ids_sha256": __import__("hashlib").sha256("\n".join(map(str, sample_ids)).encode()).hexdigest(),
            "fit_scope": "inner fitting patients only; no clipping; population std ddof=0"}


def transform(waveform, rhythm, mask, scaler):
    x = ((waveform - scaler["wave_mean"]) / scaler["wave_std"]).astype(np.float32)
    r = (np.where(mask > 0, rhythm, scaler["rhythm_median"]) - scaler["rhythm_mean"]) / scaler["rhythm_std"]
    r = np.concatenate([r.astype(np.float32), mask.astype(np.float32)], axis=1)
    if not np.isfinite(x).all() or not np.isfinite(r).all():
        raise ValueError("Nonfinite transformed input")
    return x, r


def build():
    output = BASE / "data"
    output.mkdir(parents=True, exist_ok=True)
    path = output / "development.npz"
    source = ROOT / "data/processed/mitdb44_nsvf_v1"
    arrays = []
    source_hashes = {}
    # Deliberately never open test.npz or test predictions.
    for split in ["train", "val"]:
        p = source / f"{split}.npz"
        source_hashes[p.relative_to(ROOT).as_posix()] = sha256(p)
        with np.load(p, allow_pickle=False) as z:
            arrays.append({"waveform": z["X_filtered"].copy(), "label": z["y"].copy(),
                           "split": np.full(len(z["y"]), split),
                           **{k: z[k].copy() for k in ["sample_id", "record_id", "annotation_sample", "original_label"]},
                           "subject_group": z["subject_id"].copy()})
    data = {k: np.concatenate([a[k] for a in arrays]) for k in arrays[0]}
    if len(np.unique(data["sample_id"])) != len(data["label"]):
        raise AssertionError("Duplicate sample IDs")
    features = np.full((len(data["label"]), len(NAMES)), np.nan, dtype=np.float32)
    mask = np.zeros_like(features)
    record_audit = []
    for rid in sorted(set(data["record_id"])):
        ann_path = ROOT / "data/mitdb" / str(rid)
        ann = wfdb.rdann(str(ann_path), "atr")
        beats = event_positions(ann.sample, ann.symbol)
        indices = np.flatnonzero(data["record_id"] == rid)
        for i in indices:
            raw_index = int(str(data["sample_id"][i]).rsplit(":", 1)[1])
            assert ann.sample[raw_index] == data["annotation_sample"][i]
            assert ann.symbol[raw_index] == data["original_label"][i]
            assert data["subject_group"][i] == subject_id(str(rid))
            features[i], mask[i], _ = rhythm_at(beats, int(data["annotation_sample"][i]))
        record_audit.append({"record_id": str(rid), "event_count": len(beats), "aligned_samples": len(indices),
                             "atr_sha256": sha256(ann_path.with_suffix(".atr"))})
    plan = json.loads((source / "split_plan.json").read_text(encoding="utf-8"))
    forbidden = {s for s, split in plan["subject_to_split"].items() if split == "test"}
    assert not forbidden & set(data["subject_group"])
    assert len(set(data["subject_group"])) == 37
    data.update(rhythm_features=features, rhythm_valid_mask=mask)
    np.savez(path, **data)
    import pandas as pd
    pd.DataFrame({k: v for k, v in data.items() if v.ndim == 1}).to_csv(output / "alignment.csv", index=False)
    audit = {"sample_count": len(features), "subjects": 37, "feature_names": NAMES,
             "record_audit": record_audit, "source_sha256": source_hashes,
             "locked_split_sha256": sha256(source / "split_plan.json"),
             "excluded_test_subjects": sorted(forbidden), "test_npz_opened": False,
             "features": {"history": "up to 5 complete RR before current RR; minimum 1 for median, 2 for MAD",
                          "missing": "NaN and per-feature mask; imputation/scaling fit only on inner fitting patients",
                          "events": sorted(BEAT_SYMBOLS), "inputs": "expert QRS positions only"},
             "valid_counts": mask.sum(0).astype(int).tolist(), "alignment_verified": True}
    (output / "audit.json").write_text(json.dumps(audit, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"built": str(path), "samples": len(features), "subjects": 37}), flush=True)
    return data


def load():
    path = BASE / "data/development.npz"
    if not path.exists():
        return build()
    with np.load(path, allow_pickle=False) as z:
        return {k: z[k].copy() for k in z.files}


if __name__ == "__main__":
    build()
