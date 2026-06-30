"""Hermetic unit tests for the OD-02 hook channel inbox (`sidecar/hookbus.py`).

Pure-logic: the durable per-agent inject inbox + the exact hook-output JSON the
installed build consumes (proved out live by the OD-02 spike). No live env.
"""
import sys
from pathlib import Path

import pytest

SIDECAR = Path(__file__).resolve().parents[1] / "sidecar"
if str(SIDECAR) not in sys.path:
    sys.path.insert(0, str(SIDECAR))

import hookbus  # noqa: E402


@pytest.fixture(autouse=True)
def _clean():
    hookbus.reset()
    yield
    hookbus.reset()


def test_enqueue_returns_stamped_inject():
    inj = hookbus.enqueue_inject("a1", "hello there", kind="inject", source="coder-01")
    assert inj["text"] == "hello there"
    assert inj["kind"] == "inject"
    assert inj["source"] == "coder-01"
    assert inj["id"]
    assert inj["created_at"]


def test_default_kind_is_inject():
    inj = hookbus.enqueue_inject("a1", "x")
    assert inj["kind"] == "inject"


def test_pending_lists_in_order():
    a = hookbus.enqueue_inject("a1", "one")
    b = hookbus.enqueue_inject("a1", "two")
    assert [i["text"] for i in hookbus.pending("a1")] == ["one", "two"]
    assert a["id"] != b["id"]


def test_pending_is_per_agent():
    hookbus.enqueue_inject("a1", "for-a1")
    hookbus.enqueue_inject("a2", "for-a2")
    assert [i["text"] for i in hookbus.pending("a1")] == ["for-a1"]
    assert [i["text"] for i in hookbus.pending("a2")] == ["for-a2"]


def test_drain_removes_and_returns():
    hookbus.enqueue_inject("a1", "one")
    hookbus.enqueue_inject("a1", "two")
    drained = hookbus.drain("a1")
    assert [i["text"] for i in drained] == ["one", "two"]
    assert hookbus.pending("a1") == []  # ack: gone after drain


def test_drain_by_kind_leaves_others():
    hookbus.enqueue_inject("a1", "active", kind="inject")
    hookbus.enqueue_inject("a1", "passive", kind="context")
    active = hookbus.drain("a1", kinds={"inject"})
    assert [i["text"] for i in active] == ["active"]
    # the passive context is NOT removed by an inject-only drain
    assert [i["text"] for i in hookbus.pending("a1")] == ["passive"]


def test_post_tool_use_output_shape():
    injects = [hookbus.enqueue_inject("a1", "peer says hi", source="coder-01")]
    out = hookbus.post_tool_use_output(injects)
    assert out["hookSpecificOutput"]["hookEventName"] == "PostToolUse"
    ctx = out["hookSpecificOutput"]["additionalContext"]
    assert "peer says hi" in ctx
    assert "coder-01" in ctx


def test_post_tool_use_output_empty_is_noop():
    assert hookbus.post_tool_use_output([]) == {}


def test_stop_output_blocks_with_reason():
    injects = [hookbus.enqueue_inject("a1", "answer the question", kind="inject")]
    out = hookbus.stop_output(injects)
    assert out["decision"] == "block"
    assert "answer the question" in out["reason"]


def test_stop_output_empty_is_noop():
    assert hookbus.stop_output([]) == {}


def test_render_caps_at_10k():
    big = "x" * 20000
    out = hookbus.post_tool_use_output([hookbus.enqueue_inject("a1", big)])
    ctx = out["hookSpecificOutput"]["additionalContext"]
    assert len(ctx) <= 10000


def test_reset_clears_all():
    hookbus.enqueue_inject("a1", "x")
    hookbus.reset()
    assert hookbus.pending("a1") == []
