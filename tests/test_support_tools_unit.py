"""Hermetic unit tests for the §11 #47–#49 support set (git automation,
change-log watcher, system-check).

Pure: no WSL2/tmux, no git subprocess, no network — every probe/exec seam is
injected or monkeypatch-captured. Decided contracts (ARCHITECTURE §11 #47–#49;
build plan ``dev/notes/2026-07-15-stage5-build-plan.md`` ## #47–## #49):

**#47 Git automation** — OPERATOR-TRIGGERED only (no auto-cadence anywhere):
  * ``TmuxBridge.git_run`` — one non-interactive git command in a cwd via the
    bridge's ``_run`` WSL exec path (NEVER keystrokes into the TUI pane): the
    command shape (``cd <cwd> && [ENV…] git <args>`` with per-element shell
    quoting), the trailing ``__GIT_RC__:<n>`` exit-code marker parse (a
    nonzero git exit is a RESULT, not an exception), a required cwd, and an
    unparseable marker raising rather than lying.
  * ``BridgeDriver.git`` — the CRITICAL #19 seam: the launch-time GIT_* env
    belongs to the *claude* process and does NOT reach a bridge-side git
    subprocess, so the driver explicitly injects
    ``identity.git_env(<this agent's identity>)`` into every git_run call.
    Also: action→argv mapping (status / diff / commit = stage-all then
    commit, stopping honestly when the stage fails), the typed RuntimeError
    degrades (``unknown_action`` / ``message_required`` / ``no_cwd`` /
    ``not_a_repo``), and the ``git`` capability flag. ``diff`` is the honest
    PRE-COMMIT view (review fix): ``git diff HEAD`` (staged AND unstaged) plus
    an appended untracked-files listing — exactly what ``add -A`` will sweep —
    with a plain-``git diff`` fallback on an unborn branch.
  * ``POST /sessions/{id}/git`` — 404 unknown session; 400 when the driver
    lacks the ``git`` capability; 409 when a COMMIT targets a project with ANY
    mid-turn agent — the addressed one or a sibling sharing the repo (review
    fix; status/diff stay read-only-safe and run anytime), and while a commit
    is in flight the project's queued prompts DEFER (``_flush_queue``) and are
    re-scheduled when it lands — no turn starts under the in-flight
    ``add -A``; the RuntimeError→HTTP mapping (not_a_repo / message_required
    → 400); success passes the driver's honest result through.

**#48 Change-log watcher** — on-demand v1, no live file-watch:
  * ``changelog.git_log_args`` pins the #19 author query
    (``--author=@agents.awl-cc-dash.invalid``); ``parse_git_log`` parses the
    unit-separator format and skips malformed lines; ``render_changelog``
    groups newest-first by day and renders an honest zero-commit body.
  * ``changelog.refresh`` — writes ``<project>/.awl-cc-dash/docs/
    change-log.md`` via the Library with provenance
    (``created_by="changelog-watcher"``); a second refresh overwrites in
    place (updated: True) instead of tripping create_document's
    FileExistsError; exit 128 + "not a git repository" raises
    NotAGitRepoError; exit 128 + "does not have any commits yet" (unborn
    branch — fresh ``git init``) renders the honest ZERO-commit log (review
    fix), any other git failure raises ChangelogError.
  * ``POST /projects/changelog/refresh`` — 400 with no cwd and no open
    project; 400 when the cwd is not a git repo; success returns the doc info
    with the commit count, running git through the (faked) registry bridge
    with the cwd translated to its IN-WSL spelling (review fix: the canonical
    ``\\wsl.localhost\…`` UNC key of a WSL-internal project doesn't exist
    inside WSL — ``storage.doc_path_wsl`` owns the translation).

**#49 System-check** — one honest aggregation of the EXISTING probes:
  * Each check is ``{status: ok|fail|skipped, detail}``; ``skipped`` =
    "couldn't honestly probe", never a quiet pass. ``aggregate`` — ``ok`` is
    true only when NO check failed (skipped never fails the aggregate).
  * ``check_tmux`` (probe answers → ok with the session count; raises →
    fail). The probe main.py binds is ``TmuxBridge.ping`` + ``list`` — NOT
    bare ``list``, which folds every outage into "zero sessions" and can
    never fail (review fix; ``TmuxBridge.ping`` raises on WSL outage or a
    missing tmux binary). ``check_ttyd`` (path → ok; None → fail; probe
    raising → skipped — the tmux check already owns the WSL outage),
    ``check_auth`` (the §11 #33 split-source reader over candidate cred
    paths: readable identity → ok with email/plan/expiry; files present but
    unreadable → fail; no files → skipped), ``check_drivers`` (fails only
    when the DEFAULT driver is unavailable).
  * ``GET /system-check`` — the five named checks (sidecar / tmux / ttyd /
    auth / drivers) all present with valid statuses; a dead WSL — where
    ``list`` still answers ``{}`` exactly like the real ``_list_raw`` swallow
    — fails tmux and skips ttyd.

**Product-shipped agent definitions** (the "easy-run" halves): both
``assets/agents/changelog-watcher.md`` and ``assets/agents/system-check.md``
exist, carry a frontmatter ``name`` matching the filename, and point at their
sidecar surfaces (the refresh endpoint + author query; /system-check).

These carry neither the ``integration`` nor the ``slow`` mark.
"""

