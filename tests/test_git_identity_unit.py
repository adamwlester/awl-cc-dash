"""Hermetic unit tests for per-agent git identity + the AI-touched index (§11 #19).

Decided contract (ARCHITECTURE §7.5, §11 #19; build plan
``dev/notes/2026-07-15-stage5-build-plan.md`` Open-decisions 3 & 4):

Every dashboard agent commits under its OWN git author name + a synthetic
per-agent email on a FIXED, guaranteed-non-deliverable domain, so "what did AI
touch" is a pure git query with no maintained ledger::

    git log --author='@agents.awl-cc-dash.invalid'

The mechanism is **per-launch environment injection**, NOT repo-local
``git config``: agents in one repo share one ``.git/config``, so repo-local
``user.*`` would collide/race across the fleet, while env vars are per-process
and inherited by any ``git`` the agent runs.

What this file pins (all pure Python — no WSL/tmux/network):
  * ``identity.git_author`` — name→(author_name, synthetic_email) derivation,
    the ``<slug>-<number>@agents.awl-cc-dash.invalid`` email format, safe
    slugification (lowercase, non-alnum→hyphen, collapse repeats), and the
    unnamed ``role-number`` fallback.
  * ``identity.git_env`` — the four GIT_* vars (author AND committer set to the
    same per-agent identity).
  * ``TmuxBridge.create()`` — the GIT_* env prefix appears on the launched tmux
    command when (and only when) a git author name + email are passed. The
    launch side effects are scripted-fake captured, never executed (the live
    counterpart is ``tests/test_git_identity_live.py``).
  * ``BridgeDriver._create_session()`` — derives the git identity from
    ``config.identity`` and forwards it to ``create()`` for every agent.
"""

from bridge.bridge import TmuxBridge
from sidecar.identity import (
    AGENT_EMAIL_DOMAIN,
    git_author,
    git_env,
)
from sidecar.drivers.bridge import BridgeDriver
from sidecar.drivers.base import DriverConfig


# -----------------------------------------------------------------------------
# identity.git_author — (author_name, synthetic_email) derivation
# -----------------------------------------------------------------------------

class TestGitAuthor:
    def test_named_agent_uses_name_and_slugged_email(self):
        author, email = git_author({"role": "Agent", "number": 3, "name": "zippy"})
        assert author == "zippy"
        assert email == "zippy-3@agents.awl-cc-dash.invalid"

    def test_unnamed_agent_falls_back_to_role_number(self):
        # No name -> the author name is "<role>-<number>" and the email slug is
        # the role, so an unnamed agent still lands on the AI-touched domain.
        author, email = git_author({"role": "Agent", "number": 3, "name": ""})
        assert author == "Agent-3"
        assert email == "agent-3@agents.awl-cc-dash.invalid"

    def test_unnamed_custom_role(self):
        author, email = git_author({"role": "researcher", "number": 2, "name": ""})
        assert author == "researcher-2"
        assert email == "researcher-2@agents.awl-cc-dash.invalid"

    def test_email_domain_is_the_fixed_invalid_tld(self):
        # The AI-touched query keys off this EXACT suffix — pin it so a drift
        # can't silently break `git log --author='@agents.awl-cc-dash.invalid'`.
        assert AGENT_EMAIL_DOMAIN == "agents.awl-cc-dash.invalid"
        for ident in ({"name": "x", "number": 1},
                      {"name": "", "role": "Agent", "number": 9},
                      None, {}):
            _author, email = git_author(ident)
            assert email.endswith("@agents.awl-cc-dash.invalid")

    def test_slugify_lowercases_and_collapses_non_alnum(self):
        # Spaces / punctuation / mixed case -> a single-hyphen, lowercase slug;
        # the AUTHOR name keeps the human form (git allows spaces there).
        author, email = git_author({"name": "Nova  Prime!!", "number": 5})
        assert author == "Nova  Prime!!"
        assert email == "nova-prime-5@agents.awl-cc-dash.invalid"

    def test_slugify_trims_leading_trailing_separators(self):
        _author, email = git_author({"name": "__Ada__", "number": 7})
        assert email == "ada-7@agents.awl-cc-dash.invalid"

    def test_all_punctuation_name_slugs_to_fallback(self):
        # A name that slugs to nothing still yields a valid local-part.
        _author, email = git_author({"name": "!!!", "number": 4})
        assert email == "agent-4@agents.awl-cc-dash.invalid"

    def test_none_and_empty_identity_are_safe(self):
        # Defensive: a missing identity / missing number never raises and always
        # produces a valid author + email (no "None" leaking into the local-part).
        for ident in (None, {}):
            author, email = git_author(ident)
            assert author == "Agent"
            assert email == "agent@agents.awl-cc-dash.invalid"

    def test_realistic_pool_name(self):
        # The shipped pool is lowercase 3-5 letter names already git-safe; a
        # pool name slugs to itself.
        author, email = git_author({"name": "ivy", "number": 12})
        assert author == "ivy"
        assert email == "ivy-12@agents.awl-cc-dash.invalid"


# -----------------------------------------------------------------------------
# identity.git_env — the four GIT_* vars (author AND committer)
# -----------------------------------------------------------------------------

class TestGitEnv:
    def test_all_four_vars_present_author_equals_committer(self):
        env = git_env({"name": "zippy", "number": 3})
        assert env == {
            "GIT_AUTHOR_NAME": "zippy",
            "GIT_AUTHOR_EMAIL": "zippy-3@agents.awl-cc-dash.invalid",
            "GIT_COMMITTER_NAME": "zippy",
            "GIT_COMMITTER_EMAIL": "zippy-3@agents.awl-cc-dash.invalid",
        }

    def test_matches_git_author(self):
        # git_env is exactly git_author fanned into the four vars.
        author, email = git_author({"role": "researcher", "number": 2, "name": ""})
        env = git_env({"role": "researcher", "number": 2, "name": ""})
        assert env["GIT_AUTHOR_NAME"] == env["GIT_COMMITTER_NAME"] == author
        assert env["GIT_AUTHOR_EMAIL"] == env["GIT_COMMITTER_EMAIL"] == email


