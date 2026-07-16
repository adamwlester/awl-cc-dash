"""Hermetic unit tests for Rewind / Fork — the Timeline (§7.19, §11 #15).

Pure: no WSL2/tmux, no live model, no network, no HTTP server. Every launch /
menu side effect is scripted-fake captured (``_run`` / ``_list_raw`` /
``_clear_startup_gates`` / ``read`` / ``keys``), never executed; the async
endpoint + driver functions are called directly via ``asyncio.run``. These carry
NEITHER the ``integration`` nor the ``slow`` mark. The live counterpart that
proves an actual rewind/fork against a running agent is
``tests/test_rewind_handoff_live.py``.

Decided contract (ARCHITECTURE §7.19; build plan
``dev/notes/2026-07-15-stage5-build-plan.md`` #15):

  * REWIND = drive the native ``/rewind`` menu over tmux to restore the
    CONVERSATION to an earlier prompt checkpoint IN-PLACE (same session id).
  * FORK   = ``claude --resume <src> --fork-session`` spawns an INDEPENDENT new
    session (source untouched); ``/rewind`` inside the fork is branch-from-N.
  * A ``>= 2.1.191`` version gate at the rewind/fork entry; below it (or an
    unresolvable version) the feature is UNAVAILABLE and degrades honestly —
    never a silent no-op.
  * The per-fork FILE-STATE policy is a git worktree (⚠ assumed, doc-consistent);
    the fork gets its own working copy, with an HONEST fallback to the shared cwd
    when the source isn't a git repo / isolation isn't requested / the add fails.
  * Fork sessions stay TAB-LESS and carry the fork's OWN #19 git identity.

What this file pins:
  * the version-gate comparison (below / at / above 2.1.191, malformed version);
  * ``create(fork_session=True)`` argv — ``--fork-session`` present, no pinned
    ``--session-id``, ``session_id`` None, git-env preserved, tab-less;
  * ``prepare_fork_filestate`` — the git-worktree isolation + honest fallback;
  * ``fork()`` launch-command construction end-to-end;
  * ``rewind()`` key/command sequence construction;
  * the driver's RuntimeError translation and the endpoints' honest error mapping
    (404 / 400 no-capability / 400 version-unsupported / 409 busy) + fork success.
"""

import sys
from pathlib import Path

import pytest

# Repo root on sys.path so `from bridge import ...` / `from sidecar...` resolve.
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))
# The sidecar runs with its OWN dir on sys.path (not the repo root) — mirror that
# so `import main` matches the sidecar's own import layout (as test_sidecar_unit).
_SIDECAR = _REPO_ROOT / "sidecar"
if str(_SIDECAR) not in sys.path:
    sys.path.insert(0, str(_SIDECAR))

import asyncio  # noqa: E402

from bridge.bridge import (  # noqa: E402
    REWIND_FORK_MIN_VERSION,
    TmuxBridge,
    TmuxBridgeError,
    VersionUnsupportedError,
    parse_claude_version,
    version_at_least,
)
from bridge.paths import CLAUDE_BIN  # noqa: E402
from sidecar.drivers.bridge import BridgeDriver  # noqa: E402
from sidecar.drivers.base import DriverConfig  # noqa: E402


# -----------------------------------------------------------------------------
# Version gate — pure comparison + the live-probe enforcement
# -----------------------------------------------------------------------------

class TestParseClaudeVersion:
    def test_parses_standard_output(self):
        assert parse_claude_version("2.1.198 (Claude Code)") == (2, 1, 198)

    def test_parses_bare_triple(self):
        assert parse_claude_version("2.1.191") == (2, 1, 191)

    def test_empty_or_unparseable_is_none(self):
        assert parse_claude_version("") is None
        assert parse_claude_version(None) is None
        assert parse_claude_version("Claude Code (dev build)") is None


class TestVersionAtLeast:
    MIN = REWIND_FORK_MIN_VERSION

    def test_pins_the_gate_at_2_1_191(self):
        # Drift here silently changes which builds can rewind/fork — pin it.
        assert REWIND_FORK_MIN_VERSION == (2, 1, 191)

    def test_below_is_false(self):
        assert version_at_least((2, 1, 190), self.MIN) is False
        assert version_at_least((2, 0, 999), self.MIN) is False
        assert version_at_least((1, 9, 9), self.MIN) is False

    def test_at_bar_is_true(self):
        assert version_at_least((2, 1, 191), self.MIN) is True

    def test_above_is_true(self):
        assert version_at_least((2, 1, 198), self.MIN) is True
        assert version_at_least((2, 2, 0), self.MIN) is True
        assert version_at_least((3, 0, 0), self.MIN) is True

    def test_none_or_empty_treated_as_not_met(self):
        # An unresolvable version must NOT silently pass the gate.
        assert version_at_least(None, self.MIN) is False
        assert version_at_least((), self.MIN) is False


