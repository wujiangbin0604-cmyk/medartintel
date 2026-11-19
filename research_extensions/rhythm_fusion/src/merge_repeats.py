"""Merge completed prespecified seeds, preserving each component's provenance."""
import json
from .data import BASE
from .run import write
from research_extensions.protect import sha256


def merge():
    components=["cv_cpu_v1","cv_cpu_repeats_v1"]
    summary_paths=[BASE/f"results/{name}/summary.json" for name in components]
    values=[json.loads(p.read_text(encoding="utf-8")) for p in summary_paths]
    original=values[0]
    # Preserve the single-seed aggregation before publishing the complete-seed aggregation.
    single=BASE/"results/cv_cpu_v1/summary_single_seed.json"
    if not single.exists():write(single,original)
    else:original=json.loads(single.read_text(encoding="utf-8"));values[0]=original
    for value in values:
        assert value["status"]=="completed"
        for key in ["task","sample_count","subject_count","classes"]:assert value[key]==original[key]
        for key in ["epochs","patience","batch_size","learning_rate","weight_decay","threads","fold_seed","outer_folds","inner_folds","class_weight"]:
            assert value["config"][key]==original["config"][key]
    first_folds=json.loads((BASE/"results/cv_cpu_v1/folds.json").read_text())
    repeat_folds=json.loads((BASE/"results/cv_cpu_repeats_v1/folds.json").read_text())
    assert first_folds==repeat_folds
    result=dict(original)
    result["config"]=dict(original["config"])
    result["config"]["seeds"]=[s for v in values for s in v["config"]["seeds"]]
    assert sorted(result["config"]["seeds"])==sorted(original["config"]["planned_seeds"])
    for key in ["models","folds","patients","per_class","error_transitions"]:result[key]=[r for v in values for r in v[key]]
    result["unexecuted_seeds"]=[]
    result["components"]=[{"run":name,"fingerprint_sha256":sha256(BASE/f"results/{name}/fingerprint.json"),
                           "fold_manifest_sha256":sha256(BASE/f"results/{name}/folds.json")} for name in components]
    for s in result["config"]["seeds"]:
        assert len([r for r in result["folds"] if r["seed"]==s])==20
    registries=[json.loads((BASE/f"results/{name}/model_registry.json").read_text()) for name in components]
    for value,registry in zip(values,registries):
        registry["models"]=[r for r in registry["models"] if r["seed"] in value["config"]["seeds"]]
    write(BASE/"results/cv_cpu_v1/model_registry.json",{"experiment_id":"cv_cpu_v1","models":[r for value in registries for r in value["models"] if r["seed"] in result["config"]["seeds"]],
        "selection":"fixed first seed for teaching; patient's outer-held-out fold; source component retained in checkpoint path"})
    write(summary_paths[0],result)
    print(f"Merged {len(result['folds'])} jobs / {len(result['config']['seeds'])} seeds; component fingerprints retained")


if __name__=="__main__":merge()
