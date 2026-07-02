"""Hermetic unit tests for permanent Delete planning (`sidecar/deletion.py`).

Pure-logic, no live agents, no real filesystem deletion. Delete is a HARD,
irreversible wipe governed by one rule: WIPE the agent's private footprint
(runtime record, tmux session, on-disk transcripts) and TOMBSTONE everything
shared (scratchpad posts, feed events, link history). The agent's NUMBER is
permanently retired and never reused. This module only PLANS/marks; the
orchestrator wires the real wipe.
"""
import sys
from pathlib import Path

import pytest

SIDECAR = Path(__file__).resolve().parents[1] / "sidecar"
if str(SIDECAR) not in sys.path:
    sys.path.insert(0, str(SIDECAR))

import deletion  # noqa: E402


@pytest.fixture(autouse=True)
def _clean():
    deletion.reset()
    yield
    deletion.reset()


# --- plan_deletion -------------------------------------------------------

def test_plan_deletion_full_shape():
    plan = deletion.plan_deletion(
        "agent-7",
        transcript_path="/x/main.jsonl",
        subagent_paths=["/x/sub1.jsonl", "/x/sub2.jsonl"],
        link_ids=["L1", "L2"],
        identity_number=7,
    )
    assert plan["wipe"]["runtime_record"] == "agent-7"
    assert plan["wipe"]["tmux"] is True
    assert plan["wipe"]["transcripts"] == [
        "/x/main.jsonl", "/x/sub1.jsonl", "/x/sub2.jsonl",
    ]
    assert plan["tombstone"]["links"] == ["L1", "L2"]
    assert plan["tombstone"]["retired_number"] == 7
    assert plan["clear"]["queue"] is True
    assert plan["clear"]["inbox"] is True


def test_plan_deletion_includes_transcript_and_subagents():
    plan = deletion.plan_deletion(
        "a1",
        transcript_path="/main.jsonl",
        subagent_paths=["/s1.jsonl", "/s2.jsonl"],
    )
    assert plan["wipe"]["transcripts"] == ["/main.jsonl", "/s1.jsonl", "/s2.jsonl"]


def test_plan_deletion_omits_none_transcripts():
    # No main transcript, a None mixed into subagents.
    plan = deletion.plan_deletion(
        "a1",
        transcript_path=None,
        subagent_paths=["/s1.jsonl", None, "/s2.jsonl"],
    )
    assert plan["wipe"]["transcripts"] == ["/s1.jsonl", "/s2.jsonl"]
    assert None not in plan["wipe"]["transcripts"]


def test_plan_deletion_empty_defaults():
    plan = deletion.plan_deletion("a1")
    assert plan["wipe"]["runtime_record"] == "a1"
    assert plan["wipe"]["tmux"] is True
    assert plan["wipe"]["transcripts"] == []
    assert plan["tombstone"]["links"] == []
    assert plan["tombstone"]["retired_number"] is None
    assert plan["clear"] == {"queue": True, "inbox": True}


def test_plan_deletion_available_from_any_state():
    # Running agents are interrupted+closed first; the plan always asks tmux close.
    plan = deletion.plan_deletion("running-agent", identity_number=3)
    assert plan["wipe"]["tmux"] is True


# --- tombstone_event -----------------------------------------------------

def test_tombstone_event_marks_deleted_keeps_attribution():
    ev = {"id": "e1", "source": "agent-7", "text": "hello", "ts": 123}
    out = deletion.tombstone_event(ev)
    assert out["deleted"] is True
    assert out["source"] == "agent-7"   # attribution preserved
    assert out["text"] == "hello"
    assert out["ts"] == 123


def test_tombstone_event_does_not_mutate_input():
    ev = {"id": "e1", "source": "agent-7", "text": "hello"}
    out = deletion.tombstone_event(ev)
    assert "deleted" not in ev          # input untouched
    assert out is not ev                # a copy
    out["text"] = "changed"
    assert ev["text"] == "hello"        # deep enough independence at top level


def test_tombstone_event_preserves_identity_fields():
    ev = {"source": "agent-9", "author": "agent-9", "agent_id": "agent-9", "body": "x"}
    out = deletion.tombstone_event(ev)
    assert out["source"] == "agent-9"
    assert out["author"] == "agent-9"
    assert out["agent_id"] == "agent-9"
    assert out["deleted"] is True


# --- tombstone_link ------------------------------------------------------

def test_tombstone_link_inactive_and_deleted():
    lk = {"id": "L1", "a": "A", "b": "B", "active": True}
    out = deletion.tombstone_link(lk)
    assert out["active"] is False
    assert out["deleted"] is True
    assert out["a"] == "A" and out["b"] == "B"


def test_tombstone_link_does_not_mutate_input():
    lk = {"id": "L1", "active": True}
    out = deletion.tombstone_link(lk)
    assert lk["active"] is True         # input untouched
    assert "deleted" not in lk
    assert out is not lk


# --- retired-number registry --------------------------------------------

def test_retire_then_is_retired():
    assert deletion.is_retired(5) is False
    deletion.retire_number(5)
    assert deletion.is_retired(5) is True


def test_next_free_number_skips_retired():
    deletion.retire_number(1)
    deletion.retire_number(2)
    assert deletion.next_free_number(1) == 3


def test_next_free_number_default_start():
    assert deletion.next_free_number() == 1
    deletion.retire_number(1)
    assert deletion.next_free_number() == 2


def test_next_free_number_monotonic_past_gaps():
    # Even with a non-contiguous retired set, return lowest non-retired >= start.
    for n in (3, 4, 5):
        deletion.retire_number(n)
    assert deletion.next_free_number(3) == 6
    assert deletion.next_free_number(1) == 1   # 1 isn't retired


def test_retired_numbers_never_recycled():
    # A tombstoned number stays retired so old tombstones never collide.
    deletion.retire_number(7)
    n = deletion.next_free_number(1)
    deletion.retire_number(n)
    assert deletion.is_retired(7) is True
    assert deletion.next_free_number(1) != 7


def test_reset_clears_registry():
    deletion.retire_number(42)
    assert deletion.is_retired(42) is True
    deletion.reset()
    assert deletion.is_retired(42) is False
    assert deletion.next_free_number(1) == 1


def test_plan_deletion_retires_via_registry_independently():
    # plan_deletion records the retired_number in the tombstone, but the
    # registry is a separate concern the orchestrator drives explicitly.
    plan = deletion.plan_deletion("a1", identity_number=11)
    assert plan["tombstone"]["retired_number"] == 11
    # Registry only changes when retire_number is called.
    assert deletion.is_retired(11) is False
    deletion.retire_number(11)
    assert deletion.is_retired(11) is True
