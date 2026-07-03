# Build prompt — Console `/clear` (and `/compact`) transcript-path orphaning spike

## 1. Header

- **Test working name:** `console_clear_transcript_live`
- **§10 item:** **#19 — Console `/clear` (and `/compact`) transcript-path orphaning — 🧪 needs-spike** (docs/ARCHITECTURE.md §10, item **#19**, `→ §7.13, §8.6, §8.7`)
- **Goal:** Determine — live — whether running **`/clear`** (and **`/compact`**) from the Console **rotates the agent's JSONL transcript to a new file**, and if so, whether the bridge's pinned-session-id transcript resolution **still finds the current transcript** or silently **orphans** it (loses history / reads a stale file).

This is a **spike-or-report** task. Confirming the hazard *is real* (and needs a re-resolve) or *is not* (resolution follows the rotation) are both honest, valuable outcomes. Do **not** assert "no problem" without actually running `/clear` and checking the path.

---

## 2. Read first (open these before writing a line)

1. **Your §10 item — exact wording.** `docs/ARCHITECTURE.md` §10, item **#19** (in "Priority — coverage-audit additions"). Read all bullets: Desired / Blocker / Research-POC / Fallback.
2. **The transcript master-record policy + the watch-spot.** `docs/ARCHITECTURE.md` §8.6 (transcripts — the master-record policy) and **§8.7 "Two spots to watch"** (this hazard is one of them). Plus §7.13 (Console) — `/clear` and `/compact` are Console commands.
3. **How resolution is pinned (the crux).** `bridge/bridge.py`:
   - `session_id_for(name)` (~line 428) and `register_session_id(name, session_id)` (~line 435) — the session id is **pinned at launch** so `find_transcript` resolves this agent's **own** `<session-id>.jsonl` even when co-located agents share a dir (see the comments ~lines 145–147, 300–303, 358).
   - `read_log` (~line 961) → `find_transcript(self, name)` (~line 972, in `bridge/transcript.py`) → `parse_transcript`. **If `/clear` writes a NEW `<new-id>.jsonl` but the pinned id is still the old one, `find_transcript` may resolve the stale/empty file** — that's the orphaning hypothesis.
   - `bridge/transcript.py` — `find_transcript` (how it locates the file: by pinned id, or "newest `.jsonl` in the project dir"? The comment notes the pinned id **replaced** an old "newest jsonl" heuristic — which resolution wins after a rotation matters).
4. **The research.** `dev/notes/research/claude-compaction-reference.md` — what `/compact` does, and `compact_boundary` transcript metadata (a compaction may write a boundary marker or a new file rather than rotating the id). Use it to predict whether `/compact` rotates the path or annotates in place.
5. **THE pattern to copy.** `tests/test_bridge_finisher_live.py` — mirror its shape (module-level `pytestmark`, sidecar-on-`sys.path` shim, throwaway WSL diag dir, `asyncio.run(flow())`, read-state-back-and-assert). Bridge API: `create`, `send`, `keys`, `read`, `read_log`, `status`, `wait_idle`, `close`, `session_id_for`, `_run`.

---

## 3. Mechanism / hypothesis

**Known behavior:** the sidecar resolves an agent's transcript by its **pinned session id** → `<session-id>.jsonl`. `read_log`/`find_transcript` depend on that id staying correct.

**Hypothesis:** `/clear` starts a fresh conversation, which on some Claude Code builds means a **new session id and a new `<new-id>.jsonl`** on disk. If the bridge keeps resolving the **old** pinned id, then after a Console `/clear`: (a) `read_log` reads the **old** (now-stale) transcript, and (b) new turns land in a file the sidecar isn't watching → **orphaned history**. `/compact` may behave differently — it might annotate the *same* file with a `compact_boundary` (no rotation) or also rotate. The spike distinguishes these empirically.

**Confirm, do not assume:** whether `/clear` (and `/compact`) actually change the on-disk transcript **path/id** on this build, and whether `find_transcript` follows or orphans the change.

---

## 4. Build this

Create **one** new file: **`tests/test_console_clear_transcript_live.py`**. Slug: **`clconsole`**. Module-level `pytestmark = [pytest.mark.integration, pytest.mark.slow]`. Mirror the finisher's imports/shim. Use your **own** `TmuxBridge()` (see §7 — do NOT use the shared `bridge` fixture). Two focused test functions (`/clear` and `/compact`):

**Common flow (both tests):**
1. **Setup** — throwaway WSL diag dir; spawn a tab-less, uniquely-named session (`clconsole-<uuid8>`, `show=False`); `wait_idle`.
2. **Establish a transcript** — drive one turn that plants a unique codeword (e.g. "Remember the codeword ORPHAN-<uuid6>"), `wait_idle`. Record: the pinned id via `session_id_for(name)`, the resolved transcript path via `find_transcript`, and that `read_log` returns the codeword turn. **Snapshot the set of `*.jsonl` files** in the agent's project/session dir (via `_run("ls -la … *.jsonl")`) with mtimes.
3. **Run the Console command** — send the literal command into the pane the way the Console does: `bridge.send(name, "/clear")` (then, in the other test, `/compact`), and `wait_idle` / `watch` for it to take.
4. **Re-inspect (the crux — §5):** re-snapshot the `*.jsonl` files (did a new one appear? did the id change?), re-check `session_id_for` and `find_transcript` (does resolution point at the new file or the old one?), drive a **new** turn planting a second codeword (POST-CLEAR-<uuid6>), and check where it lands and whether `read_log` surfaces it.
5. **Teardown** — `close()` your session, `rm -rf` your dir. Never `kill-server`.

