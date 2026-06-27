# UI Behavior — Open Questions (pre-backend)

**Date:** 2026-06-25
**Scope:** `design/mockup.html` + `design/DESIGN.md` + `design/tokens.css` + the in-flight refactor brief `dev/prompts/link-behavior-refactor.md` + the backend seam (`sidecar/` + `bridge/`)
**Goal:** Lock down the **runtime behavior contracts** the backend must honor, before backend build starts. These are behaviors the static mockup can't show (where it currently fakes them or the docs are silent). The refactor brief tightens many *UX* contracts but is explicitly **mock-only** ("Real backend … is out of scope") — so it constrains the backend without deciding it, which is exactly what this doc tracks.

> **Revised after re-review (2026-06-25, against `dev/prompts/link-behavior-refactor.md`).** Build state: **P0 is built** (Ultraplan removed; Mode block reverted to two labeled toggles — **Opus Fast-Mode / Thinking Mode**, Fast gated to Opus). **P1–P4 are the agreed target, in progress** (the Inbox `REQ_META` is still the old `permission/approval/decision`, so P2–P4 aren't in the mockup yet). The questions below align to that **target** design. The refactor *answers* a few of my opens — **Decision = the native `AskUserQuestion` surface**, **Attach = a path-reference delivery**, and the **auto-stop-limit (Lifecycle) vs Error** boundary — so those questions are narrowed to the residual backend unknowns rather than dropped. Key terminology updates folded in: **Approval→Plan**, **Compose→Editor**, **Share / Link-to-prompt → Embed / Attach**, Feed **Filter/Show/Include → From-To/Type/Content**. The word **"Link" is now reserved for inter-agent links** (Section B), which leaves those questions untouched. Heavy rewrites: Q1, Q6, Q10, Q11, Q13, Q14, Q15, Q21, Q26. Still 27, renumbered in place.

## How to answer

Reply per item with the option letter (e.g. "1B, 4A, 9C…"), or write **"open"** on any you'd rather talk through. **Bold** = my recommended default. Where you confirm a default, the decision gets folded into `DESIGN.md` so it's documented before backend work.

## What's deliberately excluded

- The **prior 18-question audit** (`.scratch/mockup-behavior-audit-brief.md`) — answered + built in the 2026-06-24 wiring pass.
- **UX decisions the refactor already settles** — the Embed/Attach control shape, Inbox sections, Editor rename, block primitive, select-to-act model: those are *design* calls, captured in the brief. This doc asks only the **backend contracts** underneath them.
- Items parked in the **backlog** (`design/TODO.md`): link edges (B17/C8), voice (B5), the attachment-clipboard *mechanics* (B8/B10), transcript-payload source (C6), tasks (C1). The **Review/Inbox formalization** (single-reviewer model + verdict resolution) is explicitly deferred to **B13** by the refactor — surfaced once below (Q15) since the data model should anticipate it.

---

## A. Agent lifecycle & state

**1. Status-state mapping (card vs the new Error type).** Cards show **active / idle / pending**, but the sidecar tracks `connecting / idle / running / error / closed` — and the refactor adds a first-class **Error** Inbox type with rich subtypes (API/model · Tool/MCP · **Environment/connection** incl. *bridge tmux dropped / SDK session lost* · Config · Stalled). So the Inbox now surfaces errors, yet the agent **card** still has no error/connecting state.
- A) **Reconcile: add `connecting` (spawn-in) and `error` (danger) card states, so an Error Inbox card also flips its agent card to `error`; the card's Pending/attention badge jumps to that Error card.**
- B) Errors live only in the Inbox/Messages, never on the card.
- C) Reuse `pending` (warning tone) for errors too.

*Backend needs to know which states the card must render and how `error`/`closed` map to the Inbox Error type.*

