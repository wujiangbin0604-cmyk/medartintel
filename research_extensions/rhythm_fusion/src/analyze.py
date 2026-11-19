"""Generate metrics from every completed outer fold, never cherry-pick a fold."""
import argparse
import json
from pathlib import Path
import numpy as np
import pandas as pd
from .data import BASE, load
from .run import score, write


def analyze(run_id="cv_cpu_v1"):
    folder = BASE / "results" / run_id
    completion = json.loads((folder / "COMPLETED.json").read_text())
    assert completion["status"] == "completed" and not completion["smoke"]
    fingerprint = json.loads((folder / "fingerprint.json").read_text())
    config = fingerprint["config"]
    data = load()
    if config["task"] == "nv":
        keep = np.isin(data["label"], [0,2])
        data = {k:v[keep] for k,v in data.items()}
        data["label"] = (data["label"] == 2).astype(np.int64)
    y, groups = data["label"], data["subject_group"]
    classes = ["N", "V"] if config["task"] == "nv" else ["N", "S", "V", "F"]
    rows, patients, per_class, summaries, transitions = [], [], [], [], []
    registry = []
    for seed in config["seeds"]:
        probabilities = {}
        for name in config["models"]:
            oof = np.full((len(y),len(classes)), np.nan, np.float32)
            seen = np.zeros(len(y), dtype=int)
            fold_rows = []
            for fold in range(config["outer_folds"]):
                path = folder / f"fold{fold}/seed{seed}/{name}"
                result = json.loads((path / "result.json").read_text())
                assert result["status"] == "completed" and not result["smoke"]
                with np.load(path / "predictions.npz") as p:
                    ix, prob = p["eval_indices"], p["eval_probability"]
                    oof[ix] = prob
                    seen[ix] += 1
                row = {"model": name, "seed": seed, "fold": fold,
                       **{k:result["evaluation"][k] for k in ["macro_f1", "accuracy", "balanced_accuracy", "subject_count", "sample_count"]},
                       "parameters": result["parameter_count"], "best_epoch": result["best_epoch"],
                       "latency_ms": result["latency_ms_median"], "fit_seconds": result["fit_seconds"],
                       "per_class": result["evaluation"]["per_class"], "confusion_matrix": result["evaluation"]["confusion_matrix"]}
                rows.append(row)
                fold_rows.append(row)
                registry.append({"model":name, "seed":seed, "fold":fold, "checkpoint":str((path / "best.pt").relative_to(BASE)),
                                 "sha256":result["checkpoint_sha256"],
                                 "evaluation_subjects":result["partitions"]["evaluation"]["subjects"]})
            assert np.all(seen == 1) and np.isfinite(oof).all()
            pooled = score(y, oof, groups, classes)
            for label, value in pooled["per_class"].items():
                per_class.append({"model":name,"seed":seed,"class":label,**value})
            for subject in sorted(set(groups)):
                ix = groups == subject
                metric = score(y[ix], oof[ix], groups[ix], classes)
                patients.append({"model":name,"seed":seed,"subject":subject,**metric})
            summaries.append({"model":name,"seed":seed,"pooled":pooled,
                              "fold_mean_macro_f1":float(np.mean([r["macro_f1"] for r in fold_rows])),
                              "fold_sd_macro_f1":float(np.std([r["macro_f1"] for r in fold_rows],ddof=1)),
                              "parameters":fold_rows[0]["parameters"],"latency_ms":float(np.median([r["latency_ms"] for r in fold_rows]))})
            probabilities[name] = oof
            np.savez_compressed(folder / f"oof_{name}_seed{seed}.npz", probability=oof, label=y,
                                subject_group=groups, sample_id=data["sample_id"])
        a, b = probabilities["A0"].argmax(1) == y, probabilities["A2"].argmax(1) == y
        for subject in sorted(set(groups)):
            ix = groups == subject
            transitions.append({"seed":seed,"subject":subject,"both_correct":int((ix&a&b).sum()),
                                "corrected_by_fusion":int((ix&~a&b).sum()),"new_errors_with_fusion":int((ix&a&~b).sum()),
                                "both_wrong":int((ix&~a&~b).sum()),
                                "delta_macro_f1":score(y[ix],probabilities["A2"][ix],groups[ix],classes)["macro_f1"]-score(y[ix],probabilities["A0"][ix],groups[ix],classes)["macro_f1"]})
        # Paired patient bootstrap; bootstrap subjects, retain all their beats together.
        rng = np.random.default_rng(20261118)
        subjects = sorted(set(groups))
        cms = {name:np.array([score(y[groups==g],p[groups==g],groups[groups==g],classes)["confusion_matrix"] for g in subjects])
               for name,p in probabilities.items() if name in ["A0","A2"]}
        deltas = []
        def macro(cm):
            return np.mean(np.divide(2*np.diag(cm),cm.sum(0)+cm.sum(1),out=np.zeros(len(classes)),where=(cm.sum(0)+cm.sum(1))>0))
        for _ in range(1000):
            draws = rng.integers(0,len(subjects),size=len(subjects))
            deltas.append(macro(cms["A2"][draws].sum(0))-macro(cms["A0"][draws].sum(0)))
        write(folder / f"bootstrap_seed{seed}.json", {"seed":seed,"unit":"patient group, paired OOF predictions, 1000 draws",
              "delta_macro_f1_percentile_95":np.quantile(deltas,[.025,.975]).tolist(),
              "limit":"Descriptive resampling of 37 development patients with dependent fitted folds; not an external-validation CI or independent-beat significance test"})
    summary = {"status":"completed","experiment_id":run_id,"task":config["task"],"config":config,
               "evaluation_scope":"retrospective original train+val only; each patient outer-held-out exactly once per seed",
               "classes":classes,"sample_count":len(y),"subject_count":len(set(groups)),
               "models":summaries,"folds":rows,"patients":patients,"per_class":per_class,
               "error_transitions":transitions,"source":f"research_extensions/rhythm_fusion/results/{run_id}",
               "unexecuted_seeds":sorted(set(config["planned_seeds"])-set(config["seeds"])),
               "nv_status":"not_run" if config["task"]!="nv" else "completed"}
    write(folder / "summary.json",summary)
    write(folder / "model_registry.json", {"experiment_id":run_id,"models":registry,"selection":"use fold held out for requested patient's group; fixed first seed for demonstration, no refit or best-fold selection"})
    pd.DataFrame([{k:v for k,v in r.items() if k not in ["per_class","confusion_matrix"]} for r in rows]).to_csv(folder / "fold_metrics.csv",index=False)
    pd.DataFrame(per_class).to_csv(folder / "per_class.csv",index=False)
    pd.DataFrame(transitions).to_csv(folder / "error_transitions.csv",index=False)
    print(json.dumps({"models":[{"model":m["model"],"f1":m["pooled"]["macro_f1"],"fold_mean":m["fold_mean_macro_f1"]} for m in summaries]},indent=2))
    return summary


if __name__ == "__main__":
    p=argparse.ArgumentParser();p.add_argument("--run",default="cv_cpu_v1")
    analyze(p.parse_args().run)
