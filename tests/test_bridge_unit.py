"""Hermetic unit tests for the bridge run-state detector and context derivation.

These tests are pure: no WSL2/tmux, no live model, no network. They run
anywhere and therefore carry NEITHER the ``integration`` nor the ``slow`` mark,
so a plain ``pytest tests/test_bridge_unit.py`` works with no live environment.

Two things are covered:
  * ``TmuxBridge._detect_state`` — reads the bottom status bar, distinguishes
    generating vs idle, and requires the menu marker for a permission prompt
    (no more keyword false-positives).
  * ``derive_context_usage`` — overall context tokens/percent and turn count
    derived from transcript ``message.usage``, no ``/context`` call.

Screens below are representative captures matching the layout the diagnostic
recorded (see .scratch/bridge-diagnostic-*.md appendix A4/A5/A6).
"""

from bridge.bridge import TmuxBridge
from sidecar.drivers.bridge import derive_context_usage, CONTEXT_WINDOW


# -----------------------------------------------------------------------------
# Representative captured screens
# -----------------------------------------------------------------------------

# A turn is running, bypass mode: the status bar shows "esc to interrupt". The
# empty ❯ input line is still present (and would fool a lone-❯ heuristic).
GENERATING_SCREEN = """\
● Let me work through that.

✶ Flibbertigibbeting… (12s · ↓ 1.2k tokens)
──────────────────────────────────────────────
❯ \xa0
──────────────────────────────────────────────
  ⏵⏵ bypass permissions on (shift+tab to cycle) · esc to interrupt
"""

# A turn is running, normal mode (real capture): the only generating signal is
# the spinner glyph line "✻ Percolating…". "esc to interrupt" is clipped/reworded
# and the empty ❯ box + "← for agents" status bar look exactly like idle.
GENERATING_NORMAL_MODE = """\
● A History of Unix Terminal Multiplexers

  In the early days of Unix, a user sat at a physical terminal wired to a single
✻ Percolating… (2s · thinking)
────────────────────────────────────────────────────────────────────────────────
❯ \xa0
────────────────────────────────────────────────────────────────────────────────
  ← for agents                                                ● high · /effort
"""

# Idle: the input prompt box is rendered and there is no "esc to interrupt".
# Note the status bar here shows "← for agents · ● high · /effort" — NOT
# "? for shortcuts" (that hint rotates and is dropped at narrow widths). This is
# a real capture; the old detector wrongly returned "unknown" for it.
IDLE_SCREEN = """\
● Done.

────────────────────────────────────────────────────────────────────────────────
❯ \xa0
────────────────────────────────────────────────────────────────────────────────
  ← for agents                                                ● high · /effort
"""

# Completed turn (real capture): the response is committed and Claude Code
# leaves a summary line "✻ Cooked for 1s" that REUSES the spinner glyph but has
# NO ellipsis. The turn is done → idle, not generating. (Regression: requiring
# the ellipsis on the spinner line is what prevents this false "generating".)
COMPLETED_TURN_SCREEN = """\
❯ Reply with exactly: CTX_OK

● CTX_OK

✻ Cooked for 1s

────────────────────────────────────────────────────────────────────────────────
❯ \xa0
────────────────────────────────────────────────────────────────────────────────
  ? for shortcuts · ← for agents
"""

# Idle variant where the "? for shortcuts" hint *is* present — must also be idle.
IDLE_SCREEN_WITH_SHORTCUTS_HINT = """\
● Done.

────────────────────────────────────────────────────────────────────────────────
❯ \xa0Try "fix typecheck errors"
────────────────────────────────────────────────────────────────────────────────
  ? for shortcuts · ← for agents                              ◐ medium · /effort
"""

# A genuine tool-permission menu: "Do you want …?" plus a numbered "1. Yes".
PERMISSION_SCREEN = """\
 Create file
 note.txt
 ╌╌╌ 1 banana ╌╌╌
 Do you want to create note.txt?
 ❯ 1. Yes
   2. Yes, allow all edits during this session (shift+tab)
   3. No
 Esc to cancel · Tab to amend
"""

# False positive #1: the user's prompt text contains "permission"/"approve"
# while the model is still generating. Must read "generating", not permission.
GENERATING_WITH_PERMISSION_WORDS = """\
● Working on: echo HELLO_PERMISSION_APPROVE

✶ Flibbertigibbeting… (3s)
──────────────────────────────────────────────
❯ run echo HELLO_PERMISSION_APPROVE and approve the permission
──────────────────────────────────────────────
  ⏵⏵ bypass permissions on (shift+tab to cycle) · esc to interrupt
"""