**2. What "pending" actually counts.** Pending = "waiting on you." Strictly *any open Inbox item* for that agent (now any of Permission/Plan/Decision/Error), or also a stalled/timed-out run? *(Note the refactor's status-color rework: Error owns danger; pending/attention moves off danger so they don't collide.)*
- A) **Pending = exactly one open Inbox request for that agent, of any type (the binary model DESIGN states); a Stalled run becomes an Error card, so it counts via the Inbox, not a separate signal.**
- B) Pending also fires on a hung/timed-out run independent of any Inbox card.

**3. Retire semantics.** Retire "ends the session" and greys the card. Does the agent's session and history persist?
- A) **Retire kills the live session (tmux/SDK process) but archives its config + transcript so it can be reloaded later (ties to backlog B3 "Load Past Agents"); the greyed card stays until reload, then drops from the roster.**
- B) Retire is a hard delete — nothing persists.
- C) Retire just detaches (session keeps running headless, can re-attach).

**4. Definition of a "turn" (for `Turns 34/50` + auto-stop).** The bar and the Max-turns auto-stop both depend on it, and Claude Code / the SDK count turns differently.
- A) **A turn = one user-prompt → full-response cycle (a "round").**
- B) A turn = each assistant message (so one prompt can advance several turns).
- C) Adopt whatever the SDK's `num_turns` reports verbatim, even if it's not intuitive.

**5. Hitting an auto-stop *limit* (Max turns / Context %).** Runtime behavior the moment a limit is reached? (Graceful wind-down *design* is backlog B19 — this is just the baseline.) *(The refactor fixes the vocabulary: a reached limit is **Lifecycle**, explicitly **not** an Error.)*
- A) **Finish the in-flight turn, then halt the agent into `idle` and drop a Log + (Lifecycle-flavored) Inbox item ("hit Max turns — resume?").**
- B) Hard-stop immediately (interrupt mid-turn).
- C) Soft warning only; don't actually stop.

**6. Error detection, classification & retry.** The refactor turns a failed run into a first-class **Error** Inbox card (**Retry · Dismiss · Reply**), with **Retry = re-issue the last command via the Editor** (manual), and a fixed boundary (*auto-stop limit = Lifecycle; stall/no-progress timeout = Error "Stalled"; model refusal = not Error*). Two backend contracts remain:
- *(a) Detection & classification* of each subtype — who owns it? (e.g. a 529/rate-limit from the API response, *bridge tmux dropped* from the bridge driver, *Stalled* from a no-output watchdog.)
- *(b) Auto-retry?* The earlier `0 retries left` meta implied an automatic retry layer; the brief's Retry is purely the manual Editor re-issue.
- A) **Sidecar owns detection+classification from driver signals + a stall watchdog; *no* silent auto-retry — every error surfaces as an Error card with a manual Retry (drop the `retries left` meta).**
- B) Add a small auto-retry layer for transient API/connection subtypes (N attempts) before surfacing; manual Retry for the rest.
- C) Per-agent config for both retry count and stall timeout (Lifecycle knobs).

---

## B. Inter-agent linking & context-sharing

*(The refactor reserves the word **"Link" for inter-agent links only** — content-sharing moved to Embed/Attach, Section F. These four are untouched by it and remain open.)*

**7. What event *fires* a link.** DESIGN says a link "forwards context from A to B," but never says *on what trigger*. The single biggest undefined contract.
- A) **A link fires when the source agent finishes a turn (goes idle) — its latest output is forwarded per the Trigger timing.**
- B) Fires only when the source posts to Scratch / emits an explicit "handoff" marker.
- C) Fires continuously/periodically (the backlog B12 "dynamic doc" model — defer).

**8. What "Message" payload captures.** Payload = Message/Transcript/Manual. (Transcript's source is already backlogged, C6.) For **Message**, which text exactly?
- A) **The source's final assistant message of the just-finished turn, forwarded as one rendered message.**
- B) The full turn including its tool calls/results.
- C) A summary the dashboard generates.

**9. Bidirectional turn-taking (A↔B).** With both directions on, what stops an infinite ping-pong, beyond the End-After caps?
- A) **Strict alternation: each side only fires after the other goes idle (one in flight at a time); End-After is the hard backstop.**
- B) Free-running both ways, relying entirely on End-After.
- C) Every forwarded message requires a Hold/manual release.

