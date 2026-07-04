# DASHBOARD TODO — DESIGN & BACKEND BACKLOG

> **Backlog is reference-only; the "Next up" sections are the only actionable ones.** For the backlog sections ([BD] · [BB] · [BH]), agents must not implement anything, and must not treat any entry as confirmed, approved, or scoped, unless the human points them at a specific item. The exception is **Next up**: items there are approved for work, and being directed to that section is itself the signal to build them. This is otherwise a capture-and-triage doc.
>
> **Two lanes, three tiers.** Work flows **Inbox → Next up → Backlog** in two lanes: the **Design** lane (`design/` — the mockup, tokens, DESIGN.md) and the **Build** lane (the app — `sidecar/`, `bridge/`, `frontend/`; system reference in `docs/ARCHITECTURE.md`). *Build* is the umbrella; its backlog splits into **Backend** and **Housekeeping & Docs**. So the Design lane is **[ID] → [ND] → [BD]**, and the Build lane is **[IB] → [NB] → [BB]** (+ **[BH]**).

## SECTIONS

> One row per section below. Backlog sections carry a two-letter tag; an item's ID is that tag + its list number (e.g. `BB7`, `BD2`). Next up / Inbox items stay untagged — they're transient (the human deletes each after reviewing the build). Notes/helper areas (this top matter, Scratch) carry no tag.

| Tag | Section | What lives here |
|-----|---------|-----------------|
| `[BD]` | BACKLOG — DESIGN | UI/UX work staged in the design system (`design/` — mockup, tokens, DESIGN.md). |
| `[BB]` | BACKLOG — BACKEND | Features needing real backend/runtime work (`sidecar/`, `bridge/`, `frontend/`). |
| `[BH]` | BACKLOG — HOUSEKEEPING & DOCS | Maintenance, config, and documentation chores. |
| `[ND]` | NEXT UP — DESIGN | Approved design queue, priority order. Build per the design path; leave finished items for the human to remove. Empty by design when idle. |
| `[ID]` | INBOX — DESIGN | Rough human design notes to be filed into [BD] later (one per bullet). Empty by design. |
| `[NB]` | NEXT UP — BUILD | Approved build queue, priority order. Build per the build path; leave finished items for the human to remove. Empty by design when idle. |
| `[IB]` | INBOX — BUILD | Rough human build notes to be filed into [BB]/[BH] later (one per bullet). Empty by design. |
| — | SCRATCH | Rough human ideas **not** to be used or considered by any agent. |

## HOW AGENTS MAINTAIN THIS LIST

> **Verify first.** Before adding or reordering, check the item against the current system — the design files for design items, the app code + `docs/ARCHITECTURE.md` for build items — and confirm it isn't already built. Drop anything already implemented; trim partly-built items to just the remaining gap.
>
> **Leave empty sections empty.** When a section has no items, leave it blank beneath its heading. Never add a placeholder, an "(empty)" marker, a status line, or a changelog note — the blank space *is* the signal, and that history belongs in DEVLOG, not here.
>
> **Format.** Each item is a numbered list entry — a **bold header**, then a concise description; bold only the header. E.g. `1. **Role Dropdown:** …`.
>
> **Numbering & IDs.** Within a backlog section, items are a numbered list; an item's ID is the section tag's two letters + its list number (e.g. `BB7`, `BD2`). Cross-reference related items by that ID (e.g. "see BD2"), and update those refs if you reorder. Next up / Inbox items stay unlettered — they're transient, so they don't get stable IDs.
>
> **Open questions.** An item that still needs research or a decision before it's buildable carries an **(open)** marker after its bold header. It files into whichever domain section it concerns; resolve the question (or get the human's call) and drop the marker before treating it as buildable — never build an (open) item as-is.
>
> **Next up — implementing items.** Items in a Next up section are approved for work; being directed to one is itself the signal to build it. For each:
> 1. **Build it where it belongs.** Design items → the design system (`design/`, authority `design/mockup.html`) per the CLAUDE.md design rules — propagate across all six files. Build items → the app (`sidecar/`, `bridge/`, `frontend/`) per the project's pytest conventions (hermetic where possible).
> 2. **Design path ([ND]).** Read `design/DESIGN.md` (intent, patterns) and `design/tokens.css` (single source of truth for every design value) first and let them inform the change — don't hardcode a value that belongs in tokens.css. Build in `design/` per the six-file propagation rule; if the change alters design intent or a pattern, sync DESIGN.md.
> 3. **Build path ([NB]).** `docs/ARCHITECTURE.md` — the final-intended-system reference — **leads the build**: read it first and build **toward** what it describes. Completing an item normally means clearing the matching **"⚠ Today"** marker there rather than rewriting its text; only edit the doc's actual text if the build deviated from documented intent or a new decision was made — and flag that to the human explicitly, never silently.
> 4. **Doc-sync before finishing.** DEVLOG.md always; `design/DESIGN.md` for design work; `docs/ARCHITECTURE.md` for build work; `CLAUDE.md` only if folder structure moved.
> 5. **Leave the item in place when done — do not delete it.** Log the work in DEVLOG per the project rule and report what you changed; the human reviews the build and removes the item once satisfied.
>
> **Inbox.** The human keeps rough notes as a bullet list (one per line) under the matching Inbox — **[ID]** for design, **[IB]** for build. When asked to incorporate them, handle each note in turn:
> 1. **File it** into the best-fit section — design → [BD], backend → [BB], chore → [BH] (or whatever section the human names) — with a concise **bold header**, plus an ID for backlog sections; Next up items get no ID.
> 2. **Minimal edits for clarity only** — tighten the wording so it reads cleanly and complete any obvious shorthand, but never change the intent or scope, and don't add ideas of your own.
> 3. **Disambiguate references.** Map any loose label or shorthand to the actual component/feature name as it appears in `design/mockup.html` (or the relevant app module). If you genuinely can't tell what's meant, keep the original wording and flag it rather than guess.
> 4. **Delete it from the Inbox** once filed, so the bucket stays empty for next time.

