# DEVLOG Archive 01 — 2026-03-26 → 2026-06-13

> Archived, immutable DEVLOG history. These entries were rotated out of the root `DEVLOG.md` on 2026-06-23 to keep the active log small (see the **Rotation** rule in the DEVLOG header and the **Archived history** index at the bottom of that file). Entries are **verbatim** — original `### …` headings and `Files:` lines preserved. Never edit archived entries; record new history in `DEVLOG.md`, which rotates the oldest entries here whenever it grows past ~700 lines.
>
> Span: the sandbox-era reconstruction block — workspace creation (2026-03-26) through the 2026-06-13 04:43 file reorg. 21 entries, all [Reconstructed]. The explanatory note that originally introduced them in DEVLOG.md is reproduced below.

> Entries before 2026-06-13 were reconstructed from chat transcripts, git history, and design artifacts. They are marked [Reconstructed] and their timestamps are approximate. Entries from 2026-06-13 onward are normally recorded directly by agents during active work sessions — except a few [Reconstructed] 2026-06-13 entries (the dashboard point releases v5p5–v5p9) that were backfilled afterward from git history and file mtimes because the agents failed to log them at the time.

---

### [Reconstructed] 2026-03-26 10:00:00 — Workspace created

Initial repo scaffolded. VS Code workspace configured. First MCP servers set up.

### [Reconstructed] 2026-03-28 14:00:00 — MCP server configuration complete

Core MCP servers configured: Playwright, GitHub, Google Workspace, Firecrawl, Apify, Brave Search, Exa, Notion, Docker, and others. Settings and permissions established.

### [Reconstructed] 2026-03-31 05:39:00 — Workspace scaffolding

Python environment set up. Memory system built out. Agent definitions and skills created. Obsidian integration added (later removed 2026-06-13). Folder structure established: briefs/, docs/, data/, prompts/, tools/, archive/.

### [Reconstructed] 2026-03-31 15:17:00 — tmux bridge: first draft

`awl_claude_tmux_bridge` created as a Python package. Controls Claude Code TUI sessions running in tmux inside WSL2. Sessions get visible Windows Terminal tabs. Core methods: create, send, read, status, close, shutdown.

Files: `~/.claude/tools/awl_claude_tmux_bridge/`

### [Reconstructed] 2026-03-31 17:57:00 — tmux bridge: stable

Bridge expanded to 20 methods in ~3 hours. Added: keys, read_log, rename, resume, batch_create, broadcast, interrupt, scrollback, watch, wait_idle, export, mcp_sync. Config setters: set_cwd, set_model. 30-test suite written and passing. JSONL transcript parsing, MCP config sync (Windows→WSL), screen state detection (idle, generating, permission_prompt). This is the backbone of all agent orchestration.

Files: `~/.claude/tools/awl_claude_tmux_bridge/`, `tools/testing/test_tmux_bridge.py`

### [Reconstructed] 2026-03-31 18:45:00 — HTTP bridge built

VS Code extension (`awl-claude-http-bridge`) running an HTTP server on port 7483. Endpoints: POST /create, POST /send, POST /focus, GET /list, POST /close, GET /health. Can create and send to VS Code terminal tabs but cannot read output back — fire-and-forget only. Functional but limited compared to tmux bridge.

Files: `~/.vscode/extensions/awl-claude-http-bridge/`

### [Reconstructed] 2026-03-31 20:30:00 — Dashboard: project inception

Initial concept: a TUI dashboard (Python/Textual) running as Tab 0 in tmux, with Claude Code agent sessions in Tabs 1+. All communication through the tmux bridge. Created `ui-plan-v1.md` — a 2-pane layout (left: agent graph + scratchpad + activity log, right: agent detail sidebar) with F-key navigation. Agent naming used nature/material words (cedar, flint, heron). Link types: On idle, On file change, Manual only.

Files: `agent-dashboard/archive/ui-plan-v1.md`

### [Reconstructed] 2026-04-01 10:00:00 — Dashboard: architecture research

