# Lingering System Decisions — Register & Resolution Map

## Context

The AWL Multi-Agent Dashboard has a finished **visual design** (the `design/mockup.html` authority) and a **proven backend floor** (the bridge driver, live-verified), but a large band of **system behavior between them is still undecided or unbuilt**. A separate agent is currently running the `dev/prompts/component-system-refactor.md` pass, which standardizes the *design layer only* (tokens, a shared `styles.css`, a component gallery, `data-comp` names, `data-status` markers, and a DESIGN.md reconciliation). That refactor **captures** open questions (it marks elements `data-status="undecided"`) but **does not resolve** any system/product decision.

This document inventories the decisions that still need a human call, so we can work through them deliberately. It is a **read/think artifact** — nothing here authorizes repo changes. Resolution (editing DESIGN.md / TODO.md / coverage-map / code) is **gated on**: (1) the other agent finishing its `design/` pass, and (2) explicit user approval per decision.

### Boundary with the in-flight refactor (do not touch)
- The other agent owns `design/mockup.html`, `design/tokens.css`, `design/styles.css`, `design/gallery.html`, `design/DESIGN.md` for the duration of its run. **Hold all edits to `design/`** until it reports done.
- Overlap to watch: the TODO **Inbox** color/background notes and **OQ-1 (subagent)** touch that same design layer. Decide them on paper here; don't edit design files now.

---

## Deliverable (this turn)

Create a **shared decisions tracker** the user and I work from together:

- **File:** `dev/notes/agent-qa/open-system-decisions-2026-06-29.md` (new; sits beside the existing `ui-behavior-questions-2026-06-26-v5.md`, outside the `design/` files the other agent is editing — safe to write).
- **Shape (clear + concise, per repo rules):**
  - A short header — purpose, scope, the refactor boundary, and a **kind legend** (`OPEN` / `BLOCKED` / `DECIDED-UNBUILT`).
  - A one-screen **index table** — `ID · Topic · Kind · Status(open/decided)` — the at-a-glance tracking surface.
  - The decisions themselves, **grouped by the four tiers below**, each a stable-ID'd entry of ~5 lines: **Question · Fork/options · Why it matters · Source ref · `Decision:` (blank, filled as we resolve them)**.
  - Stable IDs `OD-01 … OD-NN` so we can reference items precisely ("OD-07 → auto-on-idle").
- **Content = the register below**, reformatted into that tracker layout. No analysis is lost; it's reorganized for tracking.
- **Also:** append one `DEVLOG.md` entry recording the new doc (per the project DEVLOG rule). No other repo files change; nothing under `design/` is touched.

---

## How to read the decisions

Each open item is one of three kinds:
- **OPEN** — a genuine design/product choice waiting on a human.
- **BLOCKED** — the bridge engine (tmux `capture-pane` + JSONL transcript, polled ~1s) physically can't supply it; the decision is "route around it or accept the fallback."
- **DECIDED / UNBUILT** — the call is made; it just needs backend + UI later (listed only where the decision had a fork worth recording).

Authority for intent: `design/DESIGN.md` + `design/mockup.html`. Authority for what's real: `sidecar/` + `bridge/` + `dev/notes/coverage-map.md` (the master capability→reality checklist) and `design/TODO.md` (the backlog; section **C** is the explicit "needs research/decisions" list).

---

## Tier 1 — Foundational architecture (everything multi-agent waits on these)

1. **Cross-agent event stream + identity tagging** *(OPEN, keystone)* — Today each agent has its own feed and the UI polls `/history` every 800 ms with array-index keys; events carry no sender. Decision: how to merge N agents into one attributed, stably-id'd stream the whole dashboard subscribes to. The merged Messages feed, From/To filter, per-message badges, the Log, the Inbox fleet badge, and the Graph all depend on this. *(coverage-map Cross-Cutting; QA Q32)*
2. **Prompt queue + idle / turn-boundary detection** *(OPEN)* — `/send` to a busy agent currently 409s and drops the prompt. A sidecar-owned queue + a reliable "agent just went idle / finished a turn" signal unblocks **send-timing (Now/Queue/Next)** *and* **link triggers**. *(coverage-map; QA Q23)*
3. **Agent identity store** *(MOSTLY DECIDED / partial)* — role·number·name·color·icon set at create, persisted, shown everywhere. Built at create time. **Open sub-decision:** the past-16 uniqueness rule (repeat color + distinct icon, name reuse with role+number tuple) and whether in-panel editing is v1. *(QA Q33)*

## Tier 2 — The defining feature: agent-to-agent linking *(zero backend today)*

4. **Link fire contract** *(OPEN — "single biggest undefined contract")* — When does Agent A's output forward to Agent B? Fork: automatically on A going idle, vs. an explicit handoff marker. *(QA Q12)*
5. **Trigger modes** — Now / Queue / Next real; **Inject (mid-run)** likely degrades to Next/Queue on bridge *(BLOCKED-ish)*; **Hold** = manual release into the Editor. Decide which ship in v1. *(QA Q23)*
6. **Payload** — **Message** (last assistant turn) is clear; **Transcript** payload **source/format is TBD** (raw JSONL? filtered? summary?) *(OPEN — TODO C6)*; **Manual** = compose per fire.
7. **End-After + bidirectional alternation** — turn/token caps that end the relay; strict one-in-flight alternation for A↔B. *(DECIDED in shape; counting is net-new — QA Q14)*
8. **Dense link-graph readability** *(OPEN, research)* — once links render as directed edges, how to keep many overlapping links legible and distinguish same-config links. *(TODO C7)*

