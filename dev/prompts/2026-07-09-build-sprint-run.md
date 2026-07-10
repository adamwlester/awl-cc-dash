# Build-sprint run — full-autonomy implementation prompt (2026-07-09)

> **What this is:** the operator-issued prompt for THE build sprint — the run that takes the AWL Multi-Agent Dashboard from refactored spec to a full working proof of concept, backend and frontend. Target: **Fable 5, ultracode**, launched **unattended** (start the session in bypass-permissions / accept-all mode so no permission dialog can stall the run — the operator will not be available to approve anything). This document is also the **operator's express, in-repo permission grant** for the git license described inside — it satisfies CLAUDE.md's "never branch without express permission" rule for this run.
>
> Give the agent the body below verbatim (paste it, or point the agent at this file and say "execute this prompt").

---

ultracode

THE BUILD SPRINT — full-autonomy run. Tonight you build the AWL Multi-Agent Dashboard to the best and most complete working version you can produce: backend and frontend, end to end. You are the implementing agent. The reins are off: you have more license than any prior session in this repo — use it. Work autonomously from start to finish, commit and push continuously, and leave a working system at every stopping point.

## Mission & license

- **Goal: the complete §11 queue** in `docs/ARCHITECTURE.md`, plus §10 #1 resolved via its decision ladder — the full intended product, not a slice. The build order below is a *priority order* so that an incomplete night still lands a working system; it is not a scope limit. Push as far down the queue as the night allows.
- **Full autonomy — never pause for the operator.** No approval requests, no check-ins, no "should I…" questions. Every decision inside this repo is yours to make. When the docs answer it, follow them; when they don't, choose the option most consistent with the doc's recorded decisions, mark it "⚠ assumed" in the DEVLOG, and keep moving. Nothing may block the run waiting on a human.
- **Full git license (operator-granted, this run).** Create branches, worktrees, and whatever topology serves the work — parallel implementation lanes in worktrees are explicitly encouraged where they help. The standing no-branch rule in CLAUDE.md is suspended for this run by this grant. Two obligations come with it: commit and push to `main` continuously as work integrates (never leave `main` broken at a commit boundary), and before the run ends, merge everything back to `main`, delete the side branches, and push — no work stranded off-main, no branch litter left behind.
- **Resources are unconstrained.** Token use is not a concern — spend whatever produces the most correct, most complete result. Fan out Workflow subagents freely for parallel implementation, heavy reading, and adversarial verification. The ONE resource to manage is your own context window, only so you can finish: delegate bulk reading and per-module implementation to subagents, keep your main loop for integration decisions, and if your context tightens, write a full handoff state (what's done, what's in flight, exact next actions — to `dev/notes/`) and continue in a fresh session rather than degrading. Do not die mid-run with unrecorded state.

## Read first, in this order

1. `CLAUDE.md` (repo root) — the standing rules. They bind except where this prompt explicitly overrides them (the git license above, the no-pausing rule).
2. `docs/ARCHITECTURE.md` — read it END TO END. The body (§1–§9) is the contract you build to; **§11 is your work queue** (each row points at the body section that owns the detail — read that section before building the item); §10 holds the few genuinely-open items, each with a decided fallback; §12 explains that the tests are executable specs — read the matching `test_*_unit.py` docstring before touching a module.
3. `design/DESIGN.md` + the `design/` mockup system — before any renderer work.
4. `tests/README.md` — suite layout, tiers, markers.

## Clarifications for this run

- **The renderer freeze is LIFTED.** CLAUDE.md parks the React renderer "until the build sprint" — this is the build sprint. Rebuild the renderer FRESH from the design system per ARCHITECTURE §4.4 / §11 #37: `design/mockup.html` is the visual authority, `tokens.css` the values, `behavior.js` the interaction logic, DESIGN.md the intent. Carry `frontend/src/renderer/api.ts` through as the preserved frontend↔sidecar contract (extend it as new endpoints land; don't discard it).
- **Do not redesign the design system.** The renderer *consumes* `design/` — you don't restyle or restructure the mockups themselves. If you find a genuine defect in `design/`, note it in the DEVLOG and work around it; a trivial obvious bug (a typo-level error) you may fix with the five-file propagation rules in CLAUDE.md.
- **Bridge sessions are always tab-less** (`show=False`); a terminal opens only on explicit human request. Never break this in tests, fixtures, or the sidecar. (Correctness, not a rein.)
- **DEVLOG.md discipline holds** — append an entry per meaningful increment (format in its header; rotate per its rules past ~700 lines). This is the project's memory; an unlogged change doesn't exist to the next session.
- **Transient artifacts go in `.scratch/` only** (screenshots, scratch HTML, debug dumps, ad-hoc logs).
- **Hands off:** `transcripts/` (personal exports), `dev/notes/TODO.md` (operator-private), `archive/` except DEVLOG rotation.
- **As each §11 item lands:** clear its ⚠ Today markers in the ARCHITECTURE body, update the §11.1 index row, and remove the queue row (DEVLOG keeps history). If a statement in CLAUDE.md / ARCHITECTURE / DESIGN goes stale from your change, fix it in the same pass. If building reveals a genuine open question, demote the item to §10 with what you learned — never silently deviate from the doc.

