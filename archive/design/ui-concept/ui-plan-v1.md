# AWL Multi-Agent Terminal — Vision Spec

> What we want, not how to build it.
> The bridge (`TmuxBridge`) already handles session lifecycle, send/read, status, broadcast, and WT tabs.
> This spec covers the **control layer on top**: a TUI dashboard + per-agent controls.

---

## 1. System Map

```
┌─ Windows Terminal ──────────────────────────────────────────────────────┐
│                                                                         │
│  Tab 0 (Dashboard)       Tab 1 (●red)        Tab 2 (●blue)             │
│  ┌───────────────────┐   ┌─────────────┐     ┌─────────────┐           │
│  │ TUI App            │   │ Claude Code  │     │ Claude Code  │           │
│  │ (Textual/blessed)  │   │ (researcher) │     │ (implementer)│           │
│  │                    │   │              │     │              │           │
│  │ graph + sidebar    │   │ raw TUI      │     │ raw TUI      │           │
│  └───────────────────┘   └─────────────┘     └─────────────┘           │
│                                                                         │
│  tmux status bar:  ● Dashboard | ● researcher | ● implementer | ...    │
│                                  (colored dots per agent)               │
└─────────────────────────────────────────────────────────────────────────┘
        │                          │                    │
        ▼                          ▼                    ▼
┌── WSL2 / tmux ──────────────────────────────────────────────────────────┐
│                                                                         │
│   TUI Dashboard process ◄──── bridge API ────► tmux sessions            │
│   (Tab 0)                      (Python)        (Tab 1, 2, ...)          │
│                                    │                                    │
│                              state file                                 │
│                     ~/.claude/awl-bridge-state.json                     │
│                     (agent colors, links, queue, scratchpad path)       │
└─────────────────────────────────────────────────────────────────────────┘
```

**How it fits together:** The dashboard is itself a tmux session (Tab 0) running a Python TUI app. It talks to the other tmux sessions (each running a live Claude Code TUI) through the existing `TmuxBridge` API — the same `create()`, `send()`, `read()`, `status()`, `watch()` methods already built and tested. No new transport layer is needed. The bridge is the backbone; the dashboard is the skin.

The **state file** (`awl-bridge-state.json`) persists everything the bridge doesn't already track: agent colors, inter-agent links, prompt queues, scratchpad path, and naming counters. It's the dashboard's own memory — separate from the bridge, which is stateless by design.

---

## 2. Dashboard Layout (Tab 0)

The dashboard is a single TUI app split into two internal panels. No popups. Everything visible.

```
┌─────────────────────────────────────────────┬────────────────────────────┐
│                LEFT PANE                     │        RIGHT PANE          │
│                                             │      (selected agent)      │
│  ┌─ Agent Graph ──────────────────────────┐ │                            │
│  │                                        │ │  2.4  Agent Detail         │
│  │  2.1  Dependency graph                 │ │  ─────────────────         │
│  │       (nodes = agents, edges = links)  │ │  Name    [researcher    ]  │
│  │                                        │ │  Model    opus (locked)    │
│  │   ┌──────────┐      ┌───────────┐     │ │  Mode    ○Def ●Auto ○Edit  │
│  │   │●research │─────►│●synthesize│     │ │  Effort  [■□□] Lo Mi Hi    │
│  │   │ opus auto│      │ son  edit │     │ │  Color   [■ ■ ■ ■ ■ ■ ■]  │
│  │   │ ████░ 62%│      │ ██░░ 34%  │     │ │  Context ████████░░ 78%    │
│  │   └──────────┘      └─────┬─────┘     │ │  Status  Working           │
│  │   ┌──────────┐            │           │ │  Queue   2 prompts         │
│  │   │● auditor │────────────┘           │ │                            │
│  │   │ hai plan │                        │ │  2.5  Actions               │
│  │   │ █░░░ 12% │                        │ │  ─────────────────         │
│  │   └──────────┘                        │ │  [Clone ▼] [Compact]       │
│  │                                        │ │  [Retire]  [Rename ]       │
│  │  Click node → select in sidebar        │ │  [Link To →] [Pipe →]     │
│  │  Click edge → edit link behavior       │ │  [Share Context →]         │
│  └────────────────────────────────────────┘ │                            │
│                                             │  2.6  Prompt History       │
│  ┌─ 2.2  Shared Scratchpad ──────────────┐ │  ─────────────────         │
│  │  (live preview of scratchpad.md)       │ │  > "Analyze auth module"   │
│  │  Latest: "Found 3 matching props..."  │ │  > "Review test coverage"  │
│  │  ▼ scroll                              │ │  (click to resend/edit)    │
│  └────────────────────────────────────────┘ │                            │
│                                             │                            │
│  ┌─ 2.3  Activity Log (collapsible) ─────┐ │                            │
│  │  14:32  researcher  started task       │ │                            │
│  │  14:35  implementer committed 3 files  │ │                            │
│  │  14:37  auditor     flagged 2 issues   │ │                            │
│  └────────────────────────────────────────┘ │                            │
│                                             │                            │
├─────────────────────────────────────────────┴────────────────────────────┤
│ [F1 Help] [F2 New Agent] [F3 Broadcast] [F4 Log] [F5 Prompts]          │
└──────────────────────────────────────────────────────────────────────────┘
```

