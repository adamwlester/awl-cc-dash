"""Hermetic unit tests — polling-scale rework (§11 #34 → §4.3/§6.2).

The decided contract this file encodes:

  * **Batching:** ``TmuxBridge.poll_bundle`` collapses a driver poll cycle
    into ONE WSL invocation emitting a sentinel-delimited envelope — the state
    screen (the exact slice ``status()`` classifies), the detail screen (its
    permission re-read), and the transcript's byte size + the bytes from a
    caller-tracked offset, base64-wrapped (byte-exact through the Windows
    text-mode pipe; ``parse_bundle_envelope`` decodes it). The pre-rework
    cycle cost ~5 WSL spawns/agent/second (``read_log`` resolve+cat +
    ``status`` capture), the measured cause of the fleet degrading from N=1
    (``test_polling_scale_ceiling_live``).
  * **Incremental reads:** ``consume_transcript_chunk`` consumes only COMPLETE
    JSONL lines — a partial trailing line (a write in progress, possibly
    splitting a multi-byte character) is left unconsumed and re-read whole
    next poll, so a torn entry can never be emitted and the offset arithmetic
    stays byte-exact.
  * **Adaptive cadence:** ``AdaptiveCadence`` polls at 1 s while running /
    recently active, coasts to 5 s after ~30 s of no activity, and snaps back
    instantly on ``nudge()`` (send / interrupt / hook ingest / observed
    activity — the driver nudges internally, the sidecar's ``_nudge_driver``
    covers the push channels). Pure logic, injectable clock.
  * **The driver's events() loop** uses the bundle once the transcript path is
    resolved (one WSL call per cycle; state from the bundled screen,
    permission detail from the bundled detail slice), replaces its buffer on
    an offset-0 (full) read so the legacy→bundle handover cannot duplicate
    events, and sleeps the cadence interval.

No WSL, no tmux — scripted fakes throughout. The live re-measure (per-cycle
cost, event lag, the new practical ceiling) is ``test_polling_rework_live.py``
(findings in ``log/polling_rework_findings_latest.txt``).
"""

import asyncio
import base64
import json
import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))
_SIDECAR = _REPO_ROOT / "sidecar"
if str(_SIDECAR) not in sys.path:
    sys.path.insert(0, str(_SIDECAR))

from bridge.bridge import (  # noqa: E402
    TmuxBridge, TmuxBridgeError, parse_bundle_envelope,
)
from bridge.transcript import consume_transcript_chunk  # noqa: E402
from sidecar.drivers.bridge import AdaptiveCadence, BridgeDriver  # noqa: E402
from sidecar.drivers.base import DriverConfig  # noqa: E402


# -----------------------------------------------------------------------------
# parse_bundle_envelope — the delimited one-round-trip envelope
# -----------------------------------------------------------------------------

SENT = "AWLPB-deadbeef"


def _envelope(screen="❯ idle", detail="detail\n❯ idle", size=123,
              chunk=b'{"type":"user"}\n'):
    b64 = base64.b64encode(chunk).decode() if chunk is not None else ""
    return (f"{screen}\n{SENT}\n{detail}\n{SENT}\n{size}\n{SENT}\n{b64}")


