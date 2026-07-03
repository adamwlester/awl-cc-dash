"""Live spike — one-click launch: Electron main owns the sidecar lifecycle
without breaking detach-on-close (§10 item 10).

This pins the LIFECYCLE CONTRACT the real Electron-main POC must satisfy, using
the real sidecar-as-a-subprocess plus a real, live tmux Claude Code agent — the
most honest harness the repo venv can run (a Node/Electron POC would need a
runner the venv lacks; per the build prompt that would be a STOP-and-flag, not
an improvised shared-config edit). It models exactly what Electron main would do:
spawn the sidecar as a supervised child, kill it on "project close", respawn it
on "reopen" — and asserts the two survival read-backs that are the whole point:

  * Read-back A (survival): after the sidecar child is killed, the uniquely-named
    tmux agent is STILL in ``TmuxBridge().list()`` — detach-on-close held (§3.4).
  * Read-back B (reconnect): after the sidecar child is respawned, the new
    sidecar's ``reconnect_sessions()`` rebinds it — ``GET /sessions`` shows the
    session id and ``GET /sessions/{id}/context`` shows turn history intact.

"The sidecar process started" is explicitly NOT a pass (build prompt §4). The
confirmed principle under test (research Q3 §2): ``runtime_store.py`` + ``resume()``
rebind to a live tmux session by name on sidecar restart — detached sessions
persist without a window and survive the sidecar process's death. The spike's
job is to prove Electron-main-style lifecycle ownership (spawn-as-child, kill on
close) does not perturb that survival.

  * WORKS → a supervised-child sidecar can be killed on close and the detached
    tmux agent survives + reconnects, so Electron main CAN own the sidecar
    lifecycle without breaking §3.4. Green light for the real Electron-main POC.
  * IMPOSSIBLE (after a REAL spawn/kill/reopen) → if the tmux session does not
    survive the sidecar's death, or reconnect can't be made to work, that is a
    FINDING (write-up + propose the §10 Fallback: ``start-dashboard.bat``
    two-process launch stays the shipped model), NOT a fabricated green.

Run (single file, in isolation — NEVER the whole live tier)::

    .\\.venv\\Scripts\\python.exe -m pytest tests/test_oneclick_launch_live.py -m integration

-----------------------------------------------------------------------------
ISOLATION RULES (parallel-safe — CRITICAL; sibling agents may hold live tmux
sessions at the same time). Reproduced from the build prompt §6 and obeyed here:
  * ONE new file only: this file. Nothing else is added.
  * tmux is uniquely named + slug-prefixed (``oneclick-<uuid8>`` session id; the
    driver mints its own ``awl-<uuid8>`` tmux name, addressed ONLY via
    ``driver.tmux_name``). We touch no other session.
  * NEVER ``tmux kill-server`` (directly or via any helper). Teardown removes
    ONLY our own session (``close(<our name>)``) and our own throwaway WSL dir.
    We do NOT use conftest's session-scoped ``bridge`` / ``diag_dir`` fixtures —
    their setup AND teardown call ``tmux kill-server``, which would kill sibling
    agents' sessions. We instantiate our OWN ``TmuxBridge()`` instead.
  * We do NOT edit tests/conftest.py, pyproject.toml, or tests/README.md.
  * The sidecar child is pinned to our OWN ``AWL_SIDECAR_RUNTIME`` tmp dir, so its
    ``reconnect_sessions()`` only ever sees OUR record (a real sidecar on the
    default ``sidecar/runtime/`` is invisible to it, and vice-versa). The only
    shared resource is TCP port 7690 (the sidecar's fixed port): we skip cleanly
    if a foreign process already holds it.
  * Bridge sessions stay TAB-LESS — never ``show=True`` / never ``show()``.
-----------------------------------------------------------------------------
"""

import asyncio
import json
import logging
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path

import pytest

# Make the sidecar's modules importable as top-level (it runs with its own dir on
# sys.path, not the repo root), and the repo-root ``bridge`` package importable.
_REPO_ROOT = Path(__file__).resolve().parent.parent
_SIDECAR = _REPO_ROOT / "sidecar"
if str(_SIDECAR) not in sys.path:
    sys.path.insert(0, str(_SIDECAR))
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from drivers.bridge import BridgeDriver  # noqa: E402
from drivers.base import DriverConfig  # noqa: E402
from bridge import TmuxBridge  # noqa: E402
import runtime_store  # noqa: E402

log = logging.getLogger("tests.oneclick_launch")

pytestmark = [pytest.mark.integration, pytest.mark.slow]

_SIDECAR_URL = "http://127.0.0.1:7690"
_SCRATCH = _REPO_ROOT / ".scratch"


# --- HTTP helpers (stdlib only) ----------------------------------------------

