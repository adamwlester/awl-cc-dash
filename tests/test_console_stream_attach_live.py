r"""Live spike — streaming-terminal attach for the Console (ARCHITECTURE.md §10 #5).

Answers the polling-vs-streaming fork logged in the embedded-terminal feasibility
brief (dev/notes/research/embedded-terminal-feasibility-brief-2026-07-05.md): can we
put a REAL, live-streaming terminal (ttyd attached to the agent's tmux session,
consumed over a WebSocket) into the dashboard — the way the user pictured it —
instead of the settled *polled* capture-pane mirror? And, critically, does that live
attach coexist with the sidecar's continuous capture-pane coordination reads?

Three decided behaviors this encodes (all proven live on 2026-07-05, ttyd 1.7.7 /
WSL2 / tmux 3.4):

  1. REACH — a ttyd instance attached to a live bridge tmux session is reachable
     FROM WINDOWS over `localhost` with NO hand-rolled port-forwarding (WSL2's
     default localhost relay is enough). This was the brief's biggest medium-
     confidence unknown.

  2. COEXIST (the load-bearing one) — with a live tmux client attached to the SAME
     session, the sidecar's capture-pane scraper (`bridge.status`/`read`) keeps
     classifying state correctly (never garbled/`unknown`). The ONE side effect is
     geometry: with tmux's default `window-size latest`, a viewer resizes the pane
     and the change PERSISTS after it detaches; setting `window-size manual` and
     pinning a size fully isolates the scraper (viewer can't touch its geometry).

  3. LATENCY — streaming (a ttyd WebSocket on localhost) delivers a keystroke
     round-trip in ~10 ms vs. the polled mirror's ~500 ms average (bounded by the
     poll cadence, and O(N)-degrading with fleet size). Informational measurement,
     written to tests/log/.

This is engine/transport feasibility EVIDENCE, not a regression gate — the faithful
on-screen renderer (xterm.js in the frozen React Console) stays a build-sprint job.

Requires `ttyd` in WSL (static binary at ~/.local/bin/ttyd or on PATH); the whole
module SKIPS cleanly if it is absent.

Isolation (same rules as the other live spikes): OWN TmuxBridge (never conftest's
kill-server fixture); one uniquely-named, tab-less session (`streamattach-<uuid8>`);
its own ttyd instances killed by pidfile; teardown closes ONLY our session + dir;
NEVER `kill-server`/`shutdown()`.

Run::

    .\.venv\Scripts\python.exe -m pytest tests\test_console_stream_attach_live.py -m integration
"""
import base64
import json
import logging
import math
import os
import socket
import statistics
import struct
import sys
import time
import urllib.request
import uuid
from datetime import datetime, timezone
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from bridge import TmuxBridge  # noqa: E402

log = logging.getLogger(__name__)
pytestmark = [pytest.mark.integration, pytest.mark.slow]

SLUG = "streamattach"
LOG_DIR = Path(__file__).parent / "log"
RO_PORT = 7691   # read-only ttyd (viewer / reachability)
RW_PORT = 7692   # writable ttyd (keystroke round-trip)

# A tmux client at a FIXED size, held for N seconds — the deterministic stand-in
# for a live ttyd/browser viewer. stdlib-only (pty/fcntl/termios), runs in WSL.
_VIEWER_PY = r'''
import pty, os, sys, time, struct, fcntl, termios, signal, select, json
name, cols, rows, dur, statusf = sys.argv[1], int(sys.argv[2]), int(sys.argv[3]), float(sys.argv[4]), sys.argv[5]
pid, fd = pty.fork()
if pid == 0:
    os.environ["TERM"] = "xterm-256color"
    os.execvp("tmux", ["tmux", "attach", "-t", name])
else:
    fcntl.ioctl(fd, termios.TIOCSWINSZ, struct.pack("HHHH", rows, cols, 0, 0))
    open(statusf, "w").write(json.dumps({"started": time.time()}))
    end = time.time() + dur
    while time.time() < end:
        try:
            r, _, _ = select.select([fd], [], [], 0.2)
            if r and not os.read(fd, 65536):
                break
        except OSError:
            break
    try: os.kill(pid, signal.SIGKILL)
    except OSError: pass
    try: os.waitpid(pid, 0)
    except OSError: pass
'''


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def _wsl_write(br, path, text):
    """Write bytes to a WSL path as pure LF (base64 dodges the text-mode CRLF
    mangling that breaks multi-line bash/py written through the pipe)."""
    b64 = base64.b64encode(text.encode("utf-8")).decode("ascii")
    br._run(f"echo {b64} | base64 -d > {path}")


