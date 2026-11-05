"""Traditional baselines and the required compact 1D convolutional model."""
from __future__ import annotations

import torch
from torch import nn
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression


def make_logistic_regression(seed: int, smoke: bool = False, config: dict | None = None) -> LogisticRegression:
    settings = config or {}
    return LogisticRegression(C=float(settings.get("C", 1.0)),
                              class_weight=settings.get("class_weight", "balanced"),
                              solver=settings.get("solver", "lbfgs"),
                              max_iter=8 if smoke else int(settings.get("max_iter", 300)),
                              random_state=seed, tol=float(settings.get("tol", 1e-4)))


def make_random_forest(seed: int, smoke: bool = False, config: dict | None = None) -> RandomForestClassifier:
    settings = config or {}
    return RandomForestClassifier(n_estimators=5 if smoke else int(settings.get("n_estimators", 100)),
                                  max_depth=8 if smoke else settings.get("max_depth", 18),
                                  min_samples_leaf=int(settings.get("min_samples_leaf", 2)),
                                  max_features=settings.get("max_features", "sqrt"),
                                  class_weight=settings.get("class_weight", "balanced_subsample"),
                                  bootstrap=True, random_state=seed,
                                  n_jobs=int(settings.get("n_jobs", -1)),
                                  max_samples=float(settings.get("max_samples", .8)))


class HeartbeatCNN(nn.Module):
    """Small fixed-length 1D CNN: Conv/ReLU/MaxPool/AdaptivePool/Linear."""

    def __init__(self, num_classes: int):
        super().__init__()
        self.features = nn.Sequential(
            nn.Conv1d(1, 16, kernel_size=7, padding=3),
            nn.ReLU(inplace=True),
            nn.MaxPool1d(kernel_size=2),
            nn.Conv1d(16, 32, kernel_size=5, padding=2),
            nn.ReLU(inplace=True),
            nn.MaxPool1d(kernel_size=2),
            nn.Conv1d(32, 64, kernel_size=3, padding=1),
            nn.ReLU(inplace=True),
            nn.AdaptiveAvgPool1d(1),
        )
        self.classifier = nn.Linear(64, num_classes)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.classifier(self.features(x).squeeze(-1))
