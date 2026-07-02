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
> line numbers. A section with no marker is a section where code and intent already agree. The build queue
> that clears these markers lives in [`dev/notes/TODO.md`](../dev/notes/TODO.md) (NEXT UP — BUILD), which
> carries the task-level detail; this doc carries the decisions.
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
covering the one-time prereqs is tracked in [`dev/notes/TODO.md`](../dev/notes/TODO.md) (H3).

**Security posture — accepted by decision.** The sidecar binds `0.0.0.0:7690` with no authentication
because agents inside WSL must be able to POST hook callbacks to the Windows host; this is accepted for a
single-user personal machine, as a choice. (`AWL_SIDECAR_HOST` overrides the bind host; the frontend always
talks to `127.0.0.1:7690`.)

**One sidecar instance.** A single sidecar process on `:7690` serves whichever project is open. Its state
is partitioned per project folder (§8), so serving a different project is a matter of which project store
it is reading and writing — never a second process.

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
the design work is queued in [`dev/notes/TODO.md`](../dev/notes/TODO.md) (NEXT UP — DESIGN).

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
  running agents via the hook/watermark path (§7.7). The **Console** polls on its own demand-driven
  schedule (§7.13).

### 4.4 Design-system parity

The React renderer implements the finished design system **1:1** — every component, token, and interaction
in `design/` (authority: `mockup.html`, values in `tokens.css`) has a functional twin in the renderer. The
mockup owns the pixels; the renderer is the working client of the same design.

⚠ **Today:** the renderer trails the mockup — 16 agent colours vs the design's 25, Console gaps, the
marquee omitted, and some controls are honest no-ops for engine-blocked features. The port up to the
finished mockup/tokens is **deliberately deferred until design churn approaches zero**; this is status, not
identity.

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
| **Library** | `GET /library/documents` · `GET /library/document` · `GET/POST /library/reviews` |
| **Console** | `GET /console/catalog` · `POST /sessions/{id}/console/run` (+ the live screen mirror, §7.13 — ⚠ **Today:** the mirror feed is not wired) |
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
(§10); mode is launch-only until it is sorted.

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
(§8.2), shown everywhere, and **read-only in v1**. Pools are **25 colours and 50 curated icons**, assigned
round-robin (`colour = n mod 25`, `icon = n mod 50`); past 16 agents the icon becomes the primary
disambiguator. Icons are recolorable SVGs served from `assets/icons/agents/` via
`GET /assets/agent-icons/{name}?color=`. ⚠ **Today:** the React client ships only 16 colours (design-parity
lag, §4.4 — not a decision change).

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
from the UI and from all persistence. The round-trip: the bridge's screen-state detects the tool-permission
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
partial step-into over the left + middle columns. Its model is a **live mirror of the agent's real terminal
screen plus keystroke passthrough**:

- **Mirror:** `capture-pane` mirrors everything — output, menus, dialogs, the input/status bar — exactly as
  a human at the terminal would see it.
- **Passthrough:** the Console input passes keystrokes through to the TUI, so interactive slash-command
  follow-ups are answered exactly as if sitting at the terminal — the same `keys()` mechanism as the
  permission round-trip.
- **Slash-command runner:** a full grouped catalog with filter, staged into a run bar
  (`GET /console/catalog`, `POST /sessions/{id}/console/run`), routed via the bridge's `send`/`keys`.
- **Demand-driven polling:** none while the tab is closed; **one bounded scrollback pull on open** (catch-up
  is a single fetch); **fast polling a few times per second while visible**. Each poll crosses the
  Windows→WSL boundary (~50–150 ms), which is why the cadence is gated on visibility.

⚠ **Today:** the live mirror feed and keystroke passthrough are not wired, and the React Console is
stubbed in places; the catalog + run endpoints exist. Rendering fidelity (plain text vs ANSI colors needing
a terminal-renderer component) is the one open sliver (§10).

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

### 7.15 Settings

