Finish the backend tmux path. Prompt A landed the foundation (trustworthy run-state, startup-gate clearing, transcript-derived context and turns, with hermetic and live tests green). This pass wires the three remaining capabilities the dashboard needs: surfacing and answering permission prompts, surviving a sidecar restart, and changing model/mode/effort/fast/thinking mid-session. When this is green, the backend path is finished.

Orient first. Read the bridge section of CLAUDE.md, then the code A actually landed: `bridge/bridge.py` (`_detect_state`, `_clear_startup_gates`, `status`, `read`, `resume`), `sidecar/drivers/bridge.py` (the `BridgeDriver`, `_STATE_TO_STATUS`, `derive_context_usage`), `sidecar/main.py` (the `SessionState`, `handle_event`, the `/model` and `/mode` endpoints, and the already-present-but-unwired `pending_permission` field and `has_pending_permission` flag), and `sidecar/drivers/base.py` (the driver contract). Read A's most recent DEVLOG entry for what changed. The full evidence for the facts below is in `.scratch/bridge-diagnostic-20260623-231218.md`; read it now, and treat it as read-now reference, not a durable dependency, since it is a transient scratch file.

What is already proven (build on these as fact):

1. Permission is now a real stop-state. `_detect_state` returns `permission_prompt` only on the genuine menu marker (a "Do you want ...?" question plus a numbered "1. Yes" option). The menu looks like: a "Do you want to <action>?" line, then "1. Yes", "2. Yes, allow all edits during this session", "3. No", and an "Esc to cancel" hint. Answering is proven: approve with `keys("Enter")` (selects the default option 1), deny with `keys("Escape")` (yields "User rejected"). Option 2 (always-allow) was NOT verified in the diagnostic; treat it as live-verify-only, never assert it.

2. Restart survival is proven. A brand-new `TmuxBridge()` instance calling `resume(name)` reconnects to the still-alive tmux session, and `read_log()` and `status()` work on it. The session and its transcript outlive the process that created them.

What is NOT yet proven (discover before wiring):

3. The five session-control interactions (model, permission mode, effort, fast, thinking) were never tested. The design names slash commands (`/model`, `/effort [low|medium|high|max|auto]`, `/fast [on|off]`) and the bypass-gate text mentioned "shift+tab to cycle" for permission mode, but whether each is a slash-with-argument, an interactive picker needing navigation keys, or a shift+tab cycle is unconfirmed. Treat those as hypotheses to verify live, not facts.

Do, in `bridge/bridge.py`:

- Add a permission-detail capture. A real edit prompt renders a multi-line diff preview above the question, and `status()` currently reads only 15 lines, so the "Do you want" line can fall outside the window while the menu stays at the bottom. Read enough lines (comfortably more than 15) when a permission prompt is in play so both the question and the full menu are captured, and anchor detection on the menu options being present at the bottom so stale "Do you want" text in older scrollback cannot false-fire. Add a pure parser that turns a captured permission screen into structured-enough detail: the question text and the list of menu options (label per option), plus the raw captured block. Keep it a pure function (no live session) so it is hermetically unit-testable, mirroring how `_detect_state` is tested.

Do, in `sidecar/drivers/bridge.py`:

- Surface permission as a distinct event, not as `running`. When the detector enters `permission_prompt`, emit a `permission_request` event carrying the parsed detail (question, options, raw block) instead of silently mapping it to `running` in `_STATE_TO_STATUS`. When the state leaves `permission_prompt` (back to generating or idle, by any means including the user answering in the terminal directly), emit a clear so stale pending state cannot linger.

- Add an answer path. A method that approves via `keys("Enter")` and denies via `keys("Escape")`, against the proven keys above. Include always-allow only if you confirm option 2 live; otherwise omit it and report that.

- Wire restart survival. Persist a minimal record per session on create (the sidecar session id, the tmux session name, and the config: model, permission mode, cwd) to a gitignored runtime file the sidecar owns. Give the driver a resume-or-create start path so it can bind to an existing tmux session by name via `resume()` rather than always generating a fresh name and creating. Remove the record on close.

- Wire the five session-control commands. For each of model, permission mode, effort, fast, and thinking: first discover the exact live interaction (drive it through a real session, confirm the change actually took by reading the screen or `/context` or the next turn's behavior), then implement the driver method to perform it, preferring to extend the existing `set_model` and `set_mode` contract and adding the minimum for effort/fast/thinking. Capability-flag each one that works. If a given control cannot be driven cleanly, leave it unimplemented and report exactly what you found, rather than forcing a fragile sequence.

- Update `CAPABILITIES` to reflect what is actually wired (it currently has `interrupt` and `context`).

Do, in `sidecar/main.py`:

- Handle `permission_request` in `handle_event`: set `session.pending_permission` to the detail and push the event so `has_pending_permission` flips true. Clear `pending_permission` on the driver's clear event. Leave the status enum untouched; the design's "pending" reads off the `has_pending_permission` flag, not a new status value.

- Add a POST endpoint to answer a pending permission (approve or deny; always-allow only if it was confirmed live). It calls the driver's answer path and clears `pending_permission`.

- Add control endpoints for effort, fast, and thinking following the existing `/model` and `/mode` pattern (each gated on `driver.supports(...)`), for whichever controls got wired.

- On startup, read the runtime record file and reconnect: for each record whose tmux session is still alive, rebuild the session state and a resumed driver bound to that tmux name, and resume event pumping; prune records whose tmux session is gone.

Do, for persistence: add the runtime record file to `.gitignore` and keep it out of the repo tree (a sidecar-owned runtime location, not `.scratch`).

Do, in the tests:

- In `tests/test_tmux_bridge.py` (or a sibling live file if cleaner), add live round-trips: an approve (send a prompt that triggers an approval-gated action in default permission mode in a clean throwaway dir, observe the `permission_request` / pending state, answer approve, confirm the action completed), a deny (same setup, answer deny, confirm rejection and that the action did not happen), and a resume-after-simulated-restart (create, send a turn, build a fresh bridge and driver, resume by name, confirm history and state survive). Permission tests must run in default prompting mode, not bypass, so a prompt actually appears.

- In `tests/test_bridge_unit.py`, add hermetic tests for the permission-detail parser, including the long-diff case where the question sits well above the menu, and for any other new pure logic. These carry neither the integration nor the slow mark.

Constraints:

- Preserve everything you are not explicitly changing, in every file; carry untouched code forward exactly. Run one session at a time in a clean throwaway directory for any live test, and close every session you open.

- Do NOT build subagent sidechain detection (deferred to its own future task) or any cost/result event (per-agent cost is out of scope by design; turns already derive from the transcript). If you reach for them, stop.

- Use the repo `.venv`, the existing `bridge` and `live_session` fixtures and pytest conventions in CLAUDE.md, and append a DEVLOG entry when done.

Done, in two tiers. MUST land, fully working and tested live: the permission round-trip (a distinct event sets the pending flag, and a POST approve and a POST deny both work end to end via the proven keys) and restart survival (a resumed sidecar reconnects to a live tmux session with history and state intact). SHOULD land: the session-control commands, wired for each control whose interaction you discovered and confirmed, with a clear report of any you could not drive cleanly. All hermetic tests pass with no live environment, and the live tests pass. If any MUST-land piece cannot be made to work, stop and report it rather than papering over it; do not fake-complete a control whose interaction you could not verify.