# Backend Decision Integration (sidecar/ + bridge/)

Integrate into `sidecar/` and `bridge/` the **backend stream** of the resolved decision tracker — every actionable-now backend change it implies — in one coordinated pass, and leave the backend finished, verified, and live-tested. Deliver working code, not a proposal. You have full repo and system access (real laptop, real WSL2/tmux, the installed Claude build); use it.

**The tracker is your plan, not this prompt.** `archive/notes/open-system-decisions-2026-06-29.md` (archived — the decisions are now integrated into `docs/ARCHITECTURE.md` §10) holds the 23 Open Decisions (OD-01…OD-23), all resolved. Each OD's **`Decision:`** line is the contract for what to build — build from it, **never from `Recommended:`** (several `Recommended` lines now contradict their own `Decision` — OD-05 Inject, OD-17 scratchpad, OD-19 Delete — and are preserved as historical record, not instructions). This prompt points you at context, fixes the build order, and flags what's easy to get wrong; it deliberately does not restate the decisions.

## Parallel streams (read this first)

A **separate agent is integrating the design-layer (🎨) stream of this same tracker at the same time**, editing the `design/` files (a six-file design system). The two streams are **disjoint by file set and must stay that way**:

- **You own `sidecar/`, `bridge/`, and `tests/`.** Do not touch `design/` — those files are mid-edit and owned by the other agent.
- **The one shared file is `DEVLOG.md`.** It is append-only at the bottom; **re-read it from disk immediately before you append** (the other stream is appending concurrently, so an in-memory copy goes stale — a stale-read overwrite has bitten a prior session).
- **One cross-stream coordination seam — OD-03 colors.** The design stream defines the 25 `--ag-*` color tokens (names + OKLCH values) in `design/tokens.css`; your `identity.py` `AG_COLORS` must mirror those **names**. Your OD-03 backend work is the round-robin modulo + the 50-icon curation; the color token *values* are the design stream's. Mirror the names; don't invent a parallel palette.

Bare-minimum throwaway UI to exercise a backend feature is authorized (the user's stated workflow) — that is distinct from the 🎨 integration and does not violate the design hold. Keep it in `.scratch/`.

## Read first

- `archive/notes/open-system-decisions-2026-06-29.md` (archived; integrated into `docs/ARCHITECTURE.md` §10) — the authoritative plan; the OD **Decision** paragraphs (WHAT). Start with the foundation set — **OD-01 / OD-02 / OD-22 / OD-23** — and the **OD-02 spike note**.
- `CLAUDE.md` — the repo rules. The **bridge** (Custom Tooling) section, the **Testing** section, and the **DEVLOG** rule are mandatory (see Verification and Finish). Note the bridge-sessions rule: programmatic session creation never opens a terminal tab.
- `dev/notes/coverage-map.md` — "Backend reality in one screen" + the Cross-Cutting table; what's already proven vs the hard ceilings.
- The code each OD names: `sidecar/main.py` (`SessionState.to_dict`/`handle_event`/`push_event`, `stream_events`, `send_prompt` — the 409-drop, `create_session`, `answer_permission`, `/settings/*`, `/usage`); `sidecar/drivers/bridge.py` (`BridgeDriver.events` — the ~1s poll = the stream/queue/idle seam, `derive_context_usage`, `derive_subagents`, `classify_tool`, `CAPABILITIES`, the `isSidechain` skip at ~line 305, and `set_mode` — the honest 400 that is the BRIDGE-BLOCKED mid-run-permission-mode precedent); `bridge/bridge.py` (`TmuxBridge.create` — the launch-flag injection point, `status`/`_detect_state`, `send`/`keys`/`interrupt`, `read_log`, `_write_agent_config`, `mcp_sync`); `bridge/transcript.py`, `bridge/paths.py` (`win_to_wsl`/`wsl_to_win`/`WSL_AWL_DIR`), `sidecar/identity.py`, `sidecar/runtime_store.py`, `bridge/registry.py`; and for the carve-out, `sidecar/drivers/sdk.py` + `sidecar/drivers/serialize.py`.

## Foundation first — the build order is load-bearing

Most of Tier 2/3 collapses into orchestration once the foundation lands. Build in this order; do not start a rider before its foundation is green:

1. **OD-23 storage homes** + **OD-03 identity finish** (small, independent). Three data homes keyed off each agent's `cwd`; the `n mod 25` / `n mod 50` round-robin + the 50-icon curation (curate the 50 from the 167 currently auto-discovered on disk — that half is fully backend-now; the +9 color *tokens* are the design stream's, per Parallel streams above).
2. **OD-01 + OD-22 as ONE envelope** — the merged sidecar-owned SSE stream replacing the `/history` poll, with `source` + typed `recipients[]` stamped from the start. Deterministic composite `id` + a *separate* monotonic `seq`; identity-stamped; ring buffer + From/To filtering + scroll backfill against the on-disk JSONL. Build addressing in now to avoid a later migration.
3. **OD-02 push-queue** — fix the `send_prompt` 409-drop; the per-agent ordered queue (Queue/Next/Now dispositions) flushed on the proven `generating→idle` transition. Unblocks OD-04/05/06/07 and send-timing.
4. **THE OD-02 HOOK SPIKE — do this before wiring any fleet hooks** (see below).
5. Then by the tracker's sequence: OD-10 cap loop (also feeds OD-09 Warning) → OD-09; the linking chain OD-04 → OD-05/06/07/08; then the independent Tier-3 items (OD-11 checklist, OD-12 marquee, OD-13 subagent ingest, OD-15, OD-16, OD-17 write-side, OD-18, OD-19, OD-20) by appetite.

