# Native Django backlog

Current implementation status is recorded in [PARITY.md](PARITY.md) and
[UI-PARITY.md](UI-PARITY.md). The reference remains the read-only master branch.

## Implemented

- [x] Native Django/HTMX workspace, authentication, scoped originals, account administration.
- [x] Single and multi-file EML/MSG, ZIP, SMTP and read-only directory acceptance.
- [x] Isolated parse, extraction, OCR and deterministic analysis, with persisted evidence.
- [x] Investigations, passive document viewer, mail and policy drill-downs, analytics with CSV.
- [x] Policies, category/rule configuration, rulepacks, saved-evidence reevaluation.
- [x] Reference library, indexing jobs, document-type templates and semantic search.
- [x] Dataset imports with source/label mapping, review/delete and model lifecycle.
- [x] SIEM configuration and delivery, legal hold, retention/GC and bounded log expiry.
- [x] Per-service resource collection, queue/flow/PostgreSQL panels and audit.
- [x] Standalone target build definitions and checksummed offline image/model bundles.
- [x] Separate historical-schema adoption command.
- [x] Durable directory failure history; nested category creation in training dialogs.

## Open implementation items

- [ ] Finish exact UI and interaction parity for the rows in UI-PARITY.md.
- [ ] Automatic destructive retention parity. The experimental schedule intentionally
  previews, while confirmed administrator runs perform deletions. Retention behavior
  for adoption/production must be decided before changing the scheduling policy.
- [ ] Automated signed upgrade and rollback are outside the current image export/load
  workflow. Master has no in-tree updater. Verify the release process separately.

## Acceptance deferred to the next stage

- [ ] Build each required target image and verify dependency closure and offline load.
- [ ] Apply migrations to dedicated experimental PostgreSQL, including the resource
  index and system-category seed. Verify historical adoption separately.
- [ ] Exercise PostgreSQL, RabbitMQ/Celery, Parser/OCR/Converter and target service
  resource probes. Verify lease/retry/fencing and legal-hold preservation.
- [ ] Run browser workflow and visual comparisons in both themes and responsive widths.
- [ ] Run regression, holdout, load and recovery acceptance as requested for that stage.
- [ ] Review previously reported audit findings separately.
