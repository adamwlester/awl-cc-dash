# Build prompt — Context breakdown & Compact controls (spike)

## 1. Header

- **Test working name:** `context_compact_live`
- **§10 item:** **#09 — Context breakdown & Compact controls — 🧪 needs-spike**
- **One-line goal:** Probe whether a per-category context breakdown can be scraped from `/context`, and whether compaction events are reliably markable from a `compact_boundary` transcript entry after `/compact` — going *beyond* the already-proven total-usage + turns derivation, without re-testing it.

You are a **build agent**. Build exactly ONE new live test from this prompt, run it, and record the honest outcome. This is a **spike**: a genuine "this is impossible / too fragile, settle for total+turns" finding is a legitimate, first-class result — do not fabricate a green.

---

## 2. Read first (open these — do not guess)

- **Your §10 item, for exact wording:** `docs/ARCHITECTURE.md` **§10, item 9** ("Context breakdown & Compact controls", around line 1149). Read all five bullets (Evidence / Desired / Blocker / Research-POC-must-establish / Fallback).
- **The research that scoped this:** `dev/notes/research/claude-code-mode-control-research.md` — **"Question 4: context monitoring"** (starts line 125), especially **item 3** (per-category breakdown is a dead-end for clean structured access — only `/context` renders it, computed internally, never exposed) and **item 4** (no live mid-run per-category reading; `/context` queues to idle and renders to screen). Items 1–2 confirm the *overall* percentage is already clean — that is the part you must NOT re-test.
- **THE pattern to copy:** `tests/test_bridge_finisher_live.py` — mirror its shape exactly (see §4).
- **Modules this test touches (read them):**
  - `sidecar/drivers/bridge.py` — `derive_context_usage()` (line 103, the total-usage + turns math, **already unit-proven**, do not retest) and `BridgeDriver.get_context_usage()` (line 681).
  - `sidecar/main.py` — `GET /sessions/{id}/context` (line 1605) and `POST /sessions/{id}/console/run` (line 1354 — sends a slash command over the bridge then `read()`s 40 lines of screen back).
  - `bridge/bridge.py` — `read()` (line 534, `capture-pane -p -J -S`, strips ANSI), `read_log()` (line 960, parses the JSONL transcript), `send()` (line 497), `create()` (line 283), `close()` (line 589).

---

## 3. Mechanism / hypothesis

There are **two independent levers**, each with its own read-back:

**Lever A — per-category breakdown via `/context` screen-scrape.**
`/context` is the ONLY surface that renders the per-category split (system prompt / tools / MCP / memory / messages / free space). Per **Question 4 item 3**, this table is computed internally and **never exposed as structured data** — no statusline field, no hook field, no transcript record yields it. Per **item 4**, `/context` queues until the agent is idle and renders to the screen; it does not interrupt a run and does not emit structured data. So the only possible path is: at an idle boundary, `send("/context")`, wait, then `read()`/`scrollback()` the screen and parse the rendered rows.
**Expected outcome:** you can probably *see* category rows on screen, but parsing them into stable, labeled numbers is **fragile and point-in-time**. The research strongly predicts this settles at "screen-scrape-only snapshot, not a clean feed." Treat a robust parse as the win condition and a fragile/unparseable screen as the honest negative.

**Lever B — compaction event marking via `compact_boundary`.**
`/compact` forces a compaction. The hypothesis (from the §10 blocker bullet) is that compaction events are **inferable only from `compact_boundary` transcript metadata**. So: force `/compact`, wait for it to finish, then `read_log()` the transcript and check whether a `compact_boundary` entry (or an entry whose type/subtype/metadata marks a compaction) appears.
**Expected outcome:** either a discoverable transcript marker exists (win — record its exact shape) or it does not appear reliably (negative — record what the transcript actually contains post-compact).

**Framing per the research:** the likely honest end-state for this spike is Lever A "settle for total/turn usage" (already proven in `derive_context_usage`) plus a Lever B finding on whether `compact_boundary` is real. Do not force either lever to green.

---

## 4. Build this

Create **ONE** new file: `tests/test_context_compact_live.py`. Module-level:

```python
pytestmark = [pytest.mark.integration, pytest.mark.slow]
```

