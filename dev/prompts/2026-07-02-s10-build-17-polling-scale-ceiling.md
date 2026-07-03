# Build prompt — Polling-model scale ceiling (load test)

## 1. Header

- **Test working name:** `polling_scale_ceiling_live`
- **§10 item:** **#17 — Polling-model scale ceiling — 🧪 needs-spike (load test)** (docs/ARCHITECTURE.md §10, item **#17**, `→ §4.3, §6.2`)
- **Goal:** **Measure**, don't guess — how many concurrent agents the per-agent ~1 s poll loop sustains before poll-loop latency / CPU / event lag degrade past usability, establishing a practical **agent-count ceiling** (and whether an adaptive cadence is warranted). This is a **load/measurement spike**, not a pass/fail behavior test.

This is a **measure-or-report** task (the spike-or-omit analog for a load test): the deliverable is a **measured degradation curve + a stated ceiling**, or an honest "couldn't reach a degrading N on this hardware — here's the curve as far as it went." Do **not** assert an arbitrary "passes at N" without the measurement behind it.

---

## 2. Read first (open these before writing a line)

1. **Your §10 item — exact wording.** `docs/ARCHITECTURE.md` §10, item **#17** (in "Priority — coverage-audit additions"). Read all bullets: Desired / Blocker / Research-POC / Fallback.
2. **The cadence model.** `docs/ARCHITECTURE.md` §4.3 (transport — SSE bus + targeted polling cadences) and §6.2 (the bridge driver). These describe the poll model whose ceiling you're measuring.
3. **The exact loop under load.** `sidecar/drivers/bridge.py`:
   - `async def events()` (~line 617) — the per-session poll loop that reads the JSONL transcript for new entries.
   - `await asyncio.sleep(1.0)` (~line 663) — the fixed ~1 s cadence. There is **one such loop per agent**, so fleet cost is O(N) and each cycle crosses the Windows→WSL boundary (a `tmux capture-pane` / file read through WSL2).
   - The module header (~line 4): "no live message stream, so we poll the session's JSONL transcript for new entries." This O(N)-poll is the thing that has no stated ceiling.
4. **The research.** `dev/notes/research/electron-agent-dashboard-architecture-research.md` — prior art on multi-agent dashboard architecture and scale considerations (poll vs push, backpressure). Use it to frame what "degraded" means and what an adaptive-cadence policy would look like. (The push-based alternative is its own item — §10-14 hook-event-stream — so here you measure the *current* poll model, not redesign it.)
5. **THE pattern to copy.** `tests/test_bridge_finisher_live.py` for the live-session shape and `tests/test_tmux_bridge.py` for multi-session handling (`batch_create`, uniquely-named sessions). Bridge API: `create`, `batch_create`, `status`, `wait_idle`, `read_log`, `close`, `_run`.

---

## 3. Mechanism / hypothesis

**What we're measuring:** with the current fixed ~1 s per-agent poll cadence, as N (concurrent tab-less agents) grows, the wall-clock time to complete **one full poll sweep of all N agents** (and the CPU cost, and the lag between a transcript event landing and the poll observing it) grows roughly linearly — until, past some N, a "1 s cadence" can no longer actually be met and the fleet visibly lags.

**Hypothesis:** there is a practical ceiling N\* where the effective per-agent poll interval drifts well past 1 s (e.g. sweeps start taking >Ns for N agents), CPU saturates, or event-observation lag becomes user-noticeable. Below N\* the model is fine; the goal is to find N\* on representative hardware and decide whether an adaptive cadence (slow the poll for idle agents, prioritize the focused one) is needed before then.

**Confirm empirically, don't assume:** the actual shape of the curve (linear? cliff?), where the dominant cost is (the Windows→WSL hop per cycle, JSONL parsing, or tmux capture), and whether idle vs. generating agents cost differently.

---

## 4. Build this