Log at DEBUG (`logging.getLogger(__name__)`): before/after file sets + mtimes, pinned id before/after, resolved path before/after, and whether the post-clear turn is readable via `read_log`.

---

## 5. The read-back is the crux

Sending `/clear` is trivial — **proving what it did to the transcript resolution is the whole test.** Name the observables and read them from disk + the resolver, not from assumption:

- **Did the path rotate?** Compare the `*.jsonl` file set (and the pinned id / resolved path) before vs after `/clear`. A new `<id>.jsonl` appearing (or the resolved path changing) = rotation.
- **Did resolution orphan it?** After `/clear`, drive a new turn with a fresh codeword and check: does `read_log(name)` surface the **post-clear** turn, or does it still read the **pre-clear** file (or return the stale codeword)? If `read_log` can't see post-clear turns, **the transcript is orphaned** — the §19 hazard is confirmed and a re-resolve is needed.
- **`/compact` variant:** did it rotate (new file) or annotate in place (a `compact_boundary` entry in the same file)? Record which — they have different fixes.
- **Whatever you find is the finding.** "Orphans after `/clear`, `/compact` annotates in place" and "resolution follows both, no orphaning" are equally valid results — assert on the observed reality, and don't force a green if resolution actually breaks.

---

## 6. Two honest exits (spike-or-report)

- **HAZARD CONFIRMED** — `/clear` (and/or `/compact`) rotates the transcript and the pinned-id resolution orphans it. Keep `tests/test_console_clear_transcript_live.py` as a durable regression test asserting the observed behavior, and note the exact fix a build needs (re-resolve the session id after a Console clear/compact — the §19 fallback). This graduates §19 into a §8.7 "spots to watch" resolution + a re-resolve step.
- **NO HAZARD (resolution follows the rotation)** — if `find_transcript` correctly follows the new file (or `/clear`/`/compact` don't rotate the id on this build), record that as the finding and assert the observed correct behavior. That's a legitimate, reassuring result — not a failure. Either way, the verdict rests on the **actual live run**, never a code re-read.

---

## 7. Isolation rules (parallel-safe — CRITICAL: reproduce these in the file header/comments)

Sibling agents may be running their own live bridge sessions at the same time. Violating any of these can kill their work.

- **ONE new file only** — `tests/test_console_clear_transcript_live.py`. Do not touch any other test file.
- **Uniquely-named tmux session** — prefix with the slug: `clconsole-<uuid8>`. Never a fixed/shared name.
- **Inspect only YOUR own agent's transcript files** — in your own throwaway diag dir. Never `ls`/read/modify another agent's `~/.claude` transcripts, and never run `/clear` against a session you didn't spawn.
- **NEVER call `tmux kill-server`** (directly or via any helper) in teardown — it kills *every* agent's sessions.
- **Run ONLY your own new test** in isolation — not the whole live tier.
- **Do NOT edit shared files** — `tests/conftest.py`, `pyproject.toml`, `tests/README.md`. If you think you need a new fixture, marker, or a pythonpath tidy, **STOP and report it to the human**.
- **The non-obvious trap:** the finisher leans on conftest's session-scoped **`bridge` fixture**, whose **setup AND teardown both call `_kill_all_tmux()` (= `tmux kill-server`)** — which would kill sibling agents' sessions. **Instantiate your OWN `TmuxBridge()`** and tear down only your uniquely-named session via `bridge.close(name)` + your own dir. Never a broad kill.

---

## 8. Definition of done

- Run your **single** new test through the repo venv and paste the **actual** pytest result line — no paraphrase (the terminal `= N passed =` / `= N xfailed =` line, and/or `tests/log/results_latest.txt`):

  ```powershell
  .\.venv\Scripts\python.exe -m pytest tests\test_console_clear_transcript_live.py -m integration
  # or:  tests\run.ps1 tests\test_console_clear_transcript_live.py -m integration
  ```
  (Create the venv first if missing: `python -m venv .venv; .\.venv\Scripts\python -m pip install -r requirements.txt`.)
- Your report must state, for **`/clear`** and **`/compact`** separately: did the transcript path rotate, and did resolution orphan it — plus the fix if a hazard is confirmed (the §19 re-resolve step).
- Nothing here renders a UI, so the CLAUDE.md "Verifying UI changes" browser pass does not apply.
- **DEVLOG the change** before you finish — append a new dated entry at the bottom of `DEVLOG.md` (the observed behavior + files added), per the CLAUDE.md DEVLOG rule.

---

## 9. Guardrails (from CLAUDE.md — reproduce, do not skip)

- **Never create a git branch.** Work on `main`. Do not run `git checkout -b` / `switch -c` / `branch <name>` / `worktree add` — these are gated and will prompt; if one prompts, **stop**. Committing to `main` is fine (but the orchestrator handles git here — do not commit unless told).
- **Bridge sessions stay TAB-LESS.** Create with `show=False`; **never** pass `show=True` and **never** call `show()`. An auto-popped Windows Terminal tab steals the user's focus mid-task.
- **Scratch artifacts go to `.scratch/`** — never the repo root or other project folders. Per-run DEBUG detail goes to `tests/log/` (gitignored) via `logging.getLogger(__name__)`.
- **pytest is the standard** — no ad-hoc scripts. Tag this live test `@pytest.mark.integration` + `@pytest.mark.slow` (module-level `pytestmark`).
