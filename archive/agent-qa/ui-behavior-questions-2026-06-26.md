# UI Behavior — Open Questions (pre-backend) · v4

**Date:** 2026-06-26
**Supersedes:** `.scratch/ui-behavior-questions-2026-06-25.md` (v3). Same purpose, reworked against the **`design/TODO.md` "Next up"** queue (items 1–19) on the assumption that **all of those edits land** — plus the link-behavior refactor (`dev/prompts/link-behavior-refactor.md`, P0–P4) that v3 already folded in.
**Scope:** `design/mockup.html` + `design/DESIGN.md` + `design/tokens.css` + the "Next up" snippets under `design/ui-snippets/` + the backend seam (`sidecar/` + `bridge/`).
**Goal:** Lock down the **runtime behavior contracts** the backend must honor, before backend build starts — the behaviors a static mockup can't show, where it currently fakes them or the docs are silent.

> **What's new in v4.** This pass assumes the **"Next up"** batch is built (square agent cards, the Response popover, the Turns/Context dropdowns, the contiguous Messages rail, feed-card selection parity, divider/badge/icon polish, the universal mic, End-After losing "Time", etc.). Most of those are **presentation** and don't move a backend contract — but five introduce genuinely new runtime contracts, surfaced as a **new Section B (Agent-card live readouts & subagents)** plus **Q27 (Response settings)**: the **square card's Run-strip %**, its **live-activity Marquee**, the **subagent badges' status/click**, the **Opus Fast-Mode semantics**, the **per-turn Context attribution**, and the **Response popover's Style/Behavior/Pace levers**. The **Turns dropdown** sharpens Q4 (a by-tool breakdown needs a data source). Three existing questions absorbed Next-up wording: **Q14** (End-After is now **Turns/Tokens**, Time removed), **Q26** (Scratch/Log/Inbox cards are now **attachable**, so the Embed/Attach materialization contract widens), and **Q30** (Output-Export extends Copy). Renumbered cleanly to **33** across **9 sections (A–I)**. An **adversarial pass against the live `sidecar/`+`bridge/`** then widened five questions with *adjacent* contracts they'd taken as given — the per-agent **Max-turns / Context-% caps** (Q5a), the **Total-scope context categories + the Compact action** (Q11a/c), the **per-message Active/Complete/Failed status** (Q1), and the **Log event taxonomy** (Q32b) — and corrected a few overstated confidences (Q12/Q14 downgraded; Q10's driver wording fixed). What today's backend actually does vs. doesn't is summarized in the **Backend-reality check** just below.

## How to answer — and how this version differs

**This version pre-fills my answer.** You asked me to indicate, per item, **what I assume is correct where I can infer it at all**. So each question now carries an **`Assumed:`** line — my inferred answer plus the basis for the inference and a confidence read:

- **▶ Confident** — the design docs / refactor / snippet effectively decide it; I'd proceed on this unless you say otherwise.
- **◆ Leaning** — a reasonable default, but a real fork exists; worth a glance.
- **✚ Can't infer** — genuinely your call (or pending a fact I flag); I give a lean but wouldn't build on it unprompted.

Reply only where you differ — e.g. "Q12 → B, Q17 open, rest as assumed." Where you confirm an assumption it gets folded into `DESIGN.md` so it's documented before backend work. **Bold** in the options is still the same recommendation the `Assumed:` line points to.

## What's deliberately excluded

- The **prior 18-question audit** (`.scratch/mockup-behavior-audit-brief.md`) — answered + built in the 2026-06-24 wiring pass.
- **UX/visual decisions the refactor or "Next up" already settle** — these are *design* calls, not backend contracts, so they're out of scope here even though they're being built: divider recolour (TODO 8), agent-badge sizing (19), file-type nav icons / no-trash (18), feed timestamp alignment (10), jump-to-end pills (3, 12), the Attachments heading (16), tab-badge teal (17), the Messages contiguous-rail restyle (7), the Plans/Documents editor-rail + layout (4), feed-card selection *parity* mechanics (9 — its one backend ripple lands in Q26), the panel-size drag readout (15), and the Response popover's *layout* (2 — its backend ripple is Q27).
- **Voice/dictation** — the mic moving to a universal footer control (TODO 13) is built, but the actual **dictation backend stays backlog B5**; still excluded.
- Items parked in the **backlog** (`design/TODO.md` A–D): link edges (B17/C7-graph), the attachment-clipboard *mechanics* (B-notes), transcript-payload source (C6), tasks (C1), the Review/Inbox *formalization* (explicitly deferred to **B13** by the refactor — surfaced once, at Q20, since the data model should anticipate it).

> **Backend-reality check (how far today's `sidecar/`+`bridge/` is from these contracts).** This doc was cross-checked against the live backend seam so you know what's already there vs. net-new. **Confirmed present:** the session status enum `connecting / idle / running / error / closed` (`sidecar/main.py`), `pending_permission` + binary approve/deny, a fire-now `send` (409 if running, no queue), `/interrupt`, per-session SSE, and `derive_context_usage()` returning a single **aggregate** token figure. **Confirmed absent / net-new** (so several `Assumed:` lines describe *intended*, not current, behavior): **Fast-Mode is unimplemented on both drivers** (the sdk driver doesn't advertise `set_fast`; the bridge driver's `set_fast` is a deliberate no-op — Q10); the **two drivers count turns differently today** — the sidecar reads the SDK's `num_turns`, the bridge counts user-prompt *rounds* (Q4); there's **no `max_turns`/Context-% cap field** in session state (Q4/Q5); **no `AskUserQuestion` / plan-mode / stall / scratchpad / subagent(Task) handling** exists yet (Q9, Q16, Q21); and the context feed is **uncategorized** (Q11). None of this changes the recommended answers — it just marks which contracts are greenfield.

---

## A. Agent lifecycle & state

**1. Status-state mapping (card vs the Error type), now on the square card.** The Team Graph card is being rebuilt as a **fixed square** (TODO 5) whose status badge renders **active / idle / pending** (the snippet's four demo cards cover exactly those three). The sidecar tracks `connecting / idle / running / error / closed`, and the refactor adds a first-class **Error** Inbox type (API/model · Tool/MCP · **Environment/connection** incl. *bridge tmux dropped / SDK session lost* · Config · Stalled). So the Inbox surfaces errors, but the square card still has **no error/connecting state**.
- A) **Reconcile: add `connecting` (spawn-in) and `error` (danger) states to the square card's status badge, so an Error Inbox card also flips its agent card to `error`; the card's pending/attention badge jumps to that Error card. The Run-strip (Q7) keys off the same status (error → danger or empty).**
- B) Errors live only in the Inbox/Messages, never on the card.
- C) Reuse `pending` (warning tone) for errors too.

