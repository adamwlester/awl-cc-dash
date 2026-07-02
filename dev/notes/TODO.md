# DASHBOARD TODO — DESIGN & BACKEND BACKLOG

> **⚠ Backlog is reference-only; the "Next up" sections are the only actionable ones.** For the lettered backlog sections (D · B · H), agents must not implement anything, and must not treat any entry as confirmed, approved, or scoped, unless the human points them at a specific item. The exception is **Next up**: items there are approved for work, and being directed to that section is itself the signal to build them (see its instructions). This is otherwise a capture-and-triage doc.
>
> **What** — Staging backlog for the AWL dashboard, covering both layers of the product: the **design system** (`design/mockup.html`; design reference in `design/DESIGN.md`; design values in `design/tokens.css`) and the **backend/runtime** (`sidecar/`, `bridge/`, the `frontend/` app; system reference in `docs/ARCHITECTURE.md`). The backlog is grouped by domain.
>
> **How it's used** — The human writes rough notes under **Inbox**; an agent files each into the right section. Work gets driven either by promoting an item into **Next up** (then directing an agent there to implement it; the human removes it after reviewing) or by cutting any item into a fresh prompt. Nothing in the backlog is a work order until that happens.

## HOW AGENTS MAINTAIN THIS LIST

> **Verify first.** Before adding or reordering, check the item against the current system — the design files for design items, the app code for backend items — and confirm it isn't already built. Drop anything already implemented; trim partly-built items to just the remaining gap.
>
> **Leave empty sections empty.** When a section has no items, leave it blank beneath its heading + intro line. Never add a placeholder, an "(empty)" marker, a status line, or a changelog note (e.g. "this batch was implemented and removed on …") — the blank space *is* the signal, and that history belongs in DEVLOG, not here.
>
> **Format.** Each item is a numbered list entry — a **bold header**, then a concise description; bold only the header. E.g. `1. **Role Dropdown:** …`.
>
> **Numbering.** The backlog sections are lettered (D Design · B Backend · H Housekeeping & docs); items are a numbered list within each, so a backlog item's ID is its section letter + list number (e.g. B7). Cross-reference related items by that ID (e.g. "see D2"), and update those refs if you reorder. **Next up** items and **Inbox** notes stay unlettered — Next up items are transient (the human deletes each after reviewing the build), so they don't get stable IDs.
>
> **Open questions.** An item that still needs research or a decision before it's buildable carries an **(open)** marker after its bold header. It files into whichever domain section it concerns; resolve the question (or get the human's call) and drop the marker before treating it as buildable — never build an (open) item as-is.
>
> **Group by domain** under the headings below (D Design · B Backend · H Housekeeping & docs). Keep like with like, order related items next to each other, and merge overlapping ones. **Next up** is separate — the active implementation queues (**Next up — Design** · **Next up — Build**, each in priority order).
>
> **Next up — implementing items.** Items in the Next up sections are approved for work; being directed to one is itself the signal to build them. For each item:
> 1. **Build it where it belongs.** Design items land in the design system (`design/`, authority `design/mockup.html`) per the CLAUDE.md design rules — propagate across all six files. Backend items land in the app (`sidecar/`, `bridge/`, `frontend/`) per the project's testing conventions (pytest; hermetic where possible).
> 2. **Design path (Next up — Design).** Read `design/DESIGN.md` (intent, patterns) and `design/tokens.css` (single source of truth for every design value) first and let them inform the change — don't hardcode a value that belongs in tokens.css. Build in `design/` per the six-file propagation rule; if the change alters design intent or adds/changes a pattern, sync DESIGN.md to match.
> 3. **Build path (Next up — Build).** `docs/ARCHITECTURE.md` — the final-intended-system reference, with the decision record woven through it — **leads the build**: read it first and build **toward** what it describes. Completing an item normally means clearing the matching **"⚠ Today"** marker in ARCHITECTURE.md rather than rewriting its text; only edit the doc's actual text if the build deviated from documented intent or a new decision was made — and flag that to the human explicitly, never silently.
> 4. **Doc-sync checklist — both paths run it before finishing.** DEVLOG.md always; `design/DESIGN.md` for design work; `docs/ARCHITECTURE.md` for build work; `CLAUDE.md` only if folder structure moved.
> 5. **Leave the item in place when done — do not delete it.** Log the work in DEVLOG per the project rule and report what you changed; the human reviews the build and removes the item manually once satisfied.
>
> **Inbox.** The human keeps rough notes as a bullet list (one per line) under "Inbox" at the bottom. When asked to incorporate them, handle each note in turn:
> 1. File it into the **appropriate section** — best fit by domain, or whatever section the human names if they specify one (e.g. "Next up") — with a concise **bold header**, plus an ID (section letter + number) for backlog sections; Next up items get no letter.
> 2. Make **minimal edits for clarity only**: tighten the wording so it reads cleanly and complete any obvious shorthand, but never change the intent or scope, and don't add ideas of your own.
> 3. **Disambiguate references.** If the human used the wrong term, a loose label, or shorthand, map it to the actual component/feature name as it appears in `design/mockup.html` (or the relevant app module) so it's unambiguous what's being referenced. If you genuinely can't tell what's meant, keep the original wording and flag it rather than guess.
> 4. Delete it from the Inbox once filed, so the bucket stays empty for next time.

