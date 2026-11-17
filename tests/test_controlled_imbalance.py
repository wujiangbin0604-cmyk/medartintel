"""Behavior checks for the new experimental loss, timing and metric contracts."""
import numpy as np
import pytest
import torch

from src.evaluation.controlled_imbalance import focal_loss, past_rr_features, metrics
from src.evaluation import controlled_imbalance


def test_zero_gamma_unit_alpha_recovers_cross_entropy():
    logits = torch.tensor([[2., -1., .5, 0.], [-1., 0., 1., 2.]], requires_grad=True)
    labels = torch.tensor([0, 2])
    weights = torch.tensor([.2, 2., 3., 8.])
    loss = focal_loss(logits, labels, weights, gamma=0.)
    assert torch.allclose(loss, torch.nn.functional.cross_entropy(logits, labels, weight=weights))
    loss.backward()
    assert torch.isfinite(logits.grad).all()


def test_past_rr_is_unchanged_when_future_beats_are_changed():
    positions = np.array([0, 100, 210, 300, 430])
    a = past_rr_features(positions, np.array([210]), 100.)
    b = past_rr_features(np.array([0, 100, 210, 600, 900]), np.array([210]), 100.)
    np.testing.assert_array_equal(a, b)
    np.testing.assert_allclose(a[0], [1.1, 1.05, 1.1 / 1.05, 1.1])


def test_unannotated_target_is_rejected():
    with pytest.raises(ValueError, match="expert beat"):
        past_rr_features(np.array([0, 100, 200]), np.array([150]), 100.)


def test_balanced_accuracy_exposes_majority_only_predictions():
    result = metrics(np.array([0] * 97 + [1, 2, 3]), np.zeros(100, dtype=int), ["N", "S", "V", "F"])
    assert result["accuracy"] == .97
    assert result["balanced_accuracy"] == .25
    assert result["per_class"]["S"]["recall"] == 0


def test_completed_test_phase_is_rejected_before_loading_test_arrays(tmp_path, monkeypatch):
    (tmp_path / "selection_locked.json").write_text('{"checkpoint_hashes": {}}', encoding="utf-8")
    (tmp_path / "test_evaluation.json").write_text('{"status": "completed"}', encoding="utf-8")
    monkeypatch.setattr(controlled_imbalance, "OUT", tmp_path)
    monkeypatch.setattr(controlled_imbalance, "assert_protocol", lambda: ({}, {}))
    def forbidden_load(*args, **kwargs):
        raise AssertionError("A repeated evaluation must not load test arrays")
    monkeypatch.setattr(controlled_imbalance, "load_npz", forbidden_load)
    with pytest.raises(RuntimeError, match="already executed"):
        controlled_imbalance.final()
