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
        [✓] 3b. committed 40decbf + pushed to origin/main (see Running todo); the earlier "pending" mark was stale.
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
[✓] 9.  Split into the port (done 2026-07-05) + the structural regroup (done 2026-07-09):
        [✓] 9a. Q1–Q11 ported → ARCHITECTURE §10 (annotated-decided) + new §11.5 (buildable graduates #30–#37);
                §11.3 #18 Agent Archive reshaped (Q11); §F1 register all [✓]; Operator-answers marked settled;
                zero inbound TODO.md refs re-verified in the major docs (fixed the §10 #36/#37 regression). (2026-07-05)
        [✓] 9b. STRUCTURAL — executed 2026-07-09 (map in §H below): every ✅-proven §10 item + the #4/#7
                tails relocated into the body / Decided-omissions with inline evidence citations (new body
                subsections §7.18 context-sources + §7.19 Rewind/Handoff); §10 slimmed to 8 genuinely-open /
                parked items; §11 feature-regrouped + renumbered 1–49 (storage set #1–11 unchanged; new items
                added for mode-wiring, bypass gating, identity editing, links fixes, Projects surface, console
                attach, context/statusLine/cost wiring, renderer rebuild); ex-BB scaffolding stripped; ~30
                body cross-refs repointed; stale pointers fixed in tests/README.md + design/DESIGN.md;
                adversarial multi-agent verification pass run; tracker archived.
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

Surfaced 2026-07-04 (Phase-6 prep). **All homed as open §10 entries on 2026-07-04 (Phase 6)** — homing gives each orphan a doc entry; it does **not** decide it. Each stays `[ ]` open until the operator rules; the `→ homed §10 #N` note is *where* it was homed, not a resolution. **All decided 2026-07-05** — the operator ruled the whole Q1–Q11 batch, the coherence pass ran clean (no contradictions; strong convergence on the lineage/provenance/archive substrate), and the decisions are ported into ARCHITECTURE §10 (annotated-decided) + §11.5 (buildable graduates). Every box below is now `[✓]` with its resolution + where-applied.

Higher-stakes — leave genuinely open, user decides:
- [✓] **Security on an untrusted network** — no-auth `0.0.0.0` bind. (Tier-3) → homed §10 #32. — **Decided 2026-07-05 (Q2 → A):** OS firewall is the boundary; travel-mode noted as a cheap future add. Applied: ARCHITECTURE §10 #32.
- [✓] **Frontend degraded-mode UX** — what the poll-driven panels show when `/health` fails. (Tier-2) → homed §10 #28. — **Decided 2026-07-05 (Q3 → A):** freeze + mark-stale + poll-backoff (behavior → §11.5 #34). The *consolidated system-health display* is a separate **design-lane** follow-up (ties §10 #16 ↔ #28). Applied: ARCHITECTURE §10 #28 / §11.5 #34.
- [✓] **Voice dictation** — Web Speech API vs. a sidecar transcription service. (Tier-2) → homed §10 #27. — **Direction decided 2026-07-05 (Q4):** quality-first — spike browser/Electron built-in vs. a Whisper-class local library; better quality beats convenience. Still 🔧 spike-gated. Applied: ARCHITECTURE §10 #27.
- [✓] **Response-format preamble** — the option set + per-agent-vs-per-turn persistence. (Tier-3) → homed §10 #34. — **Decided 2026-07-05 (Q5 → A):** per-agent preset menu for v1. Applied: ARCHITECTURE §10 #34 / §11.5 #32.
- [✓] **Tier-4 "elevate if pursued" trio** — rich visual content · Authors view · subagent create/manage. → homed §10 #36/#37/#22. — **Decided 2026-07-05 (Q10 → mixed):** #36 rich visuals *wanted, elevate to design-lane when ready* (not a v1 gate; laptop-smoothness caveat); #37 Authors *rescoped — display already landed in design; provenance wiring → §11.5 #35*; #22 subagent create/manage *parked* (revisit after hooks/lineage). Applied: ARCHITECTURE §10 #36/#37/#22 / §11.5 #35.

Lower-stakes — pre-fill the audit's recommendation for confirm/override:
- [✓] **Schema versioning / migration** of the committed store. (Tier-3) → homed §10 #29. — **Decided 2026-07-05 (Q1 → A):** stamp `schema_version` now; migration machinery deferred. Applied: ARCHITECTURE §10 #29 / §11.5 #30.
- [✓] **Sidecar crash-supervision** — manual relaunch vs. auto-restart. (Tier-3) → homed §10 #30. — **Decided 2026-07-05 (Q1 → A):** manual relaunch is the v1 model (agents survive in tmux); auto-restart deferred. Applied: ARCHITECTURE §10 #30.
- [✓] **Git-merge policy** on the committed `.awl-cc-dash/` state. (Tier-3) → homed §10 #31. — **Decided 2026-07-05 (Q1 → A):** single-machine, no merge policy. Applied: ARCHITECTURE §10 #31.
- [✓] **Agent name source** — curated pool + randomize vs. user-typed. (Tier-3) → homed §10 #35. — **Decided 2026-07-05 (Q6 → A):** curated pool at `assets/names/agent-names.json` + randomize; user-typed stays. Applied: ARCHITECTURE §10 #35 / §11.5 #33.
- [✓] **Turns-by-tool + "Coordinating" derivation** — confirm derivable vs. cut. (Tier-2) → homed §10 #26. — **Decided 2026-07-05 (Q7):** display parked (total-count suffices); underlying per-turn parsing retained + valued (guard = transcript retention); "Coordinating" attribution stays the unproven piece. Applied: ARCHITECTURE §10 #26.
- [✓] **Sidecar logging / observability** — destination + retention/rotation. (Tier-3) → homed §10 #33. — **Decided 2026-07-05 (Q1 → A):** small size-bounded log file under `sidecar/runtime/`. Applied: ARCHITECTURE §10 #33 / §11.5 #31.

Blocks the Phase-9 restructure (also under Running todo):
- [✓] **"Agent Archive"** (§11.3 #18) → demote to §10? — **Decided 2026-07-05 (Q11 → B, reshaped):** NO demotion — stays a decided §11 build item, reshaped (archive-by-default / roster table / lineage fields reserved / Delete = true delete). This resolved the one hard Phase-9 placement gate. Applied: ARCHITECTURE §11.3 #18.

### G. Scratch docs to archive when their content is fully homed

- [✓] `2026-07-02-coverage-audit-orphans.md` — **archived 2026-07-04 (Phase 7)** → `archive/dev/notes/scratch/` (content homed Phases 5–6; ARCHITECTURE §10 citations repointed to the archive path).
- [✓] `2026-07-02-unverified-behavior-candidates.md` — **archived 2026-07-04 (Phase 7)** → `archive/dev/notes/scratch/` (verified integrated: all 22 candidate items homed or correctly parked; the one still-open item — voice dictation, candidate #16 — is now §10 #27).
- [✓] this tracker — **archived 2026-07-09** (Phase 9b complete) → `archive/dev/notes/scratch/`

## Running todo / open decisions

- [✓] 3b: committed 40decbf (Phase 3+3c + tracker + design [ND] triage), pushed to origin/main.
- [✓] 4b flag: #3 fast-mode RESOLVED — user enabled Fast credits (2026-07-04); re-ran the spike →
      ✅ proven (`Meta+O` opens the Fast panel, `Space` toggles OFF↔ON, read-backable there-and-back).
      §10 #3 → ✅ proven; Decided-omissions note updated; test strengthened from panel-appears to full flip.
- [✓] 4c: both spikes ran INFEASIBLE (2026-07-04); harvested → §10 #4/#7 (⛔ resolved-at-fallback) + Decided-omissions note.
- [✓] Phase 5 decisions (§E) — user decided all 3 (2026-07-04); applied to ARCHITECTURE.md + CLAUDE.md.
- [ ] BB8 "Agent Archive" sits in §11.3 #18 with a value-unclear caveat — user may prefer it demoted to §10
- [ ] Phase 9: also re-check the stale `.claude/worktrees/wf_*` clutter noticed 07-03 (unrelated to this workflow; cleanup candidate)

## Operator decision questions — the Phase-9 prerequisite set (2026-07-04)

**What this is.** The plain-language, big-picture version of every open decision that is *yours* to make so that §10/§11 of `docs/ARCHITECTURE.md` can be refactored into a complete, buildable account of the system (Phase 9). Each numbered question bundles one or more §10/§11 items into a single high-level call; the granular sub-items are named inline so nothing is hidden. This is the **human-readable companion to the §F1 register above** — §F1 stays the durable checkbox ledger and the audit trail of where each item is homed in §10; this section is where the decisions are actually framed to be read and answered. Answering by letter is enough, and **"go with your recommendation" is a complete answer.** A 🔧 marker means the item *also* needs a technical spike — but your *direction* is what's asked here; the spike settles feasibility, you settle intent.

**Scope.** These are the system/architecture decisions in `docs/ARCHITECTURE.md` §10/§11 **only** — not the design lane (`design/DESIGN.md` owns UI/UX calls) and not the private `dev/notes/TODO.md` backlog. Q10 touches two design-lane *features*, but only as a pursue-or-park call, not as design work.

**The one hard gate.** Only **Q11 (Agent Archive placement)** structurally blocks the Phase-9 refactor. The others don't block the mechanical reshuffle — but each question left unruled is a part of the system still unaccounted for, so answering them is what turns the refactored §10/§11 into a genuinely complete build map. You don't have to answer them all at once; the register survives handoffs.

### 1. Backend robustness & operations posture — how hardened is the sidecar for v1? *(bundles §10 #29, #30, #31, #33)*

**The call.** How production-hardened should the behind-the-scenes service (the "sidecar") and the project data it saves be for the first real version? Today it's built for one person on one machine. Four small production-hygiene decisions all flow from one posture choice: **schema stamp (#29)** — write a version number into saved project data now, so a future format change can still read old data? · **crash recovery (#30)** — if the sidecar process dies, is it a manual relaunch (your agents keep running in tmux regardless) or does the app auto-restart it? · **two-machine conflicts (#31)** — if the committed project state is edited from two branches/machines, is there a merge rule, or is single-machine simply assumed? · **backend logging (#33)** — does the sidecar write its own diagnostic log to a file so a crash leaves a trail, or just print to a console nobody's attached to?

- **A — Pragmatic single-machine v1.** Take the cheap protections, defer the expensive machinery: stamp `schema_version` now (near-free insurance), keep manual sidecar relaunch, assume single-machine with no merge policy (matches the cross-machine caveat you already accepted, §9.9), and write a small size-bounded log file under the backend's runtime folder.
- **B — Hardened now.** Add auto-restart supervision, a real cross-machine merge/reconcile story, and rotating logs up front. Meaningfully more work; worth it only if multi-machine or unattended operation is coming soon.
- **C — Minimal / do nothing.** Accept that a format change may break old data, a crash needs a manual restart with no log trail, and so on.

**My recommendation: A** — and you can override any single item (e.g. "A but skip the schema stamp"). It locks in the two things that are annoying to retrofit later (the version stamp and a log file) and defers the two that are real engineering you don't need yet (auto-restart, merge policy).

### 2. Security on an untrusted network *(§10 #32)*

**The call.** The dashboard's control API listens on the network with no login. At home on your own machine that's a deliberate, accepted choice. The open question is the *travelling laptop*: on café or office Wi-Fi, that same API — which can start, stop, and steer agents — is reachable by anyone else on the network.

- **A — OS firewall is the boundary; document and accept.** Rely on Windows Firewall to block inbound connections and record it as the deliberate posture. Zero new code; genuinely correct for a personal laptop that's firewalled by default.
- **B — Add a "travel mode."** A toggle that binds the API to localhost-only (or requires a token) when you're on untrusted networks. Modest work; a real safety net if you'll actually work from public Wi-Fi.
- **C — Always require auth.** A token or login on every request, everywhere. Most secure, most friction for a single-user tool.

**My recommendation: A now, with B noted as a cheap future add** if you find yourself working on public networks. The firewall really is the effective boundary on a default Windows laptop, so A is honest rather than lazy.

### 3. What the UI does when the backend drops — degraded mode *(§10 #28)*

**The call.** The dashboard polls the sidecar for its live readouts. Today, if the backend becomes unreachable, you get a single "Sidecar offline" chip and the app keeps polling at full speed. The open question is how the panels should *behave* when the backend is down — and whether polling should back off instead of hammering a dead endpoint.

- **A — Freeze + mark stale, and back off.** Panels keep showing their last-known values, visibly marked as stale, while polling slows to a gentle retry until the backend returns. Calm, informative, no pointless load.
- **B — Banner + hide live data.** Replace the live readouts with a prominent "disconnected" banner so nothing potentially-stale is shown at all.
- **C — Minimal.** Keep today's single offline chip and the unchanged poll rate.

**My recommendation: A.** Last-known-but-marked-stale is the least jarring, and the backoff avoids beating on a dead endpoint — it's the standard, well-understood pattern for this.

### 4. Voice dictation — how speech becomes text *(§10 #27)* 🔧

**The call.** The Compose / Plans / Documents editors show a mic icon for dictation, but nothing is wired behind it. The decision is *how* speech gets turned into text.

- **A — The browser's built-in speech recognition.** Free, no backend, works immediately, decent quality for short dictation. Privacy/offline behavior depends on the browser engine (worth a quick check).
- **B — A backend transcription service.** Higher quality and full control, but real work to build and run, with its own privacy/offline story.
- **C — Defer.** Leave the mic as a visual placeholder until later.

**My recommendation: A for v1**, revisiting B only if the built-in quality proves insufficient. (🔧 a small spike should confirm the browser speech API behaves inside the Electron shell before we commit.)

### 5. Response-format presets *(§10 #34)*

**The call.** You want a control that tells an agent how to shape its replies (for example your preferred TL;DR-table-with-emoji-status format). The open call is the *menu of options* and the *scope* — does the choice stick to an agent, or is it set per message?

- **A — A small preset menu, set per-agent.** A short list of formats (including your TL;DR-table + emoji style) chosen once per agent and applied to all its replies.
- **B — Set per message.** The format is picked each time you send — finer control, more repetition.
- **C — Single freeform field, no presets.** Just a text box where you type formatting instructions.

**My recommendation: A, per-agent**, with a per-message override as a later nicety. Per-agent matches how you'd actually want a given agent to behave consistently.

### 6. Where "randomize agent name" draws from *(§10 #35)*

**The call.** The Create panel has a shuffle-a-name affordance, but there's no defined pool for it to draw from. Low stakes.

- **A — A curated human-name pool + randomize.** A built-in list of friendly names to shuffle through; you can still type your own.
- **B — User-typed only.** Drop the randomize affordance; names are always typed.

**My recommendation: A** — a small curated pool is cheap and makes spinning up throwaway agents pleasant, and typing your own stays available.

### 7. How detailed the "turns by tool" breakdown should be *(§10 #26)* 🔧

**The call.** The Agent → Details view is meant to break an agent's activity into a per-tool split (reading, editing, running commands, web, subagents, plus a "Coordinating" slice for cross-agent chatter). It's not yet known how much of that is actually derivable from the transcript data. The decision is how ambitious to aim.

- **A — Spike first, then show whatever's reliably derivable, including "Coordinating" if possible.** Let a quick technical test bound what's real, then display exactly that.
- **B — Commit to the full breakdown now.** Design for every bucket up front, at the risk that some (especially "Coordinating") can't be sourced.
- **C — Cut it to the total.** Just show total turn count and drop the per-tool split.

**My recommendation: A** — decide the *ambition* (a rich, honest breakdown) and let the spike settle what's achievable; ship only the buckets that prove trustworthy.

### 8. Console rendering fidelity *(§10 #5)*

**The call.** The engine side of mirroring a live terminal into the dashboard is already proven. What's left is a pure frontend build choice: how faithfully to render it — real terminal colours, spinners, and box-drawing, or a simpler approximation. This one depends most on how central the Console is to how you'll actually work.

- **A — Full terminal renderer (xterm-class).** Faithful colours, spinners, box-drawing — looks exactly like the real terminal. More frontend weight and work.
- **B — Styled-text approximation.** Clean, readable, captures most of the value without embedding a full terminal engine; upgradeable to A later.
- **C — Plain-text mirror.** ANSI stripped entirely; simplest, least faithful.

**My best guess: B for v1**, with A as a later upgrade — *unless* you expect to live in the Console a lot, in which case go straight to A. Tell me how central the Console is and I'll firm this up.

### 9. Three "is it worth building?" items *(§10 #23, #24, #25)*

**The call.** Three capabilities were carried over from an old backlog with their *value* never validated. Each is a keep-or-park decision: **Docs in agent context (#23)** — automatically feed agents the *relevant, current* documentation for what they're working on, instead of you pasting doc references into prompts · **AI-touched file tracking (#24)** — keep an index of what the AI has changed (a per-folder `index.md`, a central ledger, or derived from git) · **Special-asset sourcing check (#25)** — confirm skills / agents / hooks / plugins are pulled from the ideal source per type.

- **A — Lightly scope #23, park #24 and #25.** "Relevant docs in context" has obvious leverage and is worth a small research pass; the other two have unclear payoff for their maintenance cost — park them as backlog.
- **B — Research all three.** Treat all as worth a proper look now.
- **C — Park all three.** None are core; revisit after v1.

**My recommendation: A.** #23 is the one with real leverage; #24 and #25 read as nice-to-haves you can defer without loss.

### 10. Three "elevate or park" features *(§10 #36, #37, #22)*

**The call.** Three features are recurring asks but not core; the question is simply whether to pursue each now or leave parked. Two are design-lane (they'd route to the design agent, not be built here); one is system-lane and needs a spike. **Rich visual content in Plans/Docs (#36, design-lane)** — diagrams / charts (e.g. mermaid) with visual commenting · **Authors / authorship view (#37, design-lane)** — a view surfacing who-wrote-what (the provenance data already exists) · **Subagent create / manage from the dashboard (#22, system-lane 🔧)** — go beyond *observing* subagents to creating, steering, and stopping them.

- **A — Park all three for v1, revisit after the core ships.** None are load-bearing for the core dashboard.
- **B — Pursue subagent-management (#22) only.** It's the most system-relevant; the two design-lane items wait for the design phase.
- **C — Pursue all three now.**

**My recommendation: A**, leaning **B** if subagent orchestration is central to how you plan to drive the fleet. The two design-lane items are natural fits for the dedicated design-review phase we discussed.

### 11. ★ Agent Archive placement — the one that gates Phase 9 *(§11.3 #18)*

**The call.** "Agent Archive" is a proposed feature — a browsable database of past agents with a short summary of each one's work and timestamps. It currently sits in the *build* backlog (§11, "decided, buildable"), but you've flagged that its *value* is unclear. Because Phase 9 refactors §10 (open questions) and §11 (decided work) as two clean buckets, this item has to be assigned to the right bucket before the refactor can run — which is why it's the single hard gate.

- **A — Demote to §10 as an open question.** It moves to the "not-yet-decided, value-unclear" bucket where it honestly belongs, and stops implying it's approved to build.
- **B — Keep in §11 as a decided build item.** Only if you *do* want it built — then it stays queued.
- **C — Drop it entirely.** Remove it as a feature idea.

**My recommendation: A** — it matches your own "value still unclear" note, keeps §11 to genuinely-decided work, and unblocks the refactor cleanly. Answering just this one lets Phase 9 proceed; the other ten make the refactored map complete.

## Operator answers — SETTLED 2026-07-05 (coherence pass clean; ported)

> **Status: RESOLVED 2026-07-05 — all answers ported.** The operator completed the Q1–Q11 block and signalled "push it all through." The **coherence pass ran** over the whole set: verdict **clean** — no contradictions, and the answers converge (git-identity attribution Q9 #24, the Agent-Archive lineage fields Q11, and the HIGH-priority lineage / hook-ingestion note all point at one substrate). Two threads were flagged and handled: (1) Q3's *display* of system-health is one question with §10 #16 + #28 → routed to the **design lane**, only the *behavior* ported here; (2) **transcript retention** (§8.6 ⚠ Today — the 30-day default is live now) is load-bearing under Q7 / Q9 / Q11 and flagged **URGENT** independent of this workflow. All 11 answers are now ported into `docs/ARCHITECTURE.md` §10 (annotated-decided) + §11.5 (buildable graduates #30–#37); every §F1 box is `[✓]`. The answers below are kept **as the settled record** (no longer tentative).

- **Q1 — backend robustness posture → A** *(tentative)* — pragmatic single-machine v1 (schema stamp now · manual sidecar relaunch · single-machine no-merge · bounded log file).
- **Q2 — security on untrusted network → A** *(tentative)* — OS firewall is the boundary; document + accept.
- **Q3 — degraded-mode UX → A** *(tentative; IN DISCUSSION)* — operator accepts A (freeze + mark-stale + backoff) in principle, but the *display* of this state is not yet resolved and gates the answer's completeness. Findings (2026-07-04): the `connector-health-badge` is Settings/connector-scoped with 4 connector-auth states (Connected / OAuth ✓ / Parked / OAuth-expired), **not** an app-wide backend-health signal; problem-states are currently spread across **three surfaces** (connector badges in Settings · System Error/Warning Inbox cards, §10 #16 / §7.8 · the frontend "Sidecar offline" chip, §4.3). **Attached requirement (operator intent):** a consolidated, always-visible system-health indicator in the app chrome that carries sidecar-offline + degraded + the other problem-states, with a broadened state vocabulary (add down + stale/degraded) reconciled with §10 #16. → **design-lane follow-up (DESIGN.md + six-file propagation; not edited in this workflow) + explicit coherence-review item** (Q3 display ↔ §10 #16 ↔ §10 #28 are one underlying question). Operator display-direction sketch (2026-07-05, recorded broad for the design agents): **the footer is the leading candidate surface**; it sits nearly empty today, and stretching status across it keeps the title bar free for actions, which the operator expects to multiply (the clock is expendable; the WSL2/tmux chips should either become live status or be absorbed). Interaction sketch: a consolidated health badge plus a small set of always-visible status items with popover / pop-up-from-the-footer drill-ins (e.g. an error-count badge popover), so MCP-server or shared-resource trouble is inspectable without a trip into Settings; a sidecar-log tail view is a candidate drill-in (pairs with Q1's bounded log file). Operator caveats: the UI is "badged out," so prefer smarter signaling over yet more badges where possible; and the prerequisite is a consolidated list of what deserves status coverage (drafted in-chat 2026-07-05; travels with the design-lane item). Reconcile with the operator's separately-captured title-bar Connected-chip upgrade note (shared health badge with connectivity-state variants) when the design-lane item is picked up.
- **Q4 — voice dictation → quality-first spike** *(tentative)* — the operator wants dictation to be genuinely good and finds OS-level dictation mediocre. Direction: the spike compares the browser/Electron built-in speech path against a high-quality library (Whisper-class local transcription); if the built-in is close, it wins on simplicity, but a meaningfully better library is preferred over convenience.
- **Q5 — response-format presets → A** *(tentative)* — basic per-agent preset menu for v1; nothing fancier for now.
- **Q6 — random agent names → A** *(tentative)* — curated pool + shuffle. Storage decided in-conversation: a JSON file in `assets/` (`assets/names/agent-names.json`, flat array of strings; optional theme grouping later). The operator will have a separate agent generate the pool.
- **Q7 — turns-by-tool breakdown → deprioritized / parked** *(tentative)* — no spike now; total turn count suffices meanwhile. Operator drift note: at pickup, re-frame the bucket list against the planned reduction of feed block/filter types (the operator believes some listed blocks are being trimmed or never existed), so the current bucket vocabulary is not settled. Amendment (same day): the operator values the underlying capability (per-turn tool parsing) more than the display. Noted for the record: the raw per-turn tool data already lives in the JSONL transcripts and the sidecar already parses tool events for the feed, so nothing is lost while this is parked; transcript retention (see priorities note below) is the guard, and the only genuinely unproven piece remains the "Coordinating" attribution.
- **Q8 — console fidelity → A, full terminal renderer, wanted ASAP** *(tentative)* — the operator has seen the 2026-07-05 live-streaming spike output (ttyd + xterm.js harness; DEVLOG 06:53) and calls it decisively better; xterm-class fidelity is the target, priority high.
- **Q11 — Agent Archive → B, reshaped** *(tentative)* — stays a decided build item; the operator states the system is not useful without it. Shape from the operator: every agent is archived by default (retire = deep-freeze), as a roster/data-table of per-agent records with distinct IDs (or one file per agent instantiation — open); records are light except transcripts; occasional purge acceptable; **Delete stays a true delete**. The schema should reserve lineage fields (parent / fork / handoff) — a separate operator-side agent is exploring lineage tracking and graphical display. Q11 was the Phase-9 gate, so the refactor is unblocked once this survives the coherence pass.
- **Q9 — worth-building trio → modified A** *(tentative)* — **#23 docs-in-agent-context: yes, scope it light.** Direction: a curated docs home agents are pointed at (the Library), plus per-agent doc attachment at launch; automatic relevance-retrieval stays future. Operator interface sketch (2026-07-05, deliberately kept broad for the design agents to develop): **the Library is the obvious hub**, reusing the existing nav-rail lens pattern from the review panels but organized by task/project/subproject instead of by section/agent; possibly the Outline tab going icon-based to free a tab slot. **#24 AI-touched tracking: NOT parked — re-scoped and elevated.** Attribution via per-agent git identity: each agent commits under its own author name + synthetic per-agent email, so "what did AI touch" becomes a git query with no maintained ledger; the operator wants this pursued as a priority together with agent commit tracking, and it feeds the lineage work. Amendment (same day): the operator ALSO wants the per-folder index files pursued (he had begun setting these up himself and values them); git identity is the attribution backbone and the index files ride on top of it, with the hand-maintained-inventory drift risk flagged and accepted. **#25 sourcing check: yes, but deferred.** The operator confirms the current setup is suboptimal (ad-hoc, duplicate AGENTS.md files) and the audit is genuinely needed, but current churn makes now the wrong moment; fold into the hooks setup pass.
- **Q10 — elevate-or-park trio → mixed** *(tentative)* — **#36 rich visuals: wanted, elevate when the design lane is ready for it** (not a v1 gate; operator caveat: must stay smooth on a modest laptop). **#22 subagent create/manage: park** — the operator accepts the parent-decides model and notes no scaffolding exists yet; revisit after hooks/lineage land. Operator sketch for the eventual feature (2026-07-05): a Compose-workspace "add agents" affordance (a button or dropdown, plausibly via the existing template-block machinery) that drops a generic fan-out instruction block into the prompt with placeholders for agent count and timing; custom per-fan-out instructions ride in the same block. **#37: rescoped, no decision needed** — the Authors-lens display already landed in the design system (the [ND] design run; see DESIGN.md's review-panel section), so remaining scope is system-side provenance wiring only.
- *Operator priorities voiced in the same pass (2026-07-05): lifecycle-hook ingestion and the lineage/agent-archive substrate are HIGH priority (the stated pain: agent origins, spawns, handoffs, and timestamps are untraceable today); transcript retention is an URGENT action item — the 30-day `cleanupPeriodDays` default is live right now (ARCHITECTURE §8.6 marks it ⚠ Today; the §11.4 "Pin transcript retention" build item covers the per-agent side, and user-level settings need it too); transcripts are referenced in place, never copied.*
- *Process note from the operator (2026-07-05): several of these summaries carried too little context to answer from — write decision questions so they stand alone for someone without the source docs open.*


## H. Phase-9b old→new numbering map (2026-07-09)

The lossless-port record for the Phase-9b structural refactor of `docs/ARCHITECTURE.md` §10/§11. Every pre-refactor item is accounted for below; "body" = relocated into the settled body with its evidence citation.

### §10 old → new

| Old §10 | Fate |
|---|---|
| #1 mid-run permission mode | body §6.2 + §7.11; build §11 #12 |
| #2 thinking toggle | body §6.2; build §11 #12 |
| #3 fast toggle | body §6.2; build §11 #12 |
| #4 mid-turn Inject | §10 Decided omissions; final model stated in §7.3 |
| #5 console fidelity/transport | body §7.13 + §4.3; build §11 #29 |
| #6 plan/decision hooks | body §7.4 + §7.16; build §11 #22 |
| #7 run-strip % | §10 Decided omissions; final model stated in §7.10 |
| #8 subagent pending-vs-active | body §7.17; build §11 #21 |
| #9 context breakdown/compact | body §7.18 (new); build §11 #30 |
| #10 one-click launch | body §2 + §4.1; build §11 #20 |
| #11 per-agent cost | body §7.15; build §11 #32 |
| #12 attachment/citation paths | **§10 #1** (with in-build decision ladder) |
| #13 native coordination primitives | **§10 #2** (absorbs old §11 #20 agent-teams messaging) |
| #14 hook event stream | body §7.4; build §11 #21 |
| #15 rewind/handoff | body §7.19 (new); build §11 #15 |
| #16 system fault harvest | body §7.2; build §11 #27 |
| #17 polling scale ceiling | body §6.2 ⚠Today(scale); build §11 #34 |
| #18 statusLine context | body §7.18 (new); build §11 #31 |
| #19 /clear orphaning | body §7.13 bullet; build §11 #35 |
| #20 bypass/auto preconditions | body §7.11; build §11 #13 |
| #21 usage/limits sources | body §7.15; build §11 #33 |
| #22 subagent create/manage | **§10 #3** (parked) |
| #23 docs in agent context | **§10 #6** (auto layer); v1 build §11 #44 |
| #24 AI-touched tracking | build §11 #19 (decision carried in the item) |
| #25 special-asset sourcing | **§10 #7** (decided-deferred) |
| #26 turns by-tool | **§10 #5** (parked) |
| #27 voice dictation | **§10 #4** (quality spike) |
| #28 degraded mode + backoff | body §4.3; build §11 #38 (display → design lane) |
| #29 schema versioning | body §8.7; build §11 #42 |
| #30 crash supervision | body §2 (recorded posture) |
| #31 git-merge policy | body §8.7 (recorded posture) |
| #32 untrusted-network security | body §2 (recorded posture) |
| #33 sidecar logging | body §2; build §11 #43 |
| #34 response-format preamble | body §7.14; build §11 #39 |
| #35 agent name pool | body §7.5; build §11 #40 |
| #36 rich visuals | **§10 #8** (design-lane pointer) |
| #37 authors view | build §11 #41 |

### §11 old → new

| Old §11 | New |
|---|---|
| #1–#11 storage set | #1–#11 (unchanged; ex-BB15–BB25 markers stripped) |
| #12 load past agents | #17 |
| #13 plans action loop | #22 |
| #14 queue awareness | #24 |
| #15 git automation | #47 |
| #16 change-log watcher | #48 |
| #17 system-check agent | #49 |
| #18 agent archive | #18 (unchanged) |
| #19 handoff artifacts | #16 |
| #20 native agent-teams messaging | folded into §10 #2 |
| #21 rewind/fork | #15 |
| #22 hook lifecycle ingestion | #21 |
| #23 /clear re-resolve | #35 |
| #24 usage-cap matcher | folded into #27 (system-fault cards) |
| #25 polling rework | #34 |
| #26 account split-source reader | #33 |
| #27 Electron-main lifecycle POC | #20 |
| #28 Task→Agent parser audit | #36 |
| #29 import external context | #28 |
| #30 schema stamp | #42 |
| #31 sidecar log | #43 |
| #32 response presets | #39 |
| #33 name pool | #40 |
| #34 degraded mode + backoff | #38 |
| #35 authors wiring | #41 |
| #36 docs-in-context light | #44 |
| #37 per-agent git identity | #19 |
| #38 prompt/UI-text library | #45 |
| #39 per-turn settings+summary | #46 |
| #40 workflow approval via Inbox | #23 |
| — (new) | #12 mode/thinking/fast wiring · #13 bypass/auto gating · #14 identity editing + name registration · #25 links model fixes · #26 Projects surface (system) · #29 console streaming attach + xterm · #30 context breakdown · #31 per-turn statusLine · #32 per-agent cost · #37 renderer rebuild |
