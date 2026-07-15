r"""Load re-measure — the polling rework's cycle cost + event lag (§11 #34).

``test_polling_scale_ceiling_live`` measured the PRE-rework model: ~5 WSL
process spawns per agent per ~1 s cycle (``read_log`` = transcript re-resolve
+ ``cat``, plus a ``status`` capture), degrading from N=1 (~1.3 s/cycle;
~10 s event-lag by N=9). This file re-measures POST-rework, head-to-head on
the same hardware:

  (a) per-cycle WSL invocations + wall time — OLD (read_log+status) vs NEW
      (one ``poll_bundle``), per agent and as synchronized N-sweeps over the
      N ladder (1..N);
  (b) event lag — a marker appended to a transcript, timed until the bundled
      incremental read surfaces it in a realistic 1 s loop;
  (c) the projected sweep>1s crossing for both modes (linear fit — reported,
      never asserted), plus the adaptive-cadence idle arithmetic (a coasted
      fleet polls at N/5 spawns/s vs the old ~5N/s).

The deliverable is the measured table in
``tests/log/polling_rework_findings_latest.txt`` (+ stamped copy) — honest
numbers, whatever they are. Soft assertions only: the bundle must be ONE
invocation per cycle and strictly cheaper in spawns than the old pair.

Works logged-out: the priming turn's 'Login expired' reply still creates the
transcript; the measurement is pure plumbing.

ISOLATION (fleet spawner — run ALONE, same rules as the pollscale spike): own
``TmuxBridge()``; unique ``pollrw-<runid>-<i>`` names; own throwaway dir;
closes only its own sessions in a try/finally; NEVER ``tmux kill-server``;
tab-less; N capped via ``AWL_POLLREWORK_N`` (default 4).

Run (single file, alone)::

    .\.venv\Scripts\python.exe -m pytest tests\test_polling_rework_live.py -x -q
"""

from __future__ import annotations

import json
import logging
import os
import shlex
import statistics
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter

import pytest

pytestmark = [pytest.mark.integration, pytest.mark.slow]

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from bridge import TmuxBridge  # noqa: E402
from bridge.transcript import (  # noqa: E402
    consume_transcript_chunk, find_transcript,
)

log = logging.getLogger("tests.polling_rework")

LOG_DIR = Path(__file__).parent / "log"
N_AGENTS = int(os.environ.get("AWL_POLLREWORK_N", "4"))
K_REPS = int(os.environ.get("AWL_POLLREWORK_REPS", "6"))  # first is warm-up
PRIME_WAIT_S = 60.0


class _CountingBridge(TmuxBridge):
    """A TmuxBridge that counts every WSL process spawn (_run invocation)."""

    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)
        self.run_count = 0

    def _run(self, bash_cmd, timeout=30, stdin_data=None):
        self.run_count += 1
        return super()._run(bash_cmd, timeout=timeout, stdin_data=stdin_data)


def _median(xs):
    xs = [x for x in xs if x is not None]
    return statistics.median(xs) if xs else None


def _old_cycle(br: TmuxBridge, name: str):
    """The pre-rework events() cycle: read_log + status (separate spawns)."""
    try:
        br.read_log(name)
    except Exception:
        pass
    try:
        br.status(name)
    except Exception:
        pass


def _new_cycle(br: TmuxBridge, name: str, path: str, offset: int) -> int:
    """One post-rework cycle: a single poll_bundle; returns the new offset."""
    try:
        bundle = br.poll_bundle(name, path, offset)
    except Exception:
        return offset
    _entries, consumed = consume_transcript_chunk(bundle.get("chunk") or b"")
    return offset + consumed


def _measure_per_agent(br: _CountingBridge, name: str, path: str):
    """(old_spawns, old_ms_median, new_spawns, new_ms_median) for one agent."""
    old_ms = []
    old_spawns = None
    for i in range(K_REPS):
        c0, t0 = br.run_count, perf_counter()
        _old_cycle(br, name)
        dt = (perf_counter() - t0) * 1000.0
        if i:                       # drop the warm-up rep
            old_ms.append(dt)
        old_spawns = br.run_count - c0
    new_ms = []
    new_spawns = None
    offset = 0
    for i in range(K_REPS):
        c0, t0 = br.run_count, perf_counter()
        offset = _new_cycle(br, name, path, offset)
        dt = (perf_counter() - t0) * 1000.0
        if i:
            new_ms.append(dt)
        new_spawns = br.run_count - c0
    return old_spawns, _median(old_ms), new_spawns, _median(new_ms)


