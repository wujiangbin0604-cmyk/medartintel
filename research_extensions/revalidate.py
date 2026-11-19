"""Independent read-only audit of inherited experiment artifacts.

Does not retrain, overwrite historical results, or open the locked test arrays.
Run with --full to reproduce every evaluation/calibration probability from weights.
"""
import argparse
from collections import Counter
from datetime import datetime
import json
from pathlib import Path
import subprocess
import time

import numpy as np
import torch
import wfdb

from research_extensions.protect import ROOT, sha256
from research_extensions.rhythm_fusion.src.data import BASE, load, rhythm_at, event_positions, fit_scaler, transform
from research_extensions.rhythm_fusion.src.models import make_model
from research_extensions.rhythm_fusion.src.run import derangement, predict, score
from research_extensions.uncertainty.src.evaluate import policy, selective_metrics, uncertainty


def audit(full=False):
    start = time.perf_counter()
    torch.set_num_threads(2)
    data = load()
    plan = json.loads((ROOT / 'data/processed/mitdb44_nsvf_v1/split_plan.json').read_text())
    assert Counter(plan['subject_to_split'].values()) == {'train': 31, 'val': 6, 'test': 6}
    forbidden = {g for g, s in plan['subject_to_split'].items() if s == 'test'}
    assert not forbidden.intersection(data['subject_group'])
    assert len(np.unique(data['sample_id'])) == len(data['label']) == 86286
    # Recompute every RR row from original annotation positions, with a prefix
    # check on each record to independently verify no future timing is required.
    for rid in np.unique(data['record_id']):
        annotation = wfdb.rdann(str(ROOT / 'data/mitdb' / str(rid)), 'atr')
        positions = event_positions(annotation.sample, annotation.symbol)
        for i in np.flatnonzero(data['record_id'] == rid):
            raw_index = int(str(data['sample_id'][i]).rsplit(':', 1)[1])
            sample = int(data['annotation_sample'][i])
            assert annotation.sample[raw_index] == sample
            assert annotation.symbol[raw_index] == data['original_label'][i]
            values, mask, _ = rhythm_at(positions, sample)
            np.testing.assert_array_equal(values, data['rhythm_features'][i])
            np.testing.assert_array_equal(mask, data['rhythm_valid_mask'][i])
        first = int(data['annotation_sample'][np.flatnonzero(data['record_id'] == rid)[0]])
        for a, b in zip(rhythm_at(positions, first), rhythm_at(positions[positions <= first], first)):
            np.testing.assert_array_equal(a, b)
    print('Verified all 86286 feature rows against original expert events', flush=True)
    summary = json.loads((BASE / 'results/cv_cpu_v1/summary.json').read_text())
    selective = json.loads((BASE.parent / 'uncertainty/results/cv_cpu_v1/summary.json').read_text())
    registry = json.loads((BASE / 'results/cv_cpu_v1/model_registry.json').read_text())['models']
    assert len(registry) == 60
    rows = []
    for component in ['cv_cpu_v1', 'cv_cpu_repeats_v1']:
        folder = BASE / 'results' / component
        fingerprint = json.loads((folder / 'fingerprint.json').read_text())
        assert fingerprint['data_sha256'] == sha256(BASE / 'data/development.npz')
        for name, digest in fingerprint['source_sha256'].items():
            assert sha256(BASE / 'src' / name) == digest
        folds = json.loads((folder / 'folds.json').read_text())
        cfg = fingerprint['config']
        for fold, parts in enumerate(folds):
            indices = {k: np.array(v['indices']) for k, v in parts.items()}
            sets = [set(data['subject_group'][ix]) for ix in indices.values()]
            assert all(not a & b for j, a in enumerate(sets) for b in sets[j+1:])
            fit = indices['fit']
            scaler = fit_scaler(data['waveform'][fit], data['rhythm_features'][fit], data['rhythm_valid_mask'][fit], data['sample_id'][fit])
            for seed in cfg['seeds']:
                for name in cfg['models']:
                    job = folder / f'fold{fold}/seed{seed}/{name}'
                    result = json.loads((job / 'result.json').read_text())
                    assert sha256(job / 'best.pt') == result['checkpoint_sha256']
                    bundle = torch.load(job / 'best.pt', map_location='cpu', weights_only=True)
                    assert bundle['scaler'] == scaler
                    entry = next(r for r in registry if (r['fold'], r['seed'], r['model']) == (fold, seed, name))
                    assert entry['sha256'] == result['checkpoint_sha256']
                    model = make_model(name, 4)
                    model.load_state_dict(bundle['state_dict'], strict=True)
                    max_delta = 0.
                    with np.load(job / 'predictions.npz') as saved:
                        for key, prefix in [('evaluation', 'eval'), ('calibration', 'calibration')]:
                            ix = indices[key]
                            np.testing.assert_array_equal(saved[f'{prefix}_indices'], ix)
                            expected = saved[f'{prefix}_probability']
                            assert np.isfinite(expected).all() and np.allclose(expected.sum(1), 1, atol=1e-5)
                            if full:
                                x, r = transform(data['waveform'][ix], data['rhythm_features'][ix], data['rhythm_valid_mask'][ix], scaler)
                                if name == 'A3':
                                    j = list(parts).index(key)
                                    r = r[derangement(len(r), cfg['fold_seed'] + fold * 100 + j)]
                                actual = predict(model, name, x, r, torch.device('cpu'))
                                np.testing.assert_allclose(actual, expected, atol=2e-6, rtol=2e-4)
                                max_delta = max(max_delta, float(np.max(np.abs(actual - expected))))
                        e, c = indices['evaluation'], indices['calibration']
                        ep, cp = saved['eval_probability'], saved['calibration_probability']
                        assert score(data['label'][e], ep, data['subject_group'][e], result['classes']) == result['evaluation']
                        for method in ['max_score', 'entropy']:
                            threshold = next(t for t in selective['thresholds'] if (t['fold'], t['seed'], t['model'], t['method']) == (fold, seed, name, method))
                            assert threshold['threshold'] == policy(cp, method)
                            assert threshold['predictions_sha256'] == sha256(job / 'predictions.npz')
                    rows.append({'component': component, 'fold': fold, 'seed': seed, 'model': name,
                                 'macro_f1': result['evaluation']['macro_f1'], 'prediction_max_absolute_delta': max_delta if full else None})
                    print(f"Verified {len(rows)}/60 {component} fold={fold} seed={seed} {name}", flush=True)
    # Independently pool saved OOF predictions, without counting seeds as patients.
    pooled = []
    for seed in summary['config']['seeds']:
        for name in summary['config']['models']:
            probabilities = np.full((len(data['label']), 4), np.nan)
            seen = np.zeros(len(probabilities), int)
            for entry in registry:
                if (entry['seed'], entry['model']) != (seed, name):
                    continue
                with np.load((BASE / entry['checkpoint']).with_name('predictions.npz')) as saved:
                    ix = saved['eval_indices']
                    probabilities[ix] = saved['eval_probability']
                    seen[ix] += 1
            assert np.all(seen == 1)
            metric = score(data['label'], probabilities, data['subject_group'], summary['classes'])
            reported = next(r for r in summary['models'] if (r['seed'], r['model']) == (seed, name))
            assert metric == reported['pooled']
            pooled.append({'seed': seed, 'model': name, **metric})
    return {'status': 'passed', 'finished': datetime.now().astimezone().isoformat(),
            'scope': 'Independent revalidation of inherited artifacts, not new formal training',
            'full_checkpoint_inference_reproduced': full, 'samples': len(data['label']), 'patients': 37,
            'jobs': rows, 'pooled': pooled, 'test_arrays_opened': False,
            'elapsed_seconds': time.perf_counter() - start}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--full', action='store_true')
    args = parser.parse_args()
    output = ROOT / 'research_extensions/validation/revalidation_20261119_artifacts.json'
    result = audit(args.full)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False), encoding='utf-8')
    print(f'Audit passed: {output}', flush=True)