Settings are **fully interactive**: a write is exposed for everything the engine can set (Config · MCP ·
Plugins, at user + project scope) plus per-agent scoping in the Create/Agent panel — and **all writes are
confirm-gated** (`GET /settings/{read,account,config,mcp,plugins}`, `POST /settings/write`). Feasibility is
marked honestly in the UI: mid-run permission-mode change is blocked (§7.11); per-agent MCP/model/plugins
take effect at launch/restart; tool scoping is deny-based. The **Account band** (email/org/plan from local
creds) and the **usage-limits band** (session/weekly %, live from the API, graceful degrade) are both in.
The intended cost surface goes one level deeper: **live per-agent cost/usage figures on each agent card**,
complementing the account-level band. ⚠ **Today:** the bridge emits no cost data, so no per-agent figure is
shown — an honest blank, never a fabricated number (open question, §10).
The Setups store lives in the dashboard store (§8.1). The tab set and the Projects tab are §3.2.

### 7.16 Library

The Library reads and renders **Plans, Documents, and Assets** from the open project's
`.awl-cc-dash/` folder (`plans/`, `docs/`, `assets/` — §8.2), reached via WSL. The dashboard **never writes
into a content file**: content is the agent's (or user's) markdown, exactly as written; everything the
dashboard adds — verdicts, comment threads, anchors, provenance — lives in the per-doc `.meta.json` sidecar
(§8.5). Documents carry the same review treatment as Plans (comments; the footer action strip minus
Reject/Approve — design work tracked in [`dev/notes/TODO.md`](../dev/notes/TODO.md)). The Library can also
browse other repo `.md` files read-only; commenting applies to dashboard-owned files under `.awl-cc-dash/`
only (§8.5; extendable later if needed).

Plan-approve from the dashboard resumes the agent out of plan mode. ⚠ **Today:** that resume path is
unproven (it rides the spike-gated Plan hook, §10); the Library lists plans **non-recursively** from the
top of `cwd` (or one named subdir — nested trees are not walked; [`sidecar/library.py`](../sidecar/library.py)),
single-doc reads are path-explicit rather than cwd-scoped (the `/library/document` handler in
[`sidecar/main.py`](../sidecar/main.py)), reviews live in one central `plan-reviews.json` keyed by filename,
Documents are read-only with no comment store, and no Assets surface exists.

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

1. **Content and metadata are separate files, paired by name.** `roadmap.md` is pure markdown, exactly as
   the agent wrote it — the dashboard **never writes into the content file**. Next to it,
   `roadmap.meta.json` holds everything else: review state/verdict (+ who/when), comment threads
   (text · author · timestamp · resolved), quote-anchors, and provenance (created-by/when/session). Nothing
   is embedded in the content file — no frontmatter requirement, no citation markers.
2. **Anchoring without citations.** A comment targeting specific text stores the *quoted snippet* plus the
   nearest heading; the UI matches and highlights it live. If the text is later edited beyond recognition,
   the comment degrades gracefully to a doc-level comment. The content file stays pristine.
3. **Renames are dashboard-mediated.** The dashboard renames both files of the pair together; an orphaned
   `.meta.json` (no matching `.md`) is detectable and offered for re-link. If agent-driven renames ever
   bite in practice, an embedded stable id can be added *then* — additive, nothing to unwind.
   ⚠ **Today:** reviews live in one central `plan-reviews.json` keyed by the plan's filename
   ([`sidecar/library.py`](../sidecar/library.py)), so a rename silently orphans the review.
4. **Documents get comments like Plans** — the editor-header Comment control plus the Plans-style footer
   action strip minus Reject/Approve (design work tracked in [`dev/notes/TODO.md`](../dev/notes/TODO.md)).
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

### 8.7 Two spots to watch

1. **Transcript-scheme drift.** The dir-name encoding and `--resume` behavior belong to Claude Code, not
   the dashboard; pinned retention + persisted resolved paths reduce the blast radius, and the live-verify
   habit in the bridge test suite is the canary for drift.
2. **Concurrent writers on one project.** Two agents in the same project share one `state/` directory —
   fine for append-only files (`routing.jsonl`) and keyed writes, but the state-store implementation must
   do **atomic write-replace per file** to avoid torn JSON.

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