### 2.1 Agent Graph

The centerpiece of the left pane. Each agent is a box (node) containing at-a-glance info: colored dot, name, model abbreviation, permission mode, and a context usage bar. Directed edges between nodes represent active links (see Section 6).

- **Click a node** to select that agent — the right pane updates to show its detail panel.
- **Click an edge** to edit the link definition (trigger condition, payload, target).
- **Press Enter** on a selected node to jump to that agent's live tmux tab in Windows Terminal. Press Esc from any agent tab to return to the dashboard.
- Nodes are arranged automatically using a simple left-to-right flow layout. Agents with no links float independently. The layout is not user-draggable (TUI limitation) but reflows when agents are added/removed.

**What each node shows:**
```
┌──────────┐
│● name    │   ● = colored dot (matches agent's assigned color)
│ mod mode │   mod = model abbreviation (opus, son, hai)
│ ████░ %  │   mode = permission mode (auto, def, edit, plan)
└──────────┘   bar = context window usage as filled/empty blocks + percentage
```

### 2.2 Shared Scratchpad

A live-updating preview of a shared markdown file (default: `~/.claude/shared/scratchpad.md`). Any agent can read from or write to this file — it's the cross-agent communication channel that doesn't require links or pipes.

- The preview auto-refreshes when the file changes on disk (via polling or inotify).
- Scrollable within its panel. Shows the tail by default (newest content visible).
- The scratchpad path is configurable in the state file. You could point it at a project-specific file instead of the default.

**Typical use:** You tell an agent "write your findings to the scratchpad." Other agents (or you, from the dashboard) can see the output appear in real time without switching tabs.

### 2.3 Activity Log

A timestamped event stream aggregated across all agents. Every significant state change gets a line: agent created, prompt sent, response started, response finished, file committed, error encountered, link triggered.

- **Collapsible** — toggle visibility with F4. When collapsed, the scratchpad and graph get more vertical space.
- Events are sourced from bridge polling (status changes) and transcript parsing (message boundaries). The dashboard polls each agent's status on a configurable interval (default: 2 seconds).
- Color-coded by agent (each line's text inherits the agent's assigned color).
- Scrollable. Oldest entries at top, newest at bottom. Auto-scrolls to bottom unless you've manually scrolled up.

### 2.4 Agent Detail (right pane)

The right pane shows full details and controls for whichever agent is selected in the graph. All controls are real interactive widgets — text fields, radio buttons, toggles, color swatches — not just display. Changes take effect immediately where possible, or show a lock icon for params that can only be set at creation time.

| Field | Type | Live-editable? | Notes |
|-------|------|----------------|-------|
| **Name** | Text input | Yes | See naming conventions below |
| **Model** | Dropdown | Locked after start | opus, sonnet, haiku |
| **Mode** | Radio buttons | Yes | Default, Auto, AcceptEdits, Plan |
| **Effort** | 3-position toggle | Yes | Low, Medium, High — maps to /fast toggle and system prompt hints |
| **Color** | Palette picker | Yes | 8 preset colors. Changes propagate to graph node, tmux tab dot, pane border |
| **Context** | Progress bar | Read-only | Parsed from the agent's /context output. Shows percentage only, no cost |
| **Status** | Text label | Read-only | "Idle", "Working", "Awaiting permission", "Unknown" — from `bridge.status()` |
| **Queue** | Count label | Read-only | Number of prompts waiting in this agent's queue |

