# UI Behavior — Open Questions (pre-backend) · v5

**Date:** 2026-06-26
**Supersedes:** `.scratch/ui-behavior-questions-2026-06-26.md` (v4). Same purpose, reworked against the **`design/TODO.md` "Next up"** queue — now a structured **cumulative change list (sections A–L)**, materially different from v4's "items 1–19" — on the assumption that **all of those edits land**. Re-grounded in a fresh code+design review of the **live** `frontend/` + `sidecar/` + `bridge/`.
**Scope:** `design/mockup.html` + `design/DESIGN.md` + `design/tokens.css` + the `design/ui-snippets/` snippets + the backend seam (`frontend/`, `sidecar/`, `bridge/`).
**Goal:** Lock down the **runtime behavior contracts** the backend must honor, before backend build starts — the behaviors a static mockup can't show, where it currently fakes them or the docs are silent.

> **What's new in v5.** Three things moved since v4. **(1) The driver decision is settled.** The **bridge** driver (real Claude Code TUI in tmux/WSL2) is now the **primary path the dashboard is built around** and is **live-verified below the UI** (run-state, permission round-trips, resume, model/effort set); the **sdk** driver (in-process Agent SDK) is the **backup / limited-use engine**, reserved for specific non-interactive tasks and selected explicitly — **bridge** is now the no-driver-named default (selection order: per-session `driver` field → `AWL_DRIVER` → `"bridge"`; an explicitly-named *unknown* driver still falls back to `"sdk"`). Every per-driver caveat in this doc is now framed **bridge-first**, with sdk as the degraded case. **(2) The "Next up" A–L list changed real contracts.** The big one is **A2 — subagent badges** now demand *three* run-states (**pending / active / idle**) **plus a stable per-subagent ID** (s1/s2), which collides head-on with the verified fact that subagents are opaque until the `Task` call returns — Q9 is reworked and its confidence cut. **A1** re-states Fast-Mode as **orthogonal** *and* adds a hard **Opus-only gate** (Q10). **H** reshapes Embed/Attach into a **link-icon dropdown** (Q26, contract unchanged). **I** turns History into a **feed-model card** with **Retry before Stop** (Q30, ties Retry to Q6). **G** generalizes **select/deselect + Output Export** to every feed and scopes **Summarize** to Messages/Scratch/Log (Q25/Q30). **L** *reverses* v4's "universal footer mic" — the mic is now **per-editor**; dictation backend still excluded. **(3) The live frontend is far behind the mockup.** `App.tsx` is a ~571-line two-pane app that touches 8 REST endpoints, of which 4 are polled (health 5s, sessions list 2s, history + session-detail 800ms); the other 4 are action calls (create/delete/send/interrupt), never selects a driver, and implements **zero** permission/model/mode/effort UI — so most contracts here are net-new *through the dashboard*, even where the bridge verifies them below the UI. What today's backend actually does vs. doesn't is in the **Backend-reality check** below.

## How to answer — and how this version differs

**This version pre-fills my answer.** Each question carries an **`Assumed:`** line — my inferred answer plus the basis for it and a confidence read:

- **▶ Confident** — the design docs / snippets / verified code effectively decide it; I'd proceed on this unless you say otherwise.
- **◆ Leaning** — a reasonable default, but a real fork exists; worth a glance.
- **✚ Can't infer** — genuinely your call (or pending a fact I flag); I give a lean but wouldn't build on it unprompted.

Reply only where you differ — e.g. "Q9 → split, Q17 open, rest as assumed." Where you confirm an assumption it gets folded into `DESIGN.md` so it's documented before backend work. **Bold** in the options is the same recommendation the `Assumed:` line points to.

## What's deliberately excluded

- The **prior 18-question audit** (`.scratch/mockup-behavior-audit-brief.md`) — answered + built in the 2026-06-24 wiring pass.
- **UX/visual decisions the "Next up" list already settles** — these are *design* calls, not backend contracts, so they're out of scope here even though they're being built: subagent-badge **footer framing** (B), the Messages **content framing** (C), **jump pills on real scrollers** (D), the **bigger expand hit target** (E), the **editor-rail navy dividers** (F), the **DESIGN.md doc patches** (J), the **dead CSS** removal (K), and the action-strip *layout* of G (only G's Output Export + Summarize touch a contract — folded into Q25/Q30).
- **Voice/dictation** — per **L** the mic moves into **each Editor header** (Compose / Plans / Documents), bound to its own field, enabled only when that field is editable. The control move is built, but the **dictation backend stays backlog**; still excluded. *(v4's "universal footer mic" wording was stale and is corrected here.)*
- Items parked in the **backlog** (`design/TODO.md` A–D): link edges (B17/C7), the attachment-clipboard *mechanics*, transcript-payload source (C6), tasks (C1), the Review/Inbox *formalization* (deferred to B13 — surfaced once, at Q20, since the data model should anticipate it).

> **Backend-reality check (how far today's `frontend/`+`sidecar/`+`bridge/` is from these contracts; bridge is the primary path).**
>
> **Bridge — the primary, live-verified driver (everything it knows comes from exactly two channels: tmux `capture-pane` screen text + the JSONL transcript, polled on a ~1.0s loop — it *samples*, it does not stream).** Verified below the UI: **screen-state detection** is an exact **4-value enum** `idle / generating / permission_prompt / unknown` (`bridge/bridge.py _detect_state`); the sidecar maps `generating→running`, `idle→idle`, surfaces `permission_prompt` as a **`permission_request`/`permission_resolved` event pair** (not a status), and emits **no** status for `unknown`. **Permission** round-trips are real but **binary** — `answer_permission` is `approve=Enter` (option 1 "Yes") / `deny=Escape`; **"always allow" (option 2) is deliberately unsupported/unverified**. **`set_model`** (`/model <name>`) and **`set_effort`** (`/effort <level>`) drive the live TUI and are confirmed via the TUI's confirmation lines. **`resume`** rebinds to a live tmux session by name; a runtime record (`session_id → tmux_name`, model, mode, cwd) is persisted so a restarted sidecar **reconnects bridge sessions** (`runtime_store.py`). **Context** = a single **cumulative aggregate** (`derive_context_usage()` = `input + cache_read + cache_creation` tokens from the *latest* assistant transcript entry, over a **hardcoded 1,000,000** window) — *not* categorized, *not* per-turn, *not* model-aware. Bridge **turn count** = number of user transcript entries whose content is a plain string — and it lives **only in `GET /context`**, not the session dict. **Bridge cannot observe:** subagents/Task run-state (opaque until the call returns), `AskUserQuestion` (its menu lacks the `1. Yes` anchor → reads as `unknown`), plan-mode / ExitPlanMode (no distinct state), fast-mode (`set_fast` is a **no-op**, unadvertised), thinking toggle (`/thinking` is "No commands match" in CC 2.1.187 — thinking *blocks* are still visible in the transcript), absolute permission-mode set (`set_mode` is a no-op; mode only cycles via Shift+Tab). **Bridge never emits cost** → bridge `total_cost_usd` stays `0.0`.
>
> **sdk — the backup / limited-use engine, not the strategic default.** In-process Agent SDK. It happens to report `num_turns` (→ session dict `total_turns`) and `total_cost_usd` from its `result` event and to advertise `set_mode` (which bridge does **not**) — but these are incidental quirks of a fallback path, not a balanced ledger of capability: it also exposes an **opaque** context-usage shape (different keys than bridge), **does not survive a sidecar restart**, and has **no real terminal** (Console is bridge-shaped). It is the explicit-only backup, never the no-driver-named default — `bridge` is what an unnamed session runs on.
>
> **Both drivers — confirmed absent / net-new (don't claim these exist):** any UI driver-selection (the live frontend posts only `permission_mode:'acceptEdits'` on create — **never** `driver`, so bridge is **never selected through the UI today**); any permission approve/deny UI; any model/mode/effort/fast/thinking control; SSE consumption (the app **polls** `GET /history` in full every 800ms — no incremental events, React keys are the array index); a **prompt queue** (`/send` while `running` returns **409** and the prompt is **dropped**); a `max_turns` cap; `AskUserQuestion` handling; plan-mode runtime behavior (the `SetModeRequest` enum *value* `plan` exists but nothing acts on it); subagent/Task detection; a scratchpad; a categorized context breakdown; always-allow; and **cost tracking on bridge**. **Session status enum is exactly 5 values: `connecting / idle / running / error / closed`** — there is **no** `permission`/`paused`/`waiting` status; a pending permission is the boolean `has_pending_permission`, by deliberate design. Several `Assumed:` lines therefore describe *intended*, not current, behavior — they're flagged inline.

---

## A. Agent lifecycle & state

**1. Status-state mapping (card vs the Error type), and the one status model behind three surfaces.** The Team-Graph card renders **active / idle / pending** (DESIGN's status enum is exactly those three; `pending` is binary, not a count). The sidecar's **session** status enum is the disjoint **`connecting / idle / running / error / closed`** (exactly 5), and the bridge's *screen-state* enum is the even-narrower **`idle / generating / permission_prompt / unknown`**. The refactor adds a first-class **Error** Inbox type (API/model · Tool/MCP · **Environment/connection** incl. *bridge tmux dropped / SDK session lost* · Config · Stalled). So three vocabularies must be reconciled into what the card shows.
- A) **Define one normalized UI status the card renders, mapped from each driver: bridge `generating→active`, `idle→idle`, `permission_prompt→pending` (via the `permission_request` event), `unknown→hold last state`; sidecar `error/closed→` an error/retired card treatment; an open Inbox item → `pending`. An Error Inbox card also flips its agent card to an error treatment and the Run-strip (Q7) keys off the same signal. The live frontend handles only `running`/`error` today (else Idle), so this normalized mapping is net-new.**
- B) Errors live only in the Inbox/Messages, never on the card.
- C) Reuse `pending` (warning tone) for errors too.

`Assumed:` **A** — ▶ Confident on the *need* (three enums must collapse to one card vocabulary; the frontend's current 2-case handling is insufficient), ◆ Leaning on the **normalization rules** — both the **`unknown` rule** (the sidecar emits no status_change for bridge `unknown`, so the card would freeze on its last state — confirm that's acceptable vs. a distinct "?" treatment; see Q32) **and the three-surface single-signal claim** (that the same signal drives the card, the per-message badge, and the Error card is net-new cross-surface reconciliation, unconfirmed — the messages-card enum is a *different* vocabulary that must be mapped, not read). **One status model, three surfaces:** the same signal also drives the **Messages feed's per-message badge** (the messages-card snippet fixes that enum at **Active / Complete / Error** only) — and a **failed** message is the same wire that raises the agent's **Error** card (Q6). Define "what flips to error" once and render it on the card, the Inbox, *and* the message stream consistently.

_**TL;DR —** how three different status vocabularies (bridge screen-state, sidecar session enum, card states) collapse into the one status the agent card shows, and whether that same signal also drives the per-message badge and Error card. **Presumed:** define a single normalized mapping (generating→active, idle→idle, permission→pending, unknown→hold last state, error/closed→error treatment) feeding card, message badge, and Inbox together; confident the collapse is needed, leaning on the exact rules._

**2. What "pending" actually counts.** Pending = "waiting on you." Strictly *any open Inbox item* for that agent (Permission/Plan/Decision/Error), or also a stalled/timed-out run? *(Status-color rework: Error owns danger; pending/attention moved off danger so they don't collide. The mock's footer "4 pending" vs 4 Inbox cards vs 13 agents are static literals — confirm all three count the same thing.)*
- A) **Pending = exactly one open Inbox request for that agent, of any type (the binary model DESIGN states); a Stalled run becomes an Error card, so it counts via the Inbox, not a separate signal. The per-card binary, the Inbox tab badge (fleet total = agents with an open request), and the footer "N pending" all count the same unit.**
- B) Pending also fires on a hung/timed-out run independent of any Inbox card.

