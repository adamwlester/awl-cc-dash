"""Hermetic tests for the shared scratchpad log + auto-read delta
(`sidecar/scratchpad.py`). Pure/in-memory + optional md persistence on tmp_path.
"""
import sys
from pathlib import Path

import pytest

SIDECAR = Path(__file__).resolve().parents[1] / "sidecar"
if str(SIDECAR) not in sys.path:
    sys.path.insert(0, str(SIDECAR))

import scratchpad  # noqa: E402
import watermark  # noqa: E402


@pytest.fixture(autouse=True)
def _clean():
    scratchpad.reset()
    watermark.reset()
    yield
    scratchpad.reset()
    watermark.reset()


def test_post_assigns_monotonic_seq():
    a = scratchpad.post("proj", "coder-01", "touched foo.py")
    b = scratchpad.post("proj", "coder-02", "touched bar.py")
    assert a["seq"] == 1 and b["seq"] == 2
    assert a["author"] == "coder-01" and a["text"] == "touched foo.py"
    assert [p["seq"] for p in scratchpad.all_posts("proj")] == [1, 2]


def test_projects_are_isolated():
    scratchpad.post("projA", "x", "a")
    scratchpad.post("projB", "y", "b")
    assert [p["text"] for p in scratchpad.all_posts("projA")] == ["a"]
    assert [p["text"] for p in scratchpad.all_posts("projB")] == ["b"]


def test_first_read_is_full_board_then_deltas():
    scratchpad.post("proj", "a", "one")
    scratchpad.post("proj", "a", "two")
    first = scratchpad.unread("agentX", "proj")
    assert [p["text"] for p in first] == ["one", "two"]        # full board
    assert scratchpad.unread("agentX", "proj") == []           # nothing new
    scratchpad.post("proj", "b", "three")
    assert [p["text"] for p in scratchpad.unread("agentX", "proj")] == ["three"]


def test_unread_is_per_agent():
    scratchpad.post("proj", "a", "one")
    assert len(scratchpad.unread("A", "proj")) == 1
    assert len(scratchpad.unread("B", "proj")) == 1   # B has its own watermark


def test_includes_own_posts_in_delta():
    # An agent sees its own posts positioned in the shared timeline (no echo loop
    # because reading never emits a post).
    scratchpad.post("proj", "A", "mine")
    assert [p["author"] for p in scratchpad.unread("A", "proj")] == ["A"]


def test_render_delta_has_attribution():
    posts = [scratchpad.post("proj", "coder-01", "touched foo.py")]
    text = scratchpad.render(posts)
    assert "coder-01" in text and "touched foo.py" in text


def test_persist_writes_markdown(tmp_path):
    md = tmp_path / ".awl" / "scratchpad.md"
    scratchpad.post("proj", "coder-01", "hello board", persist_path=str(md))
    assert md.exists()
    content = md.read_text(encoding="utf-8")
    assert "coder-01" in content and "hello board" in content


def test_reset_clears():
    scratchpad.post("proj", "a", "x")
    scratchpad.reset()
    assert scratchpad.all_posts("proj") == []
