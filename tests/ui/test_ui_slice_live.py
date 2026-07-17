"""UI slice — frontend client-contract proof against the live sidecar API.

§10 item: **UI slice (frontend)** (META build-table row 10) — the frontend proof
the backend spikes don't cover. NOT ARCHITECTURE §10 item #10 ("One-click launch").

WHAT THIS PROVES
----------------
A browser page that speaks ONLY the ``frontend/src/renderer/api.ts`` contract
(the ``/events`` SSE bus + the POST endpoints) actually:
  1. renders the live feed (SSE ``/events`` → ``#feed`` nodes),
  2. dispatches a prompt (``POST /sessions/{id}/send`` → ``SendResult``),
  3. reflects run-state (``#runstate`` → ``running`` during a turn),
  4. resolves a real tool-permission BOTH ways (``POST /sessions/{id}/permission``
     → approve writes the file, deny does not),
using the same calls the real renderer makes. It rides the ALREADY-TESTED sidecar
API (driver-level truth of the approve/deny paths lives in
``tests/test_bridge_finisher_live.py``); the open question closed here is the
*client contract*, asserted on rendered DOM state via Playwright — never pixels.

WHAT WAS LEARNED (durable notes)
--------------------------------
* The client needs very little from ``/events`` to render: every frame is
  ``{"event":"message","data": <json>}``; each event carries ``id`` (dedup key),
  ``agent_id`` (identity stamp — filter run-state/permission to your own agent),
  ``seq``, ``type``, and — for ``permission_request`` — ``data`` = the parsed
  ``{question, options:[{index,label}], raw}`` detail. Feed rendering needs only
  ``type``/``status``/``seq``; the permission card needs only ``data.question``.
* Run-state is derived two ways and both agree: SSE ``status_change`` events AND
  ``GET /sessions/{id}.status``. The harness polls the session record every 1s as
  the authoritative source and reacts to SSE for snappiness. Permission mode MUST
  be ``default`` at create (the CreateSessionRequest default is ``bypassPermissions``,
  which auto-approves writes → NO prompt would ever appear).
* ``has_pending_permission`` on the session record is the reliable "is a card up?"
  signal; the ``permission_request`` / ``permission_resolved`` SSE events give the
  same transitions live. The harness uses both.

PREREQUISITES (this test arranges them)
---------------------------------------
* **A running sidecar on :7690.** If ``GET /health`` already answers, that instance
  is reused (not torn down). Otherwise this test spawns ``python main.py`` from
  ``sidecar/`` on ``127.0.0.1:7690`` (``AWL_SIDECAR_HOST=127.0.0.1`` — loopback-only,
  so the WSL hook channel degrades; irrelevant here, permission uses screen-state +
  keys, not hooks) and tears it down after.
* **Playwright (sync API) in the same ``.venv``** — installed to *run* the test
  (``pip install playwright`` + ``playwright install chromium``). NOT added to
  ``requirements.txt`` (that durable dep add is FLAGGED to the human, not performed).
* **The fixture page** ``tests/ui/fixture/app.html`` — framework-free, talks only
  to the sidecar HTTP/SSE API, served over ``http://localhost:<port>`` (Playwright
  blocks ``file:``). It imports nothing from ``frontend/``.

ISOLATION RULES (parallel-safe — CRITICAL)
------------------------------------------
* ONE new file (+ its ``fixture/app.html``). Nothing else.
* Uniquely-named session: identity name ``ui-slice-<uuid8>``; the driver's tmux
  name is already unique (``awl-<uuid8>``). Clean up ONLY the ``session_id`` this
  test created, via ``DELETE /sessions/{id}?hard=true``.
* NEVER ``tmux kill-server`` in teardown — it kills sibling agents' live sessions.
* Do NOT depend on conftest's ``bridge`` fixture: its setup AND teardown both call
  ``tmux kill-server``. This module instantiates its OWN ``TmuxBridge()`` and only
  ever ``mkdir``/``cat``/``rm``'s its own throwaway WSL dir.
* Run ONLY this file in isolation (not the whole live tier).
* Do NOT edit ``tests/conftest.py`` / ``pyproject.toml`` / ``tests/README.md``.
  Adding ``tests/ui/`` is the trigger for a small ``pythonpath`` tidy in
  ``pyproject.toml`` — that is FLAGGED to the human, not performed here (this
  module self-inserts the repo root onto ``sys.path`` so it runs standalone).

Run::

    .\\.venv\\Scripts\\python.exe -m pytest tests\\ui\\test_ui_slice_live.py -m integration
"""

