# AWL Multi-Agent Dashboard — Vision Spec

> What we want, not how to build it.
> The bridge (`TmuxBridge`) already handles session lifecycle, send/read, status, broadcast, and tmux sessions.
> This spec covers the **control layer on top**: a desktop GUI dashboard + per-agent controls.
> Target framework: desktop GUI (likely Electron). The spec is framework-agnostic but assumes full GUI capabilities (proper graph rendering, embedded terminals, rich color, drag interactions).

---

## 1. System Map

```
┌─ Desktop Application ──────────────────────────────────────────────────────────┐
│                                                                                 │
│  ┌──────────────────┬───────────────┬──────────────────────────────────────┐    │
│  │    LEFT PANE     │  MIDDLE PANE  │          RIGHT PANE                  │    │
│  │    (~37%)        │    (~25%)     │          (~38%)                      │    │
│  │                  │               │                                      │    │
│  │  Team Graph      │  Agent Tab    │  Claude Code CLI (embedded terminal) │    │
│  │                  │  Group        │                                      │    │
│  │  Team Feed       │  Actions      │  Prompt Tab Group                    │    │
│  │                  │               │                                      │    │
│  │  Activity Log    │  Context      │                                      │    │
│  │                  │  Sharing      │                                      │    │
│  └──────────────────┴───────────────┴──────────────────────────────────────┘    │
│                                                                                 │
└─────────────────────────────────────────────────────────────────────────────────┘
         │
         ▼
┌── WSL2 / tmux ──────────────────────────────────────────────────────────────────┐
│                                                                                  │
│   GUI backend ◄──── bridge API ────► tmux sessions (one per agent)               │
│                     (Python)         (embedded in CLI pane on selection)          │
│                         │                                                        │
│                   state file                                                     │
│          ~/.claude/awl-bridge-state.json                                         │
│          (colors, links, queues, naming counters)                                │
└──────────────────────────────────────────────────────────────────────────────────┘
```

**How it fits together:** The entire UI is a single desktop application window. There are no separate terminal tabs per agent. Instead, clicking an agent node in the Team Graph switches the right pane's embedded CLI view to that agent's tmux session. The GUI talks to agent sessions through the existing `TmuxBridge` API — the same `create()`, `send()`, `read()`, `status()`, `watch()` methods already built and tested. No new transport layer is needed. The bridge is the backbone; the dashboard is the skin.

The **state file** (`awl-bridge-state.json`) persists everything the bridge doesn't already track: agent colors, inter-agent links, prompt queues, naming counters, and scratchpad path. It's the dashboard's own memory — separate from the bridge, which is stateless by design.

---

## 2. Dashboard Layout

The dashboard is a single-window application divided into three panes. The left and right panes are wider (~37% each), with the middle pane narrower (~25%). The overall window targets a landscape (4:3) aspect ratio. No popups. Everything visible.

```
┌─────────────────────────────────────┬─────────────────────┬─────────────────────────────────────┐
│          LEFT PANE                  │    MIDDLE PANE      │          RIGHT PANE                  │
│                                     │                     │                                      │
│ ┌─ 2.1 Team Graph ───────────────┐ │ ┌─ Agent Tab Group┐ │ ┌─ 2.7 Claude Code CLI ───────────┐ │
│ │                                 │ │ │ [Details][Create]│ │ │                                  │ │
│ │  ┌─────────┐ ┌─────────┐      │ │ │ ┄┄┄┄┄┄┄┄┄┄┄┄┄┄  │ │ │  (active agent's terminal —      │ │
│ │  │●res-01  │ │●syn-01  │      │ │ │ 2.4 Agent Detail │ │ │   switches on node click)        │ │
│ │  │opus auto│ │son  edit│      │ │ │                   │ │ │                                  │ │
│ │  │████░ 62%│ │██░░ 34% │      │ │ │ Name, Model,     │ │ │  > analyzing auth module...      │ │
│ │  └────┬────┘ └─────────┘      │ │ │ Mode, Effort,    │ │ │  The auth module uses JWT...     │ │
│ │       │  3↔2  ┌─────────┐     │ │ │ Color, Context,  │ │ │                                  │ │
│ │       └──────►│●aud-01  │     │ │ │ Status, Queue,   │ │ │  > _                             │ │
│ │               │hai plan │     │ │ │ Target           │ │ └──────────────────────────────────┘ │
│ │               │█░░░ 12% │     │ │ └──────────────────┘ │                                      │
│ │               └─────────┘     │ │                       │ ┌─ 2.8 Prompt Tab Group ───────────┐ │
│ │  [Link Agents]                │ │ ┌─ 2.5 Actions ────┐ │ │ [Compose][Library]                │ │
│ └────────────────────────────────┘ │ │ [Clone▼][Compact] │ │ │ [Broadcast][History]              │ │
│                                     │ │ [Retire][Rename ] │ │ │ ┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄  │ │
│ ┌─ 2.2 Team Feed ────────────────┐ │ └──────────────────┘ │ │ Source [▼ User              ]    │ │
│ │ [Out][In][Scratch][Pending]    │ │                       │ │ ┌────────────────────────────┐   │ │
│ │ Filter: ☑res ☑syn ☑aud        │ │ ┌─ 2.6 Context ────┐ │ │ │ (multi-line text area)     │   │ │
│ │ ┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄      │ │ │ Link: res→synth  │ │ │ └────────────────────────────┘   │ │
│ │ res-01: Found 3 auth vulns... │ │ │ Trigger           │ │ │ Target [▼ researcher         ]  │ │
│ │ aud-01: Confirmed 2 of 3...   │ │ │ ○Im ○Nx ○Qu ○Hd  │ │ │ [Send] [Clear] [Queue]           │ │
│ └────────────────────────────────┘ │ │ What to send      │ │ └────────────────────────────────┘ │
│                                     │ │ ○Free ○Ctx ○Man  │ │                                      │
│ ┌─ 2.3 Activity Log ─────────────┐ │ │ End after         │ │                                      │
│ │ 14:32 res-01 ▸ started         │ │ │ ○None ○Turns      │ │                                      │
│ │ 14:35 syn-01 ✓ committed 3f   │ │ │ ○Time ○Tokens     │ │                                      │
│ │ 14:37 aud-01 ⚠ flagged 2      │ │ │[Save][1Shot][Del] │ │                                      │
│ └────────────────────────────────┘ │ └────────────────────┘ │                                      │
└─────────────────────────────────────┴───────────────────────┴──────────────────────────────────────┘
```