class TestRequireRewindForkVersion:
    """The live-probe enforcement: reads `claude --version` via _run and raises
    VersionUnsupportedError below the bar / when unresolvable."""

    def _bridge(self, monkeypatch, version_out):
        b = TmuxBridge()
        monkeypatch.setattr(
            b, "_run",
            lambda cmd, **kw: version_out if "--version" in cmd else "")
        return b

    def test_above_bar_passes_and_returns_version(self, monkeypatch):
        b = self._bridge(monkeypatch, "2.1.198 (Claude Code)")
        assert b.require_rewind_fork_version() == (2, 1, 198)

    def test_at_bar_passes(self, monkeypatch):
        b = self._bridge(monkeypatch, "2.1.191 (Claude Code)")
        assert b.require_rewind_fork_version() == (2, 1, 191)

    def test_below_bar_raises_version_unsupported(self, monkeypatch):
        b = self._bridge(monkeypatch, "2.1.190 (Claude Code)")
        with pytest.raises(VersionUnsupportedError) as ei:
            b.require_rewind_fork_version()
        assert "2.1.191" in str(ei.value)          # names the required version
        assert "2.1.190" in str(ei.value)          # names what's installed
        # It is a TmuxBridgeError subclass (existing handlers still catch it).
        assert isinstance(ei.value, TmuxBridgeError)

    def test_unresolvable_version_raises(self, monkeypatch):
        # A blank / unparseable probe degrades honestly — NOT a silent pass.
        b = self._bridge(monkeypatch, "")
        with pytest.raises(VersionUnsupportedError):
            b.require_rewind_fork_version()

    def test_probe_failure_raises(self, monkeypatch):
        # `claude --version` erroring (TmuxBridgeError) => version None => raise.
        b = TmuxBridge()

        def boom(cmd, **kw):
            raise TmuxBridgeError("no claude")
        monkeypatch.setattr(b, "_run", boom)
        with pytest.raises(VersionUnsupportedError):
            b.require_rewind_fork_version()


# -----------------------------------------------------------------------------
# create(fork_session=True) — the --fork-session launch argv.
# Scripted-fake captured, never executed (mirrors TestCreateResumeLaunch /
# TestCreateGitEnvPrefix in test_bridge_unit.py / test_git_identity_unit.py).
# -----------------------------------------------------------------------------

def _patched_bridge(monkeypatch, name, version_out="2.1.198 (Claude Code)"):
    """A TmuxBridge whose launch side effects are captured, not run. `_run`
    answers `claude --version` with `version_out` (so the fork/rewind gate can
    run live-shaped) and captures every other command."""
    b = TmuxBridge()
    captured = {"commands": []}

    def fake_run(cmd, timeout=30, stdin_data=None):
        captured["commands"].append(cmd)
        if "--version" in cmd:
            return version_out
        return ""

    state = {"listed": 0}

    def fake_list_raw():
        state["listed"] += 1
        return {} if state["listed"] == 1 else {name: {"pid": "42"}}

    monkeypatch.setattr(b, "_run", fake_run)
    monkeypatch.setattr(b, "_list_raw", fake_list_raw)
    monkeypatch.setattr(b, "_clear_startup_gates", lambda n, **kw: None)
    monkeypatch.setattr("bridge.bridge.time.sleep", lambda s: None)
    return b, captured


def _launch_cmd(captured):
    cmds = [c for c in captured["commands"] if c.startswith("tmux new-session")]
    assert len(cmds) == 1, f"expected one tmux new-session, got: {cmds}"
    return cmds[0]


