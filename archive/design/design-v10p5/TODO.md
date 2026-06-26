# Dashboard TODO — ui-concept backlog

> **⚠ Backlog is reference-only; "Next up" is the one actionable section.** For the lettered backlog sections (A–D), agents must not implement anything, and must not treat any entry as confirmed, approved, or scoped, unless the human points them at a specific item. The exception is **Next up**: items there are approved for work, and being directed to that section is itself the signal to build them (see its instructions). This is otherwise a capture-and-triage doc.
>
> **What** — Backlog of changes for the dashboard mockup, `design/mockup.html` (design reference in `design/DESIGN.md`; design values in `design/tokens.css`). Focused on the UI concept. The backlog is grouped by implementation effort.
>
> **How it's used** — The human writes rough notes under **Inbox**; an agent files each into the right section. Work gets driven either by promoting an item into **Next up** (then directing an agent there to implement and remove it) or by cutting any item into a fresh prompt. Nothing in the backlog is a work order until that happens.

## How agents maintain this list

> **Verify first.** Before adding or reordering, open the latest mockup and confirm the item isn't already built. Drop anything already implemented; trim partly-built items to just the remaining gap.
>
> **Leave empty sections empty.** When a section has no items, leave it blank beneath its heading + intro line. Never add a placeholder, an "(empty)" marker, a status line, or a changelog note (e.g. "this batch was implemented and removed on …") — the blank space *is* the signal, and that history belongs in DEVLOG, not here.
>
> **Format.** Each item is a numbered list entry — a **bold header**, then a concise description; bold only the header. E.g. `1. **Role Dropdown:** …`.
>
> **Numbering.** The backlog sections are lettered A–D; items are a numbered list within each, so a backlog item's ID is its section letter + list number (e.g. B7). Cross-reference related items by that ID (e.g. "see B17"), and update those refs if you reorder. **Next up** items and **Inbox** notes stay unlettered — Next up items are transient (built, then deleted), so they don't get stable IDs.
>
> **Group by effort** under the headings below (A Quick wins · B Big picture · C Needs research · D Housekeeping & docs). Keep like with like, order related items next to each other, and merge overlapping ones. **Next up** is separate — the active implementation queue (priority order, mixed effort).
>
> **Next up — implementing items.** Items in the Next up section are approved for work; being directed to that section is itself the signal to build them. For each item:
> 1. **Build it in `design/mockup.html`** — that's where these changes land.
> 2. **Work from `design/DESIGN.md` and `design/tokens.css`.** DESIGN.md is the design reference (intent, patterns); tokens.css is the single source of truth for every design value. Read both first and let them inform the change — don't hardcode a value that belongs in tokens.css.
> 3. **Keep DESIGN.md in sync.** If a change alters design intent or adds/changes a pattern, update DESIGN.md to match, and confirm DESIGN.md and the mockup agree before you call the item done. If no DESIGN.md change is needed, confirm that explicitly.
> 4. **Remove the item** from the list once done (and log it in DEVLOG per the project rule).
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
4. **Plans Tab:** Add a Plans tab (in the Agent panel, or rename Prompts → "Editor" and host it there) that surfaces Claude Code's native plans — show multiple plans, expand each to review/edit in place, and support review/edit/approval; must support the new native ultraplan functionality.
5. **Voice Input:** Good microphone support via `/voice`, ideally with a small agent doing real-time correction.
6. **Slash Commands:** Support slash commands as well-grouped clusters with clear visual signals per command.
7. **Slash Shortcuts:** Decide which commands to surface directly in the dashboard UI (beyond full slash-command support, B6): /export, /doctor, /copy, /fast, /memory, /plan, /plugin, /rewind, /stats, /status, /tasks, /voice.
8. **Attachments & Clipboard:** Support attachments (probably as a clipboard); sort out managing attachments and clipboard cut/paste items — including pasting an image from the clipboard straight into a prompt.
9. **Assets Panel:** Add an assets panel to organize linked reference docs, images, etc.
10. **Drag-in Files:** Drag files from the VS Code explorer tree into the UI to load their paths for reference.
11. **Trigger: Interrupt / Inject:** Rename the send/link "Now" trigger to "Now: Interrupt" and add "Now: Inject" below it (reconsider wording — maybe just "Interrupt" / "Modify" or something else that is clear); Inject feeds a running agent (see B12).
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
7. **Inbox Attention Ramp:** Tune the reddish→copper request-type ramp, the per-card pending dot, and the Inbox-tab count badge for legibility and restraint. *(Moved from the old DESIGN.md "Open questions".)*
8. **Dense Link Graphs:** Once links render as directed edges (see B17), decide how to keep many overlapping links readable and how to distinguish links sharing the same configuration. *(Moved from the old DESIGN.md "Open questions".)*

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

> Active implementation queue — the one actionable section, in priority order, mixed effort. Approved for work; implement and remove each item per the **Next up** steps in "How agents maintain this list." Empty by design when nothing is queued.

## Inbox

> Rough human notes for an agent to incorporate later — one rough note per bullet. Empty by design. An agent files each into the right section per the **Inbox** steps in "How agents maintain this list" (file with a bold header, an ID for backlog sections, minimal clarity edits, disambiguate references), then clears it from this list.

- Make the Team Feed_>Inbox cards collapsible and utilize the checkbox that is already there but not functional to select the card. The collapsed card should show everything down to the title (eg "Run bash command" in the first card).
- Have the "Pending" badge click that currently opens the Inbox window also select/highlight the relevant card.
- Have the Link Agents drawer open right if that is easy to implement so that we can see all the cards in the Team Graph when it is open.

## Scratch

> Rough human design ideas and notes not to be used or considered by any agent.

- Need to organize the working ui concept better to separate out basic design system stuff (eg color palette) into its own html in a way that plays well with the DESIGN.md or just fully replaces it.
- We have too many different styled badges in terms of fills and and fonts. We need to refine these down to a hand full of badge styles we use consistently.
- I want to add hover cards for all the major components both because its helpful and it provides documentation through the design process.
- Need to change all references to "session" to "project" because that is really what will be reused in terms of a given agent config.
- Need to add ToDo functionality back into UI eventually.
- Find a way to to support highlighting words and terms in text and having it defined in context.

### Big picture
- We need to make sure we build both the ui and other elements in a modular enough way that we can easily modify and add features.
