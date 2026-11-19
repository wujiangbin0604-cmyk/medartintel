"""Recompute saved results and scalers from the actual fold artifacts."""
import json
from pathlib import Path
import numpy as np
from research_extensions.rhythm_fusion.src.data import BASE, load, fit_scaler
from research_extensions.rhythm_fusion.src.run import score
from research_extensions.protect import sha256


def test_every_completed_job_metric_matches_real_probabilities():
    d=load()
    folders=[p for p in (BASE/"results").iterdir() if (p/"COMPLETED.json").is_file() and not p.name.startswith("smoke")]
    assert folders
    for folder in folders:
        config=json.loads((folder/"fingerprint.json").read_text())["config"]
        results=list(folder.glob("fold*/seed*/A*/result.json"))
        assert len(results)==5*len(config["seeds"])*4
        for path in results:
            result=json.loads(path.read_text())
            assert sha256(path.with_name("best.pt"))==result["checkpoint_sha256"]
            with np.load(path.with_name("predictions.npz")) as p:
                ix,prob=p["eval_indices"],p["eval_probability"]
                assert np.isfinite(prob).all() and np.allclose(prob.sum(1),1,atol=1e-5)
                actual=score(d["label"][ix],prob,d["subject_group"][ix],result["classes"])
            assert actual==result["evaluation"]
            groups=[set(part["subjects"]) for part in result["partitions"].values()]
            assert all(not a&b for i,a in enumerate(groups) for b in groups[i+1:])


def test_saved_scaler_fitted_on_inner_training_patients_only():
    import torch
    d=load()
    folder=BASE/"results/cv_cpu_v1"
    parts=json.loads((folder/"folds.json").read_text())
    for fold in range(5):
        indices=np.array(parts[fold]["fit"]["indices"])
        expected=fit_scaler(d["waveform"][indices],d["rhythm_features"][indices],d["rhythm_valid_mask"][indices],d["sample_id"][indices])
        bundle=torch.load(folder/f"fold{fold}/seed20261118/A2/best.pt",map_location="cpu",weights_only=True)
        assert bundle["scaler"]==expected


def test_components_preserve_same_folds_and_distinct_seeds():
    s=json.loads((BASE/"results/cv_cpu_v1/summary.json").read_text())
    if "components" not in s:
        assert s["config"]["seeds"]==[20261118]
        return
    assert s["config"]["seeds"]==[20261118,20261119,20261120]
    assert len(s["folds"])==60 and s["unexecuted_seeds"]==[]
    registries=json.loads((BASE/"results/cv_cpu_v1/model_registry.json").read_text())["models"]
    assert len(registries)==60 and len({(r["seed"],r["fold"],r["model"]) for r in registries})==60
    assert s["components"][0]["fold_manifest_sha256"]==s["components"][1]["fold_manifest_sha256"]
