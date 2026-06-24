# Task: get the `bridge` (tmux) path working end-to-end as a frontend proof of concept

## Goal
Make the dashboard drive a **real Claude Code TUI session over the tmux bridge**, end to end, and prove it from the frontend. Today the `sdk` driver is verified live; the `bridge` driver (`sidecar/drivers/bridge.py`) is implemented but has **never been run live**. Your job is to climb the verification ladder bottom-up, fix whatever breaks, and finish with the frontend rendering a real bridge-backed turn.

"Proof of concept" here means: a session created from the UI, backed by the bridge driver, where a sent prompt streams real assistant/tool events from a live tmux Claude Code session into the feed, with the status pill tracking running/idle correctly.

## Read first (do not restate context, point back to these)
- `CLAUDE.md` (folder map, bridge capabilities, behavioral rules, the UI-verification rule).
- `DEVLOG.md` (read top-to-bottom; the Status block and the driver-seam entries are the current truth).
- `sidecar/drivers/bridge.py` (the driver under test), `sidecar/drivers/base.py` (the contract), `sidecar/drivers/__init__.py` (selection order), `sidecar/main.py` (session lifecycle, status bookkeeping).
- `bridge/bridge.py` (TmuxBridge: `create`, `send`, `read_log`, `status`, `wait_idle`), `bridge/transcript.py` (`find_transcript`, `parse_transcript`), `bridge/paths.py` (`CLAUDE_BIN`).
- `frontend/src/renderer/App.tsx` (the renderer: polls `/history` + `/sessions/{id}`; `createSession` currently sends no `driver`).

## Hard constraints
1. Stay inside the project directory. Do not touch `~/.claude` or anything outside the repo unless you explicitly clear it with the user first.
2. Do not change `sdk` driver behavior, and do not edit `archive/mvp/` or the rest of `archive/`. The bridge work must not regress the verified SDK path.
3. Preserve everything you were not asked to change (per the CLAUDE.md rule). Reproduce untouched code exactly.
4. Follow the UI-verification rule in `CLAUDE.md` for any frontend change: headless resize/click/screenshot loop, then one headed parity pass. Write screenshots to `.scratch/`.
5. Log your work in `DEVLOG.md` before you finish (append-only entry; refresh the Status block).

## Verify bottom-up. Do not start at the frontend.
The failure modes live in the lowest layer, so prove each layer before moving up.

### Layer 1: WSL/tmux + the bridge package (no sidecar)
- Confirm the runtime: WSL2 Ubuntu up, `tmux` present, and the **`claude` binary actually exists at the path `bridge/paths.py` assumes** (`CLAUDE_BIN = ~/.local/bin/claude`). Check `wsl -d Ubuntu -- bash -lc 'ls -la ~/.local/bin/claude; which claude'`. If the binary is elsewhere (for example still an npm global shim), `TmuxBridge.create` will launch a dead command and the session will not come up. Fix `CLAUDE_BIN` (or the env) so it points at the real binary. **This is the single most likely live failure; clear it first.**
- Drive the bridge package directly (its own `.venv`, repo root on path): create a session in a **known, clean cwd** (see the cwd note below), `send` a short read-only prompt, `wait_idle`, then `read_log` and confirm you get real transcript entries back. Run the existing suite (`tests\run.ps1`) to confirm nothing in the bridge package is broken in this environment.

### Layer 2: the sidecar with the bridge driver (curl, no frontend)
- Start the sidecar with `AWL_DRIVER=bridge` (this is the only way to reach the bridge driver today; the frontend does not send a `driver` field yet). Confirm `GET /health` reports `"driver": "bridge"`.
- `POST /sessions`, then poll `GET /sessions/{id}` until it leaves `connecting`. `POST /sessions/{id}/send` a short prompt. `GET /sessions/{id}/history` and confirm assistant/user events arrive with top-level `content` carrying typed blocks (the shape `App.tsx` renders). Confirm the status transitions running then back to idle.