`Assumed:` **A** — ▶ Confident. DESIGN already makes the badge a jump-shortcut and ties a Pending badge to the Inbox; the new card's status-keyed Run-strip wants a defined error state too. Backend must say which states the card renders and how `error`/`closed` map to the Inbox Error type. **One status model, three surfaces:** the *same* signal also drives the **Messages feed's per-message badge** (**Active in-flight / Complete / Failed**) — and a **Failed** message is the same wire that raises the agent's **Error** card (Q6). So "what flips to error" must be defined once and rendered on the card, the Inbox, *and* the message stream consistently.

**2. What "pending" actually counts.** Pending = "waiting on you." Strictly *any open Inbox item* for that agent (Permission/Plan/Decision/Error), or also a stalled/timed-out run? *(Status-color rework: Error owns danger; pending/attention moved off danger so they don't collide.)*
- A) **Pending = exactly one open Inbox request for that agent, of any type (the binary model DESIGN states); a Stalled run becomes an Error card, so it counts via the Inbox, not a separate signal.**
- B) Pending also fires on a hung/timed-out run independent of any Inbox card.

`Assumed:` **A** — ▶ Confident. DESIGN is explicit that an agent blocks on one thing at a time and the badge is binary; the refactor routes stalls into Error cards, which makes "pending = an open Inbox item" closed-form.

**3. Retire semantics.** Retire "ends the session" and greys the card. Does the agent's session and history persist?
- A) **Retire kills the live session (tmux/SDK process) but archives its config + transcript so it can be reloaded later (ties to backlog B3 "Load Past Agents"); the greyed card stays until reload, then drops from the roster.**
- B) Retire is a hard delete — nothing persists.
- C) Retire just detaches (session keeps running headless, can re-attach).

`Assumed:` **A** — ◆ Leaning. Fits B3 ("Load Past Agents") and the Scratch note about reusing an agent's *config* as a "project". The only wrinkle: whether the **transcript** is archived too or just the config — I assume both, but flag it (see Q31's Setup-vs-snapshot distinction).

**4. Definition of a "turn" + the new by-tool Turns breakdown.** The `Turns 34/50` bar, the Max-turns auto-stop, *and* the new **Turns dropdown** (per its snippet `turns-dropdown.html`, which TODO 1 points at — a by-tool aggregate: Read/search · Edit/Write · Bash · MCP · Subagent · Web · **Coordinating**, plus a **Remaining** slice against the cap) all depend on a turn definition, a per-tool data source, *and* the per-agent Max-turns cap that supplies the `/50` and "Remaining" (see Q5(a) — that cap has **no backend representation today**). CC / the SDK count turns in their own way.
- *(a) Turn unit.*
  - A) A turn = one user-prompt → full-response cycle (a "round").
  - B) A turn = each assistant message (so one prompt can advance several turns).
  - C) **Adopt the SDK's `num_turns` verbatim, even if unintuitive.**
- *(b) By-tool breakdown source.* Where do the dropdown's per-tool slices come from?
  - A) **Sidecar categorizes `tool_use` events from the session transcript into the fixed buckets; "Coordinating" is dashboard-derived (scratchpad posts + link/check-in events, which no single-agent tool exposes). Demo-only until the transcript feed is wired.**
  - B) Pull a native per-tool counter if the SDK/CLI exposes one; else don't show the breakdown.

`Assumed:` **4a → C, 4b → A** — and 4a **corrects the long-standing "round" assumption** (v3/the prior audit assumed A). Per the **Agent SDK docs** (external), **`num_turns` counts *agentic iterations*, not prompt→response rounds** — one user prompt can advance several turns (tool-call → result → next tool-call), and `max_turns` enforces the auto-stop on *that* unit. So the card's `34/50` and the Max-turns Lifecycle stop (Q5) **must** count SDK turns, or the bar lies about when the agent will actually halt. **Important repo wrinkle:** the two drivers already disagree — the sidecar reads the SDK's `num_turns`, but the **bridge driver currently counts user-prompt *rounds*** (`bridge.py`). So this isn't just a labeling choice: adopting the SDK unit means **changing the bridge's turn-count to match**, or the same `34/50` means different things on different drivers. The cost is intuitiveness (`34/50` reads as "rounds" to a human), so the UI should label/hover-explain it as agentic steps. 4b is ▶ Confident: transcript `tool_use` events are the only honest source, and "Coordinating" is necessarily a dashboard concept.

**5. Auto-stop limits (Max turns / Context %) — where they're stored, and what happens on hit.** *(Refactor vocabulary: a reached limit is **Lifecycle**, explicitly **not** an Error. Graceful wind-down *design* is backlog B19 — this is the baseline.)* Two contracts:
- *(a) Where the caps live.* The Turns bar's `/50` + "Remaining" (Q4) and the auto-stop both read a per-agent **Max-turns** value (and a **Context-%** ceiling) — but **session state has no `max_turns` field today** and there's no create/edit endpoint for it. Where are these per-agent Lifecycle caps stored, set (Create + the always-editable Lifecycle band), reported in the session payload, and enforced?
  - A) **Per-agent caps stored on the session, set on Create + live-editable in the Lifecycle band, reported in the session payload, and enforced by the sidecar's run loop (so the cap is the same number the bar shows).**
  - B) Caps are UI-only hints for v1; no real enforcement (the bar is cosmetic until the run loop honors them).
