# Build-sprint run — live handoff state (2026-07-10)

> **What this is:** the running state file for THE build sprint (prompt: `dev/prompts/2026-07-09-build-sprint-run.md`). If the driving session dies or hands off, a fresh session continues FROM HERE: read the prompt, read this file, check `git log` + DEVLOG since `9c58ded`, then pick up at "NEXT ACTIONS". Update this file at every stage boundary.

## ✅ RUN COMPLETE @ 2026-07-16 — this note is HISTORICAL, not authoritative

The build run finished on 2026-07-16 (session 3, the build-completion run): the complete ARCHITECTURE §11 queue #1–#50 is built and tombstoned, §10 #1 is resolved into the body, the renderer is rebuilt + fully wired, the gap batch landed, and the system was e2e-proven end to end in the real Electron window (evidence: DEVLOG entries dated 2026-07-15/16; `.scratch/e2e-final/`). Everything below this banner describes a MID-RUN state that no longer exists — a fresh session must reconcile from `DEVLOG.md` + `git log` + `docs/ARCHITECTURE.md`, never from this note.

## ⚠⚠ HANDOFF @ 2026-07-15 (build-sprint SESSION 2 — mid-Stage-5; AUTHORITATIVE, supersedes the post-restart section below for STATE)

Session 2 resumed from the post-restart handoff and drove the sprint forward. **Reconcile from `git log` + DEVLOG (both current), not from background agents.** Everything below is committed + pushed to `origin/main`.

**DONE this session (each with a DEVLOG entry + ARCHITECTURE §11 tombstone):**
- **Stage 3** — §11 #29–#34 marker sweep (`8f3aaf5`). **Stage 4** — renderer #37 recovered (clean merge `dce54bb`), verified headed (all surfaces PASS, Console xterm streams live), 2 bug fixes (`3344dfa`). **`.npmrc`** pins `legacy-peer-deps` (the vite8/electron-vite5 set).
- **Stage 5 backend:** #19 git identity (`a547bc6`), #18 archive (`0611bd9`), #15 rewind/fork (`96568d6`), #17 resume + #16 handoff artifacts (`93d8077`). Hermetic tier **890 passed** (was 777).
- #40/#41/#39 renderer-feature backends **in flight** (a batch subagent) as of this note.

