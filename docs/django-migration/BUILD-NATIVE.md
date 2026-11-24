# Experimental native build

The target stack is defined in `compose.django.yaml`. It uses Django, HTMX,
Celery, RabbitMQ, PostgreSQL/pgvector, Nginx and isolated analysis services.
Use dedicated experimental configuration for deployment.

## Images and profiles

| Dockerfile | Content and profile |
|---|---|
| `Dockerfile.django` | Django and Celery coordinators, separate from OCR/model dependencies |
| `Dockerfile.django-web` | Nginx and vendored static assets |
| `Dockerfile.django-parser` | Standalone bounded parsing and deterministic analysis |
| `Dockerfile.django-ocr` | Parser plus CPU OCR dependencies and local weights |
| `converter/Dockerfile` | Isolated Office converter |
| `Dockerfile.django-training` | Optional TF-IDF trainer, `training` queue |
| `Dockerfile.django-neural` | Optional SetFit/RuBERT trainer, `neural_training` queue |
| `Dockerfile.django-semantic` | Optional MiniLM embeddings and semantic worker |

Build contexts refer to the native images. The target build definitions do not
require React, Node.js, FastAPI, SQLAlchemy or Alembic. Frozen dependencies come
from the existing lockfiles. For the next stage, build the base, pipeline and
needed optional profiles independently. Neural training uses local snapshots in
`MICE_NEURAL_MODELS_DIR` and can be deployed with the separate TF-IDF worker.

ML and LLM inference gates default to false. The optional inference workers use
their own profiles. The LLM worker additionally requires an enabled stored
configuration and explicit transfer authorization. A model publication selects
an artifact and leaves inference off. Enable `MICE_SEMANTIC_AUTO_INDEX=true`
only in deployments running the optional semantic worker to enqueue non-template
references at upload.

## Offline bundle

`python scripts/native_offline.py export /absolute/new/bundle` exports the built
images, Compose file and probe script with checksums. Add
`--neural-models /absolute/materialized/snapshots` to include the neural image
and local snapshots. `verify` checks archive hashes and `load` additionally
imports images and verifies identities. Neither starts containers. On the target,
use the bundled Compose file and probe script together and start Compose with
local images and builds disabled.

`verify /absolute/bundle --restore-models /absolute/new-models` restores verified
regular model files into a new directory. Manifest checksums cover integrity.
Publisher authentication and upgrade/rollback procedures are separate.

## Resource collection

Compose samples CPU, memory, process limits, disk and exposed GPU locally.
Trusted services publish bounded measurements to a project volume. Parser/OCR
and Converter answer inside their existing isolated networks. The maintenance
worker reads the volume read-only, polls those endpoints and stores the history.
CPU is derived from cgroup counter deltas and quota. The view labels stale/missing
samples. No Docker socket is required.

Only Compose configuration, Python/Django and static checks were performed in
this continuation. Image installation, dependency closure during real builds,
offline restore, GPU device exposure and deployed resource probes remain for
acceptance. The resource index and system-category migrations are supplied and
were not applied.