class TestCreateForkArgv:
    SRC = "6c61e972-624e-47cb-a509-7b6ff708a1db"

    def test_fork_launch_uses_resume_and_fork_session_no_session_id(self, monkeypatch):
        b, captured = _patched_bridge(monkeypatch, "fork1")
        info = b.create("fork1", cwd="/home/lester/proj",
                        resume_session_id=self.SRC, fork_session=True)
        cmd = _launch_cmd(captured)
        assert f"--resume {self.SRC}" in cmd
        assert "--fork-session" in cmd
        assert "--session-id" not in cmd            # a fork mints a NEW id
        # The fork's id is UNKNOWN at launch — not pinned, not registered.
        assert info["session_id"] is None
        assert b.session_id_for("fork1") is None
        assert info["resumed_conversation"] is True
        assert info["forked"] is True

    def test_fork_carries_git_env_and_is_tabless(self, monkeypatch):
        # #19 git attribution rides the fork launch; tab-less (no `wt`, show off).
        b, captured = _patched_bridge(monkeypatch, "fork2")
        opened = []
        monkeypatch.setattr(b, "_open_wt_tab", lambda n: opened.append(n))
        b.create("fork2", cwd="/home/lester/proj",
                 resume_session_id=self.SRC, fork_session=True,
                 git_author_name="ivy",
                 git_author_email="ivy-5@agents.awl-cc-dash.invalid")
        cmd = _launch_cmd(captured)
        assert "GIT_AUTHOR_NAME=ivy" in cmd
        assert "GIT_COMMITTER_EMAIL=ivy-5@agents.awl-cc-dash.invalid" in cmd
        assert cmd.index("GIT_AUTHOR_NAME=") < cmd.index(CLAUDE_BIN)
        assert opened == []                         # tab-less: no WT tab opened

    def test_fork_session_without_resume_raises(self, monkeypatch):
        b, _ = _patched_bridge(monkeypatch, "bad")
        with pytest.raises(TmuxBridgeError) as ei:
            b.create("bad", cwd="/tmp/x", fork_session=True)
        assert "resume_session_id" in str(ei.value)

    def test_plain_resume_unchanged_by_fork_flag_default(self, monkeypatch):
        # Regression: fork_session defaults False, so a plain cold-restore resume
        # still reuses the SAME id (no --fork-session, --session-id absent).
        b, captured = _patched_bridge(monkeypatch, "restored")
        info = b.create("restored", cwd="/tmp/x", resume_session_id=self.SRC)
        cmd = _launch_cmd(captured)
        assert f"--resume {self.SRC}" in cmd
        assert "--fork-session" not in cmd
        assert info["forked"] is False
        assert b.session_id_for("restored") == self.SRC


# -----------------------------------------------------------------------------
# prepare_fork_filestate — the per-fork git-worktree isolation policy hook.
# -----------------------------------------------------------------------------

class TestPrepareForkFilestate:
    def test_worktree_when_source_is_git_repo(self, monkeypatch):
        b = TmuxBridge()
        calls = []

        def fake_run(cmd, **kw):
            calls.append(cmd)
            if "is-inside-work-tree" in cmd:
                return "true"
            return ""                                # `git worktree add` -> ok
        monkeypatch.setattr(b, "_run", fake_run)
        out = b.prepare_fork_filestate("/home/lester/proj", "awl-fork1")
        assert out["isolated"] is True
        assert out["policy"] == "worktree"
        assert out["cwd"] == "/home/lester/proj-fork-awl-fork1"
        assert out["worktree"] == "/home/lester/proj-fork-awl-fork1"
        assert out["branch"] == "fork/awl-fork1"
        # A `git worktree add -b fork/awl-fork1 <path>` command was issued.
        assert any("git worktree add -b" in c and "fork/awl-fork1" in c
                   for c in calls)

    def test_custom_branch_name(self, monkeypatch):
        b = TmuxBridge()
        monkeypatch.setattr(
            b, "_run",
            lambda cmd, **kw: "true" if "is-inside-work-tree" in cmd else "")
        out = b.prepare_fork_filestate("/home/lester/proj", "awl-fork1",
                                       branch="handoff/x")
        assert out["branch"] == "handoff/x"

    def test_falls_back_to_shared_cwd_when_not_a_git_repo(self, monkeypatch):
        # HONEST degrade: not a repo -> shared cwd, isolated False, a note said.
        b = TmuxBridge()
        monkeypatch.setattr(
            b, "_run",
            lambda cmd, **kw: "no" if "is-inside-work-tree" in cmd else "")
        out = b.prepare_fork_filestate("/home/lester/proj", "awl-fork1")
        assert out["isolated"] is False
        assert out["cwd"] == "/home/lester/proj"
        assert out["worktree"] is None
        assert "not a git repo" in out["note"]

    def test_isolate_false_shares_cwd_without_probing(self, monkeypatch):
        b = TmuxBridge()
        calls = []
        monkeypatch.setattr(b, "_run", lambda cmd, **kw: calls.append(cmd) or "")
        out = b.prepare_fork_filestate("/home/lester/proj", "awl-fork1",
                                       isolate=False)
        assert out["isolated"] is False
        assert out["cwd"] == "/home/lester/proj"
        assert calls == []                          # no git probe when not isolating

    def test_worktree_add_failure_degrades_honestly(self, monkeypatch):
        b = TmuxBridge()

        def fake_run(cmd, **kw):
            if "is-inside-work-tree" in cmd:
                return "true"
            if "git worktree add" in cmd:
                raise TmuxBridgeError("fatal: worktree already exists")
            return ""
        monkeypatch.setattr(b, "_run", fake_run)
        out = b.prepare_fork_filestate("/home/lester/proj", "awl-fork1")
        assert out["isolated"] is False
        assert out["cwd"] == "/home/lester/proj"    # shared, not faked-isolated
        assert "worktree add failed" in out["note"]


