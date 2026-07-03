# Build prompt — Subagent pending-vs-active status (live spike)

## 1. Header

- **Test working name:** `subagent_status` (live spike)
- **§10 item:** **#08 — Subagent pending-vs-active status — 🧪 needs-spike**
- **Goal:** Prove (or disprove) a reliable *live* active-vs-pending signal for a running subagent — beyond the already-proven spawned/running-vs-done derivation. The single empirical question: does a subagent's own transcript file exist and advance (mtime / last-event recency) *while the subagent is working*, so we can read "active" vs "pending/quiet" back deterministically?

This is a **spike-or-omit** task. A truthful "GENUINELY IMPOSSIBLE" write-up is a valid, valuable outcome — do **not** fabricate a green.

---

## 2. Read first (open these before writing a line)

- **Your §10 item — read the exact wording:** `docs/ARCHITECTURE.md` **§10, item 8 "Subagent pending-vs-active status"** (around line 1139). Note all four bullets: Desired, Blocker, Research/POC-must-establish, Fallback.
- **The research finding you are testing:** `dev/notes/research/claude-code-mode-control-research.md`
  - **Question 2** — *bjornjee/agent-dashboard* (~lines 68–75): the hook architecture (`SubagentStart`/`SubagentStop` in the event list) and the deterministic `pending-tools.js` overlay — **any `tool_use` id without a matching `tool_result` means "still working."**
  - **Question 3 → Run-state detection #3** (~lines 101–104): the *deterministic transcript overlay* — tail the JSONL, collect `tool_use` ids from assistant entries minus `tool_result` ids from user entries; nonempty set ⇒ the agent is still working. This is the exact overlay to apply to the **subagent's own** transcript.
- **THE pattern to copy:** `tests/test_bridge_finisher_live.py` — copy its shape exactly (see §4).
- **The modules this test touches (read them):**
  - `sidecar/drivers/bridge.py` — `derive_subagents()` (line ~279) and `_subagent_status()` (line ~270). Note the docstring's stated subagent-transcript path: `<project>/<parent-uuid>/subagents/agent-<agentId>.jsonl`. `_subagent_status()` today only knows `running` (no result) / `done` / `error` — the finer *active-vs-pending within running* is exactly what is unproven.
  - `sidecar/main.py` — `GET /sessions/{id}/subagents` (line ~1621); thin wrapper over `driver.get_subagents()`. You will **not** need HTTP — drive the driver directly.
  - `bridge/transcript.py` — `find_transcript()` (line ~77) and `_resolve_session_id()` / `session_id_for()`: how the parent's transcript file (`<project_dir>/<sid>.jsonl`) is resolved. The parent's `<sid>` is the directory whose `subagents/` holds the subagent JSONLs.

Do **not** retest the unit-proven identity/naming/spawn-vs-done derivation (`test_subagents_naming_unit`, the `derive_subagents` running/done logic). Spike **only** the live active-vs-pending signal.

---

## 3. Mechanism / hypothesis

**Known lever (confirm against code + research before writing):** `derive_subagents()` already pairs each `Agent`/`Task` spawn on the parent's main line with its `tool_result` — a spawn with no result yet ⇒ `running`, a result present ⇒ `done`/`error`. That coarse running-vs-done split is unit-proven and is **not** what we test.

The **open question** is finer: within `running`, is the subagent *genuinely active (working right now)* or *merely pending (spawned, quiet, between/ before steps)*? The hypothesized live signal, straight from the research:

