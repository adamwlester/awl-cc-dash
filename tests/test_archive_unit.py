"""Hermetic unit tests for the Agent archive (ARCHITECTURE §7.12, §8.4, §11 #18).

The decided contract this file encodes ("the system is not useful without it"):

  * **Schema = distinct-ID records in a per-project ``state/archive.json``** — a
    sibling of ``agents.json``/``inbox.json``/``links.json``, written through the
    same atomic write-replace ``state_store`` model and stamped with a
    ``schema_version`` (§8.7). One-file-per-instantiation was rejected.
  * **Retire = deep-freeze, archived BY DEFAULT.** Retiring an agent (the soft,
    default ``DELETE /sessions/{id}``) writes its record into the archive — it is
    NOT a discard. Retire is reversible: the transcript is kept and the identity
    number is NOT retired.
  * **Delete stays a TRUE wipe (§7.12), distinct from archive.** A hard Delete
    (``?hard=true``) wipes the agent's footprint and retires the number, and is
    NOT archived. Deleting an *archived* record really removes it.
  * **Records are LIGHT except transcripts** — the transcript is REFERENCED in
    place (path + ``claude_session_id``), NEVER copied (§8.6).
  * The schema **RESERVES lineage fields** (``lineage.{parent, fork, handoff}``,
    nullable + unpopulated), tying to #15 (fork/handoff) and #19 (per-agent git
    identity) — reserved here, populated later.
  * The archive is **per-project** (§8.2) and isolated across projects;
    ``all_archived_records`` aggregates project-first across the 🏠 index.

No WSL, no network, no live agent — pure files on tmp_path; the ``close_session``
endpoint is driven directly via ``asyncio.run`` with a fake driver.
"""

import asyncio
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
import scratchpad  # noqa: E402
import state_store  # noqa: E402
import storage  # noqa: E402
import watermark  # noqa: E402
import main  # noqa: E402
from main import SessionState  # noqa: E402
from fastapi import HTTPException  # noqa: E402


@pytest.fixture(autouse=True)
def _clean(tmp_path, monkeypatch):
    """Isolate every test: temp runtime dir, cleared modules, empty sessions."""
    monkeypatch.setenv("AWL_SIDECAR_RUNTIME", str(tmp_path / "rt"))
    inbox.reset(); links.reset(); watermark.reset()
    scratchpad.reset(); deletion.reset(); state_store.reset()
    main.sessions.clear()
    yield
    inbox.reset(); links.reset(); watermark.reset()
    scratchpad.reset(); deletion.reset(); state_store.reset()
    main.sessions.clear()


def _proj(tmp_path, name="proj") -> str:
    p = tmp_path / name
    p.mkdir(parents=True, exist_ok=True)
    return str(p)


class _FakeArchiveDriver:
    """A driver shaped like the bridge driver's persistence surface: it holds the
    roster ``_record`` (from which the archive lifts the transcript reference) and
    a stoppable async ``close``. No ``_bridge`` attr, so the hard-Delete path's
    transcript-erasure guard is a clean no-op (nothing touches disk)."""

    name = "bridge"

    def __init__(self, record):
        self._record = dict(record)
        self.closed = 0

    async def close(self):
        self.closed += 1


def _seed_session(sid, cwd, identity, record):
    s = SessionState(session_id=sid, agent_type=None, model="claude-x",
                     permission_mode="default", cwd=cwd, system_prompt=None,
                     driver_name="bridge", identity=identity)
    s.driver = _FakeArchiveDriver(record)
    state_store.register_agent(sid, cwd)
    main.sessions[sid] = s
    return s


# ---------------------------------------------------------------------------
# Record shape (pure builder — deletion.build_archive_record)
# ---------------------------------------------------------------------------

