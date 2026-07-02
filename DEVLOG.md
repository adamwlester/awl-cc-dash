# AWL Agent Platform — Project Log

> **For Claude sessions:**
>
> Read this file top-to-bottom before making changes to the codebase. This file is **100% append-only** — current state is re-derived from recent entries (the latest entry touching an area is its current truth); forward intent / next steps live in `TODO.md` and planning, not here.
>
> **Log** — append-only, ordered **oldest → newest** (oldest entry at the top of the Log, newest at the bottom). Every entry's heading MUST begin with a timestamp in `YYYY-MM-DD HH:MM:SS` (24-hour clock, to the second). **Add a new entry at the BOTTOM of the Log before you end any turn that changed the repo** — created, deleted, moved, or meaningfully edited any file (code, config, docs, or design) — and before you report "done." **Default to logging:** the bar is "did the repo change?", not "was it big?" Don't let the log fall behind the code (it has happened before). If you discover something was wrong, add a new correction entry — don't edit the old one. **Template:** a `### YYYY-MM-DD HH:MM:SS — short title` heading, 1–4 lines (what changed + the observable outcome), then a `Files:` line.
>
> **General** — never strike out, rewrite, or delete existing entries in the Log. There are no in-place-editable sections; if something was wrong, add a new correction entry.
>
> **Scope** — this log covers the entire workspace: bridges, backend, dashboard design, frontend, tooling, and infrastructure. Projects under `projects/` maintain their own logs.
>
> **Rotation** — when this file grows past **~700 lines**, archive the oldest entries to keep it small. The oldest entries are at the **top** of the Log (this file is oldest → newest), so cut from the top: move them **verbatim** (cut only at `### ` headings, never mid-entry) into the newest `archive/devlog/DEVLOG-archive-NN.md`, appending in order, until this file is back under **~300 lines**; then refresh the digest + index row in **Archived history** at the bottom. Each archive file is itself oldest → newest. Never edit moved entries.

---

## Log

> This file is the **recent window**. Older entries (2026-03-26 → 2026-06-30 15:30:00, including all `[Reconstructed]` history) have been rotated into `archive/devlog/` — see **Archived history** below.

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

## Archived history

Older entries are rotated into `archive/devlog/` (see the **Rotation** rule in the header) to keep this file small. Archived entries stay full-fidelity and **verbatim** — open the relevant archive only when you need the detail; the digest below is enough for most context.

**Digest — [`DEVLOG-archive-01.md`](archive/devlog/DEVLOG-archive-01.md) (2026-03-26 → 2026-06-13, 21 entries):** the sandbox-era origin story. Workspace + MCP-server setup; the tmux **bridge** built from first draft to a stable 20-method package with a 30-test suite; the **HTTP bridge** (VS Code extension, port 7483); dashboard inception and the **TUI → Electron/React pivot**; the wireframe lineage **v1 → v4** with the palette exploration (Vintage Teal → Warm Dark); the architecture pivot where the Agent **SDK + `stream-json`** replaced xterm/ttyd terminal embedding; the **FastAPI sidecar** (port 7690) + React single-file scaffold; the **E2E pipeline proof**; the design-system / event-feed component specs; and the early file reorganizations (`ui/` → `awl-dashboard/testing/` → `agent-dashboard/design/`).

**Digest — [`DEVLOG-archive-02.md`](archive/devlog/DEVLOG-archive-02.md) (2026-06-13 → 2026-06-21, 117 entries):** the dashboard design push and the start of the `awl-cc-dash` migration. The bulk is the **UI mockup iteration** — the ui-concept lineage from the v5 wireframes through **v9p13** (3-pane layout, the Warm-Dark palette, the Team Graph / Team Feed / Agent panels, and the Documentation/Plan review system with its nav rail + comment popout and the neobrutalist badge/shadow rules), plus the `human-notes-misc.md` "Next up" backlog churn and the `design/DESIGN.md` syncs. It closes with the **migration into `awl-cc-dash`** on 06-21: fresh git history, un-nesting `frontend/`+`sidecar/` to the root, the `tools/ → bridge/ + dev/` split and bridge-import refactor (suite green), repo config (permission allowlist, cc-exports/plans routing), and the run-up to the **sidecar driver seam #1**. (Two 06-13 entries — the v5p5–v5p9 backfills — are `[Reconstructed]`.)

