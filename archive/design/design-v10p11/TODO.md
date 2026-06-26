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

```
CUMULATIVE CHANGE LIST — design/mockup.html (+ DESIGN.md / tokens.css)
Status: NOTHING IMPLEMENTED YET.

═══ A. AGENT CARD — square redesign [TODO #5] ═══
A1 (5a) FAST mode: drop the override-greying idea entirely — mode/effort/think
        chips always show their real values. SEPARATE rule: the FAST control
        stays DISABLED whenever Opus is NOT the selected model (matches the
        Opus-only bolt). No assumption that FAST overrides effort/thinking.
A2 (5b) Subagent badges (.sbadge): make RECTANGULAR; add a run-state status dot
        inline with the number for all 3 states (pending/active/idle); number in
        standard navy ink (--foreground), NOT agent color. The number is an ID,
        not a count → if that reads ambiguous, label "s1"/"s2". Dot placement:
        leading (my lean — unconfirmed).
A3 (5c) Run strip: leave the barber-pole as-is (undecided).
A4 (5d) Resolved by A2 — the pale-numeral contrast issue was the agent-colored
        digits; standard navy ink fixes it.
A5 (5e) Badges stay clickable-but-unwired (undecided).
A6 demo  Relocate the example subagent badges OFF green-family agents — current
        offenders: emerald (card ~L2309) + teal (card ~L2550); amber (~L2381) &
        magenta (~L2525) already fine. Give demo subagents a MIX of all 3 run-
        states, each represented, consistent with each parent agent's own status.

═══ B. SUBAGENT-BADGE FOOTER FRAMING [new #7] (exploratory) ═══
B1  In the .node-subs / .sbadges band the hard --shadow-sm offset reads awkward.
    Soften/drop the shadow, rework the border, and/or adjust band spacing/
    alignment so the group sits cleanly. Agent's call on the exact fix. Applies
    to the NEW rectangular badge from A2 — do together (same element).

═══ C. MESSAGES CONTENT FRAMING [held] ═══
C1  Expanded Messages card: dissolve the inner .mrail-wrap frame (drop its own
    border / radius / 8px top-margin) so the rail+rows fill the card content
    surface. KEEP .fcard-body padding so the text keeps its breathing room.
    Messages ONLY — Scratch/Log/Inbox have no inner panel; leave them alone.

═══ D. JUMP PILLS ON REAL SCROLLERS [new #1, extends the jump-pill item] ═══
D1  Wire pills to the real scrolling elements; fix the mismatched JUMP_SELECTOR:
      • Plans + Documents editor body (real scroller, e.g. .md), Assets grid,
        Feedback list.
      • Compose editor: .compose-rich is contenteditable & deliberately excluded
        (injecting a child corrupts text) → position its pill via an OUTER
        overlay/wrapper, never inside the field.
      • All Team Feed bodies (Messages/Scratch/Log/Inbox): give each a capped
        max-height + vertical scroll FIRST, then attach pills. Pills show only on
        overflow + when scrolled away from the edge.
    NOTE: .doc-view/.asset-grid/.fb-list are actually present today — reconcile
    the true live scroller at build time; intent stands.

═══ E. BIGGER EXPAND HIT TARGET — flush square [new #2] ═══
E1  On select-AND-expand cards, make the chevron button (.fcard-chevbtn) a SQUARE
    = full header height (width = height), pinned flush to the header top/bottom/
    right with ZERO padding; chevron centered. Header elsewhere still selects.
    Targets: Messages + Scratch + Log + Inbox + History (all selectable-and-
    expandable feed/history cards — Messages confirmed included).

═══ F. EDITOR-RAIL HORIZONTAL DIVIDERS [new #3] ═══
F1  Re-add horizontal dividers in the Plans + Documents editor RAIL only (not
    across the text), color = navy --border, so it's easy to eyeball where to
    click-to-select. Keep --rule in tokens (it now backs inline code-chip + badge
    outlines — NOT deprecated); just don't use it for these dividers.

═══ G. TEAM FEED ACTION STRIP [new #4] ═══
G1  Delete the standalone Copy button (Output Export's Copy-selected / Copy-whole-
    feed replaces it).
G2  Fix/rewire the select-deselect (select-all) button — currently broken AND
    Messages-only/hidden elsewhere; generalize it to every feed tab.
G3  Resulting strip order (left→right; "|" = flex spacer / right group):
      Messages:     select/deselect · Output Export · Summarize | link-dd · Stop
      Scratch/Log:  select/deselect · Output Export · Summarize | link-dd
      Inbox:        select/deselect · Output Export | link-dd
    Summarize = Messages/Scratch/Log only; Stop = Messages only; Inbox keeps its
    per-card Approve/Deny. "link-dd" = the new control in H.

═══ H. LINK-ICON DROPDOWN replaces Embed/Attach chips [new #5] ═══
H1  Replace every Embed/Attach toggle chip (Library Plans/Documents/Assets
    footers + the Team Feed footer) with a link-icon-ONLY dropdown modeled on
    Output Export: menu items = the actions, clearer names ("Embed in prompt",
    "Attach as file") + helper text. Selection-gated (offers only the mode the
    current selection allows). Kills the bug where clicking the Embed/Attach
    label fired attach instead of just choosing the mode (no toggle labels left).

═══ I. HISTORY CARDS → feed model [new #6] ═══
I1  Selection: drop the checkbox → click header to select (light-teal select-to-
    act); separate chevron expands (gets E1's flush square).
I2  Header: move EDIT out of the footer into a ghost icon button in the card
    header — after the attach tags, before the timestamp.
I3  Footer (left→right): select/deselect · Output Export | link-dd · Retry · Stop.
    Removed: Copy (Output Export covers it) & Edit (now in header). Add Retry
    before Stop. Wire select/deselect + Output Export for the History tab too.

═══ J. DESIGN.md doc patches [held review + updated by I] ═══
J1  L158 & L160: item-18 nav rows now show per-type FILE ICONS (not thumbnails)
    and NO trash icon — fix BOTH lines.
J2  L62: items #9/#11 checkbox/footer wording is stale — and now UPDATED by I1:
    History no longer keeps a header checkbox (it's click-to-select), so NO tab
    keeps a checkbox; reflect the Output Export menu too.
J3  L141 (optional): note the new "Attachments" label heading in Compose (#16).
J4  Re-sync any lines touched by C–I (action strips, link dropdown, History
    model, Messages framing) once those land.

═══ K. DEAD CSS [held] ═══
K1  Remove the orphaned .assetnav-thumb rules (unused after item-18's
    fileTypeIcon()). Keep --rule in tokens — NOT dead (see F1).

═══ L. MIC → PER-EDITOR GHOST BUTTON [new] ═══
L1  Move the dictation mic OUT of the window footer (remove the universal
    #footer-mic from .footbar + toggleMic's universal wiring) and place one in
    EACH Editor header — Compose, Plans, Documents — as a ghost button (match the
    inline .ghost-ic buttons: 22×20, svg 14px), inserted right after the "Editor"
    heading label (left-adjacent, before the flex-1 spacer — separate from the
    right-side Copy/Edit/Clear cluster). Impl: add it to editHeadHTML() (covers
    BOTH Plans + Documents) and the Compose Editor header (~L2991).
L2  State colors: default = the normal ghost icon (active line) color; ACTIVE
    (recording) = red, var(--danger) — matching the current .mic-btn.rec fill.
    (Pink was the alternative; red chosen.)
L3  Keep the existing enabled/disabled behavior, but bind each mic DIRECTLY to its
    own text field instead of the one universal control: Compose → #compose-field;
    each Plan editor; each Document editor (doc-<name>-edit). Enabled when its
    field is available for input, disabled otherwise (e.g. Docs/Plans in rendered/
    view mode). Reuse/adapt toggleMic() per-instance.
    NOTE: the Compose paperclip Attach button (#compose-attach) reuses .mic-btn
    styling but is NOT the mic — leave it untouched; only the dictation control moves.

VERIFY (CLAUDE.md): drive the rendered UI headless — resize panels narrow+wide,
click through every touched control + both card states — then ONE headed parity pass.
```