- *(b) On hitting a limit.*
  - A) **Finish the in-flight turn, then halt the agent into `idle` and drop a Log + (Lifecycle-flavored) Inbox item ("hit Max turns — resume?").**
  - B) Hard-stop immediately (interrupt mid-turn).
  - C) Soft warning only; don't actually stop.

`Assumed:` **5a → A, 5b → A** — ▶ Confident on 5b ("finish the turn, then halt to idle" is the only reading consistent with Lifecycle-not-Error and resumability). ◆ Leaning on 5a: A is the honest target (a cosmetic bar that doesn't actually stop the agent is a trap), but it's genuinely net-new backend — flagged because the snippet hardcodes `50` and nothing in the sidecar produces or enforces it yet.

**6. Error detection, classification & retry.** The refactor makes a failed run a first-class **Error** Inbox card (**Retry · Dismiss · Reply**), with **Retry = re-issue the last command via the Editor** (manual), and a fixed boundary (auto-stop limit = Lifecycle; stall/no-progress timeout = Error "Stalled"; model refusal = not Error). Two backend contracts remain:
- *(a) Detection & classification* of each subtype — who owns it? (a 529/rate-limit from the API response, *bridge tmux dropped* from the bridge driver, *Stalled* from a no-output watchdog.)
- *(b) Auto-retry?* The earlier `0 retries left` meta implied an automatic retry layer; the brief's Retry is purely the manual Editor re-issue.
- A) **Sidecar owns detection+classification from driver signals + a stall watchdog; *no* silent auto-retry — every error surfaces as an Error card with a manual Retry (drop the `retries left` meta).**
- B) Add a small auto-retry layer for transient API/connection subtypes (N attempts) before surfacing; manual Retry for the rest.
- C) Per-agent config for both retry count and stall timeout (Lifecycle knobs).

`Assumed:` **A** — ◆ Leaning. The refactor's "everything routes through the Editor / manual Retry" through-line and dropping the `retries left` meta point at A. B is defensible for transient 529s; if you want resilience over transparency, say so and it becomes B.

---

## B. Agent card — live readouts & subagents *(new in v4 — driven by TODO 5 + 6)*

*The square-card redesign (TODO 5) and the Context turn-scope select (TODO 6) introduce live readouts the static snippet fakes with demo data. The snippet itself calls four of these **open decisions to settle with you** — they're backend contracts, not just visuals.*

**7. Run-strip progress % — what feeds it.** The square card's **Run strip** is a textless bar that keys off status (active → green · pending → warm · idle → muted) with a **barber-pole indeterminate** animation for "working, % unknown." A real percentage needs a source; the snippet floats **plan-step k/n · turns-vs-max · phase count** and calls it undecided.
- A) **Layered: show a determinate % from plan-step k/n when the agent is executing a known plan; else fall back to turns-vs-max (always available from Q4); else (working, no quantifiable progress) run the indeterminate barber-pole. One field on the card-state payload: `{progress: number|null}` (null → indeterminate).**
- B) Turns-vs-max only — simple, always available, never fake-precise.
- C) Indeterminate-only for v1; no numeric % until a reliable source exists.

`Assumed:` **A** — ✚ Can't infer firmly (TODO 5 marks this an explicit open decision). My lean is A because it degrades honestly, but the choice between "layered" and "turns-only" is yours; the backend contract is just the single nullable `progress` field either way.

**8. Marquee live-activity feed — what stream drives it.** The card's **Marquee** scrolls "the agent's current activity as one line," static+muted when idle. That's a per-agent live string the backend must emit.
- A) **The latest activity line from the same per-session event stream that feeds the Console/Messages — i.e. the current tool call / action ("Editing main.py", "Running pytest", "Thinking…") summarized to one line; when idle, freeze on the last action or a muted "idle".**
- B) A purpose-built status string the agent itself emits (ties to the Scratch note about agents posting "clear status updates" / a status bar) — richer, but needs an agent-side convention.
- C) Reuse the Log stream's most-recent event for that agent.

`Assumed:` **A** — ◆ Leaning. A is the zero-new-contract option (it reuses the event stream the Console already needs). B is the more interesting product direction but depends on a future agent-side status convention (Scratch "check-in schema" note) — so A for v1, B as the upgrade path.

**9. Subagent badges — available info, live status, and click action.** The card reserves a fixed **subagents** row of clickable badges with agent-colour numerals. TODO 5 leaves three things open: *(b)* how to encode a subagent's working/idle **status** on a badge, *(e)* what **clicking** one does, and (Scratch) "what subagent info do we want access to."
- *(a) What's exposed.* What does the backend actually know about a subagent (Task tool spawn)?
  - A) **Model subagents from `Task`-tool spawns: count + label + a coarse running/done state (running while the Task call is in flight, done when it returns). Rich live internals (a subagent's own tool stream) are *not* assumed available.**
  - B) Assume full live status per subagent (treat each like a first-class agent).
- *(b) Click action.*
  - A) **Click opens a small read-only subagent detail (label · state · last action) as an anchored popover — no full panel, no separate identity.**
  - B) Click focuses/scrolls the related parent context; no detail surface.
  - C) Inert for v1 (badges show identity/count only).

`Assumed:` **9a → A, 9b → C-then-A** — 9a is ▶ Confident on the *ceiling* (per CC/SDK docs, external): subagents are **opaque until the `Task`/`Agent` call returns** — the parent sees only the final result, no live status, no enumeration; even first-party CC UI shows just "Running agent… 2m34s ↓2.2k tokens." So the honest most-you-can-do is **count + label + a coarse running/done** (running while the Task call is in flight, done when it returns), inferred from the `tool_use` block + its completion. Rich per-subagent internals are *not* available — don't design for them. **Net-new caveat:** the current sidecar/drivers model **no** subagents at all (no Task detection), so even this coarse running/done is greenfield work, not a read of an existing signal. 9b (the click action) stays ✚ Can't infer (TODO 5 calls it explicitly undecided): I'd ship **C** (inert) for v1 and grow to **A** (a coarse read-only popover — that's all the data supports) once you decide it's worth surfacing.

