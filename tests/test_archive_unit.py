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
  * **Teardown is GATED on the archive landing** (the retire data-loss fix):
    an archive-write failure — or the cwd-less skip — must NOT take the
    record-removing ``driver.close()``. The degrade is ``stop()`` semantics
    (process ends, the persisted roster record SURVIVES as a resumable Past
    row), the response says why (``archive_error`` / ``archive_skipped:
    "no-project"``), and ``state_store.save_archive_record`` raises
    ``ValueError`` instead of silently no-opping (missing ``archive_id`` or
    no project home) so an unwritten archive can never look written.
  * **The archive record's on-disk presence is the truth**: once
    ``save_archive_record`` lands, the retire IS archived — a failure in the
    best-effort ``touch_projects_index`` afterwards must not misclassify it
    (no ``archive_error``, ``close()`` still taken).
  * **Non-archived responses carry ``record_kept``** — True when the
    overridden ``stop()`` kept the persisted roster row (bridge), False when
    the ``close()`` fallback ran and nothing survives dashboard-side (sdk).
    The archived happy path OMITS the flag (the frontend only consults it
    when ``archived`` is null).
  * ``GET /sessions/past`` never double-lists one ``session_id``: emitted
    archive rows join the ``seen`` set, so duplicate archive records for the
    same session (a partial-failure retire→resume→retire cycle) yield one row.

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
import runtime_store  # noqa: E402
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
    roster ``_record`` (from which the archive lifts the transcript reference),
    and mimics the real close/stop SPLIT — ``close()`` (the retire path) also
    removes the persisted roster record like ``BridgeDriver.close`` does, while
    ``stop()`` ends the process but KEEPS the record. Both count their calls so
    tests can assert which teardown was taken. No ``_bridge`` attr, so the
    hard-Delete path's transcript-erasure guard is a clean no-op (nothing
    touches disk)."""

    name = "bridge"

    def __init__(self, record, session_id=None):
        self._record = dict(record)
        self._session_id = session_id
        self.closed = 0
        self.stopped = 0

    async def close(self):
        self.closed += 1
        if self._session_id:   # mimic BridgeDriver.close → _remove_record
            runtime_store.remove_record(self._session_id)

    async def stop(self):
        self.stopped += 1      # mimic BridgeDriver.stop → record KEPT


def _seed_session(sid, cwd, identity, record):
    s = SessionState(session_id=sid, agent_type=None, model="claude-x",
                     permission_mode="default", cwd=cwd, system_prompt=None,
                     driver_name="bridge", identity=identity)
    s.driver = _FakeArchiveDriver(record, session_id=sid)
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

    def test_cwdless_agent_cannot_archive_and_the_store_says_so(self):
        # The archive is per-project (§8.2): no project home -> an HONEST
        # ValueError, never the old silent no-op (the retire path gates its
        # teardown on this call landing — a swallowed skip looked "written").
        with pytest.raises(ValueError):
            state_store.save_archive_record(
                None, deletion.build_archive_record("s1", archive_id="arcX"))
        assert state_store.load_archive(None) == {}

    def test_missing_archive_id_raises(self, tmp_path):
        # The other silent-no-op guard, now honest: a record with no
        # archive_id has nothing to key it by.
        key = storage.project_key(_proj(tmp_path))
        rec = deletion.build_archive_record("s1", archive_id="arcX")
        rec["archive_id"] = ""
        with pytest.raises(ValueError):
            state_store.save_archive_record(key, rec)
        assert state_store.load_archive(key) == {}

    def test_rearchiving_a_session_replaces_its_stale_row(self, tmp_path):
        # Idempotent per session (the duplicate-archive fix, live-observed
        # 2026-07-17): one session = at most ONE archive row. A second
        # archive write for the same session_id REPLACES the standing row —
        # the new record's data whole, nothing preserved from the stale one.
        cwd = _proj(tmp_path)
        key = storage.project_key(cwd)
        old = deletion.build_archive_record("s1", archive_id="arcOLD",
                                            model="m-old",
                                            claude_session_id="c-old")
        state_store.save_archive_record(key, old)
        new = deletion.build_archive_record("s1", archive_id="arcNEW",
                                            model="m-new",
                                            claude_session_id="c-new")
        state_store.save_archive_record(key, new)
        got = state_store.load_archive(key)
        assert set(got) == {"arcNEW"}                    # exactly one row
        assert got["arcNEW"]["model"] == "m-new"         # the newest data
        assert got["arcNEW"]["transcript"]["claude_session_id"] == "c-new"

    def test_rearchive_replacement_is_scoped_to_the_session(self, tmp_path):
        # Other sessions' rows are untouched by the same-session replace.
        cwd = _proj(tmp_path)
        key = storage.project_key(cwd)
        state_store.save_archive_record(
            key, deletion.build_archive_record("s1", archive_id="arcA"))
        state_store.save_archive_record(
            key, deletion.build_archive_record("s2", archive_id="arcB"))
        state_store.save_archive_record(
            key, deletion.build_archive_record("s1", archive_id="arcC"))
        assert set(state_store.load_archive(key)) == {"arcB", "arcC"}

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
        assert s.driver.stopped == 0              # full close, not the degrade
        # A clean archive carries no failure/skip fields — and no record_kept
        # (the flag belongs to the non-archived paths only).
        assert "archive_error" not in out and "archive_skipped" not in out
        assert "record_kept" not in out

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

    def test_second_retire_replaces_the_standing_row_not_duplicates(self, tmp_path):
        # The live-observed 2026-07-17 cycle: retire → resume FAILS (the
        # un-retire delete is correctly skipped on session.status == "error")
        # → retire again. The second retire must REPLACE the still-standing
        # row, never mint a sibling — one session, one archive row.
        cwd = _proj(tmp_path)
        key = storage.project_key(cwd)
        identity = {"role": "roundtrip", "number": 8, "name": ""}
        _seed_session("s1", cwd, identity,
                      {"transcript_path": None, "claude_session_id": "c1"})
        first = asyncio.run(main.close_session("s1", hard=False))
        assert first["archived"]
        # Failed resume: the agent is briefly live again; the archive row stays.
        _seed_session("s1", cwd, identity,
                      {"transcript_path": None, "claude_session_id": "c1"})
        assert set(state_store.load_archive(key)) == {first["archived"]}
        second = asyncio.run(main.close_session("s1", hard=False))
        got = state_store.load_archive(key)
        assert set(got) == {second["archived"]}          # exactly one row
        assert second["archived"] != first["archived"]   # ... the NEWEST one
        # And /sessions/past lists that session once.
        past = asyncio.run(main.list_past_agents())
        rows = [r for r in past["past"] if r["session_id"] == "s1"]
        assert len(rows) == 1
        assert rows[0]["archive_id"] == second["archived"]


# ---------------------------------------------------------------------------
# Retire teardown is GATED on the archive landing (the data-loss fix): a
# failed/skipped archive keeps the persisted roster record (stop() semantics),
# never the record-removing close().
# ---------------------------------------------------------------------------

class TestRetireGatesTeardownOnArchive:
    def _roster_row(self, cwd):
        rec = {"session_id": "s1", "cwd": cwd, "tmux_name": "awl-x",
               "driver": "bridge"}
        runtime_store.save_record(rec)
        assert any(r["session_id"] == "s1" for r in runtime_store.all_records())
        return rec

    def test_archive_write_failure_keeps_roster_and_takes_stop(
            self, tmp_path, monkeypatch):
        cwd = _proj(tmp_path)
        key = storage.project_key(cwd)
        s = _seed_session("s1", cwd, {"name": "nova", "number": 1},
                          {"transcript_path": "/t/x.jsonl",
                           "claude_session_id": "u1"})
        self._roster_row(cwd)

        def _boom(project_key, record):
            raise RuntimeError("disk full")
        monkeypatch.setattr(state_store, "save_archive_record", _boom)

        out = asyncio.run(main.close_session("s1", hard=False))

        # Honest response: closed, but the freeze did NOT land — and why.
        assert out["status"] == "closed"
        assert out["archived"] is None
        assert "disk full" in out["archive_error"]
        assert "archive_skipped" not in out
        # The record-removing close() was NOT taken; stop() (record kept) was
        # — and the response SAYS so (the honest-toast signal).
        assert out["record_kept"] is True
        assert s.driver.closed == 0
        assert s.driver.stopped == 1
        # The persisted roster record SURVIVES (the resumable Past row)...
        assert any(r["session_id"] == "s1"
                   for r in runtime_store.all_records())
        # ...while the in-memory session is gone and nothing was archived.
        assert "s1" not in main.sessions
        assert state_store.load_archive(key) == {}

    def test_cwdless_retire_skips_archive_but_keeps_record(self):
        s = _seed_session("s1", None, {"name": "solo", "number": 2},
                          {"transcript_path": None, "claude_session_id": None})
        self._roster_row(None)   # cwd-less -> the app-level sessions.json home

        out = asyncio.run(main.close_session("s1", hard=False))

        # By-design unarchivable (per-project archive, §8.2) — an explicit
        # machine-readable reason, never a bare null that reads as failure.
        assert out["status"] == "closed"
        assert out["archived"] is None
        assert out["archive_skipped"] == "no-project"
        assert "archive_error" not in out
        assert out["record_kept"] is True   # stop() branch — roster row kept
        assert s.driver.closed == 0
        assert s.driver.stopped == 1
        assert any(r["session_id"] == "s1"
                   for r in runtime_store.all_records())
        assert "s1" not in main.sessions

    def test_successful_archive_takes_the_record_removing_close(self, tmp_path):
        # The happy path is UNCHANGED by the gate: archive lands -> close()
        # removes the roster row (its contents live on in archive.json).
        cwd = _proj(tmp_path)
        key = storage.project_key(cwd)
        s = _seed_session("s1", cwd, {"name": "nova", "number": 1},
                          {"transcript_path": "/t/x.jsonl",
                           "claude_session_id": "u1"})
        self._roster_row(cwd)

        out = asyncio.run(main.close_session("s1", hard=False))

        assert out["archived"] and out["archived"].startswith("arc")
        assert "record_kept" not in out   # archived path omits the flag
        assert s.driver.closed == 1 and s.driver.stopped == 0
        assert not any(r["session_id"] == "s1"
                       for r in runtime_store.all_records())
        assert list(state_store.load_archive(key)) == [out["archived"]]

    def test_index_touch_failure_after_landed_archive_still_archived(
            self, tmp_path, monkeypatch):
        # The record's on-disk presence is the truth: once save_archive_record
        # lands, a failure in the best-effort touch_projects_index must NOT
        # misclassify the retire — archived id still reported, no
        # archive_error, and the record-removing close() still taken.
        cwd = _proj(tmp_path)
        key = storage.project_key(cwd)
        s = _seed_session("s1", cwd, {"name": "nova", "number": 1},
                          {"transcript_path": "/t/x.jsonl",
                           "claude_session_id": "u1"})
        self._roster_row(cwd)

        def _boom(project_key):
            raise RuntimeError("index write failed")
        monkeypatch.setattr(state_store, "touch_projects_index", _boom)

        out = asyncio.run(main.close_session("s1", hard=False))

        assert out["archived"] and out["archived"].startswith("arc")
        assert "archive_error" not in out
        assert "record_kept" not in out
        # Happy-path teardown: close() (roster row removed), not the degrade.
        assert s.driver.closed == 1 and s.driver.stopped == 0
        assert not any(r["session_id"] == "s1"
                       for r in runtime_store.all_records())
        # The archive record really is on disk in the project's archive.json.
        assert list(state_store.load_archive(key)) == [out["archived"]]

    def test_driver_without_stop_override_falls_back_to_close(
            self, tmp_path, monkeypatch):
        # A driver with NO stop/close split (the sdk shape — its close() never
        # touches persisted records) closes instead of leaking its process;
        # the base-class no-op stop() must NOT count as the record-keeping
        # path (it would leave the engine running forever).
        from drivers import AgentDriver, DriverConfig

        class _SplitlessDriver(AgentDriver):
            name = "sdk"

            def __init__(self):
                super().__init__(DriverConfig(), lambda e: None)
                self._record = None
                self.closed = 0

            async def close(self):
                self.closed += 1

        cwd = _proj(tmp_path)
        s = SessionState(session_id="s1", agent_type=None, model=None,
                         permission_mode="default", cwd=cwd,
                         system_prompt=None, driver_name="sdk")
        s.driver = _SplitlessDriver()
        state_store.register_agent("s1", cwd)
        main.sessions["s1"] = s

        def _boom(project_key, record):
            raise RuntimeError("boom")
        monkeypatch.setattr(state_store, "save_archive_record", _boom)

        out = asyncio.run(main.close_session("s1", hard=False))
        assert out["archived"] is None and "boom" in out["archive_error"]
        assert s.driver.closed == 1   # record-safe close taken, no leak
        # close() fallback = nothing survives dashboard-side, and the response
        # SAYS so — the frontend must not promise "kept on Past" here.
        assert out["record_kept"] is False

    def test_duplicate_archive_rows_for_one_session_list_once(self, tmp_path):
        # The partial-failure tail: two archive records sharing one session_id
        # (retire→resume→retire after an orphaned record) must yield ONE past
        # row — emitted archive sids join the `seen` set.
        cwd = _proj(tmp_path)
        key = storage.project_key(cwd)
        state_store.save_archive_record(
            key, deletion.build_archive_record("s1", archive_id="arcOld"))
        state_store.save_archive_record(
            key, deletion.build_archive_record("s1", archive_id="arcNew"))
        state_store.touch_projects_index(key)

        out = asyncio.run(main.list_past_agents())

        rows = [r for r in out["past"] if r["session_id"] == "s1"]
        assert len(rows) == 1
        assert out["count"] == len(out["past"])


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
