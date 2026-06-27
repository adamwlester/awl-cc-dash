# AWL Dashboard — Master Functionality-Coverage Map

**Date:** 2026-06-27 · **Driver focus:** bridge-first (the primary path) · sdk noted only where it materially differs.

This is the single master checklist inventorying **every capability the intended UI commits to**, each mapped to its **backend reality**. It ends the piecemeal pattern where gaps surfaced one at a time. It **extends** the partial capability map seeded in `DEVLOG.md` (the `2026-06-27 07:33` "Bridge data layer" entry — control surface + transcript-derivability findings) and the `2026-06-27 09:15` "Part 1 backend builds" entry, out to the **whole UI surface**.

**Authority for intent:** `design/DESIGN.md` + `design/mockup.html` (visual authority; static — every live behavior there is seed data or a `toast()`). **Authority for reality:** `sidecar/` + `bridge/` code + `dev/notes/agent-qa/ui-behavior-questions-2026-06-26-v5.md` (the per-question backend-reality analysis, cited as "QA Qn").

---

## How to read this map

Each capability is one row:

| Column | Meaning |
|---|---|
| **Capability** | the concrete UI thing the design commits to |
| **Data needed (source · status)** | the data it needs · where it comes from (`transcript` / `screen`-scrape / `synthesized` by the sidecar / `filesystem` / `none`) · its availability status |
| **Control needed (status)** | the action/control it needs · its status (`—` = read-only, no control) |
| **Build** | current build state: `built` / `partial` / `not-started` |
| **Evidence** | terse pointer — a `file:symbol`, a DESIGN section, or a `QA Qn` |
| **MVP** | priority `P0` (an MVP can't ship without it) → `P3` (deferred/cosmetic) |

**Data/Control status taxonomy** (used exactly):

- **`proven`** — live-verified working below or through the UI.
- **`derivable-not-built`** — reliably obtainable from existing channels (transcript / screen / files), but no code surfaces it yet.
- **`needs-investigation`** — plausible but unverified, or carries an open design fork.
- **`impossible`** — the bridge's two channels (tmux `capture-pane` + JSONL transcript) genuinely cannot supply it.

> **The bridge knows things from exactly two channels** — tmux `capture-pane` (screen text, a 4-value state enum) and the JSONL transcript — **polled ~1s. It samples; it does not stream.** Every "screen"/"transcript" source below is bounded by that.

---

## Backend reality in one screen (the foundation)

### ✅ Proven / built today — the bridge foundation an MVP rides on

- **Controls (live-verified):** `model` (`/model`), `effort` (`/effort`), `interrupt`/Stop (Ctrl+C), **permission round-trip** (approve=Enter / deny=Escape — **binary**, no always-allow), **resume/reconnect** (survives a sidecar restart via `runtime_store`), and — **new this round** — **permission mode AT LAUNCH** (`claude --permission-mode`, bypass gate auto-cleared).
- **Data (live, from the transcript via `GET /context`):** **total context %** (cumulative `input+cache_read+cache_creation` ÷ a **model-aware window** — 200K default, 1M only for 1M-context models — from the latest main-line assistant entry), **work-step count**, and the **by-tool Turns breakdown** (read/edit/bash/mcp/subagent/web/other + total).
- **Endpoints new earlier:** **`GET /sessions/{id}/subagents`** (subagent presence/count/type/running-vs-done/usage, paired from the parent transcript; live-verified), and **honest `set_mode`** (HTTP 400 on bridge instead of a false "ok").
- **The working flow:** `create → send → render (assistant/user content blocks) → idle → delete` round-trips cleanly on the bridge default.

### ✅ Built this round (2026-06-27 — additive backend, all bridge-first & live-verified)

- **Per-agent launch config (applied AT LAUNCH via native flags — a running TUI can't be re-scoped).** Extended `DriverConfig`/`CreateSessionRequest`/`TmuxBridge.create()`/`SessionState.to_dict` with: **allowed/disallowed tools** (`--allowedTools`/`--disallowedTools`), a **permission-rules object** {allow,deny,ask} and **per-agent plugin enablement** {`"id@mkt"`: bool} (both injected via a per-agent `--settings` file written to a WSL path), and **per-agent MCP scope** (a chosen server subset → a per-agent `--mcp-config` + `--strict-mcp-config`). The applied config is surfaced on `to_dict.launch_config`. **Live-proven through the dashboard:** an agent came up with `Bash=no` (disallowedTools), `Glob=no` (settings.deny), `Read/Edit=yes`; scoped to **only `exa`** via `/mcp`; and with **superpowers skills present** via enabledPlugins. **Load-bearing caveat (live-confirmed):** `--allowedTools` is IGNORED under `bypassPermissions` (a claude bug) — `--disallowedTools` / `permissions.deny` are the reliable hard-blocks.
- **Settings registry READ endpoints** (`GET /settings/mcp`, `/settings/plugins`, `/settings/config`; `?project=<path>` scopes the project reads). Real WSL-side data via a new `bridge/registry.py`: MCP servers user+project with enabled state (env **values masked** to `env_keys`); installed plugins (authoritative `enabled` from `claude plugin list --json`) + marketplaces; Config global+project (model/effort/mode/sandbox/env/hooks/perms/plansDirectory/CLAUDE.md), each field tagged **Live vs New-session**. Reads only — toggles/writes are a later run.
- **Usage aggregate** (`GET /usage`): per-agent tokens/window/percent/work_steps + **fleet totals** + the footer **token pill** value. Reuses `derive_context_usage` (now **model-aware**: 200K default, 1M for 1M-context models).
- **The working flow still passes** post-change (vanilla `create→send→render→idle→delete` round-trip re-verified).

### ⛔ Hard ceilings on bridge (do not promise these)

- **Mid-run permission-mode change** — only Shift+Tab cycles; no absolute set. `set_mode` honestly 400s. **Under separate research.**
- **Fast-mode** (`/fast` opens an interactive panel that can't be scraped) and **Thinking toggle** (`/thinking` doesn't exist in this CC build) — both honest 400s; **cosmetic until wired** (likely via the sdk path). The Opus-only FAST gate is a pure client check.
- **Run-strip completion %** — no source exists; the barber-pole indeterminate is the honest fallback.
- **Subagent pending-vs-active** — subagents are opaque until the Task returns, so only **running-vs-done** is observable; the `s1/s2` ids are **dashboard-minted**, not driver-sourced.
- **`AskUserQuestion` (Decision)** and **plan-mode (Plan)** detection from screen-state — the menus lack the `1. Yes` anchor / there's no distinct plan state, so the bridge is blind to them (net-new transcript-level interception).
- **Per-agent cost / $ spend** — bridge emits none (`total_cost_usd` stays 0.0). Out of scope by design.

### 🔧 The big net-new backend buckets (where the real work is)

1. **Aggregated cross-agent event stream** + **stable per-event ids** + **per-event identity tagging** (each event needs an `agent_id`/sender). **The keystone** — the merged Messages stream, the From/To filter, per-message badges, the Log, the Inbox fleet badge, and the multi-agent Graph all depend on it. Today: SSE exists *per session*, but the live frontend **polls `/history` every 800 ms** with array-index keys.
2. **Sidecar-owned prompt queue + turn-boundary/idle detection.** Unblocks **Send-timing** (Now/Queue/Next), **link triggers**, and **lifecycle enforcement**. Today `/send` while running **409s and drops** the prompt.
3. **Linking & context-sharing** — *the defining feature* — has **zero backend**.
4. **Shared scratchpad** — fully net-new (no field/endpoint/storage); needs an append API + a WSL-reachable materialized `.md`.
5. **Embed/Attach materialization** + **WSL2↔Windows path normalization** for pathless content.
6. **Inbox raise-paths beyond Permission** — Error/Stall detection (screen pattern-match + watchdog), Warning (limit watchdog), Decision (`AskUserQuestion` interception), Plan (plan-file/plan-mode detection).
7. **Lifecycle caps** (`max_turns` / context-%) — no field, no enforcement today.
8. **Persistent stores** with nothing backing them: History prompt-log, "last command" (Retry), Plans review side-store, templates, assets/media, Setups blueprints, the agent **identity registry**.
9. **Settings** — file-registry **reads** ✅ BUILT this round (MCP/Plugins/Config from `~/.claude.json`, `claude plugin list --json`, `~/.claude` + `.claude` settings via `bridge/registry.py`); the Usage token rollup ✅ BUILT (`/usage`). Still net-new: **gated writes** (enable/disable toggles, the confirm-gated global edit) and the Usage **plan/limits** band (see Part-4 report: OAuth-credential tier is local, but live rate-limit windows are API-only). Plus **per-agent scope** (which tools/plugins/MCP an agent may use) ✅ BUILT at launch — a different axis from the global registry, exactly as DESIGN separates them.
10. **Per-category context breakdown** — proven-available **only** by sending `/context` to the TUI and parsing the table it writes (queue it until the agent is idle — never interrupt a run); plus **Compact** (`/compact` round-trip) and per-turn attribution.
11. **Utility-LLM passes** (Revise / Summarize) — a cheap fixed model, the explicit candidate for the **sdk** in-process path.

> **The recurring shape:** the live `App.tsx` is a ~571-line two-pane stub with **zero** model/mode/effort/permission UI, so a great many `P0`s are *"backend proven, frontend not-started"* — the MVP is largely a UI build over an already-capable bridge layer, **plus** buckets 1, 2, and the identity store as the foundational new backend.

---

## Ranked MVP build order — the checklist that drives subsequent rounds

Phases are a **dependency-ordered build sequence**, not strict priority buckets (a `P0` capability can sit in a later phase if it rides on earlier plumbing — linking is the headline example).

### Phase 0 — Wire the proven foundation through the UI *(little/no new backend; the bridge already supports these)*
- **Team Graph:** agent cards + **selection-drives-the-app** focus wiring; status badge (**active/idle/pending**); **Ctx %** bar; **Turns** count + by-tool; **subagent strip** (count/id/usage/coarse status); created-time; grid + scroll. *(Identity fields need the Phase-1 identity store.)*
- **Agent → Details/Create:** **model set**, **effort set**, **mode-at-launch**, context-usage bar, Turns readout, **core Create** (`POST /sessions`), **Retire** (`close()`). 
- **Prompt + Feed basics:** Compose → **send** (fire-now); **Messages** render (single-agent today); **History** (from session events); **Stop** (`/interrupt`); **permission approve/deny UI** (round-trip proven, no UI yet).
- **Console** raw terminal feed (`capture-pane`/`scrollback`). *(P1)*

### Phase 1 — Foundational backend plumbing *(unblocks the whole multi-agent surface)*
- **Aggregated cross-agent event stream + stable per-event ids + per-event identity tagging.** ⭐ keystone.
- **Agent identity model/store** (role·number·name·color·icon assignment + past-16 uniqueness).
- **Sidecar prompt queue + idle/turn-boundary detection** → Send-timing **Now/Queue/Next**.
- **Error/Stall detection** (+ the Inbox **Error/Warning** sections, the 4th run-state on the card).
- **Lifecycle caps** storage + enforcement (`max_turns` / context-%): on hit, finish the turn → idle + Log/Inbox notice.

### Phase 2 — The defining feature + sharing *(built on Phase 1)*
- **Linking & context-sharing** — create/persist, Direction, Trigger (**Now/Queue/Next** real; **Inject** likely degrades to Next), Payload **Message**, **End-After**, **fire-on-idle**, bidirectional strict-alternation. *(P0 by design; sequenced here because it rides on the event stream + queue.)*
- **Shared scratchpad** — append API + attribution + WSL-reachable materialized `.md` (human-facing write-in/read-out for v1).
- **Embed / Attach** materialization + **cross-fs path normalization** + Export→Documents.

### Phase 3 — Rich readouts + review/library + persistence
- **Per-category context breakdown** (queued `/context` scrape) + **Compact** + per-turn attribution.
- **Plans** review **side-store** (owner/state/verdicts/comments) + Documents/Assets **file ops** (read/edit-write-back/Add/Paste/rename).
- **History persistence** + **Retry** "last command" store.
- Templates storage; the attachment/asset media model.

### Phase 4 — Settings + utility passes
- **Settings reads** — MCP/Plugins/Config registries from existing files + **Usage** token rollup + the footer token pill.
- **Settings gated writes** — enable/disable toggles, the **global-edit confirm**.
- **Revise / Summarize** utility-LLM passes (sdk path).
- **Setups** save / load-spawn-many (**tab-less**).

### Phase 5 — Deferred / blocked / cosmetic
- **Fast / Thinking** toggles (impossible on bridge — cosmetic until an sdk path).
- **Run-strip %** (barber-pole only — no source).
- **Mid-run permission-mode change** (blocked — under research).
- **`AskUserQuestion` (Decision)** + **Plan-mode (Plan)** detection + Plan **Approve→resume**.
- **Rewind-to-point**; **Handoff** prepopulation.
- **Links-as-edges** render; **citations**; **marketplaces**; **per-agent cost** (out of scope).

---

## Coverage by surface

> Each area table below is the detailed reference. Where a capability is **shared across panels** its *canonical* backend home is noted: the **event-stream architecture** → Cross-Cutting; the **prompt queue / send-timing** → Cross-Cutting; **subagents** data → Agent Panel (the Graph badge is a view of it).

## Team Graph

| Capability | Data needed (source · status) | Control needed (status) | Build | Evidence | MVP |
|---|---|---|---|---|---|
| Agent card per agent (roster render) | session list + identity fields (none · `proven` for session existence; identity is dashboard-owned config, not driver-sourced · `derivable-not-built`) | — | partial | `GET /sessions` `to_dict()`; identity store net-new (QA "Agent identity") | P0 |
| Selection drives the app (card click → focus agent) | selected session id (synthesized · `proven`, local UI state) | select-a-card (frontend, `not-started`) | not-started | DESIGN "Selection drives the app"; live `App.tsx` 2-pane | P0 |
| Status badge — 4 run-states | normalized status from bridge screen-state + session enum + `has_pending_permission` (screen+synthesized · `proven` active/idle/pending; `derivable-not-built` error) | — | partial | `_STATE_TO_STATUS`, `_detect_state`; `has_pending_permission`; QA Q1/Q2 | P0 |
| → "active" / "idle" | bridge `generating→running` / `idle→idle` (screen · `proven`) | — | built | `_STATE_TO_STATUS`; `_detect_state` | P0 |
| → "pending" | `has_pending_permission` off `permission_request` event (screen · `proven`); Plan/Decision/stall raise-paths `needs-investigation`/`impossible` | — | partial | `permission_request`/`_resolved` in `events()`; QA Q2 | P0 |
| → "error" (4th run-state) | pattern-match error text on `capture-pane` + stall watchdog; tmux-gone is structural (screen+synthesized · `derivable-not-built`) | — | not-started | DESIGN "error … danger bar"; QA Q6 | P1 |
| → bridge `unknown` handling (hold-last-state) | no status emitted for `unknown` → card freezes (screen · `proven` gap) | — | partial | `_STATE_TO_STATUS` omits unknown; QA Q1 | P1 |
| Status badge as shortcut button (jump to Inbox/History/Compose) | the card's current state (synthesized · `proven`) | navigate-to-tab (frontend, `not-started`) | not-started | DESIGN "The badge is also a shortcut button" | P2 |
| Age/created stamp (+ auto-scaling "ago") | `created_at` ISO (synthesized · `proven`) | — | built | `SessionState.created_at` → `to_dict()` | P1 |
| Identity row — role / number / name | dashboard-owned identity (none from driver · `derivable-not-built`) | edit identity (Agent panel; `not-started`) | not-started | DESIGN "Agent identity"; no field in `SessionState` | P0 |
| Identity row — model | `session.model` (synthesized/transcript · `proven`) | set_model (`proven`) | built | `to_dict()` model; `/model`; DEVLOG 07:33 readback | P1 |
| Identity row — opus-only FAST bolt | real fast on/off (screen · `impossible`); opus-gate is a client check (`proven`) | toggle fast (`impossible` — `set_fast` 400) | not-started | `set_fast` no-op; QA Q10 | P3 |
| Settings chip — mode (value readback) | permission-mode (transcript · `proven`) | set mode mid-run (`impossible` — 400; launch-only) | partial | `set_mode` 400; mode-at-launch (DEVLOG 09:15) | P2 |
| Settings chip — effort (value) | effort readback (screen · `needs-investigation`) | set_effort (`proven`) | partial | `set_effort`; `/effort`; DEVLOG 07:33 | P2 |
| Settings chip — think (value) | thinking state (screen · `impossible`) | toggle thinking (`impossible` — 400) | not-started | `set_thinking` no-op; DEVLOG 07:33 | P3 |
| Ctx bar — context usage % (health-colored) | `derive_context_usage` percent (transcript · `proven`) | — | built | `derive_context_usage`; `/context`; QA Q11 | P0 |
| Turns bar — live count (numerator) | `work_steps` distinct main-line `message.id` (transcript · `proven`) | — | built | `derive_context_usage` `work_steps`; QA Q4 | P1 |
| Turns bar — Max-turns cap (denominator + health ramp) | per-agent `max_turns` (none · `derivable-not-built`) | set/edit cap (`not-started`) | not-started | No `max_turns` field anywhere; QA Q5 | P1 |
| Turns cap enforcement (auto-stop on hit) | sidecar poll-loop vs cap (synthesized · `derivable-not-built`) | run-loop halt (`not-started`) | not-started | QA Q5b | P2 |
| Run strip — progress % | a real completion % (none · `impossible`); barber-pole is the honest fallback | — | partial | DESIGN "Run strip … honest fallback"; QA Q7 | P1 |
| Run strip — color keyed to 4 states | normalized card status (synthesized · `proven`/`derivable-not-built` for error) | — | partial | DESIGN "Run strip … keyed off status" | P1 |
| Marquee — two-track live-activity line | latest `tool_use` / `generating` screen line, ~1s sample (transcript+screen · `derivable-not-built`) | — | not-started | QA Q8; `events()` yields blocks but not a marquee string | P2 |
| Subagent strip — presence + count | `derive_subagents` count from paired tool_use↔tool_result (transcript · `proven`) | — | built | `derive_subagents`; `/subagents`; DEVLOG 09:15 | P1 |
| Subagent badge — stable id (s1/s2) | dashboard-minted ordinal (synthesized · `proven` as minted; `impossible` as driver-sourced) | — | built | `derive_subagents` mints `s{i}`; QA Q9b | P1 |
| Subagent badge — run-state color (3-state intent) | coarse running/done/error only (transcript · `proven`; pending-vs-active `impossible`) | — | partial | `_subagent_status`; QA Q9a | P1 |
| Subagent badge — type / usage detail | type/description + usage from `toolUseResult` (transcript · `proven`) | — | built | `_subagent_result`; DEVLOG 09:15 | P2 |
| Subagent strip — collapse/accordion | the subagent list (transcript · `proven`) | expand/collapse (frontend, `not-started`) | not-started | DESIGN accordion drawer | P2 |
| Subagent badge — click action | the badge's id (synthesized · `proven`) | click target (`not-started`/`needs-investigation`) | not-started | DESIGN "not yet wired"; QA Q9c | P3 |
| Scaling / grid scroll (many cards) | full session list (synthesized · `proven`) | grid + scroll (frontend, `not-started`) | not-started | DESIGN "Scales past what fits" | P1 |
| Links-as-edges (directed arrows) | link records (none · `impossible` today) | create/configure link (`not-started`) | not-started | DESIGN "Links as edges (planned)"; → Cross-Cutting | P3 |
| Per-agent cost on card | none — bridge emits no cost (`impossible`) | — | not-started (out of scope) | `total_cost_usd`=0; DESIGN out-of-scope | P3 |

## Team Feed

| Capability | Data needed (source · status) | Control needed (status) | Build | Evidence | MVP |
|---|---|---|---|---|---|
| Shared From/To filter — multi-select identity rows (incl. User) | per-event agent identity; events carry no `agent_id`/sender today (synthesized · `derivable-not-built`) | client-side select, persists across tabs (—) | not-started | DESIGN Team Feed; `_entry_to_event` (no identity) | P1 |
| Messages — merged cross-agent attributed stream | per-agent message events exist per-session; merging N + stamping identity is net-new (transcript+synthesized · `derivable-not-built`) | — | partial | `events`/`_entry_to_event` (single-agent proven); QA Q32a | P0 |
| Messages — Type/direction filter (Sent/Received) | direction tag anchored to operator; derivable from role+origin (synthesized · `derivable-not-built`) | client segment (—) | not-started | DESIGN §Messages direction rules | P1 |
| Messages — Content tool-detail filter (Thoughts/Read/Write/Bash/Diffs/Meta) | content in blocks; bridge already classifies tool_use (transcript · `proven` data) | client multi-toggle (—) | partial | `classify_tool`; messages-card rail tags | P0 |
| Messages — per-message agent badge | agent identity per card, not attached today (synthesized · `derivable-not-built`) | — | not-started | `_entry_to_event` (no identity) | P1 |
| Messages — per-message status badge (Active/Complete/Failed) | one status signal mapped to msg enum, not attached per-message (screen+synthesized · `derivable-not-built`) | — | not-started | QA Q1; messages-card enum | P1 |
| Messages — expanded tool-block rail (Turn N + block rows) | turn-grouping of blocks (transcript · `derivable-not-built`) | — | partial | DESIGN rail spec; messages-card render | P1 |
| Messages — select-to-act (block / whole-card) | selection is pure client state (none · `proven`) | client selection (—) | not-started | DESIGN §select-to-act; QA Q25/Q30 | P1 |
| Messages footer — Export (Copy/Export→file/Embed/Attach) | selected span; materialization net-new (synthesized · `derivable-not-built`; Attach `needs-investigation`) | Copy=client; Export→file=new Doc; Embed/Attach (see Cross-Cutting) | not-started | QA Q25/Q26 | P2 |
| Messages footer — Summarize | selected cards' text → utility-LLM (synthesized · `derivable-not-built`) | net-new utility-LLM pass (sdk path) | not-started | QA Q25 | P2 |
| Messages footer — Stop | run-state (screen · `proven`) | `/interrupt` scoped to agent (`proven`) | partial | `interrupt`; `/interrupt`; QA Q30 | P0 |
| Scratch — live shared-scratchpad view (attributed+timestamped) | per-post {agent,time,text}; no storage anywhere (synthesized · `derivable-not-built`) | read-only view (—) | not-started | QA Q21 (confirmed absent); → Cross-Cutting | P2 |
| Scratch — posting (agents write in) | append API stamping agent+time + materialized `.md` (synthesized · `derivable-not-built`) | append API + intercepted slash/tool; WSL path caveat (`needs-investigation`) | not-started | QA Q21–Q22 | P2 |
| Log — synthesized semantic-event stream, color-coded | a fixed taxonomy; coordination events in NO single transcript → sidecar mints (synthesized · `derivable-not-built`) | read-only (—) | not-started | QA Q32b | P2 |
| Inbox — tab fleet-total badge | count of agents with one open request; only `has_pending_permission` exists today (synthesized · `derivable-not-built`) | — | partial | `has_pending_permission`; QA Q16/Q2 | P1 |
| Inbox · Permission (raise) | bridge detects `permission_prompt` (anchored on `1. Yes`) → event pair (screen · `proven`) | Approve=Enter/Deny=Escape (binary; **no always-allow** `needs-investigation`); Reply→Editor (`derivable-not-built`) | partial | `parse_permission_prompt`, `answer_permission`; `/permission`; QA Q16/Q17 | P0 |
| Inbox · Decision (AskUserQuestion, raise) | menu **lacks `1. Yes` anchor** → reads `unknown`; needs transcript-level interception (transcript · `needs-investigation`) | pick→route as tool_result (`needs-investigation`); Reply→Editor | not-started | `_detect_state`; QA Q16(a) | P2 |
| Inbox · Plan (raise) | no distinct plan screen-state; needs plan-file watch + author tie (synthesized · `needs-investigation`) | Review→Library Plans (`derivable-not-built`); Reply; **no Approve/Reject here** | not-started | QA Q16/Q18–Q19; DESIGN Inbox | P2 |
| Inbox · Error (raise) | pattern-match error text + stall watchdog; tmux-drop structural (screen+synthesized · `derivable-not-built`) | Retry=re-issue stored last command (store net-new); Dismiss; Reply | not-started | QA Q6/Q30 | P1 |
| Inbox · Warning (raise) | limit notices (Max turns, ctx-near-limit); caps don't exist (synthesized · `derivable-not-built`) | Acknowledge=client; Reply | not-started | QA Q5; DEVLOG 06-27 04:45 | P2 |
| Inbox — cards expand/select (shared select-to-act) | one request per card (client · `proven`) | header-click select / chevron expand (—) | not-started | DESIGN Inbox cards | P2 |
| Inbox — Reply → pre-fills Editor (embed block, pre-targeted) | card contents → frozen embed block (synthesized · `derivable-not-built`) | client Editor routing (—) | not-started | DESIGN Reply generalized | P2 |
| Inbox — cross-link to Library Plans (Review) | plan↔agent mapping (side-store) (synthesized · `derivable-not-built`) | client jump + highlight (`derivable-not-built`) | not-started | QA Q18; DESIGN cross-link | P2 |
| Cross-agent event architecture (feeds all 4 tabs) | aggregated stream + stable ids; today per-session SSE but frontend polls `/history` 800ms (synthesized · `needs-investigation`) | one aggregated stream + reconnect (`derivable-not-built`) | partial | `/events`,`/history`,`push_event`; QA Q32a; **canonical: Cross-Cutting** | P1 |

## Agent Panel

| Capability | Data needed (source · status) | Control needed (status) | Build | Evidence | MVP |
|---|---|---|---|---|---|
| Header — identity (tile/role/name) | identity tuple (synthesized · `proven`/`derivable-not-built` store) | — | not-started | dashboard-minted; `to_dict` has only agent_type/model | P0 |
| Header — status badge | normalized run-state (screen+synthesized · `proven` active/idle/pending; `derivable-not-built` error) | — | not-started | `_detect_state`; QA Q1/Q6 | P0 |
| Header — created-time + "ago" | `created_at` ISO (synthesized · `proven`) | — | partial | `SessionState.created_at` | P1 |
| Band1 — Role readback/edit (agent.md-driven) | role + `agent.md` front-matter (filesystem · `derivable-not-built`) | edit/save (`not-started`) | not-started | no agent.md parse anywhere | P1 |
| Band1 — No./Name/Description edit | identity fields (synthesized · `proven`) | edit/save (`not-started`) | not-started | no edit endpoint | P1 |
| Band1 — Model readback + edit (mid-run) | model (transcript · `proven`) | `/model` set (`proven`) | partial | `set_model`; `/model`; readback clean (07:33) | P0 |
| Band1 — Skills multi-select | skills files (filesystem · `derivable-not-built`) | edit/save (`not-started`) | not-started | no skills enumeration | P2 |
| Band1 — Tools multi-select | native CC tool set (none · `proven`) | per-agent allow/deny AT LAUNCH (`proven`) | partial | `create(allowed_tools/disallowed_tools)`; `--allowedTools`/`--disallowedTools`; live-verified; bypass-allowlist bug → deny is the hard-block | P2 |
| Band1 — Color / Icon pickers | identity (synthesized · `proven`) | edit/save (`not-started`) | not-started | palettes client; >16 uniqueness net-new (QA Q33) | P1 |
| Band1 — Role-from-agent.md prepopulation (Create) | agent.md front-matter (filesystem · `derivable-not-built`) | populate-on-pick (`not-started`) | not-started | net-new agent.md read | P2 |
| Band2 — Mode segmented (Plan/Ask/Edit/Auto/Bypass) | permission-mode readback (transcript · `proven`) | mid-run set (`impossible` on bridge — 400; `proven` on sdk) | partial | `set_mode` honest 400; sdk has it; DEVLOG 09:15 | P0 |
| Band2 — Mode AT LAUNCH | — | `--permission-mode` on create (`proven`) | built | `TmuxBridge.create(permission_mode=…)`; `VALID_PERMISSION_MODES`; live-verified 09:15 | P0 |
| Band2 — Effort | effort readback (screen · `needs-investigation`) | `/effort` set (`proven`) | partial | `set_effort`; 07:33 | P0 |
| Band2 — Opus Fast-Mode toggle | fast readback (screen · `needs-investigation`) | `/fast` set (`impossible` on bridge) | not-started | `set_fast` 400; Opus-gate client-only; QA Q10 | P2 |
| Band2 — Thinking toggle | thinking state (none · `impossible`) | set (`impossible` on bridge) | not-started | `/thinking` absent → 400; QA Q10/07:33 | P2 |
| Band2 — Lifecycle Max-turns cap | work-step count vs cap (transcript · `derivable-not-built`) | set cap + sidecar enforce (`derivable-not-built`) | not-started | `work_steps`; no `max_turns`/enforcement; QA Q5 | P1 |
| Band2 — Lifecycle Context-% cap | context % vs cap (transcript · `derivable-not-built`) | set cap + sidecar enforce (`derivable-not-built`) | not-started | `percent`; no ceiling; QA Q5 | P1 |
| Band3 — Context-usage bar (total %) | tokens/window/percent (transcript · `proven`) | — | partial | `derive_context_usage`; window hardcoded 1M, not model-aware | P0 |
| Band3 — Compact action | re-derive post-compact (transcript · `proven`) | `/compact` round-trip (`derivable-not-built`) | not-started | CLI `/compact` bridge round-trip; QA Q11c/Q29 | P1 |
| Band3 — Per-category breakdown (System/MCP/Memory/Custom-agents/Messages/Free + cutoff) | category split (screen via `/context` grid · `derivable-not-built`) | queue `/context` when idle (—) | not-started | NOT in transcript (aggregate only); scrape-only, queue til idle; 07:33/QA Q11a | P1 |
| Band3 — Turn-scope select (Total / Turn n) | per-turn `message.usage` sums (transcript · `derivable-not-built`) | — | not-started | new aggregation; QA Q11b | P2 |
| Band3 — Memory-files / Custom-agents sub-inventory | loaded-context inventory (screen via `/context` · `derivable-not-built`) | — | not-started | scrape-only, scope-invariant | P2 |
| Band3 — Turns readout (count) | `work_steps` (transcript · `proven`) | — | partial | lives in `/context`; session `total_turns`=0 on bridge; QA Q4 | P0 |
| Band3 — Turns by-tool breakdown | per-tool counts (transcript · `proven`) | — | partial | `tools`+`tool_total`; `Agent`+`Task`→subagent (07:33) | P1 |
| Band3 — Turns "Coordinating" slice | cross-agent events (synthesized · `derivable-not-built`) | — | not-started | explicitly NOT derived from one transcript; QA Q4b | P2 |
| Band3 — Turns "/Tools used" + "/Coordinated with" drill-downs | raw per-tool calls (transcript · `derivable-not-built`); counterparties (synthesized · `derivable-not-built`) | — | not-started | calls from tool_use; "Coordinated with" synthesized; QA Q4b | P3 |
| Band3 — Timeline point-list | messages-to-model points (transcript · `derivable-not-built`) | — | not-started | `read_log`/`extract_messages` exist, not surfaced | P1 |
| Band3 — Rewind-to-point | timeline point (transcript · `derivable-not-built`) | roll-back + resume (`derivable-not-built`) | not-started | leans on proven `resume`; no rewind endpoint | P2 |
| Band3 — Handoff (branch to new agent) | source config (synthesized · `proven`) | open Create prepopulated (`not-started`) | not-started | Create-prepopulated UI | P2 |
| Footer — Retire (+ confirm) | — | `close()` + drop record (`proven`); config/transcript archive (`derivable-not-built`) | partial | `DELETE /sessions/{id}`→`close()`; archive net-new; QA Q3 | P1 |
| Footer — Delete (permanent, + confirm) | — | wipe config+transcript+links (`derivable-not-built`) | not-started | only `close()` exists; QA Q3 | P1 |
| Subagents (presence/count/type/running-vs-done/usage) | spawn+result pairs (transcript · `proven`) | — | built | `/subagents` + `derive_subagents`; live-verified 09:15; pending-state `impossible` (QA Q9) | P1 |
| Create — all fields | field defaults (mixed · `proven` core / `derivable-not-built` skills/tools/agent.md) | `POST /sessions` (`proven` core) | partial | `CreateSessionRequest` has model/permission_mode/cwd/system_prompt/driver; no effort/fast/thinking/max_turns/skills/tools/identity | P0 |
| Create — Create / Reset / Cancel | — | create (`proven`); reset/cancel client (`proven`) | partial | `POST /sessions`; effort/lifecycle/identity not in payload | P0 |
| Create — Handoff lands here prepopulated | source config (synthesized · `proven`) | prepopulate (`not-started`) | not-started | net-new wiring | P2 |
| Console — raw terminal feed (capture-pane/scrollback) | screen + history (screen+transcript · `proven`) | — | not-started | `capture-pane`/`scrollback(10000)`; samples ~1s; sdk has no terminal; QA Q28 | P1 |
| Console — slash-command catalog | static catalog (none · `proven` client) | — | not-started | pure client list; QA Q29 | P2 |
| Console — slash-command runner (per-command routing) | echo into feed (screen · `proven` for clean cmds) | `keys`/`send` into TUI (`proven` for `/model`,`/effort`; `impossible` for interactive `/fast`,`/thinking`) | not-started | routing table net-new; QA Q29 | P2 |
| Console — Expand step-into | — | client layout (`proven`) | not-started | pure UI reflow | P2 |

## Prompt

| Capability | Data needed (source · status) | Control needed (status) | Build | Evidence | MVP |
|---|---|---|---|---|---|
| From / Source single-select (User or agent) | session roster (synthesized · `derivable-not-built`) | select source (`derivable-not-built`) | not-started | no `from`/sender on `/send`; `SendPromptRequest` is `{prompt}` | P0 |
| Send-as-agent (From=agent, tagged one-shot) | sender identity to wrap (synthesized · `needs-investigation`) | tagged prompt wire-format (`needs-investigation`) | not-started | net-new; not a standing link; QA Q24 | P2 |
| To / Target multi-select (multiple agents) | roster (synthesized · `derivable-not-built`) | fan-out send to N sessions (`derivable-not-built`) | not-started | `/send` single-session; bridge `broadcast()` unused | P0 |
| To = Scratch target | scratchpad store (synthesized · `impossible` today) | append-to-scratchpad API (`not-started`) | not-started | no scratchpad anywhere; QA Q21; → Cross-Cutting | P2 |
| Editor contenteditable (free prose send) | — | type+Enter into TUI (`proven`) | partial | bridge `send()` types text+Enter | P0 |
| Mic / dictation | — (excluded backend) | — | not-started | dictation backend backlog | P3 |
| Attachment chip strip | attachment list (synthesized · `not-started`) | track/render attachments (`not-started`) | not-started | no attachment model | P1 |
| Embed block (frozen inline quote) | selected text (transcript/synthesized · `derivable-not-built`) | inline injection into prompt (`derivable-not-built`) | not-started | settled inline quote; QA Q26a; → Cross-Cutting | P1 |
| Attach as file (path ref + "read this") | materialized temp file (synthesized · `needs-investigation`) | write temp file, inject path (`needs-investigation`) | not-started | WSL-reachable temp + path translation; QA Q26b/c | P2 |
| Citation pill (inline ref to attachment) | attachment (synthesized · `not-started`) | insert pill, cascade-delete (`not-started`) | not-started | depends on Attach; DESIGN citations | P3 |
| Templates dropdown + fill pills | template files (synthesized · `not-started`) | load/store templates; pill fill (`not-started`) | not-started | template storage net-new; DESIGN Templates flow | P2 |
| History feed cards (per-agent prompt log) | prompt log (transcript/events · `derivable-not-built`) | render from events (`derivable-not-built`) | partial | `/history` event list | P0 |
| History persistence across reload/reconnect | persistent prompt-log store (synthesized · `not-started`) | durable store (`not-started`) | not-started | nothing backs it; runtime_store reconnects sessions not prompts; QA Q30 | P1 |
| db-* delivery states (Now/Inject/Next/Queue, Active/Complete/Held) | queue position (synthesized · `not-started`) | server queue state (`not-started`) | not-started | no queue; QA Q23/Q30 | P2 |
| Select-to-act on History cards | loaded cards (events · `proven`) | client selection (`proven`) | not-started | pure client | P1 |
| Output Export (Copy / Export→file) | selected cards (events · `derivable-not-built`) | client serialize; Export→file=new Doc (`needs-investigation`) | not-started | client-side; QA Q30 | P1 |
| Edit (card-header ghost) | card text (events · `proven`) | load into Editor (`derivable-not-built`) | not-started | client repopulate | P1 |
| Retry (re-issue last command) | stored "last command" (synthesized · `not-started`) | re-issue via Editor (`derivable-not-built`) | not-started | net-new last-command store; QA Q6/Q30 | P1 |
| Stop (interrupt run) | run-state (screen · `proven`) | `/interrupt` (`proven`) | partial | `/interrupt`; live-verified | P0 |
| Attachment paperclip + count chip (History) | attachment list (synthesized · `not-started`) | popover → open in Library (`not-started`) | not-started | depends on attachment model | P2 |
| Send · timing = Now | run-state (screen · `proven`) | interrupt-then-send (`derivable-not-built`) | not-started | `interrupt` proven; sidecar must own sequence; QA Q23 | P0 |
| Send · timing = Queue | idle detection (screen · `derivable-not-built`) | sidecar queue, send on idle (`needs-investigation`) | not-started | `/send` 409s+drops; QA Q23; → Cross-Cutting | P1 |
| Send · timing = Next | turn-boundary (screen · `needs-investigation`) | wait next boundary (`needs-investigation`) | not-started | no boundary detection; QA Q23 | P2 |
| Send · timing = Inject (mid-run, no stop) | safe-boundary detector (screen · `impossible` on bridge) | inject at boundary (`impossible`→degrades) | not-started | likely degrades to Next/Queue; QA Q23 | P3 |
| Revise split (Grammar/Language/Refactor) | prompt text (none) | utility-LLM rewrite (`derivable-not-built`) | not-started | net-new; sdk candidate; QA Q25 | P2 |
| Response-format popover (Style/Behavior dials) | — | per-prompt instruction PREAMBLE (`derivable-not-built`) | not-started | output-styles wrong granularity; "Reasoning shown" prose-only on bridge; QA Q27 | P2 |

## Library

| Capability | Data needed (source · status) | Control needed (status) | Build | Evidence | MVP |
|---|---|---|---|---|---|
| Plans — native files render (`~/.claude/plans/*.md`) | plan .md files (filesystem · `derivable-not-built`) | read files (`derivable-not-built`) | not-started | files readable via WSL; no endpoint | P0 |
| Plans — line-numbered editor + rail (Outline/Feedback) | file lines (filesystem · `derivable-not-built`) | render/select; write-back edits (`needs-investigation`) | not-started | body write-back to .md net-new; QA Q18 | P1 |
| Review side-store (owner/state/tally/verdicts/comments/reviewer) | side-store (synthesized · `not-started`) | filename-keyed store CRUD (`not-started`) | not-started | .md can't carry it; QA Q18 | P1 |
| Plan↔agent owner mapping | authoring session link (synthesized · `needs-investigation`) | tie plan to session (`needs-investigation`) | not-started | watch plan-file/plan-mode exit; QA Q16b/Q18 | P2 |
| Comment composer (verdict + note + agree) | side-store (synthesized · `not-started`) | write to side-store (`not-started`) | not-started | part of side-store | P2 |
| Merged Export control (Plans footer) | selection (file lines · `derivable-not-built`) | Copy/Export/Embed/Attach (`needs-investigation`) | not-started | Export→file=new Doc; Attach WSL-reachable; QA Q26 | P1 |
| Review reviewer-chip (single-agent select + send) | reviewer agent (synthesized · `derivable-not-built`) | hand plan to reviewer (`needs-investigation`) | not-started | workflow deferred B13; QA Q20 | P3 |
| Approve/Revise/Reject → agent | plan-mode parked state (screen · `impossible` on bridge) | resume out of plan-mode (`impossible` today) | not-started | no plan-mode detection; `set_mode` no-op; QA Q19 | P2 |
| Inbox cross-link (Review jumps to Plans) | matching plan id (synthesized · `derivable-not-built`) | navigate+highlight (`derivable-not-built`) | not-started | client routing once mapping exists | P2 |
| New-plans count badge | unreviewed count (side-store · `derivable-not-built`) | derive count (`derivable-not-built`) | not-started | counts review/draft plans | P2 |
| Documents — one-tab doc list (README, project + user CLAUDE.md) | doc files (filesystem · `derivable-not-built`) | read files (`derivable-not-built`) | not-started | readable via WSL/FS; no endpoint | P0 |
| Documents — path disambiguation | file paths (filesystem · `proven`) | render path label (`proven`) | not-started | path load-bearing (two CLAUDE.md) | P1 |
| Documents — line-numbered editor + rail | file lines (filesystem · `derivable-not-built`) | render/select; write-back (`needs-investigation`) | not-started | same editor as Plans | P1 |
| Documents — Add / Paste / rename / createDoc | — | file create/rename ops (`not-started`) | not-started | net-new file ops | P2 |
| Assets — reference-image rail + preview | image files (filesystem · `derivable-not-built`) | read/serve images (`needs-investigation`) | not-started | net-new media storage | P2 |
| Assets — single media source-of-truth | asset store (synthesized · `not-started`) | central media store (`not-started`) | not-started | net-new storage | P2 |
| Assets — attach round-trip (paperclip ↔ Assets) | asset path (filesystem · `needs-investigation`) | Attach-only whole-file (`needs-investigation`) | not-started | WSL-reachable path; QA Q26 | P2 |

## Settings

> **Reads are now BUILT** (this round): `GET /settings/mcp`, `/settings/plugins`, `/settings/config`, and `GET /usage` serve real WSL-side data via `bridge/registry.py` (the same `cat`-over-WSL mechanism `mcp_sync` uses). The bridge `CAPABILITIES` still cover only `interrupt/context/permission/resume/set_model/set_effort/subagents` (those are *session* controls; Settings reads are workspace-level and don't gate on a driver). **What remains net-new:** the **writes** — enable/disable toggles and the confirm-gated global edit — plus the Usage **plan/limits** band.

| Capability | Data needed (source · status) | Control needed (status) | Build | Evidence | MVP |
|---|---|---|---|---|---|
| **Setups** — list saved setups | blueprints (filesystem · `derivable-not-built`, store net-new) | list/refresh (`derivable-not-built`) | not-started | no endpoint; QA Q31 | P1 |
| Setups — capture current (agents + links + subagents → blueprint) | live roster + link graph (synthesized · `derivable-not-built` agents; `needs-investigation` links — zero backend) | Save → write blueprint (`not-started`) | not-started | QA Q31; linking net-new | P1 |
| Setups — Load → spawn fresh tab-less agents + recreate links | blueprint (filesystem · `derivable-not-built`) | spawn-many bridge sessions **tab-less** + recreate links (`not-started`) | not-started | QA Q31 (tab-less rule); `create_session` one-at-a-time | P1 |
| Setups — delete a setup | — | delete blueprint (`not-started`) | not-started | mockup Delete, no handler | P2 |
| **Usage** — account band (auth/email/org/plan) | plan/tier IS local (filesystem · `derivable-not-built`) | — | not-started | `~/.claude/.credentials.json` `claudeAiOauth.{subscriptionType,rateLimitTier}` + `~/.claude.json oauthAccount.{emailAddress,organizationName,organizationRateLimitTier}` — readable, not yet surfaced (Part-4 report) | P2 |
| Usage — limits band (session/weekly % + resets) | live rate-limit windows (API · `needs-investigation`) | — | not-started | NOT in local files — the % bars/resets are fetched live from the API (agent-dashboard reads them from OAuth creds + API). Decision pending (Part-4 report) | P2 |
| Usage — token consumption Σ (this session) | per-agent + fleet usage aggregate (transcript · `proven`) | — | built | `GET /usage` (per-agent + fleet totals + token pill); model-aware window; live-verified | P1 |
| Usage — Day/Week scope toggle | historical token totals (synthesized · `needs-investigation` — no time-series store) | switch window (`derivable-not-built`, UI) | not-started | mockup Day/Week static | P2 |
| Usage — by-driver / per-MCP attribution | per-category context (transcript · `derivable-not-built`) | — | not-started | categorization net-new; QA Q11a | P2 |
| Usage — cost / $ spend | **none — out of scope** (`impossible`) | — | not-started | `total_cost_usd`=0; DESIGN out-of-scope | P3 |
| **MCP** — scope segment (user/project) | active scope (UI · `proven`) | switch scope (`derivable-not-built`, UI) | not-started | DESIGN MCP scope | P1 |
| MCP — server registry (user: `~/.claude.json mcpServers`) | MCP defs (filesystem · `proven`) | — (read) | built | `GET /settings/mcp` → `registry.read_mcp_registry`; env values masked; live-verified (13 servers) | P1 |
| MCP — server registry (project: `.mcp.json`) | project MCP defs + enable flags (filesystem · `proven`) | — (read) | built | `read_mcp_registry` project scope (enableAll/enabled/disabledMcpjsonServers) | P1 |
| MCP — health band (connected/OK per server) | live connection state (synthesized · `needs-investigation` — `/mcp` scrape; `mcp_sync` is translation, not health) | — | not-started | anchor: not a live health API | P2 |
| MCP — OAuth health per server | per-server OAuth state (synthesized · `needs-investigation`) | — | not-started | `/mcp` scrape candidate | P2 |
| MCP — enable/disable (park) a server | enabled-state (filesystem · `derivable-not-built` read) | toggle → write config (`not-started`) | not-started | enable/disable writes net-new | P1 |
| MCP — add a project server | — | write `.mcp.json` (`not-started`) | not-started | net-new write | P2 |
| **Plugins** — scope segment (user/project/local) | active scope (UI · `proven`) | switch scope (`derivable-not-built`, UI) | not-started | DESIGN scope | P1 |
| Plugins — marketplaces list | marketplace registry (filesystem · `derivable-not-built`) | — | not-started | net-new read | P2 |
| Plugins — installed list (name@mkt, version, skills, enabled) | installed-plugin records (filesystem · `proven`) | — (read); per-agent enable AT LAUNCH (`proven`) | built | `GET /settings/plugins` → `read_plugins` (`claude plugin list --json` = authoritative enabled); per-agent enable via `--settings enabledPlugins` live-verified | P1 |
| Plugins — enable/disable | enabled-state (filesystem · `proven` read) | global toggle → write (`not-started`); per-agent toggle AT LAUNCH (`proven`) | partial | read built; **per-agent** enable via `--settings enabledPlugins` live-proven; **global** toggle = a settings write (later run) | P1 |
| Plugins — remove / search | — | uninstall write (`not-started`); filter (`derivable-not-built`, UI) | not-started | mockup handlers stubbed | P2 |
| **Config** — scope segment (global/project) | active scope (UI · `proven`) | switch scope (`derivable-not-built`, UI) | not-started | DESIGN scope | P1 |
| Config — default model + available models | `~/.claude` settings (filesystem · `proven` read) | edit (global) → confirm-gated write (`not-started`) | partial | `GET /settings/config` reads global+project (Live/New-session tagged); global writes still net-new | P1 |
| Config — effort (Live · `/effort`) | effort value (filesystem · `derivable-not-built` read) | per-session set exists; **global write** net-new | partial | `set_effort` endpoint; global-write net-new | P1 |
| Config — extended thinking (Live) | thinking state (filesystem · `derivable-not-built` read) | edit thinking (`not-started` — `/thinking` absent) | not-started | `set_thinking` not in bridge caps; QA intro | P2 |
| Config — permission mode (read; New-session) | mode value (filesystem · `derivable-not-built` read) | set mode (`needs-investigation` — no absolute set; **initial** applied at launch) | partial | `set_mode` 400; mode-at-launch (09:15) | P1 |
| Config — sandbox (read; New-session) | sandbox setting (filesystem · `derivable-not-built`) | edit (global) → confirm write (`not-started`) | not-started | mockup row | P2 |
| Config — hooks (read-only Live) | hooks config (filesystem · `derivable-not-built`) | — | not-started | read `~/.claude/settings.json` hooks | P2 |
| Config — env vars (New-session) | env in settings (filesystem · `derivable-not-built`) | edit (global) → confirm write (`not-started`) | not-started | mockup Environment band | P2 |
| Config — CLAUDE.md (user + project; Live re-read) | file paths/content (filesystem · `derivable-not-built`) | — (editing lives in Library→Documents) | not-started | DESIGN: doc editor in Library | P2 |
| Config — plansDirectory (read; New-session) | plans-dir setting (filesystem · `proven` — `.claude/plans` configured) | — | partial | CLAUDE.md `plansDirectory` | P2 |
| Config — project config (`.claude/settings.json` allow/deny, additionalDirectories) | project settings (filesystem · `derivable-not-built`) | edit project settings (`not-started`) | not-started | read derivable; writes net-new | P2 |
| Config — global-edit confirm gate | — | confirm gate guarding every `~/.claude` write (`not-started`) | not-started | DESIGN "global edits are gated" | P1 |
| Cross-cutting — read-only vs editable separation | n/a (presentation) | — | not-started | DESIGN rule | P1 |
| Cross-cutting — global-registry vs per-agent scope separation | n/a (model boundary) | — | not-started | DESIGN ("owns global registry, not per-agent") | P1 |
| Footer — token-usage pill → jumps to Usage | fleet token aggregate (transcript · `proven`) | click → open Settings('usage') (`derivable-not-built`, UI nav) | partial | `GET /usage` `token_pill` (value built; the click-nav is frontend) | P1 |

## Cross-Cutting

> The canonical home for capabilities that span panels: **linking** (the defining feature), the **prompt queue / send-timing**, the **event-stream architecture**, the **scratchpad**, **Embed/Attach**, **lifecycle caps**, **identity**, and **Rewind/Handoff**.

| Capability | Data needed (source · status) | Control needed (status) | Build | Evidence | MVP |
|---|---|---|---|---|---|
| **Link create + persist** (the defining feature) | link records {pair, direction, trigger, payload, end-after} (synthesized · `needs-investigation`) | create/edit/delete + store (`not-started`) | not-started | no link model/endpoint/store anywhere; DESIGN "the defining feature"; ZERO backend | P0 |
| Link Direction (A→B / B→A / A↔B) | direction flag (synthesized · `needs-investigation`) | 3-state toggle (`not-started`) | not-started | net-new; QA C | P0 |
| Source-FIRE event (when a link forwards) | source-idle transition (screen `generating→idle`, ~1s · `derivable-not-built`) | fire-on-idle detector (`not-started`) | not-started | idle observable in `events()`; QA Q12 ("single biggest undefined contract") | P0 |
| Link Trigger — Now | — (`proven` interrupt+send) | interrupt then send (`partial`) | partial | `/interrupt` proven; needs orchestration; QA Q23 | P0 |
| Link Trigger — Queue | run-state to gate (screen · `derivable-not-built`) | sidecar per-agent queue, flush on idle (`not-started`) | not-started | `/send` 409s+drops; QA Q23 | P0 |
| Link Trigger — Next | turn-boundary (screen · `derivable-not-built`) | wait next boundary (`not-started`) | not-started | depends on idle poll; QA Q23 | P1 |
| Link Trigger — Inject (mid-run) | inter-tool safe boundary (screen · `needs-investigation`) | mid-run injection (`not-started`) | not-started | unverified; likely degrades to Next/Queue; QA Q23 | P2 |
| Link Trigger — Hold (manual release) | held-relay record (synthesized · `not-started`) | stage + release into Editor as pre-filled embed (`not-started`) | not-started | route to Editor; QA Q15 | P2 |
| Link Payload — Message (final assistant msg) | last assistant msg of just-finished turn (transcript · `derivable-not-built`) | forward as one rendered message (`not-started`) | not-started | `_entry_to_event` exposes blocks; selecting final-turn msg net-new; QA Q13 | P0 |
| Link Payload — Transcript | full conversation export (transcript · `needs-investigation`) | forward transcript (`not-started`) | not-started | source TBD; `read_log`/`export(log)` untested / `extract_messages` drops tool I/O; QA Q13 | P3 |
| Link Payload — Manual | none | compose per fire (`not-started`) | not-started | depends on link record | P2 |
| Link End-After (Turns / Tokens caps) | exchange turn/token count vs cap (synthesized · `derivable-not-built`) | independent toggles + enforce, end at first hit (`not-started`) | not-started | tokens derivable; exchange-turn counting net-new; QA Q14 | P1 |
| Bidirectional strict alternation (A↔B) | both sides' idle state (screen · `derivable-not-built`) | one-in-flight orchestration + End-After backstop (`not-started`) | not-started | falls out of fire-on-idle; QA Q14 | P1 |
| Links-as-edges render (directed arrows) | link records → edges (synthesized · `not-started`) | render edges (`not-started`) | not-started | DESIGN *(planned)*; needs link store first | P2 |
| Embed (frozen inline quote) | selected text (transcript/synthesized · `derivable-not-built`) | inject embed block into Editor (`not-started`) | not-started | settled; no write path; QA Q26a | P1 |
| Attach (path ref; materialize pathless) | selection + temp-file path (synthesized · `needs-investigation`) | materialize to per-session temp file, drop path chip (`not-started`) | not-started | net-new materialization; QA Q26b | P1 |
| Attach cross-fs path normalization (WSL2↔Windows) | receiver cwd/filesystem (synthesized · `needs-investigation`) | rewrite path WSL-reachable for receiving bridge agent (`not-started`) | not-started | bridge reads via WSL; Windows temp path won't resolve; QA Q26c/Q21 | P1 |
| Citations (inline pills, cascade-delete) | attachment refs (synthesized · `not-started`) | insert/cascade pills (`not-started`) | not-started | depends on Attach; DESIGN citations | P2 |
| Shared scratchpad — append API + attribution | per-post {agent,time,text} (synthesized · `not-started`) | sidecar append endpoint stamping agent+time (`not-started`) | not-started | confirmed absent in `main.py`; QA Q21 | P1 |
| Scratchpad — materialized `.md` (agent-readable) | append log → plain .md (synthesized · `not-started`) | write WSL-reachable `scratchpad.md` (`not-started`) | not-started | same boundary as Attach; QA Q21 | P1 |
| Scratchpad — auto-read policy (v1: agents do NOT auto-read) | n/a | explicit-send only (Editor→Scratch / link) (`not-started`) | not-started | write-in/read-out for v1; QA Q22 | P1 |
| Send-timing queue (Now/Inject/Next/Queue, no Hold) | run-state to gate sends (screen · `derivable-not-built`) | sidecar per-agent prompt queue + boundary detection (`not-started`) | not-started | `/send` 409s+drops; QA Q23 | P0 |
| Turn-boundary detection | `generating→idle` (screen ~1s · `derivable-not-built`) | detect boundary (`not-started`) | not-started | underpins Next/Queue + fire-on-idle | P0 |
| Revise (Grammar/Language/Refactor utility-LLM) | none | utility-LLM endpoint, cheap fixed model, return to Editor (`not-started`) | not-started | candidate for in-process **sdk**; QA Q25 | P2 |
| Summarize (condense cards → slide-over) | selected cards (transcript/synthesized · `not-started`) | shared utility-LLM endpoint → slide-over (`not-started`) | not-started | same net-new pass; QA Q25 | P2 |
| Rewind (roll agent to Timeline point) | message points (transcript · `derivable-not-built`) | rewind + resume-from-point (`not-started`) | not-started | leans on proven `resume`; DESIGN Rewind | P2 |
| Handoff (branch into new Create-prepopulated agent) | source config + branch point (synthesized · `not-started`) | prefill Create + spawn (`partial` — create exists) | not-started | `POST /sessions` exists; prepopulate net-new; DESIGN Handoff | P2 |
| Lifecycle cap — Max-turns | work-step count vs cap (transcript `work_steps` · `derivable-not-built`) | store cap + sidecar poll-loop enforce; on hit finish turn→idle+Log/Inbox (`not-started`) | not-started | no `max_turns`/enforcement; distinct from link End-After; QA Q5 | P1 |
| Lifecycle cap — Context-% | context % vs ceiling (transcript `percent` · `derivable-not-built`) | store ceiling + enforce (`not-started`) | not-started | no cap field; QA Q5 | P1 |
| Agent identity uniqueness past 16 | color/icon/name assignment registry (synthesized · `not-started`) | next-free color+icon on create; past 16 repeat color + distinct icon; name reuse w/ role+number tuple (`not-started`) | not-started | 16-color palette + 167 icons + 14 names; QA Q33 | P1 |
| Cross-agent event-stream aggregation | merged per-session events (synthesized · `partial`) | one aggregated stream the dashboard subscribes to (`not-started`) | partial | per-session SSE exists (`/events`, replays then streams, bounded-drop); merge net-new; QA Q32a | P0 |
| Stable per-event ids + SSE-vs-polling | event identity (synthesized · `needs-investigation`) | stable ids + move off 800ms `/history` poll (`not-started`) | not-started | frontend polls `/history`, index keys; QA Q32a | P1 |
| Crash / reconnect (through dashboard) | runtime records + tmux liveness (synthesized · `partial`) | reattach via bridge `resume` + `runtime_store` (`partial`) | partial | `reconnect_sessions()`+`runtime_store` proven below UI; reattach through dashboard unproven; QA Q32a | P1 |
| Log event taxonomy (curated semantic vocab) | lifecycle/tool-commit/coordination/request-error events (synthesized · `derivable-not-built`) | sidecar mints fixed taxonomy over raw streams (`not-started`) | not-started | coordination events in NO single transcript; QA Q32b | P1 |
| Cost (per-agent spend) | none (`impossible` on bridge) | — | not-started | `total_cost_usd`=0; out of scope | P3 |

---

## Status rollup (at a glance)

- **Fully `built` (live-verified on bridge):** total context %, work-steps + by-tool Turns, the subagent strip data (`/subagents`), model set, permission-mode-at-launch, created-time. A handful — the proven floor.
- **`partial` (backend data/control exists; not wired through the live `App.tsx`, or one half missing):** the status badge (active/idle/pending), Ctx/Turns readouts, effort set, mode readback, Stop/interrupt, permission round-trip, core Create/send/History, the per-session event stream, crash/reconnect, the MCP/Plugins registry reads.
- **`not-started` (the bulk):** concentrated in the **net-new buckets** — linking, the aggregated event stream + identity tagging, the prompt queue, scratchpad, Embed/Attach, the Inbox non-Permission sections, lifecycle caps, the persistent stores (History/Plans-review/templates/assets/Setups/identity), the Settings writes, per-category context, and the utility-LLM passes.
- **`impossible` on bridge (design must route around or accept):** mid-run permission-mode change, fast/thinking toggles, run-strip %, subagent pending-vs-active, screen-state detection of Decision/Plan, per-agent cost.

**Bottom line for the next rounds:** the MVP is mostly a **UI build over a proven bridge floor (Phase 0)** plus **three foundational backend pieces — the aggregated/identity-tagged event stream, the prompt queue + boundary detection, and the agent-identity store (Phase 1)** — after which the **defining linking feature (Phase 2)** becomes a tractable build rather than a from-scratch one.
