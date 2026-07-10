"""Live integration — the WIRED mode/thinking/fast controls (§11 #12).

Contract this file pins (the decided behavior): the *production driver path* —
``BridgeDriver.set_mode / set_thinking / set_fast``, the same methods
``POST /sessions/{id}/{mode,thinking,fast}`` call — drives a real running
Claude Code TUI through the proven ``keys()`` levers and returns the READ-BACK
state, never an echo of the request:

  * **permission mode** — cycles Shift+Tab (``BTab``) at a known-idle screen,
    bounded at the ring size + 1, reading the resulting mode back from the
    status line (``bridge.set_permission_mode``). This test cycles
    ``default → acceptEdits`` and verifies the read-back both from the driver's
    return value AND independently off the live status line.
  * **thinking** — the ``Meta+T`` modal: current state read FIRST (the ✔
    option), toggled only if needed, result read back
    (``bridge.set_thinking``). This test flips on → read-back → off, then
    restores the state it found.
  * **fast** — the ``Meta+O`` panel + ``Space``: a real toggle on a credited
    account, or the HONEST degrade ``RuntimeError("credit_gated")`` on an
    account without Fast usage credits. This test accepts EITHER outcome and
    asserts its shape — it never requires credits, and if it does toggle Fast
    on it always toggles it back OFF before teardown.

DISTINCT FROM the three proving spikes (test_permission_mode_cycle_live,
test_thinking_toggle_live, test_fast_mode_toggle_live): those drove raw
``keys()`` sequences to establish feasibility; this drives the WIRED
driver/bridge methods that production traffic uses, so it is standing
regression protection for §11 #12, not evidence-generation.

Parallel-safe isolation (CRITICAL — sibling agents may run their own live
sessions concurrently):
  * ONE new file only; ONE tab-less session. The driver's tmux name is the
    unique ``awl-<uuid8>``; the sidecar session id is slug-prefixed
    ``modectl-<uuid8>``; the WSL diag dir is ``awl-modectl-<uuid8>``.
  * NEVER ``tmux kill-server`` / ``bridge.shutdown()`` — tear down ONLY this
    session via ``driver.close()`` (+ belt-and-suspenders ``bridge.close``) and
    ``rm -rf`` this test's own diag dir.
  * Does NOT use conftest's ``bridge`` fixture (its setup AND teardown call
    ``_kill_all_tmux()`` = ``tmux kill-server``, which would kill siblings). We
    instantiate our OWN ``TmuxBridge()`` for WSL shell helpers and read-backs.
  * ``show=False`` throughout — no Windows Terminal tab ever opens.

Run (PowerShell)::

    ./.venv/Scripts/python.exe -m pytest tests/test_mode_control_wired_live.py -m integration
"""

import asyncio
import logging
import sys
import uuid
from pathlib import Path

import pytest

# Make the sidecar's modules importable as top-level (it runs with its own dir
# on sys.path, not the repo root), and the repo-root `bridge` package for our
# own TmuxBridge (read-backs + WSL shell helpers).
_REPO_ROOT = Path(__file__).resolve().parent.parent
_SIDECAR = _REPO_ROOT / "sidecar"
if str(_SIDECAR) not in sys.path:
    sys.path.insert(0, str(_SIDECAR))
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from drivers.bridge import BridgeDriver  # noqa: E402
from drivers.base import DriverConfig  # noqa: E402
from bridge import TmuxBridge  # noqa: E402

log = logging.getLogger(__name__)

pytestmark = [pytest.mark.integration, pytest.mark.slow]


@pytest.fixture(autouse=True)
def _runtime_to_tmp(tmp_path, monkeypatch):
    """Keep the driver's restart-survival record out of sidecar/runtime/."""
    monkeypatch.setenv("AWL_SIDECAR_RUNTIME", str(tmp_path / "runtime"))