**10. Opus Fast-Mode (`/fast`) semantics — and does it override Effort/Think?** The square card shows an **opus-only FAST bolt**, and the snippet's card A **proposes greying Effort + Think when FAST is on** ("FAST override") — explicitly pending "the real semantics of what FAST controls." This is a behavior contract: what does Fast-Mode actually do, and is it orthogonal to the Effort tier and Thinking toggle?
- A) **FAST is orthogonal (a latency/throughput mode) — it does *not* disable Effort or Thinking; keep both live, drop the proposed greying. The card just shows the bolt; Effort/Think chips stay active.**
- B) FAST overrides — greying Effort/Think is correct because Fast-Mode forces a minimal-deliberation path.
- C) Park it: render the bolt, but don't wire any cross-control gating until the real `/fast` semantics are confirmed.

`Assumed:` **A** — now ▶ Confident (verified). Fast-Mode is a real **API throughput setting** (`speed:"fast"` + the `fast-mode` beta header on Opus 4.6+), delivering up to ~2.5× output-tokens/sec — *"the same model with a faster inference configuration; no change to intelligence or capabilities."* It is **orthogonal to both Effort (reasoning/token budget) and extended Thinking** — they're independent, composable axes (you can run High-effort + Fast, or Deep-thinking + Fast). So **drop the proposed greying** (the snippet's card-A "FAST override" is wrong): keep Effort + Think live when FAST is on; the card just adds the bolt. Two notes: (i) it being opus-only is correct (fast mode is an Opus feature); (ii) **it's unimplemented on both drivers today** — the **sdk** driver doesn't advertise `set_fast` (the intended wiring is to pass `speed:"fast"` via `ClaudeAgentOptions` once added), and the **bridge** driver's `set_fast` is a deliberate no-op (the CLI's `/fast` opens an interactive panel that can't be scraped reliably). So Fast-Mode is net-new on the sdk path and may stay **inert on bridge** until the CLI exposes it non-interactively (like Inject in Q23).

**11. Context breakdown — what the backend must feed it (Total-scope categories · per-turn attribution · Compact).** The Context accordion isn't one feed — TODO 6's turn-scope select sits on top of the existing breakdown, and today `derive_context_usage()` returns only a **single aggregate token number**. Three contracts:
- *(a) Total-scope category breakdown + loaded-context inventory* (net-new). The breakdown splits the window into **System prompt · System tools · MCP tools · Custom agents · Memory files · Messages**, and the two sub-sections enumerate **which memory files** and **which custom-agent defs** are loaded with their sizes. Who computes this categorization + inventory?
  - A) **The sidecar reads the session's loaded context and buckets it into the fixed categories + the file/agent inventory — a real per-category feed, not just `sum(usage)`. Demo data until wired.**
  - B) Approximate categories client-side from known fixtures; only the grand total is real.
- *(b) Per-turn attribution* (TODO 6's `Turn n` scope). Where do per-turn token contributions come from?
  - A) **From per-message `usage` in the transcript/stream, summed within each turn; the two-denominator design (header = share of window, rows = share of turn) is presentation, not two feeds; the Memory/Custom-agents sub-sections are scope-invariant (loaded context, not per-turn). Demo data until wired.**
  - B) Only Total is real for v1; per-turn is mock-only indefinitely.
- *(c) The Compact action* (the context bar's dedicated **Compact** button, distinct from typing `/compact` in the Console — Q29). It mutates the live window, so it's a **state-changing op with a readout-refresh** contract.
  - A) **Compact invokes `/compact` on the driver; on completion the sidecar re-derives the context feed and the bar/breakdown drop to the post-compaction window.**
  - B) Compact is a Console-only command for v1; no dedicated button.

`Assumed:` **11a → A, 11b → A, 11c → A** — ▶ Confident on the **sources** (categories + inventory must be computed by the sidecar; per-turn comes from per-message `usage`; Compact must round-trip and refresh), ◆ on **timing** (demo-now, real-later is fine for a/b). Verified nuances: the SDK's *aggregate* `ResultMessage.usage` doesn't break down by turn, but the JSONL `message.usage` carries **per-message** input + cache tokens (output_tokens is present too); the **bridge already parses `message.usage`** — but only for a *cumulative* figure today (it sums the latest entry, not per-turn), so per-turn attribution is a **new aggregation** over an existing field, and the **category breakdown is an entirely new feed** (nothing categorizes context today). The "don't reconcile the two denominators" line in TODO 6 is a UI rule, not a backend one.

---

## C. Inter-agent linking & context-sharing

*(The refactor reserves **"Link" for inter-agent links only** — content-sharing moved to Embed/Attach, Section G. These four remain open and largely untouched by "Next up" — except Q14 absorbs the End-After change.)*

**12. What event *fires* a link.** DESIGN says a link "forwards context from A to B," but never says *on what trigger*. The single biggest undefined contract.
- A) **A link fires when the source agent finishes a turn (goes idle) — its latest output is forwarded per the Trigger timing.**
- B) Fires only when the source posts to Scratch / emits an explicit "handoff" marker.
- C) Fires continuously/periodically (the backlog B12 "dynamic doc" model — defer).

`Assumed:` **A** — ◆ Leaning (the draft itself calls this the single biggest undefined contract, so I won't overstate it). Honest basis: turn-completion is the most natural source-fire trigger, but it's an *inference*, not a decided fact — DESIGN's Trigger table (Now/Inject/Next/Queue/Hold) only governs **target-side delivery timing** and is silent on *when the source fires*. B (fire on an explicit handoff marker) is the real alternative if you'd rather links be deliberate than automatic-on-every-turn.

**13. What "Message" payload captures.** Payload = Message/Transcript/Manual. (Transcript's source is backlogged, C6.) For **Message**, which text exactly?
- A) **The source's final assistant message of the just-finished turn, forwarded as one rendered message.**
- B) The full turn including its tool calls/results.
- C) A summary the dashboard generates.

