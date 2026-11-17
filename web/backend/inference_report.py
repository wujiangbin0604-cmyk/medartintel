"""Build a downloadable analysis snapshot from current real inference outputs."""
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from .model_registry import TASKS, file_sha256


def build_analysis_report(service, root: Path, record_id: str, sample: int, task: str, selected_model: str) -> dict:
    comparison = service.compare(record_id, sample, task)
    beat = service.store.beat(record_id, sample, task)
    selected = next(row for row in comparison["models"] if row["model_id"] == selected_model)
    dataset = root / TASKS[task]["dataset"]
    return {
        "schema_version": 1,
        "generated_at_Asia_Shanghai": datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(),
        "filename": f"ECG-AI_{record_id}_{sample}_{task}_analysis.json",
        "selected_model_id": selected_model,
        "selected_prediction": selected,
        "expert_reference": {"source": "MIT-BIH expert .atr annotation", "original_label": beat["original_label"],
                             "aami_label": beat["aami_label"], "used_as_model_feature": False},
        "beat": beat,
        "comparison": comparison,
        "disagreements_with_expert": [row["model_id"] for row in comparison["models"] if not row["prediction_matches_expert"]],
        "provenance": {
            "raw_files_sha256": {ext: file_sha256(root / "data/mitdb" / f"{record_id}.{ext}") for ext in ("dat", "hea", "atr")},
            "normalization_sha256": file_sha256(dataset / "normalization.json"),
            "processing_config_sha256": file_sha256(dataset / "processing_config.json"),
            "normalization_fit_split": "train",
            "model_artifacts": "Original six frozen project models; new research candidates are not deployed here.",
        },
        "limitations": [
            "This is a retrospective annotated beat, not automatic detection on unannotated ECG.",
            "Bidirectional filtering uses future signal context; historical playback is not live monitoring.",
            "Class probabilities are model outputs and are not clinically calibrated diagnostic probabilities.",
            "Agreement with one expert annotation is not population-level model accuracy or clinical validation.",
        ],
    }
