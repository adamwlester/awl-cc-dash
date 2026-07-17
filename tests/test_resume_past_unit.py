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


# ---------------------------------------------------------------------------
# Died-at (§11 #17 / #50 residual) — the roster record's `stopped_at` stamp
# surfaces as the past row's `died_at` (the mockup's "died …" stamp); legacy
# records without it fall back to nothing (the UI renders created_at).
# ---------------------------------------------------------------------------

class TestDiedAtStamp:
    def test_past_row_surfaces_stopped_at_as_died_at(self, tmp_path):
        cwd = _proj(tmp_path)
        rec = _seed_roster(cwd, "s1", claude_id="c1", name="nova")
        rec["stopped_at"] = "2026-07-14T22:10:00"
        runtime_store.save_record(rec)
        out = asyncio.run(main.list_past_agents())
        row = next(r for r in out["past"] if r["session_id"] == "s1")
        assert row["died_at"] == "2026-07-14T22:10:00"

    def test_legacy_record_has_null_died_at(self, tmp_path):
        cwd = _proj(tmp_path)
        _seed_roster(cwd, "s2", claude_id="c2")
        out = asyncio.run(main.list_past_agents())
        row = next(r for r in out["past"] if r["session_id"] == "s2")
        assert row["died_at"] is None

    def test_driver_stop_stamps_stopped_at(self, monkeypatch):
        # BridgeDriver.stop() (the §3.4 "Close & stop agents" path) stamps the
        # KEPT roster record with the moment the process ended.
        from drivers.bridge import BridgeDriver
        from drivers.base import DriverConfig
        import drivers.bridge as db
        saved = []
        monkeypatch.setattr(db, "_save_record", lambda rec: saved.append(dict(rec)))
        d = BridgeDriver(DriverConfig(), lambda e: None,
                         session_id="s-stop",
                         persisted_record={"session_id": "s-stop"})

        class _Closable:
            def close(self, name):
                return None
        d._bridge = _Closable()
        asyncio.run(d.stop())
        assert saved and saved[-1]["stopped_at"]
        assert saved[-1]["session_id"] == "s-stop"


# ---------------------------------------------------------------------------
# Timeline persistence across retire→resume (§7.19 / #50 residual) — the
# per-agent turns.jsonl lives in the launch-config dir KEYED BY TMUX NAME, so
# the resume must reuse the persisted tmux_name (fresh names silently orphan
# the Timeline). Warm-vs-cold mirrors reconnect: alive tmux → warm rebind,
# dead → a full cold create on the SAME name.
# ---------------------------------------------------------------------------

class _CapturingResumeDriver:
    instances: list = []

    def __init__(self, config, on_event, **kwargs):
        self.config = config
        self.kwargs = kwargs
        type(self).instances.append(self)

    async def start(self):
        return None

    async def events(self):
        return
        yield  # pragma: no cover — empty async generator


class TestResumeReattachesTimelineStore:
    @pytest.fixture(autouse=True)
    def _drv(self, monkeypatch):
        import drivers.bridge as db
        _CapturingResumeDriver.instances = []
        monkeypatch.setattr(db, "BridgeDriver", _CapturingResumeDriver)
        yield
        _CapturingResumeDriver.instances = []

    def _patch_tmux(self, monkeypatch, alive_names, calls=None):
        import bridge as bridge_pkg

        class _FakeTmux:
            def list(self):
                if calls is not None:
                    calls.append("list")
                return [{"name": n} for n in alive_names]
        monkeypatch.setattr(bridge_pkg, "TmuxBridge", _FakeTmux)

    def test_descriptor_carries_tmux_name(self, tmp_path):
        cwd = _proj(tmp_path)
        rec = _seed_roster(cwd, "s5", claude_id="c5")
        d = main._resumable_from_roster(rec)
        assert d["tmux_name"] == "awl-s5"

    def test_archive_descriptor_lifts_tmux_name(self):
        arc = deletion.build_archive_record(
            "s6", archive_id="arc6", cwd="/p", claude_session_id="c6",
            tmux_name="awl-s6")
        assert arc["tmux_name"] == "awl-s6"
        assert main._resumable_from_archive(arc)["tmux_name"] == "awl-s6"

    def test_dead_tmux_cold_restores_on_same_name(self, tmp_path, monkeypatch):
        self._patch_tmux(monkeypatch, alive_names=[])
        cwd = _proj(tmp_path)
        d = {"session_id": "s5", "cwd": cwd, "claude_session_id": "c5",
             "tmux_name": "awl-s5"}
        asyncio.run(main._resume_agent_from_descriptor(d))
        kw = _CapturingResumeDriver.instances[-1].kwargs
        assert kw["resume_name"] == "awl-s5"     # SAME launch-config home
        assert kw["cold_restore"] is True

    def test_alive_tmux_warm_rebinds(self, tmp_path, monkeypatch):
        self._patch_tmux(monkeypatch, alive_names=["awl-s5"])
        cwd = _proj(tmp_path)
        d = {"session_id": "s5", "cwd": cwd, "claude_session_id": "c5",
             "tmux_name": "awl-s5"}
        asyncio.run(main._resume_agent_from_descriptor(d))
        kw = _CapturingResumeDriver.instances[-1].kwargs
        assert kw["resume_name"] == "awl-s5"
        assert kw["cold_restore"] is False       # warm: never a duplicate spawn

    def test_no_tmux_name_falls_back_to_fresh_name(self, tmp_path, monkeypatch):
        # Legacy/pre-#18 rows: no persisted name → the old fresh-name cold
        # path, and the liveness probe is never taken.
        calls = []
        self._patch_tmux(monkeypatch, alive_names=["anything"], calls=calls)
        cwd = _proj(tmp_path)
        d = {"session_id": "s7", "cwd": cwd, "claude_session_id": "c7"}
        asyncio.run(main._resume_agent_from_descriptor(d))
        kw = _CapturingResumeDriver.instances[-1].kwargs
        assert kw["resume_name"] is None
        assert kw["cold_restore"] is True
        assert calls == []


