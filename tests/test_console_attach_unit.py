"""Hermetic unit tests — Console streaming attach, backend half (§7.13, §11 #29).

The decided contract this file encodes:

  * The Console's live terminal is a per-focused-agent **ttyd attached to the
    agent's tmux session**, consumed over a WebSocket from Windows (localhost —
    WSL2's default relay; spike-proven, ``test_console_stream_attach_live``).
  * **Geometry is pinned FIRST** (``window-size manual``) — the required
    coexistence fix: under the default ``window-size latest`` a live viewer
    resizes the pane and the change persists after detach, perturbing the
    sidecar's capture-pane reads. The pin must land BEFORE ttyd starts, and
    detach deliberately leaves it in place.
  * **One attach per session** — while the previous ttyd is alive a re-attach
    returns the existing one (``reused: True``), never a second server.
  * Ports come from ``CONSOLE_PORT_RANGE`` via the pure ``pick_console_port``
    (``ss -ltn`` occupancy + in-process allocations; ``None`` when exhausted).
  * The sidecar surface is ``POST /sessions/{id}/console/attach`` →
    ``{ws_url, url, port, reused}`` and ``POST /sessions/{id}/console/detach``
    (idempotent); both 404 an unknown session and 400 a non-bridge driver.
    Attach-on-open/detach-on-close is the FRONTEND's duty; interception stays
    on the JSONL transcript (§7.13) — the backend only serves the contract.

No WSL, no tmux, no ttyd — scripted fakes throughout. The live proof (real
ttyd, real WebSocket bytes, coexistence under the poller) is
``test_console_attach_endpoint_live.py``.
"""

import asyncio
import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))
_SIDECAR = _REPO_ROOT / "sidecar"
if str(_SIDECAR) not in sys.path:
    sys.path.insert(0, str(_SIDECAR))

from fastapi import HTTPException  # noqa: E402

import main  # noqa: E402
from main import SessionState  # noqa: E402
from bridge.bridge import (  # noqa: E402
    CONSOLE_PORT_RANGE, TmuxBridge, TmuxBridgeError, pick_console_port,
)


# -----------------------------------------------------------------------------
# pick_console_port — pure port selection
# -----------------------------------------------------------------------------

_SS_SAMPLE = (
    "State  Recv-Q Send-Q Local Address:Port  Peer Address:Port\n"
    "LISTEN 0      128    0.0.0.0:7690        0.0.0.0:*\n"
    "LISTEN 0      128    [::]:7710           [::]:*\n"
    "LISTEN 0      128    127.0.0.1:7711      0.0.0.0:*\n"
)


class TestPickConsolePort:
    def test_skips_ss_occupied_ports(self):
        assert pick_console_port(_SS_SAMPLE) == 7712

    def test_skips_in_process_taken_ports(self):
        assert pick_console_port(_SS_SAMPLE, taken={7712, 7713}) == 7714

    def test_empty_listing_starts_at_range_start(self):
        assert pick_console_port("") == CONSOLE_PORT_RANGE[0]
        assert pick_console_port(None) == CONSOLE_PORT_RANGE[0]

    def test_exhausted_range_returns_none(self):
        lo, hi = CONSOLE_PORT_RANGE
        assert pick_console_port("", taken=set(range(lo, hi + 1))) is None

    def test_explicit_small_range(self):
        assert pick_console_port("x:9000 ", start=9000, end=9001) == 9001
        assert pick_console_port("x:9000 x:9001 ", start=9000, end=9001) is None


# -----------------------------------------------------------------------------
# TmuxBridge.console_attach / console_detach — scripted WSL surface
# -----------------------------------------------------------------------------