`Assumed:` **A** — ▶ Confident. DESIGN literally defines Message as "the source's output, forwarded as a single rendered message"; tool-call inclusion is the Transcript payload's job.

**14. Bidirectional turn-taking (A↔B), with End-After now Turns/Tokens.** With both directions on, what stops infinite ping-pong beyond the End-After caps? *(Note: TODO 14 removes **Time** from End-After — it's now **Turns / Tokens** only. Update DESIGN's Linking table to match.)*
- A) **Strict alternation: each side only fires after the other goes idle (one in flight at a time); End-After (Turns / Tokens) is the hard backstop.**
- B) Free-running both ways, relying entirely on End-After.
- C) Every forwarded message requires a Hold/manual release.

`Assumed:` **A** — ◆ Leaning (confidence inherited from Q12's "fire on idle" premise, which is itself an inference — so no firmer than Q12). Strict alternation falls out *if* sides fire on going idle. The End-After edit is mechanical and fully grounded: drop Time, keep Turns/Tokens (and update DESIGN's End-After table, which still reads "Turns / Time / Tokens").

**15. The "Hold" relay surface.** Hold (a link Trigger) = stage a forwarded message for your manual release. The refactor fixes the Inbox at four typed sections — Permission · Plan · Decision · Error — none of which is a held-relay, and establishes "everything routes through the Editor."
- A) **Route a held relay into the Editor as a pre-filled `embed` block targeted at the receiver — consistent with the Editor-routing model (Reply/Retry already do this).**
- B) Add a 5th **Relay** section to the Inbox (release / edit / drop).
- C) Surface holds in the Console/Log only.

`Assumed:` **A** — ◆ Leaning. A keeps the Inbox at its four refactor-fixed sections and reuses the `embed` primitive + Editor through-line. B is cleaner conceptually (a held relay *is* an awaiting-you item, like the Inbox's whole purpose) — so if you'd rather Holds live in the Inbox, it's B. Worth your eye.

---

## D. Approvals / Inbox

**16. How each Inbox type is *raised* (three map to native CC surfaces; one is system-detected).** The refactor pins the types down:
- **Permission** = native permission prompt (sidecar already has `pending_permission`).
- **Decision** = the native **`AskUserQuestion`** tool — one question + options per card; pick + Approve.
- **Plan** = a native plan (plan mode / ExitPlanMode); Inbox card is **review-only** (Review + Reply) — approval + agent-review verdicts live in the Plans tab.
- **Error** = system-detected (Q6), not agent-raised.

Residual contracts:
- *(a)* Confirm the sidecar **intercepts `AskUserQuestion` tool-calls** ↔ Decision cards and routes the picked option back as the **tool result**.
- *(b)* **How a Plan card is raised** — how does the dashboard learn a native plan is "awaiting review" and which agent owns it? (ties to Q18.)
- A) **Yes to (a); for (b) the sidecar watches plan-mode exits / new `~/.claude/plans/*.md` and ties each to its authoring session (Q18's side-store).**
- B) Decision/Plan are dashboard-operator constructs, not agent-raised, for v1.
- C) Keep Permission + Decision(`AskUserQuestion`) for v1; defer agent-raised Plan cards.

`Assumed:` **A** — ▶ Confident. The refactor explicitly names `AskUserQuestion` as the Decision surface and plan-mode as the Plan source; A just states the interception mechanics those imply.

**17. "Always allow" scope & persistence.** Clicking Always-allow on a permission card writes what rule, where?
- A) **Allow that tool+command pattern for *this agent's session* only (in-memory, gone on retire).**
- B) Persist it to the project `.claude/settings.json` allow-list (affects future agents too).
- C) Per-agent, but persisted with the agent's saved config/setup.

`Assumed:` **A** — ◆ Leaning, and the one I'd most want you to confirm. Session-scoped is the *safe* default (a click can't silently widen permissions for future agents), but **native CC "Always allow" actually does B** (writes to settings). If you want dashboard Always-allow to match CC muscle memory, pick B; if you want ephemeral agents to stay sandboxed, A holds. C is the tidy middle if Setups (Q31) persist per-agent permission grants.

---

## E. Plans review *(plans are native CC `~/.claude/plans/*.md`; the review layer is a dashboard invention)*

**18. Plan↔agent mapping + where review data lives.** A plan file has no notion of owning agent, verdicts, or comments — yet the Library shows owner badges, Approve/Revise/Block tallies, and multi-agent feedback, and the refactor moves **all** plan approval + agent-review verdicts into the Plans tab (so the side-store carries even more).
- A) **Sidecar maintains a side-store (small DB/JSON) keyed by plan filename: owner agent, state, all comments/verdicts; edits to the plan body write back to the `.md`, but review metadata never touches the file.**
- B) Embed review metadata in the `.md` itself (frontmatter/HTML comments).
- C) Review metadata is ephemeral (lost on reload).

`Assumed:` **A** — ▶ Confident. A plan `.md` can't carry owner/verdict/comment data without corrupting it as a native CC artifact; a filename-keyed side-store is the only clean option, and the refactor piling more review data into the Plans tab makes ephemerality (C) a non-starter.

**19. Approve/Reject → the paused agent (now Plans-tab-only).** The refactor strips Approve/Reject from the Inbox Plan card (Review + Reply only); all plan approval happens in the **Plans tab**. The underlying contract is unchanged: when you Approve in the Plans tab, what does the authoring agent do?
- A) **Approve resumes the agent out of plan mode into execution; Revise sends the flagged sections back as a new prompt; Reject ends the plan and notifies the agent. (Requires the agent parked in plan mode awaiting the verdict.)**
- B) Approve is informational only — you still manually prompt the agent to proceed.

