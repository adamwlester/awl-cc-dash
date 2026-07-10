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
from bridge.transcript import (
    _encode_cwd,
    _resolve_project_dir,
    _resolve_session_id,
    find_transcript,
)
from bridge.paths import WSL_CLAUDE_PROJECTS, parse_default_gateway, sidecar_base_url
from sidecar.drivers.bridge import (
    derive_context_usage,
    derive_subagents,
    classify_tool,
    context_window_for_model,
    DEFAULT_CONTEXT_WINDOW,
    CONTEXT_WINDOW_1M,
    _entry_to_event,
)
from bridge.bridge import VALID_PERMISSION_MODES


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
        # The _assistant helper's model is "claude-x" -> the 200K default window.
        entries = [self._assistant(2, 23080, 240)]
        result = derive_context_usage(entries)
        assert result["tokens"] == 23322
        assert result["window"] == DEFAULT_CONTEXT_WINDOW
        assert result["percent"] == round(23322 / 200_000 * 100, 2)  # 11.66

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
            "window": DEFAULT_CONTEXT_WINDOW,  # no model -> 200K default
            "model": None,
            "percent": 0.0,
            "turns": 0,
            "work_steps": 0,
            "tools": {b: 0 for b in
                      ("read", "edit", "bash", "mcp", "subagent", "web", "other")},
            "tool_total": 0,
        }

    def test_window_is_model_aware(self):
        # 200K for a normal model; 1M only for a 1M-context model id.
        assert context_window_for_model("claude-sonnet-4-6") == DEFAULT_CONTEXT_WINDOW
        assert context_window_for_model(None) == DEFAULT_CONTEXT_WINDOW
        assert context_window_for_model("claude-sonnet-4-6-1m") == CONTEXT_WINDOW_1M
        # The window in the result follows the latest assistant entry's model.
        entries = [self._assistant(1, 999_999, 0)]  # model "claude-x" -> 200K
        assert derive_context_usage(entries)["window"] == DEFAULT_CONTEXT_WINDOW
        one_m = {"type": "assistant", "message": {
            "model": "claude-opus-4-1m", "id": "m1",
            "usage": {"input_tokens": 500_000}}}
        r = derive_context_usage([one_m])
        assert r["window"] == CONTEXT_WINDOW_1M
        assert r["percent"] == 50.0  # 500K / 1M


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
# derive_subagents — the subagent inventory from the parent transcript
#
# Entries below mirror the REAL transcript shape captured live (CC 2.1.x): the
# parent spawns via an `Agent` tool_use, and the result returns as a user
# tool_result carrying a structured `toolUseResult` (agentId/status/totals) plus
# a text "agentId: …\n<usage>…</usage>" fallback.
# -----------------------------------------------------------------------------