import functools
import http.server
import json
import logging
import os
import socketserver
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

# Repo root on sys.path so `from bridge import TmuxBridge` works standalone,
# independent of tests/conftest.py (whose destructive fixtures we must NOT use).
_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from bridge import TmuxBridge  # noqa: E402

# Playwright is a run-time-only dep (installed into .venv, NOT requirements.txt).
try:
    from playwright.sync_api import sync_playwright  # noqa: E402
except ImportError:  # pragma: no cover - environment guard
    pytest.skip("playwright not installed in .venv (pip install playwright + "
                "playwright install chromium)", allow_module_level=True)

log = logging.getLogger("tests.ui_slice")

API = "http://127.0.0.1:7690"
FIXTURE_DIR = Path(__file__).parent / "fixture"
SCRATCH = _REPO_ROOT / ".scratch"
HEADED = os.environ.get("AWL_UISLICE_HEADED") == "1"
MODE = "headed" if HEADED else "headless"

# A slug-prefixed WSL throwaway home for the created agent's cwd.
WSL_HOME = "/home/lester"


# --------------------------------------------------------------------------- #
# HTTP helpers (stdlib only — the fixture PAGE proves the browser contract;
# these are the test's own out-of-band create/read-back/cleanup calls).
# --------------------------------------------------------------------------- #
def _req(method, path, body=None, timeout=20):
    data = None
    headers = {}
    if body is not None:
        data = json.dumps(body).encode()
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(API + path, data=data, headers=headers, method=method)
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


def _session(session_id):
    code, body = _req("GET", f"/sessions/{session_id}")
    return body if code == 200 else None


def _wait_status(session_id, target, timeout=120):
    """Poll GET /sessions/{id} until status == target (or timeout). Returns the
    last-seen status."""
    deadline = time.time() + timeout
    last = None
    while time.time() < deadline:
        s = _session(session_id)
        if s:
            last = s.get("status")
            if last == target:
                return last
        time.sleep(1.0)
    return last


def _cat(bridge, path):
    """cat a file back over the bridge's WSL shell; '__MISSING__' if absent —
    mirrors the finisher's read-back discipline."""
    return bridge._run(f"cat {path} 2>/dev/null || echo __MISSING__")


# --------------------------------------------------------------------------- #
# Fixtures
# --------------------------------------------------------------------------- #
@pytest.fixture(scope="module")
def sidecar():
    """Reuse an already-healthy sidecar on :7690; otherwise spawn one on
    127.0.0.1 for the run and tear it down. Skips (never fabricates a pass) if a
    freshly spawned sidecar can't become healthy."""
    if _health_ok():
        log.info("sidecar already healthy on :7690 — reusing (no lifecycle owned)")
        yield API
        return

    SCRATCH.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ)
    env["AWL_SIDECAR_HOST"] = "127.0.0.1"          # loopback-only dev run
    env["AWL_SIDECAR_RUNTIME"] = str(SCRATCH / "uislice-runtime")
    env["PYTHONUNBUFFERED"] = "1"
    logf = (SCRATCH / "uislice-sidecar.log").open("w", encoding="utf-8")
    log.info("spawning sidecar: %s main.py (cwd=sidecar/)", sys.executable)
    proc = subprocess.Popen(
        [sys.executable, "main.py"],
        cwd=str(_REPO_ROOT / "sidecar"),
        env=env, stdout=logf, stderr=subprocess.STDOUT,
    )
    try:
        for _ in range(80):                        # ~40s to bind + import
            if proc.poll() is not None:
                pytest.skip(f"spawned sidecar exited early (rc={proc.returncode}); "
                            f"see {logf.name}")
            if _health_ok():
                break
            time.sleep(0.5)
        else:
            proc.terminate()
            pytest.skip("spawned sidecar never became healthy on :7690")
        log.info("spawned sidecar healthy")
        yield API
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
        logf.close()