# -----------------------------------------------------------------------------
# fork() — end-to-end launch-command construction (--fork-session from a source).
# -----------------------------------------------------------------------------

class TestForkConstruction:
    SRC = "6c61e972-624e-47cb-a509-7b6ff708a1db"

    def test_fork_spawns_fork_session_from_registered_source(self, monkeypatch):
        b, captured = _patched_bridge(monkeypatch, "awl-fork9")
        b._session_uuids["src"] = self.SRC          # source is bridge-known
        desc = b.fork("src", "awl-fork9", cwd="/home/lester/proj", model="sonnet",
                      git_author_name="ivy",
                      git_author_email="ivy-5@agents.awl-cc-dash.invalid",
                      resolve_timeout=0)
        cmd = _launch_cmd(captured)
        assert f"--resume {self.SRC}" in cmd
        assert "--fork-session" in cmd
        assert "--session-id" not in cmd
        assert "--model sonnet" in cmd
        assert "GIT_AUTHOR_NAME=ivy" in cmd         # fork's own #19 identity
        assert desc["status"] == "forked"
        assert desc["source"] == "src"
        assert desc["source_session_id"] == self.SRC
        # Not a git repo in this fake -> file-state shares the source cwd.
        assert desc["filestate"]["isolated"] is False
        assert desc["rewound_to"] is None

    def test_fork_refuses_unknown_source(self, monkeypatch):
        b, _ = _patched_bridge(monkeypatch, "awl-fork9")
        with pytest.raises(TmuxBridgeError) as ei:
            b.fork("ghost", "awl-fork9", cwd="/home/lester/proj", resolve_timeout=0)
        assert "unknown" in str(ei.value)

    def test_fork_version_gate_blocks_old_cli(self, monkeypatch):
        # The gate fires at fork() entry, BEFORE any tmux session is spawned.
        b, captured = _patched_bridge(monkeypatch, "awl-fork9",
                                      version_out="2.1.190 (Claude Code)")
        b._session_uuids["src"] = self.SRC
        with pytest.raises(VersionUnsupportedError):
            b.fork("src", "awl-fork9", cwd="/home/lester/proj", resolve_timeout=0)
        assert not any(c.startswith("tmux new-session")
                       for c in captured["commands"])

    def test_fork_rewinds_when_branch_from_n_requested(self, monkeypatch):
        # to_prompt_index -> a rewind-in-fork call for branch-from-N.
        b, _ = _patched_bridge(monkeypatch, "awl-fork9")
        b._session_uuids["src"] = self.SRC
        rewinds = []
        monkeypatch.setattr(
            b, "rewind",
            lambda name, tpi, **kw: rewinds.append((name, tpi, kw)))
        b.fork("src", "awl-fork9", cwd="/home/lester/proj",
               to_prompt_index=2, resolve_timeout=0)
        assert rewinds == [("awl-fork9", 2, {"check_version": False})]


# -----------------------------------------------------------------------------
# rewind() — the /rewind menu keystroke sequence.
# -----------------------------------------------------------------------------

_REWIND_MENU = """\
 Rewind — restore the conversation and/or code to the point before a prompt
 ❯ Restore the code and conversation
   Restore the conversation only
   Restore the code only
   … prompt 1 …
   … prompt 2 …
   (current)
"""

_REWIND_CONFIRM = """\
 Confirm you want to restore
 The conversation will be forked. The code will be unchanged.
 ❯ Restore conversation
   Cancel
"""


