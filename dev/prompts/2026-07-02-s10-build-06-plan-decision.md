# Build prompt — Plan/Decision hook interception (live spike)

## 1. Header

- **Working name:** `plan_decision_hooks_live` — a live spike test proving the PreToolUse hook interception for `ExitPlanMode` / `AskUserQuestion`.
- **§10 item:** **#06 — Plan/Decision hook interception (spike-gated) — 🧪 needs-spike** (High priority band).
- **Goal:** Prove **DETECTION first** — that a live bridge agent calling `ExitPlanMode` / `AskUserQuestion` fires the wired `PreToolUse` HTTP hooks and raises a typed Plan/Decision inbox card — then **probe the ANSWER/RESUME loop** (the genuinely unproven part) and write up honestly whether an approval path resumes the agent out of plan mode.

---

## 2. Read first (open these before writing a line)

- **Your §10 item:** `docs/ARCHITECTURE.md` **§10, item 6** ("Plan/Decision hook interception (spike-gated)", ~line 1113). Read all five bullets — Evidence, Desired final behavior, Current blocker, Research/POC must establish, Fallback — for the exact wording. Also skim §7.4 and §7.16 (referenced from the item) and §5's inbox/hook endpoint map (~lines 471–561).
- **The research:** `dev/notes/research/claude-code-mode-control-research.md` —
  - **Permission-prompt handling, item 2** (~line 114): *"PreToolUse/PermissionRequest deny hook … Exit 2 or `permissionDecision: "deny"` blocks a tool in any mode … Do not rely on the allow path to silence prompts in interactive mode."* This is the "Question 1 ranked approach #4" the item cites — deny path solid, allow path buggy in interactive mode.
  - **Prior art item 1, bjornjee/agent-dashboard** (~line 68–70): the confirmed-working analog whose hook architecture we adopted — tool-specific hook signals, `PreToolUse`/`PostToolUse`/`PermissionRequest` matchers, "plan mode is signaled, not gated." This is the "Question 2" pointer.
  - **Idle-gating note** (~line 57): never dispatch keys into a stop-state textarea (plan-review box, AskUserQuestion answer box). Relevant if you probe resume via `keys()`.
- **THE pattern to copy:** `tests/test_bridge_finisher_live.py` — copy its shape exactly (see §4). Note `_Driven`, `diag_dir`, module-level `pytestmark`, `asyncio.run(flow())`.
- **The modules this test touches:**
  - `sidecar/drivers/bridge.py` → `BridgeDriver._build_hook_settings()` (~line 452) — the per-agent `PreToolUse` HTTP hooks for `ExitPlanMode` → `/internal/hooks/plan/{agent}` and `AskUserQuestion` → `/internal/hooks/decision/{agent}`. Note: hooks are wired **only if** `self._session_id` is bound **and** `sidecar_hook_base_url()` resolves the WSL→host gateway.
  - `sidecar/main.py` → `_raise_plandecision()` (~line 1144), `hook_plan` / `hook_decision` endpoints (~line 1160), `GET /inbox` (~line 1178). The hook raises a card via `inbox.raise_item(agent, itype, data, dedup_key=...)` then returns `{}` (allow). `/inbox` groups open items by agent + reports `fleet_badge`.
  - `sidecar/inbox.py` → the store: `raise_item`, `items_for`, `all_open`, `reset`; `TYPES = ("permission","error","warning","plan","decision")`.
  - `bridge/bridge.py` → `sidecar_hook_base_url()` (~line 1019) + `wsl_host_ip()` (~line 1001) — confirms the gateway URL the agent's hooks POST to.

---

## 3. Mechanism / hypothesis

**The known lever (confirmed against the code + research).** Every bridge agent is launched with a `--settings` payload that includes a `PreToolUse` hook block (`_build_hook_settings`, `sidecar/drivers/bridge.py:452`):

```
PreToolUse:
  - matcher "ExitPlanMode"    -> POST {base}/internal/hooks/plan/{agent}
  - matcher "AskUserQuestion" -> POST {base}/internal/hooks/decision/{agent}
```