def _resolve_ttyd(br):
    """Absolute ttyd path in WSL, or None if not installed. Resolves $HOME via
    `cd ~ && pwd` and tests literal paths — the forms proven to work through the
    bridge's non-login `bash -c` (bare `$HOME` interpolation misbehaved there)."""
    home = br._run("cd ~ && pwd").strip()
    cand = f"{home}/.local/bin/ttyd"
    out = br._run(
        f"if [ -x {cand} ]; then echo {cand}; "
        f"elif command -v ttyd >/dev/null 2>&1; then command -v ttyd; "
        f"else echo NO; fi").strip()
    return None if (not out or out == "NO") else out


def _geo(br, name):
    return br._run("tmux display-message -p -t " + name + " '#{pane_width}x#{pane_height}'")


def _nclients(br, name):
    try:
        return int(br._run(f"tmux list-clients -t {name} 2>/dev/null | wc -l") or "0")
    except Exception:
        return -1


def _pin(br, name, cols, rows, mode):
    br._run(f"tmux set-option -t {name} window-size manual")
    br._run(f"tmux resize-window -t {name} -x {cols} -y {rows}")
    if mode == "latest":
        br._run(f"tmux set-option -t {name} window-size latest")
    time.sleep(0.3)


def _start_ttyd(br, ttyd, diag, name, port, writable):
    """Start a detached ttyd (proven setsid/nohup/</dev/null-in-a-script pattern;
    an inline `nohup ... &` gets reaped when the wsl.exe call returns)."""
    tag = "rw" if writable else "ro"
    wflag = "-W " if writable else ""
    rflag = "" if writable else " -r"
    sh = ("#!/usr/bin/env bash\n"
          f"DIAG={diag}\n"
          f'if [ -f "$DIAG/ttyd_{tag}.pid" ]; then kill "$(cat $DIAG/ttyd_{tag}.pid)" 2>/dev/null || true; sleep 0.3; fi\n'
          f'setsid nohup "{ttyd}" -p {port} {wflag}tmux attach -t {name}{rflag} '
          f'</dev/null >"$DIAG/ttyd_{tag}.log" 2>&1 &\n'
          f'echo $! > "$DIAG/ttyd_{tag}.pid"\n'
          "sleep 1.2\n"
          f'kill -0 "$(cat $DIAG/ttyd_{tag}.pid)" 2>/dev/null && echo ALIVE || echo DEAD\n')
    _wsl_write(br, f"{diag}/start_{tag}.sh", sh)
    return br._run(f"bash {diag}/start_{tag}.sh", timeout=20)


def _stop_ttyd(br, diag, tag):
    br._run(f'[ -f {diag}/ttyd_{tag}.pid ] && kill "$(cat {diag}/ttyd_{tag}.pid)" 2>/dev/null; true')


def _launch_viewer(br, diag, name, cols, rows, dur):
    sf = f"{diag}/viewer_status.json"
    sh = ("#!/usr/bin/env bash\n"
          f"setsid nohup python3 {diag}/viewer.py {name} {cols} {rows} {dur} {sf} "
          f"</dev/null >{diag}/viewer.log 2>&1 &\n"
          f"echo $! > {diag}/viewer.pid\nsleep 0.5\ncat {diag}/viewer.pid\n")
    _wsl_write(br, f"{diag}/launch_viewer.sh", sh)
    return br._run(f"bash {diag}/launch_viewer.sh")


