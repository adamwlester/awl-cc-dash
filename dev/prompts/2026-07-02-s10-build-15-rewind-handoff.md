# Build prompt — Rewind / Handoff spike (CONDITIONAL SCAFFOLD — finalize from research first)

> ## ⚠️ TO BE FINALIZED — this prompt is a scaffold, not a runnable spec yet
>
> The concrete test steps for this spike **cannot be written until the gating research
> (`dev/prompts/2026-07-02-s10-research-15-rewind-handoff.md` → report at
> `dev/notes/research/s10-research-15-rewind-handoff.md`) identifies whether *any* rewind (truncate-and-resume)
> or fork (branch-from-point) mechanism exists for a Claude Code session.** This scaffold tells the
> implementing agent how to **consume that research report and instantiate the spike from it** — or, if the
> research found no mechanism, how to record the omission instead of building a fake test. **Do not run this as
> if the mechanism were already known.** Whoever picks this up first executes §3 (the precondition gate); the
> path you take (§5A vs §5B) is decided entirely by what the research report says.

## 1. Header

- **Test working name:** `rewind_handoff_live` (conditional — may resolve to a durable test *or* a recorded omission)
- **§10 item:** **#15 — Rewind / Handoff / Timeline — conversation truncate-and-resume / fork-from-point — 🔬 needs-research** (docs/ARCHITECTURE.md §10, item **#15**, `→ §7.5, §9.2, §9.9`)
- **Goal:** *Conditional.* IF the research identifies a feasible mechanism to (A) truncate a conversation at message N and resume, and/or (B) fork a new session carrying the prefix up to N — **prove it end-to-end with a live test.** IF the research found no feasible mechanism — **record the honest omission** (propose moving §10 #15 to Decided omissions) and build **no** test.

This is a **spike-or-omit** task whose *branch* is chosen by the research, not by you. The one unacceptable outcome is a green test that doesn't actually demonstrate rewind/fork on a live session.

---

## 2. Read first (open these before writing a line)

1. **THE RESEARCH REPORT — this is your spec.** `dev/notes/research/s10-research-15-rewind-handoff.md` (produced by handing `dev/prompts/2026-07-02-s10-research-15-rewind-handoff.md` to an offline chat). **If this file does not exist yet, STOP** — the research is the precondition; report back that the spike is blocked on the research and do nothing else. Read the report's **Verdict + recommendation + fallback** section: it gives a YES / PARTIAL / NO for rewind and for fork, and — if YES/PARTIAL — "the exact steps a spike would run: what files to edit/copy, what command to run, what to observe." **Those steps ARE this test.** You are instantiating them, not inventing them.
2. **Your §10 item — exact wording.** `docs/ARCHITECTURE.md` §10, item **#15** (in the "Priority — coverage-audit additions" subsection). Read all bullets, and the "Decided omissions" tail — that is where this item goes if the research verdict is NO.
3. **The gating research prompt** — `dev/prompts/2026-07-02-s10-research-15-rewind-handoff.md` — so you understand what was asked and can judge whether the report actually answered it (if the report is thin or hedged, treat the mechanism as unconfirmed and lean toward the omission branch + a "needs a firmer research answer" note).
4. **Supporting mechanism research** — `dev/notes/research/research-cli-stream-and-permissions-api.md` (resume/`--resume`, session semantics) and `dev/notes/research/claude-compaction-reference.md` (`compact_boundary`, summary records — relevant to transcript-surgery integrity and finding safe truncation boundaries).
5. **THE pattern to copy** — `tests/test_bridge_finisher_live.py`. Mirror its shape (module-level `pytestmark`, sidecar-on-`sys.path` shim, throwaway WSL diag dir, `asyncio.run(flow())` bodies, read-state-back-and-assert). Its `resume`-after-restart test is the closest existing analog to what you'll extend — study how it drives turns and re-reads the transcript.
6. **The modules this test touches** (read real code, don't guess):
   - `bridge/bridge.py` — `create`, `send`, `keys`, `read_log(name, last_n, types)`, `status`, `wait_idle`, `close`, `resume`, `session_id_for` (~line 428) / `register_session_id` (~line 435), and `find_transcript` (via `transcript.py`, ~line 972) — the transcript is `<session-id>.jsonl` and the session id is pinned at launch. Any transcript-surgery mechanism operates on these files.
   - `sidecar/drivers/bridge.py` — how a session is launched and resumed (so a fork/rewind can reuse the launch path).
   - `bridge/transcript.py` — `find_transcript`, `parse_transcript` (how entries are read back and paired).

---

## 3. Precondition gate (do this FIRST — it decides everything below)

1. Confirm `dev/notes/research/s10-research-15-rewind-handoff.md` exists. If not → **blocked**, stop and report.
2. Read its Verdict for **rewind (A)** and **fork (B)** and note, for each, one of: **YES** (confirmed feasible mechanism), **PARTIAL** (an approximation like reconstruct-and-replay, with fidelity caveats), **NO** (no mechanism).
3. Extract the recommended mechanism's **concrete operations** — e.g. "truncate `<id>.jsonl` after the last `tool_result` at/before line N, then `claude --resume <id>`", or "copy `<id>.jsonl` → `<newid>.jsonl`, truncate, launch `--resume <newid>`", or "SDK fork call X", or "start fresh + seed prefix as preamble."
4. **Route:**
   - Any of rewind/fork is **YES or PARTIAL** → go to **§5A (build the test)**, instantiating the report's steps for the mechanism(s) that scored YES/PARTIAL. (If only one of the two is feasible, test only that one and record the other as omitted.)
   - Both are **NO** → go to **§5B (record the omission)**. Build no test.
5. If the report is ambiguous/hedged enough that you can't extract concrete operations → treat as **NO-for-now**: go to §5B and add a note that the research needs a firmer, spike-ready answer before this can proceed.

---

## 4. What "proving it" means (the observable, mechanism-agnostic)

Whatever mechanism the research names, the **observable that proves rewind/fork actually happened** is the same. Name it and read it back from the live transcript — never assert on the value you just wrote:

- **Rewind (A) proof:** build a conversation with **distinguishable, ordered facts** — e.g. drive turns that each plant a unique token the agent will "remember" ("Remember codeword ALPHA-1", then ALPHA-2, then ALPHA-3). Pick a rewind point *between* tokens (say, after ALPHA-2). Apply the mechanism. Then **resume and ask the agent what codewords it knows.** Proof = the resumed agent **knows ALPHA-1/ALPHA-2 but has genuinely lost ALPHA-3** (the post-N history), AND can continue coherently. If it still "remembers" ALPHA-3, or the resume fails/corrupts, the mechanism did not truncate-and-resume — that's a finding.
- **Fork (B) proof:** from the same seeded conversation, fork at point N into a **new** session id. Proof = **both** sessions exist and are independent: the fork knows the prefix (ALPHA-1/ALPHA-2) but diverges when driven separately, AND the **original session is untouched** (still knows ALPHA-3, still resumable). If the operation mutates or destroys the original, it's a rewind-in-disguise, not a fork — record it as such.
- **Transcript integrity:** after the operation, `parse_transcript` must still read the file (no dangling `tool_use` without its `tool_result`, no parse error). If the mechanism requires cutting only on safe boundaries (turn ends), your test must find those boundaries (per the compaction/`compact_boundary` note), not cut blindly.

---

## 5A. Build the test (only if §3 routed here)

Create **one** new file: **`tests/test_rewind_handoff_live.py`**. Slug: **`rewind`**. Module-level `pytestmark = [pytest.mark.integration, pytest.mark.slow]`. Mirror the finisher's imports/shim. Use your **own** `TmuxBridge()` (see §7 — do NOT use the shared `bridge` fixture).

Instantiate the research report's steps into this skeleton (adapt names/commands to the actual mechanism):

1. **Seed** — spawn a tab-less, uniquely-named session (`rewind-<uuid8>`, `show=False`) in a throwaway WSL diag dir. Drive 3–4 turns planting ordered codewords (ALPHA-1..N), `wait_idle` between them. Record the transcript path via `find_transcript` and note candidate truncation boundaries (turn ends / `tool_result` positions).
2. **Apply the mechanism** — perform exactly the file/command operations the research prescribes for rewind and/or fork (edit/copy the JSONL, run the resume/fork command, etc.). Keep every operation scoped to **your own** session's files.
3. **Resume & interrogate** — resume the rewound (or forked) session and ask it which codewords it knows; for fork, drive both sessions and confirm independence + original untouched.
4. **Assert on the §4 observable** — memory-loss-past-N for rewind; prefix-shared-but-independent + original-intact for fork; transcript still parses.
5. **Teardown** — `close()` your own session(s) and `rm -rf` your own diag dir. Never `kill-server`.

Write one focused test function per feasible operation (`test_rewind_truncate_and_resume`, `test_handoff_fork_from_point`) — skip/omit the one the research scored NO, with a clear skip reason.

**Finalize the header banner:** once you've instantiated real steps, update this prompt file's top banner is **not** your job — but DO record, in the test's module docstring and the DEVLOG, exactly which mechanism the research named and which you implemented, so the §10 item can graduate.

---

## 5B. Record the omission (only if §3 routed here)

Do **NOT** build a passing test. Instead:

1. Write up a short findings note (in your final report + DEVLOG) stating: the research verdict was NO (or too ambiguous to spike), no truncate-and-resume / fork mechanism is feasible on this build, and therefore Rewind/Handoff's conversation-carry cannot be built as designed.
2. **Propose moving §10 #15 to "Decided omissions"** with the fallback wording from the item: *Rewind/Handoff are cut or degraded to whole-session `--resume` + fresh-agent Create-tab prepopulation only.* (Handoff's settings-prepopulation half stays; the conversation-carry half is the omitted part.)
3. Do not leave a stub test that fakes success. A single `pytest.skip("no rewind/fork mechanism — see research report; §10 #15 → Decided omissions")` marker test carrying the reason is acceptable as a durable breadcrumb; a green assertion is not.

---

## 6. Two honest exits (spike-or-omit)

- **WORKS** — a research-named mechanism demonstrably rewinds and/or forks a live session per the §4 observable. Keep `tests/test_rewind_handoff_live.py` as a durable live test; note the mechanism. This graduates §10 #15 toward a §7 body section + `/sessions/{id}/rewind` and `/handoff` endpoints.
- **OMITTED AFTER A REAL BASIS** — either the research found no mechanism (§5B), or you tried the research's mechanism live and it failed/corrupted (memory not lost, resume rejected, original mutated). Do **NOT** fabricate a green; record the finding and propose the Decided-omission. "Impossible" here rests on either a firm NO research verdict or an actual failed live attempt — not on skipping the work.

---

## 7. Isolation rules (parallel-safe — CRITICAL: reproduce these in the file header/comments)

Sibling agents may be running their own live bridge sessions at the same time. Violating any of these can kill their work.

- **ONE new file only** — `tests/test_rewind_handoff_live.py` (or, in the omission branch, no new test / one skip-marker file). Touch no other test file.
- **Uniquely-named tmux sessions** — prefix with the slug: `rewind-<uuid8>`. Never a fixed/shared name. A fork creates a *second* uniquely-named session — track and tear down both.
- **Operate only on your OWN session's transcript files.** Any JSONL edit/copy targets only your `<your-session-id>.jsonl` in your own throwaway dir — never another agent's transcript, never a shared `~/.claude` record you didn't create.
- **NEVER call `tmux kill-server`** (directly or via any helper) in teardown — it kills *every* agent's sessions.
- **Run ONLY your own new test** in isolation — not the whole live tier.
- **Do NOT edit shared files** — `tests/conftest.py`, `pyproject.toml`, `tests/README.md`. If you think you need a new fixture, marker, pythonpath tidy, or a change to the §10 item text / Decided omissions, **STOP and report it to the human** (the omission *proposal* is a written recommendation, not an edit you make yourself).
- **The non-obvious trap:** the finisher leans on conftest's session-scoped **`bridge` fixture**, whose **setup AND teardown both call `_kill_all_tmux()` (= `tmux kill-server`)** — which would kill sibling agents' live sessions. So **instantiate your OWN `TmuxBridge()`** and tear down **only** your uniquely-named session(s) via `bridge.close(name)` + your own dir. Never a broad kill.

---

## 8. Definition of done

- **Build branch (§5A):** run your **single** new test through the repo venv and paste the **actual** pytest result line — no paraphrase:

  ```powershell
  .\.venv\Scripts\python.exe -m pytest tests\test_rewind_handoff_live.py -m integration
  # or:  tests\run.ps1 tests\test_rewind_handoff_live.py -m integration
  ```
  (Create the venv first if missing: `python -m venv .venv; .\.venv\Scripts\python -m pip install -r requirements.txt`.) The pasted line must reflect a real pass of the §4 observable (or a real xfail/skip carrying a live-attempt finding).
- **Omission branch (§5B):** the deliverable is the written findings + the §10 #15 → Decided-omissions proposal + (optionally) the skip-marker test's result line. No fake green.
- State clearly in your report **which branch you took and why** (quote the research verdict).
- Nothing here renders a UI, so the CLAUDE.md "Verifying UI changes" browser pass does not apply.
- **DEVLOG the change** before you finish — append a new dated entry at the bottom of `DEVLOG.md` (which branch, the mechanism, files added/omission proposed), per the CLAUDE.md DEVLOG rule.

---

## 9. Guardrails (from CLAUDE.md — reproduce, do not skip)

- **Never create a git branch.** Work on `main`. Do not run `git checkout -b` / `switch -c` / `branch <name>` / `worktree add` — these are gated and will prompt; if one prompts, **stop**. Committing to `main` is fine (but the orchestrator handles git here — do not commit unless told).
- **Bridge sessions stay TAB-LESS.** Create with `show=False`; **never** pass `show=True` and **never** call `show()`. An auto-popped Windows Terminal tab steals the user's focus mid-task.
- **Scratch artifacts go to `.scratch/`** — never the repo root or other project folders. Per-run DEBUG detail goes to `tests/log/` (gitignored) via `logging.getLogger(__name__)`.
- **pytest is the standard** — no ad-hoc scripts. Tag this live test `@pytest.mark.integration` + `@pytest.mark.slow` (module-level `pytestmark`).
