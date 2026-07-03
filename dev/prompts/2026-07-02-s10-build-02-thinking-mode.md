# Build prompt — Thinking-mode toggle spike (Meta+T)

## 1. Header

- **Working name:** `thinking-mode-toggle-live`
- **§10 item:** **#02 — Thinking-mode toggle (Meta+T) — 🧪 needs-spike**
- **Goal:** Prove — or honestly disprove — that thinking can be toggled on a *running* Claude Code agent by sending the `chat:thinkingToggle` keybinding (**Meta+T**) through the bridge, and that the effect is **observable in the transcript** as `thinking`-type blocks appearing/disappearing.

This is a **spike-or-omit** task. A green test is one honest outcome; a written-up "genuinely not observable" finding is the *other* honest outcome. Do **not** manufacture a pass.

---

## 2. Read first (open these before writing a line)

1. **Your §10 item — exact wording.** `docs/ARCHITECTURE.md` §10, item **#2 "Thinking-mode toggle (`Meta+T`)"** (around line 1065). Read all four bullets: Desired / Current blocker / Research-POC-must-establish / Fallback. Also note the "Decided omissions" tail (~line 1216) — that is where this item goes if the spike fails.
2. **The research lever.** `dev/notes/research/claude-code-mode-control-research.md` → **Question 3 → "Input injection" item #4** ("Keybinding actions for fast/thinking toggles", ~line 110). Read items #3 and #4 together: `/thinking` does **not** exist as a slash command; the only lever is the `chat:thinkingToggle` keybinding = **Meta+T**; both toggles have **no absolute on/off** (so read current state first); **thinking-on typically shows `thinking` blocks in the transcript.**
3. **THE pattern to copy.** `tests/test_bridge_finisher_live.py` — mirror its shape: module-level `pytestmark = [pytest.mark.integration, pytest.mark.slow]`, the sidecar-on-`sys.path` shim, a throwaway WSL diag dir, per-test body run via `asyncio.run(flow())`. **Read how it reads the transcript back** — `_send_marker_and_wait()` uses `driver._bridge.read_log(name)` and inspects `(e.get("message") or {}).get("content")`. You will do the same, but looking for **thinking blocks** instead of a marker string.
4. **The modules this test touches:**
   - `sidecar/drivers/bridge.py` — `BridgeDriver`. Confirm `set_thinking()` is a **deliberate no-op** (~line 737: *"No `/thinking` command exists in this Claude Code build. Left a no-op."*) and that `"set_thinking"` is **absent** from `CAPABILITIES` (~line 414). This is exactly the gap the spike challenges.
   - `bridge/bridge.py` — `TmuxBridge`. Confirm `keys(name, *key_names)` maps each name straight onto `tmux send-keys -t NAME <key>` (~line 517), `send(name, text, press_enter=True)` (~line 497), `read_log(name, last_n=None, types=None)` → list of parsed JSONL entries (~line 960), `close(name)` kills **one** session (~line 589).
   - `sidecar/main.py` — `POST /sessions/{id}/thinking` (~line 1594) raises **400 "Driver has no thinking control"** today because `set_thinking` is unsupported. That 400 is the honest status quo your spike is trying to change.

---

## 3. Mechanism / hypothesis