class _WS:
    """Minimal stdlib WebSocket client speaking ttyd's `tty` subprotocol."""

    def __init__(self, host, port, cols=100, rows=30):
        self.sock = socket.create_connection((host, port), timeout=8)
        key = base64.b64encode(os.urandom(16)).decode()
        self.sock.sendall(
            (f"GET /ws HTTP/1.1\r\nHost: {host}:{port}\r\nUpgrade: websocket\r\n"
             f"Connection: Upgrade\r\nSec-WebSocket-Key: {key}\r\n"
             f"Sec-WebSocket-Version: 13\r\nSec-WebSocket-Protocol: tty\r\n\r\n").encode())
        buf = b""
        while b"\r\n\r\n" not in buf:
            d = self.sock.recv(4096)
            if not d:
                raise IOError("ws handshake closed early")
            buf += d
        if b" 101 " not in buf.split(b"\r\n", 1)[0]:
            raise IOError("ws handshake not 101: " + buf[:100].decode("latin1"))
        self._rx = buf.split(b"\r\n\r\n", 1)[1]
        self._send(json.dumps({"AuthToken": "", "columns": cols, "rows": rows}).encode())

    def _send(self, payload, opcode=0x2):
        mask = os.urandom(4)
        ln = len(payload)
        hdr = bytearray([0x80 | opcode])
        if ln < 126:
            hdr.append(0x80 | ln)
        elif ln < 65536:
            hdr.append(0x80 | 126); hdr += struct.pack(">H", ln)
        else:
            hdr.append(0x80 | 127); hdr += struct.pack(">Q", ln)
        hdr += mask
        self.sock.sendall(bytes(hdr) + bytes(b ^ mask[i % 4] for i, b in enumerate(payload)))

    def send_input(self, data: bytes):
        self._send(b"0" + data, opcode=0x2)      # ttyd INPUT command

    def _need(self, n):
        while len(self._rx) < n:
            d = self.sock.recv(65536)
            if not d:
                raise IOError("ws closed")
            self._rx += d

    def _frame(self):
        self._need(2)
        b1 = self._rx[1]
        opcode = self._rx[0] & 0x0F
        masked = b1 & 0x80
        ln = b1 & 0x7F
        off = 2
        if ln == 126:
            self._need(4); ln = struct.unpack(">H", self._rx[2:4])[0]; off = 4
        elif ln == 127:
            self._need(10); ln = struct.unpack(">Q", self._rx[2:10])[0]; off = 10
        self._need(off + (4 if masked else 0) + ln)
        if masked:
            m = self._rx[off:off + 4]; off += 4
            payload = bytes(x ^ m[i % 4] for i, x in enumerate(self._rx[off:off + ln]))
        else:
            payload = self._rx[off:off + ln]
        self._rx = self._rx[off + ln:]
        return opcode, payload

    def wait_output_contains(self, marker: bytes, timeout: float):
        self.sock.settimeout(timeout)
        end = time.time() + timeout
        while time.time() < end:
            opcode, payload = self._frame()
            if opcode == 0x8:
                raise IOError("ws close frame")
            if opcode == 0x9:                    # ping -> pong
                self._send(payload, opcode=0xA)
                continue
            if payload[:1] == b"0" and marker in payload[1:]:
                return
        raise TimeoutError("marker not seen")

    def close(self):
        try:
            self.sock.close()
        except OSError:
            pass


# --------------------------------------------------------------------------- #
# Module fixture — one tab-less live session + resolved ttyd; skip if no ttyd.
# --------------------------------------------------------------------------- #
@pytest.fixture(scope="module")
def live():
    br = TmuxBridge()
    ttyd = _resolve_ttyd(br)
    if not ttyd:
        pytest.skip("ttyd not installed in WSL (~/.local/bin/ttyd or PATH) — install to run this spike")
    name = f"{SLUG}-{uuid.uuid4().hex[:8]}"
    diag = f"/home/lester/awl-{name}"
    br._run(f"mkdir -p {diag}")
    _wsl_write(br, f"{diag}/viewer.py", _VIEWER_PY)
    br.create(name, cwd=diag, show=False)         # tab-less (mandatory)
    try:
        br.watch(name, r"(Welcome|❯|for shortcuts|Bypass|>)", timeout=90, interval=1.0)
    except Exception as e:  # noqa: BLE001
        log.debug("readiness watch soft-miss (create already idled): %s", e)
    yield {"br": br, "name": name, "diag": diag, "ttyd": ttyd}
    for tag in ("ro", "rw"):
        _stop_ttyd(br, diag, tag)
    try:
        br.close(name)
    except Exception as e:  # noqa: BLE001
        log.debug("close(%s) teardown no-op: %s", name, e)
    br._run(f"rm -rf {diag}")


