r"""Load test — polling-model scale ceiling (ARCHITECTURE.md §10 #17 → §4.3, §6.2).

WHAT THIS MEASURES (a load/measurement spike, NOT a pass/fail behaviour test):
the bridge driver polls every agent on a fixed ~1 s cadence
(`sidecar/drivers/bridge.py` `events()` ~L618-663: `read_log` L621 + `status` L633,
both via `asyncio.to_thread`, then `asyncio.sleep(1.0)` L663). There is ONE such
loop per agent, so fleet cost is O(N) and every cycle crosses the Windows→WSL2
boundary (a `capture-pane` + a JSONL transcript read). No ceiling is stated
anywhere. This test escalates N tab-less agents and measures, per N:
  (a) sweep latency  — wall-clock for one full poll sweep across all N agents,
  (b) CPU            — WSL-side CPU over the sweep window (via /proc/stat), and
  (c) event lag      — time from a transcript entry landing to the poll observing it,
then identifies the ceiling N* (the smallest N where the effective per-agent
interval drifts past the stated threshold or CPU saturates) — or reports
"no degradation below N=MAX on this hardware", which is itself the finding.

The deliverable is the measured `N → sweep_ms, cpu_pct, event_lag_ms` curve (logged
at DEBUG and written to tests/log/), not an arbitrary "passes at N".

═══════════════════════════════════════════════════════════════════════════════
ISOLATION RULES — this is a FLEET SPAWNER, the highest-collision-risk live test.
Reproduced here per the build prompt (§7) so they can't be lost:
  • RUN ALONE. It is resource-heavy (spawns up to MAX_N real `claude` TUIs) and
    should run when no sibling live bridge test is active.
  • OWN BRIDGE. It instantiates its OWN `TmuxBridge()` and NEVER uses conftest's
    session-scoped `bridge` fixture, whose setup AND teardown both call
    `tmux kill-server` — fatal here (it would wipe sibling agents' sessions).
  • UNIQUE NAMES. Every session is `pollscale-<run_id>-<i>` (run_id = a fresh
    uuid8 per run). Never a fixed/shared name. Every created name is tracked and
    closed by name in a try/finally, even on failure.
  • NEVER `tmux kill-server` / `shutdown()`. Teardown closes only the sessions
    this test created, one by one, then `rm -rf`s its own throwaway dir.
  • CAP N. `MAX_N` is a module constant (env `AWL_POLLSCALE_MAX_N`), so the fleet
    is bounded and can't starve the machine or siblings.
  • TAB-LESS. All sessions are created with `show=False`; `show()` is never called.

Run (from the repo root, through the venv)::

    .\.venv\Scripts\python.exe -m pytest tests\test_polling_scale_ceiling_live.py -m integration
    # or:  tests\run.ps1 tests\test_polling_scale_ceiling_live.py -m integration

Note: `psutil` is not a project dependency, so CPU is sampled from WSL's
`/proc/stat` (aggregate) via the bridge. If a Windows-side / per-process CPU
breakdown is ever wanted, that would need `psutil` added deliberately — flagged,
not silently vendored.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import shlex
import statistics
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter

import pytest

# The tmux bridge package lives at the repo root (`bridge/`); add it to the path
# (resolved relative to this file, so cwd doesn't matter) — mirrors conftest /
# the finisher shim.
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from bridge import TmuxBridge  # noqa: E402
from bridge.bridge import TmuxBridgeError  # noqa: E402
from bridge.transcript import find_transcript  # noqa: E402

log = logging.getLogger(__name__)

# Whole module hits real WSL/tmux + N live models and is slow by nature.
pytestmark = [pytest.mark.integration, pytest.mark.slow]

LOG_DIR = Path(__file__).parent / "log"

# ── Tunables (all env-overridable; defaults bounded to be safe to run) ─────────
# Cap the fleet. On a 22-core box the asyncio default thread pool is
# min(32, cpu+4) workers, and each poll cycle fires 2 blocking WSL calls, so
# thread-pool contention starts biting around N≈(pool/2). Raise AWL_POLLSCALE_MAX_N
# to push further past the bend on a capable machine (costs RAM + model turns).
MAX_N = int(os.environ.get("AWL_POLLSCALE_MAX_N", "12"))
# N ladder — the subset ≤ the number of agents we actually spawned is measured.
_N_LADDER = (1, 3, 6, 9, 12, 16, 20, 24)
K_SWEEPS = int(os.environ.get("AWL_POLLSCALE_SWEEPS", "6"))   # synchronized sweeps / N (first is warm-up)
ITERS = int(os.environ.get("AWL_POLLSCALE_ITERS", "5"))       # realistic-loop iterations / N
NOMINAL_CADENCE_S = 1.0                                        # the fixed poll cadence (bridge.py L663)
INJECT_AT_S = 2.0                                             # when to drop the event-lag marker into the run
SWEEP_TIMEOUT_S = 60.0                                        # a hung sweep fails this N-step, not the suite
PRIME_WAIT_S = 60.0                                          # per-agent wait for the priming turn to land

# Degradation thresholds that DEFINE the ceiling (stated, not assumed).
#  • sweep work > nominal cadence  → a "1 s cadence" can no longer be met.
#  • effective per-agent interval  → drift past 2× nominal (sweep work + 1 s sleep > 2 s).
SWEEP_CEILING_MS = 1000.0
EFF_INTERVAL_CEILING_MS = 2000.0


# ── CPU sampling (psutil-free: aggregate /proc/stat inside WSL) ────────────────
def _cpu_snapshot(bridge: TmuxBridge):
    """(idle_jiffies, total_jiffies) from WSL's aggregate /proc/stat 'cpu' line, or None."""
    try:
        line = bridge._run("head -1 /proc/stat")
    except Exception:
        return None
    parts = line.split()
    if len(parts) < 5 or parts[0] != "cpu":
        return None
    try:
        vals = [int(x) for x in parts[1:]]
    except ValueError:
        return None
    idle = vals[3] + (vals[4] if len(vals) > 4 else 0)  # idle + iowait
    return (idle, sum(vals))


