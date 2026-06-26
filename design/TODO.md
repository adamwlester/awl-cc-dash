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

1. **Output Export:** Extend the existing per-card Copy into a way to select/cut/export larger spans of output.
2. **Jump to Feed Ends:** Add quick jump-to-start / jump-to-end controls on each feed.

## B — Big picture

> Larger features needing real backend/runtime.

1. **Per-Agent MCP & Plugins:** Set MCP servers and plugins per agent in the UI, not just globally.
2. **Custom Permissions:** Spin up an agent with custom permissions that would normally come from user `.claude/settings.json`.
3. **Load Past Agents:** Load past agents/models by name, ID, or via file explorer.
4. **Plans Tab:** Add a Plans tab (in the Agent panel, or rename Prompts → "Editor" and host it there) that surfaces Claude Code's native plans — show multiple plans, expand each to review/edit in place, and support review/edit/approval.
5. **Voice Input:** Good microphone support via `/voice`, ideally with a small agent doing real-time correction.
6. **Slash Commands:** Support slash commands as well-grouped clusters with clear visual signals per command.
7. **Slash Shortcuts:** Decide which commands to surface directly in the dashboard UI (beyond full slash-command support, B6): /export, /doctor, /copy, /fast, /memory, /plan, /plugin, /rewind, /stats, /status, /tasks, /voice.
8. **Attachments & Clipboard:** Support attachments (probably as a clipboard); sort out managing attachments and clipboard cut/paste items — including pasting an image from the clipboard straight into a prompt.
9. **Assets Panel:** Add an assets panel to organize linked reference docs, images, etc.
10. **Drag-in Files:** Drag files from the VS Code explorer tree into the UI to load their paths for reference.
11. **Trigger: Interrupt / Inject:** Rename the send/link "Now" trigger to "Now: Interrupt" and add "Now: Inject" below it (reconsider wording — maybe just "Interrupt" / "Modify" or something else that is clear); Inject feeds a running agent (see B12).
12. **Interactive Comms:** Incorporate interactive, dynamic agent↔me communication via a shared "dynamic doc" the agent periodically references during each run.
13. **Reviewer Link:** Build a one-button reviewer setup on top of existing linking — one agent reviews another's work. The Plans **Review chip** (single-agent reviewer select) is the control groundwork; the **Review/Inbox formalization** remains deferred — the single-reviewer-agent model, how agent verdicts resolve, and how the human gate relates to agent review.
14. **Queue Awareness:** For >2 linked agents, share in message front matter that another agent's message is queued, so an agent can decide whether to wait.
15. **Context Porting:** Select and port context between agents by blocks of prompts and replies.
16. **Subagent Forking:** Forking is covered by Handoff; still need subagent creation/management in the UI and a decision on how agents spawn subagents.
17. **Link Edges:** Add link-related UI to the Team Graph (e.g. directed graph edges) so you can see how agents are linked (replaces the old hand-drawn link lines, since removed).
18. **Scratch Post Actions:** Allow editing/commenting on individual Scratch posts (currently post-in / read-out only).
19. **Lifecycle Wind-Down:** Add an explicit end-of-life signal / graceful wind-down when an agent hits its auto-stop limits (the limits already exist).
20. **Alert Escalation & Timeouts:** Escalate alerts amber → red if unaddressed, with timeouts on alerts and on working agents to catch hanging sessions.
21. **Save Response Summary:** Option to save summary data/log of a response.
22. **Global Config Surface:** Expose global config (active plugins, MCP servers) through the UI.
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

1. **Turns Breakdown Dropdown:** Build the Agent panel's Turns dropdown per the snippet `design/ui-snippets/turns-dropdown.html` — port it into the mockup's Turns bar (Context-style `.ctx-trigger` accordion, by-tool breakdown). Demo data only.
2. **Response Settings Popover:** Rework the Compose-footer Response popover (`#fmt-menu`) per the snippet `design/ui-snippets/response-popover.html` — segmented/toggle button groups, graded options, STYLE/BEHAVIOR split, and the Pace axis.



## Inbox

> Rough human notes for an agent to incorporate later — one rough note per bullet. Empty by design. An agent files each into the right section per the **Inbox** steps in "How agents maintain this list" (file with a bold header, an ID for backlog sections, minimal clarity edits, disambiguate references), then clears it from this list.

- Remove Time from Link config "End after" and make sure it is not referenced anywhere.
- The new left rail in the Messages should use the same styling as the rails in Library in terms of the tan box with numbers and small colored strips. It can be narrower because it does not have tags. If you think it makes more sense to not number items because the filters will change the number then no number, but same basic idea. These should be contained within the sub-cards or made to seem more a part of them. Consider if the different blocks within the Messages cards should be this sort of subpannel look or something that works better to both deliniate different blocks but make them feel more vertically contiguous and also make them more ammenable to using a similar styling to the Library contents. 
- Those same card blocks in Messages need to allow for multi select within a card.
- I want to have little hover values for how wide or tall a given pannel is when the main horz or vert area borders are dragged. This values shoudl hover with the mouse and update as it moves and show the left/top panel then right/bottom values in that respective order.
- Every vertically scrollable window 
- We need the agent settings summary text in the agent cards to be better. Needs to remain space efficient but readable. Ideally with clear inline headings (eg "model: opus 4.8"). Need to consider what other info those cards should contain.
- I want to remove the checkboxes from the cards in Team Feed -> Scratch/Log/Inbox and have them work the same as the cards in Messages in terms of how they are selected and opened/closed as well as how sub-cards (if relevant) are selected.

## Scratch

> Rough human design ideas and notes not to be used or considered by any agent.

- Need to change all references to "session" to "project" because that is really what will be reused in terms of a given agent config.
- Need to consider if we should have some indication of agents lifespan in terms of when it was created
- The agent cards and possibly pannel also need a dynamic status indicator for progress on a given run


- Assuming it is straight forward to implement, for the Library->Plans. The Editor heading should be aligned with the editor box not the nav box. The nav box should extend to the top of the section like is done in the Documents tab.
- I want to fix the UX of the left rail controls in the Library->Plans and Documents contents. I want the little far left color strips to be about 2x thicker. I want the rail to extend the full hight of the visible window. I want all the associated text to highlight in that cream color during hover, not just the single line (eg, hovering over title should highlight the full rendered contents). I also want the little rail blocks to correctly resize to cover the full height of the text when lines are wrapped so their at not white spaces between them.

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