# Plan — The Dashboard System Map (data + UI + audit)

## Context

You're worried the data model is "overly distributed and hard to maintain," but you don't
have a mental model of the structure, and you suspect the storage/sharing scoping is "likely
not ideal" without an easy way to audit it. Three parallel探 passes (backend persistence
census, UI-surface map, scoping-decision rationale) established the ground truth. Two findings
reframe the worry:

1. **Persistence is concentrated, not sprawling.** Only **5 files** on disk hold state — 3 in
   the dashboard store (`sidecar/runtime/{sessions,setups,templates}.json`) and 2 in the
   project store (`<project>/.awl/{scratchpad.md,plan-reviews.json}`). Everything else is
   Claude Code's own config, read/edited *in place* (`~/.claude`, `<project>/.claude`).
2. **The real risk is an *invisible* boundary, not the number of homes.** Most of what the UI
   shows — inbox cards, links, prompt queues, cap warnings, unread-watermarks — is **in-memory
   only** and silently evaporates on a sidecar restart. Nothing in the UI signals which data is
   durable vs. a live wire. That is the thing that's actually hard to reason about.

The audit also confirmed your instinct with three concrete soft spots (plan-reviews keyed by
*filename* → rename orphans the metadata; raw `cwd` used as a key with no canonicalization →
`/project` vs `/mnt/c/project` could collide; templates with an undecided dashboard-vs-project
split). None are catastrophic; all are auditable.

**Determination on depth:** the three-homes model (Dashboard / Project / surfaced-Claude-config)
is sound — no redesign warranted. The ideal path is **flag + recommend**, plus a *light,
targeted* revision in exactly two places (make the persistence tier explicit; replace two
fragile keys). This plan reflects that.

**Deliverable:** one durable working note at **`dev/notes/data-model-map.md`** — high-level,
anchored to real repo-relative paths *and* to the specific UI panels you can point at, ending in
an honest audit. This becomes the digestible reference you keep returning to and the audit surface.

## The document: `dev/notes/data-model-map.md`

Eight short, scannable sections. Preview of the shape (final doc fills these in fully):

### 1. The one-screen model
A single boxed view of the **4 state categories**, each with its path + a one-line what/why:

```
🏠 DASHBOARD STORE   sidecar/runtime/*.json      the app's own memory (reusable, project-agnostic)
📁 PROJECT STORE     <project>/.awl/*            data that travels with the repo, WSL-reachable
🔌 CLAUDE CONFIG     ~/.claude, <project>/.claude surfaced & edited in place — NOT owned
⚡ LIVE (in-memory)  — (nothing on disk)          rebuilt each run; gone on sidecar restart
```

### 2. The three-pane UI → which stores each pane touches
Anchored to the real layout: **LEFT** = Agent panel (Details/Create/Console); **MIDDLE** =
Team Graph (top) + Work panel (Library/Links/Scratch, bottom); **RIGHT** = Team Feed
(Messages/Scratch/Log/Inbox) + Prompt (Compose/History). Each pane annotated with the stores it
reads/writes.

### 3. Master table — every data type, one row
`data type | scope (🏠/📁/🔌/⚡) | real path or "in-memory" | UI location (pane + data-comp) |
survives restart?` — the single lookup that ties **path ↔ UI ↔ durability**. Rows include:
Setups, Templates, Sessions, Identity, Scratchpad, Plan-reviews/Library, Settings, Inbox (5
types), Links, Console, Checklist/marquee, Subagents, Messages/events.

### 4. Follow one thing end-to-end
Two worked traces so it's concrete: (a) a **scratchpad post** — Prompt (Target=Scratch) → POST
`/scratch` → `<project>/.awl/scratchpad.md` + in-memory log → delta-delivered to other agents by
watermark; (b) a **plan review** — Library Plans tab → verdict → `<project>/.awl/plan-reviews.json`
(keyed by filename). Each trace names the UI control, the path, who reads it, and what persists.

