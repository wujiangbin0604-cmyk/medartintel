"""Count the full annotation stream; bound-check only visualization windows."""
import numpy as np
import pandas as pd
from .labels import AAMI_MAP, BEAT_ZH, NONBEAT_ZH, GROUPS, describe, ANNOTATION_SOURCE, MAPPING_SOURCE


def window_bounds(sample, length, fs, pre_s=0.25, post_s=0.45):
    pre, post = round(pre_s * fs), round(post_s * fs)
    start, stop = int(sample) - pre, int(sample) + post + 1
    return (start, stop) if 0 <= start < stop <= length else None


def primary_channel(record):
    return record.leads.index("MLII") if "MLII" in record.leads else 0


def beat_table(record, pre_s, post_s):
    table = record.annotations[record.annotations.annotation_kind.isin(["mapped_beat", "unmapped_beat"])].copy()
    table["lead"] = record.leads[primary_channel(record)]
    table["rr_previous_s"] = table.time_s.diff()
    table["rr_next_s"] = table.time_s.shift(-1) - table.time_s
    bounds = [window_bounds(s, len(record.signal), record.fs, pre_s, post_s) for s in table["sample"]]
    table["window_valid"] = [b is not None for b in bounds]
    table["window_start_sample"] = pd.array([b[0] if b else None for b in bounds], dtype="Int64")
    table["window_stop_sample_exclusive"] = pd.array([b[1] if b else None for b in bounds], dtype="Int64")
    table["window_start_s"] = table.window_start_sample / record.fs
    table["window_last_sample_time_s"] = (table.window_stop_sample_exclusive - 1) / record.fs
    channel = primary_channel(record)
    table["window_peak_to_peak"] = [float(np.ptp(record.signal[b[0]:b[1], channel])) if b else np.nan for b in bounds]
    table["amplitude_unit"] = record.units[channel]
    return table


def summarize_labels(annotations, record_names):
    raw_record = annotations.groupby(["record", "symbol", "meaning_zh", "annotation_kind", "aami_group"], dropna=False).size().reset_index(name="count")
    raw_total = annotations.groupby(["symbol", "meaning_zh", "annotation_kind", "aami_group"], dropna=False).size().reset_index(name="count").sort_values("count", ascending=False)
    mapping = []
    counts = annotations.symbol.value_counts()
    for symbol in dict.fromkeys(list(BEAT_ZH) + list(NONBEAT_ZH) + list(counts.index)):
        mapping.append({"symbol": symbol, **describe(symbol), "count": int(counts.get(symbol, 0)),
                        "annotation_source": ANNOTATION_SOURCE,
                        "mapping_source": MAPPING_SOURCE if symbol in AAMI_MAP else "not mapped"})
    mapped = annotations[annotations.annotation_kind == "mapped_beat"]
    class_total = mapped.aami_group.value_counts().reindex(GROUPS, fill_value=0).rename_axis("aami_group").reset_index(name="count")
    denominator = int(class_total["count"].sum())
    class_total["percentage_of_mapped_beats"] = class_total["count"] / denominator * 100 if denominator else 0.0
    class_record = mapped.groupby(["record", "aami_group"]).size().reindex(pd.MultiIndex.from_product([record_names, GROUPS], names=["record", "aami_group"]), fill_value=0).reset_index(name="count")
    totals = class_record.groupby("record")["count"].transform("sum")
    class_record["percentage_within_record_mapped_beats"] = np.where(totals > 0, class_record["count"] / totals * 100, 0)
    return {"raw_symbol_counts": raw_total, "raw_symbol_counts_by_record": raw_record,
            "label_mapping": pd.DataFrame(mapping), "aami_counts": class_total,
            "aami_counts_by_record": class_record}


def longest_equal_run(values):
    if not len(values):
        return 0
    changes = np.flatnonzero(np.r_[True, values[1:] != values[:-1], True])
    return int(np.diff(changes).max())


def signal_quality(record, window_s=10):
    summary, windows = [], []
    step = round(window_s * record.fs)
    for channel, (lead, unit) in enumerate(zip(record.leads, record.units)):
        x = record.signal[:, channel]
        finite = x[np.isfinite(x)]
        adc = record.digital[:, channel]
        bits, zero = record.header.adc_res[channel], record.header.adc_zero[channel]
        low = zero - 2 ** (bits - 1)
        high = zero + 2 ** (bits - 1) - 1
        summary.append({"record": record.name, "lead": lead, "unit": unit,
                        "nonfinite_samples": int((~np.isfinite(x)).sum()),
                        "minimum": float(finite.min()), "maximum": float(finite.max()),
                        "mean": float(finite.mean()), "std": float(finite.std()),
                        "q01": float(np.quantile(finite, .01)), "q99": float(np.quantile(finite, .99)),
                        "max_abs_sample_difference": float(np.nanmax(np.abs(np.diff(x)))),
                        "adc_minimum": int(adc.min()), "adc_maximum": int(adc.max()),
                        "adc_lower_rail": low, "adc_upper_rail": high,
                        "adc_rail_samples": int(((adc <= low) | (adc >= high)).sum()),
                        "longest_exact_flat_run_s": longest_equal_run(adc) / record.fs,
                        "duration_s": record.duration})
        for start in range(0, len(x), step):
            stop = min(start + step, len(x))
            y = x[start:stop]
            if len(y) < 2:
                continue
            windows.append({"record": record.name, "lead": lead, "unit": unit,
                            "start_sample": start, "stop_sample_exclusive": stop,
                            "start_s": start / record.fs, "end_s_exclusive": stop / record.fs,
                            "peak_to_peak": float(np.nanmax(y) - np.nanmin(y)),
                            "diff_rms": float(np.sqrt(np.nanmean(np.diff(y) ** 2))),
                            "nonfinite_samples": int((~np.isfinite(y)).sum())})
    return pd.DataFrame(summary), pd.DataFrame(windows)


def morphology_summary(beats):
    valid = beats[beats.window_valid & (beats.aami_group != "")]
    rows = []
    for (record, lead, group), part in valid.groupby(["record", "lead", "aami_group"]):
        values = part.window_peak_to_peak
        rows.append({"record": record, "lead": lead, "aami_group": group,
                     "valid_window_count": len(part), "unit": part.amplitude_unit.iloc[0],
                     "peak_to_peak_min": values.min(), "peak_to_peak_median": values.median(),
                     "peak_to_peak_max": values.max(),
                     "rr_previous_median_s": part.rr_previous_s.median(),
                     "rr_next_median_s": part.rr_next_s.median()})
    return pd.DataFrame(rows)
