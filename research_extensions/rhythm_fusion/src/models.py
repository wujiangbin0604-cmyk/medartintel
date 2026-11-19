"""Reuse the exact original morphology encoder; never alter HeartbeatCNN."""
import torch
from torch import nn
from src.models.classifiers import HeartbeatCNN


class RRMLP(nn.Module):
    def __init__(self, num_classes=4, rhythm_dim=14):
        super().__init__()
        self.rhythm = nn.Sequential(nn.Linear(rhythm_dim, 32), nn.ReLU(), nn.Linear(32, 16), nn.ReLU())
        self.classifier = nn.Linear(16, num_classes)

    def forward(self, waveform, rhythm):
        return self.classifier(self.rhythm(rhythm))


class RhythmMorphologyCNN(nn.Module):
    def __init__(self, num_classes=4, rhythm_dim=14):
        super().__init__()
        self.features = HeartbeatCNN(num_classes).features
        self.rhythm = RRMLP(num_classes, rhythm_dim).rhythm
        self.classifier = nn.Linear(80, num_classes)

    def forward(self, waveform, rhythm):
        return self.classifier(torch.cat([self.features(waveform).squeeze(-1), self.rhythm(rhythm)], dim=1))


def make_model(name, class_count=4):
    if name == "A0":
        return HeartbeatCNN(class_count)
    if name == "A1":
        return RRMLP(class_count)
    if name in ["A2", "A3"]:
        return RhythmMorphologyCNN(class_count)
    raise ValueError(name)


def forward(model, name, x, r):
    return model(x) if name == "A0" else model(x, r)
