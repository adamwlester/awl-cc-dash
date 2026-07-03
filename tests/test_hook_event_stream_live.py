"""Live spike — hook-driven run-state / permission-mode push channel.

§10 item #14 ("Hook-driven run-state / permission-mode push channel — hook event
stream", 🧪 needs-spike; docs/ARCHITECTURE.md §10 #14 → §6.2, §7.4, §7.11). This
is a SPIKE-OR-OMIT task: the deliverable is the *payload contents*, not a green.

The empirical sub-question research-14 flags for verification (and that this
spike answers on the installed CLI build): **does an HTTP-hook payload actually
carry `permission_mode` + the current tool on every tool/turn event?** The
mode-control research states "every tool/turn hook payload carries
`permission_mode` for free" as fact; the design-research prompt downgrades that
to *plausible, prior-art-observed — confirm on the installed CLI build*. The
v2.1.90 source only documents `tool_name`/`tool_input` on the payload and does
NOT confirm `permission_mode`, so this is the exact gap the spike closes.

WHAT THIS DOES
--------------
Stands up a tiny in-test HTTP receiver on an ephemeral port bound to 0.0.0.0,
reachable from the WSL agent over the WSL2 default-gateway URL (the same path the
production driver builds via ``sidecar_hook_base_url()`` — pre-flight-verified in
this test before the agent is launched). It registers a BROAD candidate hook set
(the documented events plus the research's may-not-exist candidates) pointing at
that receiver, launches a real Claude Code TUI in DEFAULT mode, drives it through
a Read (auto-approved in default mode → PreToolUse/PostToolUse fire cleanly) and
a Write (which raises a permission prompt), then inspects the RAW JSON payloads
the receiver captured: per event, whether ``permission_mode`` and the current
tool (``tool_name``) are present and correct, which candidate events actually
fired, and any ordering/dedup observation.

READ-BACK IS THE CRUX (§5 of the build prompt): we do NOT assert "a POST
arrived" (transport is already known from the finisher). We assert on the FIELDS,
or record their absence as the finding:
  * WORKS  — a tool/turn payload carries a sane ``permission_mode`` → the test
             asserts the fields green. The push channel can be the
             authoritative-when-present run-state signal (polling as fallback).
  * NEGATIVE — hooks fire but ``permission_mode`` is absent → the test asserts
             what IS present (``tool_name`` on PreToolUse) then ``pytest.xfail``s
             carrying the finding. No fabricated green. The push channel then
             augments but cannot REPLACE screen-polling for mode; screen-state
             polling stays primary (the §14 fallback).

FINDINGS (live, Claude Code 2.1.198, 2026-07-02) — WORKS
--------------------------------------------------------
The "live mode for free" claim HOLDS on this build. ``permission_mode`` is
present on EVERY tool/turn event: PreToolUse (3/3), PostToolUse (2/2), Stop
(2/2), UserPromptSubmit (3/3), SubagentStop (2/2), PermissionRequest (1/1). The
lone exception is ``Notification`` (0/1 — no ``permission_mode``). The current
tool rides ``tool_name`` (+ full ``tool_input`` + ``tool_use_id``) on the
tool-scoped events (PreToolUse/PostToolUse/PermissionRequest). The payload is
richer than expected — it also carries ``effort.level``, ``cwd``, ``session_id``,
``transcript_path``, ``prompt_id`` (and Stop adds ``last_assistant_message``),
i.e. a full run-state push, not just the mode.

The pushed mode is AUTHORITATIVE and tracks a LIVE change: after one Shift+Tab
(``BTab``) to acceptEdits, the subsequent payloads report
``permission_mode: "acceptEdits"``.

Event coverage on 2.1.198 — real & firing: PreToolUse, PostToolUse, Stop,
SubagentStop, UserPromptSubmit, Notification, and — notably — ``PermissionRequest``
(research had flagged it "may not exist"; it IS real here, and fires AFTER
PreToolUse for a gated tool). Candidates that did NOT fire: ``StopFailure`` and
``SubagentStart`` (consistent with "may not exist" on this build). SessionStart /
SessionEnd / PreCompact were registered but did not fire in this flow (SessionEnd
/ PreCompact need a clean exit / a compact; SessionStart's absence is a
timing/matcher note, not proof it is unreal). Quirk: ``SubagentStop`` fires at
every turn-end even with NO subagent spawned.

Ordering / dedup (SINGLE agent): clean per-turn order UserPromptSubmit ->
PreToolUse -> (PermissionRequest, for a gated tool) -> PostToolUse -> Stop ->
SubagentStop; ZERO duplicate ``(event, tool_use_id)`` arrivals; sub-second
tool-boundary latency (PreToolUse->PostToolUse ~150-200 ms). Concurrent-load
ordering/dedup (the sequence-number / per-session arbiter question) is NOT
covered by this single-agent spike and still needs a multi-agent test.

Recommendation for research-14 (replace-vs-run-alongside): the push channel
carries authoritative ``permission_mode`` + current tool + run-state boundaries,
so hooks CAN be the authoritative-when-present run-state layer — but should RUN
ALONGSIDE polling, not fully replace it, because (a) ``Notification`` lacks
``permission_mode``, (b) hookless sessions still need the screen-poll floor, and
(c) concurrent ordering/dedup is unverified. That matches §14's Desired behavior
(authoritative-when-present, polling as fallback).

The module docstring is the summary; the DEBUG log in tests/log/ + the DEVLOG
entry carry the full per-event table, the raw payloads, and the arrival
sequence with latencies.

PARALLEL-SAFE ISOLATION (CRITICAL — sibling agents may run their own live
sessions concurrently; violating any of these can kill their work):
  * ONE new file only; uniquely-named, slug-prefixed session ``hookstream-<uuid8>``.
  * Receiver bound to an EPHEMERAL port (``0``) so two sibling spikes can't
    collide on a fixed port; shut down in teardown.
  * NEVER ``tmux kill-server`` / ``bridge.shutdown()`` — tear down ONLY this
    session via ``bridge.close(name)`` + ``rm -rf`` this test's own diag dir.
  * Does NOT use conftest's session-scoped ``bridge`` fixture (its setup AND
    teardown call ``_kill_all_tmux()`` = ``tmux kill-server``, which would kill
    siblings). We instantiate our OWN ``TmuxBridge()``.
  * No shared-file edits (conftest.py / pyproject.toml / tests/README.md); no
    persistent hook registrations added to the real running sidecar's config —
    the spike's hooks live only in this agent's throwaway per-agent settings file.

Run (PowerShell)::

    ./.venv/Scripts/python.exe -m pytest tests/test_hook_event_stream_live.py -m integration
"""