import asyncio
import json
import sys
from pathlib import Path

import pytest
from fastapi import HTTPException

# The sidecar runs with its own dir on sys.path (not the repo root).
_SIDECAR = Path(__file__).resolve().parent.parent / "sidecar"
if str(_SIDECAR) not in sys.path:
    sys.path.insert(0, str(_SIDECAR))

import changelog  # noqa: E402
import library  # noqa: E402
import main  # noqa: E402
import system_check  # noqa: E402
from drivers.base import DriverConfig  # noqa: E402
from drivers.bridge import BridgeDriver  # noqa: E402
from identity import git_env  # noqa: E402
from main import SessionState  # noqa: E402

from bridge.bridge import TmuxBridge, TmuxBridgeError  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parent.parent


# =============================================================================
# #47 — TmuxBridge.git_run (the non-interactive WSL exec path)
# =============================================================================

class TestGitRun:
    def _bridge(self, monkeypatch, output):
        """A TmuxBridge whose _run is captured, never executed."""
        b = TmuxBridge()
        captured = {}

        def fake_run(cmd, timeout=30, stdin_data=None):
            captured["cmd"] = cmd
            captured["timeout"] = timeout
            return output

        monkeypatch.setattr(b, "_run", fake_run)
        return b, captured

    def test_command_shape_and_ok_parse(self, monkeypatch):
        b, captured = self._bridge(monkeypatch, "On branch main\n__GIT_RC__:0")
        res = b.git_run("/tmp/proj", ["status"])
        assert "cd /tmp/proj && git status" in captured["cmd"]
        # The exit-code marker rides the same single round-trip.
        assert "__GIT_RC__" in captured["cmd"]
        assert res == {"code": 0, "output": "On branch main"}

    def test_env_prefix_precedes_git(self, monkeypatch):
        # The caller's env rides as leading VAR=value assignments — the #19
        # identity injection seam (a bridge-side subprocess inherits nothing
        # from the claude launch env).
        b, captured = self._bridge(monkeypatch, "__GIT_RC__:0")
        env = git_env({"name": "zippy", "number": 3})
        b.git_run("/tmp/proj", ["status"], env=env)
        cmd = captured["cmd"]
        assert "GIT_AUTHOR_NAME=zippy" in cmd
        assert "GIT_AUTHOR_EMAIL=zippy-3@agents.awl-cc-dash.invalid" in cmd
        assert "GIT_COMMITTER_NAME=zippy" in cmd
        assert cmd.index("GIT_AUTHOR_NAME=") < cmd.index("git status")

    def test_args_are_individually_quoted(self, monkeypatch):
        # A commit message with spaces stays ONE argv element.
        b, captured = self._bridge(monkeypatch, "__GIT_RC__:0")
        b.git_run("/tmp/proj", ["commit", "-m", "fix the flush race"])
        assert "git commit -m 'fix the flush race'" in captured["cmd"]

    def test_nonzero_exit_is_a_result_not_an_exception(self, monkeypatch):
        b, _ = self._bridge(
            monkeypatch,
            "fatal: not a git repository (or any of the parent directories): "
            ".git\n__GIT_RC__:128")
        res = b.git_run("/tmp/proj", ["status"])
        assert res["code"] == 128
        assert "not a git repository" in res["output"]

    def test_empty_output_parses(self, monkeypatch):
        # `git diff` with no changes prints nothing — code still parses.
        b, _ = self._bridge(monkeypatch, "__GIT_RC__:0")
        assert b.git_run("/tmp/proj", ["diff"]) == {"code": 0, "output": ""}

    def test_missing_marker_raises(self, monkeypatch):
        # A torn/garbled read raises rather than inventing an exit code.
        b, _ = self._bridge(monkeypatch, "some output with no marker")
        with pytest.raises(TmuxBridgeError):
            b.git_run("/tmp/proj", ["status"])

    def test_requires_cwd(self, monkeypatch):
        b, _ = self._bridge(monkeypatch, "__GIT_RC__:0")
        with pytest.raises(TmuxBridgeError):
            b.git_run(None, ["status"])


# =============================================================================
# #49 — TmuxBridge.ping (the RAISING liveness probe; review fix — `list` folds
# every outage into "zero sessions" and can never signal one)
# =============================================================================

