"""Verify copied artifacts and real API behavior without training a model."""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from urllib.request import Request, urlopen
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))


def verify_files():
    manifest = json.loads((ROOT / "deploy/ubuntu22/bundle_manifest.json").read_text(encoding="utf-8"))
    for entry in manifest["files"]:
        path = (ROOT / entry["path"]).resolve()
        if not path.is_relative_to(ROOT) or not path.is_file():
            raise RuntimeError(f"Missing/invalid artifact: {entry['path']}")
        if hashlib.sha256(path.read_bytes()).hexdigest() != entry["sha256"]:
            raise RuntimeError(f"SHA256 mismatch: {entry['path']}")
    return {"verified_files": len(manifest["files"]), "source_records": manifest["record_count"],
            "game_levels": manifest["game_levels"], "frontend_built": (ROOT / "web/frontend/dist/index.html").is_file()}


def api_json(base, path, payload=None):
    body = None if payload is None else json.dumps(payload).encode()
    req = Request(base.rstrip("/") + path, data=body, headers={"Content-Type": "application/json"})
    with urlopen(req, timeout=60) as response:
        return json.load(response)


def verify_rhythm_artifacts():
    """Check all research models and provenance without needing processed NPZ arrays."""
    base = ROOT / "research_extensions/rhythm_fusion"
    result_dir = base / "results/cv_cpu_v1"
    summary = json.loads((result_dir / "summary.json").read_text(encoding="utf-8"))
    registry = json.loads((result_dir / "model_registry.json").read_text(encoding="utf-8"))["models"]
    uncertainty = json.loads((ROOT / "research_extensions/uncertainty/results/cv_cpu_v1/summary.json").read_text(encoding="utf-8"))
    if summary["status"] != "completed" or len(summary["folds"]) != 60 or len(registry) != 60:
        raise RuntimeError("Incomplete rhythm-fusion research artifacts")
    from research_extensions.rhythm_fusion.src.models import make_model
    import torch
    for entry in registry:
        path = (base / entry["checkpoint"]).resolve()
        if not path.is_relative_to(base) or hashlib.sha256(path.read_bytes()).hexdigest() != entry["sha256"]:
            raise RuntimeError("Missing or changed research checkpoint: " + entry["checkpoint"])
        bundle = torch.load(path, map_location="cpu", weights_only=True)
        model = make_model(entry["model"], 4)
        model.load_state_dict(bundle["state_dict"], strict=True)
        if bundle["classes"] != ["N", "S", "V", "F"] or len(bundle["scaler"]["rhythm_median"]) != 7:
            raise RuntimeError("Research model/scaler schema mismatch")
    if uncertainty["status"] != "completed" or len(uncertainty["results"]) != 24 or len(uncertainty["thresholds"]) != 120:
        raise RuntimeError("Incomplete uncertainty artifacts")
    for policy in uncertainty["thresholds"]:
        if set(policy["calibration_subjects"]) & set(policy["evaluation_subjects"]):
            raise RuntimeError("Calibration/evaluation patient overlap")
    if not (base / "data/alignment.csv").is_file():
        raise RuntimeError("Missing teaching sample alignment")
    return {"research_checkpoints": len(registry), "research_jobs": len(summary["folds"]),
            "research_seeds": summary["config"]["seeds"], "uncertainty_thresholds": len(uncertainty["thresholds"])}


def verify_api(base):
    health = api_json(base, "/api/health")
    assert health["status"] == "ok" and health["models_loaded"] == health["models_total"] == 6, health
    summary = api_json(base, "/api/research/summary")
    assert summary["metrics"] and summary["splits"] and summary["histories"]
    records = api_json(base, "/api/ecg/records")
    assert records["count"] == 48
    gallery = api_json(base, "/api/research/gallery")
    assert gallery["figures"]
    with urlopen(base.rstrip("/") + gallery["figures"][0]["url"], timeout=30) as response:
        assert response.headers.get_content_type() == "image/png"
    for route in ("/dashboard", "/ai-detection", "/ai-inference", "/interactive-lab/heartbeat-hunter", "/rhythm-lab"):
        with urlopen(base.rstrip("/") + route, timeout=30) as response:
            assert response.status == 200 and b"<html" in response.read().lower()
    config = api_json(base, "/api/games/heartbeat-hunter/config")
    player = str(uuid4())
    session = api_json(base, "/api/games/heartbeat-hunter/start", {"player_id": player, "difficulty": "beginner"})
    assert len(session["signal"]) == 3600 and "result" not in session and "answers" not in session
    # Reveal answers only by normal submission, then run all original models on one real beat.
    finished = api_json(base, "/api/games/heartbeat-hunter/submit", {"session_id": session["session_id"], "samples": []})
    chosen = next(a for a in finished["result"]["answers"] if a["label"] == "V")
    compared = api_json(base, "/api/inference/compare", {"record_id": session["record_id"], "annotation_sample": chosen["sample"], "task": "nv"})
    assert len(compared["models"]) == 3
    reference = json.loads((ROOT / "deploy/ubuntu22/reference_predictions.json").read_text(encoding="utf-8"))
    checked = 0
    for example in reference["examples"]:
        actual = api_json(base, "/api/inference/compare", {k: example[k] for k in ("record_id", "annotation_sample", "task")})
        by_model = {p["model_id"]: p for p in actual["models"]}
        for expected in example["models"]:
            prediction = by_model[expected["model_id"]]
            assert prediction["predicted_class"] == expected["predicted_class"], (example, prediction)
            error = max(abs(prediction["class_probabilities"][label] - value) for label, value in expected["class_probabilities"].items())
            assert error <= reference["probability_tolerance"], f"Model probability drift: {example['task']}/{expected['model_id']}: {error}"
            checked += 1
    rhythm = api_json(base, "/api/rhythm/summary")
    assert rhythm["status"] == "completed" and len(rhythm["folds"]) == 60
    assert rhythm["config"]["seeds"] == [20261118, 20261119, 20261120]
    assert len(rhythm["uncertainty"]["results"]) == 24
    candidates = api_json(base, "/api/rhythm/samples?label=S")["samples"]
    example = next(row for row in candidates if row["record_id"] == "100")
    analysis = api_json(base, f"/api/rhythm/beat?record_id={example['record_id']}&annotation_sample={example['annotation_sample']}")
    assert analysis["research_available"] and {m["model"] for m in analysis["models"]} == {"A0", "A2"}
    assert all(len(m["policies"]) == 2 and m["sha256"] for m in analysis["models"])
    return {"api": base, "loaded_models": 6, "records": records["count"], "game_levels": config["level_count"],
            "real_ecg_samples": len(session["signal"]), "real_model_comparison": len(compared["models"]),
            "reference_predictions_matched": checked, "rhythm_jobs": 60, "uncertainty_results": 24,
            "research_real_beat_predictions": len(analysis["models"]),
            "research_gallery": len(gallery["figures"]), "note": "Smoke test uses an isolated anonymous player; no training."}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--files-only", action="store_true")
    parser.add_argument("--api", help="Running service URL, e.g. http://127.0.0.1:8000")
    args = parser.parse_args()
    result = verify_files()
    result.update(verify_rhythm_artifacts())
    if args.api:
        result.update(verify_api(args.api))
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
