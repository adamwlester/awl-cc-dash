"""Hermetic unit tests for the OD-09/OD-10 inbox store + classifiers
(`sidecar/inbox.py`). Pure-logic: the typed inbox sections, the error
pattern-match, and the OD-10 cap-crossing → Warning derivation. No live env.
"""
import sys
from pathlib import Path

import pytest

SIDECAR = Path(__file__).resolve().parents[1] / "sidecar"
if str(SIDECAR) not in sys.path:
    sys.path.insert(0, str(SIDECAR))

import inbox  # noqa: E402


@pytest.fixture(autouse=True)
def _clean():
    inbox.reset()
    yield
    inbox.reset()


def test_raise_and_list_item():
    it = inbox.raise_item("a1", "error", {"message": "boom"})
    assert it["type"] == "error" and it["agent_id"] == "a1"
    assert [i["id"] for i in inbox.items_for("a1")] == [it["id"]]


def test_resolve_item():
    it = inbox.raise_item("a1", "warning", {"subtype": "max_turns"})
    assert inbox.resolve_item("a1", it["id"]) is True
    assert inbox.items_for("a1") == []                  # open list excludes resolved
    assert inbox.resolve_item("a1", "nope") is False


def test_dedup_key_updates_not_duplicates():
    a = inbox.raise_item("a1", "error", {"message": "rate limit"}, dedup_key="err:rate")
    b = inbox.raise_item("a1", "error", {"message": "rate limit again"}, dedup_key="err:rate")
    assert a["id"] == b["id"]                            # same item, updated
    assert len(inbox.items_for("a1")) == 1
    assert inbox.items_for("a1")[0]["data"]["message"] == "rate limit again"


def test_fleet_badge_counts_agents_with_open_items():
    inbox.raise_item("a1", "error", {})
    inbox.raise_item("a1", "warning", {})
    inbox.raise_item("a2", "plan", {})
    assert inbox.fleet_badge() == 2                      # agents, not items
    # resolving all of a1's items drops it from the badge
    for i in list(inbox.items_for("a1")):
        inbox.resolve_item("a1", i["id"])
    assert inbox.fleet_badge() == 1


def test_all_open_groups_by_agent():
    inbox.raise_item("a1", "error", {})
    inbox.raise_item("a2", "decision", {})
    grouped = inbox.all_open()
    assert set(grouped.keys()) == {"a1", "a2"}


# --- OD-09 error classifier (best-effort pattern match) ---

@pytest.mark.parametrize("text,subtype", [
    ("Error: 429 rate limit exceeded", "rate_limit"),
    ("API error: 529 overloaded", "api"),
    ("MCP server failed to start", "tool_mcp"),
    ("tool execution failed", "tool_mcp"),
    ("Invalid configuration in settings.json", "config"),
])
def test_classify_error_matches(text, subtype):
    res = inbox.classify_error(text)
    assert res is not None and res["subtype"] == subtype


def test_classify_error_none_on_clean_text():
    assert inbox.classify_error("All good, ran the tests successfully.") is None


# --- OD-10 cap crossing -> Warning subtypes ---

def test_cap_warnings_max_turns():
    w = inbox.cap_warnings(turns=30, max_turns=25, context_pct=10, max_context_pct=80)
    subs = {x["subtype"] for x in w}
    assert "max_turns" in subs and "context_pct" not in subs


def test_cap_warnings_context_pct():
    w = inbox.cap_warnings(turns=5, max_turns=25, context_pct=85, max_context_pct=80)
    subs = {x["subtype"] for x in w}
    assert "context_pct" in subs and "max_turns" not in subs


def test_cap_warnings_none_when_under():
    assert inbox.cap_warnings(turns=1, max_turns=25, context_pct=10, max_context_pct=80) == []


def test_cap_warnings_ignores_unset_caps():
    assert inbox.cap_warnings(turns=999, max_turns=None, context_pct=99, max_context_pct=None) == []