# ---------------------------------------------------------------------------
# Cold restore of a ZERO-TURN conversation (§9.9 edge, live-proven 2026-07-17).
# Claude Code writes `<claude_session_id>.jsonl` only on the FIRST turn, so an
# agent retired without ever being prompted has NO transcript — and
# `claude --resume <id>` then prints "No conversation found with session ID …"
# and exits at launch: the fresh tmux session dies with it, the startup-gate
# poll hits the dead pane ("can't find pane: awl-…"), and the resume lands in
# `error`. The driver's decision point: a cold restore first probes for the
# transcript; present → `resume_session_id` (`claude --resume <id>`, the
# proven path); provably absent → a FRESH launch pinned to the SAME id
# (`session_id=<id>`, exactly the original launch — the empty conversation
# continuing); unknown (probe failed) → keep the resume path (fail-open, so a
# WSL hiccup can never silently discard a real conversation).
# ---------------------------------------------------------------------------


class _ColdCreateBridge:
    """Fake bridge for `_create_session`: answers the transcript probe and
    captures the `create()` kwargs the decision produced."""

    def __init__(self, probe="no"):
        self.probe = probe        # "yes" | "no" | raise
        self.created = []

    def _resolve_cwd(self, cwd):
        return cwd

    def _run(self, cmd, **kw):
        if self.probe == "raise":
            raise RuntimeError("wsl unreachable")
        return self.probe

    def create(self, name, **kwargs):
        self.created.append((name, kwargs))
        return {"session_id": kwargs.get("resume_session_id")
                or kwargs.get("session_id"), "name": name}

    def session_id_for(self, name):
        return None


class TestColdRestoreZeroTurnFallsBackToFreshPinnedLaunch:
    def _driver(self, bridge, *, transcript_path="/t/c-x.jsonl"):
        from drivers.base import DriverConfig
        from drivers.bridge import BridgeDriver
        d = BridgeDriver(
            DriverConfig(), lambda e: None,
            resume_name="awl-x", session_id="s-x",
            claude_session_id="c-x", cold_restore=True,
            transcript_path=transcript_path,
            persisted_record={"session_id": "s-x"})
        d._bridge = bridge
        return d

    def test_missing_transcript_launches_fresh_on_the_same_id(self):
        # The tonight-repro shape: dead tmux + no `<id>.jsonl` ever written.
        b = _ColdCreateBridge(probe="no")
        d = self._driver(b)
        d._create_session()
        name, kw = b.created[-1]
        assert name == "awl-x"                       # same launch-config home
        assert kw.get("session_id") == "c-x"         # fresh launch, SAME id
        assert "resume_session_id" not in kw         # never a doomed --resume

    def test_present_transcript_keeps_the_proven_resume_path(self):
        b = _ColdCreateBridge(probe="yes")
        d = self._driver(b)
        d._create_session()
        _, kw = b.created[-1]
        assert kw.get("resume_session_id") == "c-x"
        assert "session_id" not in kw

    def test_unreadable_probe_fails_open_to_resume(self):
        # A transient WSL failure must never discard a real conversation.
        b = _ColdCreateBridge(probe="raise")
        d = self._driver(b)
        d._create_session()
        _, kw = b.created[-1]
        assert kw.get("resume_session_id") == "c-x"

    def test_no_transcript_path_and_no_project_dir_means_fresh_launch(self,
                                                                      monkeypatch):
        # Descriptor without a verified path (the archived zero-turn agent
        # carries transcript_path=None): the probe resolves the project dir —
        # none at all → nothing was ever written → fresh pinned launch.
        import bridge.transcript as bt
        monkeypatch.setattr(bt, "_resolve_project_dir", lambda b, cwd: None)
        b = _ColdCreateBridge(probe="yes")   # _run must not even be consulted
        from drivers.base import DriverConfig
        from drivers.bridge import BridgeDriver
        d = BridgeDriver(
            DriverConfig(cwd="/p"), lambda e: None,
            resume_name="awl-y", session_id="s-y",
            claude_session_id="c-y", cold_restore=True,
            transcript_path=None,
            persisted_record={"session_id": "s-y"})
        d._bridge = b
        d._create_session()
        _, kw = b.created[-1]
        assert kw.get("session_id") == "c-y"
        assert "resume_session_id" not in kw


