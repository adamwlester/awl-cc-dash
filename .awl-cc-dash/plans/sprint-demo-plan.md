# Plan: seed the demo store

Goal: populate this repo's committed `.awl-cc-dash/` project store with realistic demo content — roles, docs with provenance, and a reviewed plan — without touching the sidecar-owned `state/` files.

## Phase 1 — Roles

- [x] Create `.awl-cc-dash/agents/` with the five team role definitions (builder, reviewer, researcher, scribe, ui-checker)
- [x] Vary front-matter shapes across the files (inline tools, skills block, no tools key, commented key) so the role parser gets exercised

## Phase 2 — Library docs

- [x] Write `docs/team-handbook.md` (team overview) and `docs/dashboard-demo-notes.md` (design note)
- [x] Hand-write each doc's `.meta.json` sidecar — provenance for the Authors lens, one seeded review comment on the handbook

## Phase 3 — Plans

- [x] Create `plans/` with this plan and its sidecar carrying an approved review verdict

## Verification

- [ ] Every `.md` parses as front-matter + body; every sidecar loads as valid JSON
- [ ] Library shows both docs under Authors; plan shows the approve verdict
