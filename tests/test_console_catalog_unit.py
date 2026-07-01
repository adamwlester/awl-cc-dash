"""Hermetic unit tests for the Console slash-command runner catalog (OD-20).

Pure logic: no server, no tmux/WSL2, no bridge, no driver. Exercises the
``console_catalog`` module's catalog data and classification helpers directly.

The Console runner (product UI) needs a COMPLETE, grouped catalog of Claude
Code slash-commands plus a way to tell which ones drop the agent into a
sub-prompt (interactive) so the live wiring elsewhere can handle the follow-on
interaction rather than blind-sending. This module owns the catalog + the
classification; these tests pin the contract.

No ``integration`` / ``slow`` mark — this is fully hermetic.
"""

import sys
from pathlib import Path

SIDECAR = Path(__file__).resolve().parents[1] / "sidecar"
if str(SIDECAR) not in sys.path:
    sys.path.insert(0, str(SIDECAR))

import console_catalog as cc  # noqa: E402


# The six clusters, in the authoritative display order (OD-20 Decision).
EXPECTED_CLUSTERS = [
    "Session & context",
    "Model & behavior",
    "Info & status",
    "Tools & integrations",
    "Project & custom",
    "System",
]

REQUIRED_KEYS = {"command", "description", "cluster", "interactive"}


# --------------------------------------------------------------------------- #
# clusters()
# --------------------------------------------------------------------------- #

def test_clusters_returns_the_six_names_in_order():
    assert cc.clusters() == EXPECTED_CLUSTERS


def test_clusters_returns_a_fresh_list_each_call():
    a = cc.clusters()
    a.append("MUTATED")
    assert cc.clusters() == EXPECTED_CLUSTERS  # internal state not corrupted


# --------------------------------------------------------------------------- #
# CATALOG shape
# --------------------------------------------------------------------------- #

def test_catalog_is_nonempty_list_of_wellformed_entries():
    assert isinstance(cc.CATALOG, list)
    assert len(cc.CATALOG) > 0
    for entry in cc.CATALOG:
        assert isinstance(entry, dict)
        # Required keys present.
        assert REQUIRED_KEYS <= set(entry.keys())
        assert entry["command"].startswith("/")
        assert isinstance(entry["description"], str) and entry["description"].strip()
        assert entry["cluster"] in EXPECTED_CLUSTERS
        assert isinstance(entry["interactive"], bool)
        # also_in is either None or one of the cluster names / panel names.
        assert "also_in" in entry
        assert entry["also_in"] is None or isinstance(entry["also_in"], str)


def test_commands_are_unique():
    commands = [e["command"] for e in cc.CATALOG]
    assert len(commands) == len(set(commands))


# --------------------------------------------------------------------------- #
# by_cluster()
# --------------------------------------------------------------------------- #

def test_by_cluster_has_all_six_and_each_is_nonempty():
    grouped = cc.by_cluster()
    assert set(grouped.keys()) == set(EXPECTED_CLUSTERS)
    for name in EXPECTED_CLUSTERS:
        assert len(grouped[name]) > 0, f"cluster {name!r} is empty"


def test_by_cluster_preserves_display_order():
    grouped = cc.by_cluster()
    assert list(grouped.keys()) == EXPECTED_CLUSTERS


def test_by_cluster_covers_every_catalog_entry():
    grouped = cc.by_cluster()
    total = sum(len(v) for v in grouped.values())
    assert total == len(cc.CATALOG)


# --------------------------------------------------------------------------- #
# filter_commands()
# --------------------------------------------------------------------------- #

def test_filter_matches_on_command_case_insensitive():
    # /model lives in the catalog; match on the command text, mixed case.
    hits = cc.filter_commands("MoDeL")
    assert any(e["command"] == "/model" for e in hits)


def test_filter_matches_on_description_text():
    # "context" appears in a description (e.g. /clear or /compact frees context).
    hits = cc.filter_commands("context")
    assert len(hits) > 0
    for e in hits:
        blob = (e["command"] + " " + e["description"]).lower()
        assert "context" in blob


def test_filter_empty_query_returns_everything():
    assert len(cc.filter_commands("")) == len(cc.CATALOG)
    assert len(cc.filter_commands("   ")) == len(cc.CATALOG)


def test_filter_no_match_returns_empty():
    assert cc.filter_commands("zzz-nonexistent-token-qqq") == []


# --------------------------------------------------------------------------- #
# is_interactive()
# --------------------------------------------------------------------------- #

def test_is_interactive_true_for_model_and_clear():
    assert cc.is_interactive("/model") is True
    assert cc.is_interactive("/clear") is True


def test_is_interactive_false_for_help_and_status():
    assert cc.is_interactive("/help") is False
    assert cc.is_interactive("/status") is False


def test_is_interactive_unknown_command_is_false():
    assert cc.is_interactive("/does-not-exist") is False


# --------------------------------------------------------------------------- #
# get()
# --------------------------------------------------------------------------- #

def test_get_returns_entry_with_required_keys():
    entry = cc.get("/model")
    assert entry is not None
    assert REQUIRED_KEYS <= set(entry.keys())
    assert entry["command"] == "/model"


def test_get_unknown_returns_none():
    assert cc.get("/nope-not-a-command") is None


# --------------------------------------------------------------------------- #
# also_in tagging (commands with a home elsewhere are still listed)
# --------------------------------------------------------------------------- #

def test_at_least_model_or_mcp_is_tagged_also_available_elsewhere():
    model = cc.get("/model")
    mcp = cc.get("/mcp")
    assert model is not None and mcp is not None
    assert (model["also_in"] is not None) or (mcp["also_in"] is not None)