class TestRewindSequence:
    def _bridge(self, monkeypatch, screens):
        """A bridge with rewind's I/O faked: idle-gated True, version OK, and
        read() serving the given screens in order. Captures send/keys in order."""
        b = TmuxBridge()
        actions = []
        it = iter(screens)
        last = {"s": screens[-1]}

        def fake_read(name, lines=50):
            try:
                last["s"] = next(it)
            except StopIteration:
                pass
            return {"content": last["s"]}

        monkeypatch.setattr(b, "_run",
                            lambda cmd, **kw: "2.1.198 (Claude Code)")
        monkeypatch.setattr(b, "_require_session", lambda n: None)
        monkeypatch.setattr(b, "_idle_gate", lambda n, **kw: True)
        monkeypatch.setattr(b, "read", fake_read)
        monkeypatch.setattr(b, "send",
                            lambda name, text, press_enter=True:
                            actions.append(("send", text)))
        monkeypatch.setattr(b, "keys",
                            lambda name, *ks: actions.append(("keys", ks)))
        monkeypatch.setattr("bridge.bridge.time.sleep", lambda s: None)
        return b, actions

    def test_sequence_for_one_prompt_back(self, monkeypatch):
        b, actions = self._bridge(monkeypatch, [_REWIND_MENU, _REWIND_CONFIRM])
        out = b.rewind("agent", to_prompt_index=1)
        # /rewind -> Up×1 -> Enter (open confirm) -> Enter (restore) -> Ctrl-U.
        assert actions == [
            ("send", "/rewind"),
            ("keys", ("Up",)),
            ("keys", ("Enter",)),
            ("keys", ("Enter",)),
            ("keys", ("C-u",)),
        ]
        assert out == {"status": "rewound", "name": "agent", "to_prompt_index": 1}

    def test_up_presses_scale_with_prompt_index(self, monkeypatch):
        b, actions = self._bridge(monkeypatch, [_REWIND_MENU, _REWIND_CONFIRM])
        b.rewind("agent", to_prompt_index=3)
        ups = [a for a in actions if a == ("keys", ("Up",))]
        assert len(ups) == 3
        # The three Ups precede the two Enters + the Ctrl-U.
        assert actions[:4] == [
            ("send", "/rewind"),
            ("keys", ("Up",)), ("keys", ("Up",)), ("keys", ("Up",)),
        ]

    def test_zero_or_negative_index_rejected(self, monkeypatch):
        b, _ = self._bridge(monkeypatch, [_REWIND_MENU])
        for bad in (0, -1, None):
            with pytest.raises(TmuxBridgeError):
                b.rewind("agent", to_prompt_index=bad)

    def test_busy_when_not_idle(self, monkeypatch):
        b, _ = self._bridge(monkeypatch, [_REWIND_MENU])
        monkeypatch.setattr(b, "_idle_gate", lambda n, **kw: False)
        with pytest.raises(TmuxBridgeError) as ei:
            b.rewind("agent", to_prompt_index=1)
        assert str(ei.value).startswith("busy")     # -> the endpoint maps to 409

    def test_missing_menu_raises(self, monkeypatch):
        b, _ = self._bridge(monkeypatch, ["nothing rendered here"])
        with pytest.raises(TmuxBridgeError) as ei:
            b.rewind("agent", to_prompt_index=1)
        assert "menu did not render" in str(ei.value)

    def test_missing_confirm_dialog_raises(self, monkeypatch):
        b, _ = self._bridge(monkeypatch, [_REWIND_MENU, "still the menu, no confirm"])
        with pytest.raises(TmuxBridgeError) as ei:
            b.rewind("agent", to_prompt_index=1)
        assert "confirm dialog did not appear" in str(ei.value)

    def test_version_gate_enforced_at_entry(self, monkeypatch):
        b, actions = self._bridge(monkeypatch, [_REWIND_MENU, _REWIND_CONFIRM])
        monkeypatch.setattr(b, "_run",
                            lambda cmd, **kw: "2.1.190 (Claude Code)")
        with pytest.raises(VersionUnsupportedError):
            b.rewind("agent", to_prompt_index=1)
        assert actions == []                         # nothing sent before the gate


# -----------------------------------------------------------------------------
# BridgeDriver.rewind / .fork — the seam translates bridge errors to the
# RuntimeError(reason) the endpoint maps (version_unsupported / busy).
# -----------------------------------------------------------------------------

class _StubBridge:
    """Minimal stand-in for TmuxBridge: rewind/fork raise or return canned."""

    def __init__(self, *, rewind_exc=None, fork_exc=None, result=None):
        self._rewind_exc = rewind_exc
        self._fork_exc = fork_exc
        self._result = result or {"status": "ok"}

    def rewind(self, name, to_prompt_index):
        if self._rewind_exc:
            raise self._rewind_exc
        return {"status": "rewound", "name": name, "to_prompt_index": to_prompt_index}

    def fork(self, src_name, new_name, **kw):
        if self._fork_exc:
            raise self._fork_exc
        return {"status": "forked", "name": new_name, "source": src_name}


def _driver(bridge):
    d = BridgeDriver(DriverConfig(), lambda e: None)
    d._bridge = bridge
    return d


