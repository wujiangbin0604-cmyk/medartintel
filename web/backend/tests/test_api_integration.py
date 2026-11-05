import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from web.backend.app import infer_beat, playback_segment, record_detail
from web.backend.schemas import BeatRequest


def test_real_records_waveform_and_annotations(service):
    summaries = service.store.records()
    selected = next(item for item in summaries if item["record_id"] == "200")
    assert selected["model_inference_available"] is True
    assert "MLII" in selected["signal_names"]
    assert selected["sample_count"] > 100_000

    waveform = service.store.window("200", 6.0, 10.0, "MLII")
    marks = service.store.annotations("200", 6.0, 10.0, "nv")
    assert waveform["unit"] == "mV"
    assert waveform["point_count"] == 3600
    assert marks and all(6.0 <= item["time_seconds"] < 16.0 for item in marks)


def test_saved_models_compare_the_same_real_beat(service, record_200_sample):
    result = service.compare("200", record_200_sample, "nv")
    assert [item["model_id"] for item in result["models"]] == [
        "logistic_regression", "random_forest", "cnn_1d"
    ]
    assert len({item["annotation_sample"] for item in result["models"]}) == 1
    for item in result["models"]:
        assert set(item["class_probabilities"]) == {"N", "V"}
        assert abs(sum(item["class_probabilities"].values()) - 1.0) < 1e-5
        assert item["model_sha256"]


def test_expert_label_is_not_a_model_input(service, record_200_sample):
    beat = service.store.beat("200", record_200_sample, "nv")
    assert beat["normalized_model_input"] is None
    normalized = service.store.normalized_input("nv", beat)
    assert normalized.shape == (253,)
    assert normalized.dtype.name == "float32"


def test_invalid_record_and_out_of_task_label_return_clear_errors(record_200_s_sample):
    with pytest.raises(HTTPException) as missing:
        record_detail("999")
    assert missing.value.status_code == 404
    payload = BeatRequest(record_id="200", annotation_sample=record_200_s_sample,
                          task="nv", model_id="cnn_1d")
    with pytest.raises(HTTPException) as out_of_task:
        infer_beat(payload)
    assert out_of_task.value.status_code == 409
    assert "超出当前任务" in out_of_task.value.detail
    with pytest.raises(ValidationError):
        BeatRequest(record_id="2000", annotation_sample=record_200_s_sample,
                    task="nv", model_id="cnn_1d")


def test_playback_returns_batch_predictions_for_a_real_segment(service, record_200_sample):
    sample_time = record_200_sample / service.store.get_record("200").fs
    start = max(5.0, sample_time - 0.5)
    payload = playback_segment(record_id="200", start_sec=start, duration_sec=3,
                               task="nv", model_ids=["cnn_1d"], lead_name="MLII")
    assert payload["historical_recording"] is True
    assert payload["real_time_monitoring"] is False
    assert payload["waveform"]["record_id"] == "200"
    assert payload["prediction_model_rows"] == payload["predicted_beat_count"]


def test_playback_preserves_beats_rejected_by_filter_guard(service):
    payload = playback_segment(record_id="200", start_sec=0, duration_sec=10,
                               task="nv", model_ids=["cnn_1d"], lead_name="MLII")
    assert payload["expert_beat_count"] > payload["predicted_beat_count"]
    assert payload["prediction_model_rows"] == payload["predicted_beat_count"]
    rejected = [item for item in payload["annotations"] if item.get("prediction_unavailable_reason")]
    assert rejected
    assert all(item["predictions"] == [] for item in rejected)