## D — DESIGN

> UI/UX work staged in the design system (`design/` — the mockup, tokens, DESIGN.md).

1. **Drag-in Files:** Drag files from the VS Code explorer tree into the UI to load their paths for reference.
2. **Link Edges:** Add link-related UI to the Team Graph (directed graph edges) so you can see how agents are linked (replaces the old hand-drawn link lines, since removed). The grouped link-list in the Link drawer now exists (the grouped link-list decision — `docs/ARCHITECTURE.md` §7.6 *Links*, "Tracking"); the on-graph edges themselves remain deferred (`link-edges`, `planned`).
3. **Dense Link Graphs (open):** Once links render as directed edges (see D2), decide how to keep many overlapping links readable and how to distinguish links sharing the same configuration.
4. **Save Response Summary:** Add a save action for summaries — the Summarize slide-over is copy-only today (the Export control saves raw selections, not generated summaries).
5. **Notes Hub:** Centralize my own notes somewhere in the dashboard — a project `notes.md` exists in Library → Documents, but there's no dedicated notes surface.

## B — BACKEND

> Features needing real backend/runtime work (`sidecar/`, `bridge/`, the `frontend/` app).

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
12. **Docs-on-Demand (open):** Dynamically give agents access to relevant, up-to-date documentation.
13. **Systems-Work Docs (open):** Ensure agents doing systems-level work always have up-to-date docs in context.
14. **AI-Touched Tracking (open):** Track what AI has touched with a local file per directory (e.g. `index.md`).
15. **Asset Sourcing (open):** Check that skills and other special CC assets are pulled from the ideal source.

## H — HOUSEKEEPING & DOCS

> Maintenance, config, and documentation chores.

1. **npm Binary:** Update npm to the native binary.
2. **PowerShell Strings:** Find a better set of strings for PowerShell permissions.
3. **Dashboard README:** Update the Dashboard README.
4. **CLAUDE.md Trim:** Optimize my CLAUDE.md files — index other files instead of a full context dump.
5. **Doc Date/ID Tagging:** Better tagging of dates and IDs for document creation and editing.
6. **System Details Doc:** Document and maintain my system details — OS, Claude install, plugins, etc.
7. **Config SOPs:** Write SOPs for all major system-config activities (agent, hook, skills setup).

## NEXT UP — DESIGN

> Active implementation queue — design work, in priority order. Approved for work; implement each item per the **Next up** steps in "How agents maintain this list" (design path). Leave finished items in place — the human removes them after reviewing the work. Empty by design when nothing is queued.