class TestDriverErrorTranslation:
    def test_rewind_success_passes_through(self):
        d = _driver(_StubBridge())
        out = asyncio.run(d.rewind(2))
        assert out == {"status": "rewound", "name": d.tmux_name, "to_prompt_index": 2}

    def test_rewind_version_unsupported_becomes_reason(self):
        d = _driver(_StubBridge(rewind_exc=VersionUnsupportedError("old")))
        with pytest.raises(RuntimeError) as ei:
            asyncio.run(d.rewind(1))
        assert str(ei.value) == "version_unsupported"

    def test_rewind_busy_becomes_reason(self):
        d = _driver(_StubBridge(rewind_exc=TmuxBridgeError("busy — not idle")))
        with pytest.raises(RuntimeError) as ei:
            asyncio.run(d.rewind(1))
        assert str(ei.value) == "busy"

    def test_fork_version_unsupported_becomes_reason(self):
        d = _driver(_StubBridge(fork_exc=VersionUnsupportedError("old")))
        with pytest.raises(RuntimeError) as ei:
            asyncio.run(d.fork("awl-x"))
        assert str(ei.value) == "version_unsupported"

    def test_fork_busy_becomes_reason(self):
        d = _driver(_StubBridge(fork_exc=TmuxBridgeError("busy — not idle")))
        with pytest.raises(RuntimeError) as ei:
            asyncio.run(d.fork("awl-x"))
        assert str(ei.value) == "busy"

    def test_fork_forwards_new_name_and_args(self):
        captured = {}

        class _Cap(_StubBridge):
            def fork(self, src_name, new_name, **kw):
                captured.update(src=src_name, new=new_name, **kw)
                return {"status": "forked", "name": new_name}
        d = _driver(_Cap())
        asyncio.run(d.fork("awl-new", cwd="/p", model="opus", to_prompt_index=2,
                           isolate=False, git_author_name="ivy",
                           git_author_email="ivy-5@agents.awl-cc-dash.invalid"))
        assert captured["new"] == "awl-new"
        assert captured["cwd"] == "/p" and captured["model"] == "opus"
        assert captured["to_prompt_index"] == 2 and captured["isolate"] is False
        assert captured["git_author_name"] == "ivy"

    def test_capabilities_advertised(self):
        assert {"rewind", "fork"} <= BridgeDriver.CAPABILITIES


# -----------------------------------------------------------------------------
# Endpoints — honest error mapping (404 / 400 no-cap / 400 version / 409 busy)
# + the fork success path (adoption stubbed).
# Async endpoints called directly via asyncio.run, as in test_sidecar_unit.py.
# -----------------------------------------------------------------------------

import main  # noqa: E402
from main import SessionState  # noqa: E402
from fastapi import HTTPException  # noqa: E402


def _session():
    return SessionState(
        session_id="s1", agent_type=None, model="sonnet",
        permission_mode="acceptEdits", cwd="/home/lester/proj",
        system_prompt=None, driver_name="bridge",
    )


class _RewindForkDriver:
    """Fake bridge-like driver exposing the rewind/fork capabilities. Returns
    canned descriptors or raises RuntimeError(reason) like the real driver."""

    name = "bridge"

    def __init__(self, *, error=None):
        self._error = error
        self.calls = []

    def supports(self, cap):
        return cap in {"rewind", "fork"}

    async def rewind(self, to_prompt_index):
        self.calls.append(("rewind", to_prompt_index))
        if self._error:
            raise RuntimeError(self._error)
        return {"status": "rewound", "name": "s1", "to_prompt_index": to_prompt_index}

    async def fork(self, new_name, **kw):
        self.calls.append(("fork", new_name, kw))
        if self._error:
            raise RuntimeError(self._error)
        return {
            "status": "forked", "name": new_name, "source": "s1",
            "source_session_id": "src-claude-id", "session_id": "fork-claude-id",
            "cwd": kw.get("cwd") or "/home/lester/proj",
            "filestate": {"isolated": False, "policy": "worktree"},
            "rewound_to": kw.get("to_prompt_index"),
        }


class _NoCapDriver:
    name = "sdk"

    def supports(self, cap):
        return False