class TestPing:
    def test_answers_with_tmux_version(self, monkeypatch):
        b = TmuxBridge()
        monkeypatch.setattr(b, "_run",
                            lambda cmd, timeout=30, stdin_data=None: "tmux 3.4")
        assert b.ping() == "tmux 3.4"

    def test_raises_when_wsl_is_down(self, monkeypatch):
        b = TmuxBridge()

        def dead(cmd, timeout=30, stdin_data=None):
            raise TmuxBridgeError("wsl exec failed")

        monkeypatch.setattr(b, "_run", dead)
        with pytest.raises(TmuxBridgeError):
            b.ping()

    def test_raises_when_tmux_missing(self, monkeypatch):
        # WSL answers but tmux isn't installed — still a raising outage.
        b = TmuxBridge()
        monkeypatch.setattr(b, "_run",
                            lambda cmd, timeout=30, stdin_data=None: "__NO_TMUX__")
        with pytest.raises(TmuxBridgeError, match="not installed"):
            b.ping()

    def test_list_swallows_what_ping_raises(self, monkeypatch):
        # THE review finding, pinned on the REAL object: list() folds a dead
        # backbone into an empty fleet (by design — the UI renders, nothing
        # crashes), so health surfaces must ride ping(), never bare list().
        b = TmuxBridge()

        def dead(cmd, timeout=30, stdin_data=None):
            raise TmuxBridgeError("wsl exec failed")

        monkeypatch.setattr(b, "_run", dead)
        assert b.list() == []
        with pytest.raises(TmuxBridgeError):
            b.ping()


# =============================================================================
# #47 — BridgeDriver.git (identity injection + action mapping + typed degrades)
# =============================================================================

def _git_driver(monkeypatch, results, identity=None, cwd="/tmp/proj"):
    """A BridgeDriver whose bridge.git_run is captured; `results` is the queue
    of {"code","output"} dicts returned per call."""
    d = BridgeDriver(DriverConfig(cwd=cwd, identity=identity), lambda e: None)
    calls = []

    def fake_git_run(cwd_, args, env=None, timeout=60):
        calls.append({"cwd": cwd_, "args": list(args), "env": dict(env or {})})
        return dict(results.pop(0))

    monkeypatch.setattr(d._bridge, "git_run", fake_git_run)
    return d, calls


class TestDriverGit:
    def test_git_capability_advertised(self):
        assert "git" in BridgeDriver.CAPABILITIES

    def test_status_injects_the_agents_git_identity(self, monkeypatch):
        # THE #19 seam: the driver must explicitly inject identity.git_env —
        # the launch-time GIT_* env never reaches this subprocess.
        ident = {"role": "Agent", "number": 3, "name": "zippy"}
        d, calls = _git_driver(monkeypatch, [{"code": 0, "output": "clean"}],
                               identity=ident)
        res = asyncio.run(d.git("status"))
        assert len(calls) == 1
        assert calls[0]["args"] == ["status"]
        assert calls[0]["env"] == git_env(ident)
        assert res["ok"] is True and res["code"] == 0
        assert res["author"] == "zippy"
        assert res["email"] == "zippy-3@agents.awl-cc-dash.invalid"

    def test_unnamed_agent_still_attributed(self, monkeypatch):
        d, calls = _git_driver(monkeypatch, [{"code": 0, "output": ""}],
                               identity={"role": "researcher", "number": 2,
                                         "name": ""})
        asyncio.run(d.git("status"))
        assert calls[0]["env"]["GIT_AUTHOR_NAME"] == "researcher-2"
        assert calls[0]["args"] == ["status"]

    def test_diff_reads_head_and_appends_untracked(self, monkeypatch):
        # The honest pre-commit view (review fix): `git diff HEAD` covers
        # staged AND unstaged tracked changes, and the untracked files
        # `add -A` would sweep are NAMED — a preview blind to new files read
        # as "nothing changed" right before a commit that included them all.
        d, calls = _git_driver(
            monkeypatch,
            [{"code": 0, "output": "diff --git a/x.py b/x.py"},
             {"code": 0, "output": "new1.py\nnew2.py"}])
        res = asyncio.run(d.git("diff"))
        assert [c["args"] for c in calls] == [
            ["diff", "HEAD"],
            ["ls-files", "--others", "--exclude-standard"]]
        assert res["ok"] is True
        assert "diff --git a/x.py" in res["output"]
        assert "Untracked files" in res["output"]
        assert "new1.py" in res["output"] and "new2.py" in res["output"]

    def test_diff_without_untracked_is_plain(self, monkeypatch):
        d, _ = _git_driver(monkeypatch,
                           [{"code": 0, "output": "diff --git a/x.py b/x.py"},
                            {"code": 0, "output": ""}])
        res = asyncio.run(d.git("diff"))
        assert "Untracked files" not in res["output"]

    def test_diff_unborn_head_falls_back(self, monkeypatch):
        # Fresh `git init`: HEAD is unresolvable — fall back to plain
        # `git diff`; the untracked listing carries the (entirely new) tree.
        d, calls = _git_driver(
            monkeypatch,
            [{"code": 128,
              "output": "fatal: ambiguous argument 'HEAD': unknown revision "
                        "or path not in the working tree."},
             {"code": 0, "output": ""},
             {"code": 0, "output": "brand-new.py"}])
        res = asyncio.run(d.git("diff"))
        assert [c["args"] for c in calls] == [
            ["diff", "HEAD"], ["diff"],
            ["ls-files", "--others", "--exclude-standard"]]
        assert res["ok"] is True and "brand-new.py" in res["output"]

    def test_diff_not_a_repo_still_types(self, monkeypatch):
        d, _ = _git_driver(
            monkeypatch,
            [{"code": 128,
              "output": "fatal: not a git repository (or any of the parent "
                        "directories): .git"}])
        with pytest.raises(RuntimeError, match="not_a_repo"):
            asyncio.run(d.git("diff"))

    def test_commit_stages_all_then_commits(self, monkeypatch):
        d, calls = _git_driver(monkeypatch,
                               [{"code": 0, "output": ""},
                                {"code": 0, "output": "[main abc] msg"}],
                               identity={"name": "ivy", "number": 1})
        res = asyncio.run(d.git("commit", "fix the thing"))
        assert [c["args"] for c in calls] == [["add", "-A"],
                                              ["commit", "-m", "fix the thing"]]
        # BOTH subprocesses carry the identity env.
        for c in calls:
            assert c["env"]["GIT_AUTHOR_EMAIL"].endswith(
                "@agents.awl-cc-dash.invalid")
        assert res["ok"] is True

    def test_commit_stops_when_stage_fails(self, monkeypatch):
        d, calls = _git_driver(monkeypatch, [{"code": 1, "output": "add boom"}])
        res = asyncio.run(d.git("commit", "msg"))
        assert len(calls) == 1  # the commit step never ran
        assert res["ok"] is False and res["code"] == 1
        assert "add boom" in res["output"]

    def test_failed_commit_is_honest_result(self, monkeypatch):
        # "nothing to commit" (exit 1) is a result, not an exception.
        d, _ = _git_driver(monkeypatch,
                           [{"code": 0, "output": ""},
                            {"code": 1, "output": "nothing to commit"}])
        res = asyncio.run(d.git("commit", "msg"))
        assert res["ok"] is False and "nothing to commit" in res["output"]

    def test_commit_requires_message(self, monkeypatch):
        d, calls = _git_driver(monkeypatch, [])
        for missing in (None, "", "   "):
            with pytest.raises(RuntimeError, match="message_required"):
                asyncio.run(d.git("commit", missing))
        assert calls == []  # refused before any subprocess

    def test_no_cwd_refused(self, monkeypatch):
        d, _ = _git_driver(monkeypatch, [], cwd=None)
        with pytest.raises(RuntimeError, match="no_cwd"):
            asyncio.run(d.git("status"))

    def test_unknown_action_refused(self, monkeypatch):
        d, _ = _git_driver(monkeypatch, [])
        with pytest.raises(RuntimeError, match="unknown_action"):
            asyncio.run(d.git("push"))

    def test_not_a_repo_raises_typed(self, monkeypatch):
        d, _ = _git_driver(
            monkeypatch,
            [{"code": 128,
              "output": "fatal: not a git repository (or any of the parent "
                        "directories): .git"}])
        with pytest.raises(RuntimeError, match="not_a_repo"):
            asyncio.run(d.git("status"))


