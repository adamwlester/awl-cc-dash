# UI Concept — Change Instructions

## Orientation (read first)
You're editing the agent dashboard's UI mockup — a single static HTML/Tailwind wireframe in the warm "Happy Hues 17" palette (cream / navy / pink). No backend: make only the visual/structural changes listed below.

## Most authoritative source — the current mockup
Review the latest UI concept mockup: `agent-dashboard/design/ui-concept-v5p9.html`. The older versions are in `archive\agent-dashboard`. This HTML is the most up-to-date ground truth;
wherever it conflicts with older docs, the mockup wins.

## Chronology / "what changed when"
Start with `DEVLOG.md` (repo root) — dated, distilled entries tracking the design's
evolution (v4 → current), more reliable than reconstructing from raw transcripts. Then
use the session exports in `cc-exports/` for depth; note their timestamps and weight by
recency.

---

## Prompts panel
- **Compose Target:** add **Scratch** as the *first* Target chip (posts to the scratchpad).
  _(Future: richer select/comment-on-posts flow — out of scope now.)_
- **Compose action row** — replace the current `Send · Clear · Queue` row with one row,
  left → right:
  1. **Clean** (outline) — leads the row; runs an AI cleanup pass on the prompt text.
  2. **Timing selector** — a `.seg-ctrl`: **Now · Next · Queue** (single-select, **Now**
     active by default, no "Hold"). Same vocabulary as the Link Config Trigger.
  3. **Send** (primary) — label mirrors the timing choice: **Send Now / Send Next /
     Send to Queue**. One obvious primary action.
  4. **Right-grouped icon buttons** — **copy** + **trash** (these replace the old Clear).
- **Share this action row across the Compose and Library tabs** (History keeps its
  per-item Reuse). Treat it like the shared Target/Source sub-header.

## Team Feed
- **Scratch tab:** every entry shows **agent ID + HH:MM:SS timestamp**. Rewrite the
  sample into a fuller, multi-agent example (several scratchpad posts, not one block).
- **Log tab:** lengthen the sample (more entries); use **HH:MM:SS** to match Scratch.
- **Filter chips:** add a **User** chip at the front of the Team Feed filter group,
  exactly like the User option in the Prompts **Source** group.

## Link Config drawer
- **Direction toggle:** make the arrow between the two agents a 3-state click toggle —
  **A→B**, **B→A**, **A↔B (both)**.
- **Agent identity:** show each agent with the **two-row name** (role over "NN name")
  used elsewhere (Agent panel, chips) — not the single-line "researcher-01".
- **Trigger:** rename **Imm → Now** and **Held → Hold** (Now · Next · Queue · Hold).
- **Payload:** **Message · Transcript · Manual** (replaces Free/Context/Manual).
- **Remove the "1-Shot" button.**
- **End After** — rebuild as multi-select with paired inputs:
  - Remove **None**.
  - **Turns / Time / Tokens** become **multi-select toggles** (any combination).
  - Layout: **three equal-width columns**, each = toggle button on top, text input
    directly below (button + input share the column width).
  - Each input is **greyed/disabled until its toggle is on**; turning the toggle on
    enables it.
  - **No toggles on = no limit** (this replaces "None"). **Multiple on = ends at the
    first limit reached.**
  - Placeholders: Turns **50**, Time **30m**, Tokens **100k**.

## Agent panel
- **Request subheadings:** move the per-section count **into the leading dot** (like the
  agent cards) instead of trailing the label. Fix number legibility — white-on-gold is
  hard to read, so use **navy text on the gold fill** (and apply the same fix to the
  agent-card pending badges).
- **Reply on every subcard:** add a **Reply** action to all three subcard types
  (Permissions, Approvals, Decisions) for a custom response to the agent. **Open design
  decision — pick whichever reads better:**
  - **(a)** a **shared Reply field** in the **Request tab footer** (segregated by a divider /
    distinct surface) with an embedded **send** button, enabled when Reply is clicked on any card; or
  - **(b)** a **per-card drop-down reply box** under the clicked card, each with its own embedded send button.
- **Rewind (was Rollback):** rename to **Rewind**, move it out of the footer to **just
  under Context** in Details, as an **accordion** that expands a **scrollable list of
  messages sent to the model**, each selectable as a rewind point.
- **Per-tab footers (stop sharing one footer):**
  - **Details:** **Handoff** (replaces Clone) + **Retire**.
  - **Create:** **Create · Reset · Cancel** (Cancel = danger red).
  - **Requests:** just the shared **Reply field** described above.

## Scrollbars
- Recolor the scrollbars to match the palette, app-wide.

---

## Output
Provide a new version of the HTML as `agent-dashboard/design/ui-concept-v6p1.html`. Double check that all existing functionality that should have been preserved is. Ensure any changes you make align with the aesthetic and overall existing design as well as the objectives described.