**10. The "Hold" relay surface.** Hold (a link Trigger) = stage a forwarded message for your manual release. The refactor fixes the Inbox at four typed sections — **Permission · Plan · Decision · Error** — none of which is a held-relay, and establishes an "everything routes through the Editor" through-line (Reply, Retry already do).
- A) **Route a held relay into the Editor as a pre-filled `embed` block targeted at the receiver — consistent with the refactor's Editor-routing model.**
- B) Add a 5th **Relay** section to the Inbox (release / edit / drop).
- C) Surface holds in the Console/Log only.

---

## C. Approvals / Inbox

**11. How each Inbox type is *raised* (three now map to native CC surfaces; one is system-detected).** The refactor pins the types down:
- **Permission** = native permission prompt (the sidecar already has `pending_permission`).
- **Decision** = the native **`AskUserQuestion`** tool — one question + options per card, you pick + Approve.
- **Plan** = a native plan (plan mode / ExitPlanMode); Inbox card is **review-only** (Review + Reply) — approval + agent-review verdicts live in the Plans tab.
- **Error** = system-detected (Q6), not agent-raised.

Residual contracts:
- *(a)* Confirm the sidecar **intercepts `AskUserQuestion` tool-calls** ↔ Decision cards and routes the picked option back as the **tool result**.
- *(b)* **How a Plan card is raised** — how does the dashboard learn a native plan is "awaiting review" and which agent owns it? (ties to Q13.)
- A) **Yes to (a); for (b) the sidecar watches plan-mode exits / new `~/.claude/plans/*.md` and ties each to its authoring session (Q13's side-store).**
- B) Decision/Plan are dashboard-operator constructs, not agent-raised, for v1.
- C) Keep Permission + Decision(`AskUserQuestion`) for v1; defer agent-raised Plan cards.

**12. "Always allow" scope & persistence.** Clicking Always-allow on a permission card writes what rule, where?
- A) **Allow that tool+command pattern for *this agent's session* only (in-memory, gone on retire).**
- B) Persist it to the project `.claude/settings.json` allow-list (affects future agents too).
- C) Per-agent, but persisted with the agent's saved config/setup.

---

## D. Plans review (plans are native CC `~/.claude/plans/*.md`; review layer is a dashboard invention)

**13. Plan↔agent mapping + where review data lives.** A plan file has no notion of owning agent, verdicts, or comments — yet the Library shows owner badges, Approve/Revise/Block tallies, and multi-agent feedback, and the refactor moves **all** plan approval + agent-review verdicts into the Plans tab (so the side-store carries even more).
- A) **Sidecar maintains a side-store (small DB/JSON) keyed by plan filename: owner agent, state, and all comments/verdicts; edits to the plan body write back to the `.md`, but review metadata never touches the file.**
- B) Embed review metadata in the `.md` itself (frontmatter/HTML comments).
- C) Review metadata is ephemeral (lost on reload).

**14. Approve/Reject → the paused agent (now Plans-tab-only).** The refactor strips Approve/Reject from the Inbox Plan card (Review + Reply only); all plan approval happens in the **Plans tab**. The underlying contract is unchanged and still open: when you Approve in the Plans tab, what does the authoring agent do?
- A) **Approve resumes the agent out of plan mode into execution; Revise sends the flagged sections back as a new prompt; Reject ends the plan and notifies the agent. (Requires the agent parked in plan mode awaiting the verdict.)**
- B) Approve is informational only — you still manually prompt the agent to proceed.

**15. Cross-agent plan review routing (acknowledged direction; formalization explicitly deferred to B13).** The refactor restyles the Plans **Review** control to a **single-agent reviewer select** (P4c) as groundwork for a single-reviewer model, but explicitly **defers** the workflow — how an agent reviewer's verdict resolves, and how the human gate relates to agent review — to TODO **B13**. Worth confirming the intended *eventual* shape now so the data model anticipates it:
- A) **Review hands the plan to one reviewer agent as a structured task; its verdict returns as a Feedback entry in the Plans tab; the human keeps the final Approve/Reject gate.**
- B) Agent reviewers are advisory only; never gate.
- C) Leave fully deferred — don't model reviewer agents yet.