def _cpu_percent(before, after):
    """Busy% across the WSL VM's cores over the [before, after] window, or None."""
    if not before or not after:
        return None
    idle_d = after[0] - before[0]
    total_d = after[1] - before[1]
    if total_d <= 0:
        return None
    return max(0.0, min(100.0, 100.0 * (1.0 - idle_d / total_d)))


def _append_marker(bridge: TmuxBridge, path: str, marker_uuid: str) -> None:
    """Append one synthetic transcript entry carrying a unique uuid, so a poll
    cycle's read_log will surface it — the event-lag probe. Safe on a throwaway,
    idle session (a torn concurrent read just skips the line and catches it next
    cycle; parse_transcript drops unparseable lines)."""
    line = json.dumps({
        "type": "user",
        "uuid": marker_uuid,
        "timestamp": datetime.now().isoformat(),
        "message": {"content": f"POLLSCALE_MARKER_{marker_uuid}"},
    })
    bridge._run(f"cat >> {shlex.quote(path)}", stdin_data=line + "\n")


def _median(xs):
    xs = [x for x in xs if x is not None]
    return statistics.median(xs) if xs else None


def _project_crossing(points, threshold):
    """Least-squares projection of the N where sweep_ms crosses `threshold`.
    Reported as a projection only (never asserted). None if it can't be fit."""
    pts = [(n, y) for n, y in points if y is not None and y != float("inf")]
    if len(pts) < 2:
        return None
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    m = len(xs)
    sx, sy = sum(xs), sum(ys)
    sxx = sum(x * x for x in xs)
    sxy = sum(x * y for x, y in zip(xs, ys))
    denom = m * sxx - sx * sx
    if denom == 0:
        return None
    slope = (m * sxy - sx * sy) / denom
    intercept = (sy - slope * sx) / m
    if slope <= 0:
        return None
    return (threshold - intercept) / slope


