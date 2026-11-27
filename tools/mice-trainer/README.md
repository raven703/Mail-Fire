# MICE Trainer (experimental)

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
Only the text is passed to the classifier. The only supported category IDs
in this initial CLI are pack-ru2-financial-plans and pack-ru2-pricing.
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
Database import and activation on the actual MICE server are not implemented
by this initial CLI; they require a separate trusted deployment workflow and
compatibility tests. Do not copy model files directly into the production DB.
