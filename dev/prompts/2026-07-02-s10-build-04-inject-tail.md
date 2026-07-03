# Build prompt — Inject "open tail" spike (earlier-than-hook-boundary delivery)

## 1. Header

- **Test working name:** `inject_tail` — the mid-run Inject "open tail" spike.
- **§10 item:** `#04 — True mid-run Inject — open tail only — ◐ partially proven`
- **Goal (one line):** Probe ONLY the open tail — is there ANY delivery point on a live Claude Code TUI that gets a message to a *running* agent EARLIER than its next hook boundary (`PostToolUse` / `Stop`), without corrupting the in-flight turn? Do **not** retest hook-boundary Inject — that is already unit-proven and ships.

This is a **low-priority tail spike** (Optional band). Keep it lightweight. It has **two honest exits**: a durable live test if an earlier safe point genuinely exists, or a written-up "no earlier safe point exists" finding that proposes moving the item to Decided omissions. Fabricating an immediate-inject success is not an acceptable outcome.

---

## 2. Read first (open these before writing a line)

- **The §10 item itself** — `docs/ARCHITECTURE.md`, section §10, **item 4 "True mid-run Inject"** (currently around line 1089; search for `4. True mid-run Inject`). Read all four bullets (Desired / Blocker / Research-POC-must-establish / Fallback) for the exact wording. Also read §7.3 (the Inject disposition + hook channel) and §7.4 (the hook channel) that it points to — search `Inject — routed via the **hook channel**` (~line 459).
- **The research** — `dev/notes/research/claude-code-mode-control-research.md`:
  - **Question 1, ranked approach #4** (~line 45) — the PreToolUse/PermissionRequest hook that "re-runs on every matching tool call": hooks are a *tool-boundary / turn-end* surface, not an arbitrary mid-turn one.
  - **Question 3 → input-injection notes** (~lines 57, 107–108, and gotcha at line 57) — `tmux send-keys` literal text lands **inside the composer textarea**; **idle-gating is mandatory** because keys sent mid-prompt land in whatever textarea the agent/user is composing in. This is the whole risk the spike must respect.
- **THE pattern to copy** — `tests/test_bridge_finisher_live.py`. Copy its shape exactly (see §4). Note the module-level `pytestmark`, the `_Driven` helper wrapping a `BridgeDriver`, the `asyncio.run(flow())` bodies, and how it reads state back via `bridge.read()` / `bridge._run()` / `bridge.read_log()`.
- **The modules this test touches** (read the real code, do not guess signatures):
  - `sidecar/hookbus.py` — `enqueue_inject`, `pending`, `drain`, `post_tool_use_output`, `stop_output`. This is the **hook-boundary** channel that already works; the spike is about whether anything beats it, so you need to understand exactly what boundary it fires at.
  - `sidecar/drivers/bridge.py` — `_build_hook_settings` (~line 452): the per-agent `PostToolUse` + `Stop` HTTP hooks that ARE the current delivery boundaries. Confirm there is no earlier hook event wired.
  - `sidecar/main.py` — `POST /sessions/{id}/send` with `disposition == "inject"` (~line 941): it calls `hookbus.enqueue_inject(...)` and returns `{"status": "injected"}` — i.e. today Inject **only** rides the durable inbox drained at hook boundaries.
  - `bridge/bridge.py` (`class TmuxBridge`) — `create`, `send(name, text, press_enter=True)`, `keys(name, *key_names)`, `read(name, lines)`, `read_log(name, last_n, types)`, `status(name)`, `scrollback`, `wait_idle`, `close(name)`, `_run(bash_cmd)`.

---

## 3. Mechanism / hypothesis

**Known lever (confirm against the research + code):** the shipping model delivers an Inject via the **hook channel** — `hookbus.enqueue_inject` queues it, and the per-agent `PostToolUse` hook (or the `Stop` backstop at turn end) drains it as `additionalContext` at the **next tool boundary**. That path is unit-proven (`test_hookbus_unit`, `test_sidecar_unit`) and is **out of scope** — do not retest it.

