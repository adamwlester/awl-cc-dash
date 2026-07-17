# Dashboard demo notes

Design-note-style scratch for the demo store seed — what the seeded content is meant to exercise.

- **Authors lens**: both docs here carry provenance sidecars (`created_by` scribe / builder), so the Library's Authors grouping has two real authors to render instead of an empty state.
- **Review surfaces**: the handbook sidecar holds an unresolved comment plus in-review state; the plan sidecar carries a full approved verdict (`verdict` / `verdict_by` / `verdict_at`) — one of each review shape the UI knows.
- **Role combobox**: the five `agents/*.md` files give the Create panel's Project group real entries with deliberately varied front matter — inline tools lists, a `skills:` block, an absent `tools:` key, a commented-out `#model:` line — so the parser meets every shape it must survive.
- **Plans collection**: `plans/` now exists with one reviewed plan, so the Library's plans view and the plan-review flow have something to show on first open.

Numbers 1–3 are retired in this project's roster; nothing seeded here touches `state/` — that stays sidecar-owned.