class TestRewindForkEndpoints:
    def setup_method(self):
        self._ord = main._identity_ordinal

    def teardown_method(self):
        main.sessions.pop("s1", None)
        main._identity_ordinal = self._ord

    def _register(self, driver):
        s = _session()
        s.driver = driver
        main.sessions["s1"] = s
        return s

    # --- rewind ---

    def test_rewind_ok_returns_read_back(self):
        s = self._register(_RewindForkDriver())
        out = asyncio.run(main.rewind_session("s1", main.RewindRequest(to_prompt_index=2)))
        assert out["status"] == "ok" and out["to_prompt_index"] == 2
        assert s.driver.calls == [("rewind", 2)]

    def test_rewind_default_index_is_one(self):
        self._register(_RewindForkDriver())
        out = asyncio.run(main.rewind_session("s1", main.RewindRequest()))
        assert out["to_prompt_index"] == 1

    def test_rewind_unknown_session_404(self):
        with pytest.raises(HTTPException) as ei:
            asyncio.run(main.rewind_session("ghost", main.RewindRequest()))
        assert ei.value.status_code == 404

    def test_rewind_no_capability_400(self):
        self._register(_NoCapDriver())
        with pytest.raises(HTTPException) as ei:
            asyncio.run(main.rewind_session("s1", main.RewindRequest()))
        assert ei.value.status_code == 400
        assert "no rewind support" in ei.value.detail

    def test_rewind_version_unsupported_400(self):
        self._register(_RewindForkDriver(error="version_unsupported"))
        with pytest.raises(HTTPException) as ei:
            asyncio.run(main.rewind_session("s1", main.RewindRequest()))
        assert ei.value.status_code == 400
        assert "2.1.191" in ei.value.detail

    def test_rewind_busy_409(self):
        self._register(_RewindForkDriver(error="busy"))
        with pytest.raises(HTTPException) as ei:
            asyncio.run(main.rewind_session("s1", main.RewindRequest()))
        assert ei.value.status_code == 409
        assert "busy" in ei.value.detail

    # --- fork ---

    def test_fork_unknown_session_404(self):
        with pytest.raises(HTTPException) as ei:
            asyncio.run(main.fork_session("ghost", main.ForkRequest()))
        assert ei.value.status_code == 404

    def test_fork_no_capability_400(self):
        self._register(_NoCapDriver())
        with pytest.raises(HTTPException) as ei:
            asyncio.run(main.fork_session("s1", main.ForkRequest()))
        assert ei.value.status_code == 400
        assert "no fork support" in ei.value.detail

    def test_fork_version_unsupported_400(self):
        self._register(_RewindForkDriver(error="version_unsupported"))
        with pytest.raises(HTTPException) as ei:
            asyncio.run(main.fork_session("s1", main.ForkRequest()))
        assert ei.value.status_code == 400
        assert "2.1.191" in ei.value.detail

    def test_fork_busy_409(self):
        self._register(_RewindForkDriver(error="busy"))
        with pytest.raises(HTTPException) as ei:
            asyncio.run(main.fork_session("s1", main.ForkRequest(to_prompt_index=2)))
        assert ei.value.status_code == 409

    def test_fork_success_adopts_and_returns_lineage(self, monkeypatch):
        s = self._register(_RewindForkDriver())

        # Stub the live adoption (spawns/wires a real SessionState) — the fork
        # SPAWN + error mapping is what this endpoint owns; adoption is
        # reconnect-style wiring proven elsewhere.
        class _Forked:
            def to_dict(self):
                return {"session_id": "fk", "identity": {"number": 7},
                        "status": "idle"}

        async def _stub_adopt(descriptor, *, source, identity, model, permission_mode):
            _stub_adopt.seen = {"descriptor": descriptor, "identity": identity,
                                "model": model, "permission_mode": permission_mode}
            return _Forked()
        monkeypatch.setattr(main, "_adopt_forked_session", _stub_adopt)

        out = asyncio.run(main.fork_session(
            "s1", main.ForkRequest(to_prompt_index=2, model="opus")))
        # The new agent's dict, enriched with fork lineage + file-state.
        assert out["session_id"] == "fk"
        assert out["forked_from"] == "s1"
        assert out["forked_from_session_id"] == "src-claude-id"
        assert out["rewound_to"] == 2
        assert out["filestate"] == {"isolated": False, "policy": "worktree"}
        # The fork got its OWN identity (a distinct agent) + model override, and
        # the source's permission_mode is carried onto the fork.
        assert _stub_adopt.seen["model"] == "opus"
        assert _stub_adopt.seen["permission_mode"] == "acceptEdits"
        assert isinstance(_stub_adopt.seen["identity"], dict)
        # The driver.fork got the fork's own #19 git identity forwarded.
        fork_call = [c for c in s.driver.calls if c[0] == "fork"][0]
        assert "git_author_name" in fork_call[2]
        assert fork_call[2]["git_author_email"].endswith(
            "@agents.awl-cc-dash.invalid")


# -----------------------------------------------------------------------------
# Fork claude-session-id adoption (§7.19 / #50 residual) — a --fork-session
# launch mints a NEW id unknown at spawn, and the fork-time discovery is
# best-effort; when it missed, the driver must adopt the id from the resolved
# transcript filename (`<uuid>.jsonl`) and persist it EXACTLY like a normal
# create, so a fork is cold-restorable and a retired fork's archive row stays
# resumable (fork→retire→resume must not be a dead end).
# -----------------------------------------------------------------------------

import sidecar.drivers.bridge as _db  # noqa: E402

FORK_UUID = "3f2b8c1d-9a4e-4f6b-8c2d-1e5f7a9b0c3d"


class _RegisterCapture:
    def __init__(self):
        self.registered = []

    def register_session_id(self, name, sid):
        self.registered.append((name, sid))


