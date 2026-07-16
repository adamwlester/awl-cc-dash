"""Hermetic unit tests: Projects system surface (§11 #26), System-fault cards
(#27), and the plans action loop (#22).

The decided contracts encoded here:

  * **Projects (§3, §9.1, §9.8):** the picker feed lists known canonical roots;
    exactly ONE project opens at a time (a second open is a 409 — close-then-
    open IS the switch); **Close** detaches (agents keep running, drivers
    untouched); **Close & stop agents** uses the driver's record-KEEPING
    ``stop()`` (never the record-removing ``close()``) so reopening can
    cold-restore the team (§9.9).
  * **System cards (§7.2):** account/fleet-level error subtypes (rate limit,
    usage cap, auth expiry) raise ONE coalesced System-sourced card on top of
    the per-agent sticky card; agent-local errors never do; probe cards
    auto-resolve on recovery. The classifier matches the subscription-cap and
    auth-expiry wording.
  * **Plan verdicts (§7.16, §9.7):** approve resumes the paused agent via the
    proven ``keys()`` Enter (never a hook ``updatedInput``) and resolves the
    plan card; revise sends Escape (keep planning — the ⚠-assumed leg, e2e-
    verified) and queues the feedback at the head of the prompt queue.

No WSL, no network; endpoint functions called directly via asyncio.run.
"""

import asyncio
import sys
from pathlib import Path

import pytest
from fastapi import HTTPException

_SIDECAR = Path(__file__).resolve().parent.parent / "sidecar"
if str(_SIDECAR) not in sys.path:
    sys.path.insert(0, str(_SIDECAR))

import inbox  # noqa: E402
import main  # noqa: E402
import state_store  # noqa: E402
import storage  # noqa: E402
from main import SessionState  # noqa: E402


class _FakeStoppableDriver:
    """Driver double capturing the §3.4 close semantics (stop vs close)."""
    name = "bridge"

    def __init__(self):
        self.stopped = False
        self.closed = False

    async def stop(self):
        self.stopped = True     # ends tmux, KEEPS the roster record

    async def close(self):
        self.closed = True      # retire path - record removed


def _mk_session(sid, cwd, driver=None):
    s = SessionState(session_id=sid, agent_type=None, model=None,
                     permission_mode="default", cwd=cwd, system_prompt=None,
                     driver_name="bridge")
    s.driver = driver
    main.sessions[sid] = s
    return s


@pytest.fixture(autouse=True)
def _iso(tmp_path, monkeypatch):
    import eventbus
    monkeypatch.setenv("AWL_SIDECAR_RUNTIME", str(tmp_path / "rt"))
    inbox.reset()
    eventbus.reset()
    state_store.reset()
    main.sessions.clear()
    main._open_project = None
    yield
    inbox.reset()
    eventbus.reset()
    state_store.reset()
    main.sessions.clear()
    main._open_project = None


# ---------------------------------------------------------------------------
# Projects surface — system side (#26)
# ---------------------------------------------------------------------------

class TestProjectsSurface:
    def test_register_lists_and_canonicalizes(self, tmp_path):
        proj = tmp_path / "projA"
        proj.mkdir()
        entry = asyncio.run(main.register_project(main.ProjectPathRequest(path=str(proj))))
        assert entry["path"] == storage.project_key(str(proj))
        listing = asyncio.run(main.list_projects())
        assert listing["open"] is None
        assert [p["path"] for p in listing["projects"]] == [entry["path"]]

    def test_register_refuses_non_dir(self, tmp_path):
        with pytest.raises(HTTPException) as ei:
            asyncio.run(main.register_project(
                main.ProjectPathRequest(path=str(tmp_path / "ghost"))))
        assert ei.value.status_code == 400

    def test_open_is_exclusive_and_close_switches(self, tmp_path):
        a = tmp_path / "a"; a.mkdir()
        b = tmp_path / "b"; b.mkdir()
        out = asyncio.run(main.open_project(main.ProjectPathRequest(path=str(a))))
        assert out["status"] == "open"
        assert main._open_project == storage.project_key(str(a))
        # One project at a time: a second open is a 409.
        with pytest.raises(HTTPException) as ei:
            asyncio.run(main.open_project(main.ProjectPathRequest(path=str(b))))
        assert ei.value.status_code == 409
        # Re-opening the SAME project is idempotent, not an error.
        again = asyncio.run(main.open_project(main.ProjectPathRequest(path=str(a))))
        assert again["status"] == "open"
        asyncio.run(main.close_project(main.ProjectCloseRequest(stop_agents=False)))
        assert main._open_project is None
        out = asyncio.run(main.open_project(main.ProjectPathRequest(path=str(b))))
        assert out["status"] == "open"

    def test_close_detaches_but_does_not_stop(self, tmp_path):
        a = tmp_path / "a"; a.mkdir()
        other = tmp_path / "other"; other.mkdir()
        asyncio.run(main.open_project(main.ProjectPathRequest(path=str(a))))
        drv = _FakeStoppableDriver()
        _mk_session("s-a", str(a), drv)
        _mk_session("s-other", str(other), _FakeStoppableDriver())
        out = asyncio.run(main.close_project(main.ProjectCloseRequest(stop_agents=False)))
        # The project's session detached; agents keep running (no stop/close);
        # sessions of OTHER projects are untouched.
        assert out["detached_sessions"] == ["s-a"]
        assert "s-a" not in main.sessions and "s-other" in main.sessions
        assert drv.stopped is False and drv.closed is False

    def test_close_and_stop_uses_record_keeping_stop(self, tmp_path):
        a = tmp_path / "a"; a.mkdir()
        asyncio.run(main.open_project(main.ProjectPathRequest(path=str(a))))
        drv = _FakeStoppableDriver()
        _mk_session("s-a", str(a), drv)
        out = asyncio.run(main.close_project(main.ProjectCloseRequest(stop_agents=True)))
        assert out["stopped_agents"] is True
        # stop() (record-keeping), NEVER close() (record-removing): reopening
        # the project must be able to cold-restore the team (§9.9).
        assert drv.stopped is True and drv.closed is False

    def test_close_without_open_is_409(self):
        with pytest.raises(HTTPException) as ei:
            asyncio.run(main.close_project(main.ProjectCloseRequest()))
        assert ei.value.status_code == 409