## Inbox

> Rough human notes for an agent to incorporate later — one rough note per bullet. Empty by design. An agent files each into the right section per the **Inbox** steps in "How agents maintain this list" (file with a bold header, an ID for backlog sections, minimal clarity edits, disambiguate references), then clears it from this list.



## Scratch

> Rough human design ideas and notes not to be used or considered by any agent.

- Need to change all references to "session" to "project" because that is really what will be reused in terms of a given agent config.
- Change stop button to use a filled red icon
- I want to work out how to build in more visual elements in Plans like charts, mockups and diagrams. I am thinking a few things. We could have a seperate tab in Liibarary or put these in the Assets tab, but we will need a way to comment them with visual markers etc. We might utilize what we have already in this tool: design\mockup-toolkit.js. If we put it in the Assets, we may want to structure the nav bar with headings, like something for stock imagges
- Plans should utilize mermaid diagrams in markdown.
- Need to add a permanent delete option along with retire that fully wipes the agent info from the system.
- Add are voice reading feature and, ideally, an option to change speed from normal up to 2-3x
- Need a string search feature for text fields.
- Need to turn compact into a multi

COMPACTION / CONTEXT-EDITING STRATEGIES (API level, composable in context_management.edits)

Need to 
Summarize And Replace
Label: SUMMARIZE
Type: compact_20260112
Summarizes everything before a boundary into one block, drops the rest. Age-graded: No (hard boundary). Params: trigger (default 150K tokens, min 50K), instructions (replaces summary prompt entirely), pause_after_compaction (insert preserved recent messages before continuing).


Clear Old Tool Results
Label: CLEAR TOOLS
Type: clear_tool_uses_20250919
Drops old tool results while keeping the record that the call happened. Age-graded: Yes (keeps N most recent). Params: trigger, keep, clear_at_least, exclude_tools.


Clear Old Thinking Blocks
Label: CLEAR THINKING
Type: clear_thinking_20251015
Drops old extended-thinking blocks, optionally preserving recent ones. Age-graded: Yes (keeps N most recent). Note: must be the first entry in the edits array if used alongside tool clearing.


External Memory Tool
Label: MEMORY
Type: memory_20250818
Writes durable notes to external storage instead of holding everything in-context. Age-graded: N/A (external).


NOTES
These compose; common pattern is CLEAR TOOLS (higher trigger) plus SUMMARIZE so they split the work.
Summarization always uses the request's own model; no cheaper-model option.
Claude Code CLI surface only exposes coarse levers: /compact [focus], CLAUDE.md "Compact Instructions" section, CLAUDE_AUTOCOMPACT_PCT_OVERRIDE (lower-only, capped ~0.83), PreCompact hook.


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