## Tier 3 — Feature-area decisions (largely independent of each other)

9. **Inbox event detection** — 5 sections decided (Permission · Plan · Decision · Error · Warning), Error is "sticky." Only **Permission** is detectable today. **Error/Stall** = pattern-match + watchdog *(OPEN, best-effort)*; **Warning** = cap watchdog; **Decision (AskUserQuestion)** and **Plan-mode** are *invisible to the bridge from screen-state* and need transcript-level interception *(BLOCKED on the easy path; OPEN how to do it)*. *(QA Q16, Q6)*
10. **Lifecycle caps** *(DECIDED: notify-only)* — max-turns / context-% raise a **Warning** card; no auto-halt in v1; optional programmatic wind-down later (TODO B19). Storage + enforcement net-new.
11. **Run-strip completion %** *(BLOCKED)* — no real % source exists; barber-pole indeterminate is the honest fallback. Decision: accept indeterminate, or invest in a synthesized proxy.
12. **Marquee activity line** *(OPEN)* — the per-card live-activity ticker has no defined data source; "current activity" isn't defined (latest tool? last output line?).
13. **Subagents (OQ-1 + more)** *(OPEN)* — what clicking a subagent badge does (no-op today); whether subagents get an error state (badges have 3 states, agents have 4); what subagent info we expose and where; how agents spawn/manage subagents in the UI (TODO B16). Note: pending-vs-active is BLOCKED (only running-vs-done observable).
14. **Permissions** — **"Always allow"**: build in v1 or keep clean binary yes/no? *(OPEN, one-line call — QA Q17)*. **Mid-run permission-mode change** is BLOCKED (only Shift+Tab cycles; launch-only today; under research). Per-agent custom permissions partly wired at launch (deny is the reliable hard-block; `--allowedTools` is ignored under bypass — a claude bug).
15. **Library (Plans / Documents / Assets)** *(placeholder, zero backend)* — file read/edit/write-back endpoints; a **Plans review side-store** (owner/state/verdicts/comments — a `.md` can't carry it); plan↔agent owner mapping; **Plan Approve/Revise/Reject → resume out of plan-mode is BLOCKED on bridge**; assets media-storage model. Plus richer plans (mermaid/charts/mockups) ideas in TODO Scratch.
16. **Prompt composition extras** — **Embed** (settled, needs a write path); **Attach** needs file materialization + **WSL2↔Windows path normalization** *(OPEN — QA Q26)*; **citations** depend on Attach; **Templates** need storage; **Revise / Summarize** are the explicit **sdk-path** utility-LLM candidates; **Send-as-agent** wire format *(OPEN — QA Q24)*; response-format popover (per-prompt preamble).
17. **Shared scratchpad** *(net-new; policy DECIDED)* — append API + attribution + a WSL-reachable materialized `.md`. v1 policy: agents do **not** auto-read (explicit-send only) — revisable later.
18. **Settings writes & account/usage** — reads are built. **Gated writes** (enable/disable toggles, confirm-gated global edit) net-new. **Usage account band** (email/org/plan) is local & readable, not surfaced. **Usage limits band** (session/weekly % + resets) is **API-only, not in local files — decision pending** whether to fetch it live. **Setups** save / load-spawn-many (tab-less) has no store.
19. **Agent Delete (permanent wipe)** *(DECIDED: deferred)* — two-tier Retire(soft)/Delete(hard) is the design; v1 ships Retire only. TODO Scratch also asks for a full wipe. Confirm whether v1 keeps it deferred.
20. **Console scope** *(OPEN)* — raw terminal feed endpoint is missing; clarify the surface: always-on pane vs. per-tap drawer vs. modal, plus the slash-command runner routing.

## Tier 4 — Strategic / scope decisions

21. **Static mockup → React migration** *(OPEN, timing)* — the React app lags the mockup; the refactor is design-layer only. Trigger condition is "when design churn approaches zero." Decide when to port, and the related **neobrutalism.dev component-library consistency** question (do current components translate; commit to one library for maintenance — TODO Scratch).
22. **Product-scope "needs research"** *(OPEN — TODO C)* — whether **Tasks** belong in the workflow at all (C1); **docs-on-demand** / always-fresh systems docs in context (C2/C3); **AI-touched tracking** per directory (C4); **asset sourcing** for skills/CC assets (C5).
23. **Fresh design tweaks awaiting filing** *(OPEN — TODO Inbox; design-layer, hold)* — active→idle "output unchecked" indicator; periodic between-run context refresh + manual pull + load spinner; color rework (pink header/footer/dividers, teal on hover/drag); charcoal background instead of cream; a more distinct error red. **These edit `design/` — do not touch until the refactor agent is done.**

---

## Recommended resolution sequence

1. **Lock Tier 1 first** — the event stream, the queue + idle signal, and the identity rules are the load-bearing decisions; the linking feature and half of Tier 3 collapse into easy builds once they're settled.
2. **Then the linking contract (Tier 2)** — especially the *fire* event (item 4) and which trigger/payload variants are v1.
3. **Then pick off Tier 3 by appetite** — each is independent; Inbox-detection and Library carry the most net-new design.
4. **Hold Tier 4** until the React-port timing is chosen; hold all `design/`-touching items (incl. item 23 and OQ-1) until the refactor agent finishes.

## Verification / how decisions get recorded (later, gated)
Once a decision is made and approved, its home is one of: `design/DESIGN.md` (intent/rules + Open Questions register), `design/TODO.md` (backlog promotion/removal), `dev/notes/coverage-map.md` (status flip), or a sidecar/frontend change. No edits until the refactor agent is done and the user approves the specific change.
