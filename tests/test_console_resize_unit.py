"""Hermetic unit tests — Console resize endpoint, sidecar half (§7.13 geometry seam).

The decided contract this file encodes:

  * The console pane stays pinned (``window-size manual``); honoring a
    viewer's geometry is a DELIBERATE, sidecar-mediated act: ``POST
    /sessions/{id}/console/resize`` ``{cols, rows}`` →
    ``TmuxBridge.console_resize(name, cols, rows)`` (the bridge half issues
    ``tmux resize-window -x -y``, which keeps the manual pin by definition,
    and returns ``{ok, cols, rows}`` with the APPLIED values, or
    ``{ok: False, reason}``).
  * **Clamping is belt-and-braces**: the endpoint clamps to cols ∈ [60, 500],
    rows ∈ [15, 200] BEFORE the bridge call (the bridge clamps to the same
    bounds internally) — NARROW is the scraper-hostile direction, so the
    floor is the load-bearing guard.
  * The response carries the applied values; a bridge ``{ok: False, reason}``
    maps like the mode endpoint — ``busy`` → 409 (retryable), anything else →
    400; unknown session → 404; non-bridge driver → 400 (the Console is a
    bridge feature); a raising bridge → 500.

No WSL/tmux — a fake bridge object, following ``test_console_attach_unit.py``'s
endpoint-wiring patterns. The bridge-level resize behavior itself (the tmux
command shape + internal clamp) is pinned by the bridge unit tests, not here.
"""

import asyncio
import sys
from pathlib import Path

import pytest

_SIDECAR = Path(__file__).resolve().parent.parent / "sidecar"
if str(_SIDECAR) not in sys.path:
    sys.path.insert(0, str(_SIDECAR))

from fastapi import HTTPException  # noqa: E402

import main  # noqa: E402
from main import SessionState  # noqa: E402


class _FakeResizeBridge:
    """Echoes the applied geometry back (the bridge contract), or fails on cue."""

    def __init__(self, fail_reason=None, exc=None):
        self.fail_reason = fail_reason
        self.exc = exc
        self.calls: list[tuple[str, int, int]] = []

    def console_resize(self, name, cols, rows):
        self.calls.append((name, cols, rows))
        if self.exc is not None:
            raise self.exc
        if self.fail_reason is not None:
            return {"ok": False, "reason": self.fail_reason}
        return {"ok": True, "cols": cols, "rows": rows}


class _FakeBridgeDriver:
    """Bridge-shaped driver: has both _bridge and tmux_name."""

    def __init__(self, **kw):
        self._bridge = _FakeResizeBridge(**kw)
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


def _resize(cols, rows):
    return asyncio.run(main.console_resize_endpoint(
        "s1", main.ConsoleResizeRequest(cols=cols, rows=rows)))


class TestConsoleResizeEndpoint:
    def teardown_method(self):
        main.sessions.pop("s1", None)

    def test_happy_path_returns_applied_values(self):
        s = _register(_FakeBridgeDriver())
        out = _resize(120, 40)
        assert out == {"ok": True, "cols": 120, "rows": 40}
        assert s.driver._bridge.calls == [("awl-fake", 120, 40)]

    def test_unknown_session_404(self):
        with pytest.raises(HTTPException) as ei:
            asyncio.run(main.console_resize_endpoint(
                "nope", main.ConsoleResizeRequest(cols=100, rows=30)))
        assert ei.value.status_code == 404

    def test_non_bridge_driver_400(self):
        _register(_NonBridgeDriver())
        with pytest.raises(HTTPException) as ei:
            _resize(100, 30)
        assert ei.value.status_code == 400

    def test_clamps_to_floor_before_the_bridge_call(self):
        # 20x5 is scraper-hostile — the bridge must only ever see 60x15.
        s = _register(_FakeBridgeDriver())
        out = _resize(20, 5)
        assert s.driver._bridge.calls == [("awl-fake", 60, 15)]
        assert out == {"ok": True, "cols": 60, "rows": 15}

    def test_clamps_to_ceiling_before_the_bridge_call(self):
        s = _register(_FakeBridgeDriver())
        out = _resize(9000, 900)
        assert s.driver._bridge.calls == [("awl-fake", 500, 200)]
        assert out == {"ok": True, "cols": 500, "rows": 200}

    def test_bridge_busy_maps_to_409(self):
        _register(_FakeBridgeDriver(fail_reason="busy"))
        with pytest.raises(HTTPException) as ei:
            _resize(100, 30)
        assert ei.value.status_code == 409
        assert "busy" in ei.value.detail

    def test_bridge_other_failure_maps_to_400(self):
        _register(_FakeBridgeDriver(fail_reason="no such session"))
        with pytest.raises(HTTPException) as ei:
            _resize(100, 30)
        assert ei.value.status_code == 400
        assert "no such session" in ei.value.detail

    def test_raising_bridge_maps_to_500(self):
        _register(_FakeBridgeDriver(exc=RuntimeError("boom")))
        with pytest.raises(HTTPException) as ei:
            _resize(100, 30)
        assert ei.value.status_code == 500
        assert "console resize failed" in ei.value.detail