## The OD-02 hook spike — prerequisite #1, the single highest-leverage first move

One `PostToolUse` `additionalContext` spike, on **one** agent, on the **installed** Claude build (documented hook behaviors differ by build — a prior pass found a documented approach dead on a specific version), de-risks five decisions at once. Validate in one pass that an inject lands **mid-turn**. If it **passes**, ship the full hook functionality on its riders; if it **fails**, ship the graceful fallbacks — none is hard-blocked. **Do not wire the fleet hooks until the spike passes.**

The spike-gated riders and their fallbacks:
- **OD-05 Inject** → degrade to Next/Queue (transparent).
- **OD-09 Plan/Decision inbox cards** (the full detect→user-answers→agent-resumes round-trip, incl. the hook holding for the human within its timeout) → detect-and-surface + manual attach.
- **OD-17 live mid-run scratchpad push** → start-of-run injection.

The hook config is injected at `bridge.py:TmuxBridge.create` as a new launch flag alongside `--settings`/`--mcp-config`; the inbox-drain is a new sidecar endpoint returning pending injects as `additionalContext`, durable, ack-on-2xx.

## The second spike — WSL2↔Windows path normalization

Solve once as a shared utility, alongside the hook spike — it is the common dependency under OD-02 (the hook URL must be WSL2→host-reachable; `localhost` from WSL2 may not reach the host), OD-15 (side-store), OD-16 (Attach), OD-17 (scratchpad). Copy the proven pattern: the bridge's existing `mcp_sync` / `_write_agent_config` config-rewrite. Do not re-solve it per feature.

## sdk-driver carve-out

`sdk` is used for **exactly two** consumers, both in OD-16: **Revise** (scope chip Grammar·Language·Refactor, default Grammar) and **Summarize** — non-interactive utility-LLM passes via the in-process Claude Agent SDK. `SDKDriver` exists but has no utility-pass entrypoint; add one. **Nothing else reaches for sdk** — everything multi-agent (stream, queue, hooks, console, scratchpad, linking, Plan/Decision detection) is **bridge**. Do not infer sdk for OD-09.

## Exclusions — do not build these

- **PARKED — OD-21 (React port):** strategic/no-build. Exclude entirely.
- **BRIDGE-BLOCKED (do not build the blocked piece):** OD-14 mid-run permission-**mode** change (`set_mode` honestly 400s by design — only Shift+Tab cycles) and its always-allow rule-persistence (a deliberate no-build, now or ever) — OD-14 is effectively no-net-new backend; OD-15 Plan Approve/Revise/Reject → **resume-out-of-plan-mode** (no plan-mode set); OD-11 **true external completion-%** — no source in either channel, so **build the checklist self-report REPLACEMENT instead** (a system-prompt mandate + transcript-parse of done÷total).
- **Pure design (🎨) UI belongs to the other agent.** This is the backend stream only — endpoints, stores, parsers, queue, stream, hooks. The 🎨 panels/badges/controls in `design/` are out of scope.

## Guardrails (the tracker carries the detail; these are the ones not to miss)