class TestParseBundleEnvelope:
    def test_full_envelope_round_trips(self):
        out = parse_bundle_envelope(_envelope(), SENT)
        assert out["screen"] == "❯ idle"
        assert out["screen_detail"] == "detail\n❯ idle"
        assert out["size"] == 123
        assert out["chunk"] == b'{"type":"user"}\n'

    def test_missing_file_shape(self):
        raw = f"❯ idle\n{SENT}\n❯ idle\n{SENT}\n-1\n{SENT}\n"
        out = parse_bundle_envelope(raw, SENT)
        assert out["size"] == -1
        assert out["chunk"] == b""

    def test_trailing_strip_is_harmless(self):
        # _run strips trailing whitespace — base64 lives on one line, immune.
        out = parse_bundle_envelope(_envelope().rstrip("\n "), SENT)
        assert out["chunk"] == b'{"type":"user"}\n'

    def test_multiline_screens_survive(self):
        out = parse_bundle_envelope(
            _envelope(screen="line1\nline2\n❯", detail="a\nb\nc"), SENT)
        assert out["screen"] == "line1\nline2\n❯"
        assert out["screen_detail"] == "a\nb\nc"

    def test_corrupt_envelope_raises(self):
        with pytest.raises(TmuxBridgeError, match="corrupt"):
            parse_bundle_envelope("no sentinels here", SENT)
        with pytest.raises(TmuxBridgeError, match="corrupt"):
            parse_bundle_envelope(f"screen\n{SENT}\nonly-one", SENT)

    def test_bogus_size_and_b64_degrade(self):
        raw = f"s\n{SENT}\nd\n{SENT}\nnot-a-number\n{SENT}\n!!!notb64!!!"
        out = parse_bundle_envelope(raw, SENT)
        assert out["size"] == -1
        assert out["chunk"] == b""

    def test_poll_bundle_builds_one_command(self, monkeypatch):
        # The whole cycle must be ONE _run invocation (the point of #34).
        b = TmuxBridge()
        calls = []

        def fake_run(cmd, timeout=30, stdin_data=None):
            calls.append(cmd)
            import re
            sent = re.search(r"echo (AWLPB-[0-9a-f]+)", cmd).group(1)
            return f"scr\n{sent}\ndet\n{sent}\n5\n{sent}\n" + \
                base64.b64encode(b"12345").decode()

        monkeypatch.setattr(b, "_run", fake_run)
        out = b.poll_bundle("agent-x", "/home/u/t.jsonl", offset=10)
        assert len(calls) == 1, "poll_bundle must be a single WSL round-trip"
        assert "tail -c +11" in calls[0]       # offset+1 (1-based tail)
        assert "wc -c" in calls[0]
        assert calls[0].count("capture-pane") == 2
        assert out["size"] == 5 and out["chunk"] == b"12345"

    def test_poll_bundle_without_path_reports_missing(self, monkeypatch):
        b = TmuxBridge()

        def fake_run(cmd, timeout=30, stdin_data=None):
            import re
            sent = re.search(r"echo (AWLPB-[0-9a-f]+)", cmd).group(1)
            return f"scr\n{sent}\ndet\n{sent}\n-1\n{sent}\n"

        monkeypatch.setattr(b, "_run", fake_run)
        out = b.poll_bundle("agent-x", None)
        assert out["size"] == -1 and out["chunk"] == b""


# -----------------------------------------------------------------------------
# consume_transcript_chunk — complete-lines-only incremental parsing
# -----------------------------------------------------------------------------

class TestConsumeTranscriptChunk:
    def test_complete_lines_parse_and_consume_fully(self):
        chunk = b'{"a": 1}\n{"b": 2}\n'
        entries, consumed = consume_transcript_chunk(chunk)
        assert entries == [{"a": 1}, {"b": 2}]
        assert consumed == len(chunk)

    def test_partial_trailing_line_is_left_unconsumed(self):
        chunk = b'{"a": 1}\n{"b": '
        entries, consumed = consume_transcript_chunk(chunk)
        assert entries == [{"a": 1}]
        assert consumed == len(b'{"a": 1}\n')
        # The re-read (rest of the line + the next poll's bytes) completes it.
        rest = chunk[consumed:] + b'2}\n'
        entries2, consumed2 = consume_transcript_chunk(rest)
        assert entries2 == [{"b": 2}]
        assert consumed2 == len(rest)

    def test_partial_multibyte_character_cannot_tear(self):
        # A UTF-8 é split across the poll boundary: the partial line stays
        # unconsumed, so the offset never lands inside a character.
        line = '{"text": "café"}'.encode("utf-8")
        chunk = b'{"a": 1}\n' + line[:12]      # cut inside the é
        entries, consumed = consume_transcript_chunk(chunk)
        assert entries == [{"a": 1}]
        assert consumed == len(b'{"a": 1}\n')
        whole = chunk[consumed:] + line[12:] + b"\n"
        entries2, _ = consume_transcript_chunk(whole)
        assert entries2 == [{"text": "café"}]

    def test_no_newline_consumes_nothing(self):
        entries, consumed = consume_transcript_chunk(b'{"partial": ')
        assert entries == [] and consumed == 0

    def test_empty_chunk(self):
        assert consume_transcript_chunk(b"") == ([], 0)

    def test_corrupt_complete_line_is_skipped_but_consumed(self):
        chunk = b'not json\n{"ok": true}\n'
        entries, consumed = consume_transcript_chunk(chunk)
        assert entries == [{"ok": True}]
        assert consumed == len(chunk)

    def test_blank_lines_are_ignored(self):
        entries, consumed = consume_transcript_chunk(b'\n\n{"a": 1}\n\n')
        assert entries == [{"a": 1}]
        assert consumed == len(b'\n\n{"a": 1}\n\n')