---

## E. Shared scratchpad

**16. Storage + attribution mechanism.** The mockup writes `~/.claude/shared/scratchpad.md`. A raw `.md` can't carry per-post "agent + timestamp" attribution, yet the Scratch tab shows both.
- A) **Posts route *through the sidecar* (an append API) which stamps agent + time and keeps the structured post log; it also materializes a plain `scratchpad.md` agents can read. Agents post via a known mechanism (a slash command / tool the sidecar intercepts).**
- B) Agents write the file directly and the dashboard parses a strict per-line format for attribution.
- C) Scratch is dashboard-internal only; agents don't actually read/write a real file yet.

**17. Do agents auto-read the scratchpad?** Or is it write-only from their side until something injects it?
- A) **Write-in / read-out is human-facing only; an agent receives scratch content only when it's explicitly sent to it (Editor → Scratch target, or a link).**
- B) The scratchpad is auto-injected into every linked agent's context on each turn.

---

## F. Prompt send semantics (Compose → **Editor**)

**18. Timing (Now / Inject / Next / Queue) — server-side model.** The sidecar `send` is fire-now today; no per-agent queue or boundary detection. These four also differ in feasibility across the **sdk** vs **bridge** drivers.
- A) **Build a per-agent server-side prompt queue + turn-boundary detection so all four are real; document that `Inject` may degrade to `Next` on whichever driver can't do mid-run injection.**
- B) Implement Now + Queue for v1; mark Inject/Next as "planned" in the UI until the driver supports boundaries.
- C) Treat all four as the same immediate send for v1 (labels only).

**19. "Send as <agent>" (From = an agent).** Sending a prompt *as* an agent — literal user-style message attributed to the source, or a link-style relay with sender/trigger front-matter?
- A) **It injects into the target as a normal prompt tagged with the source agent's identity (reuses the link sender-metadata wrapping); it is not a persistent link.**
- B) It actually creates/uses a one-shot link under the hood.

**20. AI utility passes — Revise *and* Summarize.** Both rewrite/condense content with an LLM call: **Revise** (Grammar/Language/Refactor) rewrites a prompt before send (lives in the Editor footer post-rename); **Summarize** condenses selected cards into a slide-over (Messages/Scratch/Log; *not* folded into Embed/Attach — it stays a feed control). Same new backend capability.
- A) **One shared sidecar "utility-LLM" endpoint runs both on a cheap fixed model (e.g. Haiku); Revise returns to the Editor for review before Send, Summarize fills the slide-over.**
- B) Route each through the currently-focused agent's own model.
- C) Defer both to post-v1 (keep the buttons inert / mock-only for now).

**21. Embed vs Attach — backend realization (supersedes the old attachment question).** The refactor collapses content-sharing into two Editor-routed modes and fixes the *mock* contract: **Embed** = a **frozen inline quote** of the selected text dropped into the prompt body (with a "from <source>" header); **Attach** = a **path reference + a hardcoded "read this" instruction**, and for content with no real file (a message, a multi-block selection, "the whole reply") the model is **materialize-to-a-temp-file-and-reference-it**. The brief leaves the real implementation as backend:
- *(a) Embed* → inject the quoted text inline into the outgoing prompt (point-in-time copy, no liveness). Confirm.
- *(b) Attach* → for real files inject the path; for pathless content, **where do materialized temp files live, what's their naming / lifecycle / cleanup**, and how is a multi-block "whole reply" bundled into one file?
- *(c) Cross-agent path reachability* → an Attach from Agent A sent to Agent B must resolve from B's cwd/filesystem (incl. the WSL2↔Windows boundary and differing cwds). Who rewrites/normalizes the path?
- A) **Embed = inline text injection; Attach = path ref, with pathless content materialized into a per-session temp dir (under the sidecar's workspace, cleaned on retire); the sidecar normalizes paths to be reachable by the receiving agent.**
- B) Attach always materializes a temp file (even for real files) for a uniform, always-reachable path.
- C) Embed-only for v1; defer Attach's temp-file machinery.