1. **Transcript-recency signal (primary):** the subagent's own transcript persists at `<project_dir>/<parent-sid>/subagents/agent-<agentId>.jsonl`. **Hypothesis:** while the subagent is doing multi-step work, this file **exists and its mtime (and last-event timestamp) advances**; when the subagent is quiet/pending/finished the mtime goes stale. Read via WSL `stat -c %Y <file>` sampled over time (cite Q3 #3 — deterministic transcript overlay; Q2 — agent-dashboard reads these JSONLs).
2. **Deterministic pending-tools overlay (corroborating):** parse the subagent transcript, collect `tool_use` ids from its assistant entries minus `tool_result` ids from its user entries. **Nonempty ⇒ the subagent is mid-tool = active** (cite Q2 `pending-tools.js`; Q3 #3).

**What we expect:** drive a parent to spawn a subagent that does slow, multi-step work; the subagent JSONL should appear and its mtime should visibly advance across samples during the work, then stop advancing once the subagent finishes — and (2) should show a nonempty pending-tool set at some mid-run sample. **The load-bearing risk:** it is entirely possible Claude Code buffers the subagent transcript and writes `agent-<id>.jsonl` **only on completion** — in which case mtime-recency yields **no** live active signal. That negative is a real finding, not a failure to try (see §6).

---

## 4. Build this

Create **one** new file: `tests/test_subagent_status_live.py`. Mirror the finisher's shape:

- Module-level `pytestmark = [pytest.mark.integration, pytest.mark.slow]`.
- The same sys.path shim the finisher uses to import the sidecar's `drivers.bridge` as top-level (`_SIDECAR = _REPO_ROOT / "sidecar"; sys.path.insert(...)`), then `from drivers.bridge import BridgeDriver` and `from drivers.base import DriverConfig`.
- A `_Driven`-style helper wrapping a `BridgeDriver` (copy the finisher's `_Driven`: it starts the driver, pumps `driver.events()` in a background task, and exposes `driver`). You do not need the permission `pending` flag here, but keeping the event pump running is what makes the driver poll the transcript.
- The test body is an `async def flow(): ...` run via `asyncio.run(flow())`.

**Critical isolation deviation from the finisher — read §7.** The finisher takes the session-scoped `bridge` fixture (whose setup *and* teardown call `tmux kill-server`) and a `diag_dir` fixture built on it. **You must NOT use those.** Instead, inside your module, instantiate your **own** `TmuxBridge()` for WSL shell helpers and your own throwaway dir, and in teardown call `close(<your-name>)` on only your own session + `rm -rf` your own dir. Import it as the driver does:

```python
import sys
from pathlib import Path
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))
from bridge import TmuxBridge
```

**Flow (concrete):**

1. **Unique names + own dir.** Pick a slug prefix `substat` and a unique suffix, e.g. `name_suffix = uuid.uuid4().hex[:8]`. Make a throwaway WSL dir via your own bridge: `wsl_dir = f"/home/lester/awl-substat-{name_suffix}"; my_bridge._run(f"mkdir -p {wsl_dir}")`. (The driver mints its own `awl-<uuid>` tmux name internally; to keep the *tmux session* name uniquely yours and slug-prefixed, pass `resume_name` is **not** right — instead let the driver create, then capture `d.driver.tmux_name` and use THAT exact name everywhere you address tmux. Do not create a second session.)
2. **Spawn the parent (tab-less).** Build `BridgeDriver(DriverConfig(cwd=wsl_dir, permission_mode="bypassPermissions"), events.append, session_id=f"substat-{name_suffix}")` and `await d.start()`. Use `bypassPermissions` (or pre-allow the `Agent`/`Bash` tools via `permission_rules`) so the subagent work runs without stopping on a permission prompt — this spike is about status, not permissions. **Never pass `show=True`; never call `show()`.**
3. **Drive a slow multi-step subagent.** `await d.driver.send(<prompt>)` where the prompt tells the parent to **use the Agent tool to launch one subagent** that performs a *slow, observable, multi-step* task — e.g. "Use the Agent tool to spawn a general-purpose subagent. Instruct that subagent to run these Bash steps one at a time, pausing between each: `sleep 4 && echo step1`, then `sleep 4 && echo step2`, … through step5, and report when done. Do not do the work yourself." The goal is a subagent that stays alive and writes transcript entries for ~20–30s.
4. **Locate the subagent transcript.** Resolve the parent's project dir + session id the way `find_transcript` does (get pane cwd → `~/.claude/projects/<encoded>`; parent sid via `d.driver._claude_session_id` or `my_bridge.session_id_for(d.driver.tmux_name)`). The subagents live under `<project_dir>/<parent_sid>/subagents/`. **Poll with your own bridge** until an `agent-*.jsonl` appears: `my_bridge._run(f"ls {project_dir}/{parent_sid}/subagents/agent-*.jsonl 2>/dev/null || true")`, retrying for up to ~60s. Record whether/when it appears.
5. **Sample the recency signal (the read-back, §5).** Once the file exists (or the retry budget expires), take **repeated `stat -c %Y <file>` samples** a few seconds apart while the subagent is still working (also snapshot `wc -l` / tail last-event `timestamp`). Collect the sequence of mtimes.
6. **Corroborate with the pending-tools overlay.** At a mid-run sample, `cat` the subagent JSONL, parse each line's JSON, collect `tool_use` block ids (from `assistant` entries) minus `tool_result` `tool_use_id`s (from `user` entries); record whether the set is nonempty at any sample.
7. **Assert (see §5).** Assert the recency signal is *readable and moves*: the file appeared during the run **and** the mtime strictly advanced across at least two consecutive live samples (and/or the pending-tools set was nonempty mid-run), then went quiet after completion. Log every sample at DEBUG.
8. **Teardown.** In a `finally`, `await d.close()` (kills only this driver's own tmux session) and `my_bridge._run(f"rm -rf {wsl_dir}")`. Do **not** touch any other session.

Keep console output concise; push mtimes, line counts, tails, and the pending-tool set to DEBUG via `logging.getLogger(__name__)` (finisher convention).

---

## 5. The read-back is the crux

Sending the prompt that spawns a slow subagent is trivial. **Proving a live active signal exists is the entire test.** The specific observable:

> The subagent's own transcript file `<project_dir>/<parent_sid>/subagents/agent-<agentId>.jsonl` **exists while the subagent is working**, and its **mtime (`stat -c %Y`) / last-event `timestamp` advances across live samples** during work, then stops advancing when the subagent goes pending/finished — read back deterministically via your own bridge's WSL shell.

Read it back by: `stat -c %Y <file>` sampled ≥2× a few seconds apart during the run (primary), corroborated by the pending-tools overlay (`tool_use` ids minus `tool_result` ids on the subagent transcript = nonempty ⇒ active). The assertion is on the **movement of a live signal**, not merely on the file's eventual presence.

**If the signal is not observable — the file only appears at completion, or its mtime never advances mid-run — that is a FINDING, not a pass.** Do not soften it into a green by asserting something trivially true (e.g. "file exists at end"). Record exactly what you saw and route to §6.

---

## 6. Two honest exits (spike-or-omit)

- **WORKS** → the mtime/last-event recency (and/or pending-tools overlay) demonstrably moves while the subagent is active and quiets when it isn't. Keep the file as a **durable live test**, and add a short note (in the test docstring + your DEVLOG entry) of what was learned: which signal proved reliable (mtime vs last-event vs pending-tools), the observed timing, and any caveat (e.g. flush lag). This unblocks §10 item 8 toward its Desired behavior.
- **GENUINELY IMPOSSIBLE AFTER A REAL ATTEMPT** → e.g. the subagent JSONL is written only on completion, so no live recency exists; or mtime is indistinguishable between active and pending. **"Impossible" requires an ACTUAL live run** — never a re-read of the code concluding it's a no-op. Do **not** fabricate a green. Instead: write up the findings (what you drove, what you sampled, the raw mtime/line-count sequence), and in your summary **propose moving §10 item 8 to its Fallback** ("subagents are listed without a pending/active distinction") / Decided omissions. Leave the test file either as an `xfail`-documented probe or delete it per your judgment, but the *findings* are the deliverable.

Either way, report which exit you took and the evidence.

---

## 7. Isolation rules (parallel-safe — CRITICAL)

Sibling agents may be running their own live bridge sessions at the same time. Reproduce **all** of these in the file (as a comment block) and obey them:

- **ONE new file only:** `tests/test_subagent_status_live.py`. Add nothing else.
- **Name tmux sessions uniquely**, slug-prefixed (`substat-<uuid8>` / `awl-substat-<uuid8>`). Address tmux **only** by your own session's exact name (`d.driver.tmux_name`).
- **NEVER call `tmux kill-server`** (directly or via any helper) in teardown or anywhere — it kills sibling agents' sessions. Tear down with `close(<your-name>)` for your one session only.
- **Run ONLY your own new test in isolation** — never the whole live tier.
- **Do NOT edit** `tests/conftest.py`, `pyproject.toml`, or `tests/README.md`. If you think you need a shared change (a new fixture, marker, or a pythonpath tidy), **STOP and report it to the human** — do not edit a shared file.
- **Non-obvious trap — do NOT use the shared `bridge` fixture.** The finisher leans on conftest's **session-scoped `bridge` fixture**, whose setup **and** teardown both call `_kill_all_tmux()` (= `tmux kill-server`). That's fine for a human running one file alone, but it would **kill sibling agents' live sessions** and breaks the parallel-safe rule. So do **not** depend on that fixture (nor the `diag_dir` fixture built on it) for a destructive lifecycle. Instead **instantiate your OWN `TmuxBridge()`** inside your test module for WSL shell helpers (`mkdir`/`ls`/`stat`/`cat`/`rm`) and for reading, and in teardown remove **only** your own uniquely-named session (via `close(name)`) and your own throwaway dir. If you believe you truly need the shared fixture or a new shared fixture/marker, **STOP and report to the human** rather than editing a shared file.

---

## 8. Definition of done

- Run your **single** new test through the repo venv and paste the **actual** pass/fail line, no paraphrase — the pytest `= N passed =` (or `failed`/`xfailed`) terminal line and/or `tests/log/results_latest.txt`. Windows PowerShell:

  ```powershell
  .\.venv\Scripts\python.exe -m pytest tests\test_subagent_status_live.py -m integration
  # or:
  tests\run.ps1 tests\test_subagent_status_live.py -m integration
  ```

  (Create the venv first if missing: `python -m venv .venv; .\.venv\Scripts\python -m pip install -r requirements.txt`.)
- If you took the **IMPOSSIBLE** exit, paste the run output that proves you made a real live attempt (the sampled mtime/line-count sequence at DEBUG in `tests/log/`), and state the proposed §10 fallback move.
- This spike has no rendered UI surface; if any part renders, follow CLAUDE.md **"Verifying UI changes"** (headless resize/click loop, then one headed parity pass). Otherwise skip.
- **DEVLOG the change before finishing** — append a `### YYYY-MM-DD HH:MM:SS — <title>` entry at the bottom of `DEVLOG.md` with what you built/found and a `Files:` line.

---

## 9. Guardrails (from CLAUDE.md)

- **Never create a git branch.** Work on `main`. Do not run `git checkout -b` / `switch -c` / `branch <name>` / `worktree add`. Do not commit or push unless asked — the orchestrator handles git.
- **Bridge sessions stay TAB-LESS.** Never pass `show=True` and never call `show()` — a tab opening as a side effect steals the user's focus. Create and drive detached.
- **Scratch artifacts go to `.scratch/`** (gitignored), never the repo root or other project folders. The throwaway WSL dir is under `/home/lester/awl-substat-*` and is `rm -rf`'d in teardown.
- **pytest is the standard** — no ad-hoc scripts; the deliverable is the one `tests/*_live.py` file (or, on the IMPOSSIBLE exit, the findings write-up).
