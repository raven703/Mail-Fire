# Isolated Horizon category benchmark

Read `/home/user/Mice/test-data/horizon-benchmark/REPORT.md` for results and
`/home/user/Mice/test-data/horizon-benchmark/PROTOCOL.md` for decision semantics.
Requires PR #37 infrastructure on this branch. Never imports production MICE.

Environment: `/home/user/.venvs/hf-model-benchmark`; pinned dependencies in
`requirements.lock`, installed by PR #37's standalone installer. Model weights:
`/home/user/hf-model-benchmark-data/models/horizon` at the PR #37 audited revision.
No sklearn dependency: AP and confusion matrices have offline math tests.

External inputs, window-score caches and logs:
`/home/user/hf-model-benchmark-data/horizon-category`.
Use `fetch_inputs.py` to retrieve exact historical Git commits in
`source-commits.json`; requires these Git objects to be fetched. Every EML is
verified against frozen observation SHA256. `*-provenance.json` hashes extracted
texts and labels. No need to access a database or start containers/OCR engines.

Run `/home/user/Mice/test-data/horizon-benchmark/reproduce.sh development`,
then commit frozen selection before running its `holdout` phase. **Published
outputs refuse overwrite**: reproduce in a separate worktree/output copy and
adjust absolute `ROOT`/`DATA` constants to the new isolated paths. Remove generated
result files only in that new copy, not the published run. To reproduce the
published fixed holdout without retuning, retain committed hypotheses/config
and freeze; prepare inputs from the exact source commits and run holdout.

`infer.py` caches per-window probabilities, hypothesis order, model/text hashes,
timings and memory measurements. `report.py` recalculates fixed-config metrics
without GPU. For cached-only recalculation use a separate output copy and point
its `DATA` constant at the preserved caches. `optimize.py` refuses tuning after
freeze; run development selection only in a new, explicitly unfrozen experiment.

Offline validation:

```sh
/home/user/.venvs/hf-model-benchmark/bin/python /home/user/Mice/test-data/horizon-benchmark/test_benchmark.py
/home/user/.venvs/hf-model-benchmark/bin/python -m compileall -q /home/user/Mice/test-data/horizon-benchmark
bash -n /home/user/Mice/test-data/horizon-benchmark/reproduce.sh
```

`summary.csv` includes fixed decisions on all three corpora and both dtypes;
`predictions.jsonl` contains 2,500 per-message results; `errors.csv` includes all
misclassified category/text pairs. `development-best.json` identifies best
singles/ensembles/exclusions; the complete threshold grid is compressed.
`comparison.json` records verified historical cohort/label/text comparability.
No integration is implemented and no PR is merged by these scripts.