# Doc-integration workflow tracker

> **What this is:** rough working record for the test-findings → doc-integration workflow (session lineage
> `dev-doc-4d` → `4e` → current). One job: **nothing established — test verdicts, research findings,
> decisions — gets lost before it lands in a major doc.** Update as phases complete; keep it rough.
> Archive this file with the other scratch docs when the workflow ends (Phase 7/9).
>
> Major docs = `docs/ARCHITECTURE.md` (primary) · `tests/README.md` · `design/DESIGN.md` · `CLAUDE.md` · `DEVLOG.md`.

## Phase ledger

```
[✓] 1.  Review 9 test-build transcripts — all 17 spikes build+pass live (af4964d); findings trustworthy.
[✓] 1a. GATE: no product-code fixes in this workflow — 5 code gaps → §11 rows only. Test-infra → Phase 2.
[✓] 2.  tests/README.md 17-spike table + conftest live-detection + playwright/psutil deps.
        [✓] 2a. DEVLOG rotation-05 · [✓] 2b. committed + pushed (40e944f).
[✓] 3.  ARCHITECTURE §11 "Build backlog & queue" created; [BB] stripped/homed ((open) → §10 #23–25,
        #13, #22); §10 de-referenced; TODO.md cut down; CLAUDE.md synced.
        [✓] 3a. DEVLOG · [✓] 3c. correction pass: [BH] un-ported (§11.4 deleted, TODO restored);
        ALL inbound TODO.md refs stripped (ARCHITECTURE + CLAUDE.md grep-clean).
        [ ] 3b. commit — pending user go.
[✓] 4.  Harvest → docs:
        [✓] 4a. Reviewed the 5 research reports (Sonnet subagents, 2026-07-03). All settled: #12/#13/#22
                → 🧪 needs-spike; #14 → ◐; #15 → ✅ (spike-passed).
        [✓] 4b. Harvested 17 spike verdicts + 5 research findings → §10 status/evidence (8 → ✅, ~9 → ◐,
                #3 held 🧪 credit-gated); §7.15/§7.16 corrected; 5 code gaps + parser audit → new §11.4
                #23–28; 2 spike-derived features → §11.3 #21/#22.
        [✓] 4c. Late spikes ran 2026-07-04 (concurrent agent): #4 inject-tail INFEASIBLE, #7 runstrip
                INFEASIBLE — both confirm shipped fallbacks. Harvested → §10 #4/#7 (⛔ resolved-at-fallback)
                + Decided-omissions note; test files committed.
[✓] 5.  Resolved the 3 doc-vs-doc contradiction orphans WITH the user (§E) — decisions applied to
        docs/ARCHITECTURE.md (§7.5 / §4.4 / §5.2 / §7.16 / §8.5 + the two ⚠-index rows) + CLAUDE.md
        (2026-07-04; see DEVLOG).
[ ] 6.  Integrate remaining orphans (Tier-3 decided-omissions, Tier-4 trio) → §10/§11/body.
[ ] 7.  Verify unverified-behavior-candidates.md fully integrated → archive both 07-02 scratch docs.
[ ] 8.  FINAL comprehensive integration-verification sweep (full reachable trail vs major docs;
        state what could / could not be cross-checked).
[ ] 9.  Feature-refactor §10/§11 (certainty stays the section split; group by feature within) with an
        old→new mapping table; strip ex-BB scaffolding; re-verify zero inbound TODO.md refs repo-wide;
        archive this tracker.
```

## Standing rules (locked in-conversation — do not re-litigate)

- **TODO.md is private.** Nothing outside `dev/notes/TODO.md` references it — full stop. Agents touch it
  only when the human points them there. (Verified 07-03: zero refs in ARCHITECTURE.md + CLAUDE.md.)
- **§10 = don't-know-yet · §11 = know-how-queued.** Feature-grouping happens in the Phase 9 refactor,
  not before — port into the current structure through Phase 6.
- **ex-BB IDs in §11 are temporary scaffolding** — kept so the sweep can prove the port lossless;
  stripped in Phase 9.
- **No product-code fixes in this workflow.** Code gaps become §11 rows; the fixes are a later
  consolidated cleanup push.
- **No branches; work on `main`.** Tracking = this doc + inline ledger + a DEVLOG entry per repo-changing chunk.

