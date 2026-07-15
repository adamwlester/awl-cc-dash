"""LIVE verify — hook run-state ingestion through the REAL sidecar (§7.4/§7.17, §11 #21).

The hermetic half of #21 (the arbiter, ``sidecar/runstate.py`` +
``test_runstate_unit.py``) proves the merge/dedup logic; THIS file is the live
half: a real uvicorn sidecar on ``0.0.0.0:7690``, a real tab-less bridge agent
launched with the production hook set (``_build_hook_settings``), and the
question *do the registered lifecycle hooks actually POST run-state back through
the WSL gateway into the arbiter on the installed CLI build?* Asserted over
plain HTTP the way the dashboard reads it (``GET /sessions/{id}`` →
``run_state``), never by reaching into process internals.

WHAT IT ASSERTS
---------------
1. **Push channel is live:** shortly after a prompt is dispatched,
   ``run_state.source == "push"`` (the hooks really deliver over the WSL
   gateway) and ``run_state.permission_mode`` is populated from a mode-bearing
   event ("default" — the launch mode).
2. **prompt_id:** recorded from GENUINE deliveries (the env-guarded
   ``AWL_RUNSTATE_DEBUG=1`` capture, read via
   ``GET /internal/debug/run-state/{agent}``). §7.4 expects it on v2.1.196+;
   the verdict (present/absent + which events carry it) is asserted when
   present and recorded honestly either way.
3. **Concurrent-load coherence:** ~30 synthetic concurrent POSTs at
   ``/internal/hooks/run-state/{id}`` (mixed events, incl. ``Notification``
   WITHOUT ``permission_mode`` and with a bogus one) interleave with the
   genuine stream — every POST answers 200 and the final record stays coherent
   (the mode is never clobbered by a Notification; phase settles to idle).
4. **Subagent channel (best-effort observation):** a turn that spawns a real
   subagent records whether ``SubagentStart``/``SubagentStop`` fire on this
   build and what they carry (the 2.1.198 spike found SubagentStart never
   fires; re-checked here on the installed build, recorded — not hard-asserted).

FINDINGS → ``tests/log/hook_ingest_findings_latest.txt`` (+ timestamped copy):
the exact CLI version, per-event fired/mode/prompt_id/payload-keys table,
registered-but-never-fired events, the prompt_id verdict, and the
concurrent-burst result.

SIDECAR HARNESS (differs from tests/ui's reuse-or-spawn — deliberately)
----------------------------------------------------------------------
This test must exercise THIS worktree's sidecar build with
``AWL_RUNSTATE_DEBUG=1`` and a WSL-reachable bind (0.0.0.0 — the hook channel
does not work over loopback, see the hook spike). A foreign sidecar already on
:7690 can't satisfy either, so instead of reusing it (the ui-slice pattern) we
SKIP with a clear message — reusing an unknown build would falsify the verify.

ISOLATION (parallel-safe)
-------------------------
* Own ``TmuxBridge()`` — never conftest's kill-server ``bridge`` fixture.
* Unique names (``hookingest-<uuid8>``), own throwaway WSL cwd, tab-less
  creation via the sidecar's default (show is never used).
* Cleans up ONLY its own session (``DELETE /sessions/{id}?hard=true``) + its
  own diag dir; NEVER ``tmux kill-server``.

Run (single file, isolation)::

    .\\.venv\\Scripts\\python.exe -m pytest tests\\test_hook_ingest_live.py -x -q
"""

from __future__ import annotations

import datetime
import json
import logging
import os
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

log = logging.getLogger("tests.hook_ingest")

API = "http://127.0.0.1:7690"
SCRATCH = _REPO_ROOT / ".scratch"
LOG_DIR = Path(__file__).parent / "log"
SLUG = "hookingest"

# The hook events _build_hook_settings registers that INGEST into the arbiter
# (plan/decision PreToolUse hooks raise inbox cards — different channel).
_REGISTERED_INGESTING = {
    "PreToolUse", "PostToolUse", "Stop", "UserPromptSubmit", "Notification",
    "SubagentStart", "SubagentStop",
}


# --------------------------------------------------------------------------- #
# stdlib HTTP helpers
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


def _session(session_id):
    code, body = _req("GET", f"/sessions/{session_id}")
    return body if code == 200 else None


