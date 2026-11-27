# Horizon: preregistered development / holdout protocol

This experiment is isolated under `/home/user/Mice/test-data/horizon-benchmark`.
It inherits the pinned Horizon weights, dependency environment and CUDA runner
principles from PR #37. No application, Docker, database or detection configuration
is changed. No training, new corpus, B-6000, OCR selection by gold, or model conversion.

## Inputs and safety boundary

Reuse real frozen extracted `text` from hash-verified observations, including the
recorded attachment text/OCR. Do not substitute attachment-visible-text hints.
MIME subject/body metadata, labels, expected OCR, scenario, group, detector scores,
normalization results and findings are not model features. `prepare_inputs.py`
separates text and labels. `infer.py` reads text files only. Partial extraction
stays in the cohort and is documented. No silently discarded messages.

B350 and B400 (all 750 examples) are development data. Broad hypothesis and
decision search is optimistic on these sets. B500 was already used by MICE; it is
held out from Horizon selection, not an independently unseen corpus. Before any
B500 inference, commit `best_config.json`, `hypotheses.json`, `freeze.json` and
the complete decision/inference scripts. The B500 runner checks committed freeze
and uses only the union of selected hypotheses. No B500 threshold optimization,
post-result prompt changes, or model selection. FP32 is the primary reference;
FP16 uses the identical selected decisions as a quality/speed ablation.

## Search

Eight manually authored hypotheses per category (96 total): Russian short name,
English short name, Russian detailed description, English concrete action,
Russian concrete action, English topical template, Russian and English exclusion.
Category meanings come from the actual RU2 pack, retained in `hypotheses.json`.
Restriction markers are not proof of unauthorized disclosure. Requests to send
data/secrets count where MICE definitions include them. Threat news, fiction,
training, public information and mere policy discussion are explicit negatives.

Per category: 6 positive singles; 15 pairs each combined by min/mean/max;
mean of all six positives; 12 positive/exclusion pairs using clipped subtraction
or positive × (1 − exclusion): **76 candidates**. Exclusions are local to a
window, avoiding a benign quoted passage vetoing an unrelated real threat.
Each tests max/mean/top-two-mean/noisy-OR across windows and thresholds
0.10..0.95 inclusive, step 0.05. 5,472 decisions/category/dtype; 131,328 across
12 categories and two dtypes. Noisy-OR is an empirical heuristic, not a calibrated
probability; overlapping windows are dependent. Long prompts are not preferred.

Select maximum pooled B350+B400 F1 per category. Tie-break: fewer FP, fewer
hypotheses, higher threshold, first explicit enumeration. Pooled choice may mask
corpus differences; report both separately. FP16 optimum on development is
diagnostic only and does not change selected primary configuration.

## Inference and performance

RTX 4060, CUDA only, eval + inference_mode, no CPU fallback. Local audited
revision `a9a5a24e58c794a0f7532d3de842236435a9ae22`, no remote code. Explicit
two-label `not_entailment=0`, `entailment=1`; score is full two-logit softmax
probability of index 1. No invented neutral class and no normalization across
categories. 900-character windows / 100 overlap; maximum 512 paired tokens,
truncate premise only. Fixed batch size 16, eager attention, TF32 disabled.
Cache every window/hypothesis score with ordered hypotheses and text hashes.

Measure per-message warmed inference incl tokenizer and host/device transfers,
exclude extraction/loading/output writes. Record mean/p50/p95 and throughput,
process peak RSS and PyTorch allocated/reserved peak VRAM (not total desktop
usage). Separate 12/24/48/96-hypothesis speed experiment uses first 12 B350
messages, three passes; it is not a representative length benchmark. B500
performance uses selected union; development uses all 96. Never directly call
these workload differences a precision-only speedup.

## Metrics and interpretation

All 12 independent labels: TP/FP/FN/TN, precision/recall/F1, tie-aware
non-interpolated PR-AUC (average precision, explicitly not trapezoidal AUC),
FPR over category negatives. Safe means zero expected *user* categories, not
necessarily absence of builtin-sensitive entities. Report category safe-FP rate
and union-of-categories fraction of safe messages falsely flagged.
Zero-denominator precision/F1/AP are zero; safe rate is null if no safe examples.
Micro F1 pools all decisions; macro averages all 12 categories. Inspect corpus
groups and fixed length bins <=900, 901–1800, >1800 without using them as features.
Obfuscation is the corpus-authored group, not synthetic transformations here.

Historical RU3/RU4/TFIDF/SetFit/RuBERT comparison must verify B500 manifest,
observations hash, ID universe, category scope and per-message expected labels.
Reuse saved predictions, never run production or silently claim a new baseline.
No legal/production-readiness conclusion from synthetic benchmark performance.