### 5. The persistence boundary (the invisible line)
The key insight made explicit: a short list splitting **durable** (survives restart) vs
**ephemeral** (rebuilt/lost) UI features — so you can look at any panel and know which it is.

### 6. Audit — soft spots (flag + why-it's-risky + recommendation)
Plain-English, prioritized:
- **Invisible persist/ephemeral boundary** (highest) — inbox, links, queues, watermarks are
  in-memory; a restart drops them with no UI cue. Recommend: document the tier per feature +
  decide which *should* persist (see §7).
- **Plan-reviews keyed by filename** — renaming a plan orphans its verdicts/comments silently.
  Recommend: stable id (content-hash or an id written into the review record).
- **Raw `cwd` as scope key** — no canonicalization; `/project` vs `/mnt/c/project` vs symlink
  aliases resolve to different `.awl/` folders. Recommend: canonicalize/normalize cwd before use.
- **Template dashboard-vs-project split undecided** — no rule for where a new template saves.
  Recommend: pick one default now (dashboard), defer project-scoped until needed.
- **Watermark persistence unspecified** — pointers are in-memory; restart = agents re-read full
  boards. Recommend: acceptable for v1; note it, revisit if context cost bites.

### 7. Recommended target model (light revision — NOT a teardown)
Keep the three homes exactly. Two targeted refinements only:
1. **Make the 4th tier (⚡ Live) a named, documented category** and decide per in-memory item
   whether it *should* persist (candidate: inbox items; probably-not: prompt queues). This is the
   single highest-leverage maintainability fix.
2. **Replace the two fragile keys** — stable id for plan-reviews; canonicalized cwd for project
   scope.
Everything else in OD-23 stands as-is.

### 8. Keeping it current (light)
Two lines: this note is the data/architecture counterpart to `design/DESIGN.md`; update the
master table (§3) whenever a store or a UI surface changes.

## Critical files (read to write accurately — this is a docs-only change)

- Ground truth already gathered, but verify paths against source before writing:
  `sidecar/storage.py` (three-homes model + accessors), `sidecar/runtime_store.py`
  (`sidecar/runtime/` + `sessions.json`), `sidecar/scratchpad.py`, `sidecar/library.py`
  (filename key), `sidecar/settings_io.py`, `sidecar/templates_store.py`, and the in-memory
  stores (`eventbus.py`, `hookbus.py`, `inbox.py`, `links.py`, `watermark.py`, `deletion.py`).
- UI anchors: `design/DESIGN.md`, `design/mockup.html` (`data-comp` names),
  `frontend/src/renderer/` (App.tsx, TeamGraph.tsx, AgentPanel.tsx, TeamFeed.tsx, PromptPanel.tsx,
  Settings.tsx) — for the pane/component mapping and to mark designed-but-not-yet-wired features.
- Scoping rationale: `dev/notes/agent-qa/open-system-decisions-2026-06-29.md` (OD-15/16/17/18/23).

## Scope / non-goals

- **Docs only.** No code changes to `sidecar/`, `frontend/`, or `design/`. The audit *recommends*;
  it does not implement fixes. (Acting on §6/§7 would be a separate, later task if you choose.)
- New file: `dev/notes/data-model-map.md`. No existing files edited except the DEVLOG entry.

## Verification (accuracy, since this renders no UI)

- Cross-check every path in the master table against the source accessor (e.g. `storage.setups_path`,
  `runtime_store._records_file`, `storage.scratchpad_path`) — no path stated that the code doesn't
  produce.
- Confirm each UI anchor exists: the `data-comp`/pane for every row is present in `design/mockup.html`
  or the renderer, and any "designed-not-wired" flag matches `frontend/src/renderer/`.
- Sanity-check the durability column against the persistence census (persisted ↔ one of the 5 files;
  everything else marked ephemeral).

## Finish

- Append a `DEVLOG.md` entry (re-read from disk first): what the note captures + the `Files:` line.