`Assumed:` **A** — ▶ Confident. DESIGN is explicit that an agent blocks on one thing at a time and the badge is binary; routing stalls into Error cards makes "pending = an open Inbox item" closed-form. On bridge, "blocked on a permission" is observable today (the `permission_prompt` state / `permission_request` event); the other raise-paths are net-new (Q16).

_**TL;DR —** what makes an agent "pending" — strictly one open Inbox request, or also a stalled/hung run. **Presumed:** pending equals exactly one open Inbox item of any type (stalls become Error cards, so they count via the Inbox); the per-card badge, Inbox tab total, and footer count all use this same unit, confident._

**3. Retire semantics.** Retire "ends the session" and greys the card. Does the agent's session and history persist? *(Scratch note: a permanent-delete option alongside Retire that fully wipes the agent is wanted — so Retire must be the soft, recoverable form.)*
- A) **Retire kills the live session (tmux/SDK process) but archives its config + transcript so it can be reloaded later (ties to backlog B3 "Load Past Agents"); the greyed card stays until reload, then drops from the roster. A separate permanent-delete (Scratch) hard-wipes.**
- B) Retire is a hard delete — nothing persists.
- C) Retire just detaches (session keeps running headless, can re-attach).

`Assumed:` **A** — ◆ Leaning. Fits B3 and the Scratch note about reusing an agent's *config* as a "project," and the wanted permanent-delete implies Retire is the recoverable tier. Wrinkle: whether the **transcript** is archived too or just the config — I assume both, but flag it (see Q31's Setup-vs-snapshot distinction). On bridge, Retire maps cleanly to `close()` (kills one tmux session) and dropping its `runtime_store` record; sdk sessions don't survive restart anyway.

_**TL;DR —** whether retiring an agent permanently deletes it or archives it recoverably. **Presumed:** Retire kills the live session but archives its config plus transcript so it can be reloaded later, with a separate permanent-delete for hard wipes; leaning, with an open flag on whether the transcript is archived too or just the config._

**4. Definition of a "turn" + the by-tool Turns breakdown — and the live driver disagreement.** The `Turns 34/50` bar, the Max-turns auto-stop, *and* the **Turns dropdown** (`turns-dropdown.html`: a by-tool aggregate — Read/search · Edit/Write · Bash · MCP · Subagent(Task) · Web · **Coordinating**, plus a **Remaining** slice against the cap, with `34 / 50 · 16 left`) all depend on a turn definition, a per-tool data source, *and* a per-agent Max-turns cap (Q5(a) — **no backend representation today**). **The two drivers count turns differently right now:** the sidecar copies the **sdk's `num_turns`** into the session dict's `total_turns`; the **bridge** computes turns as the count of plain-string user transcript entries and exposes it **only in `GET /context`** — the bridge session dict's `total_turns` **stays 0**.
- *(a) Turn unit.*
  - A) A turn = one user-prompt → full-response cycle (a "round").
  - B) A turn = each assistant message.
  - C) **Adopt the SDK's `num_turns` definition (agentic iterations) verbatim, even if unintuitive.**
- *(b) By-tool breakdown source.*
  - A) **Sidecar categorizes `tool_use` blocks from the JSONL transcript into the fixed buckets; "Coordinating" is dashboard-derived (scratchpad posts + link/check-in events — nothing Claude Code itself reports). The two drill-down sub-sections are their own data requirement: "/ Tools used (calls)" = raw per-tool CALL counts (distinct from the turn-bucket count — one turn can fire many calls — sourced by counting `tool_use` blocks), and "/ Coordinated with" = a per-counterparty list synthesized from link-fire / scratchpad-post / check-in events (the same dashboard-minted coordination events as the Log taxonomy in Q32b and the "Coordinating" turn slice). Demo-only until the transcript feed is wired through the UI — mirroring how Q11a treats the Memory-files/Custom-agents inventory.**
  - B) Pull a native per-tool counter if one exists; else don't show the breakdown.

`Assumed:` **4a → C, 4b → A** — **4a is ◆ Leaning, not a settled correction: it's a real driver-definition fork.** The SDK docs define `num_turns` as **agentic iterations** (and `max_turns` enforces the auto-stop on *that* unit, so `34/50` would lie about when the agent halts if it counted rounds) — but the **primary (bridge) driver does not count agentic iterations; it counts plain-string user prompt entries** (bridge `total_turns` stays 0; `/context.turns` = prompts). So "adopt the SDK definition verbatim" is a **decision to override the bridge's actual behavior** — picking which driver's semantics win (SDK agentic-iterations vs bridge prompt-count) — not an inferred fact. **The live repo wrinkle is sharper than v4 framed it:** since the **bridge is the primary driver** and its session dict reports `total_turns: 0` (the real count is only in `GET /context.turns`, defined as plain-string user entries — i.e. *prompts*, excluding tool_result entries), a UI binding "turns" to the session dict shows **0 on the primary path**. The backend must decide one canonical source, and — since bridge is the primary path — the **bridge-first lean is to normalize the bridge's `/context.turns` into the session dict's `total_turns`** so the primary driver drives the canonical count, treating "UI reads `/context` for bridge, session dict for sdk" as the degraded per-driver fallback. Note the **definitions also differ** (bridge counts prompts; sdk counts agentic iterations) — pin one so `34/50` means the same thing on both drivers and matches the Rewind/Handoff timeline. 4b is ▶ Confident: transcript `tool_use` blocks (which the bridge parser already exposes raw) are the only honest source, and "Coordinating" is necessarily a dashboard construct.

_**TL;DR —** what counts as one "turn" (the drivers disagree: bridge counts prompts, sdk counts agentic iterations) and where the by-tool breakdown data comes from. **Presumed:** adopt the SDK's agentic-iteration definition but normalize bridge's prompt count into the session as the canonical source, and have the sidecar categorize transcript tool calls into the fixed buckets; the turn-unit choice is a real open call, the breakdown source confident._

**5. Auto-stop limits (Max turns / Context %) — where they're stored, and what happens on hit.** *(Refactor vocabulary: a reached limit is **Lifecycle**, explicitly **not** an Error. The `50` and "16 left" in the Turns header are this Max-turns cap. Graceful wind-down *design* is backlog B19 — this is the baseline.)*
- *(a) Where the caps live.* The Turns bar's `/50` + "Remaining" and the auto-stop both read a per-agent **Max-turns** value (and a **Context-%** ceiling) — but **session state has no `max_turns` field today** (confirmed absent in the request models, session state, and both drivers) and there's no create/edit endpoint for it.
  - A) **Per-agent caps stored on the session, set on Create + live-editable in the Lifecycle band, reported in the session payload, and enforced by the sidecar's run loop (so the cap is the same number the bar shows).**
  - B) Caps are UI-only hints for v1; no real enforcement.
