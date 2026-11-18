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

## Local review and acceptance

Reviewed against master 53790ca; PR cbc8e342 shares that baseline.
Corrected binary-response amplification: nested members are statically scanned
inside the isolated extraction subprocess and only findings are returned. ClamAV
scans the original archive via INSTREAM; its own unpacking limits still apply.
Extraction now has the scan virtual-address allowance (8 GiB for Gitleaks WASM),
while parser RSS stays cgroup-limited to 3 GiB and broker concurrency is one.
Subprocess output is spooled under RLIMIT_FSIZE, bounded before JSON decoding;
HTTP responses are streamed with an 80 MiB cap and broker checks serialized size.
BCC direction uses message addresses, never the collector's envelope recipient;
evaluate recomputes direction for deliveries received after initial analysis.
Retention rechecks legal hold under row lock and respects active event jobs.

Checks before merge: PostgreSQL disposable database mailfire_audit_test,
44 passed / 2 skipped (optional Paddle flag and local Gitleaks availability),
plus four targeted direction/archive/response-limit regressions passed locally.
One upstream TestClient deprecation warning. Production backup is
/tmp/mailfire-before-audit.dump. Production database is not used for pytest.
Remaining: versioned immutable analysis; long transactions holding job rows can
block heartbeat, though locking fences concurrent claim until commit. Full load,
crash recovery and AV unpacking-limit acceptance are not claimed by these tests.
