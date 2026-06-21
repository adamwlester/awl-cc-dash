---
source: claude
created: 2026-04-01
tags: [electron, architecture, research, agent-dashboard, xterm, react-flow, python]
---

## Research Brief: Electron Multi-Agent Orchestration Dashboard Architecture

**Date:** 2026-04-01
**Scope:** Deep technical investigation into architecture patterns for an Electron + React + TypeScript app that serves as a multi-agent orchestration dashboard for Claude Code AI sessions. The backend is the existing Python TmuxBridge library (pure stdlib, synchronous, subprocess-based, runs on Windows calling into WSL2). Frontend integrates React Flow (node graph) and xterm.js (terminal embedding).

---

### Sources

| # | Source | Type | URL |
|---|--------|------|-----|
| 1 | Ampere template (Electron/Vite + FastAPI) | GitHub + docs | https://amp.auxkit.dev/ |
| 2 | jlongster/electron-with-server-example | GitHub (1015 stars) | https://github.com/jlongster/electron-with-server-example |
| 3 | sasmazonur/react-vite-electron-fastapi-fullstack-template | GitHub template | https://github.com/sasmazonur/react-vite-electron-fastapi-fullstack-template |
| 4 | SO: Spawning/killing Uvicorn/FastAPI from Electron | Stack Overflow | https://stackoverflow.com/questions/70282149 |
| 5 | Wave Terminal (waveterm) frontend architecture | DeepWiki analysis | https://deepwiki.com/wavetermdev/waveterm/3-block-system |
| 6 | Wave Terminal GitHub | GitHub (18.8K stars) | https://github.com/wavetermdev/waveterm |
| 7 | Tabby terminal architecture | DeepWiki analysis | https://deepwiki.com/Eugeny/tabby/1.2-architecture-overview |
| 8 | Tabby terminal GitHub | GitHub (70K stars) | https://github.com/Eugeny/tabby |
| 9 | Superset: persistent terminal daemon for Electron | Blog post (Jan 2026) | https://superset.sh/blog/terminal-daemon-deep-dive |
| 10 | xterm.js attach addon docs | Official docs | https://xtermjs.org/docs/api/addons/attach/ |
| 11 | microsoft/node-pty | GitHub (1.8K stars) | https://github.com/microsoft/node-pty |
| 12 | ttyd (terminal over web) | GitHub | https://github.com/tsl0922/ttyd |
| 13 | gotty (terminal as web app) | GitHub | https://github.com/yudai/gotty |
| 14 | React Flow: custom nodes docs | Official docs | https://reactflow.dev/docs/guides/custom-nodes/ |
| 15 | React Flow: node status indicator | Official component | https://reactflow.dev/components/nodes/node-status-indicator |
| 16 | React Flow: auto-layout examples | Official docs | https://reactflow.dev/examples/layout/auto-layout |
| 17 | React Flow: performance guide | Official docs | https://reactflow.dev/learn/advanced-use/performance |
| 18 | electron-vite (build tooling) | Official site | https://electron-vite.org/ |
| 19 | Electron Forge Vite plugin | Official docs | https://electronforge.io/config/plugins/vite |
| 20 | python-shell npm package | GitHub (2.2K stars) | https://github.com/extrabacon/python-shell |
| 21 | Alex-Mann/electron-python-zeromq | GitHub boilerplate | https://github.com/Alex-Mann/electron-python-zeromq |
| 22 | Electron issue #24520: spawn procs don't close | GitHub issue | https://github.com/electron/electron/issues/24520 |
| 23 | xyflow/awesome-node-based-uis | Curated list (3.5K stars) | https://github.com/xyflow/awesome-node-based-uis |
| 24 | draw.io desktop (Electron) | GitHub (60K stars) | https://github.com/jgraph/drawio-desktop |
| 25 | ComfyUI litegraph.js | GitHub | https://github.com/Comfy-Org/litegraph.js |
| 26 | Reddit r/electronjs threads (multiple) | Community discussion | Multiple threads, 2024-2026 |
| 27 | Microsoft: Electron AI apps on Win11 (Mar 2026) | News | https://www.windowslatest.com/2026/03/17/ |
| 28 | WebView2 known issues (GDI leak, resize lag) | GitHub issues | https://github.com/MicrosoftEdge/WebView2Feedback |
| 29 | electron-with-server-example (IPC pattern) | Blog/GitHub (1K stars) | https://github.com/jlongster/electron-with-server-example |
| 30 | reloaderoo process-manager.ts | GitHub source | https://github.com/cameroncooke/reloaderoo |

