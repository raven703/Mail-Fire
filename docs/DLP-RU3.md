# RU3 candidate — deterministic DLP

All 12 RU2 categories and their 33 original rules reviewed; original baseline and benchmark snapshot left intact. New candidate contains 36 rules. Priority: pricing and customer exports (old benchmark recall 36.67% and 50%). Added alternative terms and independent context rules; tightened some broad combinations and windows for threats/phishing/sabotage. Weights are heuristic, not validated calibration. No global exclusion phrases added because the matcher suppresses the entire document. No ML/LLM changes.

Eight restored policies represented in the candidate. Removed unused semantic category from source-code policy and low-risk duplicate email/phone categories from PII policy; this does not disable their detectors. Other thresholds unchanged pending a new evaluation. Historical data not rewritten.

For restored RU2 deployments, preview with `python manage.py apply_ru3_candidate` and explicitly apply with `python manage.py apply_ru3_candidate --apply`. The command refuses locally changed baseline rows; it does not change policy enabled state. Back up DB before applying. Do not run restore_original_dlp afterwards (it restores the old baseline). The generic rulepack import is not the upgrade path for restored RU2.

Validate on independent dev/holdout data, report per-category and per-policy precision/recall/F1 and inspect false positives. Do not claim improvement before running the benchmark. Existing benchmark is historical only. No runtime tests executed in this commit.