def _measure_sweep(br: TmuxBridge, names, paths, mode: str):
    """Median wall-ms for one synchronized sweep across all `names` (serial —
    the driver offloads to threads, but serial timing gives the raw per-cycle
    WORK, the O(N) quantity the thread pool must absorb)."""
    sweeps = []
    offsets = {n: 0 for n in names}
    for i in range(K_REPS):
        t0 = perf_counter()
        for n in names:
            if mode == "old":
                _old_cycle(br, n)
            else:
                offsets[n] = _new_cycle(br, n, paths[n], offsets[n])
        dt = (perf_counter() - t0) * 1000.0
        if i:
            sweeps.append(dt)
    return _median(sweeps)


def _event_lag(br: TmuxBridge, name: str, path: str) -> float | None:
    """Marker-to-observation lag through the bundled read at a 1 s cadence."""
    marker = uuid.uuid4().hex
    line = json.dumps({
        "type": "user", "uuid": marker,
        "timestamp": datetime.now().isoformat(),
        "message": {"content": f"POLLRW_MARKER_{marker}"},
    })
    # Catch up to the current tail first.
    offset = _new_cycle(br, name, path, 0)
    br._run(f"cat >> {shlex.quote(path)}", stdin_data=line + "\n")
    t0 = perf_counter()
    deadline = t0 + 15.0
    while perf_counter() < deadline:
        try:
            bundle = br.poll_bundle(name, path, offset)
        except Exception:
            time.sleep(1.0)
            continue
        entries, consumed = consume_transcript_chunk(bundle.get("chunk") or b"")
        offset += consumed
        if any(isinstance(e, dict) and e.get("uuid") == marker for e in entries):
            return (perf_counter() - t0) * 1000.0
        time.sleep(1.0)  # the nominal active cadence
    return None


def _project_crossing(points, threshold):
    pts = [(n, y) for n, y in points if y is not None]
    if len(pts) < 2:
        return None
    xs, ys = [p[0] for p in pts], [p[1] for p in pts]
    m = len(xs)
    sx, sy = sum(xs), sum(ys)
    sxx = sum(x * x for x in xs)
    sxy = sum(x * y for x, y in zip(xs, ys))
    denom = m * sxx - sx * sx
    if denom == 0:
        return None
    slope = (m * sxy - sx * sy) / denom
    if slope <= 0:
        return None
    intercept = (sy - slope * sx) / m
    return (threshold - intercept) / slope


def _fmt(x, unit=""):
    return "n/a" if x is None else f"{x:.1f}{unit}"