Deep research into Electron + React + TypeScript for the dashboard. 30 sources evaluated. Key decisions: React Flow for agent graph, xterm.js for terminal embedding (via ttyd WebSocket proxy to tmux), electron-vite for build tooling, FastAPI sidecar wrapping TmuxBridge for backend. Reference architectures: Wave Terminal, Ampere template.

Files: `docs/research/electron-agent-dashboard-architecture-research.md`

### [Reconstructed] 2026-04-01 15:30:00 — Dashboard: decision — TUI → Desktop GUI

User confirmed "B for sure" when asked TUI vs Electron. Rationale: richer UI (embedded terminals, proper graph rendering, drag interactions, full color). The TUI spec (`ui-plan-v1.md`) was superseded. `ui-plan-draft.md` written as the new canonical vision spec — 3-pane layout, embedded CLI, Team Feed with 4 tabs, link triggers (Immediate/Next/Queued/Held), inter-agent XML message format, human-name agent naming pattern.

Files: `agent-dashboard/design/ui-plan-draft.md`

### [Reconstructed] 2026-04-02 11:00:00 — Dashboard: wireframe v1 and v2

Built first interactive HTML/Tailwind wireframes. v1 used Tailwind's default zinc palette with no custom colors. v2 introduced a custom cold indigo-slate palette (`base: 950:'#0c0d16'`) with violet accents (`#7c3aed`). Both had the 3-pane layout but lacked agent icons, subagent display, and many detail panel fields.

Files: `agent-dashboard/design/ui-concept-v1.html`, `agent-dashboard/design/ui-concept-v2.html`

### [Reconstructed] 2026-04-02 13:00:00 — Dashboard: palette exploration tool

User wanted a warmer, more distinctive palette than the generic slate/violet theme. Built a 10-palette comparison tool rendering demo components in each candidate theme. Palettes ranged from "Happy Hues 17" (light cream) to "Eggplant & Dusty Gold" to "Vintage Teal" to "Berry & Cream." Each palette had a live interactive preview.

Files: `agent-dashboard/design/palette-options/index.html`

### [Reconstructed] 2026-04-02 15:00:00 — Dashboard: wireframe v0.3 (major layout overhaul)

Massive update incorporating user feedback:
- Pane split adjusted from 37/25/38 to 40/22/38
- Equal 36px heading strips across all panels
- Window footer for bottom breathing room
- Functional draggable vertical splitters (JS mousedown/move)
- Terminal-dark backgrounds on streaming/data panels
- Every sub-panel titled: Team Graph, Team Feed, Activity Log, Agent, CLI, Prompts
- Agent icons introduced: owl (researcher), fox (synthesizer), cat (auditor), daemon (subagent)
- Name parsing on cards: role line + "01 sandy" below
- Subagent mini-circles on parent cards
- Status indicators: green (working), gray (idle), pulsing amber (permission)
- Detail panel expanded: Description, Skills, Tools, Memory, Lifecycle (max turns)
- Actions restructured: Rollback, Clone, Retire
- Color and Icon pickers with accordion expand
- Compose target changed from dropdown to multi-select pill toggles (absorbed Broadcast)
- Prompt History tab with source-colored entries and Reuse button
- Link drawer slides out from graph panel

The version files were snapshots saved during iteration — `ui-concept.html` was the active working file being overwritten.

### [Reconstructed] 2026-04-02 17:00:00 — Dashboard: wireframe v3 (Vintage Teal palette)

Applied "Vintage Teal" palette from the palette-options picker. Deep ocean-teal base (`sea: 950:'#091318'`), gold accent (`#e8b058`), warm cream text. 5 accent colors total (gold, coral, teal, sage, blush). Used gold as the primary interactive accent (buttons, active tabs, segmented controls).

Files: `agent-dashboard/design/ui-concept-v3.html`

### [Reconstructed] 2026-04-02 23:30:00 — Dashboard: wireframe v4 (Warm Dark palette — current)