# False positive #2: the "fewer-permission-prompts" skill name sits on an
# otherwise idle screen. Must read "idle", not permission.
IDLE_WITH_PERMISSION_SKILL_NAME = """\
● Available skills include fewer-permission-prompts and others.

────────────────────────────────────────────────────────────────────────────────
❯ \xa0
────────────────────────────────────────────────────────────────────────────────
  ← for agents                                                ● high · /effort
"""


# -----------------------------------------------------------------------------
# _detect_state
# -----------------------------------------------------------------------------

class TestDetectState:
    def setup_method(self):
        self.bridge = TmuxBridge()

    def test_generating(self):
        assert self.bridge._detect_state(GENERATING_SCREEN) == "generating"

    def test_generating_normal_mode_spinner_only(self):
        # No "esc to interrupt" text — detection must key off the spinner glyph.
        assert self.bridge._detect_state(GENERATING_NORMAL_MODE) == "generating"

    def test_idle(self):
        assert self.bridge._detect_state(IDLE_SCREEN) == "idle"

    def test_idle_with_shortcuts_hint(self):
        assert self.bridge._detect_state(IDLE_SCREEN_WITH_SHORTCUTS_HINT) == "idle"

    def test_completed_turn_summary_is_idle_not_generating(self):
        # "✻ Cooked for 1s" reuses the spinner glyph but has no ellipsis — done.
        assert self.bridge._detect_state(COMPLETED_TURN_SCREEN) == "idle"

    def test_permission_prompt(self):
        assert self.bridge._detect_state(PERMISSION_SCREEN) == "permission_prompt"

    def test_no_false_permission_while_generating(self):
        # "permission"/"approve" in the prompt must NOT trigger permission_prompt
        # while a turn is running.
        assert self.bridge._detect_state(GENERATING_WITH_PERMISSION_WORDS) == "generating"

    def test_no_false_permission_on_idle_skill_name(self):
        # The "fewer-permission-prompts" skill name must NOT trigger
        # permission_prompt on an idle screen.
        assert self.bridge._detect_state(IDLE_WITH_PERMISSION_SKILL_NAME) == "idle"

    def test_empty_is_unknown(self):
        assert self.bridge._detect_state("") == "unknown"


# -----------------------------------------------------------------------------
# derive_context_usage
# -----------------------------------------------------------------------------

class TestDeriveContextUsage:
    def _assistant(self, input_tokens, cache_read, cache_creation):
        return {
            "type": "assistant",
            "message": {
                "model": "claude-x",
                "usage": {
                    "input_tokens": input_tokens,
                    "cache_creation_input_tokens": cache_creation,
                    "cache_read_input_tokens": cache_read,
                    "output_tokens": 47,
                },
            },
        }

    def _user_prompt(self, text):
        return {"type": "user", "message": {"content": text}}

    def _user_tool_result(self):
        # tool_result-carrying user entries have list content — NOT a real turn.
        return {
            "type": "user",
            "message": {"content": [{"type": "tool_result", "content": "ok"}]},
        }

    def test_context_tokens_and_percent_from_latest_assistant(self):
        # Shape from diagnostic A7: 2 + 23080 + 240 = 23,322.
        entries = [self._assistant(2, 23080, 240)]
        result = derive_context_usage(entries)
        assert result["tokens"] == 23322
        assert result["window"] == CONTEXT_WINDOW
        assert result["percent"] == round(23322 / 1_000_000 * 100, 2)  # 2.33

    def test_uses_latest_assistant_not_earlier(self):
        entries = [
            self._assistant(1, 100, 0),       # earlier
            self._user_prompt("next"),
            self._assistant(2, 23080, 240),   # latest — this one wins
        ]
        assert derive_context_usage(entries)["tokens"] == 23322

    def test_turn_count_excludes_tool_results(self):
        entries = [
            self._user_prompt("first real prompt"),
            self._assistant(1, 10, 0),
            self._user_tool_result(),         # not a turn
            self._assistant(2, 20, 0),
            self._user_prompt("second real prompt"),
            self._assistant(3, 30, 0),
        ]
        result = derive_context_usage(entries)
        assert result["turns"] == 2

    def test_missing_usage_fields_default_to_zero(self):
        entries = [{"type": "assistant", "message": {"usage": {"input_tokens": 5}}}]
        result = derive_context_usage(entries)
        assert result["tokens"] == 5

    def test_no_assistant_entries(self):
        entries = [self._user_prompt("hello")]
        result = derive_context_usage(entries)
        assert result["tokens"] == 0
        assert result["percent"] == 0.0
        assert result["turns"] == 1

    def test_empty(self):
        result = derive_context_usage([])
        assert result == {"tokens": 0, "window": CONTEXT_WINDOW, "percent": 0.0, "turns": 0}
