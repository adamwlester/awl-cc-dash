# Build-prompt — Fast-mode toggle live spike

## 1. Header

- **Test working name:** `fast_mode_toggle_live`
- **§10 item:** `#03 — Fast-mode toggle (Meta+O) — 🧪 needs-spike` (High priority band)
- **Goal:** Prove (or disprove) that Fast (Opus) mode can be toggled on a *running* bridge agent by sending the `chat:fastMode` keybinding (`Meta+O`) through the bridge, and that the resulting Fast-mode state is **readable back** from the screen. If it cannot be observed, that is a finding — not a pass.

---

## 2. Read first (open these before writing a line)

- **Your §10 item:** `docs/ARCHITECTURE.md` §10, **item 3 "Fast-mode toggle (`Meta+O`)"** (currently around lines 1078–1087). Read the four bullets verbatim — Desired / Blocker / Research-POC / Fallback — they define done. Also read the "Decided omissions" note (~line 1216) that explains this item was moved *back* into the queue.
- **The research:** `dev/notes/research/claude-code-mode-control-research.md` — **Question 3**, specifically **Input injection #3** (line ~109: `/fast` opens an interactive panel, no clean scrape) and **#4 "Keybinding actions for fast/thinking toggles"** (line ~110: `chat:fastMode` = `Meta+O`; action-confirmed, integration-untested; **both are toggles with no absolute on/off, so read current state first**; and note the research's caveat that you may need to **rebind the action to a clean key** and send that).
- **THE pattern to copy:** `tests/test_bridge_finisher_live.py` — copy its *shape* (see §4). Note the module-level `pytestmark`, the `sys.path` insert of `sidecar/`, the `_Driven` helper, the `diag_dir` throwaway-WSL-dir fixture, and the `asyncio.run(flow())` bodies.
- **The modules this test touches:**
  - `sidecar/drivers/bridge.py` — `BridgeDriver`. Read the live-findings comment block (~lines 707–735) and `set_fast()` (~line 732), a **deliberate no-op** because `/fast` opens a panel with no reliable scrape. `CAPABILITIES` does **not** include `set_fast`, so `supports("set_fast")` is `False` today — that's exactly what this spike challenges.
  - `bridge/bridge.py` — `TmuxBridge`. Confirm `keys(name, *key_names)` (~line 517; each key name maps straight onto `tmux send-keys -t NAME <key>`) and `read(name, lines=50)` (~line 534; uses `capture-pane -p -J -S` — **plain, no `-e`, so ANSI is stripped**). Also `scrollback(name, max_lines)` (~line 834) and `close(name)` (~line 589).
  - `sidecar/main.py` — `POST /sessions/{id}/fast` (~line 1583): returns **400 "Driver has no fast control"** today because `set_fast` isn't advertised. You are *not* testing the HTTP layer — drive the driver/bridge directly, like the finisher does — but know this endpoint is the thing your finding unblocks (or keeps closed).

---

## 3. Mechanism / hypothesis

**Known lever (confirmed against code + research):** Claude Code exposes a keybinding *action* `chat:fastMode` bound to `Meta+O`, per research Q3 #4. There is **no** clean slash command — `/fast` opens an interactive panel that the driver comments (bridge.py ~711) explicitly say could **not** be reliably scraped, so `set_fast()` was left a no-op. The keybinding action is the only candidate lever.

**What we send:** `bridge.keys(name, "M-o")` — tmux's key name for `Meta+O` (Meta = Alt; `M-o`). This is a **toggle** (no absolute set), so the test must **read the Fast-mode state before**, send `M-o`, then read **after**, and assert the state *flipped*.

**What we expect:** a Fast-mode indicator to appear/disappear in the TUI screen (`bridge.read()`), and/or the effective model to switch to **Opus** when Fast is on. Per research Q3 #4, these keybinding actions are *action-confirmed but integration-untested* — so an equally valid outcome of this spike is discovering that (a) `M-o` isn't bound by default and must be **rebound to a clean key** before it does anything, or (b) the toggle fires but leaves **no scrapeable on-screen state**. Both are legitimate findings, not failures to hide.

