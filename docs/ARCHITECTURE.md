# AWL Multi-Agent Dashboard — System Architecture

> **What this document is.** The ground-truth reference for the **final intended system** — the product
> vision of the AWL Multi-Agent Dashboard, written as settled architecture. It describes how the finished
> system behaves and is wired: the processes, the boundaries between them, the coordination primitives, the
> storage model, and the product decisions that shape all of them, woven into the prose where each part of
> the system is described. **The body text is the contract; the code converges on it.**
>
> **Authority rules.** This doc owns **system intent** (what talks to what, how data moves and persists,
> what every behavior is supposed to be). [`design/DESIGN.md`](../design/DESIGN.md) owns **UI intent**
> (pixels, layout, interaction detail — the `design/` mockup is the visual authority).
> [`DEVLOG.md`](../DEVLOG.md) owns **history** (what changed when, and why). The code converges on this doc
> and on DESIGN.md; when you need chronology, read the DEVLOG.
>
> **The ⚠ Today marker.** Wherever today's code differs from the intended behavior described here, an
> inline marker of the form **"⚠ Today: …"** states current reality at *behavior* level, citing the file and
> symbol involved (e.g. `storage.project_root()` in [`sidecar/storage.py`](../sidecar/storage.py)) — never
> line numbers. A section with no marker is a section where code and intent already agree. The build
> backlog that clears these markers is **§11 (Build backlog & queue)** — the single home for decided,
> buildable work; the body carries the decisions, §11 the queue.
>
> **Churn note.** The doc is still being tuned as the product is; it always reflects the intended *final*
> state, never a build snapshot. **Maintenance rule:** build runs clear Today-markers as they land; decision
> changes edit the body text itself; in both cases `DEVLOG.md` records which of the two happened.

---

## 1. System at a glance

The dashboard is a **four-tier desktop application** that lets one operator run and coordinate many real
Claude Code agents from a single window, **without touching the raw CLI**:

1. **Frontend** — an **Electron + React** desktop app (`frontend/`). One window, three resizable panes.
   Talks to the sidecar over **HTTP + Server-Sent Events**; holds no agents itself.
2. **Sidecar** — a **FastAPI** service (`sidecar/`) on `127.0.0.1:7690`. The brain: it owns session state,
   the merged cross-agent **event bus**, the per-agent **prompt queue**, the **hook** callback endpoints,
   the **inbox**, **linking**, the **scratchpad**, the **library**, **settings** reads/writes, and the
   **console** command router. It drives agents through a pluggable **driver seam**. It is the **single
   source of coordination truth**: everything cross-agent lives here, never in the frontend and never in
   the bridge.
3. **Driver seam** — an abstraction (`sidecar/drivers/`) with two implementations: **`bridge`** (the
   default and primary path — real Claude Code TUIs) and **`sdk`** (a limited-use in-process engine for
   non-interactive utility passes).
4. **Bridge** — a Python package (`bridge/`) that drives **detached Claude Code TUI sessions in tmux inside
   WSL2**, reading them through two channels (screen `capture-pane` + the JSONL transcript) and never
   needing a window. Each agent is a genuine `claude` process.

The dashboard works on **one project at a time**: it opens a single project (a repo root), runs that
project's team of agents against it, and persists everything about that project in the project's own
folder. Changing projects means closing the open one and opening another — there is no second open path
and no in-place switch (§3).

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│  WINDOWS HOST (real laptop)                                                       │
│                                                                                   │
│  ┌───────────────────────────┐     HTTP + SSE      ┌────────────────────────────┐ │
│  │  Electron app  (frontend/) │  ◄──────────────►  │  Sidecar  (sidecar/)       │ │
│  │  main → preload → renderer │   127.0.0.1:7690   │  FastAPI                   │ │
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

**The one-line mental model:** *the bridge is the backbone, the sidecar is the brain, the Electron app is
the skin.* Agents always run on the bridge; the sidecar aggregates and coordinates them; the frontend
renders and commands.

The **defining capability** the whole stack exists to serve is **context-sharing between agents** — links,
a shared scratchpad, and agent-to-agent conversation — the thing that makes the product more than terminals
in a grid. Every one of those features rides a small set of sidecar-owned primitives (the event envelope
and addressing, the prompt queue, the hook channel, read-watermarks — §7) rather than inventing its own
channel.

---

## 2. Runtime topology, processes & deployment

| Process | Where it runs | Started by | Talks to |
|---------|---------------|------------|----------|
| **Electron main** | Windows | `start-dashboard.bat` / `electron-vite dev` | Creates the `BrowserWindow`; loads the renderer. **Does not spawn the sidecar.** |
| **Renderer (React)** | Windows (Chromium) | Electron main | Sidecar over HTTP/SSE via `window.awl.sidecarUrl` (`http://127.0.0.1:7690`). |
| **Sidecar (FastAPI/uvicorn)** | Windows | `start-dashboard.bat` (separately) | The driver seam; and receives **hook callbacks** from agents inside WSL2. |
| **tmux server + `claude` sessions** | WSL2 (Ubuntu) | The `bridge` driver, on session create | Driven by tmux `send-keys`; read by `capture-pane` + JSONL. |

Two boundaries matter most:

- **Frontend ↔ sidecar** is a plain **localhost HTTP + SSE** boundary. The Electron app is a thin client
  — thin enough that a browser tab could replace the shell (the renderer falls back to
  `http://127.0.0.1:7690` when `window.awl` is absent). `start-dashboard.bat` launches the sidecar and the
  Electron app together, but they are **independent processes**; whether Electron main should own the
  sidecar's lifecycle for a true one-click launch is an open question (§10).
- **Sidecar ↔ agents** crosses the **Windows→WSL2** boundary. Outbound (drive the agent) goes
  `sidecar → bridge → wsl -d Ubuntu -- bash -c '…' → tmux`. Inbound-by-poll (read the agent) is
  `capture-pane` + the transcript JSONL. Inbound-by-push (hooks) is the agent **POSTing back** to the
  sidecar over HTTP — which requires solving WSL2 networking (§6.4).

**Deployment model — a decision, not an oversight.** The final packaging model **is** the current one: a
personal tool on one machine. Prerequisites are installed manually, once — WSL2 Ubuntu with tmux and the
`claude` CLI inside WSL, plus a Windows Python venv — and the app is launched by `start-dashboard.bat`.
There is no installer, no auto-update, no multi-user story, and none is intended. A root README setup guide
covering the one-time prereqs is still owed.

**Security posture — accepted by decision.** The sidecar binds `0.0.0.0:7690` with no authentication
because agents inside WSL must be able to POST hook callbacks to the Windows host; this is accepted for a
single-user personal machine, as a choice. The untrusted-network case — the mutating control API exposed when the laptop travels onto café / office Wi-Fi — is an open question (§10 #32). (`AWL_SIDECAR_HOST` overrides the bind host; the frontend always
talks to `127.0.0.1:7690`.)

**One sidecar instance.** A single sidecar process on `:7690` serves whichever project is open. Its state
is partitioned per project folder (§8), so serving a different project is a matter of which project store
it is reading and writing — never a second process.

