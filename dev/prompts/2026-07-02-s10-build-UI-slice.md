# Build prompt — UI slice (frontend client-contract proof)

## 1. Header

- **Working name:** `ui_slice` (frontend end-to-end proof against the sidecar API)
- **§10 item:** **#10 (META build-table row 10) — UI slice (frontend) — 🧪 needs-spike** — the frontend proof the backend spikes don't cover. (This is the "UI slice" row of the META build-prompts table, *not* ARCHITECTURE §10's numbered item #10, which is "One-click launch." Don't confuse them.)
- **Goal:** Prove the **frontend behaviors** end-to-end against the **real, already-tested** sidecar API — render the live feed, send a prompt, approve **and** deny a permission, and reflect run-state — driven by **Playwright-python** against a **minimal fixture page**. This is a client-contract proof, **NOT** button polish, and it leaves `frontend/` completely untouched.

## 2. Read first (open these before writing a line)

- **Its §10 context:** `docs/ARCHITECTURE.md` **§10** (Open questions & research queue, starts line ~1009) — read the framing and the **Decided omissions** rules. Also read `dev/prompts/2026-07-02-s10-META-build-prompts.md` **row 10** of the table in §2 (the "UI slice (frontend)" row) and the **"UI-slice prompt — extra requirements"** paragraph in §3 — that row is the contract for this test.
- **The client contract you are proving:** `frontend/src/renderer/api.ts` — this is the **reference for exactly what your fixture page must call.** Note precisely:
  - `API = window.awl?.sidecarUrl || 'http://127.0.0.1:7690'` (line 14) — your fixture page hardcodes `http://127.0.0.1:7690`.
  - `openEventStream()` (lines 295–305) opens an `EventSource` on **`/events`**, parses each `message` as JSON, dedups by `event.id`.
  - `api.create()` → `POST /sessions`; `api.send(id, prompt, opts)` → `POST /sessions/{id}/send` with body `{prompt, source:'user', recipients:null, disposition:'queue'}` (lines 321–327); `api.answerPermission(id, approve)` → `POST /sessions/{id}/permission` `{approve}` (line 332); `api.session(id)` → `GET /sessions/{id}` (line 311).
  - `Session` shape (lines 34–50): `status` is `connecting | idle | running | error | closed`; `has_pending_permission: boolean`; `permission_request: PermissionDetail | null`. `PermissionDetail` = `{question?, options?, raw?}` (lines 116–120).
- **The sidecar endpoints you hit:** `sidecar/main.py` —
  - `POST /sessions` create (line ~923 is `/send`; create is the `@app.post("/sessions")` above it — open and confirm the payload).
  - `POST /sessions/{id}/send` (line 923) — enqueues; an **idle** agent flushes immediately.
  - `GET /events` (line 1026) — merged SSE bus; replays a bounded ring then streams live; each frame is `{"event":"message","data": <json>}`.
  - `POST /sessions/{id}/permission` (line 1548) — `{approve}`; **returns 409 "No pending permission prompt" if nothing is pending** (this is why you need a real agent to raise one). Pushes a `permission_resolved` event and clears `has_pending_permission`.
  - `GET /sessions/{id}` — carries `status`, `has_pending_permission`, `permission_request`.
  - **CORS:** `app.add_middleware(CORSMiddleware, allow_origins=["*"])` (line ~61) — so a fixture page served from `localhost:<port>` can `fetch`/`EventSource` cross-origin to `127.0.0.1:7690`. Good; don't work around it.
- **THE pattern to copy (conventions only):** `tests/test_bridge_finisher_live.py` — copy its **shape**: module-level `pytestmark = [pytest.mark.integration, pytest.mark.slow]`, the `sys.path`-insert of `sidecar/` if you import driver code, a real bridge session driven in a throwaway WSL dir, and **reading state back to assert** (the permission approve/deny tests there are your backend mirror). You are **not** copying the direct-driver approach — you go through the HTTP/SSE layer + a browser — but the discipline (unique session, read-back assert, clean teardown, no `tmux kill-server`) is identical.
- **Guardrails:** `CLAUDE.md` — git/branch rule, tab-less bridge sessions, DEVLOG, `.scratch/`, and **"Verifying UI changes"** (this test renders, so that section is binding).

