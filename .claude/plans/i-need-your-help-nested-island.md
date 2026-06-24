# Plan: Extract the dashboard backlog into a standardized root `TODO.md`

## Context

The `# Dashboard Add / Update Notes` section (lines 427–498 of
[dev/notes/human-notes-misc.md](dev/notes/human-notes-misc.md)) is a ~70-line **living working
backlog** — a curated, ID'd list of dashboard/repo changes with its own embedded maintenance
protocol (a "For agents maintaining this list" block + a "Loose notes" inbox bucket the human drops
rough notes into for an agent to triage). It currently sits at the bottom of a 500-line grab-bag of
**static reference** material (CLI config tables, color palettes, MCP setup notes).

That's a mismatch: the rest of the file is read-occasionally reference; this section wants to be
**edited constantly**. The user already runs the exact workflow they describe (drop rough notes →
agent reworks into sections) — it's encoded in that section today. The goal is to **promote that
workflow into its own discoverable, standardized home** so it's easy to maintain and reference,
without changing how it works.

Outcome: a root `TODO.md` that is the project's single working backlog, registered where agents
will find it, with a stale path corrected along the way. No backlog *content* is rewritten — this is
a move + light formalization, not a re-grooming.

## Decisions baked in (swappable on approval)

- **Name/location:** root `TODO.md` (matches the user's instinct + `DEVLOG.md` precedent at root).
  Alternative if preferred: `BACKLOG.md`. *Single swap point — used in ~3 places below.*
- **Scope:** keep it the **general repo backlog** — all sections A–E move as-is. The content is
  already mixed (dashboard items in A–C; repo-wide chores in D–E), so one backlog avoids
  per-item "dashboard vs repo?" sorting. No items are relocated or split out.

## Changes

### 1. Create root `TODO.md` with a status-spine structure

Move all content from the `# Dashboard Add / Update Notes` block (lines 427–498) into a new,
**restructured** doc. **No item's text is rewritten or dropped** — items are re-filed and re-tagged,
not re-groomed. The structure changes from the muddled A–E (mixed priority/effort/type axes) to a
single **status spine + inline tags**.

**Why:** a backlog has competing sort axes (status, priority, effort, area, type). Only one can be
the heading structure; the rest must be tags. The user's maintenance action is "dump notes → pull
what's next" (a *status* action), so **status is the spine; area + effort become tags.** This makes
the human touch exactly two zones; the agent owns the rest.

**A worked, populated mock of this structure (using REAL items from the current notes) lives at
[.claude/plans/todo-structure-example.md](.claude/plans/todo-structure-example.md) — read that for the
concrete shape.**

**Two-tier "what thing is this?" model.** Each item belongs to a **surface** (level-1, durable: which
part of the system) and optionally a **sub-area** (level-2, granular: which piece of that surface).
Both are carried as **tags on every item** so an entry is self-describing even in Inbox/Next up where
it sits outside any heading. Effort is a tag + the within-section sort order — **never the spine**
(it's the weakest locator; effort-as-section is what let today's B/C go stale).

**Roles & parallelism (multi-agent).** A **Curator agent** is the *single writer* below the Inbox —
it triages, tags, files, orders `Up next`, dispatches, and reconciles. **Worker agents** receive item
text from the curator, do the work, and report back; they do **not** edit the file (so no write races).
The human only writes in `Inbox` and signals priority. Parallel workers are kept apart by **surface**
(one on `ui`, one on `backend`), and the **`In progress` board** stamps each active item with `@owner`
so concurrent work is visible at a glance. `Up next` is therefore **agent-managed**: the curator
promotes items into it from priority signals (an `!`-flagged Inbox note, or a direct instruction).

**Top-level structure (status spine):**

```
# TODO — working backlog
## How to maintain          ← curator's contract (rules)
## 📥 Inbox                 ← human dumps raw notes (the ONLY human-write zone); ! = "queue soon"
## ▶ Up next                ← agent-managed priority queue; pointer lines only
## 🛠 In progress           ← parallel-work board; pointer lines stamped @owner
## 📋 Backlog               ← full item text, grouped by SURFACE:
   ### Dashboard UI-concept     (sort by effort; promote sub-areas to ### only when this grows large)
   ### Backend & runtime
   ### Bridge
   ### Infra, config & docs
   ### Open questions / research
## ✅ Done                  ← short tail; prune once logged in DEVLOG
```

**Single source of truth:** full text lives **once** in `Backlog`; `Up next` / `In progress` / `Done`
are lightweight pointer lines (ID + title + tags, plus `@owner` on the board) — nothing is duplicated.

**Formatting convention:** every heading is a clean label only; directly under it sits a consistent
guidance **blockquote** (`> **What** / **Edited by** / **How items move**`) visually separated from the
items. See [.claude/plans/todo-structure-example.md](.claude/plans/todo-structure-example.md).

**Per-item format — stable IDs + surface/sub-area + effort:**

```
**[T08] Interactive Comms**  `backend`  `big` — <description unchanged>. (refs: T11)
**[T01] Plan Footer Grouping**  `ui/plan-card`  `med` — <description unchanged>.
```
- **Stable monotonic IDs (`T01`, `T02`…)** assigned once on triage, **never reused or renumbered** —
  they survive moving between Inbox/Next/Backlog and re-tagging. This is what makes "point an agent at
  T07 and T12" unambiguous. (Replaces today's section-bound `A1`/`C12` IDs, which rot on any move.)
- **Surface tag** (mandatory): `ui`, `backend`, `bridge`, `infra`, `meta`. **Sub-area** (optional,
  free-form within a surface): `ui/plan-card`, `ui/nav`, `ui/feed`, `ui/team-graph`, `ui/badges`…
- **Effort tag**: `quick`/`med`/`big`; plus `research` (undecided) / `blocked` (waiting) as needed.
- Tags are NOT headings, so cross-surface items (`backend` + `ui`) need no arbitrary home; note the
  secondary surface inline. Cross-references use the stable ID (`refs: T11`).

**"Next up" is a pointer queue (recommended fork — confirm with user):** each item lives **once** in
the Backlog under its area; "Next up" is just an ordered list of `ID — title` lines. Reprioritizing =
reorder a few one-liners, never relocate paragraphs. (Alternative the user may prefer: physical move
of full item text between Next up and Backlog — simpler model, more cut/paste.)

**Migration mapping (content preserved, re-filed):**
- Current `A. Next up` items → `▶ Next up` (as pointers) + their full text filed in Backlog by area.
- `B. Quick wins` → Backlog under area, tagged `quick`.
- `C. Big picture` → Backlog, split across `Dashboard UI` / `Runtime & backend`, tagged `big`.
- `D. Needs research / decisions` → Backlog `### Open questions / research`.
- `E. Housekeeping & docs` → Backlog `### Infra, config & docs`.
- `Loose notes` (incl. the "session" → "project" note) → `📥 Inbox`.
- `Scratch` bullets (badge consolidation; hover cards) → triaged into Backlog with IDs, or kept under Inbox if still raw.
- Assign each migrated item a fresh `T##` ID and area/effort tags during the move.

**"How to maintain" header** = the existing "For agents maintaining this list" guidance, rewritten
for the new model: Verify-first (check the live mockup) · Inbox→triage flow (empty Inbox: assign
`T##`, tag area+effort, file by area, add to Next up if hot) · stable-ID rule (never reuse/renumber)
· tag vocabulary · cross-ref by ID · Done/cleanup convention.

**Fix the stale reference:** the intro points at `agent-dashboard/design/ui-concept-v8pN.html` —
update to the current authority `design/ui-concept-v9p14.html` (per [DEVLOG.md](DEVLOG.md) Status +
[CLAUDE.md](CLAUDE.md) design map) and reword "highest version number is live" to stay correct as
versions advance.

### 2. Leave a pointer in `dev/notes/human-notes-misc.md`

Remove the moved section (lines 427–498) and replace it with a one-line breadcrumb so anyone landing
in the old spot is redirected, e.g.:
`> The dashboard / repo backlog moved to root `TODO.md`. Drop rough notes in its "Loose notes" bucket.`
Everything else in the file (Agent Agreement, Multi-Agent Coordination, Settings dirs, MCP Server
Plan, the CLI Parameter Lifecycle tables, UI Color Theme Resources, `# General notes`) stays exactly
as-is.

### 3. Register the new doc so agents discover it

- **[CLAUDE.md](CLAUDE.md):** add a `TODO.md` row to the **Key files** table (the cross-cutting docs
  every session should know about) and to the **Root files** line in the folder map. One-line
  description: the project's working backlog + how the drop-notes/triage workflow runs.
- **Optional, recommended:** add a short bullet under **Behavioral rules** mirroring the DEVLOG rule
  — "when the user drops rough notes in `TODO.md` → Loose notes, fold each into the right
  section with an ID + header and clear the bucket" — so the triage step is a standing instruction,
  not just doc-internal guidance.

### 4. Log it

Append a `DEVLOG.md` entry (timestamped heading + 1–4 lines + `Files:`) recording the extraction,
the pointer, and the CLAUDE.md registration — per the repo's append-only DEVLOG rule.

## Files

- **New:** `TODO.md` (repo root)
- **Edit:** [dev/notes/human-notes-misc.md](dev/notes/human-notes-misc.md) — remove section, add pointer
- **Edit:** [CLAUDE.md](CLAUDE.md) — Key files table + folder map + (optional) Behavioral rule
- **Edit:** [DEVLOG.md](DEVLOG.md) — append log entry

## Verification

- Open `TODO.md` and diff its A–E items against the original lines 427–498 — confirm **every item,
  ID, and description carried over verbatim** (nothing summarized or dropped; the CLAUDE.md
  "preserve everything you weren't asked to change" rule applies). Confirm `Loose notes` and
  `Scratch` survived.
- Confirm the only intentional content change is the corrected `ui-concept-v9p14.html` path.
- Confirm [human-notes-misc.md](dev/notes/human-notes-misc.md) lost *only* that section and gained
  the pointer line; everything else byte-identical.
- Confirm the CLAUDE.md table/folder-map links resolve and the DEVLOG entry is present.
- (No code/UI affected — this is docs only; no build or browser check needed.)
