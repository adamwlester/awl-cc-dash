# Open System Decisions — shared tracker

**Date:** 2026-06-29
**Purpose:** One place for the user + Claude to track every **unaddressed system/product decision** for the AWL Multi-Agent Dashboard. The visual design (`design/mockup.html`) is finished and the bridge backend floor is proven; this doc is the band **in between** — coordination, linking, lifecycle, and the net-new backend — that still needs human calls.
**Scope:** System behavior + product scope. *Not* the design-system refactor (tokens/styles/gallery/naming) — that's the in-flight `dev/prompts/component-system-refactor.md` pass.
**Authority:** intent = `design/DESIGN.md` + `design/mockup.html`; reality = `sidecar/` + `bridge/` + `dev/notes/coverage-map.md` (master capability→reality map). Per-question backend analysis = `archive/agent-qa/ui-behavior-questions-2026-06-26-v5.md` (archived; cited as "QA Qn"). **`design/TODO.md` is NOT a source** — it's a reference-only backlog (per its own top-of-file rule); never harvest decisions from it.

> **Refactor boundary (do not edit `design/` yet).** A separate agent owns `design/mockup.html · tokens.css · styles.css · gallery.html · DESIGN.md` until it reports done. It **captures** open questions (marks elements `data-status="undecided"`) but **resolves none**. Items tagged 🎨 below touch that layer — decide them here on paper, but make no `design/` edits until the refactor lands.

## How to use this tracker
- Each decision has a stable ID (`OD-01 …`). Reference items by ID ("OD-04 → auto-on-idle").
- **Kind:** `OPEN` = a genuine human call · `BLOCKED` = the bridge engine physically can't supply it (decision = route around / accept fallback) · `DECIDED‑UNBUILT` = call made, just needs building (sub-forks noted).
- **Recommended:** my suggested call, from existing notes/context or best inference.
- **Confidence** (same convention as the v5 QA doc — honest about certainty):
  - **▶ Confident** — the design docs / verified code / a prior locked decision effectively settle it; I'd proceed unless you object.
  - **◆ Leaning** — a reasonable default, but a real fork exists; worth your glance.
  - **✚ Can't infer** — genuinely your call (product taste, vision, or pending a fact I flag); I give a lean but wouldn't build on it unprompted.
- **Status:** `open` until we settle it; then set `decided` and fill the **Decision:** line in place. (Resolution — editing DESIGN.md / coverage-map / code — is gated on per-item approval.)

---

## Index

| ID | Topic | Tier | Kind | Conf | Status |
|----|-------|------|------|------|--------|
| OD-01 | Cross-agent event stream + identity tagging | 1 Foundation | OPEN | ▶ | decided |
| OD-02 | Prompt queue + idle / turn-boundary detection | 1 Foundation | OPEN | ▶ | decided |
| OD-03 | Agent identity store (25 colors / 50 icons, folder-sourced) | 1 Foundation | DECIDED‑UNBUILT | ◆ | decided |
| OD-04 | Link **fire** contract (when A → B) | 2 Linking | OPEN | ◆ | decided |
| OD-05 | Link trigger modes (Now/Queue/Next/Inject/Hold) | 2 Linking | OPEN | ◆ | decided |
| OD-06 | Link relationship model + config drawer | 2 Linking | OPEN | ◆ | decided |
| OD-07 | Link End-After (exchanges/tokens) + alternation | 2 Linking | DECIDED‑UNBUILT | ✚ | decided |
| OD-08 | Link tracking — grouped list in Link Config | 2 Linking | OPEN | ◆ | decided |
| OD-09 | Inbox event detection (Error/Warning/Plan/Decision) | 3 Feature | OPEN / BLOCKED | ◆ | decided |
| OD-10 | Lifecycle caps (max-turns / context-%) | 3 Feature | DECIDED‑UNBUILT | ▶ | decided |
| OD-11 | Run-strip completion % | 3 Feature | BLOCKED | ▶ | decided |
| OD-12 | Marquee activity line data source | 3 Feature | OPEN | ◆ | decided |
| OD-13 | Subagent integration model 🎨 | 3 Feature | OPEN | ◆ | decided |
| OD-14 | Permissions — binary approve/deny (no "Always allow") 🎨 | 3 Feature | OPEN / BLOCKED | ◆ | decided |
| OD-15 | Library — v1 read+render, project-scoped (OD-23) 🎨 | 3 Feature | OPEN / BLOCKED | ◆ | decided |
| OD-16 | Prompt extras — full mockup set, no cut (solve plumbing) 🎨 | 3 Feature | OPEN | ◆ | decided |
| OD-17 | Shared scratchpad — always-live auto-read channel (`.awl/`, OD-23) | 3 Feature | DECIDED‑UNBUILT | ▶ | decided |
| OD-18 | Settings — write everything feasible + account & usage bands 🎨 | 3 Feature | OPEN | ◆ | decided |
| OD-19 | Retire + Delete both in v1 (hard-wipe private, tombstone shared) | 3 Feature | DECIDED‑UNBUILT | ▶ | decided |
| OD-20 | Console — adopt design (per-agent tab + slash-runner IN); wire backend 🎨 | 3 Feature | OPEN | ◆ | decided |
| OD-21 | React port + library choice — PARKED (revisit at churn→zero) | 4 Strategic | OPEN | ✚ | decided |
| OD-22 | Message addressing schema (source + recipients[]) | 1 Foundation | DECIDED‑UNBUILT | ▶ | decided |
| OD-23 | Storage & scoping model (3 homes; dev `projects/`) | 1 Foundation | OPEN | ▶ | decided |

---

## Tier 1 — Foundational architecture
*Everything multi-agent waits on these. Settle first — much of Tier 2/3 collapses into easy builds once these are fixed.*

### OD-01 · Cross-agent event stream + identity tagging — `OPEN` (keystone)
- **Question:** How do we merge N per-agent feeds into one attributed, stably-id'd stream the whole dashboard subscribes to?
- **Today:** each agent is an island; the UI polls `/history` every 800 ms with array-index keys; events carry no sender.
- **Why it matters:** the merged Messages feed, From/To filter, per-message badges, the Log, the Inbox fleet badge, and the multi-agent Graph all depend on it.
- **Source:** coverage-map Cross-Cutting; QA Q32.
- **Recommended:** sidecar owns one aggregated event stream that stamps every event with `agent_id`/sender + a stable per-event id; frontend subscribes to that single stream (SSE) instead of polling `/history`.
- **Confidence:** ▶ Confident — coverage-map names this the keystone and the architecture is well-determined (merge per-session events, identity-stamp, stable ids); only the transport detail is a free choice.
- **Decision:** Build a single **sidecar-owned aggregated SSE stream** all panels subscribe to, replacing the 800 ms `/history` poll. Events are **lightweight envelopes** `{id, agent_id, seq, type, ts, payload|pointer}` stamped with the sender; heavy content (full tool blocks) is referenced and fetched on demand. It's a **bounded bus, not a stored mega-log**: the per-agent JSONL transcripts on disk (already written by Claude Code) stay the source of truth; the sidecar keeps only a rolling ring buffer, the UI virtualizes/backfills on scroll, and From/To filters apply server-side so the full history is never materialized at once. **Event id** = deterministic composite `{agent_id}:{source}:{anchor}[:{block}]` — `agent_id` = the agent's `--session-id` UUID; `source` = `t` (transcript) | `s` (synthesized); `anchor` = the JSONL entry's `uuid` (transcript) or a deterministic trigger key e.g. `perm:<screen-sig>` (synthesized); `block` = content-block index when one entry holds several. Determinism is required so re-polls dedup to no-ops and a reconnect replays without duplicates. **Ordering** = a separate monotonic `seq` the sidecar assigns at emit (never parse the id for order).

