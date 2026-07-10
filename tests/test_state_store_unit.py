"""Hermetic unit tests for the per-project state store (ARCHITECTURE §8.2/§8.3, §11 #3/#4/#42).

The decided contract this file encodes:

  * Everything in the §8.3 Persist rows is small JSON **written as it changes**
    (write-through via module persist hooks) into the open project's
    ``<project>/.awl-cc-dash/state/`` — ``agents.json`` (roster + retired
    numbers), ``inbox.json``, ``links.json``, ``bookmarks.json``, and the
    append-only ``routing.jsonl`` (NON-default routing only).
  * Writes are **atomic write-replace** per file (§8.7) and every committed JSON
    carries a ``schema_version`` stamp (#42).
  * Loading is **lazy per project** and idempotent: the first session whose
    canonical root resolves to the project seeds the in-memory modules (inbox /
    links / watermark / deletion) and reloads the scratchpad board from its
    ``docs/scratchpad.md`` (the ``.md`` IS the board's persistence, §8.3), with
    id/seq counters advanced past everything reloaded.
  * The roster lives per-project: ``runtime_store.save_record`` routes records
    with a resolvable project cwd into ``state/agents.json`` (+ the 🏠
    ``projects.json`` index, §3.5); cwd-less records fall back to the app-level
    ``sessions.json``. ``all_records()`` aggregates both.

No WSL, no network, no live agent — pure files on tmp_path.
"""

import json
import sys
from pathlib import Path

import pytest

_SIDECAR = Path(__file__).resolve().parent.parent / "sidecar"
if str(_SIDECAR) not in sys.path:
    sys.path.insert(0, str(_SIDECAR))

import deletion  # noqa: E402
import inbox  # noqa: E402
import links  # noqa: E402
import runtime_store  # noqa: E402
import scratchpad  # noqa: E402
import state_store  # noqa: E402
import storage  # noqa: E402
import watermark  # noqa: E402


@pytest.fixture(autouse=True)
def _clean(tmp_path, monkeypatch):
    """Isolate every test: temp runtime dir, cleared modules, hooks installed."""
    monkeypatch.setenv("AWL_SIDECAR_RUNTIME", str(tmp_path / "rt"))
    inbox.reset(); links.reset(); watermark.reset()
    scratchpad.reset(); deletion.reset(); state_store.reset()
    state_store.install_hooks()
    yield
    inbox.set_persist_hook(None)
    links.set_persist_hook(None)
    watermark.set_persist_hook(None)
    inbox.reset(); links.reset(); watermark.reset()
    scratchpad.reset(); deletion.reset(); state_store.reset()


def _proj(tmp_path, name="proj") -> str:
    p = tmp_path / name
    p.mkdir(parents=True, exist_ok=True)
    return str(p)


# ---------------------------------------------------------------------------
# Primitives: schema stamp + atomicity
# ---------------------------------------------------------------------------

class TestPrimitives:
    def test_every_state_file_carries_schema_version(self, tmp_path):
        cwd = _proj(tmp_path)
        key = storage.project_key(cwd)
        state_store.save_roster_record(key, {"session_id": "a1", "cwd": cwd})
        state_store.persist_retired_number(key, 3)
        data = json.loads(state_store.agents_path(key).read_text(encoding="utf-8"))
        assert data["schema_version"] == state_store.SCHEMA_VERSION
        state_store.touch_projects_index(key)
        idx = json.loads(storage.projects_index_path().read_text(encoding="utf-8"))
        assert idx["schema_version"] == state_store.SCHEMA_VERSION

    def test_atomic_write_leaves_no_tmp_residue(self, tmp_path):
        cwd = _proj(tmp_path)
        key = storage.project_key(cwd)
        state_store.save_roster_record(key, {"session_id": "a1"})
        state_dir = storage.state_dir(cwd)
        assert not list(state_dir.glob("*.tmp"))

    def test_corrupt_file_degrades_to_empty(self, tmp_path):
        cwd = _proj(tmp_path)
        key = storage.project_key(cwd)
        p = state_store.agents_path(key)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("{not json", encoding="utf-8")
        assert state_store.load_roster(key) == {}


# ---------------------------------------------------------------------------
# Roster + retired numbers (agents.json)
# ---------------------------------------------------------------------------

