# The Dashboard System Map — where data lives, how you see it, where it's fragile

*Working note. The data/architecture counterpart to [`design/DESIGN.md`](../../design/DESIGN.md)
(which owns the visuals). This one answers: for any piece of data in the dashboard — **where is
it stored, which part of the UI shows it, and does it survive a restart?** Read §1–§3 for the
mental model; §6–§7 for the honest audit.*

> **TL;DR** — The scoping model is simpler than it looks. Only **5 files** on disk hold any
> state. The thing that *actually* makes it hard to reason about is invisible: most of what the
> UI shows is **live in-memory** and gone on a sidecar restart, and nothing on screen tells you
> which is which. The homes model is sound; two small keys are fragile. Details below.

---

## 1. The one-screen model — four places data can live

Every piece of dashboard data sits in exactly one of these four categories. This is the whole
model:

```
🏠 DASHBOARD STORE   sidecar/runtime/*.json         the app's own memory — reusable, project-agnostic
📁 PROJECT STORE     <project>/.awl/*               data that travels WITH the repo, WSL-reachable
🔌 CLAUDE CONFIG     ~/.claude , <project>/.claude   surfaced & edited IN PLACE — the dashboard does NOT own it
⚡ LIVE (in-memory)   — nothing on disk —            rebuilt each run; GONE on a sidecar restart
```

The one rule (from decision **OD-23**): *dashboard/team/tool data lives with the dashboard;
project data lives with the project; Claude's own config is surfaced, not copied.* The
tie-breaker for any fuzzy case: **"is this about the project, or about the team/tool?"** →
project goes to `📁 <project>/.awl/`; team/tool goes to `🏠 sidecar/runtime/`.

Everything is keyed off each agent's **`cwd`** (its working directory) — never a hardcoded path
— so the physical location is free to move without rearchitecting.

**What's actually on disk (the entire durable footprint):**

| # | File | Category | Holds |
|---|------|----------|-------|
| 1 | `sidecar/runtime/sessions.json` | 🏠 | Which agents exist + their tmux names + **identity** (role/name/color/icon), so they survive a sidecar restart |
| 2 | `sidecar/runtime/setups.json` | 🏠 | Saved **Setups** (reusable team rosters) |
| 3 | `sidecar/runtime/templates.json` | 🏠 | Saved **prompt templates** |
| 4 | `<project>/.awl/scratchpad.md` | 📁 | The shared team **scratchpad** (a markdown board) |
| 5 | `<project>/.awl/plan-reviews.json` | 📁 | **Plan-review** verdicts/comments/owner (keyed by plan filename) |

