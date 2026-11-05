"""Build/verify the private index from real local WFDB files. No model changes."""
from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path

import numpy as np

from src.labels import AAMI_MAP
from .ecg_service import ECGStore
from .heartbeat_hunter import DIFFICULTIES, INDEX

ROOT = Path(__file__).resolve().parents[2]


def validate(store, level):
    context = store.signal_context(level["record_id"])
    record = context.record
    start, end = level["start_sample"], level["end_sample"]
    assert record.fs == level["sampling_rate"] == 360
    assert context.lead_name == level["lead_name"] == "MLII"
    assert record.units[context.channel] == "mV"
    assert 0 <= start < end <= len(record.signal)
    assert context.safe[start:end].all(), "filter protection region"
    signal = record.signal[start:end, context.channel]
    assert len(signal) == round(level["duration"] * record.fs) and np.isfinite(signal).all()
    assert np.ptp(signal) > .1
    annotations = record.annotations.query("@start <= sample < @end")
    assert not annotations.annotation_kind.isin(["unknown", "unmapped_beat"]).any()
    assert not annotations.symbol.isin(["~", "|", "[", "]", "!"]).any()
    # A noise/flutter interval may begin before the displayed window.
    preceding = record.annotations[record.annotations["sample"] < start]
    quality = preceding[preceding.symbol.eq("~")]
    if not quality.empty:
        channel_bits = (1 << context.channel) | (1 << (context.channel + 4))
        assert not (int(quality.iloc[-1].subtype) & channel_bits), "preceding noise interval"
    flutter = preceding[preceding.symbol.isin(["[", "]"])]
    assert flutter.empty or flutter.iloc[-1].symbol != "[", "preceding flutter interval"
    beats = annotations[annotations.annotation_kind.eq("mapped_beat")]
    assert beats.aami_group.isin(["N", "V"]).all()
    assert beats["sample"].is_unique and 6 <= len(beats) <= 60
    assert 1 <= beats.aami_group.eq("V").sum() <= len(beats) * .65
    # Keep complete local beat windows at both display boundaries.
    assert (beats["sample"] - start >= .3 * record.fs).all()
    assert (end - beats["sample"] >= .4 * record.fs).all()
    answers = [{"sample": int(a.sample), "symbol": a.symbol, "label": a.aami_group,
                "meaning": a.meaning_zh} for a in beats.itertuples()]
    assert all(AAMI_MAP[a["symbol"]] == a["label"] for a in answers)
    if "answers" in level:
        assert level["answers"] == answers
    return answers


def build(store):
    levels, sources = [], {}
    # All IDs come from discovered complete files, ordered reproducibly.
    for record_id in store.record_ids():
        context = store.signal_context(record_id)
        if context.lead_name != "MLII":
            continue
        record = context.record
        targets = record.annotations[record.annotations.aami_group.eq("V")]
        added = 0
        for difficulty, spec in DIFFICULTIES.items():
            count = 0
            last_end = -1
            for row in targets.itertuples():
                # Place actual annotated V beats at varied positions within the window.
                start = round((row.sample / record.fs - spec["duration"] * .43) * record.fs)
                end = start + round(spec["duration"] * record.fs)
                if start < last_end or start < 0 or end > len(record.signal):
                    continue
                level = {"id": hashlib.sha256(f"{record_id}:{start}:{difficulty}".encode()).hexdigest()[:24],
                         "difficulty": difficulty, "record_id": record_id, "lead_name": context.lead_name,
                         "sampling_rate": record.fs, "start_sample": start, "end_sample": end,
                         "duration": spec["duration"]}
                try:
                    level["answers"] = validate(store, level)
                except AssertionError:
                    continue
                levels.append(level)
                added += 1
                count += 1
                last_end = end
                if count == 4:
                    break
        if added:
            sources[record_id] = {ext: hashlib.sha256((store.data_dir / f"{record_id}.{ext}").read_bytes()).hexdigest() for ext in ("hea", "dat", "atr")}
        if all(sum(x["difficulty"] == d for x in levels) >= 20 for d in DIFFICULTIES):
            break
    assert all(sum(x["difficulty"] == d for x in levels) >= 5 for d in DIFFICULTIES)
    return {"version": 1, "source": "https://physionet.org/content/mitdb/1.0.0/", "sources_sha256": sources, "levels": levels}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    store = ECGStore(ROOT)
    if args.check:
        data = json.loads(INDEX.read_text(encoding="utf-8"))
        for rid, files in data["sources_sha256"].items():
            for ext, expected in files.items():
                assert hashlib.sha256((store.data_dir / f"{rid}.{ext}").read_bytes()).hexdigest() == expected
        for level in data["levels"]:
            validate(store, level)
    else:
        data = build(store)
        INDEX.parent.mkdir(parents=True, exist_ok=True)
        INDEX.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"valid": True, "levels": len(data["levels"]), "by_difficulty": dict(Counter(l["difficulty"] for l in data["levels"])), "records": list(data["sources_sha256"])}, ensure_ascii=False))


if __name__ == "__main__":
    main()