# ---------------------------------------------------------------------------
# Integrator fixes on the §7.19/§11 #17 batch — the Timeline store must
# actually SURVIVE stop/retire (keeping the tmux name is useless if close()
# rm -rf's the launch-config dir), a restored agent must shed a stale death
# stamp, and fork lineage + the arm_bypass launch fact must survive the
# resume→retire round-trip.
# ---------------------------------------------------------------------------


class _CloseCaptureBridge:
    """Records bridge.close calls (name, purge_config) without any tmux."""

    def __init__(self):
        self.closed = []

    def close(self, name, purge_config=False):
        self.closed.append((name, purge_config))


class _WarmStubBridge:
    """Minimal bridge stub for the warm-resume start() path."""

    def register_session_id(self, name, sid):
        pass

    def resume(self, name, cwd=None, model=None, resume_session_id=None):
        pass

    def wait_idle(self, name, timeout, poll):
        pass


class TestTimelineStoreSurvivesStopAndRetire:
    def _driver(self, monkeypatch):
        from drivers.base import DriverConfig
        from drivers.bridge import BridgeDriver
        import drivers.bridge as db
        monkeypatch.setattr(db, "_save_record", lambda rec: None)
        monkeypatch.setattr(db, "_remove_record", lambda sid: None)
        d = BridgeDriver(DriverConfig(), lambda e: None, session_id="s-keep",
                         persisted_record={"session_id": "s-keep"})
        b = _CloseCaptureBridge()
        d._bridge = b
        return d, b

    def test_stop_keeps_the_launch_config_dir(self, monkeypatch):
        # "Close & stop agents": the roster record survives for cold restore —
        # the same-name relaunch must find turns.jsonl still there (§7.19).
        d, b = self._driver(monkeypatch)
        asyncio.run(d.stop())
        assert b.closed == [(d.tmux_name, False)]

    def test_retire_close_keeps_the_launch_config_dir(self, monkeypatch):
        # Retire archives a resumable row carrying tmux_name — purging the
        # dir here would hand every resume an EMPTY Timeline.
        d, b = self._driver(monkeypatch)
        asyncio.run(d.close())
        assert b.closed == [(d.tmux_name, False)]

    def test_hard_delete_close_purges(self, monkeypatch):
        # §7.12 TRUE wipe: the opt-in form destroys the standing stores too.
        d, b = self._driver(monkeypatch)
        asyncio.run(d.close(purge_config=True))
        assert b.closed == [(d.tmux_name, True)]


class TestRestoreClearsStaleDeathStamp:
    def test_start_pops_stale_stopped_at(self, monkeypatch):
        # stop() stamped T1 → project reopen restores the agent ALIVE: the
        # re-persisted record must NOT keep the old stamp (a later unwitnessed
        # death would render a provably-false "died <T1>" on the Past tab).
        from drivers.base import DriverConfig
        from drivers.bridge import BridgeDriver
        import drivers.bridge as db
        saved = []
        monkeypatch.setattr(db, "_save_record",
                            lambda rec: saved.append(dict(rec)))
        d = BridgeDriver(DriverConfig(), lambda e: None,
                         resume_name="awl-back", session_id="s-back",
                         claude_session_id="c-back",
                         persisted_record={"session_id": "s-back",
                                           "stopped_at": "2026-07-14T22:10:00"})
        d._bridge = _WarmStubBridge()
        asyncio.run(d.start())
        assert saved
        assert "stopped_at" not in saved[-1]


