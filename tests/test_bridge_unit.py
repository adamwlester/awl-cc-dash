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

from bridge.bridge import TmuxBridge, parse_permission_prompt
from bridge.transcript import _encode_cwd, _resolve_project_dir
from sidecar.drivers.bridge import (
    derive_context_usage,
    classify_tool,
    CONTEXT_WINDOW,
)


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
        assert result == {
            "tokens": 0,
            "window": CONTEXT_WINDOW,
            "percent": 0.0,
            "turns": 0,
            "work_steps": 0,
            "tools": {b: 0 for b in
                      ("read", "edit", "bash", "mcp", "subagent", "web", "other")},
            "tool_total": 0,
        }


# -----------------------------------------------------------------------------
# work_steps + by-tool breakdown (the Turns metric)
# -----------------------------------------------------------------------------

class TestClassifyTool:
    def test_read_search_family(self):
        for n in ("Read", "Glob", "Grep", "LS", "NotebookRead"):
            assert classify_tool(n) == "read"

    def test_edit_family(self):
        for n in ("Edit", "Write", "MultiEdit", "NotebookEdit"):
            assert classify_tool(n) == "edit"

    def test_bash_family(self):
        for n in ("Bash", "BashOutput", "KillShell"):
            assert classify_tool(n) == "bash"

    def test_mcp_prefix(self):
        assert classify_tool("mcp__playwright__browser_click") == "mcp"
        assert classify_tool("mcp__github__create_issue") == "mcp"

    def test_subagent_and_web(self):
        # This Claude Code build spawns subagents via "Agent" (live-verified);
        # the SDK / older builds use "Task". Both are the subagent slice.
        assert classify_tool("Agent") == "subagent"
        assert classify_tool("Task") == "subagent"
        assert classify_tool("WebFetch") == "web"
        assert classify_tool("WebSearch") == "web"

    def test_toolsearch_is_other(self):
        # The deferred-tool loader that precedes an Agent spawn is a meta-tool,
        # not subagent work — it must not inflate the subagent slice.
        assert classify_tool("ToolSearch") == "other"

    def test_unknown_and_missing_are_other(self):
        assert classify_tool("TodoWrite") == "other"
        assert classify_tool("ExitPlanMode") == "other"
        assert classify_tool(None) == "other"
        assert classify_tool("") == "other"


