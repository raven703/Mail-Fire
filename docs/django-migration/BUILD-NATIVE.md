# Experimental native build

Only use dedicated experimental secrets/data. Never reuse the source deployment.
No services are started by dependency lock generation or Compose config validation.

## Images

- `Dockerfile.django`: Django/ORM/Celery coordinators and web; no sklearn, torch,
  transformers, fastembed, OCR libraries or model weights.
- `Dockerfile.django-parser`: standalone bounded parsing/deterministic algorithms,
  no FastAPI/SQLAlchemy/Alembic/Redis dependency closure and no OCR weights.
- `Dockerfile.django-ocr`: Parser plus RapidOCR/Paddle CPU dependencies and weights.
  This secret-free service is separate from the light OCR coordinator worker.
- `Dockerfile.django-training`: optional `training` profile, original TF-IDF trainer.
  Neural SetFit/RuBERT training still requires a separate offline neural dependency
  lock/image and local model provisioning; do not claim neural build support yet.
- `Dockerfile.django-semantic`: optional `semantic` profile, original multilingual
  MiniLM FastEmbed model materialized at build; runtime local-files-only.

Compose additional build contexts explicitly connect images; no legacy/local backend
image is required. Generate dependency closures with:

```sh
python scripts/export_native_locks.py
docker compose -f compose.django.yaml --profile pipeline build
docker compose -f compose.django.yaml --profile training --profile semantic build
```

Build-time package/model downloads require network access. Airgap wheel/model/image
export and restore acceptance remains open. Closures use exact existing uv.lock
versions, not freshly resolved dependencies. Full image builds have not been run
in this checkpoint. Lock compatibility must be established by those future builds.

## Safety

Training/publishing a version never enables detection inference. LLM configuration
is forced disabled. Semantic jobs only run when the semantic worker is started.
GC defaults to preview, refuses other active jobs and retains all durable JSON
references including terminal-job outputs. This favors retention over accidental
loss; terminal job expiry/release is intentionally not automatic. GC currently
uses bounded maintenance table locks and requires PostgreSQL concurrency acceptance
before production use. Legal-held messages keep their FK-linked content/blobs.