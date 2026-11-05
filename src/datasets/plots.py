"""Dataset construction charts (kept separate from the original 67 EDA figures)."""
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from ..labels import GROUPS
from ..visuals.common import COLORS


class DatasetFigures:
    def __init__(self, root: Path):
        self.root = root
        self.entries: list[dict] = []
        self.directory = root / "figures/07_preprocessing"
        self.directory.mkdir(parents=True, exist_ok=True)

    def save(self, fig, name: str, title: str, purpose: str, scope: str) -> None:
        target = self.directory / f"{name}.png"
        fig.suptitle(title, fontsize=14)
        fig.tight_layout(rect=(0, 0, 1, .94))
        fig.savefig(target, dpi=300, bbox_inches="tight")
        plt.close(fig)
        self.entries.append({"file": target.relative_to(self.root).as_posix(), "title": title,
                             "purpose": purpose, "scope": scope, "dpi": 300})


def generate_dataset_figures(root: Path, metadata: pd.DataFrame, tables: dict,
                             record_symbol_counts: pd.DataFrame, contexts: dict,
                             target_groups: tuple[str, ...]) -> pd.DataFrame:
    book = DatasetFigures(root)
    # Official per-record symbol census includes both the 44-record analysis set and
    # the four paced records retained in the raw database.
    all_record_symbols = record_symbol_counts.copy()
    raw = all_record_symbols.groupby("symbol", as_index=False).agg(count=("count", "sum"))
    raw["aami_group"] = raw.symbol.map(lambda symbol: all_record_symbols.loc[all_record_symbols.symbol == symbol, "aami_label"].iloc[0])
    raw = raw.sort_values("count", ascending=False).reset_index(drop=True)
    all48 = all_record_symbols.groupby("aami_label")["count"].sum().reindex(GROUPS, fill_value=0)
    in44 = all_record_symbols[all_record_symbols.included_in_44_record_experiment]
    counts44 = in44.groupby("aami_label")["count"].sum().reindex(GROUPS, fill_value=0)
    excluded = all_record_symbols[~all_record_symbols.included_in_44_record_experiment]
    counts_excluded = excluded.groupby("aami_label")["count"].sum().reindex(GROUPS, fill_value=0)

    fig, axes = plt.subplots(2, 1, figsize=(15, 9), gridspec_kw={"height_ratios": [1.2, 1]})
    colors = [COLORS.get(str(raw.iloc[i].get("aami_group", "")), "#9099a2") for i in range(len(raw))]
    axes[0].bar(np.arange(len(raw)), raw["count"], color=colors, edgecolor="white", linewidth=.25)
    axes[0].set_xticks(np.arange(len(raw)), [str(s) for s in raw.symbol], rotation=0)
    axes[0].set_xlabel("Original WFDB annotation.symbol")
    axes[0].set_ylabel("Annotation count")
    axes[0].set_title("All original symbols | all 48 records | mapped beats and non-beat annotations")
    axes[0].grid(axis="y", alpha=.2)
    x = np.arange(len(GROUPS)); width = .25
    axes[1].bar(x-width, all48.reindex(GROUPS).to_numpy(), width, label="All 48 records", color="#436b83")
    axes[1].bar(x, counts44.reindex(GROUPS).to_numpy(), width, label="44-record experiment", color="#3c8d8a")
    axes[1].bar(x+width, counts_excluded.reindex(GROUPS).to_numpy(), width, label="Excluded paced records", color="#c78145")
    axes[1].set_xticks(x, GROUPS); axes[1].set_xlabel("AAMI group")
    axes[1].set_ylabel("Mapped heartbeat count")
    axes[1].set_title("Mapped AAMI groups; raw non-beat symbols remain separately tabulated")
    axes[1].legend(); axes[1].grid(axis="y", alpha=.2)
    book.save(fig, "label_distribution_all48_and_44", "MIT-BIH original labels and AAMI distribution",
              "Raw-symbol frequency and AAMI group counts before/after excluding the four paced records.",
              "Counts recomputed from the official .atr annotations; includes all 48 records and the 44-record subset.")

    record_order = (root / "data/mitdb/RECORDS").read_text(encoding="utf-8").split()
    record_order = [record for record in record_order if record not in {"102", "104", "107", "217"}]
    per_record = metadata[metadata.annotation_kind == "mapped_beat"].pivot_table(
        index="record_id", columns="mapped_label", values="annotation_index", aggfunc="count", fill_value=0)
    per_record = per_record.reindex(index=record_order, columns=GROUPS, fill_value=0)
    fig, ax = plt.subplots(figsize=(18, 7))
    bottom = np.zeros(len(per_record), dtype=float)
    for group in GROUPS:
        values = per_record[group].to_numpy()
        ax.bar(np.arange(len(per_record)), values, bottom=bottom, color=COLORS[group], label=group, width=.84)
        bottom += values
    split_map = metadata.drop_duplicates("record_id").set_index("record_id").split
    ax.set_xticks(np.arange(len(per_record)), [f"{r}\n{split_map[r]}" for r in per_record.index], fontsize=7)
    ax.set_xlabel("Record ID and locked patient-level split")
    ax.set_ylabel("Mapped heartbeat count")
    ax.set_title("Per-record AAMI heartbeat distribution | paced records excluded from model data")
    ax.legend(title="AAMI group", ncols=5, loc="upper right")
    ax.grid(axis="y", alpha=.2)
    book.save(fig, "record_aami_counts_44", "AAMI counts across the 44 included records",
              "Shows class concentration by record and the fixed train/validation/test allocation.",
              "44 non-paced records; all mapped heartbeat annotations, including windows later rejected for technical reasons.")

    split_counts = metadata[metadata.included].groupby(["split", "mapped_label"]).size().unstack(fill_value=0)
    split_counts = split_counts.reindex(index=["train", "val", "test"], columns=target_groups, fill_value=0)
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.7))
    for ax, values, title, ylabel in ((axes[0], split_counts, "Sample counts", "Included beats"),
                                      (axes[1], split_counts.div(split_counts.sum(axis=1), axis=0)*100,
                                       "Within-split percentages", "Beats (%)")):
        bottom = np.zeros(len(values))
        for group in target_groups:
            counts = values[group].to_numpy(dtype=float)
            ax.bar(values.index, counts, bottom=bottom, color=COLORS[group], label=group)
            bottom += counts
        ax.set_title(title); ax.set_xlabel("Patient-independent split"); ax.set_ylabel(ylabel)
        ax.legend(title="AAMI group")
    book.save(fig, f"split_class_distribution_44_{''.join(target_groups).lower()}", "44-record target-class distribution by split",
              "Provides class counts and within-split proportions for the task configured in this dataset build.",
              "Train/validation/test records were fixed before signal extraction; test data did not influence processing.")

    for record_id, context in contexts.items():
        record = context["record"]; channel = context["channel"]
        if record.leads[channel] != "MLII":
            continue
        fs = record.fs; n = min(len(record.signal), round(10 * fs)); t = np.arange(n) / fs
        raw_signal = record.signal[:n, channel]; filtered_signal = context["filtered"][:n]
        fig, axes = plt.subplots(2, 1, figsize=(13, 6), sharex=True)
        axes[0].plot(t, raw_signal, color="#536878", linewidth=.7)
        axes[0].set_title(f"Record {record_id} | MLII | original signal")
        axes[0].set_ylabel(f"Amplitude ({record.units[channel]})")
        axes[1].plot(t, filtered_signal, color="#bf635b", linewidth=.7, label="0.5–40 Hz zero-phase")
        axes[1].plot(t, raw_signal, color="#536878", alpha=.28, linewidth=.55, label="Original")
        axes[1].set_title("Continuous signal before and after filtering")
        axes[1].set_xlabel("Time from record start (s)"); axes[1].set_ylabel(f"Amplitude ({record.units[channel]})")
        axes[1].legend(); axes[1].grid(alpha=.2)
        book.save(fig, f"{record_id}_raw_vs_filtered_first10s",
                  f"Record {record_id} | MLII | first 10 seconds: filter comparison",
                  "Visualizes the fixed preprocessing filter on an untouched raw waveform.",
                  f"Record {record_id}; MLII; 0–{n/fs:.3f} s; amplitudes in {record.units[channel]}.")
    return pd.DataFrame(book.entries)
