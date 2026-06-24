"""Live round-trips for the bridge backend finisher.

Real Claude Code TUI sessions in WSL2/tmux, one at a time in a clean throwaway
dir, in DEFAULT prompting mode (so permission prompts actually appear). Covers
the MUST-land pieces — the permission round-trip (a distinct `permission_request`
event sets the pending flag; approve and deny both work via the proven keys) and
restart survival (a fresh driver resumes a live tmux session with history intact)
— plus the SHOULD-land controls confirmed live (model, effort).

These drive the `BridgeDriver` directly (no HTTP layer): the real risk lives in
the driver + bridge, and the POST endpoints are thin wrappers over the driver
methods exercised here.

Run::

    pytest tests/test_bridge_finisher_live.py -m integration   # from repo root
"""

import asyncio
import logging
import os
import sys
import uuid
from pathlib import Path

import pytest

# Make the sidecar's modules importable as top-level (it runs with its own dir on
# sys.path, not the repo root).
_REPO_ROOT = Path(__file__).resolve().parent.parent
_SIDECAR = _REPO_ROOT / "sidecar"
if str(_SIDECAR) not in sys.path:
    sys.path.insert(0, str(_SIDECAR))

from drivers.bridge import BridgeDriver  # noqa: E402
from drivers.base import DriverConfig  # noqa: E402

log = logging.getLogger("tests.bridge_finisher")

pytestmark = [pytest.mark.integration, pytest.mark.slow]


@pytest.fixture(autouse=True)
def _runtime_to_tmp(tmp_path, monkeypatch):
    """Keep restart-survival records out of sidecar/runtime/ during tests."""
    monkeypatch.setenv("AWL_SIDECAR_RUNTIME", str(tmp_path / "runtime"))


@pytest.fixture
def diag_dir(bridge):
    """A fresh, empty WSL throwaway dir; removed after the test."""
    path = f"/home/lester/awl-fin-{uuid.uuid4().hex[:8]}"
    bridge._run(f"mkdir -p {path}")
    yield path
    bridge._run(f"rm -rf {path}")


class _Driven:
    """Run a BridgeDriver, mirror the sidecar's event handling into a pending
    flag, and expose helpers — so a test reads like the sidecar would behave."""

    def __init__(self, diag, session_id):
        self.events: list[dict] = []
        self.pending = None
        self.driver = BridgeDriver(
            DriverConfig(cwd=diag, permission_mode="default"),
            self.events.append,
            session_id=session_id,
        )
        self._task = None

    async def start(self):
        await self.driver.start()
        self._task = asyncio.create_task(self._consume())

    async def _consume(self):
        async for e in self.driver.events():
            self.events.append(e)
            if e["type"] == "permission_request":
                self.pending = e.get("data")
            elif e["type"] == "permission_resolved":
                self.pending = None

    async def wait_pending(self, timeout=70):
        for _ in range(int(timeout * 2)):
            if self.pending is not None:
                return self.pending
            await asyncio.sleep(0.5)
        return None

    async def wait_cleared(self, timeout=60):
        for _ in range(int(timeout * 2)):
            if self.pending is None:
                return True
            await asyncio.sleep(0.5)
        return False

    async def close(self):
        if self._task:
            self._task.cancel()
        await self.driver.close()


def _cat(bridge, path):
    return bridge._run(f"cat {path} 2>/dev/null || echo __MISSING__")


# -----------------------------------------------------------------------------
# Permission round-trip
# -----------------------------------------------------------------------------

def test_permission_approve(bridge, diag_dir):
    """A write prompt raises a permission_request (pending flag set); approving
    via Enter writes the file."""
    async def flow():
        d = _Driven(diag_dir, "t-approve")
        await d.start()
        try:
            await d.driver.send(
                "Create a file named approve.txt containing exactly the word "
                "banana. Use the Write tool. Do not do anything else."
            )
            detail = await d.wait_pending()
            assert detail is not None, "no permission_request event arrived"
            log.debug("approve detail: %s", detail)
            # The parsed detail carries the question and a numbered Yes option.
            assert "approve.txt" in (detail.get("question") or "")
            assert any(o["index"] == 1 and o["label"].lower().startswith("yes")
                       for o in detail.get("options", []))

            await d.driver.answer_permission(True)
            assert await d.wait_cleared(), "pending flag never cleared after approve"
            # Give the write a moment to land.
            for _ in range(40):
                if _cat(bridge, f"{diag_dir}/approve.txt") == "banana":
                    break
                await asyncio.sleep(0.5)
            assert _cat(bridge, f"{diag_dir}/approve.txt") == "banana"
        finally:
            await d.close()

    asyncio.run(flow())


