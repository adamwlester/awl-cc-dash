# AWL Multi-Agent Dashboard — System Architecture

> **What this document is.** The ground-truth reference for **how the system is wired right now** — the
> processes, the boundaries between them, and the control/data flow that ties them together. It is the
> *system* counterpart to [`design/DESIGN.md`](../design/DESIGN.md) (which owns the **UI/UX intent**) and
> [`DEVLOG.md`](../DEVLOG.md) (which owns the **why-it-changed history**). When you need "what talks to what,
> and where does that code live," start here; for pixels and interaction intent read DESIGN.md, and for the
> chronology read the DEVLOG.
>
> **What it is *not*.** Not a visual spec (that's DESIGN.md + the `design/` mockup), not a task list, and not
> a decisions log. The **decided target behaviours** it references are specified in the decisions tracker,
> [`dev/notes/open-system-decisions-2026-06-29.md`](../dev/notes/open-system-decisions-2026-06-29.md) (the
> `OD-01 … OD-23` items) — this doc cites those IDs rather than restating them.
>
> **Sources & freshness.** Written against the code as it stands (sidecar `v0.3.0`), grounded in a direct read
> of `frontend/`, `sidecar/`, and `bridge/`. Two older notes describe a **pre-integration** snapshot and are
> superseded on the points below: [`dev/notes/coverage-map.md`](../dev/notes/coverage-map.md) (capability→reality
> map, written before the backend integration pass landed) and the "largely one `App.tsx`" line in the root
> `CLAUDE.md`. Where they disagree with this doc, trust the code.

---

## 1. System at a glance

The dashboard is a **four-tier desktop application** that lets one operator run and coordinate many real
Claude Code agents from a single window, **without touching the raw CLI**:

1. **Frontend** — an **Electron + React** desktop app (`frontend/`). One window, three resizable panes. Talks
   to the sidecar over **HTTP + Server-Sent Events**; holds no agents itself.
2. **Sidecar** — a **FastAPI** service (`sidecar/`) on `127.0.0.1:7690`. The brain: it owns session state, the
   merged cross-agent **event bus**, the per-agent **prompt queue**, the **hook** callback endpoints, the
   **inbox**, **linking**, the **scratchpad**, the **library**, **settings** reads/writes, and the **console**
   command router. It drives agents through a pluggable **driver seam**.
3. **Driver seam** — an abstraction (`sidecar/drivers/`) with two implementations: **`bridge`** (the default and
   primary path — real Claude Code TUIs) and **`sdk`** (a limited-use in-process engine for non-interactive
   utility passes).
4. **Bridge** — a Python package (`bridge/`) that drives **detached Claude Code TUI sessions in tmux inside
   WSL2**, reading them through two channels (screen `capture-pane` + the JSONL transcript) and never needing a
   window. Each agent is a genuine `claude` process.

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│  WINDOWS HOST (real laptop)                                                       │
│                                                                                   │
│  ┌───────────────────────────┐     HTTP + SSE      ┌────────────────────────────┐ │
│  │  Electron app  (frontend/) │  ◄──────────────►  │  Sidecar  (sidecar/)       │ │
│  │  main → preload → renderer │   127.0.0.1:7690   │  FastAPI · v0.3.0          │ │
│  │  React · 3-pane UI         │                    │  SessionState · event bus  │ │
│  │  SSE /events + poll loops  │                    │  queue · hooks · inbox     │ │
│  └───────────────────────────┘                    │  links · scratch · library │ │
│                                                    └───────────┬────────────────┘ │
│                                                                │ driver seam       │
│                                                  ┌─────────────┴─────────────┐     │
│                                          bridge (DEFAULT)              sdk (opt-in) │
│                                                  │                           │     │
│                                                  ▼                           ▼     │
│                                      ┌───────────────────────┐   in-process Claude │
│                                      │ bridge/  (TmuxBridge)  │   Agent SDK client  │
│                                      │ capture-pane + JSONL   │   (Revise/Summarize)│
│                                      │ ~1s poll · WT tab opt-in│                    │
│                                      └───────────┬───────────┘                      │
│        agent hooks POST back                     │  wsl -d Ubuntu -- bash -c ...    │
│   http://<wsl-gateway>:7690/internal/hooks/…     │                                  │
│        ▲                                         ▼                                  │
│ ─ ─ ─ ─│─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ │
│  WSL2  │ (Ubuntu)                     ┌──────────▼───────────┐                      │
│        └──────────────────────────── │  tmux server         │                      │
│                                       │   ├ agent-1 (claude) │  each session =      │
│                                       │   ├ agent-2 (claude) │  a real Claude Code  │
│                                       │   └ agent-N (claude) │  TUI + its own       │
│                                       └──────────────────────┘  <session-id>.jsonl  │
└─────────────────────────────────────────────────────────────────────────────────┘
```

**The one-line mental model:** *the bridge is the backbone, the sidecar is the brain, the Electron app is the
skin.* Agents always run on the bridge; the sidecar aggregates and coordinates them; the frontend renders and
commands. The **defining capability** the whole stack exists to serve is **context-sharing between agents**
(links, a shared scratchpad, agent-to-agent conversation) — see [§6](#6-the-coordination-spine-cross-cutting).

---

## 2. Runtime topology & processes

| Process | Where it runs | Started by | Talks to |
|---------|---------------|------------|----------|
| **Electron main** | Windows | `start-dashboard.bat` / `electron-vite dev` | Creates the `BrowserWindow`; loads the renderer. **Does not spawn the sidecar.** |
| **Renderer (React)** | Windows (Chromium) | Electron main | Sidecar over HTTP/SSE via `window.awl.sidecarUrl` (`http://127.0.0.1:7690`). |
| **Sidecar (FastAPI/uvicorn)** | Windows | `start-dashboard.bat` (separately) | The driver seam; and receives **hook callbacks** from agents inside WSL2. |
| **tmux server + `claude` sessions** | WSL2 (Ubuntu) | The `bridge` driver, on session create | Driven by tmux `send-keys`; read by `capture-pane` + JSONL. |

Two boundaries matter most:

- **Frontend ↔ sidecar** is a plain **localhost HTTP + SSE** boundary. The Electron app is a thin client; it
  could be replaced by a browser tab (the code even falls back to `http://127.0.0.1:7690` when
  `window.awl` is absent). `start-dashboard.bat` launches the sidecar and the Electron app together, but they
  are independent processes.
- **Sidecar ↔ agents** crosses the **Windows→WSL2** boundary. Outbound (drive the agent) goes
  `sidecar → bridge → wsl -d Ubuntu -- bash -c '…' → tmux`. Inbound-by-poll (read the agent) is
  `capture-pane` + the transcript JSONL. Inbound-by-push (hooks) is the agent **POSTing back** to the sidecar
  over HTTP — which requires solving WSL2 networking (see [§5.4](#54-the-bridge-package-bridge-and-the-windowswsl2-seam)).

---

## 3. Frontend — Electron + React (`frontend/`)

An **electron-vite** project with the three standard process layers.

### 3.1 Process layers
- **Main** — [`frontend/src/main/index.ts`](../frontend/src/main/index.ts): creates one `BrowserWindow`
  (1440×900, dark chrome), wires the preload bridge (`contextIsolation: true`, `nodeIntegration: false`), and
  loads the renderer. It is deliberately **frontend-only** — it does **not** launch the Python sidecar.
- **Preload** — [`frontend/src/preload/index.ts`](../frontend/src/preload/index.ts): a minimal context bridge
  that exposes `window.awl.sidecarUrl = 'http://127.0.0.1:7690'`. No RPC to main; all data flow is HTTP to the
  sidecar.
- **Renderer** — React 19 under [`frontend/src/renderer/`](../frontend/src/renderer/).

### 3.2 Renderer structure
[`App.tsx`](../frontend/src/renderer/App.tsx) is the orchestrator: it owns the merged event stream, the polling
loops, and the resizable **three-pane shell** (Agent | Team Graph + Work | Team Feed + Prompt) that mirrors the
DESIGN.md layout. It is **componentized**, not one monolith:

| Component | File | Role |
|-----------|------|------|
| `AgentPanel` | `AgentPanel.tsx` | Left pane — Details / Create / Console for the focused agent |
| `TeamGraph` | `TeamGraph.tsx` | Agent cards (status badge, identity, ctx/turns bars, subagents, run-strip) |
| `TeamFeed` | `TeamFeed.tsx` | Right-top — merged Messages + Inbox |
| `PromptPanel` | `PromptPanel.tsx` | Right-bottom — Compose (send-timing, templates, revise) + History |
| `WorkPanel` | `WorkPanel.tsx` | Middle-bottom — Library + Links + Scratch |
| `Settings` | `Settings.tsx` | Step-in overlay — Usage / MCP / Plugins / Config |
| `EventRenderer` | `events.tsx` | Renders merged-bus events into message/tool/thinking blocks |
| `api.ts` | `api.ts` | The HTTP/SSE client + the whole endpoint catalog |
| `tokens.ts` / `ui.tsx` | — | Inline design tokens + shared primitives (neobrutalism) |

**State** is plain React `useState` in `App.tsx` (no Redux/Zustand). Agent/session/usage/inbox/link data is
held locally and refreshed by polling; the message feed is merged and de-duplicated on the client.

### 3.3 Transport — SSE bus + targeted polling
The frontend reads agent state two ways:

- **Merged event bus (push):** on load it backfills via `GET /events/history` then opens the **SSE stream**
  `GET /events`. Events are keyed by their stable `id`, ordered by `seq`, de-duplicated in a `seenRef` set, and
  capped (~4000). This is the OD-01 envelope end of the pipe.
- **Targeted polling (pull)** for readouts that aren't event-shaped, each on its own cadence:
  `/health` (5s) · `/sessions` + `/usage` + `/inbox` + `/links` (2s) · `/sessions/{id}/checklist` +
  `/marquee` (3s) · `/subagents` (4.5s) · the focused agent's `/context` (~1.2s loop) · `/scratch` (3s).

> **Historical note:** the pre-integration UI polled `/history` every 800 ms with array-index keys. That is
> gone — the current renderer consumes the merged SSE bus with stable ids. The `coverage-map.md` description of
> 800 ms `/history` polling reflects the old snapshot.

### 3.4 Visual lag vs. the mockup (intentional)
The React app is **functionally** wired to the full backend but **visually trails** the `design/` mockup — e.g.
16 agent colours (vs. the mockup's 25), the Console tab still stubbed in places, and some controls are honest
no-ops for bridge-blocked features. This gap is by design: **OD-21** parks the "port the React app up to the
finished mockup/tokens" work until design churn approaches zero. The mockup is the visual target; the React app
is the working client.

---

## 4. Sidecar — the coordinator (`sidecar/`)

A **FastAPI** app ([`sidecar/main.py`](../sidecar/main.py)), `title="AWL Dashboard Sidecar"`, `version 0.3.0`,
served by uvicorn on `0.0.0.0:7690` (host overridable via `AWL_SIDECAR_HOST`). It is the single source of
coordination truth: everything cross-agent lives here, not in the frontend and not in the bridge.

### 4.1 Core in-memory state
- **`SessionState`** (per agent) holds `status` (`connecting|idle|running|error|closed`), the local `events`
  list, the SSE `subscribers`, the **`prompt_queue`** (a disposition-ordered deque, *not* strict FIFO), the
  `held` staging slot, and reply-to bookkeeping (`answering_source`/`answering_link`).
- **Event bus** (`eventbus.py`) — a bounded global ring (`GLOBAL_RING`, default 5000, `AWL_EVENT_RING_MAX`) plus
  a set of global SSE subscribers. `stamp()` assigns every event its envelope (see [§6.1](#61-the-event-envelope-od-01--od-22)).
- **Hook bus / inbox / caps** — small modules (`hookbus.py`, `inbox.py`) backing the OD-02 inject channel, the
  OD-09 inbox, and the OD-10 cap poll-loop (runs every ~3s).

### 4.2 Endpoint surface (grouped by concern)
All are implemented (no stubs); bridge-dependent ones degrade gracefully when the bridge is unavailable, and
capability-gated ones return `400` when the active driver can't do the thing.

| Concern | Endpoints | OD |
|---------|-----------|-----|
| **Health / sessions** | `GET /health` · `POST /sessions` · `GET /sessions[/{id}]` · `DELETE /sessions/{id}` (`?hard=true` → permanent wipe + tombstone) | OD-19 |
| **Messaging** | `POST /sessions/{id}/send` (disposition: now/next/queue/hold/inject) · `GET /sessions/{id}/history` | OD-02 |
| **Merged feed** | `GET /events` (SSE) · `GET /events/history?since=<seq>` — both with server-side From/To filter | OD-01/22 |
| **Hook channel** | `POST /internal/hooks/{post-tool-use,stop,plan,decision}/{agent}` | OD-02/09 |
| **Inbox** | `GET /inbox` · `POST /inbox/{agent}/{item}/resolve` | OD-09 |
| **Linking** | `POST/GET /links` · `DELETE /links/{id}` · `POST /links/{id}/kickoff` | OD-04…08 |
| **Scratchpad** | `GET /scratch` · `POST /scratch` (posts + pushes delta to running co-located agents) | OD-17 |
| **Library** | `GET /library/documents` · `GET /library/document` · `GET/POST /library/reviews` | OD-15 |
| **Console** | `GET /console/catalog` · `POST /sessions/{id}/console/run` | OD-20 |
| **Readouts** | `GET /sessions/{id}/{context,subagents,checklist,marquee}` · `GET /usage` | OD-11/12/13 |
| **Session control** | `POST /sessions/{id}/{interrupt,model,mode,permission,effort,fast,thinking}` | — |
| **Settings** | `GET /settings/{read,account,config,mcp,plugins}` · `POST /settings/write` (confirm-gated) | OD-18 |
| **Templates** | `GET/POST /templates` · `DELETE /templates/{id}` | OD-16 |
| **Utility LLM** | `POST /utility/{revise,summarize}` — routed through the **`sdk`** driver, not the bridge | OD-16 |
| **Assets** | `GET /assets/agent-icons/{name}?color=` — recolorable agent SVGs | OD-03 |

### 4.3 Serialization
[`sidecar/drivers/serialize.py`](../sidecar/drivers/serialize.py) normalizes both driver worlds into one event
shape: it maps SDK message classes (`AssistantMessage`, `UserMessage`, …) and content blocks (`text`,
`thinking`, `tool_use`, `tool_result`) to the frontend's event/`type` vocabulary, with depth-limited safe
recursion. The bridge driver maps already-Anthropic-format JSONL blocks with minimal transform, adding the
`anchor` (JSONL uuid) + `source_kind` used for OD-01 dedup.

---

## 5. Driver seam & the bridge

### 5.1 The seam (`sidecar/drivers/`)
[`base.py`](../sidecar/drivers/base.py) defines `AgentDriver`: the abstract trio `start()` / `send()` /
`events()` (an async iterator of stamped events), plus optional, default-no-op capabilities (`interrupt`,
`set_model`, `set_mode`, `set_effort`, `set_fast`, `set_thinking`, `answer_permission`, `get_context_usage`,
`get_subagents`, `close`). Each driver advertises a `CAPABILITIES` set; the sidecar checks it and returns `400`
for anything unsupported (an honest signal, never a fake-live control).

**Selection** ([`drivers/__init__.py`](../sidecar/drivers/__init__.py)) resolves in priority order:
1. an explicit per-session `driver` field on the create request, else
2. the `AWL_DRIVER` env var, else
3. **`bridge`** — the default when nothing is named.

An explicitly-named **unknown** driver falls back to **`sdk`** (with a warning) rather than crashing.

### 5.2 `bridge` driver (default, primary)
[`drivers/bridge.py`](../sidecar/drivers/bridge.py). `CAPABILITIES = {interrupt, context, permission, resume,
set_model, set_effort, subagents}`. On `start()` it creates (or resumes) a tmux session via `TmuxBridge`,
applies the agent's **per-agent launch config** (permission mode, `--allowedTools`/`--disallowedTools`,
permission rules, plugins, MCP scope), installs the **hook settings** pointing back at the sidecar, and persists
a runtime record so the session survives a sidecar restart. Its `events()` is the **~1 s poll** that reads the
transcript + screen and emits stamped events — this single loop is the shared seam for the event stream, the
queue's idle/turn-boundary detection, and inbox raising. Notably **not** advertised: `set_mode`, `set_fast`,
`set_thinking` (bridge-blocked — see [§9](#9-build-status--honest-boundaries)).

### 5.3 `sdk` driver (limited-use, opt-in)
[`drivers/sdk.py`](../sidecar/drivers/sdk.py). `CAPABILITIES = {set_model, set_mode, context, interrupt}`. Runs
an in-process `ClaudeSDKClient` — **ephemeral** (doesn't outlive the sidecar, no runtime record). It is reserved
for **non-interactive utility passes** that need no real terminal — today the Revise / Summarize LLM passes
behind `/utility/*`. It is **not** a whole-system fallback; agents always run on the bridge.

### 5.4 The bridge package (`bridge/`) and the Windows/WSL2 seam
[`bridge/bridge.py`](../bridge/bridge.py) exposes `TmuxBridge` (~20 documented methods: create, send, keys,
read, read_log, list, show, close, shutdown, rename, resume, status, batch_create, broadcast, interrupt,
scrollback, watch, wait_idle, export, mcp_sync, plus `set_cwd`/`set_model`). Key mechanics:

- **Detached creation.** `create()` runs `tmux new-session -d -s <name> … 'claude --session-id <uuid> …'`. The
  `-d` means **no window** — sessions are always **tab-less**. A Windows Terminal tab opens **only** on an
  explicit `show=True` / `show()` (a deliberate human attach), never as a side effect. It pins a
  `--session-id` uuid so each agent's transcript is collision-proof, and auto-clears the folder-trust /
  bypass-mode startup gates.
- **Two-channel observation.** The bridge **samples, it does not stream.** `status()` / `_detect_state()`
  classify the screen from `capture-pane` into `idle | generating | permission_prompt | unknown`;
  [`transcript.py`](../bridge/transcript.py) resolves `cwd → project-hash → <session-id>.jsonl` and parses the
  JSONL for message content. Everything the dashboard knows comes from these two channels, polled ~1 s.
- **Windows↔WSL2 translation.** [`paths.py`](../bridge/paths.py) converts `C:\…` ↔ `/mnt/c/…`; per-agent launch
  config is materialized to `~/.awl-agents/<name>/` inside WSL (kept out of real `~/.claude`); large payloads
  are piped via stdin to dodge the ~32 KB command-line limit.
- **The hook callback loop.** WSL2 NAT means `localhost` from WSL does **not** reach the Windows host. So the
  bridge resolves the **default-gateway IP** (`ip route show default`, cached) and builds
  `http://<gateway>:7690/internal/hooks/…` as the URL each agent's hooks POST to. This is what lets a *running*
  agent be injected mid-turn and lets Plan/Decision tool calls be intercepted — the inbound-push half of the
  coordination spine. (Hooks are best-effort: if the IP can't resolve, launch still succeeds.)
- **MCP sync.** `mcp_sync()` translates the Windows MCP registry into a WSL-usable one (`cmd /c npx → npx`,
  skip Windows-only servers, HTTP servers pass through), merging into WSL `~/.claude.json`.
- **Registry reads.** [`registry.py`](../bridge/registry.py) backs the Settings tab's read side (MCP servers,
  plugins via `claude plugin list --json`, config fields) across user/project scopes.

---

## 6. The coordination spine (cross-cutting)

The features that make this "more than terminals in a grid" all ride on a small set of sidecar-owned
primitives. These are the decided architecture (the `OD-*` tracker) as **built** in `v0.3.0`.

### 6.1 The event envelope (OD-01 + OD-22)
Every event, from either driver, is stamped by `eventbus.stamp()` into one envelope:
```
{ id, agent_id, seq, ts, type, source, recipients[], …payload }
```
- **`id`** is a deterministic composite `"{agent_id}:{source_kind}:{anchor}"` — `source_kind` is `t`
  (transcript, `anchor` = JSONL uuid) or `s` (synthesized). Determinism makes re-polls and reconnects **dedup
  to no-ops**.
- **`seq`** is a separate monotonic counter assigned at emit — the **ordering** key (never parse the id for
  order).
- **`source`** + typed **`recipients[]`** (`user | <agent-id> | scratch`, default `[user]`) are the OD-22
  addressing that drives the From/To filter, Sent/Received direction, and link delivery. `recipients` is
  *routing*, not visibility — every event still shows in the operator's feed.

The bus is a **bounded ring, not a stored mega-log**: the per-agent JSONL transcripts on disk stay the source
of truth; the sidecar keeps a rolling buffer and the UI backfills on scroll; From/To filtering is applied
server-side.

### 6.2 Prompt queue + delivery dispositions (OD-02)
Each `SessionState` owns an **ordered** queue driven by the bridge's `generating→idle` transition. A `send`
carries a disposition: **Queue** (append-tail, flush at idle) · **Next** (insert-head) · **Now** (`interrupt()`
then flush) · **Hold** (park in the staging slot, manual release only) · **Inject** (routed via the hook
channel, not this queue). This is what replaced the old "`/send` to a busy agent `409`s and drops it" behaviour.

### 6.3 The hook channel (OD-02 / OD-09)
Every bridge agent launches with `PostToolUse` + `Stop` + `PreToolUse(ExitPlanMode|AskUserQuestion)` HTTP hooks
pointed at the sidecar (via the gateway URL from [§5.4](#54-the-bridge-package-bridge-and-the-windowswsl2-seam)):
- **PostToolUse** drains any pending **inject** for that agent and returns it as `additionalContext` — a running
  agent receives it mid-turn at the next safe tool boundary, **without stopping**. Durable + ack-on-2xx.
- **Stop** backstops the no-tool-call case so a pure-text turn still catches an inject at turn end.
- **Plan / Decision** PreToolUse hooks surface the agent's `ExitPlanMode` / `AskUserQuestion` tool calls to the
  **Inbox** even though they're invisible to screen-state — closing the gap the bridge otherwise can't see.

### 6.4 Linking / reply-to (OD-04…08)
A **link** forwards context between two agents. The sidecar models the **reply-to** relationship: when a source
finishes the turn answering a linked peer's inbound (detected at the idle turn-boundary), it routes that turn's
output back to the inbound's sender by enqueuing on the peer's queue — a fire is the *completion of a reply*, not
a blind broadcast. `/links/{id}/kickoff` starts a conversation; **End-After** caps (default 25 exchanges) and
strict one-inbound-in-flight keep bidirectional links from running away.

### 6.5 Inbox, caps, identity, checklist (OD-09/10/03/11)
- **Inbox** (`/inbox`): one card per blocked agent, typed **Error · Warning · Permission · Plan · Decision**,
  raised over two mechanisms — screen-state (Permission, Error/stall) and the hook channel (Plan, Decision).
- **Lifecycle caps** (OD-10): a ~3s poll compares live turns / context-% to per-agent stored caps and raises a
  **notify-only** Warning; it never auto-kills.
- **Identity** (OD-03): role·number·name·color·icon assigned at create and persisted in the runtime store;
  icons served recolored from `assets/icons/agents/` via `/assets/agent-icons/`.
- **Checklist / marquee** (OD-11/12): an agent self-reports a step checklist (parsed from its transcript →
  `done ÷ total` run-strip); the marquee is a low-fidelity liveness tail of recent output. Both ride the
  existing stream — no new channel.

---

## 7. Storage & scoping (OD-23)

One rule: **dashboard data lives with the dashboard; project data lives with the project; teams are reusable and
live with the dashboard.** Three homes plus two Claude-Code-owned locations the dashboard only *surfaces*:

| Home | Where | Holds |
|------|-------|-------|
| **🏠 Dashboard runtime store** | `sidecar/runtime/` (`sessions.json`; override `AWL_SIDECAR_RUNTIME`) | Per-agent **identity**, which **sessions** exist (+ tmux binding, model, mode, cwd, `claude_session_id`, launch config), saved **Setups** (rosters), templates. Reusable, project-agnostic. Survives sidecar restart → drives `reconnect_sessions()`. |
| **📁 Project `.awl/`** | `<project>/.awl/` (inside each agent's `cwd` repo) | The team's **scratchpad** (`scratchpad.md`) and the **plan-review side-store** (`plan-reviews.json`). Travels with the code, WSL-reachable. |
| **👥 Setup** | (a record in the dashboard store) | Only the **roster** — agents, roles/models/identities, links. No docs, no project baked in; loaded onto whatever project you point it at. |
| **Per-agent launch config** | `~/.awl-agents/<name>/` (WSL) | The materialized `--settings` (incl. hook config) + `mcp.json` the bridge writes at launch. Kept out of real `~/.claude`. |
| **Claude Code config** | `~/.claude/`, `<project>/.claude/` | **Surfaced, not owned** — read/edited in place via Library Documents + Settings → Config. |

Code keys off each agent's **`cwd`** as the project root, never a fixed path — so a project's physical location
can change (dev `projects/` today → its own repo at release) with no rearchitecting.

---

## 8. Key end-to-end flows

**Create an agent.** `POST /sessions` → sidecar assigns identity (OD-03) → `bridge` driver `start()` →
`TmuxBridge.create()` runs detached tmux + `claude --session-id <uuid>` in WSL, clears startup gates, installs
hooks → runtime record persisted → the `events()` poll begins → stamped events flow onto the bus → the frontend
renders the new card. **No tab opens.**

**Send while busy.** `POST /sessions/{id}/send {disposition}` → enqueued per OD-02 → on the next
`generating→idle` the head flushes via tmux `send-keys` → the turn's output streams back as stamped events.
(Old behaviour: a `409` drop. Now: queued.)

**Permission round-trip.** Agent hits a tool prompt → bridge screen-state detects the menu, raises a
**Permission** inbox card → operator Approve/Deny in the UI → `POST /sessions/{id}/permission` → bridge answers
the menu via `keys()` → the agent continues. (Binary Approve/Deny only — "Always allow" was removed, OD-14.)

**Agent→agent link fire.** Source finishes replying to a peer's inbound at the idle boundary → sidecar routes
that output to the peer's queue (OD-04) → delivered per the link's trigger → bounded by End-After.

**Scratchpad delta.** `POST /scratch` appends to `<project>/.awl/scratchpad.md` → the post is fed onto the bus →
new content past each agent's read-watermark is pushed to *running* co-located agents mid-turn via the hook
channel (OD-17), or picked up at next run-start for idle ones.

**Resume after sidecar restart.** On startup the sidecar reads `sessions.json`, re-registers each
`claude_session_id` with the bridge, and rebinds to still-alive tmux sessions (`reconnect_sessions()`) — agents
keep running across a sidecar bounce because tmux held them.

---

## 9. Build status & honest boundaries

The stack is **functionally wired end-to-end** — the frontend, sidecar, and bridge together deliver the full
decided OD feature set. Verification maturity varies, and a few things are genuine engine limits.

| State | What |
|-------|------|
| **Live-verified (bridge floor)** | Create / run turns / read feed, permission round-trips, resume, model + effort changes — proven below **and through** the dashboard UI (per `CLAUDE.md` / `DEVLOG.md`). |
| **Built & wired** | The full sidecar OD surface (event bus, queue, hooks, inbox, links, scratchpad, library, settings reads + gated writes, console, templates, utility passes) and the React client that consumes it. Confirm specifics against `DEVLOG.md`. |
| **Visually lagging the mockup** | The React UI trails `design/` (16 vs 25 colours, Console gaps, some no-op controls). Parked by **OD-21** until design churn → zero. |
| **Bridge-blocked (engine limits, honest 400s / fallbacks)** | Mid-run **permission-mode** change (only Shift+Tab cycles) · **`/fast`** + **thinking** toggles · true mid-run **Inject** (degrades to Next/Queue) · run-strip real **%** (barber-pole floor) · subagent **pending-vs-active** · per-agent **cost** (bridge emits none). |

> **Reconciliation note.** [`dev/notes/coverage-map.md`](../dev/notes/coverage-map.md) predates the backend
> integration pass and still describes much of the above as "zero backend" + 800 ms `/history` polling. It's
> useful history for *what the bridge can/can't physically observe*, but for **built vs not** trust this doc and
> the code.

---

## 10. Repo map — where the architecture lives

| Path | Layer |
|------|-------|
| [`frontend/src/main/`](../frontend/src/main/) · [`preload/`](../frontend/src/preload/) · [`renderer/`](../frontend/src/renderer/) | Electron main / preload / React renderer |
| [`frontend/src/renderer/api.ts`](../frontend/src/renderer/api.ts) | The frontend↔sidecar contract (endpoints + SSE + event types) |
| [`sidecar/main.py`](../sidecar/main.py) | FastAPI app, `SessionState`, all endpoints, queue flush, cap loop |
| [`sidecar/eventbus.py`](../sidecar/eventbus.py) · `hookbus.py` · `inbox.py` | Event ring + stamping · inject channel · inbox raising |
| [`sidecar/drivers/`](../sidecar/drivers/) | `base.py` (seam) · `bridge.py` · `sdk.py` · `serialize.py` · `__init__.py` (selection) |
| [`sidecar/runtime_store.py`](../sidecar/runtime_store.py) · `identity.py` | Restart-surviving session records · identity assignment |
| [`bridge/bridge.py`](../bridge/bridge.py) · `transcript.py` · `paths.py` · `mcp.py` · `registry.py` | tmux/WSL2 control · JSONL parsing · path/net translation · MCP sync · Settings reads |
| [`start-dashboard.bat`](../start-dashboard.bat) | Launches sidecar + Electron together |

---

## 11. Related docs

- [`design/DESIGN.md`](../design/DESIGN.md) — UI/UX intent, the three-column layout, every panel, the design
  system. The `design/` mockup is the **visual authority**.
- [`dev/notes/open-system-decisions-2026-06-29.md`](../dev/notes/open-system-decisions-2026-06-29.md) — the
  `OD-01…OD-23` decisions this doc references (the WHAT behind the coordination spine).
- [`dev/notes/coverage-map.md`](../dev/notes/coverage-map.md) — pre-integration capability→reality map; still the
  best reference for **what the bridge can physically observe**.
- [`DEVLOG.md`](../DEVLOG.md) — append-only chronology; the authority on **what was built/verified when**.