## [BD] BACKLOG — DESIGN

1. **Drag-in Files:** Drag files from the VS Code explorer tree into the UI to load their paths for reference.
2. **Link Edges:** Add link-related UI to the Team Graph (directed graph edges) so you can see how agents are linked (replaces the old hand-drawn link lines, since removed). The grouped link-list in the Link drawer now exists (the grouped link-list decision — `docs/ARCHITECTURE.md` §7.6 *Links*, "Tracking"); the on-graph edges themselves remain deferred (`link-edges`, `planned`).
3. **Dense Link Graphs (open):** Once links render as directed edges (see BD2), decide how to keep many overlapping links readable and how to distinguish links sharing the same configuration.
4. **Save Response Summary:** Add a save action for summaries — the Summarize slide-over is copy-only today (the Export control saves raw selections, not generated summaries).
5. **Notes Hub:** Centralize my own notes somewhere in the dashboard — a project `notes.md` exists in Library → Documents, but there's no dedicated notes surface.

## [BB] BACKLOG — BACKEND

1. **Load Past Agents:** Load past agents by name, ID, or via file explorer. Fleet Setups save/load and startup auto-reconnect exist; still no on-demand per-agent resume (endpoint or UI).
2. **Plans Action Loop:** The Library → Plans tab (review rail + verdicts) is built; still need plan edit-in-place and wiring the Approve/Revise verdicts into the live flow (approve → resume the agent).
3. **Queue Awareness:** For >2 linked agents, share in message front matter that another agent's message is queued, so an agent can decide whether to wait.
4. **Subagent Management:** Observability is built (card badges, read-only audit accordion, feed scoping); still need subagent creation/management in the UI and a decision on how agents spawn subagents.
5. **Git Automation:** Handle and semi-automate Git tasks, including commits.
6. **Change-Log Watcher:** Have an agent watch my codebase changes and auto-update change logs (or similar).
7. **System-Check Agent:** Create a system-checking agent that's easy to run.
8. **Agent Archive:** Database of past agents with a short summary of each one's work plus timestamps (value still unclear).
9. **Handoff Artifacts:** Generate a summary/handoff report on Handoff, rather than the plain context-carry-over (which comes first) — currently an explicit deferral in DESIGN.md.
10. **Native Agent-Teams Messaging:** Adopt Claude Code's built-in inter-agent messaging in place of the custom sender/trigger wrapping, once the native feature matures.
11. **Tasks (open):** Understand tasks, and decide whether tasks should be part of the workflow.
12. **Docs in Agent Context (open):** Dynamically give agents access to relevant, up-to-date documentation, and ensure agents doing systems-level work always have current docs in context.
13. **AI-Touched Tracking (open):** Track what AI has touched with a local file per directory (e.g. `index.md`).
14. **Asset Sourcing (open):** Check that skills and other special CC assets are pulled from the ideal source.
15. **Storage Rename + Subdir Taxonomy:** Rename `.awl/` → `.awl-cc-dash/` and add the subdir taxonomy — path accessors for `plans/`, `docs/`, `assets/`, `state/`; one-time migration of any existing `.awl/` contents; scratchpad path moves to `docs/scratchpad.md`. Where: `sidecar/storage.py` (`_AWL_DIRNAME`, path accessors). *(This and BB16–BB25 implement the storage model in `docs/ARCHITECTURE.md` §8 — read it first; it owns the detail.)*
16. **Canonical Project Root:** Derive one canonical `<project>` from `cwd` — git top-level, symlink and `/mnt`-alias normalization — and use it everywhere a cwd key scopes, including the scratch project key. Where: `storage.project_root()` (`sidecar/storage.py`), `sidecar/main.py`.
17. **Per-Project State Store:** Build the `state/` persistence layer (atomic write-replace; append for `.jsonl`); move the roster out of `sessions.json` → `state/agents.json`; persist inbox (open type set), links, routing overlay, bookmarks, and retired numbers; reload the scratchpad board from its `.md` on load. Load lazily on the first session whose canonical root resolves to the project, cache per root, write-through thereafter. Where: new `sidecar` modules (`runtime_store` / `inbox` / `links` / `watermark` / `scratchpad`).
18. **Persist Session Id + Transcript Path:** Persist `claude_session_id` + the resolved transcript path per agent in `state/agents.json`; refresh on resolve. Where: `sidecar/drivers/bridge.py`, `bridge/transcript.py`.
19. **Pin Transcript Retention:** Pin `cleanupPeriodDays: 3650` in the materialized per-agent settings. Where: `_build_settings()` (`sidecar/drivers/bridge.py`).
20. **Per-Doc Metadata Sidecars:** `<doc>.meta.json` read/write (verdict, comments, quote-anchors, provenance), replacing `plan-reviews.json`; Documents comment endpoints; dashboard-mediated rename of the doc + sidecar pair; orphan detection/re-link. Where: `sidecar/library.py`, `sidecar/storage.py`.
21. **Absolute `plansDirectory`:** Set `plansDirectory` to the absolute WSL path `<canonical-root>/.awl-cc-dash/plans` in the materialized per-agent settings (a relative `./` resolves against raw cwd and breaks subfolder launches). **Depends on BB16.** Where: `_build_settings()` (`sidecar/drivers/bridge.py`).
22. **Cold-Restore on Startup:** On startup, dead-tmux records **resume** (`claude --resume <claude_session_id>`, correct cwd) instead of prune. Needs a bridge resume-launch path (today a passed `session_id` only pins `--session-id` — still a NEW conversation — and `resume()`'s dead-session fall-through calls `create()` with no id). Graceful degrade = restore data, manual re-resume. Where: `sidecar/main.py`, `bridge/bridge.py`. **Enables BB1** (BB1's on-demand per-agent resume endpoint/UI stays open). *(Mechanism proven feasible by the one-click-launch + rewind/handoff live spikes.)*
23. **WSL Home Dir Rename:** Rename `~/.awl-agents/` → `~/.awl-cc-dash-agents/` (`WSL_AWL_DIR`). Where: `bridge/paths.py`.
24. **Dogfood the Committed Store:** Commit this repo's `.awl-cc-dash/`; add a CLAUDE.md note (runtime data, deliberate commits); confirm tests stay on temp dirs. **Depends on BB15.** Where: `.gitignore`, `CLAUDE.md`.
25. **Delete → Project State Files:** Extend the delete/tombstone flow to the project `state/` files — the roster entry plus inbox/links/routing/bookmarks rows — not just the runtime record + transcripts. **Depends on BB17.** Where: `sidecar/deletion.py`, `sidecar/main.py`.

