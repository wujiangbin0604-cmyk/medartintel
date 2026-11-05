import json
import os
import textwrap
from pathlib import Path
os.environ.setdefault("MPLCONFIGDIR", str(Path(__file__).resolve().parents[2] / ".mplconfig"))
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from ..labels import GROUPS

COLORS = {"N": "#246a73", "S": "#c27c00", "V": "#c0384b", "F": "#8054ad", "Q": "#737b87"}
FAMILIES = {"A": "A_distribution", "B": "B_waveforms", "C": "C_morphology",
            "D": "D_rhythm", "E": "E_quality", "F": "F_embedding"}
plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 10,
                     "axes.spines.top": False, "axes.spines.right": False,
                     "axes.grid": True, "grid.alpha": .18, "savefig.dpi": 300})


def empty_panel(ax, message, xlabel="Time relative to expert annotation (s)", ylabel="ECG amplitude"):
    ax.text(.5, .5, message, ha="center", va="center", transform=ax.transAxes, color="#626b75")
    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)


def class_counts(meta):
    return meta.aami_group.value_counts().reindex(GROUPS, fill_value=0)


def count_text(meta):
    counts = class_counts(meta)
    return "; ".join(f"{g}={int(counts[g])}" for g in GROUPS)


def pool_scope(collection):
    names = sorted(collection.metadata.record.unique())
    return f"records={','.join(names)}; lead={collection.lead}; fs={collection.fs:g}Hz; complete windows={len(collection.raw)}"


class FigureBook:
    def __init__(self, root, records, config):
        self.root, self.records, self.config = root, records, config
        self.entries, self.selections = [], []
        self.tables = {}
        self.record_scope = "; ".join(f"{r.name}:{','.join(r.leads)} t=0-{r.duration:.3f}s fs={r.fs:g}Hz" for r in records)
        for folder in FAMILIES.values():
            (root / "figures" / folder).mkdir(parents=True, exist_ok=True)

    def save(self, fig, code, filename, title, purpose, findings, limitation, scope=None):
        folder = FAMILIES[code]
        path = self.root / "figures" / folder / (filename + ".png")
        fig.suptitle(title, fontsize=13)
        scope = scope or self.record_scope
        display_scope = scope if len(scope) < 190 else "Records, leads, sample/time ranges: results/visualization/record_metadata.csv and figure_catalog.csv"
        footer = "\n".join(textwrap.wrap(display_scope, width=155))
        fig.text(.012, .012, footer, fontsize=7, color="#4e5863", va="bottom")
        fig.tight_layout(rect=(0, .07, 1, .93))
        fig.savefig(path, dpi=300, facecolor="white")
        plt.close(fig)
        self.entries.append({"figure_id": f"{code}{sum(e['category']==code for e in self.entries)+1:02d}",
                             "category": code, "file": path.relative_to(self.root).as_posix(),
                             "title": title.replace("\n", " / "), "scope": scope, "purpose": purpose,
                             "computed_findings": findings, "interpretation_limits": limitation,
                             "dpi": 300})
        print(f"[{code}] {path.name}", flush=True)

    def select(self, collection, positions, filename, method):
        for position in positions:
            row = collection.metadata.iloc[int(position)]
            self.selections.append({"figure_file": filename, "selection_method": method,
                                    **{key: row[key] for key in ("beat_id", "record", "lead", "annotation_index", "sample", "time_s", "symbol", "aami_group", "window_start_sample", "window_stop_sample_exclusive")}})

    def write_tables(self):
        directory = self.root / "results/visualization"
        tables = {**self.tables, "figure_catalog": pd.DataFrame(self.entries),
                  "plotted_heartbeat_windows": pd.DataFrame(self.selections)}
        for name, frame in tables.items():
            frame.to_csv(directory / f"{name}.csv", index=False, encoding="utf-8-sig")
        return tables


def heatmap(ax, values, rows, columns, label, cmap="Blues", limits=None, formatter=".0f"):
    array = np.asarray(values, dtype=float)
    kwargs = {} if limits is None else {"vmin": limits[0], "vmax": limits[1]}
    palette = plt.get_cmap(cmap).copy()
    palette.set_bad("#e8ebee")
    im = ax.imshow(np.ma.masked_invalid(array), aspect="auto", cmap=palette, **kwargs)
    ax.set_xticks(range(len(columns)), columns)
    ax.set_yticks(range(len(rows)), rows)
    ax.grid(False)
    finite = array[np.isfinite(array)]
    midpoint = (finite.min() + finite.max()) / 2 if finite.size else 0
    if array.size <= 260:
        for i in range(len(rows)):
            for j in range(len(columns)):
                value = array[i, j]
                dark_cell=np.isfinite(value) and ((cmap=='Blues' and value>midpoint) or (cmap=='coolwarm' and abs(value)>.75))
                ax.text(j, i, format(value, formatter) if np.isfinite(value) else "NA", ha="center", va="center",
                        fontsize=9, color="white" if dark_cell else "#26313d")
    ax.figure.colorbar(im, ax=ax, label=label, shrink=.85)
    return im
