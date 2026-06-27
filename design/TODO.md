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

1. **Error run state (4th state):** Add Error alongside active/idle/pending on the Team Graph cards. Create an `.nb-error` badge — solid `--danger` fill, white (inverse) text — matching the other run-state badges (`.nb-idle/active/pending`, ~1031). Put at least one demo agent into the error state: `nb-error` badge "Error", a red run-strip, and a node-feed line like "run failed — see Inbox". Clicking the Error badge routes to Inbox: add an `'error'` branch to `statusJump()` (~4186) mirroring the `'pending'` branch (opens/flashes that agent's Inbox card). Also restyle the Message-card status badge `.db-error` (~1109) from its current soft-red-fill/red-text to a **solid `--danger` fill + inverse text**, so it matches the other status badges; the existing demo error card (drew / ECONNREFUSED, ~4821) picks this up automatically. Document Error as the 4th run state in DESIGN.md (the status-badge line ~5150 + run-state notes) and the inline comment at ~598.

2. **Dividers stay put on hover/select:** Today, selecting certain cards/rows/lines makes a navy divider line disappear (it gets repainted to match the fill). Stop that — every navy divider line stays navy in **every** state, with the hover (cream) and select (teal) fills showing **behind** it. Affected: the header/body divider on an expanded+selected Feed/Messages card; the divider between two stacked selected rows; the navy line between the editor's line-number gutter and the text (on both the light-teal line/section selection and the dark-teal comment-highlight). Keep all selection/hover fills and all click/select behaviour exactly as-is — the only change is "lines no longer hide."

3. **Subagent footer → accordion drawer:** Replace the +N floating popover with an in-flow accordion in the agent-card footer, like the Inbox cards: the footer is the trigger with a chevron action icon on the right (toggleFcard-style). Collapsed shows only the first row of subagent badges (chevron right); open grows the footer downward to reveal the remaining badges wrapped onto new rows (chevron down); state sticks (toggle, not a hover popover). Vertically centre the first (always-visible) row in the trigger. Only show the chevron/drawer when there's more than one row. Keep the status-fill badges and the per-badge stopPropagation.

4. **Editor gutter extends to the bottom:** The line-number gutter/rail currently stops at the last line, leaving dead space below. Extend the empty rail track (tan background + navy divider) down to the bottom of the visible editor so it doesn't stop abruptly. Do **not** fabricate line numbers for the empty space — real numbers stop at the last file line; only the empty track continues.

5. **Fix the reviewer-chip dropdown:** In Plans, the Reviewer chip dropdown opens then instantly closes. Cause: the global click-closer (~5182) doesn't exempt the reviewer chip, so its own click re-closes the just-opened menu. Fix: add `&& !e.target.closest('.rev-chip')` to that handler's guard (matching how `.exp` / `.src-dd` / etc. are exempted).

6. **One share/export dropdown (consolidate):** Merge the standalone link dropdown (Embed/Attach) into the Output Export dropdown so there's a single share control. New menu, in order — heading **"Export"**: Copy selected · Export selected → file; heading **"Add to prompt"**: Embed in prompt · Attach as file. Remove "Cut selected" entirely (menu item ~2928/3083 + the cut wiring ~4348) and rename the old "Cut & export" heading to "Export". Build it once and reuse across Feed, History, Plans, Documents. (Items 7–10 depend on this.)

7. **Embed-in-prompt always available when something's selected:** Enable "Embed in prompt" whenever anything is selected — single or multiple, whole card or sub-block/line/section (gating becomes `enEmbed = !!kind`, ~3722; today it's part-only). This requires the embed action (eaEmbed / eaEmbedFeed, ~3733/3739) to also embed **whole** selections (full card/doc text), not just sub-blocks — wire that too, or Embed enables but does nothing on a whole-card select. Attach stays whole-only.

8. **Attach as file → real saved file:** When "Attach as file" runs, auto-name a file, **create it in Library → Documents** (reuse the addDocPaste pattern, ~3592), drop a path/link chip into the prompt pointing at that saved doc, then switch to Compose and **reveal** the attachment. (Distinct from "Export → file", which only creates the doc and stays put.)

9. **Retire the standalone link dropdown:** Once it's merged into Export (item 6), delete the separate link dropdown (`.ea-dd`) from the Team Feed strip (~2933) and the History strip (~3087); clean up the orphaned `embedAttachHTML` / `.ea-dd` references.

10. **Plans & Documents use the merged Export dropdown:** Replace the standalone link dropdown in the Plans footer (~4639) and Documents footer (~3572) with the merged Export dropdown (item 6), **left-aligned** and placed **before the reviewer chip**. Plans footer becomes [Export][reviewer chip] on the left, with the right group staying [Revise][Reject][Approve]. Documents footer: drop the leading spacer so Export sits left; Remove stays at the right.

11. **Delete agent button:** Add a "Delete agent" button to the **right** of "Retire agent" (~2289). Style it as a **new solid-red-fill + white (inverse) text** variant (Retire stays as-is — its red-text-on-cream is already the softer danger, so the two read distinctly). Delete completely wipes all records of the agent within reason — **configuration and transcripts** are sufficient — and removes it from the roster/graph plus any links. Because it's irreversible, gate it behind a confirm step (type-to-confirm or a "this can't be undone" dialog), like the existing Retire confirm flow (~4077).



## Inbox

> Rough human notes for an agent to incorporate later — one rough note per bullet. Empty by design. An agent files each into the right section per the **Inbox** steps in "How agents maintain this list" (file with a bold header, an ID for backlog sections, minimal clarity edits, disambiguate references), then clears it from this list.

- Remove the vertical separator/divider in Inbox card footer before Reply
- Reviewer-chip dropdown needs to have overlay above as do all the footer popover style menus.
- Gutter does not extend down extends. Also whole doc and last section select should not highlight past last line of text for any Library text stuff
- Change heading Export to "Copy & Export" 
- Remove Copy ghost icon buttons form History card trigger/header
- Integrate warning section in Inbox and include at least one  example agent with pending status that crossed context or turn limit. 
- With that, include a badge in the same warning color in the Inbox card header (similar to the "Connection" error badge in the Error section card) that indicates max turns with some clear label

## Scratch

> Rough human design ideas and notes not to be used or considered by any agent.

- Change stop button to use a filled red icon
- I want to work out how to build in more visual elements in Plans like charts, mockups and diagrams. I am thinking a few things. We could have a seperate tab in Liibarary or put these in the Assets tab, but we will need a way to comment them with visual markers etc. We might utilize what we have already in this tool: design\mockup-toolkit.js. If we put it in the Assets, we may want to structure the nav bar with headings, like something for stock imagges
- Plans should utilize mermaid diagrams in markdown.
- Need to add a permanent delete option along with retire that fully wipes the agent info from the system.
- Add some voice reading feature and, ideally, an option to change speed from normal up to 2-3x
- Need a string search feature for text fields.
- Need to turn compact into a multiselect with the 5 built in options.
- Need to track compaction history in context dropdown. Count and what type and when based on turns and time. Maybe put in the rewind/handoff list


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