- *(b) On hitting a limit.*
  - A) **Finish the in-flight turn, then halt the agent into `idle` and drop a Log + (Lifecycle-flavored) Inbox item ("hit Max turns — resume?").**
  - B) Hard-stop immediately (interrupt mid-turn).
  - C) Soft warning only; don't actually stop.

`Assumed:` **5a → A, 5b → A** — ▶ Confident on 5b ("finish the turn, then halt to idle" is the only reading consistent with Lifecycle-not-Error and resumability). ◆ Leaning on 5a: A is the honest target (a cosmetic bar that doesn't stop the agent is a trap), but it's genuinely net-new — confirmed absent on both drivers, and on bridge enforcement means the sidecar's poll loop must watch `/context.turns` against the cap (the bridge has no native max-turns notion).

_**TL;DR —** where the per-agent max-turns/context-% caps live (none exist today) and what happens when one is hit. **Presumed:** store caps on the session, set on create and live-editable, enforced by the sidecar; on hit, finish the current turn then halt to idle with a Log/Inbox notice; confident on the halt behavior, leaning on the net-new storage/enforcement._

**6. Error detection, classification & retry.** The refactor makes a failed run a first-class **Error** Inbox card (**Retry · Dismiss · Reply**), with **Retry = re-issue the last command via the Editor** (manual), and a fixed boundary (auto-stop = Lifecycle, not Error; stall/no-progress timeout = Error "Stalled"; model refusal = not Error). *(This Retry contract is also where History's new footer Retry lands — see Q30/I3.)*
- *(a) Detection & classification* of each subtype — who owns it?
- *(b) Auto-retry?* The earlier `0 retries left` meta implied an auto-retry layer; the brief's Retry is purely the manual Editor re-issue.
- A) **Sidecar owns detection+classification; *no* silent auto-retry — every error surfaces as an Error card with a manual Retry (drop the `retries left` meta).**
- B) Add a small auto-retry layer for transient API/connection subtypes (N attempts) before surfacing; manual Retry for the rest.
- C) Per-agent config for both retry count and stall timeout (Lifecycle knobs).

`Assumed:` **A** — ◆ Leaning. **Bridge-first reality:** on the primary driver an error is **text on the captured screen, not a structured signal** — an ECONNREFUSED/529 shows up as feed text, and a stall is the *absence* of new output. So bridge error-detection means the sidecar must (i) pattern-match known error text in `capture-pane`/the transcript and (ii) run a **no-output watchdog** off the 1.0s poll loop for "Stalled." *Environment/connection* errors (bridge tmux dropped) the bridge driver can detect structurally (the tmux session is gone). On sdk, an exception/`error` event is more structured. "Retry = re-issue the last command via the Editor" needs a stored "last command" per agent (net-new; no store does this today). The refactor's "everything routes through the Editor / manual Retry" through-line points at A; B is defensible for transient 529s if you'd rather have resilience over transparency.

_**TL;DR —** who detects and classifies run errors, and whether there's any automatic retry. **Presumed:** the sidecar owns detection and classification with no silent auto-retry — every error becomes an Error card with a manual Editor re-issue (drop the "retries left" meta); leaning, since on bridge errors are just screen text the sidecar must pattern-match plus a stall watchdog._

---

## B. Agent card — live readouts & subagents

*The square-card redesign and the Context turn-scope select introduce live readouts the static snippet fakes with demo data. The "Next up" A-list calls several of these open decisions to settle — they're backend contracts, not just visuals.*

**7. Run-strip progress % — what feeds it.** The square card's **Run strip** keys off status (active → green · pending → warm · idle → muted) with a **barber-pole indeterminate** animation for "working, % unknown." A real percentage needs a source; A3 explicitly **leaves the barber-pole as-is (undecided)**, and DESIGN calls indeterminate "the honest fallback until the real Run-% source is decided."
- A) **Layered: determinate % from plan-step k/n when executing a known plan; else turns-vs-max (from Q4/Q5's cap); else (working, no quantifiable progress) the indeterminate barber-pole. One nullable field on the card-state payload: `{progress: number|null}` (null → indeterminate).**
- B) Turns-vs-max only.
- C) Indeterminate-only for v1; no numeric % until a reliable source exists.

`Assumed:` **A** — ✚ Can't infer firmly (A3 keeps it undecided). **Bridge can report run-*state* (idle/generating/permission/unknown) but has no inherent %-of-completion** — so on the primary driver the honest default is the barber-pole whenever generating, and a real % only exists if a plan-step or turns-vs-max source is wired (turns-vs-max itself depends on Q4's bridge `/context.turns` and Q5's net-new cap). My lean is A because it degrades honestly; the backend contract is just the single nullable `progress` field either way.

_**TL;DR —** what data source feeds the card's run-strip progress percentage, given bridge has no completion %. **Presumed:** a layered source — plan-step k/n when known, else turns-vs-cap, else the indeterminate barber-pole — exposed as one nullable progress field; a real open call since the design deliberately left it undecided._

**8. Marquee live-activity feed — what stream drives it.** The card's **Marquee** scrolls "the agent's current activity as one line," static+muted when idle. A per-agent live string the backend must emit; today it's hardcoded literals in the mock.
- A) **The latest activity line from the same per-session event stream that feeds the Console/Messages — the current tool call / action ("Editing main.py", "Running pytest", "Thinking…") summarized to one line; when idle, freeze on the last action or a muted "idle".**
- B) A purpose-built status string the agent itself emits (ties to the Scratch "check-in schema" note) — richer, but needs an agent-side convention.
- C) Reuse the Log stream's most-recent event for that agent.

`Assumed:` **A** — ◆ Leaning. A reuses the event stream the Console already needs; on **bridge** the line is derivable from the latest transcript `tool_use` block (or the `generating` screen line), sampled at the 1.0s poll cadence — so the marquee can lag ~1s, not stream. B is the richer product direction but depends on a future agent-side status convention — A for v1, B as the upgrade path.

_**TL;DR —** what stream feeds the card's one-line live-activity marquee. **Presumed:** the latest activity line from the same per-session event stream feeding the Console, summarized to one line (e.g. "Editing main.py"), frozen when idle; leaning, with an agent-emitted status string as the richer future alternative. On bridge it samples at ~1s, not streams._

**9. Subagent badges — three run-states + a per-subagent ID, against subagents being opaque.** *(Reworked for A2.)* A2 makes each `.sbadge` **rectangular**, carrying an **inline run-state status dot across THREE states (pending / active / idle)** and a **per-subagent ID** (a number, or **s1/s2** when ambiguous) — explicitly **"not a count,"** in **standard navy ink** (`--foreground`), not agent color. A5 keeps badges **clickable-but-unwired (undecided)**. This is the **biggest backend delta in the queue**, and it collides with a verified fact: **a `Task`-tool subagent is opaque until the call returns** — the parent sees only the final result, no live enumeration, no per-child run-state. Split into the three sub-contracts A2 actually needs:
- *(a) Can the backend distinguish pending vs active vs idle per subagent?*
  - A) **No live three-state today. The verified ceiling is coarse: a Task is "active" while its `tool_use(Task)` block is in flight and "done/idle" once it returns — "pending" (queued, not yet started) and a true mid-run "active vs idle" are **not** observable. On the primary (bridge) driver, the screen shows only the single top-level spinner and the transcript records the parent's `tool_use(Task)` block with no per-child state; the most that could ever surface is a best-effort read of in-flight vs returned. On sdk (backup), only the final Task result is seen — likely **no** pending/active at all. So A2's three-state dot is **bridge-best-effort, sdk-degraded**, and "pending" may be unrepresentable on either.**
  - B) Assume full live three-state per subagent (treat each like a first-class agent) — **not backed by either driver.**
- *(b) Where does a stable per-subagent ID (s1/s2) come from?*
  - A) **The dashboard mints + persists it. Neither driver mints or persists a per-subagent ID; subagents are ephemeral Task spawns. To label s1/s2 and let a click target one, the sidecar must assign a stable ID per detected `tool_use(Task)` block (e.g. ordinal within the parent turn) and keep it — **net-new identity, not a read of an existing field.****
  - B) Derive it from a Task-call identifier the driver exposes — **none exists today.**
- *(c) Click action (A5 leaves this unwired/undecided).*
  - A) Click opens a small read-only subagent detail (label · coarse state · last action) as an anchored popover.
  - B) Click focuses/scrolls the related parent context.
  - C) **Inert for v1 (badges show identity + coarse state only), grow to (a) once the data supports it.**

