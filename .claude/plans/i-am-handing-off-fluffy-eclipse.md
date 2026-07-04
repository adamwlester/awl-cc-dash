# Handoff review: loose ends + readiness for the next phase

## Context

This session was handed the export `.claude/cc-exports/claude-2026-07-04-dev-doc-4h.md`. The ask: **clarify the loose ends that handoff noted, then confirm whether I have everything needed to implement the next phase — but do not begin until told explicitly.** This file is a review/readiness brief, not yet an execution plan; the "next phase" I'm confirming readiness for is **Phase 6** of the doc-integration workflow.

### What the handoff session (dev-doc-4h) actually did

It was a pure **documentation-reconciliation** session — no product code touched. It:

1. **Committed housekeeping** — the concurrent design session's execution plan (`8e6e51e`).
2. **Applied Phase 5** (`b2fd3fe`) — settled the 3 doc-vs-doc contradictions the coverage audit flagged, editing `docs/ARCHITECTURE.md` (+ one `CLAUDE.md` row) only, no design files:
   - **① Identity editable** — §7.5 flipped "read-only in v1" → editable (all 5 fields: role · number · name · colour · icon), with the rationale that identity is display-metadata keyed separately from routing; the **name** also registers as the real Claude Code session name via `claude --name` (launch) + `/rename` (mid-run).
   - **② Frontend park-and-rebuild** — §4.4 rewritten: rebuild the renderer fresh from `design/`; freeze scoped to the **visible UI only**, NOT the Electron main-process shell (sidecar lifecycle, window, packaging stay active feasibility work); `api.ts` = preserve-through-rebuild contract.
   - **③ createDoc/delete** — §5.2 gained `POST`/`DELETE /library/document`; the over-absolute "never writes into a content file" (§7.16/§8.5) narrowed to "the *review layer* never writes annotations into content" (those stay in the `.meta.json` sidecar).
3. **Proved the Fast-mode toggle live** (`36c39e7`) — user enabled Fast credits; `Meta+O` opens the panel and `Space` toggles it (OFF→ON→OFF, read-backable). §10 #3 flipped 🧪 needs-spike → ✅ proven; test strengthened.
4. **Fixed the tests/README spike index** (`6973dad`) — added the two tail tests as ❌ INFEASIBLE rows; refreshed the stale Fast-mode row to ✅.

All four commits are pushed; `main` was level with origin at handoff.

---

## The loose ends the handoff noted — clarified (plain language)

**1. The TODO inbox is full of un-triaged notes.** The handoff left `dev/notes/TODO.md`'s `[IN] INBOX` untouched (it's the user's private capture bucket — agents only touch it when pointed there). Since the handoff, the inbox has *grown* to ~9 rough notes (workflow-approval-via-inbox, agent-number auto-populate, move "Compact", card-nav styling, footer-divider removal, tab-nav leading-icon removal, inbox badge alignment, agent-card model alignment) — and one is a half-typed stub ("In the"). **This is a triage loose end, separate from Phase 6.** Two of them (agent-number auto-populate; the old "role · name · number" reorder) touch the identity model Phase 5 just made editable.

**2. Phase 6 is the next phase of the doc-integration workflow.** The workflow tracker (`dev/notes/scratch/2026-07-03-doc-integration-tracker.md`) has 9 phases; 1–5 are done. **Phase 6 = "integrate the remaining coverage-audit orphans into the docs"** — pure documentation, no product code (a locked standing rule of this workflow). The source of truth for what those orphans are is `dev/notes/scratch/2026-07-02-coverage-audit-orphans.md`.

**3. Fast-mode #3 — already closed.** The handoff opened this as a loose end but resolved it in-session (credits enabled → test passed → §10 #3 proven). Nothing pending.