class _QuietHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *args):  # silence per-request stderr noise
        pass


@pytest.fixture(scope="module")
def static_server():
    """Serve tests/ui/fixture/ over http on an ephemeral localhost port
    (Playwright blocks file:)."""
    handler = functools.partial(_QuietHandler, directory=str(FIXTURE_DIR))
    httpd = socketserver.TCPServer(("127.0.0.1", 0), handler)
    port = httpd.server_address[1]
    t = threading.Thread(target=httpd.serve_forever, daemon=True)
    t.start()
    log.info("static fixture server: http://localhost:%d", port)
    yield f"http://localhost:{port}"
    httpd.shutdown()
    httpd.server_close()


@pytest.fixture(scope="module")
def wsl():
    """Our OWN TmuxBridge for WSL shell helpers (mkdir/cat/rm of the throwaway
    dir only). Deliberately NOT the conftest `bridge` fixture (its teardown does
    tmux kill-server). No destructive teardown here."""
    return TmuxBridge()


# --------------------------------------------------------------------------- #
# Screenshot helper (Verifying UI changes → .scratch/, per CLAUDE.md)
# --------------------------------------------------------------------------- #
def _shot(page, name):
    SCRATCH.mkdir(parents=True, exist_ok=True)
    try:
        page.screenshot(path=str(SCRATCH / f"uislice_{MODE}_{name}.png"))
    except Exception as e:  # pragma: no cover - screenshots are diagnostic
        log.warning("screenshot %s failed: %s", name, e)


