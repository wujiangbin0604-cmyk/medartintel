"""Traceable heartbeat windows and physical descriptors for visualization only."""
from dataclasses import dataclass
import hashlib
import numpy as np
import pandas as pd
from .analysis import beat_table, primary_channel


@dataclass
class LeadBeats:
    lead: str
    fs: float
    unit: str
    time: np.ndarray
    raw: np.ndarray
    metadata: pd.DataFrame

    @property
    def centered(self):
        return self.raw - np.median(self.raw, axis=1, keepdims=True)


def random_generator(seed, *keys):
    key = hashlib.sha256("|".join(map(str, keys)).encode("utf-8")).digest()
    return np.random.default_rng(np.random.SeedSequence([seed, int.from_bytes(key[:4], "little")]))


def window_features(values, fs):
    centered = values - np.median(values, axis=1, keepdims=True)
    return {"peak_to_peak": np.ptp(values, axis=1), "maximum": values.max(axis=1),
            "minimum": values.min(axis=1), "energy_raw": np.square(values).sum(axis=1) / fs,
            "energy_centered": np.square(centered).sum(axis=1) / fs,
            "centered_rms": np.sqrt(np.mean(np.square(centered), axis=1))}


def extract_heartbeats(records, pre_s=.25, post_s=.45):
    """All beat counts survive; only complete, finite, mapped windows form matrices."""
    all_tables, parts = [], {}
    for record in records:
        table = beat_table(record, pre_s, post_s).reset_index(drop=True)
        table["beat_id"] = [f"{record.name}:{i}" for i in table.annotation_index]
        table["fs_hz"] = record.fs
        table["boundary_status"] = "valid"
        pre, post = round(pre_s * record.fs), round(post_s * record.fs)
        left = table["sample"] - pre < 0
        right = table["sample"] + post >= len(record.signal)
        table.loc[left, "boundary_status"] = "left"
        table.loc[right, "boundary_status"] = "right"
        table.loc[left & right, "boundary_status"] = "both"
        table["extraction_status"] = table.boundary_status.where(~table.window_valid, "valid")
        channel = primary_channel(record)
        accepted, waves = [], []
        for i, row in table.iterrows():
            if not row.window_valid:
                continue
            wave = record.signal[int(row.window_start_sample):int(row.window_stop_sample_exclusive), channel]
            if not np.isfinite(wave).all():
                table.loc[i, "extraction_status"] = "nonfinite"
            elif row.aami_group == "":
                table.loc[i, "extraction_status"] = "unmapped"
            else:
                accepted.append(i)
                waves.append(wave)
        if accepted:
            selected = table.loc[accepted].copy()
            values = np.stack(waves)
            for name, feature in window_features(values, record.fs).items():
                selected[name] = feature
                table.loc[accepted, name] = feature
            key = record.leads[channel]
            parts.setdefault(key, []).append((record.fs, record.units[channel], values, selected))
        all_tables.append(table)
    collections = {}
    for lead, pieces in parts.items():
        frequencies = {p[0] for p in pieces}
        units = {p[1] for p in pieces}
        if len(frequencies) != 1 or len(units) != 1:
            raise ValueError(f"Do not pool incompatible sampling rates/units for lead {lead}")
        fs, unit = pieces[0][:2]
        raw = np.concatenate([p[2] for p in pieces])
        metadata = pd.concat([p[3] for p in pieces], ignore_index=True)
        collections[lead] = LeadBeats(lead, fs, unit,
                                      np.arange(-round(pre_s * fs), round(post_s * fs) + 1) / fs,
                                      raw, metadata)
    return pd.concat(all_tables, ignore_index=True), collections


def stratified_sample_indices(metadata, seed, per_group=500, maximum=3000):
    """Equal-cap record/class sampling without replacement; retain tiny strata."""
    groups = [np.asarray(index, dtype=int) for index in metadata.groupby(["record", "aami_group"], sort=True).indices.values()]
    if maximum < len(groups):
        raise ValueError("Embedding maximum must cover at least one beat per record/class stratum")
    caps = np.array([min(len(g), per_group) for g in groups], dtype=int)
    quotas = np.zeros(len(groups), dtype=int)
    remaining = min(maximum, int(caps.sum()))
    while remaining:
        active = np.flatnonzero(quotas < caps)
        selected = active[:remaining]
        quotas[selected] += 1
        remaining -= len(selected)
    rng = random_generator(seed, "embedding_sample")
    selected = [rng.choice(group, size=int(q), replace=False) for group, q in zip(groups, quotas)]
    return np.sort(np.concatenate(selected)) if selected else np.array([], dtype=int)
