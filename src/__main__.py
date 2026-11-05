"""Run with: python -m src --records 100 200 [--offline]."""
import argparse
import json
import platform
from collections import Counter
from datetime import datetime
from importlib.metadata import version
from pathlib import Path
from zoneinfo import ZoneInfo
import numpy as np
import pandas as pd
from .download import prepare_data, sha256
from .io import load_record
from .analysis import beat_table, summarize_labels, signal_quality, morphology_summary
from .plotting import Plotter
from .report import build_report


def csv(table, path):
    table.to_csv(path, index=False, encoding="utf-8-sig")


def json_file(value, path):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description="MIT-BIH phase 1: read, group, visualize, report; no model training")
    parser.add_argument("--records", nargs="+", default=["100", "200"], help="Official record IDs, or all")
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--offline", action="store_true", help="Use local data only, including saved official hash list")
    parser.add_argument("--pre-s", type=float, default=.25)
    parser.add_argument("--post-s", type=float, default=.45)
    args = parser.parse_args()
    if not np.isfinite([args.pre_s, args.post_s]).all() or args.pre_s <= 0 or args.post_s <= 0:
        parser.error("Window pre/post durations must be finite and positive")
    root = args.root.resolve()
    for folder in ("data/mitdb", "figures", "results", "reports"):
        (root / folder).mkdir(parents=True, exist_ok=True)
    json_file({"passed": False, "status": "running_or_incomplete", "requested_records": args.records},
              root / "results/verification.json")
    names, manifest = prepare_data(root / "data/mitdb", args.records, args.offline)
    records, metadata, beats, quality, windows = [], [], [], [], []
    plots = Plotter(root / "figures")
    for name in names:
        print(f"Read/analyze/plot record {name}", flush=True)
        record, checks = load_record(root / "data/mitdb", name)
        record_beats = beat_table(record, args.pre_s, args.post_s)
        quality_summary, quality_windows = signal_quality(record)
        records.append(record)
        metadata.append(checks)
        beats.append(record_beats)
        quality.append(quality_summary)
        windows.append(quality_windows)
        plots.strip(record, 0, 10, f"{name}_first_10s_raw.png", f"Record {name} | first 10 seconds | raw ECG")
        plots.strip(record, 0, 10, f"{name}_first_10s_annotated.png", f"Record {name} | first 10 seconds | original expert annotations", annotate=True)
        plots.compare_classes(record, record_beats)
        plots.compare_within(record, record_beats)
        plots.quality(record, quality_windows)
    metadata = pd.DataFrame(metadata)
    beats, quality, windows = pd.concat(beats, ignore_index=True), pd.concat(quality, ignore_index=True), pd.concat(windows, ignore_index=True)
    annotations = pd.concat([r.annotations for r in records], ignore_index=True)
    tables = summarize_labels(annotations, names)
    morphology = morphology_summary(beats)
    plots.distributions(tables["aami_counts"], tables["aami_counts_by_record"], records)
    figure_table, plotted_beats = plots.tables()
    nonbeat = annotations[annotations.annotation_kind == "non_beat"]
    other = annotations[annotations.annotation_kind.isin(["unmapped_beat", "unknown"])]
    output = {**tables, "annotations": annotations, "non_beat_annotations": nonbeat,
              "unmapped_or_unknown_annotations": other, "record_metadata": metadata,
              "beats": beats, "signal_quality": quality, "quality_windows": windows,
              "morphology_summary": morphology, "figure_manifest": figure_table,
              "plotted_beats": plotted_beats, "download_manifest": pd.DataFrame(manifest)}
    for name, frame in output.items():
        csv(frame, root / "results" / f"{name}.csv")
    # JSONL preserves NUL terminators in aux_note; some CSV readers discard NULs.
    annotations.to_json(root / "results/annotations.jsonl", orient="records", lines=True, force_ascii=False)
    environment = {"python": platform.python_version(), "platform": platform.platform(),
                   **{name: version(name) for name in ("wfdb", "numpy", "pandas", "matplotlib")}}
    config = {"records": names, "database_version": "1.0.0", "offline": args.offline,
              "pre_s": args.pre_s, "post_s": args.post_s, "root": str(root),
              "generated_at_Asia_Shanghai": datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(),
              "trained_model": False, "dataset_split": None}
    json_file(environment, root / "results/environment.json")
    json_file(config, root / "results/run_config.json")
    build_report(root, records, tables, metadata, quality, beats, morphology, manifest, figure_table, config)
    # Independently verify saved CSV counts against the in-memory original annotation streams.
    disk_raw = pd.read_csv(root / "results/raw_symbol_counts.csv", keep_default_na=False)
    original_counts = Counter(s for r in records for s in r.annotations.symbol)
    csv_counts = dict(zip(disk_raw.symbol, disk_raw["count"].astype(int)))
    if original_counts != csv_counts:
        raise AssertionError("Saved symbol counts disagree with annotations")
    json_rows = [json.loads(line) for line in (root / "results/annotations.jsonl").read_text(encoding="utf-8").splitlines()]
    if [row["aux_note"] for row in json_rows] != annotations.aux_note.tolist():
        raise AssertionError("Original aux_note did not survive JSONL round trip")
    if int(tables["aami_counts"]["count"].sum()) + len(nonbeat) + len(other) != len(annotations):
        raise AssertionError("Annotation accounting does not balance")
    if not np.allclose(annotations.time_s, annotations["sample"] / annotations.record.map({r.name: r.fs for r in records})):
        raise AssertionError("Annotation time/sample mismatch")
    for row in plotted_beats.itertuples():
        length = next(len(r.signal) for r in records if r.name == row.record)
        if not 0 <= row.start_sample <= row.sample < row.stop_sample_exclusive <= length:
            raise AssertionError("Plotted beat outside signal")
    for item in manifest:
        if sha256(root / "data/mitdb" / item["file"]) != item["sha256"]:
            raise AssertionError("A raw file changed during analysis")
    for item in figure_table.file:
        path = root / item
        if not path.is_file() or path.stat().st_size < 1000 or path.read_bytes()[:8] != b"\x89PNG\r\n\x1a\n":
            raise AssertionError(f"Missing/invalid PNG: {path}")
    if not (root / "reports/data_exploration.md").is_file():
        raise AssertionError("Missing report")
    verification = {"passed": True, "records": names, "total_annotations": len(annotations),
                    "mapped_beats": int(tables["aami_counts"]["count"].sum()),
                    "non_beat_annotations": len(nonbeat), "unmapped_or_unknown": len(other),
                    "valid_beat_windows": int(beats.window_valid.sum()),
                    "boundary_skipped_windows": int((~beats.window_valid).sum()),
                    "png_files_verified": len(figure_table), "csv_files_written": len(output),
                    "csv_symbol_counts_match_annotations": True, "annotation_accounting_balances": True,
                    "sample_time_round_trip": True, "plotted_boundaries_valid": True,
                    "original_aux_note_jsonl_round_trip": True,
                    "raw_hashes_unchanged": True, "trained_model": False, "dataset_split": None}
    json_file(verification, root / "results/verification.json")
    print(json.dumps(verification, ensure_ascii=False, indent=2), flush=True)


if __name__ == "__main__":
    main()