## [BH] BACKLOG — HOUSEKEEPING & DOCS

1. **npm Binary:** Update npm to the native binary.
2. **PowerShell Strings:** Find a better set of strings for PowerShell permissions.
3. **Dashboard README:** Update the Dashboard README.
4. **CLAUDE.md Trim:** Optimize my CLAUDE.md files — index other files instead of a full context dump.
5. **Doc Date/ID Tagging:** Better tagging of dates and IDs for document creation and editing.
6. **System Details Doc:** Document and maintain my system details — OS, Claude install, plugins, etc.
7. **Config SOPs:** Write SOPs for all major system-config activities (agent, hook, skills setup).

## [ND] NEXT UP — DESIGN

## [ID] INBOX — DESIGN

- I want to rework both the Plans and Documents tab layout and functionality. I want documents to have the same within card nav bar as projects. This means Documents needs to be card based as well, like Plans. This also means Documents should have commenting allowed and should the same within card action strip options and the Draft vs Approved badge and state tracking. The Documents tab should have a badge indicating how many docs have pending actions, just like the plans tab. The existing tab-based nav bar for Documents should be preserved and I want one of these added to Plans with a list of all Plans docs. For both Plans and Documents, clicking the entry in the tab-level nav bar should open the corresponding entry and, conversely, opening a given card should highlight/select that entry in the nav bar. For both the tab-level nav bars, the little card entries in the bar should have another row with the state badge (Approved/Draft). I want to add another state badge "Revising" or "Editing". With that, we might need to change the label for the "Revise" button to disambiguate it. Maybe something like "Refactor" that is more evocative of an operation that is integrating multiple sources of revision feedback. Might need to breakdown and actually have a multi word label for this button.
- Every example entry for Plans and Documents should have at least one author badge in the first rail cell (or whatever the term is for those) that indicates the original author. That first cell is the one that indicates document-wide stuff.
- The author popup box under the editor should include a note of what the agent did and why. The options I can think of are "drafted" and "edited" and maybe "revised", which can be inline headings for the summary text, followed by the nature of the action and a brief explanation if needed.
- Minor thing related to above. We need an example set of rail badges in the first plans tab entry (the one selected by default) where we have one an entry with all 3 types of rail badges/chips to see how that will fit in the layout; that is, how will a single rail block accommodate the max number of badges. On that, in order to account for the limited space, I am wondering if we really need the approve chip/badge, given that no revise or error chip/badge implicitly indicates a given section etc is approved.
- Modify the the little arrow used in the messages card indicating the sending to receiving agent in the card header. We should use the same right arrow icon as that used in the Link Config panel, though does not need to be the same size and line weight; style in a way that looks good.
- I want to change the Link Agent drawer button to be named Link Config, like the heading in the drawer. 

