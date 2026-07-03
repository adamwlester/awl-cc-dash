# Build prompt — #10 — One-click launch (Electron main spawns the sidecar) — 🧪 needs-spike

**Working name:** `oneclick_launch` lifecycle spike
**§10 item:** #10 — One-click launch (Electron main spawns the sidecar) — 🧪 **needs-spike** (Priority: Medium)
**Goal:** Prove a spawn / supervise / shutdown POC where Electron main (or a faithful stand-in modeling exactly what main would do) owns the sidecar lifecycle **without breaking detach-on-close** — verified *together with* a project close/reopen cycle against a real, live tmux agent. The pass condition is not "the process started"; it is "a running detached agent SURVIVED the close and the sidecar RECONNECTED to it on reopen."

---

## 1. Read first (open these before writing a line)

- **Your §10 item, verbatim:** `docs/ARCHITECTURE.md` §10, **item #10** ("One-click launch (Electron main spawns the sidecar)", lines ~1161–1172). Read the four bullets (Desired / Blocker / Research-POC-must-establish / Fallback) for exact wording — sections 3–6 below are built from them but the doc is the authority.
- **Detach-on-close semantics:** `docs/ARCHITECTURE.md` §3.4 (detach-on-close — a running detached agent must survive app/project close) and the reconnect prose around lines ~984–991.
- **The pattern to COPY:** `tests/test_bridge_finisher_live.py` — this is THE shape. Note specifically: module-level `pytestmark = [pytest.mark.integration, pytest.mark.slow]`; the `sys.path.insert` that makes `sidecar/` importable as top-level; the `diag_dir` throwaway-WSL-dir fixture; `_Driven` wrapping a `BridgeDriver` and driving it directly (no HTTP); each test body is an `async def flow()` run via `asyncio.run(flow())`; the `test_resume_after_simulated_restart` test — **this is your closest kin**: it starts a `BridgeDriver`, captures `tmux_name`, then builds a *fresh* driver with `resume_name=tmux_name` to prove the session survived.
- **The modules this test touches:**
  - `frontend/src/main/index.ts` — Electron main **as it exists today: deliberately frontend-only** (creates a `BrowserWindow`, `app.quit()` on `window-all-closed`; it does NOT spawn or supervise the sidecar). Confirm this yourself.
  - `start-dashboard.bat` — the **current shipped two-process launch**: `start "AWL Sidecar" ... python main.py` then `start "AWL Dashboard" ... npm run dev` in two separate windows. This is the fallback model that stays if the spike fails.
  - `sidecar/main.py` → `reconnect_sessions()` (async, ~line 533): on startup it reads `runtime_store.all_records()`, lists live tmux sessions via `TmuxBridge().list()`, prunes records whose tmux session is gone, and for each survivor rebuilds `SessionState` + a resumed `BridgeDriver` bound to the tmux name. **This is the reconnect mechanism your reopen step exercises.**
  - `sidecar/runtime_store.py` — the restart-survival records: `save_record`, `all_records`, `remove_record`; store dir overridable via **`AWL_SIDECAR_RUNTIME`** (the finisher already points this at a tmp dir — do the same).
- **Research pointer:** `dev/notes/research/claude-code-mode-control-research.md` — this is a **lifecycle/packaging** spike, not a keystroke spike, so the mode-control research is only lightly relevant. Cite **Question 3, point 2 ("Persisted runtime record + resume-or-create", ~line 118)**: the confirmed principle that `runtime_store.py` + `resume()` rebinds to a live tmux session by name on sidecar restart — i.e. detached sessions persist without a window and survive a sidecar process death.

---

## 2. Mechanism / hypothesis

**The lever.** Today the two layers are launched as two independent OS processes by `start-dashboard.bat`; Electron main knows nothing about the sidecar. The desired end-state is that **one icon** (Electron main) spawns + supervises + shuts down the sidecar, tearing everything down through the same close dialog as §3.4 — *except* the tmux agents, which must keep running.

**What we expect.** The critical, non-obvious property is the **asymmetry of shutdown**: when Electron main (or the stand-in) shuts the sidecar down on "project close," the FastAPI process dies **but the detached tmux Claude Code agents do not** — they run in WSL2, driven/read via `capture-pane` + JSONL, needing no window and no live parent. On "reopen," a fresh sidecar runs `reconnect_sessions()`, reads the `runtime_store` records, finds the tmux session still `alive`, and rebinds a resumed driver to it.

**Cited finding.** This survival-and-rebind is exactly the confirmed-working path in the research, **Question 3 §2 (~line 118)**: "Your `runtime_store.py` plus `resume()` rebinds to a live tmux session by name on sidecar restart." The spike's job is to prove that Electron-main-style lifecycle ownership (spawn the sidecar as a child, then kill it on close) **does not** perturb that survival — i.e. killing the sidecar parent leaves the tmux child untouched, and the next sidecar reconnects.

---

## 3. Build this

