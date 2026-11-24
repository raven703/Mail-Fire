# Autonomous migration backlog

Work only in experiment/django-htmx. Master/live containers/data are forbidden.
Newest user instruction permits isolated email integration/regression/load tests.

- [ ] Split native extraction and OCR contracts, including nested archives.
  Native extraction now propagates use_ocr=False recursively; OCR coordinator
  registered on its own queue. Isolated OCR service deployment and real PDF/image/
  archive verification remain required. OCR currently re-extracts the original
  attachment in the OCR service, preserving the original combined algorithm.
- [ ] Deploy dedicated secret-free Parser/OCR/Converter in internal networks.
  Parser and OCR now running on distinct internal networks. Real sandbox probe
  confirmed network_denied=true, uid=10001, no DB secret/sensitive mounts. Real
  generated PNG recognized by RapidOCR. Converter build/start was attempted;
  registry metadata retrieval delayed it; inspect build/container before retrying.
  Dockerfile.django-parser currently uses mailfire-backend:local dependency base;
  replace with standalone pinned dependencies before final independence acceptance.
- [ ] Connect detection, normalization, AV/secrets, category/reference/template rules.
- [ ] Connect optional ML/LLM workers with explicit unavailable/disabled states.
- [ ] Persist final analysis and enqueue policy/incident evaluation atomically.
  Deterministic detection adapter now wired OCR→detection→policy using unchanged
  detect()/pii() through sandbox. Missing AV/secrets/normalization/custom/reference/
  template checks are explicit engine_errors and force PARTIAL. ML/LLM skipped.
  Real full-cycle acceptance still pending updated Parser image build.
- [ ] Add upload/SMTP/import adapters and delivery-context deduplication tests.
- [ ] Exercise real RabbitMQ/Celery full cycle; crash recovery/idempotency tests.
- [ ] Port remaining APIs/services enumerated in PARITY.md and inventory.json.
- [ ] Finish HTMX pages, nested dialogs, theme/navigation and screenshot parity.
- [ ] Adopt real backup in isolated DB and compare data; no production cutover.
- [ ] Run isolated regression/integration/load acceptance and record evidence.
- [ ] Remove legacy runtime/ORM/API/frontend dependencies only after parity.

Checkpoints are not completion. Never infer full-cycle success from unit tests.

## Current build continuation

Independent Dockerfile.django-parser now starts from the public uv Python base,
installs frozen dependencies/models/tools and copies source; no local legacy image
reference. Build log `/tmp/mice-parser-no-ml-build.log` (no embeddings preparation).
Earlier `/tmp/mice-standalone-parser-build.log` may still have an older build
downloading embeddings; do not mistake its output for current build acceptance.
Converter build `/tmp/mice-converter-build.log` is downloading LibreOffice packages.
Runtime rebuilt successfully, 12 pipeline/policy checks passed (2.433 s).
Neither new detection sandbox operation nor full Celery chain is live verified yet.