# =============================================================================
# #47 — POST /sessions/{id}/git (endpoint wiring)
# =============================================================================

class _FakeGitDriver:
    name = "bridge"

    def __init__(self, result=None, error=None, git_capable=True):
        self.result = result or {"action": "status", "ok": True, "code": 0,
                                 "output": "clean", "author": "zippy",
                                 "email": "zippy-3@agents.awl-cc-dash.invalid"}
        self.error = error
        self.git_capable = git_capable
        self.calls = []
        self.sent = []

    def supports(self, cap):
        return cap == "git" and self.git_capable

    async def git(self, action, message=None):
        self.calls.append((action, message))
        if self.error is not None:
            raise self.error
        return self.result

    async def send(self, prompt):
        # For the flush-deferral tests — _flush_queue delivers through here.
        self.sent.append(prompt)


# A nonexistent Windows-side cwd: project_key resolves it purely on path math
# (no .git anywhere above), so the project-gate tests stay hermetic and fast.
_FAKE_PROJ = "C:/awl-fake-tests/proj"


def _register(sid, driver, status="idle", cwd=_FAKE_PROJ):
    s = SessionState(session_id=sid, agent_type=None, model=None,
                     permission_mode="default", cwd=cwd, system_prompt=None,
                     driver_name="bridge")
    s.driver = driver
    s.status = status
    main.sessions[sid] = s
    return s