def test_permission_deny(bridge, diag_dir):
    """Denying via Escape rejects the action; the file is never written."""
    async def flow():
        d = _Driven(diag_dir, "t-deny")
        await d.start()
        try:
            await d.driver.send(
                "Create a file named deny.txt containing exactly the word "
                "cherry. Use the Write tool. Do not do anything else."
            )
            detail = await d.wait_pending()
            assert detail is not None, "no permission_request event arrived"

            await d.driver.answer_permission(False)
            assert await d.wait_cleared(), "pending flag never cleared after deny"
            await asyncio.sleep(3)
            assert _cat(bridge, f"{diag_dir}/deny.txt") == "__MISSING__"
        finally:
            await d.close()

    asyncio.run(flow())


# -----------------------------------------------------------------------------
# Restart survival
# -----------------------------------------------------------------------------

def test_resume_after_simulated_restart(bridge, diag_dir):
    """A turn's history survives a sidecar 'restart': a fresh driver bound to the
    same tmux session by name reconnects, and the transcript history replays."""
    async def flow():
        first = BridgeDriver(
            DriverConfig(cwd=diag_dir, permission_mode="default"),
            lambda e: None, session_id="t-resume",
        )
        await first.start()
        tmux_name = first.tmux_name
        await _send_marker_and_wait(first)  # real transcript history to resume

        # Simulate a sidecar restart: brand-new driver, resume the same session.
        replayed: list[dict] = []
        second = BridgeDriver(
            DriverConfig(cwd=diag_dir, permission_mode="default"),
            replayed.append, resume_name=tmux_name, session_id="t-resume",
        )
        try:
            await second.start()  # resume() path — rebinds, does not recreate
            usage = await second.get_context_usage()
            log.debug("resumed usage: %s", usage)
            assert usage is not None and usage["turns"] >= 1, \
                "resumed session lost its turn history"

            # The event pump replays the transcript into the fresh driver.
            task = asyncio.create_task(_drain(second, replayed))
            for _ in range(40):
                if any(e["type"] == "assistant" for e in replayed):
                    break
                await asyncio.sleep(0.5)
            task.cancel()
            assert any(e["type"] == "assistant" for e in replayed), \
                "resumed driver did not replay transcript history"
        finally:
            await second.close()  # kills the shared tmux session once

    asyncio.run(flow())


async def _drain(driver, sink):
    async for e in driver.events():
        sink.append(e)


async def _send_marker_and_wait(driver):
    """Send a marker prompt and wait for it to land in the transcript, so the
    resume target has real history to restore."""
    await driver.send("Reply with exactly: RESUME_OK")
    for _ in range(120):
        try:
            entries = await asyncio.to_thread(
                driver._bridge.read_log, driver.tmux_name
            )
        except Exception:
            entries = []
        if any(
            e.get("type") == "assistant"
            and "RESUME_OK" in str((e.get("message") or {}).get("content"))
            for e in entries
        ):
            return
        await asyncio.sleep(0.5)


# -----------------------------------------------------------------------------
# Session-control commands confirmed live (SHOULD-land)
# -----------------------------------------------------------------------------

def test_set_model_and_effort_take(bridge, diag_dir):
    """/model and /effort drive the live session and the change is reflected on
    screen ("Set model to …" / "Set effort level to …")."""
    async def flow():
        d = _Driven(diag_dir, "t-control")
        await d.start()
        try:
            assert d.driver.supports("set_model")
            assert d.driver.supports("set_effort")

            await d.driver.set_effort("low")
            await asyncio.sleep(3)
            scr = bridge.read(d.driver.tmux_name, lines=30)["content"]
            assert "effort" in scr.lower() and "low" in scr.lower(), scr[-400:]

            await d.driver.set_model("sonnet")
            await asyncio.sleep(3)
            scr = bridge.scrollback(d.driver.tmux_name, max_lines=120)["content"]
            assert "Set model to" in scr, scr[-400:]
        finally:
            await d.close()

    asyncio.run(flow())
