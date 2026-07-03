# System Coverage Audit — Orphaned Elements for the Final Build

Date: 2026-07-02

## What this is

A **completeness / coverage audit** answering the question the session set out: *"Between the settled body of
`docs/ARCHITECTURE.md`, its §10 open-questions queue, and `design/DESIGN.md`, is the WHOLE intended system
accounted for — or has something fallen through a crack?"* This note flags the **major elements the final
build will likely need that are NOT adequately homed** in those three places. It's a triage note only — it
does not change ARCHITECTURE.md, DESIGN.md, or TODO.md; it says where each orphan *should* land.

**Lay-language note:** every item carries an *In plain terms:* line (denoted in italics) written for a
non-engineer.

## How it was produced

Two independent passes, then adversarial verification of every candidate against the actual doc text:

1. **A six-lens audit** — separate sweeps of (a) DESIGN controls → system-intent, (b) cross-cutting
   production concerns, (c) backend TODO / candidates-note / code no-ops, (d) research notes → unhomed
   decisions, (e) the TODO backlog/scratch, (f) the frontend strategy. 57 candidates raised; each was then
   handed to a skeptical verifier told to *refute* it by grepping ARCHITECTURE.md + DESIGN.md. 48 survived as
   genuine-orphan or partially-homed; 9 were confirmed already-covered.
2. **A systematic surface enumeration** — walking **every** `data-status` marker (27 `planned` in
   `mockup.html`, 8 `planned` + 1 `undecided` in `gallery.html`), **every** feature-deferral comment in
   `sidecar/` + `frontend/`, and **every** DESIGN panel/control, cross-checked against the body and §10.

**Reassuring result of the enumeration:** all 27+9 dormant-UI markers are already homed (via DESIGN's own
status-marker register + §7.6 / §7.14 / §7.15 / §10-12); the only `undecided` UI element is `inbox-section`
(already tracked as DESIGN OQ-2). The `set_mode/fast/thinking` no-ops, deferred Delete, and global-edit
gating are all homed (§10-1/2/3, §7.12, §7.15). **So coverage is mostly complete** — the body + §10 + DESIGN
account for the large majority of the system. What remains is the focused set below, dominated by a handful
of load-bearing items.

---

## TIER 1 — Load-bearing orphans (resolve before / at the final build)

### 1. Rewind / Handoff / Timeline — no engine-feasibility story anywhere  ⭐ biggest crack
**What.** DESIGN's *Rewind & Handoff* section + the Agent → Details **Timeline** present three v1 controls:
the Timeline point-list of "messages sent to the model," **Rewind** (roll *this* agent back to a chosen point
and resume), and **Handoff** (branch from a point into a *new* agent). A grep of ARCHITECTURE.md returns
**zero** hits for "rewind," "handoff," or "timeline." §9.9's only resume path (`claude --resume`) reattaches
the *whole* session — it cannot truncate-and-resume at message N, nor fork a session from an earlier point.
DESIGN marks only *"richer handoff artifacts"* deferred, treating the **core rollback/fork mechanism as
shipping**.
**Why it's load-bearing.** These are exactly the "don't-yet-know-if-or-how" engine-capability questions §10
exists for — at least as uncertain as the §10 mid-run items — yet presented in DESIGN as finished v1
features. (Handoff's *Create-tab-prepopulation* half **is** homed at §9.2/§7.5; the unhomed part is the
conversation carry / rollback primitive.)
**Where it should live.** A new §10 entry (needs-research/spike: can the bridge truncate-and-resume, and fork
a session from an arbitrary transcript point?), graduating to an ARCHITECTURE §7 body section + `/sessions/
{id}/rewind` and `/handoff` endpoints once proven.
*In plain terms: the app promises a "rewind" button that sends an agent back to an earlier point in its
conversation and a "hand off" that forks the work to a fresh agent — but nobody has written down how, or even
whether the underlying Claude engine can do that.*

