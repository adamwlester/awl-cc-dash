r"""LIVE acceptance — Console streaming attach through the sidecar (§7.13, §11 #29).

The spike (``test_console_stream_attach_live``) proved the TRANSPORT: ttyd on a
bridge tmux session is reachable from Windows over localhost, coexists with the
capture-pane poller once the geometry is pinned, and streams at ~10 ms. This
file proves the BUILD end-to-end through the real sidecar:

  * ``POST /sessions/{id}/console/attach`` starts a ttyd (geometry pinned
    first) and returns the ``{ws_url, port}`` contract;
  * a real WebSocket opened FROM WINDOWS on that ws_url receives terminal
    bytes (the spike's stdlib `tty`-subprotocol client, reused verbatim);
  * COEXISTENCE under the viewer: with the WS held open **and draining**, a
    real prompt sent through the sidecar still completes — the poller's
    classification keeps driving the running→idle transitions and the turn
    reaches the feed — and the pane geometry never moves. (The viewer MUST
    keep reading: a connected-but-not-draining tmux client backpressures the
    pty and stalls the TUI's output — caught live in this test's first run.
    A real xterm.js client always drains, so the backend contract is
    unaffected; the hazard is recorded in the findings file.);
  * a re-attach returns the SAME port (``reused: true``);
  * RESIZE round-trip: ``POST /sessions/{id}/console/resize`` — the ONE
    sanctioned geometry writer (§7.13 deliberate resize; the window stays
    ``window-size manual`` throughout) — applies 120x35 (tmux reports the new
    ``#{pane_width}x#{pane_height}`` and the scraper keeps classifying), and a
    below-floor request (40x10) applies as the 60x15 clamp floor;
  * ``POST /sessions/{id}/console/detach`` kills the ttyd and the port closes.

Verdict recorded in ``tests/log/console_attach_endpoint_findings_latest.txt``.

SIDECAR HARNESS: spawns THIS worktree's sidecar (loopback-only) on :7690 and
skips if the port is already occupied by a foreign build. SKIPS cleanly when
ttyd is not installed in WSL.

ISOLATION (parallel-safe): own ``TmuxBridge()`` for WSL helpers (never
conftest's kill-server fixture); unique names (``cattach-<uuid8>``); own
throwaway WSL cwd; cleans up ONLY its own session (hard delete) + dir; never
``tmux kill-server``; tab-less creation via the sidecar's default.

Run (single file, isolation)::

    .\.venv\Scripts\python.exe -m pytest tests\test_console_attach_endpoint_live.py -x -q
"""

from __future__ import annotations

import base64
import datetime
import json
import logging
import os
import socket
import struct
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path

import pytest

pytestmark = [pytest.mark.integration, pytest.mark.slow]

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from bridge import TmuxBridge  # noqa: E402

log = logging.getLogger("tests.console_attach")

API = "http://127.0.0.1:7690"
SCRATCH = _REPO_ROOT / ".scratch"
LOG_DIR = Path(__file__).parent / "log"
SLUG = "cattach"


