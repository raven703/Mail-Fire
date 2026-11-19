# Security Overview redesign — PR #5 addendum

## Original problem

The existing dashboard mixed four very tall KPI cards, a separate severity
card column, a larger category section, a recent-incidents table and a wide
technical-health panel. It had inconsistent gaps, huge whitespace, and
inconsistent visual hierarchy.

Two meaningful data-label mismatches were corrected in the redesigned view:

1. `/api/workspace/overview.categories` groups incidents by **Policy.name**.
   It is **NOT** a list of detector categories. The new heading is
   **«Политики со срабатываниями»**.
2. `recent` is ordered by incident risk DESC, date DESC, **NOT by date first**.
   The new heading is **«Приоритетные инциденты»**, with an explicit subtitle.

`active_jobs` and `health` are current-status metrics; the other count
metrics are bounded by the selected time range. The UI clearly discloses this.
`UNKNOWN` health is a lack of confirmed telemetry, not a failure.

## New hierarchy, desktop

1. Small overview title/description + jump to investigations.
2. **Single four-column compact KPI strip**: needs review, all incidents,
   analyzed messages, current active queue jobs. All KPI tiles remain clickable.
3. **Two equally-sized analytic panels**: risk distribution with three
   interactive thin bars and recent risk trend (from existing timeline API).
4. **Attention-first work area**: six risk-prioritized incidents in a condensed
   list + six incident-producing policies with bars. Entries retain drill-down.
5. **One-line compact technical status area**: health statuses and DEAD-job
   count; links to Diagnostics / Jobs and explanatory UNKNOWN footnote.

No external charting library, new API requests, new backend fields or generated
data. The design reuses existing `/api/workspace/overview` fields and
existing color tokens; no fabricated trend numbers.

`frontend/src/SecurityOverview.tsx` renders `page=dashboard` only.
The existing `analytics` page is deliberately left unchanged pending a
separate data-visualization review. Styles are scoped to
`frontend/src/security-overview.css` and imported after
`frontend/src/controls.css`, avoiding global layout conflicts.

## Responsive and accessible behavior

- Four KPI columns collapse to two on tablet and phone.
- Graph/risks, incident/policy columns stack when space is narrow.
- Technical statuses collapse from three columns to two.
- Long subjects and policy names truncate without expanding the grid.
- All drilldowns use real buttons, remain keyboard-operable; chart has an
  accessible summary via `role=img` and an ARIA label of underlying values.
- No false green color for `UNKNOWN`.
- Light/dark themes use existing Mail-Fire color variables.

## Required local acceptance checks

1. Build frontend: `cd frontend && npm ci && npm run build`.
2. Playwright screenshot comparison at 320, 375, 768, 1280 and 1920px,
   dark and light themes. No horizontal page overflow, clipping, oversized
   cards or unused blank section heights.
3. Empty data: all zeros/empty arrays; no NaN widths, layout collapse,
   wrong health/incident claims. Rich data: long subject, long policy name,
   six+ policies, 18 time buckets, mixed severity.
4. Drilldowns: open incidents, all incidents, HIGH/MEDIUM/LOW filters,
   analyzed messages, current jobs, individual incident detail, per-policy
   incident list, Policies, Analytics, System health and Jobs.
5. Check selected date range for KPI + graph + policy counts. Queue counts
   remain current-state by design.
6. Verify the "policy" filter actually matches the backend incident
   `category` query (currently mapped to Policy.name). No behavior change.
7. Cross-check the original `analytics` page still renders and CSV export
   still works.
8. Regression test PR #5 shared controls across all pages; after that,
   locally merge as authorized. Do not push automatically.
