#!/usr/bin/env bash
# Run in a fresh output/worktree copy: all outputs refuse overwrites.
set -euo pipefail
ROOT=/home/user/Mice
HERE="$ROOT/test-data/horizon-benchmark"
P=/home/user/.venvs/hf-model-benchmark/bin/python
cd "$ROOT"
case "${1:-}" in
  development)
    "$P" "$HERE/fetch_inputs.py"
    "$P" "$HERE/make_hypotheses.py"
    for c in b350 b400; do "$P" "$HERE/prepare_inputs.py" "$c"; done
    for dtype in fp32 fp16; do
      for c in b350 b400; do "$P" "$HERE/infer.py" "$c" --dtype "$dtype"; done
    done
    "$P" "$HERE/optimize.py"
    echo 'STOP: commit hypotheses, configuration, freeze and scripts before holdout.'
    ;;
  holdout)
    "$P" "$HERE/prepare_inputs.py" b500
    for dtype in fp32 fp16; do
      "$P" "$HERE/infer.py" b500 --dtype "$dtype"
      "$P" "$HERE/infer.py" speed --dtype "$dtype"
    done
    "$P" "$HERE/report.py"
    "$P" "$HERE/render_report.py"
    ;;
  *) echo 'Usage: reproduce.sh development|holdout'; exit 2 ;;
esac