class TestRoster:
    def test_save_load_remove_round_trip(self, tmp_path):
        cwd = _proj(tmp_path)
        key = storage.project_key(cwd)
        rec = {"session_id": "s1", "tmux_name": "awl-x", "cwd": cwd,
               "claude_session_id": "uuid-1", "transcript_path": "/home/u/t.jsonl"}
        state_store.save_roster_record(key, rec)
        got = state_store.load_roster(key)
        assert got["s1"]["claude_session_id"] == "uuid-1"
        assert got["s1"]["transcript_path"] == "/home/u/t.jsonl"
        assert state_store.remove_roster_record(key, "s1") is True
        assert state_store.load_roster(key) == {}
        assert state_store.remove_roster_record(key, "s1") is False

    def test_retired_numbers_persist_sorted_unique(self, tmp_path):
        cwd = _proj(tmp_path)
        key = storage.project_key(cwd)
        state_store.persist_retired_number(key, 7)
        state_store.persist_retired_number(key, 3)
        state_store.persist_retired_number(key, 7)
        assert state_store.load_retired_numbers(key) == [3, 7]

    def test_runtime_store_routes_by_project_home(self, tmp_path):
        cwd = _proj(tmp_path)
        runtime_store.save_record({"session_id": "s1", "cwd": cwd, "tmux_name": "t1"})
        # Landed in the PROJECT store, not the app-level sessions.json…
        key = storage.project_key(cwd)
        assert "s1" in state_store.load_roster(key)
        assert not (runtime_store.runtime_dir() / "sessions.json").exists()
        # …and the projects index knows the root (cold discovery, §3.5).
        assert key in state_store.known_projects()
        # A cwd-less record falls back to the app-level file.
        runtime_store.save_record({"session_id": "s2", "tmux_name": "t2"})
        assert (runtime_store.runtime_dir() / "sessions.json").exists()
        # all_records aggregates both homes.
        sids = {r["session_id"] for r in runtime_store.all_records()}
        assert sids == {"s1", "s2"}
        # remove_record finds the record wherever it lives.
        runtime_store.remove_record("s1")
        runtime_store.remove_record("s2")
        assert runtime_store.all_records() == []


# ---------------------------------------------------------------------------
# Write-through hooks: inbox / links / bookmarks
# ---------------------------------------------------------------------------

class TestWriteThrough:
    def test_inbox_raise_and_resolve_write_through(self, tmp_path):
        cwd = _proj(tmp_path)
        key = storage.project_key(cwd)
        state_store.register_agent("ag1", cwd)
        it = inbox.raise_item("ag1", "error", {"m": 1}, sticky=True)
        data = json.loads(state_store.inbox_path(key).read_text(encoding="utf-8"))
        assert data["items"]["ag1"][0]["type"] == "error"
        inbox.resolve_item("ag1", it["id"])
        data = json.loads(state_store.inbox_path(key).read_text(encoding="utf-8"))
        assert data["items"]["ag1"][0]["resolved"] is True

    def test_unregistered_agent_writes_nothing(self, tmp_path):
        inbox.raise_item("ghost", "error", {})
        # No project registered -> no file anywhere under the runtime dir.
        assert not list((Path(str(tmp_path)) / "rt").rglob("inbox.json"))

    def test_links_add_remove_and_touched_write_through(self, tmp_path):
        cwd = _proj(tmp_path)
        key = storage.project_key(cwd)
        state_store.register_agent("a", cwd)
        state_store.register_agent("b", cwd)
        lk = links.add_link(a="a", b="b")
        rows = json.loads(state_store.links_path(key).read_text(encoding="utf-8"))["links"]
        assert rows[0]["id"] == lk.id
        lk.messages = 4
        lk.active = False
        links.touched(lk)   # in-place counter mutations persist via touched()
        rows = json.loads(state_store.links_path(key).read_text(encoding="utf-8"))["links"]
        assert rows[0]["messages"] == 4 and rows[0]["active"] is False
        links.remove_link(lk.id)
        rows = json.loads(state_store.links_path(key).read_text(encoding="utf-8"))["links"]
        assert rows == []

    def test_bookmarks_scratch_and_shared_routing(self, tmp_path):
        cwd = _proj(tmp_path)
        key = storage.project_key(cwd)
        state_store.register_agent("ag1", cwd)
        # scratch:{project}:{agent} routes by its embedded project key…
        watermark.delta(f"scratch:{key}:ag1", [(1, "x"), (2, "y")])
        marks = json.loads(state_store.bookmarks_path(key).read_text(encoding="utf-8"))["marks"]
        assert marks[f"scratch:{key}:ag1"] == 2
        # …and shared:{src}:{dst} routes via the src agent's project.
        watermark.set("shared:ag1:ag2", 5)
        marks = json.loads(state_store.bookmarks_path(key).read_text(encoding="utf-8"))["marks"]
        assert marks["shared:ag1:ag2"] == 5
        # drop() removes the row from the file (agent deletion, §11 #11).
        watermark.drop("shared:ag1:ag2")
        marks = json.loads(state_store.bookmarks_path(key).read_text(encoding="utf-8"))["marks"]
        assert "shared:ag1:ag2" not in marks