## Build order (priority sequence — each stage leaves a working system; the goal is ALL of it)

0. **URGENT — §11 #5 transcript retention** (`cleanupPeriodDays: 3650` in the materialized per-agent settings). Do this before anything else; agent history is being auto-deleted at 30 days TODAY.
1. **Storage & persistence set — §11 #1–#11 in numeric order** (dependency-ordered: rename → canonical root → state store → transcript persist → sidecars → plansDirectory → cold-restore → WSL rename → dogfood → delete-extension). This makes every Persist row in §8.3 real and restart-survivable.
2. **HIGH-priority backend spine** — #21 hook lifecycle ingestion + run-state arbiter (VERIFY ordering/dedup under concurrent load live — test, don't assume; `permission_mode` is event-specific, `Notification` lacks it), #12 mode/thinking/fast wiring (the proven `keys()` levers — exact sequences in §6.2), #22 plans approve→resume (`keys()` Enter), #26 Projects surface, #25 links fixes, #27 System-fault cards (confirm the reactive auth-expiry signal live; if none, record the boundary honestly), #13, #14, #35, #36.
3. **Readouts** — #29 console streaming attach (ttyd/WebSocket, `window-size manual` pinning), #30–#32 context/statusLine/cost, #33, #34 polling rework (then re-measure the ceiling and document it).
4. **THE RENDERER REBUILD — #37**, fresh from `design/`, hosting the UI halves of #13/#26/#29/#38–#41. The Console gets the full xterm.js-class streaming terminal (HIGH priority inside the rebuild). Verify every surface per CLAUDE.md's "Verifying UI changes": headed via `dev/tools/ui-verify/`, resize panels to narrow/wide extremes, click through every control you touched, screenshot each state — before calling any surface done.
5. **Lifecycle & features** — #8 cold-restore end-to-end, #15 rewind/fork (≥ v2.1.191 gate + per-fork file-state policy), #18 agent archive, #19 per-agent git identity, #20 Electron-main one-click launch, #23 workflow approval, #16/#17, then #38–#49 by judgment.
6. **§10 #1 attachment paths:** resolve via the decision ladder written in the item (sidecar-served asset endpoint is the recommended default). §10 #2–#8 stay parked — do not build them.

## Working method

- Orchestrate with Workflow fan-outs wherever work parallelizes (per-module implementation in isolated worktrees, adversarial review of each landed stage), but keep integration decisions in your main context. Adversarially verify each stage before moving on — independent reviewers prompted to refute, not confirm.
- **pytest is the standard:** extend the unit tier for every behavior you add or change (the test docstrings ARE the spec — keep them true); run the hermetic tier green after every backend stage (`tests\run.ps1` or `.venv\Scripts\python -m pytest tests\ -m "not integration"`); run targeted live tests where WSL/tmux behavior changed.
- Commit per completed logical unit with clear messages; push regularly; never leave `main` broken at a commit boundary.
- **End-to-end proof at each major stage and at the finish:** `start-dashboard.bat` brings up sidecar + app; create a real agent, drive it, watch events / inbox / links / scratchpad flow; screenshot the working dashboard to `.scratch/`. Never claim done without having driven the real system.
- **Final report:** honest per-item status of §11 (built / partial / untouched, with file pointers), every "⚠ assumed" call you made, what broke and how you fixed it, what remains for a follow-up run, and the DEVLOG entries covering it all.

Everything you need is in `docs/ARCHITECTURE.md` — it was refactored on 2026-07-09 specifically so you can build from it without guessing. When the doc and reality disagree, the doc is the intent: converge the code on it.