**Known lever (from the item + research Q3/injection #4):** In this Claude Code build there is **no `/thinking` slash command** (sending it yields "No commands match"), and `BridgeDriver.set_thinking()` is a no-op. The *only* candidate lever is the **`chat:thinkingToggle` keybinding, default `Meta+T`**, sent to the live tmux pane as the tmux key name **`M-t`** via `bridge.keys(name, "M-t")`.

**What we expect if the lever works:** `Meta+T` flips a per-session "extended thinking" flag on the running TUI. With thinking ON, an assistant turn that involves non-trivial reasoning emits **`thinking`-type content blocks** into the JSONL transcript (per research Q3 #4: *"thinking-on typically shows `thinking` blocks in the transcript"*). With thinking OFF, those blocks are absent. Because it is a **toggle with no absolute on/off**, we must **read current state first** (observe whether thinking blocks are present at baseline) and then look for a **change** after the toggle — not an absolute target.

**Cite:** research `claude-code-mode-control-research.md`, Question 3 → Input injection **#4** (Meta+T = `chat:thinkingToggle`; action-confirmed, integration-untested; toggles have no absolute on/off; thinking-on shows `thinking` blocks). The doc is explicit that the keybinding *action* exists even though no slash command does.

---

## 4. Build this

Create **one** new file: **`tests/test_thinking_toggle_live.py`**. Slug: **`think`**. Marked at module level:

```python
pytestmark = [pytest.mark.integration, pytest.mark.slow]
```

Mirror the finisher's imports/shim (`_REPO_ROOT`, put `sidecar/` on `sys.path`). You will **NOT** use the shared session-scoped `bridge` fixture (see §7 — its teardown calls `tmux kill-server`). Instead **instantiate your own `TmuxBridge()`** inside the module for both driving and WSL shell helpers.

Two viable shapes — pick the simpler one and note which you chose:

- **Recommended — pure-bridge (synchronous):** drive the whole thing through your own `TmuxBridge`. `keys()`, `send()`, `read_log()`, `wait_idle()`, `close()` are all blocking bridge calls; there is no async driver behavior this observable needs, so you don't need `asyncio.run`. Create the session with `bridge.create(name=<unique>, cwd=<diag_dir>, show=False)` (TAB-LESS — never `show=True`).
- **Alternative — finisher-parity (async):** if you prefer to mirror the finisher literally, wrap the body in `async def flow(): ... ; asyncio.run(flow())` and drive turns via a `BridgeDriver`, but still send `M-t` and read the transcript through a **self-owned `TmuxBridge`** targeting `driver.tmux_name`. Only do this if it doesn't drag in the shared `bridge` fixture.

**Concrete flow (recommended shape):**

1. **Setup** — build a unique session name, e.g. `f"think-{uuid.uuid4().hex[:8]}"`, and a throwaway WSL dir `f"/home/lester/awl-think-{uuid.uuid4().hex[:8]}"` created with `bridge._run(f"mkdir -p {diag}")`. Create the session tab-less: `bridge.create(name=name, cwd=diag, show=False)`, then `bridge.wait_idle(name, timeout=…)` so startup gates clear.
2. **Read baseline state** — send a prompt that **reliably elicits reasoning** (see the read-back note below), e.g. *"Think step by step and solve: a bat and ball cost $1.10 together; the bat costs $1.00 more than the ball. How much is the ball? Show your reasoning."* Then `bridge.wait_idle(name, …)`. Read `bridge.read_log(name, types=["assistant"])` and compute a helper `has_thinking(entries)` (below). Record `baseline = has_thinking(...)`.
3. **Toggle** — `bridge.keys(name, "M-t")`. Optionally `bridge.read(name)` (ANSI-stripped screen) and log whether the TUI surfaces any "thinking on/off" affordance — capture it for the finding either way; don't assert on screen text alone.
4. **Read post-toggle state** — send an **equivalent** reasoning prompt again, `wait_idle`, re-read the transcript, compute `after = has_thinking(...)` over the **new** entries only (slice by entry count / timestamp so you compare the second turn, not the first).
5. **Assert on the change** — see §5. The assertion is about `baseline` vs `after` **differing** in a way consistent with a real toggle, plus the raw evidence logged.

**`has_thinking(entries)` helper** — each transcript entry looks like `{"type": "assistant", "message": {"content": [...]}}`; `content` is a list of blocks. A thinking block is a dict with `block.get("type") == "thinking"` (guard for string content too). Return `True` if any assistant entry in the slice has such a block. Log the count and a short excerpt at DEBUG (`logging.getLogger(__name__)`), per repo test conventions — full detail to `tests/log/`, console stays concise.

---

## 5. The read-back is the crux

Sending `M-t` is a one-line `tmux send-keys` — **trivial**. The entire value of this test is **proving the keystroke changed something observable**. The named observable is: **`thinking`-type content blocks in the JSONL transcript**, read back via `bridge.read_log(name)` and inspected at `entry["message"]["content"][*]["type"] == "thinking"`.

This read-back is **genuinely hard**, and you must respect that:

- **Thinking blocks only appear when the model chooses to reason.** A trivial prompt may emit none even with thinking ON, and a hard prompt may emit some regardless. So: **(a)** use a prompt that reliably triggers reasoning (a small logic/arithmetic trap like the bat-and-ball problem, or "reason through" phrasing), and use the **same class** of prompt both times so the comparison is fair; **(b)** if you cannot get a **stable, repeatable difference** between the toggle states, that is a **FINDING**, not a pass.
- **"Keystroke sent but no observable transcript change" is the honest-omit exit** (§6), never a silent green. Do not assert `True` just because `keys()` returned `{"status": ...}` — that proves nothing about thinking.
- Because it's a toggle with no absolute set, assert on a **transition** (baseline present → after absent, or baseline absent → after present), not on an absolute expected value. If both reads are identical across several attempts, thinking is not read-back-controllable via `M-t` in this build — write that up.

---

## 6. Two honest exits (spike-or-omit)

- **WORKS** — `M-t` produces a **repeatable, observable** change in transcript thinking blocks. Keep `tests/test_thinking_toggle_live.py` as a durable live test asserting the transition. Add a short module docstring note of what was learned (which key, how many attempts to get stability, what the observable looked like). This unblocks wiring `set_thinking()` + advertising the `set_thinking` capability + the `POST /sessions/{id}/thinking` endpoint later.
- **GENUINELY IMPOSSIBLE AFTER A REAL ATTEMPT** — you actually spawned a live session, sent `M-t`, ran reasoning prompts on both sides, read the transcript back, and the thinking blocks **do not observably respond** (or respond non-repeatably). Do **NOT** fabricate a green. Instead: (1) keep the file but have it record the finding (e.g. an `xfail`/skip with a clear reason string, or a test that asserts the *observed* no-op and documents it), (2) write up the findings in your final report, and (3) **propose moving §10 item #2 to "Decided omissions"** with the fallback wording: *thinking becomes a launch-time choice or an omitted control — never a fake-live toggle*. "Impossible" requires this **actual live attempt** — re-reading `set_thinking()`'s no-op body is NOT evidence of impossibility.

---

## 7. Isolation rules (parallel-safe — CRITICAL: reproduce these in the file header/comments)

Sibling agents may be running their own live bridge sessions at the same time. Violating any of these can kill their work.

- **ONE new file only** — `tests/test_thinking_toggle_live.py`. Do not touch any other test file.
- **Uniquely-named tmux session** — prefix with the slug: `think-<uuid8>`. Never a fixed/shared name.
- **NEVER call `tmux kill-server`** (directly or via any helper) in teardown — it kills *every* agent's sessions.
- **Run ONLY your own new test** in isolation — not the whole live tier.
- **Do NOT edit shared files** — `tests/conftest.py`, `pyproject.toml`, `tests/README.md`. If you think you need a new fixture, marker, or a pythonpath tidy, **STOP and report it to the human** instead of editing a shared file.
- **The non-obvious trap:** the finisher leans on conftest's session-scoped **`bridge` fixture**, whose **setup AND teardown both call `_kill_all_tmux()` (= `tmux kill-server`)**. That's fine for a human running one file alone, but it **would kill sibling agents' live sessions** and breaks parallel-safety. So do **NOT** depend on that fixture for a destructive lifecycle. Instead **instantiate your OWN `TmuxBridge()`** inside your test module (for WSL `mkdir`/`cat`/`rm` via `_run`, and for `create`/`keys`/`send`/`read_log`/`wait_idle`/driving), and in teardown remove **ONLY** your own uniquely-named session via `bridge.close(name)` and your own throwaway dir via `bridge._run(f"rm -rf {diag}")`. Never a broad kill.
- If you believe you truly need the shared fixture or a new shared fixture/marker, **STOP and report to the human** — do not add it yourself.

---

## 8. Definition of done

- Run your **single** new test through the repo venv and paste the **actual** pytest result line — no paraphrase (the terminal `= N passed =` / `= N xfailed =` line, and/or `tests/log/results_latest.txt`):

  ```powershell
  .\.venv\Scripts\python.exe -m pytest tests\test_thinking_toggle_live.py -m integration
  # or:  tests\run.ps1 tests\test_thinking_toggle_live.py -m integration
  ```

  (Create the venv first if missing: `python -m venv .venv; .\.venv\Scripts\python -m pip install -r requirements.txt`.)
- Whichever exit you land on (WORKS or honest-omit), the pasted result line must reflect the **real** run — a passing durable test, or an explicit xfail/skip that carries the finding.
- Nothing here renders a UI, so the CLAUDE.md "Verifying UI changes" browser pass does not apply. (If for any reason you touch something that renders, follow that rule.)
- **DEVLOG the change** before you finish — append a new dated entry at the bottom of `DEVLOG.md` (what the spike found, WORKS vs omit, files added), per the CLAUDE.md DEVLOG rule.

---

## 9. Guardrails (from CLAUDE.md — reproduce, do not skip)

- **Never create a git branch.** Work on `main`. Do not run `git checkout -b` / `switch -c` / `branch <name>` / `worktree add` — these are gated and will prompt; if one prompts, **stop**. Committing to `main` is fine (but the orchestrator handles git here — do not commit unless told).
- **Bridge sessions stay TAB-LESS.** Create with `show=False`; **never** pass `show=True` and **never** call `show()`. An auto-popped Windows Terminal tab steals the user's focus mid-task.
- **Scratch artifacts go to `.scratch/`** — never the repo root or other project folders. Per-run DEBUG detail goes to `tests/log/` (gitignored) via `logging.getLogger(__name__)`.
- **pytest is the standard** — no ad-hoc scripts. Tag this live test `@pytest.mark.integration` + `@pytest.mark.slow` (module-level `pytestmark`).
