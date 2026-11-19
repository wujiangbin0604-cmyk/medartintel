import json
from pathlib import Path
import numpy as np
import pytest
import torch
from research_extensions.rhythm_fusion.src.data import rhythm_at, event_positions, fit_scaler, transform, load, BASE
from research_extensions.rhythm_fusion.src.models import make_model, forward
from research_extensions.rhythm_fusion.src.run import partition, derangement
from src.preprocessing.splitting import subject_id
from research_extensions.protect import sha256, ROOT


def test_rr_formulas():
    positions = np.array([0, 360, 720, 900, 1260])
    r, mask, history = rhythm_at(positions, 1260)
    np.testing.assert_allclose(r, [1, .5, 2, 1, 1, 0, 0])
    np.testing.assert_array_equal(mask, 1)
    np.testing.assert_allclose(history, [1, 1, .5])


def test_future_invariance():
    a = rhythm_at([0, 360, 720], 720)
    b = rhythm_at([0, 360, 720, 1000, 5000], 720)
    for x, y in zip(a, b):
        np.testing.assert_array_equal(x, y)


def test_missing_no_fake_intervals():
    r, mask, history = rhythm_at([100, 500], 100)
    assert np.isnan(r).all() and not mask.any() and len(history) == 0
    r, mask, _ = rhythm_at([100, 460], 460)
    assert r[0] == 1 and mask.sum() == 1


def test_event_types_not_targets_or_class_values():
    samples = np.arange(9) * 100
    a = event_positions(samples, ["N", "x", "Q", "+", "V", "!", "/", "|", "f"])
    b = event_positions(samples, ["S", "x", "F", "+", "N", "!", "r", "|", "?"])
    np.testing.assert_array_equal(a, b)
    np.testing.assert_array_equal(a, [0, 200, 400, 600, 800])


def test_record_reset():
    r, mask, _ = rhythm_at(event_positions([100, 200], ["N", "V"]), 100)
    assert not mask.any()  # Previous record's last beat is never an input.
    with pytest.raises(ValueError):
        rhythm_at([200, 100], 100)
    with pytest.raises(ValueError):
        rhythm_at([100, 100], 100)


def test_training_only_scaling():
    x = np.arange(8, dtype=np.float32).reshape(2, 1, 4)
    r = np.array([[1, np.nan], [3, 2]], np.float32)
    m = np.isfinite(r).astype(np.float32)
    scaler = fit_scaler(x, r, m, ["a", "b"])
    x2, r2 = transform(x, r, m, scaler)
    assert abs(x2.mean()) < 1e-6 and np.isfinite(r2).all()
    original = json.dumps(scaler, sort_keys=True)
    transform(x + 1e6, r + 1e6, m, scaler)
    assert json.dumps(scaler, sort_keys=True) == original
    assert scaler["rhythm_median"] == [2., 2.]


def test_alignment_grouping_and_partition():
    d = load()
    assert len(d["sample_id"]) == len(np.unique(d["sample_id"])) == 86286
    assert subject_id("201") == subject_id("202")
    assert set(d["subject_group"][np.isin(d["record_id"], ["201", "202"])]) == {"subject_201_202"}
    cfg = json.loads((BASE / "configs/cv_cpu_v1.json").read_text())
    folds = partition(d, cfg)
    seen = []
    for parts in folds:
        groups = [set(d["subject_group"][v]) for v in parts.values()]
        assert all(not a & b for i,a in enumerate(groups) for b in groups[i+1:])
        seen.extend(parts["evaluation"].tolist())
    assert sorted(seen) == list(range(len(d["label"])))
    audit = json.loads((BASE / "data/audit.json").read_text())
    assert not set(d["subject_group"]) & set(audit["excluded_test_subjects"])
    assert audit["alignment_verified"] and not audit["test_npz_opened"]


def test_shuffle_pairing_and_reproducibility():
    order = derangement(100, 9)
    assert np.all(order != np.arange(100))
    np.testing.assert_array_equal(order, derangement(100, 9))
    assert sorted(order) == list(range(100))


@pytest.mark.parametrize("name", ["A0", "A1", "A2", "A3"])
def test_forward_backward_checkpoint_seed(name, tmp_path):
    torch.set_num_threads(2)
    torch.manual_seed(42)
    model = make_model(name)
    x, r = torch.randn(8, 1, 253), torch.randn(8, 14)
    logits = forward(model, name, x, r)
    assert logits.shape == (8, 4) and torch.isfinite(logits).all()
    torch.nn.functional.cross_entropy(logits, torch.arange(8) % 4).backward()
    assert all(torch.isfinite(p.grad).all() for p in model.parameters() if p.grad is not None)
    path = tmp_path / "model.pt"
    torch.save(model.state_dict(), path)
    copy = make_model(name)
    copy.load_state_dict(torch.load(path, weights_only=True))
    torch.testing.assert_close(forward(copy, name, x, r), logits)
    torch.manual_seed(42)
    repeat = make_model(name)
    for a, b in zip(model.parameters(), repeat.parameters()):
        torch.testing.assert_close(a, b)


def test_smoke_models_actually_completed():
    for name in ["A0", "A1", "A2", "A3"]:
        result = json.loads((BASE / f"results/smoke_v1/fold0/seed20261118/{name}/result.json").read_text())
        assert result["status"] == "completed" and result["smoke"]
        assert result["fit_seconds"] > 0


def test_original_checkpoints_unchanged():
    manifest = json.loads((ROOT / "research_extensions/protection_manifest.json").read_text(encoding="utf-8"))
    checkpoints = {p: h for p,h in manifest["files"].items() if p.startswith("checkpoints/")}
    assert checkpoints
    assert all(sha256(ROOT / p) == h for p,h in checkpoints.items())