Mirror the **finisher shape** (`tests/test_bridge_finisher_live.py`): each test body is an `async def flow()` run via `asyncio.run(flow())`; concise console output, DEBUG detail to `logging.getLogger(__name__)`; a throwaway WSL dir. **Deviation from the finisher (critical — see §7):** do NOT depend on conftest's session-scoped `bridge` fixture. Instantiate your **own** `TmuxBridge()` inside this module for WSL shell helpers and for driving the session, and give your session a **unique, slug-prefixed name**.

Because these levers exercise the raw bridge (send a slash command, read the screen / transcript back), you can drive the **bridge directly** rather than the `BridgeDriver` — that keeps the test self-contained and avoids the driver's `get_context_usage()` no-`/context` shortcut. (You may optionally cross-check against `BridgeDriver.get_context_usage()` for the total-usage number, but that is not the point of the spike.)

Sketch:

```python
import sys, uuid, asyncio, logging
from pathlib import Path
import pytest

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))
from bridge import TmuxBridge   # top-level package from repo root

log = logging.getLogger(__name__)
pytestmark = [pytest.mark.integration, pytest.mark.slow]

SLUG = "ctxcompact"
```

**Flow (single test, or two tests sharing a helper — your call, but keep it ONE file):**

1. **Spawn** a tab-less, uniquely-named session: build `name = f"{SLUG}-{uuid.uuid4().hex[:8]}"`, make a throwaway WSL dir `f"/home/lester/awl-{SLUG}-{uuid.uuid4().hex[:8]}"` via `br._run(f"mkdir -p {dir}")`, then `br.create(name, cwd=dir)` — **`show=False` (the default); never `show=True`.**
2. **Prime real context** so `/context` and `/compact` have something to act on: `br.send(name, "Reply with exactly: PRIMED")` then `br.wait_idle(name, timeout=120)` (and/or poll `read_log` for the assistant reply, as the finisher's `_send_marker_and_wait` does). A single short turn is enough to make `/context` render non-trivial rows.
3. **Lever A — `/context`:** at idle, `br.send(name, "/context")`, wait (`wait_idle` or a short `asyncio.sleep` — `/context` renders to screen, it is not a turn), then capture `br.scrollback(name, max_lines=200)["content"]` (scrollback is safer than a 50-line `read()` for a tall table). Parse for category labels — look for the rendered rows (system prompt / tools / MCP / memory / messages / free space). Record what you actually find.
4. **Lever B — `/compact`:** at idle, `br.send(name, "/compact")`, then wait for compaction to complete (`wait_idle(name, timeout=180)` — compaction can be slow; it summarizes the whole context). Then `entries = br.read_log(name)` and scan for a `compact_boundary` marker (check entry `type`, and any `subtype`/`isCompactSummary`/`compactMetadata`-style fields — inspect the raw entries and log them, since the exact field name is what you are trying to establish).
5. **Read the result back and assert** — see §5.

---

## 5. The read-back is the crux

Sending `/context` and `/compact` is trivial; **proving the result is machine-readable is the entire test.** A screen that shows rows a human can read but your parser cannot stabilize is **not** a pass — it is the predicted negative finding.

- **Lever A observable:** the per-category rows parsed off the `/context` screen — specifically labeled numbers for **system prompt / tools / MCP / memory / messages / free space**. The read-back is `scrollback()`/`read()` (ANSI already stripped by `capture-pane -p -J`). Assert that you can extract **at least the category labels and their token/percent values** into a dict with stable keys. If the table cannot be parsed into stable labeled values, that is a **FINDING**, not a pass.
- **Lever B observable:** a `compact_boundary` (or equivalently compaction-marking) entry in `read_log(name)` **after** `/compact`. The read-back is `read_log()`. Assert the marker exists and record its exact shape (type + fields). If no such entry reliably appears, that is a **FINDING** on whether `compact_boundary` marks compaction — record what the transcript contains instead.
- **Do NOT** substitute the already-proven total-usage + turns number for either observable and call the category/compaction question answered. That number is the *fallback*, not the deliverable of this spike.

---

## 6. Two honest exits (spike-or-omit)

- **WORKS** → keep the file as a durable live test. If Lever A parses cleanly, assert on the category dict and add a short note (in the module docstring + DEVLOG) on the exact rendered format and how stable it looked. If Lever B finds a reliable `compact_boundary`, assert on it and record its shape. Note precisely what was learned.
- **GENUINELY IMPOSSIBLE AFTER A REAL LIVE ATTEMPT** → do **not** fabricate a green. "Impossible" requires an **actual live run** (spawn a real session, send the real commands, read the real screen/transcript) — never a code-reading no-op. Write up the findings: what `/context` actually rendered and why it could not be parsed stably, and/or what the transcript showed post-`/compact`. Then **propose moving §10 item 9 to the fallback** ("show total usage + turn count only — proven today; no per-category rows; richer compaction controls deferred to an SDK path"), and report that recommendation to the human. Per the item guidance, **"settle for total/turn usage" recorded as a finding is a legitimate outcome of this spike.** Keep the file if any portion (e.g. Lever B) does prove out; otherwise leave a skipped/xfail test carrying the finding in its reason string rather than a fake assertion.

> Item-specific guidance from the orchestrator: the research predicts the per-category breakdown is a screen-scrape-only, point-in-time snapshot. Do NOT retest the unit-proven total-usage + turn derivation — it is out of scope here.

---

## 7. Isolation rules (parallel-safe — CRITICAL)

Reproduce ALL of these in the file (as comments) and obey them:

- **ONE new file only** — `tests/test_context_compact_live.py`. Do not add or modify any other test file.
- **Uniquely-named tmux session** — prefix the name with the test slug (`ctxcompact-<uuid8>`). Never a fixed/shared name.
- **NEVER call `tmux kill-server`** in teardown (it kills sibling agents' sessions).
- **Run ONLY your own new test in isolation** — not the whole live tier.
- **Do NOT edit `tests/conftest.py`, `pyproject.toml`, or `tests/README.md`.** If you think you need a shared change (a new fixture, a marker, or the pythonpath tidy), **STOP and report it to the human** — do not edit a shared file.
- **The non-obvious trap:** the finisher leans on conftest's session-scoped `bridge` fixture, whose **setup AND teardown both call `_kill_all_tmux()` (= `tmux kill-server`)**. That is fine for a human running one file alone, but it would **kill sibling agents' live sessions** and breaks the parallel-safe rule. So do **NOT** depend on that fixture for a destructive lifecycle. Instead:
  - Instantiate your **own** `TmuxBridge()` inside this module for WSL shell helpers (`_run` for mkdir/cat/rm) and for driving (create/send/read/read_log).
  - In teardown remove **ONLY** your own uniquely-named session via `br.close(name)` and `br._run(f"rm -rf {dir}")` for your own throwaway dir. Never a broadcast kill.
- If you believe you truly need the shared fixture or a new shared fixture/marker, **STOP and report to the human** rather than editing a shared file.

---

## 8. Definition of done

- Run your **single** new test through the repo venv and paste the **actual** pass/fail line verbatim (the pytest `= N passed =` / `= N xfailed =` / `= N failed =` terminal line and/or `tests/log/results_latest.txt`) — no paraphrase.
- Windows PowerShell command:
  ```powershell
  .\.venv\Scripts\python.exe -m pytest tests\test_context_compact_live.py -m integration
  ```
  (or `tests\run.ps1 tests\test_context_compact_live.py -m integration`)
- Create the venv first if missing:
  ```powershell
  python -m venv .venv; .\.venv\Scripts\python -m pip install -r requirements.txt
  ```
- This test does not render UI, so the CLAUDE.md "Verifying UI changes" browser pass does not apply — but if you touch anything that renders, follow it.
- **DEVLOG the change before finishing** — append a new dated entry at the bottom of `DEVLOG.md` (what you built, what the spike found — including any "settle for total/turns" recommendation, and the pass/fail line). Do this before telling the user you are done.

---

## 9. Guardrails (from CLAUDE.md)

- **Never create a git branch.** Work on `main`. Do not run `git checkout -b` / `switch -c` / `branch <name>` / `worktree add` — they are gated and will prompt; if one prompts, STOP and ask.
- **Bridge sessions stay TAB-LESS.** Never pass `show=True` to `create()` and never call `show()` — an auto-popped Windows Terminal tab steals the user's focus. Programmatic creation must be tab-less.
- **Scratch artifacts go to `.scratch/`** (gitignored) — never the repo root. Any screen dumps / debug output you save for diagnosis go there.
- **pytest is the standard** — no ad-hoc scripts; this deliverable is a pytest file in `tests/`.