class TestGitEndpoint:
    def _call(self, sid, action, message=None):
        return asyncio.run(main.session_git(
            sid, main.GitActionRequest(action=action, message=message)))

    def test_unknown_session_404(self):
        with pytest.raises(HTTPException) as e:
            self._call("nope", "status")
        assert e.value.status_code == 404

    def test_driver_without_git_capability_400(self):
        _register("g1", _FakeGitDriver(git_capable=False))
        try:
            with pytest.raises(HTTPException) as e:
                self._call("g1", "status")
            assert e.value.status_code == 400
        finally:
            main.sessions.pop("g1", None)

    def test_commit_gated_409_while_running(self):
        drv = _FakeGitDriver()
        _register("g2", drv, status="running")
        try:
            with pytest.raises(HTTPException) as e:
                self._call("g2", "commit", "msg")
            assert e.value.status_code == 409
            assert drv.calls == []  # never reached the driver
        finally:
            main.sessions.pop("g2", None)

    def test_commit_gated_409_when_sibling_mid_turn_in_same_project(self):
        # Review fix: `git add -A` spans the SHARED repo — a mid-turn sibling
        # in the same project races the commit exactly like the addressed
        # agent would, so the busy gate covers the whole project.
        drv = _FakeGitDriver()
        _register("g2a", drv, status="idle")
        _register("g2b", _FakeGitDriver(), status="running")  # same cwd
        try:
            with pytest.raises(HTTPException) as e:
                self._call("g2a", "commit", "msg")
            assert e.value.status_code == 409
            assert "g2b" in e.value.detail
            assert drv.calls == []
        finally:
            main.sessions.pop("g2a", None)
            main.sessions.pop("g2b", None)

    def test_commit_ok_when_running_sibling_is_another_project(self):
        drv = _FakeGitDriver(result={"action": "commit", "ok": True,
                                     "code": 0, "output": "[main abc] m",
                                     "author": "zippy",
                                     "email": "zippy-3@agents.awl-cc-dash.invalid"})
        _register("g2c", drv, status="idle")
        _register("g2d", _FakeGitDriver(), status="running",
                  cwd="C:/awl-fake-tests/other-proj")
        try:
            res = self._call("g2c", "commit", "m")
            assert res["ok"] is True and drv.calls == [("commit", "m")]
        finally:
            main.sessions.pop("g2c", None)
            main.sessions.pop("g2d", None)

    def test_flush_defers_while_commit_inflight_then_resumes(self):
        # Review fix (check-then-act): a queued prompt must not start a turn
        # under an in-flight `add -A`. _flush_queue defers while the project
        # has a commit in flight and delivers normally once it's gone.
        import storage  # sidecar module (sys.path'd above)
        drv = _FakeGitDriver()
        s = _register("g2e", drv, status="idle")
        pkey = storage.project_key(_FAKE_PROJ)
        try:
            s.enqueue({"id": "q1", "prompt": "hello", "source": "user",
                       "recipients": ["g2e"], "disposition": "queue",
                       "enqueued_at": "t"}, "queue")
            main._git_commits_inflight[pkey] = 1
            asyncio.run(main._flush_queue(s))
            assert drv.sent == [] and len(s.prompt_queue) == 1
            assert s.status == "idle"  # nothing started
            main._git_commits_inflight.pop(pkey, None)
            asyncio.run(main._flush_queue(s))
            assert drv.sent == ["hello"] and not s.prompt_queue
        finally:
            main._git_commits_inflight.pop(pkey, None)
            main.sessions.pop("g2e", None)

    def test_commit_reschedules_the_flushes_it_deferred(self):
        # The queued prompt a commit deferred must not sit stranded: the
        # commit's finally re-schedules the project's flushes.
        drv = _FakeGitDriver(result={"action": "commit", "ok": True,
                                     "code": 0, "output": "[main abc] m",
                                     "author": "zippy",
                                     "email": "zippy-3@agents.awl-cc-dash.invalid"})
        s = _register("g2f", drv, status="idle")
        s.enqueue({"id": "q2", "prompt": "after-commit", "source": "user",
                   "recipients": ["g2f"], "disposition": "queue",
                   "enqueued_at": "t"}, "queue")

        async def scenario():
            res = await main.session_git(
                "g2f", main.GitActionRequest(action="commit", message="m"))
            # Let the re-scheduled flush task run.
            await asyncio.sleep(0)
            await asyncio.sleep(0)
            return res

        try:
            res = asyncio.run(scenario())
            assert res["ok"] is True
            assert drv.sent == ["after-commit"]
            assert main._git_commits_inflight == {}
        finally:
            main.sessions.pop("g2f", None)

    def test_status_allowed_while_running(self):
        # Read-only actions never gate on busy.
        drv = _FakeGitDriver()
        _register("g3", drv, status="running")
        try:
            res = self._call("g3", "status")
            assert res["ok"] is True and drv.calls == [("status", None)]
        finally:
            main.sessions.pop("g3", None)

    def test_not_a_repo_maps_400(self):
        _register("g4", _FakeGitDriver(error=RuntimeError("not_a_repo")))
        try:
            with pytest.raises(HTTPException) as e:
                self._call("g4", "status")
            assert e.value.status_code == 400
            assert "not a git repository" in e.value.detail
        finally:
            main.sessions.pop("g4", None)

    def test_message_required_maps_400(self):
        _register("g5", _FakeGitDriver(error=RuntimeError("message_required")))
        try:
            with pytest.raises(HTTPException) as e:
                self._call("g5", "commit")
            assert e.value.status_code == 400
        finally:
            main.sessions.pop("g5", None)

    def test_bridge_failure_maps_500(self):
        _register("g6", _FakeGitDriver(error=RuntimeError("wsl exploded")))
        try:
            with pytest.raises(HTTPException) as e:
                self._call("g6", "status")
            assert e.value.status_code == 500
        finally:
            main.sessions.pop("g6", None)

    def test_success_passes_driver_result_through(self):
        drv = _FakeGitDriver(result={"action": "commit", "ok": True,
                                     "code": 0, "output": "[main abc] m",
                                     "author": "ivy",
                                     "email": "ivy-1@agents.awl-cc-dash.invalid"})
        _register("g7", drv)
        try:
            res = self._call("g7", "commit", "m")
            assert res["author"] == "ivy" and res["action"] == "commit"
            assert drv.calls == [("commit", "m")]
        finally:
            main.sessions.pop("g7", None)


