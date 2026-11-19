"""Fixed calibration thresholds; outer evaluation patients never select thresholds."""
import json
from pathlib import Path
import numpy as np
from sklearn.metrics import roc_auc_score
from research_extensions.rhythm_fusion.src.data import BASE, load
from research_extensions.rhythm_fusion.src.run import write, score
from research_extensions.protect import sha256

OUT = BASE.parent / "uncertainty/results"


def uncertainty(probability, method):
    p = np.asarray(probability, dtype=np.float64)
    if p.ndim != 2 or not np.isfinite(p).all() or (p < 0).any() or not np.allclose(p.sum(1), 1, atol=1e-5):
        raise ValueError("Expected normalized finite probability rows")
    if method == "max_score":
        return 1-p.max(1)
    if method == "entropy":
        return -(p*np.log(np.maximum(p, 1e-12))).sum(1)
    raise ValueError(method)


def policy(calibration_p, method, coverage=.90):
    if not 0 < coverage <= 1 or not len(calibration_p):
        raise ValueError("Nonempty calibration and coverage in (0,1] required")
    return float(np.quantile(uncertainty(calibration_p,method),coverage,method="higher"))


def selective_metrics(y, probability, groups, accepted, classes):
    pred = probability.argmax(1)
    error = pred != y
    count, kept = len(y), int(accepted.sum())
    rejected = ~accepted
    metrics = {"total":count,"accepted":kept,"rejected":int(rejected.sum()),"coverage":kept/count,
               "rejection_rate":float(rejected.mean()),"all_error_rate":float(error.mean()),
               "accepted_error_rate":float(error[accepted].mean()) if kept else None,
               "rejected_error_rate":float(error[rejected].mean()) if rejected.any() else None,
               "per_class":{},"patients":[]}
    for i,c in enumerate(classes):
        truth = y==i
        tp = int((truth & (pred==i) & accepted).sum())
        predicted = int(((pred==i)&accepted).sum())
        retained_true = int((truth&accepted).sum())
        support = int(truth.sum())
        metrics["per_class"][c] = {"support_all":support,"accepted_true":retained_true,"accepted_predicted":predicted,
            "subject_count":len(set(groups[truth])),"acceptance_rate":retained_true/support if support else None,
            "precision_retained":tp/predicted if predicted else 0.,
            "recall_retained_denominator":tp/retained_true if retained_true else 0.,
            "recall_all_denominator":tp/support if support else 0.}
    for g in sorted(set(groups)):
        ix=groups==g
        metrics["patients"].append({"subject":g,"samples":int(ix.sum()),"rejection_rate":float(rejected[ix].mean()),
                                    "errors_all":int(error[ix].sum()),"accepted":int(accepted[ix].sum())})
    return metrics


def evaluate(run_id="cv_cpu_v1"):
    folder=BASE / "results" / run_id
    # Stage B is gated on completed and independently aggregated Stage A evidence.
    summary=json.loads((folder / "summary.json").read_text(encoding="utf-8"))
    assert summary["status"]=="completed" and len(summary["folds"])==summary["config"]["outer_folds"]*len(summary["config"]["models"])*len(summary["config"]["seeds"])
    d=load(); y=d["label"]; groups=d["subject_group"]
    assert summary["task"]=="nsvf"
    registry=json.loads((folder/"model_registry.json").read_text(encoding="utf-8"))["models"]
    results=[];thresholds=[];curves=[]
    # All four prespecified models reported, no best-outer-model selection.
    for seed in summary["config"]["seeds"]:
        for name in summary["config"]["models"]:
            for method in ["max_score","entropy"]:
                p_all=np.full((len(y),4),np.nan)
                accepted=np.zeros(len(y),bool)
                all_u=np.zeros(len(y))
                for fold in range(summary["config"]["outer_folds"]):
                    entry=next(r for r in registry if r["fold"]==fold and r["seed"]==seed and r["model"]==name)
                    path=(BASE/entry["checkpoint"]).with_name("predictions.npz")
                    with np.load(path) as z:
                        e,c=z["eval_indices"],z["calibration_indices"]
                        ep,cp=z["eval_probability"],z["calibration_probability"]
                        assert not set(groups[e]) & set(groups[c])
                        t=policy(cp,method)
                        accepted[e]=uncertainty(ep,method)<=t
                        p_all[e]=ep
                        all_u[e]=uncertainty(ep,method)
                        thresholds.append({"model":name,"seed":seed,"fold":fold,"method":method,"threshold":t,
                            "target_calibration_coverage":.90,"accept_if":"uncertainty <= threshold",
                            "calibration_subjects":sorted(set(groups[c])),"evaluation_subjects":sorted(set(groups[e])),
                            "calibration_samples":len(c),"predictions_sha256":sha256(path),
                            "rule":"quantile(method=higher); uses calibration scores only, no calibration labels"})
                        error=ep.argmax(1)!=y[e]
                        # Descriptive threshold sweep only. Never used to choose the deployed threshold.
                        u=uncertainty(ep,method)
                        for coverage in [.1,.2,.3,.4,.5,.6,.7,.8,.9,1.]:
                            threshold=float(np.quantile(u,coverage,method="higher"))
                            kept=u<=threshold
                            curves.append({"model":name,"seed":seed,"fold":fold,"method":method,"nominal_coverage":coverage,
                                           "coverage":float(kept.mean()),"risk":float(error[kept].mean()),"accepted":int(kept.sum()),
                                           "scope":"outer descriptive score sweep; ties retained; not a threshold-selection result"})
                metrics=selective_metrics(y,p_all,groups,accepted,summary["classes"])
                error=p_all.argmax(1)!=y
                metrics["error_detection_auroc"]=float(roc_auc_score(error,all_u)) if len(np.unique(error))==2 else None
                results.append({"model":name,"seed":seed,"method":method,**metrics})
    value={"status":"completed","run":run_id,"selection":"all four prespecified models, no selection by outer score",
           "thresholds":thresholds,"results":results,"risk_coverage":curves,
           "note":"Softmax and entropy are uncalibrated proxies, not clinical risk or probability of correctness. Target 90% calibration coverage is not guaranteed on new patients."}
    write(OUT/run_id/"summary.json",value)
    print(json.dumps({"results":[{k:r[k] for k in ["model","method","coverage","accepted_error_rate","rejected_error_rate","error_detection_auroc"]} for r in results]},indent=2))
    return value


if __name__=="__main__":
    evaluate()
