## 1. Make the session name an editable field + title the CLI panel with it
The session name should be a real, editable field — not just a static label.
**Do:**
- Add a **Session** field as the **first field, above Role**, in **both** the Agent panel's
  **Details** tab (above the Role row at line ~301) and the **Create** tab (above the Role row at
  line ~330). Make it an editable text input, styled like the existing **Name** field.
- In the **CLI panel** (right pane, heading-strip at line ~404), **replace the "CLI" heading with
  the session name** — the panel is titled by the session rather than the generic "CLI".
- (The footer's `Session: 47m` stays as the duration readout.)

## 2. Make the agent Model selector editable (not locked)
In the Agent panel → **Details** tab, the Model field is labeled **"Model (locked)"** with a
`disabled`, dimmed `<select>` containing only `opus` (line ~307).
**Do:** make it a normal, editable dropdown — drop "(locked)" from the label, remove `disabled`
and the `opacity-60`, and offer the model options (mirror the Create tab's Model select at
line ~336: inherit / sonnet / opus / haiku).
**Why:** we can actually change an agent's model mid-run, so it shouldn't read as fixed.

## 3. Decide & clarify what the colored dots mean (two different sets)
There are two unrelated sets of colored dots that can be confused:
- **Title-bar dots** (line ~170): three static coral/gold/sage dots — currently decorative
  (macOS traffic-light style) with no meaning or legend.
- **Status dots** on the agent cards (lines ~198, ~210, ~219) and panel headers:
  green=working, grey=idle, amber=permission — these carry real run-state meaning.

**Do:** decide the purpose of the **title-bar dots** — either give them a real meaning (with a
legend/tooltip), repurpose them, or remove them so they're not mistaken for status. Confirm and
keep the **card status dots** as the liveness indicator.

## 4. Move the Activity Log into the Team Feed as a final "Log" tab
Today the **Activity Log** is its own section in the left pane (lines ~272–290) with its own agent
filter row. Fold it into the **Team Feed** so the feed's tabs become:
**Outgoing | Incoming | Scratch | Log**.
**Do:** remove the standalone Activity Log section and add its content as the last Team Feed tab
("Log"). Its per-agent filtering is now handled by the Team Feed's shared toggle set (item #5).

## 5. Team Feed — one shared agent-toggle set across all tabs
The Team Feed (lines ~247–268) needs per-agent filtering, but as a **single shared set** of
multi-select agent toggles (the chip style, `.atog-row`) that **persists across all its tabs**
(Outgoing / Incoming / Scratch / Log) — i.e. one selection filters every tab, not a separate set
per tab.
**Do:** place this toggle set in a **delineated sub-header** — a visually distinct strip directly
below the Team Feed tab bar that stays fixed while you switch tabs, making it clear the selection
persists across tabs. Include the "Select all" control (item #7).

## 6. Prompts — shared Source + Target across all three tabs
The Prompts panel has three tabs (Compose / Library / History). Both the **Source** (single-select,
`.atog-grouped`) and **Target** (multi-select, `.atog-row`) groups should be **shared across all
three tabs** and persist when switching between them.
**Do:**
- Keep the current order: **Source on top, Target on bottom** (no swap).
- Put both groups in a **delineated sub-header** (same persistent-strip treatment as item #5) so
  it's clear they apply across Compose, Library, and History — not re-picked per tab.
- Today only Compose has these (Source ~427–433, Target ~436–440); Library (~446) and History
  (~451, currently just a single-select view filter) get the shared groups too.

## 7. Add a "Select all" control to the multi-select agent toggles
Applies to every **multi-select** agent-toggle group: the **Team Feed** shared set (item #5) and
the **Prompts → Target** group (item #6).
**Do:** add a "Select all" / toggle-all affordance to each.
**Exclude** the single-select groups — **Prompts → Source** and the History view filter — where
picking one is the point.

## 8. Show that selecting an agent in the graph drives the Agent panel + CLI
The Team Graph cards (lines ~196–223) are clickable, and the Agent panel (middle) and CLI panel
(right, header at line ~404) already show one agent — but nothing visually communicates that they
are **linked**: click a card → that agent loads in the Agent panel (Details/Requests) **and** the
CLI panel.
**Do:** add a clear "selected" state to one graph card (researcher-01-sandy, which the panels
already reflect) and make the selected card ↔ Agent panel ↔ CLI visibly read as the same agent
(matching name/color highlight). Demonstrate this connection in the static wireframe.

## 9. Restore the "Link Agents" drawer
The **"Link Agents"** button in the Team Graph header (line ~191) opens the **"Link Config"**
drawer (`#link-drawer`, lines ~227–241), which configures a link's Trigger / Payload / End-After.
This drawer was lost in the current working copy.
**Do:** add it back and confirm the `toggleDrawer()` open/close still works.

## 10. Requests → Decisions card — stack the options vertically
In the Agent panel's **Requests** tab, the **Decisions** card (lines ~377–388) lays its options out
as a **horizontal** segmented row (`.atog-grouped` with `.atog-seg` buttons), which crowds the
option text.
**Do:** change the options to a **vertical** list — full-width stacked option rows — so each option
has room for longer text. Keep single-select behavior (`pickSeg`) and the Submit / Reply actions. This might work best as sub-cards.