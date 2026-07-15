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
        # Pre-idle the cadence so the nudge is observable.
        d._cadence._last_activity -= 1000
        assert d._cadence.interval() == 5.0
        events = asyncio.run(_cycles(monkeypatch, d, n=1))
        assert events[-1]["type"] == "status_change"
        assert events[-1]["status"] == "running"
        assert d._cadence.interval() == 1.0, "activity must snap the cadence"

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
