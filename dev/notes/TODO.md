# DASHBOARD TODO — BACKLOGS & WORK QUEUE

> **Backlog is reference-only; [NU] NEXT UP is the only actionable section.** For the backlog sections ([BD] · [BH]), agents must not implement anything, and must not treat any entry as confirmed, approved, or scoped, unless the human points them at a specific item. The exception is **[NU] NEXT UP**: items there are approved for work, and being directed to that section is itself the signal to build them. This is otherwise a capture-and-triage doc.
>
> **One inbox, one queue, two backlogs.** Rough notes land in a single **[IN] INBOX**; an agent then syncs each into the right downstream home. Work still splits into two lanes by *where it gets built* — the **Design** lane (`design/` — the mockup, tokens, DESIGN.md) and the **Build** lane (the app — `sidecar/`, `bridge/`, `frontend/`; system reference in `docs/ARCHITECTURE.md`) — but both lanes now share a **single approved execution queue, [NU] NEXT UP**, since design and app work land as one build effort; each queued item is built per its lane's path. The Design lane's backlog lives here (**[BD]**); the **Build lane's backlog lives in `docs/ARCHITECTURE.md` §11 (Build backlog & queue)** and is staged into [NU] when work is actually picked up; housekeeping & docs chores keep their own backlog (**[BH]**). Both lanes are fed from the shared **[IN]** inbox.

## SECTIONS

> One row per section below. Backlog sections carry a two-letter tag; an item's ID is that tag + its list number (e.g. `BD2`, `BH1`). Next up / Inbox items stay untagged — they're transient (the human deletes each after reviewing the build). Notes/helper areas (this top matter, Scratch) carry no tag. The **backend/build backlog has no section here** — it lives in `docs/ARCHITECTURE.md` §11.

| Tag | Section | What lives here |
|-----|---------|-----------------|
| `[BD]` | BACKLOG — DESIGN | UI/UX work staged in the design system (`design/` — mockup, tokens, DESIGN.md). |
| `[BH]` | BACKLOG — HOUSEKEEPING & DOCS | Maintenance, config, and documentation chores. |
| `[NU]` | NEXT UP | The single approved work queue, priority order — design and build items together; each is built where it belongs, per its lane's path below. Leave finished items for the human to remove. Empty by design when idle. |
| `[IN]` | INBOX | Rough human notes (one per bullet) to be synced into [NU] or the right backlog section later. Empty by design. |
| — | SCRATCH | Rough human ideas **not** to be used or considered by any agent. |

## HOW AGENTS MAINTAIN THIS LIST

> **Verify first.** Before adding or reordering, check the item against the current system — the design files for design items, the app code + `docs/ARCHITECTURE.md` for build items — and confirm it isn't already built. Drop anything already implemented; trim partly-built items to just the remaining gap.
>
> **Leave empty sections empty.** When a section has no items, leave it blank beneath its heading. Never add a placeholder, an "(empty)" marker, a status line, or a changelog note — the blank space *is* the signal, and that history belongs in DEVLOG, not here.
>
> **Format.** Each item is a numbered list entry — a **bold header**, then a concise description; bold only the header. E.g. `1. **Role Dropdown:** …`.
>
> **Numbering & IDs.** Within a backlog section, items are a numbered list; an item's ID is the section tag's two letters + its list number (e.g. `BD2`, `BH1`). Cross-reference related items by that ID (e.g. "see BD2"), and update those refs if you reorder. Next up / Inbox items stay unlettered — they're transient, so they don't get stable IDs.
>
> **Open questions.** An item that still needs research or a decision before it's buildable carries an **(open)** marker after its bold header. It files into whichever domain section it concerns; resolve the question (or get the human's call) and drop the marker before treating it as buildable — never build an (open) item as-is.
>
> **Next up — implementing items.** Items in **[NU] NEXT UP** are approved for work; being directed to the section is itself the signal to build them. For each:
> 1. **Build it where it belongs.** Design items → the design system (`design/`, authority `design/mockup.html`) per the CLAUDE.md design rules — propagate across all five files. Build items → the app (`sidecar/`, `bridge/`, `frontend/`) per the project's pytest conventions (hermetic where possible).
> 2. **Design path (design items).** Read `design/DESIGN.md` (intent, patterns) and `design/tokens.css` (single source of truth for every design value) first and let them inform the change — don't hardcode a value that belongs in tokens.css. Build in `design/` per the five-file propagation rule; if the change alters design intent or a pattern, sync DESIGN.md.
> 3. **Build path (build items).** `docs/ARCHITECTURE.md` — the final-intended-system reference — **leads the build**: read it first and build **toward** what it describes. Completing an item normally means clearing the matching **"⚠ Today"** marker there rather than rewriting its text; only edit the doc's actual text if the build deviated from documented intent or a new decision was made — and flag that to the human explicitly, never silently.
> 4. **Doc-sync before finishing.** DEVLOG.md always; `design/DESIGN.md` for design work; `docs/ARCHITECTURE.md` for build work; `CLAUDE.md` only if folder structure moved.
> 5. **Leave the item in place when done — do not delete it.** Log the work in DEVLOG per the project rule and report what you changed; the human reviews the build and removes the item once satisfied.
>
> **Inbox.** The human keeps rough notes as a bullet list (one per line) in the single **[IN] INBOX** — they don't sort their own notes, so an agent triages each on request. Handle each note in turn:
> 1. **Sync it** into the right downstream home — by default a backlog (design → [BD]; backend/build → the §11 build backlog in `docs/ARCHITECTURE.md`; chore → [BH]), or **[NU] NEXT UP** when the human is directing it straight to work — with a concise **bold header**, plus an ID for backlog sections (Next up items get no ID).
> 2. **Minimal edits for clarity only** — tighten the wording so it reads cleanly and complete any obvious shorthand, but never change the intent or scope, and don't add ideas of your own.
> 3. **Disambiguate references.** Map any loose label or shorthand to the actual component/feature name as it appears in `design/mockup.html` (or the relevant app module). If you genuinely can't tell what's meant, keep the original wording and flag it rather than guess.
> 4. **Delete it from the [IN] inbox** once filed, so the bucket stays empty for next time.