`Assumed:` **9a → A, 9b → A, 9c → C** — **▶ Confident on the ceiling, and this DOWNGRADES the overall confidence vs A2's intent.** The honest statement to the design: the three-state dot and the per-subagent ID that A2 asks for are **not** things either driver can supply today — subagents are opaque until the Task returns, so "active vs done" is the realistic best case (bridge, by inferring in-flight from the transcript block), "pending" is likely unrepresentable, and the s1/s2 ID is **dashboard-minted, not driver-sourced**. Build the badge to render whatever the sidecar can honestly produce (coarse active/done + a sidecar-assigned ordinal ID), keep clicks inert (A5), and treat full three-state + clickable per-subagent targeting as net-new mechanism (a transcript-sidechain parser), not an existing signal. If the design must have all three states, that's a decision to build that mechanism — flag it, don't assume it exists.

_**TL;DR —** whether the backend can supply the three subagent run-states (pending/active/idle) plus stable s1/s2 IDs the badges demand, given subagents are opaque until the Task returns. **Presumed:** no live three-state is possible (only coarse active-vs-done, pending likely unrepresentable) and the ID must be dashboard-minted, not driver-sourced, with clicks inert for v1; confident on this ceiling, which downgrades the badge's intended capability._

**10. Opus Fast-Mode (`/fast`) — orthogonal, plus the A1 Opus-only gate.** A1 settles two things: **(i)** FAST is **orthogonal** — it does **not** grey out / override Effort or Thinking; mode/effort/think chips always show their **real** values (the old "FAST override greying" idea is **dropped**; the committed `agent-card.html` snippet still shows the dropped greying and is stale vs A1). **(ii)** A **hard UI gate:** the FAST control is **DISABLED whenever Opus is NOT the selected model** (matching the Opus-only bolt).
- A) **FAST is a latency/throughput axis, orthogonal to Effort and Thinking (all three compose); the card just shows the bolt, and the FAST control is enabled only when the selected model is Opus, disabled otherwise. Drop the proposed greying.**
- B) FAST overrides — grey Effort/Think when on. *(Rejected by A1.)*
- C) Render the bolt but wire no behavior until `/fast` semantics are confirmed.

`Assumed:` **A** — ▶ Confident **ONLY on the client-side UI gate** (Opus-check + orthogonality per A1; the gate is a pure client check on the selected model); **FAST behavior itself is ✚ Can't-infer / net-new — non-functional on every driver today.** **Flag the backend reality bluntly:** `set_fast` is **not in any driver's CAPABILITIES**; on the **primary (bridge) driver** it is a deliberate **no-op** (the CLI's `/fast` opens an interactive panel that couldn't be reliably scraped, and the bridge can neither set nor *read* fast state), so `/fast` returns **400** on bridge; on **sdk** it isn't advertised either. So the toggle is **cosmetic until wired** — the Opus-only gate and orthogonality are correct UI rules, but a working FAST is net-new (likely the sdk/`speed:"fast"` path first; bridge may stay inert until the CLI exposes `/fast` non-interactively, like Inject in Q23).

_**TL;DR —** whether Fast-Mode overrides Effort/Thinking or composes with them, and its enablement rule. **Presumed:** FAST is orthogonal (all three compose, drop the greying) and the control is enabled only when Opus is selected; confident on those UI rules, but FAST itself is net-new and non-functional — `set_fast` is a no-op on bridge — so the toggle is cosmetic until wired._

**11. Context breakdown — Total-scope categories · per-turn attribution · Compact.** The Context accordion (`context-dropdown.html`) layers a turn-scope `<select>` on a category breakdown, but today the backend produces only a **single aggregate** (bridge: `{tokens, window:1_000_000, percent, turns}` from the latest assistant `message.usage`; sdk: an **opaque** SDK usage object with different keys). Three contracts:
- *(a) Total-scope categories + loaded-context inventory* (net-new). The breakdown splits the window into **System prompt · System tools · MCP tools · Custom agents · Memory files · Messages · Free space** (80% cutoff line), with sub-sections enumerating loaded **Memory files** + **Custom agents** (declared loaded-once, scope-invariant).
  - A) **The sidecar computes the categorization + inventory into the fixed buckets — a real per-category feed, not `sum(usage)`. Demo data until wired.**
  - B) Approximate categories client-side; only the grand total is real.
- *(b) Per-turn attribution* (the `Turn n` scope).
  - A) **From per-message `usage` in the transcript, summed within each turn; the two-denominator design (header = share of the 1M window; rows = share of that turn) is presentation, not two feeds; the Memory/Custom-agents sub-sections stay scope-invariant. Per-turn rows are limited to turn-attributable categories (primarily Messages, with per-turn MCP-result / memory-reload tokens); the loaded-once categories (System prompt/tools, Custom agents) are scope-invariant and appear only in Total, consistent with the Memory/Custom-agents sub-sections staying put. Demo until wired.**
  - B) Only Total is real for v1; per-turn is mock-only.
- *(c) The Compact action* (a dedicated **Compact** link in the Context head, distinct from typing `/compact` in the Console — Q29).
  - A) **Compact invokes `/compact` on the driver; on completion the sidecar re-derives the context feed and the bar/breakdown drop to the post-compaction window.**
  - B) Compact is a Console-only command for v1; no dedicated button.

`Assumed:` **11a → A, 11b → A, 11c → A** — ▶ on **11a/11b sources** (`message.usage` exists), ◆ on **timing** (demo-now/real-later for a/b), and ◆ on **11c** (Compact is a verified round-trip on the bridge TUI path only; sdk compaction is net-new). **Bridge-first nuances:** the bridge already parses `message.usage` — but only for a **cumulative** figure (latest entry), so per-turn attribution is a **new aggregation over an existing field**, and the **category breakdown is an entirely new feed** (nothing categorizes context today, on either driver; sdk's usage object is opaque and shaped differently — a UI gauge needs **one canonical shape** the sidecar normalizes). The **1,000,000 window is hardcoded and not model-aware** — confirm whether the denominator should vary by model. **Compact** maps to the CLI `/compact` only on the **bridge** TUI path (a real round-trip the sidecar can re-derive after); on sdk it would need the SDK's own compaction. The "don't reconcile the two denominators" line is a UI rule, not a backend one.

_**TL;DR —** whether the context accordion's category breakdown, per-turn attribution, and Compact button are real, given the backend only produces a single aggregate today. **Presumed:** the sidecar computes real per-category buckets and per-turn sums from transcript usage (demo data until wired), and Compact invokes `/compact` then re-derives; sources confident, timing and Compact (bridge-only round-trip) leaning._

---

## C. Inter-agent linking & context-sharing

*(The refactor reserves **"Link" for inter-agent links only** — content-sharing moved to Embed/Attach, Section G. Link Trigger enum = **Now · Inject · Next · Queue · Hold** (5); Payload = **Message · Transcript · Manual**; Direction = **A→B / B→A / A↔B**; End-After = **Turns / Tokens**. These four remain open.)*

**12. What event *fires* a link.** DESIGN says a link "forwards context from A to B" but never says *on what trigger* — the Trigger table governs **target-side delivery timing**, not *when the source fires*. The single biggest undefined contract.
- A) **A link fires when the source agent finishes a turn (goes idle) — its latest output is forwarded per the Trigger timing.**
- B) Fires only when the source posts to Scratch / emits an explicit "handoff" marker.
- C) Fires continuously/periodically (the backlog B12 "dynamic doc" model — defer).

`Assumed:` **A** — ◆ Leaning (the draft itself calls this the single biggest undefined contract). On **bridge**, "source went idle" is observable (the `idle` screen-state / `generating→idle` transition at the 1.0s cadence), so turn-completion is the most natural and detectable source-fire. B (fire on an explicit handoff marker) is the real alternative if you'd rather links be deliberate than automatic-on-every-turn.

_**TL;DR —** what event triggers a link to forward context from agent A to B (the source-fire moment, undefined in the design). **Presumed:** a link fires when the source agent finishes its turn and goes idle, forwarding its latest output; leaning — the doc calls this the single biggest undefined contract, with firing on an explicit handoff marker as the real alternative._

**13. What "Message" payload captures.** Payload = Message / Transcript / Manual. (Transcript's exact source is explicitly **TBD** in DESIGN, backlog C6.) For **Message**, which text exactly?
- A) **The source's final assistant message of the just-finished turn, forwarded as one rendered message.**
- B) The full turn including its tool calls/results.
- C) A summary the dashboard generates.

`Assumed:` **A** — ▶ Confident for Message. **Note for Transcript (TBD):** on **bridge** the candidate sources are `read_log` / `export(mode="log")` (raw JSONL — the `log` export branch is **untested** per CLAUDE.md) or `extract_messages()` (clean dicts, but it renders tool_use only as the literal `[tool: <name>]` and drops inputs/results, and is **not** on the live sidecar path). So if Transcript ships, name the bridge transcript as the source and flag it **unverified through the UI**.

_**TL;DR —** which exact text the "Message" link payload forwards. **Presumed:** the source's final assistant message of the just-finished turn, sent as one rendered message (not the full turn with tool calls, not a generated summary); confident for Message, with the separate Transcript payload source still TBD and unverified through the UI._

