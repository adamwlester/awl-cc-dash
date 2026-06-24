Fix the backend tmux path so it streams a turn with trustworthy run-state, clears the startup gates, and reports context and turns, then lock it in with a passing test. This is the foundation pass. A later pass adds permission approval, model/mode switching, and restart-survival wiring, so do NOT build those here.

Orient first: read the bridge section of CLAUDE.md, then `bridge/bridge.py` (`_detect_state`, `create`, `status`, `wait_idle`), `sidecar/drivers/bridge.py`, and `sidecar/drivers/base.py`. The full evidence for everything below is in `.scratch/bridge-diagnostic-20260623-231218.md`; read it now, and treat it as read-now reference rather than a durable dependency since it is a transient scratch file. The diagnostic already proved every capability works at the bridge level, so this pass wires the proven pieces through; it does not rediscover them.

Four load-bearing facts from the diagnostic:

1. Run-state is broken because `_detect_state` reads the empty input line (which always matches its idle regex) and discards the bottom status-bar line where the real signal lives. The reliable distinction is in the status bar: "esc to interrupt" means generating, "? for shortcuts" means idle. Permission is currently decided by naive substring matching over the whole pane and false-fires on innocent text (a prompt containing the word "permission", or the `/context` skill name "fewer-permission-prompts" on an idle screen), so a real prompt must be confirmed by the menu marker ("Do you want" plus a numbered "1. Yes" option), not loose keywords.

2. Launching in a fresh or untrusted directory shows a folder-trust gate ("1. Yes, I trust this folder / 2. No, exit", where Enter accepts option 1) before the first turn, and no flag skips it. Launching with `--dangerously-skip-permissions` additionally shows a bypass-mode gate whose default highlight is "1. No, exit" (pressing Enter blindly kills the session); accept it with `keys("2")` then `keys("Enter")`. `create()` must clear whichever of these gates appears after launch, before reporting the session ready.

3. Overall context percent and turn count derive from the transcript with no `/context` call: assistant entries carry `message.usage` with `input_tokens`, `cache_read_input_tokens`, and `cache_creation_input_tokens`; context tokens are the sum of those three on the latest assistant entry, over a 1,000,000 window. Turn count is the number of `user` entries whose `content` is a plain string (real prompts), excluding the ones carrying tool_results.

4. Claude Code 2.x renders ghost-suggestion text in the empty input box, so never infer idle from a quiet input line; rely on the status-bar marker.

Do, in `bridge/bridge.py`:

- Rewrite `_detect_state` to read the status-bar line for generating-versus-idle and to require the menu marker for `permission_prompt`, eliminating both the false idle-during-generation and the keyword false-positives.

- Make `create()` clear the startup gate or gates after launch (folder-trust always, bypass-mode when present) using the exact keys above, then wait for the genuine idle prompt before returning.

Do, in `sidecar/drivers/bridge.py`:

- Confirm the driver reports running during a turn and idle after, off the fixed detection (the existing status poll is fine once `_detect_state` is correct).

- Add context and turns: implement `get_context_usage()` to return the derived overall context (tokens and percent) and the turn count from the transcript, and add "context" to `CAPABILITIES` so the existing `/context` endpoint serves it. Put the pure derivation math in a small standalone helper so it can be unit-tested without a live session.

Do, in the tests:

- Add hermetic unit tests for `_detect_state` (no WSL needed) using representative captured screens: a generating screen (status bar shows "esc to interrupt"), an idle screen, a real permission screen with the menu, and the two false-positive cases (a prompt containing "permission" or "approve" while generating, and the "fewer-permission-prompts" skill name on an idle screen). They must assert the correct state and must NOT carry the integration or slow marks, so place them where they run without a live environment.

- Add a hermetic unit test for the context-and-turns derivation helper using the `usage` shape above.

- In `tests/test_tmux_bridge.py`, tighten the live state assertions so a turn actually observes generating during generation and idle after (the current asserts are loose enough to pass the old bug), and add a check that a session created in a fresh untrusted dir comes up to idle (gate cleared) rather than hanging.

Constraints:

- Scope is the foundation only. Do NOT wire permission approve/deny, model or mode switching, resume-based restart recovery, or subagent sidechain scanning; those are the next pass. If you reach for them, stop.

- Preserve everything you are not explicitly changing, in every file. Run one session at a time in a clean throwaway directory for any live test. Use the repo `.venv` and the existing `bridge` and `live_session` fixtures, follow the pytest conventions in CLAUDE.md, and append a DEVLOG entry when done.

Done = the hermetic `_detect_state` and derivation tests pass with no live environment, and a live `test_tmux_bridge.py` run shows a turn streaming with correct generating-then-idle state and a session coming up clean in a fresh directory. If any single piece cannot be made to work, stop and report it rather than papering over it.