# -----------------------------------------------------------------------------
# TmuxBridge.create() — the GIT_* env prefix on the launched tmux command.
# Hermetic: _run / _list_raw / _clear_startup_gates are scripted-fake captured,
# never executed (no WSL/tmux touched). Mirrors TestCreateResumeLaunch.
# -----------------------------------------------------------------------------

class TestCreateGitEnvPrefix:
    def _patched_bridge(self, monkeypatch, name):
        """A TmuxBridge whose launch side effects are captured, not run."""
        b = TmuxBridge()
        captured = {"commands": []}

        def fake_run(cmd, timeout=30, stdin_data=None):
            captured["commands"].append(cmd)
            return ""

        state = {"listed": 0}

        def fake_list_raw():
            # First call = create()'s duplicate check (no sessions yet); later
            # calls = the post-launch verification (session now exists).
            state["listed"] += 1
            return {} if state["listed"] == 1 else {name: {"pid": "42"}}

        monkeypatch.setattr(b, "_run", fake_run)
        monkeypatch.setattr(b, "_list_raw", fake_list_raw)
        monkeypatch.setattr(b, "_clear_startup_gates", lambda n, **kw: None)
        monkeypatch.setattr("bridge.bridge.time.sleep", lambda s: None)
        return b, captured

    def _launch_cmd(self, captured):
        cmds = [c for c in captured["commands"] if c.startswith("tmux new-session")]
        assert len(cmds) == 1, f"expected one tmux new-session, got: {cmds}"
        return cmds[0]

    def test_git_env_prefix_present_when_author_given(self, monkeypatch):
        from bridge.paths import CLAUDE_BIN
        b, captured = self._patched_bridge(monkeypatch, "gid")
        b.create("gid", cwd="/tmp/x",
                 git_author_name="zippy",
                 git_author_email="zippy-3@agents.awl-cc-dash.invalid")
        cmd = self._launch_cmd(captured)
        # All four vars ride the launch command (author == committer)...
        assert "GIT_AUTHOR_NAME=zippy" in cmd
        assert "GIT_AUTHOR_EMAIL=zippy-3@agents.awl-cc-dash.invalid" in cmd
        assert "GIT_COMMITTER_NAME=zippy" in cmd
        assert "GIT_COMMITTER_EMAIL=zippy-3@agents.awl-cc-dash.invalid" in cmd
        # ...and they sit BEFORE the claude binary (a leading env-assignment
        # prefix, which the `sh -c` tmux runs the command under honors).
        assert cmd.index("GIT_AUTHOR_NAME=") < cmd.index(CLAUDE_BIN)

    def test_no_git_prefix_when_author_omitted(self, monkeypatch):
        b, captured = self._patched_bridge(monkeypatch, "plain")
        b.create("plain", cwd="/tmp/x")
        cmd = self._launch_cmd(captured)
        assert "GIT_AUTHOR_NAME" not in cmd
        assert "GIT_COMMITTER_NAME" not in cmd

    def test_partial_git_args_is_a_noop(self, monkeypatch):
        # Both name AND email are required; passing only one injects nothing.
        b, captured = self._patched_bridge(monkeypatch, "half")
        b.create("half", cwd="/tmp/x", git_author_name="zippy")
        cmd = self._launch_cmd(captured)
        assert "GIT_AUTHOR_NAME" not in cmd


# -----------------------------------------------------------------------------
# BridgeDriver._create_session() — derives git identity from config.identity and
# forwards it to create() for EVERY agent (named or not).
# Hermetic: the TmuxBridge.create call is monkeypatch-captured, never executed.
# -----------------------------------------------------------------------------

def _driver(**cfg):
    return BridgeDriver(DriverConfig(**cfg), lambda e: None)


class TestCreateSessionForwardsGitIdentity:
    def _capture_create(self, d, monkeypatch):
        seen = {}

        def fake_create(name, **kw):
            seen["name"] = name
            seen.update(kw)
            return {"session_id": "deadbeef"}

        monkeypatch.setattr(d._bridge, "create", fake_create)
        return seen

    def test_named_agent_forwards_derived_identity(self, monkeypatch):
        d = _driver(identity={"role": "Agent", "number": 3, "name": "zippy",
                              "color": "#008149", "icon": "fox-head"})
        seen = self._capture_create(d, monkeypatch)
        d._create_session()
        assert seen["git_author_name"] == "zippy"
        assert seen["git_author_email"] == "zippy-3@agents.awl-cc-dash.invalid"

    def test_unnamed_agent_still_gets_attribution(self, monkeypatch):
        # An agent with no name still commits on the AI-touched domain.
        d = _driver(identity={"role": "researcher", "number": 2, "name": ""})
        seen = self._capture_create(d, monkeypatch)
        d._create_session()
        assert seen["git_author_name"] == "researcher-2"
        assert seen["git_author_email"] == "researcher-2@agents.awl-cc-dash.invalid"

    def test_missing_identity_forwards_safe_default(self, monkeypatch):
        d = _driver()  # identity=None
        seen = self._capture_create(d, monkeypatch)
        d._create_session()
        assert seen["git_author_name"] == "Agent"
        assert seen["git_author_email"] == "agent@agents.awl-cc-dash.invalid"
