"""Hermetic unit tests for the Tier-2 link store + caps + grouping + the
piggyback park-store (`sidecar/links.py`). Pure-logic: no live agents.

THE DECIDED CONTRACT (ARCHITECTURE §7.6, the §11 #25 model fixes):

  * **One relationship per link** — ``Link.relationship`` is a single string,
    ``"direct"`` | ``"shared"``; wanting both between the same two agents =
    two links. A persisted legacy LIST restores as its FIRST entry (a both-list
    becomes the direct link, warning logged — the recorded degrade).
  * **Trigger vocabulary** is Now/Next/Queue/Inject/Hold/**Piggyback**, with
    per-relationship defaults applied when the caller passes no trigger:
    direct → queue, shared → piggyback.
  * **Piggyback never initiates a turn** — payloads park on a per-target
    pending list (``park_piggyback``/``take_piggyback``) and ride the target's
    next delivered message (the prepend lives in ``main._flush_queue``).
  * **Exchange counting is direction-aware** — on a one-way link (a2b/b2a)
    every fire = one exchange (End-After binds at full rate); on a two-way link
    an exchange stays one message each direction (messages ÷ 2).

The serialized reply-to ENGINE (the on-idle relay) and the shared-context fire
are exercised separately against the sidecar (test_sidecar_unit.py) + live.
"""
import logging
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


# -----------------------------------------------------------------------------
# Defaults + the one-relationship model
# -----------------------------------------------------------------------------

def test_add_link_defaults():
    lk = links.add_link(a="A", b="B")
    assert lk.id
    assert lk.direction == "both"
    assert lk.relationship == "direct"    # ONE relationship, a string (§7.6)
    assert lk.trigger == "queue"          # the direct-messaging default
    assert lk.end_after_exchanges == 25   # decided default end-after budget for a link
    assert lk.active is True


def test_shared_link_defaults_to_piggyback_trigger():
    # §7.6 defaults: Shared context → Piggyback (an active delivery would cost
    # the target a whole turn just to ingest it).
    lk = links.add_link(a="A", b="B", relationship="shared")
    assert lk.relationship == "shared"
    assert lk.trigger == "piggyback"


def test_explicit_trigger_wins_over_default():
    lk = links.add_link(a="A", b="B", relationship="shared", trigger="queue")
    assert lk.trigger == "queue"


def test_one_relationship_per_link_is_exclusive():
    d = links.add_link(a="A", b="B", relationship="direct")
    s = links.add_link(a="A", b="B", relationship="shared")   # both = TWO links
    assert d.is_direct() and not d.is_shared()
    assert s.is_shared() and not s.is_direct()


def test_invalid_relationship_coerces_to_direct():
    lk = links.add_link(a="A", b="B", relationship="frobnicate")
    assert lk.relationship == "direct"
    assert lk.trigger == "queue"


# -----------------------------------------------------------------------------
# Direction gating (unchanged by the split)
# -----------------------------------------------------------------------------

def test_direction_gating():
    both = links.add_link(a="A", b="B", direction="both")
    assert both.allows("A", "B") and both.allows("B", "A")
    a2b = links.add_link(a="A", b="B", direction="a2b")
    assert a2b.allows("A", "B") and not a2b.allows("B", "A")
    b2a = links.add_link(a="A", b="B", direction="b2a")
    assert b2a.allows("B", "A") and not b2a.allows("A", "B")


# -----------------------------------------------------------------------------
# Direction-aware exchange counting + End-After caps
# -----------------------------------------------------------------------------

def test_exchanges_one_way_counts_every_fire():
    lk = links.add_link(a="A", b="B", direction="a2b")
    lk.messages = 3
    assert lk.exchanges == 3              # one-way: every fire = one exchange


def test_exchanges_two_way_counts_pairs():
    lk = links.add_link(a="A", b="B", direction="both")
    lk.messages = 3
    assert lk.exchanges == 1              # two-way: one each direction = 1


def test_over_cap_one_way_burns_per_fire():
    lk = links.add_link(a="A", b="B", direction="a2b", end_after_exchanges=2)
    lk.messages = 1
    assert not lk.over_cap()
    lk.messages = 2                       # second fire hits the cap (full rate)
    assert lk.over_cap()


def test_over_cap_two_way_by_exchanges():
    lk = links.add_link(a="A", b="B", direction="both", end_after_exchanges=1)
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


# -----------------------------------------------------------------------------
# Serialization + grouping
# -----------------------------------------------------------------------------

def test_to_dict_serializes_string_relationship_and_direction_aware_exchanges():
    lk = links.add_link(a="A", b="B", direction="a2b", relationship="shared")
    lk.messages = 2
    d = lk.to_dict()
    assert d["relationship"] == "shared"  # the key name is unchanged; a string now
    assert d["trigger"] == "piggyback"
    assert d["exchanges"] == 2            # one-way: exchanges == messages


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
    l2 = links.add_link(a="A", b="C", relationship="shared")
    grouped = links.grouped_by_agent()
    assert set(grouped.keys()) == {"A", "B", "C"}
    # A is in both links; B and C in one each (deliberate double-listing).
    assert {e["link_id"] for e in grouped["A"]} == {l1.id, l2.id}
    assert {e["other"] for e in grouped["A"]} == {"B", "C"}
    assert [e["link_id"] for e in grouped["B"]] == [l1.id]
    assert grouped["B"][0]["other"] == "A"
    assert grouped["B"][0]["relationship"] == "direct"    # a string, not a list
    assert grouped["C"][0]["relationship"] == "shared"