## 3. Mechanism / hypothesis

This slice is **not** keystroke research — it rides the **already-tested sidecar API** (the permission approve/deny, send, and run-state paths are proven at the driver layer by `test_bridge_finisher_live.py`). The open question this test closes is the **client contract**: does a browser page that speaks only the `api.ts` contract (`/events` SSE + the POST endpoints) actually **render** the live feed, **dispatch** a prompt, **resolve** a permission both ways, and **reflect** run-state — using the same calls `frontend/src/renderer/api.ts` makes?

Expected behavior:
1. `POST /sessions` (default permission mode) spawns a real, tab-less bridge agent; its `session_id` comes back.
2. An `EventSource` on `/events` streams envelope events (`type`, `agent_id`, `seq`, `content`, …). The fixture page appends each to a feed list → **live feed renders.**
3. `POST /sessions/{id}/send` with a Write-a-file prompt flushes to the idle agent; feed shows assistant/tool activity and `status` goes `idle → running`.
4. Because the agent is in **default** permission mode, the Write raises a **real** tool-permission prompt → the sidecar emits a `permission_request` event and `has_pending_permission` flips true. The fixture page renders an Approve/Deny control.
5. `POST /sessions/{id}/permission {approve:true|false}` resolves it → sidecar emits `permission_resolved`, `has_pending_permission` clears; approve writes the file, deny does not.

The reference for every call is `api.ts`; the reference for the driver-level truth of steps 4–5 is the finisher's `test_permission_approve` / `test_permission_deny`.

## 4. Build this

**One new test module: `tests/ui/test_ui_slice_live.py`** (new `tests/ui/` subfolder), plus **one minimal fixture page** it serves. Module-level `pytestmark = [pytest.mark.integration, pytest.mark.slow]`.

**Prerequisites the test must arrange (document them at the top of the file):**
- **A running sidecar on :7690.** Start it yourself for the run: from `sidecar/`, `python main.py` (it binds `0.0.0.0:7690`; for a loopback-only dev run you may set `AWL_SIDECAR_HOST=127.0.0.1`, but note the hook channel degrades — fine for this test). Either (a) start it in a background process inside the test's `setup` and tear it down after, or (b) require it be already up and `GET /health` to confirm, skipping with a clear message if not. **Confirm reachability with `GET /health` before doing anything else.**
- **Playwright-python** (sync API is fine) in the **same `.venv`** — no Node toolchain. If `playwright` isn't installed, install into `.venv` and run `playwright install chromium`. **Do NOT edit `requirements.txt`** to add it — if a durable dependency add is warranted, **STOP and flag it to the human** (see Isolation rules).
- **The fixture page.** Ship a small self-contained `tests/ui/fixture/app.html` (HTML + inline JS, no build step) that:
  - Sets `const API = 'http://127.0.0.1:7690'`.
  - On load, opens `new EventSource(API + '/events')` and appends each parsed event to a `#feed` list (one `<div class="event" data-type="...">` per event) — **mirror `openEventStream`'s parse + dedup-by-`id`.**
  - Exposes a "send prompt" input + button that `POST`s `/sessions/{id}/send` with `{prompt, source:'user', recipients:null, disposition:'queue'}`.
  - Renders a **run-state** element (`#runstate`) that reflects the session `status` (poll `GET /sessions/{id}` or derive from events) — text `idle`/`running`.
  - When `has_pending_permission` / a `permission_request` event is seen, renders `#permission` with **Approve** and **Deny** buttons that `POST /sessions/{id}/permission` `{approve:true|false}`; on `permission_resolved`, clears/marks it resolved.
  - Keep it deliberately minimal and **framework-free** — this is a contract harness, not a UI. It must **not** import or touch anything under `frontend/`.

