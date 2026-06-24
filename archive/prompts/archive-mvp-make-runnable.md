# Task: make the frozen MVP reference runnable from `archive/mvp/`

## What this is
`archive/mvp/frontend/` and `archive/mvp/sidecar/` are a **frozen copy of the original
working dashboard MVP** — kept as a runnable reference while the real app is rebuilt in the
root `frontend/` and `sidecar/`. They have already been **moved into place by the user**;
your job is to make this archived copy **run on its own and prove it's functional**, then
document how to launch it.

- **frontend** — Electron + React (electron-vite). The entire UI is one `src/renderer/App.tsx`.
- **sidecar** — FastAPI service (`sidecar/main.py`), SDK-direct (drives `claude_agent_sdk`'s
  `ClaudeSDKClient`; it does **not** use the tmux bridge). Exposes `/health`, `/sessions` CRUD,
  `/send`, `/history`, `/sessions/{id}/events` (SSE), `/interrupt`, `/model`, `/mode`, `/context`.
- The frontend talks to the sidecar over HTTP and renders the live event feed.

## Hard constraints — read before touching anything
1. **Do NOT modify the live root `frontend/` or `sidecar/`.** Work only inside `archive/mvp/`.
2. **Do NOT edit any other `archive/` content** (the design lineage, prompts, sdk-spikes, etc.).
3. **This is a frozen reference — do not refactor its logic.** The only edits allowed are the
   minimum needed to make it *run* from the new location: dependency setup and the **port repoint**
   below. No feature changes, no restructuring, no "improvements."
4. **Stay inside the project directory.** Don't touch `~/.claude` or anything outside the repo.
5. **Log your work in `DEVLOG.md`** before you finish (append-only entry, per the DEVLOG rules
   in `CLAUDE.md`).

## Why a port change is required
The MVP defaults to **port 7690** — the same port the future live build will use. To let this
reference run without ever colliding with the live app, **repoint the archived copy to `7691`**.
The port is hard-coded in **three** places — change all three:

1. `archive/mvp/sidecar/main.py` — the `uvicorn.run(..., port=7690, ...)` call (near the bottom).
2. `archive/mvp/frontend/src/preload/index.ts` — `sidecarUrl: 'http://127.0.0.1:7690'`.
3. `archive/mvp/frontend/src/renderer/App.tsx` — the fallback near the top:
   `const API = (window as any).awl?.sidecarUrl || 'http://127.0.0.1:7690'`.

All three must read **7691** afterward.

## Setup

### Sidecar (Python)
`requirements.txt` is **incomplete** — it lists `claude-agent-sdk` and `python-dotenv` but the
sidecar also imports `fastapi`, `uvicorn`, `pydantic`, and `sse_starlette`. Create a dedicated
venv for this reference and install the full set:

- Create/activate a venv (keep it local and gitignored — e.g. `archive/mvp/.venv/`; confirm
  `.venv/` is ignored, add a pattern if not).
- Install: `claude-agent-sdk`, `python-dotenv`, `fastapi`, `uvicorn[standard]`, `pydantic`,
  `sse-starlette` (plus `pytest` if you want it).
- **Write a complete `archive/mvp/requirements.txt`** capturing exactly what you installed (pin
  versions if you can) so the reference is reproducible.
- The Claude Agent SDK shells out to the `claude` CLI — make sure that's available on PATH; note
  it in the README if it's a prerequisite.

### Frontend (Node)
- `npm install` inside `archive/mvp/frontend/` (its `node_modules/` was intentionally not copied;
  it's gitignored). The lockfile (`package-lock.json`) is present, so install is deterministic.

## Verify it's actually functional — do not stop at "it started"
Drive it end-to-end and confirm real behavior:

1. **Sidecar up:** start it, then `curl http://127.0.0.1:7691/health` → expect a healthy response.
   Exercise the API directly: create a session (`POST /sessions`), `POST /send` a short prompt,
   then `GET /history` (or read the SSE `/sessions/{id}/events`) and confirm real events come back.
2. **Frontend up:** run `npm run dev`. electron-vite also serves the renderer over
   `http://localhost:<vite-port>` — use that for browser-based checks (the Playwright MCP browser
   can't open `file:` URLs). Confirm the **Connected** badge (not "Sidecar offline").
3. **Round-trip in the UI:** create a session, send a prompt, watch the event feed render
   (tool-call cards, results, the cost/turns result bar). Expand/collapse a tool card.
4. **Follow the UI-verification rule in `CLAUDE.md`:** do the iteration **headless** (resize the
   panels to narrow and wide extremes, click the controls you rely on), screenshot each state,
   then finish with **one headed pass** to confirm parity. Write screenshots to `.scratch/`.

## Deliverables
- `archive/mvp/` runs standalone on **port 7691**, verified functional end-to-end (sidecar API +
  frontend UI round-trip).
- `archive/mvp/requirements.txt` — complete, reflecting the real installed deps.
- `archive/mvp/README.md` — short "what this is + how to run it": the port (7691), the two
  start commands (sidecar, then `npm run dev`), any prerequisites (the `claude` CLI), and a
  one-line note that this is a **frozen reference, not the build target**.
- *(Optional, nice-to-have)* `archive/mvp/start-mvp.bat` adapted from the root launcher — it uses
  `%~dp0frontend` / `%~dp0sidecar`, so a copy alongside both folders works; confirm it launches both.
- A `DEVLOG.md` entry describing what you set up and the verified outcome.

## Definition of done
You've launched both halves from `archive/mvp/`, sent a prompt through the UI and seen real events
render with the **Connected** badge, completed the headless + headed UI passes, written the
README + complete requirements.txt, and logged it in DEVLOG — all without modifying the root
`frontend/`/`sidecar/`, the rest of `archive/`, or the test suite.
