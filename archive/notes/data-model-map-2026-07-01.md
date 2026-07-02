# The Dashboard Data & Storage Map — where every piece of data lives

> **ARCHIVED 2026-07-02 — fully ported, no longer maintained.** Everything normative here now lives in
> [`docs/ARCHITECTURE.md`](../../docs/ARCHITECTURE.md) (§§1–10 → its storage & lifecycle sections) and
> [`dev/notes/TODO.md`](../../dev/notes/TODO.md) (§11's T1–T11 → NEXT UP — BUILD). Kept for the original
> deliberation and the file:line ⚠ Today evidence; where this file disagrees with ARCHITECTURE.md, the
> ARCHITECTURE.md is right (e.g. the dashboard store now also holds a `projects.json` index, and the
> product opens one project at a time).

*Working note. The data/architecture counterpart to [`design/DESIGN.md`](../../design/DESIGN.md)
(which owns the visuals) and [`docs/ARCHITECTURE.md`](../../docs/ARCHITECTURE.md) (system wiring).
This answers: for any piece of data in the dashboard — **where is it stored, which part of the UI
shows it, and does it come back when you close and reopen the dashboard?***

*Rewritten 2026-07-01 to encode the storage-model decisions from the 2026-07-01 planning
session. **Anchored to the final intended design/system.** Where today's code diverges from the
target, a ⚠ **Today** marker states current reality (with file:line evidence). §10 lists the
amendments to roll into ARCHITECTURE.md after the build; §11 is the implementation backlog that
drives the next build run.*

> **TL;DR** — Six homes. A project's entire dashboard footprint lives in **one committed folder
> at its repo root** (`<project>/.awl-cc-dash/`) — agents, plans, docs, comments, inbox, links —
> so reopening a project restores it, and different projects never mix. The app itself keeps only
> **reusable building blocks** (Setups, templates). Claude Code's **transcripts are the master
> record**: everything display-like derives from them; we pin their retention and remember where
> they are, but never copy them. What used to be invisible in-memory state is now an explicit
> **persist-vs-derive contract** (§3). Net effect: close the dashboard, reopen it, and you're
> where you left off.

---

## 1. The six places data can live

Every piece of dashboard data sits in exactly one of these:

```
🏠 DASHBOARD STORE   sidecar/runtime/*.json            the app's shared toolbox — reusable, project-agnostic
📁 PROJECT STORE     <project>/.awl-cc-dash/*          everything about ONE project + its team — committed, travels with the repo
📜 TRANSCRIPTS       ~/.claude/projects/… (WSL)        Claude Code's own conversation logs — the master record; referenced, never copied
🛠 LAUNCH CONFIG     ~/.awl-cc-dash-agents/<name>/ (WSL)  per-agent settings.json + mcp.json written at launch (⚠ today: ~/.awl-agents/ — T9)
🔌 CLAUDE CONFIG     ~/.claude , <project>/.claude      surfaced & edited IN PLACE — the dashboard does NOT own it
⚡ DERIVED (live)     — nothing on disk —               deliberately ephemeral; rebuilt from 📜/drivers on every start
```

The one rule (amending **OD-23**): *anything about a specific project or its team lives in that
project's folder; only reusable building blocks live with the dashboard; Claude's own data is
surfaced or referenced, never owned or copied.* Tie-breaker for fuzzy cases: **"is this about one
project, or reusable across projects?"** → project → `📁`; reusable → `🏠`.

**Multi-project is a first-class requirement.** The dashboard runs different projects with
different agents and different configs — possibly at the same time. Nothing project-specific may
sit at the app level; two projects open side by side share *only* the 🏠 toolbox.

**`<project>` defined:** the **canonical repo root** of the project an agent works in — *derived*
from the agent's `cwd` (git top-level; symlink and `C:\…`/`/mnt/c/…` aliases resolved to one
form), so a subfolder launch or a path alias still lands on the same `.awl-cc-dash/`.
⚠ **Today:** `storage.project_root()` returns raw `Path(cwd)` unchanged
([`sidecar/storage.py:108`](../../sidecar/storage.py)) — canonicalization is backlog **T2**.

