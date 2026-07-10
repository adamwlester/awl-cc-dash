"""Identity name-registration live proof (§7.5 / §11 #14) — launch with a
display name, rename the LIVE session, and confirm the agent still responds.

THE DECIDED CONTRACT (ARCHITECTURE §7.5): the dashboard identity **name**
doubles as the Claude Code session's own display name — set at launch via the
``claude --name`` flag (verified present on CC 2.1.202: ``-n, --name <name>
Set a display name for this session``) and kept in sync on edit via the
``/rename <name>`` slash command — so it surfaces in the VS Code extension's
session list and the ``--resume`` picker, not only inside the dashboard. This
test proves the mechanism live:

  1. ``create(..., display_name=<launch-name>)`` — the ``--name`` launch lands:
     the session reaches idle and answers a turn (the flag didn't break launch);
  2. ``send("/rename <new-name>")`` — the rename of the live session (the
     fully-typed form, like ``/model <name>``): the screen returns idle and a
     follow-up interrogation turn still answers (the session survived the edit);
  3. **best-effort read-back**: the ``--resume`` picker itself is not
     scriptable, but ``~/.claude/sessions/<pid>.json`` records each live
     session's ``name`` (+ ``nameSource``) keyed by ``sessionId`` — when that
     record exists, assert the registered name (launch) and the edited name
     (post-rename); when the build doesn't write it, record the fact in the
     findings file rather than failing.

The name↔record verdict is written to
``tests/log/identity_rename_findings_latest.txt`` on every run.

============================================================================
ISOLATION RULES (parallel-safe — sibling agents may be running their OWN live
bridge sessions at the same time; violating any of these can kill their work):
  * ONE test file, its OWN ``TmuxBridge()`` (never conftest's shared ``bridge``
    fixture — that fixture's setup/teardown call ``tmux kill-server``, which
    would kill every sibling agent's sessions). We NEVER call kill-server.
  * Every tmux session is uniquely named (``idrename-<uuid8>``) — never a
    fixed/shared name; we close only our own.
  * We operate only inside our own throwaway WSL cwd and its matching
    ``~/.claude/projects/<escaped-cwd>/`` dir (both removed in teardown).
  * Sessions stay TAB-LESS: ``show=False`` everywhere; ``show()`` never used.

Run (from repo root, ONLY this file — not the whole live tier)::

    .\\.venv\\Scripts\\python.exe -m pytest tests\\test_identity_rename_live.py -x -q
"""
from __future__ import annotations

import datetime
import json
import logging
import shlex
import sys
import time
import uuid
from pathlib import Path

import pytest

# Repo root on sys.path so `from bridge import ...` resolves (mirrors the spikes).
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from bridge import TmuxBridge  # noqa: E402

log = logging.getLogger(__name__)

pytestmark = [pytest.mark.integration, pytest.mark.slow]

LOG_DIR = Path(__file__).parent / "log"


@pytest.fixture
def idrename_bridge():
    """Our OWN TmuxBridge — deliberately NOT conftest's shared ``bridge`` fixture,
    whose kill-server setup/teardown would nuke sibling agents' sessions.
    Construction has no side effects; the test tears down only its own
    uniquely-named session."""
    return TmuxBridge()


# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #

def _project_dir(diag: str) -> str:
    """The ``~/.claude/projects/<escaped-cwd>/`` dir Claude uses for ``diag``'s
    transcripts (cwd path with '/' -> '-')."""
    return "~/.claude/projects/-home-lester" + diag[len("/home/lester"):].replace("/", "-")


def _session_record(bridge, claude_sid: str) -> dict | None:
    """Best-effort: the ``~/.claude/sessions/<pid>.json`` record whose
    ``sessionId`` is ours — the local file that exposes the session's registered
    display ``name`` (the ``--resume`` picker's data; the picker itself is not
    scriptable). None when the build didn't write one."""
    try:
        out = bridge._run(
            f"grep -l {shlex.quote(claude_sid)} ~/.claude/sessions/*.json "
            "2>/dev/null | head -n 1"
        ).strip()
        if not out:
            return None
        return json.loads(bridge._run(f"cat {shlex.quote(out)}"))
    except Exception as e:  # noqa: BLE001 — read-back is best-effort
        log.debug("identity-rename: session record read failed: %s", e)
        return None


def _last_assistant_text(bridge, name: str) -> str:
    entries = bridge.read_log(name, types=["assistant"])
    if not entries:
        return ""
    return str((entries[-1].get("message") or {}).get("content"))


