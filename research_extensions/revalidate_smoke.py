"""Fresh isolated four-model training check; scores are not research evidence."""
import json
import numpy as np
import torch
from research_extensions.rhythm_fusion.src.data import BASE, load
from research_extensions.rhythm_fusion.src.run import job, partition, write


def main():
    config = json.loads((BASE / 'configs/cv_cpu_v1.json').read_text())
    config.update(experiment_id='revalidation_smoke_20261119', epochs=1, patience=1)
    output = BASE / 'results' / config['experiment_id']
    if output.exists():
        raise FileExistsError('Fresh smoke run requires an unused experiment directory')
    torch.set_num_threads(config['threads'])
    data = load()
    original = partition(data, config)[0]
    parts = {key: np.sort(np.concatenate([ix[data['label'][ix] == c][:128] for c in range(4)])) for key, ix in original.items()}
    write(output / 'config.json', config)
    for name in config['models']:
        job(data, parts, config, 0, 20261119, name, output / f'fold0/seed20261119/{name}', smoke=True)
    write(output / 'SMOKE_COMPLETED.json', {'status': 'completed', 'models': config['models'],
          'purpose': 'Fresh one-epoch training and persistence check; never pooled into formal experiments'})


if __name__ == '__main__':
    main()
