<!-- EXAMPLE / MOCK — not the real TODO.md. A small, illustrative slice populated with REAL
     items from the current "Dashboard Add / Update Notes" notes, refiled into the proposed
     structure. Shows: agent-managed queues, multi-agent parallel work, and the formatting convention
     (heading = label only; a guidance blockquote of its own directly under each heading). -->

# TODO — working backlog

> **What** — One working backlog for the repo. Full item text lives **once** in `Backlog`; the
> `Up next` / `In progress` / `Done` sections are lightweight pointer lines (ID + title + tags).
> **Roles** — The **Curator agent** is the *only* writer below the Inbox: it triages, tags, files,
> orders the queue, dispatches, and reconciles. **Worker agents** receive item text from the curator,
> do the work, and report back — they do **not** edit this file (no edit races). **You** only write
> in `📥 Inbox` and signal priority.

## How to maintain
> **What** — The curator's contract.
> **Triage** — Empty the Inbox: verify the item isn't already built (open the live mockup), assign a
> fresh `[T##]` ID (monotonic, **never reused or renumbered**), add tags, file into the right
> `Backlog` surface.
> **Tags** — `surface/sub-area` + `effort`. Surface ∈ {`ui`,`backend`,`bridge`,`infra`,`meta`};
> sub-area is free-form (`ui/plan-card`, `ui/nav`, …). Effort ∈ {`quick`,`med`,`big`};
> add `research` (undecided) / `blocked` (waiting). Active items also carry `@owner`.
> **Flow** — `Up next` is promoted from `Backlog` by the curator using your priority signals.
> Dispatch = move the ID to `In progress` + stamp `@owner`. On completion = move to `Done`.
> **Refs** — Cross-reference by stable ID (`refs: T11`). Live mockup authority: `design/ui-concept-v9p14.html`.

---

## 📥 Inbox
> **What** — Raw human dumps. The only place you write.
> **Edited by** — You (add notes); curator (empties it during triage).
> **Signal priority** — prefix a note with `!` to ask the curator to queue it soon.

- ! Rename all references to "session" → "project" everywhere — that's really the reusable unit of an
  agent config. *(curator: tag `meta`, file under Infra & docs, assign an ID)*

---

## ▶ Up next
> **What** — Ready, unclaimed items in priority order. Pointers only.
> **Edited by** — Curator. *(You don't hand-edit — flag priority in Inbox or tell the curator.)*
> **How items move** — Curator promotes from `Backlog`; a worker is dispatched from the top.

1. [T02] Nav Card Selection      `ui/nav`         `med`
2. [T03] Output Export           `ui/feed`        `quick`
3. [T08] Interactive Comms       `backend`        `big`

---

## 🛠 In progress
> **What** — Items currently claimed by an agent — the parallel-work board.
> **Edited by** — Curator (on dispatch + completion).
> **Parallelism** — One row per active worker; agents split by surface so they don't collide.

- [T01] Plan Footer Grouping   `ui/plan-card`  `med`   → **@opus-ui**   (since 14:20)
- [T05] Per-Agent MCP & Plugins `backend`      `big`   → **@sonnet-be** (since 13:05)

---

## 📋 Backlog
> **What** — Every item's full text, grouped by surface, sorted by effort within each.
> **Edited by** — Curator only.
> **Sub-areas** — Promote a sub-area (e.g. `ui/feed`) to its own `###` heading only when a surface
> grows large enough to need it.

### Dashboard UI-concept
- **[T01] Plan Footer Grouping**  `ui/plan-card`  `med` — Plan-card button grouping isn't working.
  Move Share + Review up into the upper strip and extend that strip under the nav pane; keep Copy/
  Edit/Comment left-aligned, Share/Review right-aligned. *(in progress: @opus-ui)*
- **[T02] Nav Card Selection**  `ui/nav`  `med` — Make nav cards selectable like other cards (teal
  fill that persists until deselect/close); selecting also highlights its associated tag text.
  *(up next #1)*
- **[T03] Output Export**  `ui/feed`  `quick` — Extend the per-card Copy into selecting/cutting/
  exporting larger spans of output. *(up next #2)*
- **[T04] Jump to Feed Ends**  `ui/feed`  `quick` — Quick jump-to-start / jump-to-end controls on
  each feed.
- **[T06] Link Edges**  `ui/team-graph`  `med` — Add link-related UI to the Team Graph (directed
  edges) so you can see how agents are linked. Replaces the removed hand-drawn link lines.
- **[T07] Badge Consolidation**  `ui/badges`  `med` — Too many badge fill/font styles; refine to a
  small consistent set. *(was: Scratch)*

### Backend & runtime
- **[T05] Per-Agent MCP & Plugins**  `backend`  `med→big` — Set MCP servers + plugins per agent in
  the UI, not just globally. *(in progress: @sonnet-be; also touches `ui`)*
- **[T08] Interactive Comms**  `backend`  `big` — Dynamic agent↔me comms via a shared "dynamic doc"
  the agent references periodically during a run. *(up next #3)*

### Bridge
*(empty for now — quiet surface; stub kept so non-UI work has an obvious home)*

### Infra, config & docs
- **[T09] npm Binary**  `infra`  `quick` — Update npm to the native binary.
- **[T10] CLAUDE.md Trim**  `meta`  `med` — Optimize CLAUDE.md files: index other files instead of a
  full context dump.

### Open questions / research
- **[T11] Tasks**  `research` — Understand Claude Code "tasks" and decide whether they belong in the
  dashboard workflow. *(decision, not a build item — lives here until resolved)*

---

## ✅ Done
> **What** — Completed items (most recent first).
> **Edited by** — Curator (on a worker's completion report).
> **Cleanup** — Keep a short tail here; prune older entries once logged in DEVLOG.md.

*(none yet)*