# ---------------------------------------------------------------------------
# System-fault cards (#27)
# ---------------------------------------------------------------------------

class TestSystemCards:
    def test_classifier_matches_usage_cap_and_auth(self):
        assert inbox.classify_error("You have hit your weekly usage limit")["subtype"] == "usage_cap"
        assert inbox.classify_error("Fast mode requires usage credits")["subtype"] == "usage_cap"
        assert inbox.classify_error("OAuth token has expired. Please run /login")["subtype"] == "auth"

    def test_fleet_subtype_raises_one_coalesced_system_card(self):
        s = _mk_session("agx", None)
        s.handle_event({"type": "error", "error": "quota exceeded - rate limit"})
        s.handle_event({"type": "error", "error": "429 rate limit again"})
        # Per-agent sticky card AND exactly ONE coalesced System card.
        agent_cards = [i for i in inbox.items_for("agx") if i["type"] == "error"]
        system_cards = inbox.items_for(main.SYSTEM_AGENT)
        assert len(agent_cards) == 1          # dedup per subtype per agent
        assert len(system_cards) == 1         # ONE fleet-wide card
        assert system_cards[0]["data"]["subtype"] == "rate_limit"
        assert system_cards[0]["data"]["seen_on"] == "agx"

    def test_agent_local_error_raises_no_system_card(self):
        s = _mk_session("agy", None)
        s.handle_event({"type": "error", "error": "tool execution failed: boom"})
        assert inbox.items_for(main.SYSTEM_AGENT) == []

    def test_probe_card_resolves_on_recovery(self):
        main._raise_system_card("infra", "tmux/WSL2 unreachable: boom")
        assert len(inbox.items_for(main.SYSTEM_AGENT)) == 1
        main._resolve_system_card("infra")
        assert inbox.items_for(main.SYSTEM_AGENT) == []

    def test_system_event_published_once_per_card(self):
        import eventbus
        main._raise_system_card("usage_cap", "weekly usage limit")
        main._raise_system_card("usage_cap", "weekly usage limit again")
        sys_events = [e for e in eventbus.GLOBAL_RING
                      if e.get("source") == main.SYSTEM_AGENT]
        assert len(sys_events) == 1
        assert sys_events[0]["agent_id"] == main.SYSTEM_AGENT


# ---------------------------------------------------------------------------
# Plans action loop (#22)
# ---------------------------------------------------------------------------

class _FakePlanBridge:
    def __init__(self):
        self.keys_sent = []

    def keys(self, name, *keys):
        self.keys_sent.append((name, keys))


class _FakePlanDriver:
    name = "bridge"

    def __init__(self):
        self._bridge = _FakePlanBridge()
        self.tmux_name = "awl-fake"


