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
[ ] 4.  Harvest → docs:
        [ ] 4a. Review the 5 research reports (never reviewed — unlike the spike transcripts).
        [ ] 4b. Harvest spike verdicts + research findings → §10 corrections/evidence + §11 rows
                (incl. the 5 code gaps). §10 is already partially harvested — fill gaps.
        [ ] 4c. Late spikes #4 inject-tail / #7 runstrip-tail — dispatched 2026-07-03; review results
                + harvest when done.
[ ] 5.  Resolve doc-vs-doc contradiction orphans WITH the user (list §E below).
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
| `test_permission_mode_cycle_live.py` | #1 | ✅ feasible — mid-run Shift+Tab flip works, suppresses prompts | pending |
| `test_thinking_toggle_live.py` | #2 | ✅ feasible — via the Meta+T modal panel (read-backable) | pending |
| `test_fast_mode_toggle_live.py` | #3 | 🚫 account credit-gated (honest xfail) → move to Decided omissions | pending |
| `test_console_mirror_live.py` | #5 | ✅ feasible — mirror + passthrough + ANSI via `-e`; xterm-class renderer = frontend job (deferred, not failed) | pending |
| `test_plan_decision_hooks_live.py` | #6 | ✅ feasible — cards raised; resume = `keys()` Enter, NOT hook `updatedInput` (correct #6's text) | pending |
| `test_subagent_status_live.py` | #8 | ✅ feasible — live active-vs-quiet off the subagent's own transcript | pending |
| `test_context_compact_live.py` | #9 | ✅ feasible — `/context` category parse + `compact_boundary` metadata | pending |
| `test_oneclick_launch_live.py` | #10 | ✅ feasible — modeled in Python; real Electron-main POC still owed (→ §11 row) | pending |
| `test_per_agent_cost_live.py` | #11 | ✅ feasible — **OVERTURNS the "honest blank" assumption**: `/cost` yields real per-session $ (correct §7.15 + #11) | pending |
| `test_hook_event_stream_live.py` | #14 | ✅ feasible — permission_mode + tool on hook events; caveats: `Notification` lacks mode; concurrent-load ordering/dedup UNTESTED; run alongside polling, not instead | pending |
| `test_rewind_handoff_live.py` | #15 | ✅ feasible — BOTH rewind and fork-from-point proven live | pending |
| `test_system_fault_harvest_live.py` | #16 | ⚠ partial — MCP outage + auth expiry detectable; **usage-cap wording missed** (→ code gap D2); reactive auth-expiry screen signal unconfirmed | pending |
| `test_polling_scale_ceiling_live.py` | #17 | ⚠ measured — degrades from N=1 (~1.3 s/cycle), ~10 s lag @ N=9 (→ code gap D3) | pending |
| `test_usage_context_sources_live.py` | #18/#21 | ✅ boundaries — statusLine context = per-turn snapshot (not mid-run feed); account = split-source (→ gap D4); live %/limits = screen-scrape only | pending |
| `test_console_clear_transcript_live.py` | #19 | ⚠ hazard confirmed — `/clear` rotates JSONL and orphans the pinned resolution (→ code gap D1); `/compact` safe | pending |
| `test_bypass_auto_preconditions_live.py` | #20 | ✅ feasible — 5-case matrix; un-pre-armed bypass = SILENTLY ABSENT from the mode ring (UI must gate) | pending |
| `tests/ui/test_ui_slice_live.py` | UI slice | ✅ feasible — browser on the `api.ts` contract drives the full live loop | n/a (contract proof; noted in README) |

### B. Late spikes — prompts authored 07-02, dispatched 2026-07-03 (were silently un-run; caught 07-03)

| Prompt | §10 item | Status |
|---|---|---|
| `dev/prompts/2026-07-02-s10-build-04-inject-tail.md` | #4 (instant mid-turn Inject) | dispatched — review + harvest in 4c |
| `dev/prompts/2026-07-02-s10-build-07-runstrip-tail.md` | #7 (genuine progress signal) | dispatched — review + harvest in 4c |

### C. Research reports — all 5 exist in `dev/notes/research/`; none reviewed or harvested yet

| Report | §10 item | Reviewed (4a) | Harvested (4b) |
|---|---|---|---|
| `attachment-citation-path-materialization-report.md` | #12 | ☐ | ☐ |
| `native-claude-code-coordination-report-2026-07-02.md` | #13 | ☐ | ☐ |
| `claude_code_hook_event_stream_report.md` | #14 | ☐ | ☐ |
| `s10-research-15-rewind-handoff.md` | #15 | ☐ (spike-validated in practice) | ☐ |
| `s10-research-22-subagent-management.md` | #22 | ☐ | ☐ |

(Pre-batch research also on file: mode-control, compaction reference, subagent architecture, CLI
stream/permissions API, electron architecture, plugin ecosystem — already cited by §10 where relevant.)

### D. Code gaps discovered by the spikes — document-only (→ §11 rows in 4b; fixes = later cleanup push)

1. `/clear` transcript orphaning — re-resolve + `register_session_id` after Console `/clear` (`bridge/bridge.py`, `sidecar/main.py`)
2. Usage-limit matcher misses subscription-cap wording ("weekly usage limit") (`sidecar/inbox.py` `classify_error`)
3. Polling scale — batch the ~5 WSL spawns/cycle + adaptive cadence (`sidecar/drivers/bridge.py`)
4. Account split-source + no auth-expiry reader (`sidecar/settings_io.py`; `.claude.json` tier fields unmatched)
5. Real Electron-main sidecar-lifecycle POC (spike modeled it in Python) (`frontend/`)

### E. Contradiction orphans — need USER decisions (Phase 5; detail in `2026-07-02-coverage-audit-orphans.md`)

1. **Identity editing** — §7.5 "read-only in v1" vs DESIGN's edit affordances
2. **Frontend §4.4** — officially adopt park-and-rebuild vs finish-in-place (rewrite §4.4 accordingly)
3. **`createDoc`** — §5.2/§7.16 "dashboard never writes content files" vs createDoc existing/implied

### F. Remaining orphans (Phase 6; same source doc)

- Tier-3 "record a decided-omission" minors · Tier-4 "worth elevating" trio

### G. Scratch docs to archive when their content is fully homed

- `dev/notes/scratch/2026-07-02-coverage-audit-orphans.md` (after Phases 5–6)
- `dev/notes/scratch/2026-07-02-unverified-behavior-candidates.md` (verify in Phase 7)
- this tracker (last — Phase 9)

## Running todo / open decisions

- [ ] 3b: commit Phase 3+3c (working tree also carries the concurrent design session's [ND] triage — one combined commit)
- [ ] 4c: review the two late-spike results when the dispatched agent finishes
- [ ] Phase 5 decisions (§E) — user's calls, not agents'
- [ ] BB8 "Agent Archive" sits in §11.3 #18 with a value-unclear caveat — user may prefer it demoted to §10
- [ ] Phase 9: also re-check the stale `.claude/worktrees/wf_*` clutter noticed 07-03 (unrelated to this workflow; cleanup candidate)
