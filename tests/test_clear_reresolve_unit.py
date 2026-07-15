"""Hermetic unit tests — Console ``/clear`` transcript re-resolve (§7.13, §11 #35).

The decided contract this file encodes:

  * A Console ``/clear`` rotates the agent's JSONL transcript to a NEW
    ``<new-id>.jsonl`` while the live process keeps its original ``--session-id``
    argv, so the sidecar's pinned resolution is orphaned until a re-resolve
    (live-proven, ``test_console_clear_transcript_live``); ``/compact`` annotates
    the SAME file and needs no re-resolve.
  * The console-run path detects a ``/clear`` (first token, whitespace/argument/
    case tolerant — ``_is_clear_command``) and calls the driver's
    ``handle_transcript_rotation()`` so main never reaches into driver privates.
  * ``TmuxBridge.reresolve_session_id`` re-pins by the newest ``*.jsonl`` in the
    session's project dir whose id differs from the pinned one (nothing else
    names the rotated id — the process args keep the OLD id), registering it so
    ``find_transcript`` follows the rotation; returns None while no rotated file
    exists yet.
  * On adoption the driver **replays the fresh transcript from 0** (a /clear is a
    NEW conversation: ``_seen`` resets, ``_transcript_path`` clears so the next
    read re-resolves + persists, and the runtime record is refreshed with the new
    ``claude_session_id``). When the rotated file hasn't appeared yet (some
    builds create it only on the first post-/clear turn), a pending flag makes
    ``events()`` stop reading the orphaned old file and retry the re-resolve
    each poll — post-/clear turns are never lost either way.

No WSL, no network — fake bridges throughout. The live acceptance (post-/clear
turns actually reach the sidecar) is ``test_console_clear_reresolve_live.py``.
"""

import asyncio
import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))
_SIDECAR = Path(__file__).resolve().parent.parent / "sidecar"
if str(_SIDECAR) not in sys.path:
    sys.path.insert(0, str(_SIDECAR))

from bridge import TmuxBridge  # noqa: E402
from main import _is_clear_command  # noqa: E402
from sidecar.drivers.bridge import BridgeDriver  # noqa: E402
from sidecar.drivers.base import DriverConfig  # noqa: E402


# -----------------------------------------------------------------------------
# /clear command detection (the console-run trigger)
# -----------------------------------------------------------------------------

class TestIsClearCommand:
    def test_plain_clear(self):
        assert _is_clear_command("/clear") is True

    def test_whitespace_and_arguments_tolerated(self):
        assert _is_clear_command("  /clear  ") is True
        assert _is_clear_command("/clear now") is True

    def test_case_insensitive(self):
        assert _is_clear_command("/CLEAR") is True

    def test_compact_is_not_clear(self):
        # /compact annotates the SAME file (live-proven) — never re-resolved.
        assert _is_clear_command("/compact") is False

    def test_prefix_lookalikes_rejected(self):
        assert _is_clear_command("/clearx") is False
        assert _is_clear_command("clear") is False

    def test_empty_rejected(self):
        assert _is_clear_command("") is False
        assert _is_clear_command("   ") is False


# -----------------------------------------------------------------------------
# TmuxBridge.reresolve_session_id — newest-file re-pin in the project dir
# -----------------------------------------------------------------------------

def _patched_bridge(monkeypatch, *, pinned, newest_lines):
    """A TmuxBridge whose WSL surface is canned: pane cwd + project dir resolve,
    and each successive `ls -t | head -1` call pops the next canned line."""
    b = TmuxBridge()
    if pinned:
        b._session_uuids["agent-x"] = pinned
    monkeypatch.setattr(b, "_tmux", lambda cmd: "/home/u/proj\n")
    monkeypatch.setattr(
        "bridge.transcript._resolve_project_dir",
        lambda bridge, cwd: "/home/u/.claude/projects/-home-u-proj",
    )
    calls = {"n": 0}

    def fake_run(cmd, timeout=30, stdin_data=None):
        i = min(calls["n"], len(newest_lines) - 1)
        calls["n"] += 1
        return newest_lines[i]

    monkeypatch.setattr(b, "_run", fake_run)
    monkeypatch.setattr("bridge.bridge.time.sleep", lambda s: None)
    return b


class TestReresolveSessionId:
    def test_rotated_file_repins_and_returns_new_id(self, monkeypatch):
        b = _patched_bridge(
            monkeypatch, pinned="old-id",
            newest_lines=["/home/u/.claude/projects/-home-u-proj/new-id.jsonl\n"],
        )
        assert b.reresolve_session_id("agent-x", timeout=0.0) == "new-id"
        # The rotated id is REGISTERED so find_transcript follows it.
        assert b.session_id_for("agent-x") == "new-id"

    def test_no_new_file_yet_returns_none_and_keeps_pin(self, monkeypatch):
        # Newest is still the pinned file — nothing rotated yet.
        b = _patched_bridge(
            monkeypatch, pinned="old-id",
            newest_lines=["/home/u/.claude/projects/-home-u-proj/old-id.jsonl\n"],
        )
        assert b.reresolve_session_id("agent-x", timeout=0.0) is None
        assert b.session_id_for("agent-x") == "old-id"

    def test_empty_project_dir_returns_none(self, monkeypatch):
        b = _patched_bridge(monkeypatch, pinned="old-id", newest_lines=[""])
        assert b.reresolve_session_id("agent-x", timeout=0.0) is None

    def test_polls_until_rotated_file_appears(self, monkeypatch):
        # First check still sees the old file; the retry sees the rotated one.
        b = _patched_bridge(
            monkeypatch, pinned="old-id",
            newest_lines=[
                "/home/u/.claude/projects/-home-u-proj/old-id.jsonl\n",
                "/home/u/.claude/projects/-home-u-proj/new-id.jsonl\n",
            ],
        )
        assert b.reresolve_session_id("agent-x", timeout=5.0, interval=0.0) == "new-id"

    def test_unresolvable_cwd_returns_none(self, monkeypatch):
        b = TmuxBridge()

        def boom(cmd):
            raise RuntimeError("no pane")

        monkeypatch.setattr(b, "_tmux", boom)
        assert b.reresolve_session_id("agent-x", timeout=0.0) is None