# ---------------------------------------------------------------------------
# Routing overlay (append-only jsonl)
# ---------------------------------------------------------------------------

class TestRoutingOverlay:
    def test_append_and_load(self, tmp_path):
        cwd = _proj(tmp_path)
        state_store.register_agent("ag1", cwd)
        state_store.append_routing("ag1", "ag1:t:u1", "ag1", ["ag2"])
        state_store.append_routing("ag1", "ag1:s:seq9", "scratch", ["scratch"])
        key = storage.project_key(cwd)
        recs = state_store.load_routing(key)
        assert recs == [
            {"anchor_id": "ag1:t:u1", "source": "ag1", "recipients": ["ag2"]},
            {"anchor_id": "ag1:s:seq9", "source": "scratch", "recipients": ["scratch"]},
        ]

    def test_unroutable_agent_is_skipped(self, tmp_path):
        state_store.append_routing("ghost", "x:t:u", "x", ["y"])  # no crash, no file


# ---------------------------------------------------------------------------
# Scratchpad .md round-trip
# ---------------------------------------------------------------------------

class TestScratchpadRoundTrip:
    def test_mirror_parses_back_including_multiline(self, tmp_path):
        cwd = _proj(tmp_path)
        key = storage.project_key(cwd)
        sp = storage.scratchpad_path(cwd)
        scratchpad.post(key, "ada", "first post", persist_path=str(sp))
        scratchpad.post(key, "bee", "two\nlines", persist_path=str(sp))
        posts = state_store.parse_scratchpad_md(sp.read_text(encoding="utf-8"))
        assert [p["author"] for p in posts] == ["ada", "bee"]
        assert posts[0]["seq"] == 1 and posts[1]["seq"] == 2
        assert posts[1]["text"] == "two\nlines"

    def test_restore_advances_seq(self, tmp_path):
        key = "K"
        scratchpad.restore(key, [{"seq": 1, "author": "a", "text": "x", "ts": "t"},
                                 {"seq": 2, "author": "b", "text": "y", "ts": "t"}])
        p = scratchpad.post(key, "c", "new")
        assert p["seq"] == 3
        assert [q["seq"] for q in scratchpad.all_posts(key)] == [1, 2, 3]


# ---------------------------------------------------------------------------
# load_project — lazy, idempotent, seeds every module
# ---------------------------------------------------------------------------

class TestLoadProject:
    def test_seeds_all_modules_and_is_idempotent(self, tmp_path):
        cwd = _proj(tmp_path)
        key = storage.project_key(cwd)
        # Persist a full store on disk first (as a prior run would have).
        state_store.register_agent("ag1", cwd)
        inbox.raise_item("ag1", "decision", {"q": "?"})
        links.add_link(a="ag1", b="ag1b", link_id="lnk7")
        watermark.set(f"scratch:{key}:ag1", 4)
        state_store.persist_retired_number(key, 9)
        sp = storage.scratchpad_path(cwd)
        scratchpad.post(key, "ada", "hello", persist_path=str(sp))
        # Simulate a fresh process: clear all in-memory state.
        inbox.reset(); links.reset(); watermark.reset()
        scratchpad.reset(); deletion.reset()
        state_store.reset()
        state_store.register_agent("ag1", cwd)  # re-registered by the session layer
        assert state_store.load_project(cwd) is True
        assert inbox.items_for("ag1")[0]["type"] == "decision"
        assert links.get_link("lnk7") is not None
        assert watermark.get(f"scratch:{key}:ag1") == 4
        assert deletion.is_retired(9) is True
        assert scratchpad.all_posts(key)[0]["text"] == "hello"
        # Idempotent: second load is a no-op.
        assert state_store.load_project(cwd) is False

    def test_restored_ids_never_collide(self, tmp_path):
        cwd = _proj(tmp_path)
        state_store.register_agent("ag1", cwd)
        inbox.restore("ag1", [{"id": "ibx41", "agent_id": "ag1", "type": "error",
                               "data": {}, "resolved": False}])
        fresh = inbox.raise_item("ag1", "warning", {})
        assert int(fresh["id"][3:]) > 41
        links.restore([{"id": "lnk12", "a": "x", "b": "y"}])
        lk = links.add_link(a="p", b="q")
        assert int(lk.id[3:]) > 12

    def test_no_cwd_is_a_noop(self):
        assert state_store.load_project(None) is False