def _scripted_bridge(monkeypatch, *, ttyd="/home/u/.local/bin/ttyd",
                     start_result="ALIVE", pid_alive=True):
    """A TmuxBridge whose _run is a script recorder answering the exact command
    shapes console_attach issues (session check, ttyd resolve, pin, ss scan,
    script write, script run, pidfile read, kill -0)."""
    b = TmuxBridge()
    calls: list[str] = []

    def fake_run(cmd, timeout=30, stdin_data=None):
        calls.append(cmd)
        if cmd.startswith("tmux list-sessions"):
            return "agent-x|123|0|42|1"
        if cmd.startswith("cd ~"):
            return "/home/u"
        if "command -v ttyd" in cmd or "-x /home/u/.local/bin/ttyd" in cmd:
            return ttyd or "NO"
        if cmd.startswith("ss -ltn"):
            return "LISTEN 0 128 0.0.0.0:7710 0.0.0.0:*"
        if "console_attach.sh" in cmd and cmd.startswith("bash "):
            return start_result
        if cmd.startswith("cat ") and "ttyd_console.pid" in cmd:
            return "4242"
        if cmd.startswith("kill -0"):
            return "ALIVE" if pid_alive else "DEAD"
        return ""

    monkeypatch.setattr(b, "_run", fake_run)
    return b, calls


class TestConsoleAttach:
    def test_attach_pins_geometry_before_ttyd_starts(self, monkeypatch):
        b, calls = _scripted_bridge(monkeypatch)
        info = b.console_attach("agent-x")
        pin_idx = next(i for i, c in enumerate(calls)
                       if "window-size manual" in c)
        start_idx = next(i for i, c in enumerate(calls)
                         if c.startswith("bash ") and "console_attach.sh" in c)
        assert pin_idx < start_idx, "geometry must be pinned BEFORE ttyd starts"
        # 7710 occupied in the fake ss listing -> first free is 7711.
        assert info["port"] == 7711
        assert info["ws_url"] == "ws://127.0.0.1:7711/ws"
        assert info["url"] == "http://127.0.0.1:7711/"
        assert info["pid"] == 4242
        assert info["reused"] is False

    def test_attach_script_is_writable_ttyd_on_the_session(self, monkeypatch):
        b, calls = _scripted_bridge(monkeypatch)
        b.console_attach("agent-x")
        write = next(c for c in calls if "console_attach.sh" in c
                     and "base64 -d" in c)
        import base64 as b64mod
        import re as remod
        payload = b64mod.b64decode(
            remod.search(r"echo (\S+) \| base64 -d", write).group(1)).decode()
        assert "-W" in payload, "ttyd must be writable (keystroke passthrough)"
        assert "tmux attach -t agent-x" in payload
        assert "setsid nohup" in payload, "detached-start pattern required"

    def test_reattach_returns_existing_attach(self, monkeypatch):
        b, calls = _scripted_bridge(monkeypatch, pid_alive=True)
        first = b.console_attach("agent-x")
        n_calls = len(calls)
        second = b.console_attach("agent-x")
        assert second["port"] == first["port"]
        assert second["reused"] is True
        # Only the session check + pid liveness probe — no new ttyd start.
        assert not any("console_attach.sh" in c for c in calls[n_calls:])

    def test_dead_previous_attach_is_replaced(self, monkeypatch):
        b, calls = _scripted_bridge(monkeypatch, pid_alive=False)
        b._console_attaches["agent-x"] = {"port": 7750, "pid": 9999}
        info = b.console_attach("agent-x")
        assert info["reused"] is False
        assert any(c.startswith("bash ") and "console_attach.sh" in c
                   for c in calls)

    def test_missing_ttyd_raises(self, monkeypatch):
        b, _ = _scripted_bridge(monkeypatch, ttyd="NO")
        with pytest.raises(TmuxBridgeError, match="ttyd is not installed"):
            b.console_attach("agent-x")

    def test_dead_start_raises(self, monkeypatch):
        b, _ = _scripted_bridge(monkeypatch, start_result="DEAD")
        with pytest.raises(TmuxBridgeError, match="did not start"):
            b.console_attach("agent-x")
        assert "agent-x" not in b._console_attaches

    def test_detach_kills_and_forgets_and_is_idempotent(self, monkeypatch):
        b, calls = _scripted_bridge(monkeypatch)
        b.console_attach("agent-x")
        out = b.console_detach("agent-x")
        assert out == {"status": "detached", "name": "agent-x", "port": 7711}
        assert "agent-x" not in b._console_attaches
        assert any("ttyd_console.pid" in c and "kill" in c for c in calls)
        # Idempotent: no tracked attach -> still a detached success, port None.
        again = b.console_detach("agent-x")
        assert again == {"status": "detached", "name": "agent-x", "port": None}

    def test_detach_leaves_geometry_pinned(self, monkeypatch):
        # The pin is the §7.13 required protection — detach must NOT restore
        # `window-size latest` (a viewer-resize under latest persists).
        b, calls = _scripted_bridge(monkeypatch)
        b.console_attach("agent-x")
        n = len(calls)
        b.console_detach("agent-x")
        assert not any("window-size" in c for c in calls[n:])

    def test_close_detaches_the_console_first(self, monkeypatch):
        b, calls = _scripted_bridge(monkeypatch)
        b.console_attach("agent-x")
        b.close("agent-x")
        kill_idx = next(i for i, c in enumerate(calls)
                        if "ttyd_console.pid" in c and "kill" in c)
        session_kill_idx = next(i for i, c in enumerate(calls)
                                if "kill-session" in c)
        assert kill_idx < session_kill_idx
        assert "agent-x" not in b._console_attaches