class TestForkClaudeIdAdoption:
    def _driver(self, monkeypatch, *, claude_id=None, transcript_stem=FORK_UUID):
        d = BridgeDriver(DriverConfig(), lambda e: None,
                         session_id="fk1",
                         claude_session_id=claude_id,
                         persisted_record={"session_id": "fk1"})
        d._bridge = _RegisterCapture()
        saved = []
        monkeypatch.setattr(_db, "_save_record",
                            lambda rec: saved.append(dict(rec)))
        monkeypatch.setattr(
            "bridge.transcript.find_transcript",
            lambda bridge, name: f"/home/u/.claude/projects/enc/{transcript_stem}.jsonl")
        return d, saved

    def test_idless_driver_adopts_uuid_stem_and_persists(self, monkeypatch):
        d, saved = self._driver(monkeypatch)
        d._resolve_and_persist_transcript_path()
        assert d._claude_session_id == FORK_UUID
        assert d._bridge.registered == [(d.tmux_name, FORK_UUID)]
        assert saved and saved[-1]["claude_session_id"] == FORK_UUID
        assert saved[-1]["transcript_path"].endswith(f"{FORK_UUID}.jsonl")

    def test_known_id_never_overwritten(self, monkeypatch):
        # A normally-created agent already carries its id — adoption is only
        # for the id-less (fork-discovery-missed) case.
        d, saved = self._driver(monkeypatch, claude_id="existing-id")
        d._resolve_and_persist_transcript_path()
        assert d._claude_session_id == "existing-id"
        assert d._bridge.registered == []

    def test_non_uuid_stem_is_not_adopted(self, monkeypatch):
        # A weird filename must never be trusted as a conversation id.
        d, saved = self._driver(monkeypatch, transcript_stem="not-a-uuid")
        d._resolve_and_persist_transcript_path()
        assert d._claude_session_id is None
        assert d._bridge.registered == []
        # The verified path still persists (the pre-existing behavior).
        assert saved and saved[-1]["transcript_path"].endswith("not-a-uuid.jsonl")
        assert not saved[-1].get("claude_session_id")


# -----------------------------------------------------------------------------
# The adoption OWNERSHIP guard (integrator fix on the batch above): the id-less
# fallback resolution is newest-.jsonl-in-project-dir, which in a SHARED-cwd
# fork (isolate=False / the honest non-git fallback) is typically the SOURCE's
# actively-written transcript. Adopting that stem would permanently pin the
# fork's reads — and a later cold restore's `claude --resume` — to the WRONG
# conversation, so a stem naming another agent's id is never adopted, pinned,
# or persisted; the read simply retries next poll.
# -----------------------------------------------------------------------------

SOURCE_UUID = "aaaaaaaa-1111-4222-8333-bbbbbbbbcccc"


class TestForkAdoptionOwnershipGuard:
    def _driver(self, monkeypatch, *, persisted_record, roster=()):
        import runtime_store
        d = BridgeDriver(DriverConfig(), lambda e: None,
                         session_id="fk1",
                         persisted_record=persisted_record)
        d._bridge = _RegisterCapture()
        saved = []
        monkeypatch.setattr(_db, "_save_record",
                            lambda rec: saved.append(dict(rec)))
        monkeypatch.setattr(runtime_store, "all_records",
                            lambda: [dict(r) for r in roster])
        monkeypatch.setattr(
            "bridge.transcript.find_transcript",
            lambda bridge, name:
                f"/home/u/.claude/projects/enc/{SOURCE_UUID}.jsonl")
        return d, saved

    def test_lineage_source_id_is_never_adopted(self, monkeypatch):
        # The resolved stem IS the fork source's conversation id (known from
        # the lineage seeded at fork adoption) — refuse, pin nothing.
        rec = {"session_id": "fk1",
               "lineage": {"parent": "src", "handoff": None,
                           "fork": {"source_session_id": "src",
                                    "source_claude_session_id": SOURCE_UUID,
                                    "rewound_to": None}}}
        d, saved = self._driver(monkeypatch, persisted_record=rec)
        d._resolve_and_persist_transcript_path()
        assert d._claude_session_id is None
        assert d._bridge.registered == []
        assert d._transcript_path is None      # next poll re-resolves
        assert saved == []                     # nothing persisted

    def test_sibling_roster_id_is_never_adopted(self, monkeypatch):
        # The stem names a co-located sibling's persisted conversation id.
        d, saved = self._driver(
            monkeypatch, persisted_record={"session_id": "fk1"},
            roster=[{"session_id": "other", "claude_session_id": SOURCE_UUID}])
        d._resolve_and_persist_transcript_path()
        assert d._claude_session_id is None
        assert d._bridge.registered == []
        assert d._transcript_path is None
        assert saved == []

    def test_own_stale_record_does_not_block_adoption(self, monkeypatch):
        # A record keyed by THIS driver's own session id never counts as
        # foreign — only OTHER agents' ids block.
        d, saved = self._driver(
            monkeypatch, persisted_record={"session_id": "fk1"},
            roster=[{"session_id": "fk1", "claude_session_id": SOURCE_UUID}])
        d._resolve_and_persist_transcript_path()
        assert d._claude_session_id == SOURCE_UUID
        assert d._bridge.registered == [(d.tmux_name, SOURCE_UUID)]
        assert saved and saved[-1]["claude_session_id"] == SOURCE_UUID