class TestDeriveSubagents:
    def _spawn(self, tuid, *, name="Agent", subagent_type="general-purpose",
               description="Reply with marker word", prompt="Reply: OK",
               sidechain=False):
        block = {"type": "tool_use", "id": tuid, "name": name,
                 "input": {"description": description, "prompt": prompt,
                           "subagent_type": subagent_type}}
        entry = {"type": "assistant", "message": {"id": "m_" + tuid,
                                                  "content": [block]}}
        if sidechain:
            entry["isSidechain"] = True
        return entry

    def _result(self, tuid, *, agent_id="acbbfd9edd81f32fc", status="completed",
                tokens=9887, tool_uses=0, duration=2407,
                model="claude-opus-4-8[1m]", is_error=False, structured=True,
                text=None):
        block = {"type": "tool_result", "tool_use_id": tuid}
        if is_error:
            block["is_error"] = True
        if text is not None:
            block["content"] = [{"type": "text", "text": text}]
        else:
            block["content"] = [{"type": "text", "text": "OK"}]
        entry = {"type": "user", "message": {"content": [block]}}
        if structured:
            entry["toolUseResult"] = {
                "status": status, "agentId": agent_id,
                "agentType": "general-purpose", "totalTokens": tokens,
                "totalToolUseCount": tool_uses, "totalDurationMs": duration,
                "resolvedModel": model,
            }
        return entry

    def test_no_subagents(self):
        entries = [{"type": "user", "message": {"content": "hi"}},
                   {"type": "assistant",
                    "message": {"id": "m1", "content": [{"type": "text", "text": "ok"}]}}]
        assert derive_subagents(entries) == {"count": 0, "subagents": []}

    def test_done_subagent_structured(self):
        entries = [self._spawn("toolu_1"), self._result("toolu_1")]
        out = derive_subagents(entries)
        assert out["count"] == 1
        sa = out["subagents"][0]
        assert sa["id"] == "s1"
        assert sa["tool_use_id"] == "toolu_1"
        assert sa["agent_id"] == "acbbfd9edd81f32fc"
        assert sa["type"] == "general-purpose"
        assert sa["description"] == "Reply with marker word"
        assert sa["status"] == "done"
        assert sa["usage"] == {
            "tokens": 9887, "tool_uses": 0, "duration_ms": 2407,
            "model": "claude-opus-4-8[1m]",
        }

    def test_running_subagent_when_no_result_yet(self):
        # A spawn whose Task hasn't returned is still running — no agent_id/usage.
        entries = [self._spawn("toolu_1")]
        sa = derive_subagents(entries)["subagents"][0]
        assert sa["status"] == "running"
        assert sa["agent_id"] is None
        assert sa["usage"] is None

    def test_task_name_also_counts(self):
        # SDK / older builds name the spawn tool "Task".
        entries = [self._spawn("toolu_1", name="Task"), self._result("toolu_1")]
        assert derive_subagents(entries)["count"] == 1

    def test_multiple_spawns_get_ordinal_ids(self):
        entries = [
            self._spawn("toolu_1"), self._result("toolu_1"),
            self._spawn("toolu_2"),  # second still running
        ]
        out = derive_subagents(entries)
        assert [s["id"] for s in out["subagents"]] == ["s1", "s2"]
        assert out["subagents"][0]["status"] == "done"
        assert out["subagents"][1]["status"] == "running"

    def test_error_status_from_toolUseResult(self):
        entries = [self._spawn("toolu_1"),
                   self._result("toolu_1", status="failed")]
        assert derive_subagents(entries)["subagents"][0]["status"] == "error"

    def test_error_status_from_is_error_block(self):
        entries = [self._spawn("toolu_1"),
                   self._result("toolu_1", structured=False, is_error=True,
                                text="boom")]
        assert derive_subagents(entries)["subagents"][0]["status"] == "error"

    def test_text_usage_fallback_when_no_structured_result(self):
        # Older/SDK builds may omit toolUseResult; the agentId + <usage> text
        # block in the tool_result content must still yield id + usage.
        text = ("agentId: deadbeefcafe (use SendMessage with to: 'deadbeefcafe' "
                "to continue this agent)\n<usage>subagent_tokens: 1234\n"
                "tool_uses: 5\nduration_ms: 6789</usage>")
        entries = [self._spawn("toolu_1"),
                   self._result("toolu_1", structured=False, text=text)]
        sa = derive_subagents(entries)["subagents"][0]
        assert sa["status"] == "done"
        assert sa["agent_id"] == "deadbeefcafe"
        assert sa["usage"]["tokens"] == 1234
        assert sa["usage"]["tool_uses"] == 5
        assert sa["usage"]["duration_ms"] == 6789
        assert sa["usage"]["model"] is None  # not in the text fallback

    def test_type_falls_back_to_description(self):
        spawn = self._spawn("toolu_1")
        del spawn["message"]["content"][0]["input"]["subagent_type"]
        sa = derive_subagents([spawn])["subagents"][0]
        assert sa["type"] == "Reply with marker word"

    def test_sidechain_spawn_is_ignored(self):
        # An Agent tool_use INSIDE a subagent's own (sidechain) work is the
        # subagent's nested spawn — not one of the PARENT's subagents.
        entries = [
            self._spawn("toolu_1"), self._result("toolu_1"),
            self._spawn("toolu_nested", sidechain=True),
        ]
        out = derive_subagents(entries)
        assert out["count"] == 1
        assert out["subagents"][0]["tool_use_id"] == "toolu_1"