`Assumed:` **A** — ◆ Leaning. A is the intended "route control through the GUI" behavior and matches plan-mode's resume-on-approval semantics. The dependency to verify: the authoring agent must actually be **parked in plan mode** awaiting the verdict (vs. having moved on) — if agents don't reliably park, A degrades toward B.

**20. Cross-agent plan review routing (acknowledged direction; formalization deferred to B13).** The refactor restyles the Plans **Review** control to a **single-agent reviewer select** (P4c) as groundwork for a single-reviewer model, but explicitly **defers** the workflow to TODO **B13**. Worth confirming the intended *eventual* shape so the data model anticipates it.
- A) **Review hands the plan to one reviewer agent as a structured task; its verdict returns as a Feedback entry in the Plans tab; the human keeps the final Approve/Reject gate.**
- B) Agent reviewers are advisory only; never gate.
- C) Leave fully deferred — don't model reviewer agents yet.

`Assumed:` **A (as the eventual shape; build C now)** — ◆ Leaning. A is the direction P4c builds toward and what the side-store (Q18) should anticipate (a `reviewer`/`verdict` field). But since B13 defers the *workflow*, the only thing to do now is make sure the data model has room — so model for A, implement C.

---

## F. Shared scratchpad

**21. Storage + attribution mechanism.** The mockup writes `~/.claude/shared/scratchpad.md`. A raw `.md` can't carry per-post "agent + timestamp" attribution, yet the Scratch tab shows both.
- A) **Posts route *through the sidecar* (an append API) which stamps agent + time and keeps the structured post log; it also materializes a plain `scratchpad.md` agents can read. Agents post via a known mechanism (a slash command / tool the sidecar intercepts).**
- B) Agents write the file directly and the dashboard parses a strict per-line format for attribution.
- C) Scratch is dashboard-internal only; agents don't actually read/write a real file yet.

`Assumed:` **A** — ▶ Confident. Attribution + a clean materialized doc both require a write path through the sidecar; direct-file (B) can't reliably carry per-post identity.

**22. Do agents auto-read the scratchpad?** Or is it write-only from their side until something injects it?
- A) **Write-in / read-out is human-facing only; an agent receives scratch content only when it's explicitly sent to it (Editor → Scratch target, or a link).**
- B) The scratchpad is auto-injected into every linked agent's context on each turn.

`Assumed:` **A** — ◆ Leaning. A matches "posting in, reading out is the whole interaction for now" (DESIGN) and avoids context bloat. B is the richer "living shared doc" vision but is explicitly the deferred B12 direction — so A for v1.

---

## G. Prompt send semantics & Response settings *(Compose → Editor)*

**23. Timing (Now / Inject / Next / Queue) — server-side model.** The sidecar `send` is fire-now today; no per-agent queue or boundary detection. These four also differ in feasibility across the **sdk** vs **bridge** drivers.
- A) **Build a per-agent server-side prompt queue + turn-boundary detection so all four are real; document that `Inject` may degrade to `Next` on whichever driver can't do mid-run injection.**
- B) Implement Now + Queue for v1; mark Inject/Next as "planned" in the UI until the driver supports boundaries.
- C) Treat all four as the same immediate send for v1 (labels only).

`Assumed:` **A** — ◆ Leaning. A is the honest target (the same timing vocabulary backs links, so the queue/boundary machinery is needed anyway). If v1 timeboxes hard, B is the pragmatic step-down with truthful UI; C (labels-only) is the one to avoid — it lies about delivery.

**24. "Send as <agent>" (From = an agent).** Sending a prompt *as* an agent — literal user-style message attributed to the source, or a link-style relay with sender/trigger front-matter?
- A) **It injects into the target as a normal prompt tagged with the source agent's identity (reuses the link sender-metadata wrapping); it is not a persistent link.**
- B) It actually creates/uses a one-shot link under the hood.

`Assumed:` **A** — ▶ Confident. DESIGN frames From=agent as "sending *as* that agent for coordination," i.e. a tagged one-shot prompt, not a standing link; B would conflate it with the Link feature the refactor deliberately keeps separate.

**25. AI utility passes — Revise *and* Summarize.** Both rewrite/condense with an LLM call: **Revise** (Grammar/Language/Refactor) rewrites a prompt before send (Editor footer); **Summarize** condenses selected cards into a slide-over (Messages/Scratch/Log). Same new backend capability.
- A) **One shared sidecar "utility-LLM" endpoint runs both on a cheap fixed model (e.g. Haiku); Revise returns to the Editor for review before Send, Summarize fills the slide-over.**
- B) Route each through the currently-focused agent's own model.
- C) Defer both to post-v1 (keep the buttons inert / mock-only for now).

`Assumed:` **A** — ◆ Leaning. A (a dedicated cheap utility model) keeps these off the agents' context windows and costs little; B is simpler to wire but spends the agent's tokens/model on chores. A is the cleaner contract.

**26. Embed vs Attach — backend realization (now widened by feed-card attach parity).** The refactor collapses content-sharing into **Embed** (a frozen inline quote in the prompt body) and **Attach** (a path reference + a hardcoded "read this"; pathless content is materialized-to-temp-file-and-referenced). *TODO 9 (feed-card selection parity) means **Scratch / Log / Inbox cards are now attachable too** — all pathless — so the materialization path must cover them, not just Messages.*
- *(a) Embed* — **settled by the refactor** (a frozen, point-in-time inline quote, no liveness); a rubber-stamp confirm, not a real unknown. The weight of this question is on (b)/(c).
- *(b) Attach* → for real files inject the path; for pathless content (a message, a Scratch/Log/Inbox card, a multi-block selection, "the whole reply"), **where do materialized temp files live, what's their naming / lifecycle / cleanup**, and how is a multi-block bundle written to one file?
- *(c) Cross-agent path reachability* → an Attach from Agent A sent to Agent B must resolve from B's cwd/filesystem (incl. the WSL2↔Windows boundary and differing cwds). Who rewrites/normalizes the path?
- A) **Embed = inline text injection; Attach = path ref, with pathless content (incl. feed cards) materialized into a per-session temp dir under the sidecar's workspace, cleaned on retire; the sidecar normalizes paths to be reachable by the receiving agent.**
- B) Attach always materializes a temp file (even for real files) for a uniform, always-reachable path.
- C) Embed-only for v1; defer Attach's temp-file machinery.