def test_polling_rework_remeasure():
    br = _CountingBridge()
    run_id = uuid.uuid4().hex[:8]
    diag = f"/home/lester/awl-pollrw-{run_id}"
    created: list[str] = []
    try:
        br._run(f"mkdir -p {shlex.quote(diag)}")
        for i in range(N_AGENTS):
            name = f"pollrw-{run_id}-{i}"
            try:
                br.create(name, cwd=diag, show=False)
                created.append(name)
            except Exception as e:
                log.warning("spawn stopped at %d agents: %s", len(created), e)
                break
        assert created, "could not spawn a single agent"

        # Prime: one send each so a transcript exists (a logged-out error
        # reply suffices — the file is what the measurement needs).
        for name in created:
            try:
                br.send(name, "Reply with only the word: READY")
            except Exception as e:
                log.warning("prime send failed for %s: %s", name, e)
        for name in created:
            try:
                br.wait_idle(name, timeout=PRIME_WAIT_S)
            except Exception:
                pass
        time.sleep(2)

        paths = {}
        for name in created:
            p = find_transcript(br, name)
            assert p, f"no transcript for {name} after priming"
            paths[name] = p

        # (a) Per-agent cycle cost, old vs new.
        name0 = created[0]
        old_spawns, old_ms, new_spawns, new_ms = _measure_per_agent(
            br, name0, paths[name0])

        # N-ladder sweeps for both modes.
        ladder = sorted({1, 2, max(1, len(created) // 2), len(created)})
        rows = []
        for n in ladder:
            names = created[:n]
            old_sweep = _measure_sweep(br, names, paths, "old")
            new_sweep = _measure_sweep(br, names, paths, "new")
            rows.append((n, old_sweep, new_sweep))

        # (b) Event lag through the bundled read.
        lag_ms = _event_lag(br, name0, paths[name0])

        # (c) Projections + cadence arithmetic.
        proj_old = _project_crossing([(n, o) for n, o, _ in rows], 1000.0)
        proj_new = _project_crossing([(n, w) for n, _, w in rows], 1000.0)
        n = len(created)

        lines = [
            "AWL polling rework — re-measured cycle cost + event lag (§11 #34)",
            f"  when:    {datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')}",
            f"  agents:  N={n} (AWL_POLLREWORK_N={N_AGENTS}); reps/probe={K_REPS - 1}",
            "",
            "  Per-agent cycle (one agent):",
            f"    OLD read_log+status : {old_spawns} WSL spawns/cycle, "
            f"median {_fmt(old_ms, ' ms')}",
            f"    NEW poll_bundle     : {new_spawns} WSL spawn/cycle,  "
            f"median {_fmt(new_ms, ' ms')}",
            "",
            "  Synchronized serial sweep (all N agents, median ms):",
            "    N | old_sweep_ms | new_sweep_ms",
        ]
        for nn, o, w in rows:
            lines.append(f"    {nn} | {_fmt(o):>12} | {_fmt(w):>12}")
        lines += [
            "",
            f"  Event lag (marker → bundled read, 1 s cadence): {_fmt(lag_ms, ' ms')}",
            f"  Projected serial sweep>1s crossing: old N≈{_fmt(proj_old)}, "
            f"new N≈{_fmt(proj_new)}",
            "  (the driver runs cycles CONCURRENTLY via the thread pool, so the",
            "   practical ceiling is higher than the serial projection — the",
            "   serial sweep is the raw O(N) work the pool must absorb)",
            "",
            "  Adaptive cadence (idle fleet): active = 1 spawn/agent/s;",
            f"  coasted (≥30 s idle) = 0.2 spawn/agent/s → an idle N={n} fleet",
            f"  costs {n / 5:.1f} spawns/s vs the old model's ~{5 * n} spawns/s",
            "  (hooks push activity, so the poll snaps back to 1 s on demand).",
        ]
        text = "\n".join(lines) + "\n"
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        (LOG_DIR / f"polling_rework_findings_{stamp}.txt").write_text(
            text, encoding="utf-8")
        (LOG_DIR / "polling_rework_findings_latest.txt").write_text(
            text, encoding="utf-8")
        log.info("\n%s", text)

        # Soft, structural assertions — the numbers themselves are findings.
        assert new_spawns == 1, (
            f"poll_bundle must be ONE WSL invocation per cycle, saw {new_spawns}")
        assert old_spawns and old_spawns >= 3, (
            f"old-cycle spawn count implausibly low ({old_spawns}) — "
            "measurement harness suspect")
        assert new_spawns < old_spawns
        if old_ms and new_ms:
            assert new_ms < old_ms, (
                f"bundle cycle ({new_ms:.0f} ms) not faster than the old pair "
                f"({old_ms:.0f} ms)")
        assert lag_ms is not None and lag_ms < 5000, (
            f"event lag through the bundle unreasonably high: {lag_ms}")
    finally:
        for name in created:
            try:
                br.close(name)
            except Exception as e:  # pragma: no cover - best effort
                log.debug("close %s failed: %s", name, e)
        try:
            br._run(f"rm -rf {shlex.quote(diag)}")
        except Exception as e:  # pragma: no cover - best effort
            log.debug("rm diag dir failed: %s", e)