# -----------------------------------------------------------------------------
# VALID_PERMISSION_MODES — the launch-flag allow-list (Part 1.2)
# -----------------------------------------------------------------------------

class TestValidPermissionModes:
    def test_matches_cli_choices(self):
        # The set claude's `--permission-mode` documents (CC 2.1.x). Drift here
        # silently drops a real mode at launch, so pin it.
        assert VALID_PERMISSION_MODES == frozenset({
            "acceptEdits", "auto", "bypassPermissions", "default",
            "dontAsk", "plan",
        })

    def test_covers_sidecar_setmode_enum(self):
        # Every mode the sidecar's SetModeRequest accepts must be launchable.
        for mode in ("default", "acceptEdits", "plan", "bypassPermissions", "dontAsk"):
            assert mode in VALID_PERMISSION_MODES


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


# -----------------------------------------------------------------------------
# transcript SESSION resolution — each agent reads its OWN <session-id>.jsonl
# (the collision fix: co-located agents share a project dir, so "newest" would
# cross-read; --session-id pins each to a distinct file).
# -----------------------------------------------------------------------------

class _FakeTranscriptBridge:
    """Bridge stub for find_transcript / session-id resolution.

    Canned cwd (fast-path project dir), an in-memory ``_session_uuids`` map, and a
    set of existing transcript files.
    """

    def __init__(self, *, session_uuids=None, cwd="/home/lester/proj",
                 existing_files=None):
        self._session_uuids = session_uuids or {}
        self._cwd = cwd
        self._existing = set(existing_files or [])
        self.calls = []

    @property
    def project_dir(self):
        return f"{WSL_CLAUDE_PROJECTS}/{_encode_cwd(self._cwd)}"

    def _tmux(self, cmd, **_kw):
        self.calls.append(cmd)
        if "pane_current_path" in cmd:
            return self._cwd
        return ""

    def _run(self, cmd, **_kw):
        self.calls.append(cmd)
        if cmd.startswith("test -d"):
            return "OK\n"  # project dir resolves via fast path
        if cmd.startswith("test -f"):
            path = cmd.split("'")[1]
            return "OK\n" if path in self._existing else "\n"
        if cmd.startswith("ls -t"):
            return (sorted(self._existing)[-1] + "\n") if self._existing else ""
        if cmd.startswith("ls "):  # legacy listing
            return ("\n".join(sorted(self._existing)) + "\n") if self._existing else ""
        return ""


class TestSessionIdResolution:
    SID_A = "6c61e972-624e-47cb-a509-7b6ff708a1db"
    SID_B = "1a40cbfa-7f37-4f3d-b904-42e60e67cebc"

    def test_in_memory_id_wins(self):
        b = _FakeTranscriptBridge(session_uuids={"agentA": self.SID_A})
        assert _resolve_session_id(b, "agentA") == self.SID_A

    def test_unknown_session_resolves_none(self):
        b = _FakeTranscriptBridge()
        assert _resolve_session_id(b, "nope") is None

    def test_colocated_agents_resolve_distinct_files(self):
        # Two agents, same cwd (same project dir), each pinned to its own file.
        b = _FakeTranscriptBridge(session_uuids={"a": self.SID_A, "b": self.SID_B})
        b._existing = {
            f"{b.project_dir}/{self.SID_A}.jsonl",
            f"{b.project_dir}/{self.SID_B}.jsonl",
        }
        ta = find_transcript(b, "a")
        tb = find_transcript(b, "b")
        assert ta == f"{b.project_dir}/{self.SID_A}.jsonl"
        assert tb == f"{b.project_dir}/{self.SID_B}.jsonl"
        assert ta != tb

    def test_known_id_missing_file_returns_none_not_newest(self):
        # The id is known but its file isn't written yet; a co-located sibling's
        # file DOES exist. We must NOT hand back the sibling's transcript.
        b = _FakeTranscriptBridge(session_uuids={"a": self.SID_A})
        b._existing = {f"{b.project_dir}/{self.SID_B}.jsonl"}  # sibling only
        assert find_transcript(b, "a") is None

    def test_unknown_id_falls_back_to_newest(self):
        # A session this bridge didn't launch (no in-memory id): legacy
        # newest-file behavior is preserved for non-dashboard sessions.
        b = _FakeTranscriptBridge()
        only = f"{b.project_dir}/{self.SID_A}.jsonl"
        b._existing = {only}
        assert find_transcript(b, "legacy") == only