# -----------------------------------------------------------------------------
# AdaptiveCadence — the pure state machine (controllable clock)
# -----------------------------------------------------------------------------

class _Clock:
    def __init__(self):
        self.t = 1000.0

    def __call__(self):
        return self.t


class TestAdaptiveCadence:
    def test_starts_active(self):
        clk = _Clock()
        c = AdaptiveCadence(clock=clk)
        assert c.interval() == 1.0

    def test_backs_off_after_idle_window(self):
        clk = _Clock()
        c = AdaptiveCadence(clock=clk)
        clk.t += 29.9
        assert c.interval() == 1.0            # still inside the window
        clk.t += 0.2                          # 30.1 s idle
        assert c.interval() == 5.0

    def test_nudge_snaps_back_instantly(self):
        clk = _Clock()
        c = AdaptiveCadence(clock=clk)
        clk.t += 100
        assert c.interval() == 5.0
        c.nudge()
        assert c.interval() == 1.0

    def test_repeated_activity_keeps_it_fast(self):
        clk = _Clock()
        c = AdaptiveCadence(clock=clk)
        for _ in range(10):
            clk.t += 20
            c.nudge()
            assert c.interval() == 1.0

    def test_custom_intervals(self):
        clk = _Clock()
        c = AdaptiveCadence(active_interval=0.5, idle_interval=8.0,
                            idle_after=10.0, clock=clk)
        assert c.interval() == 0.5
        clk.t += 11
        assert c.interval() == 8.0
        assert c.idle_for() == 11


# -----------------------------------------------------------------------------
# events() — the batched loop with a scripted fake bridge
# -----------------------------------------------------------------------------

IDLE_SCREEN = "────────────────────\n❯\n────────────────────"
GENERATING_SCREEN = "✻ Percolating… (esc to interrupt)\n❯"


class _BundleBridge:
    """Scripted fake: poll_bundle pops canned results; read_log/status count
    calls so the test can assert the batched path bypasses them."""

    def __init__(self, bundles):
        self.bundles = list(bundles)
        self.bundle_calls: list[tuple] = []
        self.read_log_calls = 0
        self.status_calls = 0

    def poll_bundle(self, name, transcript_path=None, offset=0, **kw):
        self.bundle_calls.append((transcript_path, offset))
        return self.bundles.pop(0) if self.bundles else {
            "screen": IDLE_SCREEN, "screen_detail": IDLE_SCREEN,
            "size": 0, "chunk": b""}

    def read_log(self, name):
        self.read_log_calls += 1
        return []

    def status(self, name):
        self.status_calls += 1
        return {"state": "idle"}

    def _detect_state(self, content):
        return TmuxBridge._detect_state(self, content)


def _bundle(entries=(), screen=IDLE_SCREEN, size=100):
    chunk = b"".join(json.dumps(e).encode() + b"\n" for e in entries)
    return {"screen": screen, "screen_detail": screen,
            "size": size, "chunk": chunk}