## Artifact inventory — everything that must be accounted for

### A. Spike tests — 17 built 2026-07-02, all pass live @ `af4964d` (run records in `tests/log/`)

In `tests/README.md` ✓ (Phase 2). "§ harvest" = verdict + consequences written into ARCHITECTURE (Phase 4b).

| Test file | §10 item | Verdict | § harvest |
|---|---|---|---|
| `test_permission_mode_cycle_live.py` | #1 | ✅ feasible — mid-run Shift+Tab flip works, suppresses prompts | ✅ 4b |
| `test_thinking_toggle_live.py` | #2 | ✅ feasible — via the Meta+T modal panel (read-backable) | ✅ 4b |
| `test_fast_mode_toggle_live.py` | #3 | 🚫 account credit-gated (honest xfail) → move to Decided omissions | ✅ 4b |
| `test_console_mirror_live.py` | #5 | ✅ feasible — mirror + passthrough + ANSI via `-e`; xterm-class renderer = frontend job (deferred, not failed) | ✅ 4b |
| `test_plan_decision_hooks_live.py` | #6 | ✅ feasible — cards raised; resume = `keys()` Enter, NOT hook `updatedInput` (correct #6's text) | ✅ 4b |
| `test_subagent_status_live.py` | #8 | ✅ feasible — live active-vs-quiet off the subagent's own transcript | ✅ 4b |
| `test_context_compact_live.py` | #9 | ✅ feasible — `/context` category parse + `compact_boundary` metadata | ✅ 4b |
| `test_oneclick_launch_live.py` | #10 | ✅ feasible — modeled in Python; real Electron-main POC still owed (→ §11 row) | ✅ 4b |
| `test_per_agent_cost_live.py` | #11 | ✅ feasible — **OVERTURNS the "honest blank" assumption**: `/cost` yields real per-session $ (correct §7.15 + #11) | ✅ 4b |
| `test_hook_event_stream_live.py` | #14 | ✅ feasible — permission_mode + tool on hook events; caveats: `Notification` lacks mode; concurrent-load ordering/dedup UNTESTED; run alongside polling, not instead | ✅ 4b |
| `test_rewind_handoff_live.py` | #15 | ✅ feasible — BOTH rewind and fork-from-point proven live | ✅ 4b |
| `test_system_fault_harvest_live.py` | #16 | ⚠ partial — MCP outage + auth expiry detectable; **usage-cap wording missed** (→ code gap D2); reactive auth-expiry screen signal unconfirmed | ✅ 4b |
| `test_polling_scale_ceiling_live.py` | #17 | ⚠ measured — degrades from N=1 (~1.3 s/cycle), ~10 s lag @ N=9 (→ code gap D3) | ✅ 4b |
| `test_usage_context_sources_live.py` | #18/#21 | ✅ boundaries — statusLine context = per-turn snapshot (not mid-run feed); account = split-source (→ gap D4); live %/limits = screen-scrape only | ✅ 4b |
| `test_console_clear_transcript_live.py` | #19 | ⚠ hazard confirmed — `/clear` rotates JSONL and orphans the pinned resolution (→ code gap D1); `/compact` safe | ✅ 4b |
| `test_bypass_auto_preconditions_live.py` | #20 | ✅ feasible — 5-case matrix; un-pre-armed bypass = SILENTLY ABSENT from the mode ring (UI must gate) | ✅ 4b |
| `tests/ui/test_ui_slice_live.py` | UI slice | ✅ feasible — browser on the `api.ts` contract drives the full live loop | n/a (contract proof; noted in README) |

### B. Late spikes — prompts authored 07-02, dispatched 2026-07-03 (were silently un-run; caught 07-03)

| Prompt | §10 item | Status |
|---|---|---|
| `dev/prompts/2026-07-02-s10-build-04-inject-tail.md` | #4 (instant mid-turn Inject) | ✅ INFEASIBLE — fallback final (harvested 4c) |
| `dev/prompts/2026-07-02-s10-build-07-runstrip-tail.md` | #7 (genuine progress signal) | ✅ INFEASIBLE — fallback final (harvested 4c) |

### C. Research reports — all 5 exist in `dev/notes/research/`; none reviewed or harvested yet