**Digest — [`DEVLOG-archive-03.md`](archive/devlog/DEVLOG-archive-03.md) (2026-06-21 → 2026-06-26, 72 entries):** the working-MVP backend hardening and the big design build-out. Backend: the **sidecar driver seam** (pluggable `sdk`/`bridge` drivers + `serialize.py`) with the frontend render-path fix → live E2E; the **`archive/mvp` parity sync**; and the **bridge backend** brought to trustworthy run-state — screen-state detection, startup gates, context/turns, the permission round-trip, restart survival, and live `/model`+`/effort` controls — plus the **WT-tab opt-in** (no focus theft). Design: the **`design/` single-source refactor** (`tokens.css` as sole source of truth; `ui-concept-v9p14.html` → `mockup.html`, `design-tools.js` → `mockup-toolkit.js`; `DESIGN.md` de-versioned, forward material → `TODO.md`) and the mockup iteration **v9p14 → v1.2** (Library panel rework, Agent **Console** tab, mode toggles, behavior-wiring audit), closing with the **link-behavior refactor P0→P4** (Ultraplan removal, the inserted-block primitive, feed select-to-act, the **typed Inbox + Error type**, **Compose→Editor** with templates-as-blocks + attachment strip, the **Embed/Attach** capstone + citations + Review chip) and its stale-sweep. Housekeeping: the markdown **unwrap pass** and the DEVLOG **append-only + single-timeline** conversion.

**Digest — [`DEVLOG-archive-04.md`](archive/devlog/DEVLOG-archive-04.md) (2026-06-26 → 2026-06-30, 112 entries):** the design-decision + component-system push and the backend foundation build-out. Design: the **agent-card snippet iteration** (v1→v6, the square-card redesign) and the **messages-card** rail/blocks/multi-select sketches, then the **Next-up batch shipping** into `mockup.html` (the **A–L** and **R1–R11** rounds — feed select-to-act parity, timestamp alignment, the merged Export control, per-editor mics), the **Inbox 5-section severity ramp** (Warning added; reuse `--warning`/`--danger`, one dedicated Permission token), the **icon-fill agent-card** treatment (dark scrim → light tint → near-white glyph), and the **component-system refactor** — `data-comp`/`data-status` tags, the `gallery.html` catalog, and the **`behavior.js` extraction to the 6-file design system** (capstone). Decisions: the **Open System Decisions tracker** built and driven to completion — **OD-01…OD-24** finalized (aggregated event stream + addressing, prompt queue + hook channel, identity store, typed Inbox, notify-only caps, run-strip checklist, linking/relationship/exchanges, subagent integration, Always-allow removal, storage homes, Console adoption, Settings interactivity, Retire+Delete). Backend: the **bridge Part-1** builds (honest `set_mode`, permission-mode-at-launch, subagents endpoint, per-agent launch config, Settings registry reads, Usage aggregate, per-agent transcript via `--session-id`), the **default driver flip sdk → bridge** (live-verified through the UI), the real **three-pane UI foundation** + Settings step-into, and the **Tier-1 backend foundation** (OD-23 storage homes, OD-03 identity finish).

| Archive file | Date range | Entries | Summary |
|---|---|---|---|
| [DEVLOG-archive-01.md](archive/devlog/DEVLOG-archive-01.md) | 2026-03-26 → 2026-06-13 | 21 | Sandbox-era origin: tmux/HTTP bridges, dashboard design lineage v1→v4, the SDK architecture pivot, the FastAPI sidecar + React scaffold, and the E2E pipeline proof. |
| [DEVLOG-archive-02.md](archive/devlog/DEVLOG-archive-02.md) | 2026-06-13 → 2026-06-21 | 117 | Dashboard UI mockup lineage (v5 → v9p13) + the start of the awl-cc-dash migration (git reset, root un-nest, bridge split, repo config). |
| [DEVLOG-archive-03.md](archive/devlog/DEVLOG-archive-03.md) | 2026-06-21 → 2026-06-26 | 72 | Working-MVP backend hardening (sidecar driver seam; bridge run-state / permissions / restart; WT-tab opt-in) + the design build-out (`tokens.css` single-source refactor, mockup v9p14 → v1.2, the Console tab, and the link-behavior refactor P0→P4: typed Inbox, Editor, Embed/Attach). |
| [DEVLOG-archive-04.md](archive/devlog/DEVLOG-archive-04.md) | 2026-06-26 → 2026-06-30 | 112 | The OD-decision + component-system push (agent-card/messages-card snippets, the A–L / R1–R11 mockup batches, the Inbox 5-section ramp, icon-fill cards, the `behavior.js` 6-file system, and OD-01…OD-24 finalized) + backend bridge Part-1 / per-agent config / three-pane UI foundation / Tier-1 storage+identity. |
