# AWL Agent Platform — Project Log

> **For Claude sessions:**
>
> Read this file top-to-bottom before making changes to the codebase.
>
> **Status** — the ONLY section you may update in-place. Replace the whole block
> each session to reflect current state. Keep it to ~5 lines.
>
> **Log** — append-only. Every entry's heading MUST begin with a timestamp in
> `YYYY-MM-DD HH:MM:SS` (24-hour clock, to the second). **Append a new entry before you end any
> turn that changed the repo** — created, deleted, moved, or meaningfully edited any file (code,
> config, docs, or design) — and before you report "done." **Default to logging:** the bar is
> "did the repo change?", not "was it big?" Don't let the log fall behind the code (it has happened
> before). If you discover something was wrong, add a new correction entry — don't edit the old one.
> **Template:** a `### YYYY-MM-DD HH:MM:SS — short title` heading, 1–4 lines (what changed + the
> observable outcome), then a `Files:` line.
>
> **General** — never strike out, rewrite, or delete existing entries in the Log.
> The only exception is the Status block.
>
> **Scope** — this log covers the entire workspace: bridges, backend, dashboard
> design, frontend, tooling, and infrastructure. Projects under `projects/`
> maintain their own logs.

---

## Status

**Last updated:** 2026-06-21 07:11:00