### 2. Identity editing — the two guiding docs directly contradict each other
**What.** ARCHITECTURE §7.5 states agent identity (role · number · name · colour · icon) is **"read-only in
v1."** DESIGN's Agent → Details band 1 makes Role / No. / Name / Colour / Icon **pencil-editable + save**.
The code sides with §7.5. (Config fields — model, tools, MCP, plugins, deny — are *not* the conflict; those
are covered by §7.15. The conflict is the identity tuple specifically.)
**Why it matters.** A build agent hits this immediately: do I wire the pencil-edit for name/colour/icon or
not? Two authority docs give opposite answers and nothing tracks the disagreement — the precise kind of crack
this audit was meant to catch.
**Where it should live.** Reconcile in the body: either lift §7.5's "read-only in v1" or mark DESIGN's
identity-edit affordance as post-v1; record the decision.
*In plain terms: one core doc says you can't rename or recolor an agent after creating it; the other draws
edit pencils to do exactly that. They flatly disagree and no one has reconciled it.*

### 3. System-wide fault DETECTION — the detector behind the "System" Error cards is missing
**What.** The System-sourced, fleet-wide **Error card** is well described (§7.2 ⚠Today + §7.8; DESIGN
identity + Inbox Error row). The **detector that raises it is not.** Per-agent errors have a best-effort
classifier and a claimed stall watchdog, but **account rate/usage-cap detection is explicitly punted**
(`inbox.py`: "not derived here"; `main.py` `/usage`: "rate-limit windows intentionally NOT here"), and
**auth-expiry, global-MCP-outage, and the one-card-for-the-fleet coalescing have no detector at all.**
**Where it should live.** A body health/fault-detection subsystem (§5/§7) for the deterministic probes
(tmux/WSL liveness, usage-vs-cap, auth expiry); the unproven harvests (reading rate/usage caps and MCP-outage
signals off the bridge) as §10 entries.
*In plain terms: the app is meant to flash one big red "System" alert when the engine room breaks — WSL down,
usage limit hit, login expired, a shared tool offline — but the thing that actually watches for those and
trips the alert was never built; the alert is only drawn.*

