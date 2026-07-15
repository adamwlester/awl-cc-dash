r"""LIVE acceptance — `/context` breakdown endpoint on a real session (§7.18, §11 #30).

The spike (``test_context_compact_live``) proved the LEVERS: `/context` renders
a parseable per-category split at an idle boundary, and `/compact` writes a
``compact_boundary`` marker. This file proves the BUILD end-to-end through the
real sidecar: ``GET /sessions/{id}/context/breakdown`` on a real bridge agent
returns parsed rows (incl. the stable ``system_prompt`` / ``free_space`` core)
plus the compaction history and a ``fetched_at`` stamp — and the existing JSONL
floor (``GET /sessions/{id}/context``) still serves untouched alongside it.

Verdict recorded in ``tests/log/context_breakdown_findings_latest.txt``.

SIDECAR HARNESS: spawns THIS worktree's sidecar (loopback-only) on :7690 and
skips if the port is already occupied by a foreign build.

ISOLATION (parallel-safe): own ``TmuxBridge()`` for WSL helpers (never
conftest's kill-server fixture); unique names (``ctxbd-<uuid8>``); own
throwaway WSL cwd; cleans up ONLY its own session (hard delete) + dir; never
``tmux kill-server``; tab-less creation via the sidecar's default.

Run (single file, isolation)::

    .\.venv\Scripts\python.exe -m pytest tests\test_context_breakdown_live.py -x -q
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

log = logging.getLogger("tests.context_breakdown")

API = "http://127.0.0.1:7690"
SCRATCH = _REPO_ROOT / ".scratch"
LOG_DIR = Path(__file__).parent / "log"
SLUG = "ctxbd"


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
    (LOG_DIR / f"context_breakdown_findings_{stamp}.txt").write_text(
        text, encoding="utf-8")
    (LOG_DIR / "context_breakdown_findings_latest.txt").write_text(
        text, encoding="utf-8")


def test_context_breakdown_endpoint_live(sidecar, wsl):
    slug = f"{SLUG}-{uuid.uuid4().hex[:8]}"
    diag = f"/home/lester/awl-{slug}"
    wsl._run(f"mkdir -p {diag}")
    session_id = None
    findings: list[str] = [
        "/context breakdown endpoint — live acceptance (§11 #30)",
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

        # One priming turn so the transcript has substance. Tolerant of a
        # logged-out WSL claude (the reply is then the 'Login expired' error —
        # `/context` is a LOCAL command and renders its split regardless).
        code, _ = _req("POST", f"/sessions/{session_id}/send",
                       {"prompt": "In one short sentence, name a famous "
                                  "lighthouse."}, timeout=30)
        assert code == 200
        st = _wait_status(session_id, "idle", timeout=150)
        findings.append(f"priming turn settled with status={st}")
        time.sleep(2)

        # --- THE ACCEPTANCE: the on-demand breakdown pull ---------------------
        # The pull is idle-gated and takes several seconds (bounded /context
        # scrape); a 409 'busy' straight after the turn is retried briefly.
        rows = None
        result = None
        for _ in range(4):
            code, result = _req("GET",
                                f"/sessions/{session_id}/context/breakdown",
                                timeout=60)
            if code == 200:
                rows = result.get("rows")
                break
            assert code == 409, f"unexpected {code}: {result}"
            time.sleep(3)
        assert rows is not None, f"breakdown never left busy: {result}"
        keys = [r["key"] for r in rows]
        findings.append(f"rows parsed: {keys}")
        for row in rows:
            assert row.get("tokens") is not None or row.get("percent") is not None, row
        # CC 2.1.206's compact `/context` view lists only NON-ZERO categories
        # (live-caught 2026-07-15), so a young/logged-out session legitimately
        # omits system_prompt/messages; `free_space` is the always-present
        # anchor and ≥3 rows proves the per-category parse.
        assert "free_space" in keys, (
            f"free_space anchor row missing from the parse: {keys} — "
            f"screen shape drifted on this build; rows={rows}")
        assert len(keys) >= 3, f"too few category rows parsed: {rows}"
        findings.append("note: this build renders only non-zero categories "
                        "(compact view, '/context all to expand') — absent "
                        "rows are zero-usage categories, not parse misses.")
        ch = result.get("compact_history")
        assert isinstance(ch, dict) and "count" in ch and "boundaries" in ch, ch
        assert result.get("fetched_at")
        findings.append(f"compact_history: count={ch['count']} (fresh session — "
                        "0 expected; boundary derivation is Lever-B-proven and "
                        "unit-pinned)")

        # --- The JSONL floor stays untouched alongside the deep readout -------
        code, floor = _req("GET", f"/sessions/{session_id}/context", timeout=30)
        assert code == 200 and isinstance(floor.get("tokens"), int), floor
        findings.append(f"JSONL floor intact: tokens={floor.get('tokens')} "
                        f"percent={floor.get('percent')}")

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
