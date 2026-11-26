# Fast category benchmark
Read-only production text detection replay, all 12 annotated RU3 categories by default. It does not run OCR, binary scanning, queues or policy evaluation. It retains native text detection for context rules. No production code changes.

First run B-400 using frozen run.json with --require-parity. Exact per-message category-set parity is mandatory before calibration. B-350 historical observations can be supplied with a compatible configuration snapshot; historical text/attachment order may fail strict reconstruction, which must be investigated, never guessed. Use --database to read deployed configuration or --rulepack to overlay candidate rules without applying them. Optional --category limits scoring, not execution. --normalizer keep uses frozen settings.

Use the command from .github/workflows/category-replay.yml. Output must be a fresh directory. Compare metrics.json and messages.json. Treat B-350 and B-400 as calibration data once tuned; do not call their improved scores independent validation. No actual OCR or production performance is measured.