---

### Key Findings

#### 1. Python <-> Electron Communication: FastAPI Sidecar Is the Clear Winner

**Recommendation: FastAPI sidecar with WebSocket streaming.**

The research reveals a strong consensus across the Electron + Python community. Here are the options ranked:

| Pattern | Maturity | Streaming | Complexity | Community Adoption |
|---------|----------|-----------|------------|-------------------|
| **FastAPI sidecar (HTTP + WebSocket)** | High | Native WS | Low | Strong -- multiple templates, tutorials, production apps |
| child_process + JSON-over-stdio | Medium | Manual | Medium | Used by simpler tools |
| python-shell npm | Medium | Stdout-based | Low | 2.2K stars but stale (last publish Feb 2023) |
| ZeroMQ | High | Native | High | Proven but adds native dependency complexity |
| gRPC | High | Native | High | Overkill for this use case |

**Why FastAPI sidecar wins for this project:**

- The TmuxBridge is already Python and synchronous. Wrapping it in FastAPI is trivial -- each bridge method becomes an endpoint.
- FastAPI has native WebSocket support for streaming agent status updates and terminal output.
- The Ampere template (Source 1) demonstrates exactly this architecture: Electron spawns a Uvicorn/FastAPI subprocess, frontend communicates via `fetch()` and WebSocket.
- HTTP is debuggable (curl, browser devtools) -- a major advantage during development.
- FastAPI auto-generates OpenAPI docs, which can serve as the contract between frontend and backend.

**Concrete architecture:**

```
Electron Main Process
  |-- spawns --> Python/Uvicorn (FastAPI server on localhost:PORT)
  |-- IPC --> Renderer Process (React app)
                |-- HTTP --> FastAPI REST endpoints (create, list, send, close, etc.)
                |-- WebSocket --> FastAPI WS endpoints (status stream, terminal output)
```

**Real-world examples found:**
- **Ampere** (Source 1): Clean Electron/Vite + FastAPI template with CLI scaffolding. Project structure separates `frontend/` and `backend/` directories. Uses `npm run dev` for coordinated startup.
- **sasmazonur template** (Source 3): React + Vite + Electron + FastAPI fullstack template.
- **jlongster/electron-with-server-example** (Source 2, 1015 stars): Demonstrates Electron + backend server wired via IPC. Not Python-specific but the pattern translates directly.

**python-shell verdict:** The npm package `python-shell` (Source 20) is adequate for simple request/response but does not support WebSocket-style streaming. It communicates over stdio with JSON. At 2.2K stars and last published in 2023, it is functional but stale. Not recommended for a project that needs real-time streaming.

**ZeroMQ verdict:** There is a working Electron + Python + ZeroMQ boilerplate (Source 21), and ZeroMQ is compatible with Electron via the `zeromq` npm package (prebuilt binaries available). However, it adds significant complexity (native bindings, socket patterns) for minimal benefit over FastAPI's HTTP+WS. ZeroMQ would be justified if you needed sub-millisecond IPC or complex pub/sub topologies, neither of which applies here.

---

#### 2. xterm.js + tmux Integration: Two Viable Approaches

**Approach A (Recommended): WebSocket proxy via ttyd, running inside WSL**