class TestPlanVerdict:
    def test_approve_sends_enter_and_resolves_card(self):
        drv = _FakePlanDriver()
        _mk_session("agp", None, drv)
        inbox.raise_item("agp", "plan", {"plan": "do X"})
        out = asyncio.run(main.plan_verdict("agp", main.PlanVerdictRequest(verdict="approve")))
        assert out["verdict"] == "approve"
        # The proven resume: a keys() Enter on the pane (never a hook updatedInput).
        assert drv._bridge.keys_sent == [("awl-fake", ("Enter",))]
        opens = [i for i in inbox.items_for("agp") if i["type"] == "plan"]
        assert opens == []

    def test_revise_sends_escape_and_queues_feedback(self):
        drv = _FakePlanDriver()
        s = _mk_session("agq", None, drv)
        s.status = "running"   # busy -> the feedback parks at the queue head
        out = asyncio.run(main.plan_verdict("agq", main.PlanVerdictRequest(
            verdict="revise", text="tighten step 2")))
        assert out["verdict"] == "revise"
        assert drv._bridge.keys_sent == [("awl-fake", ("Escape",))]
        assert s.prompt_queue[0]["prompt"] == "tighten step 2"
        assert s.prompt_queue[0]["disposition"] == "next"

    def test_unknown_session_is_404(self):
        with pytest.raises(HTTPException) as ei:
            asyncio.run(main.plan_verdict("ghost", main.PlanVerdictRequest(verdict="approve")))
        assert ei.value.status_code == 404


# ---------------------------------------------------------------------------
# Projects-index registration (§3.5 / the §7.19 fork-worktree fix): an index
# row auto-created by record routing (e.g. a fork's git-worktree cwd) is
# bookkeeping — enumerable for the roster/archive sweeps but NOT a known
# project in the picker until the operator registers/opens it. Rows written
# before the flag existed stay visible (grandfathered).
# ---------------------------------------------------------------------------

class TestProjectsIndexRegistration:
    def test_implicit_touch_is_hidden_from_picker_but_enumerable(self, tmp_path):
        worktree = tmp_path / "proj-fork-awl-x"
        worktree.mkdir()
        key = storage.project_key(str(worktree))
        # The record-routing path (runtime_store.save_record / load_project)
        # touches the index WITHOUT register — the fork-worktree scenario.
        state_store.touch_projects_index(key)
        assert key in state_store.known_projects()          # enumeration seam
        listing = asyncio.run(main.list_projects())
        assert key not in [p["path"] for p in listing["projects"]]

    def test_roster_record_save_does_not_register_project(self, tmp_path):
        # End-to-end through the real routing: persisting a fork's roster
        # record into its worktree store must not mint a picker row.
        import runtime_store
        worktree = tmp_path / "proj-fork-awl-y"
        worktree.mkdir()
        runtime_store.save_record({
            "session_id": "fk1", "tmux_name": "awl-fk1",
            "cwd": str(worktree), "claude_session_id": "cid-fk1",
        })
        key = storage.project_key(str(worktree))
        assert key in state_store.known_projects()
        # The record stays reachable (cold-restore / Past tab / retire).
        assert any(r.get("session_id") == "fk1"
                   for r in runtime_store.all_records())
        listing = asyncio.run(main.list_projects())
        assert key not in [p["path"] for p in listing["projects"]]

    def test_register_endpoint_makes_row_visible(self, tmp_path):
        proj = tmp_path / "projX"
        proj.mkdir()
        key = storage.project_key(str(proj))
        state_store.touch_projects_index(key)              # implicit first
        assert key not in [p["path"] for p in
                           asyncio.run(main.list_projects())["projects"]]
        asyncio.run(main.register_project(main.ProjectPathRequest(path=str(proj))))
        assert key in [p["path"] for p in
                       asyncio.run(main.list_projects())["projects"]]

    def test_open_endpoint_registers_too(self, tmp_path):
        proj = tmp_path / "projY"
        proj.mkdir()
        key = storage.project_key(str(proj))
        state_store.touch_projects_index(key)              # implicit first
        asyncio.run(main.open_project(main.ProjectPathRequest(path=str(proj))))
        assert key in [p["path"] for p in
                       asyncio.run(main.list_projects())["projects"]]
        asyncio.run(main.close_project(main.ProjectCloseRequest()))

    def test_legacy_rows_without_flag_stay_visible(self, tmp_path):
        # A pre-flag projects.json row (no `registered` key) is grandfathered.
        import json
        proj = tmp_path / "legacy"
        proj.mkdir()
        key = storage.project_key(str(proj))
        path = storage.projects_index_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(
            {"projects": {key: {"last_used": "2026-07-01T00:00:00"}}}),
            encoding="utf-8")
        listing = asyncio.run(main.list_projects())
        assert key in [p["path"] for p in listing["projects"]]

    def test_implicit_touch_never_downgrades_registration(self, tmp_path):
        proj = tmp_path / "projZ"
        proj.mkdir()
        key = storage.project_key(str(proj))
        asyncio.run(main.register_project(main.ProjectPathRequest(path=str(proj))))
        state_store.touch_projects_index(key)              # e.g. a record save
        assert key in [p["path"] for p in
                       asyncio.run(main.list_projects())["projects"]]
