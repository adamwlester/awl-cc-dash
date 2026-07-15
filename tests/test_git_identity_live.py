"""Live acceptance STUB for per-agent git identity (§11 #19) — WSL2 + tmux.

Decided contract (ARCHITECTURE §7.5, §11 #19): when the bridge launches an
agent, the GIT_* env it injects (see ``sidecar/identity.py`` ``git_author`` /
``git_env`` and ``TmuxBridge.create``) must make the agent's REAL commits carry
its own identity, so that::

    git log --author='@agents.awl-cc-dash.invalid'

is exactly "what did AI touch". The hermetic tier
(``tests/test_git_identity_unit.py``) proves the derivation + that the env
prefix reaches the launched command; only a live drive proves an agent's
commit actually lands under the synthetic author. This is that live proof — a
STUB (per the build task): marked ``integration``+``slow`` so the hermetic run
deselects it, and skipped by default until it is fleshed out against a real WSL
git repo, so it never false-fails on a machine without WSL.

Intended procedure (own, tab-less TmuxBridge; unique session name; never
``tmux kill-server``; ``show=False`` — the live-test isolation rules in
``tests/README.md``):

  1. Create a throwaway git repo in WSL (``git init`` in a temp dir; do NOT set
     repo-local ``user.name``/``user.email`` — the point is the env carries it).
  2. ``bridge.create(<uniq>, cwd=<repo>, permission_mode="bypassPermissions",
     git_author_name=<name>, git_author_email=<slug>-<n>@agents.awl-cc-dash.invalid,
     show=False)`` — or launch via a BridgeDriver with an identity so
     ``_create_session`` derives the env.
  3. ``bridge.send(...)`` a prompt telling the agent to write a file and run
     ``git add -A && git commit -m 'ai touch'``; ``wait_idle``.
  4. Read the commit back in that repo (``git log -1 --format='%an|%ae'`` via
     ``bridge._run``) and assert the author name == the agent's name and the
     email endswith ``@agents.awl-cc-dash.invalid`` (i.e. the AI-touched query
     would catch it).
  5. Close only this session (``bridge.close(<uniq>)``).

Writes ``tests/log/git_identity_findings_latest.txt`` with the read-back
author/email when implemented.
"""

import pytest

pytestmark = [pytest.mark.integration, pytest.mark.slow]


def test_agent_commit_carries_synthetic_identity_live():
    """STUB — implement the WSL git-repo drive above; do not block Stage 5 on it."""
    pytest.skip(
        "live acceptance stub for §11 #19 — run/implement manually against a "
        "real WSL git repo (see module docstring); the hermetic contract is in "
        "tests/test_git_identity_unit.py"
    )