### 4. Frontend rebuild strategy — the settled plan lives only in the transcripts, and §4.4 reads the other way
**What.** The team decided (in-session) to **park** the existing React renderer as throwaway, **rebuild the
real frontend fresh from `design/` mockups**, keep `frontend/src/renderer/api.ts` as the one trustworthy
artifact, quarantine the current code loudly (banner + §11 repo-map marker + a `start-dashboard.bat` note),
and prove "a client can drive the live loop" via a standalone Playwright **`tests/ui/` slice** (NOT by
verifying the parked code). None of this is in the guiding docs. Worse: §4.4's actual text ("the renderer is
the working client of the same design … the port up to the finished mockup/tokens is deferred") reads as
*finish/port the existing renderer* — the opposite plan — and §11 already lists "the `tests/ui/` slice" **as
if it exists** (it doesn't, no ⚠Today).
**Where it should live.** Rewrite §4.4 to the park-and-rebuild-fresh decision with a ⚠Today for the parked
state; add one line designating `api.ts` as the preserve-through-rebuild contract; add a ⚠Today on the §11
`tests/ui/` row and a NEXT UP — BUILD item to actually create it (+ the real-frontend-rebuild item, which is
currently on no queue at all).
*In plain terms: the team quietly agreed to throw away the half-built app screen and rebuild it from the
mockups — but the official spec still says "keep and finish the current screen," and it already brags about a
test folder that hasn't been created. A builder could easily work on the wrong, broken code.*

---

## TIER 2 — Moderate orphans (each needs a home: a §10 entry or a body decision)

### 5. Turns "by-tool" breakdown + the "Coordinating" slice — no data source
The Agent → Details Turns accordion expands to a per-tool breakdown (Read/search · Edit · Bash · MCP ·
Subagent · Web · **Coordinating** · Remaining). Its sibling — *context* by-category — is tracked as **§10-9**,
but the **turns** breakdown and the cross-agent "Coordinating" bucket are UI-only with no defined derivation
(§7.9 covers turn *counting* for caps only). → §10, next to #9.
*In plain terms: the panel shows a chart splitting an agent's work by tool type — including a "coordinating
with other agents" slice — but nobody said where those numbers come from.*

### 6. Voice dictation — the mic is drawn, the speech-to-text pipeline isn't decided
Per-field mics ship on the Compose / Plans / Documents editors; §7.14 names "a voice mic" but gives no
capture → speech-to-text → insert path, and no decision between a client-side Web Speech API and a sidecar
transcription service. → one §7.14 line (if client-only) or a §10 entry. *(Voice **reading**/TTS with speed
control is a separate, purely-backlog idea in TODO scratch — see Tier 4.)*
*In plain terms: there are microphone buttons for dictating prompts, but no plan for what turns your speech
into text — so today they're wired to nothing.*

### 7. Frontend↔sidecar resilience — degraded-UI-on-sidecar-down + polling backoff
SSE reconnect **is** homed (§4.3/`api.ts`) and the "Sidecar offline" chip exists, but there's no defined
**degraded-mode policy** for the poll-driven readouts when `/health` fails and no **backoff** on the fixed
poll cadences. → §4.3 body + a §10/DESIGN degraded-state note.
*In plain terms: if the background service goes down, the app changes one status light — there's no plan for
what the rest of the screen shows or how it recovers.*

### 8. Polling-model scale ceiling — how many agents before it bogs down?
The per-agent bridge `events()` loop polls each agent ~1 s (an O(N) fleet cost that crosses the Windows→WSL
boundary each time). The product is built to run "many agents," but **no ceiling, budget, or
adaptive-cadence/backpressure policy is stated anywhere.** → a §4.3/§6.2 scale paragraph, or a §10
needs-research entry to establish the poll ceiling.
*In plain terms: the app constantly checks in on every agent, but nobody has said how many it can run before
it slows to a crawl.*

### 9. Creating/writing Library documents (`createDoc`) — no endpoint, and §7.16 says the opposite
DESIGN routes several actions through a create-document operation (Export → file, Add-document Paste,
Attach-materialization). §8.2/§8.5 imply dashboard-owned `docs/` are writable, but **there is no create/write
endpoint in §5.2**, and §7.16 carries a sentence ("the dashboard never writes into a content file") that
reads as its negation. → add the endpoint to §5.2 + reconcile the §7.16 wording (new dashboard-owned docs
*are* written; agent-authored content is still never edited). *(Distinct from §10-12, which is cross-boundary
attachment path rewriting.)*
*In plain terms: several "save this to a file" and "paste a new doc" buttons need the app to create a
document on disk, but the backend has no such command — and one line of the spec even says it never does.*

### 10. Hook-driven run-state / permission-mode push channel ("hook event stream")
The research pushes a reliable architecture — agents' HTTP hooks POST run-state / permission-mode to the
sidecar (which already runs a server) — that would de-risk §10-1/4/6/8 "for free." §7.11 records the opposite
default ("detection is screen-state, not hooks") but **never weighs or records the push-stream option.** →
a §10 entry, or a decision woven into §6.2/§7.4/§7.11.
*In plain terms: today the dashboard figures out what each agent is doing by repeatedly reading a screenshot
of its terminal; the research found a more reliable way where each agent reports its own status, and no one
has decided whether to switch.*

---

## TIER 3 — Minor gaps: production-hygiene + research-note reconciliations (one-liners / decided-omissions)

Each is small and mostly needs a recorded decision (often a `§10 Decided omission`) so it isn't re-litigated:

- **Schema versioning / migration** of the committed project store — only the one-time `.awl`→`.awl-cc-dash`
  rename is homed; no `schema_version` stamp or forward-compat policy. → §8 body + policy.
  *In plain terms: the app saves data inside your project, but there's no plan for reading yesterday's saved
  data after a future version changes the format.*
- **Sidecar process supervision (crash/restart)** in the shipped bat-file model — recovery is homed (§9.9)
  but the "who restarts a crashed sidecar" decision for the *two-process* model is only stated conditionally
  inside the unbuilt §10-10. → §2/§9 note or a Decided-omission ("crash = manual relaunch; agents survive in
  tmux"). *In plain terms: nothing watches the background service to restart it if it crashes.*
- **Git-level merge conflicts** on the committed `.awl-cc-dash/` state — §8.7 covers in-process atomic writes
  only; two branches/machines editing the whole-file JSON have no merge policy. → §8.7 policy or
  Decided-omission. *In plain terms: because that data lives in version control, two branches editing it will
  collide, with no plan to untangle it.*
- **Security on an untrusted network** — §2 accepts the no-auth `0.0.0.0` bind at home, but never addresses
  the mutating control API being exposed when the laptop travels onto café/office Wi-Fi. → §2 note or
  Decided-omission (OS-firewall as the boundary). *In plain terms: the service is wide open with no password —
  fine at home, unaddressed on public Wi-Fi.*
- **Sidecar logging / observability** — only ad-hoc stdout; no decided destination/retention for the sidecar's
  own process logs. → §2/§9 note. *In plain terms: the background service keeps no proper log, so a failure
  leaves little trail.*
- **statusLine `context_window` as a live mid-run context source** — research documents a per-turn push
  readout, but DESIGN asserts context "can't be read mid-run." → fold into §10-9 + reconcile DESIGN.
  *In plain terms: the design says memory-usage can't be checked while an agent is busy, but a built-in live
  readout exists and no one decided whether to use it.*
- **Unrecorded decision: forgo the stream-json control API** (`set_permission_mode` / `set_max_thinking_
  tokens`) to keep the interactive TUI — the "no API exists" wording in §10-1/2 is really *TUI-scoped* (the
  SDK path *does* have it). → record the trade-off in §6 (and correct the wording). *In plain terms: there's
  actually a clean built-in remote control for safety-mode/thinking, but the "real terminal" choice can't use
  it — and the docs don't say that was deliberate.*
- **Console `/clear` (and `/compact`) can orphan a resolved transcript path** — running these from the
  Console writes a new JSONL without updating the persisted mapping. → §8.7 "spots to watch" note.
  *In plain terms: clearing history from the built-in terminal quietly starts a new log file the dashboard
  can lose track of.*
- **Launch preconditions for the Bypass & Auto permission-mode segments** — Bypass needs a launch flag, Auto
  needs eligibility/opt-in; both could silently no-op. → §6.2/§7.11 or fold into §10-1's POC.
  *In plain terms: two of the five safety-mode buttons only work if the agent was launched a special way, and
  the setup notes don't say so.*
- **Usage/limits source-boundary confirmation** — §7.15/DESIGN assert account-from-creds + limits-from-API
  but it's unverified. → a confirmation line in §7.15 before the Usage UI is built. *In plain terms: the docs
  confidently name where account + usage data come from, but nobody checked those sources can deliver it.*
- **Response-format preamble behavior** — the control is homed; its **option set + apply/persist model** are
  not. → §7.14 clarification. *In plain terms: there's a control for how agents format answers, but nothing
  defines the choices or how the instruction reaches the agent.*
- **Human-name pool / "randomize" source** — Create's randomize-name affordance and any auto-name have no
  defined pool (deferred in `identity.py`). → one §7.5 line, or fine-as-backlog if names are user-typed.
  *In plain terms: the "shuffle a fresh agent name" button has no list of names to draw from.*

---

## TIER 4 — Confirmed parked in TODO (nothing lost — but a few worth elevating)

These live only in `dev/notes/TODO.md` (backlog/scratch), absent from the guiding docs. Most are legitimately
fine as backlog; the audit confirms they exist so nothing is silently dropped. **Worth considering for
elevation** (recurring / substantive user asks) are marked ⬆.

| Item | Current home | Note |
|---|---|---|
| ⬆ **Rich visual content in Plans/Docs** (mermaid, charts, diagrams + visual commenting) | TODO SCRATCH (3 bullets) | Genuinely unhomed in DESIGN; a recurring ask. → DESIGN if pursued. |
| ⬆ **Authors / authorship view** for Plans & Documents | TODO SCRATCH | Provenance *data* is homed (§8.5); the *display* (a 3rd nav-rail "Authors" mode) isn't. → DESIGN. |
| ⬆ **Subagent creation / management UI** | TODO B4 | Observability (§7.17) + pending-vs-active (§10-8) + native-spawn (§10-13) homed; the *create/steer* affordance isn't. → §10 research or DESIGN. |
| **On-demand per-agent resume** (load one past agent by name/ID) | TODO B1 | Mechanism homed (§9.9 / BUILD #8); the user-triggered mid-session load is the unhomed slice. |
| **Save Response Summary** | TODO D4 | Small wiring gap on a designed feature (Summarize slide-over → existing Export→Documents). |
| **Queue-awareness front-matter** for >2 linked agents | TODO B3 | Refinement atop homed link machinery (§7.3/§7.6); not build-blocking. |
| **Git automation + agent-id on commits** | TODO B5 / SCRATCH | Feature idea; only commit-*event* attribution is adjacent-homed (DESIGN Log). |
| **Docs-on-demand / systems-work docs to agents** | TODO B12/B13 (open) | Research-flavored; fine as backlog. |
| **Drag-in files from explorer** | TODO D1 | Destination homed (attachment strip + §10-12); only the drop gesture is unhomed. |
| **Dense link-graph readability** | TODO D3 | Depends on D2 link-edges (`planned`); parkable until edges exist. |
| **Notes Hub** (dedicated operator-notes surface) | TODO D5 | Need is met by Library → Documents; a *dedicated* surface is an undecided design idea. |
| **String search in text fields · Inline spellcheck squiggles · Highlight-to-define · TL;DR emoji output preset** | TODO SCRATCH | Small polish; several come nearly free (contenteditable spellcheck; response-format preset). |
| **Voice reading (TTS) with speed control** | TODO SCRATCH | Distinct optional accessibility feature; unhomed. |
| **Charcoal / dark-theme redesign · Injectable prompt snippets · Re-add ToDo UI · Artifacts tab · Desktop-activity tracking** | TODO SCRATCH | Speculative ("I want to consider…", "Needs more research"); the SCRATCH bucket is their correct home. Desktop-activity is the biggest/most-sensitive if ever pursued → §10. |
| **Housekeeping H1–H7 · backend B6–B8/B14–B15 · markdown-vs-JSON rule** | TODO H/B; §8.2 | Confirmed already homed or correctly backlog — no action. |

---

## TLDR

- **Coverage is mostly complete.** The body + §10 + DESIGN account for the large majority of the system; all
  36 dormant-UI (`data-status`) markers and the main code no-ops are already homed. The gaps below are a
  focused set, dominated by ~4 load-bearing ones.
- **① Rewind / Handoff / Timeline** — the single biggest crack: a full v1 Details feature (roll an agent back
  to a point; fork a new agent from a point) with **zero** system story and no §10 entry, despite being an
  unproven engine-capability question. **→ §10 needs-research.**
- **② Identity editing** — `docs/ARCHITECTURE.md` §7.5 says identity is *read-only in v1*; DESIGN draws edit
  pencils for name/colour/icon. **A direct doc-vs-doc contradiction, untracked. → reconcile the body.**
- **③ System-fault detection** — the fleet-wide "System" Error card is drawn but the **detector** (rate/usage
  caps, auth expiry, MCP outage, infra-down, coalescing) was never built. **→ body health subsystem + §10.**
- **④ Frontend rebuild strategy** — the park-and-rebuild-fresh / keep-`api.ts` / `tests/ui`-slice plan lives
  only in transcripts; §4.4 documents the *opposite* (finish/port) and §11 lists `tests/ui/` as if it exists.
  **→ rewrite §4.4 + §11 ⚠Today + NEXT UP — BUILD items.**
- **Moderate (need a home):** Turns by-tool/"Coordinating" breakdown (→§10 by #9) · voice-dictation STT
  pipeline · frontend degraded-mode/backoff · polling scale ceiling · `createDoc` endpoint vs the "never
  writes" line · the hook-event-stream architecture decision.
- **Minor (record a decision / Decided-omission):** schema versioning · sidecar crash-supervision · git-merge
  on the committed store · security-on-untrusted-network · sidecar logging · plus research reconciliations
  (statusLine mid-run context, stream-json control-API rationale, Console `/clear` transcript re-resolution,
  Bypass/Auto launch preconditions, usage-source confirmation, response-format behavior, human-name pool).
- **Parked in TODO (nothing lost):** a long backlog tail is captured and mostly fine there. Three are worth
  elevating into the guiding docs if pursued: **rich visual content (mermaid/charts) in Plans**, an
  **Authors/authorship view**, and **subagent creation/management UI**.
- **One framing takeaway for the team:** *a control being drawn in DESIGN is not the same as it having a
  system home.* Rewind/Handoff and the turns breakdown are the cases where "it's in DESIGN" masked the absence
  of any backend/engine-feasibility story — which is precisely what §10 is for.
