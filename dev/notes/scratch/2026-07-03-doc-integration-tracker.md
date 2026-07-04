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
[✓] 6.  Integrated remaining orphans → docs/ARCHITECTURE.md §10 #26–#37 (12 entries: 3 Tier-2 moderates,
        7 Tier-3 minors incl. newly-surfaced sidecar-logging, 2 Tier-4 design-lane) + inline body pointers
        to the new entries (§2 → #30/#32/#33 · §4.3 → #28 · §7.5 → #35 · §7.14 → #27/#34 · §8.7 → #29/#31),
        plus a §6.2 stream-json-control-API trade-off note (→ existing #1/#2/#3, not a new entry) and a §7.11
        native-permission-hooks deferred-path note (candidates #5); §8.7 heading Two→Three spots. All
        homed-as-OPEN, none decided; §F1 annotated with homing pointers (2026-07-04). Design-lane items
        (#36/#37) recorded as §10 pointers, DESIGN.md untouched.
[✓] 7.  Verified unverified-behavior-candidates.md integrated (22 items homed/parked; voice #16 → §10 #27);
        archived BOTH 07-02 scratch docs → archive/dev/notes/scratch/ (git mv, 2026-07-04); repointed the
        ARCHITECTURE §10 + tracker §E citations to the archive path.
[✓] 8.  FINAL integration-verification sweep DONE (2026-07-04) — 4 parallel Sonnet verifiers vs the full
        trail. Verdict: PASS. Cross-refs 23/23 resolve; archived-source coverage confirms NOTHING lost by
        archiving (all Tier-1–4 orphans + all 22 candidate items homed); §F1↔§10 register consistent; zero
        new ⚠-Today markers. Fixed on the spot: #26 Decision-pending field; §8.7 heading Two→Three; §7.11
        permission-hooks deferred note; §6.2 ledger wording. Accepted LOW: link-drawer wiring (candidate
        #13) subsumed by the §4.4 renderer-rebuild scope. Could NOT machine-verify: prose quality/tone.
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

### E. Contradiction orphans — need USER decisions (Phase 5; detail in `archive/dev/notes/scratch/2026-07-02-coverage-audit-orphans.md`, archived Phase 7)

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

- **Scope (corrected 2026-07-04):** Tier-3 "record a decided-omission" minors · Tier-4 "worth elevating" trio · **+ 3 Tier-2 moderates verified still-unhomed** — turns-by-tool/"Coordinating" breakdown · voice-dictation STT pipeline · frontend degraded-mode + polling-backoff. The old one-line scope undercounted the phase; polling-ceiling (§10 #17) and hook-event-stream (§10 #14) are already homed, and createDoc was Phase 5.

### F1. Decisions needing the user's call — the durable register (keep current across handoffs)

> **Handoff rule — do not drop.** This is where product/policy decisions this workflow surfaces live so they survive session boundaries. Every subsequent session MUST (a) add to and edit this list as orphans get homed and new decisions appear, and (b) **check each open decision WITH the user before treating it as settled** — never silently adopt the audit's suggested resolution as "decided." Homing an orphan as an explicit §10 open-question is an agent's job; *deciding* it is the user's. Mark each `[ ]` open / `[✓]` decided (with date + where applied), mirroring §E.

Surfaced 2026-07-04 (Phase-6 prep). **All homed as open §10 entries on 2026-07-04 (Phase 6)** — homing gives each orphan a doc entry; it does **not** decide it. Each stays `[ ]` open until the operator rules; the `→ homed §10 #N` note is *where* it was homed, not a resolution.

Higher-stakes — leave genuinely open, user decides:
- [ ] **Security on an untrusted network** — no-auth `0.0.0.0` bind; audit suggests OS-firewall-as-boundary. (Tier-3) → homed §10 #32.
- [ ] **Frontend degraded-mode UX** — what the poll-driven panels show when `/health` fails. (Tier-2) → homed §10 #28.
- [ ] **Voice dictation** — client-side Web Speech API vs. a sidecar transcription service. (Tier-2) → homed §10 #27.
- [ ] **Response-format preamble** — the option set + per-agent-vs-per-turn persistence. (Tier-3) → homed §10 #34.
- [ ] **Tier-4 "elevate if pursued" trio** — rich visual content in Plans/Docs · Authors/authorship view · subagent create/manage UI: pursue (→ DESIGN / §10) or leave parked. Design-lane items route through the design agent, not edited here. → homed §10 #36 (rich visual) + #37 (Authors view); subagent create/manage was already §10 #22.

Lower-stakes — pre-fill the audit's recommendation for confirm/override:
- [ ] **Schema versioning / migration** of the committed store. (Tier-3) → homed §10 #29.
- [ ] **Sidecar crash-supervision** — manual relaunch (agents survive in tmux) vs. auto-restart. (Tier-3) → homed §10 #30.
- [ ] **Git-merge policy** on the committed `.awl-cc-dash/` state. (Tier-3) → homed §10 #31.
- [ ] **Agent name source** — curated pool + randomize vs. user-typed. (Tier-3) → homed §10 #35.
- [ ] **Turns-by-tool + "Coordinating" derivation** — confirm derivable (spike) vs. cut the feature. (Tier-2) → homed §10 #26.
- [ ] **Sidecar logging / observability** — log destination + retention/rotation (a file under `sidecar/runtime/` vs. stdout-only). (Tier-3; newly surfaced 2026-07-04 during Phase-6 homing) → homed §10 #33.

Blocks the Phase-9 restructure (also under Running todo):
- [ ] **"Agent Archive"** (§11.3 #18) → demote to §10? *(Not a coverage-audit orphan — a §11 placement call; stays in §11.3 until the operator rules, then handled in the Phase-9 restructure.)*

### G. Scratch docs to archive when their content is fully homed

- [✓] `2026-07-02-coverage-audit-orphans.md` — **archived 2026-07-04 (Phase 7)** → `archive/dev/notes/scratch/` (content homed Phases 5–6; ARCHITECTURE §10 citations repointed to the archive path).
- [✓] `2026-07-02-unverified-behavior-candidates.md` — **archived 2026-07-04 (Phase 7)** → `archive/dev/notes/scratch/` (verified integrated: all 22 candidate items homed or correctly parked; the one still-open item — voice dictation, candidate #16 — is now §10 #27).
- [ ] this tracker (last — Phase 9)

## Running todo / open decisions

- [✓] 3b: committed 40decbf (Phase 3+3c + tracker + design [ND] triage), pushed to origin/main.
- [✓] 4b flag: #3 fast-mode RESOLVED — user enabled Fast credits (2026-07-04); re-ran the spike →
      ✅ proven (`Meta+O` opens the Fast panel, `Space` toggles OFF↔ON, read-backable there-and-back).
      §10 #3 → ✅ proven; Decided-omissions note updated; test strengthened from panel-appears to full flip.
- [✓] 4c: both spikes ran INFEASIBLE (2026-07-04); harvested → §10 #4/#7 (⛔ resolved-at-fallback) + Decided-omissions note.
- [✓] Phase 5 decisions (§E) — user decided all 3 (2026-07-04); applied to ARCHITECTURE.md + CLAUDE.md.
- [ ] BB8 "Agent Archive" sits in §11.3 #18 with a value-unclear caveat — user may prefer it demoted to §10
- [ ] Phase 9: also re-check the stale `.claude/worktrees/wf_*` clutter noticed 07-03 (unrelated to this workflow; cleanup candidate)