# --------------------------------------------------------------------------- #
# The test
# --------------------------------------------------------------------------- #
def test_ui_slice_live(sidecar, static_server, wsl):
    slug = f"ui-slice-{uuid.uuid4().hex[:8]}"
    diag = f"{WSL_HOME}/awl-{slug}"
    wsl._run(f"mkdir -p {diag}")
    session_id = None
    try:
        # --- Create a real, tab-less bridge agent in DEFAULT permission mode ---
        code, created = _req("POST", "/sessions", {
            "permission_mode": "default",      # MUST: acceptEdits would auto-approve
            "cwd": diag,
            "identity": {"name": slug},
        }, timeout=60)
        assert code == 200 and created, f"create failed: {code} {created}"
        session_id = created["session_id"]
        log.info("created session %s (identity=%s) cwd=%s", session_id, slug, diag)
        assert created["permission_mode"] == "default"

        # Agent must reach idle (TUI fully loaded) before we drive it.
        st = _wait_status(session_id, "idle", timeout=150)
        assert st == "idle", f"agent never reached idle (last status={st})"

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=not HEADED)
            page = browser.new_context(viewport={"width": 1200, "height": 800}).new_page()
            try:
                url = f"{static_server}/app.html?sid={session_id}&api={API}"
                page.goto(url, wait_until="load")

                # --- (3) Live feed renders: ≥1 .event node from the SSE ring ---
                page.wait_for_function(
                    "document.querySelectorAll('#feed .event').length >= 1",
                    timeout=20000)
                baseline = page.locator("#feed .event").count()
                assert baseline >= 1, "feed did not render any events"
                # run-state reflects idle before we send
                page.wait_for_function(
                    "document.getElementById('runstate').getAttribute('data-state') === 'idle'",
                    timeout=20000)
                _shot(page, "feed_base")
                log.info("feed baseline=%d, runstate=idle", baseline)

                # --- (4) Send a Write prompt via the fixture's control ---
                page.fill("#prompt",
                          "Create a file named ui.txt containing exactly the word "
                          "mango. Use the Write tool. Do nothing else.")
                page.click("#send")
                # The POST returned a SendResult (status sent/queued) — read it back.
                page.wait_for_function(
                    "window.__lastSend && window.__lastSend.status", timeout=15000)
                send_status = page.evaluate("window.__lastSend.status")
                assert send_status in ("sent", "queued"), f"unexpected send result: {send_status}"
                log.info("send dispatched: %s", send_status)

                # --- (5) Run-state flips to running during the turn (read from DOM) ---
                page.wait_for_function(
                    "document.getElementById('runstate').getAttribute('data-state') === 'running'",
                    timeout=60000)
                assert page.locator("#runstate").inner_text().strip() == "running"
                _shot(page, "running")

                # --- (6) Permission APPROVE: real permission_request card appears ---
                page.wait_for_selector("#permission.pending", timeout=120000)
                assert page.locator("#permission.pending").is_visible()
                # feed grew after the send (assistant/tool + status/permission events)
                grown = page.locator("#feed .event").count()
                assert grown > baseline, f"feed did not grow after send ({grown} <= {baseline})"
                # Screenshot the richest control at narrow AND wide extremes.
                page.set_viewport_size({"width": 420, "height": 900})
                _shot(page, "perm_narrow")
                page.set_viewport_size({"width": 1400, "height": 900})
                _shot(page, "perm_wide")
                page.set_viewport_size({"width": 1200, "height": 800})

                page.click("#approve")
                # UI reflects resolution: card leaves 'pending'
                page.wait_for_function(
                    "!document.getElementById('permission').classList.contains('pending')",
                    timeout=30000)
                assert not page.locator("#permission").evaluate(
                    "el => el.classList.contains('pending')")
                page.wait_for_function("window.__lastPermission", timeout=10000)
                _shot(page, "approve_resolved")
                # Session-record read-back: pending flag cleared.
                s = _session(session_id)
                assert s and s["has_pending_permission"] is False, \
                    "has_pending_permission did not clear after approve"

                # Read-back CRUX: the file was actually written.
                written = None
                for _ in range(60):
                    written = _cat(wsl, f"{diag}/ui.txt")
                    if written == "mango":
                        break
                    time.sleep(0.5)
                assert written == "mango", f"approve did not write ui.txt (got {written!r})"
                log.info("approve read-back OK: ui.txt == 'mango'")

                # Let the approve turn finish before the next prompt.
                _wait_status(session_id, "idle", timeout=90)

                # --- (7) Permission DENY (fresh prompt for a different file) ---
                page.fill("#prompt",
                          "Create a file named deny.txt containing exactly the word "
                          "cherry. Use the Write tool. Do nothing else.")
                page.click("#send")
                page.wait_for_function(
                    "window.__lastSend && window.__lastSend.status", timeout=15000)
                page.wait_for_selector("#permission.pending", timeout=120000)
                _shot(page, "deny_pending")
                page.click("#deny")
                page.wait_for_function(
                    "!document.getElementById('permission').classList.contains('pending')",
                    timeout=30000)
                deny_answer = page.evaluate("window.__lastPermission")
                assert deny_answer, "deny answer never posted"
                _shot(page, "deny_resolved")
                s = _session(session_id)
                assert s and s["has_pending_permission"] is False, \
                    "has_pending_permission did not clear after deny"

                # Read-back CRUX: the file was NOT written.
                time.sleep(3)
                denied = _cat(wsl, f"{diag}/deny.txt")
                assert denied == "__MISSING__", \
                    f"deny should NOT have written deny.txt (got {denied!r})"
                log.info("deny read-back OK: deny.txt is __MISSING__")
            finally:
                browser.close()
    finally:
        # Retire ONLY our own session (drives the driver's single-session close);
        # remove ONLY our own throwaway dir. Never tmux kill-server.
        if session_id:
            code, _ = _req("DELETE", f"/sessions/{session_id}?hard=true", timeout=30)
            log.info("hard-deleted session %s (code=%s)", session_id, code)
        try:
            wsl._run(f"rm -rf {diag}")
        except Exception as e:  # pragma: no cover
            log.warning("cleanup of %s failed: %s", diag, e)