def _write_findings(facts: dict) -> None:
    """Durable plain-text findings record (same convention as the other spikes:
    a timestamped file + a ``_latest`` copy in tests/log/)."""
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    lines = [
        f"Identity rename live findings — {stamp}",
        "Question: does `claude --name <name>` register a display name at launch,",
        "does `/rename <name>` over send() rename the LIVE session, and does any",
        "local file expose the registered name for read-back?",
        "",
    ]
    lines += [f"{k}: {v}" for k, v in facts.items()]
    lines += [
        "",
        "Contract consequence (§7.5 / #14): the bridge driver passes",
        "config.identity['name'] as create(display_name=...); the identity",
        "endpoint drives driver.set_display_name -> /rename on a name edit.",
    ]
    text = "\n".join(lines) + "\n"
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    (LOG_DIR / f"identity_rename_findings_{stamp}.txt").write_text(text, encoding="utf-8")
    (LOG_DIR / "identity_rename_findings_latest.txt").write_text(text, encoding="utf-8")
    log.debug("identity-rename findings:\n%s", text)


# --------------------------------------------------------------------------- #
# the launch-name + live-rename proof
# --------------------------------------------------------------------------- #

def test_launch_name_and_live_rename(idrename_bridge):
    """§7.5 end to end: launch tab-less with ``display_name``, rename the live
    session via ``/rename``, and prove the agent still responds — with a
    best-effort read-back of the registered name from the local session record."""
    bridge = idrename_bridge
    tag = uuid.uuid4().hex[:8]
    name = f"idrename-{tag}"
    diag = f"/home/lester/awl-idrename-{tag}"
    proj = _project_dir(diag)
    launch_name = f"ivy-{tag}"
    new_name = f"rex-{tag}"
    facts: dict = {"cwd": diag, "launch_name": launch_name, "new_name": new_name}

    bridge._run(f"mkdir -p {shlex.quote(diag)}")
    try:
        # -- 1. Launch with a display name; the session must still come up. ----
        info = bridge.create(name, cwd=diag, model="sonnet", show=False,
                             display_name=launch_name)
        sid = info["session_id"]
        facts["claude_session_id"] = sid
        facts["launched_with_name_flag"] = True
        # create() already waited for the genuine idle prompt (startup gates).
        bridge.send(name, "Reply with exactly: LAUNCH_OK")
        bridge.wait_idle(name, timeout=180)
        time.sleep(2)
        assert "LAUNCH_OK" in _last_assistant_text(bridge, name), (
            "--name launch produced a session that does not answer turns"
        )
        facts["answers_after_name_launch"] = True

        # Best-effort read-back A: the local session record's registered name.
        rec = _session_record(bridge, sid)
        if rec is not None:
            facts["session_record_after_launch"] = {
                "name": rec.get("name"), "nameSource": rec.get("nameSource")}
            assert rec.get("name") == launch_name, (
                f"session record name {rec.get('name')!r} != --name value "
                f"{launch_name!r}"
            )
            facts["launch_name_registered"] = True
        else:
            facts["session_record_after_launch"] = (
                "absent — this build wrote no ~/.claude/sessions/<pid>.json; "
                "read-back skipped (best-effort)")

        # -- 2. Rename the LIVE session (the identity-edit path). -------------
        bridge.send(name, f"/rename {new_name}")
        time.sleep(3)
        # The fully-typed form must not strand the session in a sub-prompt:
        # the screen returns to a genuine idle.
        bridge.wait_idle(name, timeout=60)
        facts["idle_after_rename"] = True

        # -- 3. The session still responds after the rename. -------------------
        bridge.send(name, "Reply with exactly: RENAME_OK")
        bridge.wait_idle(name, timeout=180)
        time.sleep(2)
        reply = _last_assistant_text(bridge, name)
        log.debug("identity-rename: post-rename reply=%r", reply)
        assert "RENAME_OK" in reply, (
            f"session stopped answering after /rename — reply: {reply!r}"
        )
        facts["answers_after_rename"] = True

        # Best-effort read-back B: the record now carries the EDITED name.
        rec2 = _session_record(bridge, sid)
        if rec2 is not None:
            facts["session_record_after_rename"] = {
                "name": rec2.get("name"), "nameSource": rec2.get("nameSource")}
            assert rec2.get("name") == new_name, (
                f"session record name {rec2.get('name')!r} did not follow "
                f"/rename to {new_name!r}"
            )
            facts["rename_registered"] = True
        else:
            facts["session_record_after_rename"] = "absent — read-back skipped"
    finally:
        _write_findings(facts)
        try:
            bridge.close(name)
        except Exception as e:  # noqa: BLE001 — teardown is best-effort
            log.debug("identity-rename: close(%s) raised (non-fatal): %s", name, e)
        bridge._run(f"rm -rf {shlex.quote(diag)}")
        bridge._run(f"rm -rf {proj}")