def _wait_status(session_id, target, timeout=120, approve_permissions=False):
    """Poll GET /sessions/{id} until status == target. Optionally auto-approve
    any pending tool-permission prompt on the way (keeps a gated tool from
    stalling the turn). Returns the last-seen status."""
    deadline = time.time() + timeout
    last = None
    while time.time() < deadline:
        s = _session(session_id)
        if s:
            last = s.get("status")
            if approve_permissions and s.get("has_pending_permission"):
                _req("POST", f"/sessions/{session_id}/permission",
                     {"approve": True})
            if last == target:
                return last
        time.sleep(1.0)
    return last


def _cli_version():
    try:
        r = subprocess.run(
            ["wsl", "-d", "Ubuntu", "--", "bash", "-lc", "claude --version"],
            capture_output=True, text=True, timeout=30,
        )
        return (r.stdout.strip() or r.stderr.strip() or "unknown").splitlines()[0]
    except Exception as e:  # pragma: no cover - environment dependent
        return f"unknown ({e})"


# --------------------------------------------------------------------------- #
# Fixtures
# --------------------------------------------------------------------------- #
@pytest.fixture(scope="module")
def sidecar():
    """Spawn THIS worktree's sidecar on 0.0.0.0:7690 with AWL_RUNSTATE_DEBUG=1.

    Skips (never reuses) when :7690 is already occupied — a foreign sidecar is
    the wrong build, lacks the debug capture, and may bind loopback-only (which
    silently kills the hook channel this test exists to verify)."""
    if _health_ok():
        pytest.skip("a sidecar is already running on :7690 — cannot stand up "
                    "this worktree's build for the live hook verify; stop it "
                    "and re-run")
    SCRATCH.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ)
    env["AWL_SIDECAR_RUNTIME"] = str(SCRATCH / f"{SLUG}-runtime")
    env["AWL_RUNSTATE_DEBUG"] = "1"          # env-guarded ingest capture
    env["PYTHONUNBUFFERED"] = "1"
    env.pop("AWL_SIDECAR_HOST", None)        # default 0.0.0.0 = WSL-reachable
    logf = (SCRATCH / f"{SLUG}-sidecar.log").open("w", encoding="utf-8")
    log.info("spawning sidecar: %s main.py (cwd=sidecar/, host=0.0.0.0)",
             sys.executable)
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
        log.info("spawned sidecar healthy")
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
    """Our OWN TmuxBridge for WSL shell helpers + the gateway pre-flight. Never
    conftest's `bridge` fixture (its teardown is tmux kill-server)."""
    return TmuxBridge()


# --------------------------------------------------------------------------- #
# Findings record
# --------------------------------------------------------------------------- #
def _write_findings(text: str) -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    (LOG_DIR / f"hook_ingest_findings_{stamp}.txt").write_text(text, encoding="utf-8")
    (LOG_DIR / "hook_ingest_findings_latest.txt").write_text(text, encoding="utf-8")
    log.info("findings -> %s", LOG_DIR / "hook_ingest_findings_latest.txt")


def _summarize_deliveries(deliveries: list[dict]) -> dict[str, dict]:
    """Per-event: count, permission_mode presence/values, prompt_id presence,
    tool presence, and the union of payload keys."""
    by_event: dict[str, dict] = {}
    for d in deliveries:
        ev = d.get("event") or "?"
        slot = by_event.setdefault(ev, {
            "count": 0, "with_mode": 0, "modes": set(),
            "with_prompt_id": 0, "with_tool": 0, "tools": set(), "keys": set(),
        })
        slot["count"] += 1
        if d.get("permission_mode"):
            slot["with_mode"] += 1
            slot["modes"].add(d["permission_mode"])
        if d.get("prompt_id") is not None:
            slot["with_prompt_id"] += 1
        if d.get("tool_name"):
            slot["with_tool"] += 1
            slot["tools"].add(d["tool_name"])
        slot["keys"].update(d.get("payload_keys") or [])
    return by_event


