# Frozen MVP — original working dashboard reference

This is a **frozen, runnable copy of the original AWL dashboard MVP**, kept for reference
while the real app is rebuilt in the repo-root `frontend/` and `sidecar/`.

> **This is a reference, not the build target.** Do not develop features here. The live build
> lives at the repo root. This copy exists only so the original end-to-end behavior stays
> runnable and inspectable.

It runs on **port 7691** (the live build uses 7690) so the two never collide.

- **`frontend/`** — Electron + React (electron-vite). The entire UI is one `src/renderer/App.tsx`.
- **`sidecar/`** — FastAPI service (`sidecar/main.py`), **SDK-direct**: it drives the
  `claude_agent_sdk` `ClaudeSDKClient` directly (it does **not** use the tmux bridge).
  Endpoints: `/health`, `/sessions` CRUD, `/send`, `/history`, `/sessions/{id}/events` (SSE),
  `/interrupt`, `/model`, `/mode`, `/context`.

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

## Known limitations (current SDK)

- **Text and tool-call cards don't render in the feed under the current
  `claude-agent-sdk` (0.2.106).** The feed renders session-init cards, the rate-limit banner,
  and the cost/turns/duration result bar; assistant text, tool-call cards, and thinking blocks
  do not. Cause: the sidecar serializes the SDK's content blocks via `__dict__`, which yields
  e.g. `{"text": "..."}` with no `type` field, while `App.tsx` keys rendering off `block.type`.
  This is **frozen MVP behavior left intentionally unchanged** (no logic edits in this reference)
  — flagged here so the gap is expected, not a surprise.
- The **"Rate limit — Claude is waiting before retrying"** banner shows on every turn even when
  the account is not throttled (it ignores the `allowed` status). Also frozen as-is.