---

### 2.1 Team Graph

The centerpiece of the left pane. A proper graph widget where each agent is a node and inter-agent links are directed edges. The graph supports ~3 nodes across given the pane width.

- **Click a node** to select that agent — the middle pane updates to show its Detail tab and the right pane's CLI switches to that agent's live session.
- **Click an edge** to edit the link definition in the Context Sharing panel (Section 2.6).
- **To link agents:** select a source agent node, click `[Link Agents]` at the bottom of the graph, then click the target agent node. This populates the Context Sharing panel with the two agents and link direction.
- Nodes auto-layout and reflow when agents are added/removed. Manual drag-to-reposition is a nice-to-have.

**What each node shows:**
```
┌──────────┐
│● name    │   ● = colored dot (matches agent's assigned color)
│ mod mode │   mod = model abbreviation (opus, son, hai)
│ ████░ %  │   mode = permission mode (auto, def, edit, plan)
└──────────┘   bar = context window usage as filled blocks + percentage
```

**What edges show:** Each directed edge displays a compact message counter color-coded by sender. For example, an edge between researcher (red) and synthesizer (blue) might show `3↔2` where `3` renders in red (messages researcher sent) and `2` renders in blue (messages synthesizer sent back). This gives at-a-glance traffic visibility without opening the link. Edges for one-directional links show a single count with an arrow.

---

### 2.2 Team Feed

A tab group in the left pane, below the Team Graph and above the Activity Log. Provides real-time visibility into all inter-agent and user-agent communication.

**4 tabs:**

| Tab | Content |
|-----|---------|
| **Outgoing** | Real-time scrolling feed of agent outputs (responses). Each entry shows the agent's name as a heading, color-coded in the agent's color, with response body text below. Sourced from bridge polling (`read()` / `scrollback()`). |
| **Incoming** | Real-time scrolling feed of prompts received by agents. Each entry shows who sent the prompt (user or agent name as heading, color-coded) and the prompt body. Sourced from dashboard send logs and JSONL transcript parsing. |
| **Scratchpad** | Live-updating preview of a shared markdown file (default: `~/.claude/shared/scratchpad.md`). Auto-refreshes on disk change. Scrollable, shows tail by default. Path configurable in state file. |
| **Pending** | Messages queued by "Held" trigger links (see Section 2.6) awaiting manual approval. Each pending message shows source agent, target agent, timestamp, and a preview of the message body. Includes `[Approve]` and `[Deny]` buttons per message. Approved messages are dispatched immediately; denied messages are discarded and logged. |

**Shared filter:** All 4 tabs share a row of agent-name checkboxes at the top of the Team Feed area. Check/uncheck agents to show/hide their entries. Applies across all tabs simultaneously.

**Typical use:** You tell an agent "write your findings to the scratchpad." Other agents (or you) can see the output appear in the Scratchpad tab. Meanwhile, the Outgoing tab shows what each agent is producing in its own session. The Pending tab catches any held link messages for you to review before they reach their target.

---

### 2.3 Activity Log

A timestamped event stream of **system events** aggregated across all agents. This is separate from Team Feed — the Activity Log tracks metadata events, not message content.