The **only** other programmatic control surface on an interactive TUI is **keystrokes into the pane** (research Q1 approach #8 confirms there is no signal/env/IPC control channel; the only "API" is the ruled-out Agent SDK). So the open question reduces to one concrete experiment: **if you `send-keys` text into a pane whose agent is actively generating (mid-turn, before any tool boundary), does that text reach the agent earlier than the next hook boundary — or does it merely sit in the composer textarea and get submitted as the *next* prompt once the turn ends (which is just Next/Queue), or worse, corrupt the in-flight turn?**

**Expected result (hypothesis):** per research Q3's input-injection notes and the mandatory-idle-gating gotcha (line 57), `send-keys` lands in the **composer textarea**, which the TUI does not consume until the current turn finishes. So typeahead is expected to behave as **Next** (submitted after the turn), not as immediate mid-turn delivery — and pressing Enter mid-generation risks corrupting the turn. If that holds, there is **no earlier safe point** and the honest exit is the omission write-up. The spike exists to *actually try it live* rather than assert it from the code.

---

## 4. Build this

Create **one** new file: `tests/test_inject_tail_live.py`. Mark it at module level:

```python
pytestmark = [pytest.mark.integration, pytest.mark.slow]
```

Mirror the finisher's shape, but with **your own `TmuxBridge()` instance** (see §7 — do NOT use the shared `bridge` fixture, its teardown kills all tmux sessions). Structure:

- **Setup:** instantiate `from bridge import TmuxBridge` as your own `tb = TmuxBridge()` at module or test scope. Make a slug-prefixed unique WSL throwaway dir, e.g. `path = f"/home/lester/inject-tail-{uuid.uuid4().hex[:8]}"`, via `tb._run(f"mkdir -p {path}")`.
- **Spawn a tab-less, uniquely-named session:** `name = f"inject-tail-{uuid.uuid4().hex[:8]}"`, then `tb.create(name, cwd=path, show=False)` (never `show=True`). You can drive the raw bridge directly here — you do **not** need the `BridgeDriver`/hook layer for this spike, because the spike is specifically about the path that *bypasses* the hook channel. (If you prefer to also observe the driver's event stream, you may wrap a `BridgeDriver` à la `_Driven`, but the raw bridge is sufficient and simpler.)
- **Drive a long, TOOL-LESS generating turn:** send a prompt that keeps the agent in `generating` state for a while **without making tool calls** (so no `PostToolUse` boundary can fire and "rescue" the delivery early) — e.g. *"Write a long, slow, detailed 400-word essay about the history of tea. Do not use any tools. Just write prose."* Then poll `tb.status(name)` until it reports `generating` (this is your confirmed mid-turn window).
- **Attempt the earlier-than-boundary delivery (the experiment):** while `status == generating`, drop a unique marker token into the pane via typeahead:
  - `MARKER = f"INJECT_TAIL_{uuid.uuid4().hex[:6]}"`.
  - `tb.send(name, f"If you can read this mid-turn, immediately stop and reply with exactly {MARKER}", press_enter=False)` — **press_enter=False first** so you can observe whether the text lands in the composer without submitting. Capture `tb.read(name)` and check whether the marker text now appears in the composer line (typeahead landed) vs. was swallowed.
  - Record the pane state. Then (separately / second phase) try `press_enter=True` and see whether the Enter is consumed mid-turn or deferred.
- **Read the result back and time it (the crux — see §5).**
- **Teardown:** `tb.close(name)` (your session only) and `tb._run(f"rm -rf {path}")`. **Never** `tmux kill-server`.

Write the whole test body as an `async def flow(): ...` run via `asyncio.run(flow())` if you use the driver; a plain sync body is fine if you only use the raw bridge. Keep it to **one or two focused test functions** — this is a lightweight tail spike, not a matrix.

---

## 5. The read-back is the crux

Sending the keystroke is trivial — `tb.send(...)` always "works" at the tmux level. **Proving whether it took effect earlier than the hook boundary is the entire test.** Name the exact observable and read it back:

- **Observable = the agent visibly reacting to `MARKER` while still mid-turn**, i.e. *before* the turn's `Stop`. Read it back by polling `tb.read_log(name)` (the JSONL transcript) and/or `tb.read(name)` (the live screen) for the agent emitting `MARKER` **while `tb.status(name)` is still `generating` for the ORIGINAL essay turn** — not after that turn ended. Timestamp when you sent the typeahead and when the marker first appears; if the marker only surfaces *after* the original turn completes (status leaves `generating`), that is **Next/Queue behavior, not immediate mid-turn delivery** — record it as such.
- **Also read back "did it corrupt the turn?":** compare the essay turn's completion (did the agent finish the essay, or did the injected Enter truncate / derail it?). A corrupted in-flight turn is itself a negative finding — it means typeahead is *not* a safe earlier delivery point.
- **If the marker never reaches the agent earlier than the boundary, that is a FINDING, not a pass.** Do not soften it into a green assertion. The valid assertions are either: (a) marker observed mid-turn without corruption → an earlier safe point exists (surprising — keep the test), or (b) marker deferred to next turn and/or corrupted the turn → no earlier safe point (expected — write it up per §6).

---

## 6. Two honest exits (spike-or-omit)

- **WORKS** (an earlier safe delivery point genuinely exists — marker reaches the agent mid-turn, before the boundary, without corrupting the essay turn): keep `tests/test_inject_tail_live.py` as a durable live test that asserts the earlier-delivery observable, and add a short note (in the test docstring and DEVLOG) of exactly what the earlier safe point is (typeahead-consumed-mid-turn, or whatever you found) so §10 item 4 can be upgraded and §7.3 corrected.
- **GENUINELY IMPOSSIBLE AFTER A REAL LIVE ATTEMPT** (the expected outcome — you actually spawned a session, drove a generating turn, sent typeahead, and read back that it either deferred to the next turn or corrupted the turn): do **NOT** fabricate a green. Write up the findings — what you sent, what the pane/transcript showed, and the timing — and **propose in your report** that §10 item 4's open tail move to **Decided omissions** with the Fallback as the final model (hook-boundary delivery + transparent Next/Queue degrade). "Impossible" requires this **actual live attempt**, never just re-reading `main.py` and concluding the inject disposition no-ops to the inbox. If the environment blocks a real attempt (WSL/tmux unavailable), report that as a blocker — not as a finding.

Either exit is a legitimate deliverable. The one unacceptable outcome is asserting immediate mid-turn Inject succeeds when it did not.

---

## 7. Isolation rules (parallel-safe — CRITICAL; reproduce these in the file's docstring)

Other agents may be running their own live bridge sessions at the same time. Obey all of these:

- **ONE new file only** — `tests/test_inject_tail_live.py`. Do not touch any other test file.
- **Name every tmux session uniquely** — prefix with the test slug (`inject-tail-<uuid>`). Same for the throwaway WSL dir.
- **NEVER call `tmux kill-server`** (directly or via any helper) in teardown — it kills sibling agents' live sessions. Remove **only your own** session via `tb.close(name)` and your own dir via `tb._run("rm -rf ...")`.
- **Run only your own new test in isolation** — never run the whole live tier.
- **Do NOT edit `tests/conftest.py`, `pyproject.toml`, or `tests/README.md`.** If you think you need a shared change (a new fixture, marker, or a pythonpath tidy), **STOP and report it to the human** instead of editing a shared file.
- **Non-obvious trap — do NOT depend on conftest's session-scoped `bridge` fixture.** The finisher uses it, but that fixture's setup **and** teardown both call `_kill_all_tmux()` (= `tmux kill-server`). That is fine for a human running one file alone, but under parallel agents it would kill sibling sessions and breaks the parallel-safe rule. So **instantiate your OWN `TmuxBridge()`** inside your test module — for the WSL shell helpers (`_run` mkdir/cat/rm) and for driving — and tear down only your uniquely-named session. Copy the finisher's *test shape*, not its `bridge` fixture dependency. If you believe you truly need the shared fixture or a new shared fixture/marker, STOP and report to the human.

---

## 8. Definition of done

- Run your **single** new test through the repo venv and paste the **actual** pytest result line (no paraphrase):
  ```powershell
  .\.venv\Scripts\python.exe -m pytest tests\test_inject_tail_live.py -m integration
  ```
  (or `tests\run.ps1 tests\test_inject_tail_live.py -m integration`). Paste the terminal `= N passed =` / `= N failed =` line and/or the relevant lines from `tests\log\results_latest.txt`. If the venv is missing, create it: `python -m venv .venv; .\.venv\Scripts\python -m pip install -r requirements.txt`.
- For the WORKS exit, the pasted line must be a real pass of an assertion on the earlier-delivery observable. For the omission exit, the deliverable is the written findings + the pasted evidence of your live attempt (screen/transcript reads and timing) — plus the proposal to move the item to Decided omissions. Do not leave a fake-green test behind.
- Nothing here renders a UI, so the CLAUDE.md "Verifying UI changes" browser loop does not apply. If you happened to touch anything that renders, follow it.
- **DEVLOG the change before finishing** — append a new entry at the bottom of `DEVLOG.md` (heading `### YYYY-MM-DD HH:MM:SS — short title`, 1–4 lines, then a `Files:` line) recording the new test file and the spike outcome.

---

## 9. Guardrails (from CLAUDE.md)

- **Never create a git branch.** Work on `main`. Do not run `git checkout -b` / `switch -c` / `branch <name>` / `worktree add` — they are gated and will prompt; if one prompts, stop. Committing to `main` is fine (only if asked); the orchestrator handles git for this task otherwise.
- **Bridge sessions stay TAB-LESS.** Create with `show=False` (the default) — **never** pass `show=True`, and **never** call `show()`. An auto-popped Windows Terminal tab steals the user's desktop focus. Detached sessions run and are read fine via `capture-pane` + JSONL.
- **Scratch artifacts go to `.scratch/`** — any screenshot, dump, or throwaway file goes under the repo's `.scratch/` (gitignored), never the repo root. (Your WSL throwaway dir lives under `/home/lester/inject-tail-*` and is `rm -rf`'d in teardown.)
- **pytest is the standard** — no ad-hoc scripts; the deliverable is a pytest file.