`Assumed:` **A** — ▶ Confident on the shape (it's the refactor's stated mock contract); the residual *real* unknowns are exactly (b) temp-file lifecycle/cleanup and (c) cross-filesystem path normalization (the WSL2↔Windows + differing-cwd problem) — those are genuine backend design, and B is a reasonable simplification if you'd rather have one uniform always-materialized path.

**27. Response settings → runtime behavior *(new in v4 — TODO 2)*.** The reworked Response popover adds graded **STYLE** axes (Length · Altitude · Register · Structure · Emphasis) and **BEHAVIOR** axes (**Pace** · Reasoning-shown). The snippet states Pace is *"injected per-prompt,"* *"independent of the agent's Effort tier"* (Effort = how much it *can* think; Pace = how hard to work on *this* reply). So: how do these reach the agent, and are they per-send or persistent?
- A) **All Response axes compile into a compact instruction preamble attached to *that send* (per-prompt), composing with — not replacing — Effort/Thinking/Mode. The popover's values are a sticky Compose default (persist in the UI between sends) but are never written to the agent's saved config or to `.claude/settings.json`. "Reasoning shown" is likewise a prompt instruction (and/or the thinking-visibility toggle where one exists), not a separate model setting.**
- B) Map the Style axes onto a native CC **output-style** (if output styles can express length/register/structure) and inject only Behavior as prose; persist the output-style on the agent.
- C) Mock-only for v1 — the popover sets UI state but nothing is injected yet.

`Assumed:` **A** — now ▶ Confident (verified). CC **output-styles** are real but the **wrong granularity** for this: they're *session-level* Markdown system-prompt overrides (role/tone/format, set via `/config` or `outputStyle` in settings, needing `/clear` to take effect) — not per-send graded dials. So mapping the graded Style axes onto an output-style (option B) fights the feature; a **per-prompt instruction preamble** that composes with Effort/Thinking/Mode is the clean contract. Values stay a sticky Compose default (UI state), never written to agent config or `.claude/settings.json`. (If anything, only a coarse *Register* could map to an output-style — not worth splitting the model for.) The override **badge count** is pure UI.

---

## H. Console (raw terminal + slash commands)

**28. Console feed source by driver.** The Console "faithfully mimics a real Claude Code terminal." Literal for the **bridge** driver (`capture-pane`), but the **sdk** driver has no TUI.
- A) **Console is full-fidelity for bridge agents; for sdk agents it renders a reconstructed terminal-style view from the event stream (same surface, sourced differently).**
- B) Console is bridge-only — hidden/disabled for sdk-backed agents.
- C) Always reconstruct from events (never use real capture-pane), for consistency.

`Assumed:` **A** — ▶ Confident. DESIGN sells the Console as always-available raw output; B (hide it for sdk) breaks that promise, and C throws away the bridge's real fidelity. A keeps one surface, two sources.

**29. Slash-command execution & interactive commands.** The catalog runs commands against the focused agent. Many are TUI-interactive (`/model`, `/clear`, `/compact`) and some mutate state the dashboard mirrors. *(The refactor routes the Error card's **Retry** through the Editor, explicitly "not the Console"; from that I infer the Console stays reference-only for command actions — but that's my read, not a blanket statement the brief makes.)* A sharp case of "mutates mirrored state": **`/compact`** changes the live context window, so if it's run, the per-agent **Context bar/breakdown (Q11) must re-derive** — see Q11's note on the dedicated Compact button.
- A) **Run commands by sending the literal text to the agent; commands with a dashboard home (`/model`, `/compact`…) route to that control instead and just *echo* in the feed; genuinely-interactive ones are gated/queued. Define the per-command routing table.**
- B) Only run non-interactive informational commands (`/status`, `/cost`…); everything else routes to its dashboard control.

`Assumed:` **A** — ◆ Leaning. A (a per-command routing table) is the complete model the "single home for every slash command" intent wants; B is the safe subset if the routing table proves too fiddly for v1. The deliverable either way is the routing table — A just makes it exhaustive.

---

## I. History, Setups, recovery, identity

**30. History scope & persistence (+ Output Export).** History cards carry delivery states (Active/Queued/Next/Held/Complete) — the queue/delivery states that correspond to Q23's timing vocabulary (Now/Inject/Next/Queue), plus the resolved **Active/Complete** lifecycle states and **Held** (which derives from the link *Hold* trigger that Q23's Send deliberately excludes). So they overlap with Q23 without being identical. *(TODO 11, Output Export, extends the per-card Copy into select/cut/export of larger spans — mostly client-side serialization of already-loaded cards, but confirm the export target.)*
- A) **History is the per-agent prompt log derived from session events, persisted across reload/reconnect; the db-* states reflect live queue position and resolve to Complete. Output-Export serializes the selected card span to clipboard/file client-side — no new backend feed beyond what History/Messages already hold.**
- B) History is session-memory only (cleared on reload).

`Assumed:` **A** — ▶ Confident on persistence (a prompt log that vanishes on reload defeats the point), ◆ on Output-Export's target (clipboard vs file vs both is a small UX call — I assume "copy span to clipboard, optional save-to-file").

*Stop (icon-only danger in the History and Messages footers) = interrupt the agent's active run — confirm it maps to the existing `/interrupt` endpoint scoped to that agent.* `Assumed:` yes — ▶ Confident (the build settled "Stop = stop this run" in both footers).

