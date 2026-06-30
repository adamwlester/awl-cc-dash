# Dashboard TODO — ui-concept backlog

> **⚠ Backlog is reference-only; "Next up" is the one actionable section.** For the lettered backlog sections (A–D), agents must not implement anything, and must not treat any entry as confirmed, approved, or scoped, unless the human points them at a specific item. The exception is **Next up**: items there are approved for work, and being directed to that section is itself the signal to build them (see its instructions). This is otherwise a capture-and-triage doc.
>
> **What** — Backlog of changes for the dashboard mockup, `design/mockup.html` (design reference in `design/DESIGN.md`; design values in `design/tokens.css`). Focused on the UI concept. The backlog is grouped by implementation effort.
>
> **How it's used** — The human writes rough notes under **Inbox**; an agent files each into the right section. Work gets driven either by promoting an item into **Next up** (then directing an agent there to implement it; the human removes it after reviewing) or by cutting any item into a fresh prompt. Nothing in the backlog is a work order until that happens.

## How agents maintain this list

> **Verify first.** Before adding or reordering, open the latest mockup and confirm the item isn't already built. Drop anything already implemented; trim partly-built items to just the remaining gap.
>
> **Leave empty sections empty.** When a section has no items, leave it blank beneath its heading + intro line. Never add a placeholder, an "(empty)" marker, a status line, or a changelog note (e.g. "this batch was implemented and removed on …") — the blank space *is* the signal, and that history belongs in DEVLOG, not here.
>
> **Format.** Each item is a numbered list entry — a **bold header**, then a concise description; bold only the header. E.g. `1. **Role Dropdown:** …`.
>
> **Numbering.** The backlog sections are lettered A–D; items are a numbered list within each, so a backlog item's ID is its section letter + list number (e.g. B7). Cross-reference related items by that ID (e.g. "see B17"), and update those refs if you reorder. **Next up** items and **Inbox** notes stay unlettered — Next up items are transient (the human deletes each after reviewing the build), so they don't get stable IDs.
>
> **Group by effort** under the headings below (A Quick wins · B Big picture · C Needs research · D Housekeeping & docs). Keep like with like, order related items next to each other, and merge overlapping ones. **Next up** is separate — the active implementation queue (priority order, mixed effort).
>
> **Next up — implementing items.** Items in the Next up section are approved for work; being directed to that section is itself the signal to build them. For each item:
> 1. **Build it in `design/mockup.html`** — that's where these changes land.
> 2. **Work from `design/DESIGN.md` and `design/tokens.css`.** DESIGN.md is the design reference (intent, patterns); tokens.css is the single source of truth for every design value. Read both first and let them inform the change — don't hardcode a value that belongs in tokens.css.
> 3. **Keep DESIGN.md in sync.** If a change alters design intent or adds/changes a pattern, update DESIGN.md to match, and confirm DESIGN.md and the mockup agree before you call the item done. If no DESIGN.md change is needed, confirm that explicitly.
> 4. **Leave the item in place when done — do not delete it.** Log the work in DEVLOG per the project rule and report what you changed; the human reviews the build and removes the item manually once satisfied.
>
> **Inbox.** The human keeps rough notes as a bullet list (one per line) under "Inbox" at the bottom. When asked to incorporate them, handle each note in turn:
> 1. File it into the **appropriate section** — best fit by topic/effort, or whatever section the human names if they specify one (e.g. "Next up") — with a concise **bold header**, plus an ID (section letter + number) for backlog sections; Next up items get no letter.
> 2. Make **minimal edits for clarity only**: tighten the wording so it reads cleanly and complete any obvious shorthand, but never change the intent or scope, and don't add ideas of your own.
> 3. **Disambiguate references.** If the human used the wrong term, a loose label, or shorthand, map it to the actual component/feature name as it appears in `design/mockup.html` so it's unambiguous what's being referenced. If you genuinely can't tell what's meant, keep the original wording and flag it rather than guess.
> 4. Delete it from the Inbox once filed, so the bucket stays empty for next time.

## A — Quick wins

> Small changes to the current mockup.


## B — Big picture

> Larger features needing real backend/runtime.

