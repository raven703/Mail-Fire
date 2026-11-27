# PR #36 review (base 6b5cbbeb)

## Scope and isolation

Review performed in a separate worktree. Production branch, deployment and
configuration were not changed. PostgreSQL/pgvector tests used the disposable
`pr36_review` / `test_pr36_review` databases. No browser tests, B400/B500,
training, external LLM, new worker group, schema or performance redesign.

## Findings and corrections

1. **High:** an absent semantic worker held back policy evaluation of all other
   findings. Queue deterministic policy evaluation immediately and a newer
   evaluation after semantic completion. Existing policy locks/revisions fence
   out-of-order completion. Tested incident creation before semantic execution,
   then incident enrichment with body and attachment semantic findings.
2. Skip the optional queue when there are no ordinary references. Exclude
   template references again at comparison time, not only when scheduling.
3. Superseded/deleted-message jobs finish without loading the model.
4. Reject zero embeddings (undefined cosine similarity), in addition to invalid
   dimension, nonfinite values and incomplete batches.
5. Do not encode document-type templates during reindexing.
6. Show the latest semantic task outcome separately from resource heartbeats;
   a healthy worker sample is not proof of successful model loading. Preserve
   the configured toggle independently of readiness.
7. Correct restart instructions: saved UI threshold overrides the environment
   for subsequent configuration snapshots, not already queued work.

## Executed verification

219 Django tests passed in 30.592 seconds (including opt-in real offline MiniLM integration and inherited failure regressions). Additionally 22 focused pytest checks and 5 OCR evidence tests passed. Django system check passed;
`makemigrations --check --dry-run` reported no changes. Test modules:

- pipeline.test_semantic_detection
- pipeline.test_semantic_review
- pipeline.test_inference
- pipeline.test_unified_analysis
- records.test_semantic_gc
- records.test_semantic_settings
- policy_engine.test_category_catalog

Coverage includes automatic reference indexing, template exclusion, actual
pgvector matching with controlled embeddings, body/attachment boundaries,
policy application and incident enrichment, HTTP settings and access checks,
no references, missing/current versus old-model index, disabled detector and
deployment gate, model failure, terminal worker failure, superseded evidence,
and preservation of unrelated findings. HTTP checks use Django's test client,
not a browser. Category descriptions were source-reviewed: fingerprint copy
matching is distinct from probabilistic local MiniLM similarity, which is not
proof of a leak and requires indexed ordinary references.

## Corpus and real-model calibration

`test-data/semantic-reference-small/corpus.json` contains three synthetic Russian
references and fifteen queries: three each exact, partial, paraphrased,
thematically related safe, and unrelated. Nine positives and six negatives.
`scripts/check_semantic_reference_small.py` runs the existing local MiniLM and
pgvector code, rolls reference/index writes back, refuses production database
names, and calculates TP/FP/FN/TN, Precision, Recall and F1 for thresholds
0.70, 0.75, 0.80, 0.85, 0.90 and 0.95. Results are document-level, any reference
match. This small calibration set is not independent production validation.

The completed FastEmbed cache was found at `/home/user/Mice/embedding-models`.
It was copied with structure and symlinks intact to
`/home/user/mice-pr36-review/embedding-models`; 14 regular files were verified
byte-for-byte by SHA-256. No model was downloaded again. The cache is excluded
from Git and Docker build context. The ONNX weights SHA-256 is recorded below.

`EMBEDDING_CACHE_DIR` points to that copied cache for the isolated semantic
handler tests. `records.semantic.encoder()` uses `local_files_only=True`;
HF_HUB_OFFLINE=1 and TRANSFORMERS_OFFLINE=1 were set. The opt-in real model test
also rejects Python socket connections while loading/encoding: 384 dimensions,
reference indexing, independent body and attachment findings, then policy
incident enrichment all passed. Handlers run through existing job claims and
fenced completion against real pgvector. No production worker was restarted.
`compose.semantic-offline.yaml` supplies a read-only cache mount and offline
variables for a separately provisioned test semantic worker. This override was
not applied to production; a live broker/worker outage drill was not performed.
Worker absence is tested by leaving semantic work unexecuted while confirming
that deterministic policies still create an incident.

| Threshold | TP | TN | FP | FN | Precision | Recall | F1 |
|---|---:|---:|---:|---:|---:|---:|---:|
| 0.70 | 8 | 6 | 0 | 1 | 1.0000 | 0.8889 | 0.9412 |
| 0.75 | 7 | 6 | 0 | 2 | 1.0000 | 0.7778 | 0.8750 |
| 0.80 | 7 | 6 | 0 | 2 | 1.0000 | 0.7778 | 0.8750 |
| 0.85 | 5 | 6 | 0 | 4 | 1.0000 | 0.5556 | 0.7143 |
| 0.90 | 4 | 6 | 0 | 5 | 1.0000 | 0.4444 | 0.6154 |
| 0.95 | 3 | 6 | 0 | 6 | 1.0000 | 0.3333 | 0.5000 |

Preliminary recommendation: **0.70** for analyst-reviewed detection on this
small corpus, not an automatic production-default change. The missed partial
copy scores 0.6546; the closest safe thematic example scores 0.6863. The narrow
margin and six negatives do not establish a low production false-positive
rate. All exact copies match; all three paraphrases pass at 0.70. Fingerprint
REFERENCE_DOCUMENT remains necessary for short literal fragments. No threshold
or architecture was changed on the strength of this synthetic calibration.
Full per-query scores and corpus hash are in
`test-data/semantic-reference-small/results.json`.

## Additional regression corrections

The full suite found a stale skipped-check assertion lacking `semantic`; updated
it to reflect explicit optional-analysis omission. Legacy pytest category tests
patched a removed ORM helper; changed only their harness to exercise existing
persistence-independent `evaluate_groups`, without changing detector behavior.

## Limits and delivery

UI checks are HTTP/template tests, not browser tests. No actual live-worker
restart, real MIME extraction end-to-end outage exercise, B400/B500 or training
was performed. No production configuration, data or branch was modified.
Changes are intended for the existing PR36 branch; PR must remain unmerged.

ONNX SHA-256: `634d0f66c29dc934c8fa72b8a4fe91dd4d420a22f1d82a241058d4316e659a99`.