Replaced Vintage Teal with a new palette derived from Happy Hues 8 + 9. Shifted from cool ocean-teal undertones to warm purple-brown base (`base: 950:'#141018'`). Split accent role: teal (`#078080`) for primary actions, orange (`#ff8e3c`) for secondary/active states. Expanded agent color palette from 5 to 10 (teal, coral, orange, sage, lavender, gold, rose, sky + magenta, blush) — sufficient for 8 distinguishable agents. Added a Color Palette Reference section at the bottom of the wireframe as a design token spec for implementation handoff. Changed border weight from 1px to 2px throughout. Reduced border-radius from rounded-full to 4px on most surfaces. Version tag bumped to v0.4.

Files: `agent-dashboard/design/ui-concept-v4.html`

### [Reconstructed] 2026-04-03 08:00:00 — Architecture pivot: SDK replaces terminal embedding

Spike test proved that `claude -p --output-format stream-json` returns typed SDK events (AssistantMessage, tool_use, text, thinking, result). This eliminates the need for xterm.js + ttyd terminal embedding — the riskiest technical dependency (WSL2 port forwarding for WebSocket). New architecture:

```
Electron → React → FastAPI sidecar → Python Agent SDK → Claude CLI (stream-json)
                                           ↕
                                    tmux (crash recovery only)
```

Tmux shifts from "the thing we embed in the UI" to "the safety net underneath." Multi-agent handoff document created for coordinating between agents working on sidecar vs frontend.

Files: `docs/testing/sdk-stream-spike-findings.md`, `docs/testing/architecture-decision-handoff.md`

### [Reconstructed] 2026-04-03 11:00:00 — Sidecar built (FastAPI + Python Agent SDK)

`sidecar/main.py` (v0.2): FastAPI server on port 7690 wrapping `ClaudeSDKClient`. Endpoints: session CRUD, prompt send (background async), event history, SSE stream, interrupt. Multi-turn sessions via persistent Claude subprocess per session. Concurrent sessions confirmed working (2 sessions, independent prompts).

Files: `agent-dashboard/sidecar/main.py`

### [Reconstructed] 2026-04-03 14:00:00 — Electron + React frontend scaffold

Electron app via electron-vite with React renderer. Single-file `App.tsx` (~530 lines) implementing: session list (left panel), event feed with typed renderers (tool calls, text, thinking, results, rate limits), prompt composer with send/stop, auto-scroll with "New events" pill, sidecar health check polling. Uses Vintage Teal color constants (not yet updated to v4 Warm Dark palette). `start-dashboard.bat` launches sidecar then frontend.

Files: `agent-dashboard/frontend/src/renderer/App.tsx`, `agent-dashboard/frontend/src/main/index.ts`, `agent-dashboard/start-dashboard.bat`

### [Reconstructed] 2026-04-03 16:30:00 — Pipeline proof: E2E working

End-to-end validation: sidecar + SDK + React event rendering. Multi-tool tasks (bash + text response) produced 17 events through the full pipeline. Concurrent sessions, cost tracking ($0.13–0.23 per query), permission auto-approve — all working. This is the last confirmed working state of the implementation.

Files: `docs/testing/pipeline-proof-results.md`

### [Reconstructed] 2026-04-03 18:30:00 — Design system + component specs written

Extracted design tokens from the Vintage Teal wireframe into a standalone spec. Event feed component spec written with detailed rendering rules per SDK event type.

**Note:** These specs reference the Vintage Teal palette (`sea-*`, `cream-*`, `teal: #68b8c8`, `gold: #e8b058`). The v4 wireframe uses a different palette (`base-*`, `warm-*`, `teal: #078080`, `orange: #ff8e3c`). These specs need updating before implementation resumes.

Files: `docs/testing/design-system-spec.md`, `docs/testing/event-feed-component-spec.md`

### [Reconstructed] 2026-04-19 12:00:00 — Dashboard files moved to awl-dashboard/testing/

All design and spec files moved from `ui/` to `awl-dashboard/testing/`. The palette options tool, wireframes, plan specs, and design-tools.js were moved together.

### [Reconstructed] 2026-06-13 04:43:00 — Files reorganized to agent-dashboard/design/

Directory restructure: `awl-dashboard/testing/` → `agent-dashboard/design/`. `ui-plan-v1.md` moved to `agent-dashboard/archive/`. Frontend scaffold and sidecar retained at `agent-dashboard/frontend/` and `agent-dashboard/sidecar/`.