## [BD] BACKLOG — DESIGN

1. **Drag-in Files:** Drag files from the VS Code explorer tree into the UI to load their paths for reference.
2. **Link Edges:** Add link-related UI to the Team Graph (directed graph edges) so you can see how agents are linked (replaces the old hand-drawn link lines, since removed). The grouped link-list in the Link drawer now exists (the grouped link-list decision — `docs/ARCHITECTURE.md` §7.6 *Links*, "Tracking"); the on-graph edges themselves remain deferred (`link-edges`, `planned`).
3. **Dense Link Graphs (open):** Once links render as directed edges (see BD2), decide how to keep many overlapping links readable and how to distinguish links sharing the same configuration.
4. **Save Response Summary:** Add a save action for summaries — the Summarize slide-over is copy-only today (the Export control saves raw selections, not generated summaries).
5. **Notes Hub:** Centralize my own notes somewhere in the dashboard — a project `notes.md` exists in Library → Documents, but there's no dedicated notes surface.
6. **Plans/Docs Card Nested-Fill Clipping (IN-5):** Audit the nested flex chain down the Plans/Documents card → nav → scroll tree (`min-height:0` / `min-width:0` / overflow discipline) so the resizable cards stop clipping — the recurring "not using standard logical fill nesting" failure. The movable panes' min/max constraints are now Layout tokens (`--win-*` / `--col-*` / `--pane-*`, landed 2026-07-04), so this is the remaining piece; low priority, since taller Library panels are an acceptable mockup workaround for now. Folds in the deferred row-1 flex-wrap review (audit ⑤). *(The old BD6 Full Gallery Audit was deleted 2026-07-08: the gallery was retired 2026-07-05 in favor of on-element `data-comp`/`data-variants` tagging + the auto-generated states page, which is exactly the drift-proofing that audit chased.)*
7. **View `agent.md` bodies in the UI (open):** A way to open an agent's `agent.md` body text in the Library editor — e.g. a small eye-icon on each Role-dropdown entry that loads that file into the editor (read-only). Pairs with the Documents scoped/typed browser (BD8).
8. **Documents scoped/typed browser (open):** A nav **inside** the Library's Documents tab — it does **NOT** replace the Library's own top tabs (**Plans · Documents · Assets stay exactly as they are**, [mockup.html:1213-1215](../../design/mockup.html#L1213-L1215)) — surfacing the shared config markdown (agent files, templates, snippets, response instructions): **top tabs Project · System** (the settled two-scope model — "System" is the persistent cross-project store, the old User scope folded in) and **side tabs** by type whose set changes with the top tab (overlapping but not fully). Side-tab candidates from the handoff: **Templates, Snippets, Agents, Skills** — ⚠ this side-tab set is thin and **UNVERIFIED** (a refactored handoff prompt likely compressed the operator's original notes), so **re-derive the true set from the operator** before building. Every collection is scope-aware (a System copy + a Project copy). Open decisions: how the UI-injected-text surfaces group into side tabs (the file-home build item is ARCHITECTURE §11.3 #38); how Documents' current project-doc content coexists with this browser; what else project-/system-specific belongs here. Folds the earlier config-collections note.
9. **Compose "Snippets" dropdown (open):** A dropdown of prewritten blurbs in Compose, above Templates, that insert into the next line of the Compose context — reuse the Templates / inserted-block primitive (ARCHITECTURE §7.14). Storage: markdown docs (`##` group headings + `###` snippet titles, or flat shorthand-name headings), scope-aware (System + Project); the decided file home rides ARCHITECTURE §11.3 #38. Extends the SCRATCH "injectable reused snippets" idea.
10. **Shared one-line summary — Team Feed & History cards (open):** Each posting/turn carries a concise summary (one short line — single-line clamp with ellipsis rather than a hard 80-char cut) shown in the collapsed trigger preview; full detail in the expanded dropdown. Seed entries may need elaborating to differentiate summary vs. detail. The Rewind/Handoff Timeline turn rows already consume the same summary (the turn-row restyle — old [ND] 15 — built 2026-07-08); where the summary comes from is build-side (agents likely lead with a one-liner — the response-format preamble, ARCHITECTURE §11.5 #32 / §11.3 #39).
11. **Alignment release-gate sweep:** Before release, sweep every card/row for alignment predicated on an optional sibling's presence (the standing rule [ND] 19 records in DESIGN.md) — reserve fixed-footprint slots (or equivalent) so trailing badges/columns scan straight down; known offender: editable fields' trailing ghost edit icon vs. non-editable rows.
12. **UI-spike practice + "nobody knows what this looks like yet" list:** Adopt temporary throwaway visual/interactive concept mockups ("UI spikes") that agents build in parallel with other work, for features with no settled look. Starter list: (1) a visual-media/graphics interface for working with agents (`mockup-toolkit.js` fleshed out into a real surface; likely lives with `assets/`) — the operator's most-wanted; (2) the consolidated system-status/alert/error surface (the Q3 display question; the footer status rail is the leading sketch). More to be added as they surface.

## [BH] BACKLOG — HOUSEKEEPING & DOCS

1. **npm Binary:** Update npm to the native binary.
2. **PowerShell Strings:** Find a better set of strings for PowerShell permissions.
3. **Dashboard README:** Update the Dashboard README.
4. **CLAUDE.md Trim:** Optimize my CLAUDE.md files — index other files instead of a full context dump.
5. **Doc Date/ID Tagging:** Better tagging of dates and IDs for document creation and editing.
6. **System Details Doc:** Document and maintain my system details — OS, Claude install, plugins, etc.
7. **Config SOPs:** Write SOPs for all major system-config activities (agent, hook, skills setup).
8. **Over-Scoped Absolute-Language Audit:** Sweep the guiding docs (`docs/ARCHITECTURE.md`, `design/DESIGN.md`) for categorical wording — "never", "always", "only", "read-only", "no X exists", "cannot" — and test each rule against the *actual* intent it protects. Where the wording over-reaches that intent it manufactures false contradictions (with DESIGN, the code, or a sibling section) and gets re-litigated every session; narrow those to their real invariant, but leave genuinely-absolute invariants intact (the goal is right-sizing, not blanket-softening). Two already surfaced in the Phase-5 discussion and slated for that reconciliation: §7.16/§8.5 "the dashboard **never writes into a content file**" (real rule: the *review layer* never embeds annotations in agent content — create/delete/explicit user-directed edits are fine) and §7.5 identity "**read-only in v1**" (identity is editable). Same doc-reconciliation family as the coverage audit.
9. **Workflow-Tracker Convention:** Give live workflow-tracker docs (like the 2026-07-03 doc-integration tracker) a real home: `dev/notes/trackers/` — one active tracker per workflow, dated filename, a "what this is" header, a durable decision register with explicit handoff rules, archived out on completion. Record the convention in the docs so a fresh session has exactly one predictable place to look. (The eventual dashboard surfacing — trackers as a tab, Library the natural candidate — stays a future design idea.)

## [NU] NEXT UP

1. **Panel label renames (design):** "Team Graph" → "Team" and "Team Feed" → "Feed" — the panel headings ([mockup.html:917](../../design/mockup.html#L917), [mockup.html:1445](../../design/mockup.html#L1445)) plus the renderer's panel titles; true DESIGN.md's current-state prose to the new names (historical changelog notes stay as written).
2. **Past tab → Team drawer (design):** move the Past tab's content — the `past-agent-picker` panel ([mockup.html:862-886](../../design/mockup.html#L862-L886)) — into the Team (Team Graph) panel as a second drawer with the same Sheet behavior as Link Config ([mockup.html:1351](../../design/mockup.html#L1351)); the Past tab leaves the mid tab bar ([mockup.html:524](../../design/mockup.html#L524)). Mockup + renderer.
3. **Library accordions fill + comment popout fix (design):** the accordions in Library → Plans and Documents expand to fill the whole vertical panel height; and fix the comment popout not showing when active — suspected layout config (same nested-fill family as BD6). Mockup + renderer, wherever each breaks.
4. **Agent icon visibility fix (build):** reconcile the 11 icon-name mismatches between the sidecar's curated auto-assign list ([identity.py:68](../../sidecar/identity.py#L68) — raw file names like `dragon-head__lorc`) and the renderer sprite map ([icons.tsx:68](../../frontend/src/renderer/lib/icons.tsx#L68) — plain `dragon-head`), the "fnord has no icon" bug; and make the missing-sprite `<img>` fallback paint with the agent's colour instead of hardcoded white ([icons.tsx:89](../../frontend/src/renderer/lib/icons.tsx#L89)). Same seam as item 5 — do together.
5. **Icon picker serves all 167 icons (build):** the picker offers the full shipped set (`assets/icons/agents/`), not the 50 sprite-embedded subset — stages ARCHITECTURE §11 #56; direction per that row: serve the full set through the existing recolor endpoint.
6. **Console expand reuses the live attach (build):** expanding an already-attached console must not re-run the attach wait — reuse/share the existing attach + connection between the in-column and expanded views, provided reliability isn't hurt (keep the retry-on-hiccup; the single-writer resize rule unchanged).
7. **Model: drop the Claude-Code-default "Inherit"; app default = Opus (build + design):** remove the Inherit option from Create's model selector ([mockup.html:638](../../design/mockup.html#L638) + renderer) — the "no `--model` flag → whatever Claude Code's own config defaults to" path is retired; the product defines its own default, **Opus** (Create opens on Opus; sidecar/bridge pin the model explicitly). Fork's "inherit ← parent" ([mockup.html:831-832](../../design/mockup.html#L831-L832)) is a different concept — the parent agent's model — and **stays**. The five seeded role presets hard-pin `model: fable` ([.awl-cc-dash/agents/](../../.awl-cc-dash/agents/)). ⚠ Decision change: supersedes the inherit doctrine ARCHITECTURE recorded 2026-07-17 (§7.5 role-presets / launch prose) — update that text with the build and flag it explicitly.

## [IN] INBOX

## SCRATCH

> Rough human design ideas and notes not to be used or considered by any agent.

### General

- Need to integrate workflow support In terms of intercepting /workflows and approving via the inbox. The approval might require some means of displaying the proposed workflow as well, ideally rendered in the inbox card content. Need to consider if this fits in one of the existing inbox sections or it needs its own.
- I want the menus for skills/tools/servers/plugins and possibly deny rules to be formatted more nicely with clear categories and nice visible helper text giving a brief description for each tool with the tool name. 


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
- We need to clearly track fork and handoff lineage including original transcript access and it should be visible to all agents so they can reference their ancestors transcripts as needed.
- We need a way to see and potentially reuse retired agents. I am considering if we should include hidden by default collapsable sections at the end of our agent dropdowns that have them and maybe something like that in our agent cards.
- I want to make all id badges clickable so we can easily load agent details from anywhere.
- I think it would be really helpful I think it would be real it's an idea ly helpful to have a system in place that always forks an agent at any planning question stage so I can ask all the questions and get all the context I need and then work through the problem piece by piece and they can feed all that context back and retire after things are resolved
- We really need to figure out how to incorporate diagrams and mermaid visuals and all of that ideally directly in our plans and agent responses all over the place I want visuals out of the ass! I'm so tired of walls of Claude text.
- I want to build in support to use our quote unquote export code to basically import web and desktop clauds into the dashboard workspace as needed and I still think it'd be **** cool to be able to have my agents and those agents communicate through stored transcripts
- One of the most unpleasant parts of the agent workflow is trying to fish through rims of text I think I really need to spend some time on how to standardize the formatting of certain signal text or segments or sections like if there's a question actually make that text a certain color or have it highlighted vividly or something more than just emojis and something more than just bolding and something more than just italics
- I want to wire things up so that if it's like more than two or three minutes maybe 5 minutes it can be something we set goes by with a pending request that hasn't been answered and I'm clearly working in the desktop not being there that there's some kind of audible noise . on that actually I also want to wire up that if I have agents unrestricted and I start a run and then they are sitting there pending I might want to have an option to auto set them to bypass so that I don't end up coming back and finding that no work was done maybe a toggle just not an not a thing that's set by default 
- I think this project this platform would really benefit from always having one immortal Mommy agent who's just there when you need something and you need to tell them to do something they have all the context we'd have to figure out a way for them to be able to track over long periods of time which is always the problem but I just like the idea of like almost like they just sitting in the center of things just waiting for your dirty tissues so that I don't have to think about who I need to reach out to because they know the whole network and so if they don't know something they know where to look because I'm constantly losing track ....'m in with whom and where to put because I'm constantly losing track of what workflow I'm in with whom and where to put shit 