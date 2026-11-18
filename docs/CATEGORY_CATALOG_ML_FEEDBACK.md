# Category catalog and analyst feedback (draft PR)

## Implemented

- `0004_categories` Alembic migration: unified `categories` table seeded with
  currently implemented detector result categories, plus ML-only `NORMAL`.
  Existing builtin detector codes are retained for compatibility; this is
  **not** a promise to preserve them in a development-only project.
- Administrator-only category creation, editing and archiving via
  `/api/categories`. Read requires authenticated account.
- Searchable Russian multi-select with groups, inline category creation and
  selected-category chips. Reused by policy editor and ML manual labeling.
- New catalog administration section in the navigation.
- Category detection options: literal keyword/phrase matching, binding a
  reference document, and an ML-only label (effective after training and
  publishing an eligible model). Creating an ML category **does not** train it.
- Policy category validation: unknown, archived and ML-only `NORMAL` category
  cannot be selected in policies. Empty selection retains current semantics:
  all categories.
- `POST /api/ml/incidents/{id}/example`: analysts with originals permission
  can explicitly label an investigated incident's extracted text, mark its
  labeling approved, and save it for a future training run. Duplicate
  incident-derived examples return 409. Incidents do **not** train or publish
  ML automatically. Feedback is audited.
- Manual `POST /api/ml/examples` also validates category IDs.

## Migration and validation for the local agent

1. Compare this branch against the local HEAD. If `master` advanced,
   merge or cherry-pick into a fresh integration branch; resolve conflicts
   before running migrations.
2. Use a disposable PostgreSQL database; run `alembic upgrade head`,
   inspect seeded category rows, exercise downgrade only against a disposable
   copy. Preserve the user's original database.
3. Run Ruff, Python compileall, all tests (including the new
   `tests/test_categories.py` with `MAILFIRE_TEST_DB`), and frontend
   TypeScript build. The changes were authored remotely; **these checks
   have not been executed by ChatGPT**.
4. Browser E2E: create a keyword category, create a policy by selecting it,
   import an EML and confirm the finding; create a reference category,
   confirm reference matching; from an incident save an approved ML example;
   train and publish a model when the corpus is sufficient.
5. Explicit negative tests: unauthenticated category access, nonadmin
   mutation, role without original-content permission, unknown/archived
   categories, duplicate incident example, empty category selection semantics,
   malformed reference IDs, and large/hostile keyword lists.
6. Verify no nested HTML forms, keyboard accessibility, focus management,
   readability on light/dark theme, and Russian localization.
7. Rebuild and validate Compose only after passing tests. Keep PR as draft
   until verified; no push/merge into master without user/agent approval.

## Security / known limits

- Custom keyword rules are **literal case-insensitive phrases**, not raw
  user-provided regex. Arbitrary regexes could cause catastrophic
  backtracking; implement separately with bounded, safe matching if needed.
- ML-labeled `NORMAL` examples are negative examples; predictions for
  `NORMAL` are intentionally omitted from incident findings.
- Current TF-IDF classifier still requires a sizeable diverse approved
  dataset, 60/20/20 split and per-label coverage. UI actions do not bypass
  quality gates; training remains asynchronous via PostgreSQL.
- Analyst feedback currently stores copied sensitive extracted text in
  `training_examples`. Review retention, legal-hold, deletion of source
  message, role-based access, and purpose limitation before production.
- The current `Content.analysis` shared mutation/lease problem and
  existing incident policy reevaluation limitations are NOT addressed here.
- System categories are immutable in the catalog and customer categories
  are archived, not physically deleted, to keep historical labels readable.
- A category linked to a deleted reference remains a dormant configuration
  until rebound; the DB foreign key clears the link.
- Only category codes for detector outputs are seeded; if new detectors are
  introduced later, their categories must be included by a follow-up
  migration or seeding mechanism.