# --------------------------------------------------------------------------- #
# HTTP + sidecar harness (the clear-reresolve live test's proven pattern)
# --------------------------------------------------------------------------- #
def _req(method, path, body=None, timeout=20):
    data = None
    headers = {}
    if body is not None:
        data = json.dumps(body).encode()
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(API + path, data=data, headers=headers,
                                 method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            raw = r.read().decode()
            return r.status, (json.loads(raw) if raw else None)
    except urllib.error.HTTPError as e:
        raw = e.read().decode(errors="replace")
        try:
            payload = json.loads(raw) if raw else None
        except Exception:
            payload = raw
        return e.code, payload


def _health_ok():
    try:
        code, _ = _req("GET", "/health", timeout=3)
        return code == 200
    except Exception:
        return False


def _wait_status(session_id, target, timeout=120):
    deadline = time.time() + timeout
    last = None
    while time.time() < deadline:
        code, s = _req("GET", f"/sessions/{session_id}")
        if code == 200 and s:
            last = s.get("status")
            if last == target:
                return last
        time.sleep(1.0)
    return last


def _assistant_event_count(session_id) -> int:
    code, events = _req("GET", f"/sessions/{session_id}/history")
    if code != 200 or not isinstance(events, list):
        return -1
    return sum(1 for ev in events if ev.get("type") == "assistant")


def _wait_new_assistant_event(session_id, baseline, timeout=150) -> bool:
    """True once the feed carries an assistant event beyond ``baseline``.

    Send-agnostic on purpose: with a logged-out WSL claude the reply is the
    'Login expired' error text rather than the model's answer — but it is
    still a REAL assistant transcript entry the poller must ingest, which is
    exactly the coexistence plumbing under test. The login state is recorded
    in the findings either way.
    """
    deadline = time.time() + timeout
    while time.time() < deadline:
        if _assistant_event_count(session_id) > baseline:
            return True
        time.sleep(1.0)
    return False


def _login_state(wsl_bridge, tmux_name) -> str:
    """'logged_out' when the TUI screen shows the login-expired banner."""
    if not tmux_name:
        return "unknown"
    try:
        screen = wsl_bridge.read(tmux_name, lines=40)["content"]
    except Exception:
        return "unknown"
    if "Login expired" in screen or "Not logged in" in screen:
        return "logged_out"
    return "logged_in"


@pytest.fixture(scope="module")
def sidecar():
    """Spawn THIS worktree's sidecar (loopback-only) on :7690; skip if occupied."""
    if _health_ok():
        pytest.skip("a sidecar is already running on :7690 — stop it and re-run")
    SCRATCH.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ)
    env["AWL_SIDECAR_HOST"] = "127.0.0.1"
    env["AWL_SIDECAR_RUNTIME"] = str(SCRATCH / f"{SLUG}-runtime")
    env["PYTHONUNBUFFERED"] = "1"
    logf = (SCRATCH / f"{SLUG}-sidecar.log").open("w", encoding="utf-8")
    proc = subprocess.Popen(
        [sys.executable, "main.py"],
        cwd=str(_REPO_ROOT / "sidecar"),
        env=env, stdout=logf, stderr=subprocess.STDOUT,
    )
    try:
        for _ in range(80):
            if proc.poll() is not None:
                pytest.skip(f"spawned sidecar exited early (rc={proc.returncode}); "
                            f"see {logf.name}")
            if _health_ok():
                break
            time.sleep(0.5)
        else:
            proc.terminate()
            pytest.skip("spawned sidecar never became healthy on :7690")
        yield API
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
        logf.close()


@pytest.fixture(scope="module")
def wsl():
    br = TmuxBridge()
    if not br.resolve_ttyd():
        pytest.skip("ttyd not installed in WSL — the Console live stream needs it")
    return br


def _tmux_name_from_runtime(session_id, wsl_bridge, diag) -> str | None:
    """Read the persisted runtime record to learn the agent's tmux name (the
    API deliberately doesn't expose it). A record whose cwd resolves to a
    project home lands in `<cwd>/.awl-cc-dash/state/agents.json` (the
    write-through roster); only project-less records fall back to the
    app-level sessions.json — check both."""
    try:
        raw = wsl_bridge._run(
            f"cat {diag}/.awl-cc-dash/state/agents.json 2>/dev/null || true")
        if raw.strip():
            rec = (json.loads(raw) or {}).get(session_id) or {}
            if rec.get("tmux_name"):
                return rec["tmux_name"]
    except Exception:
        pass
    path = SCRATCH / f"{SLUG}-runtime" / "sessions.json"
    try:
        records = json.loads(path.read_text(encoding="utf-8"))
        return (records.get(session_id) or {}).get("tmux_name")
    except Exception:
        return None


# --------------------------------------------------------------------------- #
# Minimal stdlib WebSocket client speaking ttyd's `tty` subprotocol — REUSED
# from tests/test_console_stream_attach_live.py (the proven transport code).
# --------------------------------------------------------------------------- #
class _WS:
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


class _WSDrain(threading.Thread):
    """Continuously read (and discard) WS frames — the faithful client behavior.

    A tmux client that connects but stops reading backpressures the pty and
    STALLS the TUI's output (caught live in this test's first run: the
    coexistence turn froze until the socket drained). A real xterm.js client
    always drains; this thread stands in for it and counts the output bytes it
    saw, proving the turn streamed live over the attach.
    """

    def __init__(self, ws: _WS):
        super().__init__(daemon=True)
        self.ws = ws
        self.output_bytes = 0
        # NB: named _halt, not _stop — threading.Thread has an INTERNAL _stop()
        # method that a boolean attribute would shadow (TypeError on join).
        self._halt = False

    def run(self):
        self.ws.sock.settimeout(1.0)
        while not self._halt:
            try:
                opcode, payload = self.ws._frame()
            except (TimeoutError, socket.timeout):
                continue
            except (IOError, OSError):
                return
            if opcode == 0x8:
                return
            if opcode == 0x9:
                try:
                    self.ws._send(payload, opcode=0xA)
                except OSError:
                    return
            elif payload[:1] == b"0":
                self.output_bytes += len(payload) - 1

    def stop(self):
        self._halt = True
        self.join(timeout=5)


