# Frozen MVP — original working dashboard reference

This is a **frozen, runnable copy of the original AWL dashboard MVP**, kept for reference
while the real app is rebuilt in the repo-root `frontend/` and `sidecar/`.

> **This is a reference, not the build target.** Do not develop features here. The live build
> lives at the repo root. This copy exists only so the original end-to-end behavior stays
> runnable and inspectable.

It runs on **port 7691** (the live build uses 7690) so the two never collide.

- **`frontend/`** — Electron + React (electron-vite). The entire UI is one `src/renderer/App.tsx`.
- **`sidecar/`** — FastAPI service (`sidecar/main.py`) behind a pluggable **driver seam**
  (`drivers/` + shared `serialize.py`), mirroring the repo-root build. The default `sdk` driver
  drives the `claude_agent_sdk` `ClaudeSDKClient` in-process; a `bridge` driver (real Claude Code
  TUI via tmux/WSL2) is selectable with `AWL_DRIVER=bridge` or the per-session `driver` field.
  Endpoints: `/health`, `/sessions` CRUD, `/send`, `/history`, `/sessions/{id}/events` (SSE),
  `/interrupt`, `/model`, `/mode`, `/context`.
  > Note: the `bridge` driver imports the repo-root `bridge` package, which is **not bundled
  > inside this frozen copy** — selecting it here won't resolve. The verified path is the default
  > `sdk` driver. (Same caveat as the live build, where the bridge path is implemented but not
  > yet live-verified.)

## Prerequisites

- **Python 3.12** and **Node.js** (tested on Node 24 / npm 11).
- The **`claude` CLI** must be installed and on your `PATH` — the Claude Agent SDK shells out to it.
  (`claude --version` should work.)

## Setup (one time)

### Sidecar (Python)
```powershell
cd archive\mvp
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
```
The venv (`archive/mvp/.venv/`) is gitignored.

### Frontend (Node)
```powershell
cd archive\mvp\frontend
npm install --legacy-peer-deps
```
`--legacy-peer-deps` is required: the lockfile pins `vite@8`, which is newer than
`electron-vite@5`'s declared peer range (`vite ^5–^7`). It installs and runs fine; the flag
just tells npm to accept the already-resolved tree. `node_modules/` is gitignored.

## Run

Two halves, in two terminals (sidecar first):

```powershell
:: 1) Sidecar — from archive\mvp
.venv\Scripts\python.exe sidecar\main.py
:: serves http://127.0.0.1:7691

:: 2) Frontend — from archive\mvp\frontend
npm run dev
:: launches the Electron window + a Vite renderer server on http://localhost:5173
```

Or just run **`start-mvp.bat`** (alongside this README) to launch both at once.

When it's up, the title bar shows a green **Connected** badge. Create a session (**+ New**),
type a prompt, and the event feed streams live events (session-init card, the
cost/turns/duration result bar, etc.), with the session's running cost updating in the left list.

### Browser-only check (no Electron window)
`npm run dev` also serves the renderer at `http://localhost:5173`. Opening that in a normal
browser works too — `App.tsx` falls back to the hardcoded `http://127.0.0.1:7691` sidecar URL
when it's not running inside Electron. Useful for headless UI testing.

> If a manual `npm run dev` crashes with `Cannot read properties of undefined (reading 'whenReady')`,
> your shell has `ELECTRON_RUN_AS_NODE=1` set (some IDE-integrated terminals do). It makes the
> Electron binary run as plain Node. Launch from a clean shell, or clear that variable first.
> (`start-mvp.bat` clears it for you, so launching via the `.bat` avoids this entirely.)

## Parity with the live build

This copy is kept **behaviorally in sync** with the repo-root `frontend/` + `sidecar/`: the only
intended difference is the port (7691 vs 7690). The earlier render gap — assistant text and
tool-call cards not appearing in the feed — has been **fixed here** to match the live build, via
the same two fixes:

- **Sidecar:** content blocks are serialized through `serialize.py`, which injects the `type`
  field (`TextBlock→text`, `ToolUseBlock→tool_use`, etc.) the renderer keys off — so text,
  tool-call, tool-result, and thinking blocks now render.
- **Frontend:** `App.tsx` reads assistant/user content from the flattened `event.content`
  (with the older `event.data.message.content` shape kept as a fallback).

## Known limitations (current SDK)

- The **"Rate limit — Claude is waiting before retrying"** banner shows on every turn even when
  the account is not throttled (it ignores the `allowed` status). This matches the live build's
  current behavior (unchanged).