import json
import logging
import socket
import sys
import threading
import time
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

# The tmux bridge package lives at the repo root (`bridge/`). Make it importable
# explicitly so this file stands alone (resolved relative to this file, so cwd
# doesn't matter). conftest also inserts the repo root, but we don't rely on it.
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from bridge import TmuxBridge  # noqa: E402

log = logging.getLogger(__name__)

pytestmark = [pytest.mark.integration, pytest.mark.slow]

# Documented Claude Code hook events (2.1.x) we expect to be real, plus the
# research's may-not-exist candidates (PermissionRequest / SubagentStart /
# StopFailure). Registering an unknown event key is harmless in practice — claude
# iterates known events and ignores the rest — so a candidate that never POSTs is
# itself the finding ("not a real event on this build"). Each event gets its OWN
# receiver path so path->event is unambiguous even before we read the body.
_DOCUMENTED_EVENTS = (
    "PreToolUse", "PostToolUse", "UserPromptSubmit", "Notification",
    "Stop", "SubagentStop", "SessionStart", "SessionEnd", "PreCompact",
)
_CANDIDATE_EVENTS = ("PermissionRequest", "SubagentStart", "StopFailure")
_ALL_EVENTS = _DOCUMENTED_EVENTS + _CANDIDATE_EVENTS

_SANE_MODES = {"default", "plan", "acceptEdits", "bypassPermissions", "auto", "dontAsk"}
# The tool/turn boundaries the push-based run-state architecture depends on.
_TOOL_TURN_EVENTS = {"PreToolUse", "PostToolUse", "Stop"}