[ttyd](https://github.com/tsl0922/ttyd) (Source 12) is a mature C tool built on libwebsockets and xterm.js itself. It exposes a terminal session over WebSocket. Critical capability:

```bash
# Attach ttyd to an existing tmux session
ttyd tmux attach -t session_name
```

This means:
- ttyd runs inside WSL alongside tmux.
- Each agent session gets a ttyd instance (or a single multiplexed instance).
- xterm.js in Electron connects to `ws://localhost:PORT` using the built-in [attach addon](https://xtermjs.org/docs/api/addons/attach/).
- Full bidirectional PTY -- not screen scraping, real terminal I/O.
- Latency: ttyd is C + libwebsockets, latency is sub-10ms on localhost. The terminal will feel native.

**Architecture with ttyd:**

```
Electron Renderer
  xterm.js instance
    |-- WebSocket --> ttyd (running in WSL, port per session)
                       |-- PTY attach --> tmux session
```

**Approach B: node-pty bridge (more complex, more control)**

The standard Electron terminal pattern (used by Hyper, Tabby, VS Code, Wave) is:
- Electron main process spawns a PTY via `node-pty` (Source 11).
- xterm.js in renderer connects to it via Electron IPC.

For your case, this would mean:
- `node-pty` spawns `wsl -d Ubuntu -- tmux attach -t session_name`.
- xterm.js attaches via IPC to the main process.

This is how **Tabby** (Source 7-8, 70K stars) and **Hyper** work. However, node-pty has known Windows/Electron compatibility issues (Source 11 issues #649, #746, #821). The `worker_threads` issue on Windows is particularly relevant.

**Approach C (Current bridge pattern, enhanced): Polling `capture-pane` into xterm.js**

The bridge currently reads via `tmux capture-pane`. This could feed into xterm.js by:
- Polling every 100-200ms and writing the delta to xterm.js.
- This is read-only (no input to terminal).
- Latency: 100-200ms polling, noticeable but usable for monitoring.
- Not recommended for interactive use, but fine for a "dashboard view" of what agents are doing.

**Verdict:** Use Approach A (ttyd) for interactive terminal panels, and keep Approach C as a lightweight fallback for non-interactive monitoring dashboards. The Superset blog post (Source 9) provides an excellent case study of the engineering challenges involved -- they tried tmux first, then built a custom daemon, specifically because tmux hijacks xterm.js's scrollbar, selection, and hotkeys. Their lesson: **do not nest tmux inside xterm.js for interactive use**. Instead, use a WebSocket-to-PTY proxy (ttyd) that attaches to tmux without rendering tmux's own UI layer.

**Key insight from Superset (Source 9):** "As a terminal simulator itself, tmux takes over the scroll bar, selection, hotkeys, and the likes. This hijack inside of xterm.js makes it feel extremely clunky." Their solution was a custom daemon with headless xterm.js emulator per session. For your project, ttyd achieves a similar result with less custom code.

---

#### 3. React Flow for Agent Graph: Excellent Fit

React Flow (xyflow) is the right choice. 36K GitHub stars, actively maintained, and specifically designed for this kind of use case.

**Custom nodes -- fully supported:**

React Flow custom nodes are standard React components. You can embed anything:
- Progress bars, colored status dots, spinners
- Agent name, model, current task
- Token usage counters
- Mini terminal previews

React Flow even ships a pre-built **Node Status Indicator** component (Source 15) with states: `"success"`, `"loading"`, `"error"`, `"cancelled"`, `"default"`. This maps directly to your agent states (idle, generating, permission_prompt, error).

```tsx
// Example custom agent node
function AgentNode({ data }) {
  return (
    <NodeStatusIndicator status={data.state}>
      <div className="agent-node">
        <span className="agent-name">{data.name}</span>
        <StatusDot state={data.state} />
        <ProgressBar value={data.tokensUsed / data.tokenLimit} />
      </div>
    </NodeStatusIndicator>
  );
}
```

**Interactive edges -- yes:**

Edges can be clicked, styled dynamically, animated, and carry labels. You can add custom edge types with click handlers. This could represent message flow between agents.

**Dynamic add/remove -- native:**

React Flow operates on a `nodes` and `edges` state array. Adding a node is literally `setNodes(prev => [...prev, newNode])`. Removing is a filter. The library handles all animation and re-rendering.

**Auto-layout -- requires external library:**

React Flow does NOT include layout algorithms. You need one of:
- **dagre** (simple, hierarchical/tree layouts) -- deprecated but still widely used.
- **elkjs** (Eclipse Layout Kernel, far more powerful) -- actively maintained, recommended.
- **d3-hierarchy** (for tree structures only).
- **d3-force** (force-directed/organic layouts).

For 5-15 agent nodes in a hierarchical orchestration view, **elkjs with `layered` algorithm** is the best fit. React Flow has official examples for both dagre and elkjs (Source 16).

**Performance with 5-15 nodes:**

Absolutely no concern. React Flow's performance guide (Source 17) discusses optimizations for "large numbers of nodes." Their stress test example handles hundreds of nodes. At 5-15 nodes, you are orders of magnitude below any performance ceiling. No memoization or virtualization needed.

---

#### 4. Process Management: Spawn, Monitor, Cleanup

**Spawning the FastAPI sidecar:**

From Electron's main process:

```typescript
import { spawn } from 'child_process';
import { app } from 'electron';

let pythonProcess: ChildProcess | null = null;

function startBackend() {
  const pythonPath = 'python'; // or path to venv python
  pythonProcess = spawn(pythonPath, ['-m', 'uvicorn', 'app:app', '--port', '8742'], {
    cwd: backendDir,
    stdio: ['ignore', 'pipe', 'pipe'],
  });

  pythonProcess.stderr.on('data', (data) => {
    // Parse Uvicorn startup message to detect readiness
    if (data.toString().includes('Application startup complete')) {
      mainWindow.webContents.send('backend-ready');
    }
  });
}
```

**Cleanup on exit -- a known pain point:**

Electron issue #24520 (Source 22) documents that spawned child processes do NOT automatically terminate when Electron exits. This is a real problem. Solutions:

```typescript
// 1. Kill on app quit
app.on('before-quit', () => {
  if (pythonProcess) {
    pythonProcess.kill('SIGTERM');
    // On Windows, SIGTERM doesn't work reliably. Use:
    // require('child_process').execSync(`taskkill /pid ${pythonProcess.pid} /f /t`);
  }
});

// 2. Kill on window close
app.on('window-all-closed', () => {
  if (pythonProcess) pythonProcess.kill();
  app.quit();
});

// 3. Safety net: FastAPI shutdown endpoint
// POST /shutdown -> calls sys.exit(0)
```

On Windows specifically, `SIGTERM` is not reliable for killing Python processes. The `taskkill /f /t` approach (force kill process tree) is the Windows-safe method.

**Auto-restart on crash:**

The reloaderoo process-manager pattern (Source 30) provides a clean model:

```typescript
class SidecarManager {
  private process: ChildProcess | null = null;
  private restartCount = 0;
  private maxRestarts = 3;

  start() {
    this.process = spawn(/* ... */);
    this.process.on('exit', (code) => {
      if (code !== 0 && this.restartCount < this.maxRestarts) {
        this.restartCount++;
        setTimeout(() => this.start(), 1000 * this.restartCount); // backoff
      }
    });
  }
}
```

**Health check / readiness detection:**

Two reliable patterns:
1. **Parse Uvicorn stdout** for "Application startup complete" (fast, no polling).
2. **Poll a `/health` endpoint** with exponential backoff until it responds (more robust).

Pattern 2 is recommended because it also works for reconnection after a crash/restart:

```typescript
async function waitForBackend(port: number, timeout = 10000): Promise<void> {
  const start = Date.now();
  while (Date.now() - start < timeout) {
    try {
      const res = await fetch(`http://localhost:${port}/health`);
      if (res.ok) return;
    } catch {}
    await new Promise(r => setTimeout(r, 200));
  }
  throw new Error('Backend failed to start');
}
```

---

#### 5. Development Workflow: electron-vite + electron-builder

**Vite vs Webpack: Vite wins decisively in 2026.**

- **electron-vite** (Source 18) is the modern standard. It provides HMR for both renderer and main processes, with sub-second rebuild times.
- Webpack is legacy for new Electron projects. Even Electron Forge now uses Vite as its recommended bundler.
- Hot reload works well in development -- renderer hot-reloads React components, main process restarts on change.

**electron-builder vs electron-forge:**

| Aspect | electron-builder | electron-forge |
|--------|-----------------|----------------|
| Maturity | Very mature, 13K stars | Official Electron tool, 7K stars |
| Config | YAML/JSON driven | JS-config driven |
| Vite support | Via electron-vite | Via @electron-forge/plugin-vite (experimental as of v7.5.0) |
| Auto-update | Built-in electron-updater | Requires manual setup |
| Packaging formats | NSIS, AppX, DMG, snap, etc. | Same via makers |
| Recommendation | **Use for production builds** | Good for greenfield, more opinionated |

**Recommendation for this project:** Use **electron-vite** for the dev server (fast HMR) and **electron-builder** for packaging/distribution (more mature, better Windows support, built-in auto-update).

**Project scaffolding:**

```bash
# Scaffold with electron-vite
npm create @electron-vite/app@latest agent-dashboard -- --template react-ts