# --------------------------------------------------------------------------- #
# 1. REACH — reachable from Windows over localhost, no port-forwarding.
# --------------------------------------------------------------------------- #
def test_ttyd_reachable_from_windows(live):
    br, name, diag, ttyd = live["br"], live["name"], live["diag"], live["ttyd"]
    assert "ALIVE" in _start_ttyd(br, ttyd, diag, name, RO_PORT, writable=False)
    listen = br._run(f'ss -ltn 2>/dev/null | grep ":{RO_PORT}" || echo NONE')
    assert "NONE" not in listen, f"ttyd not listening in WSL on {RO_PORT}: {listen!r}"

    ok = None
    for host in ("localhost", "127.0.0.1"):
        try:
            r = urllib.request.urlopen(f"http://{host}:{RO_PORT}/", timeout=8)
            body = r.read(400).lower()
            if r.status == 200 and any(m in body for m in (b"ttyd", b"xterm", b"<!doctype", b"<html")):
                ok = host
                break
        except Exception as e:  # noqa: BLE001
            log.debug("reach %s failed: %s", host, e)
    assert ok, "ttyd in WSL2 was NOT reachable from Windows via localhost/127.0.0.1"
    log.info("REACH: ttyd reachable from Windows at http://%s:%d (no port-forwarding)", ok, RO_PORT)


# --------------------------------------------------------------------------- #
# 2. COEXIST — live viewer vs the capture-pane scraper (the make-or-break test).
# --------------------------------------------------------------------------- #
def _coexist_run(br, name, diag, window_mode):
    _pin(br, name, 80, 24, mode=window_mode)
    t0 = time.time()
    rows = []

    def snap():
        rows.append({"t": round(time.time() - t0, 1), "clients": _nclients(br, name),
                     "geo": _geo(br, name), "state": br.status(name)["state"]})

    snap(); snap()                                   # before (no viewer)
    _launch_viewer(br, diag, name, 120, 35, 12)
    end = time.time() + 13
    while time.time() < end:
        snap(); time.sleep(0.9)
    snap(); snap()                                   # after (viewer gone)

    during = [r for r in rows if r["clients"] and r["clients"] > 0]
    geos_during = sorted({r["geo"] for r in during})
    bad = [r for r in rows if r["state"] not in ("idle", "generating", "permission_prompt")]
    return during, geos_during, bad


def test_live_viewer_coexists_with_poller(live):
    br, name, diag = live["br"], live["name"], live["diag"]

    # NAIVE (window-size latest): viewer resizes the pane, but the scraper still
    # classifies. Geometry drift is the only effect.
    during_n, geos_n, bad_n = _coexist_run(br, name, diag, "latest")
    assert during_n, "viewer never attached in the naive run (harness fault)"
    assert not bad_n, f"scraper produced non-classifiable reads under a viewer: {bad_n}"
    assert all(r["state"] == "idle" for r in during_n), \
        f"idle agent misclassified while a viewer was attached: {during_n}"
    assert geos_n and geos_n[0] != "80x24", \
        "expected the naive viewer to RESIZE the pane (it should, to document the hazard)"
    log.info("COEXIST/naive: scraper OK under viewer; pane resized to %s (documented hazard)", geos_n)

    # MITIGATION (window-size manual): pinned; the viewer cannot touch geometry.
    during_m, geos_m, bad_m = _coexist_run(br, name, diag, "manual")
    assert during_m, "viewer never attached in the mitigation run (harness fault)"
    assert not bad_m and all(r["state"] == "idle" for r in during_m), \
        f"scraper misclassified under the pinned viewer: {during_m}"
    assert geos_m == ["80x24"], \
        f"window-size manual must PIN geometry against the viewer, saw {geos_m}"
    log.info("COEXIST/mitigation: pinned at 80x24 under a 120x35 viewer — scraper fully isolated")