# =============================================================================
# #48 — changelog engine
# =============================================================================

def _log_line(sha, author, email, date, subject):
    return "\x1f".join((sha, author, email, date, subject))


class TestChangelogEngine:
    def test_git_log_args_pin_the_author_query(self):
        args = changelog.git_log_args()
        assert args[0] == "log"
        assert "--author=@agents.awl-cc-dash.invalid" in args
        assert "--date=iso-strict" in args

    def test_parse_git_log(self):
        out = "\n".join([
            _log_line("abc1234", "zippy", "zippy-3@agents.awl-cc-dash.invalid",
                      "2026-07-16T10:00:00+00:00", "fix the flush race"),
            "malformed line without separators",
            _log_line("def5678", "ivy", "ivy-1@agents.awl-cc-dash.invalid",
                      "2026-07-15T09:00:00+00:00", "add the poll bundle"),
        ])
        commits = changelog.parse_git_log(out)
        assert [c["sha"] for c in commits] == ["abc1234", "def5678"]
        assert commits[0]["author"] == "zippy"
        assert commits[1]["subject"] == "add the poll bundle"

    def test_parse_empty_output(self):
        assert changelog.parse_git_log("") == []

    def test_render_groups_by_day_newest_first(self):
        commits = changelog.parse_git_log("\n".join([
            _log_line("abc1234", "zippy", "z@agents.awl-cc-dash.invalid",
                      "2026-07-16T10:00:00+00:00", "newest"),
            _log_line("def5678", "ivy", "i@agents.awl-cc-dash.invalid",
                      "2026-07-15T09:00:00+00:00", "older"),
        ]))
        md = changelog.render_changelog(commits, generated_at="2026-07-16T12:00:00Z")
        assert md.index("## 2026-07-16") < md.index("## 2026-07-15")
        assert md.index("`abc1234`") < md.index("`def5678`")
        assert "**zippy**" in md and "newest" in md
        assert "2026-07-16T12:00:00Z" in md  # injectable stamp renders

    def test_render_zero_commits_is_honest(self):
        md = changelog.render_changelog([], generated_at="x")
        assert "No AI-authored commits" in md
        assert "0 commit(s)" in md

    def test_refresh_creates_doc_with_provenance(self, tmp_path):
        out = _log_line("abc1234", "zippy", "z@agents.awl-cc-dash.invalid",
                        "2026-07-16T10:00:00+00:00", "fix it")
        seen = []

        def run_git(args):
            seen.append(args)
            return {"code": 0, "output": out}

        res = changelog.refresh(str(tmp_path), run_git)
        assert seen == [changelog.git_log_args()]
        path = Path(res["path"])
        assert path.resolve() == \
            (tmp_path / ".awl-cc-dash" / "docs" / "change-log.md").resolve()
        assert res["commits"] == 1 and res["updated"] is False
        assert "abc1234" in path.read_text(encoding="utf-8")
        prov = library.doc_provenance(path)
        assert prov["created_by"] == "changelog-watcher"
        assert "created_at" in prov

    def test_refresh_updates_in_place(self, tmp_path):
        first = _log_line("abc1234", "zippy", "z@agents.awl-cc-dash.invalid",
                          "2026-07-16T10:00:00+00:00", "first")
        both = first + "\n" + _log_line(
            "def5678", "ivy", "i@agents.awl-cc-dash.invalid",
            "2026-07-16T11:00:00+00:00", "second")
        changelog.refresh(str(tmp_path), lambda a: {"code": 0, "output": first})
        res = changelog.refresh(str(tmp_path), lambda a: {"code": 0, "output": both})
        # Second refresh overwrites (never FileExistsError) and says so.
        assert res["updated"] is True and res["commits"] == 2
        text = Path(res["path"]).read_text(encoding="utf-8")
        assert "def5678" in text and "abc1234" in text

    def test_refresh_not_a_repo_raises_typed(self, tmp_path):
        def run_git(args):
            return {"code": 128,
                    "output": "fatal: not a git repository (or any of the "
                              "parent directories): .git"}

        with pytest.raises(changelog.NotAGitRepoError):
            changelog.refresh(str(tmp_path), run_git)

    def test_refresh_unborn_branch_renders_zero_commits(self, tmp_path):
        # Review fix: a fresh `git init` (zero commits, unborn branch) exits
        # 128 with "does not have any commits yet" — that IS the honest
        # zero-commit state, not a failure.
        def run_git(args):
            return {"code": 128,
                    "output": "fatal: your current branch 'main' does not "
                              "have any commits yet"}

        res = changelog.refresh(str(tmp_path), run_git)
        assert res["commits"] == 0
        text = Path(res["path"]).read_text(encoding="utf-8")
        assert "No AI-authored commits" in text

    def test_refresh_other_git_failure_raises(self, tmp_path):
        with pytest.raises(changelog.ChangelogError):
            changelog.refresh(str(tmp_path),
                              lambda a: {"code": 2, "output": "boom"})