class _Receiver:
    """A tiny threaded HTTP receiver that records every POST it gets.

    Bound to 0.0.0.0 on an ephemeral port and reachable from the WSL agent over
    the WSL2 default-gateway address (see ``TmuxBridge.wsl_host_ip``). Every POST
    is appended to ``self.records`` as a dict with the raw parsed body + the
    fields the spike cares about; the handler always answers ``200 {}`` so the
    hook is a non-blocking no-op (PreToolUse ``{}`` = allow; Stop ``{}`` = let it
    stop) — the spike observes, it does not steer the agent.
    """

    def __init__(self):
        self.records: list[dict] = []
        self._lock = threading.Lock()
        recv = self

        class _Handler(BaseHTTPRequestHandler):
            def do_POST(self):  # noqa: N802
                n = int(self.headers.get("Content-Length") or 0)
                raw = self.rfile.read(n) if n else b""
                try:
                    body = json.loads(raw.decode("utf-8", "replace")) if raw else {}
                except Exception:
                    body = {"__unparsed__": raw.decode("utf-8", "replace")}
                # /ev/<EventName>/<agent>  -> path event; body carries the
                # authoritative hook_event_name too (we record both).
                parts = self.path.strip("/").split("/")
                path_event = parts[1] if len(parts) >= 2 and parts[0] == "ev" else None
                rec = {
                    "ts": time.monotonic(),
                    "path": self.path,
                    "path_event": path_event,
                    "hook_event_name": (body or {}).get("hook_event_name")
                    if isinstance(body, dict) else None,
                    "permission_mode": (body or {}).get("permission_mode")
                    if isinstance(body, dict) else None,
                    "tool_name": (body or {}).get("tool_name")
                    if isinstance(body, dict) else None,
                    "tool_use_id": (body or {}).get("tool_use_id")
                    if isinstance(body, dict) else None,
                    "body": body,
                }
                with recv._lock:
                    recv.records.append(rec)
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(b"{}")

            def log_message(self, *a):  # silence stderr access logs
                pass

        self._server = ThreadingHTTPServer(("0.0.0.0", 0), _Handler)
        self._server.daemon_threads = True
        self.port = self._server.server_address[1]
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)

    def start(self):
        self._thread.start()

    def snapshot(self) -> list[dict]:
        with self._lock:
            return list(self.records)

    def close(self):
        try:
            self._server.shutdown()
        except Exception:
            pass
        try:
            self._server.server_close()
        except Exception:
            pass


def _hook_settings(base_url: str, agent: str, events) -> dict:
    """The per-agent ``--settings`` hooks block pointing every ``events`` entry at
    this test's receiver. Mirrors the production driver's HTTP-hook shape
    ``{"type":"http","url":...,"timeout":N}`` (we build our own rather than reuse
    ``_build_hook_settings`` because that targets the sidecar's fixed
    ``/internal/hooks`` endpoints, not our throwaway receiver)."""
    hooks = {}
    for ev in events:
        hooks[ev] = [{
            "matcher": "",
            "hooks": [{
                "type": "http",
                "url": f"{base_url}/ev/{ev}/{agent}",
                "timeout": 5,
            }],
        }]
    return {"hooks": hooks}


def _cat(bridge, path):
    return bridge._run(f"cat {path} 2>/dev/null || echo __MISSING__")


