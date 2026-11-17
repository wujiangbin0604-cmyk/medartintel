"""Reproduce the frozen experiment into a fresh directory without overwriting evidence."""
from __future__ import annotations

import argparse
from pathlib import Path

import torch

from . import controlled_imbalance as experiment


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True, help="Fresh directory under results/")
    parser.add_argument("--stage", choices=("train", "final"), required=True)
    args = parser.parse_args()
    output = (experiment.ROOT / args.output).resolve() if not args.output.is_absolute() else args.output.resolve()
    if not output.is_relative_to((experiment.ROOT / "results").resolve()) or output == experiment.OUT.resolve():
        parser.error("Use a separate experiment directory under results/; the delivered evidence is protected")
    experiment.OUT = output
    config = experiment.read_json(experiment.CONFIG)
    torch.set_num_threads(config["cpu_threads"])
    torch.set_num_interop_threads(2)
    if args.stage == "train":
        experiment.train()
    else:
        experiment.final()


if __name__ == "__main__":
    main()