**14. Bidirectional turn-taking (A↔B), End-After = Turns/Tokens.** With both directions on, what stops infinite ping-pong beyond the End-After caps? *(End-After is **Turns / Tokens** only — Time was removed. End-After's scope (per inter-agent exchange) is deliberately **distinct** from Lifecycle auto-stop (per single agent, Q5) — keep them separate.)*
- A) **Strict alternation: each side only fires after the other goes idle (one in flight at a time); End-After (Turns / Tokens) is the hard backstop; when both toggles are on it ends at first reached.**
- B) Free-running both ways, relying entirely on End-After.
- C) Every forwarded message requires a Hold/manual release.

`Assumed:` **A** — ◆ Leaning (confidence inherited from Q12's "fire on idle" premise, itself an inference). Strict alternation falls out *if* sides fire on going idle. Confirm the End-After **unit** — link-exchange turns vs agent turns — DESIGN insists these are different scopes; and confirm who enforces/ends the loop (the sidecar, watching both sides' idle + the cap).

_**TL;DR —** what prevents infinite ping-pong in a bidirectional A↔B link beyond the Turns/Tokens caps. **Presumed:** strict alternation — each side fires only after the other goes idle, one in flight at a time, with End-After as the hard backstop (ends at whichever cap hits first); leaning, since it inherits the unproven "fire on idle" premise, and the End-After unit needs confirming._

**15. The "Hold" relay surface.** Hold (a link Trigger; **Hold makes sense only for a link**, which is why Send-timing omits it) = stage a forwarded message for your manual release. The Inbox is fixed at four typed sections (Permission · Plan · Decision · Error) — none is a held-relay.
- A) **Route a held relay into the Editor as a pre-filled `embed` block targeted at the receiver — consistent with the Editor-routing model (Reply/Retry already do this).**
- B) Add a 5th **Relay** section to the Inbox (release / edit / drop).
- C) Surface holds in the Console/Log only.

`Assumed:` **A** — ◆ Leaning. A keeps the Inbox at its four fixed sections and reuses the `embed` primitive + Editor through-line. B is cleaner conceptually (a held relay *is* an awaiting-you item) — so if you'd rather Holds live in the Inbox, it's B. Worth your eye.

_**TL;DR —** where a held (manually-released) relay message surfaces, given the Inbox has only four fixed sections. **Presumed:** route the held relay into the Editor as a pre-filled embed block targeted at the receiver, reusing the existing Editor-routing model rather than adding a fifth Inbox section; leaning, with a dedicated Inbox "Relay" section as the cleaner alternative worth considering._

---

## D. Approvals / Inbox

*(Inbox = exactly four typed sections: **Permission · Plan · Decision · Error**. Per-type controls differ: Permission = Approve/Deny/Always-allow/Reply; Plan = Review(→Plans)/Reply only (**no** Approve/Reject in Inbox); Decision = AskUserQuestion, pick option then Approve/Reply; Error = Retry/Dismiss/Reply. Decision **is** the AskUserQuestion surface.)*

**16. How each Inbox type is *raised*.**
- **Permission** = native permission prompt. **Strongest path:** the bridge detects `permission_prompt` (a numbered menu anchored on a literal `1. Yes` at the bottom of the capture) and the sidecar surfaces it as a `permission_request` event — **live-verified below the UI** — though the **frontend implements none of it yet** (no approve/deny UI; create pins `permission_mode:'acceptEdits'` to sidestep prompts).
- **Decision** = the native **`AskUserQuestion`** tool — one question + options per card; pick + Approve. **Net-new:** no AskUserQuestion handling exists, and on **bridge** an AskUserQuestion menu **lacks the `1. Yes` anchor**, so `_detect_state` reads it as **`unknown`** (or misreads it) — it is **not** detectable as a distinct state today.
- **Plan** = a native plan (plan mode / ExitPlanMode); Inbox card is **review-only** (Review + Reply). **Net-new:** bridge has **no** plan-mode screen-state or transcript handling (plan generation looks identical to `generating`; the plan-approval prompt is not a `1. Yes` menu).
- **Error** = system-detected (Q6).

Residual contracts: *(a)* the sidecar **intercepts `AskUserQuestion` tool-calls** ↔ Decision cards and routes the picked option back as the **tool result**; *(b)* **how a Plan card is raised** — how the dashboard learns a native plan is "awaiting review" and which agent owns it (ties to Q18).
- A) **Yes to (a); for (b) the sidecar watches plan-mode exits / new `~/.claude/plans/*.md` and ties each to its authoring session (Q18's side-store).**
- B) Decision/Plan are dashboard-operator constructs, not agent-raised, for v1.
- C) Keep Permission + Decision(`AskUserQuestion`) for v1; defer agent-raised Plan cards.

`Assumed:` **A** — ◆ Leaning (downgraded from v4's ▶, given the bridge reality). **Permission is solid via bridge; the other three are net-new and harder on the primary driver:** AskUserQuestion and plan-raise are **not** detectable by the bridge's current screen-state machine, so they each need a new detection rule (transcript-level `tool_use(AskUserQuestion)` interception; plan-file/plan-mode-exit watching) — not a read of an existing signal. A states the intended mechanics; the open part is the **detection** each non-permission type requires.

_**TL;DR —** how each of the four Inbox card types (Permission/Decision/Plan/Error) gets raised, including intercepting AskUserQuestion and detecting plans. **Presumed:** yes to intercepting AskUserQuestion tool-calls into Decision cards, and the sidecar detects plans via plan-mode exits / new plan files tied to the authoring session; leaning — Permission is solid on bridge but the other three need net-new detection the bridge can't currently see._

**17. "Always allow" scope & persistence.** The Permission card shows **Always-allow** — but **the backend has no always-allow path:** `answer_permission` is **binary** (approve/deny) and "always allow" (option 2) is **explicitly unsupported/unverified** on the **bridge** (only Enter/Escape proven). So if the card offers Always-allow, define both the scope *and* the net-new backend support.
- A) **Allow that tool+command pattern for *this agent's session* only (in-memory, gone on retire).**
- B) Persist it to the project `.claude/settings.json` allow-list (affects future agents too) — what native CC "Always allow" actually does.
- C) Per-agent, but persisted with the agent's saved config/setup (Q31).

`Assumed:` **A** — ◆ Leaning, and the one I'd most want confirmed — **with the hard caveat that always-allow is net-new on the primary driver.** Today approve is binary; the bridge proves only Enter/Escape. Session-scoped (A) is the *safe* default; native CC does **B** (writes to settings). Whichever you pick, the backend must **add** an always-allow mechanism (a third answer beyond approve/deny) — confirm whether the v1 contract is strictly the two verified actions (drop Always-allow from the card) or build the third path.

_**TL;DR —** what "Always allow" on a permission card scopes to, given the bridge only supports binary approve/deny today. **Presumed:** allow that tool/command pattern for this agent's session only (in-memory, gone on retire), rather than writing to project settings as native CC does; leaning, and the most-wanted confirmation — note always-allow is a net-new third action that must be built either way._

---

## E. Plans review *(plans are native CC `~/.claude/plans/*.md`; the review layer is a dashboard invention)*

**18. Plan↔agent mapping + where review data lives.** A plan file has no notion of owning agent, verdicts, or comments — yet the Library shows owner badges, Approve/Revise/Block tallies, and multi-agent feedback, and **all** plan approval + agent-review verdicts live in the **Plans tab** (so the side-store carries even more).
- A) **Sidecar maintains a side-store (small DB/JSON) keyed by plan filename: owner agent, state, all comments/verdicts; edits to the plan body write back to the `.md`, but review metadata never touches the file.**
- B) Embed review metadata in the `.md` itself (frontmatter/HTML comments).
- C) Review metadata is ephemeral (lost on reload).

`Assumed:` **A** — ▶ Confident. A plan `.md` can't carry owner/verdict/comment data without corrupting it as a native CC artifact; a filename-keyed side-store is the only clean option. *(Note the Scratch wish for mermaid diagrams + visual markers in Plans — a future content concern, not this mapping contract.)*

_**TL;DR —** where plan ownership, verdicts, and review comments are stored, since a native plan .md file can't carry them. **Presumed:** the sidecar keeps a side-store keyed by plan filename (owner, state, all comments/verdicts), writing only body edits back to the .md and never review metadata into the file; confident, as a filename-keyed side-store is the only clean option._

**19. Approve/Reject → the paused agent (Plans-tab-only).** Approve/Reject lives **only** in the Library Plans footer (the Inbox Plan card is Review + Reply only). When you Approve in the Plans tab, what does the authoring agent do?
- A) **Approve resumes the agent out of plan mode into execution; Revise sends the flagged sections back as a new prompt; Reject ends the plan and notifies the agent. (Requires the agent parked in plan mode awaiting the verdict.)**
- B) Approve is informational only — you still manually prompt the agent to proceed.

