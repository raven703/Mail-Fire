# Unified categories, multi-rule detection, and analyst ML feedback

> Draft implementation branch. Changes were authored through GitHub without
> running a local Docker/PostgreSQL/TypeScript build. The integration agent
> must validate and fix problems BEFORE merging into master.

## Data model and migration

- `0004_categories` seeds the category catalog and adds provenance for
  training examples originating from an incident.
- `0005_category_rules` introduces `category_rules`, one-to-many
  relationships from custom categories to their independent detection rules,
  and `categories.match_mode` (ANY / ALL). An existing draft single-mode
  custom category is converted to one appropriate detection rule.
- Built-in detector IDs remain internally as an implementation convenience;
  users select translated Russian names and can freely create new categories.
  The user stated that legacy category IDs do not need long-term compatibility.
- User categories use a generated ID and have a group, description, archive
  status, and ANY/ALL mode. Built-in system categories are immutable.
- Rule fields: type, display title, enabled flag, risk (0–100), priority
  (0–10000), exclusion phrases and type-specific configuration.
- Rule types:
  * `keywords`: up to 30 literal case-insensitive phrases;
  * `regex`: deliberately restricted syntax with bounded repeats, without
    groups, alternation, '*'/'+' wildcards, or unbounded patterns;
  * `reference`: up to 20 attached reference IDs with similarity threshold;
  * `ml`: category probability threshold, active only after an eligible
    trained model is published.
- Rule evaluation: only enabled rules count. ANY fires with any matching
  enabled rule; ALL requires every enabled rule to match. With unavailable
  ML engine, an ALL rule requiring ML does not match. An exclusion phrase
  suppresses only its own rule, not the entire category.
- Policy scope (sender, recipient, direction) remains separate from
  detection rules; category rules examine extracted text and reference/ML
  evidence. A category matching an email DOES NOT block delivery.

## Features

- Category catalog administration at `?page=categories`: create, edit,
  archive, search. Add/remove multiple rule cards, select linked references,
  configure thresholds and ANY/ALL logic.
- Searchable grouped category picker with labels and chips, shared by policy
  editor and ML labeling. Inline creation is available to administrators.
- `POST /api/ml/incidents/{id}/example` explicitly copies the extracted
  text to a labeled training example after an analyst acts; duplicates
  per incident are rejected. Approving an incident or saving an example
  does NOT automatically train or publish a model.
- Existing ML model quality gates, holdout partitions and manual
  publication remain in force.

## Acceptance tests required

1. Compare current local master with the PR base before integration.
   On a disposable database: `alembic upgrade head`, inspect tables,
   test reverting only on the disposable copy.
2. Run `ruff check .`, `python -m compileall app migrations`,
   all unit tests, `MAILFIRE_TEST_DB` PostgreSQL integration tests,
   `npm run build` for the frontend.
3. Test create/edit/archive, multi-rule ANY/ALL, disabled rules, keyword
   exclusions, priority, literal phrases with Cyrillic, regex invalid
   patterns/backtracking attempts, malformed data, and max limits.
4. Create one category with two keyword patterns, two linked references,
   regex and ML rule, then verify results from an imported EML and
   multi-attachment email. Check reference matching from both
   fingerprint and semantic index.
5. Check RBAC/CSRF on writes, unauthorized text access, ML feedback,
   duplicate training examples and published model inference. Check
   mobile layout, keyboard operation, accessibility and dark theme.
6. Test behavior if a model or reference is unavailable and evaluate
   false positives for ANY/ALL.
7. Run browser E2E and Docker Compose rebuild with preserved PostgreSQL
   before local merge. Do not push to GitHub unless explicitly approved.
8. Provide a clear per-file report and test log; fix newly detected
   implementation issues rather than claiming unexecuted tests pass.

## Important limitations

- This PR does NOT repair existing mutability of shared Content.analysis,
  worker/heartbeat long transaction issues, or policy reevaluation history.
- Custom regex is intentionally NOT the complete PCRE syntax; patterns are
  constrained because submitted text is untrusted.
- Full-text bytes are stored for feedback training: access control,
  retention and legal-hold behavior must be reviewed before production.
- Existing rules are replaced atomically on category edits, so they receive
  new rule IDs; old incident evidence keeps the old textual ID. Rule
  versioning is a later enhancement.
- Semantic reference search retrieves the top 10 candidates, so matching
  every selected reference cannot be guaranteed at large catalog scale.
- Training with a new category requires sufficient approved positive and
  negative samples and subsequent manual model publication.
- The reference document source remains linked by ID, and removing a
  reference may leave a nonmatching rule that needs reconfiguration.
- This is a feature branch, not a production-ready certified DLP release.
