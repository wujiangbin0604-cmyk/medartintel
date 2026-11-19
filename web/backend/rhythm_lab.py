"""Read-only research registry and patient-held-out demonstration inference."""
from functools import lru_cache
import json
from pathlib import Path
from typing import Literal
import numpy as np
import torch
from fastapi import APIRouter, HTTPException, Query
from research_extensions.protect import sha256
from research_extensions.rhythm_fusion.src.data import NAMES, event_positions, rhythm_at, transform
from research_extensions.rhythm_fusion.src.models import make_model, forward
from research_extensions.uncertainty.src.evaluate import uncertainty

RUN = "cv_cpu_v1"


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


@lru_cache(maxsize=12)
def load_bundle(path_string, expected_hash):
    path = Path(path_string)
    if sha256(path) != expected_hash:
        raise RuntimeError("Research checkpoint SHA-256 mismatch")
    bundle = torch.load(path, map_location="cpu", weights_only=True)
    model = make_model(bundle["model_id"], len(bundle["classes"]))
    model.load_state_dict(bundle["state_dict"], strict=True)
    model.eval()
    return model, bundle


def create_rhythm_router(service):
    router = APIRouter(prefix="/api/rhythm", tags=["节律融合研究"])
    base = service.root / "research_extensions/rhythm_fusion"
    folder = base / "results" / RUN
    uncertainty_path = base.parent / f"uncertainty/results/{RUN}/summary.json"

    @router.get("/summary")
    def summary():
        path = folder / "summary.json"
        data = read(path) if path.is_file() else {"status":"not_ready","models":[],"folds":[],"patients":[],"per_class":[],
            "completed_jobs":len(list(folder.glob("fold*/seed*/A*/result.json"))), "expected_jobs":20,
            "message":"分组实验尚未全部完成；不显示未完成的比较数值。"}
        data["uncertainty"] = read(uncertainty_path) if uncertainty_path.is_file() else {"status":"not_ready"}
        data["architecture"] = {"waveform":[1,253],"morphology_dim":64,"rhythm_features":NAMES,
                                "rhythm_input_dim":14,"rhythm_layers":[32,16],"fusion_dim":80,"classes":["N","S","V","F"]}
        return data

    @router.get("/samples")
    def samples(label: Literal["N","S","V","F"]="S"):
        path = base / "data/alignment.csv"
        if not path.is_file():
            return {"samples":[],"status":"not_ready"}
        import pandas as pd
        table = pd.read_csv(path,dtype={"record_id":str})
        rows = table[table.original_label.isin({"N":["N","L","R","e","j"],"S":["A","a","J","S"],"V":["V","E"],"F":["F"]}[label])]
        # Representative teaching examples across patients, never experimental sample selection.
        rows = rows.groupby("subject_group",sort=True).head(2).head(60)
        return {"status":"ready","samples":rows[["sample_id","record_id","subject_group","annotation_sample","original_label","split"]].to_dict("records")}

    @router.get("/beat")
    def beat(record_id: str=Query(pattern=r"^\d{3}$"), annotation_sample:int=Query(ge=0)):
        try:
            signal = service.store.beat(record_id,annotation_sample,"nsvf",require_model_eligibility=False)
            context = service.store.signal_context(record_id)
            frame = context.record.annotations
            positions = event_positions(frame["sample"],frame["symbol"])
            features,mask,history = rhythm_at(positions,annotation_sample,context.record.fs)
            out = {"beat":signal,"feature_names":NAMES,"rhythm_features":[float(v) if np.isfinite(v) else None for v in features],
                   "rhythm_valid_mask":mask.tolist(),"history_rr_s":history.tolist(),"current_rr_s":float(features[0]) if mask[0] else None,
                   "rhythm_missing_reason":None if mask.all() else "记录起始处历史心拍不足；缺失特征以训练侧填充值及掩码处理。",
                   "models":[],"original_cnn":None,"research_available":False,
                   "note":"教学离线推理依赖专家定位；原正式CNN可能见过该患者，不能与外层留出模型作公平的单拍性能比较。"}
            if signal["dataset_split"] == "test":
                out["unavailable_reason"]="原正式测试患者保持隔离，本研究接口不运行新增模型或收集其指标。"
                return out
            if not signal["inference_eligible"]:
                out["unavailable_reason"]=signal["inference_unavailable_reason"]
                return out
            out["original_cnn"]=service.predict_beat(record_id,annotation_sample,"nsvf","cnn_1d")
            registry_path=folder/"model_registry.json"
            if not registry_path.is_file():
                out["unavailable_reason"]="完整分组实验及模型注册尚未就绪。"
                return out
            registry=read(registry_path)
            seed=read(folder/"fingerprint.json")["config"]["seeds"][0]
            policies=read(uncertainty_path)["thresholds"] if uncertainty_path.is_file() else []
            for name in ["A0","A2"]:
                entry=next((m for m in registry["models"] if m["model"]==name and m["seed"]==seed and signal["subject_id"] in m["evaluation_subjects"]),None)
                if not entry:
                    continue
                model,bundle=load_bundle(str(base/entry["checkpoint"]),entry["sha256"])
                x,r=transform(np.array(signal["filtered_amplitude_mv"],np.float32)[None,None,:],features[None],mask[None],bundle["scaler"])
                with torch.inference_mode():
                    p=forward(model,name,torch.from_numpy(x),torch.from_numpy(r)).softmax(1).numpy()
                values={method:float(uncertainty(p,method)[0]) for method in ["max_score","entropy"]}
                applied=[]
                for method in values:
                    policy=next((t for t in policies if t["model"]==name and t["fold"]==entry["fold"] and t["seed"]==seed and t["method"]==method),None)
                    if policy:
                        applied.append({**policy,"uncertainty":values[method],"needs_review":values[method]>policy["threshold"]})
                out["models"].append({"model":name,"prediction":bundle["classes"][int(p.argmax())],"probabilities":dict(zip(bundle["classes"],map(float,p[0]))),
                    "max_score":float(p.max()),"entropy":values["entropy"],"policies":applied,
                    "fold":entry["fold"],"seed":seed,"sha256":entry["sha256"],"checkpoint":entry["checkpoint"],
                    "version":f"{RUN}/fold{entry['fold']}/seed{seed}/{name}","evaluation_scope":"patient outer-held-out; not used for fitting, early stopping or calibration"})
            out["research_available"]=len(out["models"])==2
            return out
        except (ValueError, KeyError) as exc:
            raise HTTPException(422,str(exc)) from exc
        except RuntimeError as exc:
            raise HTTPException(503,str(exc)) from exc

    return router
