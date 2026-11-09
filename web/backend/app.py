from __future__ import annotations

import json
import logging
import os
import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, HTTPException, Path as ApiPath, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, PlainTextResponse, Response
from .research import research_data, gallery, figure_path, figure_thumbnail, error_cases, REPORTS

from .ecg_service import InferenceService, MAX_POINTS, MAX_WINDOW_SECONDS
from .model_registry import MODEL_IDS, TASKS
from .schemas import BatchRequest, BeatRequest, CompareRequest
from .heartbeat_hunter import HunterService, create_router

ROOT = Path(__file__).resolve().parents[2]
logging.basicConfig(level=os.getenv("ECG_LOG_LEVEL", "INFO"),
                    format="%(asctime)s %(levelname)s %(name)s %(message)s")
LOGGER = logging.getLogger("ecg_ai.api")
service = InferenceService(ROOT)


@asynccontextmanager
async def lifespan(_: FastAPI):
    status = service.models.load_all()
    LOGGER.info("model_registry_ready %s", json.dumps({"all_loaded": status["all_loaded"],
                 "loaded_count": sum(bool(row.get("loaded")) for row in status["models"]),
                 "model_count": len(status["models"])}, ensure_ascii=False))
    yield


app = FastAPI(title="ECG-AI MIT-BIH 教学工作台", version="0.2.0", lifespan=lifespan,
              description=("读取本地 MIT-BIH 历史信号与专家标注，调用项目已训练的 N/V、N/S/V/F "
                           "Logistic Regression、Random Forest、1D-CNN。"))
origins = [item.strip() for item in os.getenv("ECG_CORS_ORIGINS", "http://localhost:8001,http://127.0.0.1:8001").split(",") if item.strip()]
app.add_middleware(CORSMiddleware, allow_origins=origins, allow_credentials=False,
                   allow_methods=["GET", "POST"], allow_headers=["*"])
game_service = HunterService(service.store, Path(os.getenv("ECG_HUNTER_DATABASE", str(ROOT / "web/runtime/heartbeat_hunter.sqlite3"))))
app.include_router(create_router(game_service))


@app.get("/api/research/summary", tags=["科研结果"])
def research_summary():
    try:
        return research_data()
    except Exception as exc:
        raise _http_error(exc) from exc


@app.get("/api/research/gallery", tags=["科研结果"])
def research_gallery():
    return {"figures": gallery()}


@app.get("/api/research/errors", tags=["科研结果"])
def research_errors(task: Literal["nv", "nsvf"], model: Literal["logistic_regression", "random_forest", "cnn_1d"],
                    true_label: Literal["N", "S", "V", "F"], predicted_label: Literal["N", "S", "V", "F"],
                    subject: str | None = Query(default=None, pattern=r"^subject_\d{3}(?:_\d{3})?$")):
    return error_cases(task, model, true_label, predicted_label, subject)


@app.get("/api/research/figures/{figure_id}", tags=["科研结果"])
def research_figure(figure_id: str, download: bool = False, thumbnail: bool = False):
    try:
        path = figure_path(figure_id)
        if thumbnail and not download:
            return Response(figure_thumbnail(path, path.stat().st_mtime_ns), media_type="image/png", headers={"Cache-Control": "private, max-age=3600"})
        return FileResponse(path, media_type="image/png", filename=path.name if download else None)
    except Exception as exc:
        raise _http_error(exc) from exc


@app.get("/api/research/reports/{report_id}", response_class=PlainTextResponse, tags=["科研结果"])
def research_report(report_id: str):
    if report_id not in REPORTS:
        raise HTTPException(404, "报告不存在")
    path = ROOT / REPORTS[report_id]
    if not path.is_file():
        raise HTTPException(404, "报告文件缺失")
    return path.read_text(encoding="utf-8-sig")


@app.middleware("http")
async def structured_request_log(request: Request, call_next):
    started = time.perf_counter()
    response = await call_next(request)
    LOGGER.info("request %s", json.dumps({"method": request.method, "path": request.url.path,
                 "status": response.status_code, "elapsed_ms": round((time.perf_counter() - started) * 1000, 2)},
                 ensure_ascii=False))
    return response