---

## 4. Build this

Create **one** new file: `tests/test_fast_mode_toggle_live.py`. Marked with `pytestmark = [pytest.mark.integration, pytest.mark.slow]` at module level. Mirror the finisher's shape.

Concrete flow:

1. **Set up like the finisher.** Insert `sidecar/` on `sys.path` (copy the `_REPO_ROOT / "sidecar"` block from the finisher, lines ~28–35). Import `BridgeDriver` and `DriverConfig`. Instantiate your **own** `TmuxBridge()` inside the module for WSL shell helpers and screen reads — **do not** rely on the shared conftest `bridge` fixture (see §7 for why).
2. **Unique, tab-less throwaway dir + session.** Make a slug-prefixed WSL dir yourself, e.g. `/home/lester/awl-fastmode-<uuid8>` via `your_bridge._run(f"mkdir -p {path}")`; `rm -rf` it in teardown. Drive a `BridgeDriver(DriverConfig(cwd=path, permission_mode="default"), events.append, session_id="fastmode-<uuid8>")`. The driver derives its tmux session name (`driver.tmux_name`) — confirm the name is unique/slug-prefixed; if you need to force uniqueness, pass a slug-prefixed `session_id`. **Never pass `show=True`; never call `show()`.**
3. **Start it and let it settle.** `await driver.start()`, then a short `asyncio.sleep` so the TUI paints. You do **not** need a running turn for a mode toggle — the toggle applies to the session, not a turn — but the TUI must be at its prompt.
4. **Read the BEFORE state.** `before = your_bridge.read(driver.tmux_name, lines=40)["content"]` (and/or `scrollback(...)`). Log it at DEBUG. Identify the Fast-mode indicator token in this baseline (e.g. a "fast"/"Opus" marker in the status/footer region). If you cannot even find where Fast state *would* show, note that now.
5. **Send the toggle.** `your_bridge.keys(driver.tmux_name, "M-o")`. Sleep ~2–3s.
6. **Read the AFTER state.** `after = your_bridge.read(driver.tmux_name, lines=40)["content"]`. Log at DEBUG.
7. **Diff and assert** (the crux — see §5). Assert the Fast/Opus indicator **changed** between `before` and `after`. Optionally toggle a second time and assert it flips **back**, which is stronger evidence the lever is real and not a one-way screen artifact.
8. **Teardown:** cancel any event-consumer task, `await driver.close()` (kills only this session), `your_bridge.close(driver.tmux_name)` as belt-and-suspenders if the session still exists, and `rm -rf` your throwaway dir. **Never** `tmux kill-server`.

If `M-o` produces no observable change, before concluding "impossible" try the research's rebind path once: rebind `chat:fastMode` to a clean key via the keybindings mechanism and send that instead (document exactly what you tried). Only after a real send-and-read-back attempt may you write the omission finding.

---

## 5. The read-back is the crux

Sending `M-o` is one line and always "succeeds" at the tmux level — that proves **nothing**. The entire value of this test is **reading the Fast-mode state back and showing it flipped.**

- **Primary observable:** the Fast-mode / Opus indicator in the TUI screen via `bridge.read(driver.tmux_name)` (ANSI already stripped). Capture it **before and after** the `M-o` send and diff the two captures.
- **Secondary corroboration:** the effective model becoming **Opus** when Fast is on (look for a model marker on screen or in `scrollback`).
- **If the toggle fires but leaves no scrapeable state** (nothing in `read()`/`scrollback()` distinguishes on from off), that is a **FINDING, not a pass** — it means the control isn't safely surfaceable to the UI, which is precisely the blocker in the §10 bullet. Write it up (see §6); do not assert on a screen token that isn't really there just to go green.

---

## 6. Two honest exits (spike-or-omit)

