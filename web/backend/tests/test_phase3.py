from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from web.backend.app import app
from web.backend.model_registry import ModelRegistry
from web.backend.research import research_data, gallery, figure_path


@pytest.fixture(scope="module")
def client(service):
    with TestClient(app) as instance:
        yield instance


@pytest.mark.parametrize("query,status", [
    ("record_id=999&start_sec=0&duration_sec=10", 404),
    ("record_id=200&start_sec=-1&duration_sec=10", 422),
    ("record_id=200&start_sec=1799&duration_sec=30", 422),
    ("record_id=200&start_sec=0&duration_sec=31", 422),
    ("record_id=200&start_sec=6&duration_sec=10&lead_name=BAD", 422),
])
def test_http_window_boundaries(client, query, status):
    response = client.get(f"/api/ecg/window?{query}")
    assert response.status_code == status
    assert response.json()["detail"]


def test_empty_prediction_segment(client):
    response = client.get("/api/ecg/playback/segment?record_id=200&start_sec=0&duration_sec=0.01&task=nv")
    assert response.status_code == 200
    assert response.json()["predicted_beat_count"] == 0


def test_missing_model_is_reported_without_modifying_artifacts(tmp_path):
    registry = ModelRegistry(tmp_path)
    status = registry.load_all()
    assert not status["all_loaded"]
    assert all(not row["loaded"] and "FileNotFoundError" in row["error"] for row in status["models"])
    with pytest.raises(RuntimeError, match="FileNotFoundError"):
        registry.predict("nv", "cnn_1d", [0] * 253)


def test_research_matches_final_counts_and_confusion():
    data = research_data()
    for metric in data["metrics"]:
        cells = [row for row in data["confusion"] if row["task"] == metric["task"] and row["model"] == metric["model"]]
        assert sum(int(row["count"]) for row in cells) == int(metric["n_test"])
        accuracy = sum(int(row["count"]) for row in cells if row["true_class"] == row["predicted_class"]) / int(metric["n_test"])
        assert accuracy == pytest.approx(float(metric["accuracy"]))
    assert sum(int(r["sample_count"]) for r in data["splits"] if r["dataset"] == "N/S/V/F") == 100115


def test_figure_and_report_allowlists(client):
    rows = gallery()
    assert rows and figure_path(rows[0]["id"]).is_file()
    assert client.get(rows[0]["url"]).headers["content-type"] == "image/png"
    assert client.get("/api/research/figures/unknown").status_code == 404
    assert client.get("/api/research/reports/unknown").status_code == 404
    assert client.get("/api/research/reports/final").status_code == 200


def test_phase4_error_drilldown_matches_saved_confusion(client):
    response = client.get("/api/research/errors?task=nsvf&model=cnn_1d&true_label=N&predicted_label=S")
    assert response.status_code == 200
    payload = response.json()
    assert payload["count"] == 2626
    assert len(payload["rows"]) == 20
    assert all(row["true_aami_label"] == "N" and row["predicted_aami_label"] == "S" for row in payload["rows"])
    row = payload["rows"][0]
    part = client.get(f"/api/research/errors?task=nsvf&model=cnn_1d&true_label=N&predicted_label=S&subject={row['subject_id']}").json()
    assert all(item["subject_id"] == row["subject_id"] for item in part["rows"])
    assert client.get("/api/research/errors?task=bad&model=cnn_1d&true_label=N&predicted_label=S").status_code == 422


def test_phase4_weight_details_are_existing_validation_rows():
    rows = [row for row in research_data()["weight_classes"] if row["split"] == "val"]
    assert len(rows) == 16
    for strategy in {row["strategy"] for row in rows}:
        selected = [row for row in rows if row["strategy"] == strategy]
        assert sum(int(row["support"]) for row in selected) == 14345


def test_phase4_thumbnail_preserves_original_and_aspect(client):
    from io import BytesIO
    from PIL import Image
    path = figure_path(gallery()[0]["id"])
    before = path.read_bytes()
    response = client.get(gallery()[0]["url"] + "?thumbnail=true")
    assert response.status_code == 200
    with Image.open(BytesIO(response.content)) as preview, Image.open(path) as original:
        assert preview.width <= 640 and preview.height <= 440
        assert preview.width / preview.height == pytest.approx(original.width / original.height, rel=.01)
    assert path.read_bytes() == before
