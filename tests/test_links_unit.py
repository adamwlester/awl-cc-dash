"""Hermetic unit tests for the Tier-2 link store + caps + grouping
(`sidecar/links.py`). Pure-logic: no live agents. The serialized reply-to ENGINE
(the on-idle relay) is exercised separately against the sidecar + live.
"""
import sys
from pathlib import Path

import pytest

SIDECAR = Path(__file__).resolve().parents[1] / "sidecar"
if str(SIDECAR) not in sys.path:
    sys.path.insert(0, str(SIDECAR))

import links  # noqa: E402


@pytest.fixture(autouse=True)
def _clean():
    links.reset()
    yield
    links.reset()


def test_add_link_defaults():
    lk = links.add_link(a="A", b="B")
    assert lk.id
    assert lk.direction == "both"
    assert lk.relationship == ["direct"]
    assert lk.trigger == "queue"
    assert lk.end_after_exchanges == 25   # decided default end-after budget for a link
    assert lk.active is True


def test_direction_gating():
    both = links.add_link(a="A", b="B", direction="both")
    assert both.allows("A", "B") and both.allows("B", "A")
    a2b = links.add_link(a="A", b="B", direction="a2b")
    assert a2b.allows("A", "B") and not a2b.allows("B", "A")
    b2a = links.add_link(a="A", b="B", direction="b2a")
    assert b2a.allows("B", "A") and not b2a.allows("A", "B")


def test_over_cap_by_exchanges():
    lk = links.add_link(a="A", b="B", end_after_exchanges=1)
    assert not lk.over_cap()
    lk.messages = 1          # half a round-trip
    assert not lk.over_cap()
    lk.messages = 2          # one full exchange (each direction once)
    assert lk.over_cap()


def test_over_cap_by_tokens():
    lk = links.add_link(a="A", b="B", end_after_exchanges=None, end_after_tokens=100)
    lk.tokens = 99
    assert not lk.over_cap()
    lk.tokens = 100
    assert lk.over_cap()


def test_no_caps_never_over():
    lk = links.add_link(a="A", b="B", end_after_exchanges=None, end_after_tokens=None)
    lk.messages = 9999
    lk.tokens = 9_000_000
    assert not lk.over_cap()


def test_other_and_arrow_relative_to_group():
    lk = links.add_link(a="A", b="B", direction="a2b")
    assert lk.other("A") == "B" and lk.other("B") == "A"
    # arrow relative to the group agent: a2b => A sees "→" (to B), B sees "←" (from A)
    assert lk.arrow_for("A") == "→"
    assert lk.arrow_for("B") == "←"
    both = links.add_link(a="A", b="B", direction="both")
    assert both.arrow_for("A") == "↔" and both.arrow_for("B") == "↔"


def test_grouped_by_agent_double_lists():
    l1 = links.add_link(a="A", b="B")
    l2 = links.add_link(a="A", b="C")
    grouped = links.grouped_by_agent()
    assert set(grouped.keys()) == {"A", "B", "C"}
    # A is in both links; B and C in one each (deliberate double-listing).
    assert {e["link_id"] for e in grouped["A"]} == {l1.id, l2.id}
    assert {e["other"] for e in grouped["A"]} == {"B", "C"}
    assert [e["link_id"] for e in grouped["B"]] == [l1.id]
    assert grouped["B"][0]["other"] == "A"


def test_find_direct_link_either_orientation():
    lk = links.add_link(a="A", b="B", relationship=["direct"])
    assert links.find_direct_link("A", "B") is lk
    assert links.find_direct_link("B", "A") is lk
    assert links.find_direct_link("A", "Z") is None


def test_remove_link():
    lk = links.add_link(a="A", b="B")
    assert links.get_link(lk.id) is lk
    links.remove_link(lk.id)
    assert links.get_link(lk.id) is None


def test_inactive_link_excluded_from_direct_lookup():
    lk = links.add_link(a="A", b="B")
    lk.active = False
    assert links.find_direct_link("A", "B") is None
