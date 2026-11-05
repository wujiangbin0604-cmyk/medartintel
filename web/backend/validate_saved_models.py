"""Reproduce saved validation predictions through the interactive inference service."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

from web.backend.ecg_service import InferenceService
from web.backend.model_registry import MODEL_IDS, TASKS


ROOT = Path(__file__).resolve().parents[2]
def choose_rows(npz: dict, task: str, limit: int) -> list[int]:
    labels = ["N", "V"] if task == "nv" else ["N", "S", "V", "F"]
    target_y = np.asarray(npz["y"])
    classes = np.asarray(npz["class_names"]).tolist()
    per_class = max(1, limit // len(labels))
    chosen: list[int] = []
    for label in labels:
        class_id = classes.index(label)
        candidates = np.flatnonzero(target_y == class_id)
        take = min(per_class, len(candidates))
        chosen.extend(candidates[:take].tolist())
    if len(chosen) < limit:
        remaining = [idx for idx in range(len(target_y)) if idx not in set(chosen)]
        chosen.extend(remaining[:limit - len(chosen)])
    return chosen[:limit]


def run(output_dir: Path, samples_per_task: int) -> dict:
    service = InferenceService(ROOT)
    status = service.models.load_all()
    if not status["all_loaded"]:
        raise RuntimeError(f"Not all formal model artifacts loaded: {status}")

    output_dir.mkdir(parents=True, exist_ok=True)
    detail_rows = []
    manifest_rows = []
    for task, spec in TASKS.items():
        dataset = ROOT / spec["dataset"]
        validation_npz = np.load(dataset / "val.npz", allow_pickle=False)
        saved_path = ROOT / spec["results"] / "val_predictions_all_models.csv"
        saved = pd.read_csv(saved_path, dtype={"record_id": str})
        saved = saved[saved["split"].eq("val")].copy()
        saved_by_key = {(str(row.sample_id), str(row.model)): row for row in saved.itertuples(index=False)}
        class_names = np.asarray(validation_npz["class_names"]).tolist()
        chosen = choose_rows(validation_npz, task, samples_per_task)
        for row_index in chosen:
            record_id = str(validation_npz["record_id"][row_index])
            sample = int(validation_npz["annotation_sample"][row_index])
            sample_id = str(validation_npz["sample_id"][row_index])
            expert = str(validation_npz["mapped_label"][row_index])
            beat = service.store.beat(record_id, sample, task)
            runtime_x = service.store.normalized_input(task, beat)
            saved_x = np.asarray(validation_npz["X"][row_index, 0], dtype=np.float32)
            max_abs_x_error = float(np.max(np.abs(runtime_x - saved_x)))
            manifest_rows.append({"task": task, "sample_id": sample_id, "record_id": record_id,
                                  "subject_id": str(validation_npz["subject_id"][row_index]),
                                  "annotation_sample": sample, "expert_label": expert,
                                  "max_abs_input_error": max_abs_x_error})
            if max_abs_x_error > 1e-5:
                raise AssertionError(f"Preprocessing mismatch for {task}/{sample_id}: {max_abs_x_error}")

            for model_id in MODEL_IDS:
                prediction = service.predict_beat(record_id, sample, task, model_id)
                reference = saved_by_key.get((sample_id, model_id))
                if reference is None:
                    raise AssertionError(f"Missing saved validation prediction {task}/{sample_id}/{model_id}")
                reference_prediction = str(reference.predicted_aami_label)
                reference_probabilities = {label: float(getattr(reference, f"probability_{label}")) for label in spec["labels"]}
                max_probability_error = max(abs(prediction["class_probabilities"][label] - reference_probabilities[label])
                                            for label in spec["labels"])
                prediction_matches = prediction["predicted_class"] == reference_prediction
                if not prediction_matches or max_probability_error > 1e-5:
                    raise AssertionError(
                        f"Prediction mismatch {task}/{sample_id}/{model_id}: "
                        f"class={prediction['predicted_class']} ref={reference_prediction}; "
                        f"probability error={max_probability_error}"
                    )
                detail_rows.append({"task": task, "sample_id": sample_id, "record_id": record_id,
                                    "subject_id": str(validation_npz["subject_id"][row_index]),
                                    "annotation_sample": sample, "expert_label": expert,
                                    "model_id": model_id, "api_prediction": prediction["predicted_class"],
                                    "saved_prediction": reference_prediction,
                                    "max_probability_error": max_probability_error,
                                    "max_abs_input_error": max_abs_x_error,
                                    "matched": True})

    detail = pd.DataFrame(detail_rows)
    manifest = pd.DataFrame(manifest_rows)
    detail.to_csv(output_dir / "validation_prediction_comparison.csv", index=False)
    manifest.to_csv(output_dir / "validation_sample_manifest.csv", index=False)
    summary = {
        "validation_only": True,
        "formal_test_data_read": False,
        "formal_test_data_used_for_tuning": False,
        "sample_count_by_task": manifest.groupby("task")["sample_id"].nunique().to_dict(),
        "prediction_comparisons": len(detail),
        "matched_prediction_count": int(detail["matched"].sum()),
        "preprocessing_max_abs_error": float(manifest["max_abs_input_error"].max()),
        "probability_max_abs_error": float(detail["max_probability_error"].max()),
        "model_hashes": [{"task": item["task"], "model_id": item["model_id"],
                          "sha256": item["model_sha256"]}
                         for item in service.models.status()["models"] if item.get("loaded")],
        "class_order_by_task": {task: spec["labels"] for task, spec in TASKS.items()},
    }
    (output_dir / "validation_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    return summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--samples-per-task", type=int, default=100)
    parser.add_argument("--output", type=Path, default=ROOT / "web/results/phase2_validation")
    args = parser.parse_args()
    if args.samples_per_task < 1:
        parser.error("--samples-per-task must be positive")
    print(json.dumps(run(args.output, args.samples_per_task), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
