# MICE Trainer (experimental)

## Training jobs and deployment packages

Infrastructure-only verification does **not** require training, GPU checks,
base-model downloads, dataset generation or quality evaluation. The historical
smoke commands below are not part of infrastructure verification.

Copy `tools/mice-trainer/job.example.json` to the GPU computer and edit it.
Paths are resolved relative to the job JSON (home `~` is supported).
`evaluation_dataset` is optional and may be omitted or null. `base` is optional;
the default is `~/mice-trainer-data/base_models/rubert-tiny2`. Base weights must
already exist locally; run-job never downloads them. Output must not exist.
Engine names are `tfidf`, `setfit`, `rubert`; device is `auto`, `cpu`, `cuda`.
Epochs and batch_size are positive integers; max_steps is a positive integer
or -1 for training by the specified epoch count. Seed is nonnegative,
min_f1 is in [0, 1]. These job fields are required, even for TF-IDF (whose
native algorithm does not use neural training parameters).

```bash
python tools/mice-trainer/trainer.py run-job /path/to/job.json --dry-run
# Later, separately on the RTX 4060 host, after reviewing the plan:
python tools/mice-trainer/trainer.py run-job /path/to/job.json
```

Dry-run reads and validates the job and dataset, verifies class coverage and
grouped train/validation/test assignments, and prints the model count without
creating outputs, loading neural models, training or inference. CUDA availability
and local base-model usability are checked only when native training is invoked.
TF-IDF needs at least two categories and exports one global multilabel model;
each neural engine exports one binary model per selected category. For two
categories and all three engines the plan contains five models. Dataset size
is limited to 30–10000 examples in this workflow. User category IDs must already
exist in MICE before import; arbitrary category counts retain native engine
constraints and available-memory limits.

Every engine receives the same persisted group split. Native trainers select
thresholds on validation and calculate validation/test metrics and quality gates.
The optional independent dataset must not overlap by ID, group or normalized
text, must cover positive/negative examples, and is evaluated after training
without recalibrating thresholds. A failed quality gate does not silently drop
a model: its status is preserved for review and native manual activation rules.

Results contain plan.json, split.json (no mail text), per-model native exports,
per-model Python stdout/stderr logs, report.json and models.zip. Native-extension
output is not guaranteed to enter the Python log; capture the entire CLI output
externally if needed. The temporary input copy is removed on success or exception
(an abrupt OS/process termination may leave it; protect the output directory).
Failures produce a failed report and no deployable completed package; use a new
output directory for a retry. No resume or parallel training is implemented.

The ZIP format version 1 contains only manifest.json, report.json and explicitly
listed final model.pkl/model.zip artifacts. Manifest records category IDs,
engines, thresholds, metrics, eligibility, library versions and SHA-256 hashes
for artifacts and report. No emails, base snapshots or intermediate checkpoints
are packaged. Neural native archives necessarily contain their final trained
weights; no separate base-model directory is included. SHA-256 detects corruption,
not authenticity; there are no signatures or certificates.

### Web import (administrator only)

1. Open **ML-модели и обучение → Импорт обученных моделей**.
2. Select models.zip and click **Просмотреть пакет**. This only inspects metadata
   and hashes, checks categories/library compatibility and ZIP limits; it does not
   deserialize models.
3. Review categories, engines, thresholds, quality gates and metrics. Select models
   or the entire package. Re-select the **same ZIP** (browsers cannot retain file
   inputs after preview); its digest must match the session's preview digest.
4. Explicitly confirm trust in the source and import. Trusted native artifacts may
   execute pickle/checkpoint code: do not import untrusted packages even if hashes
   match. CPU inference validates selected artifacts, not classification quality.
5. Imported MLModel rows are **inactive**. Use the existing manual activation
   controls later. Import never trains models or changes existing active models.

CLI uses the same service and retains legacy folder imports:

```bash
python manage.py import_trainer_model /trusted/models.zip --trust-local-artifact
python manage.py import_trainer_model /trusted/models.zip --trust-local-artifact --commit
# Optional repeated --model m1 --model m2 selects manifest model IDs.
```

Exact runtime versions of numpy/scikit-learn are required; neural models also
require torch/transformers/safetensors, and SetFit additionally setfit and
sentence-transformers. For torch only, official wheel flavor suffixes `+cpu`
and `+cu<digits>` (for example `+cu132`) are ignored: the complete public
version must still match, including prerelease/dev markers. Other local torch
suffixes and all other critical dependency versions remain strictly checked.
CPU inference validation after explicit trust confirmation is still required.
This conservative policy may require matching server
dependency locks. ZIP limits: 1000 outer entries, 512 MiB per file, 2 GiB expanded
total, 4 MiB manifest/report; native neural ZIPs allow at most 300 entries.
Reverse-proxy/upload limits may be lower. All entries are validated, including
unselected models. No ZIP extraction is performed by package inspection.