Events logged: agent created, agent retired, status changed (idle → working, etc.), link triggered, link created/deleted, file committed, error encountered, compact issued.

- Always visible in the left pane (no collapse toggle).
- Events sourced from bridge polling (status changes) and dashboard orchestration events. The dashboard polls each agent's status on a configurable interval (default: 2 seconds).
- Color-coded by agent (each line's text inherits the agent's assigned color).
- Scrollable. Oldest entries at top, newest at bottom. Auto-scrolls to bottom unless manually scrolled up.

---

### 2.4 Agent Detail (Details Tab — Middle Pane)

The **Details** tab in the Agent Tab Group (middle pane). Shows full details and controls for whichever agent is selected in the Team Graph. All controls are real interactive widgets — text fields, radio buttons, toggles, color swatches — not just display. Changes take effect immediately where possible, or show a lock icon for params that can only be set at creation time.

| Field | Type | Live-editable? | Notes |
|-------|------|----------------|-------|
| **Name** | Text input | Yes | See Section 5 (Naming Conventions) |
| **Model** | Dropdown | Locked after start | opus, sonnet, haiku |
| **Mode** | Radio buttons | Yes | Default, Auto, AcceptEdits, Plan |
| **Effort** | 3-position toggle | Yes | Low, Medium, High, Max — maps to `/effort low\|medium\|high\max` |
| **Color** | Palette picker | Yes | 8 preset colors. Changes propagate everywhere (see Section 6) |
| **Context** | Progress bar | Read-only | Parsed from the agent's `/context` output. Percentage only, no cost |
| **Status** | Text label | Read-only | "Idle", "Working", "Awaiting permission", "Unknown" — from `bridge.status()` |
| **Queue** | Count label | Read-only | Number of prompts waiting in this agent's queue |
| **Target** | Dropdown | Yes | Default prompt target: "User" or another agent name |

**Locked fields** show a lock icon and are grayed out during a running session. The only way to change them is to retire the agent and create a new one.

---

### 2.5 Actions (Middle Pane)

A row of action buttons below the Agent Tab Group. Each operates on the currently selected agent.