That's it. `sidecar/runtime/` is **gitignored** (live operational state, never committed).
Overridable via the `AWL_SIDECAR_RUNTIME` env var. `<project>/.awl/` is created next to whatever
each agent's `cwd` is — so it lives inside *the project the agent works on*, not inside this repo
(unless an agent's `cwd` is this repo).

---

## 2. The three-pane UI → which stores each pane touches

The dashboard is a single desktop window: title bar on top, status footer on the bottom, three
resizable columns between. Anchoring the stores to the panes you actually click:

```
┌────────────── LEFT (Agent panel) ──────────────┬──────────── MIDDLE ────────────┬─────────── RIGHT ───────────┐
│  Tabs: Details · Create · Console               │  TEAM GRAPH  (agent cards grid) │  TEAM FEED                  │
│                                                 │  ── draggable divider ──        │   Messages·Scratch·Log·Inbox│
│  • Details  → reads Identity, Settings (per-    │  WORK PANEL                     │  ── draggable divider ──    │
│    agent MCP/model/plugins), Subagents          │   Tabs: Library · Links · Scratch│  PROMPT                     │
│  • Create   → writes Identity; spawns Sessions  │                                 │   Tabs: Compose · History   │
│  • Console  → reads/writes the raw console feed │                                 │                             │
└─────────────────────────────────────────────────┴─────────────────────────────────┴─────────────────────────────┘
```

- **LEFT — Agent panel** touches 🏠 Sessions/Identity (Create writes them; Details reads them),
  🔌 per-agent Settings, and the ⚡ live console.
- **MIDDLE — Team Graph** is a live view of ⚡ session run-state (cards, run-strip, marquee,
  subagent badges). **Work panel** reads 📁 scratchpad (Scratch), 📁 plan-reviews + project `.md`
  files (Library), and ⚡ links (Links).
- **RIGHT — Team Feed** renders the ⚡ event stream (Messages), 📁 scratchpad (Scratch), the ⚡
  log and ⚡ Inbox. **Prompt** writes into the queue/scratchpad and reads 🏠 templates.

**Selection is the spine:** clicking a Team Graph card focuses that agent everywhere at once —
Agent panel, Feed filter, and Prompt target all repaint to it.

---

## 3. Master table — every data type, one row

The single lookup that ties **path ↔ UI ↔ durability**. "Survives restart?" = is it one of the
5 files in §1, or live-only?

| Data type | Scope | Real path / "in-memory" | UI location (pane · `data-comp`) | Survives restart? |
|-----------|:-----:|-------------------------|----------------------------------|:-----------------:|
| Sessions (which agents exist) | 🏠 | `sidecar/runtime/sessions.json` | Team Graph · `agent-node-card` | ✅ |
| Identity (role/name/color/icon) | 🏠 | inside `sessions.json` | everywhere · `identity-badge`, `agent-tile`; edit in Agent→Create/Details | ✅ |
| Setups (team rosters) | 🏠 | `sidecar/runtime/setups.json` | Settings (step-in) · `registry-row` | ✅ |
| Prompt templates | 🏠 | `sidecar/runtime/templates.json` | Prompt→Compose · `template-select` | ✅ |
| Shared scratchpad | 📁 | `<project>/.awl/scratchpad.md` | Feed→Scratch · `scratch-post`; Prompt Target=Scratch | ✅ (disk); working copy is ⚡ |
| Plan reviews (verdicts/comments) | 📁 | `<project>/.awl/plan-reviews.json` | Work→Library Plans · `plan-card`, `verdict-badge` | ✅ |
| Library docs/plans (the `.md` files) | 📁 | project `.md` files under `cwd` | Work→Library · `doc-editor` | ✅ (they're your repo files) |
| Claude settings (MCP/plugins/config) | 🔌 | `~/.claude`, `<project>/.claude` | Settings (step-in) · `settings-row`, `registry-row` | ✅ (Claude owns them) |
| Inbox (error/warning/permission/plan/decision) | ⚡ | in-memory (`inbox._INBOX`) | Feed→Inbox · `*-inbox-card` | ❌ rebuilt/lost |
| Agent-to-agent links | ⚡ | in-memory (`links._LINKS`) | Work→Links + Team Graph drawer · `link-drawer`, `link-list` | ❌ rebuilt/lost |
| Messages / event feed | ⚡ | in-memory ring (`eventbus.GLOBAL_RING`, ~5000) | Feed→Messages · `message-card`, `recipient-badge` | ❌ rolling window |
| Prompt queue + Hold | ⚡ | in-memory (`SessionState.prompt_queue`) | Prompt→Compose (send-timing) | ❌ |
| Cap warnings / lifecycle metrics | ⚡ | in-memory (`SessionState`) | Team Graph card + Inbox warning | ❌ |
| Unread watermarks (scratchpad deltas) | ⚡ | in-memory (`watermark._marks`) | (invisible — drives what each agent re-reads) | ❌ |
| Console feed | ⚡ | driver/live | Agent→Console · `console-feed`, `console-runbar` | ❌ |
| Checklist run-strip | ⚡ | parsed live from events | Team Graph · `run-strip` | ❌ (real data) |
| Marquee (activity ticker) | ⚡ | — | Team Graph · `marquee` | ❌ (display-only) |
| Subagents | ⚡ | live (`/subagents`) | Team Graph · `subagent-badge`; Agent→Details `subagents-accordion` | ❌ |
| Session transcript (full history) | — | **driver-owned** (tmux JSONL), not the sidecar | Feed/History | ✅ (but owned by the bridge, not us) |

*Env overrides:* `AWL_SIDECAR_RUNTIME` (moves the 🏠 store), `AWL_EVENT_RING_MAX` (event ring
size), `AWL_DRIVER` (default `bridge`).

---

## 4. Follow one thing end-to-end

**A scratchpad post (📁 + ⚡ working together):**
1. You (or an agent) post via Prompt with **Target = Scratch** → `POST /scratch`.
2. The sidecar appends it to an **in-memory log** (`scratchpad._LOG`, ⚡) *and* mirrors the whole
   board to **`<project>/.awl/scratchpad.md`** (📁, durable).
3. Every other agent **auto-reads** it — but only the *new* posts past its personal **watermark**
   (⚡), which then advances. First read with no watermark = the full board; deltas after.
4. It shows in **Feed → Scratch** as a `scratch-post` card.
   → *Restart caveat:* the `.md` file survives, but the in-memory log and the watermarks don't —
   a fresh sidecar starts with an empty working log and every agent re-reads the full board once.

**A plan review (📁, durable):**
1. Work → **Library → Plans** lists the project's plan `.md` files.
2. You set a verdict / leave comments → stored in **`<project>/.awl/plan-reviews.json`**,
   a JSON object **keyed by the plan's filename**.
3. Verdicts live *only* in the Library Plans tab (the Inbox Plan card is Review + Reply, by
   design — no Approve/Reject there).
   → *Fragility:* rename the plan file on disk and its review record silently orphans (§6).

---

## 5. The persistence boundary — the invisible line

This is the single most useful thing to internalize, and the UI gives you no cue for it:

| **Durable** (survives a sidecar restart) | **Live wire** (rebuilt or lost on restart) |
|------------------------------------------|--------------------------------------------|
| Sessions + identity, Setups, Templates   | Inbox cards, Links, Prompt queue/Hold       |
| Scratchpad **file**, Plan reviews         | Message feed (rolling), Cap warnings         |
| Your project `.md` files                  | Watermarks, Console feed, Subagent list      |
| Transcript (driver-owned)                 | Scratchpad **working log**, Marquee          |

**Why it matters:** a restart of the sidecar quietly drops the right column's Inbox, all active
Links, and any queued prompts — while the left column (agents, identities) and the two `.awl/`
files come back intact. That asymmetry is fine *by design* for some of these (a pending permission
inject is meaningless after a restart) but questionable for others (a user probably expects Inbox
items and Links to still be there). See §6.

---

## 6. Audit — the soft spots (flag · why it's risky · recommendation)

Prioritized. None are catastrophic; all are worth a decision.

1. **The invisible persist/ephemeral boundary — *highest leverage.***
   Inbox items, Links, queues, and watermarks are in-memory only; a restart drops them with no
   UI signal. This is the root of "hard to maintain / hard to reason about."
   **Recommend:** promote ⚡ to a *named, documented* tier (§7) and decide **per feature** whether
   it should persist. Prime candidates to persist: **Inbox items** and **Links** (users treat
   them as durable). Fine to stay ⚡: prompt queue, pending-permission, watermarks.

2. **Plan-reviews keyed by *filename*.**
   `<project>/.awl/plan-reviews.json` is keyed by the plan's filename, so renaming a plan
   silently orphans its verdicts/comments. (Confirmed in `sidecar/library.py`.)
   **Recommend:** key by a stable id instead (a content hash, or an id written into the review
   record) with the filename kept only as a display label.

3. **Raw `cwd` used as the scope key — no canonicalization.**
   `storage.project_root(cwd)` takes the `cwd` string as-is. `C:\proj`, `/mnt/c/proj`, and a
   symlinked alias resolve to *different* `.awl/` folders even though they're the same project;
   conversely two agents sharing a `cwd` share one `.awl/` (fine for the scratchpad, silent if
   agent-specific state ever lands there).
   **Recommend:** canonicalize/normalize `cwd` (resolve symlinks + a single WSL/Windows form)
   before using it as a key.

4. **Templates: dashboard-vs-project split undecided.**
   Templates persist in the 🏠 dashboard store today, but OD-16 leaves a "project-specific
   templates *may later* live in `.awl/`" door open, with no rule for where a *new* template saves.
   **Recommend:** commit to **dashboard-only** for now (matches Setups); defer project-scoped
   templates until there's a concrete need, so the UI has one unambiguous save target.

5. **Watermark persistence unspecified.**
   Read-pointers are in-memory, so a restart makes every agent re-read the full scratchpad/context
   once. Not data loss — just a one-time context cost.
   **Recommend:** acceptable for v1; note it explicitly. If it ever bites, persist watermarks keyed
   by `(agent_id, canonical_cwd)`.

*Not a bug — by design, but worth knowing:* the **full transcript is owned by the bridge driver**
(tmux JSONL), not the sidecar. The sidecar's event list is a rolling in-memory mirror rebuilt from
the driver on reconnect. That's why message history feels durable even though the event ring is ⚡.

---

## 7. Recommended model — a light revision, not a teardown

**Verdict of the audit: the three-homes model is sound. Keep it.** The ideal path is two small,
targeted refinements — not a redesign:

1. **Make `⚡ Live` a first-class, documented tier, and set a persist decision per item.**
   Right now "in-memory" is an accident of implementation, not a stated choice. Name it, list what's
   in it (this doc's §5 table), and mark each item **keep-ephemeral** vs **should-persist**. The two
   worth persisting: **Inbox items** (→ a 🏠 or 📁 file) and **Links** (→ likely 📁, since they're
   about a project's team). This single move turns the invisible boundary into an explicit,
   reviewable contract — and is the highest-leverage maintainability fix available.

2. **Replace the two fragile keys.**
   Plan-reviews → stable id instead of filename (soft spot #2). Project scope → canonicalized `cwd`
   instead of the raw string (soft spot #3).

Everything else in OD-23 stands unchanged. That's the whole recommendation: the structure is right;
it just needs its ephemeral tier made honest and two keys hardened.

---

## 8. Keeping this current

This note is the data/architecture ground-truth, the way `design/DESIGN.md` is the visual
ground-truth. When a store moves or a UI surface changes, update the **§3 master table** and the
**§5 boundary**. If §6/§7 recommendations get actioned, move the affected rows from ⚡ to their new
home and note it here.