**31. What a "Setup" captures and does on Load.** Setups save "agents + links." *(Related to the Scratch note about renaming session→project — the reusable thing is an agent's **config**, which is what a Setup should carry.)*
- A) **A Setup is a config blueprint — roles/names/models/modes/links — and Load spawns fresh, empty agents from it (no in-flight context carried).**
- B) A Setup also snapshots live context/transcript and Load restores running state.
- C) Setup = blueprint, but Load *offers* to also restore the last transcript per agent.

`Assumed:` **A** — ◆ Leaning. A matches "agents + links" (config, not state) and the session→project Scratch note (config is the reusable unit). C is the appealing upgrade (offer to rehydrate a transcript) and pairs naturally with Q3's archived transcript — so if Retire archives transcripts, C becomes the better target. Flagging the A/C fork.

**32. The cross-agent event stream — architecture, the Log event taxonomy, and crash/reconnect.** The sidecar reconnects sessions; tmux is the recovery net. The refactor's **Environment/connection** Error subtype names *bridge tmux dropped / SDK session lost* — so a dropped session has a home (an Error card). Three intertwined contracts:
- *(a) Stream architecture + recovery affordance.* The Feed/Graph/Inbox (and Section B's Marquee/Run-strip) are cross-agent aggregations, but the sidecar streams SSE *per session*. Who merges, and how does a drop surface?
  - A) **On a dropped/recovered session, raise the Error card *and* a brief "reconnecting" card state (ties to Q1's connecting/error states); expose one aggregated event stream the dashboard subscribes to (vs. the frontend fanning-in N per-session SSE streams + merging).**
  - B) Per-session streams; frontend merges; the Error card is the only crash signal (no separate reconnecting state).
- *(b) The Log event taxonomy* (net-new). The Team Feed **Log** tab is "started · committed · flagged · **link fired** · permission/approval requested…" — **dashboard-defined semantic events**, not raw transcript blocks. Many (e.g. *link fired*, *committed*, *plan raised*) no single-agent transcript emits as such, so the **sidecar must synthesize them**. What's the event vocabulary and who raises each? *(This feed underpins both the Log tab and Q8's Marquee, and rides the same aggregated stream as (a).)*
  - A) **Define a fixed Log event taxonomy the sidecar emits — lifecycle (started/idle/retired), tool/commit, coordination (link fired, scratch post), and request/error events — as the semantic layer over the raw per-session streams.**
  - B) Log is best-effort scraped from transcript markers for v1; no curated taxonomy.

`Assumed:` **32a → A, 32b → A** — ◆ Leaning on 32a (a single aggregated stream is the cleaner architecture — Feed/Graph/Inbox want one merged feed, and the Marquee/Run-strip want per-card slices off it — and it pairs with Q1's connecting state; B is viable if you'd rather keep per-session SSE and merge client-side). ▶ Confident on 32b's *need* (the Log's coordination events genuinely don't exist in any single transcript, so the sidecar has to mint them) — the open part is just the exact vocabulary, which the data model should pin down now since it's load-bearing for the Log tab, the Marquee, and the aggregated stream.

**33. Identity uniqueness past 16 agents.** "One identity per agent" rests on a 16-color jewel palette. With >16 agents, colors must repeat. *(The square card and the subagent badges both lean on the agent colour, so collisions get more visible.)*
- A) **Auto-assign the next free color+icon on Create (user can override); past 16, repeat color but force a distinct icon so the pair stays unique.**
- B) Let colors repeat freely past 16 (rely on icon + name).
- C) Cap practical fleets at 16 distinct identities.

`Assumed:` **A** — ◆ Leaning. A (color+icon pair as the unique key past 16) preserves "one identity per agent" without capping the fleet, and the icon set (167 glyphs) has the headroom. *(Visual aside, not a backend contract: the square card flags that **pale agent colours — amber/gold/citron — read low-contrast as badge text** on the subagent numerals, a TODO-5(d) token concern that may want a darker text variant. Noted here only because it rides on the same palette this question assigns; it's a styling fix, not a runtime decision.)*

---

*Source review: `design/DESIGN.md` (intent owner, already synced to the refactor target), `design/mockup.html` (P0 built; P1–P4 + "Next up" the in-flight target), `design/tokens.css`, the refactor brief `dev/prompts/link-behavior-refactor.md`, the `design/TODO.md` "Next up" queue (items 1–19) and the `design/ui-snippets/` it points at (agent-card, response-popover, turns-dropdown, context-dropdown, messages-card, plans-editor-rail), and the `sidecar/` + `bridge/` backend seam.*

> **Research note (resolved).** Four answers leaned on real Claude Code / Agent SDK semantics, now verified against the **official docs** (high confidence) rather than asserted from memory — each cross-checked against what the drivers actually do today (see the *Backend-reality check* up top):
> - **Q10 — Fast-Mode is orthogonal.** An API throughput setting (`speed:"fast"`, Opus 4.6+), *"no change to intelligence or capabilities,"* independent of Effort and extended Thinking → keep both live, drop the greying. (Unimplemented on both drivers today.)
> - **Q27 — output-styles are the wrong granularity.** Session-level system-prompt overrides (role/tone/format), not per-send graded dials → Response settings inject as a per-prompt preamble.
> - **Q9a — subagents are opaque until completion.** Parent sees only the final `Task`/`Agent` result; no live status or enumeration → coarse running/done is the ceiling. (And the sidecar models no subagents at all yet — net-new.)
> - **Q4a — a "turn" is an agentic iteration, not a round.** `num_turns`/`max_turns` count autonomous loop steps; one prompt can advance several → **corrected from the prior "round" assumption.** Note the drivers currently disagree (sidecar reads `num_turns`; bridge counts rounds), so this needs reconciling; per-turn token attribution comes from per-message `usage`, not an SDK turn-level field (Q11).
>
> Everything else stands on the design corpus (`DESIGN.md`, the refactor brief, the "Next up" queue + snippets, `tokens.css`, the backend seam).