Infrastructure tests (isolated environment; no real training):

```bash
python -m pytest tests/test_trainer_infrastructure.py tests/test_trainer_import.py -q
```

Do not run the whole historical Trainer test suite for an infrastructure-only
check: some legacy tests deliberately train TF-IDF or generate smoke datasets.

Run from the repository root in an isolated Python environment. No Django,
PostgreSQL, Celery, RabbitMQ or Docker services are required.

The CLI calls app.ml, app.ml_split, app.ml_engines and app.ml_runtime directly.
Server training continues to default to CPU. No changes to the runtime selection
policy or model serialization formats.

## Environment

Install the native ML dependencies in a dedicated environment, using the
appropriate PyTorch distribution for the training GPU. Record the actual versions
and compare them with the server environment before deploying artifacts. In
particular, scikit-learn pickle compatibility across versions is not guaranteed.

## First smoke test

```bash
source ~/.venvs/mice-trainer/bin/activate
cd ~/Mice
python tools/mice-trainer/trainer.py download-base
python tools/mice-trainer/trainer.py smoke-data --output ~/mice-trainer-data/datasets/smoke.jsonl
python tools/mice-trainer/trainer.py train --engine tfidf --dataset ~/mice-trainer-data/datasets/smoke.jsonl --output ~/mice-trainer-data/output/smoke-tfidf
python tools/mice-trainer/trainer.py train --engine rubert --category pack-ru2-financial-plans --device cuda --max-steps 3 --dataset ~/mice-trainer-data/datasets/smoke.jsonl --output ~/mice-trainer-data/output/smoke-rubert
python tools/mice-trainer/trainer.py train --engine setfit --category pack-ru2-financial-plans --device cuda --max-steps 3 --dataset ~/mice-trainer-data/datasets/smoke.jsonl --output ~/mice-trainer-data/output/smoke-setfit
CUDA_VISIBLE_DEVICES="" python tools/mice-trainer/trainer.py predict --model ~/mice-trainer-data/output/smoke-rubert --text "Закрытый бюджет будущего года"
CUDA_VISIBLE_DEVICES="" python tools/mice-trainer/trainer.py predict --model ~/mice-trainer-data/output/smoke-setfit --text "Закрытый бюджет будущего года"
```

The smoke fixture is intentionally simplistic and is not suitable for measuring
real-world accuracy. Use unique output directories for each run. A failed
training run may leave an incomplete output directory; do not deploy it.

## Dataset and training

JSONL rows require id, group_id, labels, and either text or subject plus body.
Only the text is passed to the classifier. Category IDs are arbitrary nonempty
strings. The first smoke fixture uses pack-ru2-financial-plans and pack-ru2-pricing.
Exact normalized duplicates are rejected. Optional preassigned split metadata
must be consistent across groups. Otherwise the native deterministic 60/20/20
split is used and class coverage is checked. Split assignments are exported.
Near-duplicate and semantic-group audits are required upstream.

TF-IDF produces one global model. Each neural engine produces one binary model
per category. Use explicit --epochs and --max-steps for full training after
the GPU smoke test. Default step limits preserve native behavior (120/150).
Use --max-steps -1 to request epoch-based training, subject to the installed
training-library version supporting that value.

Base weights are downloaded only by the explicit download-base command.
It resolves and records the model revision; subsequent training uses local
files. The model source is cointegrated/rubert-tiny2, as in native MICE.

Output directory: native model.pkl or model.zip, training.json (thresholds,
metrics, quality gate, hash, package versions), split.json. Keep these together.
predict and evaluate reload native artifacts using CPU runtime. Evaluate on an
independent JSONL corpus; exact text and scenario group overlap is rejected,
but near-duplicate detection still requires external corpus auditing.
Never adjust thresholds against the final independent evaluation set.

Only load artifacts created in a trusted environment. A hash is not an
authenticity guarantee. Native artifacts can contain executable pickle data.
The explicit server import command below creates inactive models only.
Do not copy model files directly into the production DB.

## Automatic installation and diagnostics

```bash
bash /home/user/Mice/tools/mice-trainer/install.sh
/home/user/.venvs/mice-trainer/bin/python /home/user/Mice/tools/mice-trainer/trainer.py doctor --require-cuda
```

Replace `/home/user/Mice` with your absolute checkout path. Requires Linux/WSL2,
Python 3.12+ with venv and internet access to PyPI. No apt, sudo, server, Docker
or driver installation. On WSL install the NVIDIA driver on Windows only.
The installer uses native `requirements.training.lock`, `requirements.neural.lock`
and `tools/mice-trainer/requirements-dev.lock`, runs pip check and real CUDA
matrix multiplication when a GPU is available. Set `MICE_TRAINER_ENV` or `PYTHON`
to override the environment/interpreter. All four data directories are created:
`/home/user/mice-trainer-data/{datasets,base_models,output,logs}`.

