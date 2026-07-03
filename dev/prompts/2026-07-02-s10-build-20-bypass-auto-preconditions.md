# Build prompt — Bypass & Auto permission-mode launch-precondition spike

## 1. Header

- **Test working name:** `bypass_auto_preconditions_live`
- **§10 item:** **#20 — Bypass & Auto permission-mode launch preconditions — 🧪 needs-spike** (docs/ARCHITECTURE.md §10, item **#20**, `→ §6.2, §7.11`; relates to §10 #1)
- **Goal:** Establish, live, the **launch-time preconditions** for the **Bypass** and **Auto (accept-edits)** permission-mode segments — i.e. which segments are actually reachable given how an agent was launched, and **how an *unreachable* segment presents** (does selecting Bypass on a normally-launched agent silently no-op?). This is about **launch preconditions**, distinct from §10 #1 (mid-run *cycling*).

This is a **spike-or-report** task. "Bypass requires `--allow-dangerously-skip-permissions` at launch and silently no-ops without it" and "Auto is reachable from any launch" are both honest findings. Do **not** claim a segment "works" without confirming its precondition and its failure mode.

---

## 2. Read first (open these before writing a line)

1. **Your §10 item — exact wording.** `docs/ARCHITECTURE.md` §10, item **#20** (in "Priority — coverage-audit additions"). Read all bullets. Note the explicit distinction from #1: this is *launch-time preconditions*, not mid-run cycling.
2. **The sibling item + its spike (build on it, don't duplicate).** `docs/ARCHITECTURE.md` §10 **#1** (mid-run permission-mode change via Shift+Tab/`BTab`) and its prompt `dev/prompts/2026-07-02-s10-build-01-permission-mode.md`. #1 spikes the *cycle*; **you spike whether the endpoints of that cycle (Bypass, Auto) are even reachable depending on launch flags.** Read #1's prompt so your test complements it (same bridge `keys()`/status read-back techniques) rather than overlapping.
3. **How launch config is applied (the crux anchor).** `sidecar/drivers/bridge.py` ~lines 570–597: per-agent **permission mode + tool gates + launch flags** are applied **"the only point a TUI reads them"** — i.e. **at launch**; the "startup-gate clearer handles the `bypassPermissions` warning gate; an unknown mode…" comment tells you Bypass has a **launch-time warning gate**. This is the mechanism your spike probes: what must be present at launch for each segment.
4. **The research.** `dev/notes/research/claude-code-mode-control-research.md` — **Question 1** (permission-mode approaches): the mode cycle, the `--allow-dangerously-skip-permissions` (a.k.a. "dangerously skip permissions") launch flag that pre-arms Bypass, and the accept-edits ("Auto") mode. `dev/notes/research/research-cli-stream-and-permissions-api.md` — the permission surface / mode names. Pull the exact launch flag + the mode names (`default` / `plan` / `acceptEdits` / `bypassPermissions`) from here.
5. **THE pattern to copy.** `tests/test_bridge_finisher_live.py` — mirror its shape (module-level `pytestmark`, sidecar-on-`sys.path` shim, throwaway WSL diag dir, `asyncio.run(flow())`, read-state-back-and-assert). Bridge/driver API: `create` (and how it passes launch/permission config), `keys`, `read` (status-line text), `status`, `wait_idle`, `close`.

---

## 3. Mechanism / hypothesis

**Known lever:** per-agent permission mode + launch flags are set **at launch only**. Hypothesis by segment:

- **Bypass** — likely requires launching with `--allow-dangerously-skip-permissions` (and clearing the bypass **warning gate** the startup-gate clearer handles). Without that flag, selecting/cycling to Bypass on a normally-launched agent probably **cannot reach `bypassPermissions`** — it may silently no-op or refuse.
- **Auto (acceptEdits)** — may be reachable from a normal launch (it's a less-privileged mode) or may need an opt-in. Determine which.

**Confirm, do not assume:** the exact flag name on this build, whether Bypass is truly launch-gated, and — critically — **what an unreachable segment looks like from outside** (status line unchanged? an on-screen refusal? a silent no-op?), because the UI must not present a control that silently does nothing.

---

## 4. Build this

Create **one** new file: **`tests/test_bypass_auto_preconditions_live.py`**. Slug: **`bypassauto`**. Module-level `pytestmark = [pytest.mark.integration, pytest.mark.slow]`. Mirror the finisher's imports/shim. Use your **own** `TmuxBridge()` (see §7 — do NOT use the shared `bridge` fixture). Structure as a small matrix of launch conditions × target segment:

1. **Setup** — throwaway WSL diag dir. A helper to spawn a tab-less, uniquely-named session (`bypassauto-<uuid8>`, `show=False`) **with a given launch configuration** (with vs. without the bypass flag; with a given initial permission mode). Use the driver's real launch path so you're testing production launch config, not a hand-rolled one.
2. **Case A — Bypass WITHOUT the flag:** launch a normal agent, then attempt to reach `bypassPermissions` (cycle via `keys()` `BTab` per #1's technique, or set the mode). Read back the status-line mode text (`read()`); assert whether Bypass was reached or the attempt **no-ops** — and capture *how* it fails (unchanged status line? a refusal line?).
3. **Case B — Bypass WITH the flag:** launch with `--allow-dangerously-skip-permissions` (and let the startup-gate clearer handle the warning gate), then confirm Bypass **is** reachable (status line shows the bypass mode). This confirms the precondition.
4. **Case C — Auto (acceptEdits):** launch normally, attempt to reach Auto, read back whether it's reachable and how. Determine Auto's precondition (none / opt-in).
5. **Read back the mode from the status line** in every case (the crux — §5). **Teardown:** `close()` your session(s), `rm -rf` your dir. Never `kill-server`.

Log at DEBUG (`logging.getLogger(__name__)`) a matrix: `launch_config × target_segment → reached? → how_it_presented(status text)` — full detail to `tests/log/`.

**Safety:** Bypass mode disables permission prompts — keep every agent confined to the throwaway diag dir and drive **no** destructive commands. The spike only needs to read the *mode indicator*, not exercise dangerous actions.

---

## 5. The read-back is the crux

Selecting a mode is trivial — **proving whether the segment was actually reached (and how an unreachable one presents) is the whole test.** Read the mode back from the live status line, never assert the value you sent:

- **Observable = the permission-mode text in the status line** (e.g. `⏵⏵ accept edits on`, a bypass indicator, or the default) read via `bridge.read()` after the attempt. Reached = the status line shows the target mode; not-reached = it doesn't.
- **Capture the *failure mode* of an unreachable segment** — this is the point of the item. Is it a silent no-op (status unchanged, no feedback) or a visible refusal? A **silent** no-op is the dangerous case (the UI would show a dead control); record exactly which it is.
- **The precondition is the deliverable:** for Bypass and Auto, state precisely what launch config makes each reachable, confirmed by the with/without cases. If a segment can't be reached under any launch you tried, that's a finding.
- **Do not assert "Bypass works" from the flagged case alone** — the value is the *contrast* (with-flag reachable vs without-flag no-op) and the failure-mode characterization.

---

## 6. Two honest exits (spike-or-report)

- **PRECONDITIONS ESTABLISHED** — you confirmed, per segment, the launch precondition and the unreachable-segment failure mode. Keep `tests/test_bypass_auto_preconditions_live.py` as a durable test. Note the exact rule a build/UI needs: e.g. *"gate the Bypass segment behind a launch-time `--allow-dangerously-skip-permissions` choice; disable it (don't silently no-op) when absent"* — the §20 fallback/Desired behavior.
- **INCONCLUSIVE AFTER A REAL ATTEMPT** — if a segment's behavior can't be pinned down live (e.g. the warning gate blocks automation), report that as a blocker with what you observed — not a fabricated precondition. "Established" or "inconclusive" both rest on the **actual live launches**, never a code re-read.

---

## 7. Isolation rules (parallel-safe — CRITICAL: reproduce these in the file header/comments)

Sibling agents may be running their own live bridge sessions at the same time. Violating any of these can kill their work.

- **ONE new file only** — `tests/test_bypass_auto_preconditions_live.py`. Do not touch any other test file.
- **Uniquely-named tmux sessions** — prefix with the slug: `bypassauto-<uuid8>`. Never a fixed/shared name. You launch several (with/without flag) — track and close every one.
- **Bypass agents stay confined** — spawn in your own throwaway diag dir, run no destructive commands; you only read the mode indicator.
- **NEVER call `tmux kill-server`** (directly or via any helper) in teardown — it kills *every* agent's sessions.
- **Run ONLY your own new test** in isolation — not the whole live tier.
- **Do NOT edit shared files** — `tests/conftest.py`, `pyproject.toml`, `tests/README.md`. If you think you need a new fixture, marker, or a pythonpath tidy, **STOP and report it to the human**.
- **The non-obvious trap:** the finisher leans on conftest's session-scoped **`bridge` fixture**, whose **setup AND teardown both call `_kill_all_tmux()` (= `tmux kill-server`)** — which would kill sibling agents' sessions. **Instantiate your OWN `TmuxBridge()`** and tear down only your uniquely-named sessions via `bridge.close(name)` + your own dir. Never a broad kill.

---

## 8. Definition of done

- Run your **single** new test through the repo venv and paste the **actual** pytest result line — no paraphrase (the terminal `= N passed =` / `= N xfailed =` line, and/or `tests/log/results_latest.txt`):

  ```powershell
  .\.venv\Scripts\python.exe -m pytest tests\test_bypass_auto_preconditions_live.py -m integration
  # or:  tests\run.ps1 tests\test_bypass_auto_preconditions_live.py -m integration
  ```
  (Create the venv first if missing: `python -m venv .venv; .\.venv\Scripts\python -m pip install -r requirements.txt`.)
- Your report must state, for **Bypass** and **Auto** separately: the launch precondition and how an unreachable segment presents (silent no-op vs visible refusal) — the rule the UI must implement.
- Nothing here renders a UI, so the CLAUDE.md "Verifying UI changes" browser pass does not apply.
- **DEVLOG the change** before you finish — append a new dated entry at the bottom of `DEVLOG.md` (per-segment preconditions + files added), per the CLAUDE.md DEVLOG rule.

---

## 9. Guardrails (from CLAUDE.md — reproduce, do not skip)

- **Never create a git branch.** Work on `main`. Do not run `git checkout -b` / `switch -c` / `branch <name>` / `worktree add` — these are gated and will prompt; if one prompts, **stop**. Committing to `main` is fine (but the orchestrator handles git here — do not commit unless told).
- **Bridge sessions stay TAB-LESS.** Create with `show=False`; **never** pass `show=True` and **never** call `show()`. An auto-popped Windows Terminal tab steals the user's focus mid-task.
- **Scratch artifacts go to `.scratch/`** — never the repo root or other project folders. Per-run DEBUG detail goes to `tests/log/` (gitignored) via `logging.getLogger(__name__)`.
- **pytest is the standard** — no ad-hoc scripts. Tag this live test `@pytest.mark.integration` + `@pytest.mark.slow` (module-level `pytestmark`).