1. **Per-Agent MCP & Plugins:** Set MCP servers and plugins per agent in the UI, not just globally.
2. **Custom Permissions:** Spin up an agent with custom permissions that would normally come from user `.claude/settings.json`.
3. **Load Past Agents:** Load past agents/models by name, ID, or via file explorer.
4. **Plans Tab:** Add a Plans tab (in the Agent panel, or rename Prompts → "Editor" and host it there) that surfaces Claude Code's native plans — show multiple plans, expand each to review/edit in place, and support review/edit/approval.
10. **Drag-in Files:** Drag files from the VS Code explorer tree into the UI to load their paths for reference.
12. **Interactive Comms:** Incorporate interactive, dynamic agent↔me communication via a shared "dynamic doc" the agent periodically references during each run.
14. **Queue Awareness:** For >2 linked agents, share in message front matter that another agent's message is queued, so an agent can decide whether to wait.
16. **Subagent Forking:** Forking is covered by Handoff; still need subagent creation/management in the UI and a decision on how agents spawn subagents.
17. **Link Edges:** Add link-related UI to the Team Graph (e.g. directed graph edges) so you can see how agents are linked (replaces the old hand-drawn link lines, since removed).
19. **Lifecycle Wind-Down:** Add an explicit end-of-life signal / graceful wind-down when an agent hits its auto-stop limits (the limits already exist).
21. **Save Response Summary:** Option to save summary data/log of a response.
23. **Git Automation:** Handle and semi-automate Git tasks, including commits.
24. **Change-Log Watcher:** Have an agent watch my codebase changes and auto-update change logs (or similar).
25. **System-Check Agent:** Create a system-checking agent that's easy to run.
26. **Notes Hub:** Centralize my own notes somewhere in the dashboard.
27. **Agent Archive:** Database of past agents with a short summary of each one's work plus timestamps (value still unclear).
28. **Handoff Artifacts:** Generate a summary/handoff report on Handoff, rather than the plain context-carry-over (which comes first). *(Moved from the old DESIGN.md "Future directions".)*
29. **Native Agent-Teams Messaging:** Adopt Claude Code's built-in inter-agent messaging in place of the custom sender/trigger wrapping, once the native feature matures. *(Moved from the old DESIGN.md "Future directions".)*

## C — Needs research / decisions

> Open questions to resolve before they become build items.

1. **Tasks:** Understand tasks, and decide whether tasks should be part of the workflow.
2. **Docs-on-Demand:** Dynamically give agents access to relevant, up-to-date documentation.
3. **Systems-Work Docs:** Ensure agents doing systems-level work always have up-to-date docs in context.
4. **AI-Touched Tracking:** Track what AI has touched with a local file per directory (e.g. `index.md`).
5. **Asset Sourcing:** Check that skills and other special CC assets are pulled from the ideal source.
6. **Transcript Payload:** Decide what an agent's "Transcript" link payload captures and from where (e.g. the raw session transcript files) — source/format isn't finalized. *(Moved from the old DESIGN.md "Open questions".)*
7. **Dense Link Graphs:** Once links render as directed edges (see B17), decide how to keep many overlapping links readable and how to distinguish links sharing the same configuration. *(Moved from the old DESIGN.md "Open questions".)*

## D — Housekeeping & docs

> Maintenance, config, and documentation chores.

1. **npm Binary:** Update npm to the native binary.
2. **PowerShell Strings:** Find a better set of strings for PowerShell permissions.
3. **Dashboard README:** Update the Dashboard README.
4. **CLAUDE.md Trim:** Optimize my CLAUDE.md files — index other files instead of a full context dump.
5. **Doc Date/ID Tagging:** Better tagging of dates and IDs for document creation and editing.
6. **System Details Doc:** Document and maintain my system details — OS, Claude install, plugins, etc.
7. **Config SOPs:** Write SOPs for all major system-config activities (agent, hook, skills setup).

## Next up

> Active implementation queue — the one actionable section, in priority order, mixed effort. Approved for work; implement each item per the **Next up** steps in "How agents maintain this list." Leave finished items in place — the human removes them after reviewing the work. Empty by design when nothing is queued.

## Inbox

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

## Scratch

> Rough human design ideas and notes not to be used or considered by any agent.

- Change stop button to use a filled red icon
- I want to work out how to build in more visual elements in Plans like charts, mockups and diagrams. I am thinking a few things. We could have a separate tab in Library or put these in the Assets tab, but we will need a way to comment them with visual markers etc. We might utilize what we have already in this tool: design\mockup-toolkit.js. If we put it in the Assets, we may want to structure the nav bar with headings, like something for stock images
- Plans should utilize mermaid diagrams in markdown.
- Need to add a permanent delete option along with retire that fully wipes the agent info from the system.
- Add some voice reading feature and, ideally, an option to change speed from normal up to 2-3x
- Need a string search feature for text fields.
- Need to turn compact into a multiselect with the 5 built in options.
- Need to track compaction history in context dropdown. Count and what type and when based on turns and time. Maybe put in the rewind/handoff list
- Output options should include tldr tables with tests/checks and emojis signaling status.


### Big picture
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