| Button | What it does |
|--------|-------------|
| **Clone** | Creates a new agent with the same model/mode/cwd/color. A dropdown toggle switches between "With full context" (sends a compact summary of the source agent's conversation to the clone) and "Clean start" (empty session). The clone gets a new name (see Section 5). |
| **Compact** | Sends `/compact` to the agent's session via `bridge.send()`. Useful when the context bar is getting full. |
| **Retire** | Graceful shutdown: compacts the agent, exports a summary to the agent's log file, closes the session, and marks it as archived in the state file. Retired agents disappear from the graph but their logs persist. |
| **Rename** | Opens the name field for editing. Calls `bridge.rename()` on confirm. |

---

### 2.6 Context Sharing (Middle Pane)

The bottom section of the middle pane. Defines persistent links between agents. Populated by the **Link Agents** workflow: select a source node in the Team Graph, click `[Link Agents]`, then click the target node. The Context Sharing panel populates with the link definition.

```
┌─ Link: res-01-sandy → syn-01-kai ┐
│                                    │
│  Trigger                           │
│  ○ Immediate  ○ Next               │
│  ○ Queued     ○ Held               │
│                                    │
│  What to send                      │
│  ○ Freeform                        │
│  ○ Context  [▼ Full / Summ / Last] │
│  ○ Manual only                     │
│                                    │
│  End after                         │
│  ○ None       ○ Max turns          │
│  ○ Timeout    ○ Max tokens         │
│                                    │
│  [Save Link] [One Shot] [Delete]   │
└────────────────────────────────────┘
```

#### Trigger Types

Controls **when** the link fires — specifically, how the message is delivered to the target.

| Trigger | How it works |
|---------|-------------|
| **Immediate** | Interrupts the target agent right now. The dashboard calls `bridge.interrupt()` (sends Ctrl+C/Escape to stop the target's current generation), then immediately sends the payload via `bridge.send()`. Use when urgency outweighs the cost of interrupting work in progress. |
| **Next** | Waits for the target to finish its current response (transition to idle), then sends the payload immediately — **jumping ahead of any queued prompts**. A priority delivery that doesn't interrupt but doesn't wait in line either. |
| **Queued** | Waits for the target to finish its current response **and** drain all existing queued prompts (FIFO), then delivers. The polite default — respects the queue. |
| **Held** | Stages the message in the Team Feed's **Pending** tab for manual review. The message is not sent until the user clicks `[Approve]`. Denied messages are discarded and logged. Use for high-stakes links where you want a human checkpoint. |

#### What to Send (Payload)

Controls **what** gets sent to the target when the link fires.

| Payload | What gets sent |
|---------|----------------|
| **Freeform** | The source agent's recent output, captured via `bridge.scrollback()`, wrapped in the inter-agent message format (Section 4). The target receives it as a message from the source agent. Analogous to "whatever the source just said, forward it." |
| **Context** | A structured context transfer. Three sub-options: **Full** (complete scrollback), **Summary** (compact summary of the source's conversation), **Last** (last N lines of output). All wrapped in the message format. |
| **Manual only** | The link exists (visible in the graph) but carries no automatic payload. It only fires when the user manually triggers it. Use for links where the timing is automatic but the content is composed by hand each time. |

#### Link Controls

| Button | Behavior |
|--------|----------|
| **Save Link** | Persists the link definition to `awl-bridge-state.json`. The link becomes active and the dashboard begins watching for its trigger condition. |
| **One Shot** | Saves and activates the link, but it **auto-deletes after firing once**. Useful for one-time context transfers that don't need a persistent connection. |
| **Delete** | Removes the link from the state file, removes the edge from the graph, and stops the trigger watch. |

#### Link Lifecycle

- Links persist in `awl-bridge-state.json` and survive dashboard restarts.
- A link to a retired/closed agent is automatically disabled (shown as a dashed/dimmed edge in the graph).
- Links are one-directional. To create a bidirectional flow, create two links (A→B and B→A).
- The **End after** field prevents runaway loops in bidirectional link configurations. When a link reaches its limit (max turns exchanged, timeout elapsed, or token budget hit), it automatically deactivates until manually re-enabled.

---

### 2.7 Claude Code CLI (Right Pane, Top)

An embedded terminal view showing the active agent's live Claude Code session. Switches when a different agent node is clicked in the Team Graph. This is the raw Claude Code TUI — the user can read what the agent is doing in real time.

Input to the agent goes through the Compose tab (Section 2.8) or via links, not by typing directly into this pane. The pane is a read-only view of the tmux session rendered via the bridge's `read()` / `scrollback()` methods (or via an embedded terminal widget if the framework supports it).

---

### 2.8 Prompt Tab Group (Right Pane, Bottom)

A tab group with 4 tabs for all prompt-related interactions: **Compose**, **Library**, **Broadcast**, and **History**.

#### Compose Tab

The primary interface for sending prompts to agents.

```
┌─ Compose ──────────────────────────┐
│                                     │
│  Source [▼ User                  ]  │
│                                     │
│  ┌─────────────────────────────┐    │
│  │                             │    │
│  │  (multi-line text area)     │    │
│  │  compose prompts here       │    │
│  │                             │    │
│  └─────────────────────────────┘    │
│                                     │
│  Target [▼ researcher-01-sandy  ]   │
│  [Send] [Clear] [Queue]            │
└─────────────────────────────────────┘
```

- **Source** dropdown: `User` (default) plus all active agent names. When Source is set to an agent, the prompt is wrapped in the inter-agent message format (Section 4) so the target agent perceives it as coming from the source agent. This lets the user impersonate agents for coordination purposes.
- **Text area** supports multi-line input. Paste works. Raw text, sent as-is (or wrapped in message format if Source is an agent).
- **Target** dropdown lists all active agents. Defaults to whichever agent is currently selected in the Team Graph.
- **Send** dispatches immediately. If the agent is busy, the prompt is queued automatically and a notice appears.
- **Clear** empties the text area.
- **Queue** explicitly adds the prompt to the target agent's queue without sending. Queued prompts auto-send in FIFO order when the agent reaches idle state.

#### Library Tab

```
┌─ Library ──────────────────────────┐
│                                     │
│  > analyze-codebase.md              │
│    review-pr.md                     │
│    property-research.md             │
│                                     │
│  ┌─ Preview ──────────────────┐     │
│  │ Analyze the codebase for   │     │
│  │ {{focus_area}} and report  │     │
│  │ findings to scratchpad.    │     │
│  └────────────────────────────┘     │
│                                     │
│  Fill: focus_area [auth module   ]  │
│  Target [▼ researcher-01-sandy  ]   │
│  [Send] [Queue]                     │
└─────────────────────────────────────┘
```

- **Template list** populated by scanning `~/.claude/prompts/*.md` (or the project's `prompts/` folder — configurable in state file). Each file is one reusable prompt.
- **Preview pane** shows the full text of the selected template. Template variables use `{{variable_name}}` syntax.
- **Fill fields** appear dynamically below the preview, one per `{{variable}}` found in the template. Values get substituted before sending.
- **Send/Queue** work the same as in Compose but with the filled template text.

Templates are plain text files. Optional YAML frontmatter for organization:

```yaml
---
description: Broad codebase analysis with configurable focus
variables: [focus_area]
---

Analyze the codebase for {{focus_area}} and report findings to the scratchpad.
Include: file structure, key patterns, potential issues.
```

#### Broadcast Tab

A streamlined interface for sending the same prompt to multiple agents simultaneously.

```
┌─ Broadcast ────────────────────────┐
│                                     │
│  Source [▼ User                  ]  │
│                                     │
│  Target                             │
│  ☑ researcher-01-sandy              │
│  ☑ synthesizer-01-kai               │
│  ☐ auditor-01-drew                  │
│  [All] [None]                       │
│                                     │
│  ┌─────────────────────────────┐    │
│  │ Stop current work and       │    │
│  │ report status to scratchpad │    │
│  └─────────────────────────────┘    │
│                                     │
│  [Send to checked]                  │
└─────────────────────────────────────┘
```

- **Source** dropdown: `User` (default) plus all active agent names. Same behavior as Compose — when Source is an agent, the message is wrapped in inter-agent format. **This is the one exception** where messages can be sent between unlinked agents.
- **Target checklist** shows all active agents with checkboxes. All checked by default. Toggle individually or use All/None shortcuts.
- **Text area** is the same multi-line input as Compose. Same text goes to every checked agent.
- **Send to checked** dispatches in parallel via `bridge.broadcast()`. Busy agents get the prompt queued.

#### History Tab

A scrollable feed of every prompt sent to the currently selected agent.

- Filtered to whichever agent is selected in the Team Graph.
- Each entry shows the **source name as a heading** (e.g., "User" or "researcher-01-sandy") above the prompt body text. Agent-sourced entries are **color-coded** in the source agent's color.
- **Source filter:** A checklist at the top (same pattern as Broadcast): `User` + all agents that have sent messages to the active agent. Check/uncheck to filter the feed.
- **[Reuse] button** on each entry: copies the prompt text to the Compose tab's text area, ready for editing and resending.
- Sourced from the agent's JSONL transcript via `bridge.read_log()`, filtered to user/agent message entries.

---

## 3. Agent Creation Wizard

The **Create New** tab in the Agent Tab Group (middle pane). Click the tab to open the wizard.

```
┌─ Create New Agent ─────────────────┐
│                                     │
│  Name     [researcher-04-haven   ]  │
│  Model    [▼ opus               ]   │
│  Role     [▼ researcher         ]   │
│           .claude/agents/*.md       │
│  Mode     ○Default ○AcceptEdits     │
│           ○Plan    ○Auto            │
│  Color    [■ ■ ■ ■ ■ ■ ■ ■]       │
│  CWD      [C:/Users/lester/proj  ]  │
│                                     │
│  [Create]  [Cancel]                 │
└─────────────────────────────────────┘
```

### Role Templates

The **Role** dropdown is populated by scanning `.claude/agents/*.md` files. These are Claude Code's built-in agent definition files. When a role is selected, the wizard passes `--agent <filepath>` to the `claude` command on session creation. The agent file's system prompt, tools, and configuration are applied natively by Claude Code.

If the template file specifies `default_model` or `default_mode` in its frontmatter, the wizard pre-fills those fields (but they remain editable). The `description` field shows as a subtitle in the dropdown.

### Color Assignment

Colors are auto-assigned from a rotating palette of 8 visually distinct colors: red, blue, green, yellow, magenta, cyan, orange, white. The wizard picks the first unused color. Override by clicking a different swatch. If all 8 are in use, colors are reused from the beginning.

### CWD Field

Pre-filled with the workspace default CWD (from `bridge.set_cwd()` or the state file). Accepts Windows paths (`C:\Users\lester\project`) or WSL paths (`/home/lester/project`) — the bridge handles translation.

---

## 4. Inter-Agent Message Format

All messages sent between agents — whether via links (Section 2.6), Broadcast with Source=agent, or Compose with Source=agent — are wrapped in XML metadata tags. This format serves two purposes:

1. **For the receiving agent:** The LLM sees the full XML and knows who sent the message and how it was triggered.
2. **For the dashboard display:** The UI parses these tags out and renders them visually — agent name heading, source color, trigger badge — instead of showing raw XML in History and Team Feed.

### Format

```xml
<msg_meta>
  <from>researcher-01-sandy</from>
  <trigger>queued</trigger>
</msg_meta>
<msg_body source="researcher-01-sandy">
Found 3 auth vulnerabilities in the JWT middleware.
The token refresh logic doesn't validate expiry...
</msg_body>
```

| Field | Description |
|-------|-------------|
| `<from>` | The full agent ID of the sender (e.g., `researcher-01-sandy`) |
| `<trigger>` | How the message was delivered: `immediate`, `next`, `queued`, `held`, `broadcast`, or `user` |
| `source` attribute on `<msg_body>` | Redundant with `<from>` for easy parsing — the agent can reference it without parsing the meta block |

**Dashboard rendering:** When displaying in History or Team Feed, the dashboard strips the XML tags and renders:
- Agent name as a colored heading (in the sender's agent color)
- Trigger type as a small badge or label
- Body text below the heading

**User-sourced messages** (Source = User in Compose) are sent as plain text with no wrapping. Only agent-to-agent messages get the format.

---

## 5. Naming Conventions

### Auto-generated Names

The wizard's **Name** field is pre-populated but fully editable. The pattern includes a human name drawn from a bundled list:

**With a role selected:** `{role}-{NN}-{name}`
- Examples: `researcher-01-sandy`, `implementer-02-kai`, `auditor-01-drew`
- The number increments per role across the lifetime of the state file (not just active agents). If you've created and retired three researchers, the next one is `researcher-04-{name}`.
- The role slug is derived from the agent file: `researcher.md` → `researcher`.

**Without a role:** `agent-{NN}-{name}`
- Examples: `agent-04-haven`, `agent-05-rowan`, `agent-06-brook`

### Name List

A bundled list of ~100 short, easy-to-say human names. Gender-neutral, no duplicates, no ambiguity when spoken. Cycled sequentially (not random) so names are predictable.

Sample: `sandy, kai, drew, morgan, taylor, casey, jordan, alex, riley, quinn, sage, haven, rowan, ember, brook, sky, lane, reed, dale, blair, avery, logan, devon, tate, reese, finley, marlow, arden, elliot, piper, ...`

### Manual Override

You can always clear the Name field and type any name. The only constraint is uniqueness — the wizard won't create a session with a name that already exists (active or archived).

### On Rename

The rename action (Section 2.5) is a free-text edit. It doesn't re-derive from the naming pattern — the pattern only applies at creation time.

---

## 6. Visual Identity

Each agent is assigned a color at creation time (auto-assigned or user-picked from 8 presets). That color is used **everywhere** the agent appears:

| Surface | How color is applied |
|---------|---------------------|
| **Team Graph node** | Colored dot (`●`) and node border |
| **Team Graph edge** | Message count labels colored per sender |
| **Team Feed entries** | Agent name heading rendered in agent color |
| **Activity Log entries** | Entire line text in agent color |
| **History entries** | Source heading in source agent's color |
| **Pending messages** | Source/target labels in respective colors |

Changing an agent's color in the Detail panel (Section 2.4) propagates to all displays immediately.

**Color palette:** 8 visually distinct colors — red, blue, green, yellow, magenta, cyan, orange, white. If all 8 are in use, the wizard reuses colors from the beginning. The picker always shows all 8.

---

## 7. Feature Checklist

> To be updated after the design is finalized.

---

## 8. Build Phases

> To be updated after the design is finalized.

---

## Appendix A: Claude Code CLI — Dashboard-Relevant Commands & Config

> Extracted from `cli-reference.md` (v2.1.90). Organized by how the dashboard would use them. The bridge wraps most of these — this appendix maps CLI capabilities to UI features.

---

### A.1 Agent Teams (Experimental)

The built-in agent teams feature is the closest native analog to what the dashboard does. Understanding its surface area helps us decide what to use directly vs. what to build on top of the bridge.

| Surface | Value | Notes |
|---------|-------|-------|
| `--agent-teams` flag | Enables `SendMessage`, `TeamCreate`, `TeamDelete` tools | Adds inter-agent messaging natively. Currently experimental |
| `--teammate-mode` | `auto`, `in-process`, `tmux` | Controls how teammates render. `tmux` mode aligns with our bridge |
| `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS` | `1` to enable | Env var equivalent of `--agent-teams` |
| `CLAUDE_CODE_TEAM_NAME` | Name of the team | Set automatically when agent teams are active |

**Dashboard relevance:** We could potentially hook into native agent teams for the messaging layer instead of building our own XML message format. Worth investigating whether `SendMessage` supports the trigger/payload semantics we need (immediate, queued, held) or if it's too simple.

---

### A.2 Agent & Subagent Creation

These control how agents are spawned — the dashboard's Create New wizard maps directly to these.

| CLI Flag / Env Var | Purpose | Maps to UI |
|-------------------|---------|------------|
| `--agent <filepath>` | Specify agent definition file (.md) | **Role** dropdown in Create wizard |
| `--agents <json>` | Define custom subagents dynamically via JSON | Could bypass .md files for on-the-fly agent creation |
| `--model <name>` | Set model (opus, sonnet, haiku) | **Model** dropdown |
| `--permission-mode <mode>` | default, acceptEdits, plan, auto | **Mode** radio buttons |
| `--effort <level>` | low, medium, high, max | **Effort** segmented control |
| `--allowedTools <patterns>` | Tools that skip permission prompts | Could be exposed as advanced agent config |
| `--disallowedTools <patterns>` | Tools removed entirely | Could restrict agent capabilities |
| `--worktree <name>` | Start in isolated git worktree | **CWD** field (auto-creates worktree) |
| `--tmux` | Create tmux session for worktree | Bridge already manages tmux — this enables native support |
| `--name <name>` / `-n` | Session display name | **Name** field in Create wizard |
| `--add-dir <path>` | Additional working directories | Could be multi-CWD support |
| `CLAUDE_CODE_SUBAGENT_MODEL` | Model override for subagents | Global subagent model setting |
| `ANTHROPIC_MODEL` | Model override | Alternative to `--model` |

**Key pattern for the bridge:**
```bash
claude --agent researcher.md --model opus --permission-mode auto --effort high --name "researcher-01-sandy" --tmux
```

---

### A.3 Session Lifecycle

These control session persistence, resumption, and forking — critical for agent retirement, cloning, and crash recovery.

| CLI Flag | Purpose | Maps to UI |
|----------|---------|------------|
| `-c` / `--continue` | Resume most recent session in cwd | Reconnect to agent after dashboard restart |
| `-r <id\|name>` / `--resume` | Resume session by ID or name | Agent session restore |
| `--fork-session` | Branch from existing session | **Clone** action ("With full context") |
| `--session-id <uuid>` | Use specific session UUID | Internal session tracking |
| `--no-session-persistence` | Disable persistence (print mode) | Ephemeral/disposable agents |
| `CLAUDE_CODE_RESUME_INTERRUPTED_TURN` | Auto-resume if previous session ended mid-turn | Crash recovery |

**Dashboard patterns:**
- **Clone (with context):** `--resume <source-id> --fork-session --name <new-name>`
- **Clone (clean start):** New session with same `--agent` / `--model` / `--permission-mode`
- **Retire:** Export summary, then close tmux session
- **Crash recovery:** `--continue` or `--resume` with session name

---

### A.4 Context Management

These control the context window — maps directly to the Context progress bar and Compact action.

| Surface | Purpose | Maps to UI |
|---------|---------|------------|
| `/compact` | Compress context (keep summary) | **Compact** action button |
| `/context` | Visualize context usage | **Context** progress bar (parsed) |
| `CLAUDE_CODE_AUTO_COMPACT_WINDOW` | Context capacity in tokens | Context bar max value |
| `CLAUDE_AUTOCOMPACT_PCT_OVERRIDE` | Auto-compact trigger % (default ~95%) | Could show warning threshold on bar |
| `DISABLE_AUTO_COMPACT` | Disable auto-compaction | Per-agent toggle (advanced) |
| `CLAUDE_CODE_DISABLE_1M_CONTEXT` | Disable 1M context window | Forces smaller context |
| `CLAUDE_CODE_MAX_OUTPUT_TOKENS` | Max output tokens per request | Could cap verbose agents |

---

### A.5 Print / SDK Mode (Programmatic Control)

These are how the bridge talks to agents non-interactively. Understanding the full surface area informs what the dashboard can do beyond send/read.

| CLI Flag | Purpose | Dashboard Use |
|----------|---------|---------------|
| `-p` / `--print` | Non-interactive mode | Bridge's primary invocation mode |
| `--max-turns <n>` | Limit agentic turns | **End after → Turns** in link config |
| `--max-budget-usd <n>` | Budget cap | **End after → Tokens** (approximate) |
| `--output-format json\|stream-json` | Structured output | JSONL transcript parsing |
| `--input-format stream-json` | Structured input | Programmatic prompt injection |
| `--verbose` | Full turn-by-turn output | Detailed logging for Activity Log |
| `--json-schema <schema>` | Validated JSON output | Structured agent responses |
| `--fallback-model <model>` | Fallback on overload | Auto-downgrade if Opus is rate-limited |

**Potential bridge enhancement:** The bridge currently uses `send()` into a tmux TUI session. For some operations (one-shot queries, structured extraction), `-p` mode with `--output-format json` could be more reliable than screen-scraping.

---

### A.6 TUI Slash Commands (Agent-Relevant)

Commands available inside running agent sessions. The dashboard can issue these via `bridge.send()`.

| Command | What it does | Dashboard trigger |
|---------|-------------|-------------------|
| `/compact` | Compress context | **Compact** action button |
| `/context` | Show context usage | Polled for **Context** progress bar |
| `/effort <level>` | Change effort | **Effort** segmented control (live edit) |
| `/model <name>` | Change model | Would need to unlock Model field |
| `/plan` | Toggle plan mode | **Mode** toggle (Plan) |
| `/branch` / `/fork` | Fork conversation | **Clone** action |
| `/rewind` | Restore to checkpoint | Potential undo/rollback feature |
| `/agents` | List agent configs | Available roles for Create wizard |
| `/tasks` / `/bashes` | List background tasks | Could surface subagent activity per agent |
| `/export [file]` | Export conversation | Part of **Retire** flow (export summary) |
| `/diff` | View uncommitted changes | Could show in agent detail or CLI pane |
| `/clear` / `/reset` | Wipe conversation | Nuclear reset option |
| `/rename <name>` | Rename session | **Rename** action button |
| `/color <color>` | Set prompt bar color | **Color** palette picker |
| `/brief` | Toggle brief mode | Potential per-agent output verbosity toggle |
| `/cost` | Show session cost | Could show per-agent spend |

---

### A.7 Environment Variables for Agent Orchestration

Variables the dashboard should set per-agent or globally to control behavior.

#### Per-Agent (set in agent's tmux environment)

| Variable | Purpose | Dashboard Use |
|----------|---------|---------------|
| `ANTHROPIC_MODEL` | Override model | Set at agent creation |
| `CLAUDE_CODE_EFFORT_LEVEL` | Effort level | Set at creation or live-edit |
| `CLAUDE_CODE_AUTO_COMPACT_WINDOW` | Context capacity | Per-agent context tuning |
| `CLAUDE_AUTOCOMPACT_PCT_OVERRIDE` | Compact threshold | Per-agent threshold |
| `CLAUDE_CODE_MAX_OUTPUT_TOKENS` | Max output per request | Cap verbose agents |
| `BASH_DEFAULT_TIMEOUT_MS` | Bash timeout | Prevent agent hangs |

#### Global (dashboard-level)

| Variable | Purpose | Dashboard Use |
|----------|---------|---------------|
| `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS` | Enable native teams | Toggle in dashboard settings |
| `CLAUDE_CODE_MAX_TOOL_USE_CONCURRENCY` | Max parallel tools | Global performance tuning |
| `CLAUDE_AUTO_BACKGROUND_TASKS` | Auto-background slow agents | Auto-optimization |
| `TASK_MAX_OUTPUT_LENGTH` | Subagent output cap (default 32k, max 160k) | Control context transfer sizes |
| `CLAUDE_CODE_ENABLE_TELEMETRY` | OpenTelemetry | Dashboard monitoring integration |

---

### A.8 Remote Control & Bridge Integration

Newer features that could supplement or replace parts of the tmux bridge.

| Surface | Purpose | Notes |
|---------|---------|-------|
| `claude remote-control` | Start RC server (no local TUI) | Alternative to tmux for headless agents |
| `--remote-control` / `--rc` | Interactive + RC enabled | Agent accessible via both TUI and API |
| `/remote-control` | Connect terminal for RC | Could enable dashboard ↔ agent channel |
| `CLAUDECODE` env var | Set to `1` in CC-spawned shells | Detect CC environment from bridge |

**Future consideration:** Remote Control mode could provide a cleaner API for agent communication than tmux screen-scraping. The bridge's `send()`/`read()` currently parses terminal output — RC might offer structured I/O. Worth investigating as the native feature matures.

---

### A.9 MCP Configuration

For agents that need custom MCP servers (e.g., a researcher with web search, an auditor with database access).

| Surface | Purpose | Dashboard Use |
|---------|---------|---------------|
| `--mcp-config <file\|json>` | Load MCP config from file | Per-agent MCP server sets |
| `--strict-mcp-config` | Only use specified MCP servers | Lock agent to specific tools |
| `/mcp enable\|disable <server>` | Toggle MCP servers in session | Live MCP management |
| `MCP_TIMEOUT` | MCP server startup timeout | Reliability tuning |
| `MCP_TOOL_TIMEOUT` | MCP tool execution timeout | Prevent agent stalls |

**Pattern:** Each agent role could have a preset MCP config:
- Researcher: brave-search, firecrawl, exa
- Auditor: github, neon
- Implementer: playwright, docker

---

### A.10 Summary: CLI-to-Dashboard Feature Map

| Dashboard Feature | Primary CLI Surface | Bridge Method |
|-------------------|-------------------|---------------|
| Create agent | `claude --agent <file> --model <m> --permission-mode <pm> --name <n>` | `bridge.create()` |
| Send prompt | Stdin / `-p` / tmux input | `bridge.send()` |
| Read output | Stdout / tmux capture | `bridge.read()` / `bridge.scrollback()` |
| Check status | Poll tmux pane state | `bridge.status()` |
| Compact context | `/compact` | `bridge.send('/compact')` |
| Change effort | `/effort <level>` | `bridge.send('/effort high')` |
| Clone (with context) | `--resume <id> --fork-session` | `bridge.create()` with fork params |
| Clone (clean) | New session, same params | `bridge.create()` |
| Retire | `/export` → close session | `bridge.export()` → `bridge.close()` |
| Rename | `/rename <name>` | `bridge.rename()` |
| Broadcast | Send to multiple sessions | `bridge.broadcast()` |
| Inter-agent message | tmux send with XML format | `bridge.send()` with message wrapper |
| Context transfer | `/compact` output + send | `bridge.read()` → `bridge.send()` |
| Session recovery | `--continue` / `--resume` | `bridge.resume()` |
| Background monitoring | Poll status loop | `bridge.status()` on interval |
