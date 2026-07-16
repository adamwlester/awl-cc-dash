"""Hermetic unit tests for the inbox store + classifiers
(`sidecar/inbox.py`). Pure-logic: the typed inbox sections, the error
pattern-match, the cap-crossing → Warning derivation, and the §11 #23
workflow-approval pieces that live here (the `parse_workflow_script` Review
preview parser, the open-item `update_item_data` merge, and the
env-configurable `workflow_approval_timeout_s` hold knob). No live env.
"""
import os
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


# --- Workflow-approval gate pieces (§11 #23) ---

# A compacted stand-in for a real Workflow script's `export const meta` block —
# the same field shapes the live spike's subject_workflow.js carries (mixed
# ' and " quoting is deliberate: the parser must tolerate both).
_WF_SCRIPT = (
    "export const meta = { name: 'demo-flow', "
    'description: "reviews a thing before it runs", '
    "phases: [ { title: 'Solo', agents: 1 }, { title: \"Wrap\" } ] }; "
    "export default async function run() {}"
)


def test_parse_workflow_script_recovers_preview():
    """The Review card's preview: name / description / phase titles recover
    from tool_input.script (spike-proven readable from the hook payload)."""
    p = inbox.parse_workflow_script(_WF_SCRIPT)
    assert p["has_meta"] is True
    assert p["name"] == "demo-flow"
    assert p["description"] == "reviews a thing before it runs"
    assert p["phase_titles"] == ["Solo", "Wrap"]


def test_parse_workflow_script_empty_never_raises():
    """Missing/empty script yields the all-empty preview shape, never raises —
    the hook endpoint must survive a payload with no script."""
    for script in (None, ""):
        p = inbox.parse_workflow_script(script)
        assert p == {"has_meta": False, "name": None, "description": None,
                     "phase_titles": []}


def test_parse_workflow_script_no_meta_block():
    """A script without `export const meta` parses tolerantly: has_meta False,
    whatever name:/title: fields exist are still best-effort recovered."""
    p = inbox.parse_workflow_script("export default async function run() {}")
    assert p["has_meta"] is False and p["name"] is None and p["phase_titles"] == []


def test_parse_workflow_script_scopes_to_meta_and_word_bounds():
    """Field searches are word-bounded and scoped to the meta block, so decoys
    can't misattribute the approval card (review finding): a `filename:` or a
    comment's `rename:` before meta must not win over the real `name:`, a
    `subtitle:` inside a phase must not become a phase title, and a `title:`
    inside an agent-prompt string OUTSIDE meta must not appear at all."""
    script = (
        "// rename: 'old-decoy' header comment; "
        "const cfg = { filename: 'helper.js' }; "
        "export const meta = { name: 'real-name', "
        "description: 'real description', "
        "phases: [ { title: 'Solo', subtitle: 'B side' } ] }; "
        "const p = await agent(\"set title: 'boss' now\");"
    )
    p = inbox.parse_workflow_script(script)
    assert p["has_meta"] is True
    assert p["name"] == "real-name"
    assert p["description"] == "real description"
    assert p["phase_titles"] == ["Solo"]


def test_read_script_for_preview_reads_file(tmp_path):
    """scriptPath-launched workflows (review finding): the reader returns the
    file's text for a reachable path and None — never raising — for a missing
    path or a non-string value (the card then shows the raw path only)."""
    wf = tmp_path / "flow.js"
    wf.write_text(_WF_SCRIPT, encoding="utf-8")
    assert inbox.read_script_for_preview(str(wf)) == _WF_SCRIPT
    assert inbox.read_script_for_preview(str(tmp_path / "gone.js")) is None
    assert inbox.read_script_for_preview(None) is None
    assert inbox.read_script_for_preview({"not": "a path"}) is None


@pytest.mark.skipif(os.name != "nt", reason="drive-letter translation is Windows-side")
def test_read_script_for_preview_translates_wsl_mnt_path(tmp_path):
    """A WSL `/mnt/<drive>/` scriptPath (how a bridge agent names a Windows
    file, e.g. the Library's stored workflows) resolves via the Windows
    translation when the literal path doesn't exist on this side."""
    wf = tmp_path / "flow.js"
    wf.write_text(_WF_SCRIPT, encoding="utf-8")
    win = str(wf)                      # e.g. C:\Users\...\flow.js
    wsl = f"/mnt/{win[0].lower()}/{win[3:].replace(chr(92), '/')}"
    assert inbox.read_script_for_preview(wsl) == _WF_SCRIPT


def test_update_item_data_merges_into_open_item():
    """update_item_data merges fields into an OPEN item's data (the workflow
    gate stamps timed_out this way) and leaves the rest of the data intact."""
    it = inbox.raise_item("a1", "review", {"preview": {"name": "x"}})
    assert inbox.update_item_data("a1", it["id"], {"timed_out": True}) is True
    got = inbox.get_item("a1", it["id"])
    assert got["data"]["timed_out"] is True
    assert got["data"]["preview"] == {"name": "x"}          # merge, not replace


def test_update_item_data_skips_resolved_and_missing():
    it = inbox.raise_item("a1", "review", {})
    inbox.resolve_item("a1", it["id"])
    assert inbox.update_item_data("a1", it["id"], {"timed_out": True}) is False
    assert inbox.update_item_data("a1", "nope", {"x": 1}) is False


def test_workflow_approval_timeout_env_knob(monkeypatch):
    """The hold timeout defaults to 600 s, honors AWL_WORKFLOW_APPROVAL_TIMEOUT
    at call time, and falls back to the default on an unparsable value."""
    monkeypatch.delenv("AWL_WORKFLOW_APPROVAL_TIMEOUT", raising=False)
    assert inbox.workflow_approval_timeout_s() == 600.0
    monkeypatch.setenv("AWL_WORKFLOW_APPROVAL_TIMEOUT", "12.5")
    assert inbox.workflow_approval_timeout_s() == 12.5
    monkeypatch.setenv("AWL_WORKFLOW_APPROVAL_TIMEOUT", "not-a-number")
    assert inbox.workflow_approval_timeout_s() == 600.0


# --- Error classifier (best-effort pattern match) ---

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


# --- Cap crossing -> Warning subtypes ---

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