**Current state:** Forked out of `claude-code-sandbox` into the dedicated **`awl-cc-dash`** repo.
Fresh git history (re-init'd on `main`, **no remote/commit yet**); ~1.2 GB of sandbox cruft purged.
Structure migrated toward the target: product dirs flat at root (`frontend/`, `sidecar/`, `bridge/`,
`design/`, `tests/`, `docs/`), `bridge/` promoted from `tools/cc_tmux_bridge`, `dev/` holds the
build-workflow assets (`notes/`, `prompts/`, `tools/`). The working MVP is now **frozen and runnable
in `archive/mvp/`** on port **7691** — verified end-to-end (sidecar API + UI round-trip, Connected
badge) — as a reference while the real app is rebuilt in place. Design authority = neobrutalism
mockup `design/ui-concept-v9p14.html`.

**Next step:** First clean commit + wire the `awl-cc-dash` remote. After that: sidecar→bridge driver
wiring and the React/neobrutalism build-out.

---

## Log

### 2026-06-21 08:02:11 — Completed root requirements.txt; fixed content-block rendering bug in live sidecar

Two fixes. (1) **Root `requirements.txt`** was missing the sidecar's web deps — rewrote it with the
complete, pinned set (`fastapi`, `uvicorn[standard]`, `pydantic`, `sse-starlette` + existing
`claude-agent-sdk`/`python-dotenv`/`pytest`), versions matched to the known-good MVP set. (2) **Live
sidecar rendering bug:** `_safe_serialize` dumped SDK content blocks via `__dict__`, which carry no
`type`, so the frontend (which switches on `block.type`) rendered nothing for text/tool/thinking
blocks. Added `_BLOCK_TYPE_MAP` and inject `type` from the block class name (TextBlock→text,
ToolUseBlock→tool_use, ToolResultBlock→tool_result, ThinkingBlock→thinking, + server variants).
Verified with a contract test (`.scratch/verify_serialize.py`) running real SDK blocks through the
live `serialize_message` via the MVP venv: blocks now carry the exact `type` App.tsx keys off
(text/tool_use/thinking/tool_result). Verified at the serialization-contract level; a full live-stack
render wasn't run (live `frontend/node_modules` not installed yet). Same bug still present in the
frozen `archive/mvp/` by design (left unchanged).

Files: rewrote requirements.txt; edited sidecar/main.py (_BLOCK_TYPE_MAP + type injection)

### 2026-06-21 07:45:00 — Repo config: dev-loop permission allowlist + launchers clear ELECTRON_RUN_AS_NODE

Closed two of the config gaps flagged this session. (1) `.claude/settings.json` — added a focused
`Bash(...)` allowlist for the build/run/test/agent-control loop (`npm`, `npx`, `node`, `python`,
`py`, `pip`, `*python.exe`, `uvicorn`, `pytest`, `git`, `wsl`, `tmux`, `curl`, `* --version`,
`* --help`) so the dev loop (incl. the future tmux/WSL bridge driver) won't stall on approvals under
`acceptEdits`/stricter modes; routed `git push` to an `ask` rule to honor "push only when asked"
(deny>ask>allow). Valid JSON, 26 allow / 2 ask rules. (2) Both launchers now `set "ELECTRON_RUN_AS_NODE="`
before starting the Electron frontend — the VS Code/Claude Code terminal sets that var, which makes
Electron run as plain Node and crash on startup (`app.whenReady` undefined). Verified faithfully: a
child `node` process spawned after the `.bat`'s clear reads the var as `undefined`. Updated the MVP
README note to say `start-mvp.bat` handles it automatically.
Files: .claude/settings.json, start-dashboard.bat, archive/mvp/start-mvp.bat, archive/mvp/README.md

### 2026-06-21 07:41:45 — Reconciled design/DESIGN.md to the v9p14 mockup (ground truth)

Audited `design/DESIGN.md` against `design/ui-concept-v9p14.html` (the visual authority) and fixed the
places where the doc still described the pre-v9p4/v9p9 UI. Rewrote the **Layout** section: the ASCII
diagram now shows the real arrangement — Agent (left, full height) · Team Graph over **Documentation**
(middle) · Team Feed over **Prompt** (right) — with the intro prose to match (box verified rectangular,
21 lines × 83 cols), and replaced the stale "diagram is v7/v9p4-era" note. Updated the **Team Feed**
("full-height right column" → right-top, above Prompt) and **Prompt** sections so the always-on
Source/Target/Filter selector columns read as the v9p9 **header dropdowns** (From/To, Filter) with the
identity-row lists inside the trigger popovers (badges collapsing to +N). Renamed two headings/anchors
(Team Feed → right,top · Prompts → right,bottom) and repointed every internal link — all 35 anchors
resolve. Tokens, palette, title bar, footer, action row, Mode control, and Link Config drawer were
already accurate; left unchanged.

Files: edited design/DESIGN.md

### 2026-06-21 07:20:01 — Verified test-import fix (already done); closed gitignore venv gap

Followed up on the two items flagged last entry. (1) **Tests:** `tests/conftest.py` and
`tests/test_tmux_bridge.py` already import from `bridge` (not `cc_tmux_bridge`) — the fix had been
applied since my earlier survey; verified the suite collects cleanly (27 tests, no import errors)
and `from bridge import TmuxBridge` resolves. No code change needed. (2) **.gitignore:** `.venv/`
and `venv/` were already present (and `.venv/` covers `archive/mvp/.venv/`); added `*-env/` to also
ignore the `<folder>-env` venv that `dev/tools/bootstrap-env.ps1` creates (e.g. `awl-cc-dash-env`).
Verified every venv path is ignored via `git check-ignore`.

Files: edited .gitignore (added *-env/ venv pattern)

### 2026-06-21 07:13:58 — Updated CLAUDE.md to current structure; deduped the design reference

Rewrote CLAUDE.md for the awl-cc-dash layout: new Project identity (dedicated dashboard repo, not a
sandbox), product-vs-`dev/` folder map, refreshed Key files (`design/DESIGN.md`,
`dev/notes/repo-migration.md`), `claude-context-extractor` path → `dev/tools/`, and a Testing
section pointing at the repo-root `.venv` (old `claude-code-sandbox-env` is gone). Resolved the
design-reference duplication: the re-added `design/README.md` and my earlier `docs/DESIGN.md` were
byte-identical — made `design/DESIGN.md` the single canonical copy (co-located with its mockups),
fixed two broken `design/ui-concept-v9p14.html` links to siblings, and removed `docs/DESIGN.md`.
Preserved the Behavioral rules verbatim. NOTE: `tests/conftest.py` still imports `cc_tmux_bridge`
from `tools/` — stale since the bridge moved to root `bridge/`; tests will fail until fixed.

Files: edited CLAUDE.md; renamed design/README.md → design/DESIGN.md (+link fixes); deleted docs/DESIGN.md

### 2026-06-21 07:11:00 — Made the frozen MVP (`archive/mvp/`) runnable on port 7691, verified end-to-end

Repointed the archived MVP off the live build's port: 7690→**7691** in all three hard-coded spots
(`sidecar/main.py` uvicorn, `frontend/src/preload/index.ts`, `App.tsx` fallback). Built a dedicated
gitignored venv (`archive/mvp/.venv`) and wrote a **complete pinned `requirements.txt`** (the old one
was missing fastapi/uvicorn/pydantic/sse-starlette). `npm install` needed `--legacy-peer-deps`
(lockfile pins vite 8 vs electron-vite 5's vite ≤7 peer). Verified functional: sidecar `/health` ok,
created a session + sent prompts via API and got real streamed events; in the UI (browser over the
vite port + the Electron GUI) the **Connected** badge shows, +New/select/delete and the prompt
round-trip work, session-init cards expand/collapse, the cost/turns/duration result bar updates live;
checked narrow (640px) and wide (1920px) extremes — no overflow. Added `README.md` (run steps,
prereqs incl. the `claude` CLI, frozen-reference note) and `start-mvp.bat`. **Known frozen-MVP gap
left unchanged:** under the current `claude-agent-sdk` (0.2.106), assistant text + tool-call cards
don't render — the sidecar serializes SDK content blocks via `__dict__` (no `type` field) while the
frontend keys off `block.type`; documented in the README, not fixed (no logic edits permitted).
Did not touch the root `frontend/`/`sidecar/`, the rest of `archive/`, or the test suite. The
`ELECTRON_RUN_AS_NODE=1` env from the IDE terminal must be cleared for Electron to launch (noted in
README). Also added `.venv/`+`venv/` to `.gitignore`.
Files: archive/mvp/sidecar/main.py, archive/mvp/frontend/src/preload/index.ts, archive/mvp/frontend/src/renderer/App.tsx, archive/mvp/requirements.txt, archive/mvp/README.md, archive/mvp/start-mvp.bat, .gitignore

### 2026-06-21 06:24:00 — Wrote agent prompt to make the frozen MVP runnable from archive/mvp/

Added `dev/prompts/archive-mvp-make-runnable.md` — instructions for another agent to set up
the soon-to-be-archived MVP (`archive/mvp/frontend` + `sidecar`) as a standalone runnable
reference. Covers: repoint port 7690→7691 in 3 places (sidecar uvicorn, frontend preload,
App.tsx fallback), a complete venv install (requirements.txt is missing fastapi/uvicorn/
pydantic/sse-starlette), `npm install`, end-to-end verification + the UI headless/headed
passes, and deliverables (README, complete requirements.txt, DEVLOG entry). User will move
the files into archive/mvp/ for the first commit; the prompt assumes they're already in place.

Files: created dev/prompts/archive-mvp-make-runnable.md

### 2026-06-21 06:18:40 — Un-nested the app: frontend/ + sidecar/ to root

`design/` had swallowed the whole old `agent-dashboard/`. Moved `design/frontend` →
`frontend/`, `design/sidecar` → `sidecar/`, `design/start-dashboard.bat` → root, and
`design/README.md` (the 43 KB design ref) → `docs/DESIGN.md`. `design/` is now
design-only (palette-options, ui-concept-v9p11..14, ui-snipets, design-tools.js).
Verified: `start-dashboard.bat` uses `%~dp0frontend`/`%~dp0sidecar` so it still
launches both as root siblings; DESIGN.md's `../archive/...` link still resolves
(docs/ and design/ are both one level under root). `archive/` left nested for now
(de-nesting would break that link). Pending: `tools/ → bridge/ + dev/` split.

Files: moved design/{frontend,sidecar,start-dashboard.bat} → root; design/README.md → docs/DESIGN.md

### 2026-06-21 06:11:51 — Migration cleanup: purged sandbox cruft, reset git history

Removed regenerable/unrelated material carried over by the full-tree copy from
`claude-code-sandbox`. Deleted: venv (`claude-code-sandbox-env/`, 709 MB),
`design/frontend/node_modules` + `out` (~400 MB), `assets/icons/references/`
(87 MB, unused — design only uses `icons/agents` + `icons/ui`), all `__pycache__`
+ `.pytest_cache`, `tools/claude-context-extractor/out`, and `session_key.txt`.
Deleted the old `.git/` (145 MB, still pointed at the `claude-code-sandbox` remote)
and re-init'd a fresh repo (`main`, no remote, no commit yet). Repo 1.3 GB → 36 MB.
Kept `archive/cc-exports/` per user. Everything deleted is recoverable from the
intact source sandbox. Still pending: `design/` un-nesting and `tools/ → bridge/ + dev/`.

Files: deleted claude-code-sandbox-env/, design/frontend/{node_modules,out}/, assets/icons/references/, **/__pycache__/, .pytest_cache/, tools/claude-context-extractor/{out/,session_key.txt}, .git/ (re-init)

> Entries before 2026-06-13 were reconstructed from chat transcripts, git history,
> and design artifacts. They are marked [Reconstructed] and their timestamps are
> approximate. Entries from 2026-06-13 onward are normally recorded directly by agents
> during active work sessions — except a few [Reconstructed] 2026-06-13 entries (the
> dashboard point releases v5p5–v5p9) that were backfilled afterward from git history
> and file mtimes because the agents failed to log them at the time.

### [Reconstructed] 2026-03-26 10:00:00 — Workspace created

Initial repo scaffolded. VS Code workspace configured. First MCP servers set up.

### [Reconstructed] 2026-03-28 14:00:00 — MCP server configuration complete

Core MCP servers configured: Playwright, GitHub, Google Workspace, Firecrawl, Apify,
Brave Search, Exa, Notion, Docker, and others. Settings and permissions established.

### [Reconstructed] 2026-03-31 05:39:00 — Workspace scaffolding

Python environment set up. Memory system built out. Agent definitions and skills
created. Obsidian integration added (later removed 2026-06-13). Folder structure
established: briefs/, docs/, data/, prompts/, tools/, archive/.

### [Reconstructed] 2026-03-31 15:17:00 — tmux bridge: first draft

`awl_claude_tmux_bridge` created as a Python package. Controls Claude Code TUI
sessions running in tmux inside WSL2. Sessions get visible Windows Terminal tabs.
Core methods: create, send, read, status, close, shutdown.

Files: `~/.claude/tools/awl_claude_tmux_bridge/`

### [Reconstructed] 2026-03-31 17:57:00 — tmux bridge: stable

Bridge expanded to 20 methods in ~3 hours. Added: keys, read_log, rename, resume,
batch_create, broadcast, interrupt, scrollback, watch, wait_idle, export, mcp_sync.
Config setters: set_cwd, set_model. 30-test suite written and passing. JSONL
transcript parsing, MCP config sync (Windows→WSL), screen state detection (idle,
generating, permission_prompt). This is the backbone of all agent orchestration.

Files: `~/.claude/tools/awl_claude_tmux_bridge/`, `tools/testing/test_tmux_bridge.py`

### [Reconstructed] 2026-03-31 18:45:00 — HTTP bridge built

VS Code extension (`awl-claude-http-bridge`) running an HTTP server on port 7483.
Endpoints: POST /create, POST /send, POST /focus, GET /list, POST /close, GET /health.
Can create and send to VS Code terminal tabs but cannot read output back —
fire-and-forget only. Functional but limited compared to tmux bridge.

Files: `~/.vscode/extensions/awl-claude-http-bridge/`

### [Reconstructed] 2026-03-31 20:30:00 — Dashboard: project inception

Initial concept: a TUI dashboard (Python/Textual) running as Tab 0 in tmux, with
Claude Code agent sessions in Tabs 1+. All communication through the tmux bridge.
Created `ui-plan-v1.md` — a 2-pane layout (left: agent graph + scratchpad + activity
log, right: agent detail sidebar) with F-key navigation. Agent naming used
nature/material words (cedar, flint, heron). Link types: On idle, On file change,
Manual only.

Files: `agent-dashboard/archive/ui-plan-v1.md`

### [Reconstructed] 2026-04-01 10:00:00 — Dashboard: architecture research

Deep research into Electron + React + TypeScript for the dashboard. 30 sources
evaluated. Key decisions: React Flow for agent graph, xterm.js for terminal
embedding (via ttyd WebSocket proxy to tmux), electron-vite for build tooling,
FastAPI sidecar wrapping TmuxBridge for backend. Reference architectures: Wave
Terminal, Ampere template.

Files: `docs/research/electron-agent-dashboard-architecture-research.md`

### [Reconstructed] 2026-04-01 15:30:00 — Dashboard: decision — TUI → Desktop GUI

User confirmed "B for sure" when asked TUI vs Electron. Rationale: richer UI
(embedded terminals, proper graph rendering, drag interactions, full color). The
TUI spec (`ui-plan-v1.md`) was superseded. `ui-plan-draft.md` written as the new
canonical vision spec — 3-pane layout, embedded CLI, Team Feed with 4 tabs, link
triggers (Immediate/Next/Queued/Held), inter-agent XML message format, human-name
agent naming pattern.

Files: `agent-dashboard/design/ui-plan-draft.md`

### [Reconstructed] 2026-04-02 11:00:00 — Dashboard: wireframe v1 and v2

Built first interactive HTML/Tailwind wireframes. v1 used Tailwind's default zinc
palette with no custom colors. v2 introduced a custom cold indigo-slate palette
(`base: 950:'#0c0d16'`) with violet accents (`#7c3aed`). Both had the 3-pane layout
but lacked agent icons, subagent display, and many detail panel fields.

Files: `agent-dashboard/design/ui-concept-v1.html`, `agent-dashboard/design/ui-concept-v2.html`

### [Reconstructed] 2026-04-02 13:00:00 — Dashboard: palette exploration tool

User wanted a warmer, more distinctive palette than the generic slate/violet theme.
Built a 10-palette comparison tool rendering demo components in each candidate theme.
Palettes ranged from "Happy Hues 17" (light cream) to "Eggplant & Dusty Gold" to
"Vintage Teal" to "Berry & Cream." Each palette had a live interactive preview.

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

The version files were snapshots saved during iteration — `ui-concept.html` was the
active working file being overwritten.

### [Reconstructed] 2026-04-02 17:00:00 — Dashboard: wireframe v3 (Vintage Teal palette)

Applied "Vintage Teal" palette from the palette-options picker. Deep ocean-teal
base (`sea: 950:'#091318'`), gold accent (`#e8b058`), warm cream text. 5 accent
colors total (gold, coral, teal, sage, blush). Used gold as the primary interactive
accent (buttons, active tabs, segmented controls).

Files: `agent-dashboard/design/ui-concept-v3.html`

### [Reconstructed] 2026-04-02 23:30:00 — Dashboard: wireframe v4 (Warm Dark palette — current)

Replaced Vintage Teal with a new palette derived from Happy Hues 8 + 9. Shifted
from cool ocean-teal undertones to warm purple-brown base (`base: 950:'#141018'`).
Split accent role: teal (`#078080`) for primary actions, orange (`#ff8e3c`) for
secondary/active states. Expanded agent color palette from 5 to 10 (teal, coral,
orange, sage, lavender, gold, rose, sky + magenta, blush) — sufficient for 8
distinguishable agents. Added a Color Palette Reference section at the bottom of
the wireframe as a design token spec for implementation handoff. Changed border
weight from 1px to 2px throughout. Reduced border-radius from rounded-full to 4px
on most surfaces. Version tag bumped to v0.4.

Files: `agent-dashboard/design/ui-concept-v4.html`

### [Reconstructed] 2026-04-03 08:00:00 — Architecture pivot: SDK replaces terminal embedding

Spike test proved that `claude -p --output-format stream-json` returns typed SDK
events (AssistantMessage, tool_use, text, thinking, result). This eliminates the
need for xterm.js + ttyd terminal embedding — the riskiest technical dependency
(WSL2 port forwarding for WebSocket). New architecture:

```
Electron → React → FastAPI sidecar → Python Agent SDK → Claude CLI (stream-json)
                                           ↕
                                    tmux (crash recovery only)
```

Tmux shifts from "the thing we embed in the UI" to "the safety net underneath."
Multi-agent handoff document created for coordinating between agents working on
sidecar vs frontend.

Files: `docs/testing/sdk-stream-spike-findings.md`,
`docs/testing/architecture-decision-handoff.md`

### [Reconstructed] 2026-04-03 11:00:00 — Sidecar built (FastAPI + Python Agent SDK)

`sidecar/main.py` (v0.2): FastAPI server on port 7690 wrapping `ClaudeSDKClient`.
Endpoints: session CRUD, prompt send (background async), event history, SSE stream,
interrupt. Multi-turn sessions via persistent Claude subprocess per session.
Concurrent sessions confirmed working (2 sessions, independent prompts).

Files: `agent-dashboard/sidecar/main.py`

### [Reconstructed] 2026-04-03 14:00:00 — Electron + React frontend scaffold

Electron app via electron-vite with React renderer. Single-file `App.tsx` (~530
lines) implementing: session list (left panel), event feed with typed renderers
(tool calls, text, thinking, results, rate limits), prompt composer with send/stop,
auto-scroll with "New events" pill, sidecar health check polling. Uses Vintage Teal
color constants (not yet updated to v4 Warm Dark palette). `start-dashboard.bat`
launches sidecar then frontend.

Files: `agent-dashboard/frontend/src/renderer/App.tsx`,
`agent-dashboard/frontend/src/main/index.ts`, `agent-dashboard/start-dashboard.bat`

### [Reconstructed] 2026-04-03 16:30:00 — Pipeline proof: E2E working

End-to-end validation: sidecar + SDK + React event rendering. Multi-tool tasks
(bash + text response) produced 17 events through the full pipeline. Concurrent
sessions, cost tracking ($0.13–0.23 per query), permission auto-approve — all
working. This is the last confirmed working state of the implementation.

Files: `docs/testing/pipeline-proof-results.md`

### [Reconstructed] 2026-04-03 18:30:00 — Design system + component specs written

Extracted design tokens from the Vintage Teal wireframe into a standalone spec.
Event feed component spec written with detailed rendering rules per SDK event type.

**Note:** These specs reference the Vintage Teal palette (`sea-*`, `cream-*`,
`teal: #68b8c8`, `gold: #e8b058`). The v4 wireframe uses a different palette
(`base-*`, `warm-*`, `teal: #078080`, `orange: #ff8e3c`). These specs need
updating before implementation resumes.

Files: `docs/testing/design-system-spec.md`, `docs/testing/event-feed-component-spec.md`

### [Reconstructed] 2026-04-19 12:00:00 — Dashboard files moved to awl-dashboard/testing/

All design and spec files moved from `ui/` to `awl-dashboard/testing/`. The palette
options tool, wireframes, plan specs, and design-tools.js were moved together.

### [Reconstructed] 2026-06-13 04:43:00 — Files reorganized to agent-dashboard/design/

Directory restructure: `awl-dashboard/testing/` → `agent-dashboard/design/`.
`ui-plan-v1.md` moved to `agent-dashboard/archive/`. Frontend scaffold and sidecar
retained at `agent-dashboard/frontend/` and `agent-dashboard/sidecar/`.

### 2026-06-13 07:50:00 — Dev log created and expanded to repo scope

Initially created as `agent-dashboard/CHANGELOG.md` covering only dashboard design.
Expanded to repo root as `DEVLOG.md` covering the full platform: bridges, backend,
dashboard, and infrastructure. Reconstructed history from chat transcripts, git
commits, design artifacts, research docs, and the session brief.

Files: `DEVLOG.md`

### 2026-06-13 08:05:00 — awl-claude-http-bridge phased out

Retired the HTTP bridge — a VS Code extension (`awl-claude-http-bridge`) that ran an
HTTP server on port 7483 inside VS Code. Endpoints: POST /create, POST /send,
POST /focus, GET /list, POST /close, GET /health. Could create and send to VS Code
terminal tabs but could not read output back (fire-and-forget only). Fully superseded
by the tmux bridge which supports bidirectional communication. Test code moved to
`archive/awl-claude-http-bridge-tests/`. Section removed from CLAUDE.md.

Files: `archive/awl-claude-http-bridge-tests/` (moved from `tools/testing/awl-claude-http-bridge/`),
`CLAUDE.md`

### 2026-06-13 09:48:00 — Archived completed testing artifacts from docs/testing/

Moved 8 files out of `docs/testing/` into categorized archive subdirectories.
These were one-time setup validations, spike scripts, and raw spike output whose
findings had already been captured in the synthesis docs that remain.

- `archive/wsl2-setup/` ← WSL2 + tmux environment check and Ubuntu setup results
  (Mar 31 — one-time setup, confirmed working, bridge existence proves environment)
- `archive/sdk-spikes/` ← spike1/spike2/spike2b Python scripts and raw results
  (Apr 3–4 — SDK stream capture and permission handling tests, findings rolled into
  `sdk-stream-spike-findings.md`)
- `archive/system-audits/` ← `cc-system-audit-report.md`
  (Mar 31 — initial Claude Code install audit, findings acted on)

Remaining in `docs/testing/` (5 files, all active reference for dashboard work):
`architecture-decision-handoff.md`, `design-system-spec.md`,
`event-feed-component-spec.md`, `pipeline-proof-results.md`,
`sdk-stream-spike-findings.md`

### 2026-06-13 09:50:00 — Dashboard wireframe v6 (palette + radius refinement)

Reviewed the prior-session v5 wireframe (which switched v4's Warm Dark palette to
Happy Hues 17 — cream/navy/pink — added pill/rounded styling, and introduced a
dedicated 12-color `agent.*` identity namespace). Judged v5 serviceable and kept it
as the base rather than rebuilding.

Created `ui-concept-v6.html` from v5 with three requested changes:
- **Corner radius reverted to v4 (4px / rounded-md) for all surfaces, buttons,
  inputs, segmented controls, swatches, and chips** — EXCEPT textareas (kept
  `rounded-xl`) and the Team Graph agent cards (kept `rounded-2xl`).
- **Color Palette Reference section** redesigned: deep-navy (#0e1840) background to
  clearly separate it from the live UI, light text, and a label-column + auto-fill
  chip grid layout instead of ragged flex-wrap.
- **Polish:** active segmented-control state changed from a faint pink tint to solid
  pink with navy text (legibility); idle status dot darkened with a subtle ring;
  CLI inline code-highlight radius brought in line with the sharper system.

Verified rendered output via Playwright (layout, tabs, radii, palette panel all
correct; only console noise is a favicon 404). Layout and functionality unchanged
from v4/v5.

Files: `agent-dashboard/design/ui-concept-v6.html` (new)

### 2026-06-13 09:58:00 — Standardized scratch location for transient agent artifacts

Agents were dumping temp files (screenshots like `review-v6-full.png`, `v5-*.png`)
into the repo root. Root cause: Playwright's auto-artifacts already self-contain in
the gitignored `.playwright-mcp/`, but explicitly-named files (screenshots with a
`filename`, Bash output) get written to cwd = repo root. This is governed by agent
behavior, so the fix is a convention + a rule.

- Created top-level `.scratch/` as the single home for transient artifacts, with a
  tracked `.gitkeep` (folder discoverable, contents ignored via `.scratch/*` +
  `!.scratch/.gitkeep`).
- Added a Behavioral rule to `CLAUDE.md`: transient artifacts go in `.scratch/`, never
  the repo root; prefix screenshot/export `filename`s with `.scratch/`.
- `.gitignore`: replaced the stale `scratch/tmp/` line (folder never existed) with the
  `.scratch/` rule.
- Cleared 9 disposable review PNGs from root.

Considered but skipped: pointing Playwright `--output-dir` at `.scratch/` — low value
(`.playwright-mcp/` already gitignored/self-contained) and it would touch global MCP
config in `~/.claude.json`.

Files: `.scratch/.gitkeep` (new), `CLAUDE.md`, `.gitignore`

### 2026-06-13 12:03:00 — Dashboard wireframe v7 (toggles, tints, palette layout)

Created `ui-concept-v7.html` from v6 with a batch of user-requested refinements:
- **Team Feed tabs:** "Out"/"In" → "Outgoing"/"Incoming".
- **Agent toggles:** rebuilt the agent-chip groups as real toggles showing icon +
  two-line label (role / "01 name"). Multi-select = spaced chips with a checkbox
  affordance (`.atog`); single-select = grouped/segmented row (`.atog-grouped`).
  Applied to: Activity Log (multi, agent filter), Compose Target (multi), Compose
  Source (single — converted from a dropdown, now includes a "User" option with a new
  `icon-user` glyph), Prompts History (single — "History for" header removed).
- **Layout:** removed the Team Feed footer-strip; the Activity Log toggles now sit
  inline beneath the log text, blended into the panel (no separate footer surface),
  mirroring how Compose's "Target" sits under the textarea.
- **Agent cards:** Team Graph card borders recolored to each agent's identity color.
- **Color picker:** shows all 12 agent colors (Details + Create), accordion removed.
- **Textareas:** sharper `rounded` radius + a `field` (#fdf1e6) bg tint to distinguish
  editable multiline from white dropdowns and terminal fields.
- **Terminal/stream surfaces:** CLI, Activity Log, and the Outgoing/Incoming/Scratch
  feeds got a subtle `term` (#ebedf3) cool tint to read as console (Pending kept as a
  cream action surface). Added `field` + `term` swatches to the palette reference.
- **Palette reference:** widened content area (max-width 1400, more columns) so it
  occupies less vertical height.

Verified rendered output via Playwright (tabs, toggle states, tints, recolored card
borders, full 12-color picker, palette layout all correct; only console noise is a
favicon 404). Layout/functionality otherwise unchanged from v6.

Files: `agent-dashboard/design/ui-concept-v7.html` (new)

### 2026-06-13 10:15:00 — Standardized testing on pytest; fixed tmux-bridge `mcp_sync`

Reorganized workspace testing and adopted pytest as the standard. Also fixed one real
tmux-bridge bug and disproved a second suspected one.

- **New `tests/` at repo root** (replaces `tools/testing/`). Holds the relocated tmux-bridge
  suite, a `conftest.py` (session-scoped `bridge` / `live_session` fixtures + per-run log
  setup), `run.ps1` (resolves the shared venv), `README.md`, and a gitignored `log/`.
- **Converted `test_tmux_bridge.py` to pytest** — same coverage (27 tests), now with markers
  (`integration`, `slow`) and DEBUG logging to timestamped files in `tests/log/`.
- **pytest config** added to `pyproject.toml` (new); `pytest` added to `requirements.txt`;
  `**/tests/log/*` and `.pytest_cache/` gitignored. CLAUDE.md gained a **Testing** section
  documenting the convention + a nudge to use it for future tests.
- **`mcp_sync` WinError 206 fixed** (`~/.claude/tools/awl_claude_tmux_bridge`): `.claude.json`
  is ~39 KB, over Windows' ~32 KB command-line limit. Added a `stdin_data` param to
  `bridge._run` and rewrote the config write as `cat > file` piping JSON via stdin. Also added
  a silent-by-default DEBUG logger to `_run` for command-level traceability.
- **`wait_idle` was NOT changed.** A prior session hypothesized the idle-detection heuristic
  was stale; the captured idle screen (logged) shows `❯` still on its own line, the regex
  matches, and the test passes. The original timeout was transient (slow model response), not
  a heuristic defect. Left untouched deliberately.
- **Consistency:** renamed `projects/fb-group-search/test/` → `tests/` and updated that
  project's `.gitignore` patterns (`test/` → `tests/`).
- **Deferred:** migrating the tmux-bridge library itself into the workspace (lib still lives
  at `~/.claude/tools/`); the suite's `sys.path` still points there.

Outcome: `tests\run.ps1` → 27 passed. Baseline green before any future library migration.

Files: `tests/*` (new), `pyproject.toml` (new), `requirements.txt`, `.gitignore`, `CLAUDE.md`,
`projects/fb-group-search/.gitignore` + `test/`→`tests/` rename,
`~/.claude/tools/awl_claude_tmux_bridge/{bridge.py,mcp.py}`

### 2026-06-13 10:35:00 — Migrated `awl_claude_tmux_bridge` into the workspace

Completed the deferred library migration: the package now lives in-repo at
`tools/awl_claude_tmux_bridge/` instead of `~/.claude/tools/`. Motivation was unified version
control (co-located with its tests and consumers) and discoverability.

- **Moved** the package (source + README, no `.git`/`__pycache__`) into `tools/`, then deleted
  the old `~/.claude/tools/awl_claude_tmux_bridge`. Its standalone GitHub repo
  (`adamwlester/awl_claude_tmux_bridge`) retains the old history; the in-repo copy carries the
  steps-1–3 fixes (`mcp_sync` stdin, `_run` logging).
- **Import path** is now workspace-relative: `tests/conftest.py` adds `<repo>/tools` to
  `sys.path` via `Path(__file__)` (no hardcoded user path).
- **Updated active references:** project `CLAUDE.md` (import example + folder map + path),
  `.vscode/tasks.json` folder picker, the package's own `README.md`, the global
  `~/.claude/CLAUDE.md` Custom Tools row, and `~/.claude/docs/core-docs/data-model-reference.md`
  (dropped the now-stale `awl_claude_tmux_bridge` example under `~/.claude/tools/`).
- **Left as-is (historical):** DEVLOG past entries, `briefs/`, `agent-dashboard/archive/`,
  `cc-exports/` — they describe what was true when written.
- **Test robustness:** `test_send_and_response` now polls via `watch()` instead of a fixed
  sleep; `test_wait_idle` timeout 30s→90s. These absorb TUI/model latency that varies with
  machine load (a re-test under load — plus ~8 orphaned WSL `claude` daemons from repeated runs
  — caused transient timeouts; killing the orphans + polling resolved it). No library behavior
  changed.

Outcome: `tests\run.ps1` → 27 passed against the migrated package; import verified to resolve
only to the workspace copy (no fallback to the user dir).

Files: moved `tools/awl_claude_tmux_bridge/*`; deleted `~/.claude/tools/awl_claude_tmux_bridge`;
`tests/conftest.py`, `tests/test_tmux_bridge.py`, `CLAUDE.md`, `.vscode/tasks.json`,
`~/.claude/CLAUDE.md`, `~/.claude/docs/core-docs/data-model-reference.md`

### 2026-06-13 11:00:00 — Renamed package `awl_claude_tmux_bridge` → `cc_tmux_bridge`

Shortened the package name. Applied across active code and docs only:

- **Directory** `tools/awl_claude_tmux_bridge/` → `tools/cc_tmux_bridge/`.
- **Identifiers:** import name `awl_claude_tmux_bridge` → `cc_tmux_bridge`; CLI prog
  `awl-claude-tmux-bridge` → `cc-tmux-bridge`; module/README title "AWL Claude tmux Bridge" →
  "CC tmux Bridge"; the `_run` logger name → `cc_tmux_bridge`.
- **Files updated:** the package source (`bridge.py`, `cli.py`, `__init__.py`, `__main__.py`,
  `README.md`), `tests/conftest.py`, `tests/test_tmux_bridge.py`, `tests/README.md`, project
  `CLAUDE.md`, and global `~/.claude/CLAUDE.md`.
- **Left as-is (historical/immutable):** prior DEVLOG entries, `briefs/`,
  `agent-dashboard/archive/`, `cc-exports/`, `docs/research/`, and old `tests/log/` files —
  they record the name as it was at the time. The `awl-claude-http-bridge` VS Code extension is
  a *different* tool and was not touched.

Outcome: `tests\run.ps1` → 27 passed; `import cc_tmux_bridge` resolves to the workspace package,
logger name and CLI prog reflect the new name.

Files: renamed `tools/cc_tmux_bridge/*`; `tests/{conftest.py,test_tmux_bridge.py,README.md}`,
`CLAUDE.md`, `~/.claude/CLAUDE.md`

### 2026-06-13 12:30:00 — Dashboard v7: Activity Log toggle placement correction

Adjustment to the v7 wireframe. The earlier v7 entry placed the Activity Log agent
toggles *beneath* the log text and inside the term-tinted surface. Per user feedback,
moved them **above** the log window and onto the **normal (cream) background**, so they
mirror the Prompts History toggles (which sit above their content). The log window
itself keeps the `term` tint.

Files: `agent-dashboard/design/ui-concept-v7.html`

### 2026-06-13 13:21:00 — Dashboard wireframe v8 (per-agent Requests/approval surface)

Reconceived approvals as the GUI's human-control inbox, handled one agent at a time.
Driven by the decision that the dashboard will route *all* CLI interactions — including
permission prompts — through the GUI. Created `ui-concept-v8.html` from v7:
- **Pending moved out of the Team Feed** into a new **Requests** tab in the Agent panel
  (middle pane). Team Feed is now just Outgoing / Incoming / Scratch.
- **Requests tab** shows the selected agent's queue in three sections, grouped by
  response pattern, each a `.card` with a left accent stripe:
  - **Permissions** (gold) — requested action in mono → Allow / Always / Deny
  - **Approvals** (pink) — plan/handoff title + preview + Expand → Approve / Edit / Reject
  - **Decisions** (cobalt) — question + single-select option toggles → Submit / Reply
- **Team Graph radar:** removed the per-card "+" link box (linking will be multi-select
  + the "Link Agents" button) and replaced it with a **gold pending-count badge** in that
  corner (researcher 3, auditor 1, synthesizer none). Same count badges the Requests tab.
- **Footer** pending count is now a clickable amber "4 pending →" (jump-to-next affordance).
- Palette reference: relabeled gold as "permission / pending".

Reused existing `.card`, `.btn-*`, `.atog-grouped`/`pickSeg`, `switchTab`, palette tokens
(no new CSS beyond a small section-header rule). Verified via Playwright: graph badges,
3-tab feed, Requests tab + three typed sections with correct buttons, decision toggles,
"4 pending" footer; console clean except favicon 404. Note: researcher is still shown
"Working" while holding queued requests — badge = items awaiting you, independent of run
state (illustration choice, flagged to user).

Files: `agent-dashboard/design/ui-concept-v8.html` (new)

### 2026-06-13 13:30:00 — Dashboard wireframes renamed to point-release scheme

v5 onward are all tweaks to the same basic version (the Happy Hues 17 redesign), so they
were renamed to a point-release scheme. v4 (the prior Warm Dark version) is unchanged.
Earlier log entries reference the old names — they record the name as it was at the time.

  - `ui-concept-v5.html` → `ui-concept-v5p1.html`
  - `ui-concept-v6.html` → `ui-concept-v5p2.html`
  - `ui-concept-v7.html` → `ui-concept-v5p3.html`
  - `ui-concept-v8.html` → `ui-concept-v5p4.html`  (latest)

Internal title-bar version badges (v0.5–v0.8) were left as-is. Updated the one external
reference in `prompts/dashboard-v8-change-instructions.md`.

Files: renamed `agent-dashboard/design/ui-concept-v{5,6,7,8}.html`;
`prompts/dashboard-v8-change-instructions.md`

### [Reconstructed] 2026-06-13 15:23:00 — Dashboard wireframes v5p5–v5p6

Continued the v5p4 session, implementing its punch-list (then
`prompts/dashboard-v8-change-instructions.md`, since renamed to
`dashboard-v6-change-instructions.md`). Built across v5p5 → v5p6:
- **Session field** added as the first field in the Agent panel's Details and Create tabs;
  the CLI panel is now titled by the session name.
- **Model** selector made editable (dropped the "(locked)" framing).
- **Activity Log folded into the Team Feed** as a final **Log** tab
  (Outgoing | Incoming | Scratch | Log); its per-agent filtering moved to the feed's shared
  toggle set.
- **Shared, persistent sub-headers:** one multi-select agent-toggle set across all Team Feed
  tabs, and a shared Source (single-select) + Target (multi-select) set across all Prompts
  tabs — both with a **Select all** affordance on the multi-select groups.
- **Selection linkage:** a graph card now reads as selected and drives the Agent panel + CLI.
- **Restored the Link Agents → Link Config drawer**; **Decisions** options stacked vertically.

[Reconstructed from git history (commit `11d91b7`, 15:53), file mtimes, and the
v6-change-instructions punch-list — these point releases were not logged at the time.]

Files: `agent-dashboard/design/ui-concept-v5p5.html`, `ui-concept-v5p6.html` (new)

### [Reconstructed] 2026-06-13 16:58:00 — Dashboard wireframes v5p7–v5p9 + archive reorg

A second UI session refined the concept across v5p7 → v5p8 → v5p9 (current latest), pushing
the navy palette further and aligning the Link Config trigger vocabulary to
**Now · Next · Queue · Hold**. Also moved old concept versions (v1–v5p8) and superseded docs
into `archive/agent-dashboard/`, added the session exports under `cc-exports/`, and wrote
`prompts/dashboard-readme-prompt.md`.

Captured a **pending** punch-list as `prompts/dashboard-v5-change-instructions.md` — Compose
Clean/timing action row; Link Config direction toggle + Message/Transcript/Manual payload +
multi-select End-After; per-card Reply field; Rewind accordion; per-tab footers
(Handoff/Retire); navy scrollbars. These are **not yet built** in v5p9 — they are the next step.

[Reconstructed from git history (commits `8d3a558` 17:54, `3ef641d` 18:17) and file mtimes —
not logged at the time.]

Files: `agent-dashboard/design/ui-concept-v5p9.html` (new, current);
`archive/agent-dashboard/ui-concept-v5p7.html`, `ui-concept-v5p8.html`;
`prompts/dashboard-v5-change-instructions.md` (new)

### 2026-06-13 18:30:00 — DEVLOG timestamps backfilled; missing dashboard entries added

The log had stalled at v5p4 while the design had advanced to v5p9 — agents stopped appending
entries (this is why a downstream prompt wrongly believed v5p4 was newest). Fixed and hardened
the convention:
- Converted every entry heading to `YYYY-MM-DD HH:MM:SS`; backfilled approximate times for the
  reconstructed/older entries from git history and file mtimes.
- Added the previously-unlogged v5p5–v5p9 dashboard sessions (the two entries above).
- Rewrote the **Log** header rule to mandate seconds-precision timestamps and appending an entry
  on completion of each unit of work, so the log can't silently fall behind again.
- Refreshed the **Status** block to v5p9.

Files: `DEVLOG.md`

### 2026-06-13 19:45:00 — Dashboard wireframe v6p1 (pending punch-list applied)

Built `ui-concept-v6p1.html` from v5p9, implementing the punch-list captured in
`prompts/dashboard-v6-change-instructions.md` (the work the v5p7–v5p9 note flagged as
"not yet built"). All changes are visual/structural on the static Happy Hues 17 mockup;
no backend. Verified each state in a headless browser (Playwright) — console clean except
the benign favicon 404.

- **Prompts — shared action row.** Replaced the per-tab `Send · Clear · Queue` buttons with
  one row shared across Compose & Library (History keeps per-item Reuse), pinned as a Prompts
  footer: **Clean** (outline) → **Now · Next · Queue** `.seg-ctrl` (Now default) → **Send**
  (primary, label mirrors timing: Send Now / Send Next / Send to Queue) → right-grouped
  **copy + trash** icon buttons. New `pickTiming()` syncs the Send label; `switchTab` now
  hides the row on History.
- **Prompts — Target.** Added **Scratch** as the first Target chip (amber note icon, posts to
  the shared scratchpad).
- **Team Feed.** Added a **User** filter chip at the front of the shared filter group (mirrors
  the Source User option). Rewrote **Scratch** into five multi-agent posts, each with agent ID +
  **HH:MM:SS**. Lengthened **Log** to 14 entries and switched it to **HH:MM:SS**.
- **Link Config drawer.** Arrow between agents is now a 3-state direction toggle
  (**A→B / B→A / A↔B**, `cycleDir`); both agents use the two-row role-over-name identity;
  Trigger renamed **Imm→Now / Held→Hold** (Now · Next · Queue · Hold); Payload is now
  **Message · Transcript · Manual**; removed **1-Shot**; **End After** rebuilt as three
  equal-width columns of multi-select toggle + paired input (greyed until its toggle is on;
  no toggles = no limit; placeholders 50 / 30m / 100k; `toggleLimit`).
- **Agent panel.** Request subheading counts moved into a leading **badge** (navy on gold/pink,
  white on cobalt for contrast) instead of a trailing label; agent-card pending badges already
  rendered navy-on-gold (`text-warm-50`) and were left intact. Added **Reply** to Permissions &
  Approvals cards (Decisions already had it); all Reply buttons enable a shared **Reply field**
  in the new **Requests-tab footer** (distinct surface, embedded send icon — option (a)).
  **Rollback → Rewind**: removed from the footer, placed as an accordion just under Context in
  Details that expands a scrollable, selectable list of messages sent to the model. Split the
  one shared footer into **per-tab footers** — Details: **Handoff** (replaces Clone) + **Retire**;
  Create: **Create · Reset · Cancel** (Cancel danger); Requests: the shared Reply field
  (`switchTab` swaps `data-group="mid-foot"` footers).
- **Scrollbars.** Recolored app-wide to the palette (cream `#f0e8d8` track, navy-grey `#8a8eb8`
  thumb, pink `#f582ae` hover; Firefox `scrollbar-color`), with a navy-toned variant for the
  dark Palette Reference panel.
- Title-bar badge bumped **v5.9 → v6.1**. Added four SVG symbols (copy, trash, send, note).

Files: `agent-dashboard/design/ui-concept-v6p1.html` (new)

### 2026-06-13 19:21:22 — ui-plan-draft.md archived as ui-plan-v2.md

Moved `agent-dashboard/design/ui-plan-draft.md` → `archive/agent-dashboard/ui-plan-v2.md`
(move + rename). The "draft" name was misleading: by mtime (2026-04-02, two days after
`ui-plan-v1.md`'s 2026-03-31) and content — it describes the desktop-GUI/Electron direction
that the current `ui-concept-v5pN.html` mockups follow, superseding v1's abandoned
in-terminal TUI spec — it is actually the *newer* of the two vision specs. Renaming to `v2`
makes the chronology explicit so it isn't mistaken for a preliminary draft. (Working-tree
change; `ui-plan-draft.md` was untracked at the archive path.)

Files: `archive/agent-dashboard/ui-plan-v2.md` (was `agent-dashboard/design/ui-plan-draft.md`)

### 2026-06-13 20:12:14 — Dashboard design reference written (agent-dashboard/README.md)

Authored `agent-dashboard/README.md` as the ground-truth reference for the dashboard's **UI/UX
intent** (per `prompts/dashboard-readme-prompt.md`). Focus is durable *why*, not pixels — the
mockup keeps ownership of exact visuals; the README centralizes the few specifics (palette tokens)
in one design-system section and minimizes cross-references so it survives future mockup revisions.

Sources synthesized, newest-wins: the current mockup (`ui-concept-v6p1.html`) for *what*; this
DEVLOG for chronology; the `cc-exports/` session transcripts as the primary source for *rationale*
(esp. reversals); and `archive/agent-dashboard/ui-plan-v2.md` + the early brief for foundational
vision. Structure: purpose/vision → platform → 3-pane layout → per-panel (Team Graph, Team Feed,
Agent[Details/Create/Requests], CLI, Prompts) → cross-cutting concepts (identity & naming, linking
& context-sharing, scratchpad, lifecycle/autonomy) → design system → open questions.

Captured key intent from transcripts: approvals routed through the GUI as a per-agent Requests
inbox (Permissions/Approvals/Decisions); links as the defining context-sharing feature
(direction/Trigger/Payload/End-After, Payload = Message/Transcript/Manual); compose-first; one
color+icon identity per agent; Model unlocked (changeable mid-run); per-field pencil/save edit
model in Details; scratchpad as an attributed living doc. Flagged 8 interpretation-uncertainty
questions for the user (separate from the README's own reader-facing "Open questions" section).

Files: `agent-dashboard/README.md` (new)

### 2026-06-13 20:40:00 — Dashboard wireframe v6p2 (split-button send/revise, rewind+fork, badge/colour fixes)

Built `ui-concept-v6p2.html` from v6p1 in response to a round of user feedback. Two of the
changes were guided by reference HTML the user supplied in `.scratch/`
(`inline_timing_chip_visible_fix.html`, `rewind_handoff_dropdown.html`), re-skinned to our
palette. Verified all states in a headless browser (Playwright); console clean except the
favicon 404.

- **Prompts action row — split buttons.** Replaced the `Send` + inline `Now·Next·Queue`
  segmented control with a **split button**: a primary **Send** action joined to a timing
  **chip** (`Now ▾`) that opens an upward dropdown (header *Deliver*; Now/Next/Queue with
  helper sub-text). The chip — not the main label — now carries the timing. **Clean → Revise**,
  also a split button with a **Minimal · Medium · Maximum** strength dropdown (default Medium).
  New `toggleSplitMenu()` / `pickSplit()`; menus close on outside-click/Escape; the Revise menu
  left-aligns, Send right-aligns, so neither clips. Layout is now **Revise … (spacer) … Send**,
  with the **copy/trash demoted to small stacked ghost icons** trailing Send (kept inline rather
  than overlaid, per the user's simpler option).
- **Rewind → Timeline (Rewind + Fork).** Replaced the single-select Rewind accordion with a
  **Timeline** section (renamed from the reference's "Session") exposing two actions, **Rewind**
  (undo icon) and **Fork** (git-branch icon). Either opens the same point list; only the panel
  title and each row's hover **pick** verb change (*Rewind here* / *Fork here*), with a success
  confirmation line. New `openRewind()/closeRewind()/pickRewindPoint()` + `RW_CFG`.
- **Request sections recoloured + legible badge.** Dropped the gold/pink/**cobalt** colour-coding
  for a conservative warm ramp by importance — **Permissions `#d75a4f` → Approvals `#cf8136` →
  Decisions `#b9791f`** (reddish → copper). The count badge is now a **cream pill with a constant
  navy number**, differentiated only by a **colored ring** in the section tone — so the number
  is legible on every section without per-section text colours. Decision-option selected state
  re-pointed from the lone cobalt to the app's standard **pink** selection accent.
- **Scratch Target chip** icon recoloured from amber to the neutral **navy** of the Human/User
  icon. Title badge **v6.1 → v6.2**. Added three SVG symbols (chevron-down, rewind, fork).

Note: this supersedes the README's description of Send ("one primary action whose label mirrors
the timing") and the gold/pink/cobalt Requests coding — left the README as-is for now; worth a
sync pass when the open design questions are resolved.

Files: `agent-dashboard/design/ui-concept-v6p2.html` (new)

### 2026-06-13 23:53:33 — README synced to v6p2 + v6p3 intent; user answers folded in

Updated `agent-dashboard/README.md` after the user resolved the 8 interpretation questions and
pointed at the newer mockup (`ui-concept-v6p2.html`) plus the not-yet-built "v6p3" punch-list
(TURN 3 of `cc-exports/claude-2026-06-14-review-dashboard-v6-change-instructions.md`). Per the
user's instruction, the README describes the design *assuming the v6p3 set lands*, flagging such
spots *(planned)*.

Folded in the answers: (1) kept it intent-focused but added a short "What it physically is"
orientation; (2) CLI is a read-through view of the agent's real terminal — input only via
Prompts/links; (3) directed link **edges** documented as the intended graph representation
(planned); (4) Payload **Transcript** = the agent's full conversation, export-style (source TBD);
(5) scratchpad post→read now, per-post comment deferred; (6) **Handoff** = branch the agent's
context into a new agent via the Create tab, now living on the **Timeline** alongside **Rewind**
(replaces Clone/Fork; Details footer = Retire only); (7) sender+trigger metadata hidden by the UI
and rendered as colored heading + trigger badge + body ("one message, two presentations");
(8) per-agent **Lifecycle** vs per-link **End After** kept as explicitly distinct scopes.

Also reworked per v6p2/v6p3: Prompts **split buttons** (Send+timing chip, Revise+strength;
copy/clear ghost icons in the field; Compose=Revise+Send, Library=Send-only); Library **template
pill** fill-in flow; Requests reddish→copper importance ramp with legible filled count badges and
an in-content Reply field. Restructured the ending into distinct **Open questions** (undecided) and
**Future directions** (decided-but-deferred, every item tagged not-built). Design-system section
updated (split buttons, requests ramp, inline clear-X; dropped gold "permission" accent).

Files: `agent-dashboard/README.md`

### 2026-06-14 02:55:00 — Dashboard wireframe v6p3 (badges, split-button refinements, Library pill flow)

Built `ui-concept-v6p3.html` from v6p2, implementing the punch-list the README had already
described as *(planned)*. Verified every state in a headless browser (Playwright); console clean
except the favicon 404.

- **Count badges (all three placements).** Made them filled + larger + light text. Graph-card and
  Requests-tab pending badges: bigger gold pill, **white numeral**, navy border (frames the light
  number). Requests **group** badges: a **neutral navy filled pill, right-justified** after the
  label (light text) — section identity now rides the card's left stripe only. **Widened the three
  stripe colours** into a broader importance ramp: Permissions `#d0463c` → Approvals `#d08530` →
  Decisions `#9c6a1c` (reddish → copper).
- **Prompts action row.** Split buttons reproportioned so the **dropdown chip is wider than the
  action** (flex 3:2, fixed split widths). The pink **Send** split now carries the **same navy
  outline** as Revise (pure fill buttons elsewhere untouched). **Copy/clear moved off the footer
  into the Compose textarea** (top-right ghost cluster, clear of the scrollbar + resize handle).
  **Footer scope:** Compose shows Revise + Send; **Library shows Send only** (Revise hidden via
  `switchTab`).
- **Agent panel.** Details footer is now **Retire only**. **Rewind + Handoff** render as subtle
  width-spanning **tabs** (the "Timeline" heading dropped); both open the same point list, verb +
  header swap (`RW_CFG`, Fork→**Handoff**). **Requests has no footer** — the **Reply field moved
  in-content** below the three groups: multiline, in-field copy/clear, **Send aligned outside at
  bottom-right**. Sized the Details/Create footers (`px-2 py-2.5`) so their **top border aligns**
  with the Prompts footer (both at the same y).
- **Global.** Editable single-line text inputs got an inline **clear "X"** (Details Name, Details
  Skills, Create Name); readonly No. and disabled/numeric limit fields excluded as a clear has no
  meaning there.
- **Library redesign.** Scrollable file list; a **template view** (textarea-styled div) whose
  placeholders are **clickable colored pills showing the bare tag**; clicking a pill targets the
  **fill input** below (auto-growing, tinted to the tag, no label); its **insert icon** writes the
  typed value back into the pill (stays a re-selectable, now-**filled** pill), with a clear-X too.
  Seeded with five tags — two filled (`src/auth`, `high`), three empty — and a selected pill.
- Title badge **v6.2 → v6.3**. Added three SVG symbols (clear-x, insert/upload; Handoff reuses the
  branch glyph).

Interpretation calls worth confirming: light-on-gold count badges (legible via the navy frame, but
white-on-gold is low-contrast by the numbers); clear-X scoped to editable text inputs only; copy/
clear kept inline-in-textarea (top-right) rather than a true overlay; Library kept as a static
demo of the fill cycle.

Files: `agent-dashboard/design/ui-concept-v6p3.html` (new)

### 2026-06-14 03:08:00 — Correction: v6p3 added two SVG symbols, not three

The v6p3 entry above says "Added three SVG symbols." It added **two** — `icon-x` (clear) and
`icon-insert` (upload/insert). There is no third: the **Handoff** Timeline tab reuses the existing
`icon-fork` (git-branch) glyph. No code change; the file is correct — only the count in the prior
note was wrong.

Files: none

### 2026-06-13 19:59:00 — Authoring prompts reworked (readme-prompt + v6 change-instructions)

[Logged after the fact — appended out of order; this prompt-editing work predates the v6p1/README
entries above (file mtimes ~19:14–19:59). No code or mockup changes.]

- `prompts/dashboard-readme-prompt.md`: fixed the vision-spec reference (`ui-plan-v2.md` is the GUI
  spec and the *intent* source; the abandoned-TUI caveat now points at `ui-plan-v1.md`); de-localized
  the mockup target to "highest-numbered `ui-concept-*.html`" so it can't go stale; promoted the
  `cc-exports/` transcripts to the **primary source for UX intent** with explicit loose-inference
  license; added maintainability rules (one source of truth, mockup owns pixels, centralize tokens in
  the design-system section, minimize cross-references); and added two deliverable instructions —
  flag uncertainties as numbered, lettered, ★-defaulted questions, and end with a
  "Future Directions (not built)" section.
- `prompts/dashboard-v6-change-instructions.md`: reframed the Requests **Reply** layout as an open
  (a/b) decision, trimmed the **Scrollbars** item to essentials, and set the output target to `v6p1`.

Files: `prompts/dashboard-readme-prompt.md`, `prompts/dashboard-v6-change-instructions.md`

### 2026-06-14 04:08:51 — CLAUDE.md: added Key files section; accuracy pass

Added a **Key files** section to the project `CLAUDE.md` (right after Folder map) so every session
is aware of the two cross-cutting docs, and folded the old standalone **Project log** section into
it. Entries: `DEVLOG.md` (append-only log; read first, log significant changes) and the new
`agent-dashboard/README.md` (dashboard UI/UX design reference). Accuracy pass on the rest:
added the missing `claude-code-sandbox-env/` (shared venv) row to the Folder map, and noted the
workspace's current primary focus (the multi-agent dashboard) in the identity blurb. Verified the
Folder map (`tools/bootstrap-env.ps1`, both `projects/` subdirs, `docs/temp/` all present), the
cc_tmux_bridge section, Testing, and Behavioral rules are still accurate — no other changes.

Files: `CLAUDE.md`

### 2026-06-14 15:03:00 — v7p1 reboot package finalized; crashed-build artifacts consolidated

Prepared the handoff package for a fresh Claude Desktop session to retry the v7p1 dashboard
redesign (two prior Desktop attempts crashed mid-write at ~93,754 chars). No dashboard code/design
changed — this is handoff curation + file hygiene.

- **New `briefs/ui-rockstar-reboot/design-decisions-rationale.md`** — synthesizes the *why* behind
  v7p1 from the `cc-exports/` transcripts, this DEVLOG, and `agent-dashboard/README.md`: the human's
  priorities, the taste profile, settled decisions + rationale, the recurring friction points
  (§A rounding, badge legibility, the write ceiling), and working-style calibration.
- **Curated `transcript-thinking.md`** — recut the prior session's thinking transcript from ~83k to
  ~38k tokens by keeping the design exploration (msgs 0–9) and build-approach (msgs 38–43) in full
  while condensing the Claude-Desktop tooling/plumbing saga (msgs 10–41) to a single note. Full raw
  transcript remains at `projects/claude-context-extractor/out/2026-06-14-UI-Rockstar-RETRY-1050/`.
- **Consolidated all 8 scattered v7p1 crash artifacts.** Moved the active-dir trap
  (`agent-dashboard/design/ui-concept-v7p1.html`, the empty 2.4k skeleton) and the partial
  (`...-recovered.html`) plus the malformed JSON-blob from `archive/` root into a single labeled
  `archive/agent-dashboard/v7p1-crash-legacy/` (with a README); deleted the `_temp` blob duplicate
  and two disposable `.scratch/` copies. The `ui-concept-v7p1.html` output path is now free so the
  retry copies v6p3 cleanly. Clean reference copies of the partial/skeleton remain in the package's
  `recovered-examples/`.
- **Updated `HANDOFF.md`** (rationale doc added as first read; curated-transcript + loose-reference
  framing; brief reaffirmed as the focal point) and the **brief's preface** in
  `prompts/dashboard-v7-change-instructions.md` (repointed from the moved `-recovered.html` to the
  reboot package; spec body untouched).

Files: `briefs/ui-rockstar-reboot/{design-decisions-rationale.md (new),transcript-thinking.md,HANDOFF.md}`;
`archive/agent-dashboard/v7p1-crash-legacy/{crashed-skeleton.html,crashed-partial.html,raw-jsonwrapped-blob.html,README.md (new)}`
(moved/new); `prompts/dashboard-v7-change-instructions.md` (preface only); deleted
`archive/ui-concept-v7p1-partial_temp.html`, `.scratch/v7p1-partial-recovered*.html`

### 2026-06-14 15:25:00 — v7p1 brief: folded in six late requirements

Worked the user's final feature/guideline additions into `prompts/dashboard-v7-change-instructions.md`
(spec only; no mockup change):
- **How to ask questions:** added an answer-ergonomics rule — present clarifying questions in one
  copyable/fenced block and anchor each to the brief section/element it concerns.
- **§A:** added a placement-discretion clause — position/layout of recurring controls (clear/copy
  buttons, toggles and groups, even the §F agent toggle strips) is a default, not a mandate; the
  model may improve it per UX/standards, then keep each control type self-consistent.
- **§C.6 (new):** noted dissatisfaction with the Compose copy/clear(trash) cluster placement; invite
  a cleaner home (inside or outside the textarea) as the reference treatment wherever it recurs.
- **§D rewritten:** merged Outgoing + Incoming into one **Messages** tab driven by Out/In show-hide
  toggles (feed = Messages · Scratch · Log); added content-include toggles (Thinking/Read/Write/Bash/
  Edit-diffs/Session-metadata, chat-export convention, direction toggles first + visually separated);
  kept the Raw/Formatted Format control; tabs stay stacked cards. Supersedes the README's 4-tab feed.
- **§I (new) — Demo data & realism:** flesh out all example data (full feature surface, 15–20 agent
  icons/colors, ≥12 agents + several subagents, long-form feeds/textareas overflowing the viewport)
  to stress-test scroll/resize/packed controls; per-section counts are floors. Bumped "settled
  decisions" range to B–I.

Files: `prompts/dashboard-v7-change-instructions.md`

### 2026-06-14 15:59:00 — Moved the v7p1 reboot package `briefs/` → `prompts/`

Relocated `briefs/ui-rockstar-reboot/` → `prompts/ui-rockstar-reboot/` so the handoff package sits
beside the brief it supports (`prompts/dashboard-v7-change-instructions.md`); `briefs/` reads as
agent session-summaries and `docs/` as durable reference, whereas this is task-specific instruction
material. The package's internal cross-references are relative and were unaffected. Updated the two
live external references: the brief's preface pointer and the legacy folder's README. Prior DEVLOG
entries (above) and the `cc-exports/` transcripts still cite the old `briefs/...` path — left as-is
(append-only log + immutable exports); this entry records the new location.

Files: moved `prompts/ui-rockstar-reboot/*` (was `briefs/ui-rockstar-reboot/*`);
`prompts/dashboard-v7-change-instructions.md` (preface pointer),
`archive/agent-dashboard/v7p1-crash-legacy/README.md` (pointer)

### 2026-06-17 19:28:00 — Dashboard wireframe v7p2 (cleanup of the v7p1 build)

Created `agent-dashboard/design/ui-concept-v7p2.html` from the v7p1 desktop-build (171 KB) and
applied a round of conceptual cleanup. v7p1 untouched. Verified every change in a headless browser
(isolated copy on a private port); console clean (0 errors over http).

- **Removed the CLI panel** (upper-right) — its role is now covered by Team Feed; the concept had
  drifted. **Swapped Prompts ⇄ Team Feed:** Team Feed is now the full-height rightmost panel;
  Prompts moved under Team Graph in the left column. Wrapped header+three-pane+footer in a new
  `.app` (100vh) frame so the palette reference can sit outside/below it.
- **Removed** the Team Feed Raw/Formatted dropdown; the Team Graph link-edge arrows (the
  `edge-layer` SVG — `drawEdges` now no-ops; arrows to be reintroduced later); and the model
  dropdown's "<model> versions" helper header.
- **Added back** the **Compact** text button in the Context heading (was dropped in v7p1).
- **Footer:** restyled to match the title-bar chrome (cream `base-900` + navy ink/outline buttons;
  fixed count numbers/labels/`sess-btn`/`tok-pill` that were dark-theme colors invisible on cream)
  and separated from the palette.
- **Palette reference:** converted from the dark navy block to a **white, visually-separated panel**
  (margin, border, shadow, sits below the `.app` frame) with a red disclaimer banner stating it's a
  design reference, **not** part of the UI — to stop agents rendering it inside the app.
- **Session field:** the user expected it already removed, but the v7p1 base still had it in
  Agent→Details — removed it (agent session name = the agent's name). Bumped title badge v7.1→v7.2.

Files: `agent-dashboard/design/ui-concept-v7p2.html` (new)

### 2026-06-14 16:45:00 — Moved claude-context-extractor `projects/` → `tools/`; added --name/--summary/--tokens

Relocated `projects/claude-context-extractor/` → `tools/claude-context-extractor/` — it's a reusable
utility (like `cc_tmux_bridge/`), not a standalone project, so `tools/` is the right home. No code
paths changed: `extract.py` is location-relative (`HERE` / `out/` / `session_key.txt`). Verified it
still runs from the new path; dropped stale `__pycache__`.

Earlier in the same session the script also gained:
- **`--name "<title>"`** — resolve & export a chat by title (case-insensitive substring; exact title
  wins ties; ambiguous → lists matches).
- **`--summary <dir|json>`** — offline (re)summary; every export now also auto-writes `summary.md`
  (turns split human/assistant, tool calls by name, thinking blocks, models, timing + slowest turns,
  artifacts/citations, token estimate).
- **`--tokens {heuristic,tiktoken,api}`** — token-estimate ladder. claude.ai's JSON carries no token
  counts, so content figures are estimated; `api` calls Anthropic's free `count_tokens` for an exact
  number (raw `urllib`, no SDK dep). Confirmed on the UI-Rockstar export: exact **295,670** vs the
  ~233k chars/4 heuristic (heuristic ran ~21% low on code/JSON-heavy content). Also forced UTF-8
  stdout so the summary prints on Windows consoles.

Updated live references: the tool's `README.md` (run-path), the project `CLAUDE.md` (new Custom
Tooling subsection), and the two docs pointing at the old output path
(`prompts/ui-rockstar-reboot/transcript-thinking.md`, `archive/agent-dashboard/v7p1-crash-legacy/README.md`).
Prior DEVLOG entries and `cc-exports/` transcripts still cite the old `projects/...` path — left
as-is (append-only log + immutable exports); this entry records the new location. `tools/claude-export/`
(a smaller, separate exporter) is untouched — overlaps in purpose, a candidate to reconcile later.

Files: moved `tools/claude-context-extractor/*` (was `projects/claude-context-extractor/*`);
`tools/claude-context-extractor/{extract.py,README.md}`; `CLAUDE.md` (Custom Tooling subsection);
`prompts/ui-rockstar-reboot/transcript-thinking.md` (pointer);
`archive/agent-dashboard/v7p1-crash-legacy/README.md` (pointer)

### 2026-06-14 16:55:00 — Folded claude-export into claude-context-extractor; removed the duplicate

Closed the two-export-tools overlap found after the move. `tools/claude-export/` and
`tools/claude-context-extractor/` were twins from the same commit (`758c103`, 2026-06-14 09:56) —
same core (claude.ai internal-API export of thinking/tool_use/tool_result/citations/artifacts → raw
JSON + Markdown transcript). claude-context-extractor was the maintained superset; claude-export's
only unique bits were an inline `--session-key` and a configurable `--out`.

- **Ported** both into `extract.py`: `load_key()` now accepts an optional CLI key (precedence
  `--session-key` > `$CLAUDE_SESSION_KEY` > `session_key.txt`); `cmd_fetch()` takes `out_dir`, and
  `main` exposes `--session-key` / `--out`. Verified: compiles, both flags in `--help`, offline
  `--summary` regression still passes.
- **Deleted** `tools/claude-export/` (was git-tracked → recoverable from history).
- **Docs:** refreshed the tool's `README.md` (it was stale — now documents
  `--name`/`--summary`/`--tokens`/`--session-key`/`--out` and the `summary.md` output) and updated the
  `CLAUDE.md` tooling note (claude-export absorbed, no longer "to reconcile").

Provenance note: claude-export was never recorded in this DEVLOG when created (commit `758c103`
added it with no entry) — noted here for completeness.

Files: `tools/claude-context-extractor/{extract.py,README.md}`; `CLAUDE.md` (tooling note);
deleted `tools/claude-export/{claude_export.py,README.md}`

### 2026-06-14 17:05:00 — Hardened DEVLOG-compliance language (CLAUDE.md + log header)

Acting on the observation that DEVLOG entries get skipped (e.g., `claude-export` shipped unlogged at
commit `758c103`): the cause is soft prompting, so I tightened the *always-loaded* instruction rather
than relying on this in-file header (which an agent only reads if it opens the log).

- **CLAUDE.md** — promoted DEVLOG upkeep from a Key-files footnote to a first-class Behavioral rule:
  a concrete trigger ("before ending any turn that changed the repo / before saying done"), removed
  the "significant" loophole (bar = "did the repo change?"), and inlined the entry format. Key-files
  row now points at the rule.
- **DEVLOG header** — replaced the vague "whenever you finish a unit of work" with the same trigger
  plus a copy-paste template.
- Lever note: `.claude.json` is Claude Code runtime config, not a prose surface agents read — not the
  place for this; the levers are CLAUDE.md and this header.

Durable complement (offered, not built): a Stop/PostToolUse hook that reminds when a turn edited
files but didn't append here would convert "please remember" into "you get reminded."

Files: `CLAUDE.md` (Behavioral rules + Key files row); `DEVLOG.md` (header Log rule)

### 2026-06-14 18:15:00 - Built ui-concept-v7p1.html (v6p3 redesign)

Built the v7 dashboard redesign per `prompts/dashboard-v7-change-instructions.md`, as a single new
file `agent-dashboard/design/ui-concept-v7p1.html` (v6p3 left untouched as the base). Palette stays
Happy Hues 17 (cream/navy/pink); 13-agent JWT-audit scenario; 16-colour agent palette.

Headline aesthetic call (the open §A question): adopted a calibrated radius scale on CSS vars
(card 12, control/chip 7, pill 999, node 14, input 8) and a rounded "panel card" system (head/body/
foot, 2px navy border) sitting on the cream page so the page shows through the gaps. The finding is
that rounding should STOP at two places: the window chrome (flat title bar, flat navy footer) and the
inner stream surfaces (the CLI terminal and the feed wash stay square inside their rounded frames).
Full-pill is reserved for badges, format-option pills, and tags; everything structural uses moderate
radius.

Other decisions made: (1) kept Compose and Library as separate tabs rather than merging. (2) Moved
the Model button-group OUT of the locked on-demand band into a directly-editable control alongside
Mode and Effort; the rest of the identity fields keep the per-field pencil-to-edit lock. (3) Lifted
copy/clear out of the textareas into a right-aligned ghost-icon cluster ABOVE each field, reused as
the card copy button. Also: merged Messages/Scratch/Log into one Team Feed with a Format dropdown
plus direction and content minitoggles; vertical Source (single-select) and Target (multi-select)
strips plus a vertical agent filter strip that persist across tabs; square spaced graph nodes with
directed dashed edges drawn on a top SVG layer (semi-opaque so they read across cards); grouped
multi-select Response/Format dropdowns; and a Rewind/Handoff turn timeline.

Process note (environment): single file-writes over ~90k chars truncate here and a very long single
turn can fail mid-call, so the file was assembled in ~14 small sentinel-append passes (a `<!--Q-->`
marker moved down the file), with the head JS and INIT JS each `node --check`ed in the container
before writing. Verified in Playwright at 1600x1000: layout renders, INIT runs clean (only the
harmless file:// live-reload CORS noise), graph edges draw as directed arrows, the context breakdown
expands, the Library inline-placeholder preview fills, and the Response dropdown opens upward without
clipping (the reason the Prompts card uses overflow:visible).

Files: `agent-dashboard/design/ui-concept-v7p1.html` (new)

### 2026-06-14 22:14:46 — Extracted icon sets into publisher-named folders
Extracted the two archives in `assets/icons/` and renamed each set folder by publisher.
`Unconfirmed 588710.crdownload` (a complete game-icons.net zip, per its license listing Lorc/
Delapouite/etc.) → `game-icons.net/` (4,180 SVGs). `mtnt_2024.06_short_svg.zip` (Mutant Standard
emoji, mutant.tech / Caius Nocturne) → `Mutant Standard/` (8,295 SVGs). Deleted both source archives
after verifying extraction.

Files: `assets/icons/game-icons.net/` (new), `assets/icons/Mutant Standard/` (new), `assets/icons/Unconfirmed 588710.crdownload` (deleted), `assets/icons/mtnt_2024.06_short_svg.zip` (deleted)

### 2026-06-17 21:50:00 — First agent-icon pass: 219 face/head candidates extracted from game-icons.net
Ran a 3-stage funnel over the 4,180 game-icons.net SVGs (no metadata in files — filename is the only
local signal, so no per-image geometry parsing). Stage 1: whole-word keyword match (face/head/mask/
helmet/skull/creature terms, minus a false-positive blocklist) → 243 candidates. Stage 2: rendered all
243 into a labeled contact sheet via headless browser + visually pruned 42 clear non-faces (objects,
buildings, weapons, full-body scenes, single body-parts). Stage 3: secondary net over expression/
feature/creature terms caught 18 mislabeled faces the keywords missed (delighted, screaming, shouting,
sleepy, sly, smitten, surprised, terror, oni, fish-monster, jawless-cyclop, third-eye, etc.). Final:
219 SVGs copied (not moved — references kept intact) to assets/icons/agents for manual review; 4
duplicate basenames disambiguated with __<creator>. Review sheet + screenshots in .scratch/icon-pass/.
A full exhaustive 4,180-icon visual sweep is still available if 100% recall is wanted.

Files: `assets/icons/agents/` (new, 219 SVGs), `.scratch/icon-pass/` (work: candidate lists, contact sheets, review.html)

### 2026-06-17 22:20:00 — Agent-icon shortlist selector UI
Built a self-contained review/select UI for the 219 agent-icon candidates so the keep-set can be
curated by hand. Copied the 219 SVGs into assets/icons/references/agents-shortlist/icons/ and generated
index.html (SVGs inlined — opens by double-click, no server needed). Tiles start all-kept and are grouped
most-likely-to-keep → least: Faces & expressions (41), Masks (28), Character & creature heads (29),
Helmets (29), Animal heads (35), Skulls (32), Skull-objects & borderline (25). Click toggles keep/drop;
shift-click applies the last click's state across the whole visual range (drag-free multi-select);
Export emits a newline list of kept .svg filenames (copy or download selection.txt). Verified in
Playwright: counter, plain toggle, shift-range, and export all correct. Next: user curates → hand back
selection.txt → rebuild a fresh assets/icons/agents from it.

Files: `assets/icons/references/agents-shortlist/index.html` (new), `assets/icons/references/agents-shortlist/icons/` (219 svgs), `.scratch/icon-pass/build-shortlist.js` (generator)

### 2026-06-17 22:35:00 — Dashboard UI concept v7p3 (requests rework + Agent column move)
Created ui-concept-v7p3.html from v7p2. Reworked the request model around the "one pending request per
agent" reality: moved the Requests tab out of the Agent panel into the Team Feed panel (now Messages ·
Requests(4) · Scratch · Log), where it shares the same vertical agent Filter strip; the tab badge is now
a fleet total (agents awaiting), and the tab shows one card per pending agent (drew/sandy/vega/sage) with
per-card agent identity + request type (Permission/Approval/Decision). Graph node request indicators lost
their number → unified gold "pending" dot matching the active/idle status dots. Each request card regained
a per-card Reply button (far right, divider-separated) that routes to the Prompts panel — switches to
Compose, selects that agent as the sole Target, flashes the panel, focuses the field; the old shared
"Reply to" field was removed. Decision cards now require an explicit Approve (disabled until an option is
picked) instead of submitting on option-select. Moved the Agent panel to the far-left column (same width;
order is now Agent | Team Graph+Prompts | Team Feed). Bumped the tab-state localStorage key to awl-tabs73
so stale v7p2 state can't blank the relabeled panels, and added 01 sandy to the Prompts target strip so
Reply resolves for all four pending agents. Verified in an isolated Playwright render (1680×1000): layout,
tab badge, all 4 cards, gold dots on all pending nodes, Decision enable-on-pick, and Reply routing all
confirmed; console clean (only favicon 404). Build via assertion-guarded script; v7p1/v7p2 untouched.

Files: `agent-dashboard/design/ui-concept-v7p3.html` (new, 173,904 bytes), `.scratch/build_v7p3.py` (build script)

### 2026-06-17 22:55:00 — README brought current with the v7 refactor
Updated agent-dashboard/README.md (the design-intent ground truth), which had drifted back to the
~v6p2 layout. Repointed the mockup to ui-concept-v7p3.html and rewrote the structural sections to
match: the layout diagram + three-column model (Agent left | Team Graph+Prompts middle | Team Feed
right), the removed CLI/live-stream pane (now noted under out-of-scope; live agent output reads in
the Messages tab), the merged Messages tab (was Outgoing+Incoming), and the Requests rework — moved
into the Team Feed as its own tab with the "one pending request per agent → binary card dot, fleet
total on the tab" model, per-card agent identity, Decision's explicit Approve, and Reply that routes
to the Prompts panel. Also dropped the removed Session field from the Agent/Create field lists and
re-tuned the design-system attention-ramp + open-question notes. Did it via an assertion-guarded
script with cross-anchor sanity checks (all internal links repointed; no dangling anchors). Intent
doc only — no behavior/code change.

Files: `agent-dashboard/README.md` (updated), `.scratch/update_readme.py` (update script)

### 2026-06-17 22:35:00 — Rebuilt agents/ from curated selection (219 → 167)
User curated the shortlist UI and saved agents-shortlist/selection.txt (167 picks). Validated all 167
against the source (0 mismatches), then wiped and rebuilt assets/icons/agents/ with only the selected
SVGs copied from the pristine references/agents-shortlist/icons/. Dropped 52 — mostly skull-on-object
variants (skull-ring/staff/signet/shield/bolt), plain helmets, and abstract/borderline icons. Shortlist
folder + UI left intact for future re-runs.

Files: `assets/icons/agents/` (rebuilt, 167 svgs)


### 2026-06-17 23:05:00 — Dashboard design v8p1: neobrutalism.dev refactor
Refactored the v7p3 wireframe onto the neobrutalism.dev design language as a new static mockup,
`ui-concept-v8p1.html`. Token names + Tailwind utility classes mirror the library (bg-main,
border-border, shadow-shadow, rounded-base, font-heading, hover press-translate) so it ports ~1:1 to a
React/shadcn build; the 3-pane layout is a hand-rolled Resizable frame (group/panel/handle + grips)
matching neobrutalism's Resizable. Switched agent icons to recolorable game-icons.net tiles (bg = agent
color via currentColor, glyph = cream var(--icon-fg); 29 inlined as a sprite from assets/icons/agents/)
and all UI icons to Lucide (CDN) with local source copies saved to assets/icons/ui/{actions,nav,status,
domain} (49 svgs). Color + icon pickers rebuilt as Select/Combobox popovers (current selection always
visible; icon picker searchable). Font -> Archivo; radius collapsed to a single 5px base; palette =
Happy Hues 17 core + lean semantic + 16 agent colors. Verified in-browser (Playwright, served :8851):
fixed a timeline scrollIntoView that scrolled the Agent pane, a search-focus scroll that shifted the
picker panel, and chip-name truncation. All four panels + drawer + requests + timeline + context +
pickers render clean.

Files: `agent-dashboard/design/ui-concept-v8p1.html` (new), `assets/icons/ui/` (49 Lucide svgs, new),
`.scratch/v8/*` + `.scratch/build_agent_sprite.py` + `.scratch/v8shots/*` (build & verify artifacts)

### 2026-06-17 23:40:00 — Agent-selector layout options (snippet sheet)
User flagged the nested vertical agent-toggle strips (Prompts Source/Target + Team Feed Filter) as
inelegant — triple-nested cards, tiny icon, truncated labels. Built a comparison sheet of 5 list-style
alternatives in v8 neobrutalism styling, each reading like the Agent-panel identity header / Team-Graph
card (bigger 26-30px recolorable tile + two-line role·name, no truncation, one bordered list, keeps
Select-all/Clear-all): (1) filled identity rows, (2) checkbox list w/ master box, (3) agent-color accent
stripe, (4) one-line compact, (5) wrapping chip cloud. All interactive; verified in browser.

Files: `agent-dashboard/design/ui-snipets/agent-select-options.html` (new)

### 2026-06-17 23:58:00 — v8p2: reworked the agent selectors (Source / Target / Filter)
User picked option 1 (filled identity rows) from the selector-options sheet, but wanted it without the
filled header bar — presented like the Library Templates list: a plain section heading with All / None on
the far right (where the count would be) over a bordered, divided list of filled identity rows. Copied
v8p1 -> v8p2 and replaced all three nested `.vstrip`/`.vtog` strips with `.aglist` + `.agrow`: 28px
recolorable tile + two-line role·name (full label, no truncation), selected = brand-accent fill + check.
Source is single-select (`pickAgRow`), Target/Filter multi-select (`toggleAgRow`) with `agAll()` All/None
per `[data-agscope]`. Updated `replyTo` to target `.agrow`/`.ag-name`; removed the old
selectAllV/initSelectAll. Verified in browser: single-select, All(11)/None(0), and reply-routing all pass.

Files: `agent-dashboard/design/ui-concept-v8p2.html` (new)

### 2026-06-18 00:30:00 — v8p3: palette cleanup + selector/feed/picker/library refinements
Copied v8p2 -> v8p3 and applied the user's review notes. (1) Agent-selector All/None is now a single
contextual link (`agAllNone`/`agSync`: shows "All" until everything's selected, then "None"); headings
trimmed to "Source"/"Target". (2) Palette cleanup: `--secondary-background` -> white `#ffffff` (crisp
cards on the cream canvas), removed the cool-gray `--term` feed tint (feed wells now use the cream canvas,
sticky toolbar uses `--surface-3`) — down to 3 warm surfaces. (3) Added muted pink `--select` `#f9cbdf`
for list-selection fills (agent rows, templates, version/option/split-menu rows) so the strong `--main`
pink no longer overwhelms long select lists. (4) Put Happy Hues 17 teal to work as `--secondary` `#8bd3dd`
+ a `.btn-secondary` variant; the secondary "Revise" split button is now teal (pairs with the pink primary
Send). (5) Feed direction filters relabeled "Sent"/"Received" with arrow icons and re-anchored to the
operator — User now reads SENT (never an incoming tag); In/Out tags de-colored to neutral. (6) Context
example bumped to a more illustrative 40% (399.1k/1.0M; category tokens + bar kept internally consistent).
(7) Color swatch sized to 22px to match the agent-icon tile so both pickers are the same height. (8) In the
Library fill row, Reset + Apply moved OUTSIDE the textarea as trailing icon buttons (Apply = pink primary).
Verified in browser: contextual All<->None (0<->11), equal 36px picker triggers, muted-pink selection
legibility (Source/Target/Filter/Templates), neutral Sent/Received tags, trailing Reset/Apply, 40% context.

Files: `agent-dashboard/design/ui-concept-v8p3.html` (new)

### 2026-06-18 00:45:00 — Synced the dashboard README design-reference to v8p3
Brought `agent-dashboard/README.md` up to date with the v8 neobrutalism arc (it still pointed at v7p3).
Repointed the canonical mockup to `ui-concept-v8p3.html` and noted it's a neobrutalism.dev refactor.
Rewrote the **Design system** section onto the v8p3 tokens: 3 warm surfaces (cream canvas · white cards ·
surface-3 chrome) + `--rule`, 2px navy borders, hard offset shadows, 5px radius, Archivo/JetBrains Mono;
accents pink `--main` (primary) / muted pink `--select` (list selection) / teal `--secondary`; updated the
Requests ramp + status hexes to current values; agent palette 12 -> 16 colors; documented recolorable
game-icons tiles + Lucide UI icons; components now list Resizable groups, identity-row selectors with
contextual All/None, and equal-height pickers. Also updated behavioral spots that changed: Team Feed filter
+ Source/Target are identity-row lists (not chips) with contextual All/None; Messages direction is
operator-anchored Sent/Received with neutral tags (User never "incoming"); Revise chip is now scope
(Grammar/Language/Refactor); Library fill has trailing Reset/Apply icon buttons. Removed the now-resolved
"Evolving Revise strengths" future-direction. DEVLOG Status block already reflects v8p3.

Files: `agent-dashboard/README.md`, `DEVLOG.md`

### 2026-06-19 21:10:35 — Palette exploration v2 (Happy Hues 17, restructured tokens + status ramp)
Created a standalone palette-exploration artifact to address 7 palette issues raised (pink overloaded;
too much palette spent on requests; no generalized token mapping; weak good→bad status signal; cream/white
indiscernible; header-cream misused outside headers; Messages filter/feed cream seam). Proposes a named
token taxonomy (Surfaces · Ink/Lines · Brand-Action · Status · Requests · Agents), a single monotonic
good→bad status ramp (ok→info→warn→alert→bad), folds the 3 request types ONTO that ramp (Decision=info,
Approval=warn, Permission=alert) to drop bespoke warm colors, demotes pink to action-only, reserves
header-cream for headers, and brings HH17's unused peach (#f3d2c1) + paragraph-blue (#172c66) into use.
Rendered as 3 switchable directions (A Warm/peach-select · B Balanced/refined-pink-select · C Crisp/cool-
select), each showing the full Team Feed › Messages panel + a control gallery (buttons, split buttons,
segmented, identity rows, status dots/badges, context bars, request cards). Verified visually via Playwright;
no functional console errors. Not yet wired into the mockup — awaiting direction choice.

Files: `agent-dashboard/design/ui-snipets/palette-explore-v2.html`

### 2026-06-20 09:00:00 — Palette exploration v2 reframed → agent-color families (UI locked to v8p3)
On user feedback (light button text didn't work / unclear what the palette was based on; need ≥15 agent
colors that differentiate from UI elements; don't change v8p3's working styling — just the palette):
renamed the prior surface-direction explorer `palette-explore-v2.html` → `palette-explore-v1.html`, and
wrote a new v2. The UI palette + controls are now **locked** — tokens/components copied verbatim from v8p3
and shown once as a "navy ink on every fill" control gallery (Retire is a white button with danger *text*;
the only knockout is the white agent glyph — that's the light-text fix). The single variable is the **agent
identity family**: three candidate sets of **16 colors** built in **OKLCH** (16 hues evenly spaced, fixed
lightness; only chroma/lightness defines the family) — A Jewel (deep/rich), B Muted (grayed/earthy), C Vivid
(bright/even). Each family shows a register-comparison row (agent set vs the UI signal colors it must stay
clear of), a 16-swatch grid with live canvas-resolved hexes, and the colors in real v8p3 context (identity
rows, graph cards, feed names, request cards). Verified in browser: oklch→hex resolves, families visibly
distinct, white glyph legible on all tiles incl. the lightest. Not yet wired into the mockup — awaiting a
family choice (then v8p3's 16 agent colors get updated to match).

Files: `agent-dashboard/design/ui-snipets/palette-explore-v2.html` (new), `agent-dashboard/design/ui-snipets/palette-explore-v1.html` (renamed from the old v2)

### 2026-06-20 10:30:00 — ui-concept-v8p4: tokenized the split-button "dim" shades (color-only)
Copied v8p3 -> v8p4 with a single, color-scoped change: the split-button dropdown halves were inline
one-off hexes (`#ef7aa6` on the primary/Send drop, `#bfe6ec` on the secondary/Revise drop). Promoted both
to palette tokens — `--main-dim:#ef7aa6` and `--secondary-dim:#bfe6ec` — defined in `:root`, added to the
Tailwind color map, wired into `.split--primary .split-drop` / `.split--outline .split-drop`, and added to
the bottom-of-page token legend. Verified in browser: both resolve to the original hexes (split buttons
render byte-identical), no console errors. Everything else is unchanged from v8p3. NOTE: the agent-color
family from the palette explorer was never chosen, so v8p3's existing 16 agent colors carry over untouched —
still an open decision before any agent-palette swap.

Files: `agent-dashboard/design/ui-concept-v8p4.html` (new)

### 2026-06-19 12:00:00 — Captured v8p3 to-do backlog in human notes

Organized the user's rough change notes for the v8p3 mockup into a structured backlog appended
to `docs/human-notes-misc.md` ("Dashboard v8p3 — To Add / Update"). Grouped by area (Agent panel,
Prompts & input, Team Feed & Scratch, Linking, Lifecycle & health, System, Documentation, Housekeeping),
single-level bullets, terms normalized to README vocabulary. Notes only — no mockup changes.

Files: `docs/human-notes-misc.md` (edited)

### 2026-06-19 12:30:00 — Reorganized v8p3 backlog by effort; verified against mockup

Rewrote the "Dashboard v8p3 — To Add / Update" section in `docs/human-notes-misc.md`: regrouped by
effort (Quick wins / Big picture / Needs research / Housekeeping & docs), gave each bullet an inline
header. Cross-checked every item against `ui-concept-v8p3.html` — dropped the already-built Skills
add/remove note; trimmed TLDR, Output Export, Turn Count, Context-Bar health color, Subagent forking,
and Lifecycle wind-down to just their remaining gaps.

Files: `docs/human-notes-misc.md` (edited)

### 2026-06-20 11:00:00 — ui-concept-v8p5: agent identity palette → "Jewel" family (color-only)
Copied v8p4 -> v8p5 and applied the chosen agent-color family from the palette explorer — Family A
"Jewel" (OKLCH 0.52 / 0.15, 16 evenly-spaced hues; deep, even, identity-forward). Replaced all 16 agent
hexes (mapped old→new by nearest hue so each agent keeps a similar position) across every use: inline
tiles/dots/progress-bars, feed name colors, both colour-picker grids + triggers, context-breakdown
category colors, the Tailwind `agent` token map, and the bottom-of-page legend. Relabeled the 16 token
names to the family's names (vermilion/amber/gold/citron/lime/fern/emerald/teal/cyan/azure/cobalt/indigo/
violet/orchid/magenta/crimson) so the picker + legend stay truthful. New hexes: crimson #aa3a61, emerald
#008149, cobalt #006bbb, amber #aa4600, fern #387b12, violet #7152b5, vermilion #af3c3a, cyan #007f91,
gold #9d5400, citron #876300, orchid #8b48a0, azure #0076ab, teal #008370, lime #687100, indigo #4d5ebe,
magenta #9e3f84. Also (per request) made the legend heading stateless: "Neobrutalism Token Palette — v8p4"
→ "Token Palette". Verified in browser: picker swatch/value/on-state + legend all agree, 16 distinct names,
zero leftover old hexes, no console errors. UI palette + all functionality unchanged from v8p4.

Files: `agent-dashboard/design/ui-concept-v8p5.html` (new)

### 2026-06-20 12:00:00 — v8p5: reordered agent swatches to ROYGBIV; synced README design system
Reordered the 16 agent colors into spectral **ROYGBIV** order (crimson · vermilion · amber · gold · citron ·
lime · fern · emerald · teal · cyan · azure · cobalt · indigo · violet · orchid · magenta) in both
color-dropdown grids (Details + Create) and the Token Palette legend — edit-in-place on v8p5, no version
bump. Each grid keeps its own selected swatch (Details = emerald, Create = indigo). Verified in browser:
both grids + legend match ROYGBIV exactly, picker triggers still consistent, no console errors.
Also synced `agent-dashboard/README.md` design system to the current mockup: repointed the canonical
wireframe v8p3 → v8p5; replaced the agent identity palette with the OKLCH "Jewel" family (16 hexes, ROYGBIV
order, with the even-OKLCH rationale for why it stays clear of the UI register); added a note that split
buttons use dimmed accent tints `--main-dim #ef7aa6` / `--secondary-dim #bfe6ec` (the v8p4 change).

Files: `agent-dashboard/design/ui-concept-v8p5.html` (edited), `agent-dashboard/README.md`

### 2026-06-20 09:30:00 — Cleaned v8p3 backlog guidance; folded in user's loose notes

Rewrote the "Dashboard Add / Update Notes" guidance in `docs/human-notes-misc.md` into agent-maintenance
instructions (verify against the latest `ui-concept-v8pN.html`, inline-header format, group by effort,
loose-notes workflow). Incorporated 6 user loose notes into Quick wins / Big picture (Thinking-mode
card display merged into the toggle item, Status Badge, History Status Badge, History Fill, Scratch
Target Order, Assets Panel) and emptied the Loose-notes bucket.

Files: `docs/human-notes-misc.md` (edited)

### 2026-06-20 14:00:00 — Added ID numbering to dashboard backlog; folded in 10 loose notes

Refactored "Dashboard Add / Update Notes" in `docs/human-notes-misc.md` to use letter-section /
number-item IDs (A1, B7, …) and added a Numbering rule to the maintenance guidance. Incorporated 10
user loose notes: new A5 Remove Link Lines, A6 Mode Rename, A10 Compose Mic Button; new B1–B3 Role/
Skills/Tools dropdowns, B7 Plans Tab, B14 Trigger Interrupt/Inject, B15 Interactive Comms, B20 Link
Edges. Cross-referenced related items by ID and emptied the Loose-notes bucket.

Files: `docs/human-notes-misc.md` (edited)

### 2026-06-20 15:30:00 — Converted dashboard backlog to ordered lists; bold header only

Changed all four backlog sections in `docs/human-notes-misc.md` from bulleted `**A1. Header:**` entries
to markdown numbered lists with only the header bolded; IDs are now section-letter + list-number (B7, etc.).
Updated the Format/Numbering guidance to match. Folded in one loose note (new A10 Compose Heading rename)
and renumbered Section A; emptied the Loose-notes bucket.

Files: `docs/human-notes-misc.md` (edited)

### 2026-06-20 16:15:00 — Folded last loose note into dashboard backlog

Added A15 "Demo Data Consistency" (audit mockup example data; fix the Agent → Context bar that reads
40% but renders no fill) to `docs/human-notes-misc.md` and emptied the Loose-notes bucket.

Files: `docs/human-notes-misc.md` (edited)

### 2026-06-20 17:00:00 — Added "Next up" work queue to dashboard backlog

Restructured "Dashboard Add / Update Notes" in `docs/human-notes-misc.md`: new section A "Next up"
(priority queue) holds the former A items except Live Turn Count / Output Export / Jump to Feed Ends
(now the slimmed B "Quick wins") plus the three Agent config dropdowns moved up from Big picture.
Re-lettered Big picture→C, Needs research→D, Housekeeping→E, renumbered all items, and fixed every
cross-reference ID (e.g. see C17 / see C5 / A4).

Files: `docs/human-notes-misc.md` (edited)

### 2026-06-20 09:35:00 — Dashboard mockup v8p6: interaction + consistency pass

Created `agent-dashboard/design/ui-concept-v8p6.html` from v8p5 with 16 changes: per-agent Thinking
on/off toggle (Agent → Details/Create, inline trailing Mode) shown on graph cards; context bars
(graph + Agent summary, now 40% fill) health-colored via the Timeline ctxColor scale; graph status
dot → rectangular status badge button (jumps to Requests/History/Compose); removed non-working link
lines (C17); Mode "Fuckit"→"FREE!"; History "Sent"→"Active"/"Complete"; Details History fills
remaining space; Target list leads with Scratch; Compose heading + inline mic; Response format gains
TLDR; Role→combobox (from agent.md, prefills Create), Skills/Tools→multi-select dropdowns (skills
files / all native Claude Code tools, ground-truthed against docs); Feed panel renamed. Verified in
browser: no JS errors, all dropdowns/toggles/jumps and Create prefill work.

Files: `agent-dashboard/design/ui-concept-v8p6.html` (new)

### 2026-06-20 17:45:00 — Repopulated dashboard "Next up" from loose notes

Folded 6 loose notes into the now-empty Section A of `docs/human-notes-misc.md` (Library Tag Indicator,
Source Dropdown, Team Feed Fills, Full-Bleed Header/Footer, History Actions incl. Stop button, TLDR
Placement) and emptied the Loose-notes bucket. Fixed a dangling cross-reference in C17 Link Edges (the
old "A4" target was removed when Section A was cleared).

Files: `docs/human-notes-misc.md` (edited)

### 2026-06-20 10:30:00 — Dashboard mockup v8p7: layout + interaction refinements

Created `agent-dashboard/design/ui-concept-v8p7.html` from v8p6 with 6 changes (backlog A1–A6):
Library placeholder fill no longer tints the textarea border — shows a "(tag)" link indicator instead;
shared agent selector Source is now a compact dropdown stacked above Target in one column; Feed tab
panels (Messages/Requests/Scratch/Log + the Messages sub-bar) set to white like Prompts → History;
main UI made full-bleed (`.three` padding→0, outer frame square/no shadow so header, panels, footer
meet flush to the window edges); Prompts → History cards are now selectable with the per-card action
strip moved to a single footer (Copy · Edit · Retry · Stop, Stop added); Response-format TLDR moved
under Structure instead of its own group. Verified in browser: 0 JS errors; all dropdowns, history
selection/footer, library indicator, and format groups behave correctly.

Files: `agent-dashboard/design/ui-concept-v8p7.html` (new)

### 2026-06-20 10:45:00 — Dashboard mockup v8p7: reworked to reuse existing patterns

Reworked the v8p7 changes after review feedback that the new styling didn't match what's already in
the mockup. History cards now mirror the Team Graph `.node` styling/behavior exactly (shadow-sm at
rest, press-on-hover, selected = shadow + 3px main outline). History footer rebuilt as text+icon
buttons in the standard `.btn`/`.btn-danger` family (Copy · Edit · Retry · Stop) matching the other
prompt-tab footers; dropped the "Selected prompt" label. Scrapped the out-of-scope Library "linked to
(tag)" indicator entirely — change A1 is now just dropping the placeholder's tag-colored border tint
(the field's placeholder still names the active tag). Source-dropdown, Feed-white, full-bleed, and
TLDR-under-Structure changes unchanged. Re-verified in browser: 0 JS errors, all six behaviors pass.

Files: `agent-dashboard/design/ui-concept-v8p7.html` (edited)

### 2026-06-20 18:15:00 — Folded 2 loose notes into dashboard "Next up"

Added A1 Mic Button Placement (move mic into shared footer action strip) and A2 Fast Mode & Toggles
Row (integrate Opus fast mode; Mode→Permission Mode; thinking as a toggle) to Section A of
`docs/human-notes-misc.md`; emptied the Loose-notes bucket.

Files: `docs/human-notes-misc.md` (edited)

### 2026-06-20 18:35:00 — Moved Live Turn Count into dashboard "Next up" with fuller spec

Moved the former B1/Quick-wins "Live Turn Count" into Section A (now A3) of `docs/human-notes-misc.md`
and expanded it: simple "Turns 3/50" count from max turns, good→bad color code like context, inline
on the agent cards immediately preceding the context bar. Renumbered Quick wins.

Files: `docs/human-notes-misc.md` (edited)

### 2026-06-20 18:55:00 — Added 3 loose notes to dashboard "Next up"

Folded A4 Requests Tab Order, A5 Messages Card Select (multi-select), and A6 Messages Footer
(Copy/Summarize/Share) into Section A of `docs/human-notes-misc.md`; emptied the Loose-notes bucket.

Files: `docs/human-notes-misc.md` (edited)

### 2026-06-20 11:30:00 — Dashboard mockup v8p8: agent-config + feed interaction pass

Created `agent-dashboard/design/ui-concept-v8p8.html` from v8p7 with 6 changes (backlog A1–A6):
voice-dictation mic moved from the Compose header into the shared Prompts footer as the first control
(resized to 30px to match); Mode renamed "Permission Mode" and a new "Toggles" row added hosting Opus
Fast mode (maps to /fast · fastMode setting) + Thinking, both as toggles (Details + Create); Team Graph
cards now show a health-colored "Turns n/50" count inline immediately before the context bar (reusing
the ctxColor good→bad scale); Feed tab order changed so Requests is last (Messages · Scratch · Log ·
Requests); Messages cards made multi-selectable like History; new Messages footer styled like the
Prompts footers with Copy · Summarize · Share (icon+text), shown only on the Messages tab. Ground-
truthed Fast mode against the CLI/settings docs. Verified in browser: 0 JS errors, all six pass.

Files: `agent-dashboard/design/ui-concept-v8p8.html` (new)

### 2026-06-20 11:40:00 — v8p8 tweak: merged Mode + Toggles under one "Mode" heading

Per follow-up: reverted "Permission Mode" back to "Mode" and dropped the separate "Toggles" heading;
the Mode heading now covers both the permission-mode segmented control and the Fast/Think toggle row
directly beneath it (Details + Create). Verified the Agent panel renders correctly.

Files: `agent-dashboard/design/ui-concept-v8p8.html` (edited)

### 2026-06-20 11:50:00 — Synced dashboard README with this session's v8p6→v8p8 work

Updated `agent-dashboard/README.md` (the design-intent reference) to match the mockup as built this
session: pointer bumped v8p5→v8p8; layout diagram reordered (Feed: Messages·Scratch·Log·Requests;
Source dropdown over Target; Messages footer; full-bleed frame); Team Graph cards now described with
status badge (jump button), health-colored context bar, and live turn count; Feed table reordered
with Messages multi-select + Copy/Summarize/Share footer; Agent Details/Create updated for the Mode
block's Fast/Think toggles and the Role/Skills/Tools dropdowns; Prompts updated for Source dropdown,
History selectable cards + footer, and the mic-led action row; Library input de-tinted; Design-system
surfaces/status updated (white feed wells, status badge, health-colored bars).

Files: `agent-dashboard/README.md` (edited)

### 2026-06-20 19:15:00 — Added 3 loose notes to dashboard "Next up"

Folded A1 Revise Label, A2 Selected Card Style (light pink fill, drop viewing badge), and A3 History
Card Highlight (remove dark pink selection fill) into Section A of `docs/human-notes-misc.md`; emptied
the Loose-notes bucket.

Files: `docs/human-notes-misc.md` (edited)

### 2026-06-20 20:10:00 — Dashboard mockup v8p9 (three minor tweaks)

Branched `ui-concept-v8p9.html` from v8p8 (no design-language change) and applied the three Section-A
notes: (1) Revise split button now reads "Revise: <scope>" via a prefix-aware `pickSplit` + a
`data-prefix` on its `.split-lbl`; (2) selected Team Graph card uses a light-pink `--select` fill
instead of the pink ring, and the floating "VIEWING" badge (CSS + static markup + `selectNode` JS
injection) is removed; (3) Agent → History timeline drops the bright-pink fill on the current ("now")
row — the "now" pill still marks it. Verified in-browser: Revise label tracks picks, current row bg is
white, badge gone, selected card fills light pink. The broader pink/teal recoloring remains parked.

Files: `agent-dashboard/design/ui-concept-v8p9.html` (new)

### 2026-06-20 20:35:00 — v8p9 selected-card fill extended to History + Messages cards

Followed up the v8p9 card-selection change: `#prompt-history .rcard.sel` and `#feed-messages .rcard.sel`
now use the same light-pink `--select` fill (ring removed), matching `.node.selected`. Verified
in-browser — both selected Messages (multi-select) and History cards compute to `#f9cbdf` with no
outline. Picker/`.sw`/`.icotile` rings left as-is (out of scope).

Files: `agent-dashboard/design/ui-concept-v8p9.html` (edited)

### 2026-06-20 05:12:48 — Settings panel — standalone snippet for review

Built the new top-level **Settings** panel per `prompts/add-settings-panel/`, as a standalone
snippet (other agents own the live concept) rather than branching v8p6. Step-into full-window view
(gear control to the right of the WSL2/tmux/Connected chips; toggles in/out, 3-pane returns on exit
— no floating popup). Subject tabs Usage · MCP · Plugins · Config · Setups, with scope as a secondary
segment inside MCP/Plugins/Config. Read-only status/health/usage visually separated from editable
config (inert vs raised bands); global `~/.claude` edits gated behind an explicit confirm; per-setting
Live vs New-session badges from the CLI lifecycle map. Content grounded in this machine: real MCP
allow/deny set (incl. the two parked claude.ai servers + disconnected Slack), the 5 installed plugins
with real enabled state, 3 configured models, GSD hooks, effort=max. Matches the v8p9 neobrutalism
design language (tokens, Archivo + JetBrains Mono, hard offset shadows). Verified all 5 tabs +
gate + step-out in-browser.

Files: `agent-dashboard/design/ui-snipets/settings-panel.html` (new)

### 2026-06-20 21:05:00 — Dashboard mockup v9p1 (accent rebalance, color only)

Branched `ui-concept-v9p1.html` from v8p9 and rebalanced the two accents (no layout/behavior change).
Pink (`--main`) was overloaded across brand + primary action + tabs + segmented/toggle state +
selection; it now stays only on primary commit actions (Send, Apply, `.btn-main`), the active panel
tab (`.tab-btn`), count badges (`.req-badge` / token pill), and the title bar / reply flash. Teal
(`--secondary #8bd3dd`) became the workhorse "state" accent — active segmented controls & value
pickers (Mode/Effort/Trigger/model/format), all on-toggles (Fast/Think/limit/mini), picker selection
rings, the active template pill, and hover affordances. Redefined `--select` (selection fill) from
muted pink `#f9cbdf` to light teal `#a9dde7`, so every selected list row AND card (graph nodes,
History, Messages) reads teal. `--ring` repointed to teal; Palette Reference legend updated. The
agent-identity Jewel palette and the warm Requests ramp / success-warning-danger signals are
untouched. Verified in-browser: title bar / active tab / Requests badge / Send = pink (245,130,174);
segmented / Think / model / Revise = teal (139,211,221); selected node / Target row / Library row =
light teal (169,221,231); active placeholder pill = full teal. NB — dashboard README design-system
section still describes the old pink-selection scheme; left as-is (out of scope for this color pass).

Files: `agent-dashboard/design/ui-concept-v9p1.html` (new)

### 2026-06-20 19:35:00 — Added 4 loose notes to dashboard "Next up"

Folded A1 History Tab Group, A2 Model Buttons Style, A3 Details Status Badge, and A4 Link Agents
Button into Section A of `docs/human-notes-misc.md`; emptied the Loose-notes bucket.

Files: `docs/human-notes-misc.md` (edited)

### 2026-06-20 22:10:00 — Dashboard mockup v9p2 (button/selector taxonomy, color only)

Branched `ui-concept-v9p2.html` from v9p1 to fix the action/selector color logic, grounded in
Material 3 color roles + Carbon button hierarchy (web-researched this session). One emphasis ladder:
**pink = primary · teal = secondary · cream = low · red = danger.** Changes: (1) low-emphasis ACTION
buttons move off stark white onto a new warm cream token `--surface-btn #fbf5e8` (lighter than the
`--surface-3` chrome footers so they still pop) — `.btn`/`.btn-danger`/`.fmt-btn`/`.tl-ic`/`.fill-btn`/
`.dir-cyc`; form inputs & selector FIELDS (`.in`, Color/Icon/Role/Source/Skills/Tools triggers,
steppers) stay white. (2) Response is a MENU selector → its trigger is now neutral cream (was
teal-when-active); "N selected" reads from a teal count badge (`.fmt-badge`) + teal selected pills.
Codified rule: inline selectors (segmented/tabs/toggles) show selection in place as a teal fill; menu
selectors keep a neutral trigger + teal on the value/options + count badge. (3) Revise stays the single
teal tonal secondary action; Send stays fully pink incl. its dim chip. Verified in-browser: neutral
btn + Response trigger = cream rgb(251,245,232); Response badge + selected pills = teal; Revise = teal;
Send = pink; footers sit on `--surface-3` so cream pops. README design-system still lags (out of scope).

Files: `agent-dashboard/design/ui-concept-v9p2.html` (new)

### 2026-06-20 22:55:00 — v9p2 split-button fix + README/legend sync to the new color ladder

Fixed an inherited inconsistency in v9p2: the two split buttons split light/dark in opposite
directions (`--main-dim #ef7aa6` was a *darker* shade for the Send chip, while `--secondary-dim
#bfe6ec` was a *lighter* tint for the Revise chip). Repointed `--main-dim` to a light-pink tint
`#f9b9d2` (≈44%-toward-white, matching the teal chip's tint ratio) so both split buttons now read
**light chip + full action** (Send: full-pink action + light-pink "Now" chip; Revise: full-teal action
+ light-teal chip). Updated the in-mockup Token Palette legend (`--main-dim` swatch/label). Synced the
dashboard **README** design-system to the v9p2 emphasis ladder (pink=primary · teal=secondary ·
cream=low · red=danger): rewrote the Accents table, added the `--surface-btn` surface row + the
inline-vs-menu selector rule + the light-chip split-button rule, fixed the stale "muted-pink selection"
→ light-teal, and bumped the "current wireframe" pointer v8p8 → v9p2. Left the Response badge teal
(meaning-based: selection count, not an attention badge) per the user's scope. Verified in-browser:
Send chip = rgb(249,185,210), Send action = rgb(245,130,174); Revise chip/action = teal pair.

Files: `agent-dashboard/design/ui-concept-v9p2.html` (edited), `agent-dashboard/README.md` (edited)

### 2026-06-20 23:40:00 — Dashboard mockup v9p3 (four component tweaks)

Branched `ui-concept-v9p3.html` from v9p2. (1) Agent → History (Rewind/Handoff) now behaves like
Agent → Model: restyled `.tri-tabs` as a standard fully-rounded button group with the timeline as a
separate rounded popout (`#hist-acc`) that is HIDDEN until a mode is selected — and, unlike Model,
both Rewind & Handoff can be toggled off (back to hidden); rewrote the hist-tabs JS to a `setMode(m|null)`
toggle. (2) `.model-tabs` restyled as a standard fully-rounded button group; `.ver-panel` is now a
standalone rounded popout (full border + `margin-top`) instead of flat-bottom tabs fused to the panel.
(3) Agent → Details status badge swapped from the dot-in-chip to `.node-badge nb-pending` (inline, solid
status fill + uppercase) so it matches the Team Graph card badges. (4) "Link Agents" changed from the
amber `.link-act` text link to a standard `.btn btn-sm` icon+text button. Also fixed a layout bug the
History change exposed: the section was `flex-1` inside an overflowing pane, crushing the button group to
4px (unclickable) — made History natural-height (dropped `flex-1`/`min-h-0`, `.tri-tabs` `flex-shrink:0`,
timeline `min-height:120` within the base `.tl` 230px scroll). Verified in-browser: History buttons 31px
& clickable, panel 277px, toggle/deselect work; Model version popout opens rounded with a 6px gap; Details
badge solid uppercase PENDING; Link Agents a bordered button. Bumped README wireframe pointer v9p2 → v9p3.

Files: `agent-dashboard/design/ui-concept-v9p3.html` (new), `agent-dashboard/README.md` (edited)

### 2026-06-20 06:51:20 — Dashboard mockup v9p4 (Settings panel)
Branched `ui-concept-v9p4.html` from v9p3 (byte-identical copy, then additive only — base 3-pane UI
untouched: diff = 7 deliberate base-line changes + 452 pure additions). Adds a title-bar gear that
opens a step-into full-window Settings view (toggles in/out over the body; not a 4th column, not a
floating popup; Close/Esc returns to the 3-pane). Subject tabs Usage · MCP · Plugins · Config ·
Setups, with scope as a secondary segment inside MCP/Plugins/Config. Read-only status/health/usage
kept visually separate from editable config; global (~/.claude) edits gated behind an explicit
confirm; Config rows tagged LIVE vs NEW SESSION per the CLI lifecycle map. Footer keeps glanceable
Save/Load → Setups and the token pill → Usage. Content grounded to this machine (8 connected MCP
servers + parked set, 5 installed plugins, real hooks/env/models). Verified all 5 tabs render in
Playwright. Note: the prompt's version numbers were swapped vs disk (v9p3 is the latest, no v9p4
existed), so the new file is v9p4 branched from v9p3.

Files: `agent-dashboard/design/ui-concept-v9p4.html` (new)

### 2026-06-20 06:56:17 — README synced to v9p4 (Settings panel documented)
Made the dashboard README current with v9p4: bumped the "current wireframe" pointer v9p3 → v9p4,
acknowledged the Settings step-into view in the no-popups principle, noted the title-bar gear in the
Layout section, added a new **Settings (step-into view)** panel subsection (subject tabs + scope
segment table, read-only/editable separation, gated global edits, non-duplication of the Agent panel,
footer shortcut), and listed the Settings component kit under Design system → Core components.

Files: `agent-dashboard/README.md` (edited)

### 2026-06-20 07:08:36 — Dashboard mockup v9p5 (cream content surface)
Branched `ui-concept-v9p5.html` from v9p4 (additive: 10 base-line changes + the changelog comment).
Panel/tab content areas now use canvas cream (--background #fef6e4) as their background surface,
matching the Team Graph well that already did — flipped the Agent body, Prompts body (Source/Target
column + Compose/Library/History), Team Feed body, the four feed tab wells (Messages/Scratch/Log/
Requests), the 3-pane frame (.rz-group.horizontal), and the default .pcard-body from white to cream.
Discrete components (cards, inputs, selector fields, agent-row lists, menus, chrome headers/footers)
keep their fills so they pop on cream, exactly like Team Graph cards. The Settings step-into view
(.set-* / .settings-view) is deliberately unchanged. Verified in Playwright (3-pane + Settings).

Files: `agent-dashboard/design/ui-concept-v9p5.html` (new)

### 2026-06-20 07:17:52 — Dashboard mockup v9p6 (agent lists hug content + scroll)
Branched `ui-concept-v9p6.html` from v9p5 (3 base-line changes). The persistent agent-row lists —
Prompts → Target (#prompt-targets) and Team Feed → Filter — now hug their content instead of
stretching to fill the column: swapped `flex-1` → `flex-initial` (flex:0 1 auto) on both `.aglist`s.
They keep `min-height:0` + `overflow-y:auto`, so when a pane is resized too small to fit the rows the
list shrinks and scrolls vertically inside its bounded column. Verified the gradient in Playwright:
full size hugs all rows (no scroll), ~520px panel shows ~8 rows + scrolls, 230px shows ~1 row +
scrolls; Feed Filter scrolls when the window is short. Source list unaffected (already a scrolling
dropdown); Settings unaffected.

Files: `agent-dashboard/design/ui-concept-v9p6.html` (new)

### 2026-06-20 07:38:25 — v9p6 fixes: list scrollbar + Prompts footer anchoring
Fixed two real bugs in v9p6 found on review (verified in Playwright with actual window + splitter
resizes, not just measuring scrollHeight). (1) No scrollbar: the base `.aglist{overflow:hidden}`
(corner-clipping) silently overrode Tailwind's `overflow-y-auto`, so the Target/Filter lists clipped
with no scrollbar — added higher-specificity `.aglist.aglist-scroll{overflow-y:auto}` and tagged both
lists. (2) Prompts footer detaching: the splitter resizer set `flex:'0 0 Npx'` (fixed, no shrink), so
after any splitter drag the Team Graph stopped shrinking on window resize, overflowed the stacked
middle column, and pushed the Prompts footer off-screen (the Feed, a single panel, was immune). The
resizer now sets flex-GROW proportions (`Npx 1 0`), keeping panels responsive/shrinkable after a drag.
Verified: scrollbars appear on both lists; all three panel footers stay anchored after drag+resize
down to ~400px tall.

Files: `agent-dashboard/design/ui-concept-v9p6.html` (edited)

### 2026-06-20 19:55:00 — Added 4 loose notes to dashboard "Next up"

Folded A1 Context Cutoff Shading, A2 Turns Own Line, A3 Documentation Panel (houses Plan interface +
README/CLAUDE tabs), and A4 Main Layout Reconfig (Agent · Team Graph · Documentation · Feed · Prompts)
into Section A of `docs/human-notes-misc.md`; emptied the Loose-notes bucket.

Files: `docs/human-notes-misc.md` (edited)

### 2026-06-20 16:30:00 — Plan-tab concept set for the Documentation panel

New `agent-dashboard/design/ui-snipets/plan-tab-concepts.html` — a live, neobrutalism (v9p6-token)
concept set exploring a Plan tab inside the planned Documentation panel, grounded in Claude Code's real
native planning (local Plan Mode → markdown plans in `plansDirectory`; Ultraplan cloud planning with
Simple/Visual/Deep variants, inline-comment review, teleport-to-local vs cloud→PR execution). Five
interactive concepts: 1 Plan Library (master–detail), 2 Section review (comments+reactions+outline),
3 Approve→Execute (gate→Requests, target chooser, clear-context toggle, live TodoWrite checklist),
4 Ultraplan launcher (variant picker + cloud status), 5 Versions & diff. Verified all interactions
render and fire in-browser. Addresses backlog C4 + the Documentation-panel loose note.

Files: `agent-dashboard/design/ui-snipets/plan-tab-concepts.html` (new)

### 2026-06-20 09:47:42 — Dashboard mockup v9p7: cutoff shading, Turns line, Documentation panel, layout reflow

New `agent-dashboard/design/ui-concept-v9p7.html` (branched from v9p6) implementing backlog A1–A4.
(A1) Context usage bars gray out the region above an 80% cutoff via a hatched `.bar-cut` overlay +
marker line — applied to all 13 Team Graph card bars, the Agent-panel summary bar, and the breakdown
bar (JS-built bars read `window.CTX_CUTOFF`). (A2) "Turns n/max" moved to its own line above the
bar+% row on every card. (A3) New **Documentation** panel: tabs Plan · README.md · CLAUDE.md ·
TODO.md (+ an add-doc affordance). Plan = expandable plan cards with step checklists and
Review/Edit/Approve·Reject (incl. an Ultraplan entry, per C4); the three file tabs are a doc viewer
with a path chip, Copy, and an Edit toggle (rendered view ↔ mono textarea). (A4) 3-pane frame
reflowed to reading order Agent · Team Graph · Documentation · Feed · Prompts — middle column now
splits Team Graph/Documentation, and a new right column splits Feed/Prompts (Prompts relocated from
the middle column; all ids/handlers preserved). Verified in-browser: layout, cutoff shades (13+1+1),
Turns line, all doc tabs + edit toggle, and the new Feed/Prompts splitter all render and work.

Files: `agent-dashboard/design/ui-concept-v9p7.html` (new); `.scratch/v9p7_reflow.py` (transform helper)

### 2026-06-20 17:24:17 — Dashboard mockup v9p8: Feed "Requests"→"Inbox" + Plan⇄Inbox Review cross-link

New `agent-dashboard/design/ui-concept-v9p8.html` (branched from v9p7; layout unchanged). Renamed the
Feed's **Requests** tab to **Inbox** (visible label + pending-badge tooltips only; internal id/data-tab
stays `requests`, so `switchTab('feed','requests')` and `statusJump('pending')` are untouched).
Added a **Review** button to Approval-type Inbox cards (placed Approve · Review · Reject) that calls a
new `reviewPlan(planId)` → switches Documentation to the **Plan** tab, expands the matching plan card,
scrolls it into view, and flashes it (new `.plan-flash`, mirroring `.reply-flash`) — the intended
Inbox→Plan cross-link, not a merge of the surfaces. Aligned demo data so the jump lands on the same
item: the 01-sandy Approval card targets `plan-1` (the "In review" Auth token-rotation remediation
plan; its owner set to 01 sandy). Reply→Compose unchanged. Verified in-browser: Inbox label + badge,
Review button renders, and the jump expands+flashes the right plan; no new console errors. Also updated
`agent-dashboard/README.md` (Team Feed/Requests sections) for the rename + Review control.

Files: `agent-dashboard/design/ui-concept-v9p8.html` (new); `agent-dashboard/README.md` (edited)

### 2026-06-20 17:55:42 — Concept set: Prompts agent-selector as a side drawer (3 options)

New `agent-dashboard/design/ui-snipets/agent-filter-drawer-concepts.html` — a standalone, self-contained
concept set (tokens/classes ported ~1:1 from v9p8; agent game-icon symbols spliced in) exploring how to
move the always-on ~164px Source/Target column out of the Prompts panel so Compose gets full width,
reusing existing components (`.agrow`/`.agtile`, `.src-dd`/`.src-pop`, `.sec-h`, All/None mini-link).
Three interactive options side by side: **(1) Slide-over drawer** — full-width compose + a slim "To"
summary bar of target tiles; click opens an overlay drawer with Source + Target. **(2) Collapsible icon
rail** — the column collapses to a 52px rail of color tiles (selected ones lit) and expands back, inline,
no overlay. **(3) Header popovers** — no column; From/To become dropdown triggers in a thin sub-header,
the To trigger showing selected tiles + a count. Each carries pros/cons; the winner applies 1:1 to the
Feed → Inbox filter (same list). Verified all three render + interact in-browser (drawer open/close, rail
collapse, To popover); only a favicon 404 in console.

Files: `agent-dashboard/design/ui-snipets/agent-filter-drawer-concepts.html` (new)

### 2026-06-20 18:23:03 — Concept set: header-dropdown agent filters with identity badges

User picked the header-dropdown direction (Option 3) for ALL agent filters. New
`agent-dashboard/design/ui-snipets/agent-filter-badges-concepts.html` — self-contained (ported tokens +
spliced agent icons) — explores the multi-select trigger filling with rich **identity badges** (icon +
role + number·name, same info as a list row), with the multi trigger locked to the **same height as the
single From/Source dropdown** and overflow collapsing to a `+N` chip. Three badge formats compared:
**A** two-line list format (role shrinks at one-row height), **B** one-line with the icon stamped
full-height (cleanest/densest), **C** one-line name + faded role (widest). Shown in context on both
panels: Prompts (From + To, format A) and Feed (Filter, format B). Verified in-browser: triggers open,
rows toggle, badges + `+N` render, From/To heights match; no console errors.

Files: `agent-dashboard/design/ui-snipets/agent-filter-badges-concepts.html` (new)

### 2026-06-20 18:37:27 — Dashboard mockup v9p9: agent selectors → header dropdowns with identity badges

New `agent-dashboard/design/ui-concept-v9p9.html` (branched from v9p8). Implemented the chosen concept
(Option 3 + badge format C) across the real dashboard: both the Prompts Source/Target column AND the
Feed Inbox Filter column (always-on ~160px identity-row lists) are removed and replaced by a thin header
**sub-bar of dropdown triggers** — Prompts: **From** (single) + **To** (multi); Feed: **Filter** (multi).
Compose and the feed streams now span full panel width. The multi triggers fill with identity **badges**
(format C: full-height stamped agent icon + one-line number·name + faded role), locked to the **same
height as the single From trigger** (`.dd-trig`, 40px); overflow collapses to a `+N` chip. Reused the
existing agent rows, `.src-pop` popovers, All/None link, and `pickSource`/`toggleAgRow`/`agSync`/
`agAllNone`; added `.subbar`/`.dd-trig`/`.badge-c`/`.badge-more` CSS, `toggleSrcPop()`, `updateAgBadges()`;
`pickSource` now targets `.dd-trig` and `replyTo()` refreshes the To badges. Verified in-browser: From/To
heights equal (40px), badges update on toggle/All-None, popovers open with a sticky header, Inbox Reply
still routes to Compose + selects the target (reflected in badges), pickSource updates From; only a
favicon 404. Updated the README layout-note to cover v9p9. README Panels prose sync stays under E3.

Files: `agent-dashboard/design/ui-concept-v9p9.html` (new); `agent-dashboard/README.md` (layout note)

### 2026-06-20 19:58:12 — Dashboard v9p9: agent badges → two-line (role over number·name)
Switched the identity badges in the Feed Filter and Prompts To dropdowns from a one-line
role-suffix to a two-line stack (faded role over number·name) to save horizontal space. Full-height
stamped icon kept; badge height 32px inside the unchanged 40px trigger; "+N" overflow intact.
Updated .badge-c CSS (.b-lab/.b-role/.b-name), updateAgBadges() render, and the file's header changelog.
Files: agent-dashboard/design/ui-concept-v9p9.html

### 2026-06-20 20:09:40 — README: layout note reflects two-line badges
Updated the agent-dashboard README layout note (E3 placeholder) to describe the Feed/Prompts header
dropdowns as filling with two-line identity badges (tile + role over number·name, mirroring list rows)
— keeping the doc in sync with the v9p9 badge change made this session.
Files: agent-dashboard/README.md

### 2026-06-20 20:20:00 — Added 9 loose notes to dashboard "Next up"

Folded A5–A13 into Section A of `docs/human-notes-misc.md`: Prompt Panel Rename, Doc Line Numbers,
Doc Tab Names, TODO Tab Order, Messages Header Surface, Plan Navigation Pane (from
ui-snipets/plan-tab-concepts.html option 2 + TLDR), Unify Agent Badges, Summarize Overlay, Share
Target Picker. Emptied the Loose-notes bucket.

Files: `docs/human-notes-misc.md` (edited)

### 2026-06-20 21:14:33 — Dashboard mockup v9p10: Documentation/Plan review system + unified expandable cards
Branched v9p9 → ui-concept-v9p10.html and implemented 11 changes: Prompts→Prompt rename; doc tabs
reordered (Plan·TODO·README·CLAUDE) with ".md" dropped; Plans heading → "~/.claude/plans/" path chip
with per-card filenames; expanded plan body is a faithful line-numbered markdown render of the native
CC plan file (lineMd()), README/CLAUDE/TODO viewers line-numbered the same way; per-plan nav rail
(Outline/Feedback) over the file's ## sections with 3-state stroke-icon verdict tallies (Approve/Revise/
Block), responder popovers + comment cards, and a shared "Send for review" control; TL;DR per plan;
two-line agent badges unified across Plan headers + Feed (Messages/Scratch/Log) + History via one
badgeHTML(); Feed/History became expandable cards with a header checkbox for multi-select (Inbox joins
via the same checkbox, keeps its own actions); transparent Messages filter row; Summarize slide-over
overlay; one reusable Share/Review send-to-agents control. Feed/History/Plans/docs are now data-driven
renderers. Verified in-browser: 0 JS errors, verdict popovers, Feedback mode, summarize toggle, share
send toast, expand + checkbox select, Inbox checkboxes, line-numbered TODO/README all working.
Files: agent-dashboard/design/ui-concept-v9p10.html

### 2026-06-20 20:45:00 — Added 11 Documentation/Plan loose notes to dashboard "Next up"

Folded A14–A24 into Section A of `docs/human-notes-misc.md` (Plan/Messages action groups, Plan header
order, plan dir line, filename style, nav-pane cleanup, header counts row, comment popout, plan dates,
nav-pane outline + cream doc surface, doc textarea fill, overall Documentation polish). Merged the
duplicate "fix Send group in Messages" note into A14. Emptied the Loose-notes bucket.

Files: `docs/human-notes-misc.md` (edited)

### 2026-06-20 22:38:00 — Dashboard mockup v9p11: Documentation/Plan polish pass

Branched ui-concept-v9p11.html from v9p10 (full copy → targeted edits; everything else preserved) and
worked the 24-item handoff. Most v9p7–v9p10 items were already in place; this pass refines the rough ones.
Changes: context cutoff shade → clean solid translucent gray (was a 45° hatch); sticky Messages filter
row sits on the cream canvas; PLAN HEADER rebuilt into two rows — row 1 leads with the owner badge then
state/title/Ultraplan (item 15), row 2 is a meta strip with the plain-mono filename (item 17), a counts
strip (steps done + Approve/Revise/Block tallies, item 19), and created/edited dates (item 21); NAV PANE
is now an outlined fixed-width hug with a real Feedback count badge and self-contained, clamped feedback
cards (items 10/18/22); a COMMENT POPOUT docks under the plan body (same width) with a minimal header
(verdict icon · section · agent badge · time) opened by the in-text verdict chips and the nav cards
(item 20); PLAN FOOTER now reads Edit · Share · Review(teal) with Reject/Approve right-justified, and the
Feed Messages Share group is simplified — both match the Revise split styling (leading chevron, no subject
icon, paper-airplane-only action, no "Send" text) (items 13/14). Plan-tab top line is a plain mono
"~/.claude/plans/" line like Scratch (item 16). Interpretations flagged to user: item 14 "Messages footer
reads Edit·Share·Review" read as a slip for the Plan footer; item 9 → cream (not transparent). Could not
screenshot: the MCP browser profile is locked by another instance and the headless Chromium's network
service crashes on the CDN deps in this sandbox — validated statically instead (JS node --check passed;
all onclick handlers defined + wired; all edits string-matched).
Files: agent-dashboard/design/ui-concept-v9p11.html (new)

### 2026-06-20 21:10:00 — Added 16 v9p11 refinement notes to dashboard "Next up"

Reviewed current mockup ui-concept-v9p11.html (Documentation/Plan polish) to confirm state, then
folded 16 Loose notes into Section A of `docs/human-notes-misc.md` (Plan header 3-row, warning icon,
footer button heights, doc-tab surface fix, teal Share group, nav width, chevron right, inline badge
dot, render line differentiation, line/section index rail, user Comment button, verdict text colors,
comment popup badges, Revise label trim, comment agree/save, Plan Revise action). Merged the duplicate
"index rail for all tabs" note into A10. Left the separate "## Scratch" section untouched.

Files: `docs/human-notes-misc.md` (edited)

### 2026-06-20 21:25:00 — Added 1 loose note to dashboard "Next up"

Folded A17 Nav Card Layout (agent badge + thumbs toggle first line; merged verdict badge + section/
line badge second line) into Section A of `docs/human-notes-misc.md`; emptied the Loose-notes bucket.
The separate "## Scratch" section remains untouched.

Files: `docs/human-notes-misc.md` (edited)

### 2026-06-21 07:20:00 — Dashboard mockup v9p12: Documentation/Plan line+section commenting rework

Branched ui-concept-v9p12.html from v9p11 (full copy → targeted edits; everything else preserved) and
implemented the 17-item handoff. Plan card header rebuilt into 3 rows (owner badge·title·state /
feedback badges·"done/total steps" / filename·created+edited with date-time + relative "ago"); expand
chevron moved to the right. Introduced a shared DOC EDITOR (mdEditorHTML) used by Plan bodies AND the
README/CLAUDE/TODO tabs: an interactive left rail indexes every line + section, click-selects a line or
a whole section, and shows section feedback as a verdict badge in the rail (inline in-text chips + the
pink dot removed). New comment flow: a "Comment" split (Approve/Revise/Block, upload icon) before Edit,
enabled on selection, opens a composer in the docked popout — user badge, thumbs up/down agree toggle
(default up), optional textarea, Save; viewing existing comments uses the same popout with a merged
color-coded verdict badge + section/line badge and a per-response thumbs toggle. Nav Feedback cards
restructured (badge+thumbs / verdict badge + section badge / comment); nav pane widened. Footer: equal
button heights, teal Revise before Reject, teal Share group; right trio grouped + right-justified. Doc
tabs are a single filling editor (no overlapping card+textarea), labels title-cased (Plan·Todo·Readme·
Claude). Warning verdict icon → triangle-alert; Revise split label trimmed to the setting; inline code
chips tinted teal to read apart from body text; verdict text color-coded throughout. Verified in-browser
over a local http server (file: is blocked by the MCP browser): 0 console errors; confirmed the 3-row
header, rail badges, comment popout, Feedback nav cards, Readme rail + composer, and the regrouped footer.
Files: agent-dashboard/design/ui-concept-v9p12.html (new)

### 2026-06-21 07:50:00 — Added a UI-verification rule to project CLAUDE.md

Added a Behavioral-rules bullet forcing browser verification of UI changes before hand-off: serve over
http://localhost, resize affected panel(s) to narrow + wide extremes, click through every control
touched, screenshot + compare to intent + fix — static checks (node --check/grep) are explicitly not
sufficient. Aimed at cutting the back-and-forth on the dashboard mockups.
Files: CLAUDE.md (edited)

### 2026-06-21 07:52:00 — Headless-by-default note added to the UI-verification rule

Extended the Behavioral-rules UI-verification bullet in project CLAUDE.md: run the Playwright MCP
browser `--headless` for the whole resize/click/screenshot loop (so it doesn't steal focus while the
user works), then finish with one **headed** parity pass to confirm rendering matches before reporting.
Made the headed pass a hard rule (every UI change, not "only if you suspect a difference") but scoped it
light — re-screenshot the touched states at the narrow/wide extremes and compare, not a full re-drive.
Files: CLAUDE.md (edited)

### 2026-06-21 08:20:00 — Dashboard mockup v9p13: Documentation/Plan audit + execution-defect fixes
Branched ui-concept-v9p13.html from v9p12 (full copy → targeted edits; everything else preserved) and
ran a live headless-Chromium audit of the v9p11/v9p12 rework against the two handoff lists. Fixed the
big one the user flagged ("nav card contents not even in the cards"): the Plan Feedback nav cards were
structurally broken — `fb-card` was a `<button>` wrapping the thumb-toggle `<button>`s, so the parser
closed the card early and the thumbs/verdict/section/comment all rendered OUTSIDE the card on the cream
nav. Made `fb-card` a `<div role=button>`; every row now sits inside its card (badge+thumbs / verdict+
section / comment), verified across all three feedback cards. Also flattened the identity badge (`.badge`
→ no offset shadow) everywhere it's a label — plan header, feed/scratch/log + history cards, nav cards,
comment popout, AND the From/To/Filter dropdown triggers — per the neobrutalism "shadows = interactive"
rule the user called out; the dropdown still reads as a control via its field border + chevron. Kept nav
row 1 (badge + thumbs) on one line in the 180px rail (badge shrinks; nav thumb trimmed 24→22px so a full
"researcher" role label fits). Verified live: nav feedback cards, plan header, comment popout, README rail
tab, footer, feed cards, filter trigger, and a full-dashboard parity render. All script blocks parse.
Files: agent-dashboard/design/ui-concept-v9p13.html (new)

### 2026-06-21 09:30:00 — Dashboard mockup v9p14: Plan-card resize fixes, turns bars, labels, delineation
Branched ui-concept-v9p14.html from v9p13 (full copy → targeted edits; everything else preserved) and
worked a 14-item handoff with emphasis on resize/layout that needs live testing. Headline fixes (all
verified in headless Chromium): (A1) the Plan nav is now a flex column that stretches to the text
column's height, so the feedback cards aren't clipped when the comment UI opens — measured nav 358→487px
on open, with the list scrollbar flush to the nav edge (gap 0); widened to 212px so each card's verdict +
section badges sit side by side. (A2) a neutral Copy·Edit·Comment strip now sits under the text box with
the comment popout/composer opening BETWEEN the text and the strip (popAboveStrip verified). (A3) footer
Share·Review left / Revise·Reject·Approve right, labels sized to match. (A4/A5) selected text highlights
light pink; left rail cells color-coded (pink title = select-all, dark teal section, light teal line) with
re-click-to-clear (toggle + select-all logic verified). (A12/A13) agent cards + the Agent panel show
TURNS as a labeled health bar (panel "History"→"Turns" with inline count·bar·%, then Rewind/Handoff).
(A8/A11/A14) Mode FREE!→Bypass; Thinking→Thoughts, Metadata→Meta; full-width "Opus fast-mode"/"Thinking
mode" toggles. (A10) count badges squared. (A7) resize-nub removed, 3px navy panel dividers. (A9) proposed
a slash-command approach (Compose palette scoped by Target) in the changelog. All script blocks parse.
Files: agent-dashboard/design/ui-concept-v9p14.html (new)

### 2026-06-21 12:00:00 — Folded loose notes into dashboard "Next up" (A1–A14)
Cleaned 16 loose notes against ui-concept-v9p13.html into Section A of docs/human-notes-misc.md as A1–A14 (numbered, bold-headered). Dropped 2 as already implemented: doc rail line/section indexing (v9p12) and flat non-interactive badges (v9p13). Loose notes bucket emptied; Scratch left untouched.
Files: docs/human-notes-misc.md, DEVLOG.md

### 2026-06-21 13:10:00 — Dashboard v9p14 tweaks (Plan footer regroup, nav-card selection) + README sync
Three in-place tweaks to ui-concept-v9p14.html, each verified live in headless Chromium: (1) the Plan
action strip is now FULL-WIDTH (spans under the nav pane + text), with Copy·Edit·Comment left and
Share·Review pulled up from the footer and right-aligned; the footer below the divider is just the
decision trio (Revise·Reject·Approve, right). (2) Feedback nav cards are now selectable like other cards —
light-teal fill that persists until you deselect (re-click) or close the popout, and selecting one
highlights its section in the plan text (teal, linking card↔text); verified select/toggle/close + that
the nav still resizes with the comment UI (320→449px). (3) removed the nav's horizontal overflow at the
root (cards were width:100% + 7px margin → overflowed; set width:auto), so no horizontal scrollbar.
Then synced agent-dashboard/README.md to current design intent: mockup pointer v9p4→v9p14; rewrote the
layout note; Team Graph now describes the dual Turns+Ctx labeled bars; Agent panel Mode Bypass + the
"Opus fast-mode"/"Thinking mode" toggles + the Turns readout; Feed Messages toggles →Thoughts/Meta; added
a full **Documentation (middle, bottom)** panel section (doc editor, plan review system, nav rail,
comment popout, action strip + decision footer, Inbox cross-link); and design-system notes for the 3px
panel dividers (grip nub removed), rounded-square + flat badges, and the pink/teal selection roles.
Files: agent-dashboard/design/ui-concept-v9p14.html, agent-dashboard/README.md

### 2026-06-21 14:20:00 — Dashboard v9p14: Plan footer back to one strip, Comment→button, 3-indicator sync
Reverted the separate upper action strip (the grouping wasn't working): **all plan actions live in the one
shared footer again** — Copy · Edit · Comment · Share · Review left-aligned, the decision trio (Revise ·
Reject · Approve) right-justified; wraps to a 2nd row on the narrow Documentation column (verified). The
**Comment** control is now a plain icon button (the upload action + verdict split are gone); the verdict
moved INTO the composer as a **"Mark as" dropdown** (Approve/Revise/Block, color-coded) — Save reads it.
Made the three feedback indicators move in lockstep: openCmtPop is the single sync point, so selecting a
Feedback card OR clicking the in-text rail-gutter badge fills the card (teal) + highlights its section
(teal) + opens the popout; closing/deselecting clears all three; a different comment switches all three
(added data-fbsec/fbverdict + selectMatchingCards; verified from both entry points incl. switch + toggle).
Synced the README Documentation bullets (shared footer, Comment button + Mark-as dropdown, the linked
three-indicator selection). All script blocks parse.
Files: agent-dashboard/design/ui-concept-v9p14.html, agent-dashboard/README.md

### 2026-06-21 13:30:00 — Refreshed dashboard "Next up" against v9p14 (A1–A2)
Cleared old A1–A14 (all implemented in ui-concept-v9p14.html per its changelog) and folded 2 new loose notes into Section A of docs/human-notes-misc.md: A1 Plan Footer Grouping, A2 Nav Card Selection. Loose notes bucket emptied; Scratch left untouched.
Files: docs/human-notes-misc.md, DEVLOG.md

### 2026-06-21 06:10:00 — Deleted old sandbox .git; routed session-exports + plans out of repo root
Removed the carried-over `.git/` (145MB, 161 commits, still pointed at the old `claude-code-sandbox` remote) so the new repo starts on clean history. Configured the claude-history-viewer extension to write session exports to `.claude/cc-exports/` (setting `claude-history.export.directory`) and gitignored that dir (personal transcripts + .source.jsonl sidecars); moved the existing migration export there and removed the root `cc-exports/`. Set Claude Code `plansDirectory` to `./.claude/plans` so plans land in-repo. Both settings JSON validated; dirs created with .gitkeep. Not yet self-tested live (export = extension UI action; plans = read at session start) — verify on next window reload / plan-mode task.
Files: .gitignore, .vscode/settings.json, .claude/settings.json, .claude/cc-exports/ (moved), .claude/plans/ (new)

### 2026-06-21 06:18:00 — Fixed cc-exports redirect (multi-root scope bug); plans confirmed working
Root cause of exports still landing in repo-root `cc-exports/`: the claude-history-viewer extension reads `claude-history.export.directory` via a scope-less `getConfiguration`, which in a multi-root workspace ignores folder `.vscode/settings.json` and only sees user + workspace-file settings. Moved the setting into the `awl-cc-dash.code-workspace` `settings` block and removed the ineffective folder-level line. Consolidated 2 stray root exports into `.claude/cc-exports/` and removed the recreated root dir. Requires a VS Code window reload to take effect, then re-test. Separately confirmed `plansDirectory` works — the test plan wrote to `.claude/plans/`, not global.
Files: .vscode/awl-cc-dash.code-workspace, .vscode/settings.json, .claude/cc-exports/ (consolidated), DEVLOG.md

### 2026-06-21 06:25:00 — Confirmed cc-exports redirect working after reload
User reloaded VS Code and verified session exports now write to `.claude/cc-exports/` (not repo root). Closes out the multi-root scope fix. State: clean repo (old `.git` removed, not yet re-init'd); exports + plans both routed in-repo and confirmed working.
Files: DEVLOG.md

### 2026-06-21 06:42:00 — Pre-commit cleanup: quarantined archived transcripts; annotated migration doc
First-commit pre-flight found 22MB of personal Claude transcripts in `archive/cc-exports/` (incl. a 14.7MB .jsonl) that would have been baked into history. Kept `archive/` per request; created `archive/_ignored/` (name signals untracked), moved the old cc-exports there, and gitignored it. Commit payload dropped 33.6MB→12.1MB / 162 files; no secrets staged. Added a prominent "SUPER TENTATIVE — reference only" banner to the top of `dev/notes/repo-migration.md`. Repo now clean for first commit (fresh `git init -b main`, no remote yet).
Files: .gitignore, archive/_ignored/ (moved cc-exports in), dev/notes/repo-migration.md, DEVLOG.md

### 2026-06-21 06:55:00 — First commit + push to awl-cc-dash remote
Pre-flight verified: fresh git init (main, identity AdamWardLester), no secrets staged, 12.1MB payload. Removed the throwaway plansDirectory test plan from staging. Added remote origin (github.com/adamwlester/awl-cc-dash), committed 161 files as 768c47c "Initial commit", pushed -u origin main (clean history, first commit). Structure at commit: frontend/ sidecar/ bridge/ (was tools/cc_tmux_bridge) design/ dev/tools/ (bootstrap-env + context-extractor) tests/ archive/ (transcripts quarantined in archive/_ignored/).
Files: (git) initial commit 768c47c, DEVLOG.md

### 2026-06-21 07:05:00 — Refactored bridge imports after rename/move; test suite green again
Got the bridge test suite working after `tools/cc_tmux_bridge` → root `bridge/` rename and `tools/` → `dev/tools/` moves. Package internals were already relative-import based (no change needed). Functional fixes: conftest.py now adds the repo root to sys.path and imports `from bridge import TmuxBridge`; test_tmux_bridge.py imports `from bridge.bridge import TmuxBridgeError`. Standardized the venv on `.venv` (matches new .gitignore) — updated tests/run.ps1 and .vscode interpreter path off the stale `claude-code-sandbox-env`. Created `.venv`, installed requirements.txt (pytest+claude-agent-sdk+dotenv). Coherence updates for the rename: logger name, cli/__main__ docstrings, bridge/README.md, tests/README.md, and the CLAUDE.md bridge import/CLI section. Verified: 27 tests collect; live `test_list_empty` + `test_send_to_nonexistent_errors` pass against real WSL2/tmux (via both pytest and tests/run.ps1). Did not run the 24 tests that spawn paid live Claude sessions. Deferred: broader sandbox→dashboard CLAUDE.md rewrite (folder map, Testing venv name).
Files: tests/conftest.py, tests/test_tmux_bridge.py, tests/run.ps1, tests/README.md, .vscode/settings.json, bridge/bridge.py, bridge/cli.py, bridge/__main__.py, bridge/README.md, CLAUDE.md, requirements (.venv created), DEVLOG.md

### 2026-06-21 07:12:00 — Gitignored electron-vite out/ build output
Handled the stray archive/mvp working-tree changes: the 7690→7691 port bumps (preload/App/sidecar) and the new frozen requirements.txt are intentional (archived MVP made independently runnable), so kept as-is. Only actionable was the untracked build dir — added `out/` to .gitignore (covers frontend/ and archive/mvp/frontend/). Verified archive/mvp/frontend/out/ is now ignored.
Files: .gitignore, DEVLOG.md

### 2026-06-21 07:30:00 — Verified CLAUDE.md rewrite; removed last stale ref
Checked live repo state (another agent had already rewritten CLAUDE.md: awl-cc-dash project identity, product/build-workflow folder map, .venv Testing section). Confirmed all 9 folder-map dirs (frontend/sidecar/bridge/design/archive/assets/tests/docs/dev) exist and match. Only residual sandbox-ism was a `tools/claude-export/` history footnote in the context-extractor section — removed it. No other stale tokens (agent-dashboard, projects/, claude-code-sandbox-env, cc_tmux_bridge) remain.
Files: CLAUDE.md, DEVLOG.md

### 2026-06-21 07:50:00 — Full bridge suite: 25/27 pass; 2 failures are environment, not the refactor
Ran the complete integration suite via .venv (2:41). 25 passed — all core bridge ops (create/send/read/status/rename/resume/batch/broadcast/interrupt/scrollback/wait_idle/show/set_cwd/set_model/mcp_sync/read_log). 2 failed: test_send_and_response and test_watch, both `TmuxBridgeError: Timed out waiting for pattern`. Root cause is environmental, not the import refactor: the captured tmux pane renders at a tiny width (model's marker reply wraps across lines so the literal watch pattern can't match) and shows a Claude Code "startup hook error" banner. Proven not-the-refactor: the failures are model-output timeouts (bridge sent prompts + polled correctly), and the 25 passing tests fully exercise the renamed/moved package. Refactor validated. The narrow-pane/startup-hook issue in the WSL Claude session is a separate pre-existing env problem to chase if desired. Full log: .scratch/full-suite-run.log.
Files: DEVLOG.md

### 2026-06-21 07:58:00 — Bridge suite fully green after window-sizing fix
Re-ran the 2 prior failures (test_send_and_response, test_watch) after the FancyZones narrow-window issue was fixed — both PASS (plus test_watch_timeout). Confirms the suite is effectively 27/27; the earlier 2 failures were purely the squished tmux pane wrapping the model's marker reply, nothing in the code or migration. Bridge refactor fully validated end-to-end.
Files: DEVLOG.md