- **Read `Decision:`, never `Recommended:`** — OD-05, OD-17, OD-19 have preserved `Recommended` lines stating the *reversed* policy. Building from them builds the wrong thing.
- **Build the serialized reply-to model explicitly** — it has no standalone OD but is the Tier-2 keystone (OD-04/05/06/07 all ride it). A **per-agent "currently-answering source" state variable**: the sidecar dispatches one queued inbound, records *which peer it's answering*, waits for idle, stamps that turn's output `recipients:[remembered-source]`. **Strict one-inbound-in-flight per agent.** This serialized inbound + reply-to is how one agent converses with multiple peers — NOT parallel per-peer threading.
- **Reply-to alone cannot START a conversation.** Proactive (non-reply) agent-to-agent sends need an explicit target via the Send-as-agent path (OD-16 + OD-22 `recipients`) — tentatively v1-deferrable; don't assume reply-to covers it.
- **OD-10 is Warning-only, full stop.** Notify-only (Continue/Raise/Stop). Auto-kill / auto-shutdown / "wind-down" is deliberately killed, not deferred — do not re-propose programmatic cap enforcement.
- **Per-agent tool scoping is DENY-based.** `--allowedTools` is ignored under bypass (a Claude bug); `--disallowedTools` / `permissions.deny` are the reliable hard-block (OD-14/OD-18).
- **Subagent live attribution is best-effort** until the result reconciles the `agentId` — the folder-watch join is a heuristic prompt↔first-message match (two near-identical-prompt subagents can mis-join before reconciliation). A `SubagentStart` hook is the cleaner later fix (build-verification-gated, same class as the hook spike).
- **Deterministic event `id` + a SEPARATE monotonic `seq`** — determinism so re-polls dedup to no-ops and reconnects replay without duplicates; assign `seq` at emit and **never parse the `id` for ordering**.
- **`generating→idle` is the single proven signal** powering idle-flush (OD-02), link fire (OD-04), and turn segmentation (OD-13 naming) — it already exists in `bridge.py:events`. Build on it; don't reinvent.
- **`design/TODO.md` is off-limits as a decision source** — it is reference-only backlog (and currently part of the parallel stream's uncommitted churn); do not resurface anything sourced from it.
- **Programmatic creation never opens a terminal tab** (the bridge-sessions rule) — fixtures, batch spawns, the sidecar driver, scratch scripts all create tab-less.

## Working style (ultracode)

The foundation is sequential (OD-23/03 → OD-01+22 → OD-02 → spike); past that the Tier-3 features are largely independent. Your files (`sidecar/`, `bridge/`) are committed and clean, so you may fan independent code lanes out as concurrent subagents in **git worktrees created from `HEAD`** and merge — use the worktree *mechanism* (only) from `dev/prompts/nextup-parallel-execution.md` (region-disjoint hunks auto-merge; isolate, verify per lane, then merge); ignore that prompt's `TODO.md`-sourced work list. Two constraints on the parallelism:

- **The main working tree has an in-flight design edit** owned by the parallel design-stream agent (`design/` is dirty/untracked). Create worktrees from `HEAD`, never touch `design/`, and don't try to carry the dirty design state into a lane.
- **Live tmux/WSL2 round-trips must serialize** — one live session at a time, in a clean throwaway dir. Parallelize the code and hermetic work; do not run live verifications concurrently across lanes.

You own the sequencing, the merges, and the final verification. Optimize for elapsed time; quality must match a careful single-agent pass.

## Verification (per CLAUDE.md, required)

Use the repo `.venv` and the existing pytest conventions, fixtures (`bridge` / `live_session` in `tests/conftest.py`), and marks (`@pytest.mark.integration` / `@pytest.mark.slow`). Run with `tests\run.ps1`.

- **Hermetic + live, both.** Add hermetic unit tests for every new pure-logic piece (the event envelope/id/seq builder, the queue dispositions, the checklist parser, the watermark/delta, the permission/error parsers, the path-normalization utility) — no live environment needed. Add live round-trips for every behavior that touches a real TUI.
- **Live bridge behavior is verified live, never asserted.** The hook spike's mid-turn-inject result, the queue's idle-flush, the link fire, subagent transcript ingest, Delete's hard wipe, the console feed/slash-runner, the sdk Revise/Summarize passes — drive each through a real session, confirm the change actually took by reading the screen / `/context` / the next turn / the on-disk files, and clean up every session you open. One live session at a time, in a clean throwaway dir.
- **Full DEBUG goes to `tests/log/`**; keep console output concise.

## Finish

- Append one `DEVLOG.md` entry per the project rule (re-read the file from disk first — the design stream is appending too): what the backend integration produced, the observable outcome, and a `Files:` line. Log before you report "done" — an unlogged change never happened.
- Report back with: which OD items landed (and to what depth), the **OD-02 hook-spike verdict** (pass→full functionality on its three riders, or fail→which fallbacks shipped), anything left as a graceful fallback or deferred (e.g. proactive Send-as-agent), the bridge-blocked pieces confirmed not built, and the test status (hermetic green with no live env; which live round-trips passed).