# ── One faithful poll cycle (mirrors BridgeDriver.events(), one iteration) ─────
async def _poll_cycle(bridge: TmuxBridge, name: str):
    """Exactly the two blocking WSL round-trips one `events()` iteration costs:
    read_log (bridge.py L621) + status (L633), both offloaded via asyncio.to_thread
    onto the same default thread pool the sidecar uses. Returns the parsed entries
    (for the event-lag scan); the sleep(1.0) at L663 is the caller's cadence."""
    try:
        entries = await asyncio.to_thread(bridge.read_log, name)
    except Exception:
        entries = []  # transcript may not exist yet / read raced — mirrors the driver
    try:
        await asyncio.to_thread(bridge.status, name)
    except Exception:
        pass
    return entries


async def _synchronized_sweeps(bridge: TmuxBridge, names):
    """K back-to-back synchronized sweeps (all N poll cycles fired together), timed.
    Returns (list_of_sweep_ms, cpu_pct_over_window). Isolates the raw O(N) poll
    work from the 1 s sleep."""
    cpu_before = await asyncio.to_thread(_cpu_snapshot, bridge)
    sweeps = []
    for _ in range(K_SWEEPS):
        t0 = perf_counter()
        try:
            await asyncio.wait_for(
                asyncio.gather(*[_poll_cycle(bridge, n) for n in names]),
                timeout=SWEEP_TIMEOUT_S,
            )
            sweeps.append((perf_counter() - t0) * 1000.0)
        except asyncio.TimeoutError:
            sweeps.append(float("inf"))
    cpu_after = await asyncio.to_thread(_cpu_snapshot, bridge)
    return sweeps, _cpu_percent(cpu_before, cpu_after)


async def _realistic_run(bridge: TmuxBridge, names):
    """N independent poll loops (poll_cycle + sleep 1 s), exactly as the sidecar
    runs N event generators. Returns (effective_interval_ms, event_lag_ms):
      • effective interval = median per-agent gap between consecutive cycle starts
        (the user-facing cadence; drifts past 1 s as contention inflates the work);
      • event lag = time from injecting a marker into one agent's transcript to a
        poll cycle observing it (None if never observed / no transcript)."""
    starts = {n: [] for n in names}
    marker = uuid.uuid4().hex
    inj = {"t0": None, "t_seen": None, "target": None, "path": None}

    # Pick a target that has a transcript file to append to.
    for n in names:
        path = await asyncio.to_thread(find_transcript, bridge, n)
        if path:
            inj["target"], inj["path"] = n, path
            break

    async def injector():
        if not inj["path"]:
            return
        await asyncio.sleep(INJECT_AT_S)
        inj["t0"] = perf_counter()
        try:
            await asyncio.to_thread(_append_marker, bridge, inj["path"], marker)
        except Exception as e:  # pragma: no cover - best effort
            log.debug("marker append failed: %s", e)

    async def loop(name):
        for _ in range(ITERS):
            starts[name].append(perf_counter())
            entries = await _poll_cycle(bridge, name)
            if name == inj["target"] and inj["t0"] is not None and inj["t_seen"] is None:
                if any(isinstance(e, dict) and e.get("uuid") == marker for e in entries):
                    inj["t_seen"] = perf_counter()
            await asyncio.sleep(NOMINAL_CADENCE_S)

    await asyncio.gather(injector(), *[loop(n) for n in names])

    per_agent = []
    for ts in starts.values():
        if len(ts) >= 2:
            gaps = [(b - a) * 1000.0 for a, b in zip(ts, ts[1:])]
            per_agent.append(_median(gaps))
    eff = _median(per_agent)
    lag = ((inj["t_seen"] - inj["t0"]) * 1000.0
           if inj["t0"] is not None and inj["t_seen"] is not None else None)
    return eff, lag