**4. Two minor open decisions parked in the tracker** (not blocking): (a) "Agent Archive" (§11.3 #18) — user may prefer it demoted to §10; (b) Phase 9 cleanup of stale `.claude/worktrees/wf_*` clutter.

**5. [Discovered this session, not from the handoff] There is un-committed, un-pushed work in the tree that isn't the handoff's.** `git status` shows unstaged edits to `CLAUDE.md` (a big trim/optimization pass — this is the BH4 chore), `AGENTS.md` (branch-rule wording sync), `.claude/settings.json`, `.claude/agents/vibe-guide.md`, plus new `DEVLOG.md`/`TODO.md` lines — and one unpushed commit (`367f977`, the design session's final-panel fixes). This looks like a concurrent/other session's in-progress housekeeping. **I have left it entirely alone** and will not commit or build on it without direction, since Phase 6 also edits `DEVLOG.md` and could collide.

---

## What Phase 6 entails (the next phase)

Per the tracker's Phase 6 line and the coverage-audit doc, Phase 6 integrates the **remaining orphans** the earlier phases didn't absorb. These fall into two groups:

### Group A — Tier-3 "record a decided-omission" minors (≈12 one-liners)
Each is small and mostly needs a *recorded decision* in `docs/ARCHITECTURE.md` so it stops being re-litigated. From the coverage-audit doc §"TIER 3":
- Schema versioning / migration of the committed store → §8 body + policy
- Sidecar crash-supervision in the bat-file model → §2/§9 note or Decided-omission
- Git-level merge conflicts on the committed `.awl-cc-dash/` state → §8.7 policy or Decided-omission
- Security on an untrusted network → §2 note or Decided-omission (OS-firewall boundary)
- Sidecar logging / observability → §2/§9 note
- statusLine `context_window` as a live mid-run context source → fold into §10 #9 + reconcile DESIGN
- Forgo the stream-json control API (TUI-scoped "no API" wording) → record trade-off in §6
- Console `/clear` orphaning a resolved transcript path → §8.7 "spots to watch"
- Bypass/Auto launch preconditions → §6.2/§7.11 or fold into §10 #1's POC
- Usage/limits source-boundary confirmation → §7.15 confirmation line
- Response-format preamble option-set + apply/persist model → §7.14 clarification
- Human-name pool / "randomize" source → one §7.5 line or fine-as-backlog

### Group B — Tier-4 "worth elevating" trio (the 3 ⬆ items)
Currently only in `dev/notes/TODO.md`; the audit flags them as worth a home in the guiding docs *if pursued*:
- Rich visual content in Plans/Docs (mermaid/charts/diagrams + visual commenting) → DESIGN
- Authors/authorship view for Plans & Documents → DESIGN
- Subagent creation / management UI → §10 research or DESIGN

### Group C — three still-unhomed Tier-2 "moderate" orphans (verified this session)
The tracker's Phase-6 line names only "Tier-3 + Tier-4 trio," but that line is **incomplete**. I verified each Tier-2 moderate against the current `docs/ARCHITECTURE.md`:
- ✅ **Already homed** (done in the Phase-4 harvest, *not* Phase 6): polling scale ceiling (§10 #17, ◐) and the hook-event-stream push channel (§10 #14, ◐ — decided as "Option C hybrid: hooks-authoritative-when-fresh, screen-polling as watchdog floor"). createDoc was done in Phase 5.
- ❌ **Still MISSING — genuine Phase-6 work:**
  - **Turns "by-tool" breakdown + the "Coordinating" slice** — zero hits in the doc; the sibling *context*-by-category is §10 #9 but the *turns* derivation has no home → new §10 entry beside #9.
  - **Voice dictation / speech-to-text pipeline** — §7.14 names "a voice mic" but no capture→transcribe→insert path and no client-Web-Speech-vs-sidecar decision → one §7.14 line or a §10 entry.
  - **Frontend degraded-mode policy + polling backoff** — §4.3 lists the poll cadences but states no degraded-UI-on-`/health`-fail policy and no backoff → §4.3 body + a §10/DESIGN note.

So the handoff's verbal description ("turns-by-tool, voice-to-text, degraded-mode, schema-versioning") was the *fuller* picture; the tracker line under-states Phase 6 by these three. **Recommend Phase 6 include them** (and fix the tracker line).

### §10 / §11 structure Phase 6 slots into (verified)
- **§10 "Open questions & research queue"** — items #1–25 continuous, five priority subsections; status markers ✅ proven / ◐ partial / 🧪 needs-spike / 🔬 needs-research / ⛔ impossible-today, each with an *Evidence (live|unit)* line. New Phase-6 open-questions get the next numbers (#26+) with a 🔬/🧪 marker. There's a **"Decided omissions (not open questions)"** subsection for recorded non-features.
- **§11 "Build backlog & queue"** — §11.1 ⚠-Today index, §11.2 Storage & lifecycle, §11.3 Feature backlog, §11.4 Spike-surfaced code fixes; items #1–28. Tier-3 "record a decided-omission" items mostly land as body notes / §10 Decided-omissions; anything with a known build path lands as a §11 row.

### Standing rules for Phase 6 (locked, from the tracker — do not re-litigate)
- **No product code.** Code gaps become doc rows; fixes are a later cleanup push.
- **§10 = don't-know-yet · §11 = know-how-queued.** Feature-grouping is deferred to Phase 9 — port into the current structure, don't restructure.
- **No branches; work on `main`.**
- **Tracking = the tracker doc + inline ledger + a DEVLOG entry per repo-changing chunk.**

---

## Readiness assessment

**Do I have what I need to implement Phase 6?** — *Yes, with two things to confirm with the user first (below).* The source material is complete: every Tier-3 and Tier-4 orphan has an explicit "where it should live" target in the coverage-audit doc, the target sections exist in `docs/ARCHITECTURE.md`, and the standing rules are clear.

**Confirmed with the user (2026-07-04):**
1. **The next phase = Phase 6.** (Unambiguous in this workflow's numbered ledger — my earlier "which thread" question was a calibration error, now corrected.)
2. **Scope = the fuller sweep** — Tier-3 minors + Tier-4 trio **+ the 3 verified-unhomed Tier-2 moderates** (turns-by-tool, voice STT, degraded-mode), and fix the tracker's incomplete Phase-6 line.
3. **Run as far as possible without user input.** Continue Phase 6 → **Phase 7** (verify `unverified-behavior-candidates.md` fully integrated; archive both 07-02 scratch docs) → **Phase 8** (final comprehensive integration-verification sweep). **Stop before Phase 9** — it's a large §10/§11 feature-refactor and carries a genuine user decision (whether "Agent Archive" §11.3 #18 demotes to §10); that's the review checkpoint.
4. **Uncommitted tree:** the only collision is `DEVLOG.md` (both append; git can't stage just my lines). The user's other agent will commit its pending work first; I then work on a clean tree and append my log entry on top. I touch none of the other pending files, and never `TODO.md` (private).

**Design-lane guardrail (honor without asking):** two Tier-4 "elevate" items are design-lane (rich visual content in Plans/Docs; Authors/authorship view). Do **not** edit `design/DESIGN.md` for these (a live design agent owns that surface) — record them as `§10`/architecture notes pointing to the design lane instead.

---

## Decisions embedded in the source material — surface, don't silently decide

Phase 6's job is to **home** each orphan (give it a doc entry), not to **resolve** it — so the phase can complete without user input by parking undecided items as explicit `§10` open entries. But several orphans carry a genuine product/policy call. Rather than stamp the audit's suggestion as "decided," record each as an **explicit open question** and collect a consolidated **"decisions for you"** list to present at the Phase-8 handoff.

**Higher-stakes (leave genuinely open for the user):**
1. Security posture on an untrusted network (no-auth `0.0.0.0` bind; audit suggests OS-firewall-as-boundary).
2. Frontend degraded-mode UX when `/health` fails (what the panels show).
3. Voice dictation: client-side Web Speech API vs. sidecar transcription service.
4. Response-format preamble: the option set + per-agent-vs-per-turn persistence.
5. Tier-4 "elevate if pursued" trio: rich visual content in Plans, Authors view, subagent-management UI — pursue or leave parked.

**Lower-stakes (pre-fill the audit's recommendation for confirm/override):**
6. Schema versioning / migration policy for the committed store.
7. Sidecar crash-supervision (manual relaunch vs. auto-restart).
8. Git-merge policy on the committed `.awl-cc-dash/` state.
9. Agent name source (curated pool + randomize vs. user-typed).
10. Turns-by-tool + "Coordinating" derivation (derivable? spike vs. cut).

**Blocks Phase 9 (separate):** "Agent Archive" §11.3 #18 → demote to §10?

## Verification (when Phase 6 is executed)
- Docs-only change → verification is a **read-back + grep**: confirm each Tier-3/Tier-4 target section now carries the decision, no old absolute wording remains, and the tracker ledger + `§10`/`§11` cross-refs stay consistent.
- Update the tracker (`[ ] 6.` → `[✓]`) and append one `DEVLOG.md` entry at the true tail (re-read the bottom first — the concurrent design session appends there too).
- No app run / pytest needed (no runtime surface changes).