# -----------------------------------------------------------------------------
# Settings registry reads (bridge/registry.py) — hermetic via a canned runner
# -----------------------------------------------------------------------------

import json as _json
import shlex as _shlex

from bridge.registry import (
    read_mcp_registry,
    read_plugins,
    read_config,
    build_agent_mcp_config,
)
from bridge.paths import (
    WSL_USER_CLAUDE_JSON,
    WSL_SETTINGS_JSON,
    WSL_KNOWN_MARKETPLACES,
)


class _CannedRunner:
    """Stand-in for TmuxBridge._run: serves canned file contents + plugin JSON.

    Matches the exact command shapes registry.py emits: ``cat <path> 2>/dev/null
    || true``, ``test -e <path> && echo 1 || echo 0``, and the ``plugin list
    --json`` CLI. Unknown files read as empty (missing).
    """

    def __init__(self, files=None, plugin_list_json="[]"):
        self.files = files or {}
        self.plugin_list_json = plugin_list_json

    def _run(self, cmd, **_kw):
        toks = _shlex.split(cmd)
        if toks and toks[0] == "cat":
            return self.files.get(toks[1], "")
        if toks[:2] == ["test", "-e"]:
            return "1" if toks[2] in self.files else "0"
        if "plugin" in cmd and "list" in cmd and "--json" in cmd:
            return self.plugin_list_json
        return ""


class TestReadMcpRegistry:
    def test_user_and_project_scopes_with_enable_state(self):
        runner = _CannedRunner(files={
            WSL_USER_CLAUDE_JSON: _json.dumps({"mcpServers": {
                "github": {"command": "npx", "args": ["-y", "gh-mcp"],
                           "env": {"TOKEN": "secret"}},
                "exa": {"type": "http", "url": "https://exa/mcp"},
            }}),
            "/mnt/c/proj/.mcp.json": _json.dumps({"mcpServers": {
                "local-a": {"command": "node"},
                "local-b": {"command": "node"},
            }}),
            "/mnt/c/proj/.claude/settings.json": _json.dumps({
                "disabledMcpjsonServers": ["local-b"],
                "enableAllProjectMcpServers": True,
            }),
        })
        reg = read_mcp_registry(runner, project_cwd="/mnt/c/proj")
        user = {s["name"]: s for s in reg["user"]}
        assert set(user) == {"github", "exa"}
        assert user["github"]["enabled"] is True and user["github"]["scope"] == "user"
        # Secret VALUES never surface — only the env key names.
        assert user["github"]["env_keys"] == ["TOKEN"]
        assert user["exa"]["transport"] == "http"
        proj = {s["name"]: s for s in reg["project"]}
        assert proj["local-a"]["enabled"] is True   # enableAll
        assert proj["local-b"]["enabled"] is False  # explicit disable wins

    def test_no_project_cwd_means_user_only(self):
        runner = _CannedRunner(files={
            WSL_USER_CLAUDE_JSON: _json.dumps({"mcpServers": {"exa": {}}}),
        })
        reg = read_mcp_registry(runner)
        assert [s["name"] for s in reg["user"]] == ["exa"]
        assert reg["project"] == []