**Serve it over http:** Playwright blocks `file:` — serve `tests/ui/fixture/` with a throwaway `python -m http.server` (or an in-process handler) on `http://localhost:<port>` and `page.goto` that URL.

**Test flow (mirror the finisher's read-back discipline):**
1. **Setup:** confirm sidecar `/health`; start the static server; launch a headless Chromium page and `goto` the fixture URL.
2. **Create agent:** `POST /sessions` (default permission mode, a throwaway WSL `cwd`, and a **slug-prefixed identity name** e.g. `ui-slice-<uuid8>` so it's identifiable). Capture `session_id`. (The driver auto-names the tmux session `awl-<uuid8>` — already unique — confirm in `sidecar/drivers/bridge.py` line ~433.) Point the fixture page at this `session_id`.
3. **Live feed renders:** wait until `#feed` has ≥1 event element (the SSE ring/replay + connect events). Assert via Playwright locator count.
4. **Send a prompt:** drive the fixture's send control with a Write prompt (e.g. *"Create a file named ui.txt containing exactly the word mango. Use the Write tool. Do nothing else."*). Assert the prompt dispatched (feed shows the user/assistant activity; the POST returned a `SendResult`).
5. **Run-state:** assert `#runstate` shows `running` while the turn is active (then returns toward `idle`). Read it back from the rendered DOM, not from styling.
6. **Permission approve:** wait for the `#permission` control to appear (real `permission_request`), click **Approve**; assert the UI reflects resolution (`permission_resolved` handled, `#permission` cleared / `has_pending_permission` false) and — for a true read-back — that `ui.txt` was written (cat it back over the bridge, as the finisher does).
7. **Permission deny (fresh prompt):** send another Write prompt for a different file (`deny.txt`), wait for `#permission`, click **Deny**; assert resolution reflected and the file was **not** written.
8. **Teardown:** close the browser + static server; **retire the created session via `DELETE /sessions/{id}?hard=true`** (this drives the driver's own single-session close). Remove your throwaway WSL dir. **Never `tmux kill-server`.**

Assert on **rendered DOM state** (Playwright locators / `inner_text`), never on pixels or CSS.

## 5. The read-back is the crux

Firing the fetches is trivial; **proving the client contract took effect is the whole test.** For each behavior, name and read back a concrete observable:
- **Live feed:** count of `.event` nodes in `#feed` ≥ 1 (and grows after a send) — not "the EventSource opened."
- **Send:** the feed reflects the dispatched prompt / assistant activity **and** the POST returned a `SendResult` — not just a 200.
- **Run-state:** `#runstate` text transitions to `running` during the turn (read from DOM).
- **Permission approve:** the `#permission` control disappears/marks resolved **and** `ui.txt` == `mango` when catted back over the bridge.
- **Permission deny:** resolution reflected **and** `deny.txt` is missing (`__MISSING__`) when catted back.

If any observable can't be read back — e.g. the permission prompt never renders because the SSE event doesn't carry what the client needs, or run-state never flips in the DOM — **that is a FINDING, not a pass.** Do not soften an assertion to make it green.

## 6. Two honest exits (spike-or-omit)

- **WORKS →** keep `tests/ui/test_ui_slice_live.py` as a durable live test. Add a short note (in the module docstring + DEVLOG) of what was learned — e.g. which `/events` fields the client actually needs to render the feed and the permission card, and how run-state is derived.
- **GENUINELY IMPOSSIBLE AFTER A REAL ATTEMPT →** do **NOT** fabricate a green. Write up the findings (what rendered, what didn't, the exact missing observable) and propose the disposition: if a *specific sub-behavior* proves unsupportable by the current API, say so precisely and recommend either an API gap to close (→ TODO) or, only if a spike truly proves no path, a **Decided omissions** entry. "Impossible" requires an **actual live run** against a real sidecar + real bridge agent — never a re-read of code.

## 7. Isolation rules (parallel-safe — CRITICAL — reproduce all of these in the file header)

- **ONE new file only:** `tests/ui/test_ui_slice_live.py` (+ its `tests/ui/fixture/app.html`). Nothing else.
- **Uniquely-named sessions:** create with a **slug-prefixed identity name** (`ui-slice-<uuid8>`); the driver's tmux name is already unique (`awl-<uuid8>`). Clean up **only** the `session_id`s you created, via `DELETE /sessions/{id}?hard=true`.
- **NEVER call `tmux kill-server`** in teardown — it kills sibling agents' live sessions and breaks parallel safety.
- **Non-obvious trap — do NOT depend on conftest's `bridge` fixture for a destructive lifecycle.** That session-scoped fixture's setup **and** teardown both call `_kill_all_tmux()` (= `tmux kill-server`), which would kill sibling agents' sessions. Fine for a human running one file alone; **not** parallel-safe. So: if you need raw WSL shell helpers (mkdir/cat/rm the throwaway dir, cat files back), **instantiate your OWN `TmuxBridge()` inside your test module** (`from bridge import TmuxBridge`, adding the repo root to `sys.path` if needed) and use its `_run(...)` — and in teardown remove **only** your own throwaway dir and retire **only** your own session. Do not lean on the shared fixture's destructive teardown.
- **Run ONLY your own new test in isolation** — not the whole live tier.
- **Do NOT edit** `tests/conftest.py`, `pyproject.toml`, or `tests/README.md`. **Adding the `tests/ui/` subfolder is the trigger for a small `pythonpath` fix in `pyproject.toml` — you must FLAG THAT TO THE HUMAN, not perform it.** Likewise, if the test needs a new shared fixture/marker, or a durable `requirements.txt` add for `playwright`, **STOP and report to the human** rather than editing a shared file. (Installing `playwright` into the local `.venv` to *run* the test is fine; adding it to `requirements.txt` is the shared change to flag.)

## 8. Definition of done

- Run your **single new test** through the repo venv and **paste the ACTUAL pass/fail line, verbatim** (the pytest `= N passed =` terminal line and/or `tests/log/results_latest.txt`) — no paraphrase. Windows PowerShell:
  ```powershell
  .\.venv\Scripts\python.exe -m pytest tests\ui\test_ui_slice_live.py -m integration
  ```
  (or `tests\run.ps1 tests\ui\test_ui_slice_live.py -m integration`).
- **This test renders — follow CLAUDE.md "Verifying UI changes"** for the fixture page: serve over `http://localhost` (Playwright blocks `file:`), drive the affected surface at **narrow and wide** extremes, **click through every control you touched** (send, approve, deny), screenshot each state into `.scratch/`, iterate **headless**, then do **one headed parity pass** confirming the rendering matches. Keep the headed pass light.
- **DEVLOG the change** before you finish: a `### YYYY-MM-DD HH:MM:SS — short title` entry at the bottom of `DEVLOG.md`, 1–4 lines on what landed and the observed outcome, plus a `Files:` line. (The orchestrator does NOT DEVLOG for you — you do.)

## 9. Guardrails (from CLAUDE.md)

- **Never create a git branch.** Work on `main`. Do not run `git checkout -b` / `switch -c` / `branch <name>` / `worktree add` — they're gated and will prompt; if one prompts, stop.
- **Bridge sessions stay TAB-LESS.** Sessions created via `POST /sessions` are tab-less by design; never pass `show=True` and never call `show()`. No auto-attach as a side effect.
- **Scratch artifacts go to `.scratch/`** — screenshots, the fixture's throwaway logs, debug dumps. Never the repo root.
- **pytest is the standard** — no ad-hoc scripts for the test itself.
