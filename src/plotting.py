"""Static, unfiltered waveform plots with traceable sample/time metadata."""
import os
from pathlib import Path
os.environ.setdefault("MPLCONFIGDIR", str(Path(__file__).resolve().parents[1] / ".mplconfig"))
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from .analysis import primary_channel
from .labels import GROUPS

COLORS = {"N": "#246a73", "S": "#cf8500", "V": "#bf3544", "F": "#7e4ea8", "Q": "#5b6472"}
plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 10,
                     "axes.spines.top": False, "axes.spines.right": False,
                     "axes.grid": True, "grid.alpha": 0.2, "savefig.dpi": 180})


class Plotter:
    def __init__(self, directory):
        self.directory = directory
        self.entries = []
        self.examples = []

    def save(self, figure, name, scope, **metadata):
        figure.text(.01, .008, scope, fontsize=8, color="#444444", va="bottom")
        figure.tight_layout(rect=(0, .04, 1, .96))
        target = self.directory / name
        figure.savefig(target)
        plt.close(figure)
        self.entries.append({"file": f"figures/{name}", "scope": scope, **metadata})

    def strip(self, record, start_s, end_s, name, title, annotate=False):
        start = max(0, round(start_s * record.fs))
        stop = min(len(record.signal), round(end_s * record.fs))
        fig, axes = plt.subplots(len(record.leads), 1, figsize=(14, 3 * len(record.leads)), sharex=True, squeeze=False)
        table = record.annotations[(record.annotations["sample"] >= start) & (record.annotations["sample"] < stop)]
        for channel, lead in enumerate(record.leads):
            ax = axes[channel, 0]
            ax.plot(np.arange(start, stop) / record.fs, record.signal[start:stop, channel], lw=.8, color="#253b51", label="Raw ECG")
            if annotate:
                for group in GROUPS:
                    beats = table[(table.annotation_kind == "mapped_beat") & (table.aami_group == group)]
                    if beats.empty:
                        continue
                    samples = beats["sample"].to_numpy(dtype=int)
                    amplitudes = record.signal[samples, channel]
                    ax.scatter(samples / record.fs, amplitudes, color=COLORS[group], s=24, zorder=4, label=f"AAMI {group}")
                    for row, amplitude in zip(beats.itertuples(), amplitudes):
                        ax.annotate(row.symbol, (row.time_s, amplitude), xytext=(0, 9), textcoords="offset points", ha="center", fontsize=8, color=COLORS[group])
                other = table[table.annotation_kind != "mapped_beat"]
                for i, row in enumerate(other.itertuples()):
                    ax.axvline(row.time_s, color="#717171", alpha=.5, ls=":", label="Non-beat / unmapped" if i == 0 else None)
                    ax.text(row.time_s, .94 - .08 * (i % 2), row.symbol, transform=ax.get_xaxis_transform(), fontsize=8, color="#555555")
            ax.set_ylabel(f"{lead} ({record.units[channel]})")
            ax.set_title(f"Record {record.name} | lead {lead}", loc="left", fontsize=11)
            ax.margins(y=.18)
            ax.legend(loc="lower right", bbox_to_anchor=(1, 1.02), ncol=6, fontsize=8)
        axes[-1, 0].set_xlabel("Time from record start (s)")
        axes[-1, 0].set_xlim(start / record.fs, stop / record.fs)
        fig.suptitle(title, fontsize=14)
        scope = f"record={record.name}; leads={','.join(record.leads)}; fs={record.fs:g} Hz; samples=[{start},{stop}); t=[{start/record.fs:.3f},{stop/record.fs:.3f}) s"
        self.save(fig, name, scope, record=record.name, leads=",".join(record.leads), start_s=start / record.fs, end_s=stop / record.fs)

    def example(self, record, row, purpose, image_name):
        self.examples.append({"figure": f"figures/{image_name}", "purpose": purpose,
                              "record": record.name, "lead": row.lead,
                              "annotation_index": int(row.annotation_index), "symbol": row.symbol,
                              "aami_group": row.aami_group, "sample": int(row["sample"]),
                              "time_s": row.time_s, "start_sample": int(row.window_start_sample),
                              "stop_sample_exclusive": int(row.window_stop_sample_exclusive),
                              "start_s": row.window_start_s, "last_sample_time_s": row.window_last_sample_time_s})

    def compare_classes(self, record, beats):
        channel = primary_channel(record)
        lead = record.leads[channel]
        valid = beats[beats.window_valid & (beats.aami_group != "")]
        fig, axes = plt.subplots(5, 1, figsize=(12, 13), sharex=True, sharey=True)
        name = f"{record.name}_{lead}_class_examples.png"
        for ax, group in zip(axes, GROUPS):
            part = valid[valid.aami_group == group]
            if part.empty:
                ax.text(.5, .5, f"AAMI {group}: no complete window in this record", transform=ax.transAxes, ha="center")
            else:
                row = part.iloc[len(part) // 2]
                start, stop, sample = int(row.window_start_sample), int(row.window_stop_sample_exclusive), int(row["sample"])
                ax.plot((np.arange(start, stop) - sample) / record.fs, record.signal[start:stop, channel], color=COLORS[group], lw=1.3, label=f"{row.symbol} -> {group}; sample {sample}; t={row.time_s:.3f}s")
                ax.axvline(0, color="#555555", ls="--", lw=.7)
                ax.legend(loc="upper right", fontsize=9)
                self.example(record, row, "class_comparison", name)
            ax.set_ylabel(f"{group} | {lead} ({record.units[channel]})")
        axes[-1].set_xlabel("Time relative to ORIGINAL expert beat annotation (s)")
        fig.suptitle(f"Record {record.name} | {lead} | one deterministic example per class\nRaw amplitude; identical axes; examples do not represent all class morphologies")
        self.save(fig, name, f"record={record.name}; lead={lead}; fs={record.fs:g}Hz; exact original times/windows: results/plotted_beats.csv", record=record.name, leads=lead)

    def compare_within(self, record, beats, maximum=6):
        channel = primary_channel(record)
        lead = record.leads[channel]
        valid = beats[beats.window_valid & (beats.aami_group != "")]
        for group, part in valid.groupby("aami_group"):
            chosen = part.iloc[np.unique(np.linspace(0, len(part) - 1, min(maximum, len(part)), dtype=int))]
            fig, axes = plt.subplots(1, 2, figsize=(15, 5), sharex=True, sharey=True)
            name = f"{record.name}_{lead}_{group}_within_class.png"
            for i, (_, row) in enumerate(chosen.iterrows()):
                start, stop, sample = int(row.window_start_sample), int(row.window_stop_sample_exclusive), int(row["sample"])
                time = (np.arange(start, stop) - sample) / record.fs
                values = record.signal[start:stop, channel]
                label = f"{row.symbol}, #{sample}, {row.time_s:.3f}s"
                axes[0].plot(time, values, alpha=.8, lw=1, label=label)
                # Quantitative plot uses all eligible beats; overlays are time-spread examples.
                axes[1].plot(time, values - np.median(values), alpha=.8, lw=1, label=label)
                self.example(record, row, "within_class", name)
            for ax in axes:
                ax.axvline(0, color="#555555", ls="--", lw=.7)
                ax.set_xlabel("Time relative to original annotation (s)")
                ax.set_ylabel(f"{lead} amplitude ({record.units[channel]})")
                ax.legend(fontsize=8, loc="upper right")
            axes[0].set_title("Raw physical amplitude")
            axes[1].set_title("Window median subtracted for display only")
            fig.suptitle(f"Record {record.name} | lead {lead} | AAMI {group} | {len(chosen)} time-spread beats")
            self.save(fig, name, f"record={record.name}; lead={lead}; fs={record.fs:g}Hz; legend=original annotation times; windows: results/plotted_beats.csv", record=record.name, leads=lead)

    def distributions(self, class_total, class_record, records):
        scope = "; ".join(f"{r.name}:{','.join(r.leads)} t=0-{r.duration:.3f}s fs={r.fs:g}Hz" for r in records)
        scope += "; counts use annotations once per beat, independent of lead"
        fig, axes = plt.subplots(1, 2, figsize=(13, 5))
        values = class_total.set_index("aami_group").loc[list(GROUPS), "count"]
        percentages = class_total.set_index("aami_group").loc[list(GROUPS), "percentage_of_mapped_beats"]
        for ax, data, label in zip(axes, (values, percentages), ("Beat count", "Mapped beats (%)")):
            bars = ax.bar(list(GROUPS), data, color=[COLORS[g] for g in GROUPS])
            ax.bar_label(bars, labels=[f"{v:.2f}%" if "%" in label else str(int(v)) for v in data], padding=4)
            ax.set_ylabel(label)
            ax.set_xlabel("AAMI group (raw symbol counts are reported separately)")
            ax.set_ylim(0, max(float(data.max()) * 1.2, 1))
        fig.suptitle("All selected records | mapped beat count and percentage")
        self.save(fig, "aami_class_distribution.png", scope)
        n = len(records)
        fig, axes = plt.subplots(2, 1, figsize=(max(12, min(28, n * .5)), 8), sharex=True)
        for ax, column, ylabel in zip(axes, ("count", "percentage_within_record_mapped_beats"), ("Beat count", "Within-record mapped beats (%)")):
            pivot = class_record.pivot(index="record", columns="aami_group", values=column).reindex(columns=GROUPS, fill_value=0)
            bottom = np.zeros(len(pivot))
            for group in GROUPS:
                ax.bar(pivot.index, pivot[group], bottom=bottom, label=group, color=COLORS[group])
                bottom += pivot[group].to_numpy()
            ax.set_ylabel(ylabel)
            ax.legend(title="AAMI", ncol=5, loc="upper right")
        axes[-1].set_xlabel("Record ID")
        axes[-1].tick_params(axis="x", rotation=90 if n > 10 else 0)
        fig.suptitle("Between-record distribution | full duration | non-beat events excluded")
        # Full 48-record scope remains available in CSV if the PNG footer would be too long.
        self.save(fig, "aami_distribution_by_record.png", scope if n < 6 else "All selected records; exact record/lead/time scopes: results/record_metadata.csv; annotations counted once per beat")

    def quality(self, record, windows):
        for lead, part in windows.groupby("lead"):
            row = part.loc[part.diff_rms.idxmax()]
            self.strip(record, row.start_s, row.end_s_exclusive,
                       f"{record.name}_quality_top_diff_{lead}.png",
                       f"Record {record.name} | highest first-difference RMS window on {lead} (up to 10s)\nHeuristic review window: QRS morphology and noise both contribute", annotate=True)
        events = record.annotations[(record.annotations.symbol == "~") & (record.annotations.time_s > 1)]
        if not events.empty:
            center = events.iloc[0].time_s
            self.strip(record, max(0, center - 2), min(record.duration, center + 8),
                       f"{record.name}_quality_annotation.png", f"Record {record.name} | first non-initial expert signal-quality-change event", annotate=True)

    def tables(self):
        return pd.DataFrame(self.entries), pd.DataFrame(self.examples)