# This gives you:
# electron/main.ts        -- main process
# electron/preload.ts     -- preload script
# src/                    -- React app (renderer)
# electron-builder.yml    -- build config
```

Then add:
- `backend/` directory with FastAPI app wrapping TmuxBridge
- `src/components/graph/` for React Flow agent graph
- `src/components/terminal/` for xterm.js terminal panels

---

#### 6. Real-World Architecture Examples: What to Learn From

**Wave Terminal** (Source 5-6, 18.8K stars) -- THE reference architecture:
- **Stack:** Electron + React + TypeScript frontend, Go backend.
- **Communication:** WebSocket-based RPC between frontend and Go backend. Jotai for reactive state.
- **Terminal:** xterm.js with WebGL renderer, PTY data flows through backend Go service.
- **Layout:** Custom tree-based tile layout (not React Flow, but similar concept).
- **Block system:** Extensible ViewModel pattern -- each "block" (terminal, file preview, AI chat, web view) registers a ViewModel class. This maps directly to your agent nodes.
- **Key lesson:** Wave's `TermWrap` class manages xterm.js lifecycle, addons (WebGL, Search, WebLinks), and PTY data flow. Study `frontend/app/view/term/termwrap.ts`.

**Tabby** (Source 7-8, 70K stars):
- **Stack:** Electron + Angular + TypeScript, node-pty for terminal.
- **Architecture:** Plugin-based with Angular DI. Each connection type (SSH, local, serial) is a plugin.
- **Terminal:** xterm.js with node-pty backend.
- **Key lesson:** Modular plugin architecture for connection types. The `tabby-local` plugin wraps node-pty; `tabby-ssh` wraps SSH -- same terminal UI, different backends. Your agent types could follow this plugin pattern.

**Superset** (Source 9) -- THE reference for terminal persistence:
- **Stack:** Electron + React, custom terminal daemon.
- **Architecture:** Three-layer process model: Electron main -> Terminal Host Daemon (Node.js) -> PTY subprocess per session.
- **Communication:** NDJSON over Unix domain sockets, split into Control Socket (RPC) and Stream Socket (data).
- **Key innovation:** Daemon spawned with `ELECTRON_RUN_AS_NODE=1` so it runs as plain Node.js without Chromium overhead. Daemon survives app restarts.
- **Key lessons:**
  - They tried tmux-in-xterm.js first and abandoned it (clunky, hijacks scrolling).
  - Headless xterm.js emulator per session for accurate state snapshots on reconnect.
  - Two-socket split prevents head-of-line blocking (terminal output doesn't block RPC).
  - Concurrency limiter (semaphore) prevents spawn storms when opening many terminals.
  - 128KB batched output with 32ms flush interval for ~30fps visual updates.

**draw.io Desktop** (Source 24, 60K stars):
- Electron wrapper around a graph/diagram editor.
- Demonstrates that complex interactive graph UIs work well in Electron.

**ComfyUI** (Source 25):
- Node-graph editor (litegraph.js) for AI workflow orchestration.
- Closest conceptual match to your project -- AI nodes with status, connected in a flow.
- Uses Canvas2D rather than React/DOM, so React Flow is a better choice for your React stack.

---

#### 7. Windows-Specific Gotchas

**Chromium/Electron on Windows 11:**
- Microsoft is actively encouraging Electron AI apps on Windows 11 (Source 27, March 2026).
- Electron uses its bundled Chromium, NOT WebView2. No WebView2 dependency or issues.
- The WebView2 GDI object leak (Source 28) does NOT affect Electron.
- Cold start times for Electron are now under 500ms on modern hardware (Source: dev.to article on Electron in 2026).
- RAM usage is the main concern. Expect 200-400MB baseline for an Electron app. Each xterm.js terminal instance adds ~10-20MB.

**WSL interaction from Node.js:**
- Yes, Node.js can call `wsl.exe` directly via `child_process.spawn('wsl', ['-d', 'Ubuntu', '--', 'command'])`.
- This is exactly what TmuxBridge already does. The FastAPI sidecar would continue this pattern.
- However, there is an alternative: the FastAPI server itself could run inside WSL, eliminating the `wsl` subprocess hop entirely. This would be faster for tmux operations.

**Recommended architecture for WSL:**

```
Option A (simpler, current pattern):
  Electron (Windows) -> FastAPI (Windows) -> wsl.exe -> tmux (WSL)