| Report | §10 item | Reviewed (4a) | Harvested (4b) |
|---|---|---|---|
| `attachment-citation-path-materialization-report.md` | #12 | ☑ | ☑ |
| `native-claude-code-coordination-report-2026-07-02.md` | #13 | ☑ | ☑ |
| `claude_code_hook_event_stream_report.md` | #14 | ☑ | ☑ |
| `s10-research-15-rewind-handoff.md` | #15 | ☑ (spike-validated in practice) | ☑ |
| `s10-research-22-subagent-management.md` | #22 | ☑ | ☑ |

(Pre-batch research also on file: mode-control, compaction reference, subagent architecture, CLI
stream/permissions API, electron architecture, plugin ecosystem — already cited by §10 where relevant.)

### D. Code gaps discovered by the spikes — document-only (→ §11.4 #23–28, homed 4b; fixes = later cleanup push)

1. `/clear` transcript orphaning — re-resolve + `register_session_id` after Console `/clear` (`bridge/bridge.py`, `sidecar/main.py`)
2. Usage-limit matcher misses subscription-cap wording ("weekly usage limit") (`sidecar/inbox.py` `classify_error`)
3. Polling scale — batch the ~5 WSL spawns/cycle + adaptive cadence (`sidecar/drivers/bridge.py`)
4. Account split-source + no auth-expiry reader (`sidecar/settings_io.py`; `.claude.json` tier fields unmatched)
5. Real Electron-main sidecar-lifecycle POC (spike modeled it in Python) (`frontend/`)

### E. Contradiction orphans — need USER decisions (Phase 5; detail in `2026-07-02-coverage-audit-orphans.md`)

1. [✓] **Identity editing** — DECIDED: all 5 fields **editable**; the **name** is also registered as the
       real Claude Code session name (`claude --name` at launch, `/rename` on edit — confirmed in `--help`).
       §7.5 flipped read-only→editable (+ display-metadata / stable-id rationale) + ⚠-index row.
2. [✓] **Frontend §4.4** — DECIDED: **park-and-rebuild** the renderer fresh from `design/`; the freeze is
       scoped to the *visible UI* only, NOT the Electron main-process shell (sidecar lifecycle, window,
       packaging — stays active feasibility work). §4.4 rewritten; CLAUDE.md `frontend/` row + freeze note.
3. [✓] **`createDoc`** — DECIDED: dashboard **may create / delete / explicit-edit** docs; the "never writes"
       rule narrowed to *review-layer annotations only* (those stay in the `.meta.json` sidecar). §5.2 gained
       `POST`/`DELETE /library/document`; §7.16 + §8.5 reworded + ⚠-index row.

### F. Remaining orphans (Phase 6; same source doc)

- Tier-3 "record a decided-omission" minors · Tier-4 "worth elevating" trio

### G. Scratch docs to archive when their content is fully homed

- `dev/notes/scratch/2026-07-02-coverage-audit-orphans.md` (after Phases 5–6)
- `dev/notes/scratch/2026-07-02-unverified-behavior-candidates.md` (verify in Phase 7)
- this tracker (last — Phase 9)

## Running todo / open decisions

- [✓] 3b: committed 40decbf (Phase 3+3c + tracker + design [ND] triage), pushed to origin/main.
- [✓] 4b flag: #3 fast-mode RESOLVED — user enabled Fast credits (2026-07-04); re-ran the spike →
      ✅ proven (`Meta+O` opens the Fast panel, `Space` toggles OFF↔ON, read-backable there-and-back).
      §10 #3 → ✅ proven; Decided-omissions note updated; test strengthened from panel-appears to full flip.
- [✓] 4c: both spikes ran INFEASIBLE (2026-07-04); harvested → §10 #4/#7 (⛔ resolved-at-fallback) + Decided-omissions note.
- [✓] Phase 5 decisions (§E) — user decided all 3 (2026-07-04); applied to ARCHITECTURE.md + CLAUDE.md.
- [ ] BB8 "Agent Archive" sits in §11.3 #18 with a value-unclear caveat — user may prefer it demoted to §10
- [ ] Phase 9: also re-check the stale `.claude/worktrees/wf_*` clutter noticed 07-03 (unrelated to this workflow; cleanup candidate)