# --------------------------------------------------------------------------- #
# 3. LATENCY — streaming vs polled (informational; soft assertion + tests/log).
# --------------------------------------------------------------------------- #
def _polled_latency(br, name, iters=10, cadence=1.0):
    _pin(br, name, 100, 30, mode="manual")
    t0 = time.time()
    lags = []
    for i in range(iters):
        time.sleep(0.05 + (i * 0.131) % 0.9)         # spread the phase across the grid
        marker = f"LAT{uuid.uuid4().hex[:8]}"
        inject = time.time()
        br.send(name, marker, press_enter=False)
        tick = t0 + math.ceil((inject - t0) / cadence) * cadence
        time.sleep(max(0, tick - time.time()))
        if marker in br.read(name, lines=12)["content"]:
            lags.append((tick - inject) * 1000.0)
        br.keys(name, "C-u")
        time.sleep(0.15)
    return lags


def _streaming_latency(br, name, diag, ttyd, iters=10):
    assert "ALIVE" in _start_ttyd(br, ttyd, diag, name, RW_PORT, writable=True)
    _pin(br, name, 100, 30, mode="manual")
    ws = _WS("localhost", RW_PORT)
    lags = []
    try:
        ws.wait_output_contains(b"\x1b", timeout=6)   # first paint => streaming confirmed
        for _ in range(iters):
            ws.send_input(b"\x15")                     # Ctrl-U clear
            time.sleep(0.2)
            marker = ("w" + uuid.uuid4().hex[:6]).encode()
            t = time.time()
            ws.send_input(marker)
            ws.wait_output_contains(marker, timeout=3)
            lags.append((time.time() - t) * 1000.0)
        ws.send_input(b"\x15")
    finally:
        ws.close()
    return lags


def test_streaming_latency_beats_polling(live):
    br, name, diag, ttyd = live["br"], live["name"], live["diag"], live["ttyd"]

    polled = _polled_latency(br, name)
    assert polled, "polled-latency harness captured nothing"
    p_med = statistics.median(polled)

    stream = []
    try:
        stream = _streaming_latency(br, name, diag, ttyd)
    except Exception as e:  # noqa: BLE001 — WS measurement is best-effort evidence
        log.warning("streaming-latency measurement unavailable (%s): %s", type(e).__name__, e)

    s_med = statistics.median(stream) if stream else None
    _write_latency_findings(polled, stream)

    log.info("LATENCY: polled median=%.0f ms (N=1 best case) | streaming median=%s ms",
             p_med, f"{s_med:.0f}" if s_med else "n/a")
    if s_med is not None:
        # Streaming should be at least ~5x faster than the 1 s-cadence polled mirror.
        assert s_med < p_med / 5.0, \
            f"streaming ({s_med:.0f} ms) not decisively faster than polled ({p_med:.0f} ms)"


def _write_latency_findings(polled, stream):
    def stats(xs):
        return (f"n={len(xs)} min={min(xs):.0f} median={statistics.median(xs):.0f} "
                f"mean={statistics.mean(xs):.0f} max={max(xs):.0f} ms") if xs else "n/a"
    text = (
        "AWL Console streaming-attach — latency evidence (§10 #5)\n"
        f"  when:      {datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')}\n"
        f"  polled mirror (1.0s cadence, N=1): {stats(polled)}\n"
        f"  streaming keystroke round-trip:    {stats(stream)}\n"
        "  note: polled is the N=1 BEST case and degrades ~O(N) with fleet size\n"
        "        (test_polling_scale_ceiling_live); streaming is continuous, O(1)/agent.\n")
    try:
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        (LOG_DIR / f"console_stream_findings_{stamp}.txt").write_text(text, encoding="utf-8")
        (LOG_DIR / "console_stream_findings_latest.txt").write_text(text, encoding="utf-8")
    except Exception as e:  # noqa: BLE001
        log.warning("could not write latency findings: %s", e)
    log.debug("\n%s", text)