# -----------------------------------------------------------------------------
# Lookup
# -----------------------------------------------------------------------------

def test_find_direct_link_either_orientation():
    lk = links.add_link(a="A", b="B", relationship="direct")
    assert links.find_direct_link("A", "B") is lk
    assert links.find_direct_link("B", "A") is lk
    assert links.find_direct_link("A", "Z") is None


def test_find_direct_link_ignores_shared_links():
    links.add_link(a="A", b="B", relationship="shared")
    assert links.find_direct_link("A", "B") is None      # shared ≠ conversation
    d = links.add_link(a="A", b="B", relationship="direct")
    assert links.find_direct_link("A", "B") is d


def test_remove_link():
    lk = links.add_link(a="A", b="B")
    assert links.get_link(lk.id) is lk
    links.remove_link(lk.id)
    assert links.get_link(lk.id) is None


def test_inactive_link_excluded_from_direct_lookup():
    lk = links.add_link(a="A", b="B")
    lk.active = False
    assert links.find_direct_link("A", "B") is None


# -----------------------------------------------------------------------------
# restore() backward-compat — the legacy list-relationship degrade
# -----------------------------------------------------------------------------

def test_restore_legacy_both_list_becomes_direct_with_warning(caplog):
    with caplog.at_level(logging.WARNING, logger="awl-sidecar.links"):
        links.restore([{"id": "lnk9", "a": "A", "b": "B",
                        "relationship": ["direct", "shared"]}])
    lk = links.get_link("lnk9")
    assert lk is not None
    assert lk.relationship == "direct"    # FIRST entry wins; the rest is dropped
    assert any("lnk9" in r.message for r in caplog.records)  # recorded degrade


def test_restore_legacy_single_entry_list_converts_silently(caplog):
    with caplog.at_level(logging.WARNING, logger="awl-sidecar.links"):
        links.restore([{"id": "lnk1", "a": "A", "b": "B",
                        "relationship": ["shared"], "trigger": "piggyback"}])
    assert links.get_link("lnk1").relationship == "shared"
    assert not caplog.records              # lossless conversion — no warning


def test_restore_new_string_format_passes_through():
    links.restore([{"id": "lnk2", "a": "A", "b": "B", "relationship": "shared",
                    "trigger": "piggyback", "messages": 4, "active": True,
                    "direction": "a2b"}])
    lk = links.get_link("lnk2")
    assert lk.relationship == "shared"
    assert lk.exchanges == 4               # one-way counters survive the reload


def test_restore_missing_or_invalid_relationship_defaults_direct():
    links.restore([
        {"id": "lnk3", "a": "A", "b": "B"},
        {"id": "lnk4", "a": "A", "b": "B", "relationship": "bogus"},
        {"id": "lnk5", "a": "A", "b": "B", "relationship": []},
    ])
    assert links.get_link("lnk3").relationship == "direct"
    assert links.get_link("lnk4").relationship == "direct"
    assert links.get_link("lnk5").relationship == "direct"


def test_restore_advances_id_counter_past_loaded_ids():
    links.restore([{"id": "lnk7", "a": "A", "b": "B", "relationship": "direct"}])
    fresh = links.add_link(a="X", b="Y")
    assert fresh.id != "lnk7"


# -----------------------------------------------------------------------------
# Piggyback park-store (§7.6 — never initiates; rides the next delivery)
# -----------------------------------------------------------------------------

def test_piggyback_park_pending_take():
    links.park_piggyback("B", source="A", link_id="lnk1", text="peer update")
    links.park_piggyback("B", source="C", link_id="lnk2", text="second share")
    pending = links.pending_piggyback("B")
    assert [p["text"] for p in pending] == ["peer update", "second share"]
    assert pending[0]["source"] == "A" and pending[0]["link_id"] == "lnk1"
    # pending_piggyback is a view — nothing consumed yet
    assert len(links.pending_piggyback("B")) == 2
    # take drains exactly once
    taken = links.take_piggyback("B")
    assert [p["text"] for p in taken] == ["peer update", "second share"]
    assert links.pending_piggyback("B") == []
    assert links.take_piggyback("B") == []


def test_piggyback_is_per_target():
    links.park_piggyback("B", source="A", link_id="l1", text="for B")
    links.park_piggyback("C", source="A", link_id="l2", text="for C")
    assert [p["text"] for p in links.take_piggyback("B")] == ["for B"]
    assert [p["text"] for p in links.pending_piggyback("C")] == ["for C"]


def test_reset_clears_piggyback_store():
    links.park_piggyback("B", source="A", link_id="l", text="x")
    links.reset()
    assert links.pending_piggyback("B") == []


def test_default_trigger_helper():
    assert links.default_trigger("direct") == "queue"
    assert links.default_trigger("shared") == "piggyback"
