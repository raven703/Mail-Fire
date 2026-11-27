# Horizon integration and exploratory fusion

Current integration-only follow-up: see `COMPLETION-REPORT.md` for actual tests
and open blockers, and `../../docs/HORIZON-INTEGRATION.md` for CPU/GPU/offline
setup. Historical results below do not establish completion of the new task.

Read `REPORT.md` first. **B-500 fusion is exploratory, not independent validation.**
No automatic deployment, merging, training, GPU benchmark, or model download.

## Artifacts

- `summary.csv`, `metrics.json`: all individual methods and required FP32/FP16 combinations,
  per-category confusion matrices, macro/micro metrics, safe-email FP counts and contribution IDs.
- `recommendations.json`: safety-aware per-category candidates and explicit rejection warnings.
- `category-grid-{fp32,fp16}.jsonl.gz`: every category-specific subset/ANY/two-vote decision grid.
- `combined-predictions.jsonl.gz`: saved derived predictions for auditing.
- `provenance.json`: pinned source commits, exact input digests and alignment checks.
- `cpu-results.json`: real local CPU-only smoke, synthetic examples, timings, scores and RSS.
- `validation/`: saved test results, dependency snapshots and browser results.
- `/home/user/Mice/app/horizon_defaults.json`: exact selected PR38 FP32 configurations,
  using existing category IDs; **not** the post-hoc fusion candidates.

## Reproduce fusion (no inference)

From an isolated checkout at `/home/user/Mice` (adjust this absolute path in another worktree):

```sh
python3 /home/user/Mice/test-data/horizon-integration/combine.py
python3 /home/user/Mice/test-data/horizon-integration/render_report.py
```

Source Git objects must exist locally: `d846b91`,
`19cdc936f342e2b7330fb07e1b5815a8dd604bcd` and
`e3f5d016667d8db939b614055334fb50442d4899`.
Fetch the corresponding benchmark branches as data sources if necessary; do not merge them.
Generated metrics are overwritten only inside this integration report directory; original PR38
frozen outputs and external inference caches are never modified. Use a separate output copy
to preserve the published integration artifact hashes. Gzip timestamps are fixed for reproducibility.

## CPU smoke (optional neural environment, local files only)

Existing MICE optional neural dependencies are used; no new inference framework.
Tested torch 2.15.0 / transformers 5.23.0, as recorded in PR38 and the existing neural lock.

```sh
MICE_HORIZON_MODEL_PATH=/home/user/hf-model-benchmark-data/models/horizon \
  /home/user/.venvs/hf-model-benchmark/bin/python \
  /home/user/Mice/test-data/horizon-integration/cpu_smoke.py
```

The script forces CPU, hides CUDA and enables HF offline mode. It does not evaluate B-500.
The model directory must already contain tokenizer, config and `model.safetensors` from the
approved Horizon checkpoint. There is no runtime model download. Evidence records SHA256
of actual weights, not an unverified assertion that a local directory matches the upstream revision.

## Tests (test DB only)

```sh
cd /home/user/Mice
/home/user/.venvs/horizon-integration/bin/pytest \
  /home/user/Mice/tests/test_horizon.py /home/user/Mice/tests/test_category_rules.py \
  /home/user/Mice/tests/test_text_match.py /home/user/Mice/tests/test_document_templates.py \
  /home/user/Mice/tests/test_text_normalizer.py /home/user/Mice/tests/test_ocr_evidence.py \
  /home/user/Mice/tests/test_analysis_status.py -q
DJANGO_SECRET_KEY=disposable-test-secret MICE_DB_NAME=horizon_test MICE_DB_USER=user \
  MICE_DB_PORT=15439 /home/user/.venvs/horizon-integration/bin/python \
  /home/user/Mice/manage.py test pipeline policy_engine records identity --noinput
```

Tests require a disposable PostgreSQL/pgvector installation and create a Django test database.
Never point tests at a working MICE deployment. The environment and PostgreSQL used for
this run live under `/home/user/hf-model-benchmark-data/horizon-integration/`, isolated from
existing deployments. Browser test `/home/user/Mice/scripts/check_horizon_ui.py` writes
synthetic category settings and **must only target that disposable UI instance**:

```sh
MICE_HORIZON_TEST_URL=http://127.0.0.1:18089 \
  MICE_HORIZON_TEST_PASSWORD='<disposable test account password>' \
  /home/user/.venvs/horizon-integration/bin/python /home/user/Mice/scripts/check_horizon_ui.py
```

The disposable instance needs an administrator `horizon-ui`, existing category
`pack-ru2-financial-plans`, one legacy rule and one disabled Horizon rule. Do not use live credentials.
Headless Chromium must be installed; host libraries can be extracted to an isolated sysroot
and supplied by `LD_LIBRARY_PATH` without changing the operating system or deployment.

## Configuration — instructions only, NOT performed on live MICE

1. Existing RU user categories must already be installed; no categories are created by Horizon.
2. An explicit `manage.py install_horizon_defaults` operation creates 12 **disabled** rules,
   refuses missing categories and never overwrites existing rules or enables global settings.
   It is not a migration and does not run at startup.
3. Hypotheses/risk/threshold/combine/aggregation can then be edited in the existing category UI.
   Add/delete lines to edit hypotheses without training. Keep disabled pending independent calibration.
4. Enabling for an approved shadow experiment needs all three gates: global detector switch,
   category rule `enabled`, and worker deployment `MICE_HORIZON_INFERENCE_ENABLED=true`.
5. Only neural workers need a read-only local model at `MICE_HORIZON_MODEL_PATH` (default
   `/opt/horizon`). CPU is default. `MICE_HORIZON_DEVICE=cuda` is explicit opt-in;
   unavailable CUDA marks the check incomplete instead of stopping other detectors.
6. Existing `MICE_NEURAL_TIMEOUT`, `MICE_NEURAL_SOFT_TIMEOUT`, `MICE_NEURAL_MAX_MEMORY_KB`,
   concurrency and max-tasks controls apply. Size the container for measured model RSS plus
   headroom; do not enable concurrent heavy models without a separate load test.

Offline worker recommendations: `HF_HUB_OFFLINE=1`, `TRANSFORMERS_OFFLINE=1`, network-denied
worker policy. Code always uses `local_files_only=True` and `trust_remote_code=False`.
No model weights, secrets, production DB changes or deployment files are included in this PR.