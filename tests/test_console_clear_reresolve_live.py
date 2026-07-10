"""LIVE acceptance — post-``/clear`` transcript re-resolve (§7.13, §11 #35).

The spike (``test_console_clear_transcript_live``) proved the HAZARD at the
bridge level: a Console ``/clear`` rotates the agent's JSONL to a new
``<new-id>.jsonl`` while the pinned resolution keeps reading the OLD file, so
post-/clear turns are orphaned. This file proves the FIX end-to-end through the
real sidecar: ``POST /sessions/{id}/console/run {"command":"/clear"}`` now
triggers the driver's ``handle_transcript_rotation()`` (re-pin by rotated
newest-file, or an armed retry until the rotated file appears), and THE
ACCEPTANCE is that a turn sent AFTER the /clear still reaches the sidecar's
event feed (``GET /sessions/{id}/history``) — post-/clear turns are NOT lost.

Also records (``tests/log/clear_reresolve_findings_latest.txt``) which path ran
on this build: immediate (the rotated file already existed when console_run
re-resolved → ``rotated=true``) or deferred (``pending=true`` and the events()
poll adopted it at the first post-/clear turn).

SIDECAR HARNESS: spawns THIS worktree's sidecar (loopback-only — the hook
channel is irrelevant here; transcript polling is the path under test) and
skips if :7690 is already occupied by a foreign build.

ISOLATION (parallel-safe): own ``TmuxBridge()`` for WSL helpers (never
conftest's kill-server fixture); unique names (``clfix-<uuid8>``); own
throwaway WSL cwd; cleans up ONLY its own session (hard delete) + dir; never
``tmux kill-server``; tab-less creation via the sidecar's default.

Run (single file, isolation)::

    .\\.venv\\Scripts\\python.exe -m pytest tests\\test_console_clear_reresolve_live.py -x -q
"""

from __future__ import annotations

import datetime
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

pytestmark = [pytest.mark.integration, pytest.mark.slow]

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from bridge import TmuxBridge  # noqa: E402

log = logging.getLogger("tests.clear_reresolve")

API = "http://127.0.0.1:7690"
SCRATCH = _REPO_ROOT / ".scratch"
LOG_DIR = Path(__file__).parent / "log"
SLUG = "clfix"


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


def _history_has(session_id, needle) -> bool:
    """True when an ASSISTANT event in the sidecar's per-session history carries
    ``needle`` in a text block — the sidecar-visible proof a turn landed."""
    code, events = _req("GET", f"/sessions/{session_id}/history")
    if code != 200 or not isinstance(events, list):
        return False
    for ev in events:
        if ev.get("type") != "assistant":
            continue
        content = ev.get("content")
        if isinstance(content, str) and needle in content:
            return True
        if isinstance(content, list):
            for blk in content:
                if isinstance(blk, dict) and blk.get("type") == "text" \
                        and needle in (blk.get("text") or ""):
                    return True
    return False


def _wait_history(session_id, needle, timeout=150) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if _history_has(session_id, needle):
            return True
        time.sleep(1.0)
    return False


@pytest.fixture(scope="module")
def sidecar():
    """Spawn THIS worktree's sidecar (loopback-only) on :7690; skip if occupied."""
    if _health_ok():
        pytest.skip("a sidecar is already running on :7690 — cannot stand up "
                    "this worktree's build for the live /clear acceptance; "
                    "stop it and re-run")
    SCRATCH.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ)
    env["AWL_SIDECAR_HOST"] = "127.0.0.1"    # hook channel irrelevant here
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
    return TmuxBridge()


def _write_findings(text: str) -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    (LOG_DIR / f"clear_reresolve_findings_{stamp}.txt").write_text(text, encoding="utf-8")
    (LOG_DIR / "clear_reresolve_findings_latest.txt").write_text(text, encoding="utf-8")


def test_console_clear_reresolve_live(sidecar, wsl):
    slug = f"{SLUG}-{uuid.uuid4().hex[:8]}"
    diag = f"/home/lester/awl-{slug}"
    wsl._run(f"mkdir -p {diag}")
    session_id = None
    findings: list[str] = [
        "Console /clear transcript re-resolve — live acceptance (§11 #35)",
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

        # --- PRE-/clear turn: the sidecar sees the codeword (baseline sanity) --
        cw1 = f"PRECLEAR-{uuid.uuid4().hex[:6]}"
        code, _ = _req("POST", f"/sessions/{session_id}/send",
                       {"prompt": f"Reply with exactly: {cw1}"}, timeout=30)
        assert code == 200
        assert _wait_history(session_id, cw1, timeout=120), \
            "pre-/clear turn never reached the sidecar feed — harness broken"

        # --- The Console /clear (the exact production path) --------------------
        code, run = _req("POST", f"/sessions/{session_id}/console/run",
                         {"command": "/clear"}, timeout=60)
        assert code == 200, f"console_run failed: {code} {run}"
        rotation = run.get("transcript_rotation")
        assert rotation is not None, (
            "console_run did not report transcript_rotation for a /clear — "
            f"detection failed. Response: {json.dumps(run)[:400]}"
        )
        log.info("console /clear -> transcript_rotation=%s", rotation)
        findings.append(f"console_run(/clear) -> {json.dumps(rotation)}")
        if rotation.get("rotated"):
            findings.append("Path: IMMEDIATE — the rotated <new-id>.jsonl already "
                            "existed when console_run re-resolved (re-pinned "
                            f"to {rotation.get('claude_session_id')}).")
        else:
            findings.append("Path: DEFERRED — no rotated file at /clear time; "
                            "pending flag armed, events() adopts it at the "
                            "first post-/clear turn.")

        # Give the TUI a moment to settle out of the /clear.
        _wait_status(session_id, "idle", timeout=60)

        # --- THE ACCEPTANCE: a post-/clear turn is NOT lost to the sidecar -----
        cw2 = f"POSTCLEAR-{uuid.uuid4().hex[:6]}"
        code, _ = _req("POST", f"/sessions/{session_id}/send",
                       {"prompt": f"Reply with exactly: {cw2}"}, timeout=30)
        assert code == 200
        seen = _wait_history(session_id, cw2, timeout=180)
        findings.append(f"Post-/clear turn visible to the sidecar: {seen} "
                        f"(codeword {cw2} in GET /sessions/{{id}}/history)")
        assert seen, (
            "ACCEPTANCE FAILED: the post-/clear turn never reached the "
            "sidecar's feed — the re-resolve did not follow the rotated "
            "transcript (the §7.13 orphaning hazard is NOT fixed)."
        )

        # The spike's control: /compact-style continuity — one more turn keeps
        # flowing on the SAME (rotated) resolution.
        cw3 = f"SECOND-{uuid.uuid4().hex[:6]}"
        code, _ = _req("POST", f"/sessions/{session_id}/send",
                       {"prompt": f"Reply with exactly: {cw3}"}, timeout=30)
        assert code == 200
        assert _wait_history(session_id, cw3, timeout=180), \
            "second post-/clear turn was lost — rotated pin did not hold"
        findings.append("Second post-/clear turn also visible — rotated pin holds.")

        _write_findings("\n".join(findings) + "\n")
    finally:
        if session_id:
            code, _ = _req("DELETE", f"/sessions/{session_id}?hard=true",
                           timeout=30)
            log.info("hard-deleted session %s (code=%s)", session_id, code)
        try:
            wsl._run(f"rm -rf {diag}")
        except Exception as e:  # pragma: no cover
            log.warning("cleanup of %s failed: %s", diag, e)