Create **one** new file: **`tests/test_polling_scale_ceiling_live.py`**. Slug: **`pollscale`**. Module-level `pytestmark = [pytest.mark.integration, pytest.mark.slow]`. Mirror the finisher's imports/shim. Use your **own** `TmuxBridge()` (see §7 — do NOT use the shared `bridge` fixture).

**Shape it as a parameterized load sweep** (keep N modest and bounded so the test is safe to run — e.g. N ∈ {1, 5, 10, 20} or as far as the machine allows; make the max N a module constant that's easy to cap):

1. **Setup** — one throwaway WSL diag dir; a helper to spawn K tab-less, uniquely-named sessions (`pollscale-<uuid8>-<i>`) via `create`/`batch_create` (`show=False`), each idle after `wait_idle`. Keep them mostly idle (idle is the common fleet state and the cheapest to poll — measuring idle cost is the floor; optionally also measure with a few generating).
2. **Drive N attached poll loops** — instantiate the driver's `events()` poll path (or faithfully reproduce its per-agent read cycle: the `read_log`/transcript read + `capture-pane` that one `events()` iteration performs) for all N sessions concurrently via `asyncio`, exactly as the sidecar would run them.
3. **Measure, per N:** (a) **sweep latency** — wall-clock to complete one full poll cycle across all N agents (and the drift of the *effective* per-agent interval away from the nominal 1 s); (b) **CPU** — process/system CPU over a fixed window (use `psutil` if available; otherwise sample `/proc` via `_run`); (c) **event lag** — write a marker into one agent's transcript and measure how long until the poll loop observes it, as N grows. Record all three vs N.
4. **Emit the curve** — log a small table `N → sweep_ms, cpu_pct, event_lag_ms` at DEBUG (`logging.getLogger(__name__)`), and write the same table to `tests/log/` so the numbers survive. Identify the **ceiling N\*** = the smallest N where sweep latency exceeds a stated threshold (e.g. effective interval > ~2× nominal) or CPU saturates.
5. **Teardown** — close **all** your uniquely-named sessions and `rm -rf` your dir. Never `kill-server`.

**Timeout hygiene:** cap max N and per-step timeouts so a slow machine fails gracefully with the partial curve, not a hang. Use `asyncio.wait_for`/bounded loops.

---

## 5. The read-back is the crux

Spawning N sessions is easy — **the measurement is the whole test.** The observable is the **degradation curve**, read back from real timers/CPU counters, not asserted from assumption:

- **Primary observable — effective poll interval vs N.** At each N, does one full sweep still complete within ~1 s per agent, or has the effective interval drifted (e.g. 20 agents → sweeps taking >Ns → agents effectively polled every >2 s)? The N where it crosses your stated threshold **is the ceiling** — report the number and the threshold.
- **Secondary — CPU and event lag vs N.** Report both curves; note which resource is the binding constraint first.
- **The assertion** should be a soft, informative one — e.g. assert the test *collected* a valid curve across the N sweep and *identified* a ceiling (or reached max-N without degrading, which is itself the finding: "no ceiling below N=MAX on this hardware"). Do **not** assert a hard "works at N=20" as if it were a fixed contract — the deliverable is the measured number, whatever it is.
- **If you cannot spin up enough agents to degrade** (hardware/WSL limits hit first), that limit **is** the finding — record the max reachable N and why. That's honest, not a failure.

---

## 6. Two honest exits (measure-or-report)

- **MEASURED** — you produced the `N → sweep_ms/cpu/lag` curve and identified a ceiling N\* (or established "no degradation below N=MAX here"). Keep `tests/test_polling_scale_ceiling_live.py` as a durable load test. Note the ceiling + whether an adaptive cadence is warranted — this feeds a §4.3/§6.2 scale paragraph (the Desired behavior) and possibly a §10 follow-on for adaptive cadence.
- **INCONCLUSIVE AFTER A REAL RUN** — if the environment blocked a meaningful sweep (couldn't launch enough sessions, WSL resource cap hit first), report that as a **blocker with the partial curve**, not a fabricated ceiling. Do not assert a made-up number. "Inconclusive" requires an actual run that hit a wall — never skipping the measurement.

---

## 7. Isolation rules (parallel-safe — CRITICAL: reproduce these in the file header/comments)

Sibling agents may be running their own live bridge sessions at the same time. This test is a **fleet spawner**, so it is the *highest-risk* one for collisions — be scrupulous.

- **ONE new file only** — `tests/test_polling_scale_ceiling_live.py`. Do not touch any other test file.
- **Every one of the N sessions is uniquely named** — `pollscale-<uuid8>-<i>`. Never a fixed/shared name. Track every name you create and close **all** of them, even on failure (try/finally).
- **Cap max N** at a safe module constant. This test spawns many real `claude` processes — do not run an unbounded fleet that could starve the machine or sibling agents.
- **NEVER call `tmux kill-server`** (directly or via any helper) in teardown — it would kill *every* agent's sessions, including siblings'. Close only the sessions you created, by name.
- **Run ONLY your own new test** in isolation — and ideally when no sibling live tests are running, since it consumes CPU. Note in the file header that it is resource-heavy and should be run alone.
- **Do NOT edit shared files** — `tests/conftest.py`, `pyproject.toml`, `tests/README.md`. If you think you need a new fixture, marker, pythonpath tidy, or a new dependency (e.g. `psutil`), **STOP and report it to the human** rather than editing a shared file or adding to `requirements.txt`. (If `psutil` isn't already available, fall back to `/proc` sampling via `_run` and flag the dependency request.)
- **The non-obvious trap:** the finisher leans on conftest's session-scoped **`bridge` fixture**, whose **setup AND teardown both call `_kill_all_tmux()` (= `tmux kill-server`)** — fatal here, it would wipe sibling sessions. **Instantiate your OWN `TmuxBridge()`** and tear down only your uniquely-named sessions. Never a broad kill.

---

## 8. Definition of done

- Run your **single** new test through the repo venv and paste the **actual** pytest result line — no paraphrase — plus the **measured curve** (`N → sweep_ms, cpu_pct, event_lag_ms`) from `tests/log/`:

  ```powershell
  .\.venv\Scripts\python.exe -m pytest tests\test_polling_scale_ceiling_live.py -m integration
  # or:  tests\run.ps1 tests\test_polling_scale_ceiling_live.py -m integration
  ```
  (Create the venv first if missing: `python -m venv .venv; .\.venv\Scripts\python -m pip install -r requirements.txt`.)
- Your report must state the **ceiling N\*** (with the threshold that defines it) or the max-N-reached, and a recommendation on whether an adaptive cadence is needed — the input to the §4.3/§6.2 scale paragraph.
- Nothing here renders a UI, so the CLAUDE.md "Verifying UI changes" browser pass does not apply.
- **DEVLOG the change** before you finish — append a new dated entry at the bottom of `DEVLOG.md` (the measured ceiling, files added), per the CLAUDE.md DEVLOG rule.

---

## 9. Guardrails (from CLAUDE.md — reproduce, do not skip)

- **Never create a git branch.** Work on `main`. Do not run `git checkout -b` / `switch -c` / `branch <name>` / `worktree add` — these are gated and will prompt; if one prompts, **stop**. Committing to `main` is fine (but the orchestrator handles git here — do not commit unless told).
- **Bridge sessions stay TAB-LESS.** Create with `show=False`; **never** pass `show=True` and **never** call `show()`. An auto-popped Windows Terminal tab steals the user's focus mid-task — and with N sessions this would be catastrophic.
- **Scratch artifacts go to `.scratch/`** — never the repo root or other project folders. Per-run DEBUG detail + the curve go to `tests/log/` (gitignored) via `logging.getLogger(__name__)`.
- **pytest is the standard** — no ad-hoc scripts. Tag this live test `@pytest.mark.integration` + `@pytest.mark.slow` (module-level `pytestmark`).