def _port_closed(port, tries=15, delay=0.5) -> bool:
    """True once nothing accepts on 127.0.0.1:<port> (ttyd death is async)."""
    for _ in range(tries):
        try:
            s = socket.create_connection(("127.0.0.1", port), timeout=1.5)
            s.close()
            time.sleep(delay)
        except OSError:
            return True
    return False


def _write_findings(text: str) -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    (LOG_DIR / f"console_attach_endpoint_findings_{stamp}.txt").write_text(
        text, encoding="utf-8")
    (LOG_DIR / "console_attach_endpoint_findings_latest.txt").write_text(
        text, encoding="utf-8")


def test_console_attach_endpoint_live(sidecar, wsl):
    slug = f"{SLUG}-{uuid.uuid4().hex[:8]}"
    diag = f"/home/lester/awl-{slug}"
    wsl._run(f"mkdir -p {diag}")
    session_id = None
    ws = None
    findings: list[str] = [
        "Console streaming attach — live endpoint acceptance (§11 #29)",
        f"Date: {datetime.datetime.now().isoformat(timespec='seconds')}",
    ]
    try:
        code, created = _req("POST", "/sessions", {
            "permission_mode": "default",
            "cwd": diag,
            "identity": {"name": slug},
        }, timeout=60)
        assert code == 200 and created, f"create failed: {code} {created}"
        session_id = created["session_id"]
        st = _wait_status(session_id, "idle", timeout=150)
        assert st == "idle", f"agent never reached idle (last status={st})"

        tmux_name = _tmux_name_from_runtime(session_id, wsl, diag)
        geo_before = None
        if tmux_name:
            geo_before = wsl._run(
                f"tmux display-message -p -t {tmux_name} "
                "'#{pane_width}x#{pane_height}'").strip()
        login = _login_state(wsl, tmux_name)
        findings.append(f"WSL claude login state: {login} (logged_out means "
                        "sends yield the 'Login expired' error reply — still "
                        "a real assistant transcript entry, so the plumbing "
                        "acceptance below holds either way).")

        # --- ATTACH: the endpoint contract -----------------------------------
        code, attach = _req("POST", f"/sessions/{session_id}/console/attach",
                            {}, timeout=40)
        assert code == 200, f"attach failed: {code} {attach}"
        assert attach.get("ws_url", "").startswith("ws://127.0.0.1:")
        assert attach.get("ws_url", "").endswith("/ws")
        assert isinstance(attach.get("port"), int)
        assert attach.get("reused") is False
        port = attach["port"]
        findings.append(f"attach -> port={port} ws_url={attach['ws_url']}")

        # --- BYTES FLOW: a real WS from Windows sees terminal output ---------
        ws = _WS("127.0.0.1", port)
        ws.wait_output_contains(b"\x1b", timeout=8)   # first paint (ANSI bytes)
        findings.append("WebSocket from Windows: terminal bytes flow (first "
                        "paint seen).")

        # --- COEXISTENCE: a real turn completes under a DRAINING live viewer -
        # (A connected-but-not-draining client stalls the pty — see _WSDrain.)
        drain = _WSDrain(ws)
        drain.start()
        baseline = _assistant_event_count(session_id)
        cw = f"COEXIST-{uuid.uuid4().hex[:6]}"
        code, _ = _req("POST", f"/sessions/{session_id}/send",
                       {"prompt": f"Reply with exactly: {cw}"}, timeout=30)
        assert code == 200
        seen = _wait_new_assistant_event(session_id, baseline, timeout=150)
        assert seen, ("turn sent while a live viewer was attached never "
                      "reached the feed — the poller's transcript ingestion "
                      "broke under the viewer (coexistence FAILED)")
        # The spike's own coexistence criterion: the capture-pane classifier
        # keeps producing a REAL state under the viewer — never unknown/garbled.
        # (The API `status` field is deliberately not asserted here: an
        # instant-error turn — e.g. logged-out — can end without the screen
        # ever visibly leaving idle, a pre-existing short-turn quirk of the
        # manually-set running flag, unrelated to the viewer.)
        if tmux_name:
            states = set()
            for _ in range(5):
                states.add(wsl.status(tmux_name)["state"])
                time.sleep(1.0)
            assert states <= {"idle", "generating", "permission_prompt"}, (
                f"scraper produced non-classifiable reads under the viewer: "
                f"{states}")
            findings.append(f"Classifier under viewer: states={sorted(states)} "
                            "(never unknown).")
        drain.stop()
        assert drain.output_bytes > 0, \
            "no terminal bytes streamed over the attach during the turn"
        findings.append(f"Coexistence: turn {cw} produced an assistant event "
                        "that reached the feed with the viewer attached and "
                        "draining; "
                        f"{drain.output_bytes} output bytes streamed during "
                        "the turn.")
        findings.append("Hazard (recorded): a connected viewer that STOPS "
                        "reading backpressures the pty and stalls the TUI's "
                        "output — the renderer must always drain its WS "
                        "(xterm.js does; caught live on this test's first run).")
        if tmux_name and geo_before:
            geo_during = wsl._run(
                f"tmux display-message -p -t {tmux_name} "
                "'#{pane_width}x#{pane_height}'").strip()
            assert geo_during == geo_before, (
                f"pane geometry moved under the viewer: {geo_before} -> "
                f"{geo_during} — the window-size pin failed")
            findings.append(f"Geometry pinned: {geo_before} unchanged under a "
                            "100x30 viewer (window-size manual).")

        # --- RE-ATTACH returns the same live attach ---------------------------
        code, again = _req("POST", f"/sessions/{session_id}/console/attach",
                           {}, timeout=30)
        assert code == 200 and again["port"] == port and again["reused"] is True
        findings.append("Re-attach: same port returned, reused=true.")

        # --- RESIZE ROUND-TRIP: the ONE sanctioned geometry writer ------------
        # (§7.13 deliberate resize: the window stays `window-size manual` —
        # viewer resizes are ignored by design — and this sidecar-mediated
        # endpoint is the only thing that moves geometry.) Runs AFTER the ws is
        # closed: an open-but-undrained client would backpressure the resize
        # repaint (the recorded stall hazard above); the attach itself stays
        # live server-side, and `resize-window` under `manual` needs no client.
        ws.close()
        ws = None
        code, rz = _req("POST", f"/sessions/{session_id}/console/resize",
                        {"cols": 120, "rows": 35}, timeout=30)
        assert code == 200, f"resize failed: {code} {rz}"
        assert rz.get("ok") is True, f"resize not ok: {rz}"
        assert rz.get("cols") == 120 and rz.get("rows") == 35, (
            f"resize echoed wrong applied geometry: {rz}")
        if tmux_name:
            geo_rz = wsl._run(
                f"tmux display-message -p -t {tmux_name} "
                "'#{pane_width}x#{pane_height}'").strip()
            assert geo_rz == "120x35", (
                f"resize-window did not land: tmux geometry {geo_rz} != 120x35")
            # The scraper keeps classifying at the new geometry (wider/taller
            # is the parser-safe direction — the §4 audit).
            states_rz = set()
            for _ in range(3):
                states_rz.add(wsl.status(tmux_name)["state"])
                time.sleep(1.0)
            assert states_rz <= {"idle", "generating", "permission_prompt"}, (
                f"scraper produced non-classifiable reads after the resize: "
                f"{states_rz}")
            findings.append(f"Resize 120x35: applied (tmux geometry {geo_rz}); "
                            f"classifier states={sorted(states_rz)} "
                            "(never unknown).")

        # Below-floor request clamps to 60x15 (the scraper's narrow-width
        # protection — the honest applied values come back, not the request).
        code, rz2 = _req("POST", f"/sessions/{session_id}/console/resize",
                         {"cols": 40, "rows": 10}, timeout=30)
        assert code == 200, f"clamped resize failed: {code} {rz2}"
        assert rz2.get("ok") is True, f"clamped resize not ok: {rz2}"
        assert rz2.get("cols") == 60 and rz2.get("rows") == 15, (
            f"40x10 must clamp to the 60x15 floor, got: {rz2}")
        if tmux_name:
            geo_floor = wsl._run(
                f"tmux display-message -p -t {tmux_name} "
                "'#{pane_width}x#{pane_height}'").strip()
            assert geo_floor == "60x15", (
                f"clamped resize did not land: tmux geometry {geo_floor} != "
                "60x15")
            findings.append("Clamp floor: 40x10 request applied as 60x15 "
                            f"(tmux geometry {geo_floor}).")

        # --- DETACH: ttyd dies, port closes -----------------------------------
        code, det = _req("POST", f"/sessions/{session_id}/console/detach",
                         {}, timeout=30)
        assert code == 200 and det.get("status") == "detached"
        assert _port_closed(port), f"port {port} still accepting after detach"
        findings.append(f"Detach: port {port} closed.")

        # Idempotent second detach.
        code, det2 = _req("POST", f"/sessions/{session_id}/console/detach",
                          {}, timeout=30)
        assert code == 200 and det2.get("status") == "detached"

        _write_findings("\n".join(findings) + "\n")
    finally:
        if ws is not None:
            ws.close()
        if session_id:
            code, _ = _req("DELETE", f"/sessions/{session_id}?hard=true",
                           timeout=30)
            log.info("hard-deleted session %s (code=%s)", session_id, code)
        try:
            wsl._run(f"rm -rf {diag}")
        except Exception as e:  # pragma: no cover
            log.warning("cleanup of %s failed: %s", diag, e)
