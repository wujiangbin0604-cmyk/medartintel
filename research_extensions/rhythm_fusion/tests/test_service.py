import json
import numpy as np
import torch
from fastapi.testclient import TestClient
from web.backend.app import app
from research_extensions.rhythm_fusion.src.data import load, BASE, transform
from research_extensions.rhythm_fusion.src.models import forward
from research_extensions.rhythm_fusion.src.artifact_paths import artifact_path
from web.backend.rhythm_lab import load_bundle

torch.set_num_threads(2)


def test_registry_api_and_real_checkpoint_predictions():
    client=TestClient(app)
    response=client.get("/api/rhythm/summary")
    assert response.status_code==200
    summary=response.json()
    assert summary["status"]=="completed" and len(summary["folds"])==5*4*len(summary["config"]["seeds"])
    data=load()
    registry=json.loads((BASE/"results/cv_cpu_v1/model_registry.json").read_text())
    entry=next(r for r in registry["models"] if r["model"]=="A2")
    subject=entry["evaluation_subjects"][0]
    ix=int(np.flatnonzero(data["subject_group"]==subject)[0])
    rid=str(data["record_id"][ix]);sample=int(data["annotation_sample"][ix])
    result=client.get("/api/rhythm/beat",params={"record_id":rid,"annotation_sample":sample})
    assert result.status_code==200,result.text
    result=result.json()
    assert result["research_available"]
    a2=next(r for r in result["models"] if r["model"]=="A2")
    assert a2["sha256"]==entry["sha256"] and a2["fold"]==entry["fold"]
    model,bundle=load_bundle(str(artifact_path(BASE,entry["checkpoint"])),entry["sha256"])
    x,r=transform(data["waveform"][ix:ix+1],data["rhythm_features"][ix:ix+1],data["rhythm_valid_mask"][ix:ix+1],bundle["scaler"])
    with torch.inference_mode():p=forward(model,"A2",torch.from_numpy(x),torch.from_numpy(r)).softmax(1).numpy()[0]
    np.testing.assert_allclose(list(a2["probabilities"].values()),p,rtol=1e-5,atol=1e-6)
    path=BASE/"results/cv_cpu_v1"/f"fold{entry['fold']}/seed{entry['seed']}/A2/predictions.npz"
    with np.load(path) as saved:
        row=np.flatnonzero(saved["eval_indices"]==ix)[0]
        np.testing.assert_allclose(p,saved["eval_probability"][row],rtol=1e-4,atol=1e-6)
    for policy in a2["policies"]:
        assert subject not in policy["calibration_subjects"]
        assert policy["predictions_sha256"]


def test_api_missing_history_and_invalid_input_are_safe():
    client=TestClient(app)
    # Second expert beat: one current RR, no preceding RR history, inside the filter guard.
    result=client.get("/api/rhythm/beat?record_id=100&annotation_sample=370")
    assert result.status_code==200
    d=result.json();assert not d["research_available"] and d["rhythm_missing_reason"]
    assert d["rhythm_valid_mask"]==[1.,0.,0.,0.,0.,0.,0.]
    assert client.get("/api/rhythm/beat?record_id=../../x&annotation_sample=1").status_code==422
    assert client.get("/api/rhythm/beat?record_id=200&annotation_sample=-1").status_code==422
    assert client.get("/api/rhythm/samples?label=F").json()["samples"]


def test_no_new_inference_on_original_test_patient():
    client=TestClient(app)
    import wfdb
    from research_extensions.rhythm_fusion.src.data import ROOT
    ann=wfdb.rdann(str(ROOT/"data/mitdb/208"),"atr")
    sample=next(int(s) for s,l in zip(ann.sample,ann.symbol) if s>2200 and l in ["N","V","F"])
    result=client.get("/api/rhythm/beat",params={"record_id":"208","annotation_sample":sample})
    assert result.status_code==200
    d=result.json()
    assert not d["research_available"] and not d["models"] and d["original_cnn"] is None
    assert "隔离" in d["unavailable_reason"]


def test_threshold_audit_and_evaluation_separation():
    summary=json.loads((BASE.parent/"uncertainty/results/cv_cpu_v1/summary.json").read_text())
    assert len(summary["thresholds"])%40==0 and len(summary["thresholds"])>=40
    for t in summary["thresholds"]:
        assert not set(t["calibration_subjects"]) & set(t["evaluation_subjects"])
    for r in summary["results"]:
        assert r["accepted"]+r["rejected"]==r["total"]==86286


def test_api_exposes_real_results_not_mock_numbers():
    summary=TestClient(app).get("/api/rhythm/summary").json()
    stored=json.loads((BASE/"results/cv_cpu_v1/summary.json").read_text())
    assert summary["models"]==stored["models"]
    assert summary["per_class"]==stored["per_class"]
