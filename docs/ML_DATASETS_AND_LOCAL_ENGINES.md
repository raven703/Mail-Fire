# ML datasets + optional SetFit / RuBERT-tiny2 (draft feature)

## Purpose and architecture

No local LLM is required or contacted. The operator may prepare training labels
outside Mail-Fire (including an external LLM) and import the resulting
**approved-to-process** CSV/JSONL into a local PostgreSQL dataset. External LLM
labels are **UNTRUSTED** and **NOT approved** on import.

The existing TF-IDF + Logistic Regression model remains the default lightweight
global multi-label classifier. Two separate optional CPU classifiers are added:
* **SetFit**, trained on a local Sentence Transformers checkpoint;
* **RuBERT-tiny2**, fine-tuned with Transformers as a binary classifier.

Each SetFit/RuBERT model is trained for **one selected Mail-Fire category**,
using positive examples with that label and negative examples without it.
Different categories can publish different engines simultaneously. A TF-IDF
global model stays active independently. If both global and category-specific
models predict a category, the specialized prediction takes precedence.

Published predictions flow into the existing `CategoryRule(kind="ml")`:
categories may combine ML, keywords, Regex, and document references using
ANY/ALL. Creating a category does **not** train a model. Training and
publishing remain separate, administrator-controlled actions.

## Dataset format

JSONL (UTF-8), one object per line:

```jsonl
{"text":"Синтетический внутренний прогноз выручки на следующий квартал","labels":["Финансовая информация"]}
{"text":"Синтетическое публичное объявление о встрече","labels":[]}
{"text":"Синтетическая таблица зарплат и внутренних расходов","labels":["Финансовая информация","Персональные данные"]}
```

CSV (UTF-8, column headers `text,labels`). Multiple labels separated by
semicolon within a CSV field:

```csv
text,labels
"Синтетический внутренний прогноз на следующий квартал","finance"
"Публичное сообщение для клиентов",""
"Синтетические финансовые и персональные сведения","finance;pii"
```

Create the appropriate Mail-Fire categories BEFORE import. In the upload form,
map external LLM labels to existing category IDs, e.g.:

```json
{"finance":"custom-...","pii":"RU_SNILS"}
```

The category name or ID itself is also accepted as an input label without
explicit mapping. Empty labels become `NORMAL` (a negative example; it must
not be combined with positive labels). The importer normalizes and deduplicates
text within one import, rejects conflicting labels/unknown categories, rejects
invalid encodings, and limits uploads to 12 MiB and 5000 rows. Raw dataset file
bytes are not persisted; text and labels are persisted in PostgreSQL.

## Analyst workflow

1. **ML → Наборы данных**: upload an approved CSV/JSONL.
2. Open the dataset: compare source text with suggested categories.
3. Fix labels in the searchable category picker; explicitly confirm the
   reviewed examples. Unreviewed examples are excluded from training.
4. **ML → Обучение**: choose optional dataset (or all approved examples),
   engine, and **one category for SetFit/RuBERT**; choose a model version name
   and minimum F1. A durable training job is queued.
5. The worker computes train/validation/test splits, chooses classification
   threshold on validation ONLY, evaluates on test, and records model metrics,
   dataset ID and snapshot digest.
6. The admin publishes only an eligible model after quality review.
   Publication replaces only a model for the SAME category; an existing
   global TF-IDF model remains available alongside specialized models.
7. The active published models are applied locally during subsequent email
   analysis. Failure of a model does not abort deterministic detectors;
   Mail-Fire records partial analysis with model-error metadata.

Dataset source, version, imported SHA256, text provenance and reviewer ID are
stored in PostgreSQL. Revision changes are audited. Training jobs include a
snapshot hash and fail if the reviewed corpus changed while queued.

## Optional model installation

The default Compose and API/worker images remain lightweight and run without
SetFit/Transformers/PyTorch. To use either neural engine, prepare TWO trusted
pretrained model directories on the deployment host (obtained outside Mail-Fire):