Option B (faster, recommended):
  Electron (Windows) -> FastAPI (inside WSL, exposed on localhost) -> tmux (WSL directly)
```

Option B eliminates the `wsl.exe` subprocess overhead on every tmux command. FastAPI running inside WSL can call tmux directly. Electron connects to `localhost:PORT` regardless of whether the server is on Windows or WSL -- the network is shared.

**File path handling:**
- Windows paths (`C:\Users\...`) need conversion to WSL paths (`/mnt/c/Users/...`).
- TmuxBridge already has `win_to_wsl()` in `paths.py`. This must be preserved in the FastAPI layer.
- Frontend should always work with Windows paths; backend translates as needed.

**Windows Terminal coexistence:**
- The Electron app can replace WT tabs for agent sessions entirely.
- However, keeping WT tabs as a fallback (via `bridge.show()`) is valuable for debugging.
- Recommended: Electron dashboard is the primary UI; WT tabs are a "pop-out" option for direct tmux access.

---

### Confidence Assessment

**High confidence:**
- FastAPI sidecar is the right communication pattern. Multiple production examples, strong community consensus, and the existing bridge maps cleanly to REST+WS endpoints.
- React Flow handles 5-15 custom nodes with zero performance concerns. Official stress tests demonstrate hundreds of nodes.
- React Flow custom nodes support arbitrary React content including status indicators, progress bars, and interactive elements. This is a core feature with official examples.
- electron-vite is the correct build tool choice for 2026. Vite has won the bundler war for Electron.
- Windows 11 + Electron has no show-stopping issues. Microsoft is actively promoting this combination.

**Medium confidence:**
- ttyd as the WebSocket-to-tmux proxy is the best approach for terminal embedding, but integration with Electron's localhost networking needs testing. Specifically: can Electron's renderer connect to a ttyd WebSocket running inside WSL on a forwarded port? WSL2's networking has historically had quirks.
- Running FastAPI inside WSL (Option B) is faster but adds deployment complexity (managing a WSL-side Python environment). The simpler Option A (FastAPI on Windows) may be pragmatically better for a first version.
- The Superset daemon pattern is ideal for terminal persistence, but building a custom daemon is significant engineering effort. For v1, ttyd + tmux provides persistence for free (tmux sessions already survive app restarts).

**Low confidence:**
- node-pty compatibility with current Electron + Windows 11. Multiple GitHub issues report problems (worker_threads, crashes). If the ttyd approach doesn't work out, node-pty as a fallback needs careful testing. *This is speculative -- the issues may be resolved in newer versions.*
- Whether xterm.js + ttyd-attached-to-tmux avoids the "clunky hijack" problem that Superset reported with direct tmux-in-xterm.js. ttyd may handle this better because it manages the PTY layer, but this needs hands-on testing.

---

### Gaps

1. **ttyd + WSL2 networking:** No source confirmed that xterm.js in an Electron renderer can connect to a ttyd WebSocket inside WSL2 without manual port forwarding. WSL2 automatic port forwarding is known to be unreliable for some use cases. Needs hands-on testing.

2. **FastAPI sidecar packaging:** How to bundle a Python environment with Electron for distribution. Options include PyInstaller (freeze to .exe), embedded Python, or requiring Python as a system dependency. The Ampere template punts on this. Real packaging story needs investigation.

3. **ttyd multi-session management:** ttyd runs one command per instance. With 5-15 agent sessions, you would need 5-15 ttyd instances on different ports, or a multiplexing proxy. No source addressed this at scale. Alternative: a single WebSocket proxy that can attach to any tmux session on demand.

4. **Electron IPC security model:** How to securely expose the FastAPI server (localhost only, auth token, etc.) to prevent other local apps from controlling agent sessions. Not researched in depth.

5. **State synchronization:** How to keep the React Flow graph state in sync with the actual tmux session state (sessions created externally, sessions that crash, etc.). Requires a polling or event-driven reconciliation loop.

---

### Recommended Next Steps

**Phase 1: Proof of Concept (1-2 days)**

1. **Scaffold the Electron + React project** using `npm create @electron-vite/app@latest` with the `react-ts` template.
2. **Create a minimal FastAPI wrapper** around TmuxBridge with 3 endpoints: `GET /sessions`, `POST /sessions/{name}/send`, `WS /sessions/{name}/stream`.
3. **Verify ttyd integration:** Install ttyd in WSL, run `ttyd -p 7682 tmux attach -t test`, and confirm xterm.js in the Electron renderer can connect to `ws://localhost:7682/ws`.
4. **Render a static React Flow graph** with 3 hardcoded agent nodes and verify custom node rendering (status dot, name, state label).

**Phase 2: Core Integration (3-5 days)**

5. **Implement sidecar lifecycle management** in Electron main process: spawn FastAPI on app start, health-check loop, kill on quit (using `taskkill` on Windows).
6. **Connect React Flow to live data:** poll `GET /sessions` every 2 seconds, update node states dynamically.
7. **Wire xterm.js panels:** clicking an agent node opens its terminal panel via ttyd WebSocket.
8. **Add elkjs auto-layout** so the agent graph arranges itself as nodes are added/removed.

**Phase 3: Polish (ongoing)**

9. **Add WebSocket streaming** from FastAPI for real-time status updates (replace polling).
10. **Implement terminal panel management:** split views, resizable panels (study Wave Terminal's TileLayout).
11. **Add agent lifecycle controls:** create, send prompt, interrupt, close -- all from the graph UI.
12. **Evaluate running FastAPI inside WSL** (Option B) for reduced latency.

**Key decision to make before starting:** Whether FastAPI runs on Windows (simpler, matches current bridge) or inside WSL (faster tmux access, harder to manage). Recommendation: start with Windows (Option A) for v1, migrate to WSL (Option B) if latency is a problem.
