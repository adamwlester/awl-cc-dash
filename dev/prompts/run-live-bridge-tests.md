# Prompt: Run the live bridge/integration tests and report

**For:** a Codex (or any) agent on this laptop. **Type:** mechanical run-and-report.
**Do NOT change any code, tests, or docs.** Your only job is to run the live test
tier and report exactly what happened. If something fails, report the failure and
the relevant log excerpt — do **not** attempt a fix.

## Why

The hermetic unit tier (395 tests) is already confirmed green. The **live/integration
tier** (33 tests, marked `integration`+`slow`) is the only end-to-end proof that the
tmux bridge still drives a real Claude Code agent — permission round-trips, resume,
model/effort, and the full session control surface. It is not run by default, so its
current status is unknown. This task confirms it.

## Preconditions

- Run from the repo root: `c:\Users\lester\MeDocuments\AppData\Anthropic\awl-cc-dash`.
- This laptop must have **WSL2 (Ubuntu) + tmux + a working Claude Code CLI** inside WSL.
  These tests spawn **real detached tmux sessions** — that is expected. Per the repo's
  bridge-sessions rule, they create sessions **tab-less** (no terminal windows pop);
  don't do anything to force a window open.
- The repo-root `.venv` must exist. If it doesn't:
  `python -m venv .venv; .\.venv\Scripts\python -m pip install -r requirements.txt`

## What to run

Run the two live files, verbose, with output captured. One combined run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\ -m "integration or slow" -v
```

If you want them separately (e.g. one is hanging):

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_tmux_bridge.py -v
.\.venv\Scripts\python.exe -m pytest tests\test_bridge_finisher_live.py -v
```

Notes:
- The `test_bridge_finisher_live.py` set is the highest-value 4 tests (permission
  approve/deny, resume-after-restart, model+effort take).
- These are **slow** (each spins up a TUI). Allow several minutes; a long pause is
  normal, not a hang. Only treat it as hung if there is zero progress for ~5+ min.
- On failure, the full detail (exact WSL/tmux commands, raw screen captures, detected
  states, tracebacks) is in the **newest** file under `tests\log\`. Find it with:
  `Get-ChildItem tests\log\*.log | Sort-Object LastWriteTime | Select-Object -Last 1`

## What to report back

Fill in this template and return it verbatim — nothing else needs changing in the repo:

```
## Live bridge test run — <date/time>

Environment: WSL distro = <name>, Claude Code in WSL = <version or "present/absent">
Command: <the exact pytest command you ran>

Result line: <paste the final pytest summary line, e.g. "29 passed in 214s">

Per-file:
- test_tmux_bridge.py:            <N passed / M failed / K errored>
- test_bridge_finisher_live.py:   <N passed / M failed / K errored>

Failures (if any) — for EACH failed/errored test:
- <test node id>
  - one-line reason (from the assertion / error)
  - the relevant excerpt from the newest tests\log\*.log (10-30 lines around the failure)

Anything that looked wrong but didn't fail (warnings, slowness, flaky retries):
- <notes, or "none">
```

If **every** test passes: say so plainly and paste the summary line — that confirms the
live bridge foundation is current. If **any** fail: report per the template and **stop**
(no fixes) so a Claude session can triage against the docs and `ARCHITECTURE.md §10`.