---

## G. Console (raw terminal + slash commands)

**22. Console feed source by driver.** The Console "faithfully mimics a real Claude Code terminal." Literal for the **bridge** driver (`capture-pane`), but the **sdk** driver has no TUI.
- A) **Console is full-fidelity for bridge agents; for sdk agents it renders a reconstructed terminal-style view from the event stream (same surface, sourced differently).**
- B) Console is bridge-only — hidden/disabled for sdk-backed agents.
- C) Always reconstruct from events (never use real capture-pane), for consistency.

**23. Slash-command execution & interactive commands.** The catalog runs commands against the focused agent. Many are TUI-interactive (`/model`, `/clear`, `/compact`) and some mutate state the dashboard mirrors. *(The refactor reinforces the Console is reference-only — Error **Retry** and Reply route through the Editor, "not the Console.")*
- A) **Run commands by sending the literal text to the agent; commands that have a dashboard home (`/model`, `/compact`…) route to that control instead and just *echo* in the feed; genuinely-interactive ones are gated/queued. Define the per-command routing table.**
- B) Only run non-interactive informational commands (`/status`, `/cost`…); everything else routes to its dashboard control.

---

## H. History, Setups, recovery, identity

**24. History scope & persistence.** History cards carry delivery states (Active/Queued/Next/Held/Complete) — exactly the queue states from Q18.
- A) **History is the per-agent prompt log derived from session events, persisted across reload/reconnect; the db-* states reflect live queue position and resolve to Complete.**
- B) History is session-memory only (cleared on reload).

*Stop (icon-only danger in both the History and Messages footers, both "stop this run") = interrupt the agent's active run — confirm it maps to the existing `/interrupt` endpoint scoped to that agent.*

**25. What a "Setup" captures and does on Load.** Setups save "agents + links." (Related to the Scratch note about renaming session→project.)
- A) **A Setup is a config blueprint — roles/names/models/modes/links — and Load spawns fresh, empty agents from it (no in-flight context carried).**
- B) A Setup also snapshots live context/transcript and Load restores running state.
- C) Setup = blueprint, but Load *offers* to also restore the last transcript per agent.

**26. Crash/reconnect surfacing + the live-update architecture.** The sidecar reconnects sessions and tmux is the recovery net. The refactor's **Environment/connection** Error subtype now explicitly names *bridge tmux session dropped / SDK session lost* — so a dropped session has a home (an Error card). Still unspecified: the **recovery** affordance and the cross-agent stream (the Feed/Graph/Inbox are aggregations, while the sidecar streams SSE *per session*).
- A) **On a dropped/recovered session, raise the Error card *and* show a brief "reconnecting" card state; expose one aggregated event stream the dashboard subscribes to (vs. the frontend fanning-in N per-session SSE streams + merging).**
- B) Per-session streams; frontend merges; the Error card is the only crash signal (no separate reconnecting state).

**27. Identity uniqueness past 16 agents.** "One identity per agent" rests on a 16-color jewel palette. With >16 agents, colors must repeat.
- A) **Auto-assign the next free color+icon on Create (user can override); past 16, repeat color but force a distinct icon so the pair stays unique.**
- B) Let colors repeat freely past 16 (rely on icon + name).
- C) Cap practical fleets at 16 distinct identities.

---

*Source review: the refactor brief `dev/prompts/link-behavior-refactor.md` (target intent, P0 built / P1–P4 in flight), DESIGN.md, the mockup JS data model (`AG`, `REQS`/`REQ_META`, `LINKS`, `PLANS`, `MSGS` incl. the `status:'failed'` row, `TURNS`, `FEED_SUMMARIES`, `TEMPLATES`, …), `tokens.css`, `design/TODO.md`, and the sidecar/bridge backend seam.*