def _mk_driver(bridge, path="/home/u/t.jsonl"):
    d = BridgeDriver(DriverConfig(), lambda e: None)
    d._bridge = bridge
    d._transcript_path = path
    d._last_state = "idle"     # suppress the initial state flip
    return d


async def _cycles(monkeypatch, d, n=1):
    """Run exactly n iterations of events(), collecting yielded events."""
    real_sleep = asyncio.sleep
    count = {"n": 0}

    async def counting_sleep(s):
        count["n"] += 1
        if count["n"] >= n:
            d._closed = True
        await real_sleep(0)

    monkeypatch.setattr("sidecar.drivers.bridge.asyncio.sleep", counting_sleep)
    out = []
    async for ev in d.events():
        out.append(ev)
    return out


class TestEventsBundledLoop:
    def test_one_bundle_call_per_cycle_no_legacy_calls(self, monkeypatch):
        br = _BundleBridge([_bundle(entries=[
            {"type": "user", "uuid": "u1", "timestamp": "T",
             "message": {"content": "hi"}},
            {"type": "assistant", "uuid": "a1", "timestamp": "T",
             "message": {"content": [{"type": "text", "text": "yo"}]}},
        ])])
        d = _mk_driver(br)
        events = asyncio.run(_cycles(monkeypatch, d, n=1))
        assert len(br.bundle_calls) == 1
        assert br.read_log_calls == 0, "batched path must not read_log"
        assert br.status_calls == 0, "batched path must not call status()"
        assert [e["type"] for e in events] == ["user", "assistant"]

    def test_offset_advances_and_second_cycle_extends(self, monkeypatch):
        e1 = {"type": "user", "uuid": "u1", "timestamp": "T",
              "message": {"content": "one"}}
        e2 = {"type": "user", "uuid": "u2", "timestamp": "T",
              "message": {"content": "two"}}
        b1 = _bundle(entries=[e1])
        b2 = _bundle(entries=[e2])
        br = _BundleBridge([b1, b2])
        d = _mk_driver(br)
        events = asyncio.run(_cycles(monkeypatch, d, n=2))
        # First call at offset 0, second at len(chunk1).
        assert br.bundle_calls[0][1] == 0
        assert br.bundle_calls[1][1] == len(b1["chunk"])
        assert [e["type"] for e in events] == ["user", "user"]
        assert d._seen == 2

    def test_offset_zero_read_replaces_legacy_buffer_no_duplicates(
            self, monkeypatch):
        # The legacy path pre-filled the buffer (2 entries emitted, _seen=2);
        # the first bundle read (offset 0 = full snapshot) must REPLACE, not
        # extend — otherwise every already-emitted entry would re-emit.
        e1 = {"type": "user", "uuid": "u1", "timestamp": "T",
              "message": {"content": "one"}}
        e2 = {"type": "user", "uuid": "u2", "timestamp": "T",
              "message": {"content": "two"}}
        br = _BundleBridge([_bundle(entries=[e1, e2])])
        d = _mk_driver(br)
        d._entries = [e1, e2]     # as the legacy read_log path left them
        d._seen = 2
        events = asyncio.run(_cycles(monkeypatch, d, n=1))
        assert events == []       # nothing re-emitted
        assert d._seen == 2

    def test_vanished_transcript_falls_back_to_resolving_path(
            self, monkeypatch):
        br = _BundleBridge([{"screen": IDLE_SCREEN,
                             "screen_detail": IDLE_SCREEN,
                             "size": -1, "chunk": b""}])
        d = _mk_driver(br)
        d._log_offset = 50
        asyncio.run(_cycles(monkeypatch, d, n=1))
        assert d._transcript_path is None
        assert d._log_offset == 0 and d._entries == []

    def test_generating_screen_emits_status_and_nudges(self, monkeypatch):
        br = _BundleBridge([_bundle(screen=GENERATING_SCREEN)])
        d = _mk_driver(br)
        d._pending_turn = True     # a dashboard turn is outstanding (a send fired)
        # Pre-idle the cadence so the nudge is observable.
        d._cadence._last_activity -= 1000
        assert d._cadence.interval() == 5.0
        events = asyncio.run(_cycles(monkeypatch, d, n=1))
        assert events[-1]["type"] == "status_change"
        assert events[-1]["status"] == "running"
        assert d._cadence.interval() == 1.0, "activity must snap the cadence"

    def test_generating_screen_without_pending_turn_suppresses_running(
            self, monkeypatch):
        # Post-turn background work (Claude Code auto-generating the conversation
        # title, etc.) spins the screen with NO dashboard turn outstanding. It
        # must NOT emit a running status_change — otherwise its trailing idle
        # would fire a phantom completion. The cadence still nudges on activity.
        br = _BundleBridge([_bundle(screen=GENERATING_SCREEN)])
        d = _mk_driver(br)          # _pending_turn defaults False
        d._cadence._last_activity -= 1000
        events = asyncio.run(_cycles(monkeypatch, d, n=1))
        statuses = [e for e in events if e["type"] == "status_change"]
        assert statuses == [], "generating with no turn pending emits no running"
        assert d._cadence.interval() == 1.0, "activity still snaps the cadence"
        assert d._last_state == "generating"   # the read is still recorded

    def test_legacy_path_still_used_before_resolution(self, monkeypatch):
        br = _BundleBridge([])
        d = _mk_driver(br, path=None)
        asyncio.run(_cycles(monkeypatch, d, n=1))
        assert br.bundle_calls == []
        assert br.read_log_calls == 1
        assert br.status_calls == 1

    def test_rotation_reset_clears_incremental_state(self, monkeypatch):
        d = _mk_driver(_BundleBridge([]))
        d._entries = [{"x": 1}]
        d._log_offset = 99
        d._seen = 42
        monkeypatch.setattr("sidecar.drivers.bridge._save_record",
                            lambda rec: None)
        d._apply_rotation("new-id")
        assert d._entries == [] and d._log_offset == 0 and d._seen == 0


