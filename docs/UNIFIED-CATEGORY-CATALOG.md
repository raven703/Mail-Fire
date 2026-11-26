# Unified category catalog

Existing category IDs, policy references, historical results, RU3 categories
and rule IDs remain unchanged. There is no schema migration and no automatic
semantic merge. Historical INN/PHONE IDs are retained for stored selections;
new selections show canonical IDs. The legacy rules mode is still accepted
and saved as custom when edited. Training-only labels remain in ML / Разметка.

Duplicate hints use normalized names and common identifier terms, not a
semantic classifier. A similar name requires explicit confirmation; existing
different categories are not automatically collapsed.

## Supplementary text rules

Eleven built-in text categories support optional keywords and safe regex.
Native algorithms and category metadata remain fixed. Only explicitly marked
builtin_context rules annotate overlapping occurrences in the same MIME
document. These annotations cannot create findings, increase risk, change
native verification, or increase the number of policy matches. Unmarked
historical rules on built-in categories remain inactive. File-only, reference
and semantic detectors do not receive supplementary text rules in this PR.
ML and OCR algorithms are not changed.

The rulepack extension builtin_context: true allows export and import of
context rules without overwriting native category metadata. Updating a set
requires explicit update and pack ownership. Older releases do not accept
the new extension. A potential duplicate on import requires confirm_distinct.

## Integration

Merge PR #19 before PR #20. PR #20 incorporates the identical grouped
evidence helper from #19 and adds the context details include inside each
individual match in the grouped template. If the shared _evidence.html
template conflicts, retain the #20 grouped template including the new
_builtin_context_matches.html partial. Preserve #19 incident numbers and
search changes in records/workspace.py.

Run Django CI, restricted parser suite and targeted tests for native
validation, same-document matches, category and label selection, permissions,
and rulepack import/export. Verify the UI manually. No mass reanalysis,
database purge or benchmark is required. Back up the database before
deployment and preserve the existing 350 emails and 263 incidents.
