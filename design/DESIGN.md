# AWL Multi-Agent Dashboard — Design Reference

A single-window desktop app for running and coordinating many Claude Code agents at once.
This document is the ground-truth reference for the dashboard's **UI/UX intent** — what each
part is *for* and *why it behaves the way it does*.

> **About this doc — read once.**
> - **The mockup owns the visuals.** The current wireframe,
>   [ui-concept-v9p14.html](ui-concept-v9p14.html), is the authority on exact layout,
>   sizing, and styling. It is a **[neobrutalism.dev](https://www.neobrutalism.dev) refactor** of the
>   earlier v7p3 mockup — token names + utility classes mirror that library's Tailwind theme so the
>   static mockup ports ~1:1 to a React/shadcn build. This README avoids pixels/hexes/labels except in
>   [Design system](#design-system), which is the single place specifics live.
> - **This doc owns the intent**, and intent runs slightly *ahead* of the mockup: where a change
>   has been agreed but not yet drawn (directed link edges), it's described here as the design. Such
>   spots are flagged *(planned)*.
> - **Chronology lives in [`../DEVLOG.md`](../DEVLOG.md);** the fuller original vision (parts now
>   superseded) lives in [`../archive/agent-dashboard/ui-plan-v2.md`](../archive/agent-dashboard/ui-plan-v2.md).
> - Inferred intent is flagged *(intent: …)*. Undecided items are under [Open questions](#open-questions);
>   decided-but-deferred ideas are under [Future directions](#future-directions).

---

## Purpose & vision

Running several Claude Code sessions in tmux means constant tab-switching, copy-pasting prompts
between terminals, and no real visibility into what each agent is doing or how they relate. The
dashboard replaces that with **one window** where you can see every agent, its state and context,
the messages flowing between agents, and compose/send prompts — **without ever touching the raw
CLI.**

The thing that makes this more than "several terminals in a grid" is **context-sharing between
agents** — links, a shared scratchpad, and agent-to-agent conversation. That is the defining
feature; everything else exists to support it.

Guiding principles that shape the whole UI:

- **Everything visible, no popups.** The 3-pane layout keeps all state on screen. The only
  overlay is the Link Config drawer, which is anchored, not a floating dialog. The other non-pane
  surface, [Settings](#settings-step-into-view), is a full-window **step-into view** (from the
  title-bar gear) that replaces the body in place and returns to the 3-pane on exit — also not a
  floating dialog.
- **Compose-first.** Typing into a raw CLI is the thing this tool is meant to replace, so the
  prompt-composing surface is always present and is the primary action.
- **One identity per agent, everywhere.** Each agent gets a color + icon used consistently across
  the graph, feeds, log, history, and chips, so you can track an agent at a glance — see
  [Agent identity & naming](#agent-identity--naming).
- **Route control through the GUI, including approvals.** Anything you'd normally approve in the
  CLI — permission prompts especially — surfaces in the dashboard so you never drop back to a
  terminal to unblock an agent. (This is why approvals get a first-class home; see
  [the Inbox tab](#the-inbox-tab).)
- **Bridge is the backbone; the dashboard is the skin.** Agent lifecycle/send/read already exist
  below the UI; the dashboard is a control layer on top.

> **Out of scope (deliberately):** per-agent cost/spend tracking, a diff viewer, a terminal-UI
> (TUI) version, keyboard-only (F-key) control, and a dedicated live-CLI/terminal-stream
> pane (the old upper-right panel, removed in the v7 cleanup — the Team Feed's Messages tab now
> covers what each agent is doing) — all considered and explicitly dropped.

## What it physically is

A desktop application (Electron + React) presenting one window. Each agent is a real Claude Code
session running in tmux on WSL2, driven by a local Python (FastAPI) sidecar through the tmux
bridge that already handles create/send/read/status; tmux also serves as the crash-recovery safety
net. That's the whole stack the UI sits on — deeper implementation notes live in
[`../DEVLOG.md`](../DEVLOG.md); this README stays focused on UX.

---

## Layout — the three-column model

A title bar on top, a status footer on the bottom, and three vertical columns between them. The
**Agent** column (left) is the narrow one; **Team Graph + Prompts** (middle) and **Team Feed**
(right) are the wide ones. Columns and their stacked sections are separated by draggable splitters.
The whole frame is **full-bleed** — the header, the three-pane body, and the footer meet flush and
run edge-to-edge, with no outer margin.

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│ Title bar — app name · version · agent count │ clock · WSL2 · tmux · status     │
├────────────────────┬────────────────────────────┬───────────────────────────────┤
│ LEFT (narrow)      │ MIDDLE (wide)              │ RIGHT (wide)                  │
│                    │                            │                               │
│ Agent              │ Team Graph                 │ Team Feed                     │
│ ├ Details          │   (agent cards)            │ ├ Messages                    │
│ └ Create           │   + Link Config drawer     │ ├ Scratch                     │
│                    │   ──────────────────────   │ ├ Log                         │
│                    │ Prompts                    │ └ Inbox                       │
│                    │ ├ Compose ├ Library        │   + shared agent filter       │
│                    │ └ History                  │     (persists across tabs)    │
│                    │   + Source dropdown        │   + Messages footer           │
│                    │     over Target            │                               │
│                    │   + action row (mic …)     │                               │
├────────────────────┴────────────────────────────┴───────────────────────────────┤
│ Footer — agents/subagents/linked counts · active/idle/pending · session age     │
└─────────────────────────────────────────────────────────────────────────────────┘
```

> *(Layout note — the diagram shows the v7/v9p4-era arrangement. The mockup has since evolved
> (v9p7–v9p14): a **Documentation** panel was added (tabs **Plan · Todo · Readme · Claude**), **Prompt**
> (renamed from Prompts) moved into the right column beneath the Feed, the Feed's last tab was renamed
> **Requests → Inbox**, and the
> always-on agent-selector columns (Prompt **From/To**, Feed **Filter**) became **header
> dropdowns** — the multi-selects fill with **two-line identity badges** (full-height tile + role over
> number·name, mirroring the list rows) and collapse to a `+N` chip, so Compose and
> the feed streams now span the full panel width. The **Plan** tab renders the native Claude Code plan
> file (`~/.claude/plans/*.md`) as **line-numbered markdown** with a per-card review system — see
> [Documentation](#documentation-middle-bottom). Feed/History cards are **expandable** with a header
> **checkbox** for multi-select and a shared **Copy · Summarize · Share** footer (Summarize opens a
> slide-over summary; Share reuses the agent target picker). Panels are separated by a clear navy divider
> (the draggable splitter's grip nub was removed in v9p14; the strip is still drag-resizable). The
> [current mockup](ui-concept-v9p14.html) is the visual authority; a full layout-section refresh
> is tracked as backlog E3.)*

The columns are tied together by **selection**: clicking an agent card in the Team Graph loads that
agent into the **Agent** panel, so the graph highlight and the Agent panel always describe the same
agent in focus. *(The earlier dedicated CLI/live-stream pane — the old upper-right panel — was
removed in the v7 cleanup; what an agent is producing now reads in the Team Feed's Messages tab.)*

The **title bar** also carries a **Settings** gear at its right end (beside the status chips) that
opens the [Settings](#settings-step-into-view) step-into view — a full-window surface that replaces
the body and returns to the 3-pane on exit.

---

## Panels

Each panel below is the single source of truth for its own behavior. Cross-cutting ideas
(identity, linking, the scratchpad, lifecycle) are described once in
[How it works](#how-it-works--concepts-that-span-panels).

### Team Graph (middle, top)

The roster of live agents, one **card** per agent. A card carries the agent's identity (icon +
color, role, number + name) and at-a-glance run state: **two labeled health-colored bars** — a
**Turns** bar (live count against the agent's Max turns, e.g. *Turns 34/50*) and a **Ctx** bar
(context usage %), each with a leading label and an inline value — a **status badge**, its subagents
(small numbered dots), the agent's **Thinking on/off** state in the meta line, and a config summary
(model · mode · effort). The currently-selected card is filled (light teal) and marked as the one
being viewed.

- **Selection drives the app.** Clicking a card focuses that agent in the Agent panel.
- **Status at a glance.** A single **status badge** (top-right corner) shows **active / idle /
  pending**, where *pending* (the warm attention tone) means "this agent is waiting on you." It's
  deliberately **binary, not a count** — an agent can only be blocked on one thing at a time (see
  [Inbox](#the-inbox-tab)), so the *number* of agents awaiting you lives on the Team Feed's
  Inbox tab, not on each card. The badge is also a **shortcut button**: it jumps to **Inbox**
  when pending, **Prompts → History** when active, or **Prompts → Compose** when idle.
- **Health coloring.** Both the Turns bar and the Ctx bar use the same good→bad ramp the Timeline uses
  for context % (green → amber → red), so load reads at a glance without decoding the agent's identity
  color.
- **Subagents** appear as small dots on the parent card, reflecting its background tasks/children.
- **Scales past what fits.** The graph shows many agents (not just a few); cards lay out in a grid
  and the view scrolls.
- **Linking starts here.** Select the agents you want to connect and use **Link Agents** to open
  the Link Config drawer — see [Linking & context-sharing](#linking--context-sharing). *(An older
  per-card "+" link box was removed in favor of multi-select + the button.)*
- **Links as edges *(planned)*.** Active links are intended to render as **directed arrows between
  cards**; the current mockup doesn't draw them yet (linking lives in the drawer + footer count
  for now).

### Team Feed (right)

The full-height right column: a real-time, cross-agent view of communication, attention, and events,
as four tabs over a **shared agent filter** — a multi-select **list** of agent identity rows
(including a **User** row) with a single **contextual All/None** toggle — that persists across all
four tabs, **Inbox included**.

Tab order puts the everyday streams first and the **Inbox** (approvals) last (Messages · Scratch ·
Log · Inbox). *(The Inbox tab was named "Requests" before v9p8 — the rename; its contents and the
request types below are unchanged.)*

| Tab | What it shows |
|-----|----------------|
| **Messages** | The team's traffic, attributed and color-coded by agent, merged into one stream with in-tab toggles for **direction** (Sent / Received) and for how much tool detail to include (Thoughts / Read / Write / Bash / Diffs / Meta). Direction is anchored to **you, the operator**: **Sent** = prompts you pushed to the team; **Received** = everything coming back from agents. (So **User** only ever reads as *Sent* — it never carries an incoming tag.) The direction tag on each message is intentionally neutral — no special color. Cards are **multi-selectable** (same selection style as History) and feed a **Messages footer** with **Copy · Summarize · Share** (icon+text), styled like the Prompts footers. *(Replaces the former separate Outgoing and Incoming tabs.)* |
| **Scratch** | A live view of the [shared scratchpad](#the-shared-scratchpad): each post stamped with agent ID + time. |
| **Log** | A timestamped system-event stream (started, committed, flagged, link fired, permission/approval requested…), color-coded by agent. *(The former standalone Activity Log, folded in as a tab.)* |
| **Inbox** | The team-wide **approvals inbox** (last tab) — see [The Inbox tab](#the-inbox-tab) just below. |

#### The Inbox tab

The team-wide **approvals inbox** — the human-control surface that keeps agents unblocked without
dropping to a terminal. Because a Claude Code agent is single-threaded, **it can only ever be blocked
on one thing at a time**, so this tab shows **one card per agent that's waiting on you** (narrowed by
the same agent chips as the rest of the feed), and the tab's badge is the **fleet total** — how many
agents need you right now. Each card carries the **agent's identity** (icon + role + name) and its
request **type**, color-ranked along a warm reddish→copper ramp (see [Design system](#design-system)):

| Type | For | Controls |
|------|-----|----------|
| **Permission** | A tool/command the agent wants to run (the same prompts you'd normally approve in the CLI) | Approve · Deny · Always allow |
| **Approval** | A plan/handoff to review before it proceeds | Approve · **Review** · Reject |
| **Decision** | A question with candidate options to choose between | pick an option, then an explicit **Approve** (disabled until you've selected) |

- **Review routes to the plan** *(Approval cards only)*. Between Approve and Reject, a **Review**
  button **hands you to the Documentation panel's Plan tab**, expanding and briefly highlighting the
  matching plan so you can read/edit the full proposal before deciding — rather than embedding a plan
  editor inside the card. This is the deliberate cross-link between the two surfaces: the *plan* is a
  document (it lives with the docs); its *approval* surfaces here in the Inbox. *(The reciprocal — a
  plan's own Approve routing a card back into the Inbox — is the same handoff in reverse.)*
- **Reply routes to Prompts.** Every card has its own **Reply** button, set off to the far right of
  the card (separate from the approve/deny controls so it reads as its own path). It doesn't open an
  inline field — it **hands you to the [Prompts](#prompts-middle-bottom) panel**, jumping to Compose
  with that agent pre-selected as the sole target, so a free-form reply is composed and sent from the
  one place all prompts originate. *(Supersedes the earlier shared in-tab reply field.)*

### Agent (left pane)

Everything about **one** agent — whichever is selected in the graph. Two tabs share the pane.

- **Details** — the agent's configuration and live readouts, in three deliberately-separated bands:
  1. **On-demand config** (Role, No., Name, Description, Model, Skills, Tools, Color, Icon). These
     are *greyed by default*; click a field's **pencil** to edit, then **save** — so configuration
     can't be changed by accident mid-run. **Role** is a dropdown (with free-text entry) populated
     from the user- and project-level `agent.md` files; picking one in **Create** prepopulates the
     related fields from its front matter. **Skills** and **Tools** are multi-select dropdowns
     (skills from the skills files; tools = the native Claude Code tool set) that keep floating
     chips. *(Model is intentionally editable, not locked: an agent's model can be changed mid-run.)*
  2. **Always-editable while running** — **Mode**, **Effort**, and **Lifecycle** auto-stop limits,
     the knobs you reach for during a run, so they stay live. The **Mode** block carries the
     permission-mode segmented control (**Plan · Ask · Edit · Auto · Bypass**, where Bypass is the
     bypass-permissions danger option) and, beneath it, two full-width toggles whose labels read their
     own state: **Opus fast-mode Off/On** (maps to `/fast`) and **Thinking mode off/on** (extended
     thinking). See [Lifecycle & autonomy](#lifecycle--autonomy).
  3. **Live readout** — the **health-colored** context-usage bar (with a Compact action); a **Turns**
     readout (the count inline beside the label like Context, then a health bar + %); and the
     **Timeline**: a point-by-point list of the messages sent to the model that fills the rest of the
     panel, with two actions over the same list — **Rewind** (roll this agent back to the chosen
     point) and **Handoff** (branch from that point into a *new* agent). See
     [Rewind & Handoff](#rewind--handoff).
  - **Footer:** **Retire** only.
- **Create** — the new-agent wizard: Role, No., Name (with a randomize affordance),
  Description, Skills, Tools, Color, Icon, Model, Mode (with the same Fast/Think toggles), Effort,
  Lifecycle. **Handoff** lands here with the source agent's settings prepopulated (and editable).
  - **Footer:** **Create · Reset · Cancel**.

### Prompts (middle, bottom)

The compose-first heart of the app — three tabs over a **shared sub-header**, so the way you
address a prompt is consistent no matter which tab you're on.

- **Shared Source + Target** (persist across all three tabs), stacked in one column:
  - **Source** (single-select) — who the prompt is *from*: **User**, or an agent (sending *as*
    that agent for coordination). Rendered as a compact **dropdown** showing only the active
    selection (the same agent identity-row styling, collapsed); no All/None (single-select needs
    neither).
  - **Target** (multi-select) — who it goes *to*: the full agent **identity-row list** (recolorable
    tile + two-line role·name, no truncation), led by a **Scratch** row that posts to the
    [shared scratchpad](#the-shared-scratchpad), with a single **contextual All/None** toggle (shows
    *All* until everything is selected, then *None*). Multi-target replaces a separate "broadcast"
    mode — you just pick several.
- **Tabs:**
  - **Compose** — a free-text prompt area, with **copy** / **clear** as ghost icons in its header.
  - **Library** — reusable prompt **templates** with fill-in-the-blank placeholders; see
    [the Library template flow](#the-library-template-flow).
  - **History** — past prompts for the focused agent, attributed and timestamped. Cards are
    **selectable** (same style as the Team Graph cards); their actions live in a single footer strip
    — **Copy · Edit · Retry · Stop** — rather than per-card. *(Replaces the earlier per-item Reuse.)*
- **Action row** (the shared Prompts footer) — leads with a **mic** button for voice dictation
  (moved out of the Compose header), then the Revise and Response-format controls, and the Send
  split button at the right. Sending uses a pair of **split buttons** (a button joined to a dropdown
  chip), styled as a **pink primary** (Send) next to a **teal secondary** (Revise):
  - **Send** (primary) with a **timing** chip — **Now · Next · Queue** (no "Hold"; that only makes
    sense for a link). The chip carries the delivery timing, reusing the same vocabulary as link
    [Triggers](#linking--context-sharing).
  - **Revise** with a **scope** chip — **Grammar · Language · Refactor** (default Grammar): runs an
    AI cleanup/rewrite pass on the prompt before you send it, scoped from a light spelling/grammar fix
    up to a full restructure. *(Renamed from "Clean"; the earlier Minimal/Medium/Maximum strength
    levels were reworked into these scopes.)*
  - **Scope:** Compose offers Revise + Send; Library offers Send only. History swaps the row for its
    own footer (Copy · Edit · Retry · Stop).

### Documentation (middle, bottom)

The home for **organizing and reviewing all of a project's documents** — four tabs over the same
line-numbered editor: **Plan · Todo · Readme · Claude**. (A **+** adds further docs to organize here.)
It's the other half of the middle column, beneath the Team Graph.

- **The shared doc editor.** Every tab renders its file as **line-numbered markdown** whose line numbers
  match the raw file, so "see line N" is a real reference. An **interactive left rail** indexes every
  line and section: click a rail cell to **select a line, a whole section, or the entire document** (so a
  chunk can be shared or commented on). The rail cells are **color-coded by what a click selects** — pink
  = the **title** (selects the whole doc), dark teal = a **section**, light teal = a **line**; the
  selected text highlights in **light pink**, and re-clicking the active cell clears it. Inline code is
  tinted so it reads apart from body text.
- **The Plan tab is the review surface.** It lists the native Claude Code plan files
  (`~/.claude/plans/*.md`, shown under a single directory line + a "*N plans · N awaiting review*" count)
  as **expandable cards**. Each card's header is **three rows**: ① owner **agent badge** · title · state
  (e.g. *In review*); ② the **feedback tally badges** (Approve/Revise/Block counts) · *done/total steps*;
  ③ filename · **Created / Edited** date-time with a relative "ago". Expanding a card reveals the
  line-numbered plan beside a **nav rail**, then the shared footer.
- **The nav rail** has two modes: **Outline** (the section list, each with a worst-verdict dot + comment
  count) and **Feedback** (one **card per response** — the reviewer's agent badge + a thumbs **agree**
  toggle, a color-coded **verdict badge** (Approve/Revise/Block) + a **section badge**, and a clamped
  comment summary). Selecting feedback moves **three indicators together**: the **card** fills (light
  teal), its **section text** highlights (teal, linking card ↔ text), and the **comment popout** opens.
  Closing the popout or deselecting clears all three, and opening a different comment switches all three —
  driven from either a Feedback card or the in-text rail-gutter badge. The rail **resizes with the text
  column** (it grows when the popout opens, so cards aren't clipped).
- **Comments dock under the text.** Section feedback also surfaces as a **verdict badge in the rail
  gutter** at that section's line; clicking it (or a Feedback card) opens a **comment popout** docked
  under the plan body at the same width, with a merged **verdict + section** header and, per response, the
  reviewer's badge · time · a thumbs agree toggle. You add your own with the **Comment** button — enabled
  once you select a line/section — which opens a **composer** in the same popout: your badge, a **Mark as**
  verdict dropdown (Approve/Revise/Block), a thumbs agree default, an optional note, and **Save**.
- **Actions sit in the shared footer.** One footer holds, left-aligned, **Copy · Edit · Comment** (neutral)
  and **Share · Review** (teal; both reuse the agent target picker — Share distributes the plan, Review
  sends it for review), then — right-justified — the decision trio: **Revise** (send the flagged sections
  back to the authoring agent) · **Reject** · **Approve**. (It wraps to a second row on a narrow column.)
- **Cross-linked with the Inbox.** A plan is a *document* (it lives here); its *approval* surfaces in the
  Team Feed's [Inbox](#the-inbox-tab). The Inbox's **Review** button jumps here, expanding and briefly
  highlighting the matching plan; a plan's **Approve/Reject** is the same handoff in reverse.
- **The other tabs** (Todo / Readme / Claude) use the same editor + rail over a single filling surface,
  with a top toolbar (**Comment · Edit · Copy**) and title-case labels.

### Settings (step-into view)

A top-level **Settings** surface for the whole workspace — the configuration that isn't about any one
agent. It's opened from a **gear in the title bar** (right cluster, beside the WSL2 / tmux / Connected
chips) and presents as a **step-into full-window view**: it replaces the 3-pane body in place, toggles
in and out, and returns to the 3-pane on **Close** (or Esc). It is deliberately **not a fourth
always-on column** and **not a floating popup** — it honors the
[everything-visible, no-popups principle](#purpose--vision) by stepping into the same frame rather than
overlaying it.

**Tabs are by subject, not by elevation.** Five subjects — **Usage · MCP · Plugins · Config ·
Setups** — and where a subject spans config scopes, **scope is a secondary segment inside the tab**
(never a tab of its own), so a single subject is never split across tabs:

| Tab | What it owns | Scope segment |
|-----|--------------|---------------|
| **Usage** | Plan, limits, and token consumption — the `/stats` · `/status` surface. **Usage only**; per-agent cost/dollar spend stays [out of scope](#purpose--vision). | — |
| **MCP** | The global server registry — enable/disable, connection & OAuth health, and the disabled-server **parking** state. | user / project |
| **Plugins** | Installed plugins + enabled state, and marketplaces. | user / project / local |
| **Config** | Default model, permission mode, sandbox, hooks, env, CLAUDE.md, plans. Each setting tagged **Live** (takes effect now) or **New session** (needs a restart). | global / project |
| **Setups** | The full **Save / Load setup** flow (agents + links). | — |

Cross-cutting rules:

- **Read-only vs editable, separated.** Within every tab, read-only status/health/usage is kept in its
  own band, visually distinct from editable config — so glancing at state never reads as a control.
- **Global edits are gated.** Changing global (`~/.claude`) config — which affects every project — is
  held behind an explicit **confirm**, with a standing warning on the Global scope.
- **It owns the global registry, not per-agent scope.** Enablement here is "is server/plugin X
  available at all," a different thing from "may agent Y use server X," which stays in the
  [Agent panel](#agent-left-pane). The two are deliberately not conflated.
- **The footer keeps a glanceable shortcut.** A Save/Load action and a token-usage summary live in the
  [status footer](#layout--the-three-column-model) for quick access; the panel holds the full detail
  (those footer controls jump straight into Setups / Usage).

---

## How it works — concepts that span panels

### Agent identity & naming

Every agent has a stable identity made of a **role**, a per-role **number**, a short **human
name**, a **color**, and an **icon** — e.g. *researcher · 01 · sandy* → `researcher-01-sandy`.
Human names (sandy, kai, drew, rowan…) are used because they're easy to say and remember when
you're talking about agents. Color and icon are chosen per agent (not fixed by role) and then
appear *everywhere* that agent does, which is what makes the whole UI scannable.

### Linking & context-sharing

The defining capability: a persistent **link** that forwards context from one agent to another so
they can collaborate (including back-and-forth "conversation" between two agents). You create a
link from the [Team Graph](#team-graph-middle-top) and configure it in the **Link Config drawer**:

- **Direction** — a 3-state toggle: A→B, B→A, or A↔B (both). *(On the graph itself, links are
  intended to read as directed arrows — see [Team Graph](#team-graph-middle-top).)*
- **Trigger** — *when/how* the message is delivered:
  | Trigger | Behavior |
  |---------|----------|
  | **Now** | Interrupt the target and deliver immediately. |
  | **Next** | Wait for the target's current response to finish, then deliver — ahead of its queue. |
  | **Queue** | Wait for the current response *and* let the existing queue drain first (the polite default). |
  | **Hold** | Stage the message for your manual approval before it's sent. |
- **Payload** — *what* is sent:
  | Payload | Meaning |
  |---------|---------|
  | **Message** | The source's output, forwarded as a single rendered message. |
  | **Transcript** | The source agent's full conversation/context, export-style (*intent: drawn from the agent's transcript; exact source TBD*). |
  | **Manual** | No automatic content — you compose it by hand each time the link fires. |
- **End After** — optional safety limits so bidirectional links can't run away: **Turns / Time /
  Tokens** as independent toggles, each with its own value. None on = no limit; if several are on,
  the link ends at the first one reached.

**How messages read (sender + trigger).** A message an agent receives carries lightweight metadata
— who sent it and which trigger delivered it — embedded in the message for the *receiving agent's*
benefit. The dashboard hides those tags and renders the human-facing version: a color-coded sender
heading, a small trigger badge, and the body text. One message, two presentations. User-sent
prompts go through as plain text.

### The shared scratchpad

A single shared markdown document agents post to as a **living** workspace — each post attributed
to an agent and timestamped, viewable live in the Team Feed's [Scratch tab](#team-feed-right)
and writable from [Prompts → Target → Scratch](#prompts-middle-bottom). The attribution/timestamps
exist because it's a running log of who-said-what; a clean, stateless document can be produced from
it at the end. *(Posting in, reading out is the whole interaction for now; richer per-post
selecting/commenting is a [future direction](#future-directions).)*

### Rewind & Handoff

Both act on the **Timeline** in the Agent → Details tab — the list of points (messages sent to the
model) in the focused agent's run:

- **Rewind** — roll *this* agent back to a chosen point and resume from there.
- **Handoff** — branch from a chosen point into a *new* agent: it opens the Create tab with the
  source agent's settings prepopulated (editable), so you can carry the work onward without
  disturbing the original. *(Handoff replaces the earlier "Clone"/"Fork" wording. Richer handoff
  artifacts/summaries are a [future direction](#future-directions).)*

### Lifecycle & autonomy

The project leans toward letting an agent "go as far as it can" on a task rather than babysitting
it — so agents carry **auto-stop limits** (per-agent **Max turns** and **Context %**) that end a
run safely when hit. These are deliberately a **different scope** from a link's
[End After](#linking--context-sharing) limits: **Lifecycle bounds a single agent's run; End After
bounds an inter-agent exchange.** Keep the two distinct.

### The Library template flow

Library turns reusable prompt files into fill-in-the-blank forms:

- A **scrollable list** of template files on the left (there may be many).
- The selected template renders with its placeholders shown as **clickable colored pills** (the
  bare tag name, e.g. `focus_area`).
- Click a pill → an input below it (single-line that auto-grows) with **Reset** and **Apply** as
  trailing icon buttons *outside* the field; type a value and Apply pushes it back into the pill,
  which **stays editable/re-selectable** (Reset clears it back to the bare tag). *(The input is no
  longer tinted to the pill's color — the placeholder simply names the active tag.)*
- Filled vs. unfilled pills are visually distinct, and the active pill gets a selected style, so
  it's clear what's left to fill before you Send.

---

## Design system

The mockup is the source of truth for exact styling; the values below are the few specifics this
README centralizes. The dashboard speaks the **[neobrutalism.dev](https://www.neobrutalism.dev)**
visual language — thick **2px navy borders**, **hard offset shadows** (no blur) on raised/interactive
elements, **flat fills**, a uniform **tight 5px radius**, and the **Archivo** type family (heading 800
/ body 500) with **JetBrains Mono** for metrics. The palette keeps the **"Happy Hues 17"** core
(cream / navy / pink) and puts that palette's teal to work as a secondary. Token names mirror
neobrutalism's Tailwind theme (`bg-main`, `bg-secondary-background`, `border-border`, `shadow-shadow`,
`rounded-base`, `font-heading` / `font-base`) so the static mockup ports ~1:1 to React/shadcn.

**Surfaces** — deliberately just **three warm surfaces** (the earlier extra cream / off-white /
cool-gray tints were consolidated):

| Role | Value | Used for |
|------|-------|----------|
| **canvas** (`--background`) | `#fef6e4` | the app background; the Team Graph scroll-well |
| **card** (`--secondary-background`) | `#ffffff` | cards, inputs, panel bodies, **and the Team Feed tab wells** (Messages/Scratch/Log/Inbox, white like Prompts → History) — white pops against the cream canvas |
| **chrome** (`--surface-3`) | `#f5ecd9` | panel headers/footers, toolbars, segmented tracks |
| **button** (`--surface-btn`) | `#fbf5e8` | low-emphasis **action buttons** — a warm cream, lighter than chrome so buttons still pop on `--surface-3` footers (form inputs/selector fields stay white) |
| hairline (`--rule`) | `#d8cfb8` | dividers between rows inside a bordered list |

Border + heading ink is navy `#001858` (2px everywhere). Muted text ramps `#5b5f86` (`--muted`) →
`#9a93b4` (`--muted-2`).

**Accents — one emphasis ladder** (*v9p2*, grounded in Material 3 color roles + Carbon button
hierarchy): **pink = primary · teal = secondary · cream = low-emphasis · red = danger.** The crucial
point is that "secondary" deliberately spans *both* a tonal secondary action *and* anything
selected/active — they're the same emphasis tier, so teal carrying both is correct, not muddy.

| Accent | Value | Meaning (tier) |
|--------|-------|---------|
| **pink** (`--main`) | `#f582ae` | **PRIMARY** — the one primary action per surface (Send · Apply · Create · Approve · Save) · active **panel tab** · attention/count badges (Inbox, token pill) · title bar · the **selected-text highlight** in the doc render (a light-pink tint) |
| **teal** (`--secondary`) | `#8bd3dd` | **SECONDARY** — the tonal secondary *action* (Revise) · active value in segmented controls / model·trigger tabs / toggles · selection **rings** · the "N selected" count badge |
| **light teal** (`--select`) | `#a9dde7` | **selection FILL** (the "secondary container") — selected list rows *and* cards (graph nodes, History, Messages, plan **Feedback** cards), and the text of the section a selected Feedback card refers to |
| **cream** (`--surface-btn`) | `#fbf5e8` | **LOW-EMPHASIS** action buttons (utilities: Copy, Share, Reset, Deny…) |
| **success** | `#2f9e6f` | success / active |
| **warning** | `#d98a2b` | attention / pending |
| **danger** | `#d23b6a` | destructive (Retire, Reject, Stop, Bypass) |

Form **inputs** and **selector-field triggers** (Color, Icon, Role, Source, Skills, Tools) stay white
(`--secondary-background`) — fillable surfaces read distinct from clickable low-emphasis buttons; the
accent rides the *value/selected option*, not the field chrome.

**Selectors — inline vs. menu.** *Inline* selectors (all options visible — segmented controls, tabs,
toggles) show the chosen option as a **teal fill** in place. *Menu* selectors (options hidden behind a
trigger — Color/Source/Skills/Tools and **Response**) keep a **neutral** trigger; teal rides the
selected option(s) inside the open menu plus a small **teal count badge** for multi-selects.

**Split buttons** read **light chip + full action**: the dropdown chip is a *lighter tint* of the
action's accent (it recedes; the action leads). Send = full-pink action + light-pink chip
(`--main-dim #f9b9d2`); Revise = full-teal action + light-teal chip (`--secondary-dim #bfe6ec`). The
chip is a *parameter of that action*, so it stays in the action's hue family rather than going teal.

**Inbox / attention ramp** — the three request types are ranked by urgency along a single warm
ramp (reddish → copper) so importance reads without scattering colors: **Permission `#d23b4a` →
Approval `#cf7a2c` → Decision `#a9710f`**. The warning tone (`#d98a2b`) signals **pending** elsewhere:
on a graph card it tints the **status badge** (this agent is waiting on you); on the Team Feed's
Inbox tab it's a **filled count badge** (how many agents are waiting).

**Status:** shown per graph card as a rectangular **text badge** in the top-right corner (a button
that jumps to Inbox / History / Compose) — active `#2f9e6f` · idle `#9a93b4` (User / idle tone
`--ag-user #7b7fa6`) · pending → the warning tone above. The **context bar** on graph cards and in
the Agent panel is colored by **health** (success → warning → danger), not by the agent's identity
color — matching the Timeline's context-% coloring.

**Agent identity palette** — **16** colors assigned per agent and kept in a different *register* from the
UI accents above (deeper and more saturated than the light pink/teal/status tints) so identity never
collides with meaning. It's the **"Jewel" family**: an even **OKLCH** set — 16 hues spaced evenly around
the wheel at one fixed deep lightness/chroma (`oklch 0.52 0.15`), so every agent is equally weighted and
none reads as a UI signal. Listed (and shown in the picker + key) in spectral **ROYGBIV** order:
`crimson #aa3a61 · vermilion #af3c3a · amber #aa4600 · gold #9d5400 · citron #876300 · lime #687100 ·
fern #387b12 · emerald #008149 · teal #008370 · cyan #007f91 · azure #0076ab · cobalt #006bbb ·
indigo #4d5ebe · violet #7152b5 · orchid #8b48a0 · magenta #9e3f84`. Each agent also picks an **icon** from
the **game-icons.net** set (167 in `assets/icons/agents/`); these render as **recolorable tiles** — the
tile background takes the agent's color and the glyph is a white knockout. UI (non-agent) icons are
**Lucide** (`assets/icons/ui/`), drawn at ~2.25px stroke to suit the heavy borders.

**Core components** (behavior the mockup styles): **Resizable** panel groups (drag-resizable, but major
panels read as a clear **3px navy divider** rather than a grip nub — the nub was removed in v9p14),
heading strips, tabbed panels with a persistent shared sub-header, segmented controls (single-select),
**split buttons** (a pink primary or teal secondary joined to a dropdown chip — Send+timing,
Revise+scope; light chip + full action), agent **identity rows** (recolorable tile +
two-line role·name; selected = light-teal fill + check) used for the Source / Target / Filter selectors
with a **contextual All/None** toggle, **color & icon pickers** (current selection always visible; sized
so both dropdowns are the same height), the **context accordion** (a usage bar that expands to a
per-category breakdown), **labeled status bars** (a leading label · health-colored bar · inline value,
used for Turns + Context on graph cards and in the Agent panel), the **doc editor** (line-numbered
markdown with a color-coded line/section selection rail + a docked comment popout), selectable cards
(graph nodes · History · Messages · plan **Feedback** cards — light-teal fill), cards with a colored left
accent stripe (Inbox), the Timeline point-list, and palette-matched scrollbars. The **Settings step-into view** adds its own small kit: subject tabs
over a secondary scope segment, **on/off switches** (teal-when-on) for MCP/plugin enablement,
read-only vs editable section headers, lifecycle **Live / New-session** tags, health-colored usage
bars, and an explicit global-edit confirm.

**Conventions:** one uniform tight radius (a 5px `rounded-base`; small badges/chips use a tighter 3px but
are still **rounded squares** — no pills); hard offset shadows are reserved for raised / interactive
elements, while inert rows and **non-interactive badges are flat** (border-only). Identity badges used as
labels (card headers, feed/history/nav cards, the comment popout) are flat; the raised treatment is kept
only for the interactive From/To/Filter dropdown trigger. Single-line inputs carry an inline clear
"**X**". The **Palette Reference** block at the bottom of the mockup (now a light card) is a
design-token legend for implementers, **not** part of the live UI.

---

## Open questions

Genuinely *undecided* design points (decided-but-deferred ideas are under
[Future directions](#future-directions)):

1. **Transcript payload source/format.** "Transcript" should carry an agent's full conversation,
   export-style, but exactly what is captured and from where (e.g. the raw session transcript
   files) isn't finalized.
2. **Inbox color ramp & badges.** The reddish→copper request-type ramp, the per-card pending dot, and
   the Inbox-tab count badge are still being tuned for legibility and restraint.
3. **Dense link graphs.** Once links render as directed edges, how to keep many overlapping links
   readable (and how to distinguish links that share the same configuration) is unresolved.

## Future directions

Decided-but-deferred — **not built**, intentionally out of the first version:

- **Scratchpad post-level interaction** *(not built)* — select/comment on individual scratchpad
  posts, not just post-in/read-out. Deferred to keep the first version simple.
- **Handoff artifacts** *(not built)* — summary/handoff reports generated on Handoff. Deferred;
  plain context-carry-over comes first.
- **Native agent-teams messaging** *(not built)* — adopting Claude Code's built-in inter-agent
  messaging instead of the custom sender/trigger wrapping. Deferred until the native feature
  matures; custom wrapping is used for now.
- **Image paste from clipboard** *(not built)* — a frequently-wanted shortcut to drop an image
  into a prompt. Deferred.