# -----------------------------------------------------------------------------
# nudge plumbing — driver-internal + the sidecar's _nudge_driver
# -----------------------------------------------------------------------------

class TestNudgePlumbing:
    def test_driver_send_and_interrupt_nudge(self):
        class _NoopBridge:
            def send(self, name, text):
                pass

            def interrupt(self, name):
                pass

        d = _mk_driver(_NoopBridge())
        d._cadence._last_activity -= 1000
        assert d._cadence.interval() == 5.0
        asyncio.run(d.send("hello"))
        assert d._cadence.interval() == 1.0
        d._cadence._last_activity -= 1000
        asyncio.run(d.interrupt())
        assert d._cadence.interval() == 1.0

    def test_sidecar_nudge_driver_reaches_the_cadence(self):
        import main
        from main import SessionState
        s = SessionState(
            session_id="s1", agent_type=None, model=None,
            permission_mode="default", cwd=None, system_prompt=None,
            driver_name="bridge",
        )
        d = _mk_driver(_BundleBridge([]))
        d._cadence._last_activity -= 1000
        s.driver = d
        main.sessions["s1"] = s
        try:
            main._nudge_driver("s1")
            assert d._cadence.interval() == 1.0
            main._nudge_driver("unknown")   # no-op, never raises
        finally:
            main.sessions.pop("s1", None)

    def test_nudge_driver_tolerates_driverless_sessions(self):
        import main
        from main import SessionState
        s = SessionState(
            session_id="s1", agent_type=None, model=None,
            permission_mode="default", cwd=None, system_prompt=None,
            driver_name="bridge",
        )
        main.sessions["s1"] = s
        try:
            main._nudge_driver("s1")        # driver is None — no-op
        finally:
            main.sessions.pop("s1", None)