def _drive(bridge, name, prompt, *, approve, timeout=100):
    """Send ``prompt`` and settle to idle, answering any permission prompt with
    Enter (approve) or Escape (deny). Returns the ordered list of screen states
    observed, for the DEBUG log."""
    log.debug("drive(%s) approve=%s prompt=%r", name, approve, prompt[:80])
    bridge.send(name, prompt)
    states: list[str] = []
    deadline = time.time() + timeout
    idle_streak = 0
    answered = False
    while time.time() < deadline:
        try:
            st = bridge.status(name).get("state")
        except Exception as e:  # pragma: no cover - environment dependent
            log.debug("status(%s) raised: %s", name, e)
            st = None
        if st != (states[-1] if states else None):
            states.append(st)
        if st == "permission_prompt":
            key = "Enter" if approve else "Escape"
            log.debug("drive(%s) answering permission prompt with %s", name, key)
            bridge.keys(name, key)
            answered = True
            idle_streak = 0
            time.sleep(1.5)
            continue
        if st == "idle":
            idle_streak += 1
            # Require a couple consecutive idles so we don't return during a
            # brief idle blip between a tool result and the next inference.
            if idle_streak >= 3:
                break
        else:
            idle_streak = 0
        time.sleep(1.0)
    log.debug("drive(%s) states=%s answered=%s", name, states, answered)
    return states


def _summarize(records: list[dict]) -> dict:
    """Per-event coverage + permission_mode/tool presence, for logging + asserts."""
    by_event: dict[str, dict] = {}
    for r in records:
        ev = r["hook_event_name"] or r["path_event"] or "?"
        slot = by_event.setdefault(ev, {
            "count": 0, "with_pm": 0, "pm_values": set(),
            "with_tool": 0, "tool_names": set(),
        })
        slot["count"] += 1
        pm = r["permission_mode"]
        if isinstance(pm, str) and pm:
            slot["with_pm"] += 1
            slot["pm_values"].add(pm)
        tn = r["tool_name"]
        if isinstance(tn, str) and tn:
            slot["with_tool"] += 1
            slot["tool_names"].add(tn)
    return by_event