class TestBuildAgentMcpConfig:
    def test_selects_subset_and_skips_unknown(self):
        runner = _CannedRunner(files={
            WSL_USER_CLAUDE_JSON: _json.dumps({"mcpServers": {
                "github": {"command": "a"}, "exa": {"command": "b"},
                "slack": {"command": "c"},
            }}),
        })
        cfg = build_agent_mcp_config(runner, ["exa", "nope"])
        assert cfg == {"mcpServers": {"exa": {"command": "b"}}}

    def test_empty_selection_is_strict_none(self):
        runner = _CannedRunner(files={
            WSL_USER_CLAUDE_JSON: _json.dumps({"mcpServers": {"exa": {}}}),
        })
        assert build_agent_mcp_config(runner, []) == {"mcpServers": {}}


class TestReadPlugins:
    def test_installed_from_cli_json_plus_marketplaces(self):
        runner = _CannedRunner(
            plugin_list_json=_json.dumps([
                {"id": "superpowers@superpowers-marketplace", "version": "5.0.7",
                 "scope": "project", "enabled": False,
                 "installPath": "/x", "installedAt": "2026"},
            ]),
            files={WSL_KNOWN_MARKETPLACES: _json.dumps({
                "superpowers-marketplace": {
                    "source": {"source": "github", "repo": "obra/superpowers-marketplace"},
                    "installLocation": "/m"},
            })},
        )
        out = read_plugins(runner)
        p = out["installed"][0]
        assert p["name"] == "superpowers" and p["marketplace"] == "superpowers-marketplace"
        assert p["enabled"] is False and p["version"] == "5.0.7"
        assert out["marketplaces"][0]["repo"] == "obra/superpowers-marketplace"

    def test_handles_empty_cli(self):
        out = read_plugins(_CannedRunner(plugin_list_json=""))
        assert out["installed"] == [] and out["marketplaces"] == []


class TestReadConfig:
    def test_global_and_project_fields_and_tenor(self):
        runner = _CannedRunner(files={
            WSL_SETTINGS_JSON: _json.dumps({
                "model": "opus", "effortLevel": "medium", "tui": "fullscreen",
                "theme": "dark-ansi",
            }),
            "/mnt/c/proj/.claude/settings.json": _json.dumps({
                "permissions": {"allow": ["Read(/**)"], "deny": ["Bash(rm *)"],
                                "defaultMode": "acceptEdits"},
                "enableAllProjectMcpServers": True,
                "plansDirectory": "./.claude/plans",
            }),
            "/mnt/c/proj/CLAUDE.md": "x",
        })
        cfg = read_config(runner, project_cwd="/mnt/c/proj")
        assert cfg["global"]["model"] == "opus"
        assert cfg["global"]["effort"] == "medium"
        assert cfg["project"]["permissions"]["deny"] == ["Bash(rm *)"]
        assert cfg["project"]["permissionMode"] == "acceptEdits"
        assert cfg["project"]["plansDirectory"] == "./.claude/plans"
        assert cfg["tenor"]["model"] == "Live"
        assert cfg["tenor"]["permissionMode"] == "New session"
        # CLAUDE.md existence is reported (project file present in canned FS).
        proj_md = [m for m in cfg["claudeMd"] if m["scope"] == "project"][0]
        assert proj_md["exists"] is True

    def test_project_none_when_no_cwd(self):
        runner = _CannedRunner(files={WSL_SETTINGS_JSON: _json.dumps({"model": "opus"})})
        cfg = read_config(runner)
        assert cfg["project"] is None
        assert cfg["global"]["model"] == "opus"


# -----------------------------------------------------------------------------
# Per-agent --settings building (BridgeDriver._build_settings / _build_mcp_config)
# -----------------------------------------------------------------------------

from sidecar.drivers.bridge import BridgeDriver
from sidecar.drivers.base import DriverConfig


def _driver(**cfg):
    return BridgeDriver(DriverConfig(**cfg), lambda e: None)