# -----------------------------------------------------------------------------
# Turn-completion backstop — the run->idle signal must fire even when the poll
# never samples the `generating` phase (the fast-turn / coasted-poll bug), yet
# must NOT false-fire in the brief idle gap between send and the TUI actually
# entering `generating` (proven live: firing there raised an empty completion).
#
# _flush_queue sets session.status="running" synthetically on send; the ONLY
# thing that resets it to idle AND fires the turn-completion side-effects (turn
# count, §7.8 response card, reply-relay, shared-context, queue flush) is the
# driver emitting a status_change="idle". The driver emits idle on its internal
# generating->idle transition; when the poll misses `generating` entirely the
# transition never fires (idle==idle), so send() flags `_pending_turn` and the
# poll backstops it — but ONLY once the turn's reply is in the transcript
# (`_saw_reply_since_send`), never on the empty pre-`generating` gap.
# -----------------------------------------------------------------------------

USER_ENTRY = {"type": "user", "uuid": "u1", "timestamp": "T",
              "message": {"content": "hi"}}
ASSISTANT_ENTRY = {"type": "assistant", "uuid": "a1", "timestamp": "T",
                   "message": {"content": [{"type": "text", "text": "PONG"}]}}


class _SendBridge:
    """Fake with a no-op send() so BridgeDriver.send() can set its flags."""

    def send(self, name, text):
        pass