- **WORKS** → `M-o` (or a clean rebind) toggles Fast mode and the change is **read-backable**. Keep the file as a durable live integration test, and add a short note (test docstring + DEVLOG) of what was learned: the exact key sent, the exact indicator string that flips, and whether a rebind was needed. This is the evidence that would let someone wire `set_fast` for real and flip the 400 endpoint.
- **GENUINELY IMPOSSIBLE AFTER A REAL LIVE ATTEMPT** → do **not** fabricate a green. Requires an **actual** live send-and-read-back attempt (default `M-o` *and* at least one rebind attempt) — never just re-reading `set_fast`'s no-op and declaring defeat. Write up the findings (what was sent, what the screen showed before/after, why the state is unobservable) and **propose moving §10 item #03 to "Decided omissions"** with the evidence, landing Fast as a launch-time choice rather than a fake-live toggle. Report this to the human; do not edit `docs/ARCHITECTURE.md` yourself unless asked.

---

## 7. Isolation rules (parallel-safe — CRITICAL — reproduce these in the file header)

Other agents are running their own live bridge sessions at the same time. Violating any of these corrupts their runs.

- **ONE new file only:** `tests/test_fast_mode_toggle_live.py`. Do not touch any other test.
- **Name your tmux session uniquely** — slug-prefixed (`fastmode-...`) so it can't collide with a sibling's session.
- **NEVER call `tmux kill-server`** in teardown (or anywhere). It kills *every* agent's sessions. Remove **only** your own session by name via `close(driver.tmux_name)` / `driver.close()`, and remove only your own throwaway dir.
- **Run ONLY your own new test in isolation** — not the whole live tier.
- **Do NOT edit shared files:** `tests/conftest.py`, `pyproject.toml`, or `tests/README.md`. If you think you need a new fixture, marker, or a pythonpath tidy, **STOP and report it to the human** — do not edit a shared file.
- **The non-obvious trap — do NOT use the conftest `bridge` fixture for a destructive lifecycle.** The finisher leans on conftest's session-scoped `bridge` fixture, whose **setup AND teardown both call `_kill_all_tmux()` (= `tmux kill-server`)**. That's fine for a human running one file alone, but it would **kill sibling agents' live sessions** and breaks the parallel-safe rule. So **instantiate your OWN `TmuxBridge()`** inside your test module for the WSL shell helpers (`mkdir`/`cat`/`rm` via `_run`) and for driving/reading, and in teardown remove **only** your own uniquely-named session and your own dir. If you genuinely believe you need the shared fixture or a new shared fixture/marker, STOP and report to the human rather than editing anything shared.

---

## 8. Definition of done

- Run your **single** new test through the repo venv and **paste the actual pass/fail line verbatim** (the pytest `= N passed =` / `= N failed =` terminal line, and/or `tests/log/results_latest.txt`) — no paraphrase.
  - Windows PowerShell:
    ```powershell
    .\.venv\Scripts\python.exe -m pytest tests\test_fast_mode_toggle_live.py -m integration
    ```
    or
    ```powershell
    tests\run.ps1 tests\test_fast_mode_toggle_live.py -m integration
    ```
  - Create the venv first if missing: `python -m venv .venv; .\.venv\Scripts\python -m pip install -r requirements.txt`.
- Log DEBUG detail (the exact `before`/`after` screen captures, the key sent, any rebind attempt) to the per-run file in `tests/log/` via `logging.getLogger(__name__)` — keep console output concise.
- Nothing here renders a browser UI, so the CLAUDE.md "Verifying UI changes" browser pass does not apply; if you touch anything that renders, follow it.
- **DEVLOG the change** before finishing (append a new dated entry at the bottom of `DEVLOG.md` per the CLAUDE.md DEVLOG rule) — whether the exit was WORKS or an omission finding.

---

## 9. Guardrails (from CLAUDE.md)

- **Never create a git branch.** Work on `main`. Do not run `git checkout -b` / `switch -c` / `branch <name>` / `worktree add` — they're gated and will prompt; if one prompts, STOP and ask.
- **Bridge sessions stay TAB-LESS.** Never pass `show=True`; never call `show()`. A terminal tab opens only on a deliberate human request, never as a side effect of a test.
- **Scratch artifacts go to `.scratch/`** (gitignored) — never the repo root or other project folders.
- **pytest is the standard** — no ad-hoc scripts; this is a pytest test.