The home for unresolved items. The numbered **open-questions queue** below holds only things that are still
open; a short **Decided omissions** ledger at the end records engine limits that are *settled* (so they are
not re-litigated as open questions). Framing: the product works within Claude Code's engine limits, but this
doc describes the intended end-user experience — each limit gets an honest attempt at a tractable solution
before a fallback is promoted to final intent. An entry closes one of two ways: **sorted** (a mechanism is
found and woven into the body) or **explicitly omitted** (moved to Decided omissions). The body text above
already states each intended behavior at its natural home, with a Today-marker.

Each entry carries a **status tag** — the reality of the capability *today*, not whether the question is
resolved (everything in the queue is unresolved) — plus an **Evidence** line citing the test that backs the
claim, marked **live** (real WSL2/tmux, strongest) or **unit** (hermetic contract):

- ✅ **proven** — a test or live run establishes it
- ◐ **partially proven** — part is built & tested; part is still open
- ❓ **unproven** — a plausible path exists; needs a POC/spike
- ⛔ **impossible-today** — current findings show no path on the bridge as-is (a decided limitation → Decided omissions, not the queue)

Live citations below reference the **2026-07-02 full-suite pass — 428/428 (395 unit + 33 live) @ commit
`c73a526`, Claude CLI 2.1.198** (`results_20260702T142448Z`).

Maintenance note: when adding, removing, or moving entries, renumber them continuously across the priority
subsections in display order (High → Medium → Low); do not restart numbering inside each subsection. Keep a
status tag + Evidence line on every entry. An item that resolves to ⛔ moves to **Decided omissions** (which
is *not* part of the numbered queue), never deleted.

### Priority — High

**1. Mid-run permission-mode change** *(→ §6.2, §7.11)* — ❓ **unproven**
- **Evidence:** no test covers mode-change; the live finisher suite proves permission approve/deny, resume,
  and model+effort (`test_bridge_finisher_live`, **live**) but **not** mode. `set_mode` is an honest no-op
  today; the Shift+Tab/`keys()` POC below is plausible but unproven.
- **Desired final behavior:** the operator changes an agent's permission mode live, mid-run, from the UI.
- **Current blocker:** the CLI only cycles modes via Shift+Tab inside the TUI — no flag, no slash command,
  no API; the bridge driver doesn't advertise `set_mode` and `POST /sessions/{id}/mode` returns an honest
  `400`.
- **Research/POC must establish:** whether sending Shift+Tab via the bridge's `keys()` at a known-idle
  screen state cycles modes deterministically, with the resulting mode read back from the status line.
- **Fallback if infeasible:** mode stays launch-only; the UI presents it as a launch-time choice, never a
  fake-live control.

**2. True mid-run Inject** *(→ §7.3)* — ◐ **partially proven**
- **Evidence:** hook-boundary delivery is **unit-proven** (`test_hookbus_unit`, `test_sidecar_unit`); only
  the *immediate, mid-turn* variant is open. (This corrects any framing that treats all Inject as unbuilt —
  hook-boundary Inject ships.)
- **Desired final behavior:** an Inject-disposition message reaches a running agent immediately, mid-turn.
- **Current blocker:** no safe arbitrary injection point exists on a live TUI; the hook channel delivers
  only at tool boundaries (`PostToolUse`) or turn end (`Stop`), so Inject degrades to Next/Queue.
- **Research/POC must establish:** whether any earlier safe delivery point exists (e.g. typeahead into the
  composer without corrupting an in-flight turn, or an engine-side input API).
- **Fallback if infeasible:** hook-boundary delivery plus the transparent Next/Queue degrade is the final
  model.

**3. Console rendering fidelity** *(→ §7.13)* — ❓ **unproven**
- **Evidence:** no test; plain `capture-pane` demonstrably drops ANSI. Track as two gaps: live-mirror +
  keystroke passthrough *wiring* is separate from ANSI/xterm-level *fidelity* — prove the wiring first, then
  decide if fidelity is worth it.