def _http_error(exc: Exception) -> HTTPException:
    message = str(exc)
    if isinstance(exc, KeyError):
        return HTTPException(status_code=404, detail=message.strip("'"))
    if isinstance(exc, RuntimeError):
        return HTTPException(status_code=503, detail=message)
    if "超出当前任务" in message or "不属于当前" in message or "只接受 MLII" in message:
        return HTTPException(status_code=409, detail=message)
    return HTTPException(status_code=422, detail=message)


@app.get("/api/health", tags=["平台"])
def health():
    model_status = service.models.status()
    return {"status": "ok", "dataset": "MIT-BIH Arrhythmia Database", "mode": "historical_teaching",
            "models_loaded": sum(bool(row.get("loaded")) for row in model_status["models"]),
            "models_total": len(model_status["models"]), "clinical_use": False}


@app.get("/api/ecg/records", tags=["ECG 数据"])
def records():
    try:
        return {"source": "local data/mitdb/*.dat,*.hea,*.atr", "count": len(service.store.records()),
                "records": service.store.records()}
    except Exception as exc:
        raise _http_error(exc) from exc


@app.get("/api/ecg/records/{record_id}", tags=["ECG 数据"])
def record_detail(record_id: str = ApiPath(pattern=r"^\d{3}$")):
    try:
        return service.store.record_detail(record_id)
    except Exception as exc:
        raise _http_error(exc) from exc


@app.get("/api/ecg/window", tags=["ECG 数据"],
         description="仅按需读取不超过 30 秒的真实物理信号；响应 amplitude_mv 来自 WFDB 校准波形。")
def waveform_window(record_id: str = Query(pattern=r"^\d{3}$"),
                    start_sec: float = Query(ge=0), duration_sec: float = Query(gt=0, le=MAX_WINDOW_SECONDS),
                    lead_name: str | None = None, max_points: int = Query(default=MAX_POINTS, ge=2, le=MAX_POINTS)):
    try:
        return service.store.window(record_id, start_sec, duration_sec, lead_name, max_points)
    except Exception as exc:
        raise _http_error(exc) from exc


@app.get("/api/ecg/annotations", tags=["ECG 数据"])
def annotations(record_id: str = Query(pattern=r"^\d{3}$"),
                start_sec: float = Query(ge=0), duration_sec: float = Query(gt=0, le=MAX_WINDOW_SECONDS),
                task: Literal["nv", "nsvf"] | None = None):
    try:
        return {"record_id": record_id, "annotations": service.store.annotations(record_id, start_sec, duration_sec, task)}
    except Exception as exc:
        raise _http_error(exc) from exc


@app.get("/api/ecg/beat", tags=["ECG 数据"],
         description="读取真实专家标注心拍及训练流程一致的 raw/filtered mV 局部波形，不在接口中回传归一化模型输入。")
def beat(record_id: str = Query(pattern=r"^\d{3}$"), annotation_sample: int = Query(ge=0),
         task: Literal["nv", "nsvf"] = Query(...), lead_name: str | None = None):
    try:
        return service.store.beat(record_id, annotation_sample, task, require_model_eligibility=False, lead_name=lead_name)
    except Exception as exc:
        raise _http_error(exc) from exc


@app.get("/api/models", tags=["模型"])
def models():
    return {"tasks": {task: {"labels": spec["labels"], "models": service.models.task_status(task)}
                       for task, spec in TASKS.items()},
            "probability_note": "模型类别概率", "input_length": 253, "lead_name": "MLII"}


@app.get("/api/models/{model_id}", tags=["模型"])
def model_detail(model_id: str):
    if model_id not in MODEL_IDS:
        raise HTTPException(status_code=404, detail="Unknown model id")
    service.models.load_all()
    return {"model_id": model_id, "tasks": [row for row in service.models.status()["models"]
                                          if row["model_id"] == model_id]}


@app.post("/api/inference/beat", tags=["真实模型推理"],
          summary="对一个已标注的真实心拍执行指定模型推理")
