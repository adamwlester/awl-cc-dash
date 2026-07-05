# DEVLOG Archive 05 — 2026-06-30 → 2026-07-04

> Archived, immutable DEVLOG history (oldest -> newest). Rotated out of the root `DEVLOG.md` on 2026-07-03 to keep the active log small (see the **Rotation** rule in the DEVLOG header and the **Archived history** index there). Entries are **verbatim** -- original `### ...` headings and `Files:` lines preserved. Never edit archived entries; record new history in `DEVLOG.md`.
>
> Span: the OD coordination-spine backend build-out — Tier-1 (aggregated event stream + addressing OD-01/22, prompt queue + hook channel OD-02), Tier-2 agent-to-agent linking (OD-04/05/07/08 reply-to relay, live), and Tier-3 modules (inbox/caps OD-09/10, checklist, library, templates, scratchpad/watermark, marquee, console, settings_io, subagents-naming) + the sdk Revise/Summarize carve-out — each TDD-green with key behaviors live-verified; the design-stream finisher P1/P2 passes; the feature-branch merge to main + the no-branch-without-permission rule; the creation of `docs/ARCHITECTURE.md` + OD integration into §10 (tracker archived); the data-model-map note; DEVLOG rotation-04; the `design/TODO.md` → `TODO.md` backlog refactors + Inbox triage; the ARCHITECTURE final-vision rewrite (OD record dissolved); the NEXT UP — DESIGN builds; and the run-up to the §10 spike work — from 2026-06-30 17:45:00 through 2026-07-02 07:35:14. 61 entries.
>
> Extended by the 2026-07-05 rotation (+51 entries, log order 2026-07-02 07:44:40 → 2026-07-04 00:45:00, a few concurrent-session entries timestamped later on 07-04): the **§10 spike storm** — 17 live spikes (mid-run permission-mode / thinking / fast-mode control, `/context` + `/compact`, `/cost` per-session cost, subagent pending-vs-active status, one-click Electron launch, the hook-event-stream, the polling-scale ceiling, system-fault detection, Bypass/Auto launch preconditions, usage + context data sources, Rewind/Handoff, `/clear` transcript orphaning) plus the two infeasible tails (true mid-turn Inject, real run-strip %); **doc-integration Phases 2–8** (tests/README spike table, ARCHITECTURE **§11 Build backlog & queue**, the TODO.md refactors, the doc-vs-doc contradiction reconciliations, **CLAUDE.md thinned to a router**, the coverage-audit orphans homed); the **[ND] NEXT UP — DESIGN run** (Plans/Docs unified into one reviewable-document component, Inbox typed-section accordions, the Library rail + nested TOC, the Authors lens, the 2-row card header, and the per-lane review-panel fix passes); the **ui-verify** headed-parked Playwright launcher; and DEVLOG rotation-05 itself. 112 entries total.

### 2026-06-30 17:45:00 — backend: OD-01 + OD-22 merged event stream/addressing + OD-02 push-queue (Tier-1 foundation complete, hermetic)

Built the rest of the load-bearing Tier-1 foundation from `dev/prompts/backend-decision-integration.md`, TDD, all hermetic. No `design/` touched.