**Git status:** `<project>/.awl-cc-dash/` is **committed** (state travels with the repo — cloning
or reopening a project brings its dashboard state along). `sidecar/runtime/` stays gitignored
(live app-operational state). ⚠ **Today:** the folder is named `.awl/` and holds two files;
rename + taxonomy is backlog **T1**.

---

## 2. The project folder — `<project>/.awl-cc-dash/` layout

```
<project>/.awl-cc-dash/
├── plans/                     # plan .md files (plan-mode output lands here) + their sidecars
│   ├── roadmap.md             #   content — pure markdown, exactly as the agent wrote it
│   └── roadmap.meta.json      #   metadata sidecar — verdict, comments, anchors, provenance (§5)
├── docs/                      # dashboard-owned markdown docs + their sidecars
│   ├── scratchpad.md          #   the shared team scratchpad (OD-17)
│   └── <doc>.md / .meta.json  #   other dashboard-owned docs, same sidecar pattern
├── assets/                    # Library → Assets tab media (unblocks the OD-15 deferral)
└── state/                     # dashboard-owned JSON state for THIS project
    ├── agents.json            #   the project's agent roster: sessions + identity + launch config
    │                          #   + claude_session_id + resolved transcript path + retired numbers
    ├── inbox.json             #   persisted Inbox items (open-ended type set — see §3)
    ├── links.json             #   agent-to-agent links
    ├── routing.jsonl          #   thin routing overlay — non-default source/recipients, keyed by
    │                          #   transcript anchor ids (§6); append-only
    └── bookmarks.json         #   scratchpad read-watermarks, keyed (agent, canonical project)
```

