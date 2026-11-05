"""Export a tiny, read-only inference reference for cross-platform deployment checks."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

import numpy as np
from web.backend.ecg_service import InferenceService
from web.backend.model_registry import TASKS


def main():
    service = InferenceService(ROOT)
    assert service.models.load_all()["all_loaded"]
    references = []
    for task, spec in TASKS.items():
        with np.load(ROOT / spec["dataset"] / "val.npz", allow_pickle=False) as data:
            for label in spec["labels"]:
                index = int(np.flatnonzero(data["mapped_label"] == label)[0])
                record = str(data["record_id"][index]); sample = int(data["annotation_sample"][index])
                response = service.compare(record, sample, task)
                references.append({"record_id": record, "annotation_sample": sample, "task": task, "expert_label": label,
                                   "models": [{"model_id": p["model_id"], "predicted_class": p["predicted_class"],
                                               "class_probabilities": p["class_probabilities"]} for p in response["models"]]})
    output = {"source": "Existing validation examples; no fitting/training", "probability_tolerance": 1e-5, "examples": references}
    Path(__file__).with_name("reference_predictions.json").write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"reference_beats": len(references), "reference_predictions": sum(len(r["models"]) for r in references)}))


if __name__ == "__main__": main()