class TestWorkStepsAndTools:
    def _asst(self, mid, blocks):
        return {"type": "assistant", "message": {"id": mid, "content": blocks}}

    def _text(self, t="ok"):
        return {"type": "text", "text": t}

    def _tool(self, name):
        return {"type": "tool_use", "name": name, "input": {}}

    def _thinking(self):
        return {"type": "thinking", "thinking": "…"}

    def _user_prompt(self, t):
        return {"type": "user", "message": {"content": t}}

    def test_mirrors_real_transcript(self):
        # Mirrors the live bridge-diag transcript: 3 prompts, 5 distinct
        # assistant message.ids (one streamed across two lines), tools = 1 Bash
        # + 2 Write. work_steps must be 5 (not 10 lines, not 3 prompts).
        entries = [
            self._user_prompt("run a bash command"),
            self._asst("m1", [self._thinking()]),          # streamed line 1 of m1
            self._asst("m1", [self._tool("Bash")]),        # streamed line 2 of m1
            {"type": "user", "message": {"content": [{"type": "tool_result"}]}},
            self._asst("m2", [self._text()]),
            self._user_prompt("write note.txt"),
            self._asst("m3", [self._tool("Write")]),
            {"type": "user", "message": {"content": [{"type": "tool_result"}]}},
            self._asst("m4", [self._text()]),
            self._user_prompt("write second.txt"),
            self._asst("m5", [self._tool("Write")]),
        ]
        r = derive_context_usage(entries)
        assert r["work_steps"] == 5
        assert r["turns"] == 3  # legacy prompt-round count, for contrast
        assert r["tools"]["bash"] == 1
        assert r["tools"]["edit"] == 2
        assert r["tool_total"] == 3

    def test_streamed_split_counts_once(self):
        # Two JSONL lines sharing one message.id = one inference = one work step.
        entries = [
            self._asst("same", [self._thinking()]),
            self._asst("same", [self._text()]),
        ]
        assert derive_context_usage(entries)["work_steps"] == 1

    def test_entries_without_id_count_individually(self):
        # Defensive: id-less assistant entries each count as their own step.
        entries = [
            {"type": "assistant", "message": {"content": [self._text()]}},
            {"type": "assistant", "message": {"content": [self._text()]}},
        ]
        assert derive_context_usage(entries)["work_steps"] == 2

    def test_sidechain_entries_are_excluded(self):
        # A subagent's own (sidechain) inferences and tools must NOT inflate the
        # parent's counts — only the parent's Task tool_use (main line) counts.
        entries = [
            self._asst("parent1", [self._tool("Task")]),       # parent spawns subagent
            {"type": "assistant", "isSidechain": True,
             "message": {"id": "sub1", "content": [self._tool("Bash")]}},
            {"type": "assistant", "isSidechain": True,
             "message": {"id": "sub2", "content": [self._text()]}},
            self._asst("parent2", [self._text()]),             # parent resumes
        ]
        r = derive_context_usage(entries)
        assert r["work_steps"] == 2          # parent1, parent2 — not the 2 sidechains
        assert r["tools"]["subagent"] == 1   # the Task call
        assert r["tools"]["bash"] == 0       # subagent's Bash excluded
        assert r["tool_total"] == 1

    def test_multiple_tools_in_one_message(self):
        entries = [self._asst("m", [self._tool("Read"), self._tool("Read"),
                                    self._tool("mcp__x__y")])]
        r = derive_context_usage(entries)
        assert r["work_steps"] == 1
        assert r["tools"]["read"] == 2
        assert r["tools"]["mcp"] == 1
        assert r["tool_total"] == 3

    def test_context_tokens_skip_sidechain(self):
        # The latest *main-line* assistant usage drives context %, not a trailing
        # subagent sidechain entry.
        entries = [
            {"type": "assistant",
             "message": {"id": "p", "usage": {"input_tokens": 5, "cache_read_input_tokens": 0,
                                              "cache_creation_input_tokens": 0}, "content": []}},
            {"type": "assistant", "isSidechain": True,
             "message": {"id": "s", "usage": {"input_tokens": 999, "cache_read_input_tokens": 0,
                                              "cache_creation_input_tokens": 0}, "content": []}},
        ]
        assert derive_context_usage(entries)["tokens"] == 5


# -----------------------------------------------------------------------------
# parse_permission_prompt
# -----------------------------------------------------------------------------

# A real edit prompt: a multi-line diff preview renders ABOVE the question, so
# "Do you want …?" sits well above the bottom menu. The parser must still find
# the question and the full option list (and the menu anchors detection even when
# the question would fall outside a short status window).
LONG_DIFF_PERMISSION_SCREEN = """\
● Edit(config.py)
 Update config.py
 config.py
 ╌╌╌ 1   import os
 ╌╌╌ 2 + import sys
 ╌╌╌ 3   import json
 ╌╌╌ 4 + import logging
 ╌╌╌ 5   from pathlib import Path
 ╌╌╌ 6 + from typing import Any
 ╌╌╌ 7   DEBUG = False
 ╌╌╌ 8 + VERBOSE = True
 ╌╌╌ 9   TIMEOUT = 30
 ╌╌╌ 10 + RETRIES = 3
 Do you want to make this edit to config.py?
 ❯ 1. Yes
   2. Yes, allow all edits during this session (shift+tab)
   3. No
 Esc to cancel · Tab to amend
"""