> **Read the item-specific caveat first:** this item does **not** fit the pure bridge-keystroke `tests/<slug>_live.py` mold. The *real* deliverable §10 asks for is a spawn/supervise/shutdown POC in Electron main (Node/TS). But a pytest can honestly pin the **lifecycle contract** the POC must satisfy, using the real sidecar-as-subprocess + a real tmux agent. **You choose the most honest harness** (see §6). The recommended default is the pytest below because it needs nothing the repo venv lacks; a Node/Electron POC is the richer artifact but may need a runner the venv doesn't have — **if so, STOP and flag it (see §7), do not improvise a shared-config edit.**

Create **one** new file: `tests/test_oneclick_launch_live.py`, with module-level `pytestmark = [pytest.mark.integration, pytest.mark.slow]`, mirroring the finisher's shape (`sys.path` insert for `sidecar/`; `AWL_SIDECAR_RUNTIME` pointed at a tmp dir; an `async def flow()` run via `asyncio.run`).

The test models exactly what Electron main would do and asserts the survival contract. Concrete flow:

1. **Own your own bridge.** Instantiate your **own** `TmuxBridge()` inside the module (do **not** lean on conftest's session-scoped `bridge` fixture — see §7). Use it for WSL shell helpers (`_run` for `mkdir`/`cat`/`rm`) and for `list()` / `close(name)`.
2. **Throwaway dir.** Make a unique WSL dir, `/home/lester/awl-oneclick-<uuid8>`, like the finisher's `diag_dir`; `rm -rf` it in teardown.
3. **Spawn a real detached agent through the sidecar path.** Start a `BridgeDriver` (via a small `_Driven`-style wrapper copied from the finisher, or directly) with a **unique session id and a slug-prefixed tmux name** — e.g. session id `oneclick-<uuid8>`. Send it one marker turn (`"Reply with exactly: LAUNCH_OK"`) and wait for that to land in the transcript (copy `_send_marker_and_wait`), so there is real history to resume and a real live tmux session registered in `runtime_store`. Capture `tmux_name`. **Confirm it is registered** in `runtime_store.all_records()` (the driver writes the record; if your harness drives the driver directly rather than the endpoint, write the record the way the sidecar would — read `reconnect_sessions()` and the driver's create path to see the exact record shape, and match it).
4. **Start the sidecar the way Electron main would — as a supervised child process.** Launch `python main.py` (from `sidecar/`, with `AWL_SIDECAR_RUNTIME` set to your tmp dir and the repo root on `PYTHONPATH` as needed) via `subprocess.Popen`, modeling Electron main owning the venv path + process. Wait for it to **bind `:7690`** (poll `GET http://127.0.0.1:7690/` or a cheap health/`/events` endpoint — confirm which exists in `sidecar/main.py` before using it). This proves clean spawn.
5. **Simulate project close.** Terminate the sidecar child (`Popen.terminate()` / `.kill()` + `wait()`), modeling Electron main's shutdown-ordering step. **Do NOT** touch the tmux agent here — the whole point is that close leaves it running.
6. **Assert survival (crux #1).** After the sidecar is dead, query your own `TmuxBridge().list()` and assert **your uniquely-named tmux session is still in the list** — the detached agent survived project close. Optionally `cat` a file / re-read the transcript to confirm it is genuinely the same live session.
7. **Simulate reopen (crux #2).** Start the sidecar child **again** (same `AWL_SIDECAR_RUNTIME`), wait for `:7690`. On startup it runs `reconnect_sessions()`. Assert the agent was **reconnected**: hit `GET /sessions` (or the sessions-listing endpoint — confirm its exact path in `sidecar/main.py`) and assert your session id is present and bound to your tmux name. If a direct HTTP surface for "is this session reconnected" is awkward, the equally-honest alternative is to call `reconnect_sessions()` in-process against the same `AWL_SIDECAR_RUNTIME` and assert `sessions[sid]` exists with the resumed driver — but the subprocess reopen is the more faithful model, prefer it.
8. **Teardown.** Kill any surviving sidecar child; `close(your_tmux_name)` for **only your** session; `rm -rf` your throwaway dir. **Never `tmux kill-server`.**

Keep the console output concise; log the interesting state (record contents, `list()` output, bind timings) at DEBUG via `logging.getLogger(__name__)` so a failure is diagnosable from `tests/log/`.

---

## 4. The read-back is the crux

Spawning a subprocess and seeing it bind a port is trivial and proves almost nothing about this item. **The whole test is proving the two survival read-backs:**

- **Read-back A — survival:** after the sidecar child is killed (project close), `TmuxBridge().list()` **still contains your uniquely-named tmux session**. If it does not, the spike has FOUND that Electron-main lifecycle ownership breaks detach-on-close — that is a finding, not a failing assert to paper over.
- **Read-back B — reconnect:** after the sidecar child is restarted (reopen), the new sidecar's session table (via `GET /sessions`, or an in-process `reconnect_sessions()` + `sessions[sid]` check) **shows your session id rebound to your tmux name**, with turn history intact (mirror the finisher's `get_context_usage()["turns"] >= 1` check if driving the driver directly).

Assert on both. "The sidecar process started" is explicitly **not** a pass. If either observable can't be read back, that is the finding — write it up (§5), don't fabricate a green.

---

## 5. Two honest exits (spike-or-omit)

- **WORKS** → keep `tests/test_oneclick_launch_live.py` as a durable live test that pins the lifecycle contract, plus a short note (in the test docstring and DEVLOG) of what was learned: that a supervised-child sidecar can be killed on close and the detached tmux agent survives + reconnects, so Electron main CAN own the sidecar lifecycle without breaking §3.4. That note is the green light for the real Electron-main POC.
- **GENUINELY IMPOSSIBLE AFTER A REAL ATTEMPT** → if, after actually running the spawn/kill/reopen cycle against a live agent, the tmux session does **not** survive the sidecar's death, or reconnect cannot be made to work, do **NOT** fabricate a pass. Write up the findings (what died, at what step, the actual `list()` output) and propose moving §10 item #10 toward the **Fallback**: `start-dashboard.bat` two-process launch stays the shipped model (§2). "Impossible" requires an **actual live attempt** — a real subprocess spawn + real kill + real re-list — never just re-reading `reconnect_sessions()` and reasoning about it.

---

## 6. Isolation rules (parallel-safe — CRITICAL — reproduce all of these in the file)

Sibling agents may be running their own live tmux sessions at the same time. Violating any of these can kill their work.

- **ONE new file only:** `tests/test_oneclick_launch_live.py`. Nothing else.
- **Unique tmux names:** prefix every session name with your slug (`oneclick-<uuid8>`). Never a fixed/shared name.
- **NEVER call `tmux kill-server`** (or anything that kills all sessions) in teardown — it kills sibling agents' sessions. Remove **only your own** session via `close(your_name)`.
- **Run only YOUR new test in isolation** — not the whole live tier.
- **Do NOT edit** `tests/conftest.py`, `pyproject.toml`, or `tests/README.md`. If you think you need a shared change — a new fixture, a marker, the `pythonpath` tidy, or a Node/Electron test runner the venv lacks — **STOP and report it to the human**; do not edit a shared file.
- **The non-obvious trap — do NOT depend on conftest's `bridge` fixture:** the finisher leans on conftest's session-scoped `bridge` fixture, whose **setup AND teardown both call `_kill_all_tmux()` (= `tmux kill-server`)**. That is fine for a human running one file alone, but it would **kill sibling agents' live sessions** and breaks the parallel-safe rule. So for this destructive-lifecycle test, **instantiate your OWN `TmuxBridge()`** inside your test module for the WSL shell helpers (`mkdir`/`cat`/`rm`) and for driving/listing/closing, and in teardown remove ONLY your own uniquely-named session and your own throwaway dir. If you believe you truly need the shared fixture or a new shared fixture/marker, **STOP and report to the human.**

---

## 7. Definition of done

- Run your **single** new test through the repo venv and paste the **actual** pytest result line — no paraphrase (the `= N passed =` terminal line and/or `tests/log/results_latest.txt`):
  ```powershell
  .\.venv\Scripts\python.exe -m pytest tests\test_oneclick_launch_live.py -m integration
  ```
  (or `tests\run.ps1 tests\test_oneclick_launch_live.py -m integration`). Create the venv first if missing:
  `python -m venv .venv; .\.venv\Scripts\python -m pip install -r requirements.txt`.
- If the honest outcome is the omit exit (§5), paste the actual failing/finding output and the written-up finding instead of forcing a green.
- Nothing here renders a UI, so the CLAUDE.md "Verifying UI changes" browser pass does not apply — but if you end up building the Electron-main POC surface, follow that rule for anything that renders.
- **DEVLOG the change before finishing** (append a new entry at the bottom of `DEVLOG.md` per the CLAUDE.md format: `### YYYY-MM-DD HH:MM:SS — title`, 1–4 lines, then a `Files:` line).

---

## 8. Guardrails (from CLAUDE.md)

- **Never create a git branch.** Work on `main`. Do not run `git checkout -b` / `switch -c` / `git branch <name>` / `git worktree add` — these are gated and will prompt; if one prompts, STOP and ask.
- **Bridge sessions stay TAB-LESS.** Create every session detached — **never** pass `show=True`, **never** call `show()`. An auto-popped Windows Terminal tab steals the user's focus. `create(...)` defaults to `show=False`; keep it.
- **Scratch artifacts go to `.scratch/`** (gitignored) — never the repo root or other project folders. Any subprocess log dumps, temp files, screenshots → `.scratch/`.
- **pytest is the standard** — no ad-hoc scripts for testable behavior.
- **You are building ONE test file.** Do not gold-plate, do not touch shared config, do not build the Electron-main POC unless you can do it without a shared-config edit or a missing runner — if it needs either, STOP and flag it to the human.