- `data/models/setfit/`: a **Sentence Transformers-compatible multilingual
  encoder** (e.g. `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`)
- `data/models/rubert/`: locally staged pretrained `cointegrated/rubert-tiny2`
  checkpoint and tokenizer.

The files MUST stay local; `.gitignore` excludes `data/models/`. Models
are downloaded/prepared manually in a trusted environment and mounted read-only
into the neural training worker. Do not upload untrusted checkpoints or enable
`trust_remote_code`. The program forces Hugging Face OFFLINE modes.

```sh
# Use a backup and disposable/test PostgreSQL before first deployment.
docker compose -f compose.yaml -f compose.ml.yaml build api worker neural-worker
docker compose -f compose.yaml -f compose.ml.yaml up -d
```

The optional compose overlay rebuilds the API and analyzer worker with neural
dependencies and starts a separate isolated CPU training worker.
`ML_NEURAL_ONLY` partitions job claiming: standard workers handle baseline
TF-IDF and other tasks; neural worker handles SetFit/RuBERT training only.
SetFit and RuBERT are CPU-capable but can be resource-intensive.
No internet is needed at runtime if all dependencies were installed in the
image and weights were staged beforehand. Image build may require network.

`uv.lock` still needs to be regenerated and committed if changing optional
dependency definitions. Current neural Docker stage installs bounded package
ranges independently of the existing frozen baseline lock; the local agent
should pin and verify compatibility before production.

## Data requirements / caveats

- Binary specialized classifier: >=30 distinct APPROVED texts overall, >=6
  positive and >=6 negative, and both classes in each split. For reliable
  results, prepare many more diverse examples; 100s per class are preferable.
- TF-IDF retains its original multi-label train/validation/test rules.
- A classification model finds **types of documents**. Structured extraction
  of individual PII fields still requires NER or rules; this PR does NOT
  introduce PII NER.
- RuBERT inference truncates to 512 tokenizer tokens. SetFit encoder has its
  own context length. Very long emails and attachments may require
  chunk-level classification in a follow-up PR.
- A neural training job needs access to local encoder weights. A published
  model's trained artifact is kept in PostgreSQL; the runtime loads only
  internally produced artifacts.
- This branch does not add automatic batch approval, automatic retraining, or
  automatic LLM integration. An auditor must review external labels.
- Existing known risks remain: shared mutable `Content.analysis`, worker
  lease contention during long DB transactions, top-10 semantic references.
- The project does NOT yet implement full training-text retention/erasure,
  independent artifact signatures, exhaustive RBAC/CSRF coverage or load
  testing. Do not use actual sensitive data without governance and approval.

## Required local agent verification before merge

1. Review code against latest local master and diff all changes.
2. On disposable PostgreSQL: upgrade `0005 → 0006`, downgrade
   `0006 → 0005`, upgrade again; preserve real DB.
3. Run `ruff check .`, `python -m compileall app migrations`,
   all pytest tests including `MAILFIRE_TEST_DB`, and
   `cd frontend && npm ci && npm run build`.
4. Verify import API CSRF/RBAC, corrupted files, unknown labels,
   conflicting duplicates, Unicode/CSV escaping, 12 MiB/5000-row limit,
   source attribution, reviewer changes, user with no originals permission.
5. Test TF-IDF regression, neural job routing, missing pretrained models
   error behavior, active-model publication/rollback per category,
   model error/partial finding, and category AND/OR ML rules.
6. With locally staged trusted weights and a test corpus, actually train,
   publish, reload and run SetFit and RuBERT on CPU. Compare held-out F1.
   **Code-only tests cannot verify pretrained-model compatibility.**
7. Confirm no external model weights, sensitive text or service tokens
   were committed. Test Docker default and `compose.ml.yaml` variants.
8. Verify UI dataset import/review, per-category engine selection and
   model listing. Report all remaining failures; fix before merging.
9. After review, merge locally and rebuild; do not push without the
   user's authorization.