- **Desired final behavior:** the Console mirror renders the terminal faithfully, including colors,
  spinners, and box-drawing.
- **Current blocker:** plain `capture-pane` output drops ANSI styling; faithful rendering needs `-e`
  escape capture plus a terminal-renderer component (xterm.js-class) in the frontend.
- **Research/POC must establish:** the cost/fit of ANSI-preserving capture plus a renderer, vs styled-text
  approximation.
- **Fallback if infeasible:** a clean plain-text mirror.

**4. Plan/Decision hook interception (spike-gated)** *(→ §7.4, §7.16)* — ❓ **unproven**
- **Evidence:** no test exercises `PreToolUse` for `ExitPlanMode`/`AskUserQuestion` under the bridge. Split
  the question: *detection* (surface a card) may be feasible from transcript/screen; the *answer/resume*
  loop (hold-for-answer, `updatedInput`, resume-out-of-plan-mode) is the unproven part.
- **Desired final behavior:** `ExitPlanMode` / `AskUserQuestion` surface as Plan/Decision inbox cards, and
  plan-approve from the dashboard resumes the agent out of plan mode.
- **Current blocker:** `PreToolUse` hook behavior for these tools under the bridge is unproven, and no
  verified resume-out-of-plan-mode path exists.
- **Research/POC must establish:** a spike proving the hooks fire with usable payloads, and whether the
  hook response (or a `keys()` sequence) can drive approval/resume.
- **Fallback if infeasible:** detect-and-surface — notify-only cards from transcript/screen detection, with
  the operator answering via the Console passthrough.

### Priority — Medium

**5. Real run-strip completion %** *(→ §7.10)* — ◐ **partially proven**
- **Evidence:** the self-reported checklist parser — the honest floor — is **unit-proven**
  (`test_checklist_unit`, 19 cases); a *genuine* progress signal beyond the checklist is unproven (the
  engine emits none).
- **Desired final behavior:** the run-strip shows a genuine completion percentage for every run.
- **Current blocker:** the engine emits no progress signal; the only honest source is the self-reported
  checklist, and without one the strip shows barber-pole indeterminate.
- **Research/POC must establish:** whether any engine-side signal (transcript structure, todo-tool events)
  yields a trustworthy progress measure beyond the checklist mandate.
- **Fallback if infeasible:** checklist self-report with the barber-pole floor is the final model.

**6. Subagent pending-vs-active status** *(→ §7.17)* — ❓ **unproven**
- **Evidence:** subagent identity/naming/ingestion is **unit-proven** (`test_subagents_naming_unit`); the
  *live pending-vs-active* signal is the unproven part.
- **Desired final behavior:** each subagent shows live pending vs active state.
- **Current blocker:** the bridge cannot distinguish a pending subagent from an active one — identity,
  naming, and transcript ingestion work, but live status cannot be shown honestly.
- **Research/POC must establish:** whether subagent-transcript activity (file mtime / last-event recency)
  or hook context inside the subagent gives a reliable active signal.
- **Fallback if infeasible:** subagents are listed without a pending/active distinction.