### OD-02 · Prompt queue + idle / turn-boundary detection — `OPEN`
- **Question:** Does the sidecar own a per-agent prompt queue, and how does it detect "agent just went idle / finished a turn"?
- **Today:** `/send` to a busy agent **409s and drops** the prompt.
- **Why it matters:** unblocks send-timing (Now/Queue/Next) **and** link triggers — both ride on this one signal.
- **Source:** coverage-map; QA Q23.
- **Recommended:** sidecar-owned per-agent FIFO queue; detect idle from the bridge's already-observable `generating→idle` screen transition (~1 s sample) and flush on idle. ("Next"/turn-boundary is a later refinement on the same signal.)
- **Confidence:** ▶ Confident — idle is already exposed in `events()`; the queue is the obvious, well-scoped fix for the 409-drop.
- **Decision:** Sidecar owns a **per-agent _ordered_ queue** (not strict FIFO) driven by the bridge's `generating→idle` transition (~1 s screen sample) — the same idle/turn-boundary signal OD-04 fires links on. Each queued item carries a **disposition**, delivered over **two channels**:
  - **(1) Push-on-idle (tmux send-keys)** for **Now / Next / Queue** — delivered as clean user turns. **Queue** = append-tail, flush at idle (polite default); **Next** = insert-head, flush at idle; **Now** = `interrupt()` the current run, then flush at the resulting idle.
  - **(2) Hook-pull inbox** for **true Inject** (full v1 functionality, *not* a degrade-to-Next). Every bridge agent is launched with **`PostToolUse` + `Stop` HTTP hooks** pointed at a sidecar **inbox-drain endpoint** (the hook POST body carries `session_id`). `PostToolUse` drains any pending inject for that agent and returns it as `additionalContext`, so a *running* agent receives it mid-turn at the next safe between-tools boundary **without stopping**; the `Stop` hook (`decision:"block"` + reason) backstops the no-tool-call case so a pure-text turn still catches it at turn-end. The inbox is **durable + ack-on-2xx** (HTTP hook failures are non-blocking, so an undelivered inject stays pending).
  - **Hold** (link-only): payload is produced on fire but **parked in a staging slot, never auto-flushed** — released manually into the target's compose Editor for approval/edit before send.
  - **Build notes / risk:** inject lands at tool/turn boundaries (not literally mid-sentence) and arrives as injected context, not a user bubble; bridge must launch agents with the hook config + a **WSL2→Windows-reachable sidecar URL** (localhost from WSL2 may not reach the host — `mcp_sync` is the precedent for config rewriting). **First build step = a one-agent spike** confirming `additionalContext` lands mid-turn on the installed Claude build (build-2b showed documented behaviors can differ by build) before wiring the fleet.

### OD-03 · Agent identity store — `DECIDED‑UNBUILT` (sub-fork open)
- **Decided:** role·number·name·color·icon set at create, persisted, shown everywhere (color/icon already wired at create).
- **Open sub-decisions:** (a) the **past-16 uniqueness rule** (repeat color + distinct icon; name reuse with role+number tuple); (b) whether **in-panel editing** of identity is in v1 or read-only.
- **Source:** QA Q33; build-2b session.
- **Recommended:** adopt QA Q33's rule verbatim (next-free color+icon on create; past 16 → repeat color + distinct icon; identity = role+number+name tuple). Ship v1 **read-only** display; add in-panel edit later (build-2b already accepted read-only for v1).
- **Confidence:** ◆ Leaning — the past-16 rule is effectively specified (▶ on that part); deferring edit to post-v1 is the real judgment call.
- **Decision:** Identity = role+number+name+color+icon, set at create, persisted, shown everywhere; **read-only in v1** (in-panel editing deferred). Pools: **25 colors** (extend tokens.css `--ag-*` 16→25, same OKLCH Jewel family) and a **curated 50 icons** (29→50). Assign round-robin `color = n mod 25`, `icon = n mod 50`: every (color, icon) pair is unique for the first 50 agents, then reuses beyond 50 (supported, not capped). 25 = unique-color ceiling (typical project), 50 = unique-icon ceiling; past ~16 colors the **icon is the primary disambiguator** and color becomes a soft "family" signal. **Icon source = single source of truth:** the picker indexes `assets/icons/agents/` (167 on disk) and recolors via the sidecar `GET /assets/agent-icons/{name}?color=` endpoint, retiring the mockup's hardcoded `AGENT_ICONS` array + embedded sprite sheet — curate the 50 now; converge the picker onto the endpoint at React-port time (see OD-21). 🎨 The +9 colors / +21 icons edit `design/` (tokens.css + mockup) — apply only after the refactor agent finishes.

---

## Tier 2 — The defining feature: agent-to-agent linking
*Zero backend today. The signature capability; sequenced after Tier 1 because it rides on the event stream + queue.*

### OD-04 · Link **fire** contract — `OPEN` ("single biggest undefined contract")
- **Question:** When does Agent A's output get forwarded to Agent B?
- **Fork:** **(a)** automatically when A goes idle · **(b)** only on an explicit handoff marker A emits.
- **Why it matters:** the keystone of linking; trigger/payload/alternation all hang off it.
- **Source:** QA Q12.
- **Recommended:** **fire automatically on source-idle** (turn-complete) — it's directly observable and matches the "fire-on-idle" plumbing — and offer **Hold** (OD-05) as the deliberate manual-release alternative, rather than making an explicit marker the default.
- **Confidence:** ◆ Leaning — auto-on-idle is the inferred default and the plumbing supports it, but this is a genuine product fork (an explicit marker trades convenience for control).
- **Decision:** Fires on the **reply-to** model (the Direct-messaging relationship, OD-06). When the source finishes the turn answering a linked peer's inbound message — detected at the `generating→idle` turn-boundary (OD-02) — the sidecar routes *that turn's output* back to **the inbound's source** (`recipients:[peer]`, OD-22) by enqueuing it on the peer's inbound queue. So a fire = **completion of a reply**, not a blind broadcast on every idle: the sidecar pairs each dispatched inbound with the idle-bounded turn it produced and targets the reply at that inbound's sender. Strict **one-inbound-in-flight per agent** (the serialized reply-to model, to be captured as its own entry) keeps the pairing unambiguous. No explicit handoff marker required; **Hold** (OD-05) covers human-gated sends.

