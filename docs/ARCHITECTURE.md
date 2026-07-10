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
  Electron app together, but they are **independent processes**. The decided end-state is **one-click launch**: Electron main owns sidecar spawn / supervise / shutdown with detach-on-close — the lifecycle is proven, modeled in Python (`test_oneclick_launch_live`, live, 2026-07-02); porting it into Electron main is queued (§11 #20). ⚠ **Today:** the `.bat` two-process launch is the shipped model until that lands.
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
single-user personal machine, as a choice. The untrusted-network case is **decided (2026-07-05): the OS firewall is the boundary** — Windows blocks unsolicited inbound by default, the effective boundary for a personal laptop; a "travel mode" (localhost-only bind or a token) is a noted cheap future add if work from public networks becomes real. (`AWL_SIDECAR_HOST` overrides the bind host; the frontend always
talks to `127.0.0.1:7690`.)

**One sidecar instance.** A single sidecar process on `:7690` serves whichever project is open. Its state
is partitioned per project folder (§8), so serving a different project is a matter of which project store
it is reading and writing — never a second process.

**Sidecar operational posture — decided (2026-07-05).** Crash-supervision: **manual relaunch is the v1 model** — agents survive in tmux and persistence is write-as-it-happens (§8.3), so a dead sidecar loses nothing but the live readouts; auto-restart supervision is deferred (it folds into the one-click shell, §11 #20, if unattended operation ever matters). Logging: the sidecar writes a **small, size-bounded rotating log** under the gitignored `sidecar/runtime/` (`sidecar.log`, 1 MB × 3 — `_install_file_log()` in [`sidecar/main.py`](../sidecar/main.py)) so a crash leaves a trail.

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

⚠ **Today:** the **system side exists** — the `projects.json` index plus `GET /projects` /
`POST /projects/{register,open,close}` and the §9.1/§9.8 flows ([`sidecar/main.py`](../sidecar/main.py))
— but no Projects *tab* renders yet: the React Settings tabs are Usage / MCP / Plugins / Config in the
parked renderer; the picker UI rides the rebuild (§11 #37) and the design work is the design lane's.

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
⚠ **Today:** the close *semantics* are served (`POST /projects/close` with `stop_agents` — detach vs
graceful stop, record-keeping either way); the confirm *dialog* itself rides the renderer rebuild (§11 #37).

### 3.5 The projects index

The dashboard store (§8.1) holds exactly **three** reusable things: **Setups**, **prompt templates**, and a
**projects index** (`projects.json`). The index is the list of known canonical project roots plus each
one's last-opened time. It powers the Projects picker and — critically — makes **cold discovery after a
reboot possible**: the app cannot scan the disk for `.awl-cc-dash/` folders, so the index is how it knows
where projects live. ⚠ **Today:** no `projects.json` exists yet (§11 #26).

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
  and loads the renderer. It is deliberately **frontend-only** *today* — it does not yet launch the Python
  sidecar (one-click launch is decided and queued, §2 / §11 #20).
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
  agent's terminal is a **live streaming attach** (`ttyd`/WebSocket), decided 2026-07-05 (§7.13; build queued §11 #29).

Failure handling is **decided (2026-07-05)**: on `/health` failure the poll-driven panels **freeze on last-known values, visibly marked stale**, and polling **backs off** to a gentle retry until the sidecar returns (queued, §11 #38); SSE reconnect and the "Sidecar offline" chip are already homed (`api.ts`). The *consolidated* always-visible system-health indicator is a **design-lane** item: today the health signals are scattered across three surfaces — the Settings connector badges, the System Error/Warning inbox cards (§7.8), and the "Sidecar offline" chip — and the operator wants them consolidated into one always-visible indicator in the app chrome (leading candidate surface: the **footer**), with a broadened state vocabulary (adding *down* + *stale/degraded*), a popover drill-in (a sidecar-log tail, §11 #43, is a candidate), reconciled with the separately-captured title-bar Connected-chip upgrade note.

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
(proven in the Python model, §2; the Electron-main port is the unproven half — §11 #20), window + app
lifecycle, detach-on-close, and packaging still carry feasibility unknowns to prove. "Don't build the frontend yet" means the renderer UI — never the shell
plumbing.

⚠ **Today:** the parked renderer trails the mockup — 16 agent colours vs 25, Console gaps, the marquee
omitted, honest no-op controls for engine-blocked features — and is **not** being finished; it is superseded
by the fresh rebuild above. The `tests/ui/` slice exists (built in the 2026-07-02 spike batch); the renderer
rebuild itself is queued (§11 #37).

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
| **Library** | `GET /library/documents` · `GET /library/document` · `POST /library/document` (create) · `DELETE /library/document` (delete the `.md` + its paired `.meta.json`) · `GET/POST /library/reviews` — ⚠ **Today:** only the GET pair + reviews exist; no create/delete endpoint yet (§7.16) |
| **Console** | `GET /console/catalog` · `POST /sessions/{id}/console/run` (+ the live streaming terminal — `ttyd`/WebSocket attach, §7.13 — ⚠ **Today:** not wired into the renderer) |
| **Readouts** | `GET /sessions/{id}/{context,subagents,checklist,marquee}` · `GET /usage` |
| **Session control** | `POST /sessions/{id}/{interrupt,model,mode,permission,effort,fast,thinking}` — `mode`/`fast`/`thinking` are capability-gated `400`s under the bridge driver (§6.2) |
| **Settings** | `GET /settings/{read,account,config,mcp,plugins}` · `POST /settings/write` (confirm-gated) |
| **Templates** | `GET/POST /templates` · `DELETE /templates/{id}` |
| **Projects** | `GET /projects` (picker feed + open flag) · `POST /projects/register` · `POST /projects/open` (409 when another is open) · `POST /projects/close` (`stop_agents` = the §3.4 second option) |
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

Deliberately **not** advertised *yet*: `set_mode`, `set_fast`, `set_thinking` — the CLI's flag-level API exposes none of them, but all three live controls are **proven feasible** on the real TUI via the bridge's `keys()` levers: permission mode cycles via **Shift+Tab at a known-idle screen**, deterministically, with the resulting mode read back from the status line (`test_permission_mode_cycle_live`, live, 2026-07-02); thinking toggles via the **`Meta+T`** modal, read-backable from transcript thinking blocks (`test_thinking_toggle_live`, live, 2026-07-02); and Fast mode toggles via **`Meta+O` + `Space`** — the panel's `Fast mode OFF/ON` line is a plain-text scrape, proven settable + read-backable + repeatable (`test_fast_mode_toggle_live`, live, 2026-07-04; credit-gate detection — the panel reports "requires usage credits" — stays the honest degrade for accounts without Fast credits). Wiring these levers into the driver — replacing the in-code no-ops and backing `POST /sessions/{id}/{mode,thinking,fast}` — is queued (§11 #12); until it lands the endpoints return honest `400`s and the UI never fakes a live control. (The SDK's stream-json control API — `set_permission_mode` / `set_max_thinking_tokens` — *does* expose these programmatically; forgoing it is the deliberate price of keeping the interactive real TUI.)

⚠ **Today (scale):** each agent's ~1 s `events()` cycle spawns ~5 WSL processes and crosses the Windows→WSL boundary, so the fleet degrades from N=1 (~1.3 s/cycle at N=1; ~10 s event-lag by N=9 — measured, `test_polling_scale_ceiling_live`); the batching + adaptive-cadence rework, then a re-measured practical ceiling, is queued (§11 #34).

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
  creation. `create()` pins a `--session-id` uuid so each agent's JSONL transcript is collision-proof (a
  §9.9 cold-restore instead passes `resume_session_id`, launching `claude --resume <id>` — the same
  conversation, continuing on the same id and `<id>.jsonl`), and auto-clears the folder-trust /
  bypass-mode startup gates. A closed tab does not kill the session; `show()` reconnects.
- **Two-channel observation.** The bridge **samples, it does not stream.** `status()` classifies the screen
  from `capture-pane` into `idle | generating | permission_prompt | unknown`;
  [`transcript.py`](../bridge/transcript.py) resolves `cwd → project-hash → <session-id>.jsonl` and parses
  the JSONL for message content. Everything the dashboard knows about a bridge agent comes from these two
  channels, polled ~1 s.
- **Windows↔WSL2 translation.** [`paths.py`](../bridge/paths.py) converts `C:\…` ↔ `/mnt/c/…`; large
  payloads are **piped via stdin** to dodge the ~32 KB command-line limit. Per-agent launch config (the
  materialized `--settings` including hook config, plus `mcp.json`) is written to
  `~/.awl-cc-dash-agents/<name>/` inside WSL (the `WSL_AWL_DIR` constant in
  [`bridge/paths.py`](../bridge/paths.py)) — deliberately kept **out** of the real `~/.claude`.
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
  Compose **To**, Compose **From**, and History **From**; **Reply is disabled** on System cards. The
  harvest half is built (§11 #27, 2026-07-10): the reserved `system` identity exists
  (`SYSTEM_AGENT` in [`sidecar/main.py`](../sidecar/main.py)); account/fleet-level error subtypes
  (rate-limit, the widened **usage-cap wording matcher**, auth-expiry wording) coalesce into ONE
  System-sourced fleet-wide Error card + one bus event; and a ~10 s deterministic tmux/WSL liveness probe
  raises/auto-resolves the `infra` card (sidecar-down needs no probe — the frontend's `/health` failure
  covers it, §4.3). **Recorded boundary:** a reliable *reactive* auth-expiry screen signal could not be
  forced live to verify — the deterministic wording matcher + probes are the shipped detection, per the
  §11 #27 honest-degrade instruction. The System filter entry in the UI rides the rebuild (§11 #37).

### 7.3 The prompt queue & delivery dispositions

The sidecar owns a per-agent **ordered** prompt queue (disposition-ordered, *not* strict FIFO), driven by
the bridge's `generating→idle` screen-state transition. A `send` carries a disposition:

- **Queue** — append-tail; flushed at idle (the default).
- **Next** — insert-head.
- **Now** — `interrupt()` then flush.
- **Hold** — park in the dedicated staging slot; released only manually.
- **Inject** — routed via the **hook channel** (§7.4), not through this queue: delivery mid-turn at the next safe tool boundary. True *instant* mid-turn injection is a **settled engine limit** (Decided omissions, §10): typeahead into a generating pane is held for the whole turn and submitted only at the boundary (`test_inject_tail_live`, live, 2026-07-04) — so hook-boundary delivery, with the transparent Next/Queue degrade when the hook path can't take it, **is the final model**, not a stopgap (the shipped hook-boundary base is unit-proven — `test_hookbus_unit`, `test_sidecar_unit`).

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
  is **proven** (`test_plan_decision_hooks_live`, live, 2026-07-02): the cards raise, and plan-approve
  resumes the agent via a **`keys()` Enter on the pane** — not a hook `updatedInput` response; the
  approve→resume wiring is queued (§11 #22).

Beyond inject and Plan/Decision, the hook channel is also the decided **run-state push channel** (Option C hybrid — `test_hook_event_stream_live`, live, plus [`claude_code_hook_event_stream_report.md`](../dev/notes/research/claude_code_hook_event_stream_report.md), 2026-07-02): every agent's lifecycle hooks POST run-state (`permission_mode`, current tool) to the sidecar, treated as **authoritative-when-fresh**, with screen-polling kept as the watchdog floor — HTTP-hook failures are silent, so a pure-push replacement is unsafe. Caveat for the build: `permission_mode` is **event-specific** — the `Notification` event lacks it — so the arbiter must key per event type. `SubagentStart`/`SubagentStop` ride the same channel as the roster's subagent signal (§7.17). The per-agent merge arbiter's ordering/dedup under concurrent load is design, not yet proof — verified during the build, never assumed (§11 #21; record the `prompt_id` version floor, v2.1.196+, from the build). ⚠ **Today:** only the inject / plan / decision hooks are registered — the run-state event set and the arbiter are unbuilt (§11 #21).

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
`GET /assets/agent-icons/{name}?color=`. The Create panel's randomize affordance draws from the **curated name pool** shipped at [`assets/names/agent-names.json`](../assets/names/agent-names.json) — 179 one-word, 3–5-letter, lowercase names, validated to double safely as git commit-author names (§11 #19) — with user-typed names always available; wiring the randomize/auto-name draw is queued (§11 #40). The Create panel's **role number auto-fills**: the No. field pre-fills the next value in that role's sequence (e.g. a second `researcher` pre-fills `02`) but **stays editable** — runtime behavior with nothing to draw in the static mockup (recorded 2026-07-08 from the design lane's IN-2 note). ⚠ **Today:** the React client ships only 16 colours (design-parity
lag, §4.4 — not a decision change); identity editing and the `--name`/`/rename` registration are speced but
not yet wired (§11 #14).

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
can hold both at once — the one-relationship split is queued (§11 #25).

**Triggers.** The delivery-trigger vocabulary is **Now · Inject · Next · Queue · Hold · Piggyback**, riding
the prompt-queue dispositions (§7.3). Defaults: **Direct messaging → Queue**, **Shared context →
Piggyback**. **Piggyback never initiates a turn** — the payload rides the next message delivered to the
target *from any source*. This matters because an actively-delivered share costs the target a whole turn
just to ingest it; Piggyback makes shared context free, which is why it is the shared-context default.
Shared-context delivery is bounded by a per-(source→target) **watermark** that dedups across channels — the
same watermark mechanism as the scratchpad (§7.7), persisted in the same `state/bookmarks.json` (§8.2).
⚠ **Today:** the trigger vocabulary in
[`sidecar/links.py`](../sidecar/links.py) is Now/Next/Queue/Inject/Hold with no Piggyback value (§11 #25).

**End-After.** Each link carries two independent caps — **Exchanges** and **Tokens** — each individually
toggleable; the default is **25 exchanges**. An exchange is one message each direction, and on a **one-way
link each fire counts as an exchange**, so End-After binds one-way links too. Exchanges are explicitly
**not** internal turns/steps — those belong to the lifecycle caps (§7.8). Together with
one-inbound-in-flight, End-After is what keeps bidirectional links from running away. Links carry
**Active/Expired** state. ⚠ **Today:** `Link.exchanges` counts message *pairs* (`messages ÷ 2`), so a
one-way link burns its cap at half rate (§11 #25).

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
  it is read on demand. The `.md` mirror **is** the board's persistence: the board reloads from it on
  project load (`state_store.load_project()` / `parse_scratchpad_md()` in
  [`sidecar/state_store.py`](../sidecar/state_store.py)), and the read-watermarks persist to
  `state/bookmarks.json` write-through (§8.3).

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
  card per agent** (every completed turn updates the open card's unreviewed-runs count —
  `_raise_response_card()` in [`sidecar/main.py`](../sidecar/main.py)); completable (**View / Reply**),
  with **no dismiss and no read-tracking**.

Items persist write-through to the project's `state/inbox.json` (§8.3); the pending permission stays a
derived synthetic card.

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
honest source of a real % (rejected alternatives: an external LLM estimator, and turns-used ÷ cap). That
boundary is **proven, not assumed**: a 100%-complete multi-tool run yields numerators only, never a
denominator (`test_runstrip_tail_live`, live, 2026-07-04) — so checklist self-report over the barber-pole
floor **is the final model** (Decided omissions, §10; the checklist parser itself is unit-proven —
`test_checklist_unit`, 19 cases).

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

Permission **mode** changes live, mid-run: the bridge drives **Shift+Tab at a known-idle screen** and reads the resulting mode back from the status line (`test_permission_mode_cycle_live`, live, 2026-07-02; wiring queued §11 #12). **Bypass/Auto are launch-gated:** a Bypass segment that was not pre-armed at launch is **silently absent** from the mode ring — not a visible no-op; it simply isn't reachable (`test_bypass_auto_preconditions_live`, live, 5-case launch matrix) — so the Create panel must set the launch flags and the mode control must disable/hide un-armed segments (§11 #13), never presenting a control that silently does nothing. Per-agent tool scoping is **deny-based**, because `--allowedTools` is ignored under bypass mode — a known Claude bug.

### 7.12 Retire & Delete

Both ship in v1. **Retire** is soft and reversible: stop + archive. **Delete** is hard and irreversible,
under one rule: **wipe the private footprint, tombstone everything shared.**

- Wiped: the runtime record, the tmux session, the on-disk transcripts including subagents, and the
  agent's rows in the project `state/` files (roster entry; inbox/links/routing/bookmarks rows).
- Tombstoned: scratchpad posts, feed events, link edges — **kept**, attributed to the deleted identity,
  marked inactive.

Delete works from any agent state (interrupt + close first) behind a plain confirm dialog. The agent's
**number is permanently retired** — never recycled (persisted per project in `state/agents.json`;
auto-assigned numbers skip retired ones). Wired as `DELETE /sessions/{id}?hard=true`, covering the
runtime/roster record, the tmux session, the transcripts, and the agent's rows in the project `state/`
files — inbox items and read-bookmarks dropped; `routing.jsonl` is append-only history and is kept.

### 7.13 Console

The Console is a **per-agent Console tab** scoped to the focused agent, with an **Expand** control doing a
partial step-into over the left + middle columns. Its model is a **real live-streaming terminal** — a live client (`ttyd`, attached to the agent's tmux session and consumed over a WebSocket) rendered into an xterm.js-class component, so the focused agent's terminal is watched and typed into exactly as if sitting at it. **Decided 2026-07-05 (streaming, not polled snapshots — feasibility proven live, `test_console_stream_attach_live`, ttyd 1.7.7: reachable from Windows over `localhost` with no hand-rolled port-forwarding — WSL2's default relay suffices — coexistence-safe under the poller, and a measured **~11 ms streaming vs ~778 ms polled** keystroke round-trip; the wiring half — keystroke passthrough + ANSI recovery via `capture-pane -e` — was proven earlier by `test_console_mirror_live`; full context: the embedded-terminal feasibility brief, [`dev/notes/research/embedded-terminal-feasibility-brief-2026-07-05.md`](../dev/notes/research/embedded-terminal-feasibility-brief-2026-07-05.md)):** the Console is the **focused-agent** surface and uses the live stream; the fleet-wide coordination reads and the many-agent grid overview stay on the capture-pane/transcript path (§4.3, §6.2) — you never run N live terminals at once.

- **Live stream:** the terminal streams continuously over the WebSocket (~10 ms keystroke round-trip on localhost, no poll cadence), rendering everything faithfully — output, menus, dialogs, the input/status bar, colors, spinners, box-drawing — exactly as a human at the terminal would see it.
- **Attach-on-open, detach-on-close:** the live client attaches only while the Console tab is open on that agent (never a live terminal per agent across the fleet); one bounded scrollback catch-up on open.
- **Geometry pinning (required):** the agent's tmux pane is pinned via `window-size manual` so an attached viewer cannot resize it and perturb the sidecar's capture-pane coordination reads — the one coexistence hazard, and its fix (naive `window-size latest` lets a viewer resize the pane, and the resize **persists** after it detaches).
- **Passthrough:** the Console input passes keystrokes through to the TUI over the stream, so interactive slash-command follow-ups are answered exactly as if sitting at the terminal.
- **Slash-command runner:** a full grouped catalog with filter, staged into a run bar (`GET /console/catalog`, `POST /sessions/{id}/console/run`), routed via the bridge's `send`/`keys`.
- **`/clear` hazard:** a Console `/clear` **rotates the agent's JSONL transcript** and orphans the sidecar's pinned resolution until a re-resolve — new turns are lost to the sidecar meanwhile; `/compact` is safe, same file (`test_console_clear_transcript_live`, live, 2026-07-02). The post-`/clear` re-resolve + `register_session_id` is queued (§11 #35).
- **Interception stays on the transcript:** an interactive TUI only ever emits a *painted screen*, so machine-readable data (messages, tool calls, permission events) is read from the JSONL transcript / event bus (§7.1, §8.6) — never parsed off the terminal stream. The stream is the human's surface; the transcript is the machine's.

⚠ **Today:** neither the streaming attach nor a polled mirror is wired into the React Console (a parked-renderer gap), and the React Console is stubbed in places; the catalog + run endpoints exist. The streaming transport is proven feasible end-to-end (`test_console_stream_attach_live`); what remains is the build — the sidecar/bridge attach endpoint plus the xterm.js-class renderer in the rebuilt Console (§11 #29).

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
- **Voice mic:** direction decided (2026-07-05) — dictation must be *genuinely good*; the built-in-speech-vs-Whisper-class-library quality spike is still open (§10 #4), and the mic stays a visual affordance until it lands. **Response-format preamble:** decided (2026-07-05) — a basic **per-agent preset menu** (including the operator's TL;DR-table + emoji-status style), chosen once per agent and applied to all its replies (queued, §11 #39); a per-message override is a later nicety, deferred.

### 7.15 Settings

Settings are **fully interactive**: a write is exposed for everything the engine can set (Config · MCP ·
Plugins, at user + project scope) plus per-agent scoping in the Create/Agent panel — and **all writes are
confirm-gated** (`GET /settings/{read,account,config,mcp,plugins}`, `POST /settings/write`). Feasibility is
marked honestly in the UI: mid-run permission-mode cycling is proven and queued to wire (§7.11, §11 #12), with un-armed Bypass/Auto segments absent from the mode ring (§7.11, §11 #13); per-agent MCP/model/plugins
take effect at launch/restart; tool scoping is deny-based. The **Account band** (email/org/plan from local creds) and the **usage-limits band** (session/weekly %) are both in — with the source boundaries **mapped live** (`test_usage_context_sources_live`): account identity is a *split source* (the `.claude.json` tier fields are unmatched by the current reader — fix queued, §11 #33), and live usage % / limits are **screen-scrape only**, with no clean local API — so the band shows account identity plus scraped live figures, honestly labeled. The intended cost surface goes one level deeper: **live per-agent cost/usage figures on each agent card**, complementing the account-level band — proven harvestable (`test_per_agent_cost_live`, live: `/cost` yields a real per-session dollar figure, overturning the old "honest blank" assumption), so this is an *unbuilt* surface, not an engine boundary (§11 #32). ⚠ **Today:** no per-agent figure is shown yet.
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

Plan-approve from the dashboard resumes the agent out of plan mode — wired (§11 #22, 2026-07-10):
`POST /sessions/{id}/plan/verdict` drives the proven `keys()` Enter for **approve** (resolving the plan
card + stamping the sidecar verdict), and **revise** sends Escape (keep planning) + queues the feedback at
the head of the prompt queue (the Escape leg is ⚠ assumed pending the e2e drive — the approve leg is the
live-proven one). Edit-in-place ships as `PUT /library/document` (store-scoped). ⚠ **Today:** listing is
still **non-recursive** (the store's `plans/`/`docs/` dirs list first with a legacy `<root>/<subdir>`
fallback; nested trees are not walked; [`sidecar/library.py`](../sidecar/library.py)), and no Assets
surface exists yet (§10 #1 / design lane).

### 7.17 Subagents

A subagent is a **sub-identity of its parent** (e.g. `coder-01 › A2`), riding the sender stamp (§7.1) and
the addressing model (§7.2) rather than getting its own top-level identity. Naming is **group+member**
(`A2`), never flat `s1…sN`. The one net-new backend piece: the sidecar ingests each subagent's
**own transcript** via a folder-watch on the parent's `subagents/` directory, joined to its spawn event.
Pending-vs-active status is **readable**: proven live off the subagent's **own transcript** recency
(`test_subagent_status_live`, 2026-07-02), with the `SubagentStart`/`SubagentStop` hook fields (`agent_id`,
`transcript_path`) as the cleaner authoritative signal once hook ingestion lands (§11 #21); the
identity/naming/ingestion half is unit-proven (`test_subagents_naming_unit`). Badge-click, the nested
filter tree, and the Details accordion are DESIGN.md's. ⚠ **Today:** the hook fields are not ingested and
no active-vs-quiet signal is wired into the roster (§11 #21).

### 7.18 Context readout, compaction & per-turn sources

The Agent panel's context surface is fed from three proven sources, freshest-available-wins: **(1)** the parsed **`/context`** output — per-category rows (`test_context_compact_live`, live, 2026-07-02) — as the on-demand deep readout; **(2)** the **statusLine `context_window`** — a **per-turn snapshot**, not a continuous mid-run gauge (boundary mapped by `test_usage_context_sources_live`) — as the freshest per-turn number, a genuine improvement over post-hoc JSONL; **(3)** the JSONL-derived total-context/turn floor (unit-proven, `test_bridge_unit`), which remains the fallback if the `/context` scrape is ever unavailable. Compaction is first-class: **`/compact` boundaries are detectable** from `compact_boundary` transcript metadata, keying the compaction history (count / type / when) and the Compact controls. ⚠ **Today:** the sidecar serves only the JSONL-derived totals (`GET /sessions/{id}/context`); the `/context` breakdown + compact surfaces (§11 #30) and the per-turn statusLine capture (§11 #31) are queued.

### 7.19 Rewind & Handoff — the Timeline

From the Agent→Details **Timeline**, **Rewind** rolls an agent back to a chosen prior message and resumes from there; **Handoff** branches from a chosen point into a *new* agent carrying that conversation prefix. Both are **proven end-to-end** (`test_rewind_handoff_live`, live, 2026-07-02; research: [`s10-research-15-rewind-handoff.md`](../dev/notes/research/s10-research-15-rewind-handoff.md)) on the TUI-native path: **`/rewind`** restores conversation state (not just files) to any prior prompt checkpoint, and **`--fork-session` + `/rewind` inside the fork** is the branch-from-N mechanism. Handoff creates the new agent through the standard Create flow with a **prepopulated Create tab** (§9.2, §7.5). Transcript surgery is ruled out (fragile, unsupported); the Python SDK lacks `resume_session_at` parity, so the TUI-native path is the build path. Two caveats carry into the build (§11 #15): a conversation fork does **not** isolate filesystem state — the build needs an explicit per-fork file-state policy (git worktree / code-checkpoint) — and a **≥ v2.1.191** version gate is required to rewind past a `/clear`. The per-turn settings + summary capture the Timeline rows render is its own item (§11 #46); the Handoff summary-artifact half is another (§11 #16). Timeline visuals are DESIGN.md's. ⚠ **Today:** nothing is wired — no rewind/fork endpoint or UI exists.

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
- **Launch config** is materialized per agent at launch (§6.4) at `~/.awl-cc-dash-agents/<name>/`
  (`WSL_AWL_DIR` in [`bridge/paths.py`](../bridge/paths.py)).
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
(`storage.project_root()` / `project_key()` in [`sidecar/storage.py`](../sidecar/storage.py) — git
top-level walk-up, symlink resolution, `/mnt`-alias folding.)

**Git status:** `<project>/.awl-cc-dash/` is **committed** (state travels with the repo);
`sidecar/runtime/` stays **gitignored** (live app-operational state). A pre-rename `.awl/` store migrates
into `.awl-cc-dash/` one-time on first touch (`storage.migrate_legacy_store()` — never overwriting an
existing target).

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
| Inbox items (open-ended type set, §7.8 — `type` stored as a string, never a hardcoded enum) | **Persist** | 📁 `state/inbox.json` | matches target — write-through via the inbox persist hook ([`sidecar/state_store.py`](../sidecar/state_store.py)) |
| Pending **permission** prompt | **Derive** (meaningless after a restart — the live agent re-raises it) | ⚡ | `SessionState.pending_permission` in [`sidecar/main.py`](../sidecar/main.py), merged into `GET /inbox` as a synthetic card — matches target |
| Agent-to-agent links | **Persist** | 📁 `state/links.json` | matches target — write-through (add/remove/`touched()` counter mutations) |
| Message from/to routing (source, recipients) | **Persist** — non-default only, as a thin overlay (§8.6) | 📁 `state/routing.jsonl` | matches target — appended at the `push_event` stamp point for non-default routing |
| Read-bookmarks (watermarks — scratchpad per agent; link shared-context per source→target pair) | **Persist** — rides the shared state store, no bespoke system | 📁 `state/bookmarks.json` | matches target — write-through on advance/drop; the board reloads from its `.md` on project load |
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
| Agent roster (which agents exist, per project) | 📁 | `state/agents.json` | Team Graph · `agent-node-card`; Agent→Create/Details | matches target — `runtime_store.save_record` routes project-homed records there; cwd-less records fall back to 🏠 `sessions.json` |
| Identity (role/number/name/color/icon) | 📁 | inside `state/agents.json` | everywhere · `identity-badge`, `agent-tile` | matches target |
| Retired identity numbers (never reused) | 📁 | inside `state/agents.json` | — | matches target — persisted on delete; auto-assignment skips them |
| Per-agent launch config (tools/plugins/MCP/permission rules) | 📁 | inside `state/agents.json` | Agent→Details/Create | matches target |
| Transcript reference (`claude_session_id` + **resolved path**) | 📁 | inside `state/agents.json` | — (drives Feed/History replay + resume) | matches target — the verified path persists once resolvable and refreshes on resolve |
| Projects index | 🏠 | `sidecar/runtime/projects.json` | Settings→Projects · picker list (§3.5) | exists (runtime-maintained roots index); the picker/open/close surface rides #26 |
| Setups (reusable team rosters) | 🏠 | `sidecar/runtime/setups.json` | Settings→Setups · `registry-row` | matches target |
| Prompt templates | 🏠 | `sidecar/runtime/templates.json` | Prompt→Compose · `template-select` | matches target — project-agnostic by design (§7.14) |
| Plans (content) | 📁 | `plans/*.md` | Work→Library Plans · `plan-card`, `doc-editor` | plan-mode output redirects there (`plansDirectory` in every materialized settings, §8.5); listing is store-first with a legacy `<root>/<subdir>` fallback, still non-recursive |
| Dashboard documents (content) | 📁 | `docs/*.md` | Work→Library Documents · `doc-editor` | matches target — create/delete/rename via `/library/document*` (§5.2) |
| Doc/plan metadata (verdict, comments, anchors, provenance) | 📁 | `<doc>.meta.json` sidecar, next to its doc (§8.5) | `verdict-badge`, `feedback-card`, `comment-popover`, `review-chip` | matches target — the legacy central `plan-reviews.json` migrates on first read |
| Shared scratchpad | 📁 | `docs/scratchpad.md` | Feed→Scratch · `scratch-post`; Prompt Target=Scratch | matches target — the `.md` is the store; the board reloads from it on project load |
| Library Assets (media) | 📁 | `assets/` | Work→Library Assets · `asset-card` | no Assets surface exists yet |
| Inbox items | 📁 | `state/inbox.json` | Feed→Inbox · `*-inbox-card` | matches target (§8.3) |
| Links | 📁 | `state/links.json` | Work→Links + Graph drawer · `link-drawer`, `link-list`, `link-edges` | matches target (§8.3) |
| Routing overlay | 📁 | `state/routing.jsonl` | Feed · `recipient-badge`, From/To filter | matches target (§8.3) |
| Read-bookmarks | 📁 | `state/bookmarks.json` | (invisible — drives delta reads) | matches target (§8.3) |
| Unsent prompt queue / Hold | ⚡ | — (drops on close, by design) | Prompt→Compose (send-timing) | matches target |
| Message feed / cap metrics / console / subagents / run-strip / marquee | ⚡ | — (derived, §8.3) | Feed / Team Graph / Agent→Console | matches target |
| Session transcripts (full history, incl. subagents) | 📜 | `~/.claude/projects/<encoded-cwd>/<claude_session_id>.jsonl` (WSL) | Feed/History (replayed) | matches target — retention pinned (`cleanupPeriodDays: 3650`); resolved path persisted per agent |
| Per-agent launch files (`settings.json`, `mcp.json`) | 🛠 | `~/.awl-cc-dash-agents/<name>/` | — | matches target — `WSL_AWL_DIR` in [`bridge/paths.py`](../bridge/paths.py) |
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
3. **Renames are dashboard-mediated.** The dashboard renames both files of the pair together
   (`POST /library/document/rename`); an orphaned `.meta.json` (no matching `.md`) is detectable and
   offered for re-link (`find_orphan_metas` / `relink_meta` in
   [`sidecar/library.py`](../sidecar/library.py)). If agent-driven renames ever bite in practice, an
   embedded stable id can be added *then* — additive, nothing to unwind. The legacy central
   `plan-reviews.json` migrates into per-doc sidecars on first project read (then renames to
   `.migrated` so it never re-runs).
4. **Documents get comments like Plans** — the editor-header Comment control plus the Plans-style footer
   action strip minus Reject/Approve (the design work is queued in the design lane); the store side is the
   same sidecar comment threads (`POST /library/comments`).
5. **Commenting scope:** dashboard-owned files under `.awl-cc-dash/` only; the Library can still browse
   other repo `.md` files read-only. Extendable later if needed.
6. **Plan mode is kept and redirected.** Claude Code's built-in plan mode stays — its enforced
   pause-for-approval is what the Inbox plan flow rides. Its output is redirected into the project folder
   via the standard `plansDirectory` setting (this repo itself sets `./.claude/plans`), written into each
   agent's materialized launch settings. The value is the **absolute WSL path**
   `<canonical project root>/.awl-cc-dash/plans`, computed via the cwd canonicalizer — a relative `./`
   would resolve against the agent's raw cwd and break the same-folder invariant for subfolder launches.
   (`_build_settings()` in [`sidecar/drivers/bridge.py`](../sidecar/drivers/bridge.py) sets it for every
   agent launched with a cwd.)

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
   `state/agents.json` alongside the session id — resolved lazily once the transcript exists and
   refreshed on resolve — so the mapping survives restarts and scheme drift.
3. **Retention is pinned.** Claude Code auto-deletes sessions inactive longer than `cleanupPeriodDays`
   (default 30 days) — unacceptable for long-term-referenced transcripts. The per-agent settings the bridge
   materializes at launch carry `cleanupPeriodDays: 3650` (10 years — effectively never; one constant to
   adjust — `TRANSCRIPT_RETENTION_DAYS` in [`sidecar/drivers/bridge.py`](../sidecar/drivers/bridge.py)),
   guaranteeing retention for dashboard agents without touching global Claude config.
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
   do **atomic write-replace per file** to avoid torn JSON. Cross-branch/machine merge of the committed `state/` JSON is **decided (2026-07-05): single-machine, no merge policy** — a concurrent-edit conflict is a manual git resolution, consistent with the cross-machine caveat accepted at §9.9; a merge/reconcile story is revisited only if multi-machine operation is pursued.
3. **Schema evolution of the committed store — decided (2026-07-05).** A `schema_version` stamp is written into the committed `state/` JSON at write time (`SCHEMA_VERSION` in [`sidecar/state_store.py`](../sidecar/state_store.py)) — cheap insurance so a later format change can still read old data; migration *machinery* stays deferred until a format actually changes.

---

## 9. Lifecycle flows, end to end

### 9.1 Open a project
Startup lands on the empty state and steps into Settings → Projects (§3.1). Picking a project from the
index (or "Open other folder…", which registers a new root) opens it: the sidecar loads the project store —
roster + identities from `state/agents.json`, inbox/links/bookmarks from `state/`, the scratchpad board
from its `.md` — warm-rebinds any still-alive tmux sessions and cold-restores dead ones (§9.9), and replays
transcripts into the feed. The active-project chip appears; the panes fill. ⚠ **Today:** the system-side
flow is served (`POST /projects/open` loads the store + warm-rebinds/cold-restores that project's records)
but sidecar **startup** still restores ALL persisted records rather than waiting for an open (the
picker-first startup lands with the renderer rebuild + one-click shell, §11 #37/#20), and the picker/chip
UI rides #37.

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
in Feed→Scratch carrying `recipients:[scratch]`.

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
- **Cold** (reboot / WSL shutdown; tmux gone): relaunch the agent with `claude --resume <claude_session_id>` in its cwd — the same conversation, rebuilt from the transcript, continuing on the **same** session id and the same `<id>.jsonl` (plain `--resume` never forks; a fork takes the explicit `--fork-session` flag — live-proven on CC 2.1.202 in [`tests/test_cold_restore_live.py`](../tests/test_cold_restore_live.py)). The path is wired end to end: `create(resume_session_id=…)` launches `--resume <id>` with no `--session-id` ([`bridge/bridge.py`](../bridge/bridge.py)), and `reconnect_sessions()` in [`sidecar/main.py`](../sidecar/main.py) cold-restores every dead-tmux record that carries a `claude_session_id` (a full create — launch config, hooks, retention pin all apply; the resumed transcript replays into the feed via the driver poll). Only a record with **no** claude id (no way back to the conversation) is pruned. Graceful-degrade fallback if cold-restore proves shaky in practice: restore all *data* and let agents be re-resumed manually.

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

The single home for everything the system needs but the settled body can't yet specify. **The Phase-9 relocation (2026-07-09) is complete:** every spike-proven capability now lives in the body with its evidence citation, every decided-buildable item in §11, and every proven-impossible tail under **Decided omissions** below — so this section holds **only** what is genuinely still open or deliberately parked. Between the settled body and this queue, the whole intended system is accounted for; a behavior that is neither settled above nor listed here has fallen through a crack and belongs here.

**Entry is deliberately cheap** — an item may arrive half-formed (*roughly what we want / what we don't yet know / what would settle it*) and mature in place. **Exit is strict:** an item leaves only by being **sorted** (a mechanism is found and woven into the settled body, with any buildable remainder queued in §11) or **explicitly omitted** (a recorded decision → Decided omissions). Nothing is deleted.

**Status tags** (the reality of the capability *today*): 🧪 **needs-spike** (mechanism known; needs a live experiment) · 🔬 **needs-research** (mechanism unknown) · ⏸ **parked** (a deliberate deferral with a named revisit trigger). An item resolves to impossible only after a spike actually proves no path (a code no-op is not a proof); it then moves to Decided omissions.

*Numbering note:* items were renumbered **1–8** in the Phase-9 refactor; the old→new map (for both §10 and §11) lives in the archived doc-integration tracker, [`archive/dev/notes/scratch/2026-07-03-doc-integration-tracker.md`](../archive/dev/notes/scratch/2026-07-03-doc-integration-tracker.md).

### Build-path unknowns

**1. Attachment / citation path materialization** *(→ §7.14, §7.16, §8.2)* — 🧪 **needs-spike (resolvable in-build)**
- **Evidence:** research settled ([`attachment-citation-path-materialization-report.md`](../dev/notes/research/attachment-citation-path-materialization-report.md), 2026-07-02) — **Option A**: copy bytes into `<project>/.awl-cc-dash/assets/<id>/`; store a project-relative `rel_path` + SHA-256 + MIME + provenance; render per-receiver via a `ProjectPathContext`. Design plausible; no prototype built.
- **Desired final behavior:** attachments and citations route to a real on-disk home a receiving agent can open (Citations are built with Attach, §7.14).
- **Build ladder (decided, so the implementing agent can resolve this alone):** **(a)** ingest per Option A — the WSL-native write path (`wsl.exe … cat > tmp && mv` for atomicity), verifying the `wslpath -w` edge cases live (spaces, unicode, unusual distro names); **(b)** serve bytes to the renderer through a **sidecar HTTP asset endpoint** (`GET /assets/…`) — the *recommended default*, since the app already fetches everything over localhost HTTP and it sidesteps Electron CSP/UNC-path policy entirely; **(c)** direct `file:`/`\\wsl.localhost\…` loading is an optional optimization to try, never a dependency; **(d)** if ingestion itself proves shaky, attachments stay **display-only chips** (name/size/MIME) — the recorded fallback. Test, don't assume: the WSL write path and the endpoint render are the two legs to prove during the build.

### Parked & deferred (deliberate, with named revisit triggers)

**2. Native coordination primitives (Agent teams / Workflow / SendMessage)** *(→ §7.4, §7.17)* — ⏸ **parked (adopt-narrowly-later)**
- **Decision (research settled, [`native-claude-code-coordination-report-2026-07-02.md`](../dev/notes/research/native-claude-code-coordination-report-2026-07-02.md)):** keep the sidecar's custom spine (inbox / links / scratchpad) **canonical**; adopt native primitives only narrowly, as observability enrichments or optional run modes. Findings: `Task` was renamed `Agent` in v2.1.63 (the parser-compat audit is queued, §11 #36); `TodoWrite` is disabled-by-default (v2.1.142; not the adoption target); `SendMessage` is scoped to native subagent/team graphs and **cannot** bus across independently spawned tmux processes (confirms links stay custom); agent-teams are experimental — one team/session, no nesting, no resume.
- **Folded in:** the old "native agent-teams messaging" build item — adopting Claude Code's built-in inter-agent messaging in place of the custom sender/trigger wrapping is revisited **only if the native feature matures**, behind its own live spike (hook payloads + tool-name state on the installed build; docs-derived claims are not run-verified).
- **Fallback:** the shipped custom spine — which is the decided model anyway.

**3. Subagent creation / management** *(→ §7.17)* — ⏸ **parked (operator, 2026-07-05); revisit after hooks/lineage (§11 #21, #18, #19) land**
- **Surface mapped** ([`s10-research-22-subagent-management.md`](../dev/notes/research/s10-research-22-subagent-management.md)): **CREATE** is parent-mediated only — send `@agent-<name> <task>` as literal text to the idle parent pane (no out-of-process spawn API); **OBSERVE** — `SubagentStart`/`SubagentStop` hooks give structured `agent_id` / `agent_type` / `transcript_path` / `last_assistant_message` (rides §11 #21); **STEER** — `SendMessage` resumes a *stopped* subagent; mid-turn steering of a running one is unproven; **STOP** — no per-subagent API (`Ctrl+X Ctrl+K` kills all background subagents).
- **Operator sketch for pickup:** a Compose-workspace **"add agents"** affordance (button/dropdown, plausibly via the template-block machinery) dropping a generic fan-out instruction block into the prompt. Spike-gated at pickup: the `@agent-<name>` mention parse via `send-keys -l`, the local transcript-path schema, and the stop-key timing.
- **Fallback:** subagents remain observe-only (§7.17).

**4. Voice dictation — STT quality spike** *(→ §7.14)* — 🧪 **direction decided (2026-07-05); quality spike open**
- **Decided direction:** dictation must be *genuinely good* — the operator finds OS-level dictation mediocre. The spike compares the browser/Electron built-in speech path against a **Whisper-class local library** (the original option pair: client-side **Web Speech API**, free and built-in, vs. a **sidecar transcription service**): if the built-in is close, it wins on simplicity, but meaningfully better quality beats convenience. Weigh a local model's compute against the stay-smooth-on-a-modest-laptop constraint.
- **Fallback:** the mic stays a visual affordance until the path lands.

**5. Turns by-tool breakdown (the "Coordinating" slice)** *(→ §7.9, §7.10)* — ⏸ **parked (operator, 2026-07-05): display parked, capability retained**
- The Agent→Details Turns accordion's per-tool split (Read/search · Edit · Bash · MCP · Subagent · Web · **Coordinating** · Remaining) is parked — the total turn count (§7.9) suffices meanwhile. Nothing is lost while parked: raw per-turn tool data lives in the JSONL transcripts and the sidecar already parses tool events — **pinned transcript retention (§8.6, §11 #5) is the guard**. The genuinely unproven piece is the cross-agent **"Coordinating"** attribution; at pickup, re-frame the bucket vocabulary against the reduced feed block/filter set, then spike whether per-tool counts derive cleanly from `tool_use` blocks.
- **Fallback:** derivable buckets only, or the total count alone.

**6. Docs-in-agent-context — the automatic retrieval layer** *(→ §7.16, §11 #44)* — ⏸ **future layer; v1 is decided & queued**
- The v1 mechanism is settled (curated Library home + per-agent doc attachment at launch, §11 #44). What stays open is only the *automatic* layer: how relevant, current docs are selected and refreshed per agent role — context injection, an MCP docs server, and hook-pushed digests are the candidate mechanisms.
- **Fallback:** manual doc references in prompts (status quo).

**7. Special-asset sourcing audit** *(→ 🔌 Claude config, §8.1)* — ⏸ **decided-needed, deferred (2026-07-05): fold into the hooks setup pass**
- Skills/agents/hooks/plugins sourcing is suboptimal today (ad-hoc, duplicate `AGENTS.md` files); the audit is genuinely needed but deferred — current churn makes now the wrong moment. Distinct from the dashboard's lifecycle-hook *ingestion* (§11 #21) — this is Claude Code asset-sourcing hygiene. "Ideal source" per asset type is unestablished.
- **Fallback:** current ad-hoc sourcing stands.

**8. Rich visual content in Plans/Docs** *(→ DESIGN.md; design-lane)* — ⏸ **pursue when the design lane is ready (operator, 2026-07-05); not a v1 gate**
- Mermaid / charts / diagrams + visual commenting in Plans/Docs — wanted; routes to the design lane for a DESIGN.md home when picked up. Operator caveat: must stay smooth on a modest laptop. This entry is the architecture-side pointer only.

### Decided omissions (settled limits — never re-raised)

Recorded here so they are not re-raised as open questions; an item lands here only after a **spike** actually proves no path exists.

- **Instant mid-turn Inject** — proven infeasible (`test_inject_tail_live`, live, 2026-07-04): typeahead into a *generating* pane is held for the whole turn and submitted only at the boundary — pure Next/Queue, never earlier. Hook-boundary delivery + the transparent Next/Queue degrade **is the final model** (§7.3).
- **Engine-side completion fraction** — proven absent (`test_runstrip_tail_live`, live, 2026-07-04): a 100%-complete multi-tool run yields numerators only (`work_steps`, `tool_total`), no denominator; no `TodoWrite` fired. Checklist self-report over the barber-pole floor **is the final model** (§7.10).
- *(History note: Fast/Thinking live control once sat here on a code-no-op assumption; the `Meta+T` / `Meta+O` keybinding levers were then proven live, and both now live in the settled body — §6.2.)*

---

## 11. Build backlog & queue

The single home for **decided, buildable** work — the *know-how, queued to build* side of the line whose *don't-yet-know* side is §10. A row here is a **queue entry, not a spec** — the body section each item points at owns the detail; **read it (and the matching `test_*_unit.py` docstring, §12) before building.**

**Entry:** an item enters only once it is decided and buildable; if it still needs research, a spike, or a product decision, it belongs in §10. **Exit:** an item leaves by being **built** (its ⚠ Today markers clear and the row is removed — DEVLOG keeps the history) or by being **demoted to §10** (building revealed an open question).

*Phase-9 note (2026-07-09):* the queue was regrouped **by feature** and renumbered 1–49 (the storage set #1–11 kept its numbers); ex-BB traceability IDs are stripped. The old→new map lives in the archived doc-integration tracker ([`archive/dev/notes/scratch/2026-07-03-doc-integration-tracker.md`](../archive/dev/notes/scratch/2026-07-03-doc-integration-tracker.md)).

**Operator priorities (2026-07-05):** ~~URGENT — #5 transcript retention~~ *(built 2026-07-09)*. **HIGH — #21 hook lifecycle ingestion, #18 Agent archive, #19 per-agent git identity** (the lineage/archive substrate), and **#29 Console streaming** (first-tier priority *inside* the renderer rebuild #37).

### 11.1 ⚠ Today index — build debt by body section

One row per body section carrying ⚠ Today markers, so the doc's whole build debt is scannable in one place. The body markers are canonical — this is a pointer table; update the row when a marker is added or cleared. **Queue item** ties the debt to the numbered backlog below (or to §10 where the debt is gated on an open question).

| Body § | What's owed today | Queue item |
|--------|-------------------|------------|
| §2, §4.1 | One-click launch: Electron main doesn't spawn/supervise the sidecar (`.bat` is the launcher) | #20 |
| §3.1–§3.5, §9.1 | Projects UI (picker tab, chip, close dialog) + picker-first startup — the system side is built | #37 (UI), #20 |
| §4.3 | No degraded-mode freeze/stale/backoff in the client | #38 |
| §4.4, §7.5, §7.10 | Renderer trails the design system (16/25 colours, Console gaps, marquee omitted) — superseded by the fresh rebuild | #37 |
| §5.2 | Console live attach not wired | #29 |
| §6.2 | `set_mode` / `set_thinking` / `set_fast` are in-code no-ops (the proven `keys()` levers are unwired); polling degrades from N=1 | #12, #34 |
| §7.4 | Run-state arbiter built; live payload verify (field presence, prompt_id floor) in flight | #21 |
| §7.5 | Identity editing + `--name`/`/rename` registration unwired; randomize not drawing from the shipped pool | #14, #40 |
| §7.6 | Multi-select relationship list; no Piggyback trigger value; exchanges counted as pairs | #25 |
| §7.11 | Mid-run mode cycling + Bypass/Auto launch-gating unwired | #12, #13 |
| §7.13 | Streaming attach + xterm renderer unbuilt; React Console stubbed; post-`/clear` re-resolve missing | #29, #35 |
| §7.15 | Per-agent cost unsurfaced; account split-source reader unfixed | #32, #33 |
| §7.16 | Listing non-recursive; no Assets surface | §10 #1 |
| §7.17 | Subagent active-vs-quiet signal not wired into the roster | #21 |
| §7.18 | No `/context` breakdown, compact history, or per-turn statusLine capture wired | #30, #31 |
| §7.19 | No rewind/fork endpoint or Timeline wiring | #15 |

### 11.2 Storage & persistence set (#1–11)

Implements the §8 storage model and §9 lifecycle flows — **§8/§9 own the detail; read them first.**

1. *(built 2026-07-10 — storage rename + subdir taxonomy + legacy migration; see DEVLOG)*
2. *(built 2026-07-10 — canonical project root + `project_key()` scoping; see DEVLOG)*
3. *(built 2026-07-10 — per-project state store, write-through hooks, Response card, board reload; see DEVLOG)*
4. *(built 2026-07-10 — session id + verified transcript path persisted per agent; see DEVLOG)*
5. *(built 2026-07-09 — transcript retention pinned; see DEVLOG)*
6. *(built 2026-07-10 — per-doc `.meta.json` sidecars + Library doc CRUD/comment endpoints + legacy migration; see DEVLOG)*
7. *(built 2026-07-10 — absolute-WSL `plansDirectory` in every materialized settings; see DEVLOG)*
8. *(built 2026-07-10 — cold-restore end to end: bridge `create(resume_session_id=…)` live-proven same-id in [`tests/test_cold_restore_live.py`](../tests/test_cold_restore_live.py); sidecar startup cold-restores dead records with a claude id; see DEVLOG. The full sidecar-path live drive rides the e2e proof.)*
9. *(built 2026-07-09 — WSL launch-config dir renamed; see DEVLOG)*
10. **Dogfood the committed store** *(→ §8.2 self-dogfooding; depends on #1)* — commit this repo's `.awl-cc-dash/` once the dashboard's first real run against this repo creates it (the CLAUDE.md runtime-data note landed 2026-07-10; tests confirmed on temp dirs). Where: the e2e proof run.
11. *(built 2026-07-10 — hard delete clears the agent's project `state/` rows + persists the retired number; see DEVLOG)*

### 11.3 Agent control & lifecycle (#12–20)

12. **Live mode / thinking / fast control wiring** *(→ §6.2, §7.11)* — replace the driver's `set_mode` / `set_thinking` / `set_fast` no-ops with the proven `keys()` levers: Shift+Tab cycle at a known-idle screen with status-line read-back; `Meta+T` modal with a current-state read first; `Meta+O` + `Space` with credit-gate detection as the honest degrade (`Enter`/`Escape` only close the Fast panel — `Space` is the lever; wire as open-panel → read current state → `Space`-to-target → close). Back `POST /sessions/{id}/{mode,thinking,fast}` with them and un-gate the capability set. Where: [`sidecar/drivers/bridge.py`](../sidecar/drivers/bridge.py), [`bridge/bridge.py`](../bridge/bridge.py).
13. **Bypass/Auto launch gating** *(→ §7.11)* — the Create panel sets the Bypass/Auto launch flags, and the mode control disables/hides un-armed segments (an un-pre-armed Bypass is silently absent from the mode ring). UI half rides #37. Where: [`sidecar/drivers/bridge.py`](../sidecar/drivers/bridge.py), Create panel.
14. **Identity editing + session-name registration** *(→ §7.5)* — all five identity fields editable after create; the **name** registers as the Claude Code session's own display name (`claude --name` at launch, `/rename` kept in sync on edit) so it surfaces in the VS Code extension list and the `--resume` picker. Where: [`sidecar/identity.py`](../sidecar/identity.py), [`sidecar/drivers/bridge.py`](../sidecar/drivers/bridge.py), [`bridge/bridge.py`](../bridge/bridge.py).
15. **Rewind / Fork (Timeline)** *(→ §7.19)* — implement `/rewind` (tmux-driven, conversation-restore) + `--fork-session` + `/rewind`-inside-the-fork for branch-from-N; an explicit per-fork **file-state isolation** policy (git worktree / code-checkpoint); a **≥ v2.1.191** version gate at session create. Where: [`bridge/bridge.py`](../bridge/bridge.py), [`sidecar/main.py`](../sidecar/main.py).
16. **Handoff artifacts** *(→ §7.19; DESIGN.md's explicit deferral)* — generate a summary/handoff report on Handoff, layered on the plain context-carry-over (which ships first, #15).
17. **Load past agents** *(→ §9.9; gated on #8)* — load past agents by name, ID, or via file explorer. Fleet Setups save/load and startup auto-reconnect exist; still no on-demand per-agent resume (endpoint or UI).
18. **Agent archive** *(→ §7.12, §8.4; operator-decided, **HIGH**)* — a roster / data-table of **per-agent records** with distinct IDs (or one file per agent instantiation — open), archived **by default**: retiring an agent is a **deep-freeze**, not a discard. Records are **light except transcripts** (referenced in place per §8.6, never copied); occasional purge acceptable; **Delete stays a true delete** (§7.12). The schema **reserves lineage fields** (parent / fork / handoff), tying to per-agent git-identity attribution (#19); a separate operator-side agent is exploring lineage tracking + graphical display. The operator states the system "is not useful without it."
19. **Per-agent git identity + AI-touched index** *(→ §7.5; **HIGH**)* — each agent commits under its own author name + a **synthetic per-agent email**, so "what did AI touch" is a git query with no maintained ledger; per-folder `index.md` files ride on top (drift risk accepted). **Feeds the lineage / Agent-archive substrate** (#18, #21). Where: per-agent git config at bridge launch, [`bridge/bridge.py`](../bridge/bridge.py), `sidecar`.
20. **One-click launch — Electron-main sidecar lifecycle** *(→ §2, §4.1)* — port the Python-modeled spawn/supervise/shutdown lifecycle (`test_oneclick_launch_live`) into Electron main: own the venv path and shutdown ordering, preserving **detach-on-close** of running tmux agents through the §3.4 close dialog (crash/restart supervision stays deferred per §2's manual-relaunch posture — include only if unattended operation matters). Fallback if the port hits a wall: the `.bat` two-process launch stays the shipped model. Where: [`frontend/`](../frontend/).

### 11.4 Coordination spine, hooks & inbox (#21–28)

21. **Hook lifecycle ingestion & run-state arbiter** *(→ §7.4, §7.17; **HIGH**)* — register the HTTP `SubagentStart`/`SubagentStop` + run-state event set to the sidecar; a per-agent arbiter merges pushed run-state / `permission_mode` (**authoritative-when-fresh**) with the screen-poll fallback (Option C hybrid); the subagent hook fields become the roster's active-vs-quiet signal. **Verify during build, never assume:** arbiter ordering/dedup under concurrent load; record the `prompt_id` version floor (v2.1.196+). Where: [`sidecar/hookbus.py`](../sidecar/hookbus.py), [`sidecar/main.py`](../sidecar/main.py), [`sidecar/drivers/bridge.py`](../sidecar/drivers/bridge.py).
22. *(built 2026-07-10 — `POST /sessions/{id}/plan/verdict` (approve = the proven `keys()` Enter; revise = Escape + queued feedback, ⚠ assumed leg pending the e2e drive) + `PUT /library/document` edit-in-place; see DEVLOG)*
23. **Workflow approval via the Inbox** *(→ §7.3, §7.11; spike-proven — [`tests/workflow_approval_probe/`](../tests/workflow_approval_probe/))* — intercept a `Workflow` tool call with a **PreToolUse hook** and surface it as an Inbox **Review** card (the renamed Plans-&-Docs section) with an Approve/Reject round-trip. Proven live: the hook fires with the **full script preview** in `tool_input.script` (name / description / phases recoverable for the card content), deny aborts / allow launches, and the hook verdict **preempts** the built-in dialog (the dashboard can be the sole gate; the on-pane dialog stays the fallback). Workflow subagents are headless/one-shot — a future Subagents tab is read-only *tracking*, not control; workflow editing reuses the Library editor. Card design is the design lane's.
24. **Queue awareness** *(→ §7.3, §7.6)* — for >2 linked agents, share in message front matter that another agent's message is queued, so an agent can decide whether to wait.
25. **Links model fixes** *(→ §7.6)* — split the multi-select `relationship` list into **one relationship per link** (both-relationships = two links); add the **Piggyback** trigger value + the §7.6 defaults (Direct → Queue, Shared → Piggyback); count an exchange **per fire on one-way links** (today `messages ÷ 2` burns caps at half rate). Where: [`sidecar/links.py`](../sidecar/links.py).
26. *(built 2026-07-10 — the Projects system surface: `GET /projects` + register/open/close with the §9.1/§9.8 flows and record-keeping stop; picker/chip/dialog UI rides #37; see DEVLOG)*
27. *(built 2026-07-10 — reserved System identity + coalesced fleet card + widened usage-cap/auth matcher + tmux/WSL liveness probe; the reactive auth-expiry screen signal recorded as an unforceable boundary per the item's honest-degrade instruction; see DEVLOG)*
28. **Import external Claude context** *(→ §7.3, §7.16, §8.6; the extractors exist — [`dev/tools/claude-context-extractor/`](../dev/tools/claude-context-extractor/))* — wrap the working exporters (`extract-web.py`, `extract-desktop.py`) behind a sidecar **import module** + a thin frontend Import control, pulling an outside Claude session in by title. One engine, one selectable destination: **(a)** agent-to-agent (prompt queue / Inbox — the operator's primary interest); **(b)** operator-facing read panel — the acute pain today, since the desktop app's own export is broken/misplaced; **(c)** Library reference doc. Distinct from §8.6 (agents' *own* transcripts). Open operator calls (not blocking): destination order (recorded lean: (a) first, (b) close behind) and which panel hosts Import.

### 11.5 Readouts, console & cost (#29–36)

29. **Console streaming attach + xterm renderer** *(→ §7.13; **HIGH** within #37)* — backend: per-focused-agent `ttyd` attach to the tmux session with **`window-size manual` geometry pinning**, exposed over WebSocket; frontend: the xterm.js-class renderer in the rebuilt Console (attach-on-open / detach-on-close, bounded scrollback catch-up, keystroke passthrough). Interception stays on the JSONL transcript, never the stream. Where: `sidecar` console module, [`bridge/bridge.py`](../bridge/bridge.py), rebuilt renderer.
30. **Context breakdown + Compact controls & history** *(→ §7.18)* — parse `/context` into per-category rows; key compaction history (count / type / when) off `compact_boundary` transcript metadata; wire both into the context dropdown + run-strip. Where: [`bridge/transcript.py`](../bridge/transcript.py), `sidecar`, renderer.
31. **Per-turn statusLine context capture** *(→ §7.18)* — capture the statusLine `context_window` per-turn snapshot as the freshest context source, feeding the §7.18 readout and the run-strip; reconcile DESIGN.md's "can't read mid-run" claim to "per-turn snapshot, not a continuous gauge" (a design-lane doc touch). Where: bridge launch settings + `sidecar`.
32. **Per-agent cost on cards** *(→ §7.15)* — scrape `/cost` (via the console path) for the per-session dollar figure and surface it on each agent card, complementing the account-level band. Where: [`bridge/bridge.py`](../bridge/bridge.py), `sidecar`, renderer.
33. **Usage band — account split-source + auth-expiry reader** *(→ §7.15)* — read account tier from the correct source (the `.claude.json` tier fields are unmatched today) and add an auth-expiry signal. Where: [`sidecar/settings_io.py`](../sidecar/settings_io.py).
34. **Polling-scale rework** *(→ §4.3, §6.2)* — batch the ~5 WSL spawns/cycle and add an adaptive cadence so the fleet stops degrading from N=1; then **re-measure the practical ceiling** and document it. Where: [`sidecar/drivers/bridge.py`](../sidecar/drivers/bridge.py).
35. **Console `/clear` transcript re-resolve** *(→ §7.13, §8.6, §8.7)* — after a Console `/clear`, re-resolve + `register_session_id` so the pinned transcript follows the rotated JSONL (`/compact` is safe, no change). Where: [`bridge/bridge.py`](../bridge/bridge.py), [`sidecar/main.py`](../sidecar/main.py).
36. **Sidecar `Task`→`Agent` parser audit** *(→ §7.17, §10 #2)* — confirm the transcript parser keys on the current `Agent` tool name (renamed from `Task` in v2.1.63) and add dual-name compatibility so subagent events aren't silently missed. Where: `sidecar` transcript/serialize path.

### 11.6 Frontend build (#37–41)

37. **Renderer rebuild from the design system** *(→ §4.4 — the build-sprint item)* — rebuild the visible renderer **fresh** from `design/` (authority `mockup.html`, values `tokens.css`, behavior `behavior.js`, intent DESIGN.md), carrying [`api.ts`](../frontend/src/renderer/api.ts) as the preserved contract. Closes the §4.4/§7.5/§7.10 parity debt (25 colours, marquee, Console shell, identity editing UI) and hosts the UI halves of #13, #26, #29, #38–#41.
38. **Degraded-mode + polling backoff** *(→ §4.3)* — on `/health` failure, freeze the poll-driven panels on last-known values **marked stale** and **back off** to a gentle retry until recovery. (The consolidated system-health *display* is a separate design-lane item.) Where: renderer transport.
39. **Response-format presets (per-agent)** *(→ §7.14)* — a small preset menu of reply formats (including the operator's TL;DR-table + emoji-status style), chosen once per agent; the choice reaches and persists to the agent (`state/agents.json`). Per-message override deferred. Where: prompt composition + `state/agents.json`.
40. **Name-pool wiring** *(→ §7.5)* — the pool is **shipped** ([`assets/names/agent-names.json`](../assets/names/agent-names.json), 179 curated names); wire the Create-panel randomize + auto-name to draw from it, with user-typed names still available. Where: [`sidecar/identity.py`](../sidecar/identity.py).
41. **Authors-view provenance wiring** *(→ §8.5)* — surface the sidecars' created-by / when / session provenance into the **Authors lens already landed in the design system**; system-side wiring only. Where: [`sidecar/library.py`](../sidecar/library.py), `api.ts`, renderer.

### 11.7 Platform, hygiene & support (#42–49)

42. *(built 2026-07-10 — `schema_version` stamped by the state-store writer; see DEVLOG)*
43. *(built 2026-07-10 — rotating `sidecar/runtime/sidecar.log`, 1 MB × 3; see DEVLOG)*
44. **Docs in agent context (light)** *(→ §7.16, §10 #6)* — a curated docs home agents are pointed at (the **Library**) + **per-agent doc attachment at launch**; automatic relevance-retrieval stays §10 #6. Operator interface sketch (kept broad, for the design agents): the **Library is the hub**, reusing the review-panels' nav-rail lens pattern but organized by task / project / subproject (the Outline tab possibly going icon-based to free a slot). Where: [`sidecar/library.py`](../sidecar/library.py), prompt composition, `state/agents.json`.
45. **Prompt/UI-text markdown library (scope-aware)** *(→ §7.14, §8.2, §8.4)* — one human-editable **markdown prompt library** as the single home for every UI-injected/canned text the dashboard sends on the user's behalf: the post-reviewer-request instructions, the reviewer-request **Send** and Library **Revise** texts, Compose **snippets + templates**, the **Revise scope chip** and **Response (Structure)** options, and the Team Feed **Summarize** action (which may route to a small system-run utility model) — plus more as they surface. Format: markdown with the `##` group / `###` item convention (JSON only where placeholder fill-in genuinely needs it), organized by purpose (`responses.md`, `snippets.md`, `actions.md`). **Two scopes:** a **System copy** (the persistent cross-project store, absorbing the old "User" scope; the lean is `~/.claude` for shared runtime docs) + a **Project copy** (`<project>/.awl-cc-dash/`, §8.2). Includes adding these doc types to the **§8.4 master table**. Design-lane consumers (Compose Snippets dropdown, the Documents scoped/typed browser) are queued in the design lane.
46. **Per-turn settings + summary capture** *(→ §7.19, §7.14; feeds #15 and #39)* — capture, per Timeline turn: the agent's **settings at that turn** (model + mode/effort/thinking) and a **concise one-line turn summary**, so Timeline turn rows render a settings string + summary and collapsed Team Feed / History cards show a one-line preview. The summary's source ties to the response-format preamble (#39) — the lean is agents leading every reply with a one-liner. Display is the design lane's; this is the capture/storage side.
47. **Git automation** — handle and semi-automate Git tasks, including commits. (Rides #19's per-agent identity.)
48. **Change-log watcher** — an agent that watches codebase changes and auto-updates change logs (or similar).
49. **System-check agent** — a system-checking agent that's easy to run.

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
> docstrings, not only in this document — read the matching test before implementing a feature. The body's
> inline evidence citations (and §10's Evidence lines) name the specific test that proves each claim.
> Provenance anchor: the live-spike citations were proven on the **2026-07-02 full-suite pass — 428/428
> (395 unit + 33 live) @ commit `c73a526`, Claude CLI 2.1.198** (`results_20260702T142448Z`; spike batch
> verified @ `af4964d`), except where a later date is cited inline (the 2026-07-04/05 spikes).