def test_hook_event_stream_payload_carries_mode_and_tool():
    """Register a broad hook set against an in-test receiver, drive a real agent
    through tool/turn boundaries, and inspect the RAW payloads: does a tool/turn
    hook payload carry ``permission_mode`` (+ the current tool)?"""
    bridge = TmuxBridge()
    name = f"hookstream-{uuid.uuid4().hex[:8]}"
    diag = f"/home/lester/awl-hookstream-{uuid.uuid4().hex[:8]}"
    agent_id = f"agent-{uuid.uuid4().hex[:8]}"  # rides the hook URL path

    recv = _Receiver()
    recv.start()

    try:
        # --- Reachability pre-flight (skip-gate, not a fabricated pass) --------
        gw = bridge.wsl_host_ip()
        if not gw:
            pytest.skip("environment: WSL2 default gateway did not resolve — "
                        "cannot build a WSL-reachable receiver URL")
        base = f"http://{gw}:{recv.port}"
        probe_url = f"{base}/ev/Preflight/{agent_id}"
        try:
            code = bridge._run(
                f"curl -s -m 4 -o /dev/null -w '%{{http_code}}' -X POST "
                f"{probe_url} -H 'content-type: application/json' -d '{{\"ping\":1}}'",
                timeout=15,
            )
        except Exception as e:
            pytest.skip(f"environment: WSL cannot reach the ephemeral receiver "
                        f"port ({recv.port}) over the gateway {gw}: {e}")
        time.sleep(0.4)
        pre = [r for r in recv.snapshot() if r["path_event"] == "Preflight"]
        log.debug("preflight http_code=%r receiver_saw=%d", code, len(pre))
        if code != "200" or not pre:
            pytest.skip(
                f"environment: WSL->Windows receiver pre-flight failed "
                f"(http_code={code!r}, receiver_saw={len(pre)}). The gateway path "
                f"the production hooks use is not reachable for an ephemeral port "
                f"in this environment — cannot run the HTTP-hook spike here."
            )
        recv.records.clear()  # drop the preflight; only agent-driven POSTs count

        # --- Setup: throwaway diag dir + a file for the agent to Read ----------
        bridge._run(f"mkdir -p {diag}")
        marker = f"hooktest-{uuid.uuid4().hex[:6]}"
        bridge._run(f"printf %s {marker} > {diag}/note.txt")

        # --- Launch tab-less in DEFAULT mode with the broad hook set -----------
        settings = _hook_settings(base, agent_id, _ALL_EVENTS)
        info = bridge.create(
            name, cwd=diag, permission_mode="default", show=False, settings=settings,
        )
        log.debug("created session: %s", info)
        bridge.wait_idle(name, timeout=60, interval=1.0)
        screen = bridge.read(name, lines=20)["content"]
        log.debug("post-launch screen tail:\n%s", screen[-500:])
        assert "❯" in screen or "─" in screen, (
            "TUI did not render a normal idle prompt after launch with the broad "
            f"hook settings — settings may have been rejected. Screen:\n{screen[-500:]}"
        )

        # --- Drive tool/turn boundaries ---------------------------------------
        # Turn 1: Read is auto-approved in DEFAULT mode -> Pre/PostToolUse fire
        # cleanly with no permission prompt.
        _drive(
            bridge, name,
            "Use the Read tool to read the file ./note.txt in your current "
            "directory, then reply with its exact contents and nothing else.",
            approve=True,
        )
        # Turn 2: a Write raises a permission prompt in DEFAULT mode. We DENY it
        # (Escape) so nothing is written, but the boundary still exercises the
        # PreToolUse hook and any permission-related event.
        _drive(
            bridge, name,
            "Use the Write tool to create a file named blocked.txt containing "
            "exactly the word x. Do nothing else.",
            approve=False,
        )
        # blocked.txt must not exist (write denied) — a sanity check the deny took.
        assert _cat(bridge, f"{diag}/blocked.txt") == "__MISSING__"

        # Give late hooks (Stop) a moment to arrive.
        time.sleep(3)

        # --- (Best-effort) mode-change re-drive: does permission_mode reflect a
        # live BTab to acceptEdits? Wrapped so a BTab misfire never fails the
        # primary spike — it only drops the secondary observation. -------------
        accept_edits_records: list[dict] = []
        try:
            if bridge.status(name).get("state") == "idle":
                bridge.keys(name, "BTab")
                time.sleep(1.5)
                sc = bridge.read(name, lines=20)["content"]
                if "accept edits on" in sc.lower():
                    before = len(recv.snapshot())
                    _drive(
                        bridge, name,
                        "Use the Read tool to read ./note.txt again and reply "
                        "with its contents only.",
                        approve=True,
                    )
                    time.sleep(2)
                    accept_edits_records = recv.snapshot()[before:]
                    log.debug("acceptEdits re-drive captured %d records",
                              len(accept_edits_records))
                else:
                    log.debug("BTab did not reach acceptEdits; skipping re-drive")
        except Exception as e:  # pragma: no cover - best effort
            log.debug("acceptEdits re-drive skipped: %s", e)

        # --- Read back the captured payloads (THE crux) -----------------------
        records = recv.snapshot()
        by_event = _summarize(records)

        # Ordering / dedup: sequence of (event, tool, dt_ms) + duplicate detection.
        seq = []
        prev_ts = None
        seen_keys = set()
        dupes = 0
        for r in records:
            ev = r["hook_event_name"] or r["path_event"]
            dt = None if prev_ts is None else round((r["ts"] - prev_ts) * 1000)
            prev_ts = r["ts"]
            seq.append((ev, r["tool_name"], dt))
            key = (ev, r["tool_use_id"])
            if r["tool_use_id"] is not None and key in seen_keys:
                dupes += 1
            seen_keys.add(key)

        # Compact evidence table -> DEBUG log (full detail lives in tests/log/).
        log.debug("=== hook event stream: %d POSTs on build 2.1.198 ===", len(records))
        for ev, s in sorted(by_event.items()):
            log.debug(
                "  %-16s count=%d  permission_mode=%d/%d %s  tool=%d/%d %s",
                ev, s["count"], s["with_pm"], s["count"], sorted(s["pm_values"]),
                s["with_tool"], s["count"], sorted(s["tool_names"]),
            )
        log.debug("registered events that produced NO POST (not real / did not fire): %s",
                  sorted(set(_ALL_EVENTS) - set(by_event.keys())))
        log.debug("candidate events that DID fire: %s",
                  sorted(set(_CANDIDATE_EVENTS) & set(by_event.keys())))
        log.debug("arrival sequence (event, tool, dt_ms): %s", seq)
        log.debug("duplicate (event, tool_use_id) arrivals: %d", dupes)
        for r in records:
            log.debug("  RAW %-16s body=%s", r["hook_event_name"] or r["path_event"],
                      json.dumps(r["body"])[:600])

        # Sanity gate (NOT the deliverable — transport is already known from the
        # finisher): the tool/turn hooks the run-state push depends on must have
        # fired at all, else the spike is vacuous / mis-wired.
        tool_turn = [r for r in records
                     if (r["hook_event_name"] or r["path_event"]) in _TOOL_TURN_EVENTS]
        assert tool_turn, (
            "no PreToolUse/PostToolUse/Stop POST arrived at the receiver despite a "
            "successful pre-flight — the hook set did not wire up; cannot assess the "
            f"payload. Events seen: {sorted(by_event.keys())}"
        )

        # THE observable: does a tool/turn payload carry a sane permission_mode?
        pre_tool = [r for r in records
                    if (r["hook_event_name"] or r["path_event"]) == "PreToolUse"]
        pm_present = [r for r in tool_turn
                      if isinstance(r["permission_mode"], str)
                      and r["permission_mode"] in _SANE_MODES]

        if pm_present:
            # WORKS — assert the fields the push architecture depends on.
            modes = sorted({r["permission_mode"] for r in pm_present})
            log.debug("WORKS: permission_mode present on tool/turn payload -> %s", modes)
            # Default-mode turns must report 'default' (authoritative live mode).
            assert "default" in modes, (
                f"permission_mode present but never reported 'default' during a "
                f"default-mode turn (saw {modes}) — value is not authoritative"
            )
            # The current tool must be present on PreToolUse (the run-state push
            # needs to know which tool is at the boundary).
            assert pre_tool, "PreToolUse never fired — cannot confirm current-tool field"
            assert any(isinstance(r["tool_name"], str) and r["tool_name"]
                       for r in pre_tool), (
                "PreToolUse payloads carried no tool_name — current tool absent"
            )
            # If the acceptEdits re-drive ran, the mode should have flipped live.
            ae_pm = sorted({r["permission_mode"] for r in accept_edits_records
                            if isinstance(r["permission_mode"], str)
                            and r["permission_mode"] in _SANE_MODES})
            if accept_edits_records:
                log.debug("acceptEdits re-drive permission_mode values: %s", ae_pm)
            return  # green: the push channel can be authoritative-when-present

        # NEGATIVE — hooks fire but permission_mode is absent on every tool/turn
        # event. Record the shape that IS present (tool_name on PreToolUse), then
        # xfail carrying the finding. No fabricated green.
        assert pre_tool, (
            "PreToolUse never fired — cannot even characterize the payload shape"
        )
        tool_on_pre = any(isinstance(r["tool_name"], str) and r["tool_name"]
                          for r in pre_tool)
        pm_seen_anywhere = sorted({r["permission_mode"] for r in records
                                   if isinstance(r["permission_mode"], str)
                                   and r["permission_mode"]})
        pytest.xfail(
            "HTTP-hook payload does NOT carry permission_mode on any tool/turn "
            f"event on Claude Code 2.1.198 (PreToolUse tool_name present={tool_on_pre}; "
            f"permission_mode seen anywhere={pm_seen_anywhere or 'never'}; "
            f"events fired={sorted(by_event.keys())}). FINDING for research-14: the "
            "'live mode for free' claim does NOT hold on this build — the hook push "
            "channel can augment run-state (event + current tool are pushed) but "
            "cannot REPLACE screen-polling for permission_mode; screen-state polling "
            "stays primary (the §14 fallback)."
        )
    finally:
        # Tear down ONLY this session + this test's own diag dir. NEVER kill-server.
        try:
            bridge.close(name)
        except Exception as e:  # pragma: no cover - best effort
            log.debug("close(%s) failed: %s", name, e)
        try:
            bridge._run(f"rm -rf {diag}")
        except Exception as e:  # pragma: no cover - best effort
            log.debug("rm -rf %s failed: %s", diag, e)
        recv.close()