async def _measure_all(bridge: TmuxBridge, created):
    """Walk the N ladder (capped at the agents actually spawned) and collect the
    curve. Each N-step is wrapped so one failure yields a partial curve, not a hang."""
    avail = len(created)
    n_steps = sorted({n for n in _N_LADDER if n <= avail} | {avail})
    results = []
    for n in n_steps:
        names = created[:n]
        row = {"n": n, "sweep_ms": None, "sweep_p95_ms": None,
               "cpu_pct": None, "eff_interval_ms": None, "event_lag_ms": None}
        try:
            # A discarded warm-up sweep first, then the measured batch.
            await _poll_cycle(bridge, names[0])
            sweeps, cpu = await _synchronized_sweeps(bridge, names)
            measured = [s for s in sweeps[1:] if s != float("inf")]
            row["sweep_ms"] = _median(measured)
            row["sweep_p95_ms"] = (max(measured) if measured else None)
            row["cpu_pct"] = cpu
            eff, lag = await _realistic_run(bridge, names)
            row["eff_interval_ms"] = eff
            row["event_lag_ms"] = lag
            log.debug(
                "N=%d  sweep=%s ms (p95 %s)  cpu=%s%%  eff_interval=%s ms  event_lag=%s ms",
                n, _fmt(row["sweep_ms"]), _fmt(row["sweep_p95_ms"]),
                _fmt(row["cpu_pct"]), _fmt(row["eff_interval_ms"]), _fmt(row["event_lag_ms"]),
            )
        except Exception as e:  # pragma: no cover - keep the partial curve
            log.warning("N=%d measurement failed: %s", n, e)
        results.append(row)
    return results


def _find_ceiling(results):
    """Smallest N crossing either stated threshold, or None (= no degradation ≤ MAX)."""
    for r in results:
        sw, ev = r["sweep_ms"], r["eff_interval_ms"]
        if (sw is not None and sw > SWEEP_CEILING_MS) or \
           (ev is not None and ev > EFF_INTERVAL_CEILING_MS):
            return r["n"]
    return None


def _fmt(x):
    if x is None:
        return "n/a"
    if x == float("inf"):
        return "TIMEOUT"
    return f"{x:.1f}"


def _emit_curve(results, ceiling, machine, created):
    """Log the curve at DEBUG and write a durable copy to tests/log/ (gitignored)."""
    lines = []
    lines.append("AWL polling-model scale ceiling — measured load curve")
    lines.append(f"  when:        {datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')}")
    lines.append(f"  host cores:  {machine['cpu_count']}  →  asyncio thread pool = "
                 f"{machine['pool_max_workers']} workers")
    lines.append(f"  agents:      spawned {machine['agents_spawned']} of MAX_N={machine['max_n_requested']} "
                 f"requested  (2 blocking WSL calls / agent / cycle)")
    lines.append(f"  cadence:     nominal {NOMINAL_CADENCE_S:.1f} s (bridge.py events() L663)")
    lines.append(f"  thresholds:  sweep_ms > {SWEEP_CEILING_MS:.0f}  OR  "
                 f"eff_interval_ms > {EFF_INTERVAL_CEILING_MS:.0f}")
    lines.append("")
    hdr = f"  {'N':>3} | {'sweep_ms':>9} | {'sweep_p95':>9} | {'cpu_%':>6} | {'eff_int_ms':>10} | {'event_lag_ms':>12}"
    lines.append(hdr)
    lines.append("  " + "-" * (len(hdr) - 2))
    for r in results:
        lines.append(
            f"  {r['n']:>3} | {_fmt(r['sweep_ms']):>9} | {_fmt(r['sweep_p95_ms']):>9} | "
            f"{_fmt(r['cpu_pct']):>6} | {_fmt(r['eff_interval_ms']):>10} | {_fmt(r['event_lag_ms']):>12}"
        )
    lines.append("")
    if ceiling is not None:
        lines.append(f"  CEILING N* = {ceiling}  (first N crossing a stated threshold)")
    else:
        maxn = max((r["n"] for r in results), default=0)
        lines.append(f"  CEILING N* = none reached — no degradation below N={maxn} on this hardware.")
    proj = _project_crossing([(r["n"], r["sweep_ms"]) for r in results], SWEEP_CEILING_MS)
    if proj is not None:
        lines.append(f"  projected sweep>1s crossing (linear fit): N ≈ {proj:.1f}")
    text = "\n".join(lines) + "\n"

    log.debug("\n%s", text)
    try:
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        out = LOG_DIR / f"pollscale_curve_{stamp}.txt"
        out.write_text(text, encoding="utf-8")
        (LOG_DIR / "pollscale_curve_latest.txt").write_text(text, encoding="utf-8")
        log.info("polling-scale curve -> %s", out)
    except Exception as e:  # pragma: no cover - best effort
        log.warning("could not write curve file: %s", e)
    return text