class _FakeRegistryBridge:
    """A registry-bridge stand-in honoring the REAL TmuxBridge contracts:
    ``list`` swallows outages into an empty fleet (like ``_list_raw``) — only
    ``ping`` and ``resolve_ttyd`` raise when the backbone is dead."""

    def __init__(self, git_result=None, sessions=None, ttyd="/usr/bin/ttyd",
                 broken=False):
        self.git_result = git_result or {"code": 0, "output": ""}
        self.sessions_result = sessions if sessions is not None else {}
        self.ttyd = ttyd
        self.broken = broken
        self.git_calls = []

    def git_run(self, cwd, args, env=None, timeout=60):
        self.git_calls.append((cwd, list(args)))
        return dict(self.git_result)

    def ping(self):
        if self.broken:
            raise RuntimeError("wsl down")
        return "tmux 3.4"

    def list(self):
        # Mirrors the real swallow: a dead backbone reads as zero sessions —
        # exactly why the health probe must ride ping() first (review fix).
        if self.broken:
            return {}
        return dict(self.sessions_result)

    def resolve_ttyd(self):
        if self.broken:
            raise RuntimeError("wsl down")
        return self.ttyd


class TestChangelogEndpoint:
    def _call(self, cwd):
        return asyncio.run(main.refresh_changelog(
            main.ChangelogRefreshRequest(cwd=cwd)))

    def test_no_cwd_and_no_open_project_400(self, monkeypatch):
        monkeypatch.setattr(main, "_open_project", None)
        with pytest.raises(HTTPException) as e:
            asyncio.run(main.refresh_changelog(None))
        assert e.value.status_code == 400

    def test_nonexistent_cwd_400(self, monkeypatch):
        monkeypatch.setattr(main, "_get_registry_bridge",
                            lambda: _FakeRegistryBridge())
        with pytest.raises(HTTPException) as e:
            self._call("C:/definitely/not/a/dir/xyz")
        assert e.value.status_code == 400

    def test_refresh_writes_doc_via_registry_bridge(self, tmp_path, monkeypatch):
        out = _log_line("abc1234", "zippy", "z@agents.awl-cc-dash.invalid",
                        "2026-07-16T10:00:00+00:00", "fix it")
        fake = _FakeRegistryBridge(git_result={"code": 0, "output": out})
        monkeypatch.setattr(main, "_get_registry_bridge", lambda: fake)
        res = self._call(str(tmp_path))
        assert res["commits"] == 1
        assert Path(res["path"]).is_file()
        assert fake.git_calls and fake.git_calls[0][1] == changelog.git_log_args()
        # Review fix: git runs INSIDE WSL, so the cwd handed to git_run must
        # be the in-WSL spelling of the canonical root (a Windows tmp_path →
        # /mnt/<drive>/…), never the raw Windows/UNC form.
        assert fake.git_calls[0][0].startswith("/mnt/")

    def test_wsl_internal_unc_cwd_translates_for_git(self):
        # THE WSL-internal project shape (§8.1): the canonical UNC key does
        # not exist inside WSL — the translation seam the endpoint now rides
        # must strip it to the plain /home/… path (review fix).
        import storage  # sidecar module (sys.path'd above)
        assert storage.doc_path_wsl(
            r"\\wsl.localhost\Ubuntu\home\lester\proj") == "/home/lester/proj"

    def test_not_a_repo_maps_400(self, tmp_path, monkeypatch):
        fake = _FakeRegistryBridge(git_result={
            "code": 128, "output": "fatal: not a git repository"})
        monkeypatch.setattr(main, "_get_registry_bridge", lambda: fake)
        with pytest.raises(HTTPException) as e:
            self._call(str(tmp_path))
        assert e.value.status_code == 400

    def test_git_failure_maps_502(self, tmp_path, monkeypatch):
        fake = _FakeRegistryBridge(git_result={"code": 2, "output": "boom"})
        monkeypatch.setattr(main, "_get_registry_bridge", lambda: fake)
        with pytest.raises(HTTPException) as e:
            self._call(str(tmp_path))
        assert e.value.status_code == 502


# =============================================================================
# #49 — system_check probes + aggregation
# =============================================================================