`{base}` is `bridge.sidecar_hook_base_url()` = `http://<wsl-host-gateway>:7690`, and `{agent}` is the driver's bound `session_id`. When the agent calls one of those tools, Claude Code's HTTP-hook client POSTs the tool payload; the sidecar's `hook_plan` / `hook_decision` handler calls `_raise_plandecision(agent, body, "plan"|"decision")`, which does `inbox.raise_item(...)` with `data = {"tool": tool_name, "tool_input": {...}}` and **returns `{}` (allow, detect-and-surface)**.

**Two split questions (mirror the item):**

- **(Detection)** *Expected:* a live agent driven to call `ExitPlanMode` (or `AskUserQuestion`) fires the hook; the sidecar receives a POST carrying a usable `tool_input`; a `plan` (or `decision`) card appears at `GET /inbox` keyed by the agent. This is the closest-analog architecture (research prior-art #1: "tool-specific hook signals, plan mode is signaled, not gated") and is expected to WORK.
- **(Answer/resume)** *Unproven:* the hook returns `{}` = allow, so it does **not** hold-for-answer. The research is explicit that the **allow path is buggy/interactive** (Permission-handling item 2). So the open question is: after detection, does the agent proceed on its own, or does it **park at an interactive plan-review box on screen** that needs a `keys()` approval (Enter) to resume out of plan mode? No verified resume-out-of-plan-mode path exists. This half is a **probe + write-up**, not a guaranteed green.

---

## 4. Build this

Create **one** new file: `tests/test_plan_decision_hooks_live.py`.

- Module-level `pytestmark = [pytest.mark.integration, pytest.mark.slow]`.
- Copy the finisher's `sys.path` shim (put `sidecar/` on `sys.path` so `from drivers.bridge import BridgeDriver` / `from drivers.base import DriverConfig` work), the `_runtime_to_tmp` autouse fixture, and the `asyncio.run(flow())` body style.
- **Do NOT reuse the finisher's `diag_dir` fixture as-is if it depends on the shared `bridge` fixture** — see §7. Make your own throwaway dir + your own `TmuxBridge()`.

**The end-to-end detection dependency (call this out and pick the honest approach).** The agent's hooks POST to the **sidecar's HTTP endpoints** over the WSL→Windows host gateway. Detection is only observable end-to-end if something is listening at `sidecar_hook_base_url()` (default `:7690`). A `BridgeDriver` created standalone only wires the hooks when a `session_id` is bound **and** the gateway resolves. Pick ONE:

- **Approach A (preferred — real sidecar):** Start the real sidecar (`uvicorn sidecar.main:app --host 0.0.0.0 --port 7690`) as a subprocess for the test (bound to `0.0.0.0` so WSL can reach it; confirm Windows firewall allows the inbound — the research already live-verified this gateway path for the PostToolUse inject channel). Create a standalone `BridgeDriver(DriverConfig(cwd=<dir>, permission_mode="plan"), <sink>, session_id="plandec-<uuid8>")`. Drive it. Then `GET http://127.0.0.1:7690/inbox` and assert a `plan` card exists under your agent id. (The inbox store is process-local to that sidecar, so the same process that received the hook POST serves `/inbox`.)
- **Approach B (minimal stand-in receiver):** Stand up a tiny HTTP server on the host gateway IP:port that `sidecar_hook_base_url()` resolves to, capturing `POST /internal/hooks/plan/{agent}` (and `/decision/{agent}`) bodies, returning `{}`. Assert the POST arrived with a usable `tool_input`. Lighter, but proves only "hook fired with payload," not the full card path — acceptable per the item ("if testing the hook alone, the stand-in receiver logged the POST").

Prefer **Approach A** — it proves the whole detect→card chain the dashboard actually uses.

**The flow (async `flow()` run via `asyncio.run`):**

1. **Spawn** a tab-less, uniquely-named session: `BridgeDriver(..., session_id="plandec-<uuid8>")`, `permission_mode="plan"`, in your throwaway WSL dir. `await driver.start()`. **Never `show=True`.** Confirm `driver.tmux_name` is your slug-prefixed unique name.
2. **Drive DETECTION — Plan:** with the session in plan mode, `await driver.send("Make a short plan to create a file called hello.txt containing the word world, then use the ExitPlanMode tool to present your plan. Do not write anything yet.")`. In plan mode the agent presents its plan via `ExitPlanMode`, firing the `PreToolUse(ExitPlanMode)` hook.
3. **Read back DETECTION (crux):** poll `GET /inbox` (Approach A) — for up to ~90s — until `inbox[agent]` contains an item with `type == "plan"`. Assert the card's `data.tool_input` is non-empty/usable (an `ExitPlanMode` payload carries the plan text). Under Approach B, assert your receiver logged the POST body with `tool_name`/`tool_input`.
4. **(Optional second detection — Decision):** a fresh uniquely-named session (or the same, next turn), prompt: `"Before doing anything, use the AskUserQuestion tool to ask me whether I prefer option A or option B."` Poll `/inbox` for a `type == "decision"` card. Keep this as a second assertion or a separate test function in the SAME file — do not add a second file.
5. **Probe ANSWER/RESUME (write-up, not a hard green):** after the plan card is raised (hook returned `{}` = allow), read the live screen/transcript back — `bridge.read(driver.tmux_name, lines=40)["content"]` and `driver.get_context_usage()` / `bridge.read_log(...)`. Determine: did the agent **proceed on its own**, or is it **parked at an interactive plan-review box** (screen shows the plan-approval prompt)? If parked, try a single guarded `driver` action / `keys()` (e.g. Enter to accept) — gated on a verified idle/prompt state, per the research idle-gating note — and re-read to see if it resumes out of plan mode. Record the observed behavior in the test docstring and the DEVLOG regardless of outcome.
6. **Teardown:** `await driver.close()` for each driver, remove your throwaway dir via your own `TmuxBridge()._run("rm -rf <dir>")`, and (Approach A) terminate the sidecar subprocess. **Never `tmux kill-server`.**

Keep detection assertions strict (they must pass for a green). Keep answer/resume as an observation the test records and does not fail on unless you actually prove a resume path.

---

## 5. The read-back is the crux

Sending the prompt that makes the agent call `ExitPlanMode` is trivial. **Proving the hook fired and produced a usable, card-shaped signal is the whole test.**

- **Detection observable (must assert):** `GET /inbox` shows `inbox["plandec-<uuid8>"]` containing an item with `type == "plan"` and non-empty `data["tool_input"]` (Approach A); OR your stand-in receiver captured `POST /internal/hooks/plan/{agent}` with a body carrying `tool_name == "ExitPlanMode"` and a `tool_input` (Approach B). Same pattern for `decision` / `AskUserQuestion`.
- **Answer/resume observable (probe + record):** the agent's live state after the allow — read via `bridge.read()` (screen, ANSI-stripped) and the JSONL transcript (`bridge.read_log`). "Resumed out of plan mode" means the agent left plan mode and continued (visible in transcript/screen); "still parked" means an interactive plan-review box is on screen.
- **If detection is not observable after a real live attempt, that is a FINDING, not a pass** — do not paper over it. If the hook never fires or the payload is unusable, capture the raw screen + any sidecar log and write it up (§6).

---

## 6. Two honest exits (spike-or-omit)

This is a **split** — detection can pass while answer/resume stays open.

- **DETECTION WORKS →** keep the detection assertions as a durable live test; add a short note (test docstring + DEVLOG) of what was learned: hooks fire under the bridge, payload shape, latency observed.
- **ANSWER/RESUME PROVEN →** add it as a second durable assertion and update the §10 item's "Research/POC must establish" bullet accordingly (note the resume mechanism — hook `updatedInput` vs `keys()` Enter).
- **ANSWER/RESUME GENUINELY IMPOSSIBLE AFTER A REAL LIVE ATTEMPT →** do **NOT** fabricate a green. Leave the detection test green, write up the failed resume attempt (what you drove, what the screen/transcript showed), and propose in your report that the *answer/resume* half stays 🧪/fallback (detect-and-surface: notify-only cards, operator answers via the Console passthrough). "Impossible" requires an actual live attempt, never a re-read of the code no-op.
- **DETECTION GENUINELY IMPOSSIBLE AFTER A REAL LIVE ATTEMPT →** same rule: capture findings, do not fake a pass, and propose moving item #06 toward Decided omissions / the transcript-detection fallback. Only after a real run.

---

## 7. Isolation rules (parallel-safe — CRITICAL; reproduce all of these in the file)

Other agents may be running live bridge sessions at the same time. You must not disturb them.

- **ONE new file only:** `tests/test_plan_decision_hooks_live.py`. Do not touch any other test file.
- **Uniquely name your tmux session** — prefix with the test slug: `plandec-<uuid4-hex[:8]>`. Never a fixed/shared name.
- **NEVER call `tmux kill-server`** (directly or via any helper) in setup or teardown — it kills sibling agents' sessions. Tear down **only your own** session via `close(<your-name>)` and remove **only your own** throwaway dir.
- **Run ONLY your own new test in isolation** — not the whole live tier.
- **Do NOT edit `tests/conftest.py`, `pyproject.toml`, or `tests/README.md`.** If you think you need a shared change (a new fixture, a new marker, or the pythonpath tidy), **STOP and report it to the human** — do not edit a shared file.
- **Non-obvious trap (do not fall into it):** the finisher leans on conftest's session-scoped `bridge` fixture, whose setup **and** teardown both call `_kill_all_tmux()` (= `tmux kill-server`). That is fine for a human running one file alone, but it would kill sibling agents' live sessions and breaks the parallel-safe rule. So **do NOT depend on that shared `bridge` fixture** for anything with a destructive lifecycle. Instead, **instantiate your OWN `TmuxBridge()` inside your test module** (import `from bridge import TmuxBridge`) for the WSL shell helpers (`_run` mkdir/cat/rm) and for reading, and in teardown remove **only** your own uniquely-named session (`close(name)`) and your own throwaway dir. If you genuinely believe you need the shared fixture or a new shared fixture/marker, **STOP and report to the human** rather than editing a shared file.

---

## 8. Definition of done

- Run your **single** new test through the repo venv and paste the **actual** pass/fail line, verbatim (the pytest `= N passed =` terminal line and/or `tests/log/results_latest.txt`) — no paraphrase.

  ```powershell
  .\.venv\Scripts\python.exe -m pytest tests\test_plan_decision_hooks_live.py -m integration
  # or:  tests\run.ps1 tests\test_plan_decision_hooks_live.py -m integration
  ```

  (Create the venv first if missing: `python -m venv .venv; .\.venv\Scripts\python -m pip install -r requirements.txt`.)
- Nothing here renders a UI, so the "Verifying UI changes" browser loop does not apply. If you happened to touch any renderer surface (you should not need to), follow CLAUDE.md "Verifying UI changes."
- **DEVLOG the change before finishing** — append a new dated entry at the bottom of `DEVLOG.md` (what the test proves, the detection result, and the honest answer/resume finding), with a `Files:` line. An unlogged change did not happen.
- Report back: the pass/fail line, the detection outcome, and the answer/resume finding (proven / still-open / fallback proposed).

---

## 9. Guardrails (from CLAUDE.md — reproduce and obey)

- **Never create a git branch.** Work on `main`. Do not run `git checkout -b` / `switch -c` / `branch <name>` / `worktree add`. Committing to `main` and reading git state are fine. (The orchestrator handles git/DEVLOG commits — you write the file and DEVLOG entry; do not branch.)
- **Bridge sessions stay TAB-LESS.** Never pass `show=True` to `create()` and never call `show()`. Sessions run detached; a Windows Terminal tab must never open as a side effect of this test.
- **Scratch artifacts go to `.scratch/`** (screen dumps, ad-hoc sidecar logs) — never the repo root or another project folder.
- **pytest is the standard** — this deliverable is a pytest file; do not write ad-hoc runner scripts.