`Assumed:` **A** — ◆ Leaning. A is the intended "route control through the GUI" behavior. **Bridge dependency to verify:** the authoring agent must actually be **parked in plan mode** awaiting the verdict — and the bridge has **no** plan-mode detection (it can't tell a parked-in-plan agent from a normally-generating one), and **`set_mode` is a no-op on bridge** (mode only cycles via Shift+Tab), so "resume out of plan mode" on the primary driver is a net-new mechanism, not a verified capability. If agents don't reliably park / can't be resumed cleanly, A degrades toward B.

_**TL;DR —** what the authoring agent does when you Approve/Revise/Reject its plan in the Plans tab. **Presumed:** Approve resumes it out of plan mode into execution, Revise sends flagged sections back as a new prompt, Reject ends and notifies; leaning, and dependent on the agent actually parking in plan mode — which bridge can't detect or cleanly resume, making this net-new._

**20. Cross-agent plan review routing (formalization deferred to B13).** The Plans **Review** control is a **single-agent reviewer select** as groundwork; the workflow is deferred to B13. Confirm the *eventual* shape so the data model anticipates it.
- A) **Review hands the plan to one reviewer agent as a structured task; its verdict returns as a Feedback entry in the Plans tab; the human keeps the final Approve/Reject gate.**
- B) Agent reviewers are advisory only; never gate.
- C) Leave fully deferred — don't model reviewer agents yet.

`Assumed:` **A (as the eventual shape; build C now)** — ◆ Leaning. A is the direction the single-reviewer select builds toward and what the side-store (Q18) should anticipate (a `reviewer`/`verdict` field). Since B13 defers the *workflow*, model for A, implement C.

_**TL;DR —** the eventual shape of routing a plan to another agent for review, so the data model can anticipate it now. **Presumed:** Review hands the plan to one reviewer agent as a structured task whose verdict returns as Feedback, with the human keeping the final Approve/Reject gate; leaning — model for this eventual shape now but only implement the deferred-stub version._

---

## F. Shared scratchpad

**21. Storage + attribution mechanism.** The mockup writes a shared scratchpad; a raw `.md` can't carry per-post "agent + timestamp" attribution, yet the Scratch tab shows both. *(Confirmed absent: no scratchpad field, endpoint, or storage anywhere in the sidecar today — fully net-new.)*
- A) **Posts route *through the sidecar* (an append API) which stamps agent + time and keeps the structured post log; it also materializes a plain `scratchpad.md` agents can read. Agents post via a known mechanism (a slash command / tool the sidecar intercepts).**
- B) Agents write the file directly and the dashboard parses a strict per-line format for attribution.
- C) Scratch is dashboard-internal only; agents don't actually read/write a real file yet.

`Assumed:` **A** — ▶ Confident on the shape (attribution + a clean materialized doc both require a write path through the sidecar). Flag the WSL2↔Windows boundary: if the materialized `scratchpad.md` must be read by a **bridge** agent, it has to live at a WSL-reachable path (same concern as Attach, Q26).

_**TL;DR —** how the shared scratchpad stores per-post agent+timestamp attribution that a raw .md can't carry (it's fully net-new). **Presumed:** posts route through a sidecar append API that stamps agent and time, keeps the structured log, and also materializes a plain scratchpad.md agents can read via an intercepted slash command/tool; confident on the shape, with a WSL2/Windows path caveat._

**22. Do agents auto-read the scratchpad?**
- A) **Write-in / read-out is human-facing only; an agent receives scratch content only when it's explicitly sent to it (Editor → Scratch target, or a link).**
- B) The scratchpad is auto-injected into every linked agent's context on each turn.

`Assumed:` **A** — ◆ Leaning. A matches "posting in, reading out is the whole interaction for now" and avoids context bloat. B is the richer "living shared doc" vision but is the deferred B12 direction — A for v1.

_**TL;DR —** whether agents automatically ingest the scratchpad or only see it when explicitly sent. **Presumed:** write-in/read-out is human-facing only — an agent gets scratch content solely when explicitly sent to it (via Editor target or a link), not auto-injected every turn; leaning, with the auto-injected "living shared doc" as the deferred richer alternative._

---

## G. Prompt send semantics & Response settings *(Compose → Editor)*

**23. Timing (Now / Inject / Next / Queue) — server-side model.** *(Send-timing reuses the link Trigger vocab **minus Hold** = Now · Inject · Next · Queue.)* The sidecar `send` is **fire-now only** today: `/send` while `running` returns **HTTP 409 "Session is busy"** and the prompt is **dropped** — **there is no queue**, and **no** turn-boundary detection. These four also differ in feasibility across drivers.
- A) **Build a per-agent server-side prompt queue + turn-boundary detection so all four are real; document that `Inject` may degrade to `Next` on whichever driver can't do mid-run injection.**
- B) Implement Now + Queue for v1; mark Inject/Next as "planned" until the driver supports boundaries.
- C) Treat all four as the same immediate send (labels only).

`Assumed:` **A** — ◆ Leaning. **Bridge-first reality:** the **queue is not a bridge primitive — the sidecar must own it** (the 409-and-drop behavior is the current contract). The bridge's `send()` **always types text + Enter regardless of run-state** (mid-run send is *unguarded*), and whether CC queues or interleaves a mid-generation injection is **unverified by the bridge** — it can't observe queue behavior. So `Now` (interrupt via `interrupt`/Ctrl+C then send) and `Queue` (sidecar buffers, sends when the bridge reports `idle`) are honest on bridge; `Inject` ("next safe boundary between tool calls") needs a **boundary detector the bridge doesn't have** and likely **degrades to Next/Queue** on the primary driver. C (labels-only) lies about delivery — avoid it.

_**TL;DR —** how the four send-timing options are realized, given the sidecar is fire-now only and drops prompts sent mid-run with a 409. **Presumed:** build a sidecar-owned per-agent prompt queue plus turn-boundary detection so all four are real, documenting that mid-run Inject may degrade to Next on drivers lacking boundaries; leaning, since the queue and boundary detection are net-new on bridge._

**24. "Send as <agent>" (From = an agent).** Sending a prompt *as* an agent — a user-style message attributed to the source, or a link-style relay with sender/trigger front-matter? *(DESIGN says messages carry sender+trigger metadata the dashboard hides — define the wire format.)*
- A) **It injects into the target as a normal prompt tagged with the source agent's identity (reuses the link sender-metadata wrapping); it is not a persistent link.**
- B) It actually creates/uses a one-shot link under the hood.

`Assumed:` **A** — ▶ Confident **it's a tagged one-shot prompt (not a standing link)** — DESIGN frames From=agent as "sending *as* that agent for coordination." The **source-transcript-attribution direction is the open sub-fork:** confirm whether the prompt also posts to the **source** agent's transcript (attribution both ways) or only the target's.

_**TL;DR —** whether sending a prompt "as" an agent is a tagged one-shot message or creates a hidden standing link. **Presumed:** it injects into the target as a normal prompt tagged with the source agent's identity (reusing link sender-metadata), not a persistent link; confident, with the open sub-fork being whether it also posts to the source agent's transcript._

**25. AI utility passes — Revise *and* Summarize.** Both rewrite/condense with an LLM call: **Revise** (Grammar/Language/Refactor) rewrites a prompt before send (Editor footer); **Summarize** condenses selected cards into a slide-over. *(Per G, Summarize now appears on **Messages / Scratch / Log** feeds (not Inbox), each with its own slide-over; select/deselect is generalized to every feed — see Q30.)* Same net-new backend capability.
- A) **One shared sidecar "utility-LLM" endpoint runs both on a cheap fixed model (e.g. Haiku); Revise returns to the Editor for review before Send, Summarize fills the slide-over.**
- B) Route each through the currently-focused agent's own model.
- C) Defer both to post-v1 (keep the buttons inert / mock-only).

`Assumed:` **A** — ◆ Leaning. **These are good candidates for the sdk / in-process backup engine** (programmatic, no TUI needed) rather than spending a bridge agent's TUI session on chores — but that must be a **stated decision**, not assumed. A (a dedicated cheap utility model, run via the sdk path) keeps these off the agents' context windows; B spends the focused agent's tokens. A is the cleaner contract.

_**TL;DR —** what model runs the Revise (prompt rewrite) and Summarize (condense cards) LLM passes. **Presumed:** one shared sidecar utility-LLM endpoint on a cheap fixed model like Haiku — Revise returns to the Editor, Summarize fills the slide-over — keeping these off agents' context windows; leaning, and noting this is a good fit for the in-process sdk backup engine if stated explicitly._

**26. Embed vs Attach — backend realization (now behind the H link-icon dropdown).** Content-sharing is **Embed** (a frozen inline quote in the prompt body) and **Attach** (a path reference + a hardcoded "read this"; pathless content is materialized-to-temp-file-and-referenced). **H changes only the *control shape*:** every Embed/Attach toggle chip (Library Plans/Documents/Assets footers + the Team Feed footer) becomes a **link-icon-only dropdown** with menu items "Embed in prompt" / "Attach as file," selection-gated (part→Embed, whole/Asset→Attach). **The backend realization contract is unchanged** — and it's **stubbed everywhere** in the snippets. Pathless sources now include feed cards across Messages/Scratch/Log/Inbox (G generalizes selection).
- *(a) Embed* — settled (a frozen, point-in-time inline quote, no liveness); a rubber-stamp confirm.
- *(b) Attach* → for real files inject the path; for pathless content (a message, a feed card, a multi-block selection, "the whole reply"), **where do materialized temp files live, what's their naming / lifecycle / cleanup**, and how is a multi-block bundle written to one file?
- *(c) Cross-agent path reachability* → an Attach from Agent A sent to Agent B must resolve from B's cwd/filesystem (incl. the **WSL2↔Windows boundary** and differing cwds). Who rewrites/normalizes the path?
- A) **Embed = inline text injection; Attach = path ref, with pathless content (incl. feed cards) materialized into a per-session temp dir under the sidecar's workspace, cleaned on retire; the sidecar normalizes paths to be reachable by the receiving agent.**
- B) Attach always materializes a temp file (even for real files) for a uniform, always-reachable path.
- C) Embed-only for v1; defer Attach's temp-file machinery.