For repeatable base downloads use
`--revision e8ed3b0c8bbf4fb6984c3de043bf7d2f4e5969ae`. Training/inference are offline.
`doctor` writes `/home/user/mice-trainer-data/logs/doctor.json`.
Training automatically tees stdout/stderr and library progress into timestamped
files in `/home/user/mice-trainer-data/logs/`.

## Arbitrary categories, devices and seed

`--category ID` selects one neural binary model; run once per category.
TF-IDF uses all corpus labels or a subset selected with `--categories ID1 ID2 ...`
(at least two labels, as required by the native global classifier).
Neural models together implement multilabel classification exactly as in MICE.
Unlisted labels on a row mean negative examples: annotations must be complete.
`labels: []` is supported. No fixed category catalog is required in the Trainer.

`--device auto` (CLI default) selects CUDA if available, otherwise CPU.
`cuda` fails explicitly if unavailable; `cpu` forces CPU including SetFit's
underlying Trainer. Native server training still defaults to CPU.
TF-IDF always uses CPU regardless of this argument.
`--seed 42` controls grouped splitting and training. Existing explicit split
assignments are preserved. Grouped 60/20/20 proportions apply to group counts,
not necessarily row counts. There is no automatic search for a favorable seed.

Example full epoch-based training (positive max-steps overrides epochs):

```bash
/home/user/.venvs/mice-trainer/bin/python /home/user/Mice/tools/mice-trainer/trainer.py train \
  --engine setfit --category pack-ru2-pricing --device auto \
  --batch-size 8 --epochs 2 --max-steps -1 --seed 42 \
  --dataset /home/user/mice-trainer-data/datasets/B-6000.jsonl \
  --output /home/user/mice-trainer-data/output/B6000-setfit-pricing
```

For RuBERT change `--engine rubert` and use a new output directory.
Reduce batch size on CUDA OOM. RuBERT truncates at 512 tokens.
`--min-f1` controls the eligibility gate, never publication.

**Semantic leakage:** the dataset author must assign the same `group_id` to
every variant of a scenario/template/thread. Automatic semantic clustering or
near-duplicate detection is not performed. Different hashes do not prove semantic
independence. B-1000 must be independently authored and grouped, not a renamed
copy of training examples. Evaluation rejects text/group overlap with all three
training partitions and never adjusts thresholds.

## Real end-to-end verification

```bash
/home/user/.venvs/mice-trainer/bin/python /home/user/Mice/tools/mice-trainer/smoke_check.py
/home/user/.venvs/mice-trainer/bin/python -m pytest \
  /home/user/Mice/tests/test_ml.py /home/user/Mice/tests/test_ml_datasets.py \
  /home/user/Mice/tests/test_mice_trainer.py /home/user/Mice/tests/test_trainer_import.py -q
CUDA_VISIBLE_DEVICES='' /home/user/.venvs/mice-trainer/bin/python /home/user/Mice/tools/mice-trainer/trainer.py evaluate \
  --model /home/user/mice-trainer-data/output/B6000-setfit-pricing \
  --dataset /home/user/mice-trainer-data/datasets/B-1000.jsonl \
  --output /home/user/mice-trainer-data/output/B6000-setfit-pricing/B1000.json
```

The smoke suite trains five native models (global TF-IDF and both initial
categories for each neural engine), reloads them on CPU, evaluates a separate
plumbing fixture, repeats training and compares metrics, splits and CPU scores.
All artifacts/logs remain outside Git. See `TEST_RESULTS.md` for actual results.
The fixture is not a realistic semantic benchmark; B-6000/B-1000 quality remains
to be measured. A seed is not a cross-hardware or cross-version bitwise guarantee.

## Trusted transfer to the existing MICE server

1. Transfer the complete export directory via a trusted channel. Compare hashes
   with a manifest received separately. Hashes alone do not prove authenticity.
2. Align server dependency versions with native locks, especially scikit-learn.
3. Deploy this branch's import command to the existing server. Do not install the
   server on the training computer. Ensure referenced category IDs already exist.
4. Run the following **on the server**, initially without `--commit`:

```bash
CUDA_VISIBLE_DEVICES='' python /srv/mice/manage.py import_trainer_model \
  /srv/mice-import/B6000-setfit-pricing --trust-local-artifact
```

After backup and administrator approval, add `--commit --name B6000-setfit-pricing`.
Paths above are deployment examples; replace with your server's absolute paths.
Dry run verifies SHA-256, scikit-learn version, native CPU inference and category
existence. Commit creates a new `MLModel(active=False)` and does not update any
existing model/category or activate the import. Repeat import creates another row.
Quality-gate eligibility is retained; publication stays a separate manual native
operation. The management command needs Django/DB **only on the existing server**.
It was not executed against the working database during development.

Never import untrusted pickle/joblib/checkpoints: they can execute code.
There is intentionally no public upload endpoint or automatic publication.