class TestBuildLaunchConfig:
    def test_permission_rules_and_plugins_compose_into_settings(self):
        d = _driver(
            permission_rules={"deny": ["Bash"], "ask": ["Read(/etc/**)"], "allow": []},
            enabled_plugins={"superpowers@superpowers-marketplace": True},
        )
        s = d._build_settings()
        assert s["permissions"] == {"deny": ["Bash"], "ask": ["Read(/etc/**)"]}
        assert s["enabledPlugins"] == {"superpowers@superpowers-marketplace": True}

    def test_retention_pin_always_present(self):
        # ARCHITECTURE §8.6: EVERY materialized per-agent settings payload pins
        # cleanupPeriodDays (transcripts are the master record; Claude Code's
        # 30-day auto-delete default must never apply to dashboard agents). This
        # also means a settings file is always written — even a bare agent with
        # no other per-agent config gets the pin.
        from sidecar.drivers.bridge import TRANSCRIPT_RETENTION_DAYS
        assert TRANSCRIPT_RETENTION_DAYS == 3650
        bare = _driver()._build_settings()
        assert bare == {"cleanupPeriodDays": 3650}
        configured = _driver(
            permission_rules={"deny": ["Bash"]},
        )._build_settings()
        assert configured["cleanupPeriodDays"] == 3650

    def test_mcp_none_inherits_global(self):
        # mcp_servers unset -> None -> no --mcp-config (inherit the global registry).
        assert _driver()._build_mcp_config() is None


# ---------------------------------------------------------------------------
# Transcript events carry a deterministic anchor (the JSONL entry uuid)
# so the sidecar can build a stable, dedup-able event id.
# ---------------------------------------------------------------------------

class TestEntryToEventAnchor:
    def test_assistant_event_carries_uuid_anchor(self):
        ev = _entry_to_event({
            "type": "assistant", "uuid": "abc-123",
            "message": {"content": [], "model": "sonnet"},
            "timestamp": "2026-06-30T00:00:00",
        })
        assert ev["type"] == "assistant"
        assert ev["anchor"] == "abc-123"   # the deterministic id anchor
        assert ev["source_kind"] == "t"     # transcript-sourced

    def test_user_event_carries_uuid_anchor(self):
        ev = _entry_to_event({
            "type": "user", "uuid": "u-9",
            "message": {"content": []},
        })
        assert ev["anchor"] == "u-9"
        assert ev["source_kind"] == "t"

    def test_missing_uuid_leaves_anchor_none(self):
        ev = _entry_to_event({"type": "assistant", "message": {"content": []}})
        assert ev["anchor"] is None        # sidecar falls back to a seq-based id
        assert ev["source_kind"] == "t"

    def test_non_message_entry_skipped(self):
        assert _entry_to_event({"type": "file-history-snapshot"}) is None


# -----------------------------------------------------------------------------
# WSL2 -> Windows-host gateway resolution (the hook URL must be host-reachable;
# localhost from WSL2 does NOT reach the host — live-verified in the hook-channel spike).
# -----------------------------------------------------------------------------

class TestDefaultGatewayParse:
    def test_parses_gateway_ip(self):
        out = "default via 172.26.112.1 dev eth0 proto kernel \n"
        assert parse_default_gateway(out) == "172.26.112.1"

    def test_parses_with_extra_routes(self):
        out = (
            "default via 192.168.64.1 dev eth0 proto kernel metric 100\n"
            "172.17.0.0/16 dev docker0 proto kernel scope link\n"
        )
        assert parse_default_gateway(out) == "192.168.64.1"

    def test_empty_returns_none(self):
        assert parse_default_gateway("") is None
        assert parse_default_gateway(None) is None

    def test_no_default_route_returns_none(self):
        assert parse_default_gateway("172.17.0.0/16 dev docker0 scope link\n") is None

    def test_sidecar_base_url_formats_host_and_port(self):
        assert sidecar_base_url("172.26.112.1") == "http://172.26.112.1:7690"
        assert sidecar_base_url("10.0.0.5", port=8000) == "http://10.0.0.5:8000"
        assert sidecar_base_url(None) is None
