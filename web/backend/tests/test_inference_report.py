from pathlib import Path

import pytest
from fastapi import HTTPException

from web.backend.app import analysis_report
from web.backend.schemas import BeatRequest
from web.backend.model_registry import file_sha256


def test_report_contains_real_current_predictions_and_source_hashes(service, record_200_sample):
    report = analysis_report(BeatRequest(record_id="200", annotation_sample=record_200_sample,
                                        task="nv", model_id="cnn_1d"))
    direct = service.predict_beat("200", record_200_sample, "nv", "cnn_1d")
    assert report["selected_prediction"]["predicted_class"] == direct["predicted_class"]
    assert report["selected_prediction"]["model_sha256"] == direct["model_sha256"]
    assert report["selected_prediction"]["class_probabilities"] == direct["class_probabilities"]
    assert len(report["comparison"]["models"]) == 3
    assert len(report["beat"]["filtered_amplitude_mv"]) == 253
    assert report["expert_reference"]["used_as_model_feature"] is False
    assert report["provenance"]["normalization_fit_split"] == "train"
    root = Path(__file__).resolve().parents[3]
    assert report["provenance"]["raw_files_sha256"]["atr"] == file_sha256(root / "data/mitdb/200.atr")
    assert report["disagreements_with_expert"] == [r["model_id"] for r in report["comparison"]["models"] if not r["prediction_matches_expert"]]


def test_report_rejects_labels_outside_the_selected_task(service, record_200_s_sample):
    with pytest.raises(HTTPException) as error:
        analysis_report(BeatRequest(record_id="200", annotation_sample=record_200_s_sample,
                                    task="nv", model_id="cnn_1d"))
    assert error.value.status_code == 409


def test_report_rejects_unknown_records(service):
    with pytest.raises(HTTPException) as error:
        analysis_report(BeatRequest(record_id="999", annotation_sample=2000,
                                    task="nv", model_id="cnn_1d"))
    assert error.value.status_code == 404
