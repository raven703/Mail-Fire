# RU_SNILS regression — 2026-11-20

## Diagnosis
advanced_detectors and document_templates used different regexes: only the template accepted a hyphen before checksum; neither expressed the compact 9+hyphen+2 format reliably. The previous checksum arithmetic was equivalent to the new arithmetic for ordinary 11-digit inputs, but accepted all-zero placeholders. Seven control false positives were `000-000-000 00`.

The 14 benchmark positive emails ALL contain checksum-invalid synthetic identifiers, not valid identifiers. They must not be reported as checksum-confirmed. This is an observed dataset property; Ground Truth was NOT edited.

parse_mail -> sandbox/parser service extraction (including HTML, DOCX tables, XLSX cells) -> processing concatenates extracted text with body -> pii(text). document_templates is called per attachment only with registered Reference document_template; the protected references snapshot has none configured. Thus relying on templates alone cannot fix normal analysis. Shared snils_matches now runs directly in pii and is also used by templates; no reference registration required for pii.

## Implementation
app/snils.py: ASCII digits, separator normalization (spaces including NBSP, hyphen/en/em dashes), bounded 11-digit candidates; checksum weights 9..1, sums 100/101 map to 00, larger sums modulo 101 with remainder 100 mapped to 00. All-zero nine-digit identifiers excluded. Checksum reference: Federal Tax Service, nalog.gov.ru, page “Страховые взносы”, section “Алгоритм формирования контрольного числа СНИЛС”.

Findings keep category RU_SNILS and include verification=confirmed/suspected, checksum_valid, confidence and reason. Confirmed confidence .85/risk 60; suspected confidence .45/risk 40, require explicit nearby SNILS/insurance-account wording and explain invalid checksum. This verifies arithmetic, NOT registration or ownership. Stored findings retain flags; document-template findings also preserve them. Existing category-based policies are unchanged and may still react to suspected findings.

## Tests
49 passed, 1 skipped: tests/test_snils_formats.py, tests/test_snils_pipeline.py, tests/test_document_templates.py, tests/test_advanced_detectors.py, tests/test_passport_formats.py, tests/test_passport_pipeline.py. Skip: existing gitleaks test (binary not installed locally). Fresh examples cover valid/invalid checksums, arithmetic boundaries 100/101/201/202, compact 100080947-00, spaces/dashes, zero/long numbers and distant context. MIME integration covers body, HTML, DOCX tables and XLSX for both valid and invalid identifiers.

## Live selected regression
POST /api/messages/{id}/reanalyze for 14 SNILS positives + all 60 controls. 74/74 ANALYZED, zero message errors and zero pending jobs. Original SHA-256 checked for every selected EML.

|Category-level detection|TP|FP|FN|TN|
|---|---:|---:|---:|---:|
|Before|0|7|14|53|
|After, confirmed OR suspected|14|0|0|60|

All 14 detections are SUSPECTED (invalid checksum). Confirmed findings: 0. Benchmark valid-positive denominator: 0, therefore confirmed recall cannot be estimated on this set. Invalid-positive detection: 14/14, all correctly marked suspected; none falsely promoted to confirmed. Confirmed-only evaluation against original semantic labels remains TP=0/FN=14, intentionally. Valid synthetic examples pass separate tests, including each attachment type; they were not added to benchmark.

Not a full 300-email rerun; no claim about other 226 emails or unseen data. This benchmark was inspected during development and is no longer an independent holdout for this heuristic.

Protected policy/category/settings/model/training/dataset/reference snapshots identical before/after. No training; no model/dependency changes. API and worker deployed as mailfire-backend:snils-validated, based on previous passport-validated image with only three changed application files; byte-for-byte comparison verified both containers. Frontend/parser not redeployed. Deployment compose addition: /home/user/mailfire-deploy-pr10/snils.override.yaml (include after override.yaml on future deploys).

Artifacts: baseline.json, after.json, comparison.csv, metrics.json, verification-metrics.json. Original benchmark and historical report untouched.