class TestSystemCheckProbes:
    def test_check_tmux_ok_counts_sessions(self):
        res = system_check.check_tmux(lambda: {"a": {}, "b": {}})
        assert res["status"] == "ok" and "2" in res["detail"]

    def test_check_tmux_fail_on_raise(self):
        def probe():
            raise RuntimeError("wsl down")
        res = system_check.check_tmux(probe)
        assert res["status"] == "fail" and "wsl down" in res["detail"]

    def test_check_ttyd_ok(self):
        res = system_check.check_ttyd(lambda: "/home/x/.local/bin/ttyd")
        assert res["status"] == "ok" and "/home/x/.local/bin/ttyd" in res["detail"]

    def test_check_ttyd_missing_is_fail(self):
        res = system_check.check_ttyd(lambda: None)
        assert res["status"] == "fail" and "not installed" in res["detail"]

    def test_check_ttyd_unprobeable_is_skipped(self):
        # WSL down → the tmux check owns that outage; ttyd is honestly skipped.
        def probe():
            raise RuntimeError("wsl down")
        assert system_check.check_ttyd(probe)["status"] == "skipped"

    def test_check_auth_ok_reads_split_source(self, tmp_path):
        claude_json = tmp_path / ".claude.json"
        claude_json.write_text(json.dumps({"oauthAccount": {
            "emailAddress": "op@example.com",
            "organizationName": "Org",
        }}), encoding="utf-8")
        creds = tmp_path / ".credentials.json"
        creds.write_text(json.dumps({"claudeAiOauth": {
            "subscriptionType": "max",
            "expiresAt": 1799999999000,
        }}), encoding="utf-8")
        res = system_check.check_auth([(str(claude_json), str(creds))])
        assert res["status"] == "ok"
        assert "op@example.com" in res["detail"] and "max" in res["detail"]

    def test_check_auth_no_files_is_skipped(self, tmp_path):
        res = system_check.check_auth(
            [(str(tmp_path / "no.json"), str(tmp_path / "nope.json"))])
        assert res["status"] == "skipped"

    def test_check_auth_unreadable_identity_is_fail(self, tmp_path):
        creds = tmp_path / ".credentials.json"
        creds.write_text("{}", encoding="utf-8")
        res = system_check.check_auth(
            [(str(tmp_path / "absent.json"), str(creds))])
        assert res["status"] == "fail"

    def test_check_drivers_ok_when_default_available(self):
        res = system_check.check_drivers(
            "bridge", {"bridge": ["git", "resume"],
                       "sdk": {"unavailable": "no sdk installed"}})
        assert res["status"] == "ok"
        assert "git" in res["detail"] and "unavailable" in res["detail"]

    def test_check_drivers_fails_when_default_unavailable(self):
        res = system_check.check_drivers(
            "bridge", {"bridge": {"unavailable": "boom"}, "sdk": ["context"]})
        assert res["status"] == "fail"

    def test_aggregate_ok_only_when_nothing_failed(self):
        ok = system_check.ok_result("x")
        skipped = system_check.skipped_result("y")
        fail = system_check.fail_result("z")
        assert system_check.aggregate({"a": ok, "b": skipped})["ok"] is True
        assert system_check.aggregate({"a": ok, "b": fail})["ok"] is False

    def test_result_status_validated(self):
        with pytest.raises(ValueError):
            system_check.result("warn", "not a valid status")


class TestSystemCheckEndpoint:
    EXPECTED = ("sidecar", "tmux", "ttyd", "auth", "drivers")

    def test_all_checks_present_with_valid_statuses(self, monkeypatch):
        fake = _FakeRegistryBridge(sessions={"a": {}})
        monkeypatch.setattr(main, "_get_registry_bridge", lambda: fake)
        monkeypatch.setattr(system_check, "default_auth_candidates", lambda: [])
        res = asyncio.run(main.system_check_endpoint())
        assert set(self.EXPECTED) <= set(res["checks"])
        for name in self.EXPECTED:
            assert res["checks"][name]["status"] in system_check.STATUSES
        assert res["checks"]["sidecar"]["status"] == "ok"
        assert res["checks"]["tmux"]["status"] == "ok"
        assert res["checks"]["auth"]["status"] == "skipped"
        assert isinstance(res["ok"], bool)

    def test_dead_bridge_fails_tmux_and_skips_ttyd(self, monkeypatch):
        fake = _FakeRegistryBridge(broken=True)
        monkeypatch.setattr(main, "_get_registry_bridge", lambda: fake)
        monkeypatch.setattr(system_check, "default_auth_candidates", lambda: [])
        res = asyncio.run(main.system_check_endpoint())
        assert res["checks"]["tmux"]["status"] == "fail"
        assert res["checks"]["ttyd"]["status"] == "skipped"
        assert res["ok"] is False


# =============================================================================
# Product-shipped agent definitions (the "easy-run" halves of #48/#49)
# =============================================================================

class TestAgentDefinitions:
    def _read(self, name):
        path = REPO_ROOT / "assets" / "agents" / name
        assert path.is_file(), f"missing product agent definition: {path}"
        return path.read_text(encoding="utf-8")

    def test_changelog_watcher_definition(self):
        text = self._read("changelog-watcher.md")
        assert text.startswith("---")
        assert "name: changelog-watcher" in text
        assert "/projects/changelog/refresh" in text
        assert "@agents.awl-cc-dash.invalid" in text  # the #19 author query

    def test_system_check_definition(self):
        text = self._read("system-check.md")
        assert text.startswith("---")
        assert "name: system-check" in text
        assert "/system-check" in text
