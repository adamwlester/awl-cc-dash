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

**The run writes its own durable results record** — you do not hand-assemble a report.
As of the conftest results-logging change, every run drops these into `tests\log\`
(gitignored):

- `results_latest.txt` — human-readable: PASS/FAIL, counts, duration, the git commit +
  tier + selection + env (incl. WSL distro & Claude CLI version) it was verified against,
  and any failures with one-line reasons.
- `results_<stamp>.xml` — JUnit XML equivalent for tooling.

So your report is just:

1. Run the command above.
2. Paste the **entire contents of `tests\log\results_latest.txt`** verbatim. That file
   *is* the report — it self-documents pass/fail and the environment.
   `Get-Content tests\log\results_latest.txt`
3. **Only if it shows any failures:** also paste a 10–30 line excerpt around the failure
   from the newest debug log, and then **stop** (do not attempt a fix — a Claude session
   triages against the docs and `ARCHITECTURE.md §10`).
   `Get-ChildItem tests\log\tmux_bridge_*.log | Sort-Object LastWriteTime | Select-Object -Last 1`

That's it. No manual template — the `results_latest.txt` file is the artifact, so the
result doesn't depend on you transcribing it correctly.