`Assumed:` **A** — ▶ Confident on the shape (the refactor's stated mock contract; H doesn't move it). The residual *real* unknowns are (b) temp-file lifecycle/cleanup and (c) **cross-filesystem path normalization** — and for the **primary (bridge) driver this is acute:** the receiving agent reads via WSL, so a Windows-side temp path won't resolve — the materialized file must be written **WSL-reachable** (or the path translated) before the bridge agent is told to "read this." Confirm where temp files live and which side of the boundary owns the path.

_**TL;DR —** how Embed (inline quote) and Attach (path reference) are realized, especially temp-file lifecycle for pathless content and cross-agent path reachability. **Presumed:** Embed injects inline text; Attach passes a path, materializing pathless content (incl. feed cards) into a per-session temp dir cleaned on retire, with the sidecar normalizing paths for the receiver; confident on shape, with WSL2/Windows path translation the acute open detail._

**27. Response settings → runtime behavior.** The Response popover (`response-popover.html`) defines graded **STYLE** axes — Length[Terse…Exhaustive], Altitude[High-level…Low-level], Register[Technical…Plain], Structure[TL;DR/Numbered/Bullets/Tables/Prose multi], Emphasis[multi] — and **BEHAVIOR** axes — Pace[Snap…Deep], Reasoning-shown[Hidden/Key steps/Full]. The snippet states **Pace is per-prompt and INDEPENDENT of the per-agent Effort tier** (they compose). The badge counts **overrides vs default**, not raw selections. So: how do these reach the agent, per-send or persistent?
- A) **All Response axes compile into a compact instruction preamble attached to *that send* (per-prompt), composing with — not replacing — Effort/Thinking/Mode. The popover's values are a sticky Compose default (UI state) but are never written to the agent's saved config or `.claude/settings.json`. "Reasoning shown" is a prompt instruction (and/or the thinking-visibility toggle where one exists).**
- B) Map Style onto a native CC **output-style**; persist it on the agent; inject only Behavior as prose.
- C) Mock-only for v1 — the popover sets UI state but nothing is injected.

`Assumed:` **A** — ▶ Confident. CC **output-styles** are the **wrong granularity** (session-level system-prompt overrides needing `/clear`, not per-send graded dials), so a **per-prompt instruction preamble** that composes with Effort/Thinking/Mode is the clean contract. **Per-driver realization differs** and must be stated: **Effort is already a per-agent setting verified on bridge** (`/effort`), but Pace/Style being **per-send** means the backend needs a **per-message style payload separate from agent config** — on **bridge** that would be text **prepended into the TUI prompt** before send; on sdk it could be a system/append. **Reasoning shown maps cleanly only to a prompt instruction on the primary (bridge) driver** — the native thinking-visibility toggle (`/thinking`) does not exist in CC 2.1.187 per the Backend-reality check, so Full/Key-steps/Hidden is prose-instruction-only on bridge; real toggle-backed visibility is net-new (sdk extended-thinking config at best). The override **badge count** is pure UI.

_**TL;DR —** how the Response popover's Style/Behavior dials reach the agent — per-send or persisted. **Presumed:** all axes compile into a compact per-prompt instruction preamble composing with Effort/Thinking/Mode, never written to agent config or settings; confident, since CC output-styles are the wrong (session-level) granularity, with "reasoning shown" being prose-instruction-only on bridge._

---

## H. Console (raw terminal + slash commands)

**28. Console feed source by driver.** The Console "faithfully mimics a real Claude Code terminal." This is **literal for the primary (bridge) driver** — `capture-pane` gives the current screen and `read_log` gives history (the terminal-faithful feed likely needs both). The **sdk** driver has **no real terminal**.
- A) **Console is full-fidelity for bridge agents (capture-pane + transcript); for sdk agents it renders a reconstructed terminal-style view from the event stream (same surface, sourced differently).**
- B) Console is **bridge-only** — hidden/disabled for sdk-backed agents.
- C) Always reconstruct from events (never use real capture-pane).

`Assumed:` **A** — ▶ Confident, **and bridge-centric by design**: the Console's fidelity *is* the bridge's `capture-pane`, so it's the strongest on the primary driver; throwing that away (C) wastes it, and hiding it for sdk (B) breaks the "always-available raw output" promise. One surface, two sources, bridge as the high-fidelity case. Confirm scrollback depth (bridge `scrollback()` defaults to `max_lines=10000` in `bridge/bridge.py` — a default, not a hard ceiling) and that the feed updates live at the **1.0s poll cadence** (it samples, not streams).

_**TL;DR —** what sources the Console terminal feed per driver, given bridge has a real terminal and sdk does not. **Presumed:** full-fidelity capture-pane plus transcript for bridge agents, and a reconstructed terminal-style view from the event stream for sdk agents (same surface, sourced differently); confident, updating live at the ~1s poll cadence rather than streaming._

**29. Slash-command execution & interactive commands.** The Console catalog (6 groups) is the **single home for every slash command**; commands with a dedicated home are tagged "also-available-there." Many are TUI-interactive (`/model`, `/clear`, `/compact`) and some mutate state the dashboard mirrors. *(Retry routes through the Editor, "not the Console," so I read the Console as reference-only for command *actions*.)* Sharp case: **`/compact`** changes the live window, so the Context bar/breakdown (Q11) must re-derive.
- A) **Run commands by sending the literal text to the agent (bridge `keys`); commands with a dashboard home (`/model`, `/compact`…) route to that control and just *echo* in the feed; genuinely-interactive ones are gated/queued. Define the per-command routing table (run-on-agent vs Settings-tab vs Details).**
- B) Only run non-interactive informational commands; everything else routes to its dashboard control.

`Assumed:` **A** — ◆ Leaning. **Bridge realizes "run on the focused agent" via `keys`/`send` into the live TUI** (the primary path) — `/model` and `/effort` are already proven this way; but **bridge can't cleanly run interactive-panel commands** (`/fast` opens a panel it can't scrape; `/thinking` doesn't exist in this build) — those must route to a dashboard control or be gated, not "run." The deliverable is the **routing table** (which commands run on the agent, which jump to Settings/Details, scope chip "this agent" vs "session"); A just makes it exhaustive. sdk has no terminal, so "run on agent" there means a programmatic equivalent, not keystrokes.

_**TL;DR —** how the Console runs slash commands, especially interactive ones and those mirroring dashboard state. **Presumed:** send literal text to the agent via keystrokes; commands with a dashboard home (`/model`, `/compact`) route to that control and just echo, while genuinely-interactive ones are gated — requiring a per-command routing table; leaning, since bridge can't cleanly run interactive-panel commands like `/fast`._

---

## I. History, Setups, recovery, identity

**30. History as a feed-model card — persistence, Output Export, Retry, Stop.** *(Reworked for I + G.)* **I** turns History into a **feed-model card**: drop the checkbox → **click header to select**, **Edit moves into the card header**, and the footer gains **Retry BEFORE Stop** (footer order: select/deselect · Output Export | link-dd · **Retry · Stop**); select/deselect + **Output Export** are wired for History too. History cards still carry delivery states (the `db-*` family: Active/`status-done-soft`/`status-next-soft`/`status-held-soft`) tied to Q23's timing vocabulary (Now/Inject/Next/Queue) plus resolved Active/Complete and Held. **G** generalizes **Output Export** (copy-selected / copy-whole-feed, replacing the standalone Copy) and **select/deselect** to *every* feed tab.
- A) **History is the per-agent prompt log derived from session events, persisted across reload/reconnect; the db-* states reflect live queue position and resolve to Complete. Output-Export serializes the selected card span (or whole feed) to clipboard/file client-side — no new backend feed beyond what History/Messages already hold.**
- B) History is session-memory only (cleared on reload).

`Assumed:` **A** — ▶ Confident persistence **is required** (a prompt log that vanishes on reload defeats the point) — but on the *requirement*, not on any existing path: the History prompt-log store is **net-new** (nothing backs it today). ◆ on Output-Export's **target** (clipboard vs file vs both — I assume "copy span to clipboard, optional save-to-file," client-side serialization of already-loaded cards). **Two ties to pin:** **(i) History's Retry ties to the Error-card Retry contract (Q6)** — both re-issue a stored "last command" via the Editor, so they share the "where is last-command stored" net-new requirement; on **bridge** this leans on the verified **resume** capability for re-issuing against the same session. **(ii) Persistence on bridge** rides `runtime_store.py` (bridge sessions reconnect on sidecar restart; **sdk sessions do not survive**), but the History *prompt log* store itself is net-new — no store backs it today.