# An ALREADY-ANSWERED menu scrolled up into history while the session is now
# idle below it. The menu is NOT at the bottom, so it must NOT parse as a live
# prompt (this is the stale-scrollback false-fire the bottom anchor prevents).
STALE_MENU_IN_SCROLLBACK = """\
 Do you want to create old.txt?
 ❯ 1. Yes
   2. Yes, allow all edits during this session
   3. No
● Created old.txt

────────────────────────────────────────────────────────────────────────────────
❯ \xa0
────────────────────────────────────────────────────────────────────────────────
  ← for agents                                                ● high · /effort
"""


class TestParsePermissionPrompt:
    def test_basic_menu(self):
        detail = parse_permission_prompt(PERMISSION_SCREEN)
        assert detail is not None
        assert detail["question"] == "Do you want to create note.txt?"
        labels = [o["label"] for o in detail["options"]]
        indexes = [o["index"] for o in detail["options"]]
        assert indexes == [1, 2, 3]
        assert labels[0] == "Yes"
        assert "allow all edits" in labels[1]
        assert labels[2] == "No"
        assert "Do you want to create note.txt?" in detail["raw"]

    def test_long_diff_question_above_menu(self):
        # The "Do you want …?" line sits ~14 lines above the menu (above a long
        # diff). It must still be captured as the question.
        detail = parse_permission_prompt(LONG_DIFF_PERMISSION_SCREEN)
        assert detail is not None
        assert detail["question"] == "Do you want to make this edit to config.py?"
        assert [o["index"] for o in detail["options"]] == [1, 2, 3]

    def test_stale_menu_in_scrollback_is_not_a_live_prompt(self):
        # An answered menu higher in scrollback with an idle prompt below must
        # NOT be read as a live permission prompt.
        assert parse_permission_prompt(STALE_MENU_IN_SCROLLBACK) is None

    def test_idle_screen_has_no_permission(self):
        assert parse_permission_prompt(IDLE_SCREEN) is None

    def test_generating_screen_has_no_permission(self):
        assert parse_permission_prompt(GENERATING_SCREEN) is None

    def test_permission_words_without_menu_is_none(self):
        # Prompt text mentioning "permission"/"approve" but no numbered menu.
        assert parse_permission_prompt(GENERATING_WITH_PERMISSION_WORDS) is None

    def test_empty_is_none(self):
        assert parse_permission_prompt("") is None

    def test_detect_state_uses_long_diff_menu(self):
        # _detect_state must classify the long-diff edit prompt as a permission
        # prompt purely off the bottom menu, even with the question far above.
        bridge = TmuxBridge()
        assert bridge._detect_state(LONG_DIFF_PERMISSION_SCREEN) == "permission_prompt"

    def test_detect_state_ignores_stale_menu(self):
        bridge = TmuxBridge()
        assert bridge._detect_state(STALE_MENU_IN_SCROLLBACK) == "idle"


# -----------------------------------------------------------------------------
# runtime_store — restart-survival session records (pure file persistence)
# -----------------------------------------------------------------------------

class TestRuntimeStore:
    def _store(self, tmp_path, monkeypatch):
        monkeypatch.setenv("AWL_SIDECAR_RUNTIME", str(tmp_path))
        import importlib
        import sidecar.runtime_store as rs
        return importlib.reload(rs)

    def test_save_and_load_roundtrip(self, tmp_path, monkeypatch):
        rs = self._store(tmp_path, monkeypatch)
        rs.save_record({"session_id": "abc", "tmux_name": "awl-1", "model": "sonnet"})
        records = rs.all_records()
        assert len(records) == 1
        assert records[0]["tmux_name"] == "awl-1"

    def test_save_updates_existing(self, tmp_path, monkeypatch):
        rs = self._store(tmp_path, monkeypatch)
        rs.save_record({"session_id": "abc", "tmux_name": "awl-1"})
        rs.save_record({"session_id": "abc", "tmux_name": "awl-2"})
        records = rs.all_records()
        assert len(records) == 1
        assert records[0]["tmux_name"] == "awl-2"

    def test_remove_record(self, tmp_path, monkeypatch):
        rs = self._store(tmp_path, monkeypatch)
        rs.save_record({"session_id": "abc", "tmux_name": "awl-1"})
        rs.save_record({"session_id": "def", "tmux_name": "awl-2"})
        rs.remove_record("abc")
        ids = {r["session_id"] for r in rs.all_records()}
        assert ids == {"def"}

    def test_missing_file_is_empty(self, tmp_path, monkeypatch):
        rs = self._store(tmp_path, monkeypatch)
        assert rs.all_records() == []

    def test_save_without_session_id_is_noop(self, tmp_path, monkeypatch):
        rs = self._store(tmp_path, monkeypatch)
        rs.save_record({"tmux_name": "awl-x"})
        assert rs.all_records() == []