def test_mode_thinking_fast_wired_live():
    """One tab-less session; all three wired levers driven through the
    production BridgeDriver path with independent status-line/panel read-backs.
    Fast accepts either a real toggle or the credit-gate honest degrade."""
    bridge = TmuxBridge()
    diag = f"/home/lester/awl-modectl-{uuid.uuid4().hex[:8]}"
    bridge._run(f"mkdir -p {diag}")
    events: list[dict] = []

    async def flow():
        driver = BridgeDriver(
            DriverConfig(cwd=diag, permission_mode="default"),
            events.append,
            session_id=f"modectl-{uuid.uuid4().hex[:8]}",
        )
        name = None
        try:
            await driver.start()
            name = driver.tmux_name
            log.debug("driver.tmux_name=%s (unique awl-<uuid8>)", name)
            # The wired capabilities are advertised (the endpoints gate on this).
            for cap in ("set_mode", "set_thinking", "set_fast"):
                assert driver.supports(cap), f"capability {cap!r} not advertised"
            await asyncio.sleep(3)  # let the TUI finish painting

            # --- Lever 1: permission mode default -> acceptEdits, read back ---
            start_mode = bridge.permission_mode(name)
            log.debug("start mode read-back: %s", start_mode)
            assert start_mode == "default", (
                f"session launched with --permission-mode default did not read "
                f"back as default (got {start_mode!r})"
            )
            got_mode = await driver.set_mode("acceptEdits")
            assert got_mode == "acceptEdits", (
                f"driver.set_mode('acceptEdits') read back {got_mode!r}"
            )
            # Independent read-back off the live status line (never trust only
            # the return value).
            live_mode = bridge.permission_mode(name)
            log.debug("post-set_mode status-line read-back: %s", live_mode)
            assert live_mode == "acceptEdits"

            # --- Lever 2: thinking on -> read-back -> off (then restore) ---
            st0 = bridge.thinking_state(name)
            log.debug("thinking baseline: %s", st0)
            assert st0["ok"] and st0["on"] in (True, False), (
                f"thinking baseline unreadable: {st0}"
            )
            got_on = await driver.set_thinking(True)
            assert got_on is True, f"set_thinking(True) read back {got_on!r}"
            st1 = bridge.thinking_state(name)
            log.debug("thinking after set(True): %s", st1)
            assert st1 == {"ok": True, "on": True}
            got_off = await driver.set_thinking(False)
            assert got_off is False, f"set_thinking(False) read back {got_off!r}"
            st2 = bridge.thinking_state(name)
            log.debug("thinking after set(False): %s", st2)
            assert st2 == {"ok": True, "on": False}
            # Leave the session as found.
            await driver.set_thinking(bool(st0["on"]))

            # --- Lever 3: fast — real toggle OR the credit-gate honest degrade ---
            fast_verdict = None
            try:
                got_fast = await driver.set_fast(True)
            except RuntimeError as e:
                # The honest degrade: the shape is asserted, credits are NOT
                # required for this test to pass.
                assert str(e) == "credit_gated", (
                    f"set_fast failed with unexpected reason {e!r} (only "
                    "'credit_gated' is an acceptable failure here)"
                )
                fast_verdict = "credit_gated"
                log.debug("fast: credit-gated on this account — honest degrade OK")
            else:
                assert got_fast is True, f"set_fast(True) read back {got_fast!r}"
                fs = bridge.fast_state(name)
                log.debug("fast after set(True): %s", fs)
                assert fs == {"ok": True, "on": True}
                # NEVER leave Fast drawing credits.
                got_fast_off = await driver.set_fast(False)
                assert got_fast_off is False
                fast_verdict = "toggled"

            log.debug(
                "WIRED OK: mode default->acceptEdits read-back; thinking "
                "on->off read-back (restored to %s); fast=%s",
                st0["on"], fast_verdict,
            )
        finally:
            # Tear down ONLY this session + this test's own diag dir.
            try:
                await driver.close()
            except Exception as e:  # pragma: no cover - best effort
                log.debug("driver.close() failed: %s", e)
            if name:
                try:
                    bridge.close(name)
                except Exception as e:  # pragma: no cover - best effort
                    log.debug("bridge.close(%s) failed: %s", name, e)
            try:
                bridge._run(f"rm -rf {diag}")
            except Exception as e:  # pragma: no cover - best effort
                log.debug("rm -rf %s failed: %s", diag, e)

    asyncio.run(flow())