def _http_get(path, timeout=5):
    """GET {sidecar}{path} → (status, parsed_json_or_None). Returns (None, None)
    if the connection can't be made (sidecar not up)."""
    url = f"{_SIDECAR_URL}{path}"
    try:
        with urllib.request.urlopen(url, timeout=timeout) as r:
            body = r.read().decode("utf-8", "replace")
            try:
                return r.status, json.loads(body)
            except json.JSONDecodeError:
                return r.status, None
    except urllib.error.HTTPError as e:
        return e.code, None
    except (urllib.error.URLError, ConnectionError, OSError):
        return None, None


def _sidecar_health(timeout=2):
    status, _ = _http_get("/health", timeout=timeout)
    return status == 200


def _wait_for_bind(proc, timeout=150):
    """Poll /health until the sidecar child binds :7690. Fails fast if the child
    process exits first (e.g. port already held → 'address already in use')."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if proc.poll() is not None:
            return False  # child died before binding
        if _sidecar_health():
            return True
        time.sleep(1.0)
    return False


def _wait_for_port_release(timeout=20):
    """After killing a sidecar child, wait until :7690 stops answering, so the
    next spawn doesn't race the socket."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if not _sidecar_health(timeout=1):
            return True
        time.sleep(0.5)
    return False


def _spawn_sidecar(runtime_dir, log_path):
    """Spawn the sidecar the way Electron main would — as a supervised child
    process owning the venv path + runtime dir. Returns the Popen.

    ``AWL_SIDECAR_HOST=127.0.0.1`` keeps it loopback-reachable; ``AWL_SIDECAR_RUNTIME``
    points at OUR tmp dir so its ``reconnect_sessions()`` only sees our record;
    ``AWL_DISABLE_HOOKS=1`` keeps the spike free of the hook channel. stdout+stderr
    go to a .scratch log so the pipe never fills and blocks the child.
    """
    env = os.environ.copy()
    env["AWL_SIDECAR_RUNTIME"] = str(runtime_dir)
    env["AWL_SIDECAR_HOST"] = "127.0.0.1"
    env["AWL_DISABLE_HOOKS"] = "1"
    env["PYTHONPATH"] = str(_REPO_ROOT)
    env["PYTHONIOENCODING"] = "utf-8"
    logf = open(log_path, "w", encoding="utf-8")
    proc = subprocess.Popen(
        [sys.executable, "main.py"],
        cwd=str(_SIDECAR),
        env=env,
        stdout=logf,
        stderr=subprocess.STDOUT,
    )
    proc._awl_logf = logf  # keep the handle alive with the process
    return proc


def _kill_sidecar(proc):
    if proc is None:
        return
    try:
        proc.terminate()
        try:
            proc.wait(timeout=15)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=10)
    except Exception:
        pass
    finally:
        try:
            proc._awl_logf.close()
        except Exception:
            pass


async def _send_marker_and_wait(driver, marker, timeout_iters=120):
    """Send a marker prompt and wait for it to land in the transcript, so the
    resume target has real history to restore (copied from the finisher)."""
    await driver.send(f"Reply with exactly: {marker}")
    for _ in range(timeout_iters):
        try:
            entries = await asyncio.to_thread(driver._bridge.read_log, driver.tmux_name)
        except Exception:
            entries = []
        if any(
            e.get("type") == "assistant"
            and marker in str((e.get("message") or {}).get("content"))
            for e in entries
        ):
            return True
        await asyncio.sleep(0.5)
    return False


# -----------------------------------------------------------------------------

