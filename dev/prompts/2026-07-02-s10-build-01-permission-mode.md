# Build prompt — Mid-run permission-mode change (live spike)

## 1. Header

- **Test working name:** `permission-mode-cycle-live`
- **§10 item:** **#01 — Mid-run permission-mode change — 🧪 needs-spike** (docs/ARCHITECTURE.md §10, item #01; Priority band: High)
- **Goal:** Prove (or disprove) that an agent's permission mode can be changed **live, mid-run**, by cycling `Shift+Tab` through the bridge and reading the new mode back from the TUI status line — and, crucially, that the new mode **actually changes behavior** (an auto-accepted Write stops raising a permission prompt), not just the on-screen indicator.

This is a **spike-or-omit** task. A real live attempt decides the outcome. Do **not** fabricate a green.

---

## 2. Read first (open these before writing a line)

1. **Your §10 item, verbatim:** `docs/ARCHITECTURE.md` → **§10, item #01 "Mid-run permission-mode change"**. Read the item's four bullets (Desired / Blocker / Research-POC-must-establish / Fallback) for the exact wording you are testing against — sections 3–6 below paraphrase them but the doc is authoritative.
2. **The research, Question 1:** `dev/notes/research/claude-code-mode-control-research.md` → section **"Question 1 (top priority): setting permission mode on a running TUI session"** — read *The mechanism, settled*, *Ranked approaches* (#1 especially), *Gotchas to design around*, and the **Recommended path** steps 1 & 3. This is your mechanism authority.
3. **THE pattern to copy:** `tests/test_bridge_finisher_live.py` — copy its **shape** (module-level `pytestmark`, the `sys.path` insert of `sidecar/`, a throwaway WSL diag dir keyed on `uuid`, an async `flow()` run via `asyncio.run(flow())`, generous idle/poll loops with `asyncio.sleep`). You will NOT reuse its `bridge` fixture (see §7).
4. **The module(s) this test touches** (read the relevant lines):
   - `sidecar/drivers/bridge.py` — `BridgeDriver.CAPABILITIES` (note `set_mode` is **absent**) and `async def set_mode()` (a deliberate **no-op**, with the live-finding comment block above it: "permission mode → cycles via Shift+Tab only (relative, no absolute set)"). This test is what challenges that no-op.
   - `bridge/bridge.py` — `TmuxBridge.create()` (signature incl. `permission_mode`, `claude_args`, `show=False`), `send()`, `keys(name, *key_names)` (maps each name straight onto `tmux send-keys -t NAME <key>`), `read(name, lines)` (uses `capture-pane -p -J -S` — **strips ANSI**), `status(name)` (returns `state` ∈ idle/generating/permission_prompt/unknown, plus a parsed `permission` detail), `wait_idle(name, timeout, interval)`, `close(name)`, `_run(bash_cmd)` (raw WSL shell).
   - `sidecar/main.py` — `POST /sessions/{id}/mode` (`set_mode`, lines ~1527–1545): today it returns **HTTP 400 "Driver has no mode control"** because the driver doesn't advertise `set_mode`. That honest 400 is the status quo this spike is trying to make obsolete.

---

## 3. Mechanism / hypothesis

**Known lever (confirmed against research Question 1 → Ranked approach #1 and Recommended path steps 1 & 3):** the *only* in-session control surface for an interactive Claude Code TUI is keystrokes. Permission mode has **no flag-free absolute set, no slash command, no API** — it only advances via `Shift+Tab` (`chat:cycleMode`). The research settles two facts we lean on:

- **The cycle is deterministic** (research "The mechanism, settled"): base order is `default → acceptEdits → plan → (wrap to default)`. Optional modes slot in **after `plan`** only if pre-armed at launch: `bypassPermissions` first (added by launching with `--allow-dangerously-skip-permissions`, which puts bypass *in the cycle without activating it*), then `auto` (if the account's one-time opt-in was accepted). Press-count math must key off which optional modes are enabled for that session.
- **Current mode is readable from the status bar** (research "The mechanism, settled"): e.g. `⏵⏵ accept edits on` for `acceptEdits`. `read()` strips ANSI, so this is a plain-text substring match.

`Shift+Tab` reaches tmux as the key name **`BTab`** (research Ranked #1 cites the tmux modifier-keys wiki; `keys(name, "BTab")` emits exactly `tmux send-keys -t NAME BTab`).

**What we expect:** launching in `default` and sending **one** `BTab` from a known-idle screen advances the indicator to `acceptEdits` ("accept edits on"), deterministically. **And** — the load-bearing part — `acceptEdits` then **auto-accepts an Edit/Write** so a subsequent Write raises **no** permission prompt.

**The gotchas we must design around** (research "Gotchas to design around" + "Open questions" 1 & 2):
- **Idle-gating is mandatory** — never send `BTab` mid-prompt or mid-turn; a stray key lands in a textarea. Gate every keystroke on a verified idle/safe screen state (`wait_idle` + a `status()` check).
- **Cycle membership shifts with launch flags** — this test does NOT pre-arm bypass/auto, so its cycle is exactly `default → acceptEdits → plan`. One `BTab` from `default` = `acceptEdits`. (If a later, separate spike wants bypass in the cycle, it must launch the raw bridge with `claude_args="--allow-dangerously-skip-permissions"` — a *dangerous* flag; do NOT add it to this durable test.)
- **The auto opt-in menu can interrupt the cycle** — not in-cycle here (auto isn't armed), but if any unexpected menu appears after a `BTab`, treat it as a finding, don't blind-press through it.
- **Suppression has regressed repeatedly (#52822, #55255) — verify BEHAVIOR, not just the indicator.** This is why §5 exists: on some builds the indicator flips to acceptEdits but Edit/Write prompts still fire. We must confirm on *this* build that landing on acceptEdits genuinely suppresses the Write prompt.

---

## 4. Build this

Create **one** new file: `tests/test_permission_mode_cycle_live.py`. Marked module-level:

```python
pytestmark = [pytest.mark.integration, pytest.mark.slow]
```

Mirror the finisher's shape, but **drive the raw `TmuxBridge` directly** (no `BridgeDriver`, no HTTP layer) — the behavior we verify is a raw screen-state observable (`status()["state"] == "permission_prompt"`), which is exactly what the bridge exposes and needs no async event pump. Instantiate your **own** `TmuxBridge()` in the test module (see §7 — do NOT use conftest's `bridge` fixture).

Concrete flow (one test function; body is an async `flow()` run via `asyncio.run(flow())`, matching the finisher):

1. **Own bridge + unique, slug-prefixed session.** `bridge = TmuxBridge()`. Pick `name = f"permmode-{uuid.uuid4().hex[:8]}"`. Make a throwaway WSL dir `diag = f"/home/lester/awl-permmode-{uuid.uuid4().hex[:8]}"`, `bridge._run(f"mkdir -p {diag}")`.
2. **Launch tab-less in `default` mode.** `bridge.create(name, cwd=diag, permission_mode="default", show=False)` — **never** `show=True`. Then `bridge.wait_idle(name, timeout=60, interval=1.0)` so the TUI finishes loading.
3. **Baseline: default mode DOES prompt.** `bridge.send(name, "Create a file named a.txt containing exactly the word banana. Use the Write tool. Do not do anything else.")`. Poll `bridge.status(name)["state"]` until it becomes `"permission_prompt"` (loop ~40 × 0.5 s). Assert it did — this proves the session starts in a prompting mode. Then **dismiss it**: `bridge.keys(name, "Escape")`, and `wait_idle` back to a safe state. (a.txt must NOT exist — optional secondary assert via `_cat`.)
4. **Confirm indicator baseline.** `bridge.read(name, lines=20)["content"]` — assert `"accept edits on"` is **absent** (we're still in default).
5. **Idle-gate, then cycle one step.** Re-confirm `status(name)["state"]` is `"idle"` (not generating, not a prompt). Send exactly one `BTab`: `bridge.keys(name, "BTab")`. `await asyncio.sleep(1)`.
6. **Read the indicator back (retry).** Loop ~10 × 0.5 s reading `bridge.read(name, lines=20)["content"]` until it contains `"accept edits on"` (case-insensitive). Assert it does — the indicator advanced `default → acceptEdits`. On mismatch after retries → this is a finding (see §6), likely a `BTab`-encoding misfire; the research's fallback is the rebound-keybinding path (Ranked #2).
7. **THE crux — verify behavior, not just the indicator.** `wait_idle`, then `bridge.send(name, "Create a file named b.txt containing exactly the word cherry. Use the Write tool. Do not do anything else.")`. Now poll `status(name)["state"]` for ~20 s and assert it **never** becomes `"permission_prompt"`, AND that `b.txt` lands with the expected contents (`_cat(bridge, f"{diag}/b.txt") == "cherry"`, polling ~40 × 0.5 s). Both together prove `acceptEdits` actually suppressed the Write prompt on this build.
8. **Teardown (see §7).** In a `finally`, `bridge.close(name)` (closes ONLY this session) and `bridge._run(f"rm -rf {diag}")`. **Never** `kill-server` / `shutdown()`.

Add a small `_cat(bridge, path)` helper mirroring the finisher's (`cat {path} 2>/dev/null || echo __MISSING__`), and a `_status_becomes(bridge, name, target, timeout)` poll helper. Keep DEBUG logging (`logging.getLogger(__name__)`) of each screen read so a failure is diagnosable from `tests/log/`.

> Note on the driver seam: this test deliberately bypasses `BridgeDriver`/`POST /sessions/{id}/mode` because those are no-ops/400 **today** — the point of the spike is to establish the *mechanism* the driver would wire. If the mechanism proves out, wiring `set_mode()` (read-compute-send-`BTab`-verify) + advertising `set_mode` in `CAPABILITIES` is downstream product work, NOT part of this test.

---

## 5. The read-back is the crux

Sending `BTab` is trivial — a single `keys(name, "BTab")`. **Proving it took effect is the entire test, and it has two layers:**

- **Layer 1 — indicator:** re-read the status line via `bridge.read(name)` and confirm the text flipped to `"accept edits on"` (step 6). ANSI is already stripped by `capture-pane -p -J` so this is a plain substring match.
- **Layer 2 — behavior (the real crux):** re-send a Write and confirm the permission prompt **does not fire** — `status(name)["state"]` never reaches `"permission_prompt"` and the file is written unattended (step 7). Research "Open questions" #2 and issues #52822 / #55255 warn that suppression has regressed on some builds — the indicator can flip while prompts still fire. A test that checks only Layer 1 would falsely pass on exactly the broken builds this spike exists to catch.

If the mode change is not observable in *both* layers, that is a **FINDING, not a pass**. Name the observable plainly in asserts and in the write-up: (a) status-line text `"accept edits on"`; (b) absence of `permission_prompt` state + successful unattended write.

---

## 6. Two honest exits (spike-or-omit)

- **WORKS** (indicator flips AND behavior suppresses): keep `tests/test_permission_mode_cycle_live.py` as a **durable live test**. In its module docstring, record what was learned: single `BTab` from `default` reaches `acceptEdits` deterministically on this build, and acceptEdits genuinely suppresses the Write prompt (Layer-2 confirmed). This is the green light to later wire `BridgeDriver.set_mode()` as read-compute-send-`BTab`-verify and flip §10 #01 from 🧪 needs-spike toward built.
- **GENUINELY IMPOSSIBLE AFTER A REAL LIVE ATTEMPT** (e.g. `BTab` never moves the indicator, or the indicator flips but the Write still prompts every time — a live-confirmed suppression regression): do **NOT** fabricate a green. Write up the findings (which layer failed, exact screen captures from `tests/log/`, build version) and propose the item's own **Fallback**: mode stays **launch-only** — the UI presents permission mode as a launch-time choice, never a fake-live control — and recommend moving §10 #01 to **Decided omissions** (or leaving it launch-only). "Impossible" requires an **actual live run**, never a re-read of the no-op code. If `BTab` specifically misfires, note the research fallback (rebind `chat:cycleMode` via `~/.claude/keybindings.json`, Ranked #2) as the next thing to try before declaring omission.

---

## 7. Isolation rules (parallel-safe — critical; reproduce in the file)

Other agents may be running their own live bridge sessions at the same time. Obey all of these:

- **ONE new file only:** `tests/test_permission_mode_cycle_live.py`. Add nothing else.
- **Uniquely-named, slug-prefixed session:** `permmode-<uuid hex>` (as in step 1). Never a fixed name.
- **NEVER `tmux kill-server`** (and never call `bridge.shutdown()`) in teardown — it kills *sibling agents'* sessions. Tear down with `bridge.close(name)` for **your own** session only, plus `rm -rf` your own diag dir.
- **Run ONLY your own new test in isolation** — not the whole live tier (see §8's command). Do not launch the full `-m integration` suite.
- **Do NOT edit shared files:** not `tests/conftest.py`, not `pyproject.toml`, not `tests/README.md`. If you think you need a new fixture, marker, or a pythonpath tidy — **STOP and report it to the human** instead of editing a shared file.
- **The non-obvious trap — do NOT depend on conftest's `bridge` fixture.** The finisher leans on conftest's **session-scoped `bridge` fixture, whose setup AND teardown both call `_kill_all_tmux()` (= `tmux kill-server`)**. That is fine for a human running that one file alone, but under parallel agents it would kill sibling live sessions — breaking this rule. So **instantiate your OWN `TmuxBridge()`** inside your test module for both the WSL shell helpers (`_run` mkdir/cat/rm) and for driving (`create`/`send`/`keys`/`read`/`status`/`wait_idle`/`close`), and in teardown remove ONLY your own uniquely-named session and your own throwaway dir. Do not import or request the `bridge` fixture.

---

## 8. Definition of done

- Run your **single** new test through the repo venv and paste the **actual** pass/fail line — no paraphrase (the pytest `= N passed =` / `= N failed =` terminal line, and/or `tests/log/results_latest.txt`). Windows PowerShell:

  ```powershell
  .\.venv\Scripts\python.exe -m pytest tests\test_permission_mode_cycle_live.py -m integration
  ```
  (equivalently `tests\run.ps1 tests\test_permission_mode_cycle_live.py -m integration`). Create the venv first if missing: `python -m venv .venv; .\.venv\Scripts\python -m pip install -r requirements.txt`.
- This test drives a TUI, not a rendered web UI, so there is no browser pass to do. (If your write-up produces any rendered artifact, follow CLAUDE.md "Verifying UI changes"; otherwise not applicable.)
- **DEVLOG the change before finishing** — append a dated entry at the bottom of `DEVLOG.md` (what the spike established: WORKS or IMPOSSIBLE + the observable, and the pass/fail line), per the DEVLOG rule. A `Files:` line listing the new test.

---

## 9. Guardrails (from CLAUDE.md)

- **Never create a git branch.** Work on `main`. Do not run `git checkout -b` / `switch -c` / `branch <name>` / `worktree add` — they are gated and will prompt; if one prompts, stop and ask, don't work around it.
- **Bridge sessions stay TAB-LESS.** Create with `show=False` (the default) — **never** pass `show=True`, never call `show()`. A terminal opens only on a deliberate human request, never as a side effect of a test.
- **Scratch artifacts go to `.scratch/`** (gitignored) — never the repo root or other project folders. This test's throwaway state lives in its WSL diag dir and is `rm -rf`'d in teardown.
- **pytest is the standard** — no ad-hoc scripts. Non-hermetic → `@pytest.mark.integration`; slow → `@pytest.mark.slow` (both set module-level here).