**Sidecar operational concerns — open.** Two are not yet decided: crash-supervision in the two-process model (who restarts a crashed sidecar; §10 #30), and the sidecar's own logging destination and retention (§10 #33).

---

## 3. The product model — one project at a time

### 3.1 One project open

The dashboard opens **exactly one project at a time**. While a project is open there is no second open
path anywhere in the UI; changing projects = close the current one, then open the other. No in-place
switch semantics exist, and none are needed — close-then-open *is* the switch.

On launch the app lands on an **empty state**: every pane renders a quiet "No project open", and the app
auto-steps into **Settings on the Projects tab** so the first meaningful act is choosing a project. Startup
always shows this picker with the **last-used project preselected** — never a silent auto-load.

### 3.2 The Projects tab

**Projects is the first tab in Settings** (tab order: **Projects · Setups · Usage · MCP · Plugins ·
Config**). It renders:

- A **known-projects list** fed by the projects index (§3.5). Per row: project name, path, last-opened
  time, agent count, and an **Open** action.
- An **"Open other folder…"** action that registers a new project root into the index and opens it.
- When a project is open, it renders as a **highlighted card pinned at the top** of the list, carrying the
  **Close Project** action.

⚠ **Today:** no Projects surface exists yet — the React Settings tabs are Usage / MCP / Plugins / Config
(plus a file-editor tab) in [`frontend/src/renderer/Settings.tsx`](../frontend/src/renderer/Settings.tsx);
the design work is queued in the design lane.

### 3.3 The active-project chip

The topbar/footbar carries an **active-project chip**: the open project's name plus a folder glyph. It is
**display plus a shortcut** — clicking it steps into Settings → Projects — and carries no actions of its
own (no menu, no close button). ⚠ **Today:** no chip exists in the React shell.

### 3.4 Close semantics — and why there is no Save

Closing a project raises a confirm dialog with **exactly two options**:

- **Close** — the dashboard lets go. Agents keep running detached in tmux; all state is already persisted,
  because persistence is **write-as-it-happens** (§8.3). Nothing is flushed at close because nothing needs
  flushing.
- **Close & stop agents** — additionally ends the project's tmux sessions gracefully. Transcripts persist
  either way; a cold restore can rebuild the conversations later (§9.9).

The **same dialog appears on app quit** while a project is open. There is **no Save button anywhere in the
product**: an explicit Save would contradict the continuous-persistence contract, so none exists.
⚠ **Today:** no close dialog exists; the app has no open/close notion at all yet.

### 3.5 The projects index

The dashboard store (§8.1) holds exactly **three** reusable things: **Setups**, **prompt templates**, and a
**projects index** (`projects.json`). The index is the list of known canonical project roots plus each
one's last-opened time. It powers the Projects picker and — critically — makes **cold discovery after a
reboot possible**: the app cannot scan the disk for `.awl-cc-dash/` folders, so the index is how it knows
where projects live. ⚠ **Today:** no `projects.json` exists yet.

### 3.6 Projects and Setups — adjacent, separate

Projects and Setups stay **adjacent-but-separate concepts and tabs**. A **Setup** remains a
project-agnostic, reusable **team template** — roster only: agents, roles, models, identities, links — that
you apply to whatever project is open. A **project** owns its actual saved team, in its own project folder
(§8.2). No umbrella concept renames or merges the two.

### 3.7 Multi-project-safe storage under a one-project UI

The storage layer is **multi-project-safe by construction** even though the UI opens one project at a time:
per-project folders keyed by canonical root never mix, and nothing project-specific sits at the app level
(§8). Agents belonging to an unopened project **keep running detached in tmux** — the dashboard simply is
not looking at them; opening that project later **warm-rebinds** to them (§9.9). One sidecar serves
whichever project is open, its state partitioned per project folder.

---

## 4. Frontend — Electron + React (`frontend/`)

An **electron-vite** project with the three standard process layers.

### 4.1 Process layers
- **Main** — [`frontend/src/main/index.ts`](../frontend/src/main/index.ts): creates one `BrowserWindow`
  (1440×900, dark chrome), wires the preload bridge (`contextIsolation: true`, `nodeIntegration: false`),
  and loads the renderer. It is deliberately **frontend-only** — it does not launch the Python sidecar
  (one-click launch is an open question, §10).
- **Preload** — [`frontend/src/preload/index.ts`](../frontend/src/preload/index.ts): a minimal context
  bridge exposing only `window.awl.sidecarUrl = 'http://127.0.0.1:7690'`. No RPC to main; all data flow is
  HTTP/SSE to the sidecar.
- **Renderer** — React 19 under [`frontend/src/renderer/`](../frontend/src/renderer/).

### 4.2 Renderer structure
[`App.tsx`](../frontend/src/renderer/App.tsx) is the orchestrator: it owns the merged event stream, the
polling loops, and the resizable **three-pane shell** (Agent | Team Graph + Work | Team Feed + Prompt) that
mirrors the DESIGN.md layout. It is componentized:

| Component | File | Role |
|-----------|------|------|
| `AgentPanel` | `AgentPanel.tsx` | Left pane — Details / Create / Console for the focused agent |
| `TeamGraph` | `TeamGraph.tsx` | Agent cards (status badge, identity, ctx/turns bars, subagents, run-strip) |
| `TeamFeed` | `TeamFeed.tsx` | Right-top — merged Messages + Inbox |
| `PromptPanel` | `PromptPanel.tsx` | Right-bottom — Compose (send-timing, templates, revise) + History |
| `WorkPanel` | `WorkPanel.tsx` | Middle-bottom — Library + Links + Scratch |
| `Settings` | `Settings.tsx` | Step-in overlay — Projects · Setups · Usage · MCP · Plugins · Config (§3.2) |
| `EventRenderer` | `events.tsx` | Renders merged-bus events into message/tool/thinking blocks |
| `api.ts` | `api.ts` | The HTTP/SSE client + the whole endpoint catalog |
| `tokens.ts` / `ui.tsx` | — | Inline design tokens + shared primitives (neobrutalism) |

**State** is plain React `useState` in `App.tsx` (no Redux/Zustand). Agent/session/usage/inbox/link data is
held locally and refreshed by polling; the message feed is merged and de-duplicated on the client.

### 4.3 Transport — SSE bus + targeted polling

The frontend reads agent state in exactly two modes:

- **Merged event bus (push):** on load it backfills via `GET /events/history`, then subscribes to the
  merged **SSE stream** `GET /events`. Events are de-duplicated by their stable `id` (a `seenRef` set),
  ordered by `seq`, and capped client-side (~4000). A per-session `GET /sessions/{id}/events` SSE also
  exists, but the client subscribes to the merged bus.
- **Targeted polling (pull)** for readouts that aren't event-shaped, each on its own cadence:
  `/health` (5 s) · `/sessions` + `/usage` + `/inbox` + `/links` (2 s) · `/sessions/{id}/checklist` +
  `/marquee` (3 s) · `/subagents` (4.5 s) · the focused agent's `/context` (~1.2 s loop). The
  **scratchpad** is deliberately **not** on a poll — it is read on demand, and its deltas are pushed to
  running agents via the hook/watermark path (§7.7). The **Console** is **not** on this poll — the focused
  agent's terminal is a **live streaming attach** (`ttyd`/WebSocket), decided 2026-07-05 (§7.13, §10 #5).

Failure handling is only partly specified: SSE reconnect and the "Sidecar offline" chip are homed (`api.ts`), but the degraded-UI policy when `/health` fails, and any backoff on these fixed poll cadences, are open questions (§10 #28).

### 4.4 Frontend build strategy — rebuild the renderer fresh

**The renderer is throwaway.** The current React renderer is an early prototype, not the shippable client:
it is **frozen** and will be **rebuilt fresh from the design system** (`design/` — authority `mockup.html`,
values in `tokens.css`) at the build sprint, *not* finished or ported in place. The design lane keeps
evolving the mockup as the single source of truth; the renderer is rebuilt *to* it once, from scratch. The
one artifact carried through the rebuild is [`api.ts`](../frontend/src/renderer/api.ts) — the
frontend↔sidecar contract (§4.3, §5.2). A standalone Playwright **`tests/ui/`** slice proves "a client can
drive the live loop" against that contract, independent of the parked renderer.

**Scope of the freeze — renderer only, not the Electron shell.** What is frozen is the **visible UI**:
layout, styling, components, and their interaction behaviour — the surface the design system owns. The
Electron **main-process shell** is *not* frozen and is *not* design-owned: sidecar spawn/supervise/shutdown
(§2; §10 #10; §11.4 #27), window + app lifecycle, detach-on-close, and packaging carry real feasibility
unknowns that must still be proven. "Don't build the frontend yet" means the renderer UI — never the shell
plumbing.

⚠ **Today:** the parked renderer trails the mockup — 16 agent colours vs 25, Console gaps, the marquee
omitted, honest no-op controls for engine-blocked features — and is **not** being finished; it is superseded
by the fresh rebuild above. The `tests/ui/` slice exists (built in the §10 spike batch); the real renderer
rebuild is a build-sprint item (§11).

---

## 5. Sidecar — the coordinator (`sidecar/`)

A **FastAPI** app ([`sidecar/main.py`](../sidecar/main.py)), `title="AWL Dashboard Sidecar"`, served by
uvicorn on `0.0.0.0:7690` (§2). Everything cross-agent lives here.

### 5.1 Core in-memory state
- **`SessionState`** (per agent) holds `status` (`connecting|idle|running|error|closed`), the local
  `events` list, the SSE `subscribers`, the **`prompt_queue`** (a disposition-ordered deque, *not* strict
  FIFO), the `held` staging slot, the pending-permission card, and reply-to bookkeeping
  (`answering_source` / `answering_link`).
- **Event bus** ([`eventbus.py`](../sidecar/eventbus.py)) — a bounded global ring (`GLOBAL_RING`, default
  5000 events, `AWL_EVENT_RING_MAX`) plus global SSE subscribers. `stamp()` assigns every event its
  envelope (§7.1).
- **Hook bus / inbox / caps** — small modules ([`hookbus.py`](../sidecar/hookbus.py),
  [`inbox.py`](../sidecar/inbox.py)) backing the inject channel, the Inbox, and the ~3 s lifecycle-cap
  poll loop.

### 5.2 Endpoint surface (grouped by concern)

Bridge-dependent endpoints degrade gracefully when the bridge is unavailable; capability-gated ones return
an honest `400` when the active driver cannot do the thing (§6.1).

| Concern | Endpoints |
|---------|-----------|
| **Health / sessions** | `GET /health` · `POST /sessions` · `GET /sessions[/{id}]` · `DELETE /sessions/{id}` (`?hard=true` → permanent wipe + tombstone, §7.12) |
| **Messaging** | `POST /sessions/{id}/send` (disposition: now/next/queue/hold/inject) · `GET /sessions/{id}/history` |
| **Merged feed** | `GET /events` (SSE) · `GET /events/history?since=<seq>` — both with server-side From/To filtering |
| **Hook channel** | `POST /internal/hooks/{post-tool-use,stop,plan,decision}/{agent}` |
| **Inbox** | `GET /inbox` · `POST /inbox/{agent}/{item}/resolve` |
| **Linking** | `POST/GET /links` · `DELETE /links/{id}` · `POST /links/{id}/kickoff` |
| **Scratchpad** | `GET /scratch` · `POST /scratch` (appends + pushes the delta to running co-located agents) |
| **Library** | `GET /library/documents` · `GET /library/document` · `POST /library/document` (create) · `DELETE /library/document` (delete the `.md` + its paired `.meta.json`) · `GET/POST /library/reviews` |
| **Console** | `GET /console/catalog` · `POST /sessions/{id}/console/run` (+ the live streaming terminal — `ttyd`/WebSocket attach, §7.13 — ⚠ **Today:** not wired into the renderer) |
| **Readouts** | `GET /sessions/{id}/{context,subagents,checklist,marquee}` · `GET /usage` |
| **Session control** | `POST /sessions/{id}/{interrupt,model,mode,permission,effort,fast,thinking}` — `mode`/`fast`/`thinking` are capability-gated `400`s under the bridge driver (§6.2) |
| **Settings** | `GET /settings/{read,account,config,mcp,plugins}` · `POST /settings/write` (confirm-gated) |
| **Templates** | `GET/POST /templates` · `DELETE /templates/{id}` |
| **Projects** | the Projects surface — index list, open, close (§3) — ⚠ **Today:** no endpoint surface exists yet |
| **Utility LLM** | `POST /utility/{revise,summarize}` — run on the in-process Claude Agent **SDK** path (they call SDK `query()` directly, not the `sdk` driver class), never the bridge |
| **Assets** | `GET /assets/agent-icons/{name}?color=` — recolorable agent SVGs (§7.5) |

### 5.3 Serialization

[`sidecar/serialize.py`](../sidecar/serialize.py) normalizes **both driver worlds into one event shape**,
so the renderer never knows which driver produced an event. It maps SDK message classes
(`AssistantMessage`, `UserMessage`, …) and content blocks (`text`, `thinking`, `tool_use`, `tool_result`)
to the frontend's event/`type` vocabulary with depth-limited safe recursion; the bridge driver maps
already-Anthropic-format JSONL blocks with minimal transform, adding the `anchor` (the JSONL uuid) and
`source_kind` that the deterministic event id is built from (§7.1).

---

## 6. Driver seam & the bridge

### 6.1 The seam (`sidecar/drivers/`)

[`base.py`](../sidecar/drivers/base.py) defines `AgentDriver`: the abstract trio `start()` / `send()` /
`events()` (an async iterator of stamped events), plus optional, default-no-op capabilities (`interrupt`,
`set_model`, `set_mode`, `set_effort`, `set_fast`, `set_thinking`, `answer_permission`,
`get_context_usage`, `get_subagents`, `close`). Each driver advertises a `CAPABILITIES` set; the sidecar
checks it and returns `400` for anything unsupported — an **honest signal, never a fake-live control**.

**Selection** ([`drivers/__init__.py`](../sidecar/drivers/__init__.py)) resolves in strict priority order:

1. an explicit per-session `driver` field on the create request, else
2. the `AWL_DRIVER` env var, else
3. **`bridge`** — the default when nothing is named.

An explicitly-named **unknown** driver falls back to **`sdk`** (with a warning) rather than crashing.

### 6.2 `bridge` driver (default, primary)

[`drivers/bridge.py`](../sidecar/drivers/bridge.py). `CAPABILITIES = {interrupt, context, permission,
resume, set_model, set_effort, subagents}`. On `start()` it creates (or resumes) a tmux session via
`TmuxBridge`, applies the agent's **per-agent launch config** (permission mode, deny-based tool scoping,
permission rules, plugins, MCP scope), installs the **hook settings** pointing back at the sidecar, and
persists a runtime record so the session survives a sidecar restart (§9.9). Its `events()` is the **~1 s
poll** that reads the transcript + screen and emits stamped events — this single loop is the shared seam
feeding three consumers: the event stream, the queue's idle/turn-boundary detection, and inbox raising.

Deliberately **not** advertised: `set_mode`, `set_fast`, `set_thinking`. These are engine limits of the
real TUI, not missing code: the CLI only cycles permission modes via Shift+Tab in the terminal, and exposes
no programmatic `/fast` or thinking toggle — so the corresponding endpoints return honest `400`s under the
bridge driver, and the UI never fakes a live control for them. Mid-run mode change is an open question
(§10); mode is launch-only until it is sorted. (The SDK's stream-json control API — `set_permission_mode` / `set_max_thinking_tokens` — *does* expose these programmatically; forgoing it is the deliberate price of keeping the interactive real TUI, and the proven bridge levers are instead the `keys()` Shift+Tab / `Meta+T` / `Meta+O` paths, §10 #1/#2/#3.)

### 6.3 `sdk` driver (limited-use, opt-in)

[`drivers/sdk.py`](../sidecar/drivers/sdk.py). `CAPABILITIES = {set_model, set_mode, context, interrupt}`.
Runs an in-process `ClaudeSDKClient` — **ephemeral**: it does not outlive the sidecar and writes no runtime
record. It is reserved for **non-interactive utility passes** that need no real terminal — the
Revise / Summarize LLM passes behind `/utility/*`. It is **not** a whole-system fallback; agents always run
on the bridge.

### 6.4 The bridge package (`bridge/`) and the Windows/WSL2 seam

[`bridge/bridge.py`](../bridge/bridge.py) exposes `TmuxBridge` (~20 documented methods: create, send, keys,
read, read_log, list, show, close, shutdown, rename, resume, status, batch_create, broadcast, interrupt,
scrollback, watch, wait_idle, export, mcp_sync, plus `set_cwd`/`set_model` and internal helpers
`session_id_for` / `register_session_id` / `wsl_host_ip` / `sidecar_hook_base_url`). Key mechanics:

- **Detached creation.** `create()` runs `tmux new-session -d -s <name> … 'claude --session-id <uuid> …'`.
  The `-d` means **no window** — sessions are always **tab-less**. A Windows Terminal tab opens **only** on
  an explicit `show=True` / `show()` — a deliberate human attach — never as a side effect of programmatic
  creation. `create()` pins a `--session-id` uuid so each agent's JSONL transcript is collision-proof, and
  auto-clears the folder-trust / bypass-mode startup gates. A closed tab does not kill the session;
  `show()` reconnects.
- **Two-channel observation.** The bridge **samples, it does not stream.** `status()` classifies the screen
  from `capture-pane` into `idle | generating | permission_prompt | unknown`;
  [`transcript.py`](../bridge/transcript.py) resolves `cwd → project-hash → <session-id>.jsonl` and parses
  the JSONL for message content. Everything the dashboard knows about a bridge agent comes from these two
  channels, polled ~1 s.
- **Windows↔WSL2 translation.** [`paths.py`](../bridge/paths.py) converts `C:\…` ↔ `/mnt/c/…`; large
  payloads are **piped via stdin** to dodge the ~32 KB command-line limit. Per-agent launch config (the
  materialized `--settings` including hook config, plus `mcp.json`) is written to
  `~/.awl-cc-dash-agents/<name>/` inside WSL — deliberately kept **out** of the real `~/.claude`.
  ⚠ **Today:** the directory is `~/.awl-agents/<name>/` (the `WSL_AWL_DIR` constant in
  [`bridge/paths.py`](../bridge/paths.py)).
- **The hook callback loop.** WSL2 NAT means `localhost` from inside WSL does **not** reach the Windows
  host. So the bridge resolves the **default-gateway IP** (`ip route show default`, cached) and builds
  `http://<gateway>:7690/internal/hooks/…` as the URL each agent's hooks POST to. This inbound-push half of
  the coordination spine is what lets a *running* agent be injected mid-turn and lets Plan/Decision tool
  calls be intercepted. Hooks are best-effort: if the gateway IP can't resolve, agent launch still succeeds
  (without hooks).
- **MCP sync.** `mcp_sync()` translates the Windows MCP registry into a WSL-usable one (`cmd /c npx` →
  `npx`; Windows-only servers skipped; HTTP servers pass through unchanged), merging into WSL
  `~/.claude.json`.
- **Registry reads.** [`registry.py`](../bridge/registry.py) backs the Settings tab's read side (MCP
  servers, plugins via `claude plugin list --json`, config fields) across user/project scopes.

---

## 7. The coordination spine & feature systems

Everything cross-agent rides the primitives in §7.1–§7.4; the feature systems after that are consumers of
those primitives.

### 7.1 The event envelope

Every event, from either driver, is stamped by `eventbus.stamp()` into one envelope:

```
{ id, agent_id, seq, ts, type, source, recipients[], …payload }
```

- **`id`** is a deterministic composite `"{agent_id}:{source_kind}:{anchor}"` — `source_kind` is `t`
  (transcript event; `anchor` = the JSONL entry's own uuid) or `s` (synthesized). Determinism is the point:
  the same underlying event always produces the same id, so **re-polls and SSE reconnects dedup to
  no-ops**.
- **`seq`** is a separate monotonic counter assigned at emit time — the **only** ordering key. Never parse
  the id for order: id = identity/dedup, seq = ordering. `GET /events/history` takes `?since=<seq>` for
  backfill.
- Events are **lightweight envelopes**: heavy content is referenced and fetched on demand, not embedded.

The bus is a **bounded ring, not a stored mega-log** (`GLOBAL_RING`, default 5000, `AWL_EVENT_RING_MAX`):
the per-agent JSONL transcripts on disk remain the source of truth, the sidecar keeps a rolling buffer, the
UI backfills on scroll, and **From/To filtering is applied server-side** on both `GET /events` and
`GET /events/history`. All panels consume this one sidecar-owned aggregated stream, with every event
stamped with its sender.

### 7.2 Addressing — source, recipients, and the two pseudo-identities

Every event carries **`source`** (the sender) and a typed **`recipients[]`** array (values:
`user | <agent-id> | scratch`, default `[user]`). `recipients` is **routing, not visibility**: it drives
delivery, the From/To filter, and Sent/Received direction — but every event still shows in the operator's
feed regardless of recipients. Link delivery and send-as-agent both ride this addressing.

Two reserved pseudo-identities exist alongside the agents:

- **User** — the operator; addressable (the default recipient).
- **System** — filter-only, **never addressable**. It appears as the sender on **system-wide Error cards**
  — infrastructure failures (tmux/WSL2/sidecar down), account-level events (rate/usage caps, auth expiry),
  and shared-service failures (a global MCP server failing) — and on Log lines. System is excluded from
  Compose **To**, Compose **From**, and History **From**; **Reply is disabled** on System cards.
  ⚠ **Today:** no reserved System identity exists — the string `"system"` appears only as a fallback
  source on hook-inject events in [`sidecar/main.py`](../sidecar/main.py) and as the SDK `SystemMessage`
  type mapping in [`sidecar/serialize.py`](../sidecar/serialize.py); there are no System-sourced Error
  cards and no System filter entry.

### 7.3 The prompt queue & delivery dispositions

The sidecar owns a per-agent **ordered** prompt queue (disposition-ordered, *not* strict FIFO), driven by
the bridge's `generating→idle` screen-state transition. A `send` carries a disposition:

- **Queue** — append-tail; flushed at idle (the default).
- **Next** — insert-head.
- **Now** — `interrupt()` then flush.
- **Hold** — park in the dedicated staging slot; released only manually.
- **Inject** — routed via the **hook channel** (§7.4), not through this queue: delivery mid-turn at the
  next safe tool boundary. True *arbitrary* mid-run injection is an engine limit — there is no safe
  injection point on a live TUI — so Inject **transparently degrades to Next/Queue** rather than erroring
  when the hook path can't take it. ⚠ **Today:** Inject always degrades this way; instant mid-turn
  delivery is an open question (§10).

Delivery uses two channels: **push-on-idle** (tmux `send-keys`) for Now/Next/Queue, and the **hook-pull
inbox** for Inject — durable, acknowledged on 2xx. A `send` to a busy agent is never rejected and never
dropped — it always lands in the queue.

### 7.4 The hook channel

Every bridge agent launches with `PostToolUse` + `Stop` + `PreToolUse(ExitPlanMode|AskUserQuestion)` HTTP
hooks pointed at the sidecar's `/internal/hooks/{post-tool-use,stop,plan,decision}/{agent}` endpoints (via
the WSL gateway URL, §6.4):

- **PostToolUse** drains any pending inject for that agent and returns it as `additionalContext` — a
  running agent receives it **mid-turn at the next safe tool boundary, without stopping**. Delivery is
  durable and acknowledged on 2xx.
- **Stop** backstops the no-tool-call case, so a pure-text turn still catches an inject at turn end.
- **Plan / Decision** PreToolUse hooks surface the agent's `ExitPlanMode` / `AskUserQuestion` tool calls to
  the **Inbox** — tool calls that are visible to hooks even when invisible to screen-state. This hook path
  is spike-gated (§10), with detect-and-surface as the recorded fallback.

### 7.5 Agent identity

Agent identity is **role + number + name + colour + icon**, assigned at create, persisted with the roster
(§8.2), shown everywhere, and **editable after create** — all five fields. Identity is dashboard-owned
**display metadata**: routing, links, hooks, and the inbox all key on a stable internal session id, never on
the name or number, so an edit or a mid-run rename cannot break a reference. The **name** is additionally
registered as the Claude Code session's own display name — set at launch via the `claude --name` flag and
kept in sync on edit via `/rename` — so it surfaces in the VS Code extension's session list and the
`--resume` picker, not only inside the dashboard. Pools are **25 colours and 50 curated icons**, assigned
round-robin (`colour = n mod 25`, `icon = n mod 50`); past 16 agents the icon becomes the primary
disambiguator. Icons are recolorable SVGs served from `assets/icons/agents/` via
`GET /assets/agent-icons/{name}?color=`. A human-name pool for the Create panel's randomize affordance is not yet defined (§10 #35). The Create panel's **role number auto-fills**: the No. field pre-fills the next value in that role's sequence (e.g. a second `researcher` pre-fills `02`) but **stays editable** — runtime behavior with nothing to draw in the static mockup (recorded 2026-07-08 from the design lane's IN-2 note). ⚠ **Today:** the React client ships only 16 colours (design-parity
lag, §4.4 — not a decision change); identity editing and the `--name`/`/rename` registration are speced but
not yet wired.

### 7.6 Links — agent-to-agent context

A **link** joins two agents and carries **exactly one relationship**:

- **Direct messaging** — a reply-to conversation. A link fire is the **completion of a reply**, not a blind
  broadcast: when the source agent finishes the turn answering a linked peer's inbound (detected at the
  idle turn-boundary), the sidecar routes that turn's output back to the inbound's sender by enqueuing on
  the peer's queue. Strict **one-inbound-in-flight** per agent. `POST /links/{id}/kickoff` starts a
  conversation; `SessionState` keeps the reply-to bookkeeping (`answering_source` / `answering_link`).
- **Shared context** — passive awareness: the source's output (filtered by content-type, with an optional
  backfill toggle) is made available to the target without conversation semantics.

Wanting both relationships between the same two agents = **two links**. ⚠ **Today:** a link carries a
multi-select `relationship` list (`Link.relationship` in [`sidecar/links.py`](../sidecar/links.py)) that
can hold both at once.

**Triggers.** The delivery-trigger vocabulary is **Now · Inject · Next · Queue · Hold · Piggyback**, riding
the prompt-queue dispositions (§7.3). Defaults: **Direct messaging → Queue**, **Shared context →
Piggyback**. **Piggyback never initiates a turn** — the payload rides the next message delivered to the
target *from any source*. This matters because an actively-delivered share costs the target a whole turn
just to ingest it; Piggyback makes shared context free, which is why it is the shared-context default.
Shared-context delivery is bounded by a per-(source→target) **watermark** that dedups across channels — the
same watermark mechanism as the scratchpad (§7.7), persisted in the same `state/bookmarks.json` (§8.2).
⚠ **Today:** the trigger vocabulary in
[`sidecar/links.py`](../sidecar/links.py) is Now/Next/Queue/Inject/Hold with no Piggyback value.

**End-After.** Each link carries two independent caps — **Exchanges** and **Tokens** — each individually
toggleable; the default is **25 exchanges**. An exchange is one message each direction, and on a **one-way
link each fire counts as an exchange**, so End-After binds one-way links too. Exchanges are explicitly
**not** internal turns/steps — those belong to the lifecycle caps (§7.8). Together with
one-inbound-in-flight, End-After is what keeps bidirectional links from running away. Links carry
**Active/Expired** state. ⚠ **Today:** `Link.exchanges` counts message *pairs* (`messages ÷ 2`), so a
one-way link burns its cap at half rate.

**Tracking.** No on-graph edges and no per-card link badges; link tracking lives in the **Link Config
panel** as an all-links list **grouped by agent** — each link double-listed under both participating
agents, with a direction arrow. (Visual form: DESIGN.md.)

### 7.7 The shared scratchpad

The scratchpad is an **always-current, auto-read** channel: agents do not have to be told to read it.

- Delivery to each agent is a **bounded per-agent delta off a read watermark**: an agent receives only the
  posts past its bookmark, never the whole board twice. The first read gets a full-board snapshot.
- **Running** co-located agents get live mid-run pushes via the hook channel, as **passive context that
  does not trigger a turn** — an early-collision signal. **Idle** agents catch up at start-of-run.
- Stored at `<project>/.awl-cc-dash/docs/scratchpad.md` (§8.2); posts carry `recipients:[scratch]`.
  `POST /scratch` appends and pushes the delta. The scratchpad is deliberately **not** on a frontend poll —
  it is read on demand.

⚠ **Today:** the board lives at `.awl/scratchpad.md` (`storage.scratchpad_path()` in
[`sidecar/storage.py`](../sidecar/storage.py)), and both the working board (`scratchpad._LOG` in
[`sidecar/scratchpad.py`](../sidecar/scratchpad.py)) and the watermarks (`watermark._marks` in
[`sidecar/watermark.py`](../sidecar/watermark.py)) are memory-only — the `.md` mirror is write-only and
never loaded back, so a restart wipes the live board (§8.3).

### 7.8 Inbox

The Inbox is the operator's action surface: typed cards, **one card per blocked agent**, raised over two
distinct mechanisms — bridge **screen-state** (Permission; Error/stall) and the **hook channel** (Plan via
`ExitPlanMode`, Decision via `AskUserQuestion` — §7.4). Endpoints: `GET /inbox`,
`POST /inbox/{agent}/{item}/resolve`.

The type set is **open-ended, not a closed enum** — `type` is stored as a string. The current vocabulary:

- **Error** — sticky; includes System-sourced system-wide errors (§7.2).
- **Warning** — lifecycle-cap crossings (§7.9).
- **Permission** — binary Approve/Deny (§7.11).
- **Plan** — notify-only; verdicts live in Library → Plans, not the inbox.
- **Decision** — the agent's `AskUserQuestion`, answerable from the card.
- **Response** — non-blocking: *"a run ended with output the operator has not reviewed."* One **coalesced
  card per agent**; completable (**View / Reply**), with **no dismiss and no read-tracking**. ⚠ **Today:**
  no Response type exists; the in-memory inbox (`inbox._INBOX` in [`sidecar/inbox.py`](../sidecar/inbox.py))
  raises error/warning/plan/decision, with the pending permission merged in as a synthetic card.

Visual detail for all cards stays with DESIGN.md.

