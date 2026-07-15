r"""LIVE acceptance — per-agent cost endpoint on a real session (§7.15, §11 #32).

The spike (``test_per_agent_cost_live``) proved the HARVEST: `/cost` renders a
per-session ``Total cost: $X`` panel — a defensible, non-fabricated per-agent
figure. This file proves the BUILD end-to-end through the real sidecar:
``GET /sessions/{id}/cost`` on a real bridge agent returns the
``{usd, per_model, raw, fetched_at}`` shape. SHAPE, not amount: a fresh
session's cost may read $0 (or, on a logged-out/subscription build with no
panel, ``usd: null`` — the endpoint's honest miss); whichever this build
returned is recorded in ``tests/log/cost_endpoint_findings_latest.txt``.

SIDECAR HARNESS: spawns THIS worktree's sidecar (loopback-only) on :7690 and
skips if the port is already occupied by a foreign build.

ISOLATION (parallel-safe): own ``TmuxBridge()`` for WSL helpers (never
conftest's kill-server fixture); unique names (``costep-<uuid8>``); own
throwaway WSL cwd; cleans up ONLY its own session (hard delete) + dir; never
``tmux kill-server``; tab-less creation via the sidecar's default.

Run (single file, isolation)::

    .\.venv\Scripts\python.exe -m pytest tests\test_cost_endpoint_live.py -x -q
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

log = logging.getLogger("tests.cost_endpoint")

API = "http://127.0.0.1:7690"
SCRATCH = _REPO_ROOT / ".scratch"
LOG_DIR = Path(__file__).parent / "log"
SLUG = "costep"


def _req(method, path, body=None, timeout=30):
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


def _wait_status(session_id, target, timeout=150):
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


@pytest.fixture(scope="module")
def sidecar():
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
                pytest.skip(f"spawned sidecar exited early (rc={proc.returncode})")
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
    (LOG_DIR / f"cost_endpoint_findings_{stamp}.txt").write_text(
        text, encoding="utf-8")
    (LOG_DIR / "cost_endpoint_findings_latest.txt").write_text(
        text, encoding="utf-8")


def test_cost_endpoint_live(sidecar, wsl):
    slug = f"{SLUG}-{uuid.uuid4().hex[:8]}"
    diag = f"/home/lester/awl-{slug}"
    wsl._run(f"mkdir -p {diag}")
    session_id = None
    findings: list[str] = [
        "Per-agent cost endpoint — live acceptance (§11 #32)",
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

        # One turn so the session has SOMETHING to price (tolerant of a
        # logged-out claude — the /cost dialog renders regardless).
        code, _ = _req("POST", f"/sessions/{session_id}/send",
                       {"prompt": "Reply with exactly: COST-EP-OK"}, timeout=30)
        assert code == 200
        _wait_status(session_id, "idle", timeout=150)
        time.sleep(2)

        # --- THE ACCEPTANCE: shape, not amount --------------------------------
        result = None
        for _ in range(4):
            code, result = _req("GET", f"/sessions/{session_id}/cost",
                                timeout=60)
            if code == 200:
                break
            assert code == 409, f"unexpected {code}: {result}"
            time.sleep(3)
        assert code == 200, f"cost endpoint never left busy: {result}"
        assert set(result) >= {"usd", "per_model", "raw", "fetched_at"}, result
        usd = result["usd"]
        assert usd is None or (isinstance(usd, (int, float)) and usd >= 0.0), result
        assert isinstance(result["per_model"], list), result
        if usd is not None:
            findings.append(f"per-session Total cost harvested: ${usd:.4f} "
                            f"(per-model figures: {result['per_model']})")
        else:
            findings.append("usd=null — no per-session Total-cost panel "
                            "rendered on this build/account state (the "
                            "endpoint's honest miss; raw excerpt kept). "
                            f"raw tail: {result['raw'][-300:]!r}")
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