**REMAINING (priority order):**
1. Finish the #40/#41/#39 backend batch (name-pool draw, authors provenance, response presets) → commit + tombstone.
2. **#23 workflow approval** (spike-proven, `tests/workflow_approval_probe/`), then **#46** per-turn capture, **#44** docs-in-context, **#28** import extractors, **#45** prompt/UI-text library, **#24** queue awareness.
3. **Comprehensive renderer-wiring pass** (`frontend/src/renderer`, api.ts): stage-3 display (#30 context breakdown, #32 cost-on-cards — endpoints exist), #38 degraded-mode/backoff + narrow-width clamp (<~1130px middle column collapses), and the UI halves of #39/#40/#41 + the #15 Timeline + #18 archive + #17 resume surfaces. Re-verify headed via `dev/tools/ui-verify` (resize extremes, click every control).
4. **Isolated lanes** (main.py-free, low priority): #20 Electron one-click, #47 git-automation, #48 change-log watcher, #49 system-check agent.
5. **Stage 6** — §10 #1 attachment ladder (sidecar-served asset endpoint default).
6. **Final** — `start-dashboard.bat` e2e proof (real agent via the hydrated sidecar, events/inbox/links/scratchpad/console/fork flow, screenshots to `.scratch/`), commit the dogfood `.awl-cc-dash/` (#10), then the final §11 per-item report.
7. **Run-end cleanup** — remove the 5 leftover worktrees (renderer `agent-a793…` now merged; `agent-a862…` merged; `wf_8dfaa290-a45-1..4` abandoned) + delete their branches.

**Method in force:** backend spine built SERIALLY in the main tree (one subagent per item/batch — the shared `sidecar/main.py` makes parallel worktrees conflict-heavy), reviewed + tested (hermetic green) + committed + pushed by the orchestrator; small clean items batched 2–3 per subagent. **Environment ready:** launch in bypass; hydrate `CLAUDE_CODE_OAUTH_TOKEN` from the User env var in any shell that starts the sidecar/live tests (this VS Code session doesn't natively carry it — see the 2026-07-15 auth note). ttyd is installed (Console streams). Backend halves of renderer features exist; the renderer UI wiring is the remaining big frontend chunk.

## Ground rules in force (from the prompt — read it in full)
- Full autonomy, never pause for the operator. Git license granted for this run (branches/worktrees OK; merge back + delete before run end; commit/push main continuously).
- Hermetic tier green after every backend stage: `.venv\Scripts\python.exe -m pytest tests\ -m "not integration and not slow" -q`.
- DEVLOG every increment; clear ARCHITECTURE ⚠ Today markers + tombstone §11 queue rows (keep literal numbering) as items land.
- Bridge sessions ALWAYS tab-less. design/ is consumed, not redesigned. Transient artifacts → .scratch/ only.
- Worktree lane gotcha: `assets/icons/` is untracked → copy it into any new worktree or the icon-pool unit test fails.

## DONE (all pushed to origin/main)
- **Stage 0** — §11 #5 transcript retention pinned (`9c58ded`).
- **Stage 1** — storage & persistence set COMPLETE: #1–#4, #6–#9, #11, #42 built (#10 = CLAUDE.md note done; committed store lands at e2e). Commits `c4082ee`, `ad08a87`, `cb10c3b`, merges `71aeece` (bridge resume-launch + WSL rename), `00fc6d8` (library sidecars), docs sweep `a7ddfcb`. Key facts: canonical root via `storage.project_key()`; state store = `sidecar/state_store.py` (write-through hooks on inbox/links/watermark); cold-restore proven SAME-id on CC 2.1.202 (`tests/test_cold_restore_live.py`); roster routes per-project via runtime_store; projects.json index exists.
- **Stage 2 (main-context half)** — #21 hermetic half (`1c5a904`: `sidecar/runstate.py` arbiter + hook set in `_build_hook_settings` + endpoints `/internal/hooks/run-state|subagent/{agent}` + to_dict run_state + /subagents blend); #26 + #27 + #22 (`05ee1d6`: /projects list/register/open/close + driver.stop() record-keeping semantics; System identity + widened classifier + probe loop; plan verdict endpoint + PUT /library/document). Hermetic 538/538 at `05ee1d6`.

## STATE @ 2026-07-14 (stage 2 complete)
Stage 2 is FULLY merged + pushed (through the `docs: stage-2 marker sweep` commit): #12–#14, #21 (live-verified), #22, #25–#27, #35, #36, #43 built; the 24-finding review fix batch merged (groups A–F); hermetic **680/680**. Notable live findings: CC drifted 2.1.202→2.1.206 mid-sprint ("manual mode on" indicator; Meta+O→/fast fallback); prompt_id floor holds; SubagentStart fires on 2.1.206; subagent transcript = `agent_transcript_path`. Remaining §11 queue: #10 (dogfood commit @ e2e), #15–#20, #23, #24, #28, #29–#34 (stage-3 lane in flight), #37–#41 (renderer lane in flight), #44–#49; §10 #1 ladder.

## ⚠ HANDOFF @ 2026-07-15 (post-restart — AUTHORITATIVE; supersedes the "in flight" framing that was here)
The machine **restarted mid-run**, so NOTHING is running in the background — do not wait for task-notifications; the old lanes are dead processes. Reconcile from `git log` + DEVLOG, not from background agents. HEAD = `509b5fc`.
- **Stage 3 (readouts #29-backend, #30–#34): DONE + MERGED to main** (HEAD `509b5fc`; lane hermetic was 777). ⚠ **Doc debt:** the stage-3 ARCHITECTURE marker sweep was never run — §11 body rows #29–#34 and the §11.1 index rows (§5.2 #29, §6.2 #34, §7.15 #32/#33, §7.18 #30/#31) still read "owed today." Clear them; do NOT rebuild stage 3.
- **Stage 4 (#37 renderer rebuild): COMMITTED BUT STRANDED — do NOT rebuild from scratch.** 3 commits live on branch `worktree-agent-a793f72e4f4580488` (@ `2c554ae`): frame + Team Graph + Agent panel → Feed/Prompt/Library/Settings/Console → action-row Response-format control + cream window bg (new files incl. `renderer/store.tsx`, `renderer/lib/{icons,identity,transcript,toast}`, `tailwind.config.js`). It branched BEFORE stage 3 merged, so recovering it = merge/rebase onto current main (expect conflicts in `sidecar/main.py`, `sidecar/drivers/bridge.py`, `tests/`, and `frontend/`). Completeness is the last-commit state — assess on recovery; Console xterm streaming is the HIGH piece. Verify per CLAUDE.md "Verifying UI changes" (ui-verify headed; resize narrow/wide extremes; click every control).
- **Environment is READY (fixed 2026-07-15, this handoff session):**
  - Permission pauses fixed — `.claude/settings.json` `ask` is now `[]` and git is the `Bash(git *)` wildcard, so nothing prompts on git/worktree ops. **Launch the next session in bypass-permissions mode, same as before** (bypass + empty ask = zero prompts).
  - WSL agent auth fixed + live-verified — agents run on the operator's subscription via a long-lived `CLAUDE_CODE_OAUTH_TOKEN` (Windows user env var + `WSLENV=CLAUDE_CODE_OAUTH_TOKEN/u`), no `/login` needed. See ARCHITECTURE §6.4 + DEVLOG 2026-07-15. **Launch the sidecar from a terminal opened after the VS Code reload** so it inherits the token; agents inherit it from the tmux server env.
- **Leftover worktrees to clean at run-end** (git license requires it): `agent-a862aa668344b4015` (stage-3 lane — already merged, branch redundant), `agent-a793f72e4f4580488` (the renderer — keep until merged, then remove), `wf_8dfaa290-a45-1..4` (abandoned workflow sub-worktrees @ `f3b5839` — inspect, then remove).
- **Uncommitted prep changes on main** (this session): `.claude/settings.json`, `CLAUDE.md`, `docs/ARCHITECTURE.md`, `DEVLOG.md`, and this note — should be committed to main before the sprint resumes (clean base).

## REMAINING WORK (after recovering stage 4)
- **Stage 5:** #15 rewind/fork (≥2.1.191 gate + per-fork file-state policy), #18 archive (HIGH), #19 per-agent git identity (HIGH), #20 Electron-main one-click, #23 workflow approval (spike-proven, tests/workflow_approval_probe), #16/#17, #24, #28, #39/#40/#41, #44–#49 by judgment; §10 #1 attachment ladder.
- **Final:** e2e proof (start-dashboard.bat, real agent, events/inbox/links/scratchpad flow, screenshots to .scratch/) — NOW runnable since WSL auth works — commit the dogfood `.awl-cc-dash/` (#10), then the final report per the prompt (§11 per-item status, ⚠ assumed list, breakages, what remains).

## OLD in-flight list (all landed + merged, kept for history)
- **Lane D worktree** (#12 mode/thinking/fast levers + #13 backend): bridge lever methods + driver + endpoint rewires + live test `test_mode_control_wired_live.py`.
- **Lane E worktree** (#25 links fixes + #14 identity editing/--name): links single-relationship + piggyback + per-fire exchanges; identity endpoint + /rename.
- **Lane F worktree** (#21 live verify + #35 /clear re-resolve + #36 parser audit): `test_hook_ingest_live.py` + findings file; console /clear rotation handling; dual-name audit.
- **Fix-batch worktree**: the stage-1 adversarial review returned 24 CONFIRMED findings (journal: subagents/workflows/wf_f69fb454-c9b/journal.jsonl); a fix lane is implementing groups A (state-store locking + per-agent inbox merge + link merge-by-id + roster double-home), B (per-board scratchpad seqs + watermark clamp + mirror indent round-trip + lazy-load on scratch endpoints), C (WSL-internal path canonicalization via \\wsl.localhost UNC), D (library write-scope to plans/+docs/, delete resolve, rename rollback, root-meta aggregate), E (reconnect transcript_path seeding, warm-resume args, SDK result→Response card), F (migration never raises). TRIAGED-ACCEPTED (record in final report, no fix tonight): retired-numbers set is process-global across projects (number-skip bleed only); routing overlay rows are synthesized-id keyed and don't yet join transcript anchors (replay join rides the #37/replay work).
- Merge procedure per lane: `git merge --no-ff <worktree-branch>` → hermetic tier → `git worktree remove .claude/worktrees/<dir> --force` → `git branch -d <branch>` → push. Then clear the matching ARCHITECTURE markers (§6.2 mode no-ops row, §7.5/§7.6 rows, §7.13 /clear bullet, §7.4/§7.17 rows for #21 live) + tombstone queue rows #12/#13(backend)/#14/#21/#25/#35/#36 + DEVLOG.

## NEXT ACTIONS (in order) — see the ⚠ HANDOFF @ 2026-07-15 section above for authoritative state
1–3. **DONE** — lanes D/E/F merged, stage-1 review fixes applied, Stage 3 (readouts #29–#34) merged to main. (Stage-3 ARCHITECTURE marker sweep still owed — clear §11 #29–#34 + the matching §11.1 rows.)
4. **Stage 4 — recover the STRANDED renderer #37** (do NOT rebuild): merge/rebase branch `worktree-agent-a793f72e4f4580488` (@ `2c554ae`, 3 commits) onto current main, carrying `frontend/src/renderer/api.ts` as the preserved contract (extend for new endpoints: /projects*, /library/* set, plan/verdict, run_state, mode/fast/thinking, identity). Console = xterm.js streaming terminal (HIGH). Verify per CLAUDE.md "Verifying UI changes" via dev/tools/ui-verify (headed-parked; resize extremes; click every control; screenshots to .scratch/).
5. **Stage 5**: #8 e2e drive, #15 rewind/fork (≥2.1.191 gate + per-fork file-state policy), #18 agent archive (HIGH), #19 per-agent git identity (HIGH), #20 Electron-main one-click, #23 workflow approval (spike-proven, tests/workflow_approval_probe), #16/#17, #38–#41, #43–#49 by judgment.
6. **Stage 6**: §10 #1 attachment ladder (a: WSL-native ingest to assets/<id>/; b: sidecar GET asset endpoint = recommended default; c: file: optional; d: display-only chips fallback).
7. **Final**: start-dashboard.bat e2e proof (create agent, drive, events/inbox/links/scratchpad flow, screenshots to .scratch/), commit the dogfood .awl-cc-dash/ (#10), DEVLOG, final report per the prompt (§11 per-item status, ⚠ assumed list, breakages, remains).

## ⚠ assumed so far (carry into the final report)
- §11 tombstone rows keep literal numbering (vs deleting rows) — numbering-stability reading of the exit rule.
- Routing overlay written for ANY non-default-routed stamped event incl. synthesized ones.
- Root-matched legacy review sidecars live at project root, not listed by aggregate_metas (known seam).
- cwd-less agents keep app-level sessions.json fallback.
- Startup keeps reconnect-ALL records (picker-only startup lands with the renderer/#20).
- Plan revise = keys Escape (+ queued feedback) — unproven leg, verify at e2e.
- WSL-internal (non-/mnt) cwds were already broken pre-rename for project-store paths; unchanged (agents get Windows-path cwds in practice).
