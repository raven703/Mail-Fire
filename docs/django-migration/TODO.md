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
- [ ] Add upload/SMTP/import adapters and delivery-context deduplication tests.
- [ ] Exercise real RabbitMQ/Celery full cycle; crash recovery/idempotency tests.
- [ ] Port remaining APIs/services enumerated in PARITY.md and inventory.json.
- [ ] Finish HTMX pages, nested dialogs, theme/navigation and screenshot parity.
- [ ] Adopt real backup in isolated DB and compare data; no production cutover.
- [ ] Run isolated regression/integration/load acceptance and record evidence.
- [ ] Remove legacy runtime/ORM/API/frontend dependencies only after parity.

Checkpoints are not completion. Never infer full-cycle success from unit tests.