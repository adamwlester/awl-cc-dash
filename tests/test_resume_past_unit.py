"""Hermetic unit tests for Load-past-agents — on-demand resume (§9.9, §11 #17).

The decided contract this file encodes:

  * #8 built cold-restore-on-STARTUP + Fleet-Setup load; #17 adds loading ONE
    specific past agent ON DEMAND. The mechanism is exactly #8's cold path
    (``claude --resume <claude_session_id>`` in the agent's cwd — same
    conversation, same id — live-proven in ``tests/test_cold_restore_live.py``),
    invoked à la carte instead of only at startup.
  * ``GET /sessions/past`` enumerates every resumable past agent: the persisted
    roster (``runtime_store.all_records()``, project-first) NOT currently live,
    plus every archived/retired record (§11 #18). A row is ``resumable`` when it
    has a conversation id AND isn't already live; each carries a ``source``
    (``roster`` | ``archive``).
  * ``POST /sessions/resume`` selects ONE by ``archive_id`` → ``session_id`` →
    ``name`` (that precedence), across BOTH the roster and the archive (a retired
    agent lives only in the archive), and relaunches it. Honest failures: 404
    (no match), 409 (already live), 400 (no selector / no conversation id).
  * Resuming from the archive UN-RETIRES it — the deep-freeze row is removed once
    the agent is live again (§7.12: Retire is reversible).

No WSL, no network, no live agent — pure files on ``tmp_path``. The endpoints are
driven directly via ``asyncio.run``; the live driver relaunch (proven by
``test_cold_restore_live``) is stubbed by monkeypatching
``_resume_agent_from_descriptor``, so the resolution + dispatch + un-retire wiring
is what's pinned here.
"""

import asyncio
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
    _ord = main._identity_ordinal
    yield
    main._identity_ordinal = _ord
    inbox.reset(); links.reset(); watermark.reset()
    scratchpad.reset(); deletion.reset(); state_store.reset()
    main.sessions.clear()


def _proj(tmp_path, name="proj") -> str:
    p = tmp_path / name
    p.mkdir(parents=True, exist_ok=True)
    return str(p)


def _seed_roster(cwd, sid, *, claude_id="c-" + "x", name=None, model="claude-x"):
    """Persist a roster record (dead agent — nothing live) via runtime_store."""
    ident = {"number": 1, "role": "Agent"}
    if name:
        ident["name"] = name
    rec = {
        "session_id": sid,
        "tmux_name": "awl-" + sid,
        "driver": "bridge",
        "model": model,
        "permission_mode": "acceptEdits",
        "cwd": cwd,
        "claude_session_id": claude_id,
        "transcript_path": "/t/%s.jsonl" % sid,
        "identity": ident,
    }
    runtime_store.save_record(rec)
    return rec


def _seed_archive(cwd, sid, *, aid, claude_id, name=None):
    """Write an archived (retired) record via the state store."""
    key = storage.project_key(cwd)
    ident = {"number": 2, "role": "Agent"}
    if name:
        ident["name"] = name
    rec = deletion.build_archive_record(
        sid, archive_id=aid, identity=ident, cwd=cwd, model="claude-x",
        claude_session_id=claude_id, transcript_path="/t/%s.jsonl" % sid)
    state_store.save_archive_record(key, rec)
    state_store.touch_projects_index(key)
    return rec


def _live_session(sid, cwd) -> SessionState:
    return SessionState(session_id=sid, agent_type=None, model="m",
                        permission_mode="acceptEdits", cwd=cwd,
                        system_prompt=None, driver_name="bridge")


class _Resumed:
    """Stand-in for the live SessionState the resume helper returns."""

    def __init__(self, session_id="s1", status="idle"):
        self.session_id = session_id
        self.status = status

    def to_dict(self):
        return {"session_id": self.session_id, "status": self.status, "identity": {}}


# ---------------------------------------------------------------------------
# Normalization — roster / archive record -> resume descriptor
# ---------------------------------------------------------------------------

class TestDescriptorNormalization:
    def test_archive_descriptor_lifts_transcript_pointer(self):
        arc = deletion.build_archive_record(
            "s1", archive_id="arc1", cwd="/p", model="m",
            claude_session_id="cid", transcript_path="/t/x.jsonl",
            identity={"name": "nova", "number": 3})
        d = main._resumable_from_archive(arc)
        # The LIGHT record references the transcript under transcript.*; the
        # descriptor lifts it to top-level so the cold path can resume it.
        assert d["claude_session_id"] == "cid"
        assert d["transcript_path"] == "/t/x.jsonl"
        assert d["source"] == "archive" and d["archive_id"] == "arc1"
        assert d["name"] == "nova" and d["cwd"] == "/p"

    def test_roster_descriptor_carries_launch_config(self):
        rec = {"session_id": "s1", "claude_session_id": "cid", "cwd": "/p",
               "model": "m", "permission_mode": "plan",
               "allowed_tools": ["Read"], "identity": {"name": "rex"}}
        d = main._resumable_from_roster(rec)
        assert d["source"] == "roster" and d["claude_session_id"] == "cid"
        assert d["permission_mode"] == "plan"
        assert d["allowed_tools"] == ["Read"] and d["name"] == "rex"


# ---------------------------------------------------------------------------
# GET /sessions/past — enumeration
# ---------------------------------------------------------------------------

