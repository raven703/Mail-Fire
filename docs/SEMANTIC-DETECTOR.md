# Automatic semantic reference detector

Audit: records/semantic.py already implements local MiniLM embeddings, reference indexing and manual search. Neither deterministic analysis nor optional ML/LLM inference emitted SEMANTIC_REFERENCE. This change routes an optional semantic.detect job through the existing semantic queue before policy evaluation (and before optional ML/LLM). No additional worker group, schema or external LLM.

## Deployment

- Set MICE_SEMANTIC_INFERENCE_ENABLED=true in the existing deployment environment.
- Start the existing semantic profile/worker (docker compose --profile semantic up -d --build). Recreate runtime workers so the gate propagates.
- MICE_SEMANTIC_THRESHOLD=0.85 is the initial cosine similarity threshold; valid range (0,1]. It is not a calibrated probability. Administrators can save a database override in detector settings without restart. The new value applies to subsequent analysis snapshots; queued jobs keep their original threshold. Changing the deployment gate still requires recreating runtime workers.
- Enable the semantic detector in detector settings and ensure SEMANTIC_REFERENCE is active.
- Index ordinary reference documents using the existing reference indexing UI. Template-only references are excluded. MICE_SEMANTIC_AUTO_INDEX=true optionally indexes new references.
- Add SEMANTIC_REFERENCE to a policy and verify that the policy matches risk 50. Existing policies are not changed automatically.

No references skips the optional queue. Missing index, embedding errors and limits mark the analysis PARTIAL. Deterministic findings are evaluated immediately, independently of the optional worker; semantic completion requests a newer policy evaluation. Thus a stopped worker cannot block incidents from the other detectors, although semantic work itself remains pending until the worker returns. The worker snapshots threshold and reference IDs, compares body and attachments independently, stores best evidence per source/reference with similarity and excerpts. It reads the current index for those IDs (not an immutable vector snapshot). Limits: 500 query chunks, 100 findings, bounded batch size. Default gate OFF. No additional worker group, schema or external LLM is introduced.

## Verification

Run Django pipeline.test_semantic_detection, pipeline.test_inference, pipeline.test_unified_analysis, records.test_semantic_gc on the PostgreSQL/pgvector test environment. Then run real indexed reference, exact copy, paraphrase, unrelated text, missing index, worker failure, disabled detector, attachments and policy integration cases using the installed offline model. Measure precision/recall before production enablement.

## UI readiness
The detector settings show configured switch, deployment gate, active category, current-model indexed reference count and latest resource sample status. This is not a model/queue health check. Threshold can be saved by an administrator; database setting overrides the environment default and is frozen in the analysis configuration snapshot. Reference library distinguishes fingerprint and semantic index, excluding document-type templates. Validate permissions and all readiness states on the deployed UI.