def test_oneclick_lifecycle_survives_close_and_reconnects(tmp_path, monkeypatch):
    """Electron-main-style spawn/supervise/shutdown must NOT break detach-on-close.

    Spawns a real detached agent, then models Electron main: spawn the sidecar as
    a child, kill it (project close), assert the agent survived, respawn the
    sidecar (reopen), assert it reconnected with history intact.
    """
    # Skip cleanly if a FOREIGN sidecar already holds :7690 — we can't bind a
    # second one, and a foreign 200 would mask our child never binding.
    if _sidecar_health(timeout=2):
        pytest.skip(
            "port 7690 already in use (a sidecar is already running) — stop it to "
            "run this lifecycle spike; it needs to own the sidecar process."
        )

    runtime_dir = tmp_path / "runtime"
    # The in-process driver writes its restart-survival record here; the sidecar
    # children read it from the same dir (via AWL_SIDECAR_RUNTIME).
    monkeypatch.setenv("AWL_SIDECAR_RUNTIME", str(runtime_dir))
    monkeypatch.setenv("AWL_DISABLE_HOOKS", "1")  # keep the launch hook-free
    _SCRATCH.mkdir(parents=True, exist_ok=True)

    my_bridge = TmuxBridge()
    suffix = uuid.uuid4().hex[:8]
    sid = f"oneclick-{suffix}"
    wsl_dir = f"/home/lester/awl-oneclick-{suffix}"
    my_bridge._run(f"mkdir -p {wsl_dir}")

    driver = None
    tmux_name = None
    proc1 = None
    proc2 = None

    try:
        # 1) Spawn a real detached agent through the sidecar's driver path, with a
        # unique session id + slug-prefixed tmux name. driver.start() persists the
        # runtime record (the sidecar's own create path) — no endpoint needed.
        async def bring_up_agent():
            nonlocal driver, tmux_name
            driver = BridgeDriver(
                DriverConfig(cwd=wsl_dir, permission_mode="default"),
                lambda e: None,
                session_id=sid,
            )
            await driver.start()
            tmux_name = driver.tmux_name
            landed = await _send_marker_and_wait(driver, "LAUNCH_OK")
            assert landed, "marker turn never landed in the transcript"

        asyncio.run(bring_up_agent())
        log.debug("agent up: sid=%s tmux=%s claude_sid=%s",
                  sid, tmux_name, driver._claude_session_id)

        # Confirm the record the sidecar will reconnect from is present + correct.
        records = {r["session_id"]: r for r in runtime_store.all_records()}
        assert sid in records, f"no runtime record for {sid}; have {list(records)}"
        assert records[sid]["tmux_name"] == tmux_name, "record tmux_name mismatch"
        log.debug("runtime record: %s", records[sid])

        # 2) Start the sidecar the way Electron main would — a supervised child.
        proc1 = _spawn_sidecar(runtime_dir, _SCRATCH / f"oneclick-sidecar-{suffix}-1.log")
        assert _wait_for_bind(proc1), (
            "sidecar child #1 never bound :7690 (see "
            f".scratch/oneclick-sidecar-{suffix}-1.log); proc alive="
            f"{proc1.poll() is None}"
        )
        log.debug("sidecar #1 bound :7690 (pid=%s)", proc1.pid)

        # 3) Simulate project close: kill the sidecar child. Do NOT touch tmux.
        _kill_sidecar(proc1)
        proc1_alive = proc1.poll() is None
        assert not proc1_alive, "sidecar child #1 did not die on terminate()"
        _wait_for_port_release()
        log.debug("sidecar #1 killed; port released")

        # 4) CRUX A — survival: the detached agent is still alive in tmux.
        alive_names = {s["name"] for s in my_bridge.list()}
        log.debug("tmux sessions after close: %s", sorted(alive_names))
        assert tmux_name in alive_names, (
            f"detach-on-close BROKE: agent {tmux_name} gone after the sidecar was "
            f"killed. live sessions={sorted(alive_names)}"
        )
        # Confirm it is genuinely the same live session (its transcript is readable).
        entries = my_bridge.read_log(tmux_name)
        assert any(e.get("type") == "assistant" for e in entries), \
            "surviving session has no readable transcript history"

        # 5) Simulate reopen: respawn the sidecar; startup runs reconnect_sessions().
        proc2 = _spawn_sidecar(runtime_dir, _SCRATCH / f"oneclick-sidecar-{suffix}-2.log")
        assert _wait_for_bind(proc2), (
            "sidecar child #2 (reopen) never bound :7690 (see "
            f".scratch/oneclick-sidecar-{suffix}-2.log); proc alive="
            f"{proc2.poll() is None}"
        )
        log.debug("sidecar #2 (reopen) bound :7690 (pid=%s)", proc2.pid)

        # 6) CRUX B — reconnect: the new sidecar rebound our session.
        status, sessions = _http_get("/sessions", timeout=10)
        assert status == 200 and isinstance(sessions, list), \
            f"GET /sessions failed: status={status}"
        session_ids = {s.get("session_id") for s in sessions}
        log.debug("reopened sidecar /sessions: %s", sorted(session_ids))
        assert sid in session_ids, (
            f"reconnect FAILED: session {sid} not in the reopened sidecar's table "
            f"{sorted(session_ids)}"
        )
        # ...and the driver was rebound to our tmux name (via launch_config readback
        # the endpoint doesn't expose tmux_name, so confirm history instead).
        status, ctx = _http_get(f"/sessions/{sid}/context", timeout=10)
        assert status == 200 and isinstance(ctx, dict), \
            f"GET /sessions/{sid}/context failed: status={status}"
        log.debug("reconnected context usage: %s", ctx)
        assert ctx.get("turns", 0) >= 1, (
            f"reconnected session lost its turn history: context={ctx}"
        )
        log.debug("RESULT: WORKS — survived close (crux A) AND reconnected with "
                  "turns=%s history intact (crux B).", ctx.get("turns"))

    finally:
        # Teardown: kill any surviving sidecar child, then OUR tmux session + dir.
        _kill_sidecar(proc2)
        _kill_sidecar(proc1)
        if tmux_name:
            try:
                my_bridge.close(tmux_name)  # ONLY our own session
            except Exception:
                pass
        # driver.close() would also try to kill tmux/remove the record — the tmux
        # is already gone above; drop the record best-effort so nothing lingers.
        try:
            runtime_store.remove_record(sid)
        except Exception:
            pass
        try:
            my_bridge._run(f"rm -rf {wsl_dir}")
        except Exception:
            pass