**Locked fields** show a lock icon and are grayed out during a running session. The only way to change them is to retire the agent and create a new one (or implement session restart, which is a future concern).

### 2.5 Actions

A row of action buttons below the detail fields. Each operates on the currently selected agent.

| Button | What it does |
|--------|-------------|
| **Clone** | Creates a new agent with the same model/mode/cwd/color. A dropdown toggle switches between "With full context" (sends a compact summary of the source agent's conversation to the clone) and "Clean start" (empty session). The clone gets a new name (see naming conventions). |
| **Compact** | Sends `/compact` to the agent's session via `bridge.send()`. Useful when the context bar is getting full. |
| **Retire** | Graceful shutdown: compacts the agent, exports a summary to the agent's log file, closes the session, and marks it as archived in the state file. Retired agents disappear from the graph but their logs persist. |
| **Rename** | Opens the name field for editing. Calls `bridge.rename()` on confirm. |
| **Link To** | Opens the link editor (Section 6) with this agent as the source. You pick the target and define the trigger/payload. |
| **Pipe** | One-shot context transfer: captures the current agent's recent output (last N lines or compact summary) and sends it to a target agent you select. Unlike a link, this doesn't persist — it fires once. |
| **Share Context** | Compacts the current agent's conversation into a focused summary, then sends that summary to a target agent. Like Pipe but always uses a compact summary rather than raw output. |

### 2.6 Prompt History

A scrollable list of every prompt sent to the selected agent, newest at bottom. Each entry shows the first ~60 characters of the prompt text, truncated with ellipsis.

- **Click** a prompt to open it in the Prompt Panel (Section 4) pre-filled, ready to edit and resend.
- **Right-click** (or press a modifier key) for options: resend as-is, edit-and-resend, copy to another agent's prompt queue.
- Sourced from the agent's JSONL transcript via `bridge.read_log()`, filtered to `type: "user"` entries.

---

## 3. Agent Creation Wizard

Triggered by `F2`. Renders inline in the right pane (replaces agent detail temporarily).

```
┌─ New Agent ────────────────────────┐
│                                    │
│  Name     [agent-04-            ]  │
│  Model    [▼ opus              ]   │
│  Role     [▼ (none)            ]   │
│           populated from           │
│           .claude/agents/*.md      │
│  Mode     ○Default ○AcceptEdits    │
│           ○Plan    ○Auto           │
│  Color    [■ ■ ■ ■ ■ ■ ■ ■]      │
│  CWD      [C:/Users/lester/proj ]  │
│                                    │
│  [Create]  [Cancel]                │
└────────────────────────────────────┘
```

### Naming Conventions

The **Name** field is pre-populated but fully editable. The auto-generated name follows this pattern:

**With a role selected:** `{role}-{NN}`
- Examples: `researcher-01`, `implementer-02`, `auditor-01`
- The number increments per role across the lifetime of the state file (not just active agents). If you've created and retired three researchers, the next one is `researcher-04`.
- The role slug is derived from the role template filename: `researcher.md` becomes `researcher`, `code-reviewer.md` becomes `code-reviewer`.

**Without a role (none):** `agent-{NN}-{word}`
- Examples: `agent-04-cedar`, `agent-05-flint`, `agent-06-heron`
- The word is drawn from a built-in list of short, distinct, easy-to-say nouns (nature/material themed — no ambiguous or similar-sounding words). The list is ~100 words, cycled sequentially (not random, so names are predictable and don't collide).
- Sample word list: `ash, birch, cedar, dune, elm, flint, grove, heron, iron, jade, knoll, lark, mesa, nova, onyx, peak, quartz, reef, sage, thorn, umber, vale, wren, ...`

**Manual override:** You can always clear the field and type any name. The only constraint is uniqueness — the wizard won't let you create a session with a name that already exists (active or archived).

**On rename:** The rename action in the sidebar (Section 2.5) doesn't re-derive from the pattern — it's a free-text edit. The pattern only applies at creation time.

### Role Templates

The **Role** dropdown is populated by scanning `.claude/agents/*.md` files. Each file defines a system prompt fragment that gets prepended to the agent's first message (or injected via `--system-prompt` if Claude Code supports it, otherwise sent as the first user message).

A role template is a plain markdown file with optional YAML frontmatter:

```yaml
---
name: Researcher
description: Explores codebases, reads docs, reports findings
default_model: opus
default_mode: auto
---

You are a research agent. Your job is to explore, read, and report.
Always write findings to the shared scratchpad.
Never modify code directly.
```

If the template specifies `default_model` or `default_mode`, the wizard pre-fills those fields (but they remain editable). The `description` field shows as a tooltip or subtitle in the dropdown.

### Color Assignment

Colors are auto-assigned from a rotating palette of 8 visually distinct terminal-safe colors: red, blue, green, yellow, magenta, cyan, orange, white. The wizard picks the first unused color. You can override by clicking a different swatch.

If all 8 are in use, the wizard reuses colors (starting from the beginning). The color picker always shows all 8 regardless.

### CWD Field

Pre-filled with the workspace default CWD (set via `bridge.set_cwd()` or from the state file). Accepts Windows paths (`C:\Users\lester\project`) or WSL paths (`/home/lester/project`) — the bridge handles translation.

---

## 4. Prompt Panel

Triggered by `F5`. Renders inline in the right pane with two tabs: **Compose** (free-text) and **Library** (saved templates).

### Compose Tab

```
┌─ Prompts ──────────────────────────┐
│  [Compose]  [Library]              │
│  ──────────────────────────        │
│                                    │
│  ┌──────────────────────────────┐  │
│  │                              │  │
│  │  (multi-line text area)      │  │
│  │  paste prompt here           │  │
│  │                              │  │
│  │                              │  │
│  └──────────────────────────────┘  │
│                                    │
│  Target [▼ researcher         ]    │
│                                    │
│  [Send] [Clear] [Queue]           │
└────────────────────────────────────┘
```

- **Text area** supports multi-line input. Paste works (Ctrl+V or terminal paste). No special formatting — raw text, sent as-is to the target agent via `bridge.send()`.
- **Target dropdown** lists all active agents. Defaults to whichever agent is currently selected in the graph.
- **Send** dispatches immediately. If the agent is busy (status = "generating"), the prompt is queued automatically and a notice appears.
- **Clear** empties the text area.
- **Queue** explicitly adds the prompt to the target agent's queue without sending. Queued prompts auto-send in order when the agent reaches idle state (detected via `bridge.wait_idle()` polling).

### Library Tab

```
┌─ Prompts ──────────────────────────┐
│  [Compose]  [Library]              │
│  ──────────────────────────        │
│                                    │
│  > analyze-codebase.md             │
│    review-pr.md                    │
│    property-research.md            │
│    ward-estate-attom.md            │
│                                    │
│  ┌─ Preview ───────────────────┐   │
│  │ Analyze the codebase for    │   │
│  │ {{focus_area}} and report   │   │
│  │ findings to scratchpad.     │   │
│  └─────────────────────────────┘   │
│                                    │
│  Fill: focus_area [auth module  ]  │
│  Target [▼ researcher         ]    │
│  [Send] [Queue]                    │
└────────────────────────────────────┘
```

- **Template list** is populated by scanning `~/.claude/prompts/*.md` (or the project's `prompts/` folder — configurable in state file). Each file is one reusable prompt.
- **Preview pane** shows the full text of the selected template. Template variables use `{{variable_name}}` syntax — double curly braces, no spaces inside.
- **Fill fields** appear dynamically below the preview, one per `{{variable}}` found in the template. Type a value and it gets substituted before sending.
- **Send/Queue** work the same as in Compose but with the filled template text.

Templates are plain text files. No frontmatter required, though you could add it for organization:

```markdown
---
description: Broad codebase analysis with configurable focus
variables: [focus_area]
---

Analyze the codebase for {{focus_area}} and report findings to the scratchpad.
Include: file structure, key patterns, potential issues.
```

---

## 5. Broadcast Panel

Triggered by `F3`. Renders inline in the right pane.

```
┌─ Broadcast ────────────────────────┐
│                                    │
│  ☑ researcher                      │
│  ☑ implementer                     │
│  ☐ auditor                         │
│                                    │
│  ┌──────────────────────────────┐  │
│  │ Stop current work and        │  │
│  │ report status to scratchpad  │  │
│  └──────────────────────────────┘  │
│                                    │
│  [Send to checked]                 │
└────────────────────────────────────┘
```

A streamlined interface for sending the same prompt to multiple agents simultaneously. Uses `bridge.broadcast()` under the hood.

- **Agent checklist** shows all active agents with checkboxes. All are checked by default. Toggle individually or use a "Select All / None" shortcut.
- **Text area** is the same multi-line input as the Compose tab. The same text goes to every checked agent.
- **Send to checked** dispatches immediately to all checked agents in parallel. Agents that are busy get the prompt queued (same behavior as individual send).

**Typical use:** Interrupt all agents to report status, pivot the whole fleet to a new task, or send a coordination message ("agent-02 found X, update your approach").

---

## 6. Context Sharing — Link Types

When you click `[Link To →]` and select a target, you define the link behavior:

```
┌─ Link: researcher → synthesizer ───┐
│                                     │
│  Trigger                            │
│  ○ On idle (agent finishes)         │
│  ○ On file change                   │
│  ○ Manual only                      │
│                                     │
│  What to send                       │
│  ○ Compact summary of output        │
│  ○ Last N lines of output           │
│  ○ Contents of file: [         ]    │
│  ○ Custom prompt: [            ]    │
│                                     │
│  [Save Link] [Delete Link]          │
└─────────────────────────────────────┘
```

Links are persistent, named connections between two agents. They appear as directed edges in the dependency graph (Section 2.1). The dashboard's orchestration loop watches for each link's trigger condition and fires the payload automatically.

### Trigger Types

| Trigger | How it works |
|---------|-------------|
| **On idle** | The dashboard polls the source agent's status. When it transitions from "generating" to "idle", the link fires. Uses `bridge.status()` polling, same mechanism as `wait_idle()`. |
| **On file change** | The dashboard watches a specified file path (via polling or inotify). When the file's mtime changes, the link fires. Useful for scratchpad-mediated communication or when an agent writes output to a known file. |
| **Manual only** | The link exists in the graph (visible as an edge) but only fires when you explicitly click it. Useful for "I want to be able to pipe A→B but only when I decide." |

### Payload Types

| Payload | What gets sent to the target |
|---------|------------------------------|
| **Compact summary** | Reads the source agent's recent output via `bridge.scrollback()`, then wraps it in a prompt asking the target to treat it as context. Something like: "The researcher agent produced the following output: [scrollback]. Use this as context for your next task." |
| **Last N lines** | Raw last N lines from `bridge.read()`. No wrapping — just the text. Good for short, structured output. |
| **File contents** | Reads a specified file path and sends the contents. The file path is configured when creating the link. |
| **Custom prompt** | A free-text prompt template that gets sent as-is. Can include `{{source_output}}` as a variable that gets replaced with the source agent's recent output. |

### Link Lifecycle

- Links persist in `awl-bridge-state.json` and survive dashboard restarts.
- Deleting a link removes the edge from the graph and stops the trigger watch.
- A link to a retired/closed agent is automatically disabled (shown as a dashed edge in the graph).
- Links are one-directional. To create a bidirectional flow, create two links (A→B and B→A), though this risks infinite loops — the dashboard should detect and warn about cycles.

---

## 7. Tab Identity

Each agent's tmux tab gets a colored dot matching its assigned color.

```
tmux status bar:

  ● Dashboard │ ● researcher │ ● implementer │ ● auditor │
   (white)       (red)          (blue)          (green)

  Active tab = bold/highlighted
  Inactive tab = dim with colored dot
```

The same color is used for: the graph node, the tmux tab dot, and the pane border when viewing that agent's tab. One color, everywhere.

**How tab colors work in tmux:** tmux supports per-window status formatting via `set-window-option window-status-format`. The dashboard sets this for each session/window when an agent is created or its color changes. The colored dot is a Unicode circle character (`●`) rendered in the agent's assigned terminal color (ANSI 256 or true color, depending on terminal support).

**Dashboard tab** is always white/neutral and always Tab 0 (leftmost). Agent tabs appear in creation order to the right.

---

## 8. Hotkeys

Minimal. Hardcoded. Always visible in footer. Every hotkey has a clickable button equivalent.

| Key | Action | Button |
|-----|--------|--------|
| `F1` | Help overlay — shows all hotkeys, brief descriptions, and tips | `[F1 Help]` |
| `F2` | New agent wizard — opens creation form in right pane | `[F2 New Agent]` |
| `F3` | Broadcast panel — multi-agent send interface | `[F3 Broadcast]` |
| `F4` | Toggle activity log — show/hide the event stream | `[F4 Log]` |
| `F5` | Prompt panel — compose or pick from library | `[F5 Prompts]` |
| `Tab` | Cycle selected agent in graph (next node) | Click node in graph |
| `Enter` | Jump to the selected agent's live tmux tab | Double-click node |
| `Esc` | Return to dashboard from any agent tab, or dismiss current panel | — |

**Design principle:** The footer is always visible. No hidden modes. If a panel is open in the right pane (wizard, broadcast, prompts), the footer still shows and all hotkeys still work — pressing F2 while F5 is open switches to the wizard.

---

## 9. Feature Checklist

### 9.1 Agent Lifecycle
- [ ] 9.1a  Create with wizard (name, model, role, mode, color, cwd)
- [ ] 9.1b  Clone (with/without full context toggle)
- [ ] 9.1c  Rename (inline edit in sidebar)
- [ ] 9.1d  Retire (compact → save summary → close → mark archived)

### 9.2 Context Sharing
- [ ] 9.2a  Dependency graph (visual node-edge display)
- [ ] 9.2b  Create/edit/delete links between agents
- [ ] 9.2c  Context pipe (one-shot: capture A's output → send to B)
- [ ] 9.2d  Context snapshot (compact with focus → share summary to B)
- [ ] 9.2e  Shared scratchpad (live file preview on dashboard)
- [ ] 9.2f  Linked file watches (file change triggers send to target)

### 9.3 Dashboard
- [ ] 9.3a  Agent graph with status in each node
- [ ] 9.3b  Agent detail sidebar (all params, controls, history)
- [ ] 9.3c  Activity log (collapsible timestamped events)
- [ ] 9.3d  Context bar per agent (single bar, percentage, no cost)

### 9.4 Prompt Management
- [ ] 9.4a  Compose panel (multi-line text area, paste, clear, send)
- [ ] 9.4b  Prompt library (load from `~/.claude/prompts/`, template fill)
- [ ] 9.4c  Prompt history per agent (resend, edit-resend, copy to other)
- [ ] 9.4d  Broadcast (checkboxes + text area → send to checked)
- [ ] 9.4e  Prompt queue (queue multiple, auto-send on idle)
- [ ] 9.4f  Clipboard paste support (text + image file paths)

### 9.5 Per-Agent Parameters (sidebar controls)
- [ ] 9.5a  Name (editable text)
- [ ] 9.5b  Model (dropdown, locked after session start)
- [ ] 9.5c  Permission mode (radio buttons, live-changeable)
- [ ] 9.5d  Effort level (3-position toggle, writes back)
- [ ] 9.5e  Role template (dropdown, locked after session start)
- [ ] 9.5f  Color (palette picker)
- [ ] 9.5g  Context bar (read-only)
- [ ] 9.5h  Compact / Clear buttons
- [ ] 9.5i  MCP server toggles (checklist, locked after session start)

### 9.6 Visual Identity
- [ ] 9.6a  Colored dots on tmux tab bar per agent
- [ ] 9.6b  Matching color in graph nodes
- [ ] 9.6c  Matching color on pane borders

### 9.7 Hotkeys & Footer
- [ ] 9.7a  F1-F5 + Tab/Enter/Esc (hardcoded, always in footer)
- [ ] 9.7b  Every hotkey has a clickable button equivalent

---

## 10. Build Phases

| Phase | Scope | Delivers |
|-------|-------|----------|
| **1** | Dashboard shell + graph + sidebar + agent creation + tab colors | Visible agent management replaces raw tmux |
| **2** | Prompt compose + library + broadcast + queue | Eliminates paste errors, enables prompt reuse |
| **3** | Context links + pipes + scratchpad + file watches | Multi-agent becomes orchestrated |
| **4** | Full parameter controls + prompt history + activity log polish | Refinement based on real usage patterns |

## [EDIT] Agent Tab (missing before)

See: C:\Users\lester\MeDocuments\AppData\Anthropic\claude-code-sandbox\docs\temp\agent-tab-diagram.png