### 7.9 Lifecycle caps

Caps are **notify-only**: crossing a stored max-turns or context-% cap raises a **Warning** card (offering
Continue / Raise cap / Stop) and **the run continues** — the system never auto-kills an agent. A ~3 s cap
poll-loop compares live turns / context-% against the per-agent stored caps and feeds the Inbox's Warning
section. Caps count **internal turns** — deliberately distinct from link exchange counting (§7.6).

### 7.10 Run-strip, checklist & marquee

Run-strip completion % is **agent self-report with barber-pole as the floor**: a system-prompt mandate has
each agent publish an ordered checklist up front and mark items done; the sidecar parses the checklist from
the agent's transcript (riding the existing stream — no new channel) and renders **done ÷ total** as a
segmented bar (`GET /sessions/{id}/checklist`). **No checklist → honest barber-pole indeterminate, never a
fabricated percentage** — the engine emits no progress signal of its own, so the checklist is the only
honest source of a real % (rejected alternatives: an external LLM estimator, and turns-used ÷ cap). Whether
any engine-side progress signal can ever be harvested is an open question (§10).

The **marquee** is a low-fidelity scrolling tail of the agent's transcript output — a pure **liveness**
signal, not an audit surface (auditing lives in Messages). It rides the event stream with no new backend
channel and is decoupled from the checklist; the frontend polls `/marquee` ~3 s. ⚠ **Today:** the React UI
omits the marquee (§4.4).

### 7.11 Permissions

Permission answers are a clean **binary Approve/Deny** (plus Reply). **"Always allow" is fully removed** —
from the UI and from all persistence. (Native permission-automation surfaces — `PreToolUse` / PermissionRequest hooks, `--permission-prompt-tool`, remote permission responses — are a known smoother path, deliberately **not** adopted; the binary screen-driven round-trip stays the model unless it proves insufficient in practice, per candidates-note #5.) The round-trip: the bridge's screen-state detects the tool-permission
menu → a Permission inbox card is raised → the operator answers in the UI →
`POST /sessions/{id}/permission` → the bridge answers the TUI menu via `keys()` → the agent continues.
Detection is screen-state (`capture-pane`), not hooks.

Permission **mode** is launch-only — mid-run mode change is an engine limit (only Shift+Tab cycles modes in
the real TUI; open question, §10). Per-agent tool scoping is **deny-based**, because `--allowedTools` is
ignored under bypass mode — a known Claude bug.

### 7.12 Retire & Delete

Both ship in v1. **Retire** is soft and reversible: stop + archive. **Delete** is hard and irreversible,
under one rule: **wipe the private footprint, tombstone everything shared.**

- Wiped: the runtime record, the tmux session, the on-disk transcripts including subagents, and the
  agent's rows in the project `state/` files (roster entry; inbox/links/routing/bookmarks rows).
- Tombstoned: scratchpad posts, feed events, link edges — **kept**, attributed to the deleted identity,
  marked inactive.

Delete works from any agent state (interrupt + close first) behind a plain confirm dialog. The agent's
**number is permanently retired** — never recycled. Wired as `DELETE /sessions/{id}?hard=true`.
⚠ **Today:** the delete flow covers the runtime record + tmux + transcripts, but the project `state/`
files don't exist yet (§8.3), and retired numbers live only in memory (`deletion._RETIRED` in
[`sidecar/deletion.py`](../sidecar/deletion.py)) — lost on restart.

### 7.13 Console