def _prime(bridge: TmuxBridge, names):
    """Give each agent one trivial real turn so a transcript exists (the faithful
    idle-fleet state, and the target for the event-lag marker). Sends to all first,
    then waits each idle so generations overlap. A slow agent is skipped, not fatal."""
    for name in names:
        try:
            bridge.send(name, "Reply with only the word: READY")
        except TmuxBridgeError as e:
            log.warning("prime send failed for %s: %s", name, e)
    for name in names:
        try:
            bridge.wait_idle(name, timeout=PRIME_WAIT_S)
        except TmuxBridgeError as e:
            log.warning("prime wait_idle timed out for %s: %s", name, e)


# ── The test ───────────────────────────────────────────────────────────────────
def test_polling_scale_ceiling():
    """Escalate N tab-less agents; measure the poll-loop degradation curve and
    report the ceiling N* (or 'no degradation below N=MAX'). Soft, informative
    assertions only — the deliverable is the measured curve, whatever it is."""
    bridge = TmuxBridge()  # OWN bridge — never the kill-server fixture (see header)
    run_id = uuid.uuid4().hex[:8]
    diag = f"/home/lester/awl-pollscale-{run_id}"
    created: list[str] = []
    try:
        bridge._run(f"mkdir -p {shlex.quote(diag)}")

        # Spawn up to MAX_N tab-less, uniquely-named sessions. If spawning hits a
        # wall (hardware/WSL), that max reachable N *is* the finding — stop and
        # measure what we have rather than fail.
        for i in range(MAX_N):
            name = f"pollscale-{run_id}-{i}"
            try:
                bridge.create(name, cwd=diag, show=False)  # show=False → tab-less
                created.append(name)
                log.debug("spawned %s (%d/%d)", name, len(created), MAX_N)
            except Exception as e:
                log.warning("spawn stopped at %d agents (wanted %d): %s",
                            len(created), MAX_N, e)
                break

        assert created, "could not spawn a single agent — environment can't run the sweep"

        _prime(bridge, created)

        results = asyncio.run(_measure_all(bridge, created))
        ceiling = _find_ceiling(results)
        machine = {
            "cpu_count": os.cpu_count(),
            "pool_max_workers": min(32, (os.cpu_count() or 1) + 4),
            "agents_spawned": len(created),
            "max_n_requested": MAX_N,
        }
        _emit_curve(results, ceiling, machine, created)

        # ── Soft, informative assertions (never a hard "works at N=X" contract) ──
        valid = [r for r in results if r["sweep_ms"] is not None]
        assert len(valid) >= 2, (
            f"collected too few valid N-steps ({len(valid)}) to form a curve — "
            f"could only exercise {len(created)} agent(s)"
        )
        # The realistic loop sleeps 1 s/iteration, so the effective interval must
        # sit at least around the nominal cadence — a sanity check on the harness.
        for r in valid:
            if r["eff_interval_ms"] is not None:
                assert r["eff_interval_ms"] >= NOMINAL_CADENCE_S * 1000 * 0.8, (
                    f"N={r['n']}: effective interval {r['eff_interval_ms']:.0f} ms "
                    f"below the 1 s sleep floor — measurement is unsound"
                )
        # Either we found a ceiling within the swept range, or we reached max-N
        # without degrading. Both are legitimate outcomes — assert only that the
        # result is self-consistent.
        assert ceiling is None or ceiling in {r["n"] for r in results}, \
            "ceiling N* must be one of the swept N values"
        log.info("RESULT: ceiling N*=%s across N=%s (spawned %d agents)",
                 ceiling, [r["n"] for r in results], len(created))
    finally:
        # Close ONLY our own uniquely-named sessions, one by one. NEVER kill-server.
        for name in created:
            try:
                bridge.close(name)
            except Exception as e:  # pragma: no cover - best effort
                log.debug("close %s failed: %s", name, e)
        try:
            bridge._run(f"rm -rf {shlex.quote(diag)}")
        except Exception as e:  # pragma: no cover - best effort
            log.debug("rm diag dir failed: %s", e)
