#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")"
if [[ ! -x .venv/bin/python ]]; then
  python3.12 -m venv .venv
fi
exec .venv/bin/python deploy/local.py "$@"
