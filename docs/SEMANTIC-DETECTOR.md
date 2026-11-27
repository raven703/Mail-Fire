# Automatic semantic reference detector

Audit: records/semantic.py already implements local MiniLM embeddings, reference indexing and manual search. Neither deterministic analysis nor optional ML/LLM inference emitted SEMANTIC_REFERENCE. This change routes an optional semantic.detect job through the existing semantic queue before policy evaluation (and before optional ML/LLM). No additional worker group, schema or external LLM.

## Deployment

- Set MICE_SEMANTIC_INFERENCE_ENABLED=true in the existing deployment environment.
- Start the existing semantic profile/worker (docker compose --profile semantic up -d --build). Recreate runtime workers so the gate propagates.
- MICE_SEMANTIC_THRESHOLD=0.85 is the initial cosine similarity threshold; valid range (0,1]. It is not a calibrated probability. Set a different value in the environment and recreate runtime workers.
- Enable the semantic detector in detector settings and ensure SEMANTIC_REFERENCE is active.
- Index ordinary reference documents using the existing reference indexing UI. Template-only references are excluded. MICE_SEMANTIC_AUTO_INDEX=true optionally indexes new references.
- Add SEMANTIC_REFERENCE to a policy and verify that the policy matches risk 50. Existing policies are not changed automatically.

No references is explicitly skipped. Missing index, embedding errors and limits mark the analysis PARTIAL; deterministic findings still continue to policy evaluation. The worker snapshots threshold and reference IDs, compares body and attachments independently, stores best evidence per source/reference with similarity and excerpts. It reads the current index for those IDs (not an immutable vector snapshot). Limits: 500 query chunks, 100 findings, bounded batch size. Default gate OFF to avoid sending jobs to a nonexistent optional worker; enabling without starting the worker leaves jobs waiting. No speed or quality claim before real calibration.

## Verification

Run Django pipeline.test_semantic_detection, pipeline.test_inference, pipeline.test_unified_analysis, records.test_semantic_gc on the PostgreSQL/pgvector test environment. Then run real indexed reference, exact copy, paraphrase, unrelated text, missing index, worker failure, disabled detector, attachments and policy integration cases using the installed offline model. Measure precision/recall before production enablement.
