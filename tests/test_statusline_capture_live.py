r"""LIVE acceptance — per-turn statusLine capture (§7.18 source 2, §11 #31).

The spike (``test_usage_context_sources_live`` #18) proved the SOURCE: a
configured statusLine command receives a JSON payload per render, carrying a
numeric ``context_window`` — a PER-TURN snapshot, not a continuous mid-run
feed. This file proves the BUILD: the bridge driver's materialized per-agent
settings now install that capture for EVERY agent (appending each payload to
``~/.awl-cc-dash-agents/<name>/statusline.jsonl``), the file actually grows as
the TUI renders, and ``get_statusline_snapshot()`` reads the last payload back.

Records the payload's actual field inventory on THIS build in
``tests/log/statusline_capture_findings_latest.txt`` — including, honestly,
whether ``context_window`` is present (if the build dropped it, the plumbing
still ships whatever fields exist, per the §11 #31 contract).

Driver-level (no sidecar): the same BridgeDriver start path the sidecar uses,
so the capture rides the REAL materialized settings. Tolerant of a logged-out
WSL claude — the statusLine renders regardless of auth.

ISOLATION (parallel-safe): own ``TmuxBridge()`` for read-back (never
conftest's kill-server fixture); unique ``slcap-<uuid8>`` names; own throwaway
WSL dir; closes ONLY its own session; never ``tmux kill-server``; tab-less.

Run (single file, isolation)::

    .\.venv\Scripts\python.exe -m pytest tests\test_statusline_capture_live.py -x -q
"""

from __future__ import annotations

import asyncio
import datetime
import json
import logging
import sys
import time
import uuid
from pathlib import Path

import pytest

pytestmark = [pytest.mark.integration, pytest.mark.slow]

_REPO_ROOT = Path(__file__).resolve().parent.parent
_SIDECAR = _REPO_ROOT / "sidecar"
for _p in (_REPO_ROOT, _SIDECAR):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from drivers.bridge import BridgeDriver  # noqa: E402
from drivers.base import DriverConfig  # noqa: E402
from bridge import TmuxBridge  # noqa: E402
from bridge.paths import WSL_AWL_DIR  # noqa: E402

log = logging.getLogger("tests.statusline_capture")

SLUG = "slcap"
LOG_DIR = Path(__file__).parent / "log"


@pytest.fixture(autouse=True)
def _runtime_to_tmp(tmp_path, monkeypatch):
    """Keep restart-survival records out of sidecar/runtime/ during tests."""
    monkeypatch.setenv("AWL_SIDECAR_RUNTIME", str(tmp_path / "runtime"))


@pytest.fixture
def shell_bridge():
    return TmuxBridge()


@pytest.fixture
def diag_dir(shell_bridge):
    path = f"/home/lester/awl-{SLUG}-{uuid.uuid4().hex[:8]}"
    shell_bridge._run(f"mkdir -p {path}")
    yield path
    shell_bridge._run(f"rm -rf {path}")


def _line_count(bridge: TmuxBridge, path: str) -> int:
    try:
        out = bridge._run(f"wc -l < '{path}' 2>/dev/null || echo 0", timeout=10)
        return int(out.strip().split()[-1])
    except Exception:
        return 0


def _find_ctx_window(payload):
    """Locate a context_window-ish object anywhere in the payload (the spike's
    tolerant scan, so a nesting change on a future build is still found)."""
    if not isinstance(payload, dict):
        return None
    cw = payload.get("context_window")
    if isinstance(cw, dict) and (
            "context_window_size" in cw or "used_percentage" in cw):
        return cw
    found = []

    def walk(o):
        if isinstance(o, dict):
            if "context_window_size" in o or "used_percentage" in o:
                found.append(o)
            for v in o.values():
                walk(v)
        elif isinstance(o, list):
            for v in o:
                walk(v)

    walk(payload)
    return found[0] if found else None


def _write_findings(text: str) -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    (LOG_DIR / f"statusline_capture_findings_{stamp}.txt").write_text(
        text, encoding="utf-8")
    (LOG_DIR / "statusline_capture_findings_latest.txt").write_text(
        text, encoding="utf-8")


def test_statusline_capture_live(shell_bridge, diag_dir):
    """Start a REAL BridgeDriver agent (its materialized settings install the
    capture), watch the per-agent statusline.jsonl appear and grow, and read
    the snapshot back through the driver."""

    async def flow():
        findings: list[str] = [
            "Per-turn statusLine capture — live acceptance (§11 #31)",
            f"Date: {datetime.datetime.now().isoformat(timespec='seconds')}",
        ]
        events: list[dict] = []
        sid = f"{SLUG}-{uuid.uuid4().hex[:8]}"
        driver = BridgeDriver(
            DriverConfig(cwd=diag_dir, permission_mode="default"),
            events.append,
            session_id=sid,
        )
        driver._name = sid  # slug-prefixed, unique tmux session name
        await driver.start()  # tab-less; settings include the capture command
        capture_path = f"{WSL_AWL_DIR}/{sid}/statusline.jsonl"
        try:
            # (1) The capture file appears once the TUI renders its status bar.
            n0 = 0
            for _ in range(30):
                n0 = _line_count(shell_bridge, capture_path)
                if n0 > 0:
                    break
                await asyncio.sleep(1.0)
            assert n0 > 0, (
                f"statusLine capture file never appeared at {capture_path} — "
                "the statusLine command did not fire on this build")
            findings.append(f"capture file live: {capture_path} ({n0} renders "
                            "at idle)")

            # (2) A send makes it GROW (renders fire around the turn — works
            # logged-out too: the error reply still repaints the status bar).
            await driver.send("Reply with exactly: SL-OK")
            grew = False
            n1 = n0
            for _ in range(60):
                await asyncio.sleep(1.0)
                n1 = _line_count(shell_bridge, capture_path)
                if n1 > n0:
                    grew = True
                    break
            findings.append(f"renders before send={n0}, after={n1}, grew={grew}")
            assert grew, "statusLine capture never grew across a send"

            # (3) The driver reads the LAST payload back (the lazy tail).
            snap = await driver.get_statusline_snapshot()
            assert isinstance(snap, dict) and snap, (
                "get_statusline_snapshot returned nothing despite a live "
                f"capture file (tail unparseable?): {snap!r}")
            findings.append(f"payload top-level fields: {sorted(snap.keys())}")

            # (4) The honest context_window verdict for THIS build.
            cw = _find_ctx_window(snap)
            if cw is not None:
                findings.append(
                    f"context_window PRESENT: {json.dumps(cw)[:400]}")
                size = cw.get("context_window_size")
                assert isinstance(size, (int, float)) and size > 0, cw
            else:
                findings.append(
                    "context_window ABSENT on this build — the capture ships "
                    f"whatever fields exist (per_turn = {sorted(snap.keys())}); "
                    "recorded honestly per the §11 #31 contract.")
            _write_findings("\n".join(findings) + "\n")
        finally:
            await driver.close()  # kills ONLY this session; never kill-server

    asyncio.run(flow())