# -----------------------------------------------------------------------------
# transcript project-dir resolution — Claude Code's cwd→dir-name encoding
# -----------------------------------------------------------------------------

class TestEncodeCwd:
    def test_replaces_slashes(self):
        # Plain mount path: every "/" -> "-" (regression baseline).
        assert _encode_cwd("/mnt/c/Users/lester") == "-mnt-c-Users-lester"

    def test_replaces_dots_not_just_slashes(self):
        # The bug: a dotted segment must encode the "." as "-" too, so a leading
        # dot after a slash yields a DOUBLE dash. Confirmed live against the real
        # dir Claude Code created.
        assert (
            _encode_cwd("/mnt/c/foo/awl-cc-dash/.scratch/dottest")
            == "-mnt-c-foo-awl-cc-dash--scratch-dottest"
        )

    def test_preserves_literal_dashes_and_digits(self):
        assert _encode_cwd("/home/lester/awl-fin-0f97b358") == "-home-lester-awl-fin-0f97b358"

    def test_underscore_and_space_become_dash(self):
        assert _encode_cwd("/a/b_c d") == "-a-b-c-d"


class _FakeBridge:
    """Minimal bridge stub recording shell commands and returning canned output."""

    def __init__(self, test_dir_ok=False, listing=""):
        self._test_dir_ok = test_dir_ok
        self._listing = listing
        self.calls = []

    def _run(self, cmd, **_kw):
        self.calls.append(cmd)
        if cmd.startswith("test -d"):
            return "OK\n" if self._test_dir_ok else "\n"
        if cmd.startswith("ls -1"):
            return self._listing
        return ""


class TestResolveProjectDir:
    def test_fast_path_when_dir_exists(self):
        b = _FakeBridge(test_dir_ok=True)
        got = _resolve_project_dir(b, "/mnt/c/x/.scratch")
        assert got is not None and got.endswith("/-mnt-c-x--scratch")
        # Fast path returns before listing the projects dir.
        assert not any(c.startswith("ls -1") for c in b.calls)

    def test_falls_back_to_real_listing_match(self):
        # Encoded dir not found by `test -d`; resolve via the real listing.
        real = "-mnt-c-Users-lester-MeDocuments-AppData-Anthropic-awl-cc-dash--scratch-dottest"
        b = _FakeBridge(test_dir_ok=False, listing=f"-other-proj\n{real}\n")
        cwd = "/mnt/c/Users/lester/MeDocuments/AppData/Anthropic/awl-cc-dash/.scratch/dottest"
        got = _resolve_project_dir(b, cwd)
        assert got is not None and got.endswith("/" + real)

    def test_collapsed_match_is_tolerant(self):
        # Even if the real dir collapsed consecutive separators, a dash-collapsed
        # comparison still resolves it.
        b = _FakeBridge(test_dir_ok=False, listing="-mnt-c-x-scratch\n")
        got = _resolve_project_dir(b, "/mnt/c/x/.scratch")  # encodes to -mnt-c-x--scratch
        assert got is not None and got.endswith("/-mnt-c-x-scratch")

    def test_returns_none_when_no_match(self):
        b = _FakeBridge(test_dir_ok=False, listing="-totally-unrelated\n")
        assert _resolve_project_dir(b, "/mnt/c/x/y") is None