### Layer 3: the frontend round-trip
- With the bridge sidecar running, launch the frontend and create + send from the UI. Confirm the **Connected** badge, then a real bridge-backed turn rendering tool-call and text cards in the feed, with the status pill tracking running/idle. Do the headless then headed UI passes.

## Known gaps and risks to expect (verify and resolve, do not just trust the code)
These are where live behavior is likely to diverge from the happy path. Treat each as something to confirm or fix.

1. **`claude` binary path** (Layer 1 above): the highest-probability break. Resolve before anything else.
2. **Transcript binding is a guess.** `find_transcript` picks the *newest* `.jsonl` under the cwd's project-hash dir; there is no session-UUID binding. If the session launches in a busy cwd (the default is the WSL home `/home/lester`, which likely has many prior transcripts), or if two bridge sessions share a cwd, the driver can latch onto the wrong transcript and either show stale entries or skip everything (it seeds `self._seen` from the file length). **Run the PoC in a dedicated, known cwd with at most one active session**, and make that cwd explicit rather than relying on the WSL-home default. Decide whether to give the bridge driver a default cwd or thread `cwd` through from the create request.
3. **Status detection is screen-scraped and brittle.** Running/idle on the bridge path rides entirely on `TmuxBridge._detect_state` (braille-spinner and `❯`-prompt regex on the captured pane). Watch for premature idle (the turn flips to idle mid-generation) and stuck-running (idle never detected). The first `send` sets status to running in `main.py`; make sure the driver's poll does not immediately overwrite it with a stale idle read.
4. **Permission prompts have no UI path.** The driver maps `permission_prompt` to `running`, and the frontend has no approve control, so a prompt that triggers a permission gate will look like "running forever." For the PoC use `acceptEdits` and a benign read-only prompt so you do not hit a gate. Note this as a known limitation, do not try to build the approval flow in this task unless asked.
5. **No cost/turns/result bar on the bridge path.** The bridge driver never emits a `result` event, and the raw Claude Code transcript does not carry the SDK's cost/turns/duration the way the SDK driver gets them, so the result bar stays empty and `total_cost_usd`/`total_turns` stay 0. This is expected. Do not fake it. If you want partial parity, the only honest source is per-message `message.usage` on assistant entries (tokens, not USD); otherwise leave the bar empty for bridge sessions. Flag the decision for the user rather than inventing numbers.

## Frontend change (Layer 3, keep it minimal)
Once the env-var path is proven, make the frontend able to create a bridge session so it is a real frontend PoC, not just an env-var demo:
- Add a minimal way to pick the driver at create time (send `driver: 'bridge'` in the `POST /sessions` body). A small toggle or dropdown in the create flow is enough; do not redesign the panel.
- Surface the active driver on the session row (the session dict from `to_dict()` already returns `driver`), so a bridge session is visually legible as such.
- Keep the SDK path the default and fully working. This is additive.

## Deliverables
- The bridge path verified live end to end: bridge package (Layer 1), sidecar with `AWL_DRIVER=bridge` (Layer 2), and a frontend round-trip rendering a real bridge-backed turn (Layer 3).
- Whatever fixes Layers 1 and 2 required (most likely `CLAUDE_BIN`, the cwd/transcript-selection handling, and any status-flip timing in the driver), with the SDK path unregressed.
- The minimal frontend driver selector plus a driver indicator on the session row.
- Screenshots of the bridge round-trip (narrow and wide) in `.scratch/`.
- A `DEVLOG.md` entry stating what you changed and the verified outcome, and a refreshed Status block. Note any gaps you intentionally left (for example the empty result bar, the permission-prompt limitation).

## Definition of done
A session created from the UI with the bridge driver selected drives a real Claude Code TUI session in tmux, a sent prompt streams real assistant and tool events into the feed, the status pill tracks running then idle, and you have completed the headless and headed UI passes. The SDK path still works unchanged. It is logged in DEVLOG. If any layer cannot be made to work in this environment, stop and report exactly where it broke and what you saw, rather than papering over it.