class TestEnumeratePast:
    def test_lists_roster_and_archive_with_source_and_resumable(self, tmp_path):
        cwd = _proj(tmp_path)
        _seed_roster(cwd, "s1", claude_id="c1", name="nova")
        _seed_archive(cwd, "s2", aid="arc1", claude_id="c2", name="zed")
        out = asyncio.run(main.list_past_agents())
        assert out["count"] == 2
        by_id = {r["session_id"]: r for r in out["past"]}
        assert by_id["s1"]["source"] == "roster" and by_id["s1"]["resumable"] is True
        assert by_id["s2"]["source"] == "archive" and by_id["s2"]["archive_id"] == "arc1"
        assert by_id["s2"]["resumable"] is True

    def test_live_agent_excluded(self, tmp_path):
        cwd = _proj(tmp_path)
        _seed_roster(cwd, "s1", claude_id="c1")
        main.sessions["s1"] = _live_session("s1", cwd)  # currently live
        out = asyncio.run(main.list_past_agents())
        assert all(r["session_id"] != "s1" for r in out["past"])

    def test_record_without_conversation_id_is_not_resumable(self, tmp_path):
        cwd = _proj(tmp_path)
        _seed_roster(cwd, "s3", claude_id=None)
        out = asyncio.run(main.list_past_agents())
        row = next(r for r in out["past"] if r["session_id"] == "s3")
        assert row["resumable"] is False


# ---------------------------------------------------------------------------
# POST /sessions/resume — resolution + dispatch + un-retire
# ---------------------------------------------------------------------------

class TestResumeDispatch:
    def _patch_resume(self, monkeypatch, seen):
        async def _stub(d):
            seen["d"] = d
            return _Resumed(session_id=d.get("session_id") or "s1")
        monkeypatch.setattr(main, "_resume_agent_from_descriptor", _stub)

    def test_resume_by_archive_id_dispatches_and_unretires(self, tmp_path, monkeypatch):
        cwd = _proj(tmp_path)
        _seed_archive(cwd, "s9", aid="arcZ", claude_id="c9", name="ivy")
        seen = {}
        self._patch_resume(monkeypatch, seen)
        out = asyncio.run(main.resume_past_session(main.ResumeRequest(archive_id="arcZ")))
        assert seen["d"]["source"] == "archive" and seen["d"]["claude_session_id"] == "c9"
        assert out["resumed_from"] == "archive" and out["archive_id"] == "arcZ"
        assert out["claude_session_id"] == "c9"
        # Un-retire: the deep-freeze row is gone once the agent is live again.
        assert state_store.find_archive_record("arcZ") is None

    def test_resume_by_session_id_from_roster(self, tmp_path, monkeypatch):
        cwd = _proj(tmp_path)
        _seed_roster(cwd, "s5", claude_id="c5", name="rex")
        seen = {}
        self._patch_resume(monkeypatch, seen)
        out = asyncio.run(main.resume_past_session(main.ResumeRequest(session_id="s5")))
        assert seen["d"]["source"] == "roster" and seen["d"]["claude_session_id"] == "c5"
        assert out["resumed_from"] == "roster" and out["archive_id"] is None

    def test_resume_by_name_reaches_archive_case_insensitive(self, tmp_path, monkeypatch):
        cwd = _proj(tmp_path)
        _seed_archive(cwd, "s7", aid="arcN", claude_id="c7", name="Vera")
        seen = {}
        self._patch_resume(monkeypatch, seen)
        asyncio.run(main.resume_past_session(main.ResumeRequest(name="vera")))
        assert seen["d"]["source"] == "archive" and seen["d"]["session_id"] == "s7"

    def test_failed_resume_keeps_archive_row(self, tmp_path, monkeypatch):
        cwd = _proj(tmp_path)
        _seed_archive(cwd, "s8", aid="arcE", claude_id="c8", name="err")

        async def _stub(d):
            return _Resumed(session_id="s8", status="error")
        monkeypatch.setattr(main, "_resume_agent_from_descriptor", _stub)
        asyncio.run(main.resume_past_session(main.ResumeRequest(archive_id="arcE")))
        # A failed relaunch must NOT drop the archive record (nothing lost).
        assert state_store.find_archive_record("arcE") is not None


class TestResumeErrors:
    def test_no_selector_is_400(self):
        with pytest.raises(HTTPException) as ei:
            asyncio.run(main.resume_past_session(main.ResumeRequest()))
        assert ei.value.status_code == 400

    def test_unknown_target_is_404(self, tmp_path):
        with pytest.raises(HTTPException) as ei:
            asyncio.run(main.resume_past_session(main.ResumeRequest(archive_id="ghost")))
        assert ei.value.status_code == 404

    def test_already_live_is_409(self, tmp_path):
        cwd = _proj(tmp_path)
        _seed_roster(cwd, "s1", claude_id="c1")
        main.sessions["s1"] = _live_session("s1", cwd)
        with pytest.raises(HTTPException) as ei:
            asyncio.run(main.resume_past_session(main.ResumeRequest(session_id="s1")))
        assert ei.value.status_code == 409

    def test_found_but_no_conversation_id_is_400(self, tmp_path):
        cwd = _proj(tmp_path)
        _seed_roster(cwd, "s2", claude_id=None)
        with pytest.raises(HTTPException) as ei:
            asyncio.run(main.resume_past_session(main.ResumeRequest(session_id="s2")))
        assert ei.value.status_code == 400
