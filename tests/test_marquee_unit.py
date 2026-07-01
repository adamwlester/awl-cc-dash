import sys; from pathlib import Path
SIDECAR = Path(__file__).resolve().parents[1] / "sidecar"
if str(SIDECAR) not in sys.path: sys.path.insert(0, str(SIDECAR))
import marquee


# ---------------------------------------------------------------------------
# activity_verb
# ---------------------------------------------------------------------------

def test_activity_verb_read_uses_basename():
    block = {"type": "tool_use", "name": "Read",
             "input": {"file_path": "/home/user/proj/app.tsx"}}
    assert marquee.activity_verb(block) == "→ Read app.tsx"


def test_activity_verb_read_windows_path_basename():
    block = {"type": "tool_use", "name": "Read",
             "input": {"file_path": r"C:\Users\me\src\app.tsx"}}
    assert marquee.activity_verb(block) == "→ Read app.tsx"


def test_activity_verb_edit_uses_basename():
    block = {"type": "tool_use", "name": "Edit",
             "input": {"file_path": "src/renderer/App.tsx"}}
    assert marquee.activity_verb(block) == "→ Edit App.tsx"


def test_activity_verb_write_uses_basename():
    block = {"type": "tool_use", "name": "Write",
             "input": {"file_path": "notes.md"}}
    assert marquee.activity_verb(block) == "→ Write notes.md"


def test_activity_verb_bash_uses_command_prefix():
    block = {"type": "tool_use", "name": "Bash",
             "input": {"command": "npm test"}}
    assert marquee.activity_verb(block) == "→ Bash npm test"


def test_activity_verb_bash_truncates_long_command():
    cmd = "x" * 100
    block = {"type": "tool_use", "name": "Bash", "input": {"command": cmd}}
    verb = marquee.activity_verb(block)
    assert verb.startswith("→ Bash ")
    # first ~40 chars of the command retained
    assert "x" * 40 in verb
    # the full 100-char command is not carried through verbatim
    assert cmd not in verb


def test_activity_verb_bash_normalizes_command_whitespace():
    block = {"type": "tool_use", "name": "Bash",
             "input": {"command": "npm\n  test\t--watch"}}
    assert marquee.activity_verb(block) == "→ Bash npm test --watch"


def test_activity_verb_unknown_tool_just_name():
    block = {"type": "tool_use", "name": "Grep", "input": {"pattern": "foo"}}
    assert marquee.activity_verb(block) == "→ Grep"


def test_activity_verb_non_tool_block_returns_none():
    assert marquee.activity_verb({"type": "text", "text": "hello"}) is None


def test_activity_verb_missing_file_path_falls_back_to_name():
    block = {"type": "tool_use", "name": "Read", "input": {}}
    assert marquee.activity_verb(block) == "→ Read"


def test_activity_verb_missing_command_falls_back_to_name():
    block = {"type": "tool_use", "name": "Bash", "input": {}}
    assert marquee.activity_verb(block) == "→ Bash"


# ---------------------------------------------------------------------------
# marquee_line
# ---------------------------------------------------------------------------

def _assistant(*blocks):
    return {"type": "assistant", "content": list(blocks)}


def test_marquee_line_picks_latest_text():
    events = [
        _assistant({"type": "text", "text": "first line"}),
        _assistant({"type": "text", "text": "second line"}),
    ]
    assert marquee.marquee_line(events) == "second line"


def test_marquee_line_normalizes_newlines_to_single_line():
    events = [_assistant({"type": "text", "text": "hello\nworld\n  again"})]
    assert marquee.marquee_line(events) == "hello world again"


def test_marquee_line_collapses_all_whitespace():
    events = [_assistant({"type": "text", "text": "a\t\t b\r\nc   d"})]
    assert marquee.marquee_line(events) == "a b c d"


def test_marquee_line_truncates_past_max_len_with_ellipsis():
    long = "word " * 60  # 300 chars
    events = [_assistant({"type": "text", "text": long})]
    line = marquee.marquee_line(events, max_len=40)
    assert len(line) <= 40
    assert line.endswith("…")


def test_marquee_line_no_truncation_when_within_max_len():
    events = [_assistant({"type": "text", "text": "short"})]
    line = marquee.marquee_line(events, max_len=40)
    assert line == "short"
    assert not line.endswith("…")


def test_marquee_line_empty_events_returns_empty_string():
    assert marquee.marquee_line([]) == ""


def test_marquee_line_no_output_returns_empty_string():
    # events present but nothing renderable
    events = [{"type": "assistant", "content": []}]
    assert marquee.marquee_line(events) == ""


def test_marquee_line_falls_back_to_activity_verb_when_no_text():
    events = [
        _assistant({"type": "tool_use", "name": "Read",
                    "input": {"file_path": "app.tsx"}}),
    ]
    assert marquee.marquee_line(events) == "→ Read app.tsx"


def test_marquee_line_prefers_most_recent_meaningful_output():
    # newest event is a tool_use verb; it should win over an older text block
    events = [
        _assistant({"type": "text", "text": "old text"}),
        _assistant({"type": "tool_use", "name": "Bash",
                    "input": {"command": "npm test"}}),
    ]
    assert marquee.marquee_line(events) == "→ Bash npm test"


def test_marquee_line_skips_empty_text_blocks():
    events = [
        _assistant({"type": "text", "text": "meaningful"}),
        _assistant({"type": "text", "text": "   "}),
    ]
    assert marquee.marquee_line(events) == "meaningful"


# ---------------------------------------------------------------------------
# is_idle
# ---------------------------------------------------------------------------

def test_is_idle_true_on_empty_events():
    assert marquee.is_idle([]) is True


def test_is_idle_false_with_text_output():
    events = [_assistant({"type": "text", "text": "working"})]
    assert marquee.is_idle(events) is False


def test_is_idle_false_with_tool_output():
    events = [_assistant({"type": "tool_use", "name": "Read",
                          "input": {"file_path": "x.py"}})]
    assert marquee.is_idle(events) is False


def test_is_idle_true_when_no_renderable_output():
    events = [{"type": "assistant", "content": []}]
    assert marquee.is_idle(events) is True
