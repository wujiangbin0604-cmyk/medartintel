"""Read WFDB physical/digital data and retain all original annotation fields."""
from dataclasses import dataclass
import json
import numpy as np
import pandas as pd
import wfdb
from .labels import describe


@dataclass
class ECGRecord:
    name: str
    fs: float
    signal: np.ndarray
    digital: np.ndarray
    leads: list
    units: list
    annotations: pd.DataFrame
    header: object

    @property
    def duration(self):
        return len(self.signal) / self.fs


def load_record(directory, name):
    path = str(directory / name)
    header = wfdb.rdheader(path)
    physical = wfdb.rdrecord(path, physical=True)
    digital = wfdb.rdrecord(path, physical=False)
    annotation = wfdb.rdann(path, "atr")
    if physical.p_signal.shape != (header.sig_len, header.n_sig):
        raise ValueError(f"{name}: signal shape does not agree with .hea")
    if header.fs <= 0 or not np.isclose(physical.fs, header.fs):
        raise ValueError(f"{name}: invalid/inconsistent sampling rate")
    if annotation.fs is not None and not np.isclose(annotation.fs, header.fs):
        raise ValueError(f"{name}: annotation fs mismatch")
    samples = np.asarray(annotation.sample, dtype=np.int64)
    if len(samples) == 0 or np.any(samples < 0) or np.any(samples >= header.sig_len):
        raise ValueError(f"{name}: empty or out-of-range annotations")
    if np.any(np.diff(samples) < 0):
        raise ValueError(f"{name}: non-monotonic annotations")
    for channel in range(header.n_sig):
        checksum = int(digital.d_signal[:, channel].astype(np.int64).sum()) % 65536
        if header.checksum[channel] is not None and checksum != header.checksum[channel] % 65536:
            raise ValueError(f"{name}: digital checksum mismatch in channel {channel}")
    rows = []
    for i, (sample, symbol) in enumerate(zip(samples, annotation.symbol)):
        row = {"record": name, "annotation_index": i, "sample": int(sample),
               "time_s": float(sample / header.fs), "symbol": symbol,
               "subtype": int(annotation.subtype[i]), "chan": int(annotation.chan[i]),
               "num": int(annotation.num[i]), "aux_note": annotation.aux_note[i],
               "aux_note_json": json.dumps(annotation.aux_note[i], ensure_ascii=False),
               "aux_note_text": annotation.aux_note[i].rstrip("\x00"),
               **describe(symbol)}
        for channel, lead in enumerate(header.sig_name):
            row[f"amplitude_{lead}_{header.units[channel]}"] = physical.p_signal[sample, channel]
        rows.append(row)
    table = pd.DataFrame(rows)
    beat_samples = table.loc[table.annotation_kind.isin(["mapped_beat", "unmapped_beat"]), "sample"]
    record = ECGRecord(name, float(header.fs), physical.p_signal, digital.d_signal,
                       header.sig_name, header.units, table, header)
    checks = {"record": name, "fs_hz": record.fs, "samples": header.sig_len,
              "duration_s": record.duration, "last_sample_time_s": (header.sig_len - 1) / record.fs,
              "leads": ", ".join(record.leads), "units": ", ".join(record.units),
              "annotation_count": len(table), "annotation_min_sample": int(samples.min()),
              "annotation_max_sample": int(samples.max()), "annotations_in_range": True,
              "annotations_monotonic": True, "duplicate_annotation_times": int(table["sample"].duplicated().sum()),
              "duplicate_beat_times": int(beat_samples.duplicated().sum()),
              "all_signal_samples_finite": bool(np.isfinite(record.signal).all()),
              "all_beat_positions_finite": bool(np.isfinite(record.signal[beat_samples.to_numpy()]).all()),
              "digital_checksums_match": True, "header_comments": " | ".join(header.comments)}
    return record, checks