class TestTurnCompletionBackstop:
    def test_send_arms_backstop_and_resets_reply_watermark(self):
        d = _mk_driver(_SendBridge())
        d._saw_reply_since_send = True     # a stale prior-turn reply
        assert d._pending_turn is False
        asyncio.run(d.send("do a thing"))
        assert d._pending_turn is True, \
            "a successful send must flag an outstanding turn"
        assert d._saw_reply_since_send is False, \
            "send must reset the reply watermark — a new turn owes a fresh reply"

    def test_failed_send_leaves_no_pending_turn(self):
        class _BoomBridge:
            def send(self, name, text):
                raise RuntimeError("tmux gone")

        d = _mk_driver(_BoomBridge())
        with pytest.raises(RuntimeError):
            asyncio.run(d.send("x"))
        assert d._pending_turn is False, \
            "a throwing send starts no turn — must not flag one"

    def test_missed_generating_with_reply_emits_one_completion(self, monkeypatch):
        # The bug: the whole turn (generating + the reply) landed inside one
        # coasted poll interval. The poll wakes to an idle screen with the reply
        # already in the transcript delta; `_last_state` is still "idle" so the
        # transition path stays silent — the backstop must emit exactly one idle.
        br = _BundleBridge([_bundle(entries=[USER_ENTRY, ASSISTANT_ENTRY],
                                    screen=IDLE_SCREEN)])
        d = _mk_driver(br)                 # _last_state="idle"
        d._pending_turn = True             # a send happened; generating missed
        events = asyncio.run(_cycles(monkeypatch, d, n=1))
        idles = [e for e in events
                 if e["type"] == "status_change" and e["status"] == "idle"]
        assert len(idles) == 1, "must emit the run->idle completion signal once"
        assert d._saw_reply_since_send is True
        assert d._pending_turn is False, "the outstanding turn is now resolved"

    def test_no_false_completion_in_pre_generating_gap(self, monkeypatch):
        # The false-early bug (proven live): after send the screen is briefly
        # still idle BEFORE the TUI enters `generating`, and NO reply exists yet.
        # The completion must NOT fire here, and must LEAVE `_pending_turn` armed
        # so the real completion still fires later.
        br = _BundleBridge([_bundle(entries=(), screen=IDLE_SCREEN)])
        d = _mk_driver(br)                 # _last_state="idle"
        d._pending_turn = True             # send outstanding, reply not in yet
        events = asyncio.run(_cycles(monkeypatch, d, n=1))
        idles = [e for e in events
                 if e["type"] == "status_change" and e["status"] == "idle"]
        assert idles == [], "no reply yet => the gap idle must NOT complete a turn"
        assert d._pending_turn is True, "the turn stays outstanding — armed"

    def test_no_false_completion_on_first_poll_after_immediate_send(
            self, monkeypatch):
        # The live `None -> idle` race (proven on a create-then-send agent whose
        # first poll ran only AFTER the send): `_last_state` is still None, so the
        # first idle read is a `None -> idle` transition. With a turn outstanding
        # that transition must be SUPPRESSED (not fire an empty completion); only
        # the reply-backed completion may close the turn.
        br = _BundleBridge([_bundle(entries=(), screen=IDLE_SCREEN)])
        d = _mk_driver(br)
        d._last_state = None               # first poll ever, but send already fired
        d._pending_turn = True
        events = asyncio.run(_cycles(monkeypatch, d, n=1))
        idles = [e for e in events
                 if e["type"] == "status_change" and e["status"] == "idle"]
        assert idles == [], "None->idle with a turn outstanding must not complete it"
        assert d._pending_turn is True
        assert d._last_state == "idle"     # the read is still recorded

    def test_connect_idle_emits_when_no_turn_outstanding(self, monkeypatch):
        # A freshly-connected agent (no send) must still emit its connect idle so
        # its status settles to idle — the suppression is gated on `_pending_turn`.
        br = _BundleBridge([_bundle(entries=(), screen=IDLE_SCREEN)])
        d = _mk_driver(br)
        d._last_state = None               # fresh driver, nothing emitted yet
        # _pending_turn defaults False (no send)
        events = asyncio.run(_cycles(monkeypatch, d, n=1))
        idles = [e for e in events
                 if e["type"] == "status_change" and e["status"] == "idle"]
        assert len(idles) == 1, "the connect idle must fire when no turn is pending"

    def test_gap_then_real_completion_fires_exactly_once(self, monkeypatch):
        # The full live sequence: an empty pre-generating gap idle (no fire), then
        # the reply lands with the screen idle (missed generating) => fire ONCE.
        br = _BundleBridge([
            _bundle(entries=(), screen=IDLE_SCREEN),                 # gap
            _bundle(entries=[USER_ENTRY, ASSISTANT_ENTRY], screen=IDLE_SCREEN),
        ])
        d = _mk_driver(br)
        d._pending_turn = True
        events = asyncio.run(_cycles(monkeypatch, d, n=2))
        idles = [e for e in events
                 if e["type"] == "status_change" and e["status"] == "idle"]
        assert len(idles) == 1, "exactly one completion across the gap + real idle"
        assert d._pending_turn is False

    def test_no_completion_without_a_pending_turn(self, monkeypatch):
        # A steady idle agent (freshly connected / between turns) must NOT emit a
        # spurious idle even if a stale reply sits in the transcript.
        br = _BundleBridge([_bundle(entries=[ASSISTANT_ENTRY], screen=IDLE_SCREEN)])
        d = _mk_driver(br)                 # _last_state="idle", _pending_turn=False
        events = asyncio.run(_cycles(monkeypatch, d, n=1))
        idles = [e for e in events
                 if e["type"] == "status_change" and e["status"] == "idle"]
        assert idles == [], "no send outstanding => no completion signal"

    def test_backstop_fires_exactly_once_across_repeated_idle_polls(
            self, monkeypatch):
        # After the reply-backed idle fires once, a second idle poll (coasted
        # re-read) must not re-fire — `_pending_turn` was cleared.
        br = _BundleBridge([
            _bundle(entries=[USER_ENTRY, ASSISTANT_ENTRY], screen=IDLE_SCREEN),
            _bundle(entries=(), screen=IDLE_SCREEN),
        ])
        d = _mk_driver(br)
        d._pending_turn = True
        events = asyncio.run(_cycles(monkeypatch, d, n=2))
        idles = [e for e in events
                 if e["type"] == "status_change" and e["status"] == "idle"]
        assert len(idles) == 1, "repeated idle polls must not re-fire completion"

    def test_caught_generating_then_idle_emits_running_then_single_idle(
            self, monkeypatch):
        # The normal path still works and does NOT double-fire: the poll catches
        # generating (emit running), then idle with the reply (the completion
        # branch emits idle), and nothing adds a second idle.
        br = _BundleBridge([
            _bundle(entries=(), screen=GENERATING_SCREEN),
            _bundle(entries=[USER_ENTRY, ASSISTANT_ENTRY], screen=IDLE_SCREEN),
        ])
        d = _mk_driver(br)                 # _last_state="idle"
        d._pending_turn = True
        events = asyncio.run(_cycles(monkeypatch, d, n=2))
        statuses = [e["status"] for e in events if e["type"] == "status_change"]
        assert statuses == ["running", "idle"], \
            "one running, exactly one idle — no duplicate completion"
        assert d._pending_turn is False

    def test_post_turn_background_spinner_emits_no_second_running(
            self, monkeypatch):
        # The live post-turn double (proven on agent c38e3037): after a turn
        # completes, Claude Code auto-generates the conversation title — a brief
        # `generating -> idle` spinner with NO dashboard turn pending. That cycle
        # must emit NO running (so its idle carries no `_was_running` and cannot
        # raise a second §7.8 card). Full sequence: send-turn generating -> reply
        # idle (completion) -> post-turn generating -> settle idle.
        br = _BundleBridge([
            _bundle(entries=(), screen=GENERATING_SCREEN),                   # turn
            _bundle(entries=[USER_ENTRY, ASSISTANT_ENTRY], screen=IDLE_SCREEN),
            _bundle(entries=(), screen=GENERATING_SCREEN),                   # ai-title
            _bundle(entries=(), screen=IDLE_SCREEN),                         # settle
        ])
        d = _mk_driver(br)                 # _last_state="idle"
        d._pending_turn = True             # the dashboard turn is outstanding
        events = asyncio.run(_cycles(monkeypatch, d, n=4))
        runnings = [e for e in events
                    if e["type"] == "status_change" and e["status"] == "running"]
        idles = [e for e in events
                 if e["type"] == "status_change" and e["status"] == "idle"]
        assert len(runnings) == 1, \
            "exactly one running — the post-turn ai-title spinner emits none"
        # One completion idle (the turn) + one harmless settle idle (post-title);
        # the settle carries no _was_running, so handle_event completes nothing.
        assert len(idles) == 2
        assert d._pending_turn is False

    def test_reconciled_idle_drives_side_effects_exactly_once(self):
        # End-to-end: the backstop-emitted idle, fed to a synthetically-running
        # session (as _flush_queue leaves it), must bump the turn count and raise
        # ONE §7.8 response card — and a second idle poll must not double either.
        import main
        import inbox
        from main import SessionState
        inbox.reset()
        try:
            s = SessionState(
                session_id="recon-1", agent_type=None, model=None,
                permission_mode="default", cwd=None, system_prompt=None,
                driver_name="bridge",
            )
            # _flush_queue's synthetic running-set (pushed running event sets
            # _was_running; status is forced to running before the await send).
            s.status = "running"
            s._was_running = True

            def _idle():
                return {"type": "status_change", "status": "idle",
                        "timestamp": datetime_now_iso()}

            s.handle_event(_idle())
            assert s.status == "idle"
            assert s.turn_count == 1
            assert s.total_turns == 1     # surfaced on the API for bridge agents
            cards = [it for it in inbox.items_for("recon-1")
                     if it["type"] == "response"]
            assert len(cards) == 1 and cards[0]["data"]["runs"] == 1

            # A second idle (stray re-read) must not double-count the turn nor
            # re-raise the card — the _was_running guard blocks it.
            s.handle_event(_idle())
            assert s.turn_count == 1
            assert s.total_turns == 1
            cards = [it for it in inbox.items_for("recon-1")
                     if it["type"] == "response"]
            assert len(cards) == 1 and cards[0]["data"]["runs"] == 1
        finally:
            inbox.reset()


def datetime_now_iso():
    from datetime import datetime
    return datetime.now().isoformat()