# -----------------------------------------------------------------------------
# BridgeDriver.handle_transcript_rotation — adopt-or-arm-pending
# -----------------------------------------------------------------------------

class _FakeRotBridge:
    """Driver-facing bridge stub: reresolve_session_id returns a scripted queue
    of answers (None = not rotated yet); read_log records its calls."""

    def __init__(self, answers):
        self.answers = list(answers)
        self.reresolve_calls = 0
        self.read_log_calls = 0

    def reresolve_session_id(self, name, timeout=5.0, interval=0.5):
        self.reresolve_calls += 1
        if self.answers:
            return self.answers.pop(0)
        return None

    def read_log(self, name):
        self.read_log_calls += 1
        return []

    def status(self, name):
        return {"state": "idle"}


def _driver(monkeypatch, answers, *, record=True):
    d = BridgeDriver(DriverConfig(), lambda e: None)
    d._bridge = _FakeRotBridge(answers)
    d._claude_session_id = "old-id"
    d._seen = 42
    d._transcript_path = "/home/u/.claude/projects/p/old-id.jsonl"
    d._last_state = "idle"   # suppress the first status_change from the stub
    if record:
        d._record = {"session_id": "s1", "claude_session_id": "old-id",
                     "transcript_path": d._transcript_path}
    saved = []
    monkeypatch.setattr("sidecar.drivers.bridge._save_record",
                        lambda rec: saved.append(dict(rec)))
    return d, saved


async def _one_events_poll(monkeypatch, d):
    """Run exactly ONE iteration of the driver's events() poll loop, returning
    the events it yielded (the loop is cut at its end-of-iteration sleep)."""
    real_sleep = asyncio.sleep

    async def stop_sleep(s):
        d._closed = True
        await real_sleep(0)

    monkeypatch.setattr("sidecar.drivers.bridge.asyncio.sleep", stop_sleep)
    events = []
    async for ev in d.events():
        events.append(ev)
    return events


class TestHandleTranscriptRotation:
    def test_rotation_adopts_new_id_and_replays_from_zero(self, monkeypatch):
        d, saved = _driver(monkeypatch, ["new-id"])
        out = asyncio.run(d.handle_transcript_rotation())
        assert out == {"rotated": True, "claude_session_id": "new-id",
                       "pending": False}
        # New conversation: replay the fresh transcript from 0.
        assert d._seen == 0
        assert d._claude_session_id == "new-id"
        # Path cleared -> the next successful read re-resolves + persists it.
        assert d._transcript_path is None
        assert d._rotation_pending is False
        # The runtime record was refreshed (restart-survival keeps the new id).
        assert saved and saved[-1]["claude_session_id"] == "new-id"
        assert saved[-1]["transcript_path"] is None

    def test_no_rotated_file_yet_arms_pending(self, monkeypatch):
        d, saved = _driver(monkeypatch, [None])
        out = asyncio.run(d.handle_transcript_rotation())
        assert out == {"rotated": False, "claude_session_id": "old-id",
                       "pending": True}
        assert d._rotation_pending is True
        # Nothing adopted, nothing persisted.
        assert d._seen == 42
        assert d._claude_session_id == "old-id"
        assert saved == []

    def test_pending_skips_the_orphaned_old_file(self, monkeypatch):
        """While a rotation is pending (rotated file not on disk yet), events()
        must NOT read the orphaned old transcript — it only retries the
        re-resolve each poll."""
        d, saved = _driver(monkeypatch, [None, None])
        asyncio.run(d.handle_transcript_rotation())
        assert d._rotation_pending is True

        events = asyncio.run(_one_events_poll(monkeypatch, d))
        assert d._rotation_pending is True        # retry saw no rotated file yet
        assert d._bridge.read_log_calls == 0      # orphaned old file untouched
        assert d._bridge.reresolve_calls == 2     # the arm + the poll retry
        assert events == []

    def test_pending_rotation_resolves_on_events_poll(self, monkeypatch):
        """Once the rotated file lands, the events() retry adopts it — the
        deferred path for builds that create the rotated file only on the
        first post-/clear turn."""
        d, saved = _driver(monkeypatch, [None, "new-id"])
        asyncio.run(d.handle_transcript_rotation())
        assert d._rotation_pending is True

        events = asyncio.run(_one_events_poll(monkeypatch, d))
        assert d._rotation_pending is False
        assert d._claude_session_id == "new-id"
        assert d._seen == 0
        # After adoption the SAME iteration reads the rotated (fresh) file.
        assert d._bridge.read_log_calls == 1
        assert events == []          # no stale events replayed from the old file

    def test_missing_record_is_tolerated(self, monkeypatch):
        d, saved = _driver(monkeypatch, ["new-id"], record=False)
        d._record = None
        out = asyncio.run(d.handle_transcript_rotation())
        assert out["rotated"] is True
        assert saved == []