*Stop (icon-only danger in the History and Messages footers; G scopes Stop to **Messages**, and History adds its own per-I3) = interrupt the agent's active run — maps to the existing `/interrupt` endpoint (the bridge's verified Ctrl+C) scoped to that agent.* `Assumed:` yes — ▶ Confident. *(Scratch wish: a filled-red Stop icon — styling, not contract.)*

_**TL;DR —** whether History persists across reload and how Output Export, Retry, and Stop work on it. **Presumed:** History is the per-agent prompt log persisted across reload/reconnect, with Output Export serializing selected/whole-feed cards client-side and Retry re-issuing a stored last command (tied to Q6); confident persistence is required but the prompt-log store is net-new, Output Export target leaning._

**31. What a "Setup" captures and does on Load.** Setups save "agents + links." *(Related to the Scratch note about renaming session→project — the reusable thing is an agent's **config**.)*
- A) **A Setup is a config blueprint — roles/names/models/modes/links — and Load spawns fresh, empty agents from it (no in-flight context carried).**
- B) A Setup also snapshots live context/transcript and Load restores running state.
- C) Setup = blueprint, but Load *offers* to also restore the last transcript per agent.

`Assumed:` **A** — ◆ Leaning. A matches "agents + links" (config, not state). **Bridge note:** Load implies **re-creating multiple bridge sessions** — and per the bridge-sessions rule those must be created **tab-less** (no auto-popped Windows Terminal tabs as a side effect). C is the appealing upgrade (offer to rehydrate a transcript) and pairs with Q3's archived transcript — if Retire archives transcripts, C becomes the better target. Flag the A/C fork.

_**TL;DR —** whether a saved Setup is just a config blueprint or also snapshots live context. **Presumed:** a Setup captures config only (roles/names/models/modes/links) and Load spawns fresh empty agents with no carried context; leaning, with the appealing alternative of optionally rehydrating each agent's last transcript — and Load must re-create bridge sessions tab-less._

**32. The cross-agent event stream — architecture, the Log taxonomy, crash/reconnect.** The Feed/Graph/Inbox (and Section B's Marquee/Run-strip) are cross-agent aggregations, but the sidecar streams **SSE per session** (replays the full in-memory event list on each new subscriber, then streams; bounded queues silently drop on overflow) — **and the live frontend doesn't even use SSE yet** (it polls `GET /history` in full every 800ms, with array-index React keys → no stable event identity). The **Environment/connection** Error subtype names *bridge tmux dropped / SDK session lost*, so a dropped session has a home (an Error card). Three intertwined contracts:
- *(a) Stream architecture + recovery affordance + event identity.* Who merges the per-session streams, and does the app move to SSE (with stable per-event ids, replay-on-reconnect) or stay on full-history polling?
  - A) **Move to one aggregated event stream the dashboard subscribes to (vs. the frontend fanning-in N per-session SSE streams + merging), with stable per-event ids; on a dropped/recovered session raise the Error card *and* a brief "reconnecting" card state (ties to Q1). Bridge's verified `resume`/reconnect (`runtime_store.py`) is the recovery primitive.**
  - B) Keep per-session SSE; frontend merges; the Error card is the only crash signal; keep full-history polling for v1.
- *(b) The Log event taxonomy* (net-new). The Log tab is "started · committed · flagged · **link fired** · permission/approval requested…" — **dashboard-defined semantic events**, not raw transcript blocks. Many (*link fired*, *committed*, *plan raised*, *scratch post*) no single-agent transcript emits, so the **sidecar must synthesize them**.
  - A) **Define a fixed Log event taxonomy the sidecar emits — lifecycle (started/idle/retired), tool/commit, coordination (link fired, scratch post), and request/error events — as the semantic layer over the raw per-session streams.**
  - B) Log is best-effort scraped from transcript markers for v1; no curated taxonomy.

`Assumed:` **32a → A, 32b → A** — ◆ Leaning on 32a (a single aggregated stream is cleaner and pairs with Q1's reconnecting state; **moving to SSE is also what fixes the current polling/identity gap** — the 800ms full-replace + index keys can't give stable ordering or incremental delivery; B is viable if v1 timeboxes). ▶ Confident on 32b's *need* (the Log's coordination events genuinely don't exist in any single transcript — they're **dashboard-level multi-agent constructs**, same family as the Turns "Coordinating" slice — so the sidecar must mint them); the open part is the exact vocabulary, which the data model should pin now. **Bridge recovery note:** `resume` is **live-verified below the UI** and is the crash-recovery primitive (tmux is the safety net), but reattach *through the dashboard* is unproven.

_**TL;DR —** whether the app moves to one aggregated event stream with stable IDs (vs. today's full-history polling) and what the Log event taxonomy is. **Presumed:** move to a single aggregated stream with stable per-event IDs and reconnect handling, and have the sidecar emit a fixed Log taxonomy including synthesized coordination events; leaning on the architecture move, confident the taxonomy must be sidecar-minted._

**33. Identity uniqueness past 16 agents.** "One identity per agent" rests on a **16-color** jewel palette (`--ag-crimson…--ag-magenta`, OKLCH 0.52/0.15, ROYGBIV — exactly 16, the single source for the picker + tiles) plus **167 game-icons.net icons** and a **14-name** pool. With >16 agents, colors must repeat; the design shows a roster that "scales past what fits." *(Note: A2 puts subagent-badge numerals in **navy ink**, not agent color — so subagent badges no longer add to color collisions; the ceiling is purely the per-agent identity color.)*
- A) **Auto-assign the next free color+icon on Create (user can override); past 16, repeat color but force a distinct icon so the pair stays unique. Past the 14-name pool, reuse names but keep the role+number+name tuple unique (the number already disambiguates within a role), or auto-suffix the name — so name exhaustion never blocks Create.**
- B) Let colors repeat freely past 16 (rely on icon + name).
- C) Cap practical fleets at 16 distinct identities.

`Assumed:` **A** — ◆ Leaning. A (color+icon pair as the unique key past 16) preserves "one identity per agent" without capping the fleet; the icon set has the headroom and the name pool (14) is the tighter constraint to watch. For the name pool I lean ◆ on reuse-with-tuple-uniqueness (the role+number already disambiguates) over auto-suffixing, but that's the secondary fork to confirm alongside color+icon. The 16-color ceiling vs a fleet that "scales past what fits" is otherwise unreconciled in the design.

_**TL;DR —** how agent identity stays unique past the 16-color palette and 14-name pool. **Presumed:** auto-assign the next free color+icon on create; past 16, repeat color but force a distinct icon so the pair stays unique, and reuse names with the role+number tuple keeping them distinct so creation never blocks; leaning, with name-reuse-vs-suffix the secondary fork._

---

*Source review: `design/DESIGN.md` (intent owner), `design/mockup.html` (static visual authority — zero network/IPC; every live behavior is seed data or a `toast()`), `design/tokens.css` (single source of truth; the 16-color `--ag-*` palette, the status/run signal tokens, the `db-*` history/plan badge family), the `design/ui-snippets/` set (agent-card **[stale vs A1/A2]**, response-popover, turns-dropdown, context-dropdown, messages-card, plans-editor-rail), the `design/TODO.md` "Next up" **cumulative change list A–L**, and a fresh code review of the live `frontend/src/renderer/App.tsx` (two-pane, 8 REST endpoints touched / 4 polled, no driver/permission/model UI), `sidecar/` (FastAPI 0.3.0 — 5-value status enum, binary permission, fire-now send/no-queue, single-aggregate context, sdk/bridge driver seam), and `bridge/` (the primary driver — 4-value screen-state, capture-pane + JSONL only, ~1.0s poll, verified model/effort/permission/resume below the UI).*

> **Research note (resolved).** Four answers lean on real Claude Code / Agent SDK semantics, verified against the official docs and cross-checked against what the drivers actually do today (see the *Backend-reality check*):
> - **Q10 — Fast-Mode is orthogonal, Opus-gated, and unimplemented.** An API throughput setting (`speed:"fast"`, Opus only), independent of Effort and extended Thinking → keep both live, drop the greying, gate the control to Opus. **`set_fast` is a deliberate no-op on the primary (bridge) driver and unadvertised on sdk** — so the working toggle is net-new.
> - **Q27 — output-styles are the wrong granularity.** Session-level system-prompt overrides, not per-send graded dials → Response settings inject as a per-prompt preamble (text prepended into the bridge TUI prompt; system/append on sdk).
> - **Q9 — subagents are opaque until the Task call returns.** No live per-subagent run-state and no driver-minted ID; the bridge sees only the parent's `tool_use(Task)` block, sdk only the final result → A2's three-state dot is bridge-best-effort/sdk-degraded ("pending" likely unrepresentable) and the s1/s2 ID is **dashboard-minted**. This **downgrades** confidence vs A2's intent.
> - **Q4 — a "turn" is an agentic iteration, not a round; and the drivers disagree today.** sdk reports `num_turns` into the session dict; the **primary (bridge) driver reports `total_turns: 0`** and counts prompts only in `GET /context.turns` → pin one canonical source + definition or `34/50` means different things per driver.
>
> Everything else stands on the design corpus (`DESIGN.md`, the "Next up" A–L list + snippets, `tokens.css`) and the live `frontend/` + `sidecar/` + `bridge/` seam.