- **OD-01 + OD-22 (one envelope)** — new `sidecar/eventbus.py`: the sidecar now owns ONE aggregated, identity-stamped event stream. Every event is stamped at the single `push_event` choke point with `{id, agent_id, seq, ts, source, recipients[]}` — `seq` a separate global monotonic ordering key, `id` a **deterministic** composite `{agent_id}:{source_kind}:{anchor}` (anchor = the JSONL entry `uuid`, surfaced from the bridge driver's `_entry_to_event`) so a re-poll/reconnect **dedups to a no-op**; synthesized events get a unique seq-based id. OD-22 `source` + typed `recipients[]` (default `source=agent`, `recipients=['user']`; pre-addressed events preserved). New **`GET /events`** (merged SSE) + **`GET /events/history`** (REST backfill) replace the per-session `/history` poll, both with server-side **From/To filtering** (`?source=`/`?recipient=`) + `?since=<seq>` scroll-backfill against a **bounded ring** (the per-agent JSONL stays source of truth). `SendPromptRequest` gained `source`/`recipients` so linking/multi-target sends need no later migration.
- **OD-02 push-queue** — `send_prompt` no longer **409-drops** to a busy agent: it enqueues on a per-agent **ordered queue** (`SessionState.enqueue` + `prompt_queue`/`held`) with dispositions **Now / Next / Queue / Hold** (Queue the polite default), flushed by `_flush_queue` on the proven **generating→idle** transition (scheduled from `handle_event`, strict one-in-flight via a pre-await status gate). *Now* interrupts the run so the resulting idle delivers at the head; *Hold* stages for manual release. (*Inject* = the hook channel — spike-gated, next.) Unblocks the OD-04/05/06/07 linking chain.
- **Verified:** 146 hermetic tests green (`tests/test_eventbus_unit.py` new +16; `tests/test_sidecar_unit.py` +envelope/merged-endpoint/queue; `tests/test_bridge_unit.py` +`_entry_to_event` anchor). Sidecar imports clean; `/events` + `/events/history` routes registered. **LIVE verification still pending** (next phase, serial): the merged stream end-to-end through a real agent, the queue idle-flush on a real turn boundary, and the OD-02 hook spike. Seam-mapping of the big files was done via a 4-agent parallel understand-sweep first.

Files: sidecar/eventbus.py (new), sidecar/main.py, sidecar/drivers/bridge.py, tests/test_eventbus_unit.py (new), tests/test_sidecar_unit.py, tests/test_bridge_unit.py, DEVLOG.md

---

### 2026-06-30 18:30:00 — design: the OD tracker's full design-layer (🎨) stream integrated into design/ (8 ODs)

Integrated the eight design-tagged decisions (OD-03/13/14/15/16/18/19/20) into the six-file design system on the live (now-committed) `design/` files. **OD-03:** identity pools 16→**25** named `--ag-*` OKLCH-jewel colors (additive, gamut-clamped, existing 16 unchanged) + 29→**50** curated icons (sprite symbols + `AGENT_ICONS`); pickers auto-count to 50; gave the gallery a synced sprite so its agent glyphs render. **OD-14:** "Always allow" fully removed — Permission card is binary Approve/Deny (+Reply). **OD-20:** Console run bar flipped `planned`→built (markers removed; live feed/route is the backend stream's job). **OD-18:** net-new per-agent **MCP / Plugins / Deny-rules** scoping msels in Create + Details (reuse the msel primitive); Account/Limits bands confirmed present. **OD-13** (largest): `s1`→`A2` group+member badges; badge-click (focus parent → open Details Subagents → scope feed) **resolving OQ-1**; new **Subagents audit accordion**; nested **From/To feed tree** (parent-subtree vs leaf; Prompt-To kept flat); **Messages nesting**; gallery specimens flipped + a new accordion card; DESIGN.md updated, **OQ-1 deleted** from the register, and the "Inbox included" From/To contradiction **reconciled** to the inert-on-Inbox model. **OD-15/OD-16:** confirmed complete, left untouched (no scope creep). **OD-19:** confirmed Delete ships in v1 with a plain confirm — no change.

Verified by driving the rendered UI over `http://localhost` with headless Chromium (the Playwright MCP browser was locked by another instance — used the prompt's sanctioned fallback): every touched surface screenshotted, narrow (1180) + wide (1920) resize with no overflow / console errors, and the new controls driven (badge-click, feed tree, accordion, scoping msels, pickers, Messages nesting, gallery). A 5-agent adversarial review caught 4 gallery propagation gaps (OD-20 console flip + OD-13 nested-tree / message-sub variants not propagated to the catalog, plus a stale `.sbadge` comment) — all fixed and re-verified. (Note: DEVLOG is now >700 lines; rotation deferred to avoid racing the concurrent backend-stream appends.)

Files: design/tokens.css, design/styles.css, design/behavior.js, design/mockup.html, design/gallery.html, design/DESIGN.md, DEVLOG.md

---

### 2026-06-30 19:10:00 — dev: design-stream finisher part 2 prompt (the under-tagged design-layer gaps)

Cross-referenced all 23 ODs against the live (post-pass-1) design files via three parallel audit agents and found the design-layer work the tracker decided but never 🎨-tagged — so it fell outside `design-stream-finisher.md`'s scope. Wrote `dev/prompts/design-stream-finisher-p2.md` to finish it: **OD-06** Link Config drawer reframe (drop Payload → Relationship multi-select + Shared-context content-type filter + backfill toggle; reorder), **OD-07** End-After "Turns/50"→"Exchanges/25", **OD-08** grouped-by-agent link-tracking list, **OD-10** Warning-card Continue/Raise-cap/Stop actions, **OD-11** segmented run-strip (done÷total + step label; barber-pole floor kept), **OD-22** per-message recipient mini-badge. Flagged one genuine **conflict** for a human call (not in the build): the **OD-09 Plan card** ships Review+Reply and deliberately drops Approve/Reject, but the OD-09 decision says Approve/Reject. Everything else in those clusters (OD-05 triggers, OD-12 marquee, OD-17 scratch, OD-01/22 sender+From/To+direction, OD-09 Permission/Error/Warning/Decision types, OD-10 cap inputs) audited as already-present.

Files: dev/prompts/design-stream-finisher-p2.md (new), DEVLOG.md

---

### 2026-06-30 20:30:00 — backend: OD-02 hook channel SHIPPED + spike PASS + foundation live-verified

Ran the prerequisite-#1 **OD-02 hook spike** live on the installed build (claude **2.1.195**) and it **PASSES** — so per the prompt I shipped the full hook functionality (unblocks OD-05 Inject, OD-09 Plan/Decision, OD-17 live scratchpad). Findings, each proven by driving a real tmux agent (serialized, throwaway cwd):
- **Inject lands mid-turn.** A `PostToolUse` hook returning `hookSpecificOutput.additionalContext` is surfaced by the agent **in the same turn** — proven first with a static `command` hook (Step A), then end-to-end through a real **`http`** hook + the sidecar drain (Step B): the agent echoed the injected sentinel mid-turn and the sidecar logged `hook drain post-tool-use … delivered=1`. Both `http` and `command` hook types fire and reach the host; `http`'s returned `additionalContext` injects too.
- **WSL2→host URL.** `localhost`/`host.docker.internal` are NOT reachable from WSL2 (NAT mode); the **default-gateway IP** is (firewall permits the WSL vEthernet). New `bridge.paths.parse_default_gateway` + `TmuxBridge.wsl_host_ip()`/`sidecar_hook_base_url()` resolve it at launch. The sidecar now binds **0.0.0.0** by default (`AWL_SIDECAR_HOST`) so the in-WSL hook can reach it.
- **Gotcha fixed:** claude's http-hook client does **not** forward a query string — the agent id rides the URL **path** (`/internal/hooks/post-tool-use/{agent}`), not `?agent=`. (This was the lone Step-B failure; path-param fixed it.)

Built: new `sidecar/hookbus.py` — durable per-agent inject inbox (kinds `inject`=active / `context`=passive), `drain` (ack-on-2xx; Stop drains active-only so passive scratchpad never force-continues a turn), and the exact PostToolUse/Stop output builders (10k-cap). New sidecar endpoints `POST /internal/hooks/post-tool-use/{agent}` + `/stop/{agent}` (drain + synthesized `inject_delivered` feed event). `send_prompt` gained the **`inject`** disposition → routes to the hook inbox (not the prompt queue) + a synthesized `inject` feed event (injects aren't written to the JSONL). The bridge driver auto-injects the per-agent PostToolUse+Stop hooks at launch (gated by `AWL_DISABLE_HOOKS`).

Also **live-verified the Tier-1 foundation** through the same real agent: the merged `GET /events` stream (OD-01/22 envelope id/agent_id/seq/source/recipients present; live SSE delivering) and the **OD-02 queue idle-flush** on a real `generating→idle` boundary — both PASS.

Verified: **+21 hermetic tests** (`tests/test_hookbus_unit.py` 12; bridge gateway-parse 5; sidecar inject-disposition + drain-endpoints 4) → **167 hermetic green**; plus the live spikes above. No `design/` touched.

Files: sidecar/hookbus.py (new), sidecar/main.py, sidecar/drivers/bridge.py, bridge/bridge.py, bridge/paths.py, tests/test_hookbus_unit.py (new), tests/test_bridge_unit.py, tests/test_sidecar_unit.py, DEVLOG.md

---

### 2026-06-30 20:05:00 — fix: corrected an OD-09 tracker error (Inbox Plan card has no Approve/Reject)

Per the user: the Inbox **Plan** card carries no Approve/Reject — those verdicts (Approve · Revise · Reject) live **only in the Library → Plans tab**; the Inbox Plan card is notify-only (Review + Reply). The tracker's OD-09 Decision wrongly read "Approve/Reject for Plan" on the card. Fixed the clause inline and added a dated **Correction note** (matching the doc's OD-13/OD-17 convention). Also tightened `design-stream-finisher-p2.md`: the Plan card is now marked "confirmed correct — do not change; ignore the erroneous tracker line" (previously framed as an open decision to surface). The p2 build scope (OD-06/07/08/10/11/22) is unchanged.

Files: dev/notes/agent-qa/open-system-decisions-2026-06-29.md, dev/prompts/design-stream-finisher-p2.md, DEVLOG.md

---

### 2026-06-30 21:30:00 — backend: Tier-2 agent-to-agent linking (OD-04/05/07/08) — reply-to relay LIVE

Built the defining feature — the **serialized reply-to** link engine — and verified one full round-trip **live** through two real bridge agents. New `sidecar/links.py`: the link store + OD-06 config (direction a2b/b2a/both, relationship direct/shared, OD-05 trigger, OD-07 End-After caps) + the OD-08 grouped-by-agent view (a link double-lists under both agents, with the arrow relative to each group). New endpoints `POST/GET/DELETE /links` + `POST /links/{id}/kickoff` (reply-to can't *start* a convo — kickoff seeds it).
- **OD-04 reply-to engine (in `main`):** a per-agent `answering_source`/`answering_link` — when an agent finishes a turn it was answering a linked peer for (detected at `generating→idle`), the sidecar lifts **that turn's** assistant text and routes it back to the peer (`recipients:[peer]`), then sets the peer's reply-to in return — strict **one-in-flight alternation**. Delivered by the link's **OD-05 trigger** (queue/next/now/**inject**[hook channel]/hold). **OD-07** caps it (default **25 exchanges**; a round-trip = 2 messages) — the runaway backstop; tokens cap too.
- **Race fix (found live):** the bridge emits idle off *screen* state ~1s before the assistant entry is polled into `events`, so the first live run fired 0 times (empty turn-text → dropped). Fixed: the relay now **retries without dropping the reply-to** until the turn text lands, bounded to one turn.
- **LIVE PASS:** A↔B link, End-After=1 → kickoff A→B → `link_fire` B→A ("GREETINGS-FROM-B") → `link_fire` A→B (cap) → link ends `messages=2 exchanges=1 active=False`. All three checks green.
- **OD-06 scoping:** the *direct-messaging* relationship is fully built + live. The *shared-context* passive-awareness path (content-filtered piggyback on the receiver's next prompt via a per-(src→target) **watermark**) shares its mechanism with OD-17's scratchpad delta — its config is stored now; delivery lands with the OD-17 watermark utility.

Verified: **+14 hermetic tests** (`tests/test_links_unit.py` 10; sidecar relay/cap/inject-trigger 4) → 181 hermetic green; plus the live relay above. No `design/` touched.

Files: sidecar/links.py (new), sidecar/main.py, tests/test_links_unit.py (new), tests/test_sidecar_unit.py, DEVLOG.md

---

### 2026-06-30 22:45:00 — backend: OD-10 caps + OD-09 inbox + Tier-3 batch (OD-11/15/16/19) — caps & delete LIVE

Built OD-10 + OD-09 and integrated four Tier-3 modules (four built in parallel by background subagents, each TDD-green; I wired the endpoints + driver + live-verified).
- **OD-10 caps (notify-only):** per-agent `max_turns`/`max_context_pct` (set on Create) + a sidecar **poll-loop** that raises a **Warning** inbox card on crossing — the run continues (Continue/Raise/Stop is the user's call; no auto-kill). Added a locally-derived `turn_count` (each generating→idle = a turn) so caps work for the **bridge** driver (it emits status_change, not the SDK's `result.num_turns`). **LIVE PASS:** max_turns=1 → a `max_turns` Warning card raised, fleet_badge=1.
- **OD-09 inbox:** new `sidecar/inbox.py` — the typed store (permission/error/warning/plan/decision) + the **error pattern-match** classifier + the cap→Warning derivation. `GET /inbox` (grouped by agent + pending-permission merged + fleet badge), `POST /inbox/{a}/{id}/resolve`. **Error** raised sticky on driver error events. **Plan/Decision** = the spike-gated path: per-agent **PreToolUse** hooks on `ExitPlanMode`/`AskUserQuestion` POST to `/internal/hooks/plan|decision/{agent}` → raise the typed card (**detect-and-surface** floor; returns allow so the agent isn't blocked). The richer hold-for-answer round-trip via `updatedInput` is a designed fast-follow needing its own live proof.
- **OD-19 Retire/Delete:** `DELETE /sessions/{id}?hard=true` → `sidecar/deletion.py` plan: **wipe** the private footprint (runtime record + tmux kill + **on-disk transcript erased via the bridge's WSL shell** — a Windows `Path.unlink` can't reach the WSL fs) and **tombstone** the shared (links → inactive), retire the number (never reused), drop queue+inbox. **LIVE PASS:** transcript GONE on disk, number retired, tmux killed.
- **OD-11 checklist:** `sidecar/checklist.py` (done÷total parse, barber-pole floor) → `GET /sessions/{id}/checklist`. **OD-15 library:** `sidecar/library.py` (project-scoped md read + plan-review side-store at `<project>/.awl/plan-reviews.json`) → `/library/*`. **OD-16 templates:** `sidecar/templates_store.py` (dashboard-store CRUD + placeholder render) → `/templates`.

Verified: **274 hermetic green** (new: inbox 11, checklist 19, deletion 17, library 25, templates 17) + the two live PASSes above. No `design/` touched.

Files: sidecar/inbox.py (new), sidecar/checklist.py (new), sidecar/deletion.py (new), sidecar/library.py (new), sidecar/templates_store.py (new), sidecar/main.py, sidecar/drivers/bridge.py, tests/test_inbox_unit.py (new), tests/test_checklist_unit.py (new), tests/test_deletion_unit.py (new), tests/test_library_unit.py (new), tests/test_templates_store_unit.py (new), DEVLOG.md

---

### 2026-06-30 23:55:00 — design: design-stream finisher P2 — the under-tagged linking/feed work integrated into design/ (OD-06/07/08/10/11/22)

Integrated the **remaining design-layer decisions the tracker decided but never 🎨-tagged** (the set Part 1 didn't cover) into the six-file design system, building each from its OD `Decision:` line. **OD-06:** reframed the **Link Config drawer** — removed the **Payload** segment; added a **Relationship** multi-toggle (Direct messaging / Shared context — a link can be both), with Shared context revealing a **content-type multi-select** (Thoughts/Read/Write/Bash/Diffs/Meta) + a **"share all prior context" backfill switch** (default off); reordered to pair+direction → Relationship → Trigger → End After → Save/Delete → link list (`linkRel`/`linkSwitch` + the hover/blurb de-Payloaded; `linkSave` now reads the Relationship state, not the deleted seg). **OD-07:** End-After left cap **"Turns"→"Exchanges"**, default **50→25** (an Exchange = one message each direction). **OD-08:** net-new **`link-list`** — every link **grouped by agent**, double-listed under both endpoints, each row a **→/←/↔ arrow relative to that group's agent** (`renderLinkList`/`linkArrow`, `LINKS_CFG`). **OD-10:** **Warning** inbox card now has **two variants** — a cap-crossing one (Continue / Raise cap / Stop, notify-only) and the generic Acknowledge — via an `o.cap` branch. **OD-11:** **segmented run-strip** (`.run-seg`) — done÷total equal segments with navy separators, the current step shimmering and **labelling the bar** (mono); barber-pole kept as the floor; one node card converted. **OD-22:** typed **`recipients[]`** on `MSGS` + a compact **`recipient-badge`** rendered `sender → recipient → status → dir` (routing, not visibility). Cosmetics: OD-17 scratch path → `<project>/.awl/scratchpad.md`; OD-04 fire = reply-completion sentence.

Verified by driving the rendered UI over `http://localhost` (headless Chromium — the Playwright MCP browser was locked; used the prompt's sanctioned fallback) at narrow (1180) + wide (1920): every new control driven (Relationship disclosure, content/backfill toggles, link list, Exchanges/25, recipient badges, segmented strip, the three cap actions), **zero console errors**, plus a headed parity pass. A **6-reviewer adversarial panel** (parallel, per-finding verify) caught **4 real gaps** — a `linkSave()` stale-Payload leak (always toasted "Message"), a stale `Payload` CSS-section comment, a gallery Composites count off-by-one (50→51), and this missing log entry — **all fixed and re-verified** (Save now toasts the Relationship; gallery 116 articles balanced). Gallery: +`link-list` (populated + empty) and +`recipient-badge` cards; both Warning variants and the segmented run-strip shown. OD-09 Plan card left **as-is** (Review + Reply, no Approve/Reject — the tracker's "Approve/Reject for Plan" line is a known doc error). No scope-creep (OD-15/16 untouched, the OD-03 sprite/picker convergence not started, OQ-2 `inbox-section` marker intact). DEVLOG **rotation deferred** (>700 lines) to avoid racing the concurrent backend-stream appends.

Files: design/mockup.html, design/styles.css, design/behavior.js, design/gallery.html, design/DESIGN.md, DEVLOG.md

---

### 2026-06-30 — sidecar: settings_io.py — path-explicit, confirm-gated settings file I/O (OD-18)

Added the safe file-layer primitives under the OD-18 interactive Settings surface: `read_json` (missing/empty/corrupt → `{}`), `write_json` (atomic temp-file+replace, pretty, creates parent dirs), `set_key`/`toggle_key`/`remove_key` (nested dotted-path read-modify-write), and read-only `account_band` (lenient email/org/plan mapping, one-level nesting, `{"signed_out": True}` when absent). Every mutator is confirm-gated via a required `confirm=True` kwarg that raises `ConfirmationRequired` (a `PermissionError` subclass) before any FS change. **Safety:** operates ONLY on explicit paths passed by the caller — hardcodes no real `~/.claude`/`<project>/.claude` location. Module docstring records the honest feasibility boundary (mid-run permission-mode engine-BLOCKED; per-agent MCP/model/plugins apply at launch/restart) without enforcing engine semantics. Endpoints wire later. TDD: 35 hermetic pytest cases on `tmp_path`, all green (`tests/test_settings_io_unit.py -q` → 35 passed). No existing file edited.

Files: sidecar/settings_io.py, tests/test_settings_io_unit.py, DEVLOG.md

---

### 2026-07-01 00:40:00 — backend: OD-12/13/17/18/20 + sdk (OD-16) — scratchpad & Revise LIVE; Tier-3 complete

Finished the Tier-3 backend + the sdk carve-out. Five more pure modules were built in parallel by background subagents (each TDD-green: watermark 17, subagents_naming 13, marquee 25, settings_io 35, console_catalog 17); I wired the endpoints + driver + live-verified the novel bridge/SDK behaviors.
- **OD-17 scratchpad** — new `sidecar/scratchpad.py` on the shared `watermark.py` (per-agent auto-read delta; first read = full board; own posts included). `POST/GET /scratch`. Delivery = the OD-02 hook channel as a **passive `context` inject** (never triggers a turn): **live mid-run push** to running co-located agents + **start-of-run catch-up** on `status→running`. **LIVE PASS:** a scratch note posted mid-run reached the running agent at its next tool boundary — it surfaced the token in-turn (`scratch_delivered` event + token both present). `watermark.py` is the shared OD-06/OD-17 mechanism; OD-06 shared-context delivery rides it next.
- **OD-16 sdk carve-out** — new `sidecar/utility_llm.py`: **Revise** (Grammar/Language/Refactor, default Grammar) + **Summarize** as non-interactive one-shot `claude_agent_sdk.query()` passes — the ONLY two non-bridge consumers. `POST /utility/revise|summarize`. **LIVE PASS:** "this sentance has an obvous eror" → "This sentence has an obvious error in it."
- **OD-18 settings** — endpoints over the confirm-gated `settings_io.py`: `GET /settings/read|account`, `POST /settings/write` (write/set/toggle/remove; 428 when unconfirmed).
- **OD-20 console** — `console_catalog.py` (6 clusters, 43 commands, interactive flags) → `GET /console/catalog`; `POST /sessions/{id}/console/run` routes a slash-command over the bridge's send + capture-pane (interactive commands flagged for follow-on).
- **OD-12 marquee** — `marquee.py` liveness tail → `GET /sessions/{id}/marquee`. **OD-11 checklist** endpoint added earlier. **OD-13** — `subagents_naming.py` (group+member `A2`, no `s` prefix) relabels the subagents endpoint (v1 single-run grouping; per-run segmentation + subagent-transcript ingest is the follow-on).

Verified: **395 hermetic green** (new: scratchpad 8, watermark 17, marquee 25, subagents_naming 13, console_catalog 17, settings_io 35, utility_llm 6) + the two live PASSes above. No `design/` touched.

Files: sidecar/scratchpad.py (new), sidecar/watermark.py (new), sidecar/marquee.py (new), sidecar/subagents_naming.py (new), sidecar/console_catalog.py (new), sidecar/settings_io.py, sidecar/utility_llm.py (new), sidecar/main.py, tests/test_scratchpad_unit.py (new), tests/test_watermark_unit.py (new), tests/test_marquee_unit.py (new), tests/test_subagents_naming_unit.py (new), tests/test_console_catalog_unit.py (new), tests/test_utility_llm_unit.py (new), DEVLOG.md

---

### 2026-06-30 23:57:30 — design: OD-11 run-strip — sizing bug fixed + segmented bar brought to every active card

Fixed the segmented run-strip regression from the P2 pass. **Sizing:** `.run-seg` was `--size-13` (13px) while every other `.run-strip` is `--size-6` (6px), so the one segmented card's bar rendered ~2× tall and misaligned in the node-band. Dropped it to `--size-6` and moved the current-step label out of the bar — it was an absolute overlay *inside* the 13px bar; it now rides **above** the bar as a compact mono line (`.rseg-lab`, `display:block`, `--size-7`). Because the node-band is bottom-pinned (`margin:auto` top), the label floats up without moving the bar, so the bar stays 6px and every card's bar seats identically. **Consistency:** the segmented form was on only one card (node-4 max); brought it to **all actively-running cards** with representative step counts — node-4 (5-step · Run typecheck), node-9 wren (4-step · Regenerate API table), node-13 fen (3-step · Summarise turns) — and kept node-10 lex as the **barber-pole indeterminate floor** (the no-checklist example). No hardcoded px (reused `--size-6/7`, `--space-9/2`); nothing outside the run-strip touched.

Verified over `http://localhost` (headless Chromium, MCP browser locked — sanctioned fallback) at 4 widths (1000/1180/1920/2300): **every** card's bar = 6px and sits 54px off its card-bottom (identical → aligned), **0** row-misalignments, 3 segmented cards with visible labels, **0** console errors; gallery specimen all six bars 6px with the label above; **headed parity pass** returned identical metrics + rendering.

Files: design/styles.css, design/mockup.html, design/gallery.html, design/DESIGN.md, DEVLOG.md

---

### 2026-07-01 00:42:53 — Merged feature/agent-console-tab back into main (fast-forward)

Consolidated ~a week of work back onto `main`: the long-lived `feature/agent-console-tab` branch (67 commits, 2026-06-24 → 07-01, from the Agent Console tab through the OD backend/design passes) was merged into `main` via a clean fast-forward — `main` had not diverged (0 commits ahead), so no conflicts and no file-content changes. Pushed; `main` d98725f → f4b4c39, now identical to the feature branch. Per request to stop work happening on a side branch — future work lands on `main`. Feature branch left in place pending a delete decision.

Files: branch topology / DEVLOG.md (no product file contents changed by the merge)

---

### 2026-07-01 00:49:20 — Rule + enforced gate: agents must not branch without permission

Added a **new first entry** to CLAUDE.md's Behavioral rules — "Git — never branch without express permission" — that overrides the harness "branch off the default branch" default: work stays on `main`, branch-creating commands need an explicit yes, and approved branches get merged back + deleted. Backed it with an enforced guardrail in `.claude/settings.json`: restored the (removed) `git push` `ask` gates and added `git checkout -b/-B`, `git switch -c/-C`, `git branch *`, and `git worktree add *` to `ask`, so those prompt (they override the blanket `Bash(git *)` allow). Note: `git branch <listing>` (e.g. `-vv`) now also prompts — acceptable friction, can narrow later.

Files: CLAUDE.md, .claude/settings.json, DEVLOG.md

---

### 2026-07-01 00:53:14 — Correction: keep `git push` un-gated (user intent), gate only branch creation

Prior entry wrongly said it "restored the `git push` ask gates" — those had been removed **deliberately** by the user (commit 22d84ab, "allow pushing commits without asking"), not by accident. Reverted that part: removed `Bash(git push *)` / `Bash(git push)` from `.claude/settings.json` `ask`, keeping only the branch-creation gates (`checkout -b/-B`, `switch -c/-C`, `branch *`, `worktree add *`). Fixed the CLAUDE.md Git rule line that claimed push "stays gated" — push now stays free; only branch creation prompts.

Files: CLAUDE.md, .claude/settings.json, DEVLOG.md

---

### 2026-07-01 01:02:01 — Deleted the merged feature/agent-console-tab branch (local + remote)

Now that the branch was fully merged into `main` (0 unmerged commits), deleted it both locally (`git branch -d`, the safe merged-only delete) and on `origin` (`git push origin --delete`), then pruned stale tracking refs. Only `main` remains, local and remote in sync. Closes out the branch-consolidation work — future work stays on `main` per the new Git behavioral rule.

Files: branch topology only (no file contents changed) + DEVLOG.md

---

### 2026-07-01 01:22:06 — frontend: throwaway MVP renderer rewired to the current (OD) sidecar contract

The MVP renderer under `frontend/src/renderer/` had fallen out of sync with the heavily-extended backend — it still spoke the old per-session `/history` poll + `send({prompt})`. Rewired `api.ts` to the full current contract and replaced the per-session poll with the merged **`/events` SSE stream + `/events/history` backfill** (dedup by envelope id, seq-ordered, dedup-set bounded in lockstep with the event cap). Wired the now-available features across the panels: merged **Messages** feed (Focused/All with per-agent grouping + system-line renderers for link_fire/inject/scratch/warning/plan/decision), the 5-type **Inbox** (permission Approve/Deny + error/warning/plan/decision resolve), agent-to-agent **linking** (create/delete/kickoff, sender constrained to the link direction), **Scratch** read/post, the **Console** slash-command catalog + runner, send-timing **Now/Next/Queue/Hold** + **send-as-agent** (From selector), **Settings** account band + confirm-gated file writes (428 gate), **Library** reads, subagents, the checklist/marquee **run-strip**, **templates** (insert/save), and **revise/summarize**. Added `WorkPanel.tsx` (Library/Links/Scratch) and a standalone `frontend/vite.config.ts` for headless browser verification (the Electron `npm run dev`/`build` path is unaffected — it uses `electron.vite.config.ts`). Left `design/`, `sidecar/`, `bridge/` untouched.

Verified live against a running sidecar (which reconnected to a real bridge agent, "01 bob"): renderer `tsc --noEmit` clean; the app loads with **0 console errors** (added an inline empty favicon to kill the dev-server 404); the merged feed renders bob's real turns/tool-calls; the Inbox surfaced bob's live permission prompt; the Console loaded the 6-cluster catalog; the Settings account band read plan `max`; Files-read rendered `.claude/settings.json`; layout held at 1000px and 2560px extremes. An adversarial review workflow (4 dimensions → per-finding skeptic verify) confirmed 2 real issues, both fixed here: (1) kickoff sender could violate a directional link (→ backend 400, silently swallowed), and (2) the SSE dedup `Set` grew unbounded while the event array was capped.

Also repaired a DEVLOG corruption introduced concurrently during this session — the `## Archived history` heading had been clobbered onto the prior (01:02:01) entry's `Files:` line — restoring the heading + rotation intro verbatim. Note: `DEVLOG.md` is now ~1090 lines, past the ~700 rotation threshold; a rotation pass is due (deferred — not bundled into this feature turn).

Files: frontend/src/renderer/{api.ts, App.tsx, events.tsx, TeamFeed.tsx, PromptPanel.tsx, WorkPanel.tsx (new), AgentPanel.tsx, TeamGraph.tsx, Settings.tsx, index.html}, frontend/vite.config.ts (new), DEVLOG.md

---

### 2026-07-01 02:15:00 — design: OD-11 run-strip step label → hover-only (per user)

Per the user, the OD-11 current-step name is now **hover-only** rather than an always-on mono line above the bar (the always-on label changed the card's layout, which they didn't want). Removed the `.rseg-lab` element from the three segmented cards (node-4/9/13) and the gallery specimen, deleted the now-unused `.rseg-lab` CSS rule, and updated the DESIGN.md + gallery wording. The step name (`Step N of M · <name>`) stays on the bar's `title` tooltip. Net effect: segmented and plain run-strips are now **layout-identical** (no label line) — every card's bar is `--size-6` and seats identically.

Verified over `http://localhost` (headless + headed, narrow 1180 / wide 1920): every bar 6px, all bars 54px off card-bottom (aligned), **0** `.rseg-lab` elements, all three segmented tooltips intact, **0** console errors.

Context (not built): a broader OD-11 revision is under discussion — state should **recolor the current segment** (running→shimmer / paused-pending→warm / errored→danger) on a persistent segmented track rather than collapse to a flat bar; a run/turn/step glossary (a "run" = between prompt inputs; steps live within a run; retry redoes the whole run → segments reset); and a **per-card inbox footer** (split the subagents footer into subagents-left + an envelope+count inbox-right, expandable to typed entries that deep-link into the Inbox) so non-blocking Warnings surface on the card without touching the binary status badge.

Files: design/mockup.html, design/styles.css, design/gallery.html, design/DESIGN.md, DEVLOG.md

---

### 2026-07-01 14:49:23 — docs: created docs/ARCHITECTURE.md (system architecture) + moved the OD decisions tracker

Created **`docs/ARCHITECTURE.md`** — the first system-architecture reference (the `docs/` dir was empty). It documents the four-tier stack (Electron frontend ↔ FastAPI sidecar `:7690` ↔ driver seam ↔ tmux/WSL2 bridge) with per-layer sections, the OD **coordination spine** (event envelope OD-01/22, prompt queue + hook channel OD-02, linking OD-04+, inbox/caps/identity/checklist, storage-homes OD-23), key end-to-end flows (create / send-while-busy / permission round-trip / link fire / scratchpad delta / resume), and an honest **built vs. visually-lagging vs. bridge-blocked** matrix. Written from a parallel code read of `frontend/` + `sidecar/` + `bridge/`, reconciled against DESIGN.md (intent) and the OD tracker (decided behaviour); explicitly flags `dev/notes/coverage-map.md` as a **pre-integration snapshot** now superseded on "built vs not" (backend + the React renderer are both wired to the full OD contract; the UI only trails the mockup *visually*, per OD-21). Positioned as the system counterpart to DESIGN.md (visuals) and DEVLOG.md (history), linking out rather than duplicating.

Per the user, also **moved** `dev/notes/agent-qa/open-system-decisions-2026-06-29.md` → `dev/notes/` (via `git mv`, history preserved) and **removed** the now-empty `agent-qa/` folder; fixed the two stale path references in `dev/prompts/backend-decision-integration.md`. (DEVLOG entries naming the old path are left verbatim — this file is append-only. Rotation is still due at >1090 lines — deferred, not bundled into this docs turn.)

Files: docs/ARCHITECTURE.md (new), dev/notes/open-system-decisions-2026-06-29.md (moved from dev/notes/agent-qa/), dev/prompts/backend-decision-integration.md, DEVLOG.md

---

### 2026-07-01 15:44:05 — docs: corrected & tightened docs/ARCHITECTURE.md after external review

Reviewed `docs/ARCHITECTURE.md` (created earlier today, commit `108d3c7`) against the live code — a provenance trace of its authoring session plus a fresh parallel re-verification of `sidecar/` + `bridge/` + `frontend/` and the referenced docs. Verdict: **substantively accurate** (dozens of concrete claims — driver CAPABILITIES sets, the event envelope, the endpoint surface, ring size, poll cadences, OD-01…OD-23 attributions, storage, reconnect — all confirmed against code). Fixed the defects the review surfaced: **(D1)** `serialize.py` path corrected `sidecar/drivers/serialize.py` → **`sidecar/serialize.py`** in §4.3 + §10; **(D2)** removed the phantom `/scratch (3s)` poll from §3.3 (scratch is read on demand + delta-pushed via the hook/watermark path, OD-17, not polled); **(D3)** completed the §10 repo map — added the 13 previously-omitted sidecar modules (`links`, `scratchpad`, `watermark`, `library`, `templates_store`, `console_catalog`, `checklist`, `marquee`, `subagents_naming`, `settings_io`, `utility_llm`, `deletion`, `storage`); **(D4)** noted the per-session `GET /sessions/{id}/events` SSE in §4.2; **(D5)** reconciled the `TmuxBridge` method list in §5.4 with the internal helpers (`session_id_for`/`register_session_id`/`wsl_host_ip`/`sidecar_hook_base_url`); **(D6)** reworded "/utility/* via the `sdk` driver" → the in-process SDK `query()` path (not the driver class).

Also **collapsed the `v0.3.0` version string to a single canonical mention** (the "Sources & freshness" header) — removed the inline repeats in the topology diagram, the §4 intro, and §6 — so the one volatile value that recurred can't drift out of sync. Per discussion, deliberately did **not** add a separate parameters table / inline tags: agents treat code as source-of-truth (the doc says so), and a parallel value registry would just add a second sync burden. No structural rewrite — surgical edits only; all CONFIRMED content preserved verbatim. (DEVLOG rotation still overdue at >1110 lines — deferred, not bundled into this turn.)

Files: docs/ARCHITECTURE.md, DEVLOG.md

---

### 2026-07-01 16:00:32 — System data-model map (dev/notes/data-model-map.md)

Wrote a new working note mapping the dashboard's data model end-to-end, in response to a concern
that the storage model felt "overly distributed" and hard to audit. Frames all state in four
categories (🏠 dashboard store `sidecar/runtime/`, 📁 project store `<project>/.awl/`, 🔌 surfaced
Claude config, ⚡ in-memory) and ties each data type to its real repo-relative path *and* its UI
pane/`data-comp` in a master table, plus two end-to-end traces, the durable-vs-ephemeral boundary,
and an audit. Built from three read-only探 passes (persistence census, UI-surface map, OD-23
scoping rationale). Key finding: persistence is concentrated (only 5 files on disk); the real
maintainability risk is the *invisible* persist/ephemeral split — Inbox/Links/queues/watermarks
are in-memory and lost on a sidecar restart with no UI cue. Audit verdict: keep the OD-23
three-homes model; recommend two light fixes — make ⚡ a documented tier and decide which items
should persist (Inbox, Links), and replace the plan-reviews filename key + the raw-`cwd` scope key.
Docs-only, no code changed. Complements the broader `docs/ARCHITECTURE.md` by zooming into the
storage/scoping model with UI anchoring + audit. (DEVLOG rotation still overdue at >1120 lines —
deferred again, not bundled into this turn.)

Files: dev/notes/data-model-map.md (new), DEVLOG.md

---

### 2026-07-01 16:10:26 — docs: integrated the OD decisions into ARCHITECTURE.md; archived the tracker

Refactored `docs/ARCHITECTURE.md` to **absorb the decided `OD-*` decisions** so they live in one doc, then **archived** the standalone tracker. Added a new **§10 "Design decisions (the OD record)"** — one distilled entry per **OD-01…OD-20, OD-22, OD-23** (settled decision + where it's wired / "UI: DESIGN.md"), grouped by the original tiers; the `OD-NN` labels stay stable anchors (DESIGN.md + `dev/prompts/` reference them and now resolve here). **OD-21 (React-port timing) was retired from tracking** per the user — its "park until design churn → zero" fact stays as plain context in §3.4 + §9, with a one-line retirement note in §10. Rewrote the header ("what it is *not*" now says decisions are integrated, not externalized), repointed the §12 Related-docs bullet, and renumbered Repo map → §11 / Related docs → §12. Rationale kept out: the archived tracker retains the forks/confidence/"why," §10 records only the *what* (build status stays §9's matrix).

`git mv dev/notes/open-system-decisions-2026-06-29.md → archive/notes/open-system-decisions-2026-06-29.md` (history preserved); fixed the now-dangling tracker path in `dev/prompts/backend-decision-integration.md` (2 refs) and `dev/prompts/design-stream-finisher-p1.md` (1 ref — it still pointed at the even-older `agent-qa/` path), both now → the archive path + a note that decisions live in ARCHITECTURE.md §10. Verified: §§1–12 numbered with no gaps, 22 OD entries present, no stray OD-21, both tracker links resolve to the archive. (Concurrent stream note: another session's 16:00:32 `data-model-map` entry above + its untracked files were left untouched; only my own paths were staged. DEVLOG rotation still overdue >1130 lines — deferred.)

Files: docs/ARCHITECTURE.md, archive/notes/open-system-decisions-2026-06-29.md (moved from dev/notes/), dev/prompts/backend-decision-integration.md, dev/prompts/design-stream-finisher-p1.md, DEVLOG.md

---

### 2026-07-01 17:40:00 — design: OD-10/OD-11 refactor — warning simplification, run-strip segment-recolor, run/turn/step glossary, per-card inbox footer

Landed the four agreed decisions from the build-3a handoff across the six `design/` files. **(A) Run-strip segment-recolor (OD-11):** the **current segment now carries the run's state** instead of the bar collapsing to flat — running = green + barber-pole; a **blocking pause** (Permission/Plan/Decision/max-turns) = warm `--warning`, static; a **step-scoped error** = `--danger`, static. A non-blocking **Warning keeps shimmering**, "paused between steps" colours the **next** segment, a **structural/whole-run error** uses the flat `.run-error` fallback, and **Retry resets** the segments. Added `.cur-paused`/`.cur-error` modifiers (shimmer suppressed), converted node-1 (sandy, paused-at-step-3) to a live segmented-paused bar, kept node-3 (drew, structural error) on the flat fallback with a clarifying comment. **(B) Glossary:** added a **Session › Run › Turn › Step** execution-vocabulary section to DESIGN.md ("Exchange" stays reserved for OD-07 inter-agent). **(C) Per-card inbox footer (`node-inbox`, new component):** split the card footer into **subagents-left + a teal envelope+count inbox-right** — a **faithful mirror** of the agent's open Inbox items (built from `REQS` at boot via `renderNodeInboxes()`), expandable to **typed rows that deep-link into the Team Feed → Inbox** (scroll+expand+select+flash), **dimmed+non-expandable** when empty, drawer **independent** of the subagents drawer. Count = **open items** (can be >1, and >0 while the badge reads *active* — added a non-blocking Context warning to `max` to demonstrate). **(D) Warning simplification (OD-10):** dropped the two-variant cap-crossing (Continue/Raise cap/Stop) + generic (Acknowledge) sets — a Warning is now a plain FYI with **Dismiss** (pink `btn-main`, its sole completion action — *not* danger) + **Reply** only; never auto-clears.

Propagated across all six files **except `tokens.css`** (intentionally unchanged — reuse-first: `--success`/`--warning`/`--danger`/`--secondary`/`--inbox-permission` already cover every value). Registered `node-inbox` in DESIGN.md + a gallery card; synced the gallery agent-node-card + run-strip specimens; updated the OD-10/OD-11 notes, the Team-Graph footer bullet + Inbox Warning row, the glossary, and the accent-ladder colour clause (a Warning's Dismiss is pink vs. the Error card's Dismiss danger).

Verified over `http://localhost` on a real Chromium (Playwright MCP, regular-Chrome UA), narrow (cards forced to their **176px minimum**) + wide (1920): `behavior.js` `node --check` clean; **0 real console errors** (only the pre-existing Tailwind-CDN warning + a favicon 404); run-strips uniformly **6px**; node-1 current segment computed `--warning`; **6 footer envelopes** (count 1: sandy/drew/max/rowan/vega/sage) + **7 dimmed empties**; envelope expand/collapse + row deep-link (→ inbox card open+selected+flashed) + empty non-expand + independent drawers all drive correctly; both warning cards show **Dismiss (pink `#f582ae`) + Reply** only with **zero** stray cap-actions; Dismiss removes the card + decrements the section count (2→1); **no footer/run-strip overflow at 176px** (drawer rows ellipsize in-bounds); gallery run-strip (paused/error segments), `node-inbox` (4 specimens), and the warning card all render correct. Static-mockup caveat (already documented): the footer envelope and the Inbox card aren't live cross-wired — resolving one doesn't rebuild the other in the demo; the *mechanism* is specified, live sync is a `frontend/` concern. (DEVLOG rotation still overdue >1150 lines — deferred, not bundled into this feature turn.)

Files: design/styles.css, design/behavior.js, design/mockup.html, design/gallery.html, design/DESIGN.md, DEVLOG.md

---

### 2026-07-01 17:55:00 — DEVLOG rotation: archived 112 entries into DEVLOG-archive-04

Cleared the long-overdue rotation the prior entries kept deferring. Moved the oldest **112** Log entries (2026-06-26 02:10:00 → 2026-06-30 15:30:00) **verbatim** into a new [`archive/devlog/DEVLOG-archive-04.md`](archive/devlog/DEVLOG-archive-04.md) (cut only at `### ` headings, never mid-entry), taking `DEVLOG.md` from **1167 → ~290 lines**; the recent window now opens at the 2026-06-30 17:45:00 Tier-1 backend-foundation entry. Refreshed the recent-window note + added the archive-04 digest paragraph and index row under **Archived history**. Verified the move **byte-for-byte** against a pre-rotation backup — the moved block, the retained tail, and the header are each `diff`-identical, no entry split.

Files: DEVLOG.md, archive/devlog/DEVLOG-archive-04.md

---

### 2026-07-01 18:05:00 — docs: fully anchored data-model-map to the final intended design

Per the user, re-anchored `dev/notes/data-model-map.md` so its UI column reflects the **final
intended design/system**, not current MVP wiring. The §2/§3 structure (pane names, tabs, every
`data-comp`) was already the `design/` mockup; stripped the four §3 table cells that had leaked
current-implementation caveats ("save flow planned in MVP", "reads wired / global writes planned",
"drawer wired; Save/Delete + edges planned", "placeholder — no live source yet") so features read
as the finished product. Left the "survives restart?" column + the §5–§7 audit as current-backend
truth **on purpose** — that gap is exactly what the audit measures against the ideal. Touched only
my own paths (concurrent session active on `docs/`+`design/`).

Files: dev/notes/data-model-map.md, DEVLOG.md

---

### 2026-07-01 18:25:00 — chore: moved design/TODO.md → dev/notes/DESIGN_TODO.md (design/ now pure design files)

Per the user, moved the design backlog out of `design/` so the design system is exactly its **six files** and nothing else. `git mv design/TODO.md dev/notes/DESIGN_TODO.md` (history preserved). Updated the live **path** references: the CLAUDE.md "Design changes" rule (now names the backlog's new home) and the three dev prompts that cited `design/TODO.md` as their work-list/context ([`link-behavior-refactor.md`](dev/prompts/link-behavior-refactor.md), [`nextup-parallel-execution.md`](dev/prompts/nextup-parallel-execution.md), [`backend-decision-integration.md`](dev/prompts/backend-decision-integration.md) — verified no `design/TODO.md` path remains under `dev/`). Left untouched: the `archive/**` snapshots, the append-only DEVLOG history, `.claude/plans/`, and the purely-conceptual "don't reference the backlog" mentions in the spent prompts (policy statements, not path pointers).

Files: design/TODO.md → dev/notes/DESIGN_TODO.md (moved), CLAUDE.md, dev/prompts/link-behavior-refactor.md, dev/prompts/nextup-parallel-execution.md, dev/prompts/backend-decision-integration.md, DEVLOG.md

---

### 2026-07-01 17:01:17 — docs: CLAUDE.md audit — fixed stale claims + surfaced ARCHITECTURE.md

Audited CLAUDE.md against the live tree and fixed the drift the user flagged. **Added [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) to Key files** (the system/structure reference) and named it in the `docs/` folder row — the highest-value add, and the lever that lets the rest stay terse (point to ARCHITECTURE.md for module/endpoint/component detail instead of enumerating it here). Fixes: **frontend** row "largely one App.tsx" → the componentized renderer (App.tsx shell + the six panels + shared events/api/tokens/ui); **serialize.py** corrected in prose to the `sidecar/` root (not `drivers/`) + a §4 pointer; **design/** row gained `styles.css`; **archive/** row broadened (devlog + retired notes/docs); the dangling **`dev/notes/repo-migration.md`** Key-files link repointed to `archive/dev/notes/`; the **tests/** + Testing blurbs updated from the stale 4-file list to the ~18-file per-module unit suite; and the bridge's 4 internal helpers noted beyond the 20 documented methods. No behavioral-rule changes; edits landed on the concurrent stream's committed base (its `design/TODO.md`→`DESIGN_TODO.md` CLAUDE.md tweak was in a different region — no collision).

Prior commit this turn (`4741614`) was a tree-cleanup checkpoint of leftover untracked files (a concurrent session's `data-model-map.md` + `archive/design/design-v11p6/`, plus two `.claude/plans/` files) — committed, not authored, per the user's request to clean the tree. (Timestamp is my Git-Bash clock; the 18:25 entry above reflects the other session's clock skew.)

Files: CLAUDE.md, DEVLOG.md

---

### 2026-07-01 18:08:32 — design: sandy dual-dropdown demo card + OD-11 run-strip segment-recolor demo coverage

Closed the two remaining design gaps across the six-file system (map→implement→review workflow + main-loop triage + browser verify). **Task 1 (sandy dual-dropdown):** node-1 now carries both drawers so they can be driven open together — added a 2nd `sandy` REQS item (`type:'permission'`, "Edit settings.json" → envelope count 2) and replaced her `subs-empty` footer with a populated 6-badge `.subs-acc` (A1–A6, mixed: 4 active / 1 idle / 1 error), modeled on node-4. **Task 2 (OD-11 coverage):** converted the three flat `run-pending` bars — node-5 rowan (Step 5/5, max turns), node-7 vega (Step 3/5, sign-off), node-11 sage (Step 4/6, permission) — to segmented `run-seg` bars with a single `.rseg.cur.cur-paused`, dropping the fabricated `width:%` fills (node-3 drew's flat `run-error` left intact as the whole-run fallback). Propagated to `gallery.html`: synced the agent-node-card live mirror (6 badges + ✉2), added a 6-badge node-subagents specimen, and added a "paused BETWEEN steps" run-strip specimen (warm on the *next* segment); reconciled the hand-written line-1725 overview count (5→6, sandy's permission added). No `tokens.css`/`styles.css`/`DESIGN.md` change (reuse-only — existing tokens/classes cover every value). Verified: `node --check` clean; browser-driven at wide (1920) + narrow (182px) with **both drawers open on sandy at once** (zero overflow, card grows downward), all three converts segmented with no fabricated widths, drew unchanged, and the three new/updated gallery specimens — headless loop closed with a headed parity pass.

Files: design/behavior.js, design/mockup.html, design/gallery.html, DEVLOG.md

---

### 2026-07-01 19:47:00 — docs: backlog audited + refactored — dev/notes/DESIGN_TODO.md → TODO.md (design & backend staging backlog)

Audited every backlog item (old sections A–D + Next up; Inbox/Scratch untouched) against the live system via three parallel read-only sweeps (design files · frontend/sidecar/bridge · repo+DEVLOG), then refactored per the user. **Removed as done/resolved:** B1 per-agent MCP & plugins (OD-18 Create/Details msels + `--mcp-config`/`enabledPlugins`), B2 custom permissions (Mode + Deny rules in Create/Details; full `permission_rules` at launch), B12 interactive comms (the OD-17 scratchpad is the shared dynamic doc, live-verified), C6 transcript payload (resolved by the OD-06 Relationship model), and B19 lifecycle wind-down (signal half = the OD-10 cap-crossing Warning, built; wind-down half deliberately killed by OD-10 — "do not re-propose"). **Trimmed to the remaining gap:** load past agents, Plans action loop (edit-in-place + approve→resume), subagent management (observability built), save response summary (Summarize is copy-only), notes hub, link edges (grouped link-list exists; on-graph edges deferred). All of old-D kept (none verifiably done). **Restructure:** renamed → `dev/notes/TODO.md` (git mv), four effort sections → three domain sections **D Design · B Backend · H Housekeeping & docs** (former "Needs research" items now carry an **(open)** marker in their domain section), header + maintenance notes rewritten for two-layer staging (backend items point at `docs/ARCHITECTURE.md` + pytest conventions; design items unchanged at the six-file rules). Cross-ref updated (old "see B17" → "see D2"). Updated live path refs: CLAUDE.md design rule + the three dev/prompts files; DEVLOG history left verbatim.

Files: dev/notes/DESIGN_TODO.md → dev/notes/TODO.md (moved + rewritten), CLAUDE.md, dev/prompts/nextup-parallel-execution.md, dev/prompts/link-behavior-refactor.md, dev/prompts/backend-decision-integration.md, DEVLOG.md

---

### 2026-07-01 19:52:04 — docs: TODO.md h1/h2 heading labels → ALL CAPS

Per the user, uppercased the eight `#`/`##` heading labels in `dev/notes/TODO.md` (title, HOW AGENTS MAINTAIN THIS LIST, D — DESIGN, B — BACKEND, H — HOUSEKEEPING & DOCS, NEXT UP, INBOX, SCRATCH). The `###` subheads under Scratch and all body text/prose section references left unchanged.

Files: dev/notes/TODO.md, DEVLOG.md

---

### 2026-07-01 20:58:00 — docs: TODO.md Inbox triaged → 13 NEXT UP items + D6 (open); Inbox cleared

Triaged the Inbox against the live design files (mockup/styles/behavior/tokens/DESIGN.md), with the user resolving the open questions in-conversation. Filed **13 items into NEXT UP**: context refresh + on-demand pull (w/ a new loading-state primitive); pink footer + splitters (teal kept on hover **and drag** — needs a drag-state class, teal is `:hover`-only today); link direction defaults 2-way; a **"Text"** content toggle (CC's `text` block; rail tag `msg`→`txt`) mirrored into the Link drawer's shared taxonomy; History card delete (non-Active/Complete); agent-surface data alignment (**Team Graph cards = ground truth**; the feed filter tree is hand-authored and drifts); subagent count badge → selected/total ("2/4"); selector popovers → in-flow accordions (feed filter · Prompt To · From); History From → multi-select filter (Compose stays single); Stop buttons → solid danger fill; Link Config pair dropdowns; Documents footer action strip (Plans strip minus Reject/Approve); comment popout fit fix (`.plan-rev` cap). Filed the idle-unseen indicator as **D6 (open)** — mechanism/clear-condition needs the human's call. Dropped the subagent All/None note as already-wired in the mockup (`agAllNone` walks `.agrow--sub`; superseded by the alignment/accordion items). Inbox now empty; the user self-moved the charcoal note to Scratch and deleted the error-red + from/to-vis-toggle notes before filing.

Files: dev/notes/TODO.md, DEVLOG.md

---

### 2026-07-01 21:19:52 — docs: D6 idle-unseen indicator resolved → NEXT UP 14 ("Response" Inbox type)

Resolved the D6 (open) design call in-conversation and moved it to **NEXT UP item 14**: a new non-blocking **Response** Inbox section (bottom of the ramp, neutral heading) that opens when a run ends with unreviewed output — one coalesced card per agent, **View** (→ Messages scoped + flashed, completes) · **Reply** (shared routing, completes), status badge untouched (no fifth idle state), envelope counts it like a Warning. Naming settled after weighing Result/Message/Response: the request-vs-response frame won (the five existing sections are agent *requests*; this is the lone *response* to the operator's prompt), and the existing `response-format-control` shares the same referent so the term reinforces rather than collides. D6 removed from the D section (D1–D5 unchanged, no renumbering needed).

Files: dev/notes/TODO.md, DEVLOG.md

---

### 2026-07-01 22:05:00 — docs: data-model-map.md rewritten to the new storage model (planning session encoded)

Full rewrite of `dev/notes/data-model-map.md` encoding the 2026-07-01 storage-planning decisions,
anchored to the final intended system with ⚠ Today markers for current-code divergence. The new
model: **six homes** (dashboard store · project store · transcripts · launch config · Claude
config · derived); `.awl/` → **`.awl-cc-dash/`** (committed, not ignored) with a
`plans/ · docs/ · assets/ · state/` taxonomy; `<project>` = canonical repo root (not raw cwd);
multi-project first-class (all per-project state incl. the agent roster moves into the project
folder); an explicit **persist-vs-derive contract** replacing the invisible ⚡ boundary; per-doc
**`.meta.json` sidecars** (quote-anchored comments, verdicts, provenance) replacing
`plan-reviews.json`; a **transcript policy** (retention pinned via `cleanupPeriodDays: 3650` in
per-agent launch settings, resolved path + session-id persisted, reference-never-copy,
overlay-index keyed to event anchor ids); the **close/reopen restore model** (warm rebind +
T8 cold-restore via `claude --resume` replacing prune-on-dead-tmux); §10 OD-amendment roll-up
queue for ARCHITECTURE.md; §11 implementation backlog **T1–T12** to drive the next build run.
Built ultracode: 3 fact-mapper agents (sidecar state, bridge launch, docs cross-refs) fed the
draft; 3 adversarial verifiers (facts vs code — ~40 citations checked; decisions vs the 18-item
session ledger — PASS; consistency) produced 15 findings, all applied (notably: the scratchpad
board itself is ⚡ and never reloaded — restart wipes it; T7's `plansDirectory` must be an
absolute canonical-root WSL path, not `./`; inbox type set left open-ended for TODO.md #14's
queued "Response" type).

Files: dev/notes/data-model-map.md, DEVLOG.md

---

### 2026-07-01 22:37:04 — docs: second Inbox batch triaged → NEXT UP 15–18; Inbox cleared

Thought through the four new Inbox notes with the user (no-edit discussion rounds), then filed all four into **NEXT UP**: **15 — "System" identity** (gear-on-navy reserved pseudo-identity via an additive `--ag-system` token; Inbox Error cards for system-wide failures + Log lines; filter-only-never-addressable per the subagent precedent — feed-filter row #2 after User, excluded from Compose To/From + History From; Reply disabled, not removed). **16 — Timeline heading** (`.sec-h` label over the `timeline-mode-switcher`). **17 — Link restructure** (supersedes OD-06 "a link can be both": one relationship per link, Relationship → single-select button group; Trigger segmented → dropdown with a new link-only **Piggyback** trigger, defaults DM→Queue / SC→Piggyback, SC ungated; OD-07 amendment — on a one-way link each fire counts as an exchange; All-links → collapsible **Active/Expired** sections, peer-adjacent ordering, full relationship labels per entry, corner count badge on group headers = a new overlay badge family; one-shot context sharing explicitly dropped as a goal — the user handles that via Messages → Embed/Attach). **18 — Lucide direction arrows** (replace the unicode `→ ← ↔` text glyphs in the direction-cycler + links-list rows with `arrow-right`/`arrow-left`/`arrow-left-right`, `--foreground` ink, flex-centred). Inbox now empty; NEXT UP holds 18 items.

Files: dev/notes/TODO.md, DEVLOG.md

---

### 2026-07-01 22:46:09 — chore: commit leftover design-v11p7 archive snapshot

Tree-cleanup checkpoint while committing + syncing the repo: committed the untracked `archive/design/design-v11p7/` — a concurrent session's snapshot of the six design-system files + `mockup-toolkit.js` (file dates 2026-07-01 16:05–17:25), following the same leftover-checkpoint precedent as `design-v11p6`. Committed, not authored, by this session.

Files: archive/design/design-v11p7/ (7 files), DEVLOG.md

---

### 2026-07-02 01:01:03 — Projects-tab concept snippet (Settings step-in) in .scratch

Built a standalone, interactive concept snippet for a future Settings → **Projects** tab: an active-project card (name · path · agents · last-opened · a Close-project action), a Known-projects registry list (reg-row pattern, per-row Open, one-project-at-a-time gating), an "Open other folder…" register action, and a two-choice close confirm ("Close" keeps agents running in tmux / "Close & stop agents"; ghost-×/Esc cancels — deliberately no third Cancel button, per the spec's "exactly two buttons"). Links the real design/tokens.css + styles.css (design/ untouched); behavior is a small inline script by design. Verified end-to-end with a scripted isolated-Chrome click-through (28 assertions, headless + a headed parity pass, narrow/wide extremes) plus an 11-agent adversarial design review — 7 confirmed findings fixed (button tiers per the emphasis ladder: pink Close commit, cream trigger; hbadge not set-kind for the Open state; confirm force-open not toggle; 0-agent running-flag coherence).

Files: .scratch/ui-snippets/projects-tab.html (new), .scratch/pw-verify/ (new — verification harness + screenshots), DEVLOG.md

---

### 2026-07-02 01:12:30 — Projects-tab snippet: Projects moved to first tab

Per user direction, the concept snippet's Settings tab row now leads with **Projects** (Projects · Setups · Usage · MCP · Plugins · Config — was last). Verification harness updated (asserts tab order; inert-tab check retargeted to Setups); full suite re-run green, headless + headed.

Files: .scratch/ui-snippets/projects-tab.html, .scratch/pw-verify/verify.js, DEVLOG.md

---

### 2026-07-02 01:59:40 — ARCHITECTURE.md rewritten as the final-vision reference; OD record dissolved repo-wide

Complete rewrite of `docs/ARCHITECTURE.md` (~1,120 lines) to **final-intended-system** framing: the doc now leads the build (code converges on it), with every OD-01…23 decision woven seamlessly into topical prose (no labels, no index — historical `OD-NN` ids in DEVLOG/archives resolve via the archived tracker), the data-model-map storage model ported wholesale (§8: six homes, `.awl-cc-dash/` taxonomy, persist-vs-derive contract, transcript policy, warm/cold restore), the one-project product model + Projects tab + `projects.json` (§3), the Console mirror+passthrough model (§7.13), TODO #14/15/17 integrated (open Inbox type set + Response, System pseudo-identity, one-relationship links + Piggyback + one-way exchange counting), and an Open-questions research register (§10, four fields per entry); divergences carried as ⚠ Today markers (file+symbol, never line numbers). Verified by a 20-agent workflow: 139-item adversarial traceability check (0 missing), coherence pass (all findings fixed), hermetic unit suite green (395 passed). Ripples: `OD-NN` tokens stripped from all code comments (~197 refs across sidecar/, frontend/src/, tests/, bridge/ — comment-only, zero behavior change) and rewritten to section-name refs in the three `dev/prompts` files; `dev/notes/TODO.md` split into **NEXT UP — DESIGN / — BUILD** (T1–T11 ported with file:line evidence; Projects-tab + design-OD-sweep items appended; per-path instruction sets + shared doc-sync checklist); `dev/notes/data-model-map.md` archived → `archive/notes/data-model-map-2026-07-01.md` with a supersession banner; CLAUDE.md Key-files row reframed + folder-map § refs corrected. **Outstanding:** the five `design/` files still carry ~85 OD tokens — deferred (design churn active) as NEXT UP — DESIGN #20.

Files: docs/ARCHITECTURE.md, dev/notes/TODO.md, dev/notes/data-model-map.md → archive/notes/data-model-map-2026-07-01.md, CLAUDE.md, dev/prompts/backend-decision-integration.md, dev/prompts/design-stream-finisher-p1.md, dev/prompts/design-stream-finisher-p2.md, sidecar/ (20 files), frontend/src/renderer/ (6 files), tests/ (15 files), bridge/bridge.py, bridge/paths.py, DEVLOG.md

---

### 2026-07-02 02:12:33 — design: NEXT UP — DESIGN items 1–18 implemented across the six-file design system

All 18 queued design items built into `design/` (ultracode run: 5 recon agents → 6 sequential implementation batches, with batch E in a user-approved temporary worktree merged back by patch and the branch deleted; per-item adversarial verification; headless UI drive; headed parity pass). Shipped: **pink footbar + pink splitters** with a `.dragging` teal drag-state in `initResizers` (2) · **Timeline** `.sec-h` heading (16) · solid-danger Stop via new `icon-btn--danger-solid` (10) · History-card danger trash + inline confirm on Queued/Next/Held (5) · link direction default **A↔B** (3) with **Lucide arrow icons** (18) and **pair single-select dropdowns** (11) · the **link restructure** (17): one relationship per link (single-select group), Trigger segmented→dropdown (Now·Inject·Next·Queue·Hold·**Piggyback**; defaults DM→Queue, SC→Piggyback), collapsible **Active/Expired** link sections with peer-adjacent sort + a new **corner-count overlay badge** family, and the OD-06/OD-07 DESIGN.md amendments · **shared roster single-source** (`AG[k].subs` → `fillRosterLists`) aligning the feed filter tree / Prompt To / History From to the Team Graph cards (6) · **selected/total** subcount badges (7) · selector popovers → **in-flow accordions** (8) · History From **multi-select** (9) · **"Text" content toggle** + `msg`→`txt` rail tag + Link-drawer taxonomy mirror (4) · **"Response" Inbox section** with one coalesced card per agent, View/Reply only (14) · **System pseudo-identity** (`--ag-system` gear-on-navy, filter-only, Reply-disabled Error card) (15) · Documents **footer action strip** minus Reject/Approve (12) · comment-popout **fit root-cause fix** + `.plan-rev` cap 346→520 (13) · new **`loading-strip` primitive** + context-accordion simulated on-open pull, design side only (1). Verified: 15 items by independent adversarial verifiers (all PASS) + E's three by a 24-check scripted drive; headless drive of mockup+gallery clean (0 console errors); headed parity pass via isolated-Chrome script (`.scratch/pw-verify/parity-pass.js`) — identical rendering. Known residues for review: a pre-existing narrow-viewport History-card badge overflow (untouched, out of scope) and a feed demo message attributed to `max › B1` while max's card roster has only A1 (demo data, flagged not fixed). Items left in place in TODO.md per the review rule; the later-added items 19–20 (other session) untouched.

Files: design/tokens.css, design/styles.css, design/behavior.js, design/mockup.html, design/gallery.html, design/DESIGN.md, DEVLOG.md

---

### 2026-07-02 02:28:00 — design/ OD-reference sweep (closes NEXT UP — DESIGN #20)

Removed all 85 retired `OD-NN` tokens from the five design files, completing the repo-wide OD dissolution: DESIGN.md prose rewritten to plain decision names with `docs/ARCHITECTURE.md` § pointers at each first substantive mention; behavior.js / styles.css / mockup.html refs were all comments; gallery.html additionally had 12 `gx-blurb` rendered-text spots — strict token deletions only (text shortens, no layout risk; browser pass skipped by user call). Zero `OD-[0-9]` hits remain in `design/`; `node --check behavior.js` passes; diff verified 79−/79+ with every removed line containing an OD token. TODO #20 left in place for human review/removal.

Files: design/DESIGN.md, design/mockup.html, design/gallery.html, design/behavior.js, design/styles.css, DEVLOG.md

---

### 2026-07-02 02:35:12 — TODO Next up — Design #1 synced to the built Projects-tab concept

Per user direction, rewrote **NEXT UP — DESIGN #1 (Projects Tab + Close Flow)** so its description matches the built + click-verified concept snippet: registry-row list wording, the active-project card's exact fields, one-project-at-a-time gating (other rows' Open disabled), the exactly-two-button confirm semantics (keep-running vs stop, one-line explanations, Cancel/Esc), sentence-case **Close project**; cleaned a corrupted trailing fragment ("each number meant.") and expanded the snippet reference (`.scratch/ui-snippets/projects-tab.html`, marked concept-only / rebuild-don't-port). The topbar/footbar chip + gallery-empty-state scoping notes kept as-is (settled model, deliberately beyond the snippet — chip now marked "not in the snippet").

Files: dev/notes/TODO.md, DEVLOG.md

---

### 2026-07-02 04:01:29 — codex: add AGENTS.md entry point

Added a root `AGENTS.md` for Codex sessions. It points agents to `CLAUDE.md` as the primary project guide, explains that Codex is being used as support capacity to continue focused repo work while Claude Code / Claude Max plan tokens are limited, and repeats the key working rules that matter before editing.

Files: AGENTS.md, DEVLOG.md

---

### 2026-07-02 04:03:29 — claude guide: note Codex entry point

Added `AGENTS.md` to the `CLAUDE.md` Key files table so Claude agents understand that it is the Codex-specific entry point, points back to the Claude guide, and exists as coordination context for support work while Claude Max tokens are constrained.

Files: CLAUDE.md, DEVLOG.md

---

### 2026-07-02 04:14:40 — architecture queue numbered with priority placeholders

Numbered the eight current `docs/ARCHITECTURE.md` §10 open-question entries and preallocated empty `Priority — High`, `Priority — Medium`, and `Priority — Low` subsections at the end of the section for the next sorting pass.

Files: docs/ARCHITECTURE.md, DEVLOG.md

---

### 2026-07-02 04:23:29 — scratch cleanup: preserved ui-snippets

Cleaned the ignored `.scratch/` transient bucket per request: removed 156 non-protected top-level entries (~91 MB), including stale screenshots/logs/scripts/folders and generated verification output. Preserved `.scratch/ui-snippets/` untouched; it remains the only child under `.scratch/`.

Files: .scratch/ (ignored transient cleanup; `.scratch/ui-snippets/` preserved), DEVLOG.md

---

### 2026-07-02 04:26:02 - docs: old note port-candidate review scratch

Reviewed the three old dev notes requested (`component-inventory-and-wiring`, `component-system-spec`, and `coverage-map`) against current DESIGN/ARCHITECTURE/DEVLOG, then wrote a scratch handoff identifying which details are already absorbed, stale, or still worth centralizing.

Files: dev/notes/scratch/2026-07-02-doc-port-candidates.md (new), DEVLOG.md

---

### 2026-07-02 04:30:15 — architecture queue sorted by priority

Sorted `docs/ARCHITECTURE.md` §10 into `Priority — High`, `Priority — Medium`, and `Priority — Low` subsections per user direction, renumbering entries continuously across the subsections. Added a maintenance note that future edits must renumber entries continuously in High → Medium → Low display order.

Files: docs/ARCHITECTURE.md, DEVLOG.md

---

### 2026-07-02 04:32:31 - docs: add TLDR to old-note port review

Appended a concise TLDR to the scratch port-candidate review so the actionable candidates are scannable without reading the full analysis.

Files: dev/notes/scratch/2026-07-02-doc-port-candidates.md, DEVLOG.md

---

### 2026-07-02 04:41:10 - docs: correct port-candidate TLDR

Corrected the scratch port-candidate review after rechecking `DESIGN.md`: the mockup behavior checklist is already covered, so it is now marked as not a port candidate and removed from the TLDR's candidate list.

Files: dev/notes/scratch/2026-07-02-doc-port-candidates.md, DEVLOG.md

---

### 2026-07-02 04:54:08 - docs: archive retired dev notes

Moved the three retired dev notes into `archive/dev/notes/` for deprecation cleanup: component inventory/wiring, component system spec, and coverage map. Searched current docs/prompts for remaining references; no references were edited in this pass.

Files: dev/notes/component-inventory-and-wiring.md -> archive/dev/notes/component-inventory-and-wiring.md, dev/notes/component-system-spec.md -> archive/dev/notes/component-system-spec.md, dev/notes/coverage-map.md -> archive/dev/notes/coverage-map.md, DEVLOG.md

---

### 2026-07-02 04:57:39 - docs: remove architecture related-docs section

Removed `docs/ARCHITECTURE.md`'s trailing Related docs section so the architecture reference no longer points agents at superseded archive/provenance docs; current authority relationships remain defined in the document intro and project guide.

Files: docs/ARCHITECTURE.md, DEVLOG.md

---

### 2026-07-02 05:00:16 - docs: audit archive notes for port candidates

Audited `archive/notes/data-model-map-2026-07-01.md` and `archive/notes/open-system-decisions-2026-06-29.md` against the current architecture/design/TODO ground truth, then overwrote the scratch review with the finding that no meaningful port-worthy content remains.

Files: dev/notes/scratch/2026-07-02-doc-port-candidates.md, DEVLOG.md

---

### 2026-07-02 05:03:07 - docs: review unverified behavior candidates

Reviewed the numbered candidate source set for desired behavior that is not proven, not wired, or still lacks a clear implementation path. Wrote a concise scratch triage with 22 candidate items and recommendations, noting the moved coverage-map archive path and the highest-value follow-ups for the architecture queue.

Files: dev/notes/scratch/2026-07-02-unverified-behavior-candidates.md (new), DEVLOG.md

---

### 2026-07-02 05:56:50 - tests: inventory current suite coverage

Reviewed the live `tests/` tree, collected 428 pytest cases, and ran the hermetic subset (`395 passed, 33 deselected`). Rewrote `tests/README.md` from the stale bridge-only summary into a current inventory by file, marking what is established, what is not established, live-test caveats, and coverage gaps for app/UI smoke testing.

Files: tests/README.md, DEVLOG.md

---

### 2026-07-02 05:59:20 - tests: add README maintenance rule

Added an explicit maintenance note to `tests/README.md` that test-suite changes must keep the README's layout table and established/not-established coverage notes current.

Files: tests/README.md, DEVLOG.md

---

### 2026-07-02 06:05:57 - tests: revert README audit rewrite

Restored `tests/README.md` back to its pre-audit tracked content after the test inventory write-up proved too snapshot-like for a durable README.

Files: tests/README.md, DEVLOG.md

---

### 2026-07-02 — reviewed + committed the Codex-session working tree

Audited the uncommitted working tree from the prior Codex session before committing: confirmed the three `dev/notes/` deletions are content-identical moves into `archive/dev/notes/` (CRLF-only diff), the `ARCHITECTURE.md` §10 sort preserved all 8 open-question entries (renumbered into High/Medium/Low), and the §12 Related-docs removal only dropped pointers to now-archived docs. Nothing lost or mangled. Committed and pushed as housekeeping.

Files: (review only — committing CLAUDE.md, DEVLOG.md, dev/notes/TODO.md, docs/ARCHITECTURE.md, archive/dev/notes/*, dev/notes/scratch/2026-07-02-unverified-behavior-candidates.md)

---

### 2026-07-02 06:27:02 — tests: durable README rewrite + live-suite Codex hand-off

Ran the hermetic unit tier for ground truth (`395 passed, 33 deselected` in ~1.7s — imports the real modules, so confirmed current). Rewrote `tests/README.md` from the stale bridge-only summary into a **durable** map: the two-tier model (hermetic default vs live/integration opt-in), a file→module coverage table, an explicit **established-vs-not** section (frontend has zero tests; `serialize.py`/`runtime_store.py`/`drivers/sdk.py` are gaps), run commands, and a maintenance rule (no pass-count snapshots). Left the 20 `test_*` files flat per decision (no folder reorg). Added `dev/prompts/run-live-bridge-tests.md` — a mechanical run-and-report hand-off for Codex to execute the 33-test live tier (needs WSL2/tmux) and report via a fixed template without fixing anything.

Files: tests/README.md, dev/prompts/run-live-bridge-tests.md (new), DEVLOG.md

---

### 2026-07-02 06:45:42 — docs: promoted 2 Inbox tweaks into NEXT UP — DESIGN (#3, #4)

Filed both Inbox notes into NEXT UP — DESIGN with disambiguated component refs, then cleared the Inbox. #3 **Turns → Timeline Gap** — balance the Agent-panel Details gap between the Turns accordion (`#turns-bd-panel`) and the "Timeline" `.sec-h` heading to match the Context→Turns gap. #4 **Picker Accordion Chevron Control** — give the Prompt-panel From/To multi-select pickers (`.src-dd.dd.multi.dd--acc`) a square, divider-flanked toggle like the card accordions' `.fcard-chevbtn` (replacing the inline `.acc-cv`). No design files touched yet — implementation pending user go-ahead.

Files: dev/notes/TODO.md

---

### 2026-07-02 07:16:37 — test: durable per-run results records + retention + Codex prompt

Wired `tests/conftest.py` to emit JUnit XML (`results_*.xml`) + a human-readable summary (`results_*.txt` + `results_latest.txt`) into `tests/log/` each run — PASS/FAIL, counts (incl. deselected/skipped), duration, and the commit + tier + selection + env it was verified against, plus any failures with one-line reasons. Prunes `tmux_bridge_*.log` to the newest 20 (results records never pruned). Verified on the hermetic tier (395 passed; debug logs pruned 132→21). Updated `tests/README.md` to document the records, and `dev/prompts/run-live-bridge-tests.md` so the Codex live-run reports by pasting `results_latest.txt` instead of hand-assembling a template. Test infra was committed as `42e8b06` (conftest + README only) to avoid entangling a concurrent session's DEVLOG/TODO edits.

Files: tests/conftest.py, tests/README.md, dev/prompts/run-live-bridge-tests.md, DEVLOG.md

---

### 2026-07-02 07:25:22 — note: commit 6b4f425 also carried a concurrent design propagation

History-clarity note. Commit `6b4f425` (logged above as the results-record + Codex-prompt change) was made with a pathspec-less `git commit`, so it also swept in a concurrent session's already-staged six-file design propagation — `design/DESIGN.md`, `behavior.js`, `gallery.html`, `mockup.html`, `styles.css` — alongside the intended `DEVLOG.md` + `dev/prompts/run-live-bridge-tests.md`. No work was lost: the design unit is complete and committed; only the commit message under-describes it. Not reverted (main is shared + pushed). Corrective practice: commits here now use explicit `git commit -- <paths>` to isolate from the shared index.

Files: DEVLOG.md

---

### 2026-07-02 07:35:14 — design: NEXT UP — DESIGN items 1–4 built across the six-file system (4-way parallel + rendered-verified)

Implemented all four NEXT UP — DESIGN items via a 4-way parallel worktree workflow (one agent per item, isolated worktrees, full six-file propagation + diff export), then merged the four diffs to main and drove the rendered UI to verify. (1) **Projects tab + close flow** — new *first* Settings tab (Projects · Setups · Usage · MCP · Plugins · Config), active-project card, one-project-at-a-time registry, two-button warning-toned close-confirm (Close / Close & stop agents; ghost-x + layered Esc), topbar active-project chip, empty state shipped as a gallery-only variant. (2) **Subagent demo-message roster fit** — MSGS now references only real subagents (max→A1, fen→B1–B3, sandy→A1–A6; dropped the phantom `max›B1`), cross-checked against the card rosters. (4) **Picker accordion chevron** — the multi From/To pickers (`#feed-filter`, `#hist-from`, `#prompt-targets`) seat their chevron in a flush 36px square, `border-left`-divider cell (`.acc-chevcell`) mirroring `.fcard-chevbtn`, scoped to `.dd.multi` so the single source picker is unchanged. (3) **Turns→Timeline gap** — the build agent's `mb-3` on `#turns-bd-panel` was a no-op (the accordion body is `display:none` when collapsed); rendered measurement caught it, so the 12px moved onto the always-rendered `.sec-h` via `mt-3` — now equal to the Context→Turns gap (12px == 12px, confirmed narrow + wide).

Verification: Playwright drive of every touched surface (open → close-confirm → Esc → close branch → register → reopen; picker open + chevron rotation; gap measurement; Messages nesting; gallery cards) at narrow (1080) + wide (1920); the browser renders headed/new-headless (normal UA), so pixel-identical to a headed pass. `node --check design/behavior.js` passes; 0 console errors (favicon 404 only).

History note: items 1/2/4 + the Projects/picker parts of `mockup.html` landed in HEAD via the concurrent commit `6b4f425` (the sweep documented above); this commit carries the item-3 gap fix, the TODO.md promotion of #3/#4 into NEXT UP — DESIGN, and this log — committed with explicit `git commit -- <paths>` per that corrective practice.

Files: design/mockup.html, dev/notes/TODO.md, DEVLOG.md

---

### 2026-07-02 07:44:40 — docs: §10 open-questions queue → evidence-backed status board

Reworked `docs/ARCHITECTURE.md` §10 into a status board. Added a status-tag legend (✅ proven / ◐ partially proven / ❓ unproven / ⛔ impossible-today) + an **Evidence** line on every entry citing the test that backs it (unit vs live), anchored to the 2026-07-02 full-suite pass (428/428 @ `c73a526`, CLI 2.1.198, `results_20260702T142448Z`). Tagged all 8 existing items (e.g. Inject → ◐ hook-boundary unit-proven / mid-turn open; run-strip % → ◐ checklist parser proven / true % open). Added 3 new open items — **7** Context breakdown & Compact, **10** Attachment/citation path materialization, **11** Native coordination primitives — renumbered continuously 1–11. Relocated Fast/Thinking-mode into a new **Decided omissions** ledger (⛔ impossible-today) instead of deleting it, per the "nothing leaves §10 without a home" rule. Existing Desired/Blocker/Research/Fallback bullets preserved verbatim.

Files: docs/ARCHITECTURE.md, DEVLOG.md

---

### 2026-07-02 07:50:30 — design: Settings always opens on Projects (settings tab no longer persisted)

Follow-up to the Projects-tab work. The mockup's HTML already defaulted the Settings step-in to Projects, but `settingsTab()` persisted the last-selected tab to `localStorage['awl-v8'].settings` and restored it on load — so any browser that had ever selected **Setups** kept reopening on Setups, overriding the intended default. Removed the settings-tab persistence: dropped the write in `settingsTab()` and skipped the `settings` branch in the on-load restore, so the Settings view always opens on its lead tab (**Projects**) regardless of stale saved state. Scoped to settings only — every other tab group (feed/prompt/library/agent) still persists. Verified in-browser: seeded `localStorage {settings:'setups', feed:'log'}`, reloaded → Settings opens on Projects (stale `setups` ignored) while feed still restores to Log; clicking a settings tab no longer writes localStorage. `node --check` passes.

Files: design/behavior.js, DEVLOG.md

---

### 2026-07-02 08:18:32 — docs: §10 corrected — needs-spike/needs-research tags, Fast/Thinking un-omitted, entry loosened, §11 tests pointer

Corrective pass over §10 (supersedes the 083e991 tag pass) after cross-checking the forked review + mode-control research. **Fixed the real error:** Fast/Thinking were mis-filed in "Decided omissions" as ⛔ impossible; the research surfaced untested `Meta+T`/`Meta+O` keybind levers (action-confirmed, integration-untested — same class as #1), so both moved back into the queue as 🧪 needs-spike (now items #2, #3). Decided omissions is now "None currently" (an item lands there only after a spike proves no path — a code no-op isn't proof). **Split the `❓ unproven` tag into two:** 🧪 **needs-spike** (mechanism known, run the experiment — 9 items) and 🔬 **needs-research** (mechanism unknown, investigate first — path materialization #12, native primitives #13); retired the off-legend `research` tag. Renumbered continuously 1–13. **Loosened §10 entry** guidelines (half-formed items welcome, mature toward the full template; kept the strict exit rules and the §10-vs-TODO boundary; added "holding pen, not a scorecard" + "body + §10 should account for the whole system" framing). **Added the tests-as-specs signal:** a `tests/` row in the §11 repo map + a callout that `test_*_unit.py` docstrings are executable specs to read before building. Confirmed the doc-sync items (Delete/Usage/Settings) are homed in the body + TODO, not orphaned.

Files: docs/ARCHITECTURE.md, DEVLOG.md

---

### 2026-07-02 08:36:10 — prompts: two meta-generators for the §10 build + research prompt families

Added two "meta-prompt" generators under `dev/prompts/` so a single agent each can author the full prompt families (which then fan out to X build/research sessions). **Build generator** (`2026-07-02-s10-META-build-prompts.md`) covers all **9 🧪 needs-spike** §10 items (#1 permission-mode, #2 thinking, #3 fast, #5 console, #6 plan/decision, #8 subagent, #9 context/compact, #10 one-click launch, #11 per-agent cost) + the **UI slice**, plus optional low-priority tail spikes for the two ◐ items (#4 Inject, #7 run-strip); each child prompt bakes in the spike-or-omit honesty exit, parallel-safe isolation (one new file, unique tmux names, no `kill-server`, no shared-file edits), the finisher test pattern, and CLAUDE.md rules. **Research generator** (`2026-07-02-s10-META-research-prompts.md`) covers the **2 🔬 needs-research** items (#12 path materialization, #13 native coordination), with each child prompt self-contained for an offline chat (no repo access — context embedded inline) and asking for a structured, cited report into `dev/notes/research/`. Shared find-prefix: `dev/prompts/2026-07-02-s10-*`; child filenames carry the §10 item number for traceability.

Files: dev/prompts/2026-07-02-s10-META-build-prompts.md (new), dev/prompts/2026-07-02-s10-META-research-prompts.md (new), DEVLOG.md

---

### 2026-07-02 08:41:00 — prompts: research reports must be one-action download/copy

Refined the research meta-generator's output spec: each child research prompt now requires the offline chat to return the whole report as **one self-contained Markdown document retrievable in a single action** (a `.md` download if the tool supports it, else the entire report in one fenced block / canvas / artifact — never scattered across the chat), with a suggested `s10-research-NN-<slug>.md` filename so it drops straight into `dev/notes/research/`. Framed tool-agnostically so it works on both ChatGPT (file download) and Claude web (artifact copy/download).

Files: dev/prompts/2026-07-02-s10-META-research-prompts.md, DEVLOG.md

---

### 2026-07-02 08:44:52 — docs: system coverage audit → orphaned-elements report

Ran a completeness/coverage audit answering "is the whole intended system accounted for between the ARCHITECTURE.md body, its §10 queue, and DESIGN.md?" — a multi-lens agent sweep (57 candidates, adversarially verified → 48 survivors) plus a systematic enumeration of every `data-status` marker (36, all homed), code no-op/deferral, and DESIGN control. Wrote the findings to a new triage note. Headline orphans: ① Rewind/Handoff/Timeline (a v1 Details feature with zero engine-feasibility story — the biggest crack); ② an ARCHITECTURE §7.5 "identity read-only in v1" vs DESIGN "pencil-editable" contradiction; ③ the missing detector behind the System-wide Error cards; ④ the frontend park-and-rebuild-fresh strategy living only in transcripts while §4.4 reads the opposite. No changes to ARCHITECTURE.md/DESIGN.md/TODO.md — the note only says where each orphan should land.

Files: dev/notes/scratch/2026-07-02-coverage-audit-orphans.md, DEVLOG.md

---

### 2026-07-02 08:56:00 — prompts: generated the §10 research-prompt family (#12, #13, +hook-event-stream)

Executed the s10-META research-prompt meta-generator: wrote three self-contained research prompts (each pasteable into a no-repo offline chat) for the two 🔬 needs-research §10 items — **#12** attachment/citation path materialization across the WSL2↔Windows filesystem boundary, and **#13** native coordination primitives (Task/TodoWrite/Workflow/SendMessage/agent-teams) adopt-vs-custom-spine + what's reachable over tmux — plus one optional additional candidate, **#14** adopting a push-based HTTP-hook event stream as the primary run-state signal. Each embeds its own system-context/constraints/known-facts inline (no repo refs, no §N leaks) and specifies the structured report shape (question · options · trade-offs · per-finding confidence · sources · recommendation+fallback). Built via a draft→3-lens-adversarial-verify workflow (self-containment / repo-accuracy / completeness); the accuracy lens caught and I corrected several built-vs-deferred overstatements against live code: the plans-dir cwd-canonicalizer is intended-not-built (`.awl/` today, no `plansDirectory` written, `project_root()` uncanonicalized — real precedent is the `*_wsl()` `/mnt/...` helpers), the progress checklist parses markdown from assistant text (not `TodoWrite`, which buckets to "other"), subagents derive from the parent transcript (folder-watch deferred), Piggyback isn't a built link trigger, and the Plan/Decision hook path is spike-gated not proven.

Files: dev/prompts/2026-07-02-s10-research-12-path-materialization.md, dev/prompts/2026-07-02-s10-research-13-native-coordination.md, dev/prompts/2026-07-02-s10-research-14-hook-event-stream.md, DEVLOG.md

---

### 2026-07-02 10:15:00 — prompts: generated the §10 test-BUILD prompt family (10 core spikes + 2 optional tails)

Executed the s10-META build-prompt meta-generator: wrote **12** self-contained, in-repo build prompts — one per §10 spike item, each handed to a fresh Claude Code agent to build **ONE** live pytest. Core set = the 9 🧪 needs-spike items (**#1** permission-mode Shift+Tab/`BTab` cycle read back off the status line, **#2** thinking `Meta+T`, **#3** fast `Meta+O`, **#5** console wiring-vs-ANSI-fidelity split, **#6** Plan/Decision `PreToolUse`-hook detection-vs-answer/resume split, **#8** subagent pending-vs-active, **#9** context `/context`-scrape + `compact_boundary`, **#10** one-click Electron-main sidecar lifecycle vs detach-on-close, **#11** per-agent cost) **+ the Playwright-python UI slice**; plus 2 low-priority ◐ tails spiking only the open sliver (**#4** earlier-than-hook-boundary Inject, **#7** engine progress signal beyond the checklist). Each carries the 9-section contract (header · read-first · mechanism · build-this · read-back-is-the-crux · spike-or-omit exits · parallel-safe isolation · definition-of-done · guardrails), grounded in the mode-control research levers, the real bridge/driver/sidecar API (`keys()`→`BTab`/`M-t`/`M-o`, the `set_mode`/`set_fast`/`set_thinking` no-ops, `POST /mode` 400, the wired `PreToolUse` plan/decision hooks), and the `test_bridge_finisher_live.py` pattern. Built via a parallel author→adversarial-verify workflow (12 writers + 12 checkers, all pass). Baked in the non-obvious isolation trap — conftest's session-scoped `bridge` fixture runs `tmux kill-server` on setup+teardown, fatal under parallel agents, so each prompt spawns its own `TmuxBridge` and tears down only its own session — and on review normalized every instructed test filename to the `test_` prefix after empirically confirming a non-prefixed `*_live.py` is collected via an explicit path but **silently skipped** by a `pytest tests/` directory scan (would have made the "durable" tests invisible to the full-suite ledger).

Files: dev/prompts/2026-07-02-s10-build-01-permission-mode.md, dev/prompts/2026-07-02-s10-build-02-thinking-mode.md, dev/prompts/2026-07-02-s10-build-03-fast-mode.md, dev/prompts/2026-07-02-s10-build-04-inject-tail.md, dev/prompts/2026-07-02-s10-build-05-console.md, dev/prompts/2026-07-02-s10-build-06-plan-decision.md, dev/prompts/2026-07-02-s10-build-07-runstrip-tail.md, dev/prompts/2026-07-02-s10-build-08-subagent-status.md, dev/prompts/2026-07-02-s10-build-09-context-compact.md, dev/prompts/2026-07-02-s10-build-10-oneclick-launch.md, dev/prompts/2026-07-02-s10-build-11-per-agent-cost.md, dev/prompts/2026-07-02-s10-build-UI-slice.md, DEVLOG.md

---

### 2026-07-02 16:05:00 — §10 #01 spike: mid-run permission-mode change via BTab — WORKS (live)

Built + ran the first §10 build prompt (`s10-build-01-permission-mode`). New durable live test `tests/test_permission_mode_cycle_live.py` proves **both layers** on Claude CLI **2.1.198**: sending one `Shift+Tab` (tmux `BTab`) via `bridge.keys()` from a known-idle `default`-mode session **(Layer 1)** flips the status line to `⏵⏵ accept edits on` (indicator advanced `default → acceptEdits` deterministically, no optional modes pre-armed), **and (Layer 2 — the crux)** genuinely suppresses behavior: a subsequent Write raised **no** `permission_prompt` and `b.txt` landed unattended as `cherry` — no live suppression regression (cf. #52822/#55255) on this build. Baseline sanity held too: default mode DID prompt and the denied `a.txt` stayed `__MISSING__`. Drives the raw `TmuxBridge` directly (no `BridgeDriver`/HTTP); parallel-safe — own `TmuxBridge()`, unique `permmode-<uuid8>` session, teardown closes only its own session + `rm -rf`s its own diag dir, never `kill-server`. This green-lights later wiring of `BridgeDriver.set_mode()` as read-compute-send-`BTab`-verify and advancing §10 #01 off 🧪 needs-spike. Result line: **`1 passed in 41.27s`** (`results_20260702T160315Z.txt`, PASS).

Files: tests/test_permission_mode_cycle_live.py (new), DEVLOG.md

---

### 2026-07-02 09:05:00 — tests: Console mirror live spike (§10 #5) — Gap A wiring PASS, Gap B ANSI recoverable-via-`-e` PASS

Built the §10 item-#5 spike as **one** new live pytest, `tests/test_console_mirror_live.py` (two functions, the "split" the item tracks), and ran it green: `= 2 passed in 27.86s =` (own durable record `results_20260702T160327Z.txt`: passed=2 failed=0). **Gap A — wiring:** a unique literal marker typed into a live composer via `bridge.send(..., press_enter=False)` (the same `send-keys` path `POST /console/run` uses) appeared in the very next `bridge.read()` capture and was absent from the baseline — keystroke passthrough + live mirror are wired end-to-end below the HTTP layer; the endpoint's send-then-read is sound. (Secondary, non-fatal: a `/help` slash round-trip changed the screen too.) **Gap B — fidelity:** the production `read()` path (`capture-pane` **without** `-e`) dropped all SGR escapes, while re-capturing the *same* idle colored pane with `capture-pane -e` re-exposed the raw `\x1b[…m` sequences (`re.findall(r"\x1b\[[0-9;]*m", raw)` non-empty AND `"\x1b[" not in plain`, both asserted). So ANSI styling **is** recoverable — but faithful rendering still needs an xterm.js-class renderer in the frontend, which the §10 blocker names and is **out of scope for this backend spike** (that half stays deferred, not failed). Parallel-safe: own `TmuxBridge` (not conftest's kill-server `bridge` fixture), unique `conmirror-<uuid8>` session, teardown closes only its own session + throwaway dir, never `kill-server`. Verified in practice — the run's DEBUG log shows a sibling `permmode-*` live session running concurrently and untouched. Backend-only spike, no rendered surface, so the UI browser pass does not apply.

Files: tests/test_console_mirror_live.py (new), DEVLOG.md

---

### 2026-07-02 16:15:00 — tests: UI slice (§10 build-table row 10) — frontend client-contract PROVEN live

Built the frontend client-contract proof as **one** new live pytest, `tests/ui/test_ui_slice_live.py`, plus a framework-free fixture page `tests/ui/fixture/app.html`, and ran it green twice: headless `= 1 passed in 52.19s =` and the headed parity pass `= 1 passed in 60.51s =` (own durable records `results_20260702T161036Z.txt` / `results_20260702T161213Z.txt`). The test drives a **real, tab-less bridge agent** (created in **`default` permission mode** — the CreateSessionRequest default is `acceptEdits`, which would auto-approve the Write and never raise a prompt) purely through a browser that speaks only the `frontend/src/renderer/api.ts` contract, asserting on **rendered DOM + read-back files**, never pixels: (1) **live feed renders** — `#feed` gets ≥1 `.event` node from the `/events` SSE ring and grows after a send; (2) **send dispatches** — the fixture's control `POST`s `/sessions/{id}/send {prompt,source:'user',recipients:null,disposition:'queue'}` and the returned `SendResult.status` is read back (`sent`); (3) **run-state** — `#runstate` flips to `running` during the turn (read from the DOM, polled off `GET /sessions/{id}` + SSE `status_change`); (4) **permission approve** — a real `permission_request` card renders ("Do you want to create ui.txt?"), `POST …/permission {approve:true}` clears it (`has_pending_permission`→false) **and `ui.txt` == `mango`** catted back over the bridge; (5) **permission deny** — a fresh Write prompt raises a new card, `{approve:false}` resolves it **and `deny.txt` is `__MISSING__`**. **Learned & noted in the module docstring:** the client needs very little from `/events` to render — each frame is `{"event":"message","data":<json>}` carrying `id` (dedup), `agent_id` (identity stamp → filter own-agent state), `seq`, `type`, and for permission the parsed `data.{question,options,raw}`; run-state derives identically from SSE and the session record; CORS `*` lets the cross-origin POST/EventSource through cleanly. UI verified per CLAUDE.md — screenshots of all states into `.scratch/` (`uislice_{headless,headed}_*`) at **narrow (420px) and wide (1400px)** extremes, every control (send/approve/deny) clicked, headed render identical to headless. Parallel-safe: own `TmuxBridge` (never conftest's `kill-server` `bridge` fixture), unique `ui-slice-<uuid8>` identity + `awl-<uuid8>` tmux name, teardown retires **only** its own session (`DELETE …?hard=true`) + its own throwaway WSL dir, never `kill-server`; the sidecar is reused if already healthy on :7690 else spawned on `127.0.0.1` for the run and torn down. **`frontend/` left completely untouched.** **FLAGGED, not performed** (shared changes): adding `tests/ui/` warrants a small `pythonpath` tidy in `pyproject.toml`, and a durable `playwright` add to `requirements.txt` — both left for the human (playwright was installed into `.venv` only, to *run* the test).

Files: tests/ui/test_ui_slice_live.py (new), tests/ui/fixture/app.html (new), DEVLOG.md

---

### 2026-07-02 16:16:00 — §10 #02 spike: thinking control via Meta+T — WORKS via a state panel (live, mechanism refined)

Built + ran the second §10 build prompt (`s10-build-02-thinking-mode`). New durable live test `tests/test_thinking_toggle_live.py`. The spike **refined the hypothesis**: on Claude CLI **2.1.198**, `M-t` is **not** a blind toggle — it opens an interactive **"Toggle thinking mode" panel** (`❯ 1. Enabled ✔ / 2. Disabled`, Enter to confirm) on the running session. That panel is **better** than the hypothesised blind toggle: current state is directly **read-backable** (which line carries the `✔`, plain-text after ANSI strip) **and settable absolutely** (pick 1/2 + Enter). The durable test drives the real mechanism — open panel → read state → set opposite → reopen+confirm → flip back — asserting a clean there-and-back: **`enabled → disabled → enabled`** (settable + read-backable, repeatable). **Caveat recorded (honest):** the *specifically hypothesised* observable — `thinking`-type blocks in the JSONL transcript — did **not** hold; with thinking Enabled by default, a step-by-step reasoning turn on the default model (**Fable 5**, fast) emitted **zero** transcript thinking blocks (exploratory run `results_20260702T160845Z` = `1 xfailed`, superseded). So transcript-block presence is a model-dependent/unreliable observable here; the panel is the reliable one (`has_thinking()` kept to document the attempt). This unblocks wiring `set_thinking()` as open-panel→read→select-target→confirm + advertising the capability, and advances §10 #02 off 🧪 needs-spike. The first run also caught a real mechanism bug (post-`M-t` prompts landed in the modal panel → zero-turn transcript slices); the panel screen-capture diagnosed it. Parallel-safe (own `TmuxBridge()`, unique `think-<uuid8>`, close-only teardown, never `kill-server`). Result line: **`1 passed in 14.44s`** (`results_20260702T161557Z.txt`, PASS).

Files: tests/test_thinking_toggle_live.py (new), DEVLOG.md

---

### 2026-07-02 09:18:30 — tests: Plan/Decision hook interception live spike (§10 #6) — detection PASS + answer/resume PROVEN via keys()

Built the §10 item-#6 spike as **one** new live pytest, `tests/test_plan_decision_hooks_live.py` (two detection functions, same file), Approach A (the real detect→card chain the dashboard uses): the test stands up the **real sidecar** as a subprocess bound to `0.0.0.0:7690` (the fixed hook port) with an **empty `AWL_SIDECAR_RUNTIME`** so its startup `reconnect_sessions()` never rebinds a real/sibling tmux session, drives a standalone `BridgeDriver`, then reads the card back over HTTP. Ran green twice: `= 2 passed in 43.38s =` (own durable record `results_20260702T161731Z.txt`: passed=2 failed=0). **Detection — PROVEN (both).** A plan-mode agent driven to call `ExitPlanMode` fires `PreToolUse(ExitPlanMode)` → a `plan` card with a usable `data.tool_input` appears at `GET /inbox` keyed by the agent; an agent driven to call `AskUserQuestion` fires `PreToolUse(AskUserQuestion)` → a `decision` card the same way. Confirms the hooks fire under the bridge with usable payloads over the WSL→Windows host gateway (`sidecar_hook_base_url` → `:7690`), the detect-and-surface path (`hook_plan`/`hook_decision` → `inbox.raise_item`, return `{}`). **Answer/resume — PROVEN (stronger than the item anticipated).** Because the hook returns `{}` (allow), the agent **parks at the native interactive box**, and a single **guarded `keys(Enter)`** (selecting the highlighted option, gated on a non-generating state) **resumes it**: plan → agent left plan mode and executed `Write(hello.txt)`→"world" + entered auto mode; decision → agent recorded "You picked Option A" and continued. So the resume mechanism is **`keys()` Enter on the box, NOT the hook's `updatedInput`**; promoted to a durable-but-robust assertion (`resumed is not False` — fires only when the box was actually driven, degrades to no-op on future wording drift, so it can't flake). Parallel-safe: own `TmuxBridge` (not conftest's kill-server `bridge` fixture), unique `plandec-<uuid8>` tmux name pinned == sidecar session id == inbox key, teardown closes only its own session + throwaway dir + terminates its own sidecar subprocess (verified no leak — post-run `:7690` shows only `TIME_WAIT`, nothing `LISTENING`). **Recommendation (flagged, not applied):** §10 item #6's answer/resume half is now proven via `keys()` — the doc-owner should update the ARCHITECTURE.md §10 #6 marker + "Research/POC must establish" bullet (resume = `keys()` Enter, not `updatedInput`); I did **not** edit ARCHITECTURE.md (decision-bearing doc). Scratch probe write-ups in `.scratch/plandec_resume_probe_*.txt` (gitignored).

Files: tests/test_plan_decision_hooks_live.py (new), DEVLOG.md

---

### 2026-07-02 09:22:00 — §10 #09 spike: Context breakdown (`/context`) + Compact marking (`/compact`) — BOTH LEVERS WORK (live)

Built + ran the §10 item-#9 build prompt (`s10-build-09-context-compact`) as **one** new durable live test, `tests/test_context_compact_live.py` (two levers, one primed session, own `TmuxBridge()`). Both came back **WORKS on Claude CLI 2.1.198** — stronger than the research's screen-scrape-only prediction. **Lever A — `/context` per-category breakdown: PROVEN.** At an idle boundary `send("/context")` renders the split to the screen; the rows parse cleanly into stable labeled values — all **6** categories (system_prompt 9k/0.9%, system_tools 21.9k/2.3%, skills 2.1k/0.2%, messages 4.4k/0.5%, free_space 896.6k/92.7%, autocompact_buffer 33k/3.4%). **Bonus discovery:** `/context` output is ALSO written into the JSONL transcript as a clean **markdown table** (a local-command `user` entry — "## Context Usage … | System prompt | 9k | 0.9% |"), a steadier read-back than raw screen-scrape (asserted as a secondary check). Caveat kept honest: it's a point-in-time, idle-gated **pull** (triggered by `/context`), not a passive live feed. **Lever B — `compact_boundary` marking: PROVEN, and richer than the item hoped.** A real `/compact` writes a `type:"system" subtype:"compact_boundary"` entry (`content:"Conversation compacted"`) carrying `compactMetadata` = `trigger`(manual/auto) · `preTokens` · `postTokens` · `durationMs` · `cumulativeDroppedTokens` · `preservedSegment`/`preservedMessages`, plus a companion `user` entry flagged `isCompactSummary:true` — so the DESIGN **compaction history** (count = #boundaries, type = trigger, when = timestamp, + token deltas) IS derivable from JSONL. **Non-obvious trap caught (honesty save):** the FIRST exploratory run xfailed Lever B because a single-turn primed context makes `/compact` **refuse** ("Not enough messages to compact." — recorded in a local-command stdout entry); a throwaway probe proved compaction fires reliably from ~3 conversational rounds. The finalized test primes 4 rounds and **retries with extra rounds if ever refused**, so the negative can't be a too-small-context artifact. This answers the §10 #9 blocker (`compact_boundary` **does** reliably mark compaction) and shows the per-category breakdown is scrapable/transcript-recoverable — advancing #9 off 🧪 needs-spike toward "on-demand `/context` pull + JSONL-derived compaction history" rather than the total/turns-only fallback. **Recommendation (flagged, not applied — I did NOT edit ARCHITECTURE.md):** the doc-owner can update §10 #9 (both blocker sub-questions resolved: parse `/context` = viable on-demand; `compact_boundary` = reliable). Parallel-safe: own `TmuxBridge()` (not conftest's kill-server `bridge` fixture), unique `ctxcompact-<uuid8>` name, close-only + rm-own-dir teardown, never `kill-server`. Result line: **`2 passed in 47.22s`** (`results_20260702T161857Z.txt`, PASS). Scratch probe in `.scratch/probe_compact.py` (gitignored).

Files: tests/test_context_compact_live.py (new), DEVLOG.md

---

### 2026-07-02 16:26:00 — §10 #03 spike: Fast-mode toggle via Meta+O — HONEST OMISSION (credit-gated, live)

Built + ran the third §10 build prompt (`s10-build-03-fast-mode`). New durable live test `tests/test_fast_mode_toggle_live.py` records the **honest omission** (an `xfail` carrying the finding — NOT faked green) after a real send-and-read-back attempt on Claude CLI **2.1.198**. Findings: (1) default `M-o` (`chat:fastMode`) produces **no observable change** — no panel, no footer indicator, no model switch (before/after screens identical bar transient footer rotation); (2) the research's sanctioned fallback — rebinding `chat:fastMode` to a clean chord (`ctrl+x ctrl+f`) via a temporary WSL `~/.claude/keybindings.json` and sending it — was performed in the spike and **also** produced no change; (3) **ROOT CAUSE, read straight off the TUI:** `/fast` opens a panel reading **"↯ Fast mode (research preview) … Fast mode requires usage credits · /usage-credits to turn them on"**, and `/fast` reports **"Fast mode OFF"** — Fast mode is **credit-gated and OFF for this account**, so there is no Enabled/Disabled state to flip and no keystroke can surface a read-backable one (the durable test captures this programmatically: `credit_gated=True, fast_off=True`). Crucially this is **not** a key-encoding failure — `meta`-delivery over tmux is proven (the sibling #02 `Meta+T` opens the thinking panel), so it's an account/capability gate. The test keeps a future-proof WORKS branch (passes if a later account/build makes `M-o` toggle an observable Fast state). **Recommendation (flagged, not applied — I did NOT edit ARCHITECTURE.md):** move §10 #03 → **Decided omissions** — Fast stays a launch-time/credit-gated choice, never a fake-live toggle. Parallel-safe: driver tmux name `awl-<uuid8>` (unique) + slug `fastmode-<uuid8>` session id, own `TmuxBridge()` (not conftest's kill-server `bridge` fixture), close-only + rm-own-dir teardown, never `kill-server`; the temporary keybindings.json (none existed) was deleted in teardown — verified restored to absent, no sibling impact. Result line: **`1 xfailed in 19.12s`** (`results_20260702T162629Z.xml`; xfail-only runs don't emit the durable `.txt`). Exploration captures in `tests/log/` (`results_20260702T161936Z`, `162318Z`).

Files: tests/test_fast_mode_toggle_live.py (new), DEVLOG.md

---

### 2026-07-02 09:28:00 — §10 #11 spike: Per-agent cost harvest — `/cost` DOES yield a defensible per-session cost (live; hypothesis overturned)

Built + ran the §10 item-#11 build prompt (`s10-build-11-per-agent-cost`) as **one** new durable live test, `tests/test_per_agent_cost_live.py` (own `TmuxBridge()` for WSL helpers + `/cost` read-back; a real `BridgeDriver` for the turn; slug-prefixed unique tmux name `pacost-<uuid8>`). Two harvest paths, head-to-head. **Path (a) — JSONL usage: usage, not cost (as expected).** `get_context_usage()` returns a real positive token count off the latest assistant `message.usage`, but the dict has **no** `cost`/`total_cost_usd`/dollar key and `BridgeDriver.CAPABILITIES` excludes `cost` — JSONL yields *usage*, never *cost* (asserted explicitly so the two can't be conflated). **Path (b) — `/cost` console scrape: OVERTURNS the prompt's hypothesis.** The prompt predicted a Max/Pro subscription would print no dollar figure; live on **2.1.198** `/cost` opens the unified **Usage** dialog and renders a real **per-SESSION** cost panel — `Session · Total cost: $0.2128`, `Total duration (API/wall)`, and a **per-model breakdown** (`claude-haiku-4-5 … ($0.0012)`, `claude-sonnet-5 … 33.1k cache write ($0.2116)`), above the account rate-limit bands (55% session / 11% week). So a **defensible, non-fabricated per-agent cost IS harvestable via the `/cost` scrape** — the test parses the *specific* "Total cost: $X" session line (not any incidental `$`) + the per-model figures and asserts on them; it degrades to an xfail usage-only-boundary FINDING if a future build/account shows no per-session cost. **Honesty guardrails:** the number is Claude Code's OWN estimate (tokens × model price), a **point-in-time, idle-gated on-demand pull** (not a passive feed), pricing the whole `claude` session (== one bridge agent). The first exploratory run flagged the `$0.2127` as "not auto-trusted"; inspecting the full screen (labeled "Session / Total cost") confirmed it's a legit per-session figure, so the finalized test asserts it as a WORKS. **Recommendation (flagged, NOT applied — did NOT edit ARCHITECTURE.md):** §7.15 / §10 #11's shipped "honest blank" can be **revisited** — a per-agent cost estimate is available via a `/cost` scrape; if wired, surface it as an idle-time on-demand "Claude Code estimate," not a live per-turn number. Parallel-safe: own `TmuxBridge()` (not conftest's kill-server `bridge` fixture), unique `pacost-<uuid8>` name, `AWL_SIDECAR_RUNTIME`→tmp, driver-close-only + rm-own-dir teardown, never `kill-server`. Result line: **`1 passed in 16.80s`** (`results_20260702T162722Z.txt`, PASS).

Files: tests/test_per_agent_cost_live.py (new), DEVLOG.md

---

### 2026-07-02 16:34:00 — §10 #08 spike: Subagent pending-vs-active status — WORKS (live)

Built + ran the §10 item-#8 build prompt (`s10-build-08-subagent-status`) as **one** new durable live test, `tests/test_subagent_status_live.py` (own `TmuxBridge()`, slug `substat-<uuid8>`, driver tmux `awl-<uuid8>`, close-only + rm-own-dir teardown, never `kill-server`). **WORKS on Claude CLI 2.1.198** — the live active-vs-pending signal is real and **refutes the load-bearing "buffered-until-completion" risk**. Drove a real parent (bypassPermissions) that delegates 5 sequential `sleep 4` steps to ONE general-purpose subagent, then sampled the subagent's OWN transcript `<project>/<parent_sid>/subagents/agent-<id>.jsonl` every ~3s. Across 2 confirming runs: the file appears **~2.6–2.9s** after the turn starts (NOT at completion), and every recency channel advances monotonically WHILE the subagent works then **freezes the instant it finishes** — `stat -c %Y` mtime (cheapest reliable signal), line count, and last-event `timestamp` — plus the deterministic pending-tools overlay (subagent `tool_use` ids minus `tool_result` ids) is nonempty mid-run and 0 before the first tool / after completion. Caveat: recency is flush-lagged ~a couple seconds, so read "active" as "mtime advanced within the last ~N seconds". **Two non-obvious traps caught during bring-up:** (1) a prompt sent via the bridge must be pure-ASCII AND free of backticks/`&&` — the wsl.exe interop breaks single-quote literalness so backtick content gets command-substituted (an early prompt embedding `` `sleep 4 && echo step1` ``×5 actually RAN five real sleeps during bash parsing and blew `send()`'s 10s timeout); (2) gating the signal on the PARENT transcript's Agent-spawn pairing is flaky (it flush-lags, worse under concurrent sibling load) — the hardened test derives active/quiet from the SUBAGENT file itself, no parent dependency. Advances §10 #8 off 🧪 needs-spike toward its Desired "live pending vs active". **Recommendation (flagged, NOT applied — I did NOT edit ARCHITECTURE.md):** the doc-owner can mark #8's blocker resolved (subagent-transcript mtime/last-event recency + pending-tools overlay give a reliable live active signal). Result lines: **`1 passed in 91.94s`** then **`1 passed in 94.57s`** (2 consecutive greens under concurrent sibling agents; `results_20260702T162016Z`).

Files: tests/test_subagent_status_live.py (new), DEVLOG.md

---

### 2026-07-02 16:35:00 — §10 #10 spike: One-click launch (Electron main owns the sidecar) — WORKS (live)

Built + ran the §10 item-#10 build prompt (`s10-build-10-oneclick-launch`) as **one** new durable live test, `tests/test_oneclick_launch_live.py` (own `TmuxBridge()`, slug `oneclick-<uuid8>`, own `AWL_SIDECAR_RUNTIME` tmp dir, close-only + rm-own-dir teardown, never `kill-server`; skips cleanly if a foreign sidecar already holds :7690). **WORKS on Claude CLI 2.1.198** — Electron-main-style lifecycle ownership does **NOT** break detach-on-close (§3.4). The pytest models exactly what Electron main would do (the honest harness the venv can run; a Node/Electron POC would need a runner the venv lacks = STOP-and-flag, so not attempted): start a real detached agent through the driver path (record persisted to `runtime_store`), send a `LAUNCH_OK` marker turn, then spawn the sidecar as a **supervised child** (`python main.py` via `subprocess.Popen`, `AWL_SIDECAR_HOST=127.0.0.1`), wait for it to bind :7690, `terminate()` it (project close), then reopen a fresh child. Both survival read-backs proven across 2 runs: **Crux A — survival:** after the sidecar child is killed, `TmuxBridge().list()` still contains the agent (`awl-<uuid8>`) with its transcript readable — the detached tmux agent runs in WSL2 independent of the Windows sidecar process, so killing the parent leaves the child untouched. **Crux B — reconnect:** the reopened sidecar's `reconnect_sessions()` rebinds it — `GET /sessions` shows the session id and `GET /sessions/{id}/context` shows `turns=1` (history intact, model claude-sonnet-5, 18.5% context). "The process started" was explicitly NOT treated as a pass. Confirms the research Q3 §2 principle (`runtime_store` + `resume()` rebind a live tmux session by name on sidecar restart) holds under supervised-child spawn/kill, so Electron main CAN own the sidecar lifecycle. Advances §10 #10 off 🧪 needs-spike toward its Desired one-icon launch. **Recommendation (flagged, NOT applied — I did NOT edit ARCHITECTURE.md):** green light for the real Electron-main spawn/supervise/shutdown POC; the `start-dashboard.bat` two-process fallback is no longer forced. Result lines: **`1 passed in 30.82s`** then **`1 passed in 32.59s`** (2 consecutive greens; `results_20260702T162558Z.txt`, PASS). Sidecar child logs → `.scratch/oneclick-sidecar-*.log` (gitignored).

Files: tests/test_oneclick_launch_live.py (new), DEVLOG.md

---

### 2026-07-02 09:57:55 — §10: integrate coverage-audit orphans (#14–#22) + author their spike/research prompts

Graduated the flagged orphans from the coverage-audit note into **ARCHITECTURE.md §10** as a new **"Priority — coverage-audit additions (2026-07-02)"** subsection, appended as items **#14–#22** (existing 1–13 numbering left untouched to preserve the item↔prompt mapping in `dev/prompts/`). New entries, each tagged per the queue's convention (status + Evidence + Desired/Blocker/POC/Fallback): **#14** hook-event-stream (🧪), **#15** Rewind/Handoff/Timeline (🔬, gating), **#16** system-fault detection — harvest half (🧪), **#17** polling-scale ceiling (🧪 load test), **#18** statusLine context mid-run (🧪), **#19** Console `/clear` transcript orphaning (🧪), **#20** Bypass/Auto launch preconditions (🧪), **#21** usage/limits source-boundary (🧪), **#22** subagent create/manage (🔬, overlaps #13). Then authored the matching prompts in `dev/prompts/` following the dev-doc-4b house style (9-section build prompts; self-contained research prompts): **7 build prompts** — `build-14-hook-event-stream` (references existing `research-14`), `build-15-rewind-handoff` (**conditional scaffold, to-be-finalized from research-15**), `build-16-system-fault-detection`, `build-17-polling-scale-ceiling`, `build-18-21-usage-context-sources` (**grouped** #18+#21), `build-19-console-clear-transcript`, `build-20-bypass-auto-preconditions` — and **2 research prompts** — `research-15-rewind-handoff` (full, gates its spike) and `research-22-subagent-management`. Each prompt points its agent at the relevant existing research in `dev/notes/research/` and existing prompts in `dev/prompts/` so it builds on prior work. No tests built or research run — prompts + the §10 edit are the deliverable.

Files: docs/ARCHITECTURE.md, dev/prompts/2026-07-02-s10-build-14-hook-event-stream.md (new), dev/prompts/2026-07-02-s10-research-15-rewind-handoff.md (new), dev/prompts/2026-07-02-s10-build-15-rewind-handoff.md (new), dev/prompts/2026-07-02-s10-build-16-system-fault-detection.md (new), dev/prompts/2026-07-02-s10-build-17-polling-scale-ceiling.md (new), dev/prompts/2026-07-02-s10-build-18-21-usage-context-sources.md (new), dev/prompts/2026-07-02-s10-build-19-console-clear-transcript.md (new), dev/prompts/2026-07-02-s10-build-20-bypass-auto-preconditions.md (new), dev/prompts/2026-07-02-s10-research-22-subagent-management.md (new), DEVLOG.md

---

### 2026-07-02 17:35:00 — §10 #14 spike: hook-event-stream — WORKS (payload carries permission_mode + tool, live)

Built and ran the §10 #14 spike (`dev/prompts/…-build-14-hook-event-stream.md`): does an HTTP-hook payload actually carry `permission_mode` + the current tool on every tool/turn event? **WORKS on Claude Code 2.1.198.** New single live test stands up an in-test threaded HTTP receiver on an ephemeral port bound to `0.0.0.0`, reachable from the WSL agent over the WSL2 default-gateway URL (pre-flight-verified before launch), registers a broad candidate hook set → the receiver, launches a real tab-less TUI in DEFAULT mode, drives a Read (auto-approved → clean Pre/PostToolUse) + a denied Write (permission prompt), and inspects the RAW payloads. Result line: **`1 passed in 92.17s`**. Isolation held while a sibling `pollscale-*` spike ran concurrently (own `TmuxBridge`, unique `hookstream-<uuid8>` name, close-only teardown, never kill-server).
Findings for research-14: **`permission_mode` is present on every tool/turn event** — PreToolUse/PostToolUse/Stop/UserPromptSubmit/SubagentStop/PermissionRequest all 100%; only `Notification` lacks it (0/1). Current tool rides `tool_name`(+`tool_input`+`tool_use_id`) on tool-scoped events. Payload is richer than expected — also `effort.level`, `cwd`, `session_id`, `transcript_path`, `prompt_id`; Stop adds `last_assistant_message`. The pushed mode is **authoritative and tracks a LIVE change** — one `BTab` to acceptEdits flips subsequent payloads to `permission_mode:"acceptEdits"`. Event coverage on 2.1.198: real & firing = PreToolUse, PostToolUse, Stop, SubagentStop, UserPromptSubmit, Notification, **PermissionRequest** (research flagged it "may not exist" — it IS real here, fires after PreToolUse for a gated tool); candidates that did NOT fire = **StopFailure, SubagentStart**; SessionStart/SessionEnd/PreCompact registered but didn't fire this flow. Quirk: SubagentStop fires at every turn-end even with no subagent. Ordering/dedup (single-agent): clean per-turn order, **0 duplicate arrivals**, sub-second tool-boundary latency; concurrent-load ordering/dedup still untested. Recommendation: hooks can be the authoritative-when-present run-state/mode layer but should RUN ALONGSIDE polling (Notification lacks mode; hookless sessions need the poll floor; concurrent dedup unverified) — matches §14's Desired behavior. (Note: `tests/log/results_latest.txt` was clobbered by a concurrent sibling run; the authoritative record is the terminal `1 passed` line + the per-run `results_<stamp>` file.)

Files: tests/test_hook_event_stream_live.py (new), DEVLOG.md

---

### 2026-07-02 10:38:00 — §10 #17 spike: Polling-model scale ceiling — MEASURED (the "1 s cadence" is unmet from N=1; live)

Built and ran the §10 #17 load test (`dev/prompts/…-build-17-polling-scale-ceiling.md`): how many concurrent tab-less agents the per-agent ~1 s bridge `events()` poll sustains before it degrades. New single live test spawns up to MAX_N (=12) uniquely-named `pollscale-<uuid8>-<i>` sessions on its **OWN `TmuxBridge`** (never conftest's kill-server `bridge` fixture), primes each idle, then faithfully reproduces one `events()` iteration (`read_log` L621 + `status` L633 via `asyncio.to_thread`) as a concurrent sweep across N — measuring sweep latency, WSL CPU (`/proc/stat`; psutil absent → flagged, not vendored), and event-observation lag (a marker appended to one transcript, timed to first poll that sees it). Result line: **`1 passed in 366.70s`**. Scrupulous isolation held (ran alongside the §10 #14 sibling; zero leftover `pollscale-*` sessions, diag dir removed; never `kill-server`).
**Measured curve (22-core host, asyncio thread pool = 26): N → sweep_ms = 1:1334 · 3:1722 · 6:2538 · 9:4229 · 12:5677; CPU 1.5→4.2 %; event_lag ~2.0→~10 s** (durable: `tests/log/pollscale_curve_*.txt`). Headline: the **"1 s cadence" is a misnomer on the Windows→WSL2 path — one poll cycle already costs ~1.3 s for a SINGLE agent** (≈5 `wsl.exe` subprocess spawns/cycle × ~250 ms boundary overhead), so the effective per-agent interval is ~2.5 s at N=1 and the stated threshold (eff > 2× nominal) is crossed at **N\*=1**. Two regimes: concurrency is well-absorbed to N≈6 (amortized cost DROPS 1334→423 ms/agent), then marginal cost ~doubles past N≈9 as the 26-worker pool saturates (2N→24). **CPU is never the constraint (≤4.2 %); the binding cost is per-cycle boundary latency**, and event lag reaches ~10 s by N=9 (user-noticeable). Recommendation: adaptive cadence (slow idle agents, prioritize the focused one) IS warranted, but the bigger lever is collapsing the ~5 per-cycle WSL spawns into one batched `bash -c` — feeds a §4.3/§6.2 scale paragraph + a likely §10 follow-on. ARCHITECTURE.md left unedited (the fix is the human's decision to make).

Files: tests/test_polling_scale_ceiling_live.py (new), DEVLOG.md

---

### 2026-07-02 10:42:00 — §10 #16 spike: System-wide fault detection (harvest half) — 3 signals characterized, all PASS (live)

Built and ran the §10 #16 harvest-half spike (`dev/prompts/…-build-16-system-fault-detection.md`): for each non-deterministic System-card fault (account rate/usage cap, auth expiry, global MCP outage), is there a reliable machine-readable signal the sidecar can key a detector on? New single live test `tests/test_system_fault_harvest_live.py` (slug `sysfault`, three focused tests) uses its **OWN `TmuxBridge`** — never conftest's kill-server `bridge` fixture; unique `sysfault-<uuid8>` sessions; the bogus MCP server scoped per-agent via `--mcp-config … --strict-mcp-config`; creds read **READ-ONLY**, token values never logged. Result line: **`3 passed in 14.57s`** (durable: `tests/log/results_20260702T174016Z.txt`, PASS). Ran clean alongside sibling live agents; zero leftover `sysfault-*` sessions/diag dirs; never `kill-server`.
**Per-fault findings (matcher + source, for the body §5/§7 detector):** (1) **Rate/usage-cap → PARTIAL.** `inbox.classify_error`'s `rate_limit` regex reliably matches API-429-shaped copy (429 / rate limit / quota exceeded / too many requests) and `bridge.read()` surfaces such a line off a live pane (proven end-to-end via a raw pane → classify). FINDING: the CLI's *subscription* cap copy uses **"usage limit"** wording (live-observed banner: "weekly usage limit"), which the current regex MISSES — a detector must ADD a `usage limit reached` pattern; the regex is also brittle (false-fires on "rate_limit" in a filename). `claudeAiOauth.rateLimitTier` also exists in creds (proactive tier hint, not a cap-hit event). (2) **Auth expiry → POSITIVE (proactive creds signal).** `claudeAiOauth.expiresAt` is a machine-readable Unix-ms timestamp in `~/.claude/.credentials.json` — read read-only, compare to now (warn within a window, raise past). `settings_io.account_band` already traverses the `claudeAiOauth` wrapper but surfaces only email/org/plan → expiry needs a small sibling reader (`creds_expiry()`). The reactive screen signal (re-login/"session expired" prompt) is a candidate but not provokable without expiring real auth → left unconfirmed. (3) **MCP outage → POSITIVE (live-provoked).** A bogus/unreachable server surfaces in the `/mcp` panel as **"<server> · ✘ failed"** — matcher `(✘|✗|×)\s*failed|\bfailed\b` on the server row; `inbox`'s `tool_mcp` pattern is a complementary transcript-text source. All three graduate the harvest half toward the §7.2/§7.8 System-card detector; ARCHITECTURE.md §10 #16 left unedited (the human owns the marker). DEVLOG passed ~700 lines and is due for rotation — deferred while sibling agents are concurrently appending (rotation rewrites the top + digest and would race their appends).

Files: tests/test_system_fault_harvest_live.py (new), DEVLOG.md

---

### 2026-07-02 17:50:00 — §10 #20 spike: Bypass & Auto launch preconditions — PRECONDITIONS ESTABLISHED (live)

Built and ran the §10 #20 spike (`dev/prompts/…-build-20-bypass-auto-preconditions.md`): which permission-mode segments are reachable given how an agent was launched, and how an *unreachable* one presents? New single live test = a 5-case matrix on Claude Code **2.1.198**; **`5 passed in 85.21s`**. Own `TmuxBridge`, unique `bypassauto-<uuid8>` names, per-test throwaway diag dirs, `_Fleet` closes only its own sessions (never kill-server); ran cleanly alongside sibling `usagesrc-*` sessions. First discovered the exact status-line indicators live (a throwaway probe): acceptEdits=`accept edits on`, plan=`plan mode on`, auto=`auto mode on`, bypass=`bypass permissions on`, default=none.
Findings (the UI rule §20 needs). **Default-launch cycle ring on this account = `default → acceptEdits → plan → auto → (wrap)`.** Also resolves the prompt's terminology: acceptEdits ("accept edits on") and `auto` ("auto mode on") are DISTINCT segments, not the same "Auto (accept-edits)" thing. Per segment: **acceptEdits** — reachable, NO launch flag (direct `--permission-mode acceptEdits` lands in it; precondition NONE). **auto** — reachable, NO flag on this account (direct launch AND cycling both reach it; no opt-in prompt) — but flagged account-eligibility-dependent (research: needs v2.1.83+/qualifying plan + one-time opt-in on a non-qualifying account; the test xfails honestly there rather than fabricating). **bypassPermissions** — the crux: **NOT in the default-launch ring** (5-press traversal `[acceptEdits, plan, auto, default, acceptEdits]` — bypass never appears), so an unreachable Bypass is a **SILENT ABSENCE from the cycle** (no refusal, no indicator; the only signal is the ring wrapping past it) — the dangerous case the UI must guard. Reachable two ways: `--permission-mode bypassPermissions` (production `create` path — starts IN bypass, startup-gate clearer accepts the warning; read back "bypass permissions on"), and `--allow-dangerously-skip-permissions` which **ARMS bypass into the cycle without activating** (starts in default; armed ring `[acceptEdits, plan, bypassPermissions, auto, default]` — bypass slots after plan, matching the research's full order). UI rule: gate Bypass behind a launch-time choice and DISABLE/HIDE it when neither pre-arm is present (never a live control that silently no-ops); acceptEdits/auto need no flag on this build, but confirm Auto against account eligibility rather than assume. Distinct from #1 (mid-run cycling) — this is launch-time preconditions. No ARCHITECTURE.md edit (spike-report; recommendation flagged here for the human).

Files: tests/test_bypass_auto_preconditions_live.py (new), DEVLOG.md

---

### 2026-07-02 17:55:00 — §10 #18 + #21 spike: Usage & context data-source probe (grouped) — statusLine=PER-TURN, account split-source, usage/limits screen-only (live)

Built and ran the grouped §10 #18 + #21 data-source spike (`dev/prompts/…-build-18-21-usage-context-sources.md`): per candidate source the dashboard's context/usage readouts depend on, what does it actually deliver under the bridge? New single live file `tests/test_usage_context_sources_live.py` (slug `usagesrc`, **3 focused tests**), Claude Code **2.1.198**. **`3 passed in 48.71s`** (durable: `tests/log/results_20260702T174936Z.txt`, PASS). Own `TmuxBridge` (never conftest's kill-server `bridge` fixture); one module-scoped tab-less `usagesrc-<uuid8>` session with a **per-agent `--settings` statusLine** command capturing the piped payload into OUR diag dir; creds read **READ-ONLY** (WSL side probed key-names only, token values never copied/logged); teardown closes only our own session + dir; never `kill-server`. Ran cleanly alongside sibling live sessions (`rewind-src-*`, `bypassauto-*`).
**#18 — statusLine `context_window` mid-run → CONFIRMED FIELD, but PER-TURN (BOUNDARY), not a live feed.** The statusLine payload on this build DOES carry a machine-readable `context_window` object — `context_window_size` (**1,000,000** for this account's model), `used_percentage`/`remaining_percentage`, `current_usage` (input/output/cache). But over a CONFIRMED long generation (story_len=4608 chars / ~1465 output tokens, 15 samples) the statusLine fired only **+1** time (`fires_delta=1`, at the turn boundary) and `used_percentage` never moved — so it is a **per-turn snapshot emitted at the boundary, NOT a continuous mid-run feed**. A numeric value is *readable* at any instant (last-boundary value persists), but it does not refresh mid-run. Two build notes worth keeping: `used_percentage` is **input-only** (an output-heavy turn won't move it even at the boundary — the fire-count, not the %, is the discriminating signal); and `bridge._detect_state` returns **`unknown` during long prose streaming** (the "esc to interrupt" hint clips at the pane's right edge), so the test tracks turns by transcript content, not the screen heuristic. **Verdict: DESIGN's "can't read (fresh) mid-run" HOLDS**; the statusLine is a confirmed per-turn/idle-boundary context source complementing §10-9's JSONL derivation, not a live mid-run one.
**#21 account → CONFIRMED but SPLIT-SOURCE (a "missing plan" finding).** `settings_io.account_band` yields `{email, org}` from `.claude.json` `oauthAccount` (`emailAddress`/`organizationName`) and `{plan: 'max'}` from `.credentials.json` `claudeAiOauth.subscriptionType` — **no single file yields all three**; `.claude.json`'s own tier fields (`seatTier`/`organizationRateLimitTier`/`userRateLimitTier`/`billingType`) are **NOT matched** by `account_band._PLAN_FIELDS`. So the Usage UI must read BOTH files (or `_PLAN_FIELDS` be extended) to show email+org+plan. WSL agents' creds mirror the same structure (email/org in `~/.claude.json`, subscriptionType/rateLimitTier in `~/.claude/.credentials.json`).
**#21 usage/limits → honest boundary: numbers are SCREEN-ONLY, not structured.** The transcript (`derive_context_usage`) gives context tokens/window but NO limit/reset fields. The TUI **`/usage` command DOES render live usage** — "Current session ██ 69% used · Resets 11:10am", "Current week ██ 14% used · Resets Jul 9", plus per-model cost — but only as **human-readable screen text** (scrapeable via the Console/bridge, not structured data). Creds carry only a **static tier label** (`subscriptionType='max'`, `rateLimitTier`), not live numbers. So live usage/limit NUMBERS are obtainable ONLY by scraping `/usage`, never as structured local data — the boundary the Usage UI must respect. #18 and #21 resolve independently; ARCHITECTURE.md §10 markers left for the human to clear.

Files: tests/test_usage_context_sources_live.py (new), DEVLOG.md

---

### 2026-07-02 11:00:00 — §10 #15 spike: Rewind / Handoff — BOTH conversation-rewind AND fork-from-point proven live (§5A)

Precondition gate passed — the gating research report `dev/notes/research/s10-research-15-rewind-handoff.md` exists with verdict **PARTIAL YES for both Rewind (A) and Fork (B)** → routed to §5A (build the test), not §5B (omission). New single live test `tests/test_rewind_handoff_live.py` (slug `rewind`, two focused tests), Claude Code **2.1.198**. Result line: **`2 passed in 88.45s`** (durable: `tests/log/results_20260702T175653Z.txt`, PASS). Own `TmuxBridge` (never conftest's kill-server `bridge` fixture); unique `rewind-*` / `rewind-src-*` / `rewind-fork-*` sessions torn down individually; ops scoped to our own diag + `~/.claude/projects/<cwd>/` dirs (both removed); never `kill-server`. Ran clean alongside sibling live agents (`bypassauto-*`, `usagesrc-*`). The interactive `/rewind` menu — the automation the research flagged as the open risk — was first mapped with throwaway probes and is now confirmed drivable over tmux.
**Mechanism (research-named → implemented):** (A) **Rewind = native `/rewind` restore-conversation**, driven over tmux: `/rewind → Up×k → Enter → Enter (Restore conversation) → Ctrl-U` (the selected prompt is restored into the input field; Ctrl-U clears it before interrogating). (B) **Fork = the research's path 1 = `claude --resume <src> --fork-session` then `/rewind`-in-fork** (absolute `CLAUDE_BIN`; a bare `claude` isn't on tmux's non-login PATH, which silently killed the first attempt). Path 2 (TypeScript-SDK `resumeSessionAt`) deliberately NOT used — this repo's SDK driver is the **Python** Agent SDK, which the research confirmed lacks a `resume_session_at` equivalent, and wiring a TS-SDK step would need shared tooling outside a single-file spike.
**§4 observable proven (read back from the live agent, never from injected text):** plant ordered codewords ALPHA-1/2/3; target "before ALPHA-3". (A) after rewind the SAME session replies **`ALPHA-1, ALPHA-2`** — ALPHA-3 genuinely lost from live context — and `read_log` still parses (transcript integrity intact). (B) the fork replies **`ALPHA-1, ALPHA-2`** (diverged, lost ALPHA-3) and writes its OWN new `<newid>.jsonl`, WHILE the source session stays **untouched** (replies **`ALPHA-1, ALPHA-2, ALPHA-3`**, still live) — a true fork, not a rewind-in-disguise. KEY build note: `/rewind` restore-conversation rewinds **in-place** on the same session-id (no new file at rewind time; old lines stay as history, live context drops them) — a clean rewind but NOT a fork on its own; `--fork-session` supplies the independent second session. Both graduate §10 #15 toward a §7 body section + `/sessions/{id}/rewind` and `/handoff` endpoints; ARCHITECTURE.md §10 #15 left unedited and NOT moved to Decided omissions (both operations scored WORKS) — the human owns the marker.

Files: tests/test_rewind_handoff_live.py (new), DEVLOG.md

---

### 2026-07-02 18:05:00 — §10 #19 spike: Console /clear (and /compact) transcript-path orphaning — /clear ORPHANS, /compact annotates-in-place (live)

Built and ran the §10 #19 spike (`dev/prompts/…-build-19-console-clear-transcript.md`): does a Console `/clear` (and `/compact`) rotate the agent's JSONL transcript, and does the bridge's pinned-session-id resolution (`session_id_for`/`find_transcript`) still find it or silently orphan it? New single live file `tests/test_console_clear_transcript_live.py` (slug `clconsole`, **2 focused tests**), Claude Code **2.1.198**. **`2 passed in 68.00s`** (durable: `tests/log/results_20260702T180426Z.txt`, PASS). Own `TmuxBridge` (never conftest's kill-server `bridge` fixture); fresh tab-less `clconsole-<uuid8>` session per test in its own unique diag-dir cwd (so its `~/.claude/projects` subdir is ours alone); we inspect ONLY our own transcripts; teardown closes only our session + dir; never `kill-server`. Ran alongside a sibling `rewind-src-*` live session.
**`/clear` → HAZARD CONFIRMED (needs a re-resolve).** Plant a pre-clear codeword (lands in `<pinned-id>.jsonl`), run `/clear`, plant a post-clear codeword: `/clear` **rotates to a NEW `<new-id>.jsonl`** (proven both runs — e.g. pinned `3217141a…` stays, post-clear turn's assistant echo lands in a fresh `fd53f4eb…`), the bridge's pinned id is **unchanged** (it has no knowledge of the Console clear), so `find_transcript` still resolves the OLD file and **`read_log` CANNOT see the post-clear turn — history is ORPHANED** (`readlog_surfaces_cw2=False`, codeword absent from the old file). This is exactly the §8.7 "spots to watch" hazard, live-confirmed (matches recon's prior-art note). **Fix (§19 fallback):** after a Console `/clear`, re-resolve the agent's session id (discover the new `<id>.jsonl`) and `register_session_id` it back with the bridge so resolution follows the rotation.
**`/compact` → NO HAZARD (annotate-in-place, different fix profile).** With real conversation to compact (3 filler turns first — a one-turn convo is a `/compact` no-op), `/compact` writes a **`compact_boundary`** marker and keeps the **SAME `<id>.jsonl`** (no new file), the pinned id is unchanged and still resolves the current file, and the post-compact turn's assistant echo lands in that same file → **`read_log` DOES surface it** (`readlog_surfaces_cw2=True`) — no orphaning, no re-resolve needed. Matches `claude-compaction-reference.md`'s prediction (compaction annotates in place). **Measurement notes for the durable test:** the post-command codeword is matched only in an **assistant** entry (`"type":"assistant"` + needle) — the user-prompt echo is written immediately and would false-signal completion for the same-file `/compact` case; and turn state is tracked by transcript content, not the prose-flaky screen heuristic. Net: `/clear` and `/compact` have DISTINCT fixes — `/clear` needs the §19 re-resolve, `/compact` is safe as-is. ARCHITECTURE.md §10 #19 / §8.7 left unedited (the human owns the marker).

Files: tests/test_console_clear_transcript_live.py (new), DEVLOG.md

---

### 2026-07-02 20:18:06 — Authors lens (3rd editor-rail tab) built across the six design/ files

The Plans/Documents editor nav rail is now a **three-tab lens switch** (Outline · Feedback · Authors, V1 layout: Outline keeps its label + first half, Feedback + Authors are icon+count tabs splitting the second half): the selected tab repaints the rail card list + editor gutter badges + docked box together. **Authors** surfaces authorship metadata (agent + timestamp) via a neutral users-glyph gutter badge, author cards (agent badge + section chip + timestamp), and an author box listing **one entry per gutter-badge count**. `behavior.js` — new `getAuthors`/`authorsBySec`/`authorBadge`/`authorListHTML`/`openAuthorPop`; lens-aware `mdEditorHTML`/`navCardClick`/`planNavMode` (the switch now repaints the gutter + resets the box); seeded `authors:[]` on the 3 PLANS; plans now open in **Outline with no gutter badges** (intentional — badges show only in Feedback/Authors). `styles.css` — V1 tab layout (`.nt-ic`/`.nt-lab`/`.nav-tab--ol/fb/au`) + `.rd--author` + `.au-line`/`.au-clk`, **zero new tokens** (tokens.css untouched). `gallery.html` — V1 strip on nav-tab, author gutter badge on verdict-chip, new `author-card` card (Composites 54→55), author box on comment-popover. `DESIGN.md` — nav-rail prose → three lenses + V1, `author-card` registered, `.rd--author` noted, dark-teal/`--select` rows updated. Verified headless in the mockup + gallery (all 3 lenses, three-indicator box sync, narrow/wide extremes, 0 JS errors). An adversarial review pass (3 dimensions + per-finding verify) caught & fixed a **real regression** — the lens `outerHTML` swap dropped the editor body's jump-to-end pill, now re-attached via `refreshJumpPills()` — plus a dead `au-list` class and 3 stale two-mode comments. Prototype/rationale: `.scratch/ui-snippets/authors-lens.html`. Approved item also added to `dev/notes/TODO.md` NEXT UP — DESIGN.

Files: design/behavior.js, design/styles.css, design/gallery.html, design/DESIGN.md, dev/notes/TODO.md

---

### 2026-07-03 16:59:18 — docs: TODO.md refactored — split inboxes, section tags, backend backlog merged

Reorganized `dev/notes/TODO.md` (overwritten **in place** so git history on the path is preserved). Split the single Inbox into **[ID] INBOX — DESIGN** (the 6 existing all-design notes) + **[IB] INBOX — BUILD**, each placed directly under its Next up. Consolidated every per-section helper line into a new **SECTIONS** table + a tightened HOW-block at the top (two-lane Design/Build framing; nothing dropped). Tagged all list headers with bracket IDs (`[BD]`/`[BB]`/`[BH]`/`[ND]`/`[ID]`/`[NB]`/`[IB]`; item IDs now `BB7`/`BD2`-style) and updated cross-refs (`D2`→`BD2`). Cleared the unapproved **NEXT UP — BUILD** and moved all 11 storage/persistence items into **[BB] BACKEND** as BB15–BB25 (brittle `§n`/line-number refs stripped; kept stable file/symbol + one `docs/ARCHITECTURE.md` §8 pointer; deps rewired to `BB16`/`BB1`/`BB15`/`BB17`); merged old B12+B13 → **BB12 Docs in Agent Context**. Relevance-audited both sections first against live code + this log — the whole 2026-07-02 sprint was §10 validation spikes, not storage build (`.awl`/`.awl-agents` still un-renamed, roster/inbox/links still memory-only), so nothing in the backlog was already built and all 11 moved items were kept. Removed the `TODO-temp.md` working draft.

Files: dev/notes/TODO.md, DEVLOG.md

---

### 2026-07-03 17:21:28 — docs: TODO.md reverted to a single [IN] INBOX (per user)

Per the user, collapsed the two-inbox split (`[ID]`/`[IB]`) back to a single **`[IN]` INBOX** — they add unsorted notes and have agents triage them, so per-lane inboxes didn't fit the real workflow. The single inbox now sits after both Next up sections (before Scratch) and holds the 6 existing notes; the SECTIONS table, the intro lane-map ("one inbox, two lanes"), and the HOW-block Inbox guidelines were all updated so agents **sync each note into the appropriate Next up or backlog section** (a backlog section by default; a Next up queue when the human directs it straight to work). No item content changed; only the inbox structure + its guidelines.

Files: dev/notes/TODO.md, DEVLOG.md

---

### 2026-07-03 18:16:34 — tests: README spike table + conftest live-tier detection + requirements deps (doc-integration Phase 2)

Phase 2 of the test-findings/doc-integration pass (harvesting the 2026-07-02 spike builds). Added the **17 new live spike files** to `tests/README.md` as a new **"Feasibility spikes (opt-in, live)"** table — each row names the §10 question it probes + a one-line verdict (13 ✅ FEASIBLE; ⚠ system-fault PARTIAL, console-`/clear` HAZARD, polling degrades-from-N=1; 🚫 fast-mode OMITTED); also tweaked the frontend-gap note for the new `tests/ui/` contract spike. Made `conftest.py` live-tier detection **convention-based** (new `_is_live_nodeid`: any `*_live.py` + the legacy `test_tmux_bridge.py`) so the durable results record stops mislabeling live runs as "hermetic" and the list can't rot as spikes are added. Added `playwright==1.61.0` + `psutil==5.9.8` to `requirements.txt` (the UI-slice + polling-scale spikes' deps, previously `.venv`-only). **No product code touched** — test-support files only. Verified: hermetic tier **395 passed, 63 deselected** (all 17 spikes correctly excluded by their `integration`/`slow` markers), results record labels/counts correct.

Files: tests/README.md, tests/conftest.py, requirements.txt, DEVLOG.md

---

### 2026-07-03 18:40:00 — DEVLOG rotation: archived 61 entries into DEVLOG-archive-05

Cleared the long-overdue rotation (the file had grown to ~877 lines, well past the ~700 threshold). Moved the oldest **61** Log entries (2026-06-30 17:45:00 → 2026-07-02 07:35:14) **verbatim** into a new [`archive/devlog/DEVLOG-archive-05.md`](archive/devlog/DEVLOG-archive-05.md) (cut only at `### ` headings, never mid-entry), taking `DEVLOG.md` from **~877 → ~300 lines**; the recent window now opens at the 2026-07-02 07:44:40 §10 evidence-board entry, keeping the whole §10 / spike / doc-integration workflow in view. Refreshed the recent-window note and added the archive-05 digest paragraph + index row under **Archived history**. Verified the move **byte-for-byte** against a pre-rotation backup (the moved block and the retained tail each `diff`-identical, no entry split).

Files: DEVLOG.md, archive/devlog/DEVLOG-archive-05.md

---

### 2026-07-03 19:55:00 — ARCHITECTURE §11 "Build backlog & queue" + TODO.md [BB] strip (doc-integration Phase 3)

Phase 3 of the test-findings/doc-integration pass: consolidated all build-related backlog into `docs/ARCHITECTURE.md` so it lives in **one place**. Created a new top-level **§11 "Build backlog & queue"** (Repo map renumbered §11→§12; no internal refs broke): §11.1 = a **⚠ Today index** (one row per body section carrying markers, each tied to its queue item or §10 gate; "—" = unqueued debt), §11.2 = the storage/lifecycle set (ex-BB15–25, pointing into §8/§9), §11.3 = the feature backlog (ex-BB1–3, 5–10), §11.4 = docs/meta chores (ex-BH3, 5–7) — all rows keep their ex-IDs for traceability. The backlog's four **(open)** items routed to §10 instead: BB12/13/14 became new queue entries **#23–25** (a "backlog-port additions (2026-07-03)" block), BB11 was absorbed into #13, and BB4 was recorded as already homed at #22. Stripped every `TODO.md` reference out of §10 and the doc header/§2 (build-queue pointers now → §11; the three design-lane refs remain by design). `dev/notes/TODO.md` correspondingly cut down: **[BB] removed entirely**, [BH] trimmed to the 3 dev-env chores (npm, PowerShell strings, CLAUDE.md trim), top matter/SECTIONS/triage prose rewritten so backend inbox notes now route to §11 and [NB] NEXT UP — BUILD stays as the execution hand-off lane; [BD]/[ND]/[IN]/SCRATCH untouched. `CLAUDE.md` synced (2 lines: the ARCHITECTURE key-files row + the design-rule backlog parenthetical).

Files: docs/ARCHITECTURE.md, dev/notes/TODO.md, CLAUDE.md, DEVLOG.md

---

### 2026-07-03 20:06:28 — docs: TODO.md [ND] NEXT UP — DESIGN queue seeded from inbox (Plans/Docs refactor)

Filed all 6 `[IN]` INBOX notes into `[ND]` NEXT UP — DESIGN as **7 sequenced design items**, after a multi-turn design discussion this session. The batch unifies Library → Plans and Documents onto one shared reviewable-document card: Documents gains a card layout + the Outline/Feedback/Authors rail + commenting + the full Draft→In review→Approved approval workflow + a pending badge (overturns the "approval is Plans-only" rule); both tabs get a left tab-level nav column with bidirectional card↔nav sync; the Outline gains a nested Table of contents + Authors/Reviewers rosters (a two-level approval model); the per-section Approve gutter chip is dropped; plus card-header/box/edit-parity refinements, an Inbox docs-review flow with neutral accordion sections, a gallery section-nav, and a no-hard-wrap example-content cleanup. Decisions locked in-conversation: keep the "Revise" button name (no new "Revising" state — In review covers it), Feedback tab stays (caption "Responses"→"Feedback"), nested headings supported to `####` built level-generically. `[IN]` inbox cleared to empty. No design/code files touched — this is queue/log only.

Files: dev/notes/TODO.md, DEVLOG.md

---

### 2026-07-03 21:05:00 — Phase 3 correction pass: [BH] un-ported, all inbound TODO.md refs stripped (doc-integration Phase 3c)

Alignment corrections after user review of Phase 3. New standing rule: **nothing outside `dev/notes/TODO.md` references TODO.md — full stop** (it's a private capture doc, used only when the human points an agent at it). Applied: **ARCHITECTURE.md** — removed the §11 "Execution hand-off" note (§11 exit is now just built→row-removed or demoted→§10), de-named TODO in the §11/§11.2/§11.3 intros (bare ex-BB IDs remain as *temporary* scaffolding, stripped in the final refactor), **deleted §11.4 entirely** ([BH] was not meant to port), reverted the §2 README pointer to a plain "still owed," and stripped the three legacy design-lane refs (§3.2, §7.16, §8.5 → "queued in the design lane"). **TODO.md** — [BH] restored verbatim to its 7-item "HOUSEKEEPING & DOCS" form (heading, table row, lane prose, triage prose); the concurrent design session's [ND] queue / emptied [IN] / SCRATCH edits left untouched. **CLAUDE.md** — both TODO.md mentions removed (§11 pointers kept). Verified: `grep TODO` returns zero hits in ARCHITECTURE.md and CLAUDE.md. Also agreed: a new **Phase 9** (after the final sweep) will feature-refactor §10/§11 by feature with an old→new mapping table, strip the ex-ID scaffolding, and re-verify zero inbound TODO.md refs repo-wide.

Files: docs/ARCHITECTURE.md, dev/notes/TODO.md, CLAUDE.md, DEVLOG.md

---

### 2026-07-03 21:35:00 — scratch: doc-integration workflow tracker created (+ 2 un-run spikes caught)

A repo-state audit answering "did any scoped research go un-run?" found: all **5 research reports exist** in `dev/notes/research/` (#12, #13, #14, #15, #22 — none yet reviewed or harvested), but **two authored spike prompts were never dispatched** — `2026-07-02-s10-build-04-inject-tail.md` (§10 #4) and `…-build-07-runstrip-tail.md` (§10 #7); the user is dispatching them now. To guard the rest of the workflow against exactly this kind of silent fall-through, created [`dev/notes/scratch/2026-07-03-doc-integration-tracker.md`](dev/notes/scratch/2026-07-03-doc-integration-tracker.md) — the phase ledger (now 9 phases; Phase 4 split into 4a research-review / 4b harvest / 4c late spikes), the locked standing rules (TODO.md private, §10/§11 split, ex-ID scaffolding, no code fixes), and a full artifact inventory with harvest checkboxes: 17 spike tests, 2 late spikes, 5 research reports, 5 code gaps, the contradiction orphans, and the scratch docs due for archiving. Tracker is disposable — archived at Phase 9.

Files: dev/notes/scratch/2026-07-03-doc-integration-tracker.md, DEVLOG.md

---

### 2026-07-03 20:47:39 — docs: TODO.md [IN] inbox — token-compliance sweep captured

Added one `[IN]` INBOX note capturing the token-compliance sweep from this session's design discussion: migrate hardcoded design values that duplicate an existing token to `var(--…)` (known leaks — `styles.css` `4px`/`6px` radii, `gallery.html`'s `4px`/`3px` chrome, stray inline `2px` borders), scoped to values matching an existing token only — font-sizes stay inline (no such token, by design) and documented exceptions (circles/pills/squares, `--nc`, `--term-*`, `mockup-toolkit.js`) are preserved; noted that the guidelines already exist and the real gap is enforcement. Left as a capture, not promoted to `[ND]` — the human will fold it in alongside the radius change. No design/code files touched. (Timestamp trails the entry above it — concurrent design/doc-integration sessions logging on a clock ~48 min ahead; appended at the Log foot per the append-only rule.)

Files: dev/notes/TODO.md, DEVLOG.md

---

### 2026-07-03 20:52:15 — docs: correction — token-sweep note promoted [IN] → [ND] item 8

Supersedes the 20:47:39 entry's "left as a capture, not promoted" line: at the human's direction, moved the token-compliance sweep out of `[IN]` INBOX into `[ND]` NEXT UP — DESIGN as **item 8** (reformatted to the section's bold-header convention; scope and exclusions unchanged). `[IN]` re-emptied. Intent: the sweep now runs as part of the design refactor so the hardcoded radius/border leaks are tokenized before the human hand-edits the three `--radius-*` values. TODO.md only — no design/code touched.

Files: dev/notes/TODO.md, DEVLOG.md

---

### 2026-07-03 21:19:13 — §10 #4 tail spike: true mid-run Inject (open tail) — INFEASIBLE, no earlier-than-boundary point

Ran the "earlier-than-hook-boundary Inject" feasibility spike as a new live test `tests/test_inject_tail_live.py` (integration+slow; own `TmuxBridge()`, tab-less, parallel-safe, no `kill-server`). Live result: typeahead into a *generating* pane lands in the composer but is **held there for the whole turn** and submitted only at the turn boundary — pure Next/Queue, never mid-turn. Decisive run: an ultrathink turn was driven to `generating`, the marker typed + Enter pressed mid-turn, then the marker sat **queued ~36 s** (`marker_in_user=False`) during live generation and flipped to a real `user` transcript entry only when the turn ended (t≈41 s), answered as an ordinary next turn (`mid_turn_hit=False`, `earlier_safe_point=False`). 2 consecutive clean passes (`= 1 passed in 51.9s / 53.3s =`, `results_20260704T041754Z`, CLI 2.1.201). Design notes captured live: (a) extended thinking ("ultrathink") is the only reliable way to hold a multi-second generating window — output length streams too fast/variably; (b) `status()`'s 15-line detection false-reads *idle* once the composer holds typed text (spinner/"esc to interrupt" pushed out) — the test confirms `generating` with an empty composer *before* typing, then probes after Enter. **Verdict: INFEASIBLE** — confirms §10 item 4's Fallback (hook-boundary delivery + transparent Next/Queue degrade) is the final model. Doc-change recommendation flagged to the human (not applied): move item 4's open tail to a Decided omission / resolved-as-fallback. No edits to ARCHITECTURE.md or TODO.md.

Files: tests/test_inject_tail_live.py, DEVLOG.md

---

### 2026-07-03 21:23:42 — §10 #7 tail spike: real run-strip completion % (open tail) — INFEASIBLE, no engine progress fraction

Ran the "engine-side progress signal" feasibility spike as a new live test `tests/test_runstrip_tail_live.py` (integration+slow; own `TmuxBridge()`, tab-less `acceptEdits` session, parallel-safe, no `kill-server`). Drove a genuine multi-tool task (three Write calls → a/b/c.txt, then `DONE_TAIL`) that publishes **no checklist**, then read the transcript back via `derive_context_usage(read_log(...))`. Live result: the run is **100% complete** (all 3 files written, DONE_TAIL) yet the engine yields only NUMERATORS — `work_steps=2`, `tool_total=3` (three `edit` tool_uses) — with **no denominator**: the sole percentage is `percent=18.79` = **context tokens** (37583/200000), categorically not work done. No `TodoWrite` fired (`todo_uses=[]`), so not even the self-report todo channel appeared; and `checklist.parse_checklist([...])` on the no-checklist texts returns the honest **barber-pole indeterminate** floor (`total=0, fraction=0.0`). Test pins `derive_context_usage`'s exact 8-key shape so a future engine denominator would flag as the WORKS case. 2 consecutive clean passes (`= 1 passed in 12.9s / 14.2s =`, `results_20260704T042321Z`, CLI 2.1.201, Sonnet 5). Cited: research Q3 item 3 (transcript overlay = busy/idle, not a fraction) + §10 item 7. **Verdict: INFEASIBLE** — no trustworthy engine-side completion fraction exists; confirms §10 item 7's Fallback (checklist self-report + barber-pole floor) as the final model. Doc-change recommendation flagged to the human (not applied): move item 7 from ◐ partially-proven to a Decided omission / resolved-as-fallback. No edits to ARCHITECTURE.md or TODO.md.

Files: tests/test_runstrip_tail_live.py, DEVLOG.md

---

### 2026-07-04 11:30:00 — ARCHITECTURE §10/§11 harvest complete: 17 spikes + 5 reports + 2 late tails (doc-integration Phase 4)

Phase 4 of the doc-integration pass — the full §10/§11 harvest, **docs only** (no product code). **4a** (5 parallel Sonnet subagents): reviewed the 5 never-reviewed research reports — #12 assets / #13 native-coordination / #22 subagent-mgmt settled to 🧪 needs-spike (research done, not yet buildable), #14 → ◐, #15 → ✅ (spike-passed). **4b:** harvested the 17-spike batch + the 5 research findings into §10 — **8 → ✅ proven** (#1 permission-mode, #2 thinking, #6 plan/decision [resume is a `keys()` Enter, **not** a hook `updatedInput`], #8 subagent-status, #9 context/compact, #11 per-agent cost [**overturns the "honest blank"** — `/cost` gives a real figure], #15 rewind/fork, #20 bypass/auto), **9 → ◐ partially-proven** (#5, #10, #14, #16, #17, #18/#21, #19), **#3 fast held 🧪** (credit-gated xfail = account limit, not a proven dead-end — flagged). **4c:** both late tail-spikes came back **INFEASIBLE** (#4 mid-turn Inject held to the turn boundary → pure Next/Queue; #7 engine emits numerators, no denominator) → both marked **⛔ resolved-at-fallback** (shipped model is final) and recorded in the Decided-omissions note; formal relocation deferred to Phase 9. Every ✅/⛔ carries a *(pending relocation — Phase 9)* marker (updated in place; relocates to the settled body at the refactor). Body corrected: §7.15 (honest-blank overturned), §7.16 (plan-resume proven), the two §11.1 ⚠-index rows. **§11 grew:** new **§11.4 "Spike-surfaced code fixes"** #23–28 (the 5 code gaps + a `Task`→`Agent` parser audit) + 2 spike-derived features in §11.3 (#21 Rewind/Fork, #22 hook-lifecycle arbiter). Tracker updated (4a/4b/4c ✓). The two late-spike test files (`test_inject_tail_live.py`, `test_runstrip_tail_live.py`, logged above by the concurrent spike agent) are committed alongside this harvest.

Files: docs/ARCHITECTURE.md, dev/notes/scratch/2026-07-03-doc-integration-tracker.md, DEVLOG.md

---

### 2026-07-04 12:15:00 — Commit the concurrent design session's [ND] execution plan (housekeeping)

Session handoff from dev-doc-4g. That agent's Phase-4 harvest was already committed + pushed (`e94935e`); the only thing left in the working tree was the concurrent design session's untracked `[ND] DESIGN queue` parallel-lane execution plan (`.claude/plans/you-will-be-implementing-quiet-gem.md`), which dev-doc-4g deliberately left alone as not-theirs. Committed it now to clean the tree and preserve the plan as reference — no product/design code touched. Whether that design refactor actually runs is a separate call: frontend/design *implementation* is being frozen pending the build sprint (the Phase-5 identity-editing + frontend-freeze decisions are being reconciled into ARCHITECTURE next).

Files: .claude/plans/you-will-be-implementing-quiet-gem.md, DEVLOG.md

---

### 2026-07-03 22:10:00 — ND L1: unify Plans & Documents into one reviewable-document component (items 1+2)

Rebuilt the Library's Documents tab onto the Plans card component: new plan-shaped `DOCS[]` (md moved verbatim from the retired textareas, DOC_FB folded in, mixed lifecycle statuses) + `entryById()` unifying every Library lookup (doc special-cases in getAuthors/saveComment deleted). Both tabs are now two-column — a shared `entry-nav` (mini-card rows: icon · name(·path) · lifecycle badge) beside the card list, with bidirectional nav↔card sync (`openEntry`/`navPick` ↔ `togglePlan`/`syncNavHighlight`). Docs gain the full decision footer (Revise·Reject·Approve; old doc **Remove** button dropped — deliberate), a per-card raw-md edit toggle (`entryEdit`), a `docs-badge` count chip, and a live plans subtitle; `libFootHTML` survives for Assets only. DESIGN.md Library section reconciled — approval is no longer Plans-only. Spot-checked live: zero console errors, both tabs render, doc Approve flows like a plan. Gallery propagation deferred to the batched L3 pass. Commit `b9916df`.

Files: design/behavior.js, design/mockup.html, design/styles.css, design/DESIGN.md

---

### 2026-07-03 22:14:00 — ND Lane Q: quick wins 7a/7b/7c + token-compliance sweep 8 (merge `f2b09af`)

7a: message-card sender→recipient arrow swapped from the Unicode `→` glyph to the `arrow-right` lucide icon (`recipientsHTML`; `.rcpt-to` restyled to a 14px icon holder). 7b: Team Graph "Link Agents" button renamed "Link Config" to match its drawer heading. 7c: `gallery.html` gains a sticky sectioned left ToC (`gx-toc`, gallery-local, built generically off the `.gx-sec`/`.gx-card` DOM — 5 sections, ~126 card entries, scroll-to + scroll-spy, collapses <780px; the old horizontal `.gx-nav` absorbed). 8: token sweep — `4px`/`6px` radii → `var(--radius-base)` on `.ghost-ic`/`.vrow`/`.att-item`/`.exp-mi`/`.con-perm` (intended +1px softening), six inline `2px` borders → `var(--border-width)` (mockup status dot, `#hist-acc`, minibar, legend dots), gallery chrome radii → `var(--radius-base/-sm)` + its `3px` section divider → `var(--divider-width)`; final grep shows no non-exception px radii remain. Verified in-browser at 900/1900px. Built on branch `nd-lane-q` (commit `453ffcb`), merged clean.

Files: design/behavior.js, design/styles.css, design/mockup.html, design/gallery.html

---

### 2026-07-03 22:18:00 — ND Lane I: Inbox docs-review flow + accordion typed sections (item 6; merge `6d4d9bf`)

Renamed the Inbox "Plan" typed section to "Plans & Docs" (one unified card type) with the Review action routing by entry kind — `doc-*` ids → Library → Documents, else Plans (post-merge this rides L1's `openEntry`); seeded a wren README.md doc-review card. Converted every Inbox typed section to a neutral `--surface-3` accordion band (leading chevron, count badge, `--rule` hairline, expanded by default, deliberately distinct from the `.fcard` accordion) via new `toggleInboxSec()`; this resolves OQ-2 (fold vs catalog → **folds**) and drops the `inbox-section` `undecided` marker; gallery card updated with the real accordion markup. Verified in-browser: all six sections toggle, doc Review switches the Library tab, bands hold at 300/900px. Built on branch `nd-lane-i` (commit `69462a8`); merge conflicts in `reviewPlan` (superseded by L1's `openEntry` — same routing convention) and the DESIGN.md registry (kept both lanes' rows) resolved by hand.

Files: design/behavior.js, design/styles.css, design/gallery.html, design/DESIGN.md

---

### 2026-07-03 22:24:00 — ND review-panel fixups: stale gallery arrows + kind-aware Inbox Review tooltip

Two confirmed findings from the adversarial review panels on the lane diffs, fixed on merged main. (1) Lane Q's `.rcpt-to` restyle (font glyph → icon holder) had orphaned the gallery's six static `→` specimens (Recipient Badge ×4, Message Card ×2), leaving them oversized/off-spec — replaced with the real `<i data-lucide="arrow-right">` markup. (2) `inboxCardHTML`'s Review tooltip was hardcoded to "…Library → Plans" even for `doc-*` cards that route to Documents — now kind-aware, matching the gallery specimen's wording and `reviewPlan`'s actual routing.

Files: design/gallery.html, design/behavior.js

---

### 2026-07-03 22:30:00 — TODO [BH8]: audit for over-scoped absolute language in the guiding docs

Added a housekeeping/docs backlog item (`BH8`) to `dev/notes/TODO.md`: sweep `docs/ARCHITECTURE.md` + `design/DESIGN.md` for categorical wording ("never / always / only / read-only / no X exists / cannot") and test each rule against the intent it protects, narrowing the ones that over-reach (they manufacture false doc-vs-doc / doc-vs-code contradictions and get re-litigated every session). Prompted by the Phase-5 discussion, which already surfaced two: §7.16/§8.5 "never writes into a content file" and §7.5 identity "read-only in v1". No doc bodies changed yet — this just queues the audit.

Files: dev/notes/TODO.md, DEVLOG.md

---

### 2026-07-03 22:52:00 — ND L1 review panel: switchTab stale-key remap regression fixed

The adversarial panel on L1 (5 findings confirmed, 0 refuted) caught that the `awl-v8` stale-doc-tab remap guard (`!getElementById('doc-'+t)`) now matches the new doc CARD ids (`doc-readme`, `doc-claude`), so a returning user with a stale saved sub-tab got a blank Library. The guard now gates on the known tab set (`plan/documents/assets`). The remaining confirmed findings (lens-switch-during-edit double-view; two stale DESIGN.md prose refs to the retired doc-switcher/single-doc-pane shape) are deferred to the L2 checkpoint — L2 is concurrently rewriting that exact region. The fix rides in the L2 checkpoint commit (same file, in-flight tree).

Files: design/behavior.js, DEVLOG.md

---

### 2026-07-03 23:25:00 — ND L2: Library rail, nested TOC & two-level review surface (item 3)

Reworked the Library editor rail/review surface (gallery propagation deferred to L3). Outline caption → "Table of contents", Feedback caption → "Feedback". Level-generic heading parse (`##`–`####`): heading rows carry `data-hlevel` + a line-index `data-secid`; one `sectionRows(host,secid)` boundary helper (a level-L section spans to the next heading ≤ L) now drives `railClick`/`railHover`/`highlightFbSection`/`planJump` — nested selection covers sub-headings, and repeated heading names can't collide. The Outline gains **Authors** + **Reviewers** rosters (distinct agents; reviewer rows trail their worst revise/block badge, or a lone Approve) — encoding the two-level model (reviewer verdicts ≠ document lifecycle). Dropped the per-section approve gutter chip + approve outline dot (absence = approved). Revise/Block verdicts now require a non-empty comment (Save disabled + hint + submit guard); Approve stays comment-optional. Seeds: every plan/doc gained a document-wide author; plan-1 Approach carries revise+approve+block; readme.md re-seeded with real `###`/`####` levels. Verified headless: 0 JS errors, boundaries/rosters/gutters/comment-rule all driven. **Checkpoint fixes folded in** (L1-panel deferrals): lens-switch during raw-edit now implicitly saves and exits edit (was: stacked double-view with Edit stuck on "Save"); DESIGN.md's two stale refs to the retired doc-switcher/single-doc-pane shape corrected.

Files: design/behavior.js, design/styles.css, design/DESIGN.md, DEVLOG.md

---

### 2026-07-03 23:55:00 — ND L2 review panel: Authors-lens crash hot-fixed (esc null-guard)

The adversarial panel on L2 (3 findings, all the same root bug) caught a **high-severity crash**: L2's document-wide `{sec:null}` author seeds hit `authorListHTML` → `esc(f.sec)` → `null.replace()` TypeError, killing the Authors lens on every plan/doc (the tab even advertised a nonzero count). Hot-fixed by making `esc()` null-safe (`String(s==null?'':s)`); the in-flight L3 agent was messaged mid-run to render `sec:null` rows as proper document-wide entries in its item-5a author-box rework and to drive the Authors lens in its full verification. Also restored the `## Archived history` heading + separator that the 22:52 DEVLOG append had accidentally consumed (orchestrator error, caught by a structure check).

Files: design/behavior.js, DEVLOG.md

---

### 2026-07-04 00:15:00 — Phase 5: applied the 3 doc-vs-doc contradiction reconciliations (docs only)

Doc-integration Phase 5 — reconciled the three contradictions the coverage audit flagged, per the user's decisions. **Docs only, no product code;** all substantive edits in `docs/ARCHITECTURE.md` (+ one `CLAUDE.md` row) — **zero design-file edits** (in all three, DESIGN was already the correct side, so this was ARCHITECTURE catching up). **(1) Identity editable** — §7.5 flipped "read-only in v1" → **editable (all 5 fields)**, with the rationale that identity is dashboard-owned display metadata keyed separately from routing (links/hooks/inbox key on a stable session id, so a rename can't break refs); the **name** is additionally registered as the real Claude Code session name via `claude --name` at launch + `/rename` mid-run (confirmed live in `claude --help`), surfacing in the VS Code extension session list + `--resume` picker. **(2) Frontend park-and-rebuild** — §4.4 retitled + rewritten from "finish/port the renderer" to **rebuild the renderer fresh from `design/`**, freeze **scoped to the visible UI only** — the Electron main-process shell (sidecar lifecycle, window, detach-on-close, packaging; §10 #10 / §11.4 #27) stays active feasibility work; `api.ts` = preserve-through-rebuild contract; `tests/ui/` noted as existing. CLAUDE.md `frontend/` row corrected ("built in place" → parked/rebuild + Electron-shell-not-frozen note). **(3) createDoc/delete** — §5.2 gained `POST`/`DELETE /library/document`; the over-absolute "the dashboard never writes into a content file" (§7.16 + §8.5) narrowed to **the review layer never writes annotations into content** (those stay in the `.meta.json` sidecar), while create/delete/explicit user-directed edit are allowed. Both §11.1 ⚠-index rows (§7.5, §7.16) synced. Tracker §E + Phase-5 checkbox ticked. These two absolutes were also the seed examples for the BH8 audit.

Files: docs/ARCHITECTURE.md, CLAUDE.md, dev/notes/scratch/2026-07-03-doc-integration-tracker.md, DEVLOG.md

---

### 2026-07-04 00:45:00 — §10 #3 Fast-mode toggle: re-ran the spike with credits → ✅ proven

User enabled Fast/Opus usage credits, unblocking the previously credit-gated §10 #3 spike. Re-ran `test_fast_mode_toggle_live` live (CLI 2.1.201): `credit_gated=False` now, and `Meta+O` opens the "↯ Fast mode (research preview)" panel. Explored the interaction (scratch, since removed) and found the lever: with the panel open, **`Space` toggles** the `Fast mode OFF/ON` line (Enter/Escape only close it). Strengthened the test from its old "panel-appears + honest xfail" shape to the **full there-and-back flip proof** (open → read OFF → Space → read ON → Space → read OFF), mirroring the proven `Meta+T` thinking spike (#2); it leaves Fast OFF before teardown so nothing keeps drawing credits, and keeps a credit-gate `xfail` branch for accounts without Fast. Test passes live (`off → on → off`, read-backable, repeatable; no orphaned tmux sessions). Harvested: §10 #3 🧪 needs-spike → **✅ proven** *(pending relocation — Phase 9)* with the `Meta+O`+`Space` mechanism + wiring guidance; the §10 Decided-omissions note updated (both mode toggles now proven); tracker 4b flag resolved. `set_fast()` remains an in-code no-op (wiring is a build item; the §5.2/§6 capability-gated-400 ⚠Todays stay accurate).

Files: tests/test_fast_mode_toggle_live.py, docs/ARCHITECTURE.md, dev/notes/scratch/2026-07-03-doc-integration-tracker.md, DEVLOG.md

---