class TestArchiveRecordShape:
    def test_distinct_id_lineage_reserved_and_transcript_referenced(self):
        rec = deletion.build_archive_record(
            "s1",
            identity={"role": "Reviewer", "number": 3, "name": "nova",
                      "color": "#008149", "icon": "fox-head"},
            created_at="2026-07-15T10:00:00",
            transcript_path="/home/u/proj/abc.jsonl",
            claude_session_id="uuid-abc",
        )
        # DISTINCT id — never the session id.
        assert rec["archive_id"] != "s1"
        assert rec["archive_id"].startswith("arc")
        assert rec["session_id"] == "s1"
        # Reserved lineage fields — present but null (for #15/#19).
        assert rec["lineage"] == {"parent": None, "fork": None, "handoff": None}
        # Transcript REFERENCED, never copied (§8.6): only the pointer lives here.
        assert rec["transcript"] == {"transcript_path": "/home/u/proj/abc.jsonl",
                                     "claude_session_id": "uuid-abc"}
        assert set(rec["transcript"]) == {"transcript_path", "claude_session_id"}
        # Identity snapshot + convenience name/color/icon.
        assert rec["name"] == "nova"
        assert rec["identity"]["role"] == "Reviewer"
        assert rec["color"] == "#008149" and rec["icon"] == "fox-head"
        # created + retired timestamps.
        assert rec["created_at"] == "2026-07-15T10:00:00"
        assert rec["retired_at"]

    def test_git_author_and_light_metadata(self):
        rec = deletion.build_archive_record(
            "s2", identity={"name": "zed", "number": 5},
            cwd="/home/u/proj", model="claude-x", driver="bridge",
            permission_mode="default",
            git_author=("zed", "zed-5@agents.awl-cc-dash.invalid"),
        )
        assert rec["cwd"] == "/home/u/proj"
        assert rec["model"] == "claude-x"
        assert rec["driver"] == "bridge"
        assert rec["permission_mode"] == "default"
        assert rec["git_author_name"] == "zed"
        assert rec["git_author_email"] == "zed-5@agents.awl-cc-dash.invalid"

    def test_ids_distinct_across_calls(self):
        a = deletion.build_archive_record("s1")
        b = deletion.build_archive_record("s1")
        assert a["archive_id"] != b["archive_id"]

    def test_lineage_override_keeps_only_reserved_keys(self):
        rec = deletion.build_archive_record(
            "s1", lineage={"parent": "arcX", "stray": "nope"})
        assert rec["lineage"] == {"parent": "arcX", "fork": None, "handoff": None}
        assert "stray" not in rec["lineage"]

    def test_injected_archive_id_is_honored(self):
        rec = deletion.build_archive_record("s1", archive_id="arcFIXED")
        assert rec["archive_id"] == "arcFIXED"


# ---------------------------------------------------------------------------
# Persistence (state_store archive.json)
# ---------------------------------------------------------------------------

class TestArchivePersistence:
    def test_save_load_get_round_trip_with_schema_version(self, tmp_path):
        cwd = _proj(tmp_path)
        key = storage.project_key(cwd)
        r1 = deletion.build_archive_record("s1", archive_id="arc1",
                                           transcript_path="/t/1.jsonl")
        r2 = deletion.build_archive_record("s2", archive_id="arc2")
        state_store.save_archive_record(key, r1)
        state_store.save_archive_record(key, r2)
        got = state_store.load_archive(key)
        assert set(got) == {"arc1", "arc2"}
        assert state_store.get_archive_record(key, "arc1")["session_id"] == "s1"
        # schema_version stamp (#42) + no tmp residue (§8.7).
        data = json.loads(state_store.archive_path(key).read_text(encoding="utf-8"))
        assert data["schema_version"] == state_store.SCHEMA_VERSION
        assert not list(storage.state_dir(cwd).glob("*.tmp"))

    def test_true_delete_of_archived_record(self, tmp_path):
        cwd = _proj(tmp_path)
        key = storage.project_key(cwd)
        state_store.save_archive_record(
            key, deletion.build_archive_record("s1", archive_id="arcX"))
        assert state_store.remove_archive_record(key, "arcX") is True
        assert state_store.load_archive(key) == {}
        # A real, irreversible wipe — a second delete finds nothing.
        assert state_store.remove_archive_record(key, "arcX") is False

    def test_cwdless_agent_does_not_archive(self):
        # The archive is per-project (§8.2): no project home -> a silent no-op.
        state_store.save_archive_record(
            None, deletion.build_archive_record("s1", archive_id="arcX"))
        assert state_store.load_archive(None) == {}

    def test_per_project_isolation(self, tmp_path):
        cwdA = _proj(tmp_path, "A")
        cwdB = _proj(tmp_path, "B")
        keyA = storage.project_key(cwdA)
        keyB = storage.project_key(cwdB)
        state_store.save_archive_record(
            keyA, deletion.build_archive_record("a1", archive_id="arcA"))
        state_store.save_archive_record(
            keyB, deletion.build_archive_record("b1", archive_id="arcB"))
        state_store.touch_projects_index(keyA)
        state_store.touch_projects_index(keyB)
        # Each project's file holds only its own record.
        assert set(state_store.load_archive(keyA)) == {"arcA"}
        assert set(state_store.load_archive(keyB)) == {"arcB"}
        # Cross-project aggregation + lookup + delete route to the right home.
        ids = {r["archive_id"] for r in state_store.all_archived_records()}
        assert ids == {"arcA", "arcB"}
        assert state_store.find_archive_record("arcB")[0] == keyB
        assert state_store.delete_archived_anywhere("arcA") is True
        assert set(state_store.load_archive(keyA)) == set()
        assert set(state_store.load_archive(keyB)) == {"arcB"}


# ---------------------------------------------------------------------------
# Retire archives by default (DELETE /sessions/{id}, soft)
# ---------------------------------------------------------------------------

