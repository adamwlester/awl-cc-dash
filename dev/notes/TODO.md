# DASHBOARD TODO — DESIGN & BACKEND BACKLOG

> **⚠ Backlog is reference-only; "Next up" is the one actionable section.** For the lettered backlog sections (D · B · H), agents must not implement anything, and must not treat any entry as confirmed, approved, or scoped, unless the human points them at a specific item. The exception is **Next up**: items there are approved for work, and being directed to that section is itself the signal to build them (see its instructions). This is otherwise a capture-and-triage doc.
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
> **Group by domain** under the headings below (D Design · B Backend · H Housekeeping & docs). Keep like with like, order related items next to each other, and merge overlapping ones. **Next up** is separate — the active implementation queue (priority order, mixed domain).
>
> **Next up — implementing items.** Items in the Next up section are approved for work; being directed to that section is itself the signal to build them. For each item:
> 1. **Build it where it belongs.** Design items land in the design system (`design/`, authority `design/mockup.html`) per the CLAUDE.md design rules — propagate across all six files. Backend items land in the app (`sidecar/`, `bridge/`, `frontend/`) per the project's testing conventions (pytest; hermetic where possible).
> 2. **Work from the reference docs.** For design items, read `design/DESIGN.md` (intent, patterns) and `design/tokens.css` (single source of truth for every design value) first and let them inform the change — don't hardcode a value that belongs in tokens.css. For backend items, read `docs/ARCHITECTURE.md` (system wiring + the OD decision record) first.
> 3. **Keep the reference docs in sync.** If a change alters design intent or adds/changes a pattern, update DESIGN.md to match; if it changes system wiring, update ARCHITECTURE.md. Confirm doc and build agree before you call the item done. If no doc change is needed, confirm that explicitly.
> 4. **Leave the item in place when done — do not delete it.** Log the work in DEVLOG per the project rule and report what you changed; the human reviews the build and removes the item manually once satisfied.
>
> **Inbox.** The human keeps rough notes as a bullet list (one per line) under "Inbox" at the bottom. When asked to incorporate them, handle each note in turn:
> 1. File it into the **appropriate section** — best fit by domain, or whatever section the human names if they specify one (e.g. "Next up") — with a concise **bold header**, plus an ID (section letter + number) for backlog sections; Next up items get no letter.
> 2. Make **minimal edits for clarity only**: tighten the wording so it reads cleanly and complete any obvious shorthand, but never change the intent or scope, and don't add ideas of your own.
> 3. **Disambiguate references.** If the human used the wrong term, a loose label, or shorthand, map it to the actual component/feature name as it appears in `design/mockup.html` (or the relevant app module) so it's unambiguous what's being referenced. If you genuinely can't tell what's meant, keep the original wording and flag it rather than guess.
> 4. Delete it from the Inbox once filed, so the bucket stays empty for next time.

## D — DESIGN

> UI/UX work staged in the design system (`design/` — the mockup, tokens, DESIGN.md).

1. **Drag-in Files:** Drag files from the VS Code explorer tree into the UI to load their paths for reference.
2. **Link Edges:** Add link-related UI to the Team Graph (directed graph edges) so you can see how agents are linked (replaces the old hand-drawn link lines, since removed). The grouped link-list in the Link drawer now exists (OD-08); the on-graph edges themselves remain deferred (`link-edges`, `planned`).
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

## NEXT UP

> Active implementation queue — the one actionable section, in priority order, mixed domain. Approved for work; implement each item per the **Next up** steps in "How agents maintain this list." Leave finished items in place — the human removes them after reviewing the work. Empty by design when nothing is queued.

## INBOX

> Rough human notes for an agent to incorporate later — one rough note per bullet. Empty by design. An agent files each into the right section per the **Inbox** steps in "How agents maintain this list" (file with a bold header, an ID for backlog sections, minimal clarity edits, disambiguate references), then clears it from this list.