## [NB] NEXT UP — BUILD

## [IB] INBOX — BUILD

## SCRATCH

> Rough human design ideas and notes not to be used or considered by any agent.

### General
- I want to switch from the cream background to something darker, like a charcoal. I want to keep the lighter cream for the main footer and the panel headers but for subheader within the panels I want to move to a darker charcoal (or whatever we use for the new main surface fill/background). 
- I want to consider darker background colors for the panel to replace #fef6e4 (thinking charcoal).
- We need to standardize our count chips better. I am partial to just using teal for all these, not including the ones related to editing (approve, revise, etc). 

### Big picture and/or Needs more research 
- We need to make sure we build both the ui and other elements in a modular enough way that we can easily modify and add features.
- Need to build in more visual elements in plans like charts, mockups and diagrams
- Consider including an Artifacts tab in Library
- Need to come up with a way to support injectable reused snippets into the prompts.
- Need to add ToDo functionality back into UI eventually.
- Find a way to to support highlighting words and terms in text and having it defined in context.
- I want inline squiggle spelling highlights in any large text areas like in Prompt->Compose or the Library editors.
- I want to be able to select any or sections of text anywhere and right click (or something) to be able to get a definition in context for that term.
- Need to support a mode where agents can track real time desktop activity.
- Need to confirm that the current UI components etc translate to neobrutalism.dev. Acceptable if they do not, but leaning towards using a consistent library for maintenance.
- Need to determine what files should stay markdown vs what files would actually work better as JSON given they will be handled by agents and can be rendered in the UI however we want.
- I want to work out how to build in more visual elements in Plans like charts, mockups and diagrams. I am thinking a few things. We could have a separate tab in Library or put these in the Assets tab, but we will need a way to comment them with visual markers etc. We might utilize what we have already in this tool: design\mockup-toolkit.js. If we put it in the Assets, we may want to structure the nav bar with headings, like something for stock images
- Plans should utilize mermaid diagrams in markdown.
- Add some voice reading feature and, ideally, an option to change speed from normal up to 2-3x
- Need a string search feature for text fields.
- Need to turn compact into a multiselect with the 5 built in options.
- Need to track compaction history in context dropdown. Count and what type and when based on turns and time. Maybe put in the rewind/handoff list
- Output options should include tldr tables with tests/checks and emojis signaling status.
- I suspect we need support for "workflows" but I need to research these more.
- All commits need to include an agent id.
- We need a shared roster of agents and their state and current work that all agents have access to as part of their ongoing context. This might be subserved just by scratch
- Need to research if it is possible to directly render a terminal in the dashboard. Like actually embed a terminal so we could potentially cut down latency and generally have more direct ground truth regarding underlying terminal output.
- For our Decisions type entries in inbox, we need to have a way for me to get more detailed info for a given option. Either agents need to embed more detailed summaries of each option, a smaller support agent needs to be able to generate summaries as needed and/or there needs to be some type of small scoped qa feature for these. 
- Need to consider if we want to track all document/plans (possibly assets tab content) revisions. Ideally we would have a means of doing this by integrating minimal tracking metadata stored locally with git version control.
