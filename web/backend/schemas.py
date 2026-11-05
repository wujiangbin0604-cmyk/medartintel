from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

TaskName = Literal["nv", "nsvf"]
ModelName = Literal["logistic_regression", "random_forest", "cnn_1d"]


class BeatRequest(BaseModel):
    record_id: str = Field(pattern=r"^\d{3}$")
    annotation_sample: int = Field(ge=0)
    task: TaskName
    model_id: ModelName


class CompareRequest(BaseModel):
    record_id: str = Field(pattern=r"^\d{3}$")
    annotation_sample: int = Field(ge=0)
    task: TaskName


class BatchRequest(BaseModel):
    record_id: str = Field(pattern=r"^\d{3}$")
    annotation_samples: list[int] = Field(min_length=1, max_length=128)
    task: TaskName
    model_ids: list[ModelName] = Field(min_length=1, max_length=3)

