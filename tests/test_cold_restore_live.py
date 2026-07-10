"""Cold-restore live proof (§9.9 / §11.2 #8, bridge half) — relaunch a DEAD agent
resuming its prior conversation.

THE DECIDED CONTRACT (ARCHITECTURE §9.9, "Cold"): when the dashboard reopens
after a reboot/WSL shutdown (tmux gone, transcript persisted), the agent is
relaunched with ``claude --resume <claude_session_id>`` in its cwd — the SAME
conversation, rebuilt from the transcript — instead of being pruned/forgotten.
The bridge half of that is ``TmuxBridge.create(..., resume_session_id=<id>)``
(claude argv gets ``--resume <id>`` and NO ``--session-id``) and ``resume()``'s
dead-session fall-through to it. This test proves the mechanism live:

  1. create a tab-less session in a throwaway WSL cwd, plant a distinctive
     marker turn, and confirm it landed in the ``<id>.jsonl`` transcript;
  2. ``close()`` the tmux session — the agent is now DEAD, transcript persists
     (the §9.9 cold case: process gone, 📜 record intact);
  3. ``create(name2, cwd=same, resume_session_id=<id>)`` — the relaunch reaches
     idle, ``read_log`` on the NEW session resolves a transcript CONTAINING the
     earlier marker turn (same conversation), and a live interrogation turn
     shows the resumed agent genuinely remembers the marker.

THE SAME-ID-VS-FORK QUESTION (load-bearing for the sidecar half): does the
resumed process keep writing the SAME ``<id>.jsonl`` or fork to a new session
id? Pre-verified by a manual probe and pinned by this test's assertions:
**on Claude Code 2.1.202 plain ``--resume <id>`` REUSES the original session id
and keeps appending to the same ``<id>.jsonl``** (the file even grows by a
couple of entries at resume-attach, before any new turn). A fork requires the
explicit ``--fork-session`` flag (its --help text says exactly that; the
rewind/handoff spike proved the forked case separately). So the bridge
registers the resumed id as-is and transcript resolution continues unchanged.
If a future CLI build starts forking on plain ``--resume``, the same-id
assertions here fail and flag it. The verdict is also recorded in
``tests/log/cold_restore_findings_latest.txt`` on every run.

============================================================================
ISOLATION RULES (parallel-safe — sibling agents may be running their OWN live
bridge sessions at the same time; violating any of these can kill their work):
  * ONE test file, its OWN ``TmuxBridge()`` (never conftest's shared ``bridge``
    fixture — that fixture's setup/teardown call ``tmux kill-server``, which
    would kill every sibling agent's sessions). We NEVER call kill-server.
  * Every tmux session is uniquely named (``coldres-<uuid8>`` /
    ``coldres-r-<uuid8>``) — never a fixed/shared name; we close only our own.
  * We operate only inside our own throwaway WSL cwd and its matching
    ``~/.claude/projects/<escaped-cwd>/`` dir (both removed in teardown).
  * Sessions stay TAB-LESS: ``show=False`` everywhere; ``show()`` never used.

Run (from repo root, ONLY this file — not the whole live tier)::

    .\\.venv\\Scripts\\python.exe -m pytest tests\\test_cold_restore_live.py -x -q
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
def coldres_bridge():
    """Our OWN TmuxBridge — deliberately NOT conftest's shared ``bridge`` fixture,
    whose kill-server setup/teardown would nuke sibling agents' sessions.
    Construction has no side effects; the test tears down only its own
    uniquely-named sessions."""
    return TmuxBridge()


# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #

def _project_dir(diag: str) -> str:
    """The ``~/.claude/projects/<escaped-cwd>/`` dir Claude uses for ``diag``'s
    transcripts (cwd path with '/' -> '-')."""
    return "~/.claude/projects/-home-lester" + diag[len("/home/lester"):].replace("/", "-")


def _jsonl_ids(bridge, proj: str) -> set[str]:
    out = bridge._run(
        f"ls -1 {proj}/*.jsonl 2>/dev/null | xargs -n1 basename 2>/dev/null || echo"
    )
    return {x for x in out.split() if x.endswith(".jsonl")}


def _last_line_session_id(bridge, proj: str, sid: str) -> str | None:
    """The ``sessionId`` stamped on the transcript's last entry — the id the
    live process is actually writing under."""
    try:
        last = bridge._run(f"tail -n 1 {proj}/{sid}.jsonl")
        return json.loads(last).get("sessionId")
    except Exception as e:  # noqa: BLE001 — findings record the failure
        log.debug("cold-restore: last-line read failed: %s", e)
        return None


def _last_assistant_text(bridge, name: str) -> str:
    """The last assistant message from the structured transcript (also proves
    ``read_log`` resolves + parses on the resumed session)."""
    entries = bridge.read_log(name, types=["assistant"])
    if not entries:
        return ""
    return str((entries[-1].get("message") or {}).get("content"))


def _write_findings(facts: dict) -> None:
    """Durable plain-text findings record (same convention as the other spikes:
    a timestamped file + a ``_latest`` copy in tests/log/)."""
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    lines = [
        f"Cold-restore live findings — {stamp}",
        "Question: after `claude --resume <id>` relaunches a DEAD agent, does the",
        "CLI continue writing the SAME <id>.jsonl or fork to a new session id?",
        "",
    ]
    lines += [f"{k}: {v}" for k, v in facts.items()]
    lines += [
        "",
        "Contract consequence (bridge half of #8): create(resume_session_id=<id>)",
        "registers <id> as-is; find_transcript keeps resolving <id>.jsonl; the",
        "returned dict carries session_id=<id> + resumed_conversation=True.",
    ]
    text = "\n".join(lines) + "\n"
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    (LOG_DIR / f"cold_restore_findings_{stamp}.txt").write_text(text, encoding="utf-8")
    (LOG_DIR / "cold_restore_findings_latest.txt").write_text(text, encoding="utf-8")
    log.debug("cold-restore findings:\n%s", text)


# --------------------------------------------------------------------------- #
# the cold-restore proof
# --------------------------------------------------------------------------- #

def test_cold_restore_resumes_same_conversation(coldres_bridge):
    """§9.9 cold case, end to end: kill the tmux session, relaunch via
    ``create(resume_session_id=<id>)``, and prove the new process carries the
    SAME conversation on the SAME session id / ``<id>.jsonl``."""
    bridge = coldres_bridge
    tag = uuid.uuid4().hex[:8]
    name1 = f"coldres-{tag}"
    name2 = f"coldres-r-{tag}"
    diag = f"/home/lester/awl-coldres-{tag}"
    proj = _project_dir(diag)
    marker = f"COLDRES-{tag.upper()}"
    facts: dict = {"cwd": diag, "marker": marker}

    bridge._run(f"mkdir -p {shlex.quote(diag)}")
    try:
        # -- 1. Seed: create tab-less, plant the marker turn, capture the id. --
        info = bridge.create(name1, cwd=diag, model="sonnet", show=False)
        sid = info["session_id"]
        facts["original_session_id"] = sid
        assert info["resumed_conversation"] is False
        bridge.send(name1, f"Remember this codeword: {marker}. "
                           "Reply with exactly: GOT-IT")
        bridge.wait_idle(name1, timeout=180)
        time.sleep(2)
        seed_entries = bridge.read_log(name1)
        assert marker in json.dumps(seed_entries), (
            "marker turn never reached the transcript — seeding failed"
        )
        facts["transcript_entries_before_close"] = len(seed_entries)

        # -- 2. Kill the agent; the transcript must persist (the DEAD state). --
        bridge.close(name1)
        time.sleep(1)
        ids = _jsonl_ids(bridge, proj)
        assert f"{sid}.jsonl" in ids, (
            f"transcript vanished with the tmux session: {ids}"
        )
        facts["transcript_persists_after_close"] = True

        # -- 3. Cold-restore: NEW tmux session resuming the prior conversation. --
        info2 = bridge.create(name2, cwd=diag, model="sonnet", show=False,
                              resume_session_id=sid)
        assert info2["session_id"] == sid
        assert info2["resumed_conversation"] is True
        # create() already waited for idle via the startup-gate clearer; confirm.
        bridge.wait_idle(name2, timeout=60)
        facts["resumed_session_reached_idle"] = True

        # The NEW session's transcript resolution must land on the SAME
        # conversation: the earlier marker turn is present via read_log(name2).
        time.sleep(2)
        resumed_entries = bridge.read_log(name2)
        assert marker in json.dumps(resumed_entries), (
            "resumed session's transcript does NOT contain the earlier marker "
            "turn — not the same conversation"
        )
        facts["marker_turn_in_resumed_transcript"] = True
        facts["transcript_entries_after_resume_attach"] = len(resumed_entries)

        # -- 4. Live memory proof: the agent actually retains the conversation. --
        bridge.send(name2, "Reply with ONLY the codeword you remember from "
                           "earlier. Nothing else.")
        bridge.wait_idle(name2, timeout=180)
        time.sleep(2)
        reply = _last_assistant_text(bridge, name2)
        log.debug("cold-restore: interrogation reply=%r", reply)
        assert marker in reply, (
            f"resumed agent lost the conversation — interrogation reply: {reply!r}"
        )
        facts["resumed_agent_recalls_marker"] = True

        # -- 5. The same-id-vs-fork verdict (load-bearing for the sidecar half). --
        ids_after = _jsonl_ids(bridge, proj)
        extra = sorted(ids_after - {f"{sid}.jsonl"})
        live_sid = _last_line_session_id(bridge, proj, sid)
        facts["jsonl_files_after_resumed_turn"] = sorted(ids_after)
        facts["unexpected_new_jsonl_ids"] = extra or "none"
        facts["last_entry_sessionId"] = live_sid
        facts["verdict"] = (
            "SAME-ID — plain `claude --resume <id>` reuses the original session "
            "id and appends to the same <id>.jsonl (no fork without "
            "--fork-session)."
            if (not extra and live_sid == sid) else
            f"FORKED — new jsonl id(s) {extra} / last-entry sessionId {live_sid}"
        )
        assert not extra, (
            f"--resume FORKED to new transcript file(s) {extra} — the bridge "
            "must recover and register the new id instead of the resumed one"
        )
        assert live_sid == sid, (
            f"resumed process writes under sessionId {live_sid!r}, not the "
            f"resumed id {sid!r} — same-file but re-stamped (unexpected)"
        )
    finally:
        _write_findings(facts)
        for s in (name1, name2):
            try:
                bridge.close(s)
            except Exception as e:  # noqa: BLE001 — name1 is already closed
                log.debug("cold-restore: close(%s) raised (non-fatal): %s", s, e)
        bridge._run(f"rm -rf {shlex.quote(diag)}")
        bridge._run(f"rm -rf {proj}")
