#!/usr/bin/env bash
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV="${HF_BENCHMARK_ENV:-$HOME/.venvs/hf-model-benchmark}"
"${PYTHON:-python3}" -m venv "$ENV"
"$ENV/bin/python" -m pip install -r "$HERE/requirements.lock"
"$ENV/bin/python" -m pip check
"$ENV/bin/python" -c 'import torch; assert torch.cuda.is_available(), "CUDA required, CPU fallback forbidden"; print(torch.cuda.get_device_name())'