- We need some kind of indicator when an agent goes from active to idle and the user has not yet checked the output/response. 
- Given that we we cannot pull context information while an agent's running we could have context update periodically between runs and also have an option to pull directly possibly just by dropping down the context drop down in the agent panel but then we should probably have some kind of load indicator like a spinning thing so it's clear that it's not loaded but it will be.
- Make the major header and footer use the pink color and do the same for the major movable internal panel area dividers. For the latter, I still want them teal when hover or actively being moved.
- I want to switch from the cream background to something darker, like a charcoal. I want to keep the lighter cream for the main footer and the panel headers but for subheader within the panels I want to move to a darker charcoal (or whatever we use for the new main surface fill/background). 
- Our error/danger red reads as a little too pink. Works for the palette but does not jump out when scanning the UI. I think we need a more distinct error red for this.
- The Link config should default to 2-way.
- The Messages "Content" filter needs to include an option for the actual 'message' text (ie, whatever the main reply text is referred to).
- We need to include a trash/delete ghost button after edit for History cards for prompts that are not "Active" or "Complete" so that they can be deleted before they get run if needed.
- Make from and to inline heading labels the from and to vis toggles.
- Subagent selection in the dropdown needs to have the select All/None action wired to them. Right now, it does not select/deselect subagents, only agents.
- Make the stop buttons a danger background fill with empty square, not just the danger outline square.
- The agent selector at the top of the link config needs to be a dropdown for both the agents being linked.
- We need to include the same action strip in Documents as Plans for each of the Documents cards (eg Export, Reviewer, Revise...). Basically the same action strip as what we have in Plans cards. 

## SCRATCH

> Rough human design ideas and notes not to be used or considered by any agent.

### General
- I want to work out how to build in more visual elements in Plans like charts, mockups and diagrams. I am thinking a few things. We could have a separate tab in Library or put these in the Assets tab, but we will need a way to comment them with visual markers etc. We might utilize what we have already in this tool: design\mockup-toolkit.js. If we put it in the Assets, we may want to structure the nav bar with headings, like something for stock images
- Plans should utilize mermaid diagrams in markdown.
- Add some voice reading feature and, ideally, an option to change speed from normal up to 2-3x
- Need a string search feature for text fields.
- Need to turn compact into a multiselect with the 5 built in options.
- Need to track compaction history in context dropdown. Count and what type and when based on turns and time. Maybe put in the rewind/handoff list
- Output options should include tldr tables with tests/checks and emojis signaling status.
- I think we need to make a sort of icon/badge for the "system". This would be used for, say, system wide errors that are listed in the Inbox.
- We need a simple way to share context once between agents. Could add this to "timeline-mode-switcher" as another option. Could make it part of link config as an one-time option instead of save
- We need to add a "Fork" option to the Rewind/Handoff to the "timeline-mode-switcher".

### Big picture and/or Needs more research 
- We need to make sure we build both the ui and other elements in a modular enough way that we can easily modify and add features.
- Need to build in more visual elements in plans like charts, mockups and diagrams
- Consider including an Artifacts tab in Library
- Need to come up with a way to support injectable reused snippets into the prompts.
- Need to add ToDo functionality back into UI eventually.
- Find a way to to support highlighting words and terms in text and having it defined in context.
- I want inline squiggle spelling highlights in any large text areas like in Prompt->Compose or the Library editors.
- I want to be able to select any or sections of text anywhere and right click (or something) to be able to get a definition in context for that term.
- Need to impliment a schema such that for long sessions, agents check in with clear status updates. Better, also have an actual status bar that updates. We could include this status bar in the agent panel and agent cards
- Need to support a mode where agents can track real time desktop activity.
- Need to standardize our badge sizes better.
- Need to decide what subagent info we want access to and where we access it. Related, what does clicking the subagent icon on agent cards do?
- Need to confirm that the current UI components etc translate to neobrutalism.dev. Acceptable if they do not, but leaning towards using a consistent library for maintinence.
- Need to determine what files should stay markdown vs what files would actually work better as JSON given they will be handled by agents and can be rendered in the UI however we want.
- In addition to retry, I believe we 