### OD-05 · Link trigger modes — `OPEN`
- **Question:** Which delivery modes ship in v1 — Now · Queue · Next · Inject (mid-run) · Hold (manual release into Editor)?
- **Constraint:** **Inject** likely degrades to Next/Queue on bridge (no safe mid-run injection point).
- **Why it matters:** defines the link config UI and the queue behavior.
- **Source:** QA Q23.
- **Recommended:** v1 = **Now + Queue + Next + Hold**; treat **Inject** as transparently degrading to Next/Queue (don't promise true mid-run injection on bridge).
- **Confidence:** ◆ Leaning — coverage-map ranks Now/Queue as P0, Next P1, Inject deferred; the exact v1 subset is a scoping call.
- **Decision:** Ship the full trigger vocabulary — **Now · Next · Queue · Inject · Hold** — all delivered via the OD-02 per-agent ordered queue, with **Queue the default** (politest). *Now* interrupts the target and delivers immediately; *Next* waits for the current turn to finish then delivers ahead of the queue; *Queue* waits for the turn **and** lets the existing queue drain first; **Inject** (mid-run, no stop) has no safe injection point on the bridge, so it **transparently degrades to Next/Queue** (don't promise true mid-run injection); **Hold** stages the message for your **manual approval before it sends** — the human review-gate on a link. (Send-from-Prompt reuses the same vocabulary minus Hold.)

### OD-06 · Link relationship model + config drawer — `OPEN`
- **Question:** How is a link configured, and what flows across it? (Reframed: the **Payload field is removed** — replaced by a **Relationship** selector; what's sent is *derived* from the relationship.)
- **Why it matters:** "Payload" was the wrong primary knob — the relationship type is, and it governs the receiver's context cost (the old Transcript-dump worry).
- **Source:** QA Q13.
- **Recommended:** v1 = **Message + Manual**; **defer Transcript** until OD-06's source/format is specified (it's low-priority in coverage-map and risks dumping huge context onto the receiver). *(superseded by the reframe below)*
- **Confidence:** ◆ Leaning — Message-as-default is solid (▶ on that); deferring Transcript is the judgment part.
- **Decision:** Replace the **Payload** field with the link-config structure below; what's sent is *derived* from the relationship. **Drawer order, top→bottom:** **(1) Agent pair + direction** *(first row)* — two **single-select** agent dropdowns with a **direction-arrow** control between them (A→B / B→A / A↔B); endpoints static-modeled for now. **(2) Relationship** — a **multi-select** (a link can be both): **Direct messaging** = reply-to conversation (OD-04), no extra config yet; **Shared context** = passive awareness, whose dropdown is a **content-type multi-select** reusing the Messages Content taxonomy (Thoughts/Read/Write/Bash/Diffs/Meta) to filter *what* is shared, plus a **"share all prior context" backfill toggle** (default off, ideally summarized). Shared-context delivery is **piggyback**: updates ride the receiver's **next prompt (user or agent)**, never triggering a turn on their own, and a per-(source→target) **watermark** attaches exactly the context produced **since the last share** (no re-dump, no gap) — the watermark also **dedups across both channels** when both relationships are on. **(3) Trigger** (OD-05). **(4) End After** (OD-07). **(5) Action strip** (Save / Delete). **Dropped:** the Message/Transcript/Manual payload options (Manual = just send a prompt; Message/Transcript fold into the two relationship types).

### OD-07 · Link End-After + bidirectional alternation — `DECIDED‑UNBUILT`
- **Decided (shape):** exchange/token caps end the relay; A↔B is strict one-in-flight alternation with the cap as backstop.
- **Open/net-new:** exchange counting is new work (count round-trips, not internal turns).
- **Source:** QA Q14.
- **Recommended:** keep the decided mechanism; default to a **conservative cap** (e.g. End-After ≈ 6 exchange-turns *or* a modest token budget, whichever first) so an unattended link can't run away — but the exact number is yours.
- **Confidence:** ✚ Can't infer — the mechanism is settled, but the default cap value depends on your use; I won't pick it unprompted.
- **Decision:** End After bounds the **inter-agent exchange**, counted in **Exchanges** — a round-trip = **one message each direction** — explicitly **not** internal agentic *turns/steps* (those are the lifecycle scope, OD-10). Two independent caps — **Exchanges** and **Tokens** — each with its own toggle; none on = no limit, both on = ends at the first reached. **Default = 25 exchanges.** A↔B stays strict one-in-flight alternation with the cap as the runaway backstop.

### OD-08 · Dense link-graph readability — `OPEN` (research)
- **Question:** Once links render as directed edges, how do we keep many overlapping links legible and distinguish links that share the same config?
- **Why it matters:** the Team Graph becomes unreadable at scale without a plan; gated behind link edges existing.
- **Source:** follows OD-04/05 (linking); coverage-map (links-as-edges).
- **Recommended:** **defer until link edges exist**; then apply standard techniques — curved/offset parallel edges, hover-to-highlight a link's full config, and style/color keyed to config — rather than designing it now in the abstract.
- **Confidence:** ◆ Leaning — "defer until edges exist" is confident; the specific legibility approach is a generic best-guess until there's something to look at.
- **Decision:** Keep it simple — **no on-graph edges and no per-card link badges for now** (both deferred; no room on the cards). Basic link tracking lives entirely in the **Link Config panel**: add a **new section at the bottom** (below the existing fields) listing **all links, grouped by agent** — each agent is a group header. Because a link joins two agents, **each link appears under both agents' groups** (deliberate double-listing). Each entry shows the **other agent** + a **direction arrow relative to that group's agent** — → (to) / ← (from) / ↔ (both) — reusing the **same arrow indicator** as the agent-pair row at the top (OD-06). So the panel reads: agent-pair+direction → Relationship → Trigger → End After → action strip → **this all-links list**. *(Natural extension, not required for v1: clicking a list entry loads it into the fields above to edit — the master/detail pattern.)*

---

## Tier 3 — Feature-area decisions
*Largely independent of each other; pick off by appetite after Tier 1/2. Inbox-detection and Library carry the most net-new design.*

### OD-09 · Inbox event detection — `OPEN` / `BLOCKED`
- **Correction note (2026-06-30):** the **Plan** Inbox card carries **no Approve/Reject** — the Decision text below originally read "Approve/Reject for Plan," which was an error (now fixed inline). Plan verdicts (**Approve · Revise · Reject**) live **only in the Library → Plans tab**; the Inbox Plan card is notify-only — **Review** (jumps to that plan) + **Reply**. (Decision cards keep their option-pick + Approve; Permission keeps binary Approve/Deny.) Design ground truth = the `design/` Inbox section ("Plan cards drop Approve/Reject").
- **Decided:** 5 sections (Permission · Plan · Decision · Error · Warning); Error is "sticky" (unknown reads don't clear it).
- **Reality:** only **Permission** is detectable today. **Error/Stall** = pattern-match + watchdog (best-effort, OPEN). **Warning** = cap watchdog. **Decision (AskUserQuestion)** and **Plan-mode** are **invisible to the bridge from screen-state** — need transcript-level interception (BLOCKED on the easy path; OPEN how).
- **Why it matters:** the Inbox is the central "needs you" surface; 4 of 5 raise-paths are net-new.
- **Source:** QA Q16, Q6.
- **Recommended:** build by tractability — **Permission (done) → Error/Stall (pattern-match + no-output watchdog, accept best-effort) → Warning (cap watchdog) → Decision/Plan last** via transcript-level interception. Ship the first three for v1; treat Decision/Plan as a follow-on.
- **Confidence:** ◆ Leaning — the sequencing and the first three are well-grounded (▶ there); Decision/Plan detection is the genuinely hard, unproven piece.
- **Decision:** Build all five typed sections, by detection tractability, over **two raise mechanisms** (screen-state for what the bridge can see; the **OD-02 hook channel** for what it can't):
  - **Permission** — already proven (screen-anchored prompt → event pair). v1 = binary Approve/Deny; "Always allow" removed entirely (OD-14).
  - **Error** — `derivable-not-built`. Three detection paths: **structural** (tmux/session gone — reliable), a **no-output stall watchdog** (~1 s loop; threshold tuned over time), and **best-effort text pattern-match** on capture-pane/transcript (API/rate-limit, tool/MCP, config). **Sticky** — persists until explicit **Retry/Dismiss** (a simple inbox flag). Retry re-issues a net-new **"last command" store**; Dismiss/Reply→Editor. Pattern catalog + stall threshold improve iteratively; the architecture is fixed.
  - **Warning** — `synthesized`; it is the visible output of **OD-10's** cap poll-loop. Max-turns + context-% subtypes are fully local/deterministic; the "approaching rate/usage cap" subtype is gated on **OD-18's** API-only usage data. Acknowledge clears (client); Reply→Editor.
  - **Plan + Decision** — screen-state blind (bridge `impossible`); resolved via the **OD-02 hooks**, since the agent's `ExitPlanMode` (Plan) and `AskUserQuestion` (Decision) **tool calls are visible to hooks even when the screen isn't**. A `PreToolUse`-style interception raises the Inbox card and **routes the answer back**: `updatedInput` supplies the picked option for **Decision** (its card carries the options + an Approve). For **Plan**, the Inbox card is **notify-only — Review (→ Library Plans) + Reply, with no Approve/Reject on the card**; the plan-exit is allowed/denied from the **Library Plans tab** (Approve · Revise · Reject), which routes back to the agent's pending `ExitPlanMode` hook — this still **sidesteps the old "resume out of plan-mode" block**, since the agent leaves plan mode via its *own* allowed tool call rather than an outside mode-set.
  - **Spike-gated:** the Plan/Decision path is **pursue-but-prove-first** — confirm the full **detect → user-answers → agent-resumes** round-trip (including the hook holding for the human within its timeout) as part of the OD-02 hook spike. **If it proves out → Plan/Decision ship as full Inbox cards; if not → graceful fallback to "detect-and-surface"** (card is raised, but you answer by manually attaching to that agent).
  - **Sequencing:** **v1 = Permission (done) + Error + Warning**; **Plan + Decision are a fast-follow** the moment the spike confirms. The Inbox tab's fleet badge counts agents with ≥1 open request across all five types.

### OD-10 · Lifecycle caps — `DECIDED‑UNBUILT`
- **Decided:** max-turns / context-% crossing raises a **Warning** card (Continue / Raise cap / Stop).
- **Open/net-new:** cap storage + sidecar enforcement loop.
- **Source:** QA Q5.
- **Recommended:** **v1 = notify-only** — raise a Warning; build cap storage + a sidecar poll-loop comparing work-step count / context-% to the stored caps.
- **Confidence:** ▶ Confident — this was explicitly locked in ui-spec Q5b.
- **Decision:** **Notify-only.** When an agent crosses its stored **max-turns** or **context-%** cap, the sidecar raises a **Warning** card (Continue / Raise cap / Stop) and the run continues until you choose. Build = cap storage (set on Create, editable in the Lifecycle band) + a sidecar poll-loop comparing live work-step count / context-% to the stored caps — **the same loop that feeds OD-09's Warning section** (not separate work). Caps are user-set per agent.

### OD-11 · Run-strip completion % — `BLOCKED`
- **Question:** Accept the barber-pole indeterminate forever, or invest in a synthesized progress proxy?
- **Reality:** no real % source exists in the bridge's two channels; barber-pole is the honest fallback.
- **Source:** QA Q7; coverage-map.
- **Recommended:** **accept the barber-pole indeterminate**; don't synthesize a fake %. Revisit only if a genuine progress signal appears.
- **Confidence:** ▶ Confident — DESIGN + coverage-map already call barber-pole the honest fallback; a made-up % would mislead.
- **Decision:** **Agent self-report, with barber-pole as the floor.** The bridge can't compute a true % from the outside, so the *agent* supplies it: a **system-prompt mandate** has every agent **publish a short ordered checklist of the major operations it plans, up front** (before substantive work) and **mark each item done as it goes**; a trivial run declares a single step (or none) so the cost stays proportionate to run size. The sidecar reads the checklist from the transcript (rides on the OD-01 stream + OD-02 transcript/hook parsing — no new channel) and renders **done ÷ total** as the run strip: a **segmented bar with a vertical separator per step**, so you see both how many major steps the run has and how far through it is. The **current in-progress item labels the bar** (the step name beside the segments) — this is separate from the OD-12 marquee, which is its own liveness stream (see OD-12). **Floor:** any run that publishes no checklist (or a non-cooperative agent) shows the honest **barber-pole indeterminate** — never a fabricated %. **Rejected:** a background LLM estimator that reads agents from the outside — it costs *more* (re-reading large, growing transcripts × cadence × fleet = heavy input tokens) for a *worse* number (less informed than the agent; invents its own denominator); a no-LLM heuristic (tool-count vs. a rolling baseline) is allowed only as an optional, clearly-noisy fallback, not the default. Also **not** used: turns-used ÷ max-turns cap (that's distance to the safety limit, not task completion). **Caveat:** the denominator can grow if the agent adds steps mid-run, so the bar can step backward — bounded within the run, and the honest cost of a real signal.

### OD-12 · Marquee activity line — `OPEN`
- **Question:** What feeds the per-card live-activity ticker, and what does "current activity" mean (latest tool_use? last screen line? generating state)?
- **Reality:** derivable from the ~1s transcript/screen sample, but the definition + extraction is undefined; omitted in the React build ("no data source").
- **Source:** QA Q8; TeamGraph.tsx.
- **Recommended:** define "current activity" = the **latest tool_use / generating line** from the ~1 s sample; keep it cosmetic and low-stakes (a glanceable ticker, not a contract).
- **Confidence:** ◆ Leaning — clearly derivable, but the exact definition is a judgment call on a low-stakes element.
- **Decision:** **Marquee = a low-fidelity scrolling tail of the agent's transcript output.** A pure **liveness** signal ("it's running and moving"), **not** an audit/inspection surface — auditing lives in the Messages feed. Source = the agent's own slice of the OD-01 stream (recent transcript output), rendered as a scrolling line; **no new backend**. Raw recent output is the default; lightly-derived activity verbs (e.g. "→ Read app.tsx", "→ Bash npm test") are optional polish, not required. When the agent is idle (no new output) the marquee goes quiet / holds its last line. **Explicitly decoupled from the OD-11 checklist** — a discrete step label doesn't belong in a scrolling ticker (and short lists wouldn't scroll); the checklist's current step stays on the progress bar, the marquee stays the continuous output flow. Keep it simple.

### OD-13 · Subagent integration model — `OPEN` 🎨 (was OQ-1 click; scope expanded 2026-06-30)
- **Scope note (2026-06-30):** expanded from the lone OQ-1 *click* question into the full **subagent integration model** — the narrow framing below is kept as history; the **Decision** carries the settled model.
- **The one open question:** what does **clicking a subagent badge** do? Today it's a deliberate no-op (`stopPropagation`, isolated from the card).
- **Already resolved (not open) —** keep for context, don't re-decide: (a) **error state** ✅ — `sb-error` was added as the 4th subagent run-state, mirroring the status badge (DESIGN OQ-1); (b) **what info / where** ✅ — settled in DESIGN: the subagent strip shows id + run-state colour + type/status/usage, collapsed to one row with a chevron→accordion drawer; (c) **spawn/manage subagents in the UI** is a separate backlog item, not part of this OQ.
- **Reality:** pending-vs-active is **BLOCKED** (only running-vs-done observable); s1/s2 ids are dashboard-minted.
- **Why it matters:** the refactor's one still-open captured question — decide the intent on paper, but the badge edit waits on the refactor (🎨).
- **Source:** DESIGN OQ-1 (narrowed to click-only); QA Q9.
- **Recommended:** **click expands** the subagent strip/accordion to that subagent's detail (cheap, useful) rather than a no-op.
- **Confidence:** ◆ Leaning — grounded in the existing strip/accordion, but it's the parked OQ-1 and partly a design-taste call (held behind the refactor).
- **Decision:** Model a subagent as a **sub-identity of its parent** (`coder-01 › A2`), riding the OD-01 sender stamp + OD-22 addressing — so Messages, the From/To filter, and identity inherit subagents with no new subsystem.
  - **Backend (the one net-new piece):** the sidecar also **ingests each subagent's own transcript** (`<parent-uuid>/subagents/agent-<id>.jsonl`, today skipped as an `isSidechain`) with the *same* parser, tagged under the parent. **Real-time, not deferred:** a running subagent's id/path only return *with its result*, so the sidecar **watches the parent's `subagents/` dir and tails new files live**, joining each to its spawn by **matching the spawn's prompt to the subagent transcript's first message**, then reconciling against the `agentId` when the result lands (same ~1 s poll as OD-01/02; no new infra). *(A subagent-start hook would give cleaner attribution — adopt later if build-verified; folder-watch is the v1 mechanism.)*
  - **Naming:** replace the flat monotonic `s1…sN` (bridge `derive_subagents`) with **group + member** — **group** = a parent **run** that spawned subagents, lettered in occurrence order (A, B, C…); **member** = spawn order within that run (1, 2…). Badge shows `A2`; **no `s` prefix anywhere**; full sender form `coder-01 › A2`. Derived by segmenting the transcript at user-prompt/turn boundaries (OD-02's signal); past Z → `AA`.
  - **Team Graph card (glance view):** the subagent strip stays; badges relabel to `A2` and keep their run-state colour (incl. `sb-error`). **Badge click** (resolves OQ-1, replacing the `stopPropagation` no-op): **(1)** focuses the **parent** in the Agent panel, **(2)** opens its Details **Subagents** accordion scrolled + highlighted to that row, and **(3)** sets the Team Feed filter to that subagent on the **Messages** tab — i.e. clicking a helper selects its parent and scopes everything to the helper.
  - **Agent → Details "Subagents" accordion:** a **read-only audit history** — a collapsed accordion **pinned below the Timeline, above the Retire/Delete footer**, header carrying a **total-subagent count badge**. Expands to rows **grouped by run**, each: id+type (`A2 · Explore`) · task · status (running/done/error) · usage (tokens · tools · duration) · model · link to its own transcript. The card strip stays the glance view; this is the audit home.
  - **Team Feed From/To filter (nested, sender-side):** the shared filter becomes a **2-level tree** — agents on top, expand to reveal subagents; parent-select = the whole subtree, leaf-select = just that subagent. It's the same shared field across all feed tabs and **applies universally** — tabs with no subagent traffic (Scratch, Inbox) simply match nothing for a subagent selection. **Filter-only, never addressable:** subagents appear in the feed *filter* but **not** in the **Prompt compose-To** (you can't send to a helper — To stays parents + User).
  - **Messages display:** subagent events stream in **nested/indented under their parent**, visible by default, with the Type/Content filters applying as normal; a "collapse subagent chatter" toggle is an allowed fast-follow. Subagent traffic is always **Received** (helpers never receive operator sends). Log may optionally carry lightweight "spawned A2 / A2 done" events (additive).
  - **Lifecycle:** no manual Retire — a subagent self-completes (running → done/error) and is subordinate to its parent (gone when the parent is retired/deleted). No new lifecycle concept.
  - **Out of scope (v1):** subagent **create/config** (the Create-side) and subagent treatment in **Scratch / Inbox** (issues surface via the parent). *(Live mid-run streaming is explicitly IN — see Backend.)*
  - **🎨 design-layer:** the badge relabel, the nested-filter tree, and the Details accordion are `design/` edits — land after the component-system refactor is confirmed done + per-item approval.

### OD-14 · Permissions — "Always allow" + mid-run mode — `OPEN` / `BLOCKED`
- **Questions:** (a) build **"Always allow"** in v1, or keep clean binary yes/no? (b) per-agent custom permissions from `.claude/settings.json`.
- **Reality:** approve/deny is **binary** today. **Mid-run permission-mode change is BLOCKED** (only Shift+Tab cycles; mode is launch-only; under research). Per-agent launch scoping is partly wired — **deny is the reliable hard-block**; `--allowedTools` is ignored under bypass (a claude bug).
- **Source:** QA Q17; coverage-map; build-2b.
- **Recommended:** **defer "Always allow" in v1** — keep the clean binary approve/deny (it's net-new and the bridge is binary today); **accept launch-only** permission-mode and leave mid-run change parked under research; lean on **deny-lists** as the reliable per-agent hard-block.
- **Confidence:** ◆ Leaning on deferring always-allow (your one-line call); ▶ that mid-run mode stays blocked.
- **Decision:** **Fully remove "Always allow"** — from the UI and all present/future dashboard implementation. Permissions stay a clean **binary Approve / Deny** (+ Reply): drop the **Always allow** button from the Inbox **Permission** card (DESIGN currently lists *Approve · Deny · Always allow · Reply*) and build **no** always-allow rule-persistence path, now or later — it's net-new, the bridge round-trip is binary, and a persisted "always" rule is a silent auto-approve surface we don't want. **Unchanged context (reality, not a new choice):** permission **mode** stays **launch-only** (mid-run change is BLOCKED — only Shift+Tab cycles — and isn't pursued); per-agent scoping is **deny-based** (deny is the reliable hard-block; `--allowedTools` is ignored under bypass, a claude bug). 🎨 The Permission-card button removal is a `design/` edit — land after the component-system refactor is confirmed done + approval.

### OD-15 · Library (Plans / Documents / Assets) — `OPEN` / `BLOCKED`
- **Question:** The whole Library is a placeholder with zero backend. Decide: file read/edit/write-back endpoints; a **Plans review side-store** (owner/state/verdicts/comments — a `.md` can't carry it); plan↔agent owner mapping; assets media-storage model; richer plans (mermaid/charts/mockups).
- **Reality:** **Plan Approve/Revise/Reject → resume out of plan-mode is BLOCKED on bridge** (no plan-mode detection / mode set).
- **Source:** coverage-map Library; QA Q18/Q19.
- **Recommended:** scope v1 to **read + render** of Plans/Documents (files via WSL) plus a **filename-keyed review side-store** (verdicts/comments); **defer** write-back, assets media, and plan-approve→resume (blocked on bridge).
- **Confidence:** ◆ Leaning — coverage-map sequences exactly this (read P0, side-store P1, approve/resume blocked); the v1 cut is a judgment call.
- **Decision:** **v1 = read + render, project-scoped per OD-23.** The Library reads/renders **Plans + Documents** from files in the **project's directory** (the agents' `cwd`, via WSL) — these are *project* data, owned by the project, not the dashboard. The **Plans review side-store** (owner/state/verdicts/comments — can't live inside a `.md`) is a small structured file under **`<project>/.awl/`** (e.g. `<project>/.awl/plan-reviews.json`), keyed by plan **filename**, so it travels with the repo and is WSL-reachable; it also carries the **plan↔agent owner** mapping. **Deferred to later:** file **write-back** (edit-and-save endpoints), **Assets** media-storage, and richer plans (mermaid/charts/mockups). **Still BLOCKED (bridge):** **Plan Approve/Revise/Reject → resume out of plan-mode** (no plan-mode detection / mode-set) — but note the **OD-09 hook path** may unblock it later, since the agent's own `ExitPlanMode` tool call is hook-visible (approve/deny the plan-exit). 🎨 the Library **panel UI** is a `design/` edit (held until the refactor + per-item approval); the file/side-store **endpoints** here are backend and free to build now.

### OD-16 · Prompt composition extras — `OPEN`
- **Question:** Which of these are v1 — **Embed** (settled; needs a write path) · **Attach** (needs file materialization + **WSL2↔Windows path normalization**) · **citations** (depend on Attach) · **Templates** (need storage) · **Revise / Summarize** (explicit **sdk-path** utility-LLM passes) · **Send-as-agent** wire format · response-format popover (per-prompt preamble)?
- **Why it matters:** several need Tier-1 plumbing; Attach's cross-fs path translation is a real open problem.
- **Source:** QA Q24/Q25/Q26/Q27; coverage-map Prompt.
- **Recommended:** v1 = **Embed** (settled, just needs a write path) + History basics; **defer Attach/citations** until WSL↔Windows path normalization is solved; do **Revise/Summarize via the sdk path** when the utility-LLM lands; Templates + Send-as-agent later.
- **Confidence:** ◆ Leaning — Embed-first is well-supported; the rest is sequencing against unsolved plumbing (Attach paths are a genuine open problem).
- **Decision:** **Include the full prompt-composition surface from the mockup — nothing cut.** Per this doc's purpose, it records *what we want*; the plumbing each piece needs is **work to solve**, not a reason to defer. The set, each tagged with the plumbing it requires:
  - **Editor + inserted-block primitive** — the contenteditable Editor holds free prose + three block variants (`embed` / `template` / `citation`, card-outline boundary). Frontend; **Send** serializes the blocks into the outgoing prompt text.
  - **Embed** — drops a frozen "from \<source\>" block (doc section / feed-block run / whole card/doc) into the Editor with click-to-source. Needs a **write path** from the Library/feed strip into the Editor (the merged Export control's *Add to prompt → Embed*).
  - **Attach** — attachment-chip strip above the Editor; whole-doc/asset/card → a chip (real path for on-disk files, a materialized `/tmp/…` for feed content). **Load-bearing solve:** **file materialization + Windows↔WSL2 path normalization** — the one genuinely hard piece; **solve it** (the bridge's `mcp_sync` config-rewrite is the precedent), don't dodge it.
  - **Citations** — inline `citation` pills inserted from an attachment's link icon; you can only cite something already attached; deleting a citation leaves the attachment, deleting an attachment **cascades** to its citations. Built **with** Attach (same payload).
  - **Templates** — single-select dropdown (None + saved) + fill-input; picking inserts a `template` block with placeholder pills (filled/unfilled). **Storage per OD-23 = the dashboard runtime store** (reusable / project-agnostic — templates are tool-level reusable data, like Setups); project-specific templates may later live in `<project>/.awl/`.
  - **Revise** (scope chip: Grammar · Language · Refactor, default Grammar) and **Summarize** (messages slide-over) — both run as **`sdk`-driver utility-LLM passes** (the non-interactive in-process Claude Agent SDK engine reserved exactly for this; **not** the bridge). This is the SDK support that must be wired.
  - **Send-as-agent** — compose/dispatch a prompt attributed **from** a chosen agent (the shared sub-header's Source/Target). Wire format rides the **OD-22** `source` + `recipients[]` schema, delivered via the **OD-02** queue.
  - **Response-format popover** — a per-prompt **preamble** (TLDR / Structure groups) prepended to the outgoing prompt. Frontend.
  - **Plus:** **Voice mic** (Editor-header dictation) · **History tab** (past prompts, multi-select, **Retry** / Stop, Edit — rides the OD-02 queue + a prompt-history store) · the **merged Export control** (Copy · Export→file · Embed · Attach).
  - **Build order (dependencies, not cuts):** the two solves that gate the rest are **Attach's path-normalization** (unlocks Attach + Citations + materialized-content embeds) and the **`sdk` utility-LLM pass** (unlocks Revise + Summarize); Templates needs the OD-23 store; Send-as-agent needs OD-22; the Editor / inserted-blocks / preamble / mic are frontend that can land early.
  - **🎨 design-layer:** the Editor, blocks, Templates, attachment-strip, and Export-control UI are `design/` edits — land after the component-system refactor is confirmed done + per-item approval. The backend plumbing (path-normalization, the sdk passes, the template store) is **free to build now**.

### OD-17 · Shared scratchpad — `DECIDED‑UNBUILT`
- **Correction note (2026-06-30):** this **reverses** the earlier *no-auto-read* policy. The `Decided:` / `Recommended:` / `Confidence:` lines below are kept **verbatim as the pre-correction record** (per the leave-`Recommended`-as-is rule); the **Decision** now carries the corrected model — the scratchpad is an **always-current, auto-read** live channel, delivered as a bounded per-agent delta.
- **Decided:** append API + attribution + a WSL-reachable materialized `.md`; **v1 policy = agents do NOT auto-read** (explicit-send only).
- **Open/net-new:** all of it is unbuilt; revisit auto-read later; same path-normalization caveat as Attach.
- **Source:** QA Q21/Q22; coverage-map Cross-Cutting.
- **Recommended:** confirm **v1 = write-in / read-out only** (agents post; they read only when explicitly sent); build the append API + attribution + WSL-reachable `scratchpad.md`.
- **Confidence:** ▶ Confident — the auto-read policy was explicitly decided (QA Q22).
- **Decision (corrected 2026-06-30):** The scratchpad is the team's **always-current shared comms channel** — every agent **auto-reads** it (reversing the old explicit-send-only policy). Delivered as a **per-agent delta off a read watermark** so context stays bounded: each agent keeps a last-read pointer into the append-log and receives only **new posts past that pointer**, which then advances (the **same watermark mechanism as OD-06** shared-context). Prior history is **not** re-sent — it already sits in the agent's own transcript; the agent actively "sees" only what's new.
  - **Live mid-run push (option b — chosen):** new posts are pushed to **running** agents **mid-run**, injected at the next tool boundary via the **OD-02 hook channel** (PostToolUse `additionalContext`, Stop-hook backstop), as **passive context that does not trigger a turn**. This is the point: an agent learns *while working* that a peer just touched the same area — an **early collision signal**. *(Rides the OD-02 inject hook — the same spike-gated path as Inject/Plan/Decision. **Fallback:** if that hook doesn't prove out on the installed build, delivery degrades to **start-of-run** injection — no hook needed — so the feature can't get stuck.)*
  - **Idle agents catch up at run-start:** mid-run push only reaches agents currently in a turn; an idle agent has no tool boundary, so it picks up everything past its watermark **when it next runs**. Net: live push to the running, start-of-run catch-up for the rest — one watermark, two delivery moments.
  - **First run = full board:** with no watermark yet, an agent's first read delivers the **entire current scratchpad** (full snapshot), then deltas thereafter.
  - **Includes the agent's own posts** in its delta — so it sees its notes **positioned in the shared timeline** relative to peers. (Reading never emits a post, so there's no echo loop.)
  - **No delta cap:** always the full diff since last read, however large — deliberately **not** managed in v1 (revisit a cap/rollup only if it proves necessary).
  - **Write side unchanged:** agents **post** via the append API with per-post **attribution** + timestamp; posts carry `recipients:[scratch]` (OD-22). **Storage** = `<project>/.awl/scratchpad.md` (OD-23), WSL-reachable; same Windows↔WSL2 path-normalization as Attach (OD-16).

### OD-18 · Settings writes + account/usage — `OPEN`
- **Question:** reads are built. Decide: **gated writes** (enable/disable toggles, confirm-gated global edit); surfacing the **account band** (email/org/plan — local & readable); and the **usage limits band** (session/weekly % + resets) which is **API-only, not in local files** — fetch it live or omit? Plus **Setups** save / load-spawn-many (tab-less) store.
- **Source:** coverage-map Settings; Part-4 report.
- **Recommended:** build **gated writes** (toggles + confirm-gated global edit) and surface the **account band** from local creds; **defer the live limits band** in v1 (it adds an API dependency for a cosmetic band) — show tier from local creds only.
- **Confidence:** ◆ Leaning — the limits-band live-fetch is explicitly "decision pending"; my lean is to defer it, but it's a real call.
- **Storage (resolved per OD-23):** the **Setups** save / load-spawn-many (tab-less) store lives in the **dashboard runtime store** (`sidecar/runtime/`, alongside identity + sessions) — reusable and **project-agnostic**, not per-project. *(A Setup carries only the roster per OD-23 — agents, roles/models/identities, links — no docs and no project baked in.)*
- **Decision:** **Make the Settings surface fully interactive — expose a write for everything the engine can actually set, read-display the rest.**
  - **Writes (the principle: if it's feasible to set, you can set it):** the Settings tabs (**Config · MCP · Plugins**) become **editable**, not view-only — toggles, add/remove/enable, and config edits write to the real Claude Code files (`~/.claude` user-global and `<project>/.claude` project scope). **Per-agent scoping** (an agent's MCP servers, plugins, tools, permission rules) is **surfaced in the Create form / Agent panel** too — today it's accepted at create but not exposed (coverage-map B6/G7). All writes are **confirm-gated** (a plain confirm, heavier for global/destructive edits) — interactive, not foot-gun-y.
  - **Feasibility boundary (marked honestly, never faked):** **mid-run permission-mode stays engine-BLOCKED** (OD-14 — launch-only); **per-agent MCP / model / plugins take effect at launch/restart**, so editing them on a *live* agent means "applies on next start," not instantly (set live where the engine allows, at-launch where it doesn't); per-agent tool scoping leans **deny-based** (`--allowedTools` is ignored under bypass — a claude bug, OD-14). Anything the engine can't change live is shown as **launch-time** or **blocked**, not as a fake-live toggle.
  - **Account band — IN:** show **email / org / plan** from local creds (readable, no API); "signed out" when creds are absent.
  - **Usage-limits band — IN:** show **session / weekly % + resets**, fetched **live from the API** (it isn't in local files). Fetch on open + a light poll; **degrade gracefully** ("unavailable") if the API/creds aren't reachable, so the new API dependency can't break the screen.
  - **Storage:** **Setups** save / load-spawn-many is already resolved → the **dashboard runtime store** (OD-23; see the Storage line above).
  - **🎨 design-layer:** the Settings tabs' write controls, the two new bands, and the per-agent Create-form controls are `design/` edits — land after the component-system refactor is confirmed done + per-item approval; the read/write endpoints behind them are backend, free to build now.

### OD-19 · Agent permanent Delete vs Retire — `DECIDED‑UNBUILT`
- **Decided:** two-tier — Retire (soft, archives config+transcript) + Delete (hard wipe, confirm-gated). v1 ships **Retire only**.
- **Open:** confirm v1 keeps Delete deferred.
- **Source:** QA Q3; build-2b.
- **Recommended:** **keep Delete deferred for v1** (Retire only, per the build-2b scope call); add Delete later as a clean confirm-gated wipe of config+transcript+links.
- **Confidence:** ▶ Confident — this was the explicit build-2b decision.
- **Decision:** **Ship both tiers in v1** — Retire **and** permanent Delete (this **changes the prior "Retire only" scope**, per the user). **Retire** stays the soft, reversible tier (stop the session + archive config/transcript; recoverable). **Delete = a hard, irreversible wipe**, governed by one rule: **wipe the agent's private footprint; tombstone everything shared.**
  - **Wipe (private, hard — scope-b):** remove the dashboard **runtime record** (`runtime_store.remove_record`), kill the live **tmux session** (`bridge.close` → `kill-session`), and **delete the agent's on-disk Claude Code transcript + its subagent transcripts** — true on-disk erasure, not just a dashboard-record removal. *(Honest note: those JSONLs are Claude Code's own data; Delete destroys them deliberately — that's what distinguishes it from Retire, which keeps/archives them.)*
  - **Available from any state:** Delete works on a running agent too — it's **interrupted + closed first**, then wiped. No forced Retire-then-Delete two-step.
  - **Gate:** a **plain confirmation dialog** (not type-to-confirm).
  - **Tombstone everything shared:** the agent's **scratchpad posts** (OD-17), **feed events/messages** (OD-01), and its **link history** (OD-08) are **kept, attributed to the now-deleted identity** and marked deleted/inactive — Delete does **not** rewrite the shared record or corrupt peers' OD-17 watermarks / OD-01 stream. Link edges become **inactive tombstones** on the surviving peer's list (non-functional), not silent removals.
  - **Clear the agent's own transient state:** its **queued prompts** + **inbox items** (its pending inbound work, OD-02/09) are dropped — moot once the agent is gone, and operational state rather than shared history.
  - **No identity recycling (ties OD-03):** the agent's **number is permanently retired** — monotonic, never reused, so an old `coder-03` living in tombstoned history never collides with a future agent. Color/icon may still cycle (they repeat by design past 16/25); the tombstone holds the retired number.
  - **🎨 design-layer:** the Retire/Delete footer already exists in the mockup — any wording/confirm-dialog tweak is a `design/` edit, held until the refactor + per-item approval; the wipe/tombstone backend is free to build now.

### OD-20 · Console surface + slash-command runner — `OPEN`
- **Question:** raw terminal feed endpoint is missing. Decide the **surface** (always-on pane vs. per-tap drawer vs. modal) and whether the slash-command **runner/routing** is in scope.
- **Reality:** screen feed is `proven` (capture-pane/scrollback); the routing table is net-new.
- **Source:** DESIGN Console; QA Q28/Q29.
- **Recommended:** a **per-tap expandable drawer scoped to one agent** (matches DESIGN's "expandable surface"), fed by capture-pane/scrollback; treat the slash-command runner as **later/optional**.
- **Confidence:** ◆ Leaning — DESIGN leans expandable-per-agent, but drawer-vs-modal is a UX call.
- **Decision:** **Adopt the Console exactly as DESIGN/mockup already specify** — the design **settled both "open" questions** (the OD-20 framing was stale); the only residue is backend wiring, not a product call.
  - **Surface (decided in design):** a **per-agent Console tab** in the Agent panel, scoped to the **single focused agent** (single-select so a command's target is unambiguous — why it lives here, not in the multi-target Prompt or multi-filter Feed), with an **Expand** control → a **partial step-into view covering left + middle columns only** (right edge stops at the right column so Team Feed + Prompt stay visible; recomputed on resize/splitter). Reflow: in-column the catalog slides up over the feed; expanded it becomes a left rail beside a wide feed with the run bar across the bottom. The feed **faithfully mimics a real Claude Code terminal** (dark self-contained `--term-*` palette — a documented `tokens.css` exception — with native `>` / `●` / `⎿` / `✻ Thinking…` / diff / permission markers). *(Not a modal, not always-on; deliberately distinct from Settings' full-body step-into.)* — DESIGN.md "Console".
  - **Slash-command runner — IN (decided in design):** a first-class part of the Console, **not** deferred. A **complete catalog grouped into clusters** (Session & context · Model & behavior · Info & status · Tools & integrations · Project & custom · System), each entry = command + one-line description, with a filter box; commands with a home elsewhere (`/model` in Details, `/mcp` in Settings) are still listed, tagged *also-available-there*. Pick → stages into the run bar; typed-or-staged → runs against the focused agent → output lands in the feed.
  - **The only open work is backend** (the mockup already tags the run bar `data-comp="console-runbar" data-status="planned"`; `runConsoleCmd` is a mock over a static `CON_FEED`): **(1)** wire the **live raw-terminal feed** — `capture-pane` / `scrollback` is already proven at the bridge, just connect it to the `console-feed`; **(2)** the **slash-command send/route** rides the bridge's existing `send` / `keys` (fire the command at the focused agent) + `capture-pane` (read output back). **Build caveat:** **interactive** commands (`/model`, `/clear`, …) drop the agent into a sub-prompt, so the runner must handle the follow-on interaction, not blind-send-and-forget.
  - **🎨 design-layer:** nothing new — the Console surface, catalog, and run bar already exist in the mockup (`data-status="planned"`); flipping them planned→built is a `design/` + wiring step held until the refactor + per-item approval. The feed/route backend is free to build now.

---

## Tier 4 — Strategic / scope
*Hold until the React-port timing is chosen; hold all `design/`-touching items until the refactor agent finishes.*

### OD-21 · Static mockup → React migration + library choice — `OPEN` (timing)
- **Question:** When does the React app get ported up to the finished mockup/tokens (it currently lags)? Trigger condition is "when design churn approaches zero." Related: do current components translate to **neobrutalism.dev**, and do we commit to one component library for maintenance?
- **Why it matters:** the refactor is design-layer only; syncing the app to it is deliberately future work.
- **Source:** spec §2/§9.
- **Recommended:** **hold the port until the design-system refactor lands and churn drops** (the stated condition); when porting, run a translation check against neobrutalism.dev/shadcn and **commit to one library** only if the current components map cleanly — otherwise keep the hand-rolled tokens/styles as the system.
- **Confidence:** ✚ Can't infer — "hold until churn→zero" is grounded, but the library commitment needs a translation spike + your maintenance preference; I won't pick it for you.
- **Decision:** **Park — not yet.** Defer the React port until **design churn reaches zero** — which is **after** the QA-doc UI changes are integrated into the mockup *and* the component-system refactor lands (per the user, churn is **not** there yet). The two coupled calls — **(a) port timing** and **(b) library commitment** (adopt **neobrutalism.dev** / **shadcn** vs. keep the hand-rolled `tokens.css` / `styles.css` system) — are a **dedicated future discussion**, gated on a **translation spike** (map a few real components onto a candidate library to see whether they fit cleanly) **plus your maintenance preference** at that point. Nothing to build now: this is the **convergence milestone** where the two parallel tracks (frontend mockup ↔ backend) finally meet, so it stays parked until both sides are stable. *(Kept in the tracker rather than deleted so the item + its trigger don't get lost — it self-surfaces when churn hits zero.)*

### OD-22 · Message addressing schema (source + recipients) — `DECIDED‑UNBUILT` (Tier 1 / cross-cutting — added later; pairs with OD-01)
- **Question:** How is every message/event tagged with **who it's from** and **who it's addressed to**?
- **Why it matters:** completes the OD-01 envelope; it's what the From/To filter, the Messages **Sent/Received** direction, link delivery, and scratch posts all read. Building it in now avoids a schema migration once linking/multi-target sends land.
- **Source:** OD-01; DESIGN "How messages read" (sender + trigger metadata already embedded) + the `recipient` mini-badge in the registry; coverage-map Prompt (From/To, P0).
- **Recommended:** stamp `source` (already provided by OD-01) **and** a typed `recipients[]`, defaulting to `[user]`.
- **Confidence:** ▶ Confident — source is settled (OD-01) and the design already implies a recipient; the default and list shape follow directly.
- **Decision:** Every message/event carries **`source`** (the OD-01 `agent_id` stamp) and **`recipients[]`** — a list of **typed** recipients `user | <agent-id> | scratch` — **defaulting to `[user]`**. Mapping: a normal agent turn → `[user]`; a user send → the To/Target selection (multi); a link fire → `[B]` (per OD-04/05); a scratch post → `[scratch]`. **`recipients` is addressed-to (routing) — it drives delivery, the From/To filter, and Sent/Received direction — NOT visibility**; every message still shows in the operator's feed regardless of recipients. Build the field now (cheap, defaults to `[user]`) so linking and multi-target sends need no later migration.

### OD-23 · Storage & scoping model — `OPEN` (Tier 1 / cross-cutting — added 2026-06-30; the storage home for OD-15/17/18, and later OD-16)
- **Question:** What is the canonical **home** for each kind of data the dashboard touches — the app's own memory, a project's docs/notes, and a reusable team — so OD-15 (Library), OD-17 (scratchpad), and OD-18 (Setups store) resolve against **one** model instead of each inventing its own location?
- **Why it matters:** 15/17/18 were all blocked on "where does this live?" Settling the tiers once removes that blocker and prevents divergent storage choices (and a later migration). The user named this as the prerequisite before OD-15 could be answered.
- **Source:** this session's storage/scoping brainstorm (dev-qa-1c); grounded against `sidecar/runtime_store.py` (the existing dashboard store) + the per-agent `cwd` model.
- **Recommended:** three homes keyed off each agent's `cwd`, with **project** data living *with the project* and **teams** reusable, living *with the dashboard*. (Matches what the user settled.)
- **Confidence:** ▶ Confident — settled directly with the user this session.
- **Decision:** **One rule — dashboard data lives with the dashboard; project data lives with the project; teams are reusable and live with the dashboard.** Three homes:
  - **🏠 Dashboard** *(its own repo + a private runtime store)* — the app plus its **memory**: per-agent **identity** records, which **sessions** exist, and saved **Setups** (rosters). Reusable, project-agnostic. *(Exists today as `sidecar/runtime/` — `sessions.json`, override `AWL_SIDECAR_RUNTIME`.)*
  - **📁 Project** *(its own repo = the agents' `cwd`)* — the code **and all its documentation, period**: `README`, `CLAUDE.md`, plans, **plus** the team's **scratchpad** (OD-17) and the **plan-review side-store** (OD-15). Dashboard-owned project data sits in a small **`<project>/.awl/`** folder inside the repo, so it **travels with the code** and is **WSL-reachable** (the agents can read it). Nothing project-specific leaks up into the dashboard store.
  - **👥 Setup** *(a reusable team — a dashboard concept, not a folder)* — **only the roster**: which agents, their roles/models/identities, and the **links** between them. **No docs, no project baked in.** Saved once to the dashboard store, then **loaded onto whatever project** you point it at. (The "reuse agents" wish.)
  - **Claude Code's own config** (`~/.claude/`, `<project>/.claude/`) is **surfaced, not owned** — the dashboard reads/edits it **in place** (Library Documents, Settings → Config); it doesn't store it.
  - **Tie-breaker for fuzzy cases:** *is this thing about the **project**, or about the **team/tool**?* Project → `<project>/.awl/`; team/tool → dashboard store.
  - **Code keys off `cwd`, never a fixed path.** Each agent's `cwd` = its project root; the dashboard treats that as the project home regardless of where it physically sits — so the physical location is free to change with **no** rearchitecting.
  - **Dev-time arrangement (footnote):** for now, dev projects live under a **`projects/`** dir **in this repo** (gitignored; each graduates to its own git repo at release). Agents reach them via the `/mnt/c/...` WSL mount — the existing Windows↔WSL path translation covers it (slightly slower than a native WSL path, fine for dev). "Move to a new repo at release" is then just a **different `cwd`** — the logical model is identical. *(DEVLOG header already notes "Projects under `projects/` maintain their own logs.")*

---

## Recommended resolution sequence
1. **Lock Tier 1** (OD-01/02/03) — load-bearing; collapses much of Tier 2/3 into easy builds.
2. **Then the linking contract** (OD-04 first, then OD-05/06).
3. **Then Tier 3 by appetite** — independent; Inbox (OD-09) and Library (OD-15) carry the most net-new design.
4. **Hold Tier 4** until React-port timing (OD-21) is chosen; hold all 🎨 items until the refactor lands.