class TestRetireArchivesByDefault:
    def test_soft_retire_writes_archive_record(self, tmp_path):
        cwd = _proj(tmp_path)
        key = storage.project_key(cwd)
        identity = {"role": "Reviewer", "number": 3, "name": "nova",
                    "color": "#008149", "icon": "fox-head"}
        s = _seed_session("s1", cwd, identity,
                          {"transcript_path": "/home/u/proj/abc.jsonl",
                           "claude_session_id": "uuid-abc"})

        out = asyncio.run(main.close_session("s1", hard=False))

        assert out["status"] == "closed"
        aid = out["archived"]
        assert aid and aid.startswith("arc")
        assert "s1" not in main.sessions          # gone from the LIVE roster
        assert s.driver.closed == 1               # the live session was stopped

        arch = state_store.load_archive(key)
        assert list(arch) == [aid]
        rec = arch[aid]
        assert rec["session_id"] == "s1" and rec["archive_id"] != "s1"
        assert rec["name"] == "nova"
        assert rec["identity"]["role"] == "Reviewer"
        # Transcript REFERENCED in place, never copied (§8.6).
        assert rec["transcript"]["transcript_path"] == "/home/u/proj/abc.jsonl"
        assert rec["transcript"]["claude_session_id"] == "uuid-abc"
        # Reserved lineage fields present-but-null.
        assert rec["lineage"] == {"parent": None, "fork": None, "handoff": None}
        # created_at snapshot + the #19 git author/email.
        assert rec["created_at"] == s.created_at
        assert rec["git_author_email"].endswith("@agents.awl-cc-dash.invalid")

    def test_retired_agent_is_discoverable_via_list_endpoint(self, tmp_path):
        cwd = _proj(tmp_path)
        _seed_session("s1", cwd, {"name": "nova", "number": 1},
                      {"transcript_path": "/t/x.jsonl", "claude_session_id": "u1"})
        out = asyncio.run(main.close_session("s1", hard=False))
        listing = asyncio.run(main.list_archive())
        assert listing["count"] == 1
        assert listing["archived"][0]["archive_id"] == out["archived"]
        got = asyncio.run(main.get_archive(out["archived"]))
        assert got["session_id"] == "s1"


# ---------------------------------------------------------------------------
# Delete is a TRUE wipe, distinct from archive (§7.12)
# ---------------------------------------------------------------------------

class TestDeleteIsTrueWipeDistinctFromArchive:
    def test_hard_delete_does_not_archive_and_retires_number(self, tmp_path):
        cwd = _proj(tmp_path)
        key = storage.project_key(cwd)
        identity = {"role": "Agent", "number": 5, "name": "zed",
                    "color": "#006bbb", "icon": "wolf-head"}
        _seed_session("s2", cwd, identity,
                      {"transcript_path": None, "claude_session_id": None})

        out = asyncio.run(main.close_session("s2", hard=True))

        assert out["status"] == "deleted"
        assert "s2" not in main.sessions
        # Delete does NOT create an archive record...
        assert state_store.load_archive(key) == {}
        # ...and it IS a true wipe: the identity number is permanently retired.
        assert deletion.is_retired(5) is True

    def test_delete_archived_record_via_endpoint(self, tmp_path):
        cwd = _proj(tmp_path)
        key = storage.project_key(cwd)
        state_store.save_archive_record(
            key, deletion.build_archive_record("s1", archive_id="arcZ"))
        state_store.touch_projects_index(key)

        out = asyncio.run(main.delete_archive("arcZ"))
        assert out == {"status": "deleted", "archive_id": "arcZ"}
        assert state_store.find_archive_record("arcZ") is None
        # Deleting again -> 404 (really gone).
        with pytest.raises(HTTPException) as exc:
            asyncio.run(main.delete_archive("arcZ"))
        assert exc.value.status_code == 404


# ---------------------------------------------------------------------------
# List / get endpoints
# ---------------------------------------------------------------------------

class TestArchiveEndpoints:
    def test_list_and_get(self, tmp_path):
        cwd = _proj(tmp_path)
        key = storage.project_key(cwd)
        state_store.save_archive_record(
            key, deletion.build_archive_record("s1", archive_id="arc1"))
        state_store.save_archive_record(
            key, deletion.build_archive_record("s2", archive_id="arc2"))
        state_store.touch_projects_index(key)

        listing = asyncio.run(main.list_archive())
        assert listing["count"] == 2
        assert {r["archive_id"] for r in listing["archived"]} == {"arc1", "arc2"}

        assert asyncio.run(main.get_archive("arc1"))["session_id"] == "s1"

    def test_get_unknown_is_404(self):
        with pytest.raises(HTTPException) as exc:
            asyncio.run(main.get_archive("nope"))
        assert exc.value.status_code == 404