1. **Context Refresh + On-Demand Pull** *(B+D)*: Context can't be read while an agent is running — refresh it automatically between runs, and let opening the Agent panel's context accordion (`context-breakdown`) trigger a direct pull, with a loading indicator on the accordion while a pull is in flight (no loading-state primitive exists in the design system yet — add one).
2. **Pink Footer + Splitters** *(D)*: The title bar (`.topbar`) is already pink (`--main`); recolor the main footer (`.footbar`) to match, and swap the major panel splitters (`.rz-handle::before`) from navy to pink — keeping teal on hover **and while actively dragged** (teal currently rides `:hover` only; add a drag-state class in `behavior.js`'s `initResizers`). Update DESIGN.md's "clear navy divider" rule.
3. **Link Direction Defaults 2-Way** *(D)*: The Link Config `direction-cycler` defaults to A→B (`data-dir="ab"`); default it to A↔B (both).
4. **"Text" Content Toggle** *(D)*: Add a toggle for the main reply text — Claude Code's `text` content block, currently the always-visible `msg` block — to the Messages **Content** filter (default on), and mirror it into the Link drawer's **Shared content** multi-select (the two deliberately share one taxonomy). Label it **Text**; align the rail tag `msg` → `txt` to match.
5. **History Card Delete** *(D)*: Add a trash/delete ghost button after Edit in the History card header for prompts whose status is not **Active** or **Complete** (Queued / Next / Held), so prompts can be deleted before they get run.
6. **Agent-Surface Data Alignment** *(D)*: Every surface that lists agents/subagents (the feed From/To filter tree, Prompt To, graph cards, Agent panel) must render from one shared data source so rosters/counts can't drift — the feed filter tree is currently hand-authored HTML and disagrees with the graph cards on subagent counts (e.g. sandy, fen). **Team Graph cards are ground truth** where surfaces conflict.
7. **Subagent Count Badge → Selected/Total** *(D)*: In the From/To filter tree, a parent's subagent count badge (`ag-subcount`) shows only the total; show selected-of-total instead (e.g. "2/4").
8. **Selector Popovers → Accordions** *(D)*: Convert the agent-selector popovers — the feed From/To filter, Prompt **To**, and the **From** selector — from floating popovers to in-flow accordion drawers (content pushes down rather than overlaying); keep the contents, size, and layout otherwise, and switch the trigger icon to accordion chevron norms. From and To take equal space in the header sub-bar.
9. **History From → Multi-Select Filter** *(D)*: On the History tab, From becomes a multi-select filter (same list as To, minus the Scratch row); Compose keeps the single-select From source — multiple sources only make sense for history filtering, not for sending.
10. **Stop Buttons → Solid Danger** *(D)*: The icon-only Stop buttons (`.icon-btn--danger`, Messages + History footers) get a solid `--danger` background fill with a white square icon, not just the danger-red outline square. Update DESIGN.md's "Delete is the one solid-red-fill variant" wording.
11. **Link Config Pair Dropdowns** *(D)*: The two agents at the top of the Link Config drawer are static identity displays; make each a single-select agent dropdown (graph selection still prepopulates them).
12. **Documents Footer Action Strip** *(D)*: Give the Documents tab footer the same action strip as Plans (merged Export control · Reviewer chip · Revise) but leave out **Reject** and **Approve**, keeping the trash (Remove) icon button.
13. **Comment Popout Fit** *(D)*: In the Documents tab, clicking a comment opens the popout vertically smashed and the surrounding layout doesn't resize to fit its contents; fix the fit/resize behavior and give the Plans cards more height allowance (the `.plan-rev` row cap) to support it.
14. **"Response" Inbox Type** *(D)*: New non-blocking Inbox section at the bottom of the ramp (Error · Warning · Permission · Plan · Decision · **Response**, neutral `--muted` heading like Plan/Decision) signalling a run ended with output the user hasn't reviewed — the answer to the operator's prompt, complementing the five request-type sections (requests agents make of you vs. the response to what you asked). **One coalesced card per agent** (a second unseen run updates the card, e.g. "×2 runs", never stacks); the status badge stays plain **idle** (no fifth state, no state-dependent click) while the card envelope (`node-inbox`) counts it like a Warning. Actions: **View** (→ Team Feed → Messages with the filter scoped to that agent, scroll + flash the run's final reply — the plan-flash jump pattern; **completes the item**) · **Reply** (the shared Reply routing; also completes). No Dismiss; no read-tracking — it's a completable item like every other card ("leaves only when completed, never on a glance"). Opens on run end; stays open (coalescing) if a new prompt fires unseen; clears on Retire/Delete. Slug `response-inbox-card`; add the gallery specimen + a REQS demo item; update DESIGN.md (Inbox section table row, the coalescing rule, the node-inbox note — status-badge section unchanged).
15. **"System" Identity** *(D)*: Add a reserved System pseudo-identity, parallel to User: **gear glyph on a navy tile** (one additive `--ag-system` token in the `--foreground` ink family — never a jewel colour, System isn't an agent). Appears on Inbox **Error** cards for system-wide failures (infrastructure: tmux/WSL2/sidecar down; account-level: rate/usage caps, auth expiry; shared services: a global MCP server failing) and on **Log** lines for system events. **Filter-only, never addressable** (the existing subagent precedent): a System row sits **second, after User**, in the feed From/To filter, but is excluded from Compose To, Compose From, and the History From filter. On a System Error card, **Reply is disabled** — greyed, not removed (the Export-menu convention); no graph card exists, so there's no envelope mirror. Gallery specimens + DESIGN.md updates (identity section, Inbox notes).
16. **Timeline Heading** *(D)*: Give the Rewind/Handoff `timeline-mode-switcher` in Agent → Details a section heading labelled **"Timeline"** in the standard `.sec-h` style, matching the Context/Turns section labels.
17. **Link Restructure — One Relationship per Link, Trigger Dropdown, Active/Expired List** *(D)*: Supersedes the earlier dual-relationship link model ("a link can be both" — `docs/ARCHITECTURE.md` §7.6 *Links — agent-to-agent context* now describes the final one-relationship model): each link carries **one relationship** — the Relationship control becomes a **single-select button group** (Direct messaging | Shared context); wanting both = two links. **Trigger converts from a segmented control to a dropdown** (per the inline-vs-menu selector rule): **Now · Inject · Next · Queue · Hold · Piggyback**, entries styled like the Send split-button's timing-menu items (bold label + one-line description); defaults DM → Queue, SC → **Piggyback**. **Piggyback** (new, link-only trigger) never initiates — the payload rides the next message delivered to the target from any source; SC links keep the **full** trigger menu (no gating), with DESIGN.md's "Shared context never triggers a turn on its own" rewritten as trigger-dependent, plus a note that an actively-delivered share costs the target a turn to ingest (why Piggyback stays the default). **End-After amendment** (to the exchange-counting rule in `docs/ARCHITECTURE.md` §7.6, "End-After"): on a one-way link, each fire counts as an exchange — without this, End After is dead on every one-way link. SC's content-type multi-select + backfill switch unchanged, scoped to SC links. **All-links list rework:** replace the static "All links" heading with collapsible **Active Links / Expired Links** sections (the "— grouped by agent" hint text dropped; **no gray-out** — the section carries the state, per the Inbox typed-section precedent); entries **sorted peer-adjacent** within each agent group; each entry carries its **full relationship label** ("Direct messaging" / "Shared context") since a link now has exactly one; group-header agent badges gain a **corner count badge** (top-right overlay on the identity badge; teal fill >0 / muted at none — the node-inbox envelope convention; this is a **new overlay badge family** — register it in the gallery + the DESIGN.md badge catalog); include a few expired-link examples in the mockup demo data. One-shot context sharing is **not** a goal here (the human handles that via Messages → Embed/Attach) — do not add a "Once" preset. Update DESIGN.md throughout (the relationship-model and End-After notes, the Trigger table, the links-list section).
18. **Lucide Direction Arrows** *(D)*: The link direction-cycler and the All-links row indicators render unicode text glyphs (`→ ← ↔` via `textContent`) — thin and off-centre. Replace them with **Lucide icons** (`arrow-right` / `arrow-left` / `arrow-left-right`) at the standard ~2.25px UI-icon stroke, inked `--foreground` navy (no true black exists in the palette; navy is the ink everywhere), flex-centred in the control.
19. **Projects Tab + Close Flow** *(D)*: Add the Projects surface to the design system per the settled model: a **Projects tab first** in the Settings step-in tab row (Projects · Setups · Usage · MCP · Plugins · Config); a known-projects list (name, path, last-opened, agent count, an Open action per row) plus **"Open other folder…"**; the open project as a highlighted card pinned on top with **Close Project**; the two-button close confirm dialog (**"Close"** = agents keep running / **"Close & stop agents"**); a small active-project chip in the topbar/footbar (display + shortcut only). The empty/no-project-open state ships as a labeled gallery variant, **not** in mockup.html — the mockup stays in the project-open state. Working concept snippet to match: `.scratch/ui-snippets/projects-tab.html`.
20. **Design-file OD-reference sweep** *(D)*: `design/DESIGN.md`, `mockup.html`, `gallery.html`, `behavior.js`, and `styles.css` still carry ~85 retired OD-NN tokens; once design churn settles, rewrite each to reference the relevant `docs/ARCHITECTURE.md` section by name (or drop it where redundant). The archived tracker `archive/notes/open-system-decisions-2026-06-29.md` resolves what each number meant.

## NEXT UP — BUILD

> Active implementation queue — backend/runtime build work, in priority order. Approved for work; implement each item per the **Next up** steps in "How agents maintain this list" (build path). Leave finished items in place — the human removes them after reviewing the work. Empty by design when nothing is queued. Ported from the archived data-model map (`archive/notes/data-model-map-2026-07-01.md`) §11; the §n references below point to sections of that archived doc.

1. **Storage Rename + Subdir Taxonomy** *(B)*: Rename `.awl/` → `.awl-cc-dash/` and add the §2 subdir taxonomy — path accessors for `plans/`, `docs/`, `assets/`, `state/`; one-time migration of any existing `.awl/` contents; scratchpad path moves to `docs/scratchpad.md`. Where: `sidecar/storage.py` (`_AWL_DIRNAME:68`, path accessors). Why: §2.
2. **Canonical Project Root** *(B)*: Canonicalize `<project>` from `cwd` — git top-level, symlink and `/mnt`-alias normalization — and use it everywhere cwd keys scope, including the scratch project key (`sidecar/main.py:453`). Where: `storage.project_root()` (`sidecar/storage.py:108`). Why: §1; audit #3.
3. **Per-Project State Store** *(B)*: Build the `state/` persistence layer (atomic write-replace; append for `.jsonl`); move the roster out of `sessions.json` → `state/agents.json`; persist inbox (open type set), links, routing overlay, bookmarks, and retired numbers (`sidecar/deletion.py:104`); reload the scratchpad board from its `.md` on load. Load trigger: lazily on the first session whose canonical root resolves to the project (create or reconnect), cache per root, write-through thereafter. Where: new `sidecar` module + `inbox.py` / `links.py` / `watermark.py` / `scratchpad.py` / `runtime_store.py`. Why: §3, §4; multi-project.
4. **Persist Session Id + Transcript Path** *(B)*: Persist `claude_session_id` + the **resolved transcript path** per agent in `state/agents.json`; refresh on resolve. Where: `sidecar/drivers/bridge.py:586-605`, `bridge/transcript.py`. Why: §6.2.
5. **Pin Transcript Retention** *(B)*: Pin `cleanupPeriodDays: 3650` in the materialized per-agent settings. Where: `_build_settings()` (`sidecar/drivers/bridge.py:504`). Why: §6.3.
6. **Per-Doc Metadata Sidecars** *(B)*: `<doc>.meta.json` read/write (verdict, comments, quote-anchors, provenance), replacing `plan-reviews.json`; Documents comment endpoints; dashboard-mediated rename of the doc + sidecar pair; orphan detection/re-link. Where: `sidecar/library.py`, `sidecar/storage.py`. Why: §5; audit #2.
7. **Absolute `plansDirectory`** *(B)*: Set `plansDirectory` to the absolute WSL path `<canonical-root>/.awl-cc-dash/plans` in the materialized per-agent settings. **Depends on item 2** — a relative `./` resolves against raw cwd and breaks subfolder launches. Where: `_build_settings()` (`sidecar/drivers/bridge.py:504`). Why: §5.6.
8. **Cold-Restore on Startup** *(B)*: On startup, dead-tmux records **resume** (`claude --resume <claude_session_id>`, correct cwd) instead of prune (`sidecar/main.py:567-570`). Needs a bridge resume-launch path — today a passed `session_id` only pins `--session-id` (still a NEW conversation, `bridge/bridge.py:360`), no caller passes one, and `resume()`'s dead-session fall-through calls `create()` with no id at all (`bridge/bridge.py:664-665`); this swaps in `--resume <old-id>`. Graceful degrade = restore data, manual re-resume. Where: `sidecar/main.py`, `bridge/bridge.py`. Why: §7; **enables backlog B1** (B1's on-demand per-agent resume endpoint/UI stays open).
9. **WSL Home Dir Rename** *(B)*: Rename `~/.awl-agents/` → `~/.awl-cc-dash-agents/` (`WSL_AWL_DIR`, `bridge/paths.py:121`). Where: `bridge/paths.py`. Why: naming consistency.
10. **Dogfood the Committed Store** *(B)*: Commit this repo's `.awl-cc-dash/`; add a CLAUDE.md note (runtime data, deliberate commits); confirm tests stay on temp dirs. Where: `.gitignore`, `CLAUDE.md`. Why: §2.
11. **Delete → Project State Files** *(B)*: Extend the delete/tombstone flow to the project `state/` files — the roster entry plus inbox/links/routing/bookmarks rows — not just the runtime record + transcripts. Where: `sidecar/deletion.py`, `sidecar/main.py`. Why: §10 delete-flow amendment row.

## INBOX

> Rough human notes for an agent to incorporate later — one rough note per bullet. Empty by design. An agent files each into the right section per the **Inbox** steps in "How agents maintain this list" (file with a bold header, an ID for backlog sections, minimal clarity edits, disambiguate references), then clears it from this list.

## SCRATCH

> Rough human design ideas and notes not to be used or considered by any agent.

### General
- I want to switch from the cream background to something darker, like a charcoal. I want to keep the lighter cream for the main footer and the panel headers but for subheader within the panels I want to move to a darker charcoal (or whatever we use for the new main surface fill/background). 

- I want to consider darker background colors for the panel to replace #fef6e4 (thinking charcoal). 

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
- Need to confirm that the current UI components etc translate to neobrutalism.dev. Acceptable if they do not, but leaning towards using a consistent library for maintinence.
- Need to determine what files should stay markdown vs what files would actually work better as JSON given they will be handled by agents and can be rendered in the UI however we want.
- I want to work out how to build in more visual elements in Plans like charts, mockups and diagrams. I am thinking a few things. We could have a separate tab in Library or put these in the Assets tab, but we will need a way to comment them with visual markers etc. We might utilize what we have already in this tool: design\mockup-toolkit.js. If we put it in the Assets, we may want to structure the nav bar with headings, like something for stock images
- Plans should utilize mermaid diagrams in markdown.
- Add some voice reading feature and, ideally, an option to change speed from normal up to 2-3x
- Need a string search feature for text fields.
- Need to turn compact into a multiselect with the 5 built in options.
- Need to track compaction history in context dropdown. Count and what type and when based on turns and time. Maybe put in the rewind/handoff list
- Output options should include tldr tables with tests/checks and emojis signaling status.
- I suspect we need support for "workflows" but I need to research these more.