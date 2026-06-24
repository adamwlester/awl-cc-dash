# Dashboard TODO — ui-concept backlog

> **⚠ Reference only — do not work from this unless explicitly directed.** Agents must not implement anything here, and must not treat any entry as confirmed, approved, or scoped, unless the human points them at a specific item. This is a capture-and-triage doc. The only signal to act is the human handing you a specific item (typically by pasting it into a fresh prompt).
>
> **What** — Backlog of changes for the dashboard mockup, `design/ui-concept-v9p14.html` (the highest version number is the live one). Focused on the UI concept. Grouped by implementation effort.
>
> **How it's used** — The human writes rough notes under **Loose notes**; an agent files each into the right section. The human then drives work by cutting an item (usually from **A — Next up**) into a prompt. Nothing here is a work order until that happens.

## How agents maintain this list

> **Verify first.** Before adding or reordering, open the latest mockup and confirm the item isn't already built. Drop anything already implemented; trim partly-built items to just the remaining gap.
>
> **Format.** Each item is a numbered list entry — a **bold header**, then a concise description; bold only the header. E.g. `1. **Role Dropdown:** …`.
>
> **Numbering.** Sections are lettered A–E; items are a numbered list within each, so an item's ID is its section letter + list number (e.g. C7). Cross-reference related items by that ID (e.g. "see C17"), and update those refs if you reorder. Loose notes stay unnumbered.
>
> **Group by effort** under the headings below (A Next up · B Quick wins · C Big picture · D Needs research · E Housekeeping & docs). A is the working queue (priority, mixed effort); the rest stay grouped by effort. Keep like with like, order related items next to each other, and merge overlapping ones.
>
> **Loose notes.** The human drops rough notes under "Loose notes" at the bottom. When asked to incorporate them, fold each into the **appropriate section** — its best fit by topic/effort, or whatever section the human specifies if they name one — with an ID + header, then delete it from Loose notes so that bucket stays empty for next time.

## A — Next up

> Current work queue — priority order, mixed effort.

1. **Plan Footer Grouping:** The current Plan-card button grouping isn't working. Move Share and Review up into the upper strip, and extend that strip under the nav pane too so everything fits. Keep the three already there (Copy, Edit, Comment) left-aligned to the larger card surface, with the two being moved (Share, Review) right-aligned.
2. **Nav Card Selection:** Make the nav cards selectable like the other cards — a teal fill that persists until you deselect or close the associated comment popout. Selecting a card should also highlight the text for its associated tag.

## B — Quick wins

> Small changes to the current mockup.

1. **Output Export:** Extend the existing per-card Copy into a way to select/cut/export larger spans of output.
2. **Jump to Feed Ends:** Add quick jump-to-start / jump-to-end controls on each feed.

## C — Big picture

> Larger features needing real backend/runtime.

1. **Per-Agent MCP & Plugins:** Set MCP servers and plugins per agent in the UI, not just globally.
2. **Custom Permissions:** Spin up an agent with custom permissions that would normally come from user `.claude/settings.json`.
3. **Load Past Agents:** Load past agents/models by name, ID, or via file explorer.
4. **Plans Tab:** Add a Plans tab (in the Agent panel, or rename Prompts → "Editor" and host it there) that surfaces Claude Code's native plans — show multiple plans, expand each to review/edit in place, and support review/edit/approval; must support the new native ultraplan functionality.
5. **Voice Input:** Good microphone support via `/voice`, ideally with a small agent doing real-time correction.
6. **Slash Commands:** Support slash commands as well-grouped clusters with clear visual signals per command.
7. **Slash Shortcuts:** Decide which commands to surface directly in the dashboard UI (beyond full slash-command support, C6): /export, /doctor, /copy, /fast, /memory, /plan, /plugin, /rewind, /stats, /status, /tasks, /voice.
8. **Attachments & Clipboard:** Support attachments (probably as a clipboard); sort out managing attachments and clipboard cut/paste items.
9. **Assets Panel:** Add an assets panel to organize linked reference docs, images, etc.
10. **Drag-in Files:** Drag files from the VS Code explorer tree into the UI to load their paths for reference.
11. **Trigger: Interrupt / Inject:** Rename the send/link "Now" trigger to "Now: Interrupt" and add "Now: Inject" below it (reconsider wording — maybe just "Interrupt" / "Modify" or something else that is clear); Inject feeds a running agent (see C12).
12. **Interactive Comms:** Incorporate interactive, dynamic agent↔me communication via a shared "dynamic doc" the agent periodically references during each run.
13. **Reviewer Link:** Build a one-button reviewer setup on top of existing linking — one agent reviews another's work.
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

## D — Needs research / decisions

> Open questions to resolve before they become build items.

1. **Tasks:** Understand tasks, and decide whether tasks should be part of the workflow.
2. **Docs-on-Demand:** Dynamically give agents access to relevant, up-to-date documentation.
3. **Systems-Work Docs:** Ensure agents doing systems-level work always have up-to-date docs in context.
4. **AI-Touched Tracking:** Track what AI has touched with a local file per directory (e.g. `index.md`).
5. **Asset Sourcing:** Check that skills and other special CC assets are pulled from the ideal source.

## E — Housekeeping & docs

> Maintenance, config, and documentation chores.

1. **npm Binary:** Update npm to the native binary.
2. **PowerShell Strings:** Find a better set of strings for PowerShell permissions.
3. **Dashboard README:** Update the Dashboard README.
4. **CLAUDE.md Trim:** Optimize my CLAUDE.md files — index other files instead of a full context dump.
5. **Doc Date/ID Tagging:** Better tagging of dates and IDs for document creation and editing.
6. **System Details Doc:** Document and maintain my system details — OS, Claude install, plugins, etc.
7. **Config SOPs:** Write SOPs for all major system-config activities (agent, hook, skills setup).

## Loose notes

> Loose human notes for an agent to incorporate later. Empty by design — add rough notes here; an agent folds each into the **appropriate section** above (best fit by topic/effort) unless the human names a target section, in which case use that. File with an ID + inline header, then clear it from this list.

## Scratch

> Rough human design ideas and notes not to be used or considered by any agent.

- Need to organize the workign ui concept better.
- We have too many different styled badges in terms of fills and and fonts. We need to refine these down to a hand full of badge styles we use consistently.
- I want to add hover cards for all the major components both because its helpful and it provides documentation through the design process.
- Need to change all references to "session" to "project" because that is really what will be reused in terms of a given agent config.
- Need to add ToDo functionality back into UI.