# Build-sprint run — live handoff state (2026-07-10)

> **What this is:** the running state file for THE build sprint (prompt: `dev/prompts/2026-07-09-build-sprint-run.md`). If the driving session dies or hands off, a fresh session continues FROM HERE: read the prompt, read this file, check `git log` + DEVLOG since `9c58ded`, then pick up at "NEXT ACTIONS". Update this file at every stage boundary.

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

## IN FLIGHT (background, this session — check completion before proceeding)
- **Stage-3 lane** (worktree): #29 backend (ttyd attach endpoints), #30 (/context breakdown + compact history), #31 (statusLine per-turn capture), #32 (/cost per agent), #33 (account split-source), #34 (poll batching + adaptive cadence + re-measured ceiling).
- **Stage-4 lane** (worktree): the #37 renderer rebuild from design/ (priority: frame → Team Graph → Agent panel (+#13 UI) → Team Feed/Inbox → Prompt → Console xterm (HIGH) → Library → Settings/Projects), incl. #38 degraded mode; headed-verified via ui-verify per CLAUDE.md.
- On completion: merge each (conflicts likely in sidecar/main.py + drivers/bridge.py for stage 3; frontend/ for stage 4), hermetic green, marker sweep (§7.13/§7.18/§7.15/§6.2-polling rows; §4.3/§4.4/§3.x UI rows), DEVLOG.
- THEN stage 5 lane(s): #15 rewind/fork, #18 archive (HIGH), #19 git identity (HIGH), #20 one-click, #23 workflow approval (spike: tests/workflow_approval_probe), #16/#17, #39/#40/#41, #44–#49 by judgment; §10 #1 ladder. THEN the final e2e proof (start-dashboard.bat, real agent, screenshots to .scratch/), commit the dogfood .awl-cc-dash/ (#10), final report.

## OLD in-flight list (all landed + merged, kept for history)
- **Lane D worktree** (#12 mode/thinking/fast levers + #13 backend): bridge lever methods + driver + endpoint rewires + live test `test_mode_control_wired_live.py`.
- **Lane E worktree** (#25 links fixes + #14 identity editing/--name): links single-relationship + piggyback + per-fire exchanges; identity endpoint + /rename.
- **Lane F worktree** (#21 live verify + #35 /clear re-resolve + #36 parser audit): `test_hook_ingest_live.py` + findings file; console /clear rotation handling; dual-name audit.
- **Fix-batch worktree**: the stage-1 adversarial review returned 24 CONFIRMED findings (journal: subagents/workflows/wf_f69fb454-c9b/journal.jsonl); a fix lane is implementing groups A (state-store locking + per-agent inbox merge + link merge-by-id + roster double-home), B (per-board scratchpad seqs + watermark clamp + mirror indent round-trip + lazy-load on scratch endpoints), C (WSL-internal path canonicalization via \\wsl.localhost UNC), D (library write-scope to plans/+docs/, delete resolve, rename rollback, root-meta aggregate), E (reconnect transcript_path seeding, warm-resume args, SDK result→Response card), F (migration never raises). TRIAGED-ACCEPTED (record in final report, no fix tonight): retired-numbers set is process-global across projects (number-skip bleed only); routing overlay rows are synthesized-id keyed and don't yet join transcript anchors (replay join rides the #37/replay work).
- Merge procedure per lane: `git merge --no-ff <worktree-branch>` → hermetic tier → `git worktree remove .claude/worktrees/<dir> --force` → `git branch -d <branch>` → push. Then clear the matching ARCHITECTURE markers (§6.2 mode no-ops row, §7.5/§7.6 rows, §7.13 /clear bullet, §7.4/§7.17 rows for #21 live) + tombstone queue rows #12/#13(backend)/#14/#21/#25/#35/#36 + DEVLOG.

## NEXT ACTIONS (in order)
1. Merge lanes D/E/F as they complete (conflicts expected in sidecar/main.py endpoint regions + sidecar/drivers/bridge.py + bridge/bridge.py — resolve keeping BOTH sides' features). Hermetic green between merges. Docs sweep + DEVLOG after all three.
2. Apply stage-1 review findings (if any CONFIRMED).
3. **Stage 3 — readouts**: #29 backend (ttyd/WebSocket console attach + `window-size manual` pinning — see §7.13 + test_console_stream_attach_live), #30 (/context parse + compact history off compact_boundary), #31 (statusLine per-turn capture), #32 (/cost per-agent scrape), #33 (account tier source fix in settings_io), #34 (polling batch + adaptive cadence, then re-measure ceiling). Lanes: #30–#33 parallelize well; #34 + #29 bridge-heavy.
4. **Stage 4 — THE RENDERER REBUILD #37** (biggest item): fresh from design/ (mockup.html authority, tokens.css values, behavior.js logic, DESIGN.md intent; carry frontend/src/renderer/api.ts as the contract, extend for new endpoints: /projects*, /library/* new set, plan/verdict, run_state, mode/fast/thinking, identity). Console = xterm.js streaming terminal (HIGH). Verify per CLAUDE.md "Verifying UI changes" via dev/tools/ui-verify (headed-parked; resize extremes; click every control; screenshots to .scratch/).
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
