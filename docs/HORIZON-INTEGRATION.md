# Horizon integration: CPU first, offline

Horizon is a rule method of a custom category, not a system category or new
classification pipeline. Existing neural queue, policies and incidents apply.
Deployment gate, global switch and seeded rules default OFF. GPU defaults OFF;
neither hardware detection nor an environment variable selects CUDA inference.

## Stage offline assets

Supply a trusted, complete checkpoint for
`Horizon-Labs/multilingual-zeroshot-base`, including `config.json`,
`model.safetensors`, tokenizer configuration, special tokens and tokenizer
vocabulary/model files. Keep the original snapshot intact. Configuration must
map label 0 to `not_entailment` and 1 to `entailment`. No remote code is loaded.
Model/tokenizer use `local_files_only=True`. The neural worker sets
HF_HUB_OFFLINE=1 and TRANSFORMERS_OFFLINE=1. Weights are not stored in Git.

Set `MICE_HORIZON_MODEL_DIR` to the checkpoint's absolute host directory.
Compose mounts it read-only at `/opt/horizon`; the host directory must already
exist and be readable/traversable by the image's non-root `mice` user. No web
model mount or torch import is needed. Transfer the full directory, checksums,
required Docker images (docker save/load), Compose files and environment to an
offline server. Stage Python wheels/build images before disconnecting; never
install packages or download weights in a running worker.

## Enable or disable

1. Build the existing neural image using its existing training/runtime build
   contexts and `requirements.neural.lock`. No new worker group is introduced.
2. Explicitly set `MICE_HORIZON_INFERENCE_ENABLED=true`; recreate affected
   runtime services so web/schedulers/worker share that gate. Start the existing
   `neural-inference` profile. Keep it false until the integration is accepted.
3. As administrator, open Detectors -> Horizon, enable and select CPU.
4. Open an applicable custom category, add Horizon Zero-shot, edit hypotheses,
   exclusions, combination, window aggregation, threshold, risk, priority and
   enabled flag in the existing rule editor. Built-in categories remain limited
   to context rules. There is no fixed category allowlist.
5. Add the category to an existing policy. Run ordinary message ingestion.
   Evidence includes source document, excerpt, hypothesis scores, threshold,
   configuration version and actual model weights hash. Category ANY/ALL is
   unchanged; a missing required method cannot satisfy ALL.

UI changes affect subsequent immutable analysis snapshots; already queued work
retains its settings. Disable the global switch or individual rules to stop new
work. Existing findings/history are not deleted by configuration changes.

## Explicit GPU opt-in (not validated on this machine)

CPU mode does not need NVIDIA GPU, CUDA drivers or NVIDIA Container Toolkit.
The current neural dependency lock includes CUDA-capable PyTorch packages;
these libraries alone do not select GPU and do not require a GPU to run CPU.
For GPU on a later server, prepare a compatible NVIDIA driver, NVIDIA Container
Toolkit and CUDA-capable torch image. Apply `compose.neural-gpu.yaml` explicitly
with the base Compose file to expose a GPU to the **same neural service**.
Then select GPU (CUDA) in Detectors -> Horizon. Selecting CPU switches subsequent
jobs back without source edits. No automatic fallback silently changes the
requested device. Unavailable CUDA produces incomplete Horizon analysis and a
visible warning; independent findings continue to policies.

## Current verification limits

See `test-data/horizon-integration/COMPLETION-REPORT.md`. Earlier benchmark and
browser artifacts are historical, not proof of this completion task. No quality
benchmark, calibration, training, GPU inference or production update is part of
this change.

## Verified checkpoint and CPU runtime (2026-11-27)

The complete snapshot is pinned to `a9a5a24e58c794a0f7532d3de842236435a9ae22`.
The per-file SHA-256/size manifest is in
`test-data/horizon-integration/validation/completion/checkpoint-manifest.json`.
Download the full snapshot with huggingface_hub.snapshot_download using that
explicit revision, then verify every file against the manifest and upstream
SHA256SUMS before transfer. Do not execute the upstream training/export scripts.
Keep weights outside the repository and mount them read-only.

Build existing Dockerfiles and all dependencies while connected, use dedicated
image tags, and transfer the prepared images using docker save/load. Offline
runtime was exercised with PostgreSQL/RabbitMQ/parser and existing workers on
an internal Docker network, including cold local model loading. An offline
build from an empty wheel cache was not claimed. Keep all deployment gates OFF
until explicitly enabling a test/accepted installation; CPU remains default.
See the completion report for evidence and precise failure-test limitations.
