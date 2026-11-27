#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
ENV="${MICE_TRAINER_ENV:-$HOME/.venvs/mice-trainer}"
PYTHON="${PYTHON:-python3}"
"$PYTHON" -c 'import sys; assert sys.version_info >= (3,12), "Python 3.12+ required"'
if [[ ! -x "$ENV/bin/python" ]]; then "$PYTHON" -m venv "$ENV"; fi
"$ENV/bin/python" -m pip install -r "$ROOT/requirements.training.lock" -r "$ROOT/requirements.neural.lock" -r "$ROOT/tools/mice-trainer/requirements-dev.lock"
"$ENV/bin/python" -m pip check
mkdir -p "$HOME/mice-trainer-data/"{datasets,base_models,output,logs}
"$ENV/bin/python" "$ROOT/tools/mice-trainer/trainer.py" doctor
echo "Ready: source $ENV/bin/activate"