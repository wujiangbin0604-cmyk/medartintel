"""Recompute selective results and figures into fresh independent directories."""
import json
from research_extensions.rhythm_fusion.src.data import BASE
from research_extensions.rhythm_fusion.src.figures import generate
from research_extensions.uncertainty.src import evaluate as reliability


if __name__ == '__main__':
    reliability.OUT = BASE.parent / 'uncertainty/results/revalidation_20261119'
    actual = reliability.evaluate()
    inherited = json.loads((BASE.parent / 'uncertainty/results/cv_cpu_v1/summary.json').read_text())
    assert actual == inherited, 'Selective metrics or threshold provenance changed'
    generate(output_directory=BASE / 'figures/revalidation_20261119')
    print('Selective metrics exactly match inherited results; all figures regenerated separately')