Naming: the folder spells out the product (`awl-cc-dash`) — deliberately *not* `.awl` (too vague)
and *not* `.cc-dash` (reads as Claude Code's own, which is `.claude/`). Content format rule:
**things people/agents read = Markdown; records the app reads = JSON.** Subdirs are created as
they're first populated — no empty scaffolding.

⚠ **Today:** only `scratchpad.md` and `plan-reviews.json` exist, at the `.awl/` root
([`sidecar/storage.py:68-70`](../../sidecar/storage.py)); the roster lives app-level in
`sidecar/runtime/sessions.json`; everything under `state/` except the roster is in-memory only.
Migration is backlog **T1/T3**.

**Self-dogfooding:** this repo gets its own committed `.awl-cc-dash/` when the dashboard runs
against it — that's the product working correctly, not a special case. Dev agents: it's runtime
data, not product source (the code that creates it is `sidecar/storage.py`); commit it
deliberately, never as a side effect of unrelated commits. Tests keep using temp dirs via
`AWL_SIDECAR_RUNTIME` + per-test cwds. (Backlog **T10**.)

---

## 3. The persist-vs-derive contract

The old model had an invisible line: some things survived a restart, some silently didn't, and
nothing on screen told you which. The new model makes it an explicit contract with one rule:

> **Persist** what carries semantic or user-authored state that is NOT in the transcripts.
> **Derive** everything presentational or recomputable from the transcripts / live drivers.

| On-screen thing | Contract | Home | ⚠ Today |
|---|---|---|---|
| Inbox items — **open-ended type set** (today error/warning/plan/decision; a "response" type is already queued, [TODO.md](TODO.md) Next up #14 — store `type` as a string, don't hardcode the enum) | **Persist** | 📁 `state/inbox.json` | ⚡ `inbox._INBOX` ([inbox.py:32](../../sidecar/inbox.py)) — lost on restart |
| Pending **permission** prompt | **Derive** (meaningless after restart — re-raised by the live agent) | ⚡ | `SessionState.pending_permission` ([main.py:123](../../sidecar/main.py)); merged into `GET /inbox` as a synthetic card |
| Agent-to-agent Links | **Persist** | 📁 `state/links.json` | ⚡ `links._LINKS` ([links.py:27](../../sidecar/links.py)) — lost on restart |
| Message from/to routing (source, recipients) | **Persist** (non-default only — thin overlay, §6) | 📁 `state/routing.jsonl` | ⚡ lives only on ring events; lost with the ring |
| Scratchpad read-bookmarks (watermarks) | **Persist** (rides the state store — no bespoke system) | 📁 `state/bookmarks.json` | ⚡ `watermark._marks` ([watermark.py:25](../../sidecar/watermark.py)) — and the working board itself is ⚡ too (`scratchpad._LOG`, [scratchpad.py:32](../../sidecar/scratchpad.py)): the `.md` mirror is write-only, never loaded back, so today a restart **wipes the live board** (T3 adds reload-from-file + persisted bookmarks) |
| Typed-but-unsent prompt queue / Hold | **Derive** — *decided: drops on close*, no carry-over | ⚡ | same (`SessionState.prompt_queue`/`held`, [main.py:110](../../sidecar/main.py)) — already matches target |
| Message feed / history | **Derive** — replay 📜 transcripts into the ring | ⚡ ring (~5000, `AWL_EVENT_RING_MAX`) | same ([eventbus.py:37-41](../../sidecar/eventbus.py)) — already matches target |
| Cap warnings / lifecycle metrics | **Derive** — recompute from events | ⚡ | same |
| Console feed | **Derive** — live from the driver | ⚡ | same |
| Subagent list | **Derive** — re-query `/subagents` | ⚡ | same |
| Checklist run-strip | **Derive** — parsed live from events | ⚡ | same |
| Marquee (activity ticker) | **Derive** — a pure function over recent events ([marquee.py](../../sidecar/marquee.py)); zero persistence needed | ⚡ | same — already matches target |
| Hook-inject queue (pending context pushes) | **Derive** — regenerated by delivery logic | ⚡ | same (`hookbus._INBOX`, [hookbus.py:37](../../sidecar/hookbus.py)) |

Everything in the **Persist** rows is small JSON written as it changes (append-friendly, no
shutdown snapshot to lose). Everything in **Derive** is a view — restart-cheap by construction.

---

## 4. Master table — every data type, one row

The single lookup tying **home ↔ path ↔ UI ↔ restart behavior**. UI anchors are the final-design
`data-comp` names ([DESIGN.md registry](../../design/DESIGN.md)). "Today" states current code
reality where it differs from the target.

| Data type | Home | Target path | UI (pane · `data-comp`) | ⚠ Today |
|-----------|:----:|-------------|--------------------------|---------|
| Agent roster (which agents exist, per project) | 📁 | `state/agents.json` | Team Graph · `agent-node-card`; Agent→Create/Details | 🏠 `sidecar/runtime/sessions.json`, keyed by session id ([runtime_store.py:45](../../sidecar/runtime_store.py)) |
| Identity (role/number/name/color/icon) | 📁 | inside `state/agents.json` | everywhere · `identity-badge`, `agent-tile` | inside `sessions.json` (`identity` field, [drivers/bridge.py:604](../../sidecar/drivers/bridge.py)) |
| Retired identity numbers (never reused) | 📁 | inside `state/agents.json` | — | ⚡ `deletion._RETIRED` ([deletion.py:104](../../sidecar/deletion.py)) — lost on restart |
| Per-agent launch config (tools/plugins/MCP/permission rules) | 📁 | inside `state/agents.json` | Agent→Details/Create | inside `sessions.json` ([drivers/bridge.py:598-602](../../sidecar/drivers/bridge.py)) |
| Transcript reference (claude_session_id + **resolved path**) | 📁 | inside `state/agents.json` | — (drives Feed/History + resume) | id persisted; **path recomputed every call, never stored** ([transcript.py:77](../../bridge/transcript.py)) |
| Setups (reusable team rosters) | 🏠 | `sidecar/runtime/setups.json` | Settings (step-in) · `registry-row` | same — unchanged |
| Prompt templates | 🏠 | `sidecar/runtime/templates.json` | Prompt→Compose · `template-select` | same — **decided: shared store, final** (the "project templates may later…" door in [storage.py:98](../../sidecar/storage.py) is closed) |
| Plans (content) | 📁 | `plans/*.md` | Work→Library Plans · `plan-card`, `doc-editor` | listed **non-recursively** from the top of `cwd` (or one named subdir; nested trees not walked, [library.py:24](../../sidecar/library.py)); single-doc reads are path-explicit, not cwd-scoped ([main.py:1271](../../sidecar/main.py)); plan-mode output goes to Claude's default plans dir |
| Dashboard documents (content) | 📁 | `docs/*.md` | Work→Library Documents · `doc-editor` | only the scratchpad exists |
| Doc/plan metadata (verdict, comments, anchors, provenance) | 📁 | `<doc>.meta.json` sidecar, next to its doc (§5) | `verdict-badge`, `feedback-card`, `comment-popover`, `review-chip` | central `plan-reviews.json` keyed by **filename** ([library.py:13](../../sidecar/library.py)); Documents have none |
| Shared scratchpad | 📁 | `docs/scratchpad.md` | Feed→Scratch · `scratch-post`; Prompt Target=Scratch | `.awl/scratchpad.md` ([storage.py:139](../../sidecar/storage.py)); working log ⚡ (`scratchpad._LOG`) |
| Library Assets (media) | 📁 | `assets/` | Work→Library Assets · `asset-card` | deferred with **no home** (OD-15) — now unblocked |
| Inbox items | 📁 | `state/inbox.json` | Feed→Inbox · `*-inbox-card` | ⚡ (§3) |
| Links | 📁 | `state/links.json` | Work→Links + Graph drawer · `link-drawer`, `link-list`, `link-edges` | ⚡ (§3) |
| Routing overlay | 📁 | `state/routing.jsonl` | Feed · `recipient-badge`, From/To filter | ⚡ (§3) |
| Read-bookmarks | 📁 | `state/bookmarks.json` | (invisible — drives delta reads) | ⚡ (§3) |
| Unsent prompt queue / Hold | ⚡ | — (drops on close, by decision) | Prompt→Compose (send-timing) | same |
| Message feed / cap metrics / console / subagents / run-strip / marquee | ⚡ | — (derived, §3) | Feed / Team Graph / Agent→Console | same |
| Session transcripts (full history, incl. subagents) | 📜 | `~/.claude/projects/<encoded-cwd>/<claude_session_id>.jsonl` (WSL) | Feed/History (replayed) | exists; **retention unpinned** — 30-day default auto-delete (§6) |
| Per-agent launch files (`settings.json`, `mcp.json`) | 🛠 | `~/.awl-cc-dash-agents/<name>/` | — | `~/.awl-agents/<name>/` (`WSL_AWL_DIR`, [paths.py:120](../../bridge/paths.py)) — rename is backlog **T9** |
| Claude Code config (MCP/plugins/settings) | 🔌 | `~/.claude`, `<project>/.claude` | Settings (step-in) · `settings-row`, `registry-row` | same — surfaced, not owned |

*Env overrides:* `AWL_SIDECAR_RUNTIME` (moves 🏠), `AWL_EVENT_RING_MAX` (ring size), `AWL_DRIVER`
(default `bridge`), `AWL_SIDECAR_HOST` (bind host), `AWL_DISABLE_HOOKS` (kills per-agent hooks).

---

## 5. Documents & plans — content + sidecar metadata

**The design (decided this session):**

1. **Content and metadata are separate files, paired by name.** `roadmap.md` (pure markdown,
   exactly as the agent wrote it — the dashboard never writes into it) sits next to
   `roadmap.meta.json` (everything else: review state/verdict + who/when, comment threads
   (text · author · timestamp · resolved), quote-anchors, provenance — created-by/when/session).
   Nothing is embedded in the content file — no frontmatter requirement, no citation markers.
2. **Anchoring without citations:** a comment that targets specific text stores the *quoted
   snippet* (+ nearest heading); the UI matches and highlights it live. If the text is later
   edited beyond recognition, the comment degrades gracefully to a doc-level comment. Content
   stays pristine.
3. **Renames:** the dashboard renames both files together; an orphaned `.meta.json` (no matching
   `.md`) is detectable and offered for re-link. If agent-driven renames ever bite in practice,
   an embedded stable id can be added *then* — additive, nothing to unwind.
4. **Documents get comments like Plans.** The final design already gives Documents the
   editor-header Comment control (same treatment as Plans, [DESIGN.md:162](../../design/DESIGN.md));
   what Documents still needs is the Plans-style **footer action strip** (minus Reject/Approve) —
   already captured as a design task in [TODO.md](TODO.md) ("Documents Footer Action Strip", Next
   up #12; + the "Comment Popout Fit" bug, #13).
5. **Scope:** commenting applies to dashboard-owned files under `.awl-cc-dash/` only (the Library
   can still browse other repo `.md` files read-only). Extendable later if needed.
6. **Plan mode: kept, redirected.** Claude Code's built-in plan mode stays (its enforced
   pause-for-approval is what the Inbox plan flow rides). Its output is redirected into the
   project folder via the `plansDirectory` setting — a standard setting (this repo itself sets
   `./.claude/plans`) — written into each agent's materialized launch settings. Target:
   `plansDirectory` = the **absolute WSL path** `<canonical project root>/.awl-cc-dash/plans`,
   computed via the T2 canonicalizer (a relative `./` would resolve against the agent's raw cwd
   and break the §1 same-folder invariant for subfolder launches). ⚠ **Today:** the materialized
   settings carry only
   permissions/plugins/hooks ([drivers/bridge.py:504-523](../../sidecar/drivers/bridge.py)) — no
   `plansDirectory`. Backlog **T7**.

⚠ **Today:** plan reviews live in one central `plan-reviews.json` keyed by the plan's *filename*
(rename → review silently orphans, [library.py:13](../../sidecar/library.py)); Documents are
read-only with no comment store; doc write-back and Assets are deferred per OD-15. The sidecar
system (backlog **T6**) replaces all of that.

---

## 6. Transcripts — the master-record policy

Claude Code writes the full conversation of every agent (and its subagents) to JSONL transcripts.
**These are the master record**; the dashboard's rule is *reference, don't copy* — fat content
lives once, in the transcript; the dashboard persists only thin semantic overlays on top.

1. **Where they are.** Bridge agents run in WSL, so their transcripts are WSL-side:
   `~/.claude/projects/<encoded-cwd>/<claude_session_id>.jsonl`
   (`WSL_CLAUDE_PROJECTS`, [paths.py:104](../../bridge/paths.py)) — *not* the Windows-side
   `C:\Users\lester\.claude\projects` (that tree belongs to your own Windows sessions).
2. **Path mapping is solved, not trusted.** The dir-name encoding is lossy (every non-alphanumeric
   → `-`), so the bridge verifies against the real directory listing and resolves the exact file
   by session id ([transcript.py:31-126](../../bridge/transcript.py)).
   ⚠ **Today** the resolved path is recomputed on every read and never persisted; target persists
   it per agent in `state/agents.json` (with the session id), so the mapping survives restarts and
   scheme drift (backlog **T4**).
3. **Retention is pinned.** Claude Code auto-deletes sessions inactive longer than
   `cleanupPeriodDays` (default **30**) — unacceptable for transcripts we reference long-term.
   The bridge already materializes per-agent settings at launch; target adds
   `cleanupPeriodDays: 3650` there (10 years — effectively never; one constant to adjust),
   guaranteeing retention for dashboard agents without touching global config.
   ⚠ **Today:** not set anywhere (verified). Backlog **T5**.
4. **No backup copies.** Decided: pin retention + persist paths; do *not* archive transcript
   copies. Revisit only if durability proves shaky in practice (parked).
5. **Session prompts** are *not* separately saved — they're in the transcript; anything durable a
   user wants to reuse becomes a 🏠 template.
6. **The overlay-index principle.** Anything the dashboard adds *about* transcript content is
   keyed to the event **anchor id** the bus already mints —
   `{agent_id}:{source_kind}:{anchor}` where `anchor` is the transcript entry's own uuid
   ([eventbus.py:78](../../sidecar/eventbus.py)) — so overlays re-join losslessly on replay.
   First instance: `state/routing.jsonl`, an append-only file of
   `{anchor_id, source, recipients}` for **non-default routing only** (agent↔agent, scratch;
   default `agent → [user]` is re-derivable and never written). Replay transcript → left-join
   overlay → full feed, addressing intact, zero duplicated text.

---

## 7. Close & reopen — the restore model

**Requirement (decided, high priority):** closing the dashboard and reopening it later lands you
in near-exactly the same state. Two halves:

1. **State restore** — everything in §3's Persist rows plus the 📁 files comes back by
   construction: roster, identities, plans + reviews, scratchpad, inbox, links, routing,
   bookmarks. Feed history re-derives from 📜 transcripts — even when the agent processes are
   gone. (⚠ **Today** replay only happens through a live/rebound session's driver poll; a
   pruned dead agent's transcript is never replayed — fixed by T8 keeping the record.)
2. **Agent restore** — two cases:
   - **Warm** (sidecar restarted; tmux/WSL still running): rebind to the live session.
     ⚠ *Today this works* — `reconnect_sessions()` rebuilds `SessionState` from the record and
     re-attaches the driver ([main.py:579-615](../../sidecar/main.py)).
   - **Cold** (reboot/WSL shutdown; tmux gone): relaunch the agent with
     `claude --resume <claude_session_id>` in its cwd — same conversation, rebuilt from the
     transcript. ⚠ **Today this is the gap:** a dead-tmux record is **pruned** — deleted, agent
     forgotten ([main.py:567-570](../../sidecar/main.py)) — and nothing anywhere invokes
     `claude --resume` (the bridge's `resume()` only rebinds live tmux; if the session is gone it
     falls through to `create()` with a **fresh** session id, i.e. a brand-new conversation,
     [bridge.py:644-665](../../bridge/bridge.py)). Cold-restore is backlog **T8**; graceful
     degrade if it proves hard: restore all *data* and let agents be re-resumed manually.

**Cross-machine caveat (accepted):** cloning a project to another machine brings all 📁 state, but
transcripts and live processes stay in this machine's WSL — agents re-launch fresh there. By
decision, no cross-machine resume machinery gets built.

---

## 8. Follow one thing end-to-end

*Narrated in the **target model** — the ⚠ Today markers from §2–§7 apply; divergences are flagged
inline.*

**A scratchpad post (📁 + ⚡ + 🛠 working together):**
1. You (or an agent) post via Prompt with Target = Scratch → `POST /scratch`.
2. The sidecar appends to the in-memory working log (⚡ `scratchpad._LOG`) *and* rewrites the full
   board to `docs/scratchpad.md` (📁, durable; ⚠ today `.awl/scratchpad.md`)
   ([scratchpad.py:87-97](../../sidecar/scratchpad.py)).
3. Other agents get only the posts past their **bookmark** — delivered mid-run as passive context
   through the hook channel (🛠 hooks → `hookbus`), or at start-of-run catch-up; the bookmark
   advances (📁 `state/bookmarks.json`; the board reloads from its `.md` on start — ⚠ today both
   are memory-only, so a restart wipes the working board, per §3).
4. It renders in Feed→Scratch as a `scratch-post`; posts carry `recipients:[scratch]` (OD-22).

**A plan, reviewed (📜 + 📁):**
1. An agent in plan mode writes `plans/refactor.md` (plan-mode output redirected there, §5.6).
2. The plan-approval pause raises an Inbox `plan` card (📁 `state/inbox.json`); you review in
   Work→Library Plans.
3. Your verdict + comments land in `plans/refactor.meta.json` — quote-anchored to the passages
   they address, content file untouched.
4. Approve → the agent resumes; the whole exchange is in its 📜 transcript; the review record
   stays with the project, committed.

**Close and reopen (the §7 model, end to end):**
1. You close the dashboard (or reboot). Nothing is flushed at shutdown — persists were written as
   they happened.
2. Reopen: the sidecar reads each project's `state/agents.json` → roster + identities return.
   Live tmux sessions rebind (warm — works today); dead ones relaunch via `claude --resume <id>`
   (cold — T8, today they're pruned).
3. Feed history replays from 📜 transcripts; `state/routing.jsonl` re-joins addressing; Inbox,
   Links, bookmarks load from `state/`. The unsent prompt queue is intentionally empty.

---

## 9. Audit — what this model fixes (and the two spots to watch)

The 2026-06 audit's soft spots, resolved by this model:

1. ~~Invisible persist/ephemeral boundary~~ → the §3 contract (explicit, reviewable).
2. ~~Plan-reviews keyed by filename~~ → per-doc sidecars paired by name, dashboard-mediated
   renames, orphan re-link (§5).
3. ~~Raw `cwd` as scope key~~ → canonical repo root (§1, backlog **T2**).
4. ~~Templates dashboard-vs-project undecided~~ → decided: shared 🏠 store, final.
5. ~~Watermark persistence unspecified~~ → persisted as bookmarks in the shared state store (§3).

Still worth watching:

1. **Transcript-scheme drift.** The dir-encoding + `--resume` behavior belong to Claude Code, not
   us. Pinned retention + persisted paths (§6) reduce the blast radius; the live-verify habit in
   the bridge suite is the canary.
2. **Concurrent writers on one project.** Two agents in the same project share one `state/` —
   fine for append-only (`routing.jsonl`) and keyed writes, but the store implementation (T3)
   should do atomic write-replace per file to avoid torn JSON.

---

## 10. Amendments to roll into ARCHITECTURE.md (§7 + §10 OD record) after the build

| OD | Amendment |
|----|-----------|
| **OD-23** (storage & scoping) | `.awl/` → **`.awl-cc-dash/`** with the §2 taxonomy; `<project>` = **canonical repo root derived from cwd** (not raw cwd); the folder is **committed**; six-home model (📜 transcripts + 🛠 launch config promoted to first-class homes); **per-project agent roster moves from the dashboard store into `state/agents.json`** — the 🏠 store keeps only Setups + templates; the §3 persist-vs-derive contract replaces the implicit ⚡ tier. |
| **OD-15** (Library) | Plans/Documents/Assets live **inside** `.awl-cc-dash/` (`plans/`, `docs/`, `assets/` — Assets un-deferred); central `plan-reviews.json` → **per-doc `.meta.json` sidecars** (quote-anchored comments, provenance; rename-safe); **Documents gain the review actions** (footer strip minus Reject/Approve, per TODO.md Next up #12); plan-mode output redirected via `plansDirectory`. |
| **OD-16** (prompt composition) | Templates: shared 🏠 store is **final** — the "project-specific templates may later live in `.awl/`" door is closed. |
| **OD-17** (scratchpad) | Path → `.awl-cc-dash/docs/scratchpad.md`; **watermarks persist** as `state/bookmarks.json`. |
| **OD-22** (addressing) | Non-default routing **persists** as the `state/routing.jsonl` overlay keyed by event anchor ids. |
| **OD-19** (delete) | Delete/tombstone flow extends to the project `state/` files (roster entry, inbox/links/routing/bookmarks rows), not just the runtime record + transcripts. |
| *(new)* | Transcript policy (§6): retention pinned via per-agent `cleanupPeriodDays`; resolved path + session id persisted; reference-never-copy. |
| *(new)* | Close/reopen restore (§7): cold-restore via `claude --resume` replaces prune-on-dead-tmux. |
| *(new)* | `~/.awl-agents/` → `~/.awl-cc-dash-agents/`. |

---

## 11. Implementation backlog (beyond this doc's scope — drives the next build run)

Tasks, not facts. Each: what · where · why. Roll-up target after the build: ARCHITECTURE.md per §10.

| # | Task | Where | Why / closes |
|---|------|-------|--------------|
| **T1** | Rename `.awl/` → `.awl-cc-dash/` + the §2 subdir taxonomy (accessors for `plans/`, `docs/`, `assets/`, `state/`); one-time migration of any existing `.awl/` contents; scratchpad path → `docs/scratchpad.md` | [`sidecar/storage.py`](../../sidecar/storage.py) (`_AWL_DIRNAME:68`, path accessors) | §2 |
| **T2** | Canonicalize `<project>` from `cwd`: git top-level, symlink//mnt-alias normalization; use it everywhere cwd keys scope (incl. the scratch project key, [main.py:453](../../sidecar/main.py)) | `storage.project_root()` ([storage.py:108](../../sidecar/storage.py)) | §1; audit #3 |
| **T3** | Per-project state store: `state/` persistence layer (atomic write-replace; append for `.jsonl`); move the roster out of `sessions.json` → `state/agents.json`; persist inbox (open type set), links, routing overlay, bookmarks, retired numbers ([deletion.py:104](../../sidecar/deletion.py)); reload the scratchpad board from its `.md` on load. **Load trigger:** lazily on the first session whose canonical root resolves to the project (create or reconnect), cache per root, write-through thereafter | new `sidecar` module + [`inbox.py`](../../sidecar/inbox.py) / [`links.py`](../../sidecar/links.py) / [`watermark.py`](../../sidecar/watermark.py) / [`scratchpad.py`](../../sidecar/scratchpad.py) / [`runtime_store.py`](../../sidecar/runtime_store.py) | §3, §4; multi-project |
| **T4** | Persist `claude_session_id` + **resolved transcript path** per agent in `state/agents.json`; refresh on resolve | [`drivers/bridge.py:586-605`](../../sidecar/drivers/bridge.py), [`transcript.py`](../../bridge/transcript.py) | §6.2 |
| **T5** | Pin `cleanupPeriodDays: 3650` in the materialized per-agent settings | `_build_settings()` ([drivers/bridge.py:504](../../sidecar/drivers/bridge.py)) | §6.3 |
| **T6** | Per-doc metadata sidecars: `<doc>.meta.json` read/write (verdict, comments, quote-anchors, provenance), replacing `plan-reviews.json`; Documents comment endpoints; dashboard-mediated rename of the pair; orphan detection/re-link | [`sidecar/library.py`](../../sidecar/library.py), [`storage.py`](../../sidecar/storage.py) | §5; audit #2 |
| **T7** | `plansDirectory` = absolute WSL path `<canonical-root>/.awl-cc-dash/plans` in the materialized per-agent settings (**depends on T2** — a relative `./` resolves against raw cwd and breaks subfolder launches) | `_build_settings()` ([drivers/bridge.py:504](../../sidecar/drivers/bridge.py)) | §5.6 |
| **T8** | Cold-restore: on startup, dead-tmux records **resume** (`claude --resume <claude_session_id>`, correct cwd) instead of prune ([main.py:567-570](../../sidecar/main.py)); needs a bridge resume-launch path — today a passed `session_id` only pins `--session-id` (still a NEW conversation, [bridge.py:360](../../bridge/bridge.py)), no caller passes one, and `resume()`'s dead-session fall-through calls `create()` with no id at all ([bridge.py:664-665](../../bridge/bridge.py)); T8 swaps in `--resume <old-id>`; graceful degrade = restore data, manual re-resume | [`sidecar/main.py`](../../sidecar/main.py), [`bridge/bridge.py`](../../bridge/bridge.py) | §7; **enables** TODO.md B1 (B1's on-demand endpoint/UI stays open) |
| **T9** | Rename `~/.awl-agents/` → `~/.awl-cc-dash-agents/` (`WSL_AWL_DIR`, [paths.py:120](../../bridge/paths.py)) | [`bridge/paths.py`](../../bridge/paths.py) | naming consistency |
| **T10** | Dogfood: commit this repo's `.awl-cc-dash/`; CLAUDE.md note (runtime data, deliberate commits); confirm tests stay on temp dirs | `.gitignore`, `CLAUDE.md` | §2 |
| **T11** | Extend delete/tombstone to the project `state/` files | [`sidecar/deletion.py`](../../sidecar/deletion.py), [`main.py`](../../sidecar/main.py) | §10 OD-19 row |
| **T12** | *(design layer — already tracked)* Documents footer action strip minus Reject/Approve ([TODO.md](TODO.md) Next up #12); Documents comment-panel bug (#13) | `design/` (six-file propagation) | §5.4 |

**Decided-and-closed** (no task): templates → shared store final · unsent queue drops on close ·
no transcript backups · no cross-machine resume · env prefix stays `AWL_` · frontend package stays
`agent-dashboard` · content = Markdown / records = JSON · commenting scope = dashboard-owned files.

---

## 12. Keeping this current

This note is the data/storage ground-truth, the way `design/DESIGN.md` is the visual
ground-truth. When a store moves or a surface changes: update the **§4 master table** and the
**§3 contract**. When a backlog task lands: flip its ⚠ Today marker, strike the row in §11, and
carry the corresponding §10 amendment into ARCHITECTURE.md. When all of §11 is done, §10 empties
and this doc describes reality with no ⚠ markers left.