# --------------------------------------------------------------------------- #
# The test
# --------------------------------------------------------------------------- #
def test_hook_ingest_live(sidecar, wsl):
    slug = f"{SLUG}-{uuid.uuid4().hex[:8]}"
    diag = f"/home/lester/awl-{slug}"
    session_id = None
    findings: list[str] = []
    cli_version = _cli_version()
    findings.append(f"Hook run-state ingestion — live verify (§11 #21)")
    findings.append(f"Date:        {datetime.datetime.now().isoformat(timespec='seconds')}")
    findings.append(f"Claude CLI:  {cli_version}")
    findings.append(f"Sidecar:     worktree build, 0.0.0.0:7690, AWL_RUNSTATE_DEBUG=1")

    # --- Gateway pre-flight (skip-gate, not a fabricated pass) ----------------
    base = wsl.sidecar_hook_base_url()
    if not base:
        pytest.skip("environment: WSL2 default gateway did not resolve — the "
                    "hook channel cannot be built here")
    code = wsl._run(
        f"curl -s -m 5 -o /dev/null -w '%{{http_code}}' {base}/health", timeout=20,
    ).strip()
    if code != "200":
        pytest.skip(f"environment: WSL cannot reach the sidecar over the gateway "
                    f"({base}/health -> {code!r}) — the production hook path is "
                    f"unavailable in this environment")
    findings.append(f"Gateway:     {base} (WSL->host preflight 200)")

    try:
        wsl._run(f"mkdir -p {diag} && printf %s alpha > {diag}/a.txt && "
                 f"printf %s beta > {diag}/b.txt")

        # --- Create a real, tab-less bridge agent (default mode) --------------
        code, created = _req("POST", "/sessions", {
            "permission_mode": "default",
            "cwd": diag,
            "identity": {"name": slug},
        }, timeout=60)
        assert code == 200 and created, f"create failed: {code} {created}"
        session_id = created["session_id"]
        log.info("created session %s cwd=%s", session_id, diag)
        st = _wait_status(session_id, "idle", timeout=150)
        assert st == "idle", f"agent never reached idle (last status={st})"
        rs0 = _session(session_id)["run_state"]
        log.info("baseline run_state: %s", rs0)

        # ======================================================================
        # Phase A — a ≥2-tool-use turn; genuine hooks must push run-state.
        # ======================================================================
        code, sent = _req("POST", f"/sessions/{session_id}/send", {
            "prompt": "Use the Read tool to read ./a.txt, then use the Read "
                      "tool again to read ./b.txt, then reply with exactly the "
                      "word DONE and nothing else.",
        }, timeout=30)
        assert code == 200 and sent.get("status") in ("sent", "queued"), \
            f"send failed: {code} {sent}"

        # Poll run_state at high cadence: the crux is source=="push" (+ a mode)
        # BEFORE any synthetic traffic exists — proof the real hooks POST back.
        transitions: list[tuple[float, str, str, str, str]] = []
        pushed = None
        deadline = time.time() + 90
        while time.time() < deadline:
            s = _session(session_id)
            rs = (s or {}).get("run_state") or {}
            key = (rs.get("source"), rs.get("last_event"), rs.get("phase"),
                   rs.get("current_tool"), rs.get("permission_mode"))
            if not transitions or transitions[-1][1:] != key:
                transitions.append((round(time.time() % 1000, 1), *key))
            if rs.get("source") == "push" and rs.get("permission_mode"):
                pushed = rs
                break
            time.sleep(0.25)
        log.info("run_state transitions (pre-synthetic): %s", transitions)
        assert pushed is not None, (
            "run_state never reported source='push' with a permission_mode "
            f"within 90s of a dispatched prompt — the registered hooks did not "
            f"deliver. Last transitions: {transitions[-5:]}"
        )
        # (1) The hooks really POST back through the WSL gateway…
        assert pushed["source"] == "push"
        # …and the mode is populated from a mode-bearing event with the mode the
        # agent was launched in (Notification can never set it — arbiter rule).
        assert pushed["permission_mode"] == "default", pushed
        genuine_prompt_id = pushed.get("prompt_id")
        findings.append("")
        findings.append("(1) PUSH CHANNEL: WORKS — run_state.source='push' with "
                        f"permission_mode='default' (last_event={pushed['last_event']}, "
                        f"age_s={pushed['age_s']})")

        # ======================================================================
        # Phase B — ~30 synthetic concurrent POSTs interleave with the genuine
        # stream. Every payload carries a "synthetic" marker so the debug
        # capture can split genuine from synthetic afterwards.
        # ======================================================================
        burst: list[dict] = []
        for i in range(10):     # Notification WITHOUT permission_mode
            burst.append({"hook_event_name": "Notification",
                          "message": f"synthetic-{i}", "synthetic": True})
        for i in range(5):      # Notification with a BOGUS mode (must be ignored)
            burst.append({"hook_event_name": "Notification",
                          "permission_mode": "bypassPermissions",
                          "synthetic": True})
        for i in range(10):     # distinct PostToolUse boundaries
            burst.append({"hook_event_name": "PostToolUse",
                          "permission_mode": "default",
                          "tool_name": "SynthTool",
                          "tool_use_id": f"synthetic-{i}",
                          "prompt_id": "synthetic-p", "synthetic": True})
        dup = {"hook_event_name": "PostToolUse", "permission_mode": "default",
               "tool_name": "SynthTool", "tool_use_id": "synthetic-dup",
               "prompt_id": "synthetic-p", "synthetic": True}
        burst.extend([dict(dup) for _ in range(5)])   # exact redeliveries

        statuses: list[int] = []
        lock = threading.Lock()

        def fire(payload):
            code, _ = _req("POST", f"/internal/hooks/run-state/{session_id}",
                           payload, timeout=15)
            with lock:
                statuses.append(code)

        threads = [threading.Thread(target=fire, args=(p,)) for p in burst]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert len(statuses) == len(burst) == 30
        assert all(c == 200 for c in statuses), (
            f"synthetic concurrent POSTs saw non-200s: "
            f"{sorted(set(statuses))}"
        )
        log.info("synthetic burst: %d POSTs, all 200", len(statuses))

        # Let the turn finish, then let push freshness settle: the final record
        # must be coherent — phase back to idle, mode NEVER clobbered by the
        # Notification flood (neither None'd nor flipped to bypassPermissions).
        st = _wait_status(session_id, "idle", timeout=180,
                          approve_permissions=True)
        assert st == "idle", f"turn never settled (last status={st})"
        final_rs = None
        deadline = time.time() + 30
        while time.time() < deadline:
            final_rs = _session(session_id)["run_state"]
            if final_rs.get("phase") == "idle":
                break
            time.sleep(1.0)
        assert final_rs and final_rs.get("phase") == "idle", (
            f"run_state phase never settled to idle after the turn: {final_rs}"
        )
        assert final_rs["permission_mode"] == "default", (
            f"mode was clobbered under concurrent load: {final_rs}"
        )
        findings.append("(3) CONCURRENT LOAD: 30 synthetic POSTs (10 "
                        "Notification w/o mode, 5 Notification w/ bogus mode, "
                        "10 distinct PostToolUse, 5 exact duplicates) — all "
                        "200; final record coherent (phase=idle, "
                        "permission_mode='default' — never clobbered).")

        # ======================================================================
        # Phase C — spawn a real subagent: does SubagentStart/SubagentStop fire
        # on this build, and what do the payloads carry? (Recorded, and the
        # roster blend is checked when the registry actually populated.)
        # ======================================================================
        code, sent = _req("POST", f"/sessions/{session_id}/send", {
            "prompt": "Use the Agent tool to spawn one subagent of type "
                      "general-purpose whose prompt is: Reply with exactly the "
                      "word OK. When it returns, reply DONE.",
        }, timeout=30)
        assert code == 200, f"subagent send failed: {code} {sent}"
        _wait_status(session_id, "running", timeout=60)
        st = _wait_status(session_id, "idle", timeout=300,
                          approve_permissions=True)
        log.info("subagent turn settled: status=%s", st)
        code, subs = _req("GET", f"/sessions/{session_id}/subagents")
        log.info("GET /subagents -> %s %s", code, json.dumps(subs)[:600])

        # ======================================================================
        # Read back the debug capture: EXACTLY which events the CLI fired.
        # ======================================================================
        code, dbg = _req("GET", f"/internal/debug/run-state/{session_id}")
        assert code == 200, f"debug endpoint unavailable ({code}) — was the " \
                            f"sidecar spawned with AWL_RUNSTATE_DEBUG=1?"
        deliveries = dbg["deliveries"]
        genuine = [d for d in deliveries
                   if "synthetic" not in (d.get("payload_keys") or [])]
        synthetic = [d for d in deliveries if d not in genuine]
        by_event = _summarize_deliveries(genuine)
        fired = set(by_event.keys())
        never_fired = sorted(_REGISTERED_INGESTING - fired)

        findings.append("")
        findings.append(f"GENUINE hook deliveries ingested: {len(genuine)} "
                        f"(+{len(synthetic)} synthetic)")
        findings.append("Per-event (genuine only):")
        for ev, s in sorted(by_event.items()):
            findings.append(
                f"  {ev:<18} count={s['count']:<3} "
                f"mode={s['with_mode']}/{s['count']} {sorted(s['modes'])} "
                f"prompt_id={s['with_prompt_id']}/{s['count']} "
                f"tool={s['with_tool']}/{s['count']} {sorted(s['tools'])[:6]}"
            )
            findings.append(f"  {'':<18} payload keys: {sorted(s['keys'])}")
        findings.append(f"Registered-but-never-fired (this flow): {never_fired}")
        findings.append(f"Notification fired: {'Notification' in fired}")
        findings.append(f"SubagentStart fired: {'SubagentStart' in fired}; "
                        f"SubagentStop fired: {'SubagentStop' in fired}")
        if code == 200 and isinstance(subs, dict):
            findings.append(f"GET /subagents blend: count={subs.get('count')} "
                            f"(hook-fed registry entries appear when Subagent* "
                            f"payloads carry agent_id)")

        # Subagent transcript-path mapping (the live-mapped 2.1.206 reality):
        # the payload's plain transcript_path is the PARENT's; the subagent's
        # own file rides agent_transcript_path — and the registry must store
        # the subagent's own, never the parent's.
        sub_deliveries = [d for d in genuine
                          if d["event"] in ("SubagentStart", "SubagentStop")]
        for d in sub_deliveries:
            findings.append(f"  {d['event']}: transcript_path="
                            f"{d.get('transcript_path')!r} "
                            f"agent_transcript_path="
                            f"{d.get('agent_transcript_path')!r}")
        own_paths = {d["agent_transcript_path"] for d in sub_deliveries
                     if d.get("agent_transcript_path")}
        if own_paths and isinstance(subs, dict):
            registry_paths = {s.get("transcript_path")
                              for s in subs.get("subagents", [])
                              if s.get("transcript_path")}
            assert own_paths & registry_paths, (
                "the subagent registry never stored the subagent's OWN "
                f"transcript (agent_transcript_path={sorted(own_paths)}; "
                f"registry={sorted(registry_paths)}) — parent-path mapping bug"
            )
            parent_paths = {d["transcript_path"] for d in sub_deliveries
                            if d.get("transcript_path")}
            assert not (parent_paths & registry_paths), (
                "the registry stored the PARENT session's transcript_path on a "
                f"subagent record: {sorted(parent_paths & registry_paths)}"
            )
            findings.append("Subagent registry stores the subagent's OWN "
                            "transcript (agent_transcript_path) — parent-path "
                            "never pinned.")

        # Sanity: the tool/turn events the push architecture depends on fired.
        assert {"PreToolUse", "PostToolUse", "Stop"} & fired, (
            f"no tool/turn event was ingested from the REAL agent — hook set "
            f"mis-wired? fired={sorted(fired)}"
        )

        # (2) prompt_id verdict — from GENUINE deliveries only (synthetics carry
        # prompt_id='synthetic-p' and must not fake the verdict).
        with_pid = [d for d in genuine if d.get("prompt_id") is not None]
        if with_pid:
            events_with_pid = sorted({d["event"] for d in with_pid})
            findings.append("")
            findings.append(f"(2) prompt_id: PRESENT on this build "
                            f"({cli_version}) — carried by {events_with_pid}; "
                            f"§7.4's v2.1.196+ floor holds.")
            # It must also have surfaced through the public run_state read.
            assert genuine_prompt_id is not None or \
                final_rs.get("prompt_id") is not None, (
                "prompt_id present in payloads but never surfaced via "
                "GET /sessions/{id}.run_state"
            )
        else:
            findings.append("")
            findings.append(f"(2) prompt_id: ABSENT from every genuine hook "
                            f"payload on this build ({cli_version}) — recorded "
                            f"honestly; §7.4's v2.1.196+ expectation does NOT "
                            f"hold here.")

        findings.append("")
        findings.append("run_state transitions sampled during Phase A "
                        "(poll-cadence ~0.25s; sub-poll boundaries can be "
                        "missed — the debug table above is the exact record):")
        for t in transitions:
            findings.append(f"  t={t[0]:>6}s source={t[1]} last_event={t[2]} "
                            f"phase={t[3]} tool={t[4]} mode={t[5]}")

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
