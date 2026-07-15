# Stage 5 build plan — ARCHITECTURE §11 backlog (2026-07-15)

Buildable implementation plan for the Stage-5 slice of the build sprint, for the orchestrator to fan out to parallel lanes. Source of truth for each item is the ARCHITECTURE body section its §11 row points at, plus the matching `test_*_unit.py` docstring (the decided behavioral contract, §12). This plan names real files/functions verified against the tree on 2026-07-15. It plans **backend/lifecycle/Electron** only — renderer UI halves (#38–#41 and the UI sides of #23/#28/#44) belong to the renderer rebuild #37 and are noted, not planned.

## Strategy (one paragraph)

The Stage-5 set has exactly two hard serial spines and a large parallel body. The two spines are the **HIGH-priority substrate** items: **#19 per-agent git identity** (feeds #18's lineage fields, #47's automation, #48's watcher) and **#15 rewind/fork** (the Timeline anchor #16 layers on). Everything else is independently seam-able, but a majority of items add endpoints to `sidecar/main.py` and a handful touch `sidecar/drivers/bridge.py` and `bridge/bridge.py`, so the real coordination cost is **merge-conflict management on three shared files**, not logical dependency. The build therefore runs as: **Wave A** = the two HIGH anchors (#19, #15) plus #18 (defines the reserved lineage schema #19 populates) plus every independent lane that owns its own new module, launched in parallel; **Wave B** = the three dependents (#16 after #15; #47 and #48 after #19). Two items are fully isolated worktree lanes with zero shared-file risk — **#20** (Electron `frontend/` only, TypeScript) and **#49** (a standalone agent definition). Where an item adds an endpoint, the lane adds it as a **new** handler + a **new** Pydantic request model in the existing blocks so conflicts stay at the import line and the request-model cluster, resolvable mechanically. Open product calls (the #18 archive schema, the #28 destination order, the #19 synthetic-email format) are resolved here to the most doc-consistent option, marked ⚠ assumed per the sprint mandate, and never block.

## Build waves

| Wave | Items | Why here |
|------|-------|----------|
| **A — anchors + independent lanes (parallel)** | **#19** (HIGH), **#15**, **#18** (HIGH), #17, #23, #24, #28, #44, #45, #46, #20, #49 | #19 and #15 are the substrate other items ride; #18 defines the reserved lineage schema #19 fills; the rest each own a new module or an isolated surface and can run concurrently subject to shared-file coordination. |
| **B — dependents (after their anchor merges)** | **#16** (after #15), **#47** (after #19), **#48** (after #19) | Each layers directly on a Wave-A anchor's landed mechanism. |

**Serial edges (only these two):** `#16 → #15`; `#47 → #19` and `#48 → #19`. Everything else is order-free.

**Isolated worktree lanes (no shared-file risk):** #20 (frontend TS only), #49 (agent-definition file only). #28 and #45 are *nearly* isolated (one new module each; only a small `main.py` endpoint + master-table doc edit touch shared surface).

## High-conflict files (flag for the integrator)

| File | Items touching it | Conflict shape / mitigation |
|------|-------------------|------------------------------|
| [`sidecar/main.py`](../sidecar/main.py) | #15, #16, #17, #18, #23, #24, #28, #44, #45, #46 | Everyone adds a new endpoint + a new `*Request(BaseModel)`. Collisions only at the `import` block (top), the request-model cluster (~L1013–1135), and the endpoint tail. Mitigation: each lane appends its handler in a clearly-commented section; integrate #15/#18 (Wave-A anchors) first, then rebase the parallel lanes onto them. |
| [`sidecar/drivers/bridge.py`](../sidecar/drivers/bridge.py) | #19 (`_create_session`/`_build_settings`), #23 (`_build_hook_settings`), #46 (per-turn summary alongside the existing statusLine capture) | Distinct methods, but #19 and #46 both extend `_build_settings`/`_create_session`. Land #19 first (it changes the launch argv path); #46 and #23 rebase. |
| [`bridge/bridge.py`](../bridge/bridge.py) | #15 (new `rewind`/`fork` methods), #19 (`create()` argv — git env prefix) | #19 edits `create()` (L535–719, the argv/tmux-command build); #15 adds *new* methods (no `create()` edit needed). Land #19's `create()` change first, then #15 adds methods cleanly. |
| [`sidecar/library.py`](../sidecar/library.py) | #28 (import → Library doc dest), #44 (docs-at-launch attach), #45 (project-scope prompt library) | Additive new functions; low overlap. #45 mostly lives in a new module and only reads `storage.docs_dir`. |
| [`sidecar/identity.py`](../sidecar/identity.py) | #19 (synthetic-email derivation helper) | Single new function next to `assign_identity`; no conflict unless #40 (name-pool, out of Stage-5) lands concurrently. |

## Open decisions (resolved to doc-consistent leans, ⚠ assumed)

1. **#18 archive schema — distinct-IDs-in-a-table vs one-file-per-instantiation.** ⚠ **Assumed: distinct-IDs in a table**, stored as a sibling `state/archive.json` (per project, same `state/` home + write-through + atomic-write-replace model as `agents.json`). Rationale: the whole state store is a small set of JSON files written atomically per-file ([`sidecar/state_store.py`](../sidecar/state_store.py), §8.3/§8.7); one-file-per-instantiation explodes file count and fights that model, while a keyed table matches the existing roster (`agents.json`) and its retired-number persistence exactly (§8.4). Reversible/additive — an embedded-id migration to per-file is always available later.
2. **#28 destination order — which lands first.** ⚠ **Assumed: (a) agent-to-agent first** (import → prompt queue / Inbox), (b) operator read panel close behind, (c) Library doc. Rationale: the §11 #28 row records exactly this lean ("(a) first, (b) close behind"); the engine is built once with a `destination` param covering all three, so ordering is a wiring choice, not a fork. Note (b) is the operator's acute pain and is cheap to add immediately after (a).
3. **#19 synthetic-email format.** ⚠ **Assumed: `<name>-<number>@agents.awl-cc-dash.invalid`** (RFC-2606 `.invalid` TLD → guaranteed non-routable; fixed domain so "what did AI touch" = `git log --author='@agents.awl-cc-dash.invalid'`). Author name = the identity `name` (already validated to double as a git author name, §7.5) or `role-number` when unnamed.
4. **#19 per-agent attribution mechanism.** ⚠ **Assumed: env-injection at tmux launch** (`GIT_AUTHOR_NAME/EMAIL` + `GIT_COMMITTER_NAME/EMAIL` prefixed onto the claude launch command in `create()`), **not** repo-local `git config`. Rationale: many agents share one repo `.git/config`, so repo-local config collides across agents; env vars are per-process, inherited by any `git` the agent runs, and need no `.bashrc`/`WSLENV` bridge (we own the launch command string).

---

# Per-item detail

## #19 — Per-agent git identity + AI-touched index (HIGH)  [Wave A anchor]

1. **Goal:** each agent commits under its own author name + synthetic per-agent email, so "what did AI touch" is a pure git query. **HIGH.**
2. **Decided contract (§7.5, §11 #19):** per-agent git config set at bridge launch; author name doubles as the commit-author name (drawn from the validated name pool); a **synthetic per-agent email**; per-folder `index.md` files ride on top (drift risk accepted). Feeds the lineage / Agent-archive substrate (#18) and rides into #47/#48. Names in [`assets/names/agent-names.json`](../assets/names/agent-names.json) are already "validated to double safely as git commit-author names."
3. **Files / signatures:**
   - [`sidecar/identity.py`](../sidecar/identity.py) — add `git_author(identity: dict) -> tuple[str, str]` returning `(author_name, synthetic_email)` next to `assign_identity` (L96). Email per Open-decision 3.
   - [`sidecar/drivers/bridge.py`](../sidecar/drivers/bridge.py) `_create_session` (L681) — derive `(name, email)` from `self.config.identity` and pass to `create()`.
   - [`bridge/bridge.py`](../bridge/bridge.py) `create()` (L535–719) — add `git_author_name`/`git_author_email` params; in the argv/tmux-command build (L678–685) prepend `GIT_AUTHOR_NAME=… GIT_AUTHOR_EMAIL=… GIT_COMMITTER_NAME=… GIT_COMMITTER_EMAIL=…` to `claude_cmd` (shell-quoted), so the session shell exports them for any `git` the agent runs.
   - Per-folder `index.md`: a light helper (new `sidecar/agent_index.py` or a function in `storage.py`) that appends/updates an `index.md` per touched folder — lower priority, drift accepted; ship the git-identity core first.
4. **Test contract:** [`tests/test_bridge_unit.py`](../tests/test_bridge_unit.py) governs `create()` argv (it already pins `--name`/`--session-id`/`--resume` argv via scripted fakes) — extend it to assert the git env prefix appears in the launched command for a given identity. Add a hermetic unit for `identity.git_author` (name→email derivation, unnamed fallback). A live drive can extend [`tests/test_identity_rename_live.py`](../tests/test_identity_rename_live.py) to make a real commit in a throwaway WSL repo and read `git log` author back.
5. **Open decisions:** Open-decisions 3 (email format) + 4 (env-injection vs config) above.
6. **Dependencies / ordering:** none upstream. **Downstream: #18 (lineage fields), #47, #48 depend on this.** Land first in Wave A.
7. **Parallelizability:** shares `create()` in `bridge.py` with #15 and `_build_settings`/`_create_session` with #46 — **land #19's `create()` + `_create_session` edits first**, then #15/#46 rebase. Not a clean worktree lane; it is the anchor others merge onto.

## #15 — Rewind / Fork (Timeline)  [Wave A anchor]

1. **Goal:** roll an agent back to a prior message (Rewind) and branch a new agent from a chosen point (Fork/Handoff). Normal priority (but anchors #16).
2. **Decided contract (§7.19):** TUI-native path, proven end-to-end (`test_rewind_handoff_live`). **Rewind** = drive `/rewind` over tmux to restore *conversation* state to a prior prompt checkpoint (in-place, same session id). **Fork/Handoff** = `claude --resume <src> --fork-session` then `/rewind` inside the fork to the target point → a new agent via the standard Create flow with a prepopulated Create tab (§9.2). Two build caveats: (a) a conversation fork does **not** isolate filesystem state → an **explicit per-fork file-state policy** (git worktree / code-checkpoint); (b) a **≥ v2.1.191 version gate** at session create (required to rewind past a `/clear`). Transcript surgery ruled out; Python SDK lacks `resume_session_at`, so TUI-native is the only path.
3. **Files / signatures:**
   - [`bridge/bridge.py`](../bridge/bridge.py) — new methods `rewind(name, to_prompt_index)` (drive the `/rewind` menu: open, `Up`×k to "before the k-th-from-last prompt", Enter→confirm→Enter, `Ctrl-U` to clear the restored input — exact keystroke sequence documented in the `test_rewind_handoff_live` docstring L20–28) and `fork(src_name, new_name, cwd, ...)` (launch `create(..., resume_session_id=<src>)` **plus** a new `fork=True` path that adds `--fork-session`; note `create()` currently forbids `session_id`+`resume_session_id` together — fork needs `--resume <src> --fork-session` with no `--session-id`, mints a *new* id, so extend the resume branch, L637–644).
   - **Version gate:** add a `claude --version` probe (or reuse an existing version read) in `create()`/driver `start()`; refuse rewind/fork below 2.1.191 with an honest 400.
   - **Per-fork file-state policy:** implement the decided isolation — a `git worktree add` for the fork's cwd (ties to #19's per-agent identity; the fork commits under its own author) **or** a code-checkpoint; pick worktree (git-native, matches the repo's worktree tooling). ⚠ Note: `git worktree add` is an `ask`-gated command per `.claude/settings.json` — the *product* creating a worktree at runtime is distinct from a dev agent branching, but flag that the sidecar's worktree call must not trip the dev gate.
   - [`sidecar/main.py`](../sidecar/main.py) — new `POST /sessions/{id}/rewind` (body: target prompt/checkpoint) and `POST /sessions/{id}/fork` (→ returns a prepopulated Create payload); new `RewindRequest`/`ForkRequest` models in the L1013–1135 cluster. Wire through the bridge driver (add `rewind`/`fork` to `CAPABILITIES` + `base.py` optional methods).
4. **Test contract:** [`tests/test_rewind_handoff_live.py`](../tests/test_rewind_handoff_live.py) is the governing live contract (ALPHA-1/2/3 codeword observable, both Rewind and Fork). Add a hermetic unit (extend [`tests/test_bridge_unit.py`](../tests/test_bridge_unit.py)) for the `--fork-session` argv and the version-gate refusal; add a sidecar-endpoint unit (extend [`tests/test_sidecar_unit.py`](../tests/test_sidecar_unit.py)) for the 400-on-old-version and capability-gated 400.
5. **Open decisions:** file-state policy is *decided in principle* (worktree/checkpoint) but the exact worktree-vs-checkpoint pick is the build's call — ⚠ assume **git worktree** (git-native, composes with #19). Note the ask-gate interaction above.
6. **Dependencies / ordering:** none upstream (mechanism proven). **Downstream: #16 layers on this.** Prefer merging after #19 so the fork's file-state worktree commits under the per-agent identity.
7. **Parallelizability:** shares `bridge.py` (adds methods, no `create()` body edit if #19 lands first) and `main.py`. Coordinate as a Wave-A anchor.

## #16 — Handoff artifacts  [Wave B — after #15]

1. **Goal:** generate a summary/handoff report on Handoff, layered on the plain context-carry-over. Normal.
2. **Decided contract (§7.19; DESIGN.md's explicit deferral):** the plain context-carry-over ships first (#15); #16 adds a generated **summary/handoff report** artifact on top. The summary's source ties to the response-format preamble (#39/#46 — the lean is agents leading every reply with a one-liner). Ship as a dashboard-owned doc (a natural Library doc under `docs/`).
3. **Files / signatures:**
   - Generation runs on the in-process SDK utility path (like Revise/Summarize) — [`sidecar/utility_llm.py`](../sidecar/utility_llm.py) + `POST /utility/summarize` precedent (main.py L2291); add a handoff-summary variant or reuse summarize over the forked conversation prefix.
   - Persist the artifact as a doc via [`sidecar/library.py`](../sidecar/library.py) `create_document(cwd, filename, content, subdir="docs")` (L457) with provenance via `set_provenance` (L308).
   - Hook into the #15 `POST /sessions/{id}/fork` flow so the prepopulated Create payload references the generated handoff doc.
4. **Test contract:** new hermetic unit (mock the utility LLM; assert a handoff doc is written with provenance). No existing docstring governs it — a new `test_handoff_artifact_unit.py` or an extension of [`tests/test_library_unit.py`](../tests/test_library_unit.py).
5. **Open decisions:** artifact format (freeform summary vs structured) — ⚠ assume a short structured markdown (what-was-done / decisions / pending), matching the operator's TL;DR style (§7.14).
6. **Dependencies / ordering:** **after #15** (needs the fork/handoff flow to hang the artifact on). Also composes with #46 (turn summaries as source material).
7. **Parallelizability:** serial to #15; otherwise isolated (its own utility path + a Library write).

## #17 — Load past agents / on-demand resume  [Wave A]

1. **Goal:** load a past agent by name, ID, or via file explorer — on-demand per-agent resume (the missing piece; #8 cold-restore-on-startup is done). Normal.
2. **Decided contract (§9.9, §11 #17):** Fleet Setups save/load and startup auto-reconnect exist; still no **on-demand per-agent resume** endpoint or UI. The mechanism is exactly #8's cold-restore, invoked à la carte: relaunch with `claude --resume <claude_session_id>` in the agent's cwd (same conversation, same id, live-proven `test_cold_restore_live`). Past agents are enumerable from the persisted roster (`state/agents.json` via [`sidecar/runtime_store.py`](../sidecar/runtime_store.py) `all_records()` L153, which aggregates project-first across `known_projects()`).
3. **Files / signatures:**
   - [`sidecar/main.py`](../sidecar/main.py) — new `GET /sessions/past` (enumerate resumable records from `runtime_store.all_records()` — those with a `claude_session_id`, not currently live) and `POST /sessions/{record_id}/resume` (or `POST /sessions/resume` with a body carrying id/name), which rebuilds a `SessionState` from the record and starts the driver in the resume path (mirror `reconnect_sessions()` cold-restore branch, L820/1030).
   - Reuse the bridge driver's existing `resume`/cold-restore path ([`bridge/bridge.py`](../bridge/bridge.py) `resume()` L999, `create(resume_session_id=…)`); no new bridge method needed.
4. **Test contract:** [`tests/test_cold_restore_live.py`](../tests/test_cold_restore_live.py) governs the resume mechanism (same-id-vs-fork; the contract is "plain `--resume` reuses the id"). Add a hermetic sidecar unit (extend [`tests/test_sidecar_unit.py`](../tests/test_sidecar_unit.py)) for `GET /sessions/past` enumeration from seeded records + the resume endpoint dispatch (mock driver).
5. **Open decisions:** the "file explorer" load path (pick an `<id>.jsonl` directly) — ⚠ assume deferred to the renderer/UI half; the backend exposes enumerate-by-record + resume-by-id, which covers name/ID. Note the file-picker is a #37 renderer concern.
6. **Dependencies / ordering:** none (rides the done #8 mechanism). Independent Wave-A lane.
7. **Parallelizability:** touches only `main.py` (2 new endpoints) + reads `runtime_store`. Low conflict.

## #18 — Agent archive (HIGH)  [Wave A]

1. **Goal:** a roster/data-table of per-agent records, archived by default — retiring an agent is a deep-freeze, not a discard. **HIGH** ("the system is not useful without it").
2. **Decided contract (§7.12, §8.4):** archived by default; **Retire = deep-freeze** (soft, reversible: stop + archive, §7.12), **Delete stays a true delete**. Records are **light except transcripts** (referenced in place per §8.6, never copied); occasional purge acceptable. The schema **reserves lineage fields** (parent / fork / handoff), tying to per-agent git-identity attribution (#19). A separate operator-side agent explores lineage tracking + graphical display (out of scope here — reserve the fields).
3. **Files / signatures:**
   - [`sidecar/state_store.py`](../sidecar/state_store.py) — add an archive table alongside the roster: a sibling `state/archive.json` (Open-decision 1), with load/save/write-through mirroring the `agents.json` persist hooks; carry `schema_version` (§8.7, existing `SCHEMA_VERSION`).
   - [`sidecar/deletion.py`](../sidecar/deletion.py) / the Retire path — on Retire, move/copy the roster record into the archive with reserved lineage fields (`parent_id`, `fork_of`, `handoff_of` — populated by #15/#19 where available) + the per-agent git author/email (#19). Retire is soft; the transcript stays referenced in place (persisted `transcript_path`, §8.6) — never copied.
   - [`sidecar/main.py`](../sidecar/main.py) — new `GET /agents/archive` (list archived records) + `POST /sessions/{id}/retire` if a distinct retire endpoint is needed (today Retire is soft-stop; confirm whether an explicit endpoint exists — `DELETE ?hard=true` is Delete). Keep Delete's hard-wipe (§7.12) unchanged.
4. **Test contract:** [`tests/test_state_store_unit.py`](../tests/test_state_store_unit.py) governs the `state/` roster (write-through, atomic write-replace, `schema_version`) — extend it (or add `test_archive_unit.py`) to pin: archive record shape with reserved lineage fields, Retire→archive round-trip, Delete-still-wipes, reserved fields default-empty and survive reload. [`tests/test_deletion_unit.py`](../tests/test_deletion_unit.py) governs the hard-delete/tombstone side.
5. **Open decisions:** **Open-decision 1** (distinct-IDs-in-a-table `state/archive.json`, ⚠ assumed). Also: does an archived record keep appearing in the live roster? ⚠ assume **no** — archive is a separate table; the live `GET /sessions` stays live-only.
6. **Dependencies / ordering:** reserves fields #19 populates — **define the schema in Wave A; coordinate with #19** so the lineage/author fields line up. Can start immediately (fields reserved-but-empty) without blocking on #19.
7. **Parallelizability:** touches `state_store.py` + `deletion.py` + `main.py`. State-store edits don't collide with the other main.py lanes; coordinate the lineage-field names with #19.

## #23 — Workflow approval via the Inbox  [Wave A]

1. **Goal:** intercept a `Workflow` tool call and surface it as an Inbox **Review** card with an Approve/Reject round-trip. Normal (spike-proven).
2. **Decided contract (§7.3, §7.11; spike `tests/workflow_approval_probe/`):** a **PreToolUse hook on `Workflow`** fires with the full script preview in `tool_input.script` (name / description / phases recoverable), **deny aborts / allow launches**, and the **hook verdict preempts the built-in dialog** — so the dashboard can be the sole gate (the on-pane dialog stays the fallback). Surface as an Inbox **Review** card (the renamed Plans-&-Docs section) with Approve/Reject. Workflow subagents are headless/one-shot (a future Subagents tab is read-only tracking, not control); workflow editing reuses the Library editor. Card design is the design lane's (#37).
3. **Files / signatures:**
   - [`sidecar/drivers/bridge.py`](../sidecar/drivers/bridge.py) `_build_hook_settings` (L541–592) — add a `PreToolUse` matcher `{"matcher": "Workflow", "hooks": [_http("workflow")]}` alongside the existing `ExitPlanMode`/`AskUserQuestion`/`.*` matchers. Per the spike, also set `skipWorkflowUsageWarning` per-session in `_build_settings` (L627) so the built-in popup is suppressed and the hook is the sole gate.
   - [`sidecar/main.py`](../sidecar/main.py) — new `POST /internal/hooks/workflow/{agent}` (mirror `hook_plan`/`hook_decision` L1621–1632) that raises a **Review**-typed inbox card via [`sidecar/inbox.py`](../sidecar/inbox.py) `raise_item(agent, "review", data=…)` carrying the parsed `tool_input.script` preview — but, unlike plan/decision which return `{}` (allow), this hook **holds the verdict**: return `{"hookSpecificOutput": {"permissionDecision": "allow"|"deny", ...}}` based on the operator's Inbox answer. This needs a **blocking/deferred-response** pattern (the hook POST must await the operator's resolve) — the spike proved the round-trip; the build wires resolve→verdict back to the pending hook call.
   - Resolve path: extend `POST /inbox/{agent}/{item}/resolve` (L1657) so a `review` card's approve/reject completes the awaiting workflow hook.
4. **Test contract:** [`tests/workflow_approval_probe/test_workflow_approval_intercept_live.py`](../tests/workflow_approval_probe/test_workflow_approval_intercept_live.py) is the governing live spike (8/8 green; deny aborts, allow launches, hook preempts dialog, `skipWorkflowUsageWarning` honored per-session). Add a hermetic unit (extend [`tests/test_sidecar_unit.py`](../tests/test_sidecar_unit.py) + [`tests/test_inbox_unit.py`](../tests/test_inbox_unit.py)) for: the workflow hook raises a `review` card carrying the script preview, and resolve→verdict maps approve→allow / reject→deny.
5. **Open decisions:** the deny→abort blocking pattern (how long the hook POST waits) — ⚠ assume a bounded await with a timeout that falls back to the on-pane dialog (the documented fallback). The `review` card type string ("Review") — ⚠ assume `"review"` (§7.8's type set is open-ended, stored as a string).
6. **Dependencies / ordering:** none. Independent Wave-A lane.
7. **Parallelizability:** touches `drivers/bridge.py` (`_build_hook_settings`/`_build_settings` — coordinate with #19/#46) + `main.py` (new hook endpoint + inbox resolve edit) + `inbox.py`. Moderate; the hook-settings edit is small and localized.

## #24 — Queue awareness  [Wave A]

1. **Goal:** for >2 linked agents, share in message front matter that another agent's message is queued, so an agent can decide whether to wait. Normal.
2. **Decided contract (§7.3, §7.6):** when more than two linked agents interact, the delivered message's **front matter** advertises that another agent's message is already queued for the recipient — enough for the receiving agent to choose to wait rather than answer stale. Rides the existing prompt-queue (§7.3, disposition-ordered `SessionState.prompt_queue`) and link delivery (§7.6).
3. **Files / signatures:**
   - [`sidecar/main.py`](../sidecar/main.py) `_flush_queue` (L373) / the link-relay path `_maybe_relay_reply` (L452) and `_fire_shared_context` (L623) — when enqueuing a link-delivered message, inspect the target's `prompt_queue` depth and, if >0 other queued items exist, prepend a front-matter note (attributed block, like the Piggyback park block in [`sidecar/links.py`](../sidecar/links.py)).
   - Likely a small helper in [`sidecar/links.py`](../sidecar/links.py) to format the front-matter line.
4. **Test contract:** [`tests/test_links_unit.py`](../tests/test_links_unit.py) governs link relationships/exchange counting; extend it (or [`tests/test_sidecar_unit.py`](../tests/test_sidecar_unit.py)) to assert: with ≥2 items queued for a target, a link delivery carries the "another message is queued" front matter; with ≤1, it does not.
5. **Open decisions:** exact front-matter wording/threshold — ⚠ assume the ">2 linked agents" condition = "target already has ≥1 queued item from a different source." Additive, tune later.
6. **Dependencies / ordering:** none. Independent Wave-A lane.
7. **Parallelizability:** touches `main.py` flush/relay path + `links.py`. Low endpoint conflict (no new endpoint); coordinate the `_flush_queue` edit region.

## #28 — Import external Claude context  [Wave A]

1. **Goal:** wrap the working exporters behind a sidecar import module + a thin frontend Import control, pulling an outside Claude session in by title. Normal.
2. **Decided contract (§7.3, §7.16, §8.6):** the extractors already exist — [`dev/tools/claude-context-extractor/`](../dev/tools/claude-context-extractor/) (`extract-web.py`, `extract-desktop.py`, both list via `--list` and export by title via `--name`). **One engine, one selectable destination:** (a) agent-to-agent (prompt queue / Inbox — operator's primary interest); (b) operator-facing read panel (the acute pain today); (c) Library reference doc. Distinct from §8.6 (agents' *own* transcripts). Open operator calls (non-blocking): destination order and which panel hosts Import.
3. **Files / signatures:**
   - New module `sidecar/import_context.py` — `list_external(source: "web"|"desktop") -> list[dict]` and `import_by_title(source, title, destination, target_agent=None) -> dict`, calling the extractor functions (e.g. web `cmd_list`/`resolve_name`/`cmd_fetch` in [`dev/tools/claude-context-extractor/extract-web.py`](../dev/tools/claude-context-extractor/extract-web.py); desktop reads on-disk). Add the tool dir to `sys.path` and import, or shell out to the scripts (they're stdlib-only; importing is cleaner but the scripts are CLI-shaped — ⚠ assume shell-out to reuse them verbatim, capturing the rendered markdown).
   - Destinations: (a) → enqueue on the target agent's `prompt_queue` / raise an Inbox card ([`sidecar/inbox.py`](../sidecar/inbox.py)); (b) → return the rendered markdown for a read panel; (c) → `library.create_document(cwd, filename, content, subdir="docs")`.
   - [`sidecar/main.py`](../sidecar/main.py) — new `GET /import/external?source=` (list) + `POST /import/external` (body: source, title, destination, target_agent) + an `ImportRequest` model.
4. **Test contract:** no existing docstring — add `test_import_context_unit.py` (mock the extractor call; assert each destination routes: (a) enqueues on the agent, (b) returns markdown, (c) writes a Library doc). Keep it hermetic (no network — mock the extractor).
5. **Open decisions:** **Open-decision 2** (destination order — ⚠ (a) first, engine covers all three). Which panel hosts Import → renderer (#37) concern; backend is destination-agnostic.
6. **Dependencies / ordering:** none. Nearly-isolated lane (one new module + one small `main.py` addition + one `library.py`/`inbox.py` reuse).
7. **Parallelizability:** mostly a new module; only the `main.py` endpoint touches shared surface. Good parallel lane.

## #44 — Docs in agent context (light)  [Wave A]

1. **Goal:** a curated docs home agents are pointed at (the Library) + per-agent doc attachment at launch. Normal (automatic relevance-retrieval stays §10 #6).
2. **Decided contract (§7.16, §10 #6):** the **Library is the hub** of curated docs; **per-agent doc attachment at launch** points an agent at chosen docs. Automatic relevance-retrieval is explicitly out of scope (§10 #6). Operator interface sketch (design-lane): Library reuses the review-panels' nav-rail lens pattern, organized by task/project/subproject.
3. **Files / signatures:**
   - [`sidecar/drivers/bridge.py`](../sidecar/drivers/bridge.py) `_build_settings` (L627) / `_create_session` (L681) — inject chosen doc references into the agent's launch (e.g. a system-prompt preamble listing attached doc paths, or an appended context block). The doc set comes from per-agent launch config.
   - [`sidecar/main.py`](../sidecar/main.py) `CreateSessionRequest` (L1022) + `DriverConfig` ([`sidecar/drivers/base.py`](../sidecar/drivers/base.py) L43) — add an `attached_docs: list[str]` field, persisted into `state/agents.json` (the roster carries per-agent launch config, §8.2/§8.4).
   - [`sidecar/library.py`](../sidecar/library.py) — resolve attached doc paths (WSL-reachable) for the agent to open.
4. **Test contract:** extend [`tests/test_library_unit.py`](../tests/test_library_unit.py) (doc resolution) + a hermetic unit for the launch-config carry (attached_docs persists into the record and materializes into the launch preamble). No existing docstring names this — add to the library or a small new unit.
5. **Open decisions:** attachment mechanism (system-prompt preamble vs `@`-path injection vs MCP) — ⚠ assume a **system-prompt preamble listing WSL doc paths** (simplest; automatic retrieval is deferred per §10 #6). State this is the "light" v1.
6. **Dependencies / ordering:** none. Independent lane.
7. **Parallelizability:** touches `drivers/bridge.py` (launch config — coordinate with #19/#23/#46), `base.py` config, `main.py` request model, `library.py`. Moderate; the launch-config additions cluster with other driver edits.

## #45 — Prompt / UI-text markdown library (scope-aware)  [Wave A]

1. **Goal:** one human-editable markdown prompt library as the single home for every UI-injected/canned text the dashboard sends on the user's behalf. Normal.
2. **Decided contract (§7.14, §8.2, §8.4):** the single home for all UI-injected/canned text — post-reviewer-request instructions, the reviewer-request **Send** and Library **Revise** texts, Compose **snippets + templates**, the **Revise scope chip** and **Response (Structure)** options, the Team Feed **Summarize** action. Format: markdown with the `##` group / `###` item convention (JSON only where placeholder fill-in needs it), organized by purpose (`responses.md`, `snippets.md`, `actions.md`). **Two scopes:** a **System copy** (persistent cross-project store — the lean is `~/.claude` for shared runtime docs) + a **Project copy** (`<project>/.awl-cc-dash/`, §8.2). Includes adding these doc types to the **§8.4 master table** (do this via a DEVLOG/doc note — this plan must not edit ARCHITECTURE.md; flag the master-table addition for a doc pass).
3. **Files / signatures:**
   - New module `sidecar/prompt_library.py` — load/resolve the markdown library across the two scopes (System `~/.claude/awl-cc-dash/prompts/` ⚠ assumed path, Project `<project>/.awl-cc-dash/docs/prompts/`), parse the `##`/`###` convention, resolve an item by group+key with project-overrides-system precedence.
   - [`sidecar/main.py`](../sidecar/main.py) — `GET /prompt-library?scope=` + `POST /prompt-library` (write a scoped item, confirm-gated like settings). Reuse [`sidecar/settings_io.py`](../sidecar/settings_io.py) write primitives for the confirm gate.
   - Consumers (Compose snippets, Revise/Summarize canned text) read via this module instead of hardcoded strings — refactor the existing hardcoded UI-text sends to read from here (scope-aware).
   - **Master table (§8.4) addition** — flag for the doc-owner (not edited here per the task constraint).
4. **Test contract:** no existing docstring — add `test_prompt_library_unit.py` (hermetic: parse the `##`/`###` markdown, System/Project scope resolution + project-overrides-system precedence, missing-item fallback). [`tests/test_settings_io_unit.py`](../tests/test_settings_io_unit.py) governs the confirm-gated write primitives it reuses.
5. **Open decisions:** the System-scope path — ⚠ assume `~/.claude/awl-cc-dash/prompts/` (the §11 #45 lean is "`~/.claude` for shared runtime docs"). File names `responses.md`/`snippets.md`/`actions.md` are decided.
6. **Dependencies / ordering:** none. Nearly-isolated lane (new module + a small `main.py` endpoint + refactoring hardcoded strings to read from it).
7. **Parallelizability:** mostly self-contained; the string-refactor touches whatever currently hardcodes UI-text (grep for the reviewer-request/Revise strings). Good parallel lane; coordinate only the `main.py` endpoint add.

## #46 — Per-turn settings + summary capture  [Wave A]

1. **Goal:** capture, per Timeline turn, the agent's settings at that turn (model + mode/effort/thinking) and a concise one-line turn summary. Normal (feeds #15 and #39).
2. **Decided contract (§7.19, §7.14):** per Timeline turn, capture (1) the agent's **settings at that turn** (model + mode/effort/thinking) and (2) a **concise one-line turn summary**, so Timeline rows render a settings string + summary and collapsed Team Feed / History cards show a one-line preview. The summary's source ties to the response-format preamble (#39) — the lean is agents leading every reply with a one-liner. **This is the capture/storage side; display is the design lane's (#37).**
3. **Files / signatures:**
   - Settings-at-turn: the per-turn statusLine capture already exists ([`sidecar/drivers/bridge.py`](../sidecar/drivers/bridge.py) `_build_statusline_settings` L594 → `statusline.jsonl`, read by `get_statusline_snapshot` L1042). Extend the captured payload (or a sibling capture) to also record model + mode/effort/thinking per turn. The arbiter ([`sidecar/runstate.py`](../sidecar/runstate.py)) already tracks `permission_mode` per event — join it at the turn boundary.
   - Turn summary: derive the one-line summary from the assistant text's leading line (the #39 preamble lean — "agents lead every reply with a one-liner"); parse it in the driver's `events()` at the idle/turn boundary (like the checklist parser rides the stream).
   - Storage: per §8.3 this is **derived** where possible (recomputable from transcripts) — but the settings-at-turn snapshot is not in the transcript, so persist it thin (a per-agent `turns.jsonl` in the launch-config dir, mirroring `statusline.jsonl`, or a `state/` overlay keyed by anchor id per §8.6's overlay-index principle).
   - Expose via `GET /sessions/{id}/context` (`per_turn` field precedent, main.py L2585) or a new `GET /sessions/{id}/timeline`.
4. **Test contract:** [`tests/test_readouts_unit.py`](../tests/test_readouts_unit.py) governs the readout surfaces (#30/#31/#32 — the statusLine per-turn capture is #31); extend it for the settings-string + one-line-summary capture. [`tests/test_settings_io_unit.py`](../tests/test_settings_io_unit.py) if the settings string reuses those readers.
5. **Open decisions:** summary source when the agent does *not* lead with a one-liner (pre-#39) — ⚠ assume a fallback of the first sentence of the turn's assistant text; the clean source arrives with #39.
6. **Dependencies / ordering:** none upstream (independent capture). **Feeds #15's Timeline rows and #39's preamble** — but builds independently. Coordinate the `_build_settings`/`_create_session` edit region with #19.
7. **Parallelizability:** touches `drivers/bridge.py` (capture, alongside the existing statusLine) + a readout endpoint. Coordinate driver edits with #19/#23/#44.

## #47 — Git automation  [Wave B — after #19]

1. **Goal:** handle and semi-automate Git tasks, including commits. Normal (rides #19's per-agent identity).
2. **Decided contract (§11 #47):** semi-automate git tasks (commits, etc.) on top of #19's per-agent attribution — with #19 in place, an agent's commits are already authored correctly, so #47 is the automation surface that triggers/stages them.
3. **Files / signatures:**
   - A git-automation surface driven through the bridge (an agent runs `git` in its cwd, inheriting #19's `GIT_AUTHOR_*` env). Likely a `sidecar/main.py` endpoint `POST /sessions/{id}/git` (action: commit/status/…) that routes a `git` command via the bridge's `send`/`keys` or a direct `_run`, plus an optional agent/skill definition for the "commit this work" flow.
   - Reuse [`bridge/bridge.py`](../bridge/bridge.py) `_run` for non-interactive git in the agent's cwd.
4. **Test contract:** no existing docstring — add a hermetic unit for the endpoint's command construction + a live drive (throwaway WSL repo, assert a commit lands with the #19 author). Ties to the #19 live test.
5. **Open decisions:** how much automation is "semi" (auto-commit cadence vs operator-triggered) — ⚠ assume **operator-triggered** commits first (safest), auto-cadence deferred.
6. **Dependencies / ordering:** **after #19** (attribution must exist first). Wave B.
7. **Parallelizability:** serial to #19; otherwise a small `main.py` endpoint + bridge reuse.

## #48 — Change-log watcher  [Wave B — after #19]

1. **Goal:** an agent that watches codebase changes and auto-updates change logs (or similar). Normal (rides #19).
2. **Decided contract (§11 #48):** a watcher agent that observes codebase changes and keeps a change log current. Rides #19 (attribution) — the log can attribute changes to the per-agent git identity.
3. **Files / signatures:**
   - Primarily an **agent definition** (`.claude/agents/` in the running project or a product-provided agent) plus a light sidecar trigger. Uses git (the #19 author query `git log --author='@agents.awl-cc-dash.invalid'`) to enumerate AI-touched changes and write a change-log doc via [`sidecar/library.py`](../sidecar/library.py) `create_document`.
   - Optional: a file-watch trigger (reuse the subagents' folder-watch pattern) — but the simpler v1 is an on-demand agent run.
4. **Test contract:** new hermetic unit for the change-log write (mock git output → assert a doc is written). Light coverage.
5. **Open decisions:** watch mechanism (live file-watch vs on-demand/scheduled run) — ⚠ assume **on-demand/scheduled agent run** first; live-watch deferred.
6. **Dependencies / ordering:** **after #19** (uses the author query). Wave B.
7. **Parallelizability:** mostly an agent definition + a Library write; low shared-file risk.

## #49 — System-check agent  [Wave A — isolated]

1. **Goal:** a system-checking agent that's easy to run. Normal.
2. **Decided contract (§11 #49):** an easy-to-run agent that checks system health (WSL/tmux/sidecar/bridge/auth reachability, etc.). The pieces it checks already exist as sidecar probes — §7.2's tmux/WSL liveness probe, `/health`, the bridge-path `claude -p` auth check (§6.4).
3. **Files / signatures:**
   - Primarily an **agent-definition file** (a product-provided or `.claude/agents/` agent) that runs the existing checks and reports. Optionally a `GET /system-check` endpoint in [`sidecar/main.py`](../sidecar/main.py) aggregating the existing probes (health, the System-identity liveness probe, auth-expiry from `settings_io.account_band_split`).
4. **Test contract:** light — a hermetic unit for the aggregation endpoint if added (mock the probes). Mostly a definition file.
5. **Open decisions:** agent-only vs agent+endpoint — ⚠ assume **agent + a thin `GET /system-check` aggregation** (reuses built probes; makes "easy to run" real).
6. **Dependencies / ordering:** none. Fully isolated lane.
7. **Parallelizability:** isolated worktree lane (a new agent file + at most one aggregation endpoint).

## #20 — One-click launch: Electron-main sidecar lifecycle  [Wave A — isolated]

1. **Goal:** port the Python-modeled spawn/supervise/shutdown lifecycle into Electron main, so one click launches everything (`.bat` becomes the fallback). Normal.
2. **Decided contract (§2, §4.1, §11 #20):** Electron main owns sidecar **spawn / supervise / shutdown** with **detach-on-close** — the lifecycle is proven, modeled in Python (`test_oneclick_launch_live`). Port it into Electron main: own the venv path and shutdown ordering, **preserving detach-on-close of running tmux agents through the §3.4 close dialog** (Close = detach, Close & stop = graceful stop). Crash/restart supervision stays deferred per §2's manual-relaunch posture — include only if unattended operation matters. **Fallback if the port hits a wall:** the `.bat` two-process launch stays the shipped model. The Electron main-process shell is explicitly **not** frozen (CLAUDE.md — only the React renderer is), so this is buildable now.
3. **Files / signatures:**
   - [`frontend/src/main/index.ts`](../frontend/src/main/index.ts) — spawn the sidecar as a supervised child (`child_process.spawn` of the repo `.venv` python running uvicorn on `:7690`), own its shutdown ordering, and wire the §3.4 close semantics so closing the window detaches (leaves tmux agents running) vs graceful-stops. Read-back parity with `reconnect_sessions()` on respawn (the spike's Read-back B).
   - Model exactly what `test_oneclick_launch_live` does (spawn-as-child, kill on close, respawn on reopen, assert the tmux agent survives + reconnects).
   - Keep [`start-dashboard.bat`](../start-dashboard.bat) as the documented fallback.
4. **Test contract:** [`tests/test_oneclick_launch_live.py`](../tests/test_oneclick_launch_live.py) **is** the lifecycle contract (Read-back A: tmux agent survives the sidecar child's death; Read-back B: respawned sidecar's `reconnect_sessions()` rebinds it). There is **no pytest for Electron** — the venv can't run a Node/Electron POC (the spike docstring says so explicitly). Verification is: the Python spike stays green as the contract, plus a **manual Electron drive** (launch, close-detach, reopen-reconnect, close-and-stop). "The sidecar process started" is explicitly NOT a pass — the two survival read-backs are.
5. **Open decisions:** include crash-restart supervision now or defer — ⚠ assume **defer** (§2's manual-relaunch posture; add only if unattended operation matters).
6. **Dependencies / ordering:** none. Fully isolated.
7. **Parallelizability:** **the cleanest isolated worktree lane** — TypeScript in `frontend/src/main/` only, zero Python-file overlap with any other Stage-5 item.

---

## Test-tier note

Per [`tests/README.md`](../tests/README.md): the **hermetic unit tier** (no marker, no WSL) is the everyday net — every new endpoint/module gets a hermetic unit. The **live tier** (`integration`/`slow`) proves the bridge end-to-end and is opt-in; the governing live spikes here (#15 `test_rewind_handoff_live`, #17 `test_cold_restore_live`, #20 `test_oneclick_launch_live`, #23 the workflow_approval_probe, #19 an extension of `test_identity_rename_live`) already exist as contracts. Follow the isolation rules those files document (own `TmuxBridge()`, unique session names, never `tmux kill-server`, tab-less `show=False`) for any new live drive.