class TestResumeCarriesLineage:
    @pytest.fixture(autouse=True)
    def _drv(self, monkeypatch):
        import drivers.bridge as db
        _CapturingResumeDriver.instances = []
        monkeypatch.setattr(db, "BridgeDriver", _CapturingResumeDriver)
        yield
        _CapturingResumeDriver.instances = []

    LINEAGE = {"parent": "src1",
               "fork": {"source_session_id": "src1",
                        "source_claude_session_id": "c-src",
                        "rewound_to": None},
               "handoff": None}

    def test_roster_descriptor_carries_lineage(self, tmp_path):
        cwd = _proj(tmp_path)
        rec = _seed_roster(cwd, "s8", claude_id="c8")
        rec["lineage"] = dict(self.LINEAGE)
        runtime_store.save_record(rec)
        d = main._resumable_from_roster(rec)
        assert d["lineage"] == self.LINEAGE

    def test_archive_descriptor_carries_lineage_and_arm_bypass(self):
        arc = deletion.build_archive_record(
            "s9", archive_id="arc9", cwd="/p", claude_session_id="c9",
            lineage=dict(self.LINEAGE), arm_bypass=True)
        d = main._resumable_from_archive(arc)
        assert d["lineage"]["fork"]["source_claude_session_id"] == "c-src"
        assert d["arm_bypass"] is True

    def test_archive_row_defaults_arm_bypass_false(self):
        # Pre-field archive rows resume un-armed — honest: the cold relaunch
        # passes no arm flag, so the derived ring and reality agree.
        arc = deletion.build_archive_record(
            "s10", archive_id="arc10", cwd="/p", claude_session_id="c10")
        assert main._resumable_from_archive(arc)["arm_bypass"] is False

    def test_resume_seeds_the_driver_record_with_lineage(self, tmp_path,
                                                         monkeypatch):
        # One resume→retire cycle must re-archive the SAME lineage — start()
        # re-persists on the record base, so the base must carry it.
        import bridge as bridge_pkg

        class _NoTmux:
            def list(self):
                return []
        monkeypatch.setattr(bridge_pkg, "TmuxBridge", _NoTmux)
        cwd = _proj(tmp_path)
        d = {"session_id": "s8", "cwd": cwd, "claude_session_id": "c8",
             "tmux_name": "awl-s8", "lineage": dict(self.LINEAGE)}
        asyncio.run(main._resume_agent_from_descriptor(d))
        kw = _CapturingResumeDriver.instances[-1].kwargs
        assert kw["persisted_record"]["lineage"] == self.LINEAGE
        assert kw["persisted_record"]["session_id"] == "s8"


class TestArchiveTrueDeletePurgesLaunchConfig:
    def test_delete_archive_purges_the_named_dir(self, tmp_path, monkeypatch):
        # DELETE /archive/{id} is the TRUE-delete: nothing can resume the row
        # afterwards, so its tmux-name-keyed Timeline store goes with it.
        import bridge as bridge_pkg
        purged = []

        class _PurgeTmux:
            def purge_launch_config(self, name):
                purged.append(name)
        monkeypatch.setattr(bridge_pkg, "TmuxBridge", _PurgeTmux)
        cwd = _proj(tmp_path)
        key = storage.project_key(cwd)
        rec = deletion.build_archive_record(
            "s11", archive_id="arc11", cwd=cwd, claude_session_id="c11",
            tmux_name="awl-s11")
        state_store.save_archive_record(key, rec)
        state_store.touch_projects_index(key)
        out = asyncio.run(main.delete_archive("arc11"))
        assert out["status"] == "deleted"
        assert purged == ["awl-s11"]
        assert state_store.find_archive_record("arc11") is None

    def test_row_without_tmux_name_deletes_without_purge(self, tmp_path,
                                                         monkeypatch):
        import bridge as bridge_pkg

        class _Boom:
            def purge_launch_config(self, name):  # pragma: no cover - guard
                raise AssertionError("must not purge without a tmux_name")
        monkeypatch.setattr(bridge_pkg, "TmuxBridge", _Boom)
        cwd = _proj(tmp_path)
        _seed_archive(cwd, "s12", aid="arc12", claude_id="c12")
        out = asyncio.run(main.delete_archive("arc12"))
        assert out["status"] == "deleted"