# -----------------------------------------------------------------------------
# Sidecar endpoint wiring — fake driver/bridge
# -----------------------------------------------------------------------------

class _FakeConsoleBridge:
    def __init__(self, fail=False):
        self.fail = fail
        self.attach_calls: list[str] = []
        self.detach_calls: list[str] = []

    def console_attach(self, name, port=None):
        self.attach_calls.append(name)
        if self.fail:
            raise RuntimeError("boom")
        return {"port": 7711, "pid": 4242, "url": "http://127.0.0.1:7711/",
                "ws_url": "ws://127.0.0.1:7711/ws", "reused": False}

    def console_detach(self, name):
        self.detach_calls.append(name)
        return {"status": "detached", "name": name, "port": 7711}


class _FakeBridgeDriver:
    """Bridge-shaped driver: has both _bridge and tmux_name."""

    def __init__(self, fail=False):
        self._bridge = _FakeConsoleBridge(fail=fail)
        self.tmux_name = "awl-fake"


class _NonBridgeDriver:
    """SDK-shaped driver: no _bridge/tmux_name — the Console must 400."""


def _register(driver):
    s = SessionState(
        session_id="s1", agent_type=None, model=None,
        permission_mode="default", cwd=None, system_prompt=None,
        driver_name="bridge",
    )
    s.driver = driver
    main.sessions["s1"] = s
    return s


class TestConsoleAttachEndpoints:
    def teardown_method(self):
        main.sessions.pop("s1", None)

    def test_attach_returns_ws_contract(self):
        s = _register(_FakeBridgeDriver())
        out = asyncio.run(main.console_attach_endpoint("s1"))
        assert out == {"ws_url": "ws://127.0.0.1:7711/ws",
                       "url": "http://127.0.0.1:7711/",
                       "port": 7711, "reused": False}
        assert s.driver._bridge.attach_calls == ["awl-fake"]

    def test_detach_wires_through(self):
        s = _register(_FakeBridgeDriver())
        out = asyncio.run(main.console_detach_endpoint("s1"))
        assert out == {"status": "detached", "port": 7711}
        assert s.driver._bridge.detach_calls == ["awl-fake"]

    def test_unknown_session_404(self):
        with pytest.raises(HTTPException) as ei:
            asyncio.run(main.console_attach_endpoint("nope"))
        assert ei.value.status_code == 404

    def test_non_bridge_driver_400(self):
        _register(_NonBridgeDriver())
        with pytest.raises(HTTPException) as ei:
            asyncio.run(main.console_attach_endpoint("s1"))
        assert ei.value.status_code == 400
        with pytest.raises(HTTPException) as ei:
            asyncio.run(main.console_detach_endpoint("s1"))
        assert ei.value.status_code == 400

    def test_bridge_failure_maps_to_500(self):
        _register(_FakeBridgeDriver(fail=True))
        with pytest.raises(HTTPException) as ei:
            asyncio.run(main.console_attach_endpoint("s1"))
        assert ei.value.status_code == 500
        assert "console attach failed" in ei.value.detail