def infer_beat(payload: BeatRequest):
    try:
        return service.predict_beat(payload.record_id, payload.annotation_sample, payload.task, payload.model_id)
    except Exception as exc:
        raise _http_error(exc) from exc


@app.post("/api/inference/compare", tags=["真实模型推理"],
          summary="对同一心拍运行 Logistic Regression、Random Forest 与 1D-CNN")
def compare_beat(payload: CompareRequest):
    try:
        return service.compare(payload.record_id, payload.annotation_sample, payload.task)
    except Exception as exc:
        raise _http_error(exc) from exc


@app.post("/api/inference/batch", tags=["真实模型推理"],
          summary="对最多 128 个专家标注心拍批量运行 1 至 3 个模型")
def batch_predict(payload: BatchRequest):
    try:
        predictions = service.batch(payload.record_id, payload.annotation_samples, payload.task,
                                    list(dict.fromkeys(payload.model_ids)))
        return {"task": payload.task, "record_id": payload.record_id,
                "annotation_count": len(payload.annotation_samples), "model_ids": list(dict.fromkeys(payload.model_ids)),
                "predictions": predictions}
    except Exception as exc:
        raise _http_error(exc) from exc


@app.get("/api/ecg/playback/segment", tags=["历史回放"],
         description="历史片段按需加载；本接口使用与单拍推理相同的真实模型，最多处理 128 个标签位置。")
def playback_segment(record_id: str = Query(pattern=r"^\d{3}$"),
                    start_sec: float = Query(ge=0), duration_sec: float = Query(gt=0, le=MAX_WINDOW_SECONDS),
                    task: Literal["nv", "nsvf"] = "nv",
                    model_ids: list[Literal["logistic_regression", "random_forest", "cnn_1d"]] = Query(default=["cnn_1d"]),
                    lead_name: str | None = None):
    try:
        waveform = service.store.window(record_id, start_sec, duration_sec, lead_name)
        annotations_in_range = service.store.annotations(record_id, start_sec, duration_sec, task)
        task_beats = [item for item in annotations_in_range if item["within_task"]]
        if len(task_beats) > 128:
            raise ValueError("This playback segment contains more than 128 target heartbeats; request a shorter segment")
        record_summary = service.store.record_detail(record_id)
        can_predict = record_summary["model_inference_available"] and waveform["lead_name"] == "MLII"
        selected_models = list(dict.fromkeys(model_ids)) if can_predict else []
        eligible_beats = []
        for annotation in annotations_in_range:
            annotation["predictions"] = []
            annotation["prediction_eligible"] = False
            if not annotation["within_task"]:
                continue
            if not selected_models:
                annotation["prediction_unavailable_reason"] = record_summary["model_inference_reason"] or "模型仅支持 MLII 导联"
                continue
            try:
                service.store.beat(record_id, annotation["annotation_sample"], task)
                eligible_beats.append(annotation)
                annotation["prediction_eligible"] = True
            except ValueError as exc:
                annotation["prediction_unavailable_reason"] = str(exc)
        predictions = service.batch(record_id, [item["annotation_sample"] for item in eligible_beats], task, selected_models) if eligible_beats else []
        keyed = {(item["annotation_sample"], item["model_id"]): item for item in predictions}
        for annotation in annotations_in_range:
            annotation["predictions"] = [keyed[(annotation["annotation_sample"], model_id)]
                                         for model_id in selected_models
                                         if (annotation["annotation_sample"], model_id) in keyed]
        return {"record_id": record_id, "task": task, "model_ids": selected_models,
                "start_sec": start_sec, "duration_sec": duration_sec,
                "historical_recording": True, "real_time_monitoring": False,
                "notice": "MIT-BIH ECG 记录回放。",
                "waveform": waveform, "annotations": annotations_in_range,
                "expert_beat_count": len(annotations_in_range),
                "predicted_beat_count": len(eligible_beats),
                "prediction_model_rows": len(predictions),
                "inference_unavailable_reason": None if selected_models else
                    (record_summary["model_inference_reason"] if not record_summary["model_inference_available"] else
                     ("模型仅支持 MLII 导联" if waveform["lead_name"] != "MLII" else None))}
    except Exception as exc:
        raise _http_error(exc) from exc