**7. Context breakdown & Compact controls** *(→ §7, DESIGN context dropdown)* — ❓ **unproven**
- **Evidence:** the bridge derives *total* context usage + turn count from JSONL (unit-covered in
  `test_bridge_unit`'s context-derivation); the per-category breakdown DESIGN shows, and richer compact
  multi-select/history, are neither built nor tested.
- **Desired final behavior:** an on-demand context pull with per-category rows, plus compact controls
  (multi-select options) and a compaction history (count / type / when).
- **Current blocker:** category breakdown isn't derivable from JSONL alone — it needs `/context` table
  scraping; compaction events are only inferable from `compact_boundary` transcript metadata.
- **Research/POC must establish:** whether to parse `/context`, settle for total/turn usage, or move richer
  compaction controls to an SDK path; and whether `compact_boundary` reliably marks compaction events.
- **Fallback if infeasible:** show total usage + turn count only (proven today); no per-category rows.

**8. One-click launch (Electron main spawns the sidecar)** *(→ §2, §4.1)* — ❓ **unproven**
- **Evidence:** no test; Electron main is deliberately frontend-only today. Test this *together with*
  project close/reopen semantics (what happens to running tmux agents when the app/project closes), not as
  a standalone packaging chore.
- **Desired final behavior:** one icon starts everything; quitting tears it down cleanly through the same
  close dialog as §3.4.
- **Current blocker:** Electron main is deliberately frontend-only; owning the sidecar means owning the
  Python venv path, crash/restart supervision, and shutdown ordering against agents that should keep
  running.
- **Research/POC must establish:** a spawn/supervise/shutdown POC from Electron main that preserves the
  detach-on-close semantics.
- **Fallback if infeasible:** `start-dashboard.bat` two-process launch stays the shipped model (§2).

### Priority — Low

**9. Per-agent cost** *(→ §7.15)* — ❓ **unproven**
- **Evidence:** the bridge emits no cost data; any per-agent figure would be fabricated, so none is shown. A
  harvest path (JSONL usage fields, `/cost` scrape) is plausible but unproven.
- **Desired final behavior:** live per-agent cost/usage figures on each card.
- **Current blocker:** the bridge emits no cost data at all; any displayed number would be fabricated, so
  none is shown for bridge agents.
- **Research/POC must establish:** whether per-session token/cost data can be harvested reliably (JSONL
  usage fields, `/cost` output scraped via the console path, or an engine telemetry surface).
- **Fallback if infeasible:** no per-agent cost is shown (an honest boundary, not a missing feature); the
  account-level usage band (§7.15) remains the cost surface.

**10. Attachment / citation path materialization** *(→ §7, `library.py`)* — ❓ **unproven**
- **Evidence:** `library.py` defers assets/media and doc write-back; the file/path story — how a *receiver*
  reliably reads a referenced file across the WSL↔Windows boundary — is an untested investigation item.
- **Desired final behavior:** attachments and citations route to a real on-disk home a receiving agent can
  open.
- **Current blocker:** no `.awl-cc-dash/assets/` home exists yet, and WSL↔Windows path rewriting for
  referenced files is unproven.
- **Research/POC must establish:** where attachments materialize, and how a path is rewritten so both a
  Windows renderer and a WSL agent resolve it.
- **Fallback if infeasible:** attachments stay display-only chips until a storage/path story lands.

**11. Native coordination primitives (Tasks / Workflow / SendMessage)** *(→ research notes)* — ❓ **research**
- **Evidence:** research files describe native `Task`/`TodoWrite`/`Workflow`/`SendMessage`/team-spawn
  concepts; the dashboard hasn't decided how much to adopt versus its own wrappers. No code yet — pure
  research.
- **Desired final behavior:** the dashboard's coordination (tasks, agent-team messaging) reuses native
  Claude Code primitives where they fit, rather than reinventing them.
- **Current blocker:** the trade-off (native adoption vs custom wrappers) is undecided, and native surfaces
  under the bridge are unmapped.
- **Research/POC must establish:** which native primitives are reachable/observable via the bridge, and
  which the product should adopt.
- **Fallback if infeasible:** keep the current custom coordination spine (inbox, links, scratchpad).

### Decided omissions (not open questions)

Settled engine limits — recorded here so they are not re-raised as open questions. **Not** part of the
numbered queue.

- **Fast Mode / Thinking Mode live control** *(→ §7.11, DESIGN mode toggles)* — ⛔ **impossible-today.** The
  bridge's `set_fast()` / `set_thinking()` are deliberate no-ops; current findings show no flag, API, or
  keybind to toggle these mid-run on the TUI. **Disposition:** treat as launch-time choices or omitted
  controls — never fake-live toggles. If DESIGN implies live Fast/Thinking controls, that is a design-sync
  fix, not a research item. Re-opens only if a keybind POC (cf. the mode-change BTab approach in #1) proves
  a mechanism.

---

## 11. Repo map — where the architecture lives

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
