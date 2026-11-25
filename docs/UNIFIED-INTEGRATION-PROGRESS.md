# Integration validation ledger

Work is in progress; this tree is not production-approved or deployed.

## Security-gate follow-up

- Broker periodically removes request/preflight directories after launcher death,
  without requiring shutdown or a new request. Regression verifies this before
  requesting launcher restart.
- Isolated helpers have a trusted session guardian watching an owner-only pipe.
  Broker death closes the pipe and the guardian SIGKILLs its entire group;
  a real helper descendant and absence of the surviving group are tested.
- OCR now uses AsyncClient under asyncio.wait_for for an absolute operation
  deadline, including upload, headers and slow streamed body. A local server
  emitting bytes every 50 ms cannot extend a 400 ms deadline.
- Process-control policy additionally blocks scheduling/priority/affinity,
  NUMA process manipulation, BPF/perf, reboot/kexec. Probe resolves syscall
  numbers with libseccomp and verifies EPERM for all available audited calls.
- Disposable parser container, 512 MiB, restart on-failure: Docker events show
  oom -> die -> start, RestartCount=1, followed by successful real /analyze.
  Fault injection is confined to tests/parser_oom_entry.py, never production.
- 161 Django regressions and the restricted image suite passed. Logs:
  gates-django.log, gates-full.log, gates-tests.log, parser-oom-result.log,
  oom-events.log in /home/user/mice-archives/unified-review/.

The container OOM/restart and durable dependency deferral/retry are currently
tested separately. A single end-to-end durable job interrupted by actual OOM
and subsequently completed has not yet been demonstrated; this remains a gate
before merging main. No benchmark, bulk processing or deployment was performed.

The earlier remaining-audit list is historical; use this follow-up for status.

## Validation update, 2026-11-24

- 161 Django tests passed, including analysis dependency deferral without
  consuming attempts, subsequent retry and exactly one persisted attachment.
- Restricted image suite passes with real HTTP parallel analysis, queue-full
  rejection, retry after launcher SIGKILL, malformed/oversized IPC rejection,
  real Regex timeout and shortened Gitleaks deadline, PID exhaustion/recovery,
  address-space allocation failure and supervisor process-group cleanup.
- Launcher startup now waits for preflight and a two-way readiness handshake.
  The acknowledgement prevents the launcher accepting its own readiness frame.
- Helpers receive Landlock and the unified seccomp policy; their trusted owner
  kills the process group and waits on both success and timeout. Go scans were
  exercised, but a short scan is not a comprehensive Go runtime stress test.
- A real image-only PDF yielded SCANNED PDF OCR TEST through the live RapidOCR
  gateway, unchanged model cyrillic_PP-OCRv5_rec_mobile, confidence .95339.
- Disposable 192 MiB cgroup OOM test killed an allocating child with SIGKILL;
  its parent survived, reaped it and successfully forked again. This is NOT
  a full broker/container OOM recovery test.
- Parser containers now use init for orphan reaping. Monitoring includes the
  analysis queue. Concurrency/admission defaults are in .env.example.
- Benchmark and production processing were not run.

Evidence: final-architecture-django.log, final-restricted.log, scanned-pdf.log,
cgroup-oom.log in /home/user/mice-archives/unified-review/.

Remaining audit limitations before merge: complete broker/container OOM restart
scenario; crash-time temporary-directory cleanup without waiting for broker
shutdown; helper descendant lifetime under broker death; comprehensive alternate
process-control syscall probes and wall-clock bounds for slow OCR streaming.
Legacy routing is retained behind the disabled feature flag for staged rollout;
enabled fresh intake is covered by the no-legacy-jobs regression.

The earlier ledger below is historical and is superseded by this update.

Implemented and tested so far:
- Unified HTTP requests use the JSON envelope directly, retaining only the
  original EML's necessary Base64 encoding. Added client contract regression.
- Coordinator snapshots live OCR enabled/provider; fixed gateway propagates
  provider, keeps redirects disabled and treats transient HTTP failures as
  dependency unavailability. Added live configuration regression.
- Main sandbox rejects kill/tkill/tgkill, queued signal interfaces, pidfd,
  ptrace/process_vm, process_madvise/process_mrelease, process-group escape
  and io_uring interfaces. No extra capabilities or weaker Docker profile.
- Regex/Gitleaks requests use an allowlisted IPC helper gateway, so main-child
  timeouts no longer require signalling from its restricted process.
- Queue migration follows local deferrals migration; no production reset.

Evidence:
- 160 Django tests passed; migration-state and diff checks passed.
- Real restricted image passed original signal probe after syscall restriction.
- Real fork broker processed two parallel requests with mocked OCR.
- Real OCR gateway recognized PNG MF350-0304 using unchanged RapidOCR model.
- PDF MF350-0308 extracted native text; this is NOT scanned-PDF OCR validation.
- Baseline legacy run completed all 350 fresh evaluations: TP235 FP8 FN7,
  precision .967078, recall .971074, F1 .969072 on 12 custom categories;
  342 ANALYZED, 8 PARTIAL, 263 messages with policy hits/incidents.

Remaining release gates:
- Complete helper-process confinement, same-UID signal audit including helper
  processes and internal Go threads, not just the main analysis child.
- Prove helper and launcher cancellation/timeout/reaping, including descendants,
  launcher SIGKILL, OOM and PID exhaustion. Current helper bridge is not evidence
  that all those cases pass.
- Real scanned PDF OCR and unavailable-service tests.
- End-to-end HTTP server test, malicious-frame limits and parallel oversize input.
- Fresh unified benchmark via normal durable intake at concurrency 1 and 2,
  with resource sampling and normalized evidence comparison.

Do not merge or enable production based only on the passing unit tests.
Logs: /home/user/mice-archives/unified-review/.