The Console is a **per-agent Console tab** scoped to the focused agent, with an **Expand** control doing a
partial step-into over the left + middle columns. Its model is a **real live-streaming terminal** — a live client (`ttyd`, attached to the agent's tmux session and consumed over a WebSocket) rendered into an xterm.js-class component, so the focused agent's terminal is watched and typed into exactly as if sitting at it. **Decided 2026-07-05 (streaming, not polled snapshots — feasibility proven, §10 #5):** the Console is the **focused-agent** surface and uses the live stream; the fleet-wide coordination reads and the many-agent grid overview stay on the capture-pane/transcript path (§4.3, §6.2) — you never run N live terminals at once.

- **Live stream:** the terminal streams continuously over the WebSocket (~10 ms keystroke round-trip on localhost, no poll cadence), rendering everything faithfully — output, menus, dialogs, the input/status bar, colors, spinners, box-drawing — exactly as a human at the terminal would see it.
- **Attach-on-open, detach-on-close:** the live client attaches only while the Console tab is open on that agent (never a live terminal per agent across the fleet); one bounded scrollback catch-up on open.
- **Geometry pinning (required):** the agent's tmux pane is pinned via `window-size manual` so an attached viewer cannot resize it and perturb the sidecar's capture-pane coordination reads — the one coexistence hazard, and its fix (§10 #5).
- **Passthrough:** the Console input passes keystrokes through to the TUI over the stream, so interactive slash-command follow-ups are answered exactly as if sitting at the terminal.
- **Slash-command runner:** a full grouped catalog with filter, staged into a run bar (`GET /console/catalog`, `POST /sessions/{id}/console/run`), routed via the bridge's `send`/`keys`.
- **Interception stays on the transcript:** an interactive TUI only ever emits a *painted screen*, so machine-readable data (messages, tool calls, permission events) is read from the JSONL transcript / event bus (§7.1, §8.6) — never parsed off the terminal stream. The stream is the human's surface; the transcript is the machine's.

⚠ **Today:** neither the streaming attach nor a polled mirror is wired into the React Console (a parked-renderer gap), and the React Console is stubbed in places; the catalog + run endpoints exist. The streaming transport is proven feasible end-to-end (`test_console_stream_attach_live`, §10 #5); what remains is the frontend build — the xterm.js-class renderer plus the `ttyd`/WebSocket wiring — deferred to the build sprint.

### 7.14 Prompt composition

Prompt composition ships the **full mockup surface with nothing cut**: the Editor + inserted-block
primitive (embed/template/citation), **Embed**, **Attach**, **Citations**, **Templates**,
**Revise/Summarize**, **Send-as-agent**, a response-format preamble, a voice mic, History + Retry, and a
merged Export control.

- **Attach** requires Windows↔WSL2 path normalization — the decision is solve it, not dodge it. Citations
  are built with Attach.
- **Templates** are stored in the dashboard store (`sidecar/runtime/templates.json`) via `GET/POST
  /templates` and `DELETE /templates/{id}`. Templates are **project-agnostic by design**: the dashboard
  store is their only home, and no per-project template store exists.
- **Revise/Summarize** run on the in-process SDK path (`POST /utility/{revise,summarize}`), never the
  bridge.
- **Send-as-agent** rides the addressing model (§7.2) + the prompt queue (§7.3).
- **Voice mic** and the **response-format preamble** are surfaced but not yet fully specified: the mic's speech-to-text capture→transcribe→insert path (client Web Speech API vs. a sidecar service) is an open question (§10 #27), and the preamble's option-set + apply/persist model is another (§10 #34).

### 7.15 Settings

Settings are **fully interactive**: a write is exposed for everything the engine can set (Config · MCP ·
Plugins, at user + project scope) plus per-agent scoping in the Create/Agent panel — and **all writes are
confirm-gated** (`GET /settings/{read,account,config,mcp,plugins}`, `POST /settings/write`). Feasibility is
marked honestly in the UI: mid-run permission-mode change is blocked (§7.11); per-agent MCP/model/plugins
take effect at launch/restart; tool scoping is deny-based. The **Account band** (email/org/plan from local
creds) and the **usage-limits band** (session/weekly %, live from the API, graceful degrade) are both in.
The intended cost surface goes one level deeper: **live per-agent cost/usage figures on each agent card**,
complementing the account-level band. ⚠ **Today:** no per-agent figure is shown yet — but the 2026-07-02
spike **overturned the old "honest blank" assumption**: `/cost` yields a real per-session figure (§10 #11 →
✅ proven), so this is an *unbuilt* surface, not an engine boundary — scrape-and-surface is the build.
The Setups store lives in the dashboard store (§8.1). The tab set and the Projects tab are §3.2.

### 7.16 Library

The Library reads and renders **Plans, Documents, and Assets** from the open project's
`.awl-cc-dash/` folder (`plans/`, `docs/`, `assets/` — §8.2), reached via WSL. The dashboard **can create and
delete documents** (`POST`/`DELETE /library/document`, §5.2) and may rewrite a document on an explicit,
user-directed operation (e.g. a reformat or a schema fix). What it **never** does is let the **review layer**
write into content: verdicts, comment threads, anchors, and provenance never touch the agent's (or user's)
markdown — they live in the per-doc `.meta.json` sidecar (§8.5), so content stays exactly as written and a
running agent is never raced. Documents carry the same review treatment as Plans (comments; the footer action
strip minus Reject/Approve — the design work is queued in the design lane). The Library can also
browse other repo `.md` files read-only; commenting applies to dashboard-owned files under `.awl-cc-dash/`
only (§8.5; extendable later if needed). **Assets thumbnails (mechanism, decided 2026-07-08):** the Assets
list's fixed-footprint leading slot shows a real **thumbnail for image files** and a **file-type icon** for
non-image/unsupported files — built on Electron's `nativeImage.createThumbnailFromPath` (the Windows Shell
thumbnail provider) with `app.getFileIcon()` as the icon fallback, so no third-party dependency; the UI rule
lives in `design/DESIGN.md` (Library → Assets).

Plan-approve from the dashboard resumes the agent out of plan mode. ⚠ **Today:** that resume path is
now **proven** (§10 #6 → ✅, via a `keys()` Enter, not a hook `updatedInput`) but not yet wired; the Library lists plans **non-recursively** from the
top of `cwd` (or one named subdir — nested trees are not walked; [`sidecar/library.py`](../sidecar/library.py)),
single-doc reads are path-explicit rather than cwd-scoped (the `/library/document` handler in
[`sidecar/main.py`](../sidecar/main.py)), reviews live in one central `plan-reviews.json` keyed by filename,
Documents are read-only with no comment store, no create/delete endpoint exists yet, and no Assets surface exists.

### 7.17 Subagents

A subagent is a **sub-identity of its parent** (e.g. `coder-01 › A2`), riding the sender stamp (§7.1) and
the addressing model (§7.2) rather than getting its own top-level identity. Naming is **group+member**
(`A2`), never flat `s1…sN`. The one net-new backend piece: the sidecar ingests each subagent's
**own transcript** via a folder-watch on the parent's `subagents/` directory, joined to its spawn event.
Pending-vs-active status is an engine limit — the bridge cannot distinguish a pending subagent from an
active one (open question, §10). Badge-click, the nested filter tree, and the Details accordion are
DESIGN.md's.

---

## 8. Storage & the data model

### 8.1 The six homes

Every piece of dashboard data sits in **exactly one** of six homes:

```
🏠 DASHBOARD STORE   sidecar/runtime/*.json              the app's shared toolbox — reusable, project-agnostic
📁 PROJECT STORE     <project>/.awl-cc-dash/*            everything about ONE project + its team — committed, travels with the repo
📜 TRANSCRIPTS       ~/.claude/projects/… (WSL)          Claude Code's own conversation logs — the master record; referenced, never copied
🛠 LAUNCH CONFIG     ~/.awl-cc-dash-agents/<name>/ (WSL)  per-agent settings.json + mcp.json written at launch
🔌 CLAUDE CONFIG     ~/.claude , <project>/.claude        surfaced & edited IN PLACE — the dashboard does NOT own it
⚡ DERIVED (live)     — nothing on disk —                 deliberately ephemeral; rebuilt from 📜/drivers on every start
```

**The one storage rule:** *anything about a specific project or its team lives in that project's folder;
only reusable building blocks live with the dashboard; Claude's own data is surfaced or referenced, never
owned or copied.* Tie-breaker for fuzzy cases: **"is this about one project, or reusable across
projects?"** — one project → 📁; reusable → 🏠.

- The **dashboard store** holds exactly three things: **Setups**, **prompt templates**, and the **projects
  index** (`projects.json`, §3.5). Nothing project-specific may live there.
- The **project store** holds everything about one project and its team — agents, plans, docs, comments,
  inbox, links — committed to git so it travels with the repo: reopening or cloning a project restores its
  dashboard state, and different projects never mix.
- **Transcripts** are the master record (§8.6); the dashboard pins their retention and remembers where they
  are, but never copies them.
- **Launch config** is materialized per agent at launch (§6.4). ⚠ **Today:** at `~/.awl-agents/<name>/`
  (`WSL_AWL_DIR` in [`bridge/paths.py`](../bridge/paths.py)); the target name is `~/.awl-cc-dash-agents/`.
- **Claude config** is surfaced and edited **in place** via the Settings step-in UI — never owned or copied.
- **Derived** state holds nothing on disk — deliberately ephemeral, rebuilt from transcripts and live
  drivers on every start.

The storage layer is **multi-project-safe as a first-class requirement**: different projects with different
agents and different configs never share anything except the 🏠 toolbox, even though the product UI opens
one project at a time (§3.7).

**`<project>` defined:** the **canonical repo root** of the project an agent works in, *derived* from the
agent's `cwd` — git top-level, with symlink and `C:\…`/`/mnt/c/…` path aliases resolved to one canonical
form — so a subfolder launch or a path alias still lands on the same `.awl-cc-dash/` folder. Code keys off
each agent's `cwd`, never a fixed path, so a project can physically move with no rearchitecting.
⚠ **Today:** `storage.project_root()` in [`sidecar/storage.py`](../sidecar/storage.py) returns the raw
`Path(cwd)` unchanged — no canonicalization.

**Git status:** `<project>/.awl-cc-dash/` is **committed** (state travels with the repo);
`sidecar/runtime/` stays **gitignored** (live app-operational state). ⚠ **Today:** the project folder is
named `.awl/` and holds only two files at its root (`scratchpad.md`, `plan-reviews.json`) — the
`_AWL_DIRNAME` constant and path accessors in [`sidecar/storage.py`](../sidecar/storage.py).

### 8.2 The project folder — `<project>/.awl-cc-dash/`

```
<project>/.awl-cc-dash/
├── plans/                     # plan .md files (plan-mode output lands here) + their sidecars
│   ├── roadmap.md             #   content — pure markdown, exactly as the agent wrote it
│   └── roadmap.meta.json      #   metadata sidecar — verdict, comments, anchors, provenance (§8.5)
├── docs/                      # dashboard-owned markdown docs + their sidecars
│   ├── scratchpad.md          #   the shared team scratchpad (§7.7)
│   └── <doc>.md / .meta.json  #   other dashboard-owned docs, same sidecar pattern
├── assets/                    # Library → Assets tab media
└── state/                     # dashboard-owned JSON state for THIS project
    ├── agents.json            #   the project's agent roster: sessions + identity + launch config
    │                          #   + claude_session_id + resolved transcript path + retired numbers
    ├── inbox.json             #   persisted Inbox items (open-ended type set, §7.8)
    ├── links.json             #   agent-to-agent links
    ├── routing.jsonl          #   thin routing overlay — non-default source/recipients, keyed by
    │                          #   transcript anchor ids (§8.6); append-only
    └── bookmarks.json         #   read-watermarks: scratchpad (per agent) + link shared-context (per source→target)
```

- **Naming:** the folder spells out the product name (`awl-cc-dash`) — deliberately *not* `.awl` (too
  vague) and *not* `.cc-dash` (reads as Claude Code's own config, which is `.claude/`).
- **Content format rule:** things people/agents read = **Markdown**; records the app reads = **JSON**.
- Subdirs are created **as they are first populated** — no empty scaffolding is written up front.
- `state/agents.json` is the project's roster: sessions + identity (role/number/name/colour/icon) +
  per-agent launch config (tools/plugins/MCP/permission rules) + `claude_session_id` + the resolved
  transcript path + retired identity numbers (never reused).
- Giving Assets the `assets/` home is what makes the Library's Assets tab buildable — media has a place to
  live with the project.

⚠ **Today:** only `scratchpad.md` and `plan-reviews.json` exist, at the `.awl/` root; the roster lives
app-level in `sidecar/runtime/sessions.json` ([`sidecar/runtime_store.py`](../sidecar/runtime_store.py));
everything under `state/` except the roster is in-memory only (§8.3).

**Self-dogfooding:** the awl-cc-dash repo itself gets its own committed `.awl-cc-dash/` when the dashboard
runs against it — that is the product working correctly, not a special case. Dev agents treat it as
**runtime data, not product source** (the creating code is [`sidecar/storage.py`](../sidecar/storage.py));
it is committed deliberately, never as a side effect of unrelated commits. Tests keep using temp dirs via
`AWL_SIDECAR_RUNTIME` plus per-test cwds.

### 8.3 The persist-vs-derive contract

One explicit rule replaces any invisible persist/ephemeral boundary:

> **Persist** what carries semantic or user-authored state that is **not** in the transcripts.
> **Derive** everything presentational or recomputable from the transcripts / live drivers.

Everything in the Persist rows is small JSON **written as it changes** — append-friendly, with **no
shutdown snapshot to lose; nothing is flushed at shutdown**. Everything in the Derive rows is a view,
restart-cheap by construction. This contract is what makes the two-option close dialog (§3.4) honest.

| On-screen thing | Contract | Home | ⚠ Today |
|---|---|---|---|
| Inbox items (open-ended type set, §7.8 — `type` stored as a string, never a hardcoded enum) | **Persist** | 📁 `state/inbox.json` | ⚡ `inbox._INBOX` in [`sidecar/inbox.py`](../sidecar/inbox.py) — lost on restart |
| Pending **permission** prompt | **Derive** (meaningless after a restart — the live agent re-raises it) | ⚡ | `SessionState.pending_permission` in [`sidecar/main.py`](../sidecar/main.py), merged into `GET /inbox` as a synthetic card — matches target |
| Agent-to-agent links | **Persist** | 📁 `state/links.json` | ⚡ `links._LINKS` in [`sidecar/links.py`](../sidecar/links.py) — lost on restart |
| Message from/to routing (source, recipients) | **Persist** — non-default only, as a thin overlay (§8.6) | 📁 `state/routing.jsonl` | ⚡ lives only on ring events; lost with the ring |
| Read-bookmarks (watermarks — scratchpad per agent; link shared-context per source→target pair) | **Persist** — rides the shared state store, no bespoke system | 📁 `state/bookmarks.json` | ⚡ `watermark._marks` in [`sidecar/watermark.py`](../sidecar/watermark.py); the working board is ⚡ too (`scratchpad._LOG`) — the `.md` mirror is write-only, never loaded back, so a restart wipes the live board; the target reloads the board from its `.md` on start |
| Typed-but-unsent prompt queue / Hold | **Derive** — **drops on close** by design, no carry-over | ⚡ | `SessionState.prompt_queue` / `held` in [`sidecar/main.py`](../sidecar/main.py) — matches target |
| Message feed / history | **Derive** — replay 📜 transcripts into the ring | ⚡ ring (~5000, `AWL_EVENT_RING_MAX`) | [`sidecar/eventbus.py`](../sidecar/eventbus.py) — matches target |
| Cap warnings / lifecycle metrics | **Derive** — recomputed from events | ⚡ | matches target |
| Console feed | **Derive** — live from the driver | ⚡ | matches target |
| Subagent list | **Derive** — re-queried from `/subagents` | ⚡ | matches target |
| Checklist run-strip | **Derive** — parsed live from events | ⚡ | matches target |
| Marquee (activity ticker) | **Derive** — a pure function over recent events ([`sidecar/marquee.py`](../sidecar/marquee.py)); zero persistence | ⚡ | matches target |
| Hook-inject queue (pending context pushes) | **Derive** — regenerated by delivery logic | ⚡ | `hookbus._INBOX` in [`sidecar/hookbus.py`](../sidecar/hookbus.py) — matches target |

### 8.4 Master table — every data type, one row

The single lookup tying **home ↔ path ↔ UI ↔ restart behavior**. UI anchors are the final-design
`data-comp` names (the [DESIGN.md](../design/DESIGN.md) registry).

| Data type | Home | Path | UI (pane · `data-comp`) | ⚠ Today |
|-----------|:----:|------|--------------------------|---------|
| Agent roster (which agents exist, per project) | 📁 | `state/agents.json` | Team Graph · `agent-node-card`; Agent→Create/Details | 🏠 `sidecar/runtime/sessions.json`, keyed by session id ([`sidecar/runtime_store.py`](../sidecar/runtime_store.py)) |
| Identity (role/number/name/color/icon) | 📁 | inside `state/agents.json` | everywhere · `identity-badge`, `agent-tile` | the `identity` field inside `sessions.json`, written by the bridge driver ([`sidecar/drivers/bridge.py`](../sidecar/drivers/bridge.py)) |
| Retired identity numbers (never reused) | 📁 | inside `state/agents.json` | — | ⚡ `deletion._RETIRED` ([`sidecar/deletion.py`](../sidecar/deletion.py)) — lost on restart |
| Per-agent launch config (tools/plugins/MCP/permission rules) | 📁 | inside `state/agents.json` | Agent→Details/Create | inside `sessions.json` ([`sidecar/drivers/bridge.py`](../sidecar/drivers/bridge.py)) |
| Transcript reference (`claude_session_id` + **resolved path**) | 📁 | inside `state/agents.json` | — (drives Feed/History replay + resume) | id persisted; the path is recomputed on every call and never stored (`find_transcript()` in [`bridge/transcript.py`](../bridge/transcript.py)) |
| Projects index | 🏠 | `sidecar/runtime/projects.json` | Settings→Projects · picker list (§3.5) | does not exist yet |
| Setups (reusable team rosters) | 🏠 | `sidecar/runtime/setups.json` | Settings→Setups · `registry-row` | matches target |
| Prompt templates | 🏠 | `sidecar/runtime/templates.json` | Prompt→Compose · `template-select` | matches target — project-agnostic by design (§7.14) |
| Plans (content) | 📁 | `plans/*.md` | Work→Library Plans · `plan-card`, `doc-editor` | listed non-recursively from the top of `cwd`; plan-mode output goes to Claude's default plans dir (§8.5) |
| Dashboard documents (content) | 📁 | `docs/*.md` | Work→Library Documents · `doc-editor` | only the scratchpad exists |
| Doc/plan metadata (verdict, comments, anchors, provenance) | 📁 | `<doc>.meta.json` sidecar, next to its doc (§8.5) | `verdict-badge`, `feedback-card`, `comment-popover`, `review-chip` | central `plan-reviews.json` keyed by filename ([`sidecar/library.py`](../sidecar/library.py)); Documents have none |
| Shared scratchpad | 📁 | `docs/scratchpad.md` | Feed→Scratch · `scratch-post`; Prompt Target=Scratch | `.awl/scratchpad.md`; working log ⚡ (§7.7) |
| Library Assets (media) | 📁 | `assets/` | Work→Library Assets · `asset-card` | no Assets surface exists yet |
| Inbox items | 📁 | `state/inbox.json` | Feed→Inbox · `*-inbox-card` | ⚡ (§8.3) |
| Links | 📁 | `state/links.json` | Work→Links + Graph drawer · `link-drawer`, `link-list`, `link-edges` | ⚡ (§8.3) |
| Routing overlay | 📁 | `state/routing.jsonl` | Feed · `recipient-badge`, From/To filter | ⚡ (§8.3) |
| Read-bookmarks | 📁 | `state/bookmarks.json` | (invisible — drives delta reads) | ⚡ (§8.3) |
| Unsent prompt queue / Hold | ⚡ | — (drops on close, by design) | Prompt→Compose (send-timing) | matches target |
| Message feed / cap metrics / console / subagents / run-strip / marquee | ⚡ | — (derived, §8.3) | Feed / Team Graph / Agent→Console | matches target |
| Session transcripts (full history, incl. subagents) | 📜 | `~/.claude/projects/<encoded-cwd>/<claude_session_id>.jsonl` (WSL) | Feed/History (replayed) | exists; **retention unpinned** — the 30-day default auto-delete applies (§8.6) |
| Per-agent launch files (`settings.json`, `mcp.json`) | 🛠 | `~/.awl-cc-dash-agents/<name>/` | — | `~/.awl-agents/<name>/` (`WSL_AWL_DIR` in [`bridge/paths.py`](../bridge/paths.py)) |
| Claude Code config (MCP/plugins/settings) | 🔌 | `~/.claude`, `<project>/.claude` | Settings (step-in) · `settings-row`, `registry-row` | matches target — surfaced, not owned |

*Env overrides on the storage model:* `AWL_SIDECAR_RUNTIME` (moves 🏠) · `AWL_EVENT_RING_MAX` (event ring
size) · `AWL_DRIVER` (default `bridge`) · `AWL_SIDECAR_HOST` (bind host) · `AWL_DISABLE_HOOKS` (disables
per-agent hooks).

*Naming boundaries:* the environment-variable prefix is **`AWL_`**, and the frontend package name is
**`agent-dashboard`** — neither follows the `.awl-cc-dash` naming.

### 8.5 Documents & plans — content + sidecar metadata

1. **Content and metadata are separate files, paired by name.** `roadmap.md` is pure markdown — the
   dashboard **never writes review metadata into the content file** (though it may create, delete, or, on an
   explicit user-directed operation, rewrite the file itself; §7.16). Next to it,
   `roadmap.meta.json` holds everything else: review state/verdict (+ who/when), comment threads
   (text · author · timestamp · resolved), quote-anchors, and provenance (created-by/when/session). No
   review data is embedded in the content file — no frontmatter requirement, no citation markers.
2. **Anchoring without citations.** A comment targeting specific text stores the *quoted snippet* plus the
   nearest heading; the UI matches and highlights it live. If the text is later edited beyond recognition,
   the comment degrades gracefully to a doc-level comment. The content file stays pristine.
3. **Renames are dashboard-mediated.** The dashboard renames both files of the pair together; an orphaned
   `.meta.json` (no matching `.md`) is detectable and offered for re-link. If agent-driven renames ever
   bite in practice, an embedded stable id can be added *then* — additive, nothing to unwind.
   ⚠ **Today:** reviews live in one central `plan-reviews.json` keyed by the plan's filename
   ([`sidecar/library.py`](../sidecar/library.py)), so a rename silently orphans the review.
4. **Documents get comments like Plans** — the editor-header Comment control plus the Plans-style footer
   action strip minus Reject/Approve (the design work is queued in the design lane).
   ⚠ **Today:** Documents are read-only with no comment store.
5. **Commenting scope:** dashboard-owned files under `.awl-cc-dash/` only; the Library can still browse
   other repo `.md` files read-only. Extendable later if needed.
6. **Plan mode is kept and redirected.** Claude Code's built-in plan mode stays — its enforced
   pause-for-approval is what the Inbox plan flow rides. Its output is redirected into the project folder
   via the standard `plansDirectory` setting (this repo itself sets `./.claude/plans`), written into each
   agent's materialized launch settings. The value is the **absolute WSL path**
   `<canonical project root>/.awl-cc-dash/plans`, computed via the cwd canonicalizer — a relative `./`
   would resolve against the agent's raw cwd and break the same-folder invariant for subfolder launches.
   ⚠ **Today:** the materialized per-agent settings carry only permissions/plugins/hooks
   (`_build_settings()` in [`sidecar/drivers/bridge.py`](../sidecar/drivers/bridge.py)) — no
   `plansDirectory`, so plan-mode output goes to Claude's default plans dir.

### 8.6 Transcripts — the master-record policy

Claude Code writes the full conversation of every agent (and its subagents) to JSONL transcripts. **These
are the master record**; the dashboard's rule is *reference, don't copy* — fat content lives once, in the
transcript; the dashboard persists only thin semantic overlays on top.

1. **Where they are.** Bridge agents run in WSL, so their transcripts are WSL-side:
   `~/.claude/projects/<encoded-cwd>/<claude_session_id>.jsonl` (`WSL_CLAUDE_PROJECTS` in
   [`bridge/paths.py`](../bridge/paths.py)) — **not** the Windows-side `C:\Users\…\.claude\projects` tree,
   which belongs to the user's own Windows sessions.
2. **Path resolution is verified, not trusted.** The transcript dir-name encoding is lossy (every
   non-alphanumeric character becomes `-`), so the bridge verifies against the real directory listing and
   resolves the exact file by session id (`find_transcript()` in
   [`bridge/transcript.py`](../bridge/transcript.py)). The resolved path is persisted per agent in
   `state/agents.json` alongside the session id, so the mapping survives restarts and scheme drift.
   ⚠ **Today:** the path is recomputed on every read and never persisted.
3. **Retention is pinned.** Claude Code auto-deletes sessions inactive longer than `cleanupPeriodDays`
   (default 30 days) — unacceptable for long-term-referenced transcripts. The per-agent settings the bridge
   materializes at launch carry `cleanupPeriodDays: 3650` (10 years — effectively never; one constant to
   adjust), guaranteeing retention for dashboard agents without touching global Claude config.
   ⚠ **Today:** `cleanupPeriodDays` is not set anywhere, so the 30-day default applies.
4. **No backup copies.** Pinned retention plus persisted paths **are** the durability model — transcript
   copies are never archived. The one trigger for revisiting is durability proving shaky in practice.
5. **Session prompts are not separately saved** — they are already in the transcript; anything durable a
   user wants to reuse becomes a dashboard-store template.
6. **The overlay-index principle.** Anything the dashboard adds *about* transcript content is keyed to the
   event **anchor id** the bus already mints — `{agent_id}:{source_kind}:{anchor}`, where `anchor` is the
   transcript entry's own uuid (`stamp()` in [`sidecar/eventbus.py`](../sidecar/eventbus.py)) — so overlays
   re-join losslessly on replay. First instance: `state/routing.jsonl`, an append-only file of
   `{anchor_id, source, recipients}` records written for **non-default routing only** (agent-to-agent,
   scratch); the default `agent → [user]` routing is re-derivable and never written. Replay = transcript →
   left-join overlay → full feed, addressing intact, zero duplicated text.

### 8.7 Three spots to watch

1. **Transcript-scheme drift.** The dir-name encoding and `--resume` behavior belong to Claude Code, not
   the dashboard; pinned retention + persisted resolved paths reduce the blast radius, and the live-verify
   habit in the bridge test suite is the canary for drift.
2. **Concurrent writers on one project.** Two agents in the same project share one `state/` directory —
   fine for append-only files (`routing.jsonl`) and keyed writes, but the state-store implementation must
   do **atomic write-replace per file** to avoid torn JSON. Cross-branch/machine merge of the committed `state/` JSON is a separate, still-open concern — there is no merge policy for two branches editing the whole-file state (§10 #31).
3. **Schema evolution of the committed store.** The `state/` JSON carries no `schema_version` stamp or forward-compat policy yet, so a future format change could break older data — an open question (§10 #29).

---

## 9. Lifecycle flows, end to end

### 9.1 Open a project
Startup lands on the empty state and steps into Settings → Projects (§3.1). Picking a project from the
index (or "Open other folder…", which registers a new root) opens it: the sidecar loads the project store —
roster + identities from `state/agents.json`, inbox/links/bookmarks from `state/`, the scratchpad board
from its `.md` — warm-rebinds any still-alive tmux sessions and cold-restores dead ones (§9.9), and replays
transcripts into the feed. The active-project chip appears; the panes fill. ⚠ **Today:** there is no
open/close flow; the sidecar starts against whatever sessions its runtime store holds.

### 9.2 Create an agent
`POST /sessions` → the sidecar assigns identity (§7.5) → the `bridge` driver `start()` →
`TmuxBridge.create()` runs detached tmux + `claude --session-id <uuid>` in WSL, clears the startup gates,
installs hooks → the roster record is persisted → the `events()` poll begins → stamped events flow onto the
bus → the frontend renders the new card. **No tab opens.**

### 9.3 Send while busy
`POST /sessions/{id}/send {disposition}` → enqueued per §7.3 → on the next `generating→idle` transition the
head flushes via tmux `send-keys` → the turn's output streams back as stamped events. Nothing is dropped.

### 9.4 Permission round-trip
Agent hits a tool prompt → bridge screen-state detects the menu → a Permission inbox card → the operator
answers Approve/Deny → `POST /sessions/{id}/permission` → the bridge answers the TUI menu via `keys()` →
the agent continues (§7.11).

### 9.5 Agent→agent link fire
The source finishes replying to a peer's inbound at the idle boundary → the sidecar routes that turn's
output to the peer's queue → delivered per the link's trigger → bounded by End-After and
one-inbound-in-flight (§7.6).

### 9.6 A scratchpad post
A post via Prompt with Target = Scratch hits `POST /scratch` → the sidecar appends to the working log
**and** rewrites the full board to `docs/scratchpad.md` → other agents receive only the posts past their
bookmark — mid-run as passive context through the hook channel, or at start-of-run catch-up — and the
bookmark advances in `state/bookmarks.json` → the board reloads from its `.md` on start → the post renders
in Feed→Scratch carrying `recipients:[scratch]`. (⚠ Today-markers: §7.7.)

### 9.7 A plan, reviewed
An agent in plan mode writes `plans/refactor.md` (plan-mode output redirected there, §8.5) → the
plan-approval pause raises an Inbox `plan` card → the operator reviews in Work→Library Plans → verdict +
comments land in `plans/refactor.meta.json`, quote-anchored, content file untouched → Approve resumes the
agent out of plan mode. The whole exchange is in the 📜 transcript; the review record stays with the
project, committed.

### 9.8 Close a project / quit the app
Close (or quit with a project open) raises the two-option dialog (§3.4). **Close**: the dashboard detaches;
agents keep running in tmux; nothing is flushed because persistence is write-as-it-happens. **Close & stop
agents**: the project's tmux sessions are also ended gracefully; transcripts persist.

### 9.9 Restore — warm and cold
Closing the dashboard and reopening later lands you in near-exactly the same state (a hard product
requirement). The **state half** comes back by construction: everything in the Persist rows plus the 📁
files — roster, identities, plans + reviews, scratchpad, inbox, links, routing, bookmarks — and feed
history re-derives from 📜 transcripts *even when the agent processes are gone*. The unsent prompt queue is
intentionally empty. The **agent half** has two cases:

- **Warm** (sidecar restarted; tmux/WSL still running): rebind to the live session. This works today —
  `reconnect_sessions()` in [`sidecar/main.py`](../sidecar/main.py) rebuilds `SessionState` from the
  persisted record and re-attaches the driver; agents keep running across a sidecar bounce because tmux
  held them.
- **Cold** (reboot / WSL shutdown; tmux gone): relaunch the agent with
  `claude --resume <claude_session_id>` in its cwd — the same conversation, rebuilt from the transcript.
  Graceful-degrade fallback if cold-restore proves hard in practice: restore all *data* and let agents be
  re-resumed manually. ⚠ **Today:** a dead-tmux record is **pruned** — deleted, the agent forgotten
  (`reconnect_sessions()` in [`sidecar/main.py`](../sidecar/main.py)) — and nothing invokes
  `claude --resume`: the bridge's `resume()` in [`bridge/bridge.py`](../bridge/bridge.py) only rebinds live
  tmux and, if the session is gone, falls through to `create()` with a *fresh* session id — a brand-new
  conversation. Also today, transcript replay only happens through a live/rebound session's driver poll, so
  a pruned agent's transcript is never replayed.

**Cross-machine caveat (accepted):** cloning a project to another machine brings all 📁 state, but
transcripts and live processes stay in the original machine's WSL — agents re-launch fresh there. No
cross-machine resume machinery gets built.

### 9.10 Delete an agent
`DELETE /sessions/{id}?hard=true` → interrupt + close if needed → wipe the private footprint (runtime/roster
record, tmux session, transcripts incl. subagents, the agent's rows in the project `state/` files) →
tombstone everything shared (scratchpad posts, feed events, link edges — kept, attributed, inactive) →
retire the number permanently (§7.12).

---

## 10. Open questions & research queue

The single home for everything the system needs but the settled body above can't yet specify — at **any
maturity**, from a vague "we should figure out X" to a POC-ready item. This is a **holding pen, not a
scorecard**: the *proven* product lives in the body (§1–§9) and the test suite; §10 holds only what's still
unsettled, so it reads as mostly-open by design — that is not a measure of progress. Between the settled body
and this queue, the whole intended system should be accounted for; a behavior that is neither settled above
nor listed here has fallen through a crack and belongs here.

**Entry is deliberately cheap.** An item may enter half-formed — as little as *roughly what we want / what we
don't yet know / what would settle it* — and **mature toward** the full template (Desired / Blocker /
Research·POC / Fallback) as it's understood. Don't withhold an under-baked item because it isn't fully
specced; parking it here *is* the point.

**Exit is strict** (unchanged): an item leaves only by being **sorted** (a mechanism is found and woven into
the settled body) or **explicitly omitted** (a recorded decision → Decided omissions). Nothing is deleted.

**§10 vs §11 — keep the line sharp:** §10 = *don't-yet-know-if-or-how* (not buildable; needs research, a
spike, or a decision first). §11 = *know-how, queued to build*. When a spike settles a §10 item into
"buildable," it graduates to the body + §11 and leaves the queue.

Each entry carries a **status tag** — the reality of the capability *today*, not whether the question is
resolved (everything here is unresolved) — plus an **Evidence** line citing the test that backs it, marked
**live** (real WSL2/tmux, strongest) or **unit** (hermetic contract):

- ✅ **proven** — a test or live run establishes it
- ◐ **partially proven** — part is built & tested; part is still open
- 🧪 **needs-spike** — unproven, but a concrete mechanism is known; next step is a live experiment
- 🔬 **needs-research** — unproven, and the mechanism/approach is unknown; next step is investigation before it can even be spiked
- ⛔ **impossible-today** — a spike found no path on the bridge as-is (a decided limitation → Decided omissions, not the queue)

Live citations below reference the **2026-07-02 full-suite pass — 428/428 (395 unit + 33 live) @ commit
`c73a526`, Claude CLI 2.1.198** (`results_20260702T142448Z`).

**Spike-settled items (2026-07-02 batch).** Where a live feasibility spike (`tests/*_live.py`, verified @
`af4964d`; index in [`tests/README.md`](../tests/README.md)) or a completed research pass has since settled
an item, its tag is updated **in place** (✅/◐/🧪/⛔) and its Evidence line cites the spike test or research
report. Per the port-then-refactor plan, a fully-proven item stays listed here with a ✅ tag and a *(pending
relocation — Phase 9)* marker until the Phase 9 refactor moves it into the settled body — so a ✅ here means
"proven, pending relocation," not "still open."

Maintenance note: when adding, removing, or moving entries, renumber them continuously across the priority
subsections in display order (High → Medium → Low); do not restart numbering inside each subsection. Keep a
status tag + Evidence line on every entry (a fresh, half-formed item may carry `🧪`/`🔬` with a one-line
Evidence and grow the rest later). An item resolves to ⛔ only **after a spike** actually proves no path (a
code no-op is not a proof); it then moves to **Decided omissions** (not part of the numbered queue), never
deleted.

### Priority — High

**1. Mid-run permission-mode change** *(→ §6.2, §7.11)* — ✅ **proven** *(pending relocation — Phase 9)*
- **Evidence:** **spike passed** (`test_permission_mode_cycle_live`, **live**, 2026-07-02): Shift+Tab via the
  bridge's `keys()` at a known-idle screen cycles the permission mode deterministically and actually
  suppresses prompts, with the resulting mode read back from the status line. (`set_mode` is still an in-code
  no-op — the proven lever is the `keys()` Shift+Tab path; wiring it into the driver is the build.)
- **Desired final behavior:** the operator changes an agent's permission mode live, mid-run, from the UI.
- **Spike established:** the Shift+Tab `keys()` cycle is deterministic and readable at idle; wire it into the
  bridge driver (replacing the `set_mode` no-op) and back the `POST /sessions/{id}/mode` route with it.
- **Fallback if infeasible:** n/a — proven feasible; the launch-only degrade is no longer needed.

**2. Thinking-mode toggle (`Meta+T`)** *(→ §7.11, DESIGN mode toggles)* — ✅ **proven** *(pending relocation — Phase 9)*
- **Evidence:** **spike passed** (`test_thinking_toggle_live`, **live**, 2026-07-02): thinking toggles on a
  running agent via the `Meta+T` modal panel, and the result is read-backable (thinking blocks appear in the
  transcript). (`set_thinking()` is still an in-code no-op — the proven lever is the `Meta+T` path.)
- **Desired final behavior:** the operator toggles thinking on/off on a running agent from the UI.
- **Spike established:** `Meta+T` via `keys()` reaches the modal and toggles thinking, read-backable from the
  transcript; wire it into the driver (replacing the `set_thinking()` no-op) with a current-state read first.
- **Fallback if infeasible:** n/a — proven feasible.

**3. Fast-mode toggle (`Meta+O`)** *(→ §7.11, DESIGN mode toggles)* — ✅ **proven** *(pending relocation — Phase 9)*
- **Evidence:** **spike passed** (`test_fast_mode_toggle_live`, **live**, 2026-07-04, Fast credits enabled):
  `Meta+O` opens the "↯ Fast mode (research preview)" panel on a running agent, and **`Space` toggles the
  state** — the panel's `Fast mode OFF/ON` line is a plain-text scrape, and a there-and-back flip
  (OFF → ON → OFF) proved it settable + read-backable + repeatable. (`Enter`/`Escape` only close the panel;
  `Space` is the lever. `set_fast()` is still an in-code no-op — the proven lever is the `Meta+O`+`Space` path.)
  The earlier `xfail` (2026-07-02) was a **credit-gate** — an account limit, since lifted — not a bridge limit.
- **Desired final behavior:** the operator toggles Fast (Opus) mode on a running agent from the UI.
- **Spike established:** `Meta+O` via `keys()` opens the Fast panel and `Space` toggles it, read-backable from
  the panel; wire it into the driver (replacing the `set_fast()` no-op) as open-panel → read → Space-to-target
  → close, with a current-state read first. Credit-gate detection (the panel reports "requires usage credits")
  stays the honest degrade for accounts without Fast credits.

**4. True mid-run Inject** *(→ §7.3)* — ⛔ **tail impossible → resolved at fallback** *(pending relocation — Phase 9)*
- **Evidence:** **tail spike passed — INFEASIBLE** (`test_inject_tail_live`, **live**, 2026-07-04): typeahead
  into a *generating* pane lands in the composer but is **held for the whole turn** and submitted only at the
  turn boundary — pure Next/Queue, never earlier-than-boundary. So the *immediate mid-turn* variant has **no
  path** on the bridge as-is. The base — hook-boundary delivery — is **unit-proven** (`test_hookbus_unit`,
  `test_sidecar_unit`) and ships (§7.3).
- **Desired final behavior:** an Inject-disposition message reaches a running agent immediately, mid-turn.
- **Resolved:** the mid-turn variant is a **decided engine limitation** (→ Decided omissions at Phase 9); the
  shipped model — hook-boundary delivery + the transparent Next/Queue degrade — **is the final model**.
- **Fallback (now the ceiling):** hook-boundary delivery plus the transparent Next/Queue degrade.

**5. Console rendering fidelity + live-streaming transport** *(→ §7.13)* — ✅ **transport decided: streaming** · ✅ **fidelity decided (2026-07-05): full xterm-class renderer, priority HIGH** (frontend build)
- **Evidence (wiring/fidelity):** **spike passed** (`test_console_mirror_live`, **live**, 2026-07-02) on the *wiring*: keystroke passthrough works and ANSI is recoverable from the pane via `capture-pane -e`. The remaining fidelity gap is pure frontend — a faithful xterm-class renderer — which is a build decision, not an engine feasibility question.
- **Evidence (streaming transport):** **spike passed** (`test_console_stream_attach_live`, **live**, 2026-07-05, ttyd 1.7.7) — a real *live-streaming* terminal (`ttyd` attached to the agent's tmux session, consumed over a WebSocket) is: **(a)** reachable from Windows over `localhost` with **no hand-rolled port-forwarding** (WSL2's default relay suffices); **(b)** safely coexistent with the sidecar's capture-pane poller — the scraper keeps classifying state correctly under a live viewer, and **`tmux window-size manual`** pins the pane so a viewer cannot perturb the geometry the poller reads (the one real hazard: naive `window-size latest` lets a viewer resize the pane, and the resize **persists** after it detaches); **(c)** far lower latency — a keystroke round-trip of **~11 ms streaming vs ~778 ms polled** (N=1 best case; the polled mirror also degrades ~O(N) with fleet size, per `test_polling_scale_ceiling_live`). A throwaway harness rendered the live stream faithfully in an xterm.js embed (screenshots in the DEVLOG entry). Interception stays on the JSONL transcript regardless — an interactive TUI only ever emits a painted screen.
- **Decided (2026-07-05) — streaming for the focused Console:** the Console (§7.13, updated) renders the focused agent via the **live streaming attach** (`ttyd`/WebSocket), not polled `capture-pane` snapshots — the "watch Claude live" experience, chosen once coexistence + reachability + latency all came back green. **Polling and the transcript stay** where they belong: the capture-pane/transcript path keeps serving the fleet-wide coordination reads and the many-agent grid overview (§4.3, §6.2) — you never run N live terminals at once. The two are complementary, not competitors. Full context: the embedded-terminal feasibility brief, `dev/notes/research/embedded-terminal-feasibility-brief-2026-07-05.md`.
- **Desired final behavior:** the Console mirror renders the terminal faithfully, including colors, spinners, and box-drawing.
- **Decided (2026-07-05, operator — Q8 / §F1): full terminal renderer (xterm-class), priority HIGH.** The operator saw the 2026-07-05 live-streaming spike (ttyd + xterm.js harness; DEVLOG 06:53) and calls it decisively better — so the fidelity choice is **A (faithful colours / spinners / box-drawing)**, not the styled-text or plain-text degrades. It is a frontend build that lands **within the §4.4 renderer rebuild**: the visible renderer is parked-to-rebuild, so "ASAP / high" means first-tier priority *inside* that rebuild, not a carve-out before it. Transport half already proven + decided above.
- **Current blocker (frontend only):** faithful rendering needs the streamed terminal bytes fed into a terminal-renderer component (xterm.js-class) in the React Console — proven to render faithfully in a throwaway spike harness (2026-07-05); the sidecar/bridge/transport half (the decided streaming attach) is proven.
- **Research/POC must establish:** n/a — feasibility is proven and the transport choice is **decided** (streaming); the one remaining open call is the frontend build itself — the xterm.js-class renderer + `ttyd`/WebSocket wiring in the (frozen, to-be-rebuilt) React Console.
- **Fallback if infeasible:** a clean plain-text mirror (ANSI stripped).

**6. Plan/Decision hook interception** *(→ §7.4, §7.16)* — ✅ **proven** *(pending relocation — Phase 9)*
- **Evidence:** **spike passed** (`test_plan_decision_hooks_live`, **live**, 2026-07-02): `ExitPlanMode` /
  `AskUserQuestion` surface as cards, **and** the agent resumes out of plan mode. Key correction: resume is
  driven by a **`keys()` Enter** on the pane, **not** by a hook `updatedInput` response — the earlier
  "spike-gated" framing (and §7.16's "resume rides the Plan hook") is superseded.
- **Desired final behavior:** `ExitPlanMode` / `AskUserQuestion` surface as Plan/Decision inbox cards, and
  plan-approve from the dashboard resumes the agent out of plan mode.
- **Spike established:** cards can be raised from the hook/transcript, and approve→resume works via `keys()`
  Enter (not `updatedInput`); wire the approve action to that keystroke, not a hook response.
- **Fallback if infeasible:** n/a — proven feasible (detect-and-surface is no longer the ceiling).

### Priority — Medium

**7. Real run-strip completion %** *(→ §7.10)* — ⛔ **tail impossible → resolved at fallback** *(pending relocation — Phase 9)*
- **Evidence:** **tail spike passed — INFEASIBLE** (`test_runstrip_tail_live`, **live**, 2026-07-04): a
  100%-complete multi-tool run (3 writes + DONE) yields only NUMERATORS from `derive_context_usage`
  (`work_steps`, `tool_total`) with **no denominator** — the only percentage is *context tokens*, not work
  done — and no `TodoWrite` fired. So **no trustworthy engine-side completion fraction exists**. The base —
  the self-reported checklist parser — is **unit-proven** (`test_checklist_unit`, 19 cases) and ships (§7.10).
- **Desired final behavior:** the run-strip shows a genuine completion percentage for every run.
- **Resolved:** an engine-emitted progress fraction is a **decided limitation** (→ Decided omissions at Phase
  9); the shipped model — checklist self-report + the barber-pole indeterminate floor — **is the final model**.
- **Fallback (now the ceiling):** checklist self-report with the barber-pole floor.

**8. Subagent pending-vs-active status** *(→ §7.17)* — ✅ **proven** *(pending relocation — Phase 9)*
- **Evidence:** **spike passed** (`test_subagent_status_live`, **live**, 2026-07-02): a subagent's
  active-vs-quiet state is readable from its **own transcript** (recency of the last event). Complements the
  unit-proven identity/naming/ingestion (`test_subagents_naming_unit`). The `SubagentStart`/`SubagentStop`
  hooks (research #13/#22) offer an even cleaner authoritative signal — see §11.
- **Desired final behavior:** each subagent shows live pending vs active state.
- **Spike established:** subagent-transcript recency yields a reliable active signal; wire it into the roster,
  and prefer the `SubagentStart`/`SubagentStop` hook fields (`agent_id`, `transcript_path`) once hook
  ingestion lands (§11).
- **Fallback if infeasible:** n/a — proven feasible.

**9. Context breakdown & Compact controls** *(→ §7, DESIGN context dropdown)* — ✅ **proven** *(pending relocation — Phase 9)*
- **Evidence:** **spike passed** (`test_context_compact_live`, **live**, 2026-07-02): the `/context` output
  parses into per-category rows, and `/compact` boundaries are detectable from `compact_boundary` transcript
  metadata. Complements the unit-proven total-context/turn derivation (`test_bridge_unit`).
- **Desired final behavior:** an on-demand context pull with per-category rows, plus compact controls
  (multi-select options) and a compaction history (count / type / when).
- **Spike established:** parse `/context` for the category breakdown and key compaction history off
  `compact_boundary`; wire both into the context dropdown + run-strip.
- **Fallback if infeasible:** n/a — proven feasible; total usage + turn count remains the floor if the
  `/context` scrape is ever unavailable.

**10. One-click launch (Electron main spawns the sidecar)** *(→ §2, §4.1)* — ◐ **partially proven**
- **Evidence:** **spike passed in model** (`test_oneclick_launch_live`, **live**, 2026-07-02): the
  spawn/supervise/shutdown lifecycle (including detach-on-close of running tmux agents) is proven **modeled in
  Python**; the real **Electron-main** POC is still owed (→ §11.4 #27).
- **Desired final behavior:** one icon starts everything; quitting tears it down cleanly through the same
  close dialog as §3.4.
- **Current blocker:** the lifecycle logic is proven, but it has not been ported into Electron main, which
  must own the Python venv path, crash/restart supervision, and shutdown ordering against agents that should
  keep running.
- **Research/POC must establish:** re-home the proven lifecycle model in Electron main and confirm
  detach-on-close end-to-end (the §11.4 #27 build item).
- **Fallback if infeasible:** `start-dashboard.bat` two-process launch stays the shipped model (§2).

### Priority — Low

**11. Per-agent cost** *(→ §7.15)* — ✅ **proven** *(pending relocation — Phase 9)*
- **Evidence:** **spike passed** (`test_per_agent_cost_live`, **live**, 2026-07-02) — this **overturns the
  "honest blank" assumption**: `/cost` yields a real per-session dollar figure, so a genuine per-agent cost
  *is* harvestable. §7.15's ⚠Today ("the bridge emits no cost data… an honest blank") is corrected: the
  figure is unbuilt, not unavailable.
- **Desired final behavior:** live per-agent cost/usage figures on each card.
- **Spike established:** scrape `/cost` (via the console path) for a per-session figure and surface it on the
  card; the account-level band (§7.15) stays as the complementary aggregate.
- **Fallback if infeasible:** n/a — proven feasible; the honest-blank is now a temporary unbuilt gap, not a
  boundary.

**12. Attachment / citation path materialization** *(→ §7, `library.py`)* — 🧪 **needs-spike**
- **Evidence:** **research settled** ([`attachment-citation-path-materialization-report.md`](../dev/notes/research/attachment-citation-path-materialization-report.md),
  2026-07-02): recommends **Option A** — copy bytes into `<project>/.awl-cc-dash/assets/<id>/`; store a
  project-relative `rel_path` + SHA-256 + MIME + provenance; render per-receiver via a `ProjectPathContext`
  (Windows-drive path shapes confirmed against Microsoft docs). Design is "plausible" — no prototype built.
- **Desired final behavior:** attachments and citations route to a real on-disk home a receiving agent can
  open.
- **Current blocker:** no `ProjectPathContext`, no `.awl-cc-dash/assets/` catalog, no ingestion path;
  `library.py` still defers assets.
- **Spike must verify before building:** (a) the WSL-native write path (`wsl.exe … cat > tmp; mv final`) and
  `wslpath -w` edge cases (spaces, unicode, unusual distro names); (b) Electron/Chromium security policy for
  loading Windows-absolute and `\\wsl.localhost\…` UNC paths in the renderer, or whether a sidecar-served
  local HTTP asset endpoint is required instead.
- **Fallback if infeasible:** attachments stay display-only chips (name/size/MIME) until the path story lands.

**13. Native coordination primitives (Tasks / Workflow / SendMessage)** *(→ research notes)* — 🧪 **needs-spike**
- **Evidence:** **research settled** ([`native-claude-code-coordination-report-2026-07-02.md`](../dev/notes/research/native-claude-code-coordination-report-2026-07-02.md)):
  **decision — keep the sidecar custom spine (inbox / links / scratchpad) as canonical; adopt native
  primitives only narrowly** as observability enrichments or optional run modes. Concrete findings: `Task`
  was renamed to `Agent` (v2.1.63; `Task(…)` is a legacy alias — the sidecar parser may key on the wrong
  name, a silent-miss risk → §11.4 #28); `TodoWrite` is disabled-by-default (v2.1.142; not the adoption
  target); `SendMessage` is scoped to native subagent/team graphs and **cannot** bus across independently
  spawned tmux processes (confirms LINKS must stay); agent-teams are experimental/disabled-by-default (one
  team/session, no nesting, no resume) — spike-only. (This item also absorbs the old backend backlog's *Tasks
  (open)* question — absorbed from BB11, 2026-07-03.)
- **Desired final behavior:** the dashboard's coordination reuses native Claude Code primitives **where they
  fit** (observability, optional modes), atop the durable custom spine.
- **Current blocker (spike-grade):** the report is docs-derived, not run-verified against the deployed CLI —
  the `SendMessage`/JSONL shapes, `SubagentStart`/`SubagentStop` payloads, and workflow observability under
  detached tmux need a live spike before adoption.
- **Research/POC must establish:** a live spike confirming the hook payloads + tool-name state on the
  installed build; agent-teams stay behind their own spike if ever pursued.
- **Fallback if infeasible:** keep the current custom coordination spine (inbox, links, scratchpad).

### Priority — coverage-audit additions (2026-07-02)

Surfaced by the 2026-07-02 system coverage audit
([`archive/dev/notes/scratch/2026-07-02-coverage-audit-orphans.md`](../archive/dev/notes/scratch/2026-07-02-coverage-audit-orphans.md))
and **appended here as #14 onward** — deliberately *not* interleaved into the High/Medium/Low subsections
above — so the existing item↔prompt numbering in [`dev/prompts/`](../dev/prompts/) is not disturbed. Per-item
priority is noted inline. Each carries a spike or research prompt queued under
`dev/prompts/2026-07-02-s10-*` (cited per item); those are the concrete next step, not evidence of a built
capability.

**14. Hook-driven run-state / permission-mode push channel ("hook event stream")** *(→ §6.2, §7.4, §7.11)* — ◐ **partially proven** *(priority: medium)*
- **Evidence:** **spike passed** (`test_hook_event_stream_live`, **live**, 2026-07-02) + **research settled**
  ([`claude_code_hook_event_stream_report.md`](../dev/notes/research/claude_code_hook_event_stream_report.md)):
  hook transport + payload fields + the WSL→Windows gateway are confirmed on the installed build; run-state
  (`permission_mode` + current tool) is readable from hook payloads. Design decision: **Option C hybrid** —
  hooks authoritative-when-fresh, screen-polling as the watchdog floor (HTTP-hook failures are silent, so a
  pure-push replacement is unsafe). **Caveats:** `permission_mode` is event-specific (Notification lacks it);
  ordering/dedup under concurrent load is **untested** — the per-agent merge/arbiter is design, not proven.
- **Desired final behavior:** every agent's hooks POST each lifecycle event to the sidecar, which treats
  pushed run-state / `permission_mode` as authoritative-when-present, with screen-polling as the fallback for
  hookless sessions.
- **Remaining open (resolves during build):** arbiter merge correctness, dedup keys, and late-event ordering
  under concurrent load; the `prompt_id` version floor (v2.1.196+) should be recorded from the build. The
  arbiter + `SubagentStart`/`SubagentStop` ingestion is the §11.3 #22 build item.
- **Fallback if infeasible:** screen-state polling stays the primary run-state signal (today's floor); hooks
  remain limited to the proven inject/plan paths.

**15. Rewind / Handoff / Timeline — conversation truncate-and-resume / fork-from-point** *(→ §7.5, §9.2, §9.9, DESIGN "Rewind & Handoff")* — ✅ **proven** *(pending relocation — Phase 9; priority: high — was the biggest crack)*
- **Evidence:** **research settled** ([`s10-research-15-rewind-handoff.md`](../dev/notes/research/s10-research-15-rewind-handoff.md))
  **+ spike passed** (`test_rewind_handoff_live`, **live**, 2026-07-02 — **both** rewind and fork-from-point
  proven end-to-end). Native mechanism confirmed: **`/rewind`** restores conversation state (not just files)
  to any prior prompt checkpoint; **`--fork-session` + `/rewind`-inside-the-fork** is the proven TUI-native
  path for branch-from-N. This **overturns the old blocker** ("no known rollback/fork API"). Transcript
  surgery is ruled out (fragile/unsupported). TypeScript SDK `resumeSessionAt + forkSession` is the best
  non-interactive path — **but the Python SDK lacks `resume_session_at` parity**, so the sidecar uses the
  TUI-native path.
- **Desired final behavior:** from the Agent→Details Timeline, **Rewind** rolls an agent back to a chosen
  message and resumes from there; **Handoff** branches from a chosen point into a *new* agent carrying that
  conversation prefix.
- **Spike established (build carries two caveats):** (1) conversation fork does **not** isolate filesystem
  state — the build needs an explicit per-fork file-state policy (git worktree / code-checkpoint); (2) a
  version gate ≥ **v2.1.191** is required to rewind past a `/clear`. Build item: §11.3 #21 (the
  summary/handoff-artifact half stays #19).
- **Fallback if infeasible:** n/a — proven feasible; whole-session `--resume` + Create-tab prepopulation is
  no longer the ceiling.

**16. System-wide fault detection — the harvest half behind the "System" Error cards** *(→ §5, §7.2, §7.8)* — ◐ **partially proven** *(priority: high)*
- **Evidence:** **spike PARTIAL** (`test_system_fault_harvest_live`, **live**, 2026-07-02): **MCP outage +
  auth expiry are detectable**, but the **usage-cap wording is not matched** (`classify_error` misses the
  subscription-cap phrasing, e.g. "weekly usage limit" → code gap, §11.4 #24), and the *reactive*
  auth-expiry **screen signal is unconfirmed**. The deterministic tmux/WSL/sidecar-liveness probes remain
  ordinary build (body §5/§7).
- **Desired final behavior:** the sidecar detects and raises one coalesced fleet-wide System Error card for the
  non-deterministic faults — account rate/usage cap hit, auth expiry, global MCP outage.
- **Remaining open:** widen the usage-cap matcher (§11.4 #24); confirm a reliable reactive auth-expiry signal;
  then coalesce into one fleet-wide card.
- **Fallback if infeasible:** the System card fires only for the deterministic probes (tmux/WSL/sidecar down);
  the non-harvestable faults are surfaced best-effort from screen text or omitted — recorded as a boundary.

**17. Polling-model scale ceiling** *(→ §4.3, §6.2)* — ◐ **partially proven** *(priority: medium — load test)*
- **Evidence:** **spike measured** (`test_polling_scale_ceiling_live`, **live**, 2026-07-02): the load test
  runs, but the curve is **bad — the ~1 s per-agent `events()` loop degrades from N=1** (~1.3 s/cycle at N=1,
  ~10 s event-lag by N=9), because each cycle makes ~5 WSL spawns × N and crosses the Windows→WSL boundary.
  The mechanism is proven **not** to scale as-is → rework required (batch the spawns + adaptive cadence, code
  gap §11.4 #25).
- **Desired final behavior:** a known, documented agent-count ceiling (and, if needed, an
  adaptive-cadence/backpressure policy) so the fleet degrades gracefully rather than silently bogging down.
- **Remaining open:** implement the batching + adaptive-cadence rework (§11.4 #25), then re-measure the
  practical ceiling.
- **Fallback if infeasible:** document a conservative soft cap and a "slows past N agents" note; adaptive
  cadence deferred.

**18. statusLine `context_window` as a live mid-run context source** *(→ §7.9, §9, DESIGN context dropdown)* — ◐ **partially proven** *(priority: low; grouped with #21)*
- **Evidence:** **spike passed — boundary found** (`test_usage_context_sources_live`, **live**, 2026-07-02):
  the statusLine `context_window` is a **per-turn snapshot** (it refreshes once per turn), **not** a continuous
  mid-run feed. So DESIGN's "can't read *mid-run*" stands for a live gauge, but a per-turn context readout
  **is** available — a genuine improvement over post-hoc JSONL. Complements the unit-proven total-context
  derivation (§10-9 / `test_bridge_unit`).
- **Desired final behavior:** the dashboard reads context-window usage as fresh as the engine exposes it
  (per-turn from the statusLine), feeding §10-9's readout and the run-strip.
- **Remaining open:** wire the per-turn statusLine `context_window` capture; reconcile DESIGN to "per-turn
  snapshot, not a continuous mid-run gauge."
- **Fallback if infeasible:** context stays derived from JSONL / `/context` (per §10-9).

**19. Console `/clear` (and `/compact`) transcript-path orphaning** *(→ §7.13, §8.6, §8.7)* — ◐ **partially proven** *(priority: low)*
- **Evidence:** **spike confirmed the hazard** (`test_console_clear_transcript_live`, **live**, 2026-07-02):
  a Console **`/clear` rotates the JSONL and orphans** the sidecar's pinned `<session-id>.jsonl` resolution
  (`bridge/bridge.py` `session_id_for`/`register_session_id`; `find_transcript`) — new turns are lost to the
  sidecar until re-resolve. **`/compact` is safe** (same file). Fix = re-resolve + `register_session_id`
  after a Console `/clear` (code gap §11.4 #23).
- **Desired final behavior:** after a Console `/clear` or `/compact`, the sidecar still resolves the agent's
  *current* transcript, with no lost history or stale mapping.
- **Remaining open:** implement the post-`/clear` re-resolve (§11.4 #23); `/compact` needs no change.
- **Fallback if infeasible:** document the hazard and re-resolve the transcript path on demand after a Console
  clear.

**20. Bypass & Auto permission-mode launch preconditions** *(→ §6.2, §7.11)* — ✅ **proven** *(pending relocation — Phase 9; priority: low; relates to #1)*
- **Evidence:** **spike passed** (`test_bypass_auto_preconditions_live`, **live**, 2026-07-02): a 5-case
  launch matrix confirms the preconditions — a **Bypass segment that was not pre-armed at launch is SILENTLY
  ABSENT from the mode ring** (it doesn't no-op visibly; it simply isn't reachable). So the UI **must gate**
  Bypass/Auto on the launch flags. Distinct from #1 (mid-run cycling) — this is *launch-time* preconditions.
- **Desired final behavior:** the UI presents Bypass/Auto as available only when the agent's launch actually
  supports them, never as controls that silently do nothing.
- **Spike established:** un-pre-armed Bypass is absent from the ring (not a silent no-op) → the Create panel
  must set the launch flag, and the mode control must disable/hide the segment when its precondition is absent.
- **Fallback if infeasible:** n/a — proven; gate Bypass/Auto on the launch-time choice as established.

**21. Usage / limits source-boundary confirmation** *(→ §7.15)* — ◐ **partially proven** *(priority: low; grouped with #18)*
- **Evidence:** **spike passed — boundaries mapped** (`test_usage_context_sources_live`, **live**,
  2026-07-02): account identity is a **split source** (the `.claude.json` tier fields are not matched by the
  current reader → code gap §11.4 #26), and **live usage % / limits are screen-scrape only** (no clean local
  API surface). So the Usage band can show account identity + scraped live figures, but "from an API" is not
  accurate. Complements the per-agent-cost spike (§10-11).
- **Desired final behavior:** the Settings Usage band is fed from confirmed sources (account from creds;
  usage/limits from the real, reachable surface) before the UI is built against them.
- **Remaining open:** fix the account split-source reader + add an auth-expiry signal (§11.4 #26); build the
  Usage band against the confirmed boundaries (identity + screen-scraped live %).
- **Fallback if infeasible:** show only what a source demonstrably provides (account identity but not a clean
  live-limits API); mark the rest an honest boundary.

**22. Subagent creation / management** *(→ §7.17, §10-8, §10-13)* — 🧪 **decided (2026-07-05): parked (revisit after hooks/lineage)** *(priority: low; overlaps #13)*
- **Evidence:** **research settled** ([`s10-research-22-subagent-management.md`](../dev/notes/research/s10-research-22-subagent-management.md)):
  the surface is mapped. **CREATE** is parent-mediated only — send `@agent-<name> <task>` as literal text to
  the idle parent pane via tmux `send-keys` (no out-of-process spawn API in the non-SDK path). **Observe** —
  `SubagentStart`/`SubagentStop` hooks give structured `agent_id` / `agent_type` / `transcript_path` /
  `last_assistant_message` (closes §10-8 cleanly → §11.3 #22). **STEER** — `SendMessage` resumes a *stopped*
  subagent; mid-turn steering of a *running* one is unproven. **STOP** — no stable single-subagent API
  (`Ctrl+X Ctrl+K` kills all background subagents). (Formerly BB4; sole home since 2026-07-03.)
- **Desired final behavior:** the operator can create and manage (steer / stop) subagents from the dashboard,
  not only observe them.
- **Decided (2026-07-05, operator — Q10 / §F1):** **parked** — the operator accepts the parent-decides model and notes no scaffolding exists yet; revisit after the hooks / lineage substrate lands (§11 #22, priorities note). Operator sketch for the eventual feature: a Compose-workspace **"add agents"** affordance (button or dropdown, plausibly via the existing template-block machinery) that drops a generic **fan-out instruction block** into the prompt — placeholders for agent count and timing, with custom per-fan-out instructions riding in the same block. Still spike-gated when picked up.
- **Current blocker (spike-grade):** the load-bearing claims are docs-derived — `send-keys -l` delivering
  `@agent-<name>` as a parsed mention, the subagent transcript-path schema on the local install, and the
  `Ctrl+X Ctrl+K` timing — each needs a live spike before build.
- **Research/POC must establish:** a spike confirming the `@agent-<name>` create path, the transcript-path
  schema, and the stop-key timing on the installed CLI; active mid-turn steer stays observe-only until proven.
- **Fallback if infeasible:** subagents remain observe-only (§7.17); creation/management stays queued.

### Priority — backlog-port additions (2026-07-03)

Ported from the old backend backlog ([BB]) when it was consolidated into §11: these three carried the
backlog's **(open)** marker — still needing research or a decision before they're buildable — so they
belong in this queue, not §11. Appended as #23 onward per the numbering convention above; they entered
half-formed, by design (see the cheap-entry rule).

**23. Docs in agent context** *(→ §7.6, §7.7)* — ✅ **decided (2026-07-05): scope light → §11 #36** *(priority: medium; ex-BB12)*
- **Evidence:** no code, no test; ported from the backlog's open set 2026-07-03. Half-formed by design.
- **Desired final behavior:** agents dynamically get relevant, up-to-date documentation in context, and
  agents doing systems-level work always have current docs in context.
- **Decided (2026-07-05, operator — Q9 / §F1):** **yes — scope it light.** v1 mechanism: a **curated docs home agents are pointed at (the Library, §7.16)** plus **per-agent doc attachment at launch**; automatic relevance-retrieval stays future. Interface sketch (broad, for the design agents): the **Library is the hub**, reusing the review-panels' nav-rail lens pattern but organized by task / project / subproject (the Outline tab possibly going icon-based to free a slot). Buildable (light) → §11 #36.
- **Remaining open (post-decision):** only *automatic* relevance-retrieval — how "relevant and current" docs
  are selected and refreshed per agent role (context injection / MCP docs server / hook-pushed digests remain
  the candidate mechanisms for that future layer). The v1 curated-Library + per-agent-attach path is decided.
- **Research/POC must establish:** a delivery mechanism, and how relevant/current docs are selected and
  refreshed per agent role.
- **Fallback if infeasible:** manual doc references in prompts (status quo).

**24. AI-touched file tracking** *(→ §7.5 attribution, DEVLOG practice)* — ✅ **decided (2026-07-05): elevated → §11 #37 (feeds lineage)** *(priority: high; ex-BB13)*
- **Evidence:** no code, no test; ported from the backlog's open set 2026-07-03. Half-formed by design.
- **Desired final behavior:** what AI has touched is tracked, e.g. a local per-directory index file
  (`index.md`) or equivalent.
- **Decided (2026-07-05, operator — Q9 / §F1):** **elevated, not parked.** Attribution rides **per-agent git identity** — each agent commits under its own author name + a synthetic per-agent email, so "what did AI touch" becomes a **git query with no maintained ledger**. The operator ALSO wants the **per-folder `index.md` files** pursued (he had begun these himself and values them); git identity is the attribution *backbone* and the index files ride on top of it, with the hand-maintained-inventory drift risk **flagged and accepted**. Pursue **as a priority together with agent commit tracking**; this **feeds the lineage / Agent-Archive substrate** (§11 #18, priorities note). Buildable → §11 #37.
- **Resolved shape:** git-derived attribution (per-agent identity) is the backbone; per-folder `index.md`
  files ride on top; a central ledger is rejected. Product value is validated (operator priority).
- **Research/POC must establish:** the cheapest reliable attribution mechanism, and whether it earns its
  maintenance cost.
- **Fallback if infeasible:** rely on git history + DEVLOG (status quo).

**25. Special-asset sourcing check** *(→ 🔌 Claude config, §8.1)* — ✅ **decided (2026-07-05): needed but deferred (fold into hooks pass)** *(priority: low; ex-BB14)*
- **Evidence:** no code, no test; ported from the backlog's open set 2026-07-03. Half-formed by design.
- **Desired final behavior:** skills and other special Claude Code assets are confirmed to be pulled from
  the ideal source.
- **Decided (2026-07-05, operator — Q9 / §F1):** **yes — the audit is genuinely needed** (the current setup is suboptimal: ad-hoc, duplicate `AGENTS.md` files), **but deferred** — current churn makes now the wrong moment; **fold it into the hooks setup pass** (distinct from the dashboard's lifecycle-hook *ingestion*, §11 #22 — this is Claude Code asset-sourcing hygiene). Decided-but-deferred; stays queued.
- **Current blocker:** "ideal source" per asset type (skills, agents, hooks, plugins) is unestablished.
- **Research/POC must establish:** an inventory of where each special asset currently comes from, and a
  per-type sourcing rule.
- **Fallback if infeasible:** current ad-hoc sourcing stands.

### Priority — coverage-audit remainder (2026-07-04)

The Phase-6 homing of the last coverage-audit orphans ([`archive/dev/notes/scratch/2026-07-02-coverage-audit-orphans.md`](../archive/dev/notes/scratch/2026-07-02-coverage-audit-orphans.md)): the Tier-2 "moderate" items still unhomed after the Phase-4 harvest, the Tier-3 production-hygiene minors, and the two Tier-4 design-lane items worth elevating. Appended as **#26 onward** (same append-don't-interleave convention as #14/#23, to preserve existing numbering). Each carries a genuine **product/policy decision that is the operator's to make**, so it is homed here **as an open question, deliberately not decided** — the leading candidate (where the audit suggested one) is noted but not adopted. The consolidated call-list lives in the **§F1 decision register** of the workflow tracker ([`dev/notes/scratch/2026-07-03-doc-integration-tracker.md`](../dev/notes/scratch/2026-07-03-doc-integration-tracker.md)) and is presented to the operator as a batch; when the operator rules, each item converts to a body decision or a Decided omission and leaves the queue. **Ruled 2026-07-05:** the operator worked through the whole Q1–Q11 batch, so each #26–#37 entry now carries a **Decided** line (the buildable graduates are listed in §11.5). They keep their §10 slot, annotated-decided, until the Phase-9 relocation moves the settled ones into the body.

**26. Turns "by-tool" breakdown + the "Coordinating" slice** *(→ §7.9, §7.10, §10 #9)* — 🧪 **decided (2026-07-05): display parked, capability retained** *(priority: low — deprioritized)*
- **Evidence:** no derivation defined — the Agent→Details Turns accordion expands to a per-tool split (Read/search · Edit · Bash · MCP · Subagent · Web · **Coordinating** · Remaining), but §7.9 covers turn *counting* for caps only, and the cross-agent "Coordinating" bucket has no source. The sibling *context*-by-category is §10 #9. Tracked: §F1.
- **Desired final behavior:** the Turns accordion shows a trustworthy per-tool breakdown, including a "Coordinating" slice for cross-agent work.
- **Decided (2026-07-05, operator — Q7 / §F1):** **park the rich display** — the total turn count (§7.9) suffices meanwhile; no spike scheduled now. The *underlying capability is retained and valued*: raw per-turn tool data already lives in the JSONL transcripts and the sidecar already parses tool events for the feed, so nothing is lost while this is parked — **transcript retention (§8.6) is the guard**. The only genuinely unproven piece stays the **"Coordinating"** cross-agent attribution. Bucket-vocabulary caveat: at pickup, re-frame the tool-bucket list against the planned reduction of feed block/filter types (some listed blocks may be trimmed or never existed), so the current vocabulary is not settled.
- **Spike must establish:** whether per-tool turn counts are derivable from the transcript's `tool_use` blocks, and whether a "Coordinating" slice (link / scratch / inbox activity) can be attributed at all — or whether the breakdown is cut to the derivable tools only.
- **Fallback if infeasible:** show only the derivable tool buckets (or the total turn count alone, §7.9) and drop the "Coordinating" slice.

**27. Voice dictation — speech-to-text pipeline** *(→ §7.14)* — 🧪 **direction decided (2026-07-05); needs a quality spike** *(priority: medium)*
- **Evidence:** no capture→transcribe→insert path — §7.14 names "a voice mic" on the Compose / Plans / Documents editors, but the STT mechanism is unchosen and unwired. Tracked: §F1.
- **Desired final behavior:** the per-field mic captures speech and inserts transcribed text into the editor.
- **Decided direction (2026-07-05, operator — Q4 / §F1):** dictation must be **genuinely good** — the operator finds OS-level dictation mediocre. The spike compares the browser/Electron built-in speech path against a **high-quality library (Whisper-class local transcription)**: if the built-in is close, it wins on simplicity, but a meaningfully better library is preferred over convenience. Resource caveat: weigh a local model's compute cost against the "stay smooth on a modest laptop" constraint (cf. Q10 #36). Intent is set; the 🔧 spike still settles which path — options were client-side **Web Speech API** (free, built-in) vs. a **sidecar transcription service** (candidates-note #16).
- **Fallback if infeasible:** the mic stays a visual affordance until the path lands.

**28. Frontend degraded-mode policy + polling backoff** *(→ §4.3)* — ✅ **behavior decided (2026-07-05) → §11 #34; display consolidation → design-lane** *(priority: medium)*
- **Evidence:** §4.3 fixes the poll cadences, and SSE reconnect + the "Sidecar offline" chip are homed, but there is **no defined degraded-UI policy when `/health` fails** and **no backoff** on the fixed poll cadences. Distinct from #17's scale-ceiling adaptive cadence — this is failure-mode UX plus a retry policy. Tracked: §F1.
- **Desired final behavior:** when the sidecar is unreachable, the poll-driven readouts degrade predictably and polling backs off rather than hammering the fixed cadence.
- **Decided (2026-07-05, operator — Q3 / §F1):** on `/health` failure the poll-driven panels **freeze and show last-known values, visibly marked stale**, while polling **backs off** to a gentle retry until the sidecar returns (the standard calm pattern; no pointless load on a dead endpoint). This *behavior* is buildable → §11 #34. **Open, and routed to the design lane:** the *display* of system-health is one underlying question with §10 #16 (System-fault cards) and the signals scattered across three surfaces today — connector badges (Settings), System Error/Warning inbox cards (§7.8), and the "Sidecar offline" chip (§4.3) — which the operator wants **consolidated into one always-visible system-health indicator in the app chrome** (leading candidate surface: the footer), with a broadened state vocabulary (add *down* + *stale/degraded*) reconciled with §10 #16, popover/drill-in inspection (a sidecar-log tail — §11 #31 — is a candidate drill-in), and reconciliation with the operator's separately-captured title-bar Connected-chip upgrade note. That display work is DESIGN.md's (six-file propagation) and is **not edited in this workflow**.
- **Fallback if infeasible:** today's single "Sidecar offline" chip with unchanged poll cadences.

**29. Schema versioning / migration of the committed store** *(→ §8.1, §8.2)* — ✅ **decided (2026-07-05) → §11 #30** *(priority: low)*
- **Evidence:** only the one-time `.awl`→`.awl-cc-dash` rename (§11.2 #1) is homed; the committed `state/` JSON carries **no `schema_version` stamp or forward-compat policy**. Tracked: §F1.
- **Desired final behavior:** a future format change can read (or migrate) data written by an older version without silent breakage.
- **Decided (2026-07-05, operator — Q1 / §F1):** stamp a `schema_version` into the committed `state/` **now** — cheap insurance so a later format change can still read old data (part of the "pragmatic single-machine v1" posture). Buildable → §11 #30; the §8.7 open-question note is superseded. Migration *machinery* stays deferred (YAGNI until a format actually changes).
- **Fallback if infeasible:** none needed — the do-nothing path *is* one of the two options.

**30. Sidecar crash-supervision** *(→ §2, §9.9)* — ✅ **decided (2026-07-05): manual relaunch is the v1 model** *(priority: low)*
- **Evidence:** agent recovery is homed (§9.9), but in the **two-process bat-file model** the "who restarts a crashed sidecar" question is only stated conditionally inside the unbuilt one-click-launch item (§10 #10). Tracked: §F1.
- **Desired final behavior:** a crashed sidecar recovers (or is known to require a manual relaunch) without losing the running agents.
- **Decided (2026-07-05, operator — Q1 / §F1):** accept **manual relaunch** for v1 — agents survive in tmux and state is written as-it-happens, so a dead sidecar loses nothing but the live readouts. Auto-restart supervision is **deferred** (revisit only with unattended / multi-machine operation; it folds into §10 #10 if pursued). No new build item — a recorded posture.
- **Fallback if infeasible:** manual relaunch is the shipped model.

**31. Git-merge policy on the committed `.awl-cc-dash/` state** *(→ §8.7)* — ✅ **decided (2026-07-05): single-machine, no merge policy** *(priority: low)*
- **Evidence:** §8.7 covers in-process atomic write-replace only; two branches/machines editing the whole-file JSON state have **no merge policy**. Tracked: §F1.
- **Desired final behavior:** concurrent edits to the committed project state from two branches/machines have a defined resolution (or a recorded decision that this is out of scope).
- **Decided (2026-07-05, operator — Q1 / §F1):** accept **single-machine, no merge policy** — consistent with the cross-machine caveat already accepted at §9.9; a concurrent-edit conflict is a manual git resolution. No build item — a recorded posture. (A merge/reconcile story is revisited only if multi-machine operation is pursued.)
- **Fallback if infeasible:** the single-machine assumption stands; a conflict is a manual git resolution.

**32. Security on an untrusted network** *(→ §2)* — ✅ **decided (2026-07-05): OS firewall is the boundary** *(priority: low)*
- **Evidence:** §2 accepts the no-auth `0.0.0.0:7690` bind for a single-user machine at home, but does **not** address the mutating control API being exposed when the laptop travels onto café / office Wi-Fi. Tracked: §F1.
- **Desired final behavior:** the exposed control API is safe (or consciously accepted) on an untrusted network.
- **Decided (2026-07-05, operator — Q2 / §F1):** **OS-firewall-as-the-boundary** is the accepted posture — the Windows firewall blocks inbound by default, the effective boundary for a personal laptop, and the no-auth `0.0.0.0:7690` bind stays a deliberate, documented choice (§2). A "travel mode" (localhost-only bind or a token on untrusted Wi-Fi) is noted as a **cheap future add** if the operator starts working from public networks — not built for v1.
- **Fallback if infeasible:** the OS firewall is the boundary; document it as the accepted posture.

**33. Sidecar logging / observability** *(→ §2, §9)* — ✅ **decided (2026-07-05) → §11 #31** *(priority: low)*
- **Evidence:** the sidecar keeps only ad-hoc stdout — **no decided destination or retention** for its own process logs, so a failure leaves little trail. Tracked: §F1 *(newly surfaced 2026-07-04 during Phase-6 homing)*.
- **Desired final behavior:** the sidecar writes a proper, bounded log to a decided home so a crash/fault is diagnosable.
- **Decided (2026-07-05, operator — Q1 / §F1):** the sidecar writes a **small, size-bounded log file** under the gitignored `sidecar/runtime/`, so a crash/fault leaves a trail (not stdout-only). Buildable → §11 #31. Pairs with the health-drill-in tail view sketched under Q3 (a candidate consumer of this log).
- **Fallback if infeasible:** ad-hoc stdout stands.

**34. Response-format preamble — option-set + apply/persist model** *(→ §7.14)* — ✅ **decided (2026-07-05) → §11 #32** *(priority: low)*
- **Evidence:** §7.14 ships the response-format preamble control, but its **option set and how the instruction reaches/persists to the agent** are undefined. Tracked: §F1.
- **Desired final behavior:** the operator picks a response-format from a defined menu, and the choice reaches the agent and persists at the chosen scope.
- **Decided (2026-07-05, operator — Q5 / §F1):** a **basic per-agent preset menu** for v1 — a short list of response-formats (including the operator's TL;DR-table + emoji-status style) chosen once per agent and applied to all its replies. A per-message override is a later nicety, not v1. Buildable → §11 #32.
- **Fallback if infeasible:** a single freeform preamble field with no preset menu.

**35. Agent name pool / "randomize" source** *(→ §7.5)* — ✅ **decided (2026-07-05) → §11 #33** *(priority: low)*
- **Evidence:** the Create panel's randomize-name affordance (and any auto-name) has **no defined name pool** (deferred in [`sidecar/identity.py`](../sidecar/identity.py)); §7.5 defines the colour/icon pools but not a name pool. Tracked: §F1.
- **Desired final behavior:** "shuffle a fresh agent name" draws from a defined source.
- **Decided (2026-07-05, operator — Q6 / §F1):** a **curated human-name pool + randomize**, with user-typed names always available. Storage decided in-conversation: a flat JSON array at `assets/names/agent-names.json` (optional theme-grouping later); the operator will have a separate agent generate the pool. Buildable → §11 #33.
- **Fallback if infeasible:** names are user-typed and the randomize affordance is dropped or disabled.

**36. Rich visual content in Plans/Docs** *(→ DESIGN.md; design-lane)* — ✅ **decided (2026-07-05): pursue → design-lane (not a v1 gate)** *(priority: low)*
- **Evidence:** mermaid / charts / diagrams + visual commenting in Plans/Docs — a recurring ask, genuinely unhomed in DESIGN. Tracked: §F1. **Design-lane item:** the design surface is owned by the live design agent; this workflow does not edit DESIGN.md — this entry is the architecture-side pointer only.
- **Desired final behavior:** Plans / Documents can render rich visual content (diagrams / charts) with visual commenting.
- **Decided (2026-07-05, operator — Q10 / §F1):** **wanted** — pursue, elevated to the design lane *when it's ready for it* (not a v1 gate). Operator caveat: rich visuals must **stay smooth on a modest laptop**. Routes to the design agent for a DESIGN.md home; not built or design-edited here.
- **Fallback if deferred:** stays a parked design-lane idea until the design phase picks it up.

**37. Authors / authorship view for Plans & Documents** *(→ §8.5, DESIGN.md; design-lane)* — ✅ **rescoped (2026-07-05): display landed in design; provenance wiring → §11 #35** *(priority: low)*
- **Evidence:** provenance *data* is homed (§8.5 sidecar: created-by / when / session); the *display* — a nav-rail "Authors" lens — **has since landed in the design system** (the [ND] design run; see DESIGN.md's review-panel section). Tracked: §F1.
- **Desired final behavior:** an Authors view surfaces the authorship/provenance already captured in the doc sidecars.
- **Resolved (2026-07-05, operator — Q10 / §F1):** **no product decision needed** — the Authors-lens display already landed in the design system, so the remaining scope is **system-side provenance wiring only** (surface §8.5's created-by / when / session into the landed view). Buildable → §11 #35.
- **Fallback:** n/a — resolved; the provenance data (§8.5) already exists and the view has landed in design.

### Decided omissions (not open questions)

Settled engine limits — recorded here so they are not re-raised as open questions, and **not** part of the
numbered queue. An item lands here only after a **spike** actually proves no path exists (a code no-op is not
a proof).

- **Two spike-proven tail limits (2026-07-04), pending relocation here at Phase 9:** **#4's** immediate
  mid-turn Inject (`test_inject_tail_live` — typeahead is held to the turn boundary, pure Next/Queue) and
  **#7's** engine-side completion fraction (`test_runstrip_tail_live` — the engine emits numerators only, no
  denominator). Both keep their numbered §10 slot for now (marked ⛔ resolved-at-fallback) and move here
  formally in the Phase 9 refactor; their shipped fallbacks are the final models.
- Fast/Thinking live control was previously parked here on a code-no-op assumption; the mode-control research
  surfaced untested `Meta+T` / `Meta+O` keybinding levers, so both moved back into the queue — **both are now
  ✅ proven** (#2 `Meta+T` modal; #3 `Meta+O` opens the Fast panel + `Space` toggles it, once Fast credits
  were enabled, 2026-07-04).

---

## 11. Build backlog & queue

The single home for **decided, buildable** work — the *know-how, queued to build* side of the line whose
*don't-yet-know* side is §10. Everything actionable lands here, in one place: the body's ⚠ Today markers
(indexed in §11.1), the ported backend backlog (ex-[BB] ids, 2026-07-03), and build gaps surfaced by
spikes. A row here is a **queue entry, not a spec** — the body section each item points at owns the
detail; read it before building.

**Entry:** an item enters only once it is decided and buildable. If it still needs research, a spike, or a
product decision first, it belongs in §10 — the two sections model the pipeline (§10 question → spike →
§11 build item → body marker cleared). **Exit:** an item leaves by being **built** (its ⚠ Today markers
clear and the row is removed — DEVLOG keeps the history) or by being **demoted to §10** (building revealed
an open question).

### 11.1 ⚠ Today index — build debt by body section

One row per body section carrying ⚠ Today markers, so the doc's whole build debt is scannable in one
place. The body markers are canonical — this is a pointer table; update the row when a marker is added or
cleared. **Queue item** ties the debt to the numbered backlog below (or to §10 where the debt is gated on
an open question); **—** means the debt has no queue item yet.

| Body § | What's owed today | Queue item |
|--------|-------------------|------------|
| §3.1–§3.5, §9.1 | The whole Projects surface: picker tab, active-project chip, close dialog, `projects.json` index, open/close flow | — |
| §4.4 | Renderer trails the finished mockup (16/25 colours, Console gaps, marquee omitted) — deliberately deferred until design churn ≈ 0 | — (deliberate deferral) |
| §5.2 | Console live-mirror feed not wired; no Projects endpoint surface | §10 #5 / — |
| §6.4, §8.1 | Launch-config dir still `~/.awl-agents/` (target `~/.awl-cc-dash-agents/`) | #9 |
| §7.2 | No reserved System identity; no System-sourced Error cards | §10 #16 |
| §7.3 | Inject always degrades to hook-boundary; no instant mid-turn delivery | §10 #4 |
| §7.5 | React client ships 16 of 25 colours (parity lag); identity editing + `--name`/`/rename` registration speced, not wired | — (§4.4 deferral) |
| §7.6 | Link holds a multi-select relationship list (should be one each); no Piggyback trigger value; exchanges counted as pairs (one-way links burn caps at half rate) | — |
| §7.7 | Scratchpad at `.awl/scratchpad.md`; board + watermarks memory-only, `.md` never loaded back | #1, #3 |
| §7.8 | No Response card type; inbox in-memory | #3 |
| §7.10 | Marquee omitted in the React UI | — (§4.4 deferral) |
| §7.12 | Delete misses the project `state/` files; retired numbers memory-only | #11, #3 |
| §7.13 | Live mirror + keystroke passthrough not wired; React Console stubbed in places | §10 #5 |
| §7.15 | Per-agent cost not surfaced yet — proven feasible via `/cost` (§10 #11 → ✅), honest-blank overturned | §10 #11 |
| §7.16 | Plan approve→resume proven (§10 #6 → ✅) but unwired; plans listed non-recursively; central `plan-reviews.json`; Documents read-only, no comment store; no create/delete endpoint yet; no Assets surface | #13, #6, §10 #6 |
| §8.1 | `project_root()` returns raw cwd (no canonicalization); project folder still `.awl/` | #1, #2 |
| §8.2 | Only `scratchpad.md` + `plan-reviews.json` exist; roster lives app-level in `sessions.json` | #1, #3 |
| §8.3, §8.4 | Every Persist row still in-memory or app-level (see the tables' ⚠ Today columns) | #3, #4, #11 |
| §8.5 | Central `plan-reviews.json` keyed by filename (rename orphans reviews); Documents have no comment store; no `plansDirectory` in materialized settings | #6, #7 |
| §8.6 | Transcript path recomputed every read, never persisted; retention unpinned (30-day default applies) | #4, #5 |
| §9.9 | Dead-tmux records pruned instead of cold-restored; nothing invokes `claude --resume` | #8 |

### 11.2 Storage & lifecycle set

Implements the §8 storage model and §9 lifecycle flows — **§8/§9 own the detail; read them first.**
(Ex-IDs BB15–BB25 are temporary traceability scaffolding, stripped in the final refactor pass.)

1. **Storage rename + subdir taxonomy** *(ex-BB15 → §8.1, §8.2)* — rename `.awl/` → `.awl-cc-dash/`; add
   path accessors for `plans/`, `docs/`, `assets/`, `state/`; one-time migration of existing `.awl/`
   contents; scratchpad moves to `docs/scratchpad.md`. Where: `_AWL_DIRNAME` + accessors in
   [`sidecar/storage.py`](../sidecar/storage.py).
2. **Canonical project root** *(ex-BB16 → §8.1 "`<project>` defined")* — derive one canonical `<project>`
   from `cwd` (git top-level; symlink + `/mnt`-alias normalization) and use it everywhere a cwd key scopes,
   including the scratch project key. Where: `storage.project_root()` ([`sidecar/storage.py`](../sidecar/storage.py)),
   [`sidecar/main.py`](../sidecar/main.py).
3. **Per-project state store** *(ex-BB17 → §8.2, §8.3)* — build the `state/` persistence layer (atomic
   write-replace; append for `.jsonl`); move the roster out of `sessions.json` → `state/agents.json`;
   persist inbox (open type set), links, routing overlay, bookmarks, and retired numbers; reload the
   scratchpad board from its `.md` on load. Load lazily on the first session whose canonical root resolves
   to the project, cache per root, write-through thereafter. Where: `sidecar` modules (`runtime_store` /
   `inbox` / `links` / `watermark` / `scratchpad`).
4. **Persist session id + transcript path** *(ex-BB18 → §8.4, §8.6)* — persist `claude_session_id` + the
   resolved transcript path per agent in `state/agents.json`; refresh on resolve. Where:
   [`sidecar/drivers/bridge.py`](../sidecar/drivers/bridge.py), [`bridge/transcript.py`](../bridge/transcript.py).
5. **Pin transcript retention** *(ex-BB19 → §8.6)* — pin `cleanupPeriodDays: 3650` in the materialized
   per-agent settings. Where: `_build_settings()` ([`sidecar/drivers/bridge.py`](../sidecar/drivers/bridge.py)).
6. **Per-doc metadata sidecars** *(ex-BB20 → §8.5)* — `<doc>.meta.json` read/write (verdict, comments,
   quote-anchors, provenance), replacing `plan-reviews.json`; Documents comment endpoints;
   dashboard-mediated rename of the doc + sidecar pair; orphan detection/re-link. Where:
   [`sidecar/library.py`](../sidecar/library.py), [`sidecar/storage.py`](../sidecar/storage.py).
7. **Absolute `plansDirectory`** *(ex-BB21 → §8.5; depends on #2)* — set `plansDirectory` to the absolute
   WSL path `<canonical-root>/.awl-cc-dash/plans` in the materialized per-agent settings (a relative `./`
   resolves against raw cwd and breaks subfolder launches). Where: `_build_settings()`
   ([`sidecar/drivers/bridge.py`](../sidecar/drivers/bridge.py)).
8. **Cold-restore on startup** *(ex-BB22 → §9.9; enables #12)* — on startup, dead-tmux records **resume**
   (`claude --resume <claude_session_id>`, correct cwd) instead of prune. Needs a bridge resume-launch path
   (today a passed `session_id` only pins `--session-id` — still a NEW conversation — and `resume()`'s
   dead-session fall-through calls `create()` with no id). Graceful degrade = restore data, manual
   re-resume. *(Mechanism proven feasible by the one-click-launch + rewind/handoff live spikes.)* Where:
   [`sidecar/main.py`](../sidecar/main.py), [`bridge/bridge.py`](../bridge/bridge.py).
9. **WSL home dir rename** *(ex-BB23 → §6.4, §8.1)* — rename `~/.awl-agents/` → `~/.awl-cc-dash-agents/`.
   Where: `WSL_AWL_DIR` ([`bridge/paths.py`](../bridge/paths.py)).
10. **Dogfood the committed store** *(ex-BB24 → §8.2 self-dogfooding; depends on #1)* — commit this repo's
    `.awl-cc-dash/`; add a CLAUDE.md note (runtime data, deliberate commits); confirm tests stay on temp
    dirs. Where: `.gitignore`, `CLAUDE.md`.
11. **Delete → project state files** *(ex-BB25 → §9.10, §7.12; depends on #3)* — extend the
    delete/tombstone flow to the project `state/` files — the roster entry plus
    inbox/links/routing/bookmarks rows — not just the runtime record + transcripts. Where:
    [`sidecar/deletion.py`](../sidecar/deletion.py), [`sidecar/main.py`](../sidecar/main.py).

### 11.3 Feature backlog

Decided, buildable features with no storage-set dependency ordering (ex-IDs BB1–BB10; ex-BB4 *Subagent
Management* is **not** here — it carries an open question and lives at §10 #22; ex-BB11 *Tasks* was
absorbed into §10 #13). **#21–#22 are spike-derived additions** (2026-07-02 batch, now buildable), not ex-BB.

12. **Load past agents** *(ex-BB1; gated on #8)* — load past agents by name, ID, or via file explorer.
    Fleet Setups save/load and startup auto-reconnect exist; still no on-demand per-agent resume (endpoint
    or UI).
13. **Plans action loop** *(ex-BB2 → §7.16, §9.7)* — the Library → Plans tab (review rail + verdicts) is
    built; still need plan edit-in-place and wiring the Approve/Revise verdicts into the live flow
    (approve → resume the agent; the resume half rides the spike-gated Plan hook, §10 #6).
14. **Queue awareness** *(ex-BB3 → §7.3, §7.6)* — for >2 linked agents, share in message front matter that
    another agent's message is queued, so an agent can decide whether to wait.
15. **Git automation** *(ex-BB5)* — handle and semi-automate Git tasks, including commits.
16. **Change-log watcher** *(ex-BB6)* — an agent that watches codebase changes and auto-updates change
    logs (or similar).
17. **System-check agent** *(ex-BB7)* — a system-checking agent that's easy to run.
18. **Agent archive** *(ex-BB8; spans §7.12 Retire/Delete + §8.4 roster; **decided build item — Q11, 2026-07-05**)* — a
    roster / data-table of **per-agent records** with distinct IDs (or one file per agent instantiation — open),
    archived **by default**: retiring an agent is a **deep-freeze**, not a discard. Records are **light except
    transcripts** (referenced in place per §8.6, never copied); occasional purge is acceptable; **Delete stays a
    true delete**. The schema **reserves lineage fields** (parent / fork / handoff) — a separate operator-side
    agent is exploring lineage tracking + graphical display, tying to the per-agent git-identity attribution
    (§11.5 #37). The operator states the system "is not useful without it," so it stays a decided §11 item — the
    ruling that resolved the Phase-9 §10↔§11 placement gate. **HIGH priority** (the lineage/archive substrate,
    alongside lifecycle-hook ingestion #22).
19. **Handoff artifacts** *(ex-BB9 → DESIGN.md's explicit deferral; gated on §10 #15)* — generate a
    summary/handoff report on Handoff, rather than the plain context-carry-over (which comes first).
20. **Native agent-teams messaging** *(ex-BB10; gated on §10 #13 research)* — adopt Claude Code's built-in
    inter-agent messaging in place of the custom sender/trigger wrapping, once the native feature matures.
21. **Rewind / Fork (Timeline)** *(→ §7.5, §9.2, §9.9; spike-passed §10 #15)* — implement `/rewind`
    (tmux-driven, conversation-restore) + `--fork-session` + `/rewind`-inside-the-fork for branch-from-N; add
    an explicit per-fork **file-state isolation** policy (git worktree / code-checkpoint) and a **≥ v2.1.191**
    version gate at session create. (The summary/handoff-artifact half is #19; the Create-tab prepopulation
    half is homed at §9.2/§7.5.)
22. **Hook lifecycle ingestion & run-state arbiter** *(→ §6.2, §7.4, §7.11, §7.17; spike-proven §10 #14,
    closes §10 #8)* — register HTTP `SubagentStart`/`SubagentStop` (+ the run-state event set) to the sidecar;
    a per-agent arbiter merges pushed run-state / `permission_mode` (authoritative-when-fresh) with the
    screen-poll fallback (Option C hybrid), and the subagent hook fields become the roster's active-vs-quiet
    signal. Where: [`sidecar/hookbus.py`](../sidecar/hookbus.py), [`sidecar/main.py`](../sidecar/main.py),
    [`sidecar/drivers/bridge.py`](../sidecar/drivers/bridge.py).
29. **Import external Claude context** *(→ §7.3, §7.16, §8.6; the extractors exist today — [`dev/tools/claude-context-extractor/`](../dev/tools/claude-context-extractor/))* — wrap the two working exporters (`extract-web.py` = claude.ai cloud chats via the sessionKey cookie; `extract-desktop.py` = the desktop app's local-agent-mode sessions, on-disk, no auth) behind a sidecar **import module** (a new coordination-spine feature module beside `library.py` / `scratchpad.py`) plus a thin frontend **Import** control, so an outside Claude session can be pulled into the dashboard by title. One import engine, one selectable destination: **(a) agent-to-agent** — drop the pulled context into an agent's prompt queue / Inbox (§7.3) so one agent can hand another external context [the operator's primary interest]; **(b) operator-facing** — render it in a panel to read/copy, the acute pain today since the desktop app's own export is broken/misplaced; **(c) Library** (§7.16) — park it as a reusable reference doc. Deliberately distinct from §8.6, which governs agents' *own* transcripts — this ingests *external* Claude history. **Open (operator's call, not started, explicitly not critical):** destination order (default (a) first, (b) close behind) and which panel hosts the Import button.
38. **Prompt/UI-text markdown library (scope-aware)** *(→ §7.14, §8.2, §8.4; operator-decided 2026-07-04)* — one human-editable **markdown prompt library** as the single home for every UI-injected/canned text the dashboard sends on the user's behalf: the post-reviewer-request instructions, the text behind the reviewer-request **Send** and the Library Plans/Documents **Revise** button, Compose **snippets + templates**, the Compose **Revise scope chip** and the **Response (Structure)** options, and the Team Feed **Summarize** action (which may route to a small system-run utility model rather than an agent) — and likely more as they surface. Format: markdown with the `##` group / `###` item convention (JSON kept only where it genuinely eases template placeholder fill-in), organized by purpose (e.g. `responses.md`, `snippets.md`, `actions.md`). **Scope-aware, two scopes** (the operator's settled scope model — "System" = the persistent cross-project store, absorbing the old "User" scope; the lean is `~/.claude` for the shared runtime docs): a **System copy + a Project copy** (`<project>/.awl-cc-dash/`, §8.2). Includes adding these runtime doc types to the **§8.4 master data-type table** (one row per type) — they are not tracked there yet. The design-lane consumers (the Compose Snippets dropdown, the Documents scoped/typed browser) are queued in the design lane.
39. **Per-turn settings + summary capture** *(→ §7.5 Timeline, §7.14; feeds #21 Rewind/Fork and §11.5 #32)* — capture, per Timeline turn: the agent's **settings at that turn** (model + mode/effort/thinking) and a **concise one-line turn summary**, so the Rewind/Handoff Timeline turn rows can render a settings string + summary per point and the collapsed Team Feed / History cards can show a one-line preview. Where the summary comes from ties to the response-format preamble (§11.5 #32) — the lean is agents leading every reply with a one-liner. The turn-row *display* is the design lane's queued restyle; this item is the capture/storage side.
40. **Workflow approval routed through the Inbox** *(→ §7.3, §7.11; spike-proven 2026-07-04 — [`tests/workflow_approval_probe/`](../tests/workflow_approval_probe/))* — intercept a Claude Code `Workflow` tool call with a **PreToolUse hook** and surface it as an Inbox **Review** card (the renamed Plans-&-Docs section) with an Approve/Reject round-trip. The spike proved every leg live: the hook **fires** for the `Workflow` tool and carries the **full script preview** in `tool_input.script` (name/description/phases recoverable for the card content), a hook **deny aborts** the workflow and **allow launches** it, the hook verdict **preempts** the built-in "Run a dynamic workflow?" dialog (so the dashboard can be the sole gate), and the on-pane dialog remains a working fallback. Workflow subagents are headless/one-shot (≠ the steerable regular subagents), so the linked future **Subagents tab** in the Agent panel is a read-only *tracking* surface, not a control one (back-burnered); if a workflow ever needs editing or feedback, reuse the Library editor infrastructure rather than duplicating it. The Inbox card *design* is queued in the design lane.

### 11.4 Spike-surfaced code fixes (2026-07-02)

Concrete code gaps found by the 17-spike batch (and the native-coordination research). **Document-only — no
product code is changed in this workflow;** these are the queued cleanup, deferred to the consolidated fix
push. Each cites the §10 item that surfaced it.

23. **Console `/clear` transcript re-resolve** *(→ §7.13, §8.6, §8.7; §10 #19)* — after a Console `/clear`,
    re-resolve + `register_session_id` so the pinned transcript follows the rotated JSONL (`/compact` is safe,
    no change). Where: [`bridge/bridge.py`](../bridge/bridge.py), [`sidecar/main.py`](../sidecar/main.py).
24. **Usage-cap error matcher** *(→ §7.2, §7.8; §10 #16)* — extend `classify_error` to match subscription
    usage-cap wording ("weekly usage limit", …), which the spike found unmatched. Where:
    [`sidecar/inbox.py`](../sidecar/inbox.py).
25. **Polling-scale rework** *(→ §4.3, §6.2; §10 #17)* — batch the ~5 WSL spawns/cycle and add an adaptive
    cadence so the fleet stops degrading from N=1. Where: [`sidecar/drivers/bridge.py`](../sidecar/drivers/bridge.py).
26. **Account split-source + auth-expiry reader** *(→ §7.15; §10 #18/#21)* — read account tier from the
    correct source (`.claude.json` tier fields are currently unmatched) and add an auth-expiry signal. Where:
    [`sidecar/settings_io.py`](../sidecar/settings_io.py).
27. **Real Electron-main sidecar-lifecycle POC** *(→ §2, §4.1; §10 #10)* — the spike modeled
    spawn/supervise/shutdown in Python; build the real Electron-main POC preserving detach-on-close. Where:
    [`frontend/`](../frontend/).
28. **Sidecar `Task`→`Agent` parser audit** *(→ §7.17; §10 #13)* — confirm the transcript parser keys on the
    current `Agent` tool name (renamed from `Task` in v2.1.63) and add dual-name compatibility so subagent
    events aren't silently missed. Where: `sidecar` transcript/serialize path.

### 11.5 Operator-decided additions (2026-07-05)

The buildable items graduated from §10 when the operator ruled the Phase-9 decision batch (tracker §F1 / the
Operator-answers block). Each cites the §10 item and the operator question it resolved. **Priority flags the
operator voiced in the same pass:** #37 (per-agent git identity → lineage) is **HIGH**, alongside hook
lifecycle ingestion (§11.3 #22) and the Agent Archive (§11.3 #18); **transcript retention (§11.2 #5) is
URGENT** — the 30-day `cleanupPeriodDays` default is live *today* (§8.6 ⚠), so it is the one action-now item
independent of the rest.

30. **Schema-version stamp** *(→ §8.2, §8.7; §10 #29 / Q1)* — write a `schema_version` field into the
    committed `state/` JSON at write time; readers validate/tolerate it. Migration *machinery* stays deferred.
    Where: state-store writer ([`sidecar/runtime_store.py`](../sidecar/runtime_store.py), [`sidecar/storage.py`](../sidecar/storage.py)).
31. **Sidecar log file** *(→ §2, §9; §10 #33 / Q1)* — write a small, size-bounded (rotating) diagnostic log
    under the gitignored `sidecar/runtime/`, so a crash/fault leaves a trail instead of vanishing to an
    unattached stdout. Where: app logging config ([`sidecar/main.py`](../sidecar/main.py)).
32. **Response-format presets (per-agent)** *(→ §7.14; §10 #34 / Q5)* — a small preset menu of reply formats
    (including the operator's TL;DR-table + emoji-status style), chosen once per agent; the choice reaches and
    persists to the agent. Per-message override deferred. Where: prompt composition + `state/agents.json`.
33. **Agent name pool** *(→ §7.5; §10 #35 / Q6)* — ship `assets/names/agent-names.json` (flat array;
    operator-generated by a separate agent) and wire the Create-panel randomize + auto-name to draw from it,
    with user-typed names still available. Where: [`sidecar/identity.py`](../sidecar/identity.py), `assets/names/`.
34. **Frontend degraded-mode + polling backoff** *(→ §4.3; §10 #28 / Q3)* — on `/health` failure, freeze the
    poll-driven panels showing last-known values **marked stale**, and **back off** the poll cadence to a gentle
    retry until recovery. (The consolidated always-visible system-health *display* is a separate **design-lane**
    item — see §10 #28 / #16 — not this build.) Where: `frontend/` renderer transport.
35. **Authors-view provenance wiring** *(→ §8.5; §10 #37 / Q10)* — surface §8.5's created-by / when / session
    provenance into the **Authors lens that already landed in the design system**; system-side wiring only.
    Where: [`sidecar/library.py`](../sidecar/library.py) doc sidecars, `api.ts`, renderer.
36. **Docs in agent context (light)** *(→ §7.6, §7.16; §10 #23 / Q9)* — a curated docs home agents are
    pointed at (the **Library**) + **per-agent doc attachment at launch**; automatic relevance-retrieval stays
    §10 #23's future layer. Where: [`sidecar/library.py`](../sidecar/library.py), prompt composition, `state/agents.json`.
37. **Per-agent git identity + AI-touched index** *(→ §7.5, DEVLOG practice; §10 #24 / Q9; **HIGH**)* — each
    agent commits under its own author name + a **synthetic per-agent email**, so "what did AI touch" is a git
    query with no maintained ledger; per-folder `index.md` files ride on top (drift risk accepted). **Feeds the
    lineage / Agent-Archive substrate** (§11.3 #18, #22). Where: per-agent git config at bridge launch,
    [`bridge/bridge.py`](../bridge/bridge.py), `sidecar`.

---

## 12. Repo map — where the architecture lives

| Path | Layer |
|------|-------|
| [`frontend/src/main/`](../frontend/src/main/) · [`preload/`](../frontend/src/preload/) · [`renderer/`](../frontend/src/renderer/) | Electron main / preload / React renderer |
| [`frontend/src/renderer/api.ts`](../frontend/src/renderer/api.ts) | The frontend↔sidecar contract (endpoints + SSE + event types) |
| [`sidecar/main.py`](../sidecar/main.py) | FastAPI app, `SessionState`, all endpoints, queue flush, cap loop, `reconnect_sessions()` |
| [`sidecar/eventbus.py`](../sidecar/eventbus.py) · `hookbus.py` · `inbox.py` · `serialize.py` | Event ring + stamping · inject channel · inbox raising · driver→event normalization |
| [`sidecar/drivers/`](../sidecar/drivers/) | `base.py` (seam) · `bridge.py` · `sdk.py` · `__init__.py` (selection) |
| [`sidecar/runtime_store.py`](../sidecar/runtime_store.py) · `identity.py` · `deletion.py` · `storage.py` | Restart-surviving session records · identity assignment · hard-delete/tombstone · project-store paths |
| `links.py` · `scratchpad.py` · `watermark.py` · `library.py` · `templates_store.py` · `console_catalog.py` · `checklist.py` · `marquee.py` · `subagents_naming.py` · `settings_io.py` · `utility_llm.py` | Coordination-spine feature modules: linking · scratchpad · read-watermarks · library · templates · console catalog · checklist parse · marquee tail · subagent naming · settings read/write · utility-LLM passes |
| [`bridge/bridge.py`](../bridge/bridge.py) · `transcript.py` · `paths.py` · `mcp.py` · `registry.py` | tmux/WSL2 control · JSONL transcript resolution · path/net translation · MCP sync · Settings reads |
| [`start-dashboard.bat`](../start-dashboard.bat) | Launches sidecar + Electron together (§2) |
| [`tests/`](../tests/) | The pytest suite — **and a primary spec source, not just verification.** Each `test_*_unit.py` opens with a docstring stating the *decided behavioral contract* its module must satisfy — **read it before building or changing that module.** The live tier (`test_tmux_bridge.py`, `test_bridge_finisher_live.py`, and the `tests/ui/` slice) proves bridge + client behavior end-to-end. Index + coverage map: [`tests/README.md`](../tests/README.md). |

> **The tests are executable specs.** A chunk of the buildable contract lives in the `test_*_unit.py`
> docstrings, not only in this document — read the matching test before implementing a feature. The §10
> Evidence lines cite the specific test that proves each claim.
