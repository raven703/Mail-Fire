# Mail-Fire audit corrective branch

This change proposes conservative direction classification, nested ZIP member
binary scanning, explicit incomplete antivirus coverage, partial database-write
lease fencing, and retention enumeration without the fixed 5000-row cutoff.

## Required validation before deployment

- Configure INTERNAL_DOMAINS with actual authoritative corporate domains;
  without configuration direction deliberately stays UNKNOWN.
- End-to-end: mixed recipients, BCC delivery, zip nested YARA/Gitleaks/ClamAV,
  parser response/output limits, malicious and large archives.
- Verify ClamAV-off messages display PARTIAL, not CLEAN; decide whether AV is
  mandatory for each deployment.
- Validate job lease renewal, cancellation, retry, incident idempotence and
  overlapping workers against PostgreSQL.
- Test retention with >5000 held records plus expired unheld records.
- Run lint, full pytest suite, Compose rebuild, E2E, rollback and load tests.

## Limitations

Do not merge without validating these patches against the full test suite.
The derived analysis Content is still mutable/shared; immutable versioned
analysis is a separate architectural correction. In particular, a stale worker
could still affect downstream operations outside the fenced transactions.
The extraction response contains base64 copies of nested archive member data:
the agent must check memory/broker response limits and switch to a bounded
per-member sandbox flow before production rollout.
OCR/ML worker separation, full policy reevaluation, full context-based scoring,
and broad legacy-format parsing are not included in this branch.
