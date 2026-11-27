# Integration completion follow-up — partial, not accepted for merge

Base: 053f23c. Scope: updated PR39 Completion task — integration only.

## Changes

- Existing Compose runtime environment now carries disabled-by-default Horizon
  deployment gate. Existing neural service mounts a pre-staged checkpoint
  read-only, with offline flags. No new worker/queue/category was added.
- Administrator can persist explicit CPU/CUDA choice in existing detector
  settings. CPU is default; environment/hardware cannot silently enable GPU.
  Device choice is captured in the immutable configuration snapshot.
- Horizon exceptions no longer erase all custom findings. Refresh is restricted
  to complete source results and Horizon-bearing categories; other custom and
  native evidence remains. Added failure-preservation regression.
- Web no longer probes its own filesystem to claim worker model availability.
  Added configured device, gate, worker/task state and incomplete-analysis warning.
- Added optional GPU infrastructure override for the same neural service and
  offline installation/handoff documentation in docs/HORIZON-INTEGRATION.md.

## Executed tests

- `manage.py test pipeline records policy_engine identity --noinput`:
  229 tests run, 13 opt-in skipped, no failures (28.423 seconds).
- `pytest tests/test_horizon.py tests/test_category_rules.py
  tests/test_analysis_status.py -q`: 31 passed (5.07 seconds).
- `docker compose --profile neural-inference config --quiet`: passed.
- `git diff --check`: passed.
- HTTP/form tests verify CPU default, persistence of explicit CUDA/CPU selection,
  invalid device rejection, plus existing rule editing and permission tests.
- Functional controlled-score tests cover policy idempotence, sibling inference,
  ANY/ALL and independent findings. No quality benchmark was run.

## Blockers / outstanding acceptance checks

Docker is available (29.6.1), but the Horizon checkpoint and the historical
`/home/user/hf-model-benchmark-data` / `.venvs/horizon-integration` environment
are absent here. Searches covered Linux home/cache and Windows user directories;
the mounted D: directory is empty. Existing MiniLM/RuBERT weights are NOT Horizon
and were not substituted. No checkpoint was downloaded or trained.

Consequently real CPU neural-worker/container E2E with disposable RabbitMQ,
native ingestion/parser, body and attachment evidence has NOT been completed.
No live worker outage/timeout exercise or browser create/edit/reload check was
performed. Earlier saved CPU/browser artifacts do not close these checks.
GPU inference was NOT tested; no GPU is available. Missing-GPU status still
needs verification against a real prepared CPU worker after weights are staged.
The CUDA device reservation override is preparatory, not validated GPU support.

The GPU-aware neural dependency lock already contains CUDA libraries; CPU does
not require a GPU/driver/toolkit, but a minimal CPU-only wheel image was not built
in this follow-up. Build/export the image and all wheels before offline transfer.

Production deployment, data and settings were not modified. PR must remain
unmerged and its real E2E/browser acceptance items unchecked.