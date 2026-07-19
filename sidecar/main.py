"""
AWL Dashboard — FastAPI Sidecar (v2)
=====================================
Multi-turn agent sessions behind a pluggable driver seam.

Each session is backed by an `AgentDriver` (see `drivers/`): the `bridge` driver
runs a real Claude Code TUI session in tmux/WSL2 — the primary path the dashboard
is built around, and the default when no driver is named — while the `sdk` driver
runs an in-process Claude Agent SDK subprocess as a backup / limited-use engine
reserved for specific non-interactive tasks. Select with the `AWL_DRIVER` env var
(`sdk` | `bridge`) or per-session via the create request's `driver` field; with
neither, sessions run on `bridge`.
The sidecar itself is driver-agnostic.
"""

import asyncio
import base64
import json
import logging
import os
import re
import shlex
import uuid
from collections import deque
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Literal

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

from drivers import create_driver, default_driver_name, AgentDriver, DriverConfig
from identity import assign_identity, git_author, draw_name, AG_ICONS
import attachments
import response_presets
import eventbus
import hookbus
import links
import inbox
import checklist
import deletion
import library
import templates_store
import storage
import state_store
import scratchpad
import watermark
import runstate
import timeline
import marquee
import console_catalog
import settings_io
import utility_llm
import handoff
import subagents_naming
import prompt_library
import roles
import import_context
import changelog
import system_check

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("awl-sidecar")


def _install_file_log() -> None:
    """§11 #43 (§2 operational posture): a small, size-bounded rotating
    diagnostic log under the gitignored ``sidecar/runtime/`` so a crash or
    fault leaves a trail — 1 MB × 3 rotations, INFO+, attached to the root
    logger (all `awl-sidecar.*` families + uvicorn errors flow through).
    Best-effort: a read-only disk must never block startup."""
    try:
        import logging.handlers
        import runtime_store
        log_dir = runtime_store.runtime_dir()
        log_dir.mkdir(parents=True, exist_ok=True)
        handler = logging.handlers.RotatingFileHandler(
            log_dir / "sidecar.log", maxBytes=1_000_000, backupCount=3,
            encoding="utf-8")
        handler.setLevel(logging.INFO)
        handler.setFormatter(logging.Formatter(
            "%(asctime)s %(levelname)s %(name)s: %(message)s"))
        root = logging.getLogger()
        # Idempotent across reloads: never stack duplicate handlers.
        if not any(isinstance(h, logging.handlers.RotatingFileHandler)
                   and getattr(h, "baseFilename", "").endswith("sidecar.log")
                   for h in root.handlers):
            root.addHandler(handler)
            if root.level > logging.INFO or root.level == logging.NOTSET:
                root.setLevel(logging.INFO)
    except Exception:  # pragma: no cover - the log must never block startup
        pass


_install_file_log()

# Monotonic counter driving the round-robin agent identity (color/icon/number).
# Reset on restart, but reconnected sessions keep their PERSISTED identity, and
# reconnect advances this past their numbers so new agents don't reuse them.
_identity_ordinal = 0

app = FastAPI(title="AWL Dashboard Sidecar", version="0.3.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============================================================================
# Session State
# ============================================================================

# The Shift+Tab mode ring WITHOUT any launch pre-arm (the launch-matrix spike,
# `test_bypass_auto_preconditions_live`, re-verified CC 2.1.206): default →
# acceptEdits → plan → auto → wrap. Bypass is launch-gated — it joins only via
# `--permission-mode bypassPermissions` (arm AND activate) or
# `--allow-dangerously-skip-permissions` (arm without activate, the
# CreateSessionRequest `arm_bypass` flag). Auto is account-eligibility-
# dependent in general (in the default ring on this account); the mode
# endpoint's honest 400 "unreachable" stays the live corrector, and the
# renderer keeps that 400 as its teaching backstop.
BASE_MODE_RING = ("default", "acceptEdits", "plan", "auto")


def armed_modes_for(permission_mode: str | None, arm_bypass: bool) -> list[str]:
    """The armed permission-mode set for a session's launch config (§7.11).

    Derived, never guessed per-click: the base ring plus Bypass when the
    launch pre-armed it (either pre-arm form). Defensive floor: the launch
    mode itself is always reachable, so an off-ring spelling (e.g. ``dontAsk``)
    appends rather than vanishing.
    """
    armed = list(BASE_MODE_RING)
    if arm_bypass or permission_mode == "bypassPermissions":
        armed.append("bypassPermissions")
    if permission_mode and permission_mode not in armed:
        armed.append(permission_mode)
    return armed


class SessionState:
    def __init__(self, session_id: str, agent_type: str | None, model: str | None,
                 permission_mode: str, cwd: str | None, system_prompt: str | None,
                 driver_name: str | None = None,
                 allowed_tools: list[str] | None = None,
                 disallowed_tools: list[str] | None = None,
                 permission_rules: dict[str, list[str]] | None = None,
                 enabled_plugins: dict[str, bool] | None = None,
                 mcp_servers: list[str] | None = None,
                 identity: dict[str, Any] | None = None,
                 response_preset: str | None = None,
                 attached_docs: list[str] | None = None,
                 arm_bypass: bool = False):
        self.session_id = session_id
        self.agent_type = agent_type
        self.model = model
        self.permission_mode = permission_mode
        self.cwd = cwd
        self.system_prompt = system_prompt
        self.driver_name = driver_name
        # Per-agent launch config (applied at create time; surfaced on to_dict).
        self.allowed_tools = allowed_tools
        self.disallowed_tools = disallowed_tools
        self.permission_rules = permission_rules
        self.enabled_plugins = enabled_plugins
        self.mcp_servers = mcp_servers
        # §7.11/§11 #13 — the launch-armed permission-mode set. `arm_bypass`
        # is the arm-without-activate flag (`--allow-dangerously-skip-
        # permissions`, persisted in the roster record); `armed_modes` is
        # DERIVED from it + the launch mode so the Details ring is exact for
        # sessions created outside the renderer and across restarts.
        self.arm_bypass = bool(arm_bypass)
        self.armed_modes = armed_modes_for(permission_mode, self.arm_bypass)
        # Per-agent reply-format preset (§7.14, §11 #39). Applied at launch via
        # `--append-system-prompt` (the bridge driver resolves the instruction);
        # persisted in the roster record so it survives a restart.
        self.response_preset = response_preset
        # Per-agent attached Library docs (§7.16, §11 #44): the doc references
        # chosen at Create. The bridge driver resolves them to WSL paths and
        # leads the appended system prompt with a consult-these-docs preamble;
        # persisted in the roster record like the preset (launch config, §8.4).
        self.attached_docs = attached_docs
        # Dashboard-owned identity (role/number/name/color/icon), assigned at
        # create and surfaced on to_dict so the UI reads it everywhere.
        self.identity = identity
        self.status: Literal["connecting", "idle", "running", "error", "closed"] = "connecting"
        self.created_at = datetime.now().isoformat()
        self.events: list[dict[str, Any]] = []
        self.subscribers: list[asyncio.Queue[dict[str, Any]]] = []
        # Event-stream dedup set: deterministic ids already emitted, so a transcript
        # re-poll / reconnect replays without duplicates (no-op on a repeat).
        self._emitted_ids: set[str] = set()
        # Per-agent ORDERED prompt queue (not strict FIFO) + a Hold staging
        # slot. Sends to a busy agent are queued, not 409-dropped, and flushed on
        # the proven generating->idle transition. `held` items are parked (link-
        # only) and never auto-flushed (released manually into the Editor).
        self.prompt_queue: deque[dict[str, Any]] = deque()
        self.held: list[dict[str, Any]] = []
        # Serialized reply-to: the peer (agent id) whose inbound message this
        # agent is currently answering, and the link it came over. Set when a link
        # inbound is delivered; on the next generating->idle the sidecar routes
        # THIS turn's output back to that peer (recipients:[peer]) and clears it.
        # Strict one-inbound-in-flight per agent keeps the pairing unambiguous.
        self.answering_source: str | None = None
        self.answering_link: str | None = None
        # Index into `events` where the current turn's output begins (set when the
        # agent goes running), so the reply-to engine can lift just this turn's
        # assistant text on idle.
        self._turn_start_idx: int = 0
        self.pending_permission: dict[str, Any] | None = None
        # Lifecycle caps (notify-only). Set on Create, editable; the cap
        # poll-loop raises a Warning inbox card on crossing — the run continues.
        self.max_turns: int | None = None
        self.max_context_pct: float | None = None
        self.context_pct: float | None = None   # latest derived context usage %
        # Locally-derived turn count (each generating->idle = one turn), so the
        # notify-only cap loop works for the bridge driver too (it emits status_change,
        # not the SDK's `result` with num_turns).
        self.turn_count: int = 0
        self._was_running: bool = False
        self.total_cost_usd: float = 0.0
        self.total_turns: int = 0
        # §11 #46 — per-turn Timeline capture. The last-known effort/thinking
        # levers, tracked when set through the dashboard endpoints (None until
        # then — neither the run-state arbiter nor the statusline payload
        # reports them, so the endpoints are the join's only source), plus the
        # in-memory record mirror (per-turn records AND typed rewind events,
        # in stored order). The bridge driver ALSO persists each record thin
        # to its launch-config turns.jsonl (§8.3); the mirror is the serve
        # fallback for drivers with no persist surface.
        self.last_effort: str | None = None
        self.last_thinking: bool | None = None
        self.turns: list[dict[str, Any]] = []
        # Capture serialization: the tail of the per-session capture chain
        # (each capture awaits its predecessor, so a stalled statusline
        # snapshot can never let a later turn's record land first) and the
        # records whose driver persist failed transiently — retried IN ORDER
        # ahead of the next record, so `turns.jsonl` self-heals instead of
        # holing permanently.
        self._capture_tail: asyncio.Task | None = None
        self._turns_pending: list[dict[str, Any]] = []
        self.driver: AgentDriver | None = None
        self.listen_task: asyncio.Task | None = None

    def to_dict(self) -> dict:
        return {
            "session_id": self.session_id,
            "agent_type": self.agent_type,
            "model": self.model,
            "permission_mode": self.permission_mode,
            "cwd": self.cwd,
            "driver": self.driver.name if self.driver else (self.driver_name or default_driver_name()),
            "status": self.status,
            "created_at": self.created_at,
            "total_cost_usd": round(self.total_cost_usd, 6),
            "total_turns": self.total_turns,
            "event_count": len(self.events),
            "has_pending_permission": self.pending_permission is not None,
            # The parsed detail of a pending tool-permission prompt (question +
            # options), so the Inbox can render the request for any agent, not
            # just the focused one. None when nothing is pending.
            "permission_request": self.pending_permission,
            # Dashboard-owned identity (role/number/name/color/icon) — the UI
            # renders agent cards and the Agent panel from this everywhere.
            "identity": self.identity,
            # The launch-armed permission-mode set (§7.11): the segments this
            # session's Shift+Tab ring actually contains. The renderer hides
            # un-armed segments from the Details ring; the live 400
            # "unreachable" stays the account-dependence backstop (Auto).
            "armed_modes": self.armed_modes,
            # The arbitrated run-state (§7.4): hook-pushed fields when fresh
            # (source="push"), the screen-poll floor otherwise. Additive —
            # `status` above stays the poll-driven enum.
            "run_state": runstate.effective(self.session_id, self.status),
            # The applied per-agent launch config, so a UI can read back what an
            # agent was scoped with. NOTE: under bypassPermissions the
            # `allowed_tools` allow-list is ignored by claude (a known bug) —
            # `disallowed_tools` / permission_rules.deny are the reliable blocks.
            "launch_config": {
                "allowed_tools": self.allowed_tools,
                "disallowed_tools": self.disallowed_tools,
                "permission_rules": self.permission_rules,
                "enabled_plugins": self.enabled_plugins,
                "mcp_servers": self.mcp_servers,
                # Per-agent reply-format preset id (§11 #39); None = default style.
                "response_preset": self.response_preset,
                # Attached Library docs (§11 #44); None/[] = nothing attached.
                "attached_docs": self.attached_docs,
                # Arm-without-activate (§7.11 #13): Bypass pre-armed at launch
                # without being the launch mode.
                "arm_bypass": self.arm_bypass,
            },
        }

    def push_event(self, event: dict[str, Any]):
        # Stamp the envelope (id/agent_id/seq/ts/source/recipients)
        # at the single fan-out choke point. A re-polled transcript entry (same
        # deterministic id) dedups to a no-op (stamp returns None).
        event = eventbus.stamp(event, agent_id=self.session_id,
                               emitted_ids=self._emitted_ids)
        if event is None:
            return
        # Routing overlay (§8.6): persist NON-default routing only — the default
        # `agent -> [user]` is re-derivable from the transcript and never written.
        src, rcp = event.get("source"), event.get("recipients")
        if (src not in (None, self.session_id) or rcp not in (None, ["user"])) \
                and not (src == "user" and rcp == [self.session_id]):
            try:
                state_store.append_routing(self.session_id, event["id"],
                                           src or self.session_id,
                                           rcp or ["user"])
            except Exception:  # pragma: no cover - overlay is best-effort
                pass
        self.events.append(event)
        # Reply-to relay: mark where the current turn's output begins so the reply-to
        # engine can lift just this turn's assistant text on the next idle.
        if event.get("type") == "status_change" and event.get("status") == "running":
            self._turn_start_idx = len(self.events)
            self._was_running = True
        for q in self.subscribers:
            try:
                q.put_nowait(event)
            except asyncio.QueueFull:
                pass  # subscriber too slow, skip
        # Mirror into the bounded cross-agent ring + merged subscribers.
        eventbus.publish_global(event)

    def enqueue(self, entry: dict[str, Any], disposition: str) -> dict[str, Any]:
        """Place a prompt per its send-timing disposition (an ordered queue, not FIFO):

        * ``queue`` — append-tail, flush at idle (the polite default).
        * ``next``  — insert-head, flush at idle (jump ahead of the queue).
        * ``now``   — insert-head; the caller interrupts the run so the resulting
          idle flushes it immediately.
        * ``hold``  — park in the staging slot; never auto-flushed (released
          manually into the Editor for approval/edit before send).

        (``inject`` rides the hook channel, not this queue — spike-gated.)
        Returns ``{status, position}`` (or ``{status:'held', held}``).
        """
        if disposition == "hold":
            self.held.append(entry)
            return {"status": "held", "held": len(self.held)}
        if disposition in ("next", "now"):
            self.prompt_queue.appendleft(entry)
            position = 0
        else:  # "queue"
            self.prompt_queue.append(entry)
            position = len(self.prompt_queue) - 1
        return {"status": "queued", "position": position}

    def handle_event(self, event: dict[str, Any]):
        """Driver event callback: update session bookkeeping, then fan out.

        Drivers emit already-serialized event dicts. The session owns the
        cross-event bookkeeping (status, cost, turns) so drivers stay simple.
        """
        etype = event.get("type")

        if etype == "status_change":
            st = event.get("status")
            if st in ("connecting", "idle", "running", "error", "closed"):
                self.status = st  # type: ignore[assignment]
            self.push_event(event)
            if st == "running":
                # Start-of-run scratchpad catch-up — deliver this agent's
                # unread delta as a passive `context` inject (lands at its first
                # tool boundary; idle agents have no boundary so they catch up now).
                _deliver_scratch_delta(self)
            # The generating->idle transition is the proven flush signal.
            if st == "idle":
                if self._was_running:        # one completed turn (feeds the cap loop)
                    self.turn_count += 1
                    # Surface the count on the API too: the bridge driver has no
                    # SDK `result`/`num_turns`, so without this `total_turns`
                    # (to_dict / the UI's turn readout) would sit at 0 forever for
                    # every bridge agent. Keep it in lockstep with the local
                    # per-turn counter.
                    self.total_turns = self.turn_count
                    self._was_running = False
                    _raise_response_card(self)
                    # §11 #46: capture this turn's settings + one-line summary.
                    # Rides the SAME exactly-once completion gate as the turn
                    # count (the driver's reply-gated completion → _was_running
                    # consumed once) — never a parallel turn detector.
                    _capture_turn(self)
                # Reply-to: relay this finished turn back to a linked peer FIRST (uses
                # this turn's output before a queued prompt starts a new turn), then
                # the shared-context fire (§7.6), then flush the next queued prompt.
                _maybe_relay_reply(self)
                _fire_shared_context(self)
                _schedule_flush(self)
            return

        if etype == "permission_request":
            # A driver paused on a tool-permission prompt. Record the detail so
            # `has_pending_permission` flips true, then fan the event out. The
            # status enum is intentionally left untouched (pending reads off the
            # flag, not a new status value).
            self.pending_permission = event.get("data") or {}
            self.push_event(event)
            return

        if etype == "permission_resolved":
            # The prompt was answered (here or directly in the terminal) — drop
            # the pending detail so it cannot linger.
            self.pending_permission = None
            self.push_event(event)
            return

        if etype == "error":
            # Inbox Error section: raise a STICKY inbox card (persists until
            # Retry/Dismiss). Best-effort subtype from the message text.
            msg = event.get("error") or event.get("message") or ""
            cls = inbox.classify_error(msg) or {"subtype": "error", "message": str(msg)[:500]}
            inbox.raise_item(self.session_id, "error", cls, sticky=True,
                             dedup_key=f"error:{cls['subtype']}")
            # Account/fleet-level subtypes (rate/usage caps, auth expiry) ALSO
            # coalesce into ONE System-sourced fleet-wide card (§7.2, §11 #27).
            if cls["subtype"] in inbox.SYSTEM_WIDE_SUBTYPES:
                _raise_system_card(cls["subtype"], cls.get("message", ""),
                                   seen_on=self.session_id)
            self.push_event(event)
            return

        # Preserve original ordering: push the message, then react to results.
        self.push_event(event)

        if etype == "result":
            data = event.get("data", event)
            cost = data.get("total_cost_usd") or event.get("total_cost_usd")
            if cost:
                self.total_cost_usd = float(cost)
            turns = data.get("num_turns") or event.get("num_turns")
            if turns:
                self.total_turns = int(turns)
            self.status = "idle"
            self.push_event({
                "type": "status_change", "status": "idle",
                "timestamp": datetime.now().isoformat(),
            })
            # SDK-driver turns end HERE (a `result`, never a was-running idle
            # status_change): same turn accounting as the idle branch, and the
            # §7.8 Response card raises on this path too.
            if self._was_running:
                self.turn_count += 1
                self._was_running = False
                # §11 #46: per-turn capture on the SDK completion point too —
                # same exactly-once gate as the turn count.
                _capture_turn(self)
            _raise_response_card(self)
            # Reply-to relay, then the shared-context fire, then flush of the
            # next queued prompt.
            _maybe_relay_reply(self)
            _fire_shared_context(self)
            _schedule_flush(self)

sessions: dict[str, SessionState] = {}


def _render_piggyback(items: list[dict[str, Any]]) -> str:
    """Render parked piggyback payloads as ONE bounded, attributed block (§7.6)
    for prepending to the next prompt delivered to the target."""
    lines = ["[Shared context from linked agents — passive awareness, no reply expected]"]
    for it in items:
        lines.append(f"- (from {it['source']}) {it['text']}")
    return "\n".join(lines)


# §11 #47: operator commits in flight, counted per PROJECT key. `git add -A`
# walks the whole shared repo, so while one runs no queued prompt may start a
# turn anywhere in that project (the other half of the 409 busy gate — the gate
# rejects a commit while a turn runs; this stops a turn starting mid-commit).
# _flush_queue defers; session_git's finally re-schedules the deferred flushes.
_git_commits_inflight: dict[str, int] = {}


def _git_commit_inflight_for(session: "SessionState") -> bool:
    """True when an operator commit is running in this session's project."""
    if not _git_commits_inflight:
        return False  # fast path — never resolve a project key per flush
    key = storage.project_key(session.cwd)
    return bool(key) and key in _git_commits_inflight


async def _flush_queue(session: "SessionState") -> None:
    """Send the next queued prompt iff the agent is idle and one is queued.

    Re-entrancy is gated by flipping status to ``running`` *before* the only
    ``await`` (driver.send), so a concurrent flush sees ``running`` and returns —
    strict one-in-flight, no double-send. An in-flight operator commit in this
    session's project (§11 #47) also defers the flush — the commit's `add -A`
    must never capture a turn's half-written files; the commit path re-schedules
    every deferred flush the moment it finishes.

    Piggyback (§7.6): any payloads parked for this agent ride THIS delivery —
    they never initiate a turn of their own. The parked block is prepended to
    the prompt (one bounded block; parking was already watermark-deduped per
    source→target at fire time, so nothing delivers twice).

    Queue awareness (§7.3/§7.6, §11 #24): a link-delivered entry (flagged
    ``queue_awareness`` at its enqueue point — relay, shared queue-family fire,
    kickoff) leads with the ONE attributed front-matter note when OTHER-source
    mail is still queued behind it at this pop — computed HERE, at delivery
    time, so the note is true when the recipient reads it (an enqueue-time
    snapshot of a tail-appended entry counts only mail delivered before it).
    Order when both ride: piggyback block, then the note, then the message.
    """
    if session.status == "running" or not session.prompt_queue or not session.driver:
        return
    if _git_commit_inflight_for(session):
        return  # deferred — session_git re-schedules when the commit lands
    entry = session.prompt_queue.popleft()
    prompt = entry["prompt"]
    if entry.get("queue_awareness"):
        note = links.queue_awareness_note(
            str(entry.get("source") or "user"), list(session.prompt_queue))
        if note:
            prompt = note + "\n\n" + prompt
    rides = links.take_piggyback(session.session_id)
    if rides:
        prompt = _render_piggyback(rides) + "\n\n" + prompt
    session.status = "running"  # gate re-entry before the await
    session.push_event({
        "type": "status_change", "status": "running",
        "timestamp": datetime.now().isoformat(),
        "source": entry.get("source", "user"),
        "recipients": entry.get("recipients", ["user"]),
    })
    if rides:
        # Feed visibility: the parked shared context was delivered on this send.
        session.push_event({
            "type": "piggyback_delivered", "count": len(rides),
            "sources": sorted({r["source"] for r in rides}),
            "timestamp": datetime.now().isoformat(),
            "source": "system", "recipients": [session.session_id],
        })
    try:
        await session.driver.send(prompt)
    except Exception as e:  # pragma: no cover - exercised live
        logger.error(f"Session {session.session_id} queued-send failed: {e}")
        session.status = "error"
        session.push_event({
            "type": "error", "error": str(e),
            "timestamp": datetime.now().isoformat(),
        })


def _schedule_flush(session: "SessionState") -> None:
    """Schedule a queue flush on the event loop (handle_event is sync and must
    not await). No-op when nothing is queued or no loop is running (e.g. tests)."""
    if not session.prompt_queue:
        return
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return
    loop.create_task(_flush_queue(session))


def _last_turn_assistant_text(session: "SessionState", start_idx: int) -> str:
    """The text the agent produced in the turn that just ended — assistant text
    blocks from `start_idx` up to the next turn boundary (a running status_change),
    used as the reply-to payload."""
    parts: list[str] = []
    for ev in session.events[start_idx:]:
        if ev.get("type") == "status_change" and ev.get("status") == "running":
            break  # a new turn started; don't bleed into it
        if ev.get("type") != "assistant":
            continue
        content = ev.get("content")
        if isinstance(content, str):
            parts.append(content)
        elif isinstance(content, list):
            for block in content:
                if isinstance(block, dict) and block.get("type") == "text":
                    parts.append(block.get("text") or "")
                elif isinstance(block, str):
                    parts.append(block)
    return "\n".join(p for p in parts if p).strip()


def _maybe_relay_reply(session: "SessionState",
                       _start_idx: int | None = None, _attempt: int = 0) -> None:
    """Link fire: if this agent just finished answering a linked peer's
    inbound, route THIS turn's output back to that peer over the link (delivered
    by the link's trigger mode), then set the peer's reply-to back to this agent
    — strict one-in-flight alternation, bounded by the link's End-After cap.

    The bridge emits generating->idle off *screen* state ~1s before the assistant
    entry is polled into `events`, so when the turn text isn't there yet we RETRY
    (keeping the reply-to) rather than dropping the fire. Idempotent: the reply-to
    is consumed only once text is in hand.
    """
    src = session.answering_source
    link_id = session.answering_link
    if not src or not link_id:
        return
    lk = links.get_link(link_id)
    if not lk or not lk.active:
        session.answering_source = None
        session.answering_link = None
        return
    start_idx = session._turn_start_idx if _start_idx is None else _start_idx
    text = _last_turn_assistant_text(session, start_idx)
    if not text:
        # Turn text not polled into events yet — retry without losing the reply-to.
        if _attempt < 6:
            try:
                asyncio.get_running_loop().call_later(
                    1.5, lambda: _maybe_relay_reply(session, start_idx, _attempt + 1))
            except RuntimeError:
                pass  # no loop (hermetic tests) — text was simply absent
        else:
            logger.warning("relay: no turn text for %s after retries; dropping",
                           session.session_id)
            session.answering_source = None
            session.answering_link = None
        return
    # Got the text — consume the reply-to and fire.
    session.answering_source = None
    session.answering_link = None
    target = sessions.get(src)
    if not target or not target.driver:
        return

    # Account the fire (one message, one direction) and check the End-After cap
    # (direction-aware: a one-way link burns one exchange per fire, §7.6).
    lk.messages += 1
    lk.tokens += max(1, len(text) // 4)  # rough token estimate for the token cap
    capped = lk.over_cap()
    if capped:
        lk.active = False
    else:
        # Set up the peer's reply-to back here so the conversation alternates.
        target.answering_source = session.session_id
        target.answering_link = link_id
    links.touched(lk)  # write-through: counters/active persist (§8.3)

    logger.info("link_fire %s -> %s msg=%d exchanges=%d capped=%s trigger=%s",
                session.session_id, src, lk.messages, lk.exchanges, capped, lk.trigger)
    session.push_event({
        "type": "link_fire", "link_id": link_id, "text": text,
        "timestamp": datetime.now().isoformat(),
        "source": session.session_id, "recipients": [src],
        "exchanges": lk.exchanges, "capped": capped,
    })

    trigger = lk.trigger or "queue"
    if trigger == "piggyback":
        # Piggyback never initiates a turn (§7.6): park the reply — it rides the
        # next message delivered to the peer from any source (a piggybacked DM
        # reads as a deferred reply).
        links.park_piggyback(src, source=session.session_id, link_id=link_id,
                             text=text)
        return
    if trigger == "inject":
        # Mid-run delivery via the hook channel.
        inj = hookbus.enqueue_inject(src, text, kind="inject",
                                     source=session.session_id)
        target.push_event({
            "type": "inject", "text": text, "kind": "inject",
            "inject_id": inj["id"], "timestamp": datetime.now().isoformat(),
            "source": session.session_id, "recipients": [src],
        })
        return

    entry = {
        "id": str(uuid.uuid4())[:8], "prompt": text,
        "source": session.session_id, "recipients": [src],
        "disposition": trigger, "enqueued_at": datetime.now().isoformat(),
        # Queue awareness (§11 #24): mark this as a link delivery so
        # _flush_queue renders the attributed front-matter note at DELIVERY
        # time, against the mail still waiting behind it — never here at
        # enqueue, where a tail-appended entry would count only items delivered
        # before it (a note false by the time it is read).
        "queue_awareness": True,
    }
    target.enqueue(entry, trigger)
    if trigger == "hold":
        return  # parked for manual release
    if trigger == "now" and target.status == "running":
        try:
            asyncio.get_running_loop().create_task(target.driver.interrupt())
        except Exception:  # pragma: no cover
            pass
        return
    _schedule_flush(target)


# ============================================================================
# The reserved System identity (§7.2, §11 #27) — filter-only, never addressable.
# It appears as the sender on fleet-wide Error cards (infrastructure faults,
# account-level events, shared-service failures) and Log lines; it is excluded
# from Compose To/From and Reply is disabled on its cards (UI contract).
# ============================================================================

SYSTEM_AGENT = "system"
_system_emitted_ids: set[str] = set()


def _push_system_event(event: dict[str, Any]) -> None:
    """Stamp + publish a System-sourced event onto the merged bus (no session)."""
    try:
        stamped = eventbus.stamp(event, agent_id=SYSTEM_AGENT,
                                 emitted_ids=_system_emitted_ids,
                                 source=SYSTEM_AGENT, recipients=["user"])
        if stamped is not None:
            eventbus.publish_global(stamped)
    except Exception:  # pragma: no cover - system events are best-effort
        pass


def _raise_system_card(subtype: str, message: str, *, seen_on: str | None = None) -> None:
    """Raise/refresh the ONE coalesced fleet-wide System Error card per subtype."""
    data = {"subtype": subtype, "message": str(message)[:500]}
    if seen_on:
        data["seen_on"] = seen_on
    item = inbox.raise_item(SYSTEM_AGENT, "error", data, sticky=True,
                            dedup_key=f"system:{subtype}")
    if not item.get("_system_event_pushed"):
        item["_system_event_pushed"] = True
        _push_system_event({
            "type": "error", "error": data["message"], "subtype": subtype,
            "timestamp": datetime.now().isoformat(),
        })


def _resolve_system_card(subtype: str) -> None:
    """Auto-clear the coalesced System card when its probe recovers."""
    for it in inbox.items_for(SYSTEM_AGENT):
        if it.get("dedup_key") == f"system:{subtype}":
            inbox.resolve_item(SYSTEM_AGENT, it["id"], answer="recovered")


SYSTEM_PROBE_INTERVAL = 10.0  # seconds


async def _system_probe_loop():
    """Deterministic infrastructure probes (§7.2/§11 #27): every ~10 s, verify
    the WSL2/tmux backbone answers (the raising `TmuxBridge.ping` through the
    shared registry bridge — `list` can't serve here: it folds every outage
    into "zero sessions", so a dead WSL would read as healthy, the §11 #49
    review finding). A failure raises the coalesced System `infra` Error card;
    recovery auto-resolves it. (Sidecar-down needs no probe — a dead sidecar
    can't raise cards; the frontend's /health failure covers it, §4.3/#38.)"""
    while True:
        try:
            await asyncio.sleep(SYSTEM_PROBE_INTERVAL)
            try:
                bridge = _get_registry_bridge()
                await asyncio.to_thread(bridge.ping)
                _resolve_system_card("infra")
            except Exception as e:
                _raise_system_card("infra", f"tmux/WSL2 unreachable: {e}")
        except asyncio.CancelledError:  # pragma: no cover
            return
        except Exception as e:  # pragma: no cover - keep the loop alive
            logger.error("system probe loop error: %s", e)


def _fire_shared_context(session: "SessionState",
                         _start_idx: int | None = None, _attempt: int = 0) -> None:
    """Shared-context fire (§7.6): on this agent's completed turn, make the
    turn's output available to every peer on an active ``shared`` link that lets
    this agent send. Passive awareness only — no conversation semantics, so no
    reply-to bookkeeping and no alternation.

    Delivery rides the link's trigger: **piggyback** (the shared default) parks
    the payload on the target's pending list — it rides the target's next
    delivered message and never initiates a turn; ``inject`` rides the hook
    channel as passive context; the queue-family triggers take the existing
    prompt-queue path. Dedup: the per-(source→target) ``shared:{src}:{dst}``
    watermark (the same §7.7 mechanism, persisted in the same
    ``state/bookmarks.json``) is advanced to this turn's ordinal at fire time,
    so an idle re-emission or channel overlap never delivers the same turn
    twice. The ``shared_content`` content-type filter is a pass-through today
    (no content-type classification at this seam yet) — the raw turn text is
    shared. Fires count against End-After like any other fire (direction-aware).

    Same transcript-lag retry as ``_maybe_relay_reply``: the bridge flips idle
    ~1s before the turn text is polled into ``events``, so a missing text
    retries rather than dropping the fire (the watermark advances only once the
    text is in hand).
    """
    src_id = session.session_id
    marker = session.turn_count
    if marker <= 0:
        return
    due: list[tuple[Any, str]] = []
    for lk in links.all_links():
        if not lk.active or not lk.is_shared():
            continue
        dst = lk.other(src_id)
        if dst is None or not lk.allows(src_id, dst):
            continue
        if watermark.get(f"shared:{src_id}:{dst}") >= marker:
            continue  # this turn already shared to this target (dedup)
        due.append((lk, dst))
    if not due:
        return
    start_idx = session._turn_start_idx if _start_idx is None else _start_idx
    text = _last_turn_assistant_text(session, start_idx)
    if not text:
        # Turn text not polled into events yet — retry, watermark un-advanced.
        if _attempt < 6:
            try:
                asyncio.get_running_loop().call_later(
                    1.5, lambda: _fire_shared_context(session, start_idx, _attempt + 1))
            except RuntimeError:
                pass  # no loop (hermetic tests) — text was simply absent
        return
    for lk, dst in due:
        target = sessions.get(dst)
        trigger = lk.trigger or "piggyback"
        if trigger != "piggyback" and (target is None or target.driver is None):
            continue  # nowhere to deliver — leave the watermark un-advanced
        watermark.set(f"shared:{src_id}:{dst}", marker)
        # Account the fire (End-After binds shared links too, direction-aware).
        lk.messages += 1
        lk.tokens += max(1, len(text) // 4)
        if lk.over_cap():
            lk.active = False
        links.touched(lk)
        session.push_event({
            "type": "shared_context_fire", "link_id": lk.id, "text": text,
            "timestamp": datetime.now().isoformat(),
            "source": src_id, "recipients": [dst],
            "exchanges": lk.exchanges, "capped": not lk.active,
        })
        if trigger == "piggyback":
            links.park_piggyback(dst, source=src_id, link_id=lk.id, text=text)
            continue
        if trigger == "inject":
            # Mid-run delivery via the hook channel, as PASSIVE context (never
            # blocks Stop, never forces a continuation).
            hookbus.enqueue_inject(dst, text, kind="context", source=src_id)
            continue
        entry = {
            "id": str(uuid.uuid4())[:8], "prompt": text,
            "source": src_id, "recipients": [dst],
            "disposition": trigger, "enqueued_at": datetime.now().isoformat(),
            # Queue awareness (§11 #24): link delivery — the attributed
            # front-matter note renders in _flush_queue at delivery time,
            # against the mail still waiting behind this entry.
            "queue_awareness": True,
        }
        target.enqueue(entry, trigger)
        if trigger == "hold":
            continue  # parked for manual release
        if trigger == "now" and target.status == "running":
            try:
                asyncio.get_running_loop().create_task(target.driver.interrupt())
            except Exception:  # pragma: no cover
                pass
            continue
        _schedule_flush(target)


def _raise_response_card(session: "SessionState") -> None:
    """Response card (§7.8): non-blocking — "a run ended with output the operator
    has not reviewed." ONE coalesced card per agent (the dedup key updates the
    open card in place, counting unreviewed runs), completable via the standard
    resolve endpoint (View / Reply); no dismiss and no read-tracking."""
    try:
        runs = 1
        for it in inbox.items_for(session.session_id):
            if it["type"] == "response":
                runs = int(it["data"].get("runs", 0)) + 1
                break
        inbox.raise_item(
            session.session_id, "response",
            {"runs": runs, "last_turn_at": datetime.now().isoformat()},
            dedup_key=f"response:{session.session_id}")
    except Exception:  # pragma: no cover - a card must never break the turn loop
        pass


# §11 #46: the bridge flips generating->idle off *screen* state ~1s before the
# turn's trailing transcript entries are polled into `events` (the exact lag
# `_maybe_relay_reply` retries for), so a capture that lifted summary + anchors
# immediately could anchor `reply_uuid` mid-reply. The capture instead SETTLES:
# it re-lifts until two consecutive lifts agree, sleeping one poll cycle between
# attempts (bounded — the same 6-attempt budget as the relay). Hermetic tests
# zero the sleep; the re-lift logic still runs. Honest limit: a trailing entry
# that lands after a QUEUED next turn's boundary is outside this turn's window
# and stays missed (the pre-existing window semantics).
_CAPTURE_SETTLE_SECS = 1.5
_CAPTURE_SETTLE_ATTEMPTS = 6


def _capture_turn(session: "SessionState") -> None:
    """Per-turn settings + summary capture (§7.19/§7.14, §11 #46) — scheduler.

    Called ONLY at the exactly-once turn-completion points in ``handle_event``
    (the bridge driver's reply-gated run→idle and the SDK driver's ``result``
    — both consume ``_was_running`` once), never from a bare idle, so one
    dashboard-initiated turn yields exactly one Timeline record.
    ``handle_event`` is sync, so the join + persist run as a loop task; the
    turn number, turn-start index, AND the timestamp are snapshotted HERE (a
    queued follow-up prompt may move the indices before the task runs, and the
    timestamp must mark the completion point, not append time). Captures are
    SERIALIZED per session — each task awaits its predecessor before building
    or appending — because stored order IS the read surface's re-minted
    ordinal order: a capture whose statusline snapshot stalls on a slow WSL
    round trip must never let a faster later turn's record land first. With no
    running loop (hermetic sync callers) the capture is skipped silently — it
    is a side-effect of the live loop, never load-bearing for the turn.
    """
    turn_no = session.turn_count
    start_idx = session._turn_start_idx
    ts = datetime.now().isoformat()
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return
    prev = session._capture_tail

    async def _chained() -> None:
        if prev is not None:
            try:
                await prev
            except Exception:  # pragma: no cover - predecessor already logged
                pass
        await _capture_turn_record(session, turn_no, start_idx, ts)

    session._capture_tail = loop.create_task(_chained())


async def _capture_turn_record(session: "SessionState", turn_no: int,
                               start_idx: int, ts: str | None = None) -> None:
    """Build + store one per-turn Timeline record (§11 #46).

    Settings-at-turn is a JOIN of what's already known at the turn boundary —
    the statusline capture's model (§11 #31, the freshest boundary payload;
    ``session.model`` is the fallback), the run-state arbiter's
    ``permission_mode`` (§7.4 hook-pushed; ``session.permission_mode`` is the
    fallback), and the session-tracked effort/thinking levers. The one-line
    summary is the leading line of the turn's assistant reply (the §11 #39
    preamble lean; first-sentence fallback, sanely truncated —
    ``timeline.turn_summary``), and the turn's transcript anchors
    (``prompt_uuid``/``reply_uuid`` — the JSONL entry uuids the event stream
    already carries as ``anchor`` on ``source_kind='t'`` events) are lifted
    from the turn's events (``timeline.turn_anchors`` — forward window for
    the closing reply, a bounded backward scan for the prompt, which live
    ordering polls in BEFORE the boundary's running flip; null-safe — an
    SDK-driven or synthesized turn simply records nulls), both under the
    bounded trailing-entry settle (``_CAPTURE_SETTLE_SECS``). The record lands in
    the in-memory mirror and — for drivers with a persist surface (bridge) —
    appends thin to the per-agent ``turns.jsonl`` (§8.3: the settings
    snapshot is NOT in the transcript, so it must persist). Best-effort
    throughout: a failed join source degrades to its fallback; a failed
    persist logs, keeps the in-memory record, AND queues it for an in-order
    re-append ahead of the next turn's record (``_turns_pending``), so a
    transient WSL hiccup never permanently holes ``turns.jsonl``.
    """
    text = _last_turn_assistant_text(session, start_idx)
    prompt_uuid, reply_uuid = timeline.turn_anchors(session.events, start_idx)
    # Trailing-entry settle (see _CAPTURE_SETTLE_SECS above): re-lift until the
    # window is stable across a poll cycle, so `reply_uuid` anchors the CLOSING
    # assistant entry — not whichever mid-reply entry had polled in when the
    # screen flipped idle. The anchor lift walks the FULL event list from the
    # boundary: live ordering polls the prompt entry in BEFORE the boundary's
    # running flip, so `turn_anchors` looks backward for it (timeline.py).
    for _ in range(_CAPTURE_SETTLE_ATTEMPTS):
        if _CAPTURE_SETTLE_SECS:
            await asyncio.sleep(_CAPTURE_SETTLE_SECS)
        text2 = _last_turn_assistant_text(session, start_idx)
        anchors2 = timeline.turn_anchors(session.events, start_idx)
        if text2 == text and anchors2 == (prompt_uuid, reply_uuid):
            break  # stable — the transcript tail has flushed
        text, (prompt_uuid, reply_uuid) = text2, anchors2
    summary = timeline.turn_summary(text)
    drv = session.driver
    snap = None
    if drv is not None and hasattr(drv, "get_statusline_snapshot"):
        try:
            snap = await drv.get_statusline_snapshot()
        except Exception:  # pragma: no cover - best-effort by contract
            snap = None
    model = timeline.model_from_snapshot(snap) or session.model
    rstate = runstate.get(session.session_id) or {}
    mode = rstate.get("permission_mode") or session.permission_mode
    record = timeline.build_record(
        turn=turn_no, timestamp=ts or datetime.now().isoformat(), model=model,
        mode=mode, effort=session.last_effort, thinking=session.last_thinking,
        summary=summary, prompt_uuid=prompt_uuid, reply_uuid=reply_uuid)
    await _store_turn_line(session, record)


async def _store_turn_line(session: "SessionState",
                           record: dict[str, Any]) -> None:
    """Mirror + thin-persist one ``turns.jsonl`` line (turn OR rewind event).

    The shared tail of ``_capture_turn_record`` and ``_append_rewind_record``:
    the record lands in the in-memory mirror (``session.turns``) and — for
    drivers with a persist surface (bridge) — drains to ``turns.jsonl`` IN
    ORDER: any earlier record whose persist failed goes FIRST
    (``_turns_pending``), so the file keeps completion order and a rewind
    event can never land ahead of a turn record still draining. Callers are
    serialized per session (the ``_capture_tail`` chain), so this drain never
    races another one.
    """
    session.turns.append(record)
    drv = session.driver
    if drv is not None and hasattr(drv, "append_turn_record"):
        session._turns_pending.append(record)
        while session._turns_pending:
            head = session._turns_pending[0]
            try:
                await drv.append_turn_record(head)
            except Exception as e:
                logger.warning(
                    "turn-record persist failed for %s (%d queued for the "
                    "next capture): %s",
                    session.session_id, len(session._turns_pending), e)
                break
            session._turns_pending.pop(0)


async def _append_rewind_record(session: "SessionState",
                                to_prompt_index: int) -> None:
    """Persist one typed rewind event to the session's Timeline (§11 #46).

    Called ONLY after a SUCCESSFUL driver rewind (a failed rewind appends
    nothing): the JSONL transcript is append-only — the rewind itself writes
    NOTHING at rewind time and no engine checkpoint id exists anywhere — so
    this event line is the only persisted trace, and the read surface's
    replay (``timeline.replay_timeline``) is what turns it into rolled-row
    truth that survives a reload. Chained through the SAME per-session
    ``_capture_tail`` serialization as turn captures and awaited, so the
    record can never land ahead of an in-flight turn capture and is on disk
    (or honestly queued on ``_turns_pending``) before the endpoint responds.
    Manual-terminal rewinds (outside the dashboard) write no event and stay
    unmarked — the settled scope: the Timeline logs dashboard turns.
    """
    record = timeline.build_rewind_record(
        timestamp=datetime.now().isoformat(), to_prompt_index=to_prompt_index)
    prev = session._capture_tail

    async def _chained() -> None:
        if prev is not None:
            try:
                await prev
            except Exception:  # pragma: no cover - predecessor already logged
                pass
        await _store_turn_line(session, record)

    task = asyncio.get_running_loop().create_task(_chained())
    session._capture_tail = task
    await task


def _scratch_key(session: "SessionState") -> str:
    """The scratchpad project key — co-located agents share one board.

    Keyed by the CANONICAL project root (§8.1), never the raw cwd, so a
    subfolder launch or a `/mnt`-alias spelling still lands on the same board.
    """
    return storage.project_key(session.cwd) or session.session_id


def _deliver_scratch_delta(session: "SessionState") -> None:
    """Shared scratchpad: enqueue the agent's unread scratchpad delta as a PASSIVE `context`
    inject (delivered at the next tool boundary via the hook channel; never
    triggers a turn). No-op when there's nothing new past its watermark."""
    try:
        delta = scratchpad.unread(session.session_id, _scratch_key(session))
        if not delta:
            return
        hookbus.enqueue_inject(session.session_id, scratchpad.render(delta),
                               kind="context", source="scratch")
        session.push_event({
            "type": "scratch_delivered", "count": len(delta),
            "timestamp": datetime.now().isoformat(),
            "source": "scratch", "recipients": [session.session_id],
        })
    except Exception:  # pragma: no cover - delivery is best-effort
        pass

# ============================================================================
# Session Lifecycle
# ============================================================================

async def start_session(session: SessionState):
    """Create the driver, start it, and pump its events into the session."""
    config = DriverConfig(
        agent_type=session.agent_type,
        model=session.model,
        permission_mode=session.permission_mode,
        cwd=session.cwd,
        system_prompt=session.system_prompt,
        allowed_tools=session.allowed_tools,
        disallowed_tools=session.disallowed_tools,
        permission_rules=session.permission_rules,
        enabled_plugins=session.enabled_plugins,
        mcp_servers=session.mcp_servers,
        identity=session.identity,
        response_preset=session.response_preset,
        attached_docs=session.attached_docs,
        arm_bypass=session.arm_bypass,
    )
    try:
        driver = create_driver(config, session.handle_event, session.driver_name)
        session.driver = driver
        # Bridge sessions persist a runtime record keyed by the sidecar session
        # id so a restarted sidecar can rebind to the live tmux session.
        if hasattr(driver, "bind_session_id"):
            driver.bind_session_id(session.session_id)  # type: ignore[attr-defined]
        await driver.start()
        session.status = "idle"
        session.listen_task = asyncio.create_task(_listen(session))
        logger.info(f"Session {session.session_id} connected via {driver.name} driver")
    except Exception as e:
        logger.error(f"Session {session.session_id} connect failed: {e}")
        session.status = "error"
        session.push_event({
            "type": "error", "error": str(e),
            "timestamp": datetime.now().isoformat(),
        })


async def _listen(session: SessionState):
    """Pump the driver's event stream into the session until cancelled."""
    if not session.driver:
        return
    try:
        async for event in session.driver.events():
            session.handle_event(event)
    except asyncio.CancelledError:
        logger.info(f"Session {session.session_id} listener cancelled")
    except Exception as e:
        logger.error(f"Session {session.session_id} listener error: {e}")
        session.status = "error"
        # Died-at stamp (§11 #17 / #50 residual): the event pump failing is the
        # sidecar observing the agent die — persist the moment on the roster
        # record so the Past tab can render an honest "died …" stamp.
        marker = getattr(session.driver, "mark_stopped", None)
        if callable(marker):
            try:
                marker()
            except Exception:  # pragma: no cover - stamp is best-effort
                pass
        session.push_event({
            "type": "error", "error": str(e),
            "timestamp": datetime.now().isoformat(),
        })


async def reconnect_sessions(project_key: str | None = None):
    """Restore bridge sessions that outlived a previous sidecar process (§9.9).

    With ``project_key`` set, only that project's records restore — the §9.1
    open flow (``POST /projects/open`` calls this), which is the NORMAL
    restore point: startup is picker-first and restores nothing by default
    (see ``_on_startup``). Without a key, every persisted record restores —
    the restore-everything sweep the ``AWL_STARTUP_RESTORE=all`` escape hatch
    (and tests) use.

    Two cases per persisted record:

    * **Warm** (tmux still alive): rebuild the session state and a resumed
      driver bound to that tmux name, then resume event pumping (the transcript
      replay restores history).
    * **Cold** (tmux gone — reboot / WSL shutdown): relaunch the agent with
      ``claude --resume <claude_session_id>`` in its cwd — the same
      conversation, rebuilt from the transcript. Only records with no
      ``claude_session_id`` (no way back to the conversation) are pruned.
    """
    global _identity_ordinal
    try:
        import runtime_store
        from drivers.bridge import BridgeDriver
    except Exception as e:  # pragma: no cover - bridge deps optional
        logger.info("Reconnect skipped (bridge unavailable): %s", e)
        return

    records = runtime_store.all_records()
    if not records:
        return

    # Which tmux sessions are actually still alive?
    try:
        from bridge import TmuxBridge  # type: ignore[import-not-found]
        alive = {s["name"] for s in TmuxBridge().list()}
    except Exception as e:  # pragma: no cover - environment dependent
        logger.warning("Reconnect: could not list tmux sessions: %s", e)
        return

    for rec in records:
        sid = rec.get("session_id")
        tmux_name = rec.get("tmux_name")
        if not sid or not tmux_name:
            continue
        if project_key is not None and \
                storage.project_key(rec.get("cwd")) != project_key:
            continue
        cold = tmux_name not in alive
        if cold and not rec.get("claude_session_id"):
            # No conversation id to resume — nothing to restore. Prune.
            logger.info("Pruning dead session record %s (tmux %s gone, no claude id)",
                        sid, tmux_name)
            runtime_store.remove_record(sid)
            continue
        if sid in sessions:
            continue

        identity = rec.get("identity")
        # Keep the round-robin counter ahead of any restored agent's number so a
        # newly-created agent doesn't reuse a reconnected one's color/number.
        if isinstance(identity, dict) and isinstance(identity.get("number"), int):
            _identity_ordinal = max(_identity_ordinal, identity["number"])
        # Load the project's persisted state (lazy, idempotent) and register the
        # agent→project mapping before any event/persist hook can fire for it.
        state_store.load_project(rec.get("cwd"))
        state_store.register_agent(sid, rec.get("cwd"))
        session = SessionState(
            session_id=sid,
            agent_type=None,
            model=rec.get("model"),
            permission_mode=rec.get("permission_mode", "acceptEdits"),
            cwd=rec.get("cwd"),
            system_prompt=None,
            driver_name="bridge",
            allowed_tools=rec.get("allowed_tools"),
            disallowed_tools=rec.get("disallowed_tools"),
            permission_rules=rec.get("permission_rules"),
            enabled_plugins=rec.get("enabled_plugins"),
            mcp_servers=rec.get("mcp_servers"),
            identity=identity,
            response_preset=rec.get("response_preset"),
            attached_docs=rec.get("attached_docs"),
            arm_bypass=rec.get("arm_bypass", False),
        )
        sessions[sid] = session
        config = DriverConfig(
            agent_type=None,
            model=rec.get("model"),
            permission_mode=rec.get("permission_mode", "acceptEdits"),
            cwd=rec.get("cwd"),
            system_prompt=None,
            allowed_tools=rec.get("allowed_tools"),
            disallowed_tools=rec.get("disallowed_tools"),
            permission_rules=rec.get("permission_rules"),
            enabled_plugins=rec.get("enabled_plugins"),
            mcp_servers=rec.get("mcp_servers"),
            identity=identity,
            response_preset=rec.get("response_preset"),
            attached_docs=rec.get("attached_docs"),
            arm_bypass=rec.get("arm_bypass", False),
        )
        try:
            driver = BridgeDriver(
                config, session.handle_event,
                resume_name=tmux_name, session_id=sid,
                claude_session_id=rec.get("claude_session_id"),
                cold_restore=cold,
                # The persisted transcript path skips a pointless re-resolve;
                # the full record seeds the driver's record base so refreshes
                # never drop fields another writer persisted.
                transcript_path=rec.get("transcript_path"),
                persisted_record=rec,
            )
            session.driver = driver
            # Warm: resume() rebinds the live tmux session. Cold: a fresh
            # create with `claude --resume <id>` rebuilds the conversation.
            await driver.start()
            session.status = "idle"
            session.listen_task = asyncio.create_task(_listen(session))
            logger.info("%s session %s (tmux %s)",
                        "Cold-restored" if cold else "Reconnected", sid, tmux_name)
        except Exception as e:
            logger.error("%s failed for %s: %s",
                         "Cold-restore" if cold else "Reconnect", sid, e)
            session.status = "error"


# ============================================================================
# Projects — the one-project-at-a-time surface (§3, §9.1, §9.8; §11 #26)
# ============================================================================

# The canonical root of the project the dashboard currently has open, or None
# (the empty state). One sidecar serves whichever project is open (§2); agents
# of unopened projects keep running detached in tmux — the dashboard simply is
# not looking at them (§3.7).
_open_project: str | None = None


def _project_entry(key: str, meta: dict[str, Any]) -> dict[str, Any]:
    """One Projects-picker row: name, path, last-opened, agent count, open flag."""
    roster = state_store.load_roster(key)
    return {
        "path": key,
        "name": Path(key).name,
        "last_used": meta.get("last_used"),
        "agent_count": len(roster),
        "open": key == _open_project,
    }


CAP_POLL_INTERVAL = 3.0  # seconds


async def _cap_poll_loop():
    """Notify-only cap loop: compare each agent's live turns / context-% to
    its stored caps and raise a Warning inbox card on crossing (dedup'd per
    subtype so it fires once). The run is NOT auto-killed — the user chooses
    Continue / Raise cap / Stop. This is the same loop that feeds the inbox's Warning
    section."""
    while True:
        try:
            await asyncio.sleep(CAP_POLL_INTERVAL)
            for session in list(sessions.values()):
                if session.max_turns is None and session.max_context_pct is None:
                    continue
                warns = inbox.cap_warnings(
                    turns=max(session.turn_count, session.total_turns),
                    max_turns=session.max_turns,
                    context_pct=session.context_pct,
                    max_context_pct=session.max_context_pct,
                )
                for w in warns:
                    item = inbox.raise_item(
                        session.session_id, "warning", w,
                        dedup_key=f"warning:{w['subtype']}")
                    if item.get("_new_warning_pushed"):
                        continue
                    item["_new_warning_pushed"] = True
                    session.push_event({
                        "type": "warning", "subtype": w["subtype"],
                        "value": w["value"], "cap": w["cap"],
                        "timestamp": datetime.now().isoformat(),
                        "source": session.session_id, "recipients": ["user"],
                    })
        except asyncio.CancelledError:  # pragma: no cover
            return
        except Exception as e:  # pragma: no cover - keep the loop alive
            logger.error("cap poll loop error: %s", e)


@app.on_event("startup")
async def _on_startup():
    """Sidecar startup — picker-first, restoring NOTHING by default (§9.1).

    The decided §3.1/§9.1 flow: startup lands on the empty state and the
    operator picks a project — the restore point is ``POST /projects/open``,
    which runs ``reconnect_sessions(project_key=…)`` for exactly that project
    (§9.9 warm-rebind + cold-restore). Startup itself never silently restores
    ALL persisted records any more. Escape hatch: ``AWL_STARTUP_RESTORE=all``
    (or ``1``) keeps the old restore-everything-at-boot behavior for tests and
    one-sidecar-per-project setups.
    """
    state_store.install_hooks()   # write-through persistence (§8.3)
    if os.environ.get("AWL_STARTUP_RESTORE", "").lower() in ("all", "1", "true"):
        await reconnect_sessions()
    asyncio.create_task(_cap_poll_loop())
    asyncio.create_task(_system_probe_loop())


# ============================================================================
# Request Models
# ============================================================================

class IdentityInput(BaseModel):
    """Optional create-time identity overrides. Any field omitted is assigned a
    default (round-robin color/icon, sequential number, role "Agent")."""
    role: str | None = None
    number: int | None = None
    name: str | None = None
    color: str | None = None   # hex; default round-robin from the 16 --ag-* tokens
    icon: str | None = None    # icon name from assets/icons/agents/

# The product-owned model default (2026-07-18 decision): the app defines its
# own default — Opus — instead of falling through to whatever Claude Code's
# config would pick (the retired "no --model flag" path). create_session
# coerces a missing/empty/"inherit" model to this so every NEW session
# persists a concrete model and the bridge always emits --model. The request
# field below stays Optional (an explicit JSON null from older clients must
# not 422); historical roster/archive read-backs and the fork's
# "inherit ← parent" derivation keep their own semantics.
DEFAULT_MODEL = "opus"

class CreateSessionRequest(BaseModel):
    agent_type: str | None = None
    model: str | None = None
    # bypassPermissions is the launch default (2026-07-17 decision — matches
    # DriverConfig): launching in it arms the Bypass segment implicitly, so a
    # default create needs no arm_bypass. The rec.get(..., "acceptEdits")
    # roster/archive read-back fallbacks are deliberately NOT flipped — they
    # describe what old records were launched with.
    permission_mode: str = "bypassPermissions"
    cwd: str | None = None
    system_prompt: str | None = None
    driver: str | None = None  # "sdk" | "bridge"; None -> AWL_DRIVER, else default "bridge"
    # Per-agent launch config (applied at create time only — see DriverConfig).
    allowed_tools: list[str] | None = None
    disallowed_tools: list[str] | None = None
    permission_rules: dict[str, list[str]] | None = None  # {allow,deny,ask}
    enabled_plugins: dict[str, bool] | None = None         # {"id@mkt": bool}
    mcp_servers: list[str] | None = None                   # subset; None = global
    # Arm-without-activate (§7.11, §11 #13): pass
    # `--allow-dangerously-skip-permissions` at launch so Bypass joins the
    # Shift+Tab mode ring while the agent still LAUNCHES in `permission_mode`
    # (launching in bypassPermissions arms it implicitly). Persisted in the
    # roster record; drives the session's `armed_modes` read.
    arm_bypass: bool = False
    identity: IdentityInput | None = None                  # dashboard-owned id fields
    response_preset: str | None = None                     # reply-format preset id (§11 #39)
    # Library docs attached at launch (§7.16, §11 #44): store/project doc paths
    # or bare filenames the agent is pointed at via a system-prompt preamble.
    attached_docs: list[str] | None = None
    max_turns: int | None = None                           # lifecycle cap (notify-only)
    max_context_pct: float | None = None                   # lifecycle cap (notify-only)

class SendPromptRequest(BaseModel):
    prompt: str
    # Message addressing (built in now so linking / multi-target sends need no later
    # migration). source = who the prompt is from (default the operator);
    # recipients = typed addressees (user | <agent-id> | scratch), default the
    # target agent. These drive routing + the From/To filter + Sent/Received — not
    # visibility. Full agent-to-agent routing lands with the prompt queue/linking.
    source: str = "user"
    recipients: list[str] | None = None
    # Send-timing disposition. `queue` (the polite default) waits for the
    # turn AND the existing queue; `next` jumps ahead at the next idle; `now`
    # interrupts the current run and delivers immediately; `hold` stages for
    # manual release; `inject` = true mid-run delivery via the hook channel
    # (spike-proven on the installed build — lands at the next tool boundary
    # without stopping the turn; if the agent is idle it lands on its next run).
    disposition: Literal["now", "next", "queue", "hold", "inject"] = "queue"
    # Attachment references (§10 #1, §7.14): asset ids from POST /library/assets,
    # resolved against THIS agent's project store. The delivered text gains ONE
    # attributed block listing each asset's receiver-readable absolute path
    # (the WSL form a bridge agent can open — attachments.attachments_block);
    # an unknown id is an honest 400, never a silent drop.
    attachments: list[str] | None = None

class SetResponsePresetRequest(BaseModel):
    # A known preset id from GET /presets/response (§11 #39). Unknown -> 400.
    preset: str

class SetModelRequest(BaseModel):
    model: str

class SetModeRequest(BaseModel):
    # `auto` is the Auto segment's canonical spelling (the launch path and the
    # status-line indicator both use it); `dontAsk` is the CLI's alias for the
    # same segment — accepted and folded to `auto` by the bridge's cycle lever
    # (see bridge.bridge._MODE_TARGET_ALIASES).
    mode: Literal["default", "acceptEdits", "plan", "auto",
                  "bypassPermissions", "dontAsk"]

class AnswerPermissionRequest(BaseModel):
    # approve = Yes (Enter); deny = No (Escape). Always-allow is unsupported
    # (option 2 was never verified live), so the choice is binary.
    approve: bool

class CreateLinkRequest(BaseModel):
    a: str
    b: str
    direction: Literal["a2b", "b2a", "both"] = "both"
    # Exactly ONE relationship per link (§7.6) — "direct" | "shared"; wanting
    # both between the same two agents = two links. A legacy list input is
    # tolerated (its first element is taken) so pre-split clients don't 422.
    relationship: str | list[str] = "direct"
    shared_content: list[str] = []                # shared-content type filter
    shared_backfill: bool = False
    # Link trigger mode. None -> the per-relationship default (§7.6):
    # direct → queue, shared → piggyback.
    trigger: Literal["now", "next", "queue", "inject", "hold", "piggyback"] | None = None
    end_after_exchanges: int | None = 25          # End-After default
    end_after_tokens: int | None = None

class LinkKickoffRequest(BaseModel):
    """Seed a reply-to conversation: deliver `prompt` to `to_agent`, recording
    that its reply routes back to `from_agent` over the link (reply-to alone can't
    start a conversation — this is the explicit kickoff)."""
    from_agent: str
    to_agent: str
    prompt: str

class TemplateRequest(BaseModel):
    name: str
    body: str
    placeholders: list[str] | None = None

class ReviewRequest(BaseModel):
    cwd: str
    filename: str
    owner: str | None = None
    state: str | None = None
    verdict: str | None = None
    verdict_by: str | None = None
    comments: list[Any] | None = None

class DocumentCreateRequest(BaseModel):
    cwd: str
    filename: str
    content: str = ""
    subdir: str = "docs"          # "docs" | "plans" — the two store collections

class DocumentRenameRequest(BaseModel):
    cwd: str
    path: str                     # the .md to rename (must be store-scoped)
    new_filename: str

class CommentRequest(BaseModel):
    cwd: str
    path: str                     # the .md commented on (must be store-scoped)
    text: str
    author: str = "user"
    anchor_quote: str | None = None
    anchor_heading: str | None = None

class CommentResolveRequest(BaseModel):
    cwd: str
    path: str
    comment_id: str

class SetEffortRequest(BaseModel):
    effort: str

class SetFastRequest(BaseModel):
    on: bool

class SetThinkingRequest(BaseModel):
    on: bool

class RewindRequest(BaseModel):
    """Rewind the agent's conversation to an earlier prompt checkpoint (§7.19,
    §11 #15). ``to_prompt_index`` = how many user-prompt checkpoints to roll back
    from the current end (1 = discard only the latest prompt) — the count-from-end
    the native ``/rewind`` menu navigates by ``Up`` × k. Absolute Timeline-turn
    addressing is the per-turn-capture / renderer surface (§11 #46, #37)."""
    to_prompt_index: int = 1

class ForkRequest(BaseModel):
    """Fork/Handoff a NEW agent from an existing session (§7.19, §11 #15).

    ``--fork-session`` branches an independent session from the source (source
    untouched); an optional ``to_prompt_index`` rewinds the fork to an earlier
    prompt for branch-from-N. The fork is a first-class live agent through the
    standard Create wiring (§9.2) with its own identity (and its own #19 git
    attribution). Fields left None inherit from the source."""
    to_prompt_index: int | None = None       # branch-from-N (None = fork at head)
    model: str | None = None                 # fork's model (default: source's)
    cwd: str | None = None                   # override fork cwd (default: source's)
    isolate: bool = True                     # per-fork file-state policy: own git worktree
    identity: IdentityInput | None = None    # fork identity overrides (else assigned)
    # §11 #16 — Handoff artifacts: when true, layer a generated summary/handoff
    # report on the plain context carry-over (a utility-LLM pass over the source's
    # recent transcript, stored as a Library doc the Create payload references).
    handoff: bool = False
    handoff_model: str | None = None         # model for the handoff-summary pass


class ResumeRequest(BaseModel):
    """Select ONE past agent to resume on demand (§9.9, §11 #17).

    The missing piece over #8's startup cold-restore: load a SPECIFIC past agent
    à la carte — by its original sidecar ``session_id``, its identity ``name``, or
    an ``archive_id`` from the Agent archive (§11 #18, a retired/deep-frozen
    agent). Exactly one selector is used; precedence is ``archive_id`` →
    ``session_id`` → ``name``. The resume relaunches ``claude --resume
    <claude_session_id>`` in the agent's cwd (the same conversation, same id — the
    live-proven §9.9 cold path), adopting it back as a first-class live agent."""
    session_id: str | None = None
    name: str | None = None
    archive_id: str | None = None


class HandoffReportRequest(BaseModel):
    """Generate a standalone Handoff artifact for a live session (§7.19, §11 #16).

    A concise summary/handoff report (what the agent was doing / key decisions /
    current state) distilled from the agent's recent transcript via the utility
    LLM and persisted as a Library doc (§8.4). ``cwd`` overrides where the doc
    lands (default the source agent's own project home); ``target_session_id``
    records which agent the handoff is FOR (provenance only)."""
    target_session_id: str | None = None
    model: str | None = None
    cwd: str | None = None


class ImportExternalRequest(BaseModel):
    """Import an OUTSIDE Claude session by title (§11 #28; engine:
    ``sidecar/import_context.py``).

    ``source`` = ``web`` (claude.ai — needs the tool's gitignored
    ``session_key.txt``) | ``desktop`` (the desktop app's local store).
    ``destination`` picks where the captured markdown lands — one engine, one
    selectable destination: ``agent`` (deliver onto ``target_agent``'s §7.3
    prompt queue), ``panel`` (return the markdown for the operator read
    panel), ``library`` (a §7.16 reference doc under ``cwd``'s project store,
    provenance stamped). ``cwd`` is only meaningful for ``library``;
    ``target_agent`` only for ``agent``."""
    source: str
    title: str
    destination: str
    target_agent: str | None = None
    cwd: str | None = None


# ============================================================================
# Endpoints
# ============================================================================

@app.get("/health")
async def health():
    return {
        "status": "ok",
        "active_sessions": len(sessions),
        "driver": default_driver_name(),
        "version": "0.3.0",
    }


def _live_identity_names() -> set[str]:
    """Every live agent's identity name — the auto-name draw's exclusion set
    (mirrors ``GET /identity/random-name``)."""
    taken: set[str] = set()
    for s in list(sessions.values()):
        nm = (s.identity or {}).get("name") if s.identity else None
        if nm:
            taken.add(nm)
    return taken


@app.post("/sessions")
async def create_session(req: CreateSessionRequest):
    global _identity_ordinal
    session_id = str(uuid.uuid4())[:8]
    # First session for a project loads its persisted state/ (lazy, §11 #3) and
    # registers the agent→project mapping the write-through hooks route by.
    state_store.load_project(req.cwd)
    state_store.register_agent(session_id, req.cwd)
    # Resolve the dashboard-owned identity (round-robin color/icon/number, with
    # any caller-provided overrides; a blank name auto-draws from the curated
    # pool, excluding live agents' names), then advance the round-robin counter.
    identity = assign_identity(
        req.identity.model_dump() if req.identity else None, _identity_ordinal,
        taken_names=_live_identity_names(),
    )
    _identity_ordinal += 1
    # Retired numbers are NEVER reused (§7.12): an auto-assigned number that was
    # retired skips forward to the next free one (explicit requests pass through).
    if not (req.identity and req.identity.number is not None):
        if deletion.is_retired(identity["number"]):
            identity["number"] = deletion.next_free_number(identity["number"])
            _identity_ordinal = max(_identity_ordinal, identity["number"])
    # Model coercion (the DEFAULT_MODEL decision): an explicit model passes
    # through verbatim, but None/empty/"inherit" (case-insensitive, stripped —
    # the retired Claude-Code-default passthrough) become DEFAULT_MODEL, so
    # every NEW session carries a concrete model down to the driver (the
    # bridge then always emits --model). Resume/reconnect read-backs and the
    # fork's `req.model or source.model` parent-inherit are deliberately NOT
    # coerced — historical records keep what they recorded.
    _model = (req.model or "").strip()
    model = DEFAULT_MODEL if (not _model or _model.lower() == "inherit") else req.model
    session = SessionState(
        session_id=session_id,
        agent_type=req.agent_type,
        model=model,
        permission_mode=req.permission_mode,
        cwd=req.cwd,
        system_prompt=req.system_prompt,
        driver_name=req.driver,
        allowed_tools=req.allowed_tools,
        disallowed_tools=req.disallowed_tools,
        permission_rules=req.permission_rules,
        enabled_plugins=req.enabled_plugins,
        mcp_servers=req.mcp_servers,
        identity=identity,
        response_preset=req.response_preset,
        attached_docs=req.attached_docs,
        arm_bypass=req.arm_bypass,
    )
    session.max_turns = req.max_turns                  # notify-only caps
    session.max_context_pct = req.max_context_pct
    sessions[session_id] = session
    logger.info(f"Created session {session_id}")

    # Start the driver and wait for it to connect (or timeout).
    asyncio.create_task(start_session(session))
    for _ in range(30):
        await asyncio.sleep(0.5)
        if session.status != "connecting":
            break

    return session.to_dict()


@app.get("/sessions")
async def list_sessions_endpoint():
    # Snapshot (list()) like every other `sessions` iteration: safe against a
    # concurrent create/retire landing between suspension points.
    return [s.to_dict() for s in list(sessions.values())]


# ---------------------------------------------------------------------------
# Load past agents — on-demand per-agent resume (§9.9, §11 #17)
#
# #8 built cold-restore-on-startup + Fleet-Setup load; what was missing is
# loading ONE specific past agent à la carte. These two endpoints add it, riding
# the SAME live-proven cold path (`claude --resume <id>`): enumerate the
# resumable roster + archive records, then resume a chosen one back into a live
# session. NOTE: `GET /sessions/past` is declared BEFORE `GET /sessions/{id}` so
# the literal `past` segment isn't swallowed by the `{session_id}` route.
# ---------------------------------------------------------------------------

def _resumable_from_roster(rec: dict[str, Any]) -> dict[str, Any]:
    """Normalize a persisted roster record (runtime_store) into a resume descriptor."""
    ident = rec.get("identity") if isinstance(rec.get("identity"), dict) else None
    return {
        "session_id": rec.get("session_id"),
        "claude_session_id": rec.get("claude_session_id"),
        # The agent's original tmux session name: resume reuses it so the
        # per-agent launch-config dir (turns.jsonl / statusline.jsonl) —
        # keyed by tmux name — re-attaches instead of starting empty (§7.19).
        "tmux_name": rec.get("tmux_name"),
        "cwd": rec.get("cwd"),
        "model": rec.get("model"),
        "permission_mode": rec.get("permission_mode", "acceptEdits"),
        "identity": ident,
        "name": (ident or {}).get("name"),
        "transcript_path": rec.get("transcript_path"),
        "allowed_tools": rec.get("allowed_tools"),
        "disallowed_tools": rec.get("disallowed_tools"),
        "permission_rules": rec.get("permission_rules"),
        "enabled_plugins": rec.get("enabled_plugins"),
        "mcp_servers": rec.get("mcp_servers"),
        "attached_docs": rec.get("attached_docs"),
        "arm_bypass": rec.get("arm_bypass", False),
        # Fork provenance (§11 #18): carried so a resume re-seeds the driver's
        # record with it — otherwise one resume→retire cycle would archive
        # lineage: null and lose the fork graph edge.
        "lineage": rec.get("lineage") if isinstance(rec.get("lineage"), dict) else None,
        "created_at": rec.get("created_at"),
        # When the sidecar observed this agent stop/die (§11 #17): stamped by
        # the driver's stop()/mark_stopped(); absent for legacy records and
        # unwitnessed deaths (reboot) — the row falls back to created_at.
        "died_at": rec.get("stopped_at"),
        "retired_at": None,
        "source": "roster",
        "archive_id": None,
    }


def _resumable_from_archive(arc: dict[str, Any]) -> dict[str, Any]:
    """Normalize an archived record (§11 #18, LIGHT — transcript referenced in
    place) into a resume descriptor. The transcript pointer lives under
    ``transcript.{claude_session_id, transcript_path}``; the light record carries
    no per-agent launch config, so those resume as None (the resumed conversation
    is what matters — §9.9)."""
    ident = arc.get("identity") if isinstance(arc.get("identity"), dict) else None
    tr = arc.get("transcript") if isinstance(arc.get("transcript"), dict) else {}
    return {
        "session_id": arc.get("session_id"),
        "claude_session_id": tr.get("claude_session_id"),
        # Archived (§11 #18) so a resume re-attaches the same per-agent
        # launch-config dir (turns.jsonl Timeline) — absent on older records.
        "tmux_name": arc.get("tmux_name"),
        "cwd": arc.get("cwd"),
        "model": arc.get("model"),
        "permission_mode": arc.get("permission_mode", "acceptEdits"),
        "identity": ident,
        "name": arc.get("name") or (ident or {}).get("name"),
        "transcript_path": tr.get("transcript_path"),
        "allowed_tools": None,
        "disallowed_tools": None,
        "permission_rules": None,
        "enabled_plugins": None,
        "mcp_servers": None,
        "attached_docs": None,
        # Pre-armed Bypass (§7.11) is a LIGHT launch fact the archive keeps
        # alongside permission_mode, so an un-retired agent relaunches with
        # the ring it was created with (False for pre-field rows — the cold
        # relaunch and the derived ring then agree honestly).
        "arm_bypass": bool(arc.get("arm_bypass", False)),
        # Fork provenance (§11 #18) — un-retiring must not shed it: the
        # resume re-seeds the driver's record, and the NEXT retire re-archives
        # the same lineage.
        "lineage": arc.get("lineage") if isinstance(arc.get("lineage"), dict) else None,
        "created_at": arc.get("created_at"),
        "died_at": None,
        "retired_at": arc.get("retired_at"),
        "source": "archive",
        "archive_id": arc.get("archive_id"),
    }


def _past_summary(d: dict[str, Any], live_ids: set[str]) -> dict[str, Any]:
    """One `GET /sessions/past` row: identity/cwd/model + resume eligibility.

    ``resumable`` = has a conversation id to resume AND isn't already live."""
    sid = d.get("session_id")
    live = sid in live_ids
    return {
        "session_id": sid,
        "name": d.get("name"),
        "identity": d.get("identity"),
        "cwd": d.get("cwd"),
        "model": d.get("model"),
        "claude_session_id": d.get("claude_session_id"),
        "created_at": d.get("created_at"),
        # §11 #17: the observed stop/death stamp (roster rows; None when the
        # death was unwitnessed — the UI falls back to created_at).
        "died_at": d.get("died_at"),
        "retired_at": d.get("retired_at"),
        "source": d.get("source"),
        "archive_id": d.get("archive_id"),
        "live": live,
        "resumable": bool(d.get("claude_session_id")) and not live,
    }


@app.get("/sessions/past")
async def list_past_agents():
    """Enumerate resumable past agents — the persisted roster + the archive (§11 #17).

    Aggregates every persisted roster record (``runtime_store.all_records()``,
    project-first) that ISN'T currently live, plus every archived (retired) record
    (§11 #18). Currently-live agents are excluded — they're already in
    ``GET /sessions``. Each row carries a ``resumable`` flag (has a
    ``claude_session_id`` to resume, and isn't live) and a ``source``
    (``roster`` | ``archive``), so a UI can offer load-by-name/ID/archive."""
    import runtime_store
    live_ids = set(sessions)
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for rec in runtime_store.all_records():
        sid = rec.get("session_id")
        if not sid or sid in live_ids:
            continue          # live agents belong to GET /sessions, not "past"
        out.append(_past_summary(_resumable_from_roster(rec), live_ids))
        seen.add(sid)
    for arc in state_store.all_archived_records():
        sid = arc.get("session_id")
        if sid and sid in live_ids:
            continue
        if sid and sid in seen:
            continue          # a roster record already covers this id
        out.append(_past_summary(_resumable_from_archive(arc), live_ids))
        if sid:
            # Guard against duplicate archive rows for one session_id (e.g. a
            # retire→resume→retire cycle after a partial failure): the first
            # emitted row wins, the same id never double-lists.
            seen.add(sid)
    return {"past": out, "count": len(out)}


def _resolve_resume_target(req: "ResumeRequest") -> dict[str, Any] | None:
    """Resolve a ResumeRequest to a resume descriptor (or None = not found).

    Precedence archive_id → session_id → name. An id/name is matched against BOTH
    the live-capable roster AND the archive (a retired agent lives only in the
    archive), so "load past agent by name or ID" reaches deep-frozen agents too."""
    import runtime_store
    if req.archive_id:
        found = state_store.find_archive_record(req.archive_id)
        return _resumable_from_archive(found[1]) if found else None
    if req.session_id:
        for rec in runtime_store.all_records():
            if rec.get("session_id") == req.session_id:
                return _resumable_from_roster(rec)
        for arc in state_store.all_archived_records():
            if arc.get("session_id") == req.session_id:
                return _resumable_from_archive(arc)
        return None
    if req.name:
        target = req.name.strip().lower()
        for rec in runtime_store.all_records():
            nm = ((rec.get("identity") or {}).get("name") or "").strip().lower()
            if nm and nm == target:
                return _resumable_from_roster(rec)
        for arc in state_store.all_archived_records():
            nm = (arc.get("name") or (arc.get("identity") or {}).get("name")
                  or "").strip().lower()
            if nm and nm == target:
                return _resumable_from_archive(arc)
        return None
    return None


async def _resume_agent_from_descriptor(d: dict[str, Any]) -> "SessionState":
    """Relaunch a past agent from a resume descriptor into a live SessionState.

    Mirrors ``reconnect_sessions()`` (§9.9): warm-rebind when the descriptor's
    persisted ``tmux_name`` is still alive (the agent never died — a duplicate
    relaunch would orphan the running conversation), else the COLD branch — a
    tmux session relaunched with ``claude --resume <claude_session_id>`` in the
    agent's cwd — the SAME conversation, rebuilt from its transcript,
    continuing on the SAME sidecar session id (so it's THE agent returning,
    not a clone/fork). The persisted ``tmux_name`` is REUSED for the relaunch
    (§7.19 Timeline persistence): the per-agent launch-config dir
    (``turns.jsonl`` / ``statusline.jsonl``) is keyed by tmux name, so a
    fresh name would silently orphan the agent's Timeline on every
    retire→resume round-trip. Only a descriptor with no ``tmux_name`` (legacy
    /pre-#18 archive rows) falls back to a fresh name. ``start()`` re-persists
    the roster record, bringing the agent back to the live roster."""
    global _identity_ordinal
    from drivers.bridge import BridgeDriver  # local import (mirrors reconnect)

    sid = d.get("session_id") or str(uuid.uuid4())[:8]
    cwd = d.get("cwd")
    claude_sid = d.get("claude_session_id")
    identity = d.get("identity")
    tmux_name = d.get("tmux_name") or None
    # Warm-vs-cold: reuse reconnect's liveness read — in a worker thread, so
    # the wsl.exe→tmux roundtrip never stalls the event loop (SSE feeds and
    # hook ingestion keep flowing while it runs). Unreadable tmux (or no
    # persisted name) reads as not-alive — the cold create then answers
    # honestly if the name is somehow still taken.
    alive = False
    if tmux_name:
        def _live_tmux_names() -> set[str]:
            from bridge import TmuxBridge  # type: ignore[import-not-found]
            return {s["name"] for s in TmuxBridge().list()}
        try:
            alive = tmux_name in await asyncio.to_thread(_live_tmux_names)
        except Exception:  # pragma: no cover - environment dependent
            alive = False
    # Keep the round-robin counter ahead of a restored agent's number (as reconnect).
    if isinstance(identity, dict) and isinstance(identity.get("number"), int):
        _identity_ordinal = max(_identity_ordinal, identity["number"])
    state_store.load_project(cwd)
    state_store.register_agent(sid, cwd)
    session = SessionState(
        session_id=sid,
        agent_type=None,
        model=d.get("model"),
        permission_mode=d.get("permission_mode", "acceptEdits"),
        cwd=cwd,
        system_prompt=None,
        driver_name="bridge",
        allowed_tools=d.get("allowed_tools"),
        disallowed_tools=d.get("disallowed_tools"),
        permission_rules=d.get("permission_rules"),
        enabled_plugins=d.get("enabled_plugins"),
        mcp_servers=d.get("mcp_servers"),
        identity=identity,
        attached_docs=d.get("attached_docs"),
        arm_bypass=d.get("arm_bypass", False),
    )
    sessions[sid] = session
    config = DriverConfig(
        agent_type=None,
        model=d.get("model"),
        permission_mode=d.get("permission_mode", "acceptEdits"),
        cwd=cwd,
        system_prompt=None,
        allowed_tools=d.get("allowed_tools"),
        disallowed_tools=d.get("disallowed_tools"),
        permission_rules=d.get("permission_rules"),
        enabled_plugins=d.get("enabled_plugins"),
        mcp_servers=d.get("mcp_servers"),
        identity=identity,
        attached_docs=d.get("attached_docs"),
        arm_bypass=d.get("arm_bypass", False),
    )
    # The driver's record BASE (start() re-persists on top of it): carry the
    # fields start() does not itself rewrite — today the fork lineage (§11
    # #18) — so a resume→retire round-trip re-archives the same provenance
    # instead of shedding it (reconnect passes the FULL record for the same
    # reason).
    persisted: dict[str, Any] = {"session_id": sid, "cwd": cwd}
    if isinstance(d.get("lineage"), dict):
        persisted["lineage"] = d["lineage"]
    driver = BridgeDriver(
        config, session.handle_event,
        resume_name=tmux_name,          # reuse the launch-config home (§7.19)
        session_id=sid, claude_session_id=claude_sid,
        cold_restore=not alive,
        transcript_path=d.get("transcript_path"),
        persisted_record=persisted,
    )
    session.driver = driver
    try:
        # Warm: resume() rebinds the alive tmux. Cold: a full create with
        # `claude --resume <id>` on the SAME tmux name.
        await driver.start()
        session.status = "idle"
        session.listen_task = asyncio.create_task(_listen(session))
    except Exception as e:  # pragma: no cover - environment dependent
        logger.error("on-demand resume failed for %s: %s", sid, e)
        session.status = "error"
    return session


@app.post("/sessions/resume")
async def resume_past_session(req: ResumeRequest):
    """Resume ONE past agent on demand, back into a live session (§9.9, §11 #17).

    Selects by ``archive_id`` / ``session_id`` / ``name`` (that precedence) across
    the roster + archive, then relaunches it on the §9.9 cold path (same
    conversation, same id). Honest failures: **404** when nothing matches; **409**
    when the target is already live; **400** when no selector is given or the
    target has no conversation id to resume. Resuming from the archive un-retires
    it — the deep-freeze row is removed once it's live again (§7.12 reversibility)."""
    if not (req.archive_id or req.session_id or req.name):
        raise HTTPException(status_code=400,
                            detail="Provide one of: archive_id, session_id, name")
    d = _resolve_resume_target(req)
    if d is None:
        raise HTTPException(status_code=404, detail="No matching past agent to resume")
    sid = d.get("session_id")
    if sid and sid in sessions:
        raise HTTPException(status_code=409, detail=f"Agent {sid} is already live")
    if not d.get("claude_session_id"):
        raise HTTPException(status_code=400,
                            detail="Target has no resumable conversation id")
    session = await _resume_agent_from_descriptor(d)
    # Un-retire: a successful resume from the archive removes the deep-freeze row
    # (§7.12 — Retire is reversible; the agent is live again). Best-effort.
    if d.get("source") == "archive" and d.get("archive_id") \
            and session.status != "error":
        try:
            state_store.delete_archived_anywhere(d["archive_id"])
        except Exception:  # pragma: no cover - best effort
            pass
    out = session.to_dict()
    out["resumed_from"] = d.get("source")
    out["archive_id"] = d.get("archive_id")
    out["claude_session_id"] = d.get("claude_session_id")
    return out


@app.get("/sessions/{session_id}")
async def get_session(session_id: str):
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    return sessions[session_id].to_dict()


@app.delete("/sessions/{session_id}")
async def close_session(session_id: str, hard: bool = False):
    """Retire (soft, default) or — with ?hard=true — permanent **Delete**.

    **Retire (default) = deep-freeze, archived by default (§7.12, §11 #18):** the
    live session is stopped and a LIGHT archive record is written into the
    project's ``state/archive.json`` (distinct id, identity snapshot, created +
    retired timestamps, the transcript **referenced in place** — never copied,
    §8.6 — the per-agent git author/email from #19, and the reserved lineage
    fields). Retire is reversible: the transcript is kept and the identity number
    is NOT retired. This is a freeze, not a discard.

    **Delete (?hard=true) = TRUE wipe (§7.12), distinct from archive:** a hard
    wipe of the agent's private footprint (runtime record, tmux session, on-disk
    transcript) while everything SHARED is tombstoned (links → inactive
    tombstones; feed/scratchpad history is kept and attributed). The agent's
    number is retired (never reused). Queue + inbox (operational state) are
    dropped. A hard Delete is NOT archived.
    """
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    session = sessions[session_id]

    if session.listen_task and not session.listen_task.done():
        session.listen_task.cancel()

    if hard:
        # --- hard wipe + tombstone ---
        number = (session.identity or {}).get("number") if session.identity else None
        link_ids = [lk.id for lk in links.all_links()
                    if session_id in (lk.a, lk.b)]
        transcript_path = None
        subagent_paths: list[str] = []
        drv = session.driver
        try:
            # Resolve the on-disk transcript for true erasure (bridge driver only).
            if drv is not None and hasattr(drv, "_bridge") and hasattr(drv, "tmux_name"):
                from bridge.transcript import find_transcript  # type: ignore
                transcript_path = find_transcript(drv._bridge, drv.tmux_name)  # type: ignore[attr-defined]
        except Exception:
            transcript_path = None
        plan = deletion.plan_deletion(
            session_id, transcript_path=transcript_path,
            subagent_paths=subagent_paths, link_ids=link_ids,
            identity_number=number)
        # interrupt + close the live tmux session. TRUE wipe (§7.12): the
        # bridge driver also purges the per-agent launch-config dir
        # (turns.jsonl Timeline + statusline.jsonl) — nothing can resume a
        # hard-deleted agent, so the standing stores go with it. (Retire and
        # stop keep that dir so a resume re-attaches the Timeline, §7.19.)
        if drv is not None:
            try:
                if hasattr(drv, "_bridge"):
                    await drv.close(purge_config=True)  # type: ignore[call-arg]
                else:
                    await drv.close()
            except Exception:
                pass
        # erase the on-disk transcript(s). The bridge writes them inside WSL, so a
        # WSL path (/home/...) must be removed via the bridge's WSL shell — a
        # Windows Path.unlink can't reach the WSL filesystem.
        for p in plan["wipe"]["transcripts"]:
            try:
                if drv is not None and hasattr(drv, "_bridge") and str(p).startswith("/"):
                    drv._bridge._run(f"rm -f {shlex.quote(p)}")  # type: ignore[attr-defined]
                else:
                    Path(p).unlink(missing_ok=True)
            except Exception:
                pass
        # remove the roster record (project state/agents.json or app-level fallback)
        try:
            import runtime_store
            runtime_store.remove_record(session_id)
        except Exception:
            pass
        # tombstone shared links (inactive, non-functional — persisted) + retire
        # the number (persisted per project: never reused, §7.12/§11 #11)
        for lid in link_ids:
            lk = links.get_link(lid)
            if lk:
                lk.active = False
                links.touched(lk)
        project_key = state_store.project_of(session_id)
        if isinstance(number, int):
            deletion.retire_number(number)
            if project_key:
                try:
                    state_store.persist_retired_number(project_key, number)
                except Exception:
                    pass
        # drop operational state + the agent's rows in the project state/ files:
        # its inbox items and its read-bookmarks (roster row removed above;
        # routing.jsonl is append-only history and is deliberately kept).
        session.prompt_queue.clear()
        session.held.clear()
        inbox.drop_agent(session_id)
        for key in list(watermark.keys()):
            parts = key.split(":")
            if (key.startswith("scratch:") and parts[-1] == session_id) or \
                    (key.startswith("shared:") and session_id in parts[1:3]):
                watermark.drop(key)
        runstate.drop_agent(session_id)
        state_store.unregister_agent(session_id)
        session.status = "closed"
        del sessions[session_id]
        logger.info("Deleted (hard) session %s (number %s retired)", session_id, number)
        return {"status": "deleted", "session_id": session_id,
                "wiped": plan["wipe"], "tombstoned": plan["tombstone"]}

    # --- soft Retire (default) = deep-freeze, archived by default (§11 #18) ---
    # Build the LIGHT archive record BEFORE closing, sourcing the transcript
    # reference from the persisted roster record (referenced in place, never
    # copied — §8.6). The archive is per-project; a cwd-less agent has no home,
    # so archiving is skipped there (`archive_skipped: "no-project"`).
    #
    # Teardown is GATED on the archive landing (the retire data-loss fix):
    # only a successful archive write may take `driver.close()` — the retire
    # path that also removes the persisted roster row. When the write fails or
    # is skipped, that roster row is the agent's ONLY remaining persisted
    # trace, so the degrade is `stop()` semantics — end the process, KEEP the
    # record (it stays a resumable Past row) — mirroring the resume side,
    # which keeps the archive row on a failed relaunch (§9.9).
    archive_id = None
    archive_error: str | None = None
    project_key = state_store.project_of(session_id) or storage.project_key(session.cwd)
    if project_key:
        rec = getattr(session.driver, "_record", None)
        rec = rec if isinstance(rec, dict) else {}
        archive_record = deletion.build_archive_record(
            session_id,
            identity=session.identity,
            created_at=session.created_at,
            transcript_path=rec.get("transcript_path"),
            claude_session_id=rec.get("claude_session_id"),
            cwd=session.cwd,
            model=session.model,
            driver=(session.driver.name if session.driver else session.driver_name),
            permission_mode=session.permission_mode,
            git_author=git_author(session.identity) if session.identity else None,
            lineage=rec.get("lineage") if isinstance(rec.get("lineage"), dict) else None,
            # §7.19: archived so a resume re-attaches the same turns.jsonl
            # Timeline (the launch-config dir is keyed by tmux name).
            tmux_name=rec.get("tmux_name") or getattr(session.driver, "tmux_name", None),
            # §7.11: the pre-armed-Bypass launch fact, kept beside
            # permission_mode so an un-retire re-arms the same ring.
            arm_bypass=bool(rec.get("arm_bypass", session.arm_bypass)),
        )
        try:
            state_store.save_archive_record(project_key, archive_record)
            # The record's on-disk presence is the truth: the moment the write
            # lands, the retire IS archived — assign the id here so a later
            # index-touch failure can't misclassify a landed archive.
            archive_id = archive_record["archive_id"]
        except Exception as e:
            archive_error = str(e) or e.__class__.__name__
            logger.warning("archive-on-retire failed for %s: %s", session_id, e)
        if archive_id:
            # Make the archive discoverable across projects (GET /archive reads
            # the 🏠 projects index, like the live roster's all_records()).
            # Best-effort on its own: the project is almost always already in
            # the index, so a failed touch loses nothing — it must never turn
            # a landed archive into an archive_error.
            try:
                state_store.touch_projects_index(project_key)
            except Exception as e:
                logger.warning("projects-index touch failed for %s: %s",
                               project_key, e)

    # Which teardown ran on the NON-archived path: True = an overridden stop()
    # kept the persisted roster row (bridge — a resumable Past row survives),
    # False = the close() fallback ran and nothing survives dashboard-side
    # (sdk — no roster record ever existed). On the archived happy path the
    # flag is OMITTED from the response: the record lives in archive.json and
    # the frontend only consults record_kept when `archived` is null.
    record_kept: bool | None = None
    if session.driver:
        try:
            if archive_id:
                # Archived: the record lives on in archive.json, so the retire
                # close() — which also removes the roster row — is safe.
                await session.driver.close()
            else:
                # NOT archived: the persisted record must survive. Prefer the
                # driver's stop() (bridge: ends tmux, KEEPS the roster row +
                # stamps stopped_at → a resumable Past row). The base-class
                # stop() is a deliberate no-op, so only an OVERRIDDEN stop
                # counts as the record-keeping path; a driver with no
                # stop/close split (sdk — its close() never touches persisted
                # records) closes instead of leaking its process.
                stop = getattr(session.driver, "stop", None)
                if callable(stop) and getattr(type(session.driver), "stop",
                                              None) is not AgentDriver.stop:
                    record_kept = True
                    await stop()
                else:
                    record_kept = False
                    await session.driver.close()
        except Exception:
            pass
    elif not archive_id:
        # No driver to tear down — nothing removed any persisted record.
        record_kept = True
    session.status = "closed"
    del sessions[session_id]
    logger.info("Retired session %s (archived as %s)", session_id, archive_id)
    out: dict[str, Any] = {"status": "closed", "session_id": session_id,
                           "archived": archive_id}
    if record_kept is not None:
        # Non-archived path only: did a persisted (resumable) record survive?
        out["record_kept"] = record_kept
    if archive_error is not None:
        # Machine-readable "the freeze did NOT land" — the roster row was kept.
        out["archive_error"] = archive_error
    if not project_key:
        # By-design unarchivable (per-project archive, §8.2) — an explicit
        # reason, never a bare null indistinguishable from a failure.
        out["archive_skipped"] = "no-project"
    return out


# ---------------------------------------------------------------------------
# Agent archive (§11 #18) — the deep-freeze of retired agents. A separate table
# from the live roster: `GET /sessions` stays live-only; retired agents land
# here (written on Retire above). Records are light — the transcript is
# referenced in place, never copied (§8.6).
# ---------------------------------------------------------------------------

@app.get("/archive")
async def list_archive():
    """List every archived agent record across known projects (§11 #18)."""
    records = state_store.all_archived_records()
    return {"archived": records, "count": len(records)}


@app.get("/archive/{archive_id}")
async def get_archive(archive_id: str):
    """One archived record by its distinct id (404 when absent)."""
    found = state_store.find_archive_record(archive_id)
    if found is None:
        raise HTTPException(status_code=404, detail="Archived record not found")
    return found[1]


@app.delete("/archive/{archive_id}")
async def delete_archive(archive_id: str):
    """TRUE-delete an archived record (§7.12) — a real, irreversible wipe of the
    archive row, distinct from Retire (which CREATES the record) and from a hard
    agent Delete. Removes the archived record and — best-effort — the agent's
    per-agent launch-config dir (the turns.jsonl Timeline + statusline.jsonl the
    row's ``tmux_name`` keys, §7.19): nothing can resume the row afterwards, so
    keeping the standing stores would only leak them. Shared history is untouched.
    """
    found = state_store.find_archive_record(archive_id)
    if not state_store.delete_archived_anywhere(archive_id):
        raise HTTPException(status_code=404, detail="Archived record not found")
    tmux_name = (found[1] or {}).get("tmux_name") if found else None
    if tmux_name:
        try:
            from bridge import TmuxBridge  # type: ignore[import-not-found]
            await asyncio.to_thread(
                lambda: TmuxBridge().purge_launch_config(tmux_name))
        except Exception:  # pragma: no cover - purge is best-effort
            logger.warning("launch-config purge failed for archive %s (tmux %s)",
                           archive_id, tmux_name)
    return {"status": "deleted", "archive_id": archive_id}


@app.post("/sessions/{session_id}/send")
async def send_prompt(session_id: str, req: SendPromptRequest):
    """Enqueue a prompt on the per-agent ordered queue (never 409-drop).

    An idle agent flushes immediately; a busy agent queues per disposition
    (`queue`/`next`), or — for `now` — is interrupted so the resulting idle
    flushes it at the head. `hold` stages for manual release. The entry
    carries `source` + `recipients` (default the operator -> this agent).

    Attachments (§10 #1, §7.14): when the request carries asset ids, the
    delivered text gains the ONE attributed attachments block — lead line +
    one `- <WSL-readable absolute path>` bullet per asset (citation anchors
    inline) — appended after the message, on EVERY disposition (inject rides
    it too). The block is rendered here at send time (asset paths are static,
    unlike the delivery-time queue-awareness note). Honest failures: 400 for
    an unknown asset id or an agent with no cwd — never a silent drop."""
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    session = sessions[session_id]
    if not session.driver:
        raise HTTPException(status_code=503, detail="Session not connected yet")
    # §11 #34: an inbound prompt is activity — even a QUEUED one must tighten
    # the poll so the flush-on-idle transition is seen promptly.
    _nudge_driver(session_id)

    # §10 #1: resolve attachment references to the receiving agent's readable
    # absolute paths and append the attributed block to the delivered text.
    prompt_text = req.prompt
    if req.attachments:
        if not session.cwd:
            raise HTTPException(
                status_code=400,
                detail="agent has no cwd; attachments need a project store to resolve from")

        def _render_block(cwd: str, ids: list[str]) -> str:
            # Sidecar reads (slow 9P/UNC on a WSL-internal store) — runs in a
            # worker thread, never on the event loop.
            records = []
            for aid in ids:
                rec = attachments.load_asset_record(cwd, aid)
                if rec is None:
                    raise ValueError(aid)
                records.append(rec)
            return attachments.attachments_block(cwd, records)

        try:
            block = await asyncio.to_thread(
                _render_block, session.cwd, req.attachments)
        except ValueError as e:
            raise HTTPException(status_code=400,
                                detail=f"unknown attachment asset id: {e.args[0]}")
        if block:
            prompt_text = f"{prompt_text}\n\n{block}" if prompt_text.strip() else block

    # `inject` rides the hook channel, not the prompt queue: it's pushed to
    # the agent mid-turn at its next tool boundary (no stop). Queue it on the
    # durable inbox and surface a synthesized feed event (the inject text is not
    # written to the agent's JSONL transcript, so the sidecar owns its visibility).
    if req.disposition == "inject":
        inj = hookbus.enqueue_inject(session_id, prompt_text, kind="inject",
                                     source=req.source)
        event = {
            "type": "inject", "text": prompt_text, "kind": "inject",
            "inject_id": inj["id"],
            "timestamp": datetime.now().isoformat(),
            "source": req.source,
            "recipients": req.recipients if req.recipients is not None else [session_id],
        }
        if req.attachments:
            event["attachments"] = list(req.attachments)
        session.push_event(event)
        return {"status": "injected", "session_id": session_id, "inject_id": inj["id"]}

    entry = {
        "id": str(uuid.uuid4())[:8],
        "prompt": prompt_text,
        "source": req.source,
        "recipients": req.recipients if req.recipients is not None else [session_id],
        "disposition": req.disposition,
        "enqueued_at": datetime.now().isoformat(),
    }
    if req.attachments:
        entry["attachments"] = list(req.attachments)
    result = session.enqueue(entry, req.disposition)
    result["session_id"] = session_id

    if req.disposition == "hold":
        return result  # parked; never auto-flushed

    # `now` jumps the queue and interrupts the running turn so the resulting idle
    # flushes the head; otherwise try to flush immediately if the agent is idle.
    if req.disposition == "now" and session.status == "running":
        try:
            await session.driver.interrupt()
        except Exception as e:
            logger.error(f"Session {session_id} interrupt-for-now failed: {e}")
        return result

    await _flush_queue(session)
    # If it flushed (agent was idle), report sent; else it's queued behind the run.
    flushed = entry not in session.prompt_queue and req.disposition != "hold"
    if flushed and session.status != "error":
        result["status"] = "sent"
    return result


@app.get("/sessions/{session_id}/events")
async def stream_events(session_id: str):
    """SSE: replays existing events then streams new ones in real-time."""
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    session = sessions[session_id]

    queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue(maxsize=500)
    session.subscribers.append(queue)

    async def generator():
        try:
            for event in list(session.events):
                yield {"event": "message", "data": json.dumps(event)}
            while True:
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=30.0)
                    yield {"event": "message", "data": json.dumps(event)}
                except asyncio.TimeoutError:
                    yield {"event": "ping", "data": ""}
        finally:
            if queue in session.subscribers:
                session.subscribers.remove(queue)

    return EventSourceResponse(generator())


@app.get("/sessions/{session_id}/history")
async def get_history(session_id: str):
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    return sessions[session_id].events


def _parse_csv(value: str | None) -> set[str] | None:
    """Split a comma-separated From/To filter query param into a set (or None)."""
    if not value:
        return None
    parts = {p.strip() for p in value.split(",") if p.strip()}
    return parts or None


@app.get("/events")
async def stream_all_events(since: int | None = None,
                            source: str | None = None,
                            recipient: str | None = None):
    """Merged cross-agent SSE stream — the single feed all panels subscribe
    to, replacing the per-session `/history` poll.

    Replays the bounded ring (optionally from `?since=<seq>` for scroll-backfill)
    then streams live, with **server-side** From/To filtering: `?source=a,b`
    (sender) and `?recipient=user,c` (any addressee). Each event carries the stream
    envelope (id/agent_id/seq/ts) + addressing (source/recipients).
    """
    sources = _parse_csv(source)
    recipients = _parse_csv(recipient)

    queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue(maxsize=1000)
    eventbus.GLOBAL_SUBSCRIBERS.append(queue)

    async def generator():
        try:
            for event in eventbus.replay(since=since, sources=sources,
                                         recipients=recipients):
                yield {"event": "message", "data": json.dumps(event)}
            while True:
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=30.0)
                    # Apply the same server-side filter to live events.
                    if eventbus.event_matches(event, sources, recipients):
                        yield {"event": "message", "data": json.dumps(event)}
                except asyncio.TimeoutError:
                    yield {"event": "ping", "data": ""}
        finally:
            if queue in eventbus.GLOBAL_SUBSCRIBERS:
                eventbus.GLOBAL_SUBSCRIBERS.remove(queue)

    return EventSourceResponse(generator())


@app.get("/events/history")
async def get_merged_history(since: int | None = None,
                             source: str | None = None,
                             recipient: str | None = None):
    """Non-streaming merged backfill — the bounded ring sliced by `?since=<seq>`
    and From/To filtered server-side (same params as `/events`). For virtualized
    scroll without holding an SSE connection; the on-disk JSONL transcripts remain
    the source of truth beyond the ring window."""
    return eventbus.replay(since=since,
                           sources=_parse_csv(source),
                           recipients=_parse_csv(recipient))


# ============================================================================
# Hook channel — inbox-drain endpoints (the bridge points each agent's
# PostToolUse + Stop HTTP hooks here, keyed by ?agent=<sidecar-session-id>).
# Spike-proven: a PostToolUse `additionalContext` reply lands mid-turn on the
# installed build. Durable + ack-on-2xx: an inject leaves the inbox only when it
# is handed back in this 200 response; a failed/timed-out hook (non-blocking on
# the build) leaves it pending for the next boundary.
# ============================================================================

def _surface_delivered_injects(agent_id: str, injects: list[dict[str, Any]]) -> None:
    """Push a synthesized 'delivered' feed event per drained inject (best-effort,
    never fails the 2xx ack)."""
    session = sessions.get(agent_id)
    if not session:
        return
    for inj in injects:
        try:
            session.push_event({
                "type": "inject_delivered",
                "text": inj.get("text", ""),
                "kind": inj.get("kind", "inject"),
                "inject_id": inj.get("id"),
                "timestamp": datetime.now().isoformat(),
                "source": inj.get("source") or "system",
                "recipients": [agent_id],
            })
        except Exception:  # pragma: no cover - never break the ack
            pass


def _nudge_driver(agent_id: str) -> None:
    """§11 #34: snap an agent's adaptive poll cadence back to active.

    Called on the push channels that see activity BEFORE the poll does — hook
    ingest (every internal-hook endpoint), sends, interrupts, and console
    runs — so a coasted (5 s) idle poll returns to the 1 s cadence the moment
    anything happens. Best-effort no-op for sessions/drivers without it.
    """
    session = sessions.get(agent_id)
    drv = session.driver if session else None
    if drv is not None and hasattr(drv, "nudge"):
        try:
            drv.nudge()
        except Exception:  # pragma: no cover - never let a nudge break a hook
            pass


@app.post("/internal/hooks/post-tool-use/{agent}")
async def hook_post_tool_use(agent: str, body: dict[str, Any] | None = None):
    """PostToolUse drain: hand back ALL pending injects (active + passive) as one
    `additionalContext` block so a running agent receives them mid-turn at the
    next tool boundary. Empty -> `{}` (a 2xx no-op).

    Also ingests the payload's run-state fields (permission_mode / tool /
    prompt_id) into the arbiter (§7.4) — the drain and the push channel ride
    the same delivery.

    ``agent`` is a PATH param (the sidecar session id the bridge baked into the
    hook URL) — claude's http-hook client does not reliably forward a query
    string, so the id rides the path.
    """
    _nudge_driver(agent)  # §11 #34: hook activity snaps the poll cadence
    runstate.ingest(agent, "PostToolUse", body)
    injects = hookbus.drain(agent)
    if injects:
        logger.info("hook drain post-tool-use agent=%s delivered=%d", agent, len(injects))
    _surface_delivered_injects(agent, injects)
    return hookbus.post_tool_use_output(injects)


@app.post("/internal/hooks/stop/{agent}")
async def hook_stop(agent: str, body: dict[str, Any] | None = None):
    """Stop backstop: for the no-tool-call turn, surface only ACTIVE injects via
    `decision:"block"` so a pure-text turn still catches them at turn-end. Passive
    `context` injects are left pending (blocking Stop would force a continuation).
    Ingests the payload's run-state (phase → idle) into the arbiter (§7.4)."""
    _nudge_driver(agent)  # §11 #34
    runstate.ingest(agent, "Stop", body)
    injects = hookbus.drain(agent, kinds={"inject"})
    if injects:
        logger.info("hook drain stop agent=%s delivered=%d", agent, len(injects))
    _surface_delivered_injects(agent, injects)
    return hookbus.stop_output(injects)


@app.post("/internal/hooks/run-state/{agent}")
async def hook_run_state(agent: str, body: dict[str, Any] | None = None):
    """Run-state push channel (§7.4): PreToolUse catch-all / UserPromptSubmit /
    Notification POST here. The event name rides the payload's
    `hook_event_name`; `permission_mode` is event-specific (Notification lacks
    it) and the arbiter keys per event. Always returns `{}` (never gates)."""
    event = (body or {}).get("hook_event_name") or \
            (body or {}).get("hookEventName") or "Notification"
    _nudge_driver(agent)  # §11 #34
    runstate.ingest(agent, str(event), body)
    return {}


@app.post("/internal/hooks/subagent/{agent}")
async def hook_subagent(agent: str, body: dict[str, Any] | None = None):
    """SubagentStart/SubagentStop → the subagent registry (§7.17): agent_id /
    agent_type / transcript_path become the roster's authoritative
    active-vs-quiet signal, blended over the transcript-derived list."""
    event = (body or {}).get("hook_event_name") or \
            (body or {}).get("hookEventName") or "SubagentStart"
    _nudge_driver(agent)  # §11 #34
    runstate.ingest_subagent(agent, str(event), body)
    return {}


@app.get("/internal/debug/run-state/{agent}")
async def debug_run_state(agent: str):
    """Env-guarded (``AWL_RUNSTATE_DEBUG=1``) read-back of every hook delivery
    the arbiter ingested for an agent — event name, arbiter-relevant fields, and
    the raw payload key set. A live-test observability aid (§11 #21's verify
    reads exactly which events the installed CLI fired); 404 unless enabled."""
    if os.environ.get("AWL_RUNSTATE_DEBUG") != "1":
        raise HTTPException(status_code=404, detail="Not enabled")
    return {"agent": agent, "deliveries": runstate.debug_log(agent)}


# --- Plan/Decision detection via the PreToolUse hook channel ---
# The agent's ExitPlanMode (Plan) and AskUserQuestion (Decision) tool calls are
# visible to hooks even when the screen isn't. The spike confirmed the hook
# channel works; these raise the typed Inbox card (detect-and-surface). Returning
# `{}` allows the tool to proceed so the agent isn't blocked if no one answers —
# the user answers by attaching. (The richer hold-for-answer round-trip via
# updatedInput is a fast-follow that needs its own live proof.)

def _raise_plandecision(agent: str, body: dict[str, Any], itype: str) -> None:
    _nudge_driver(agent)  # §11 #34: a Plan/Decision tool call is activity
    session = sessions.get(agent)
    tool_input = (body or {}).get("tool_input") or {}
    data = {"tool": (body or {}).get("tool_name"), "tool_input": tool_input}
    inbox.raise_item(agent, itype, data, dedup_key=f"{itype}:{(body or {}).get('tool_use_id','')}")
    if session:
        try:
            session.push_event({
                "type": itype, "data": data,
                "timestamp": datetime.now().isoformat(),
                "source": agent, "recipients": ["user"],
            })
        except Exception:  # pragma: no cover
            pass


@app.post("/internal/hooks/plan/{agent}")
async def hook_plan(agent: str, body: dict[str, Any] | None = None):
    """PreToolUse(ExitPlanMode) — raise a Plan inbox card, then allow."""
    _raise_plandecision(agent, body or {}, "plan")
    return {}


@app.post("/internal/hooks/decision/{agent}")
async def hook_decision(agent: str, body: dict[str, Any] | None = None):
    """PreToolUse(AskUserQuestion) — raise a Decision inbox card, then allow."""
    _raise_plandecision(agent, body or {}, "decision")
    return {}


# --- Workflow approval via the Inbox (§11 #23) ---
# The PreToolUse(Workflow) hook fires with the FULL script preview in
# tool_input.script, a deny verdict aborts / allow launches, and the hook
# verdict preempts the built-in dialog — all spike-proven
# (tests/workflow_approval_probe/). Unlike plan/decision (detect-and-surface,
# return {}), this hook HOLDS its HTTP response on an asyncio.Future until the
# operator resolves the Review card, then answers with the verdict. The hold is
# bounded (inbox.workflow_approval_timeout_s, default 600 s — clamped per gate
# to the agent's launch-time hook-client timeout, _workflow_hold_s): on timeout
# it returns {} so Claude Code falls back to its own on-pane
# 'Run a dynamic workflow?' dialog — the documented honest fallback (the
# per-agent settings pin skipWorkflowUsageWarning:false so that dialog stays
# armed; see BridgeDriver._build_settings).

# Pending workflow gates: (agent, item_id) -> the Future the held hook awaits.
_workflow_gates: dict[tuple[str, str], asyncio.Future] = {}


def _workflow_verdict(answer: Any) -> str:
    """Normalize a Review card's resolve answer to 'approve' | 'reject'.

    Accepts the bare string ("approve") or the dict form ({"verdict":
    "approve"}); only an explicit approve/allow maps to approve — anything
    else denies (deny is the safe default for a launch gate)."""
    verdict = answer.get("verdict") if isinstance(answer, dict) else answer
    if str(verdict or "").strip().lower() in ("approve", "approved", "allow"):
        return "approve"
    return "reject"


def _workflow_hold_s(driver: Any) -> float:
    """The bounded hold for ONE workflow gate: the current knob
    (inbox.workflow_approval_timeout_s), clamped so the sidecar always answers
    before the agent's hook client gives up. The client's timeout was baked
    into the agent's --settings at LAUNCH (hold-at-launch + margin,
    BridgeDriver._build_hook_settings) while the knob is re-read per gate — so
    without the clamp, an agent launched before a knob raise (bridge agents
    outlive sidecar restarts, §9.9) would be held past its client's patience
    and the operator could "approve" into a connection nobody is waiting on.
    An unknown launch-time value (hook-less driver, pre-field record) leaves
    the knob unclamped — the constant-knob behavior."""
    hold = inbox.workflow_approval_timeout_s()
    client = getattr(driver, "workflow_hook_timeout", None)
    try:
        client_s = float(client) if client is not None else None
    except (TypeError, ValueError):  # pragma: no cover - defensive
        client_s = None
    if client_s is not None:
        hold = min(hold, max(client_s - inbox.WORKFLOW_CLIENT_MARGIN_S, 0.0))
    return hold


@app.post("/internal/hooks/workflow/{agent}")
async def hook_workflow(agent: str, body: dict[str, Any] | None = None):
    """PreToolUse(Workflow) — the workflow approval gate. Raises a Review
    inbox card carrying the parsed script preview (name / description / phases
    recovered from ``tool_input.script``) and HOLDS this response until the
    operator resolves the card: approve → PreToolUse ``allow`` (launches),
    reject → ``deny`` (aborts the Workflow call). After the bounded hold
    (default 600 s) it returns ``{}`` — the on-pane-dialog fallback — and
    marks the still-open card ``timed_out``."""
    _nudge_driver(agent)  # §11 #34: a Workflow tool call is activity
    body = body or {}
    session = sessions.get(agent)
    # Bounded hold: the knob, clamped to the client timeout the agent actually
    # launched with (see _workflow_hold_s) — computed up front so the card can
    # honestly say when its live window closes.
    hold = _workflow_hold_s(session.driver if session else None)
    tool_input = body.get("tool_input") or {}
    script = tool_input.get("script") if isinstance(tool_input, dict) else None
    script_path = tool_input.get("scriptPath") \
        if isinstance(tool_input, dict) else None
    if not script and script_path:
        # scriptPath launch shape (file-stored workflows — the Library's
        # editing model, and a shape the spike's capture treats as first-class
        # alongside inline `script`): best-effort read of the file so the
        # approval card still carries a real preview, not an empty one.
        script = inbox.read_script_for_preview(script_path)
    preview = inbox.parse_workflow_script(script)
    if script_path:
        preview["script_path"] = script_path  # always show WHAT file launches
    data = {
        "tool": body.get("tool_name") or "Workflow",
        "tool_input": tool_input,
        "preview": preview,
        # When the hold lapses unanswered the gate falls back to the on-pane
        # dialog — stamp WHEN so the card is honest about its live window.
        "hold_deadline": (datetime.now() + timedelta(seconds=hold)).isoformat(),
    }
    tool_use_id = body.get("tool_use_id")
    item = inbox.raise_item(
        agent, "review", data,
        dedup_key=f"review:{tool_use_id}" if tool_use_id else None)
    if session:
        try:
            session.push_event({
                "type": "review", "data": data,
                "timestamp": datetime.now().isoformat(),
                "source": agent, "recipients": ["user"],
            })
        except Exception:  # pragma: no cover
            pass

    key = (agent, item["id"])
    # A redelivered gate (hook retry on the same tool_use_id dedups onto the
    # same card) supersedes any stale hold: release the old waiter with the
    # {} fallback so it never dangles until timeout.
    prev = _workflow_gates.pop(key, None)
    if prev is not None and not prev.done():
        prev.set_result(None)
    fut: asyncio.Future = asyncio.get_running_loop().create_future()
    _workflow_gates[key] = fut
    try:
        verdict = await asyncio.wait_for(fut, timeout=hold)
    except asyncio.TimeoutError:
        # Honest fallback: hand the gate back to the TUI's own dialog. The
        # card stays open (the operator should still see it) but says so.
        inbox.update_item_data(agent, item["id"], {"timed_out": True})
        logger.info("workflow gate timed out agent=%s item=%s — falling back "
                    "to the on-pane dialog", agent, item["id"])
        return {}
    finally:
        if _workflow_gates.get(key) is fut:
            _workflow_gates.pop(key, None)
    if verdict == "approve":
        return {"hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "allow",
        }}
    if verdict == "reject":
        return {"hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason":
                "Workflow launch rejected from the dashboard Inbox "
                "(Review card).",
        }}
    return {}  # superseded by a redelivered gate — the fresh hold owns the verdict


# ============================================================================
# Inbox — the merged "needs you" surface across all five typed sections.
# ============================================================================

@app.get("/inbox")
async def get_inbox():
    """All open inbox items grouped by agent (error/warning/plan/decision from the
    inbox store, plus each agent's pending permission), and the fleet badge =
    number of agents with >=1 open request."""
    grouped: dict[str, list[dict[str, Any]]] = {}
    for agent_id, items in inbox.all_open().items():
        grouped.setdefault(agent_id, []).extend(items)
    # Merge in screen-anchored permission prompts (they live on SessionState).
    # (Snapshot against concurrent create/retire mutation, like GET /usage.)
    for sid, s in list(sessions.items()):
        if s.pending_permission:
            grouped.setdefault(sid, []).append({
                "id": f"perm:{sid}", "agent_id": sid, "type": "permission",
                "data": s.pending_permission, "resolved": False,
            })
    return {"inbox": grouped, "fleet_badge": len(grouped)}


@app.post("/inbox/{agent}/{item_id}/resolve")
async def resolve_inbox_item(agent: str, item_id: str, body: dict[str, Any] | None = None):
    """Resolve an inbox item. Resolving a `review` card additionally completes
    the HELD workflow hook (§11 #23): the answer's verdict maps approve → allow
    (launch) / anything else → deny (abort). A review card whose hold already
    lapsed (timed out) still resolves normally — the gate just isn't waiting."""
    answer = (body or {}).get("answer")
    ok = inbox.resolve_item(agent, item_id, answer=answer)
    if not ok:
        raise HTTPException(status_code=404, detail="Inbox item not found")
    gate = _workflow_gates.pop((agent, item_id), None)
    if gate is not None and not gate.done():
        gate.set_result(_workflow_verdict(answer))
    return {"status": "resolved", "agent": agent, "item_id": item_id}


# ============================================================================
# Run-strip checklist (done÷total, barber-pole floor)
# ============================================================================

def _assistant_texts(session: "SessionState") -> list[str]:
    out: list[str] = []
    for ev in session.events:
        if ev.get("type") != "assistant":
            continue
        content = ev.get("content")
        if isinstance(content, str):
            out.append(content)
        elif isinstance(content, list):
            buf = []
            for block in content:
                if isinstance(block, dict) and block.get("type") == "text":
                    buf.append(block.get("text") or "")
                elif isinstance(block, str):
                    buf.append(block)
            if buf:
                out.append("\n".join(buf))
    return out


@app.get("/sessions/{session_id}/checklist")
async def get_checklist(session_id: str):
    """The agent's self-reported checklist parsed from its transcript
    (done÷total + current item); barber-pole indeterminate when none published."""
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    return checklist.parse_checklist(_assistant_texts(sessions[session_id]))


# ============================================================================
# Templates store (dashboard runtime store; reusable / project-agnostic)
# ============================================================================

# ============================================================================
# Plans action loop (§7.16, §9.7; §11 #22) — verdicts wired into the live flow
# ============================================================================

class PlanVerdictRequest(BaseModel):
    """Answer a pending plan-approval pause. ``approve`` resumes the agent out
    of plan mode via the proven `keys()` Enter (`test_plan_decision_hooks_live`
    — NOT a hook `updatedInput`). ``revise`` sends Escape (keep planning) and
    queues the revise feedback as the next prompt. Optionally records the
    verdict on the plan doc's `.meta.json` sidecar (`filename` + the agent's
    project resolves it)."""
    verdict: Literal["approve", "revise"]
    text: str | None = None        # revise feedback (queued to the agent)
    filename: str | None = None    # plan doc to stamp the verdict on
    by: str | None = None          # verdict author (defaults to "user")


@app.post("/sessions/{session_id}/plan/verdict")
async def plan_verdict(session_id: str, req: PlanVerdictRequest):
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    session = sessions[session_id]
    if not session.driver:
        raise HTTPException(status_code=503, detail="Session not connected yet")
    drv = session.driver
    if not hasattr(drv, "_bridge"):
        raise HTTPException(status_code=400, detail="Driver has no plan control")

    if req.verdict == "approve":
        # The proven resume: Enter selects the plan menu's default approve.
        await asyncio.to_thread(drv._bridge.keys, drv.tmux_name, "Enter")  # type: ignore[attr-defined]
    else:
        # Revise: Escape keeps the agent planning (⚠ assumed — the Escape leg
        # is the unproven half; verified at the e2e drive), then the feedback
        # queues as the next prompt.
        await asyncio.to_thread(drv._bridge.keys, drv.tmux_name, "Escape")  # type: ignore[attr-defined]
        if req.text:
            entry = {
                "id": str(uuid.uuid4())[:8], "prompt": req.text,
                "source": "user", "recipients": [session_id],
                "disposition": "next", "enqueued_at": datetime.now().isoformat(),
            }
            session.enqueue(entry, "next")
            _schedule_flush(session)

    # Resolve the open plan inbox card(s) for this agent.
    for it in inbox.items_for(session_id):
        if it["type"] == "plan":
            inbox.resolve_item(session_id, it["id"], answer=req.verdict)

    # Stamp the verdict on the plan doc's sidecar when named (a review WRITE —
    # resolved over the store's plans/+docs/ only, never the project root).
    if req.filename and session.cwd:
        try:
            doc = library.resolve_document_for_write(session.cwd, req.filename)
            if doc is not None:
                library.set_doc_review(str(doc), verdict=req.verdict,
                                       verdict_by=req.by or "user")
        except Exception:
            logger.warning("plan verdict: could not stamp %s", req.filename)

    return {"status": "ok", "verdict": req.verdict, "session_id": session_id}


class DocumentWriteRequest(BaseModel):
    """Edit-in-place for a dashboard-owned doc/plan (§7.16: an explicit,
    user-directed rewrite — never the review layer writing into content)."""
    cwd: str
    path: str
    content: str


@app.put("/library/document")
async def library_write_document(req: DocumentWriteRequest):
    if not library.document_in_content_dirs(req.path, req.cwd):
        raise HTTPException(status_code=400,
                            detail="writes are scoped to the store's plans/ and docs/ dirs")
    p = Path(req.path)
    if not p.is_file():
        raise HTTPException(status_code=404, detail="Document not found")
    tmp = p.with_suffix(p.suffix + ".tmp")
    tmp.write_text(req.content, encoding="utf-8")
    os.replace(tmp, p)
    return {"status": "written", "path": str(p), "size": len(req.content)}


# ============================================================================
# Projects — system-side surface (§3, §9.1, §9.8; §11 #26)
# ============================================================================

class ProjectPathRequest(BaseModel):
    path: str


class ProjectCloseRequest(BaseModel):
    # §3.4: exactly two options — Close (detach; agents keep running in tmux)
    # and Close & stop agents (also end the project's tmux sessions gracefully).
    stop_agents: bool = False


@app.get("/projects")
async def list_projects():
    """The Projects picker feed (§3.2): known canonical roots from the 🏠 index
    (name, path, last-opened, agent count) plus which project is open (if any).
    Only OPERATOR-registered roots list — an index row auto-created by record
    routing (e.g. a fork's git-worktree cwd, §7.19) is bookkeeping, not a known
    project, until the operator registers/opens it."""
    entries = [_project_entry(key, meta)
               for key, meta in state_store.registered_projects().items()]
    entries.sort(key=lambda e: e.get("last_used") or "", reverse=True)
    return {"open": _open_project, "projects": entries}


@app.post("/projects/register")
async def register_project(req: ProjectPathRequest):
    """"Open other folder…" first half (§3.2): register a new project root into
    the index (canonicalized). Does not open it."""
    key = storage.project_key(req.path)
    if not key:
        raise HTTPException(status_code=400, detail="path required")
    if not Path(key).is_dir():
        raise HTTPException(status_code=400, detail=f"not a directory: {key}")
    state_store.touch_projects_index(key, register=True)
    return _project_entry(key, state_store.known_projects().get(key, {}))


@app.post("/projects/open")
async def open_project(req: ProjectPathRequest):
    """Open a project (§9.1): load its persisted store (roster, inbox, links,
    bookmarks, scratchpad board), warm-rebind still-alive tmux sessions and
    cold-restore dead ones (§9.9 — transcript replay refills the feed via the
    driver polls), and mark it the open project. One project at a time: opening
    while another is open is a 409 — close-then-open IS the switch (§3.1)."""
    global _open_project
    key = storage.project_key(req.path)
    if not key:
        raise HTTPException(status_code=400, detail="path required")
    if not Path(key).is_dir():
        raise HTTPException(status_code=400, detail=f"not a directory: {key}")
    if _open_project is not None and _open_project != key:
        raise HTTPException(
            status_code=409,
            detail=f"another project is open ({_open_project}); close it first")
    state_store.load_project(key)
    # §9.1: project-open IS the restore point — warm-rebind the still-alive
    # tmux sessions and cold-restore the dead ones for THIS project (startup
    # restores nothing by default; see _on_startup).
    await reconnect_sessions(project_key=key)
    _open_project = key
    state_store.touch_projects_index(key, register=True)
    return {"status": "open", **_project_entry(key, state_store.known_projects().get(key, {}))}


@app.post("/projects/close")
async def close_project(req: ProjectCloseRequest | None = None):
    """Close the open project (§3.4, §9.8). **Close** (default): the dashboard
    lets go — agents keep running detached in tmux; nothing is flushed because
    persistence is write-as-it-happens. **Close & stop agents**
    (`stop_agents: true`): additionally ends the project's tmux sessions
    gracefully; transcripts persist either way."""
    global _open_project
    if _open_project is None:
        raise HTTPException(status_code=409, detail="no project is open")
    key = _open_project
    stop = bool(req and req.stop_agents)
    closed_sessions = []
    for sid, session in list(sessions.items()):
        if storage.project_key(session.cwd) != key:
            continue
        if session.listen_task and not session.listen_task.done():
            session.listen_task.cancel()
        if stop and session.driver:
            try:
                # stop() ends the tmux session but KEEPS the roster record, so
                # reopening the project can cold-restore the team (§9.9).
                stopper = getattr(session.driver, "stop", None)
                if stopper is not None:
                    await stopper()
                else:  # drivers without a stop(): fall back to close()
                    await session.driver.close()
            except Exception:
                pass
        state_store.unregister_agent(sid)
        del sessions[sid]
        closed_sessions.append(sid)
    _open_project = None
    return {"status": "closed", "path": key,
            "stopped_agents": stop, "detached_sessions": closed_sessions}


@app.get("/templates")
async def list_templates_endpoint():
    return templates_store.list_templates()


@app.post("/templates")
async def add_template_endpoint(req: TemplateRequest):
    return templates_store.add_template(req.name, req.body, req.placeholders)


@app.delete("/templates/{template_id}")
async def delete_template_endpoint(template_id: str):
    if not templates_store.remove_template(template_id):
        raise HTTPException(status_code=404, detail="Template not found")
    return {"status": "deleted", "template_id": template_id}


# ============================================================================
# Library — project-scoped read + render + per-doc metadata sidecars (§8.5).
# Every WRITE endpoint is scope-guarded to the store's plans/ and docs/ content
# dirs (document_in_content_dirs — never state/ or other store files); the rest
# of the repo stays browse-read-only (§8.5 rule 5), and review writes never
# mint a sidecar at the repo root (resolve_document_for_write).
# ============================================================================

@app.get("/library/documents")
async def library_documents(cwd: str, subdir: str | None = None):
    """List the project's markdown Plans/Documents (project-scoped).

    ``subdir="plans"`` / ``"docs"`` list the project store
    (``<project>/.awl-cc-dash/<subdir>``), falling back to the legacy
    ``<root>/<subdir>`` when the store dir doesn't exist yet — both
    **recursive** (§7.16): nested trees (e.g. ``plans/phase-1/plan.md``) are
    walked (cycle-safe — junctions/symlinks are never traversed), each entry
    carrying its base-relative ``rel_path``. The store's ``docs/prompts/``
    subtree is excluded: that is the §11 #45 prompt-library project copy — the
    ``/prompt-library`` surface's data, not documents (the legacy fallback has
    no such carve-out; a repo's real ``docs/prompts/`` is ordinary browse
    content). No ``subdir`` keeps listing the project root itself — the
    browse-read-only surface, deliberately top-level only (walking a whole
    repo would be pathological; other ``subdir`` values likewise browse
    ``<root>/<subdir>`` read-only, top-level).

    Each entry carries a ``provenance`` block (created-by / when / session) from
    the doc's ``.meta.json`` sidecar (§8.5, §11 #41), so the renderer's Authors
    lens groups by author off the listing; ``{}`` for un-stamped/browse docs."""
    root = storage.project_root(cwd)
    if not root:
        raise HTTPException(status_code=400, detail="cwd required")
    if subdir in ("plans", "docs"):
        exclude = (library.PROMPT_LIBRARY_SUBDIR,) if subdir == "docs" else ()
        store_dir = storage.plans_dir(cwd) if subdir == "plans" else storage.docs_dir(cwd)
        if store_dir is not None and store_dir.is_dir():
            return await asyncio.to_thread(
                library.list_markdown, str(store_dir), None, True, exclude)
        return await asyncio.to_thread(
            library.list_markdown, str(root), subdir, True)
    return library.list_markdown(str(root), subdir)


@app.get("/library/document")
async def library_document(path: str):
    try:
        return library.read_document(path)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Document not found")


@app.post("/library/document")
async def library_create_document(req: DocumentCreateRequest):
    """Create a dashboard-owned document in the store (``docs/`` or ``plans/``).
    409 when the target already exists; 400 on an invalid filename/subdir."""
    try:
        return library.create_document(req.cwd, req.filename, req.content, subdir=req.subdir)
    except FileExistsError:
        raise HTTPException(status_code=409, detail="Document already exists")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.delete("/library/document")
async def library_delete_document(path: str, cwd: str):
    """Delete a store document + its paired ``.meta.json``. 400 outside the
    store's ``plans/``/``docs/`` dirs (browse-only files and ``state/`` are
    never deletable), 404 when missing."""
    try:
        return library.delete_document(path, cwd)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Document not found")


@app.post("/library/document/rename")
async def library_rename_document(req: DocumentRenameRequest):
    """Rename a store document AND its sidecar together (§8.5 rule 3). 400
    outside the store's ``plans/``/``docs/`` dirs, 404 when the source is
    missing, 409 on an existing target."""
    if not library.document_in_content_dirs(req.path, req.cwd):
        raise HTTPException(status_code=400,
                            detail="path is not under the project store's plans/ or docs/ dirs")
    try:
        return library.rename_document_pair(req.path, req.new_filename)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Document not found")
    except FileExistsError:
        raise HTTPException(status_code=409, detail="Target already exists")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/library/reviews")
async def library_reviews(cwd: str):
    """Per-doc sidecar metadata for the whole project, filename-keyed (§8.5).
    Runs the one-time legacy ``plan-reviews.json`` → sidecar migration first,
    then aggregates every sidecar under the store's ``plans/`` + ``docs/`` —
    recursively, the same §7.16 scope the Documents listing walks (a comment
    on a nested doc must surface here), ``docs/prompts/`` excluded."""
    if not storage.project_root(cwd):
        raise HTTPException(status_code=400, detail="cwd required")
    await asyncio.to_thread(library.migrate_plan_reviews, cwd)
    return await asyncio.to_thread(library.aggregate_metas, cwd)


@app.post("/library/reviews")
async def library_set_review(req: ReviewRequest):
    """Write review fields into the doc's ``.meta.json`` sidecar (§8.5) —
    merge-don't-clobber. The doc is resolved by bare filename over the WRITE
    collections only (store ``plans/``, then ``docs/`` — never the project
    root, so no sidecar is ever minted at the repo root); 404 when no such
    ``.md`` exists there. ``comments`` (backward-compatible: strings or dicts)
    append as comment threads. Returns the updated sidecar."""
    try:
        md = library.resolve_document_for_write(req.cwd, req.filename)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    if md is None:
        raise HTTPException(status_code=404, detail="Document not found")
    library.set_doc_review(md, owner=req.owner, state=req.state,
                           verdict=req.verdict, verdict_by=req.verdict_by)
    for item in (req.comments or []):
        if isinstance(item, dict):
            library.add_comment(
                md, text=str(item.get("text") or ""),
                author=str(item.get("author") or req.owner or "user"),
                anchor_quote=item.get("anchor_quote"),
                anchor_heading=item.get("anchor_heading"))
        else:
            library.add_comment(md, text=str(item), author=req.owner or "user")
    return library.load_meta(md)


@app.post("/library/comments")
async def library_add_comment(req: CommentRequest):
    """Append a comment (optionally quote-anchored, §8.5) to a store document's
    sidecar. 400 outside the store's ``plans/``/``docs/`` dirs, 404 when the
    ``.md`` is missing."""
    if not library.document_in_content_dirs(req.path, req.cwd):
        raise HTTPException(status_code=400,
                            detail="path is not under the project store's plans/ or docs/ dirs")
    if not Path(req.path).is_file():
        raise HTTPException(status_code=404, detail="Document not found")
    return library.add_comment(req.path, text=req.text, author=req.author,
                               anchor_quote=req.anchor_quote,
                               anchor_heading=req.anchor_heading)


@app.post("/library/comments/resolve")
async def library_resolve_comment(req: CommentResolveRequest):
    """Mark one comment resolved. 400 outside the store's ``plans/``/``docs/``
    dirs, 404 for an unknown id."""
    if not library.document_in_content_dirs(req.path, req.cwd):
        raise HTTPException(status_code=400,
                            detail="path is not under the project store's plans/ or docs/ dirs")
    if not library.resolve_comment(req.path, req.comment_id):
        raise HTTPException(status_code=404, detail="Comment not found")
    return {"status": "resolved", "comment_id": req.comment_id}


# ============================================================================
# Shared scratchpad — post + auto-read delta (live mid-run push)
# ============================================================================

class ScratchPostRequest(BaseModel):
    cwd: str                       # the project (co-located agents share a board)
    author: str
    text: str


@app.get("/scratch")
async def get_scratch(cwd: str):
    # Lazy-load (idempotent): a GET against a not-yet-loaded project must
    # surface its persisted board, not an empty in-memory one.
    state_store.load_project(cwd)
    # Boards are keyed by the CANONICAL project root, so any cwd spelling the
    # client passes resolves to the same board an agent in that project uses.
    key = storage.project_key(cwd) or cwd
    return {"posts": scratchpad.all_posts(key)}


@app.post("/scratch")
async def post_scratch(req: ScratchPostRequest):
    """Append a post; feed it (recipients:[scratch]); and push each RUNNING agent
    in the same project its unread delta mid-run via the hook channel (idle agents
    catch up at their next run's first tool boundary)."""
    # Lazy-load (idempotent) BEFORE posting: a post into a not-yet-loaded
    # project must append to the persisted board, never clobber it with a
    # one-post mirror rewrite.
    state_store.load_project(req.cwd)
    key = storage.project_key(req.cwd) or req.cwd
    persist = None
    try:
        sp = storage.scratchpad_path(req.cwd)
        persist = str(sp) if sp else None
    except Exception:
        persist = None
    post = scratchpad.post(key, req.author, req.text, persist_path=persist)
    # live mid-run push to running co-located agents (canonical-key match)
    # (Snapshot against concurrent create/retire mutation, like GET /usage.)
    for s in list(sessions.values()):
        if s.status == "running" and _scratch_key(s) == key:
            _deliver_scratch_delta(s)
    return {"status": "posted", "post": post}


# ============================================================================
# Marquee — the per-agent liveness tail (derived from the stream)
# ============================================================================

@app.get("/sessions/{session_id}/marquee")
async def get_marquee(session_id: str):
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    events = sessions[session_id].events
    return {"line": marquee.marquee_line(events), "idle": marquee.is_idle(events)}


# ============================================================================
# Console — slash-command catalog (the live feed/route rides send/keys +
# capture-pane on the bridge; interactive commands need follow-on handling)
# ============================================================================

@app.get("/console/catalog")
async def console_catalog_endpoint(q: str | None = None):
    if q:
        return {"commands": console_catalog.filter_commands(q)}
    return {"clusters": console_catalog.clusters(),
            "by_cluster": console_catalog.by_cluster()}


class ConsoleRunRequest(BaseModel):
    command: str


class ConsoleResizeRequest(BaseModel):
    """Viewer-driven geometry for the pinned console pane (§7.13): the applied
    size is clamped to the scraper-safe bounds below before reaching tmux."""
    cols: int
    rows: int


# Scraper-safe console geometry bounds (§7.13): every capture-pane parser is
# proven tolerant of WIDER/TALLER; NARROW is the hostile direction (menu
# bottom-slack and TUI truncation start biting somewhere below ~60 columns) —
# so the floor is the load-bearing guard. Clamping is belt-and-braces: the
# bridge's console_resize clamps to the same bounds internally.
CONSOLE_COLS_RANGE = (60, 500)
CONSOLE_ROWS_RANGE = (15, 200)


def _is_clear_command(command: str) -> bool:
    """True when a Console command is a ``/clear`` — the one slash-command that
    rotates the agent's JSONL transcript and orphans the pinned resolution
    (§7.13; ``/compact`` annotates the same file and is safe). Keyed on the
    first token so arguments/whitespace don't dodge the detection."""
    parts = (command or "").strip().split()
    return bool(parts) and parts[0].lower() == "/clear"


@app.post("/sessions/{session_id}/console/run")
async def console_run(session_id: str, req: ConsoleRunRequest):
    """Route a slash-command to the focused agent over the bridge (send/keys), then
    read the screen back. Interactive commands (e.g. /model, /clear) drop the agent
    into a sub-prompt — flagged so the caller drives the follow-on rather than
    blind-sending.

    A ``/clear`` additionally triggers the post-rotation transcript re-resolve
    (§7.13, §11 #35): the driver re-pins the rotated ``<new-id>.jsonl`` (or arms a
    pending retry until it appears) so post-/clear turns are never lost to the
    sidecar. The result rides back as ``transcript_rotation``.
    """
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    session = sessions[session_id]
    drv = session.driver
    if drv is None or not hasattr(drv, "_bridge") or not hasattr(drv, "tmux_name"):
        raise HTTPException(status_code=400, detail="Console requires a bridge agent")
    interactive = console_catalog.is_interactive(req.command.split()[0] if req.command else "")
    _nudge_driver(session_id)  # §11 #34: a console run is activity
    try:
        drv._bridge.send(drv.tmux_name, req.command)          # type: ignore[attr-defined]
        await asyncio.sleep(1.0)
        screen = drv._bridge.read(drv.tmux_name, lines=40)["content"]  # type: ignore[attr-defined]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"console run failed: {e}")
    result = {"command": req.command, "interactive": interactive, "screen": screen}
    if _is_clear_command(req.command) and hasattr(drv, "handle_transcript_rotation"):
        try:
            result["transcript_rotation"] = await drv.handle_transcript_rotation()
        except Exception as e:  # pragma: no cover - never fail the console reply
            logger.warning("post-/clear transcript re-resolve failed: %s", e)
            result["transcript_rotation"] = {"rotated": False, "pending": True,
                                             "error": str(e)}
    return result


def _require_bridge_console(session_id: str):
    """Resolve a session to its bridge driver for the Console surfaces (404 on
    an unknown session, 400 on a non-bridge driver — the Console is a bridge
    feature: there is no terminal to attach for the sdk driver)."""
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    drv = sessions[session_id].driver
    if drv is None or not hasattr(drv, "_bridge") or not hasattr(drv, "tmux_name"):
        raise HTTPException(status_code=400, detail="Console requires a bridge agent")
    return drv


@app.post("/sessions/{session_id}/console/attach")
async def console_attach_endpoint(session_id: str):
    """Attach the focused agent's LIVE terminal stream (§7.13, §11 #29).

    Starts (or reuses — one attach per session) a writable ttyd inside WSL
    bound to the agent's tmux session, with the pane geometry pinned FIRST
    (`window-size manual`) so a viewer can never perturb the sidecar's
    capture-pane coordination reads. Returns the WebSocket endpoint the
    xterm.js-class renderer consumes (ttyd's `tty` subprotocol; reachable from
    Windows over localhost — WSL2's default relay, no port-forwarding).

    Attach-on-open / detach-on-close is the FRONTEND's duty — the backend only
    serves the contract. Interception stays on the JSONL transcript (§7.13):
    nothing machine-reads this stream.
    """
    drv = _require_bridge_console(session_id)
    try:
        info = await asyncio.to_thread(
            drv._bridge.console_attach, drv.tmux_name)  # type: ignore[attr-defined]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"console attach failed: {e}")
    return {"ws_url": info["ws_url"], "url": info["url"],
            "port": info["port"], "reused": info["reused"]}


@app.post("/sessions/{session_id}/console/detach")
async def console_detach_endpoint(session_id: str):
    """Detach the focused agent's live terminal stream (kill its ttyd).

    Idempotent — detaching an un-attached session is a no-op success. The
    geometry pin stays in place (deliberate; see `TmuxBridge.console_detach`).
    """
    drv = _require_bridge_console(session_id)
    try:
        result = await asyncio.to_thread(
            drv._bridge.console_detach, drv.tmux_name)  # type: ignore[attr-defined]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"console detach failed: {e}")
    return {"status": result.get("status", "detached"),
            "port": result.get("port")}


@app.post("/sessions/{session_id}/console/resize")
async def console_resize_endpoint(session_id: str, req: ConsoleResizeRequest):
    """Resize the focused agent's pinned console pane (§7.13 geometry seam).

    The pane stays under ``window-size manual`` — honoring a viewer's geometry
    is a DELIBERATE, sidecar-mediated act (the bridge issues ``tmux
    resize-window -x -y``, which keeps the manual pin by definition), never a
    viewer side effect. cols/rows are clamped to the scraper-safe bounds
    BEFORE the bridge call (the bridge clamps to the same bounds — belt and
    braces), and the response carries the APPLIED values from the bridge's
    ``{ok, cols, rows}``. A bridge ``{ok: False, reason}`` maps like the mode
    endpoint: ``busy`` → 409 (retryable), anything else → 400.
    """
    drv = _require_bridge_console(session_id)
    cols = max(CONSOLE_COLS_RANGE[0], min(CONSOLE_COLS_RANGE[1], req.cols))
    rows = max(CONSOLE_ROWS_RANGE[0], min(CONSOLE_ROWS_RANGE[1], req.rows))
    try:
        result = await asyncio.to_thread(
            drv._bridge.console_resize, drv.tmux_name, cols, rows)  # type: ignore[attr-defined]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"console resize failed: {e}")
    if not result.get("ok"):
        reason = str(result.get("reason") or "failed")
        raise HTTPException(status_code=409 if reason == "busy" else 400,
                            detail=f"console resize failed: {reason}")
    return {"ok": True, "cols": result.get("cols"), "rows": result.get("rows")}


# ============================================================================
# Settings — interactive reads/writes (confirm-gated) + account/usage
# ============================================================================

class SettingsWriteRequest(BaseModel):
    path: str
    key: str | None = None      # dotted key for set/toggle/remove; None -> whole-doc write
    value: Any | None = None
    op: Literal["write", "set", "toggle", "remove"] = "set"
    confirm: bool = False


@app.get("/settings/read")
async def settings_read(path: str):
    return settings_io.read_json(path)


@app.get("/settings/account")
async def settings_account(creds_path: str, claude_json_path: str | None = None):
    """The Usage tab's account band (read-only, §7.15).

    With ``claude_json_path`` given this is the §11 #33 **split-source** read
    (the live-mapped boundary: email/org from `.claude.json` `oauthAccount`,
    plan from the credentials file's `claudeAiOauth.subscriptionType`, plus
    `rate_limit_tier` and the read-only `auth_expiry` signal — null when the
    creds expose no expiry). Without it, the legacy single-file read is served
    unchanged.
    """
    if claude_json_path:
        return settings_io.account_band_split(claude_json_path, creds_path)
    return settings_io.account_band(creds_path)


@app.post("/settings/write")
async def settings_write(req: SettingsWriteRequest):
    try:
        if req.op == "write":
            return settings_io.write_json(req.path, req.value or {}, confirm=req.confirm)
        if req.op == "toggle":
            return settings_io.toggle_key(req.path, req.key, confirm=req.confirm)
        if req.op == "remove":
            return settings_io.remove_key(req.path, req.key, confirm=req.confirm)
        return settings_io.set_key(req.path, req.key, req.value, confirm=req.confirm)
    except settings_io.ConfirmationRequired:
        raise HTTPException(status_code=428, detail="Confirmation required (set confirm=true)")


# ============================================================================
# Utility-LLM passes — Revise / Summarize via the sdk engine (the ONLY two
# non-bridge consumers). Everything else multi-agent stays on the bridge.
# ============================================================================

class ReviseRequest(BaseModel):
    # `cwd` scopes the system-prompt text to a project's prompt-library copy
    # (§11 #45); omitted -> the shipped defaults / in-code fallback apply.
    text: str
    scope: Literal["grammar", "language", "refactor"] = "grammar"
    model: str | None = None
    cwd: str | None = None

class SummarizeRequest(BaseModel):
    text: str
    model: str | None = None
    cwd: str | None = None  # §11 #45 project scoping, like ReviseRequest


@app.post("/utility/revise")
async def utility_revise(req: ReviseRequest):
    try:
        return {"scope": req.scope, "result": await utility_llm.revise(req.text, req.scope, req.model, req.cwd)}
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"revise pass failed: {e}")


@app.post("/utility/summarize")
async def utility_summarize(req: SummarizeRequest):
    try:
        return {"result": await utility_llm.summarize(req.text, req.model, req.cwd)}
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"summarize pass failed: {e}")


# ============================================================================
# Prompt / UI-text markdown library (§7.14, §8.2, §8.4; §11 #45) — scope-aware
# canned text: shipped defaults in-repo (assets/prompts/) + a per-project copy
# (<project>/.awl-cc-dash/docs/prompts/), project-overrides-defaults.
# ============================================================================

class PromptLibraryWriteRequest(BaseModel):
    """Upsert ONE item into the PROJECT scope (§11 #45). The shipped defaults
    are repo source files — never written through the API. ``file`` names the
    target ``.md`` (basename); omitted, it is inferred from where the group
    lives in the shipped defaults."""
    cwd: str
    group: str
    key: str
    text: str
    file: str | None = None


@app.get("/prompt-library")
async def get_prompt_library(scope: str = "resolved", cwd: str | None = None):
    """The prompt/UI-text library as ``{scope, cwd, groups}`` (§11 #45).

    ``scope=defaults`` reads the shipped in-repo files; ``scope=project`` reads
    the project copy under ``cwd``'s store (400 without a ``cwd``; ``{}`` when
    the project has none); ``scope=resolved`` (the default) is the merged view —
    project overrides defaults item-wise, and without a ``cwd`` it is exactly
    the defaults (no project in play). 400 on an unknown scope.
    """
    if scope not in ("resolved", "defaults", "project"):
        raise HTTPException(status_code=400,
                            detail="scope must be resolved|defaults|project")
    if scope == "defaults":
        groups = prompt_library.load_defaults()
    elif scope == "project":
        if not cwd:
            raise HTTPException(status_code=400,
                                detail="project scope requires cwd")
        groups = prompt_library.load_project(cwd)
    else:
        groups = prompt_library.resolved(cwd)
    return {"scope": scope, "cwd": cwd, "groups": groups}


@app.post("/prompt-library")
async def write_prompt_library(req: PromptLibraryWriteRequest):
    """Write one item into the PROJECT prompt-library scope (§11 #45).

    Writes only ``<project>/.awl-cc-dash/docs/prompts/`` (atomic re-render of
    the target file; sibling groups/items preserved) — the shipped defaults are
    edited as repo source, never through here. 400 on an invalid write (no
    project home, unknown group with no explicit ``file``, unsafe file name,
    or item text that would re-parse as ``##``/``###`` structure)."""
    try:
        return {"status": "written",
                **prompt_library.write_item(req.cwd, req.group, req.key,
                                            req.text, file=req.file)}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/roles")
async def get_roles(cwd: str | None = None):
    """The two-scope ``agent.md`` role catalog (DESIGN.md's ND 12 Role combobox).

    ``system`` reads ``~/.claude/agents`` (surfaced, not owned;
    ``AWL_SYSTEM_AGENTS_DIR`` overrides for tests); ``project`` reads
    ``<project>/.awl-cc-dash/agents/`` under ``cwd``. With no ``cwd`` (or one
    with no project home) the project scope degrades honestly — ``dir: null``
    + empty roles — mirroring the prompt library's no-project read. Each role
    is the parsed front matter (LIGHT — no markdown body) plus
    ``file``/``scope``, and carries both the raw ``color`` and the mapped
    ``color_hex`` (see :mod:`roles`); roles sort by name within each scope.
    """
    system_dir = roles.system_agents_dir()
    project_dir = roles.project_agents_dir(cwd)
    return {
        "system": {
            "label": roles.SYSTEM_LABEL,
            "dir": str(system_dir),
            "roles": roles.list_roles(system_dir, "system"),
        },
        "project": {
            "label": roles.PROJECT_LABEL,
            "dir": None if project_dir is None else str(project_dir),
            "roles": roles.list_roles(project_dir, "project"),
        },
    }


# ============================================================================
# Tier-2 linking — link CRUD + the reply-to conversation kickoff.
# The on-idle reply-to relay lives in SessionState.handle_event / _maybe_relay_reply.
# ============================================================================

@app.post("/links")
async def create_link(req: CreateLinkRequest):
    """Create an agent-to-agent link (one relationship per link, §7.6).

    A legacy list ``relationship`` is tolerated — its first element is taken
    (the pre-split multi-select shape). No ``trigger`` applies the
    per-relationship default: direct → queue, shared → piggyback."""
    rel = req.relationship
    if isinstance(rel, list):                     # legacy multi-select input
        rel = next((str(r) for r in rel if r), "direct")
    if rel not in ("direct", "shared"):
        raise HTTPException(status_code=400,
                            detail="relationship must be 'direct' or 'shared'")
    lk = links.add_link(
        a=req.a, b=req.b, direction=req.direction,
        relationship=rel, shared_content=req.shared_content,
        shared_backfill=req.shared_backfill, trigger=req.trigger,
        end_after_exchanges=req.end_after_exchanges,
        end_after_tokens=req.end_after_tokens,
    )
    return lk.to_dict()


@app.get("/links")
async def list_links():
    """All links, plus the grouped-by-agent view (each link under both
    agents' groups, with the direction arrow relative to that group's agent)."""
    return {
        "links": [lk.to_dict() for lk in links.all_links()],
        "grouped": links.grouped_by_agent(),
    }


@app.delete("/links/{link_id}")
async def delete_link(link_id: str):
    if not links.remove_link(link_id):
        raise HTTPException(status_code=404, detail="Link not found")
    return {"status": "deleted", "link_id": link_id}


@app.post("/links/{link_id}/kickoff")
async def kickoff_link(link_id: str, req: LinkKickoffRequest):
    """Start a reply-to conversation over a link: deliver `prompt` to `to_agent`
    and record that its reply routes back to `from_agent`. The relay then
    alternates automatically until the End-After cap. Queue awareness (§11 #24):
    if other-source mail is still queued for the target when the kickoff is
    DELIVERED (the _flush_queue pop), the prompt leads with the attributed
    front-matter note; else it is byte-for-byte unchanged."""
    lk = links.get_link(link_id)
    if not lk:
        raise HTTPException(status_code=404, detail="Link not found")
    if not lk.allows(req.from_agent, req.to_agent):
        raise HTTPException(status_code=400,
                            detail="Link direction does not allow from->to")
    target = sessions.get(req.to_agent)
    if not target or not target.driver:
        raise HTTPException(status_code=404, detail="Target agent not connected")
    # Record reply-to BEFORE delivery so the target's finished turn fires back.
    target.answering_source = req.from_agent
    target.answering_link = link_id
    entry = {
        "id": str(uuid.uuid4())[:8], "prompt": req.prompt,
        "source": req.from_agent, "recipients": [req.to_agent],
        "disposition": lk.trigger, "enqueued_at": datetime.now().isoformat(),
        "queue_awareness": True,  # §11 #24: note renders at flush, not here
    }
    target.enqueue(entry, lk.trigger if lk.trigger in ("now", "next", "queue") else "queue")
    await _flush_queue(target)
    return {"status": "kicked_off", "link_id": link_id,
            "to": req.to_agent, "from": req.from_agent}


@app.post("/sessions/{session_id}/interrupt")
async def interrupt_session(session_id: str):
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    session = sessions[session_id]
    if session.driver:
        await session.driver.interrupt()
    return {"status": "interrupted"}


@app.post("/sessions/{session_id}/model")
async def set_model(session_id: str, req: SetModelRequest):
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    session = sessions[session_id]
    if session.driver and session.driver.supports("set_model"):
        await session.driver.set_model(req.model)
    session.model = req.model
    return {"status": "ok", "model": req.model}


def _lever_http_error(e: RuntimeError, lever: str) -> HTTPException:
    """Map a live-control lever failure to an honest HTTP error.

    The bridge driver raises RuntimeError(<reason>) when a mode/fast/thinking
    control could not be applied on the running TUI (§11 #12): "busy" (screen
    not idle — retryable) → 409; anything else — "unreachable" (an un-armed
    Bypass/Auto segment, silently absent from the Shift+Tab ring, §7.11),
    "credit_gated" (Fast without usage credits), "unreadable" (panel/status
    scrape failed) — → 400 with the reason in the detail.
    """
    reason = str(e) or "failed"
    code = 409 if reason == "busy" else 400
    return HTTPException(status_code=code, detail=f"{lever} failed: {reason}")


@app.post("/sessions/{session_id}/mode")
async def set_mode(session_id: str, req: SetModeRequest):
    """Set the permission mode on a live session — with read-back.

    Bridge driver (§11 #12): cycles the proven Shift+Tab ring at a known-idle
    screen and reads the resulting mode back from the status line; the response
    carries that READ-BACK mode, never an echo of the request. An un-armed
    Bypass/Auto segment is silently absent from the ring (§7.11), so the driver
    raises "unreachable" → an honest 400 (arming is a launch-time choice — the
    Create panel's `--permission-mode` pre-arm, §11 #13); a non-idle screen →
    409 "busy". The *initial* mode is still applied at launch via the
    `--permission-mode` flag (see the bridge driver).
    """
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    session = sessions[session_id]
    if not (session.driver and session.driver.supports("set_mode")):
        raise HTTPException(status_code=400, detail="Driver has no mode control")
    try:
        result = await session.driver.set_mode(req.mode)
    except RuntimeError as e:
        raise _lever_http_error(e, "set_mode")
    # The bridge driver returns the read-back mode; the sdk driver returns None
    # (its control API applies the requested mode directly).
    mode = result if isinstance(result, str) else req.mode
    session.permission_mode = mode
    return {"status": "ok", "mode": mode}


class IdentityUpdateRequest(BaseModel):
    """Post-create identity edit (§7.5) — any subset of the five fields; an
    omitted field is left untouched (merge, not replace)."""
    role: str | None = None
    number: int | None = None
    name: str | None = None
    color: str | None = None
    icon: str | None = None


@app.post("/sessions/{session_id}/identity")
async def update_identity(session_id: str, req: IdentityUpdateRequest):
    """Edit a session's dashboard-owned identity (§7.5) — all five fields are
    editable after create.

    Merges any subset of {role, number, name, color, icon} into
    ``session.identity`` and persists the merged identity through the roster
    record (the driver's ``_record`` → ``runtime_store.save_record``), which is
    exactly what ``reconnect_sessions`` reads back (``rec["identity"]``) — so an
    edit survives a sidecar restart. Routing, links, hooks, and the inbox all
    key on the session id, so an edit can't break a reference.

    Two §7.5 specifics: **retired numbers are never reused** (§7.12) — a number
    edit to a retired number is refused with a 400; and the **name doubles as
    the Claude Code session display name** — a changed, non-empty name drives
    ``/rename`` on the live session (capability-gated ``set_display_name``;
    a no-op on drivers without a display-name surface, e.g. the sdk driver).
    Returns the updated identity.
    """
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    session = sessions[session_id]
    patch = {k: v for k, v in req.model_dump().items() if v is not None}
    if "number" in patch and deletion.is_retired(patch["number"]):
        raise HTTPException(
            status_code=400,
            detail=f"identity number {patch['number']} is retired and is never "
                   "reused (§7.12)")
    identity = dict(session.identity or {})
    old_name = identity.get("name") or ""
    identity.update(patch)
    session.identity = identity

    drv = session.driver
    # Keep the driver's config copy in sync — it is what the bridge driver
    # writes into any roster record it persists later.
    if drv is not None and getattr(drv, "config", None) is not None:
        drv.config.identity = identity
    # Persist through the roster record (§8.2) so a restarted sidecar
    # reconnects with the EDITED identity, not the create-time one.
    rec = getattr(drv, "_record", None)
    if isinstance(rec, dict):
        rec["identity"] = identity
        try:
            import runtime_store
            runtime_store.save_record(rec)
        except Exception as e:  # pragma: no cover - persistence is best-effort
            logger.warning("identity persist failed for %s: %s", session_id, e)

    # Name registration (§7.5): a changed, non-empty name renames the live
    # Claude Code session (`/rename` — the launch-time counterpart is the
    # `claude --name` flag the bridge driver passes at create).
    new_name = identity.get("name") or ""
    if "name" in patch and new_name and new_name != old_name \
            and drv is not None and drv.supports("set_display_name"):
        try:
            await drv.set_display_name(new_name)
        except Exception as e:  # pragma: no cover - rename is best-effort
            logger.warning("display-name rename failed for %s: %s", session_id, e)

    return {"status": "ok", "session_id": session_id, "identity": identity}


@app.get("/identity/random-name")
async def identity_random_name(exclude: str | None = None):
    """Draw a random unused name from the shipped 179-name pool (§7.5, §11 #40).

    The Create panel's randomize / auto-name affordance calls this; a user-typed
    name is always allowed instead (the pool is a convenience, not a constraint).
    The draw avoids collisions with names already taken: every LIVE agent's
    identity name, plus any extra names the caller passes as a comma-separated
    ``exclude`` query param (e.g. a name staged in an unsubmitted Create form).
    Returns ``{"name": <str|null>}`` — ``null`` only if the pool is empty.
    """
    taken: set[str] = set()
    if exclude:
        taken |= {n.strip() for n in exclude.split(",") if n.strip()}
    for s in list(sessions.values()):
        nm = (s.identity or {}).get("name") if s.identity else None
        if nm:
            taken.add(nm)
    return {"name": draw_name(exclude=taken)}


# ---- Response-format presets (§7.14, §11 #39) ------------------------------

@app.get("/presets/response")
async def response_preset_catalog():
    """The per-agent reply-format preset menu (§7.14, §11 #39).

    A small catalog of canned response formats (id · label · description),
    including the operator's TL;DR-table + emoji-status house style. The operator
    picks one per agent (Create / Agent panel); the chosen preset's instruction is
    appended to that agent's system prompt at launch so every reply follows the
    format. ``default`` is the no-op (the agent's own natural style)."""
    return {"default": response_presets.DEFAULT_PRESET,
            "presets": response_presets.catalog()}


@app.get("/sessions/{session_id}/response-preset")
async def get_response_preset(session_id: str):
    """The agent's chosen reply-format preset id (§11 #39), or ``None``."""
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    return {"session_id": session_id,
            "response_preset": sessions[session_id].response_preset}


@app.post("/sessions/{session_id}/response-preset")
async def set_response_preset(session_id: str, req: SetResponsePresetRequest):
    """Choose an agent's reply-format preset (§7.14, §11 #39), persisted to
    ``state/agents.json``.

    The choice reaches and persists to the agent: it lands on ``session`` +
    the driver config + the roster record (the same persist path as
    ``update_identity``), so it survives a sidecar restart. Because the preset is
    injected via ``--append-system-prompt`` (a launch flag a running TUI can't be
    re-scoped with), a change here **takes effect at the next launch/restart** —
    exactly like per-agent MCP/model/plugins (§7.15). The create-time choice IS
    applied immediately (the agent launches with it). 400 on an unknown preset id.
    """
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    if not response_presets.is_valid(req.preset):
        raise HTTPException(status_code=400,
                            detail=f"unknown response preset {req.preset!r}")
    session = sessions[session_id]
    session.response_preset = req.preset
    drv = session.driver
    # Keep the driver's config copy in sync (what the bridge driver persists).
    if drv is not None and getattr(drv, "config", None) is not None:
        drv.config.response_preset = req.preset
    # Persist through the roster record (§8.2) so a restart keeps the choice.
    rec = getattr(drv, "_record", None)
    if isinstance(rec, dict):
        rec["response_preset"] = req.preset
        try:
            import runtime_store
            runtime_store.save_record(rec)
        except Exception as e:  # pragma: no cover - persistence is best-effort
            logger.warning("response-preset persist failed for %s: %s", session_id, e)
    return {"status": "ok", "session_id": session_id, "response_preset": req.preset}


@app.post("/sessions/{session_id}/permission")
async def answer_permission(session_id: str, req: AnswerPermissionRequest):
    """Answer a pending tool-permission prompt (approve = Yes, deny = No)."""
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    session = sessions[session_id]
    if not session.driver:
        raise HTTPException(status_code=503, detail="Session not connected yet")
    if session.pending_permission is None:
        raise HTTPException(status_code=409, detail="No pending permission prompt")
    if not session.driver.supports("permission"):
        raise HTTPException(status_code=400, detail="Driver has no permission support")

    await session.driver.answer_permission(req.approve)
    # Clear immediately; the driver's permission_resolved event is also handled
    # when the screen state leaves the prompt, but don't depend on its timing.
    session.pending_permission = None
    session.push_event({
        "type": "permission_resolved", "approve": req.approve,
        "timestamp": datetime.now().isoformat(),
    })
    return {"status": "ok", "approve": req.approve}


# The effort levels Claude Code accepts (the documented EffortValue set — see
# dev/notes/research/research-subagent-architecture.md). The bridge lever is a
# fire-and-forget typed `/effort <level>` with NO read-back surface, so the
# endpoint must supply the honesty the driver can't: validate the value here
# rather than recording an arbitrary string as settings-at-turn truth.
_EFFORT_LEVELS = {"low", "medium", "high", "max"}


@app.post("/sessions/{session_id}/effort")
async def set_effort(session_id: str, req: SetEffortRequest):
    """Set reasoning effort on a live session — validated + idle-gated.

    Unlike the mode/fast/thinking siblings there is no read-back for effort
    (the bridge lever just types `/effort <level>`), so the gates live here:
    an unknown level is a 400 (never sent, never recorded), and a mid-run send
    is a 409 ``busy`` — typed into a generating TUI the command would land as
    queued composer input, not an applied setting, and the §11 #46 per-turn
    settings join would then report a lever the turn never ran with.
    """
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    session = sessions[session_id]
    if not (session.driver and session.driver.supports("set_effort")):
        raise HTTPException(status_code=400, detail="Driver has no effort control")
    if req.effort not in _EFFORT_LEVELS:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown effort level {req.effort!r} — expected one of "
                   f"{sorted(_EFFORT_LEVELS)}")
    if session.status == "running":
        raise HTTPException(status_code=409,
                            detail="set_effort failed: busy — agent is not idle")
    await session.driver.set_effort(req.effort)
    # §11 #46: remember the lever for the per-turn settings join — validated
    # and sent at an idle boundary (best-effort apply; /effort has no
    # read-back surface, so this is the requested-at-idle value, not an echo
    # of the TUI's state).
    session.last_effort = req.effort
    return {"status": "ok", "effort": req.effort}


@app.post("/sessions/{session_id}/fast")
async def set_fast(session_id: str, req: SetFastRequest):
    """Set Fast mode on a live session — with read-back (§11 #12).

    Bridge driver: the `Meta+O` panel + `Space` toggle, state read back off the
    panel's "Fast mode OFF/ON" line. A credit-gated account degrades honestly —
    400 "credit_gated", never a faked toggle; a non-idle screen → 409 "busy".
    """
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    session = sessions[session_id]
    if not (session.driver and session.driver.supports("set_fast")):
        raise HTTPException(status_code=400, detail="Driver has no fast control")
    try:
        result = await session.driver.set_fast(req.on)
    except RuntimeError as e:
        raise _lever_http_error(e, "set_fast")
    return {"status": "ok", "fast": result if isinstance(result, bool) else req.on}


@app.post("/sessions/{session_id}/thinking")
async def set_thinking(session_id: str, req: SetThinkingRequest):
    """Set extended thinking on a live session — with read-back (§11 #12).

    Bridge driver: the `Meta+T` modal — current state read first (the ✔ option),
    toggled only if needed, result read back. Non-idle screen → 409 "busy".
    """
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    session = sessions[session_id]
    if not (session.driver and session.driver.supports("set_thinking")):
        raise HTTPException(status_code=400, detail="Driver has no thinking control")
    try:
        result = await session.driver.set_thinking(req.on)
    except RuntimeError as e:
        raise _lever_http_error(e, "set_thinking")
    applied = result if isinstance(result, bool) else req.on
    # §11 #46: remember the READ-BACK lever state for the per-turn settings join.
    session.last_thinking = applied
    return {"status": "ok", "thinking": applied}


# --- Timeline: Rewind / Fork (§7.19, §11 #15) ------------------------------

def _rewind_fork_http_error(e: RuntimeError, op: str) -> HTTPException:
    """Map a rewind/fork lever failure to an honest HTTP error (§7.19, §11 #15).

    The bridge driver raises RuntimeError(<reason>) when the Timeline op can't
    proceed: "version_unsupported" (Claude Code < 2.1.191 or unresolvable — the
    feature is genuinely unavailable) → 400; "busy" (the screen isn't idle for
    the `/rewind` menu) → 409; anything else (an unexpected bridge failure) → 500
    with the reason. Never a fake success.
    """
    reason = str(e) or "failed"
    if reason == "version_unsupported":
        need = ".".join(str(x) for x in _REWIND_FORK_MIN_VERSION)
        return HTTPException(
            status_code=400,
            detail=f"{op} unavailable: requires Claude Code >= {need}")
    if reason == "busy":
        return HTTPException(status_code=409,
                             detail=f"{op} failed: busy — agent is not idle")
    return HTTPException(status_code=500, detail=f"{op} failed: {reason}")


# Mirrors bridge.bridge.REWIND_FORK_MIN_VERSION for the 400 message (kept here so
# the message renders even when the bridge package isn't importable in a test).
_REWIND_FORK_MIN_VERSION = (2, 1, 191)


@app.post("/sessions/{session_id}/rewind")
async def rewind_session(session_id: str, req: RewindRequest):
    """Rewind an agent's conversation to an earlier prompt checkpoint (§7.19, §11 #15).

    Drives the native `/rewind` menu over tmux (the bridge driver) to restore the
    CONVERSATION in-place — same session id; the agent genuinely loses the later
    turns from its live context. Requires Claude Code >= 2.1.191: a too-old (or
    unresolvable) CLI degrades to an honest 400, never a silent no-op. 409 `busy`
    when the agent's screen isn't idle (a slash command can only land at an idle
    boundary); 400 for drivers without the capability. On success the sidecar
    appends a typed rewind event to the session's Timeline record
    (``_append_rewind_record`` — the transcript is append-only and writes
    nothing at rewind time, so this is the persisted trace the timeline read
    surface replays rolled state from); a failed rewind appends nothing.
    """
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    session = sessions[session_id]
    if not (session.driver and session.driver.supports("rewind")):
        raise HTTPException(status_code=400, detail="Driver has no rewind support")
    try:
        result = await session.driver.rewind(req.to_prompt_index)
    except RuntimeError as e:
        raise _rewind_fork_http_error(e, "rewind")
    await _append_rewind_record(session, req.to_prompt_index)
    # Spread the driver's rewind detail (name, to_prompt_index) but keep the
    # endpoint envelope's status "ok" (the driver's inner "rewound" must not
    # clobber it).
    return {**(result if isinstance(result, dict) else {}), "status": "ok"}


async def _adopt_forked_session(descriptor: dict[str, Any], *,
                                source: "SessionState", identity: dict[str, Any],
                                model: str | None,
                                permission_mode: str) -> "SessionState":
    """Wire an already-spawned fork into a first-class live SessionState (§7.19, §9.2).

    The fork's tmux session already exists (spawned by the source driver's bridge
    via `--fork-session`); this adopts it — exactly like reconnect's warm-restore
    — as a restart-survivable SessionState with its OWN resumed BridgeDriver
    (bound to the fork's tmux name + discovered claude id) and its own dashboard
    identity + #19 git attribution. The reserved lineage fields (§11 #18) record
    the parent/fork provenance. Returns the new live SessionState.

    ⚠ RUNTIME-WIRING SEAM (§11 #15 — flagged, NOT faked): the fork is spawned by
    the raw `--fork-session` launch, so it does NOT yet re-materialize the
    sidecar's PER-AGENT settings (the hook push-channel, the per-turn statusLine
    capture, and the §8.6 transcript-retention pin — see `_build_settings`), which
    are keyed to a sidecar session id that only exists at adoption. The fork IS a
    first-class, tracked, resumable agent (transcript polling + events + restart
    survival all work); wiring its per-agent settings onto the fork launch is the
    open follow-up (it needs the fork's sidecar id minted BEFORE the spawn).
    """
    global _identity_ordinal
    from drivers.bridge import BridgeDriver  # local import (mirrors reconnect)

    new_sid = str(uuid.uuid4())[:8]
    fork_tmux = descriptor["name"]
    cwd = descriptor.get("cwd") or source.cwd
    claude_sid = descriptor.get("session_id")
    # Reserved lineage (§11 #18): the fork's parent + fork provenance, seeded into
    # the persisted record so it survives restart and is available to later
    # archive/graph work (#16/#18 own the archive-on-retire hookup).
    lineage = {
        "parent": source.session_id,
        "fork": {
            "source_session_id": source.session_id,
            "source_claude_session_id": descriptor.get("source_session_id"),
            "rewound_to": descriptor.get("rewound_to"),
        },
        "handoff": None,
    }
    state_store.load_project(cwd)
    state_store.register_agent(new_sid, cwd)
    session = SessionState(
        session_id=new_sid,
        agent_type=source.agent_type,
        model=model,
        permission_mode=permission_mode,
        cwd=cwd,
        system_prompt=source.system_prompt,
        driver_name="bridge",
        allowed_tools=source.allowed_tools,
        disallowed_tools=source.disallowed_tools,
        permission_rules=source.permission_rules,
        enabled_plugins=source.enabled_plugins,
        mcp_servers=source.mcp_servers,
        identity=identity,
        # #44: inherited doc attachment — REAL at the fork spawn (the source
        # driver's fork() passes the docs preamble on the --fork-session
        # launch), so this persisted field and the fork's behavior agree.
        attached_docs=source.attached_docs,
        # §7.11: the fork rides the raw --fork-session spawn, which does not
        # carry the arm flag — its ring is the un-armed base ring, so the
        # honest readback is arm_bypass=False (never inherited-but-untrue).
        arm_bypass=False,
    )
    sessions[new_sid] = session
    config = DriverConfig(
        agent_type=source.agent_type,
        model=model,
        permission_mode=permission_mode,
        cwd=cwd,
        system_prompt=source.system_prompt,
        allowed_tools=source.allowed_tools,
        disallowed_tools=source.disallowed_tools,
        permission_rules=source.permission_rules,
        enabled_plugins=source.enabled_plugins,
        mcp_servers=source.mcp_servers,
        identity=identity,
        attached_docs=source.attached_docs,
        arm_bypass=False,
    )
    driver = BridgeDriver(
        config, session.handle_event,
        resume_name=fork_tmux, session_id=new_sid,
        claude_session_id=claude_sid, cold_restore=False,
        persisted_record={"session_id": new_sid, "lineage": lineage},
    )
    session.driver = driver
    try:
        await driver.start()          # resume() rebinds the alive fork tmux
        session.status = "idle"
        session.listen_task = asyncio.create_task(_listen(session))
    except Exception as e:  # pragma: no cover - environment dependent
        logger.error("fork adopt failed for %s: %s", new_sid, e)
        session.status = "error"
    return session


@app.post("/sessions/{session_id}/fork")
async def fork_session(session_id: str, req: ForkRequest):
    """Fork/Handoff a NEW agent from an existing session (§7.19, §9.2, §11 #15).

    Branches an independent session from the source via `claude --resume <src>
    --fork-session` (the source is never touched), optionally rewinds the fork to
    an earlier prompt for branch-from-N (`to_prompt_index`), applies the per-fork
    file-state policy (its own git worktree, honest fallback to the shared cwd),
    and adopts the fork as a first-class live agent through the standard Create
    wiring (§9.2) — its own dashboard identity + #19 git attribution + reserved
    lineage. Returns the new agent's session dict enriched with the fork lineage
    and the file-state result. Requires Claude Code >= 2.1.191 (400 below that);
    409 `busy` if a rewind-in-fork can't reach idle; 400 for drivers without the
    capability.
    """
    global _identity_ordinal
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    source = sessions[session_id]
    if not (source.driver and source.driver.supports("fork")):
        raise HTTPException(status_code=400, detail="Driver has no fork support")
    # Assign the FORK's own dashboard identity (round-robin + retired-skip +
    # auto-name draw, like create_session) so the branch is a distinct agent,
    # not a clone of the source.
    identity = assign_identity(
        req.identity.model_dump() if req.identity else None, _identity_ordinal,
        taken_names=_live_identity_names())
    _identity_ordinal += 1
    if not (req.identity and req.identity.number is not None):
        if deletion.is_retired(identity["number"]):
            identity["number"] = deletion.next_free_number(identity["number"])
            _identity_ordinal = max(_identity_ordinal, identity["number"])
    # The fork's OWN #19 git attribution (its commits author under its identity).
    git_name, git_email = git_author(identity)
    fork_tmux = f"awl-{uuid.uuid4().hex[:8]}"
    model = req.model or source.model
    try:
        descriptor = await source.driver.fork(
            fork_tmux, cwd=req.cwd, model=model,
            to_prompt_index=req.to_prompt_index, isolate=req.isolate,
            git_author_name=git_name, git_author_email=git_email)
    except RuntimeError as e:
        raise _rewind_fork_http_error(e, "fork")
    forked = await _adopt_forked_session(
        descriptor, source=source, identity=identity,
        model=model, permission_mode=source.permission_mode)
    out = forked.to_dict()
    out["forked_from"] = source.session_id
    out["forked_from_session_id"] = descriptor.get("source_session_id")
    out["rewound_to"] = descriptor.get("rewound_to")
    out["filestate"] = descriptor.get("filestate")
    # §11 #16 — Handoff artifact: layer a generated summary/handoff report on the
    # plain context carry-over. Distilled from the SOURCE's recent transcript and
    # stored as a Library doc under the FORK's project home; the Create payload
    # references it (§9.2). Non-fatal — a fork still succeeds if generation fails
    # (the failure is reported honestly on the payload, never faked).
    if req.handoff:
        try:
            out["handoff"] = await _generate_handoff_artifact(
                source, cwd=forked.cwd, target_session_id=forked.session_id,
                model=req.handoff_model)
        except Exception as e:  # pragma: no cover - live/env dependent
            logger.warning("handoff artifact failed for fork of %s: %s",
                           source.session_id, e)
            out["handoff"] = {"error": str(e)}
    return out


async def _generate_handoff_artifact(source: "SessionState", *, cwd: str | None,
                                     target_session_id: str | None,
                                     model: str | None) -> dict[str, Any]:
    """Distill + persist a handoff report from ``source``'s recent transcript (§11 #16).

    The transcript excerpt is lifted from the source session's already fanned-out
    events (assistant/user text); the utility-LLM pass + Library write live in
    :mod:`handoff`. Returns the artifact dict (filename / path / summary / …)."""
    excerpt = handoff.transcript_text_from_events(source.events)
    return await handoff.generate_and_store_handoff(
        cwd, excerpt,
        source_session_id=source.session_id,
        source_identity=source.identity,
        target_session_id=target_session_id,
        model=model,
    )


@app.post("/sessions/{session_id}/handoff-report")
async def handoff_report_endpoint(session_id: str, req: HandoffReportRequest):
    """Generate a standalone Handoff artifact for a live session (§7.19, §11 #16).

    The dedicated seam (the fork ``handoff`` flag rides the same generator): a
    utility-LLM pass over the agent's recent transcript → a short structured
    report (what was being done / key decisions / current state & pending) →
    persisted as a Library doc (§8.4) under the agent's project ``docs/`` with
    provenance. ``cwd`` overrides where the doc lands; ``target_session_id``
    records who it's for. 404 unknown session; 400 when there's no project home to
    store the doc; 502 when the generation pass fails (honest, never a fake doc)."""
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    session = sessions[session_id]
    cwd = req.cwd or session.cwd
    if not cwd:
        raise HTTPException(status_code=400,
                            detail="Agent has no project home to store the handoff doc")
    try:
        return await _generate_handoff_artifact(
            session, cwd=cwd, target_session_id=req.target_session_id,
            model=req.model)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"handoff report failed: {e}")


@app.get("/sessions/{session_id}/context")
async def get_context_usage(session_id: str):
    """The context readout floor + the per-turn snapshot (§7.18).

    The body stays the JSONL-derived totals (source 3 — the fallback floor).
    Bridge sessions additionally carry ``per_turn`` (§11 #31): the last
    statusLine payload captured at a turn boundary — the freshest per-turn
    number (source 2), incl. its ``context_window`` object. Best-effort:
    ``per_turn: null`` when nothing was captured yet (fresh session, capture
    disabled, torn line). The on-demand deep readout (source 1) is its own
    endpoint: ``GET /sessions/{id}/context/breakdown``.
    """
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    session = sessions[session_id]
    if not session.driver:
        raise HTTPException(status_code=503, detail="Not connected")
    if not session.driver.supports("context"):
        return {}
    try:
        usage = await session.driver.get_context_usage()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    result = dict(usage or {})
    if hasattr(session.driver, "get_statusline_snapshot"):
        try:
            result["per_turn"] = await session.driver.get_statusline_snapshot()
        except Exception:  # pragma: no cover - best-effort by contract
            result["per_turn"] = None
    return result


@app.get("/sessions/{session_id}/timeline")
async def get_timeline_endpoint(session_id: str):
    """The ordered per-turn Timeline list (§7.19, §11 #46).

    One row per completed dashboard-initiated turn: the settings the agent ran
    that turn with (model + mode/effort/thinking — joined at the turn boundary
    from the statusline capture, the run-state arbiter, and the session
    levers — rendered as a ``settings`` string) plus a concise one-line
    ``summary`` (the reply's leading line per the §11 #39 preamble lean;
    first-sentence fallback). Rows come from the per-agent ``turns.jsonl`` for
    drivers that persist it (bridge — survives a sidecar restart) PLUS any
    records still queued on the transient-persist-failure path
    (``_turns_pending`` — so a rewind event whose append hiccuped still rolls
    its rows instead of silently serving un-rolled state), else the
    session's in-memory mirror; ``turn`` is re-minted 1..N in stored order
    over TURN records only, so the index stays monotonic across restarts (the
    session-local count resets, the file does not) and pure-turn files keep
    exactly today's numbering. The interleaved rewind event records (§11 #46
    — appended on each successful dashboard rewind, since the transcript
    itself is append-only and no engine checkpoint id exists) are REPLAYED
    server-side (``timeline.replay_timeline``): each row gains ``rolled``,
    and the response gains ``rolled_ranges`` (merged, ascending) +
    ``rewinds`` — the rolled marking survives a reload instead of living in
    renderer memory. An empty list before the first completed turn — never an
    error. Manual-terminal turns AND manual-terminal rewinds are absent by
    design: the dashboard tracks turns it initiated (the driver's completion
    gate), so the replay mirrors the renderer's k-from-last arithmetic and
    diverges only if manual TUI turns interleave (the pre-existing limit).
    """
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    session = sessions[session_id]
    records: list[dict[str, Any]] | None = None
    pending: list[dict[str, Any]] = []
    drv = session.driver
    if drv is not None and drv.supports("timeline"):
        # Snapshot the not-yet-persisted queue BEFORE the file read: a record
        # whose append transiently failed sits on `_turns_pending` until the
        # next capture drains it, and serving the file WITHOUT it would lie —
        # most critically for a rewind event, whose absence silently un-rolls
        # rows and skews the renderer's k-from-last arithmetic until the queue
        # drains. Snapshot-then-read means a drain racing this GET can only
        # DUPLICATE a snapshot prefix onto the file tail (deduped below),
        # never hide a record from both sides. (A sidecar restart before the
        # drain still loses the queued record — the persist is best-effort by
        # design; this closes the read gap, not that one.)
        pending = list(session._turns_pending)
        try:
            records = await drv.get_timeline()
        except Exception:  # pragma: no cover - fall back to the mirror
            records, pending = None, []  # the mirror already holds the queue
    if records is None:
        records = []
    if pending:
        # Drop the snapshot prefix a concurrent drain already appended to the
        # file — order is preserved end to end, so a drained record can only
        # be a snapshot PREFIX sitting at the file tail.
        for i in range(min(len(pending), len(records)), 0, -1):
            if records[-i:] == pending[:i]:
                pending = pending[i:]
                break
        records = records + pending
    if not records:
        records = list(session.turns)
    replayed = timeline.replay_timeline(records)
    turns = replayed["turns"]
    return {"session_id": session_id, "count": len(turns), "turns": turns,
            "rolled_ranges": replayed["rolled_ranges"],
            "rewinds": replayed["rewinds"]}


@app.get("/sessions/{session_id}/context/breakdown")
async def get_context_breakdown_endpoint(session_id: str):
    """The §7.18 deep context readout (§11 #30) — ON-DEMAND ONLY.

    Runs `/context` on the live TUI via the console path (idle-gated send +
    bounded wait + screen scrape, the spike-proven mechanics) and parses the
    per-category rows; compaction history (count / type / when + token deltas)
    is derived from `compact_boundary` transcript metadata. This is the
    "opening the accordion triggers a direct pull" contract — it is NOT on any
    poll loop, and the JSONL-derived floor stays `GET /sessions/{id}/context`
    (untouched). 409 `busy` when the agent's screen isn't idle (a slash
    command can only land at an idle boundary); 400 for drivers without the
    capability (an honest signal, never a fake readout).
    """
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    session = sessions[session_id]
    if not session.driver:
        raise HTTPException(status_code=503, detail="Not connected")
    if not session.driver.supports("context_breakdown"):
        raise HTTPException(status_code=400,
                            detail="Driver has no context breakdown")
    try:
        result = await session.driver.get_context_breakdown()
    except RuntimeError as e:
        if str(e) == "busy":
            raise HTTPException(status_code=409, detail="busy — agent is not idle")
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    result["fetched_at"] = datetime.now().isoformat()
    return result


@app.get("/sessions/{session_id}/cost")
async def get_cost_endpoint(session_id: str):
    """Per-agent cost — ON-DEMAND ONLY (§7.15, §11 #32).

    Scrapes `/cost` on the live TUI (idle-gated send + ~3s dialog render +
    scrollback parse + Escape — the spike-proven console path) and returns the
    per-session ``Total cost: $X`` figure with its per-model breakdown:
    Claude Code's OWN estimate, and for a bridge agent the session IS that one
    agent. **Endpoint-only, deliberately NOT in `/usage`'s per-agent rows or
    any poll loop** — each read costs a live TUI round-trip, so the frontend
    pulls it lazily (card expand / periodic slow refresh). ``usd: null`` is
    the honest miss (no panel rendered) — never a fabricated figure. 409
    `busy` when the agent's screen isn't idle; 400 for drivers without the
    capability.
    """
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    session = sessions[session_id]
    if not session.driver:
        raise HTTPException(status_code=503, detail="Not connected")
    if not session.driver.supports("cost"):
        raise HTTPException(status_code=400, detail="Driver has no cost readout")
    try:
        result = await session.driver.get_cost()
    except RuntimeError as e:
        if str(e) == "busy":
            raise HTTPException(status_code=409, detail="busy — agent is not idle")
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    result["fetched_at"] = datetime.now().isoformat()
    return result


@app.get("/sessions/{session_id}/subagents")
async def get_subagents(session_id: str):
    """Surface a session's subagents — presence, count, type, running-vs-done,
    and usage — derived from the parent agent's transcript.

    The parent transcript records each subagent spawn (an `Agent`/`Task` tool_use
    carrying type/description/prompt) and its result (carrying the subagent's
    `agentId` and a usage summary); a spawn with no result yet is still running.
    Drivers that can't observe subagents (e.g. the SDK driver) return the empty
    shape rather than erroring.
    """
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    session = sessions[session_id]
    if not session.driver:
        raise HTTPException(status_code=503, detail="Not connected")
    if not session.driver.supports("subagents"):
        return {"count": 0, "subagents": []}
    try:
        result = await session.driver.get_subagents() or {"count": 0, "subagents": []}
        # Relabel subagents to the group+member scheme (A2, no `s` prefix). v1 groups
        # the current flat set as one run (A); full per-run segmentation + the
        # subagent-transcript ingest is the follow-on.
        subs = result.get("subagents") or []
        if subs:
            result["subagents"] = subagents_naming.assign_names([subs])
        # Blend the hook-fed registry over the transcript-derived list (§7.17):
        # SubagentStart/Stop pushes are the authoritative active-vs-quiet
        # signal. The blend (`subagents_naming.blend_live`) matches by engine
        # agent_id (exact/prefix), pairs a RUNNING hook record in order with
        # the id-less running spawn its result hasn't named yet (the fix for
        # the {id: null} double-count), keeps still-running hook-only records
        # with an honest minted id, and drops stopped hook-only leftovers
        # (the engine's internal helper agents — never a transcript row).
        live = runstate.subagents_live(session_id)
        if live:
            result["subagents"] = subagents_naming.blend_live(
                result.get("subagents", []), live)
            result["count"] = len(result["subagents"])
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# Settings registry reads (workspace-level; read-only this run)
# ============================================================================
#
# These surface the REAL MCP / plugin / config state the bridge AGENTS see,
# read from the WSL-side files/CLI via a shared TmuxBridge (the same cat/CLI-
# over-WSL mechanism mcp_sync uses). Reads only — enable/disable toggles and the
# gated global-edit writes are a later run. `?project=<path>` (Windows or WSL)
# scopes the project-level reads; omit it for user/global scope only.

_registry_bridge = None


def _get_registry_bridge():
    """A shared TmuxBridge for read-only WSL registry/config reads."""
    global _registry_bridge
    if _registry_bridge is None:
        import sys as _sys
        from pathlib import Path as _Path
        repo_root = str(_Path(__file__).resolve().parents[1])
        if repo_root not in _sys.path:
            _sys.path.insert(0, repo_root)
        from bridge import TmuxBridge  # type: ignore[import-not-found]
        _registry_bridge = TmuxBridge()
    return _registry_bridge


@app.get("/settings/mcp")
async def settings_mcp(project: str | None = None):
    """MCP server registry by scope (user / project), each with enabled state."""
    from bridge.registry import read_mcp_registry  # type: ignore[import-not-found]
    try:
        return await asyncio.to_thread(read_mcp_registry, _get_registry_bridge(), project)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/settings/plugins")
async def settings_plugins():
    """Installed plugins (authoritative enabled state) + known marketplaces."""
    from bridge.registry import read_plugins  # type: ignore[import-not-found]
    try:
        return await asyncio.to_thread(read_plugins, _get_registry_bridge())
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/settings/config")
async def settings_config(project: str | None = None):
    """Config-tab readouts (model/mode/sandbox/hooks/env/CLAUDE.md/plans/perms),
    global + project scope, each field tagged Live vs New-session."""
    from bridge.registry import read_config  # type: ignore[import-not-found]
    try:
        return await asyncio.to_thread(read_config, _get_registry_bridge(), project)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# Agent identity icons (recolorable game-icon tiles)
# ============================================================================
#
# Serves the existing `assets/icons/agents/*.svg` set so the renderer can draw
# each agent's identity tile. A `?color=#rrggbb` query recolors the icon's
# full-bleed background rect to the agent's color (the white glyph stays a
# knockout) — the recolorable-tile treatment the mockup uses. Read-only; serves
# files the repo already ships (not a data/feature endpoint).

_ICONS_DIR = Path(__file__).resolve().parents[1] / "assets" / "icons" / "agents"
_HEX_RE = re.compile(r"^#[0-9a-fA-F]{6}$")
# The full-bleed background rect every game-icon opens with (default black fill).
_ICON_BG_PATH = '<path d="M0 0h512v512H0z"/>'


@app.get("/assets/agent-icons/{name}")
async def agent_icon(name: str, color: str | None = None):
    safe = name if name.endswith(".svg") else f"{name}.svg"
    if "/" in safe or "\\" in safe or ".." in safe:
        raise HTTPException(status_code=404, detail="Not found")
    path = _ICONS_DIR / safe
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Icon not found")
    svg = path.read_text(encoding="utf-8")
    # Recolor only when a valid hex is given (guards against SVG injection).
    if color and _HEX_RE.match(color):
        svg = svg.replace(
            _ICON_BG_PATH, f'<path d="M0 0h512v512H0z" fill="{color}"/>', 1
        )
    return Response(content=svg, media_type="image/svg+xml",
                    headers={"Cache-Control": "public, max-age=86400"})


@app.get("/assets/agent-icons")
async def list_agent_icons():
    """The full shipped agent-icon set (§11 #56) — every SVG stem in
    ``assets/icons/agents/``, sorted, so the manual icon picker can offer all
    of them (the curated 50 stay the auto-assign pool only); each listed name
    is servable through the recolor route above. Discovered once at sidecar
    import (identity.AG_ICONS, with its single-default degrade on an
    unreadable asset tree) — icons added on disk mid-run appear after a
    restart, not live. Read-only, no auth, cheap (mirrors GET /roles)."""
    return {"icons": AG_ICONS, "count": len(AG_ICONS)}


# ============================================================================
# §10 #1 — Attachments / project assets (Option A materialization)
#
# Registered AFTER /assets/agent-icons/{name} above so the static icon route
# keeps precedence over the {asset_id}/{filename} pattern.
# ============================================================================

class AssetIngestRequest(BaseModel):
    """Ingest ONE attachment into the open project's asset store (§10 #1).

    Exactly one byte source: ``content_base64`` (the upload body — base64
    JSON, the decided upload form; requires ``filename``) or ``source_path``
    (a local file in any spelling the storage layer folds — ``C:\\…``,
    ``/mnt/c/…``, a WSL-internal ``/home/…``, UNC; ``filename`` defaults to
    its basename). ``citation`` is the optional §7.14 anchor:
    ``{"doc": …, "location": …}``."""
    cwd: str
    filename: str | None = None
    content_base64: str | None = None
    source_path: str | None = None
    created_by: str = "user"                 # provenance: who attached it
    session: str | None = None               # provenance: attaching session
    citation: dict[str, Any] | None = None   # optional anchor (doc + location)


@app.post("/library/assets")
async def library_ingest_asset(req: AssetIngestRequest):
    """Copy attachment bytes into ``<project>/.awl-cc-dash/assets/<id>/<name>``
    (§10 #1 ladder leg a — Option A). Atomic (tmp + rename) with a post-write
    hash verify on both write legs; the WSL-native leg engages automatically
    for WSL-internal project roots. Returns the canonical asset record plus
    the two receiver renderings (``agent_path`` — the WSL-readable absolute
    path; ``http_url`` — the renderer's byte-endpoint URL). 400 on a bad
    request (no project cwd, zero/both byte sources, bad base64/filename/
    citation, over-size), 404 for a missing ``source_path``, 500 when the
    write itself fails."""
    if not storage.project_root(req.cwd):
        raise HTTPException(status_code=400, detail="cwd required")
    has_body = req.content_base64 is not None
    has_path = bool(req.source_path)
    if has_body == has_path:
        raise HTTPException(
            status_code=400,
            detail="provide exactly one of content_base64 or source_path")
    try:
        if has_body:
            if not req.filename:
                raise HTTPException(status_code=400,
                                    detail="content_base64 requires filename")
            try:
                data = base64.b64decode(req.content_base64 or "", validate=True)
            except (ValueError, TypeError):
                raise HTTPException(status_code=400,
                                    detail="content_base64 is not valid base64")
            # The write leg may shell into WSL — keep the event loop free.
            record = await asyncio.to_thread(
                attachments.ingest_bytes, req.cwd, req.filename, data,
                created_by=req.created_by, session=req.session,
                citation=req.citation)
        else:
            record = await asyncio.to_thread(
                attachments.ingest_source_path, req.cwd, req.source_path,
                req.filename, created_by=req.created_by, session=req.session,
                citation=req.citation)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except FileNotFoundError:
        raise HTTPException(status_code=404,
                            detail=f"source_path not found: {req.source_path}")
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=f"asset write failed: {e}")
    except OSError as e:
        # Any other filesystem refusal (disk full, permissions, an exotic
        # name the sanitizer didn't foresee) is an honest 500 with the OS
        # detail — never a raw traceback.
        raise HTTPException(status_code=500, detail=f"asset write failed: {e}")
    return {"asset": record,
            "agent_path": attachments.render_wsl_path(req.cwd, record),
            "http_url": attachments.render_http_url(req.cwd, record)}


@app.get("/library/assets")
async def library_list_assets(cwd: str):
    """List the open project's assets with their metadata (§7.16 — the Assets
    surface's data): id · filename · mime · size · created · provenance (+
    rel_path/sha256/citation), each with the two receiver renderings. Loose
    files dropped directly under ``assets/`` list honestly with ``id: null``
    (visible media, not byte-endpoint-addressable)."""
    if not storage.project_root(cwd):
        raise HTTPException(status_code=400, detail="cwd required")

    def _rows() -> list[dict]:
        # One sidecar read + stat per asset — slow 9P/UNC reads on a
        # WSL-internal store, so the whole scan runs off the event loop.
        return [{**rec,
                 "agent_path": attachments.render_wsl_path(cwd, rec),
                 "http_url": attachments.render_http_url(cwd, rec)}
                for rec in attachments.list_assets(cwd)]

    return await asyncio.to_thread(_rows)


@app.delete("/library/assets/{asset_id}")
async def library_delete_asset(asset_id: str, cwd: str):
    """Delete one ingested asset — bytes dir + ``.meta.json`` sidecar (§7.16,
    the Assets preview's Remove; #50 residual). Traversal-safe (plain-segment
    id resolved strictly inside the store's ``assets/`` dir); an unknown /
    unsafe / loose-file id is an honest 404, a failed removal an honest 500.
    400 when ``cwd`` resolves no project store."""
    if not storage.project_root(cwd):
        raise HTTPException(status_code=400, detail="cwd required")
    try:
        # The removal leg may shell into WSL — keep the event loop free.
        removed = await asyncio.to_thread(attachments.delete_asset, cwd, asset_id)
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))
    if not removed:
        raise HTTPException(status_code=404, detail="Asset not found")
    return {"status": "deleted", "asset_id": asset_id}


@app.get("/assets/{asset_id}/{filename}")
async def serve_asset(asset_id: str, filename: str, cwd: str):
    """Stream one asset's bytes from the open project store (§10 #1 ladder
    leg b — the renderer's recommended default render path: localhost HTTP,
    no Electron CSP/UNC-path issues). Content-type comes from the asset's
    stored ``mime`` (guess fallback). Path-traversal-safe: both segments must
    be plain names and the resolved file must live strictly inside the store's
    ``assets/`` dir (``attachments.asset_file_path``) — anything else is a
    plain 404, including the ``.meta.json`` sidecars (metadata is
    ``GET /library/assets``'s job)."""
    def _resolve() -> tuple[Path | None, dict]:
        # resolve() + sidecar read — off the event loop (slow over 9P/UNC).
        p = attachments.asset_file_path(cwd, asset_id, filename)
        rec = (attachments.load_asset_record(cwd, asset_id) or {}) if p else {}
        return p, rec

    path, record = await asyncio.to_thread(_resolve)
    if path is None:
        raise HTTPException(status_code=404, detail="Asset not found")
    media = record.get("mime") if record.get("filename") == filename else None
    return FileResponse(path, media_type=media or attachments.guess_mime(filename))


# ============================================================================
# Usage (token / context aggregate)
# ============================================================================

@app.get("/usage")
async def get_usage():
    """Token/context aggregate for the Usage tab + the footer token pill.

    Per-agent context (tokens/window/percent/work_steps/tool_total) from every
    driver that supports it, plus fleet totals. The window is model-aware now
    (200K default, 1M for 1M-context models). Per-agent COST is deliberately
    NOT in these rows (§11 #32): it is harvestable, but only via a live-TUI
    `/cost` scrape (idle-gated send + dialog render per read — far too heavy
    for this polled aggregate), so it lives on its own ON-DEMAND endpoint,
    `GET /sessions/{id}/cost`, pulled lazily by the frontend. Plan /
    rate-limit windows are intentionally NOT here — the clean source is the
    OAuth credentials + live API, not the transcript (see the run's
    verify-and-report).
    """
    agents = []
    fleet_tokens = 0
    # Snapshot: the per-agent context read below AWAITS mid-iteration, so a
    # concurrent create/retire mutating `sessions` raised "dictionary changed
    # size during iteration" (intermittent 500, live-observed 2026-07-17).
    for sid, session in list(sessions.items()):
        entry: dict[str, Any] = {
            "session_id": sid,
            "model": session.model,
            "status": session.status,
            "tokens": None,
            "window": None,
            "percent": None,
            "work_steps": None,
            "tool_total": None,
        }
        if session.driver and session.driver.supports("context"):
            try:
                usage = await session.driver.get_context_usage()
            except Exception:
                usage = None
            if usage:
                entry.update({
                    "tokens": usage.get("tokens"),
                    "window": usage.get("window"),
                    "percent": usage.get("percent"),
                    "work_steps": usage.get("work_steps"),
                    "tool_total": usage.get("tool_total"),
                    "model": usage.get("model") or session.model,
                })
                fleet_tokens += usage.get("tokens") or 0
        agents.append(entry)

    return {
        "agents": agents,
        "fleet": {
            "agent_count": len(agents),
            "total_tokens": fleet_tokens,
        },
        # The status-footer token pill jumps to Usage; this is its value.
        "token_pill": fleet_tokens,
    }


# ============================================================================
# §11 #28 — Import external Claude context (engine: sidecar/import_context.py)
# ============================================================================

def _import_http_error(e: Exception) -> HTTPException:
    """Map the import engine's typed degrades to honest, plain-language HTTP
    errors (§11 #28's honest-degrade instruction): a missing prerequisite
    (session key / desktop store / extractor tool) or any other extractor
    failure is a 400 the operator can act on, no-title-match is 404, and the
    bounded subprocess timeout is 504 — never a crash, never a hang."""
    if isinstance(e, HTTPException):
        return e  # already-typed (e.g. the deliver-time 409) — pass through
    if isinstance(e, import_context.SessionNotFoundError):
        return HTTPException(status_code=404, detail=str(e))
    if isinstance(e, import_context.ExtractorTimeoutError):
        return HTTPException(status_code=504, detail=str(e))
    if isinstance(e, (import_context.ImportContextError, ValueError)):
        return HTTPException(status_code=400, detail=str(e))
    return HTTPException(status_code=500, detail=f"import failed: {e}")


@app.get("/import/external")
async def list_import_external(source: str):
    """List importable outside Claude sessions by title (§11 #28).

    ``source=web|desktop`` runs the matching extractor's ``--list`` (in a
    worker thread — the web one does network I/O) and returns
    ``{source, sessions: [{source, id, title, updated_at, model}]}``. Honest
    degrades per ``_import_http_error`` (400 missing key/store/tool with a
    plain-language message, 504 on the bounded timeout)."""
    try:
        items = await asyncio.to_thread(import_context.list_external, source)
    except Exception as e:
        raise _import_http_error(e)
    return {"source": source, "sessions": items}


@app.post("/import/external")
async def import_external(req: ImportExternalRequest):
    """Import one outside Claude session by title to ONE destination (§11 #28).

    Destination prerequisites are validated BEFORE the (network-bound) fetch:
    400 on an unknown source/destination, a missing ``target_agent``, or a
    ``library`` request whose ``cwd`` doesn't resolve to an existing project;
    404 when the target agent doesn't exist. The engine call runs in a worker
    thread. For ``destination=agent`` the markdown is enqueued on the target's
    §7.3 prompt queue (``queue`` disposition — an idle agent flushes
    immediately below, a busy one keeps it queued; never dropped) — and
    because the fetch can span up to the extractor timeout, the target's
    liveness is RE-CHECKED at delivery time: a target retired/deleted
    mid-fetch is an honest 409, never an enqueue onto an orphaned session
    reported as queued. ``panel`` returns the markdown; ``library`` writes the
    provenance-stamped doc. Extractor degrades map per ``_import_http_error``."""
    if req.destination not in import_context.DESTINATIONS:
        raise HTTPException(
            status_code=400,
            detail=f"destination must be one of "
                   f"{'|'.join(import_context.DESTINATIONS)}, not {req.destination!r}")
    if req.source not in import_context.SOURCES:
        raise HTTPException(
            status_code=400,
            detail=f"source must be one of {'|'.join(import_context.SOURCES)}, "
                   f"not {req.source!r}")
    session: SessionState | None = None
    if req.destination == "agent":
        if not req.target_agent:
            raise HTTPException(status_code=400,
                                detail="destination 'agent' requires target_agent")
        if req.target_agent not in sessions:
            raise HTTPException(status_code=404, detail="Target agent not found")
        session = sessions[req.target_agent]
    if req.destination == "library":
        # The library prerequisite — a cwd under an existing project — is as
        # pre-checkable as the agent ones: fail the request BEFORE spending an
        # up-to-timeout extractor run on an import that can never land.
        root = storage.project_root(req.cwd)
        if root is None or not root.is_dir():
            raise HTTPException(
                status_code=400,
                detail="destination 'library' requires cwd — an existing "
                       "project folder for the imported doc to land under "
                       "(<project>/.awl-cc-dash/docs/)")

    def _deliver(agent_id: str, text: str) -> dict[str, Any]:
        # The §7.3 conventional entry shape (mirrors /sessions/{id}/send),
        # operator-attributed: the import is the operator handing context over.
        # Liveness re-check first: this runs AFTER the network-length fetch,
        # and the target can be retired/deleted meanwhile (close_session drops
        # it from the roster) — enqueueing onto the orphaned SessionState
        # would report "queued" while silently dropping the import.
        if sessions.get(agent_id) is not session:
            raise HTTPException(
                status_code=409,
                detail="the target agent was closed while the import was "
                       "fetching — nothing was delivered; pick a live agent "
                       "and retry")
        entry = {
            "id": str(uuid.uuid4())[:8],
            "prompt": text,
            "source": "user",
            "recipients": [agent_id],
            "disposition": "queue",
            "enqueued_at": datetime.now().isoformat(),
        }
        return session.enqueue(entry, "queue")  # type: ignore[union-attr]

    try:
        result = await asyncio.to_thread(
            import_context.import_by_title, req.source, req.title,
            req.destination, req.target_agent, req.cwd, deliver=_deliver)
    except Exception as e:
        raise _import_http_error(e)
    if session is not None and sessions.get(req.target_agent) is session:
        # §11 #34: the delivered import is inbound activity — snap the poll
        # cadence even while it sits queued (same rule as /sessions/{id}/send).
        _nudge_driver(req.target_agent)
        # An idle target takes the import now; a busy one keeps it queued (§7.3).
        await _flush_queue(session)
    return result


# ============================================================================
# §11 #47 — Git automation (operator-triggered; rides #19's per-agent identity)
# ============================================================================

class GitActionRequest(BaseModel):
    # Operator-triggered git in the agent's cwd. `message` is required for
    # (and only used by) `commit`.
    action: Literal["status", "diff", "commit"]
    message: str | None = None


def _git_http_error(e: RuntimeError) -> HTTPException:
    """Map the driver's typed git degrades to honest HTTP errors (§11 #47).

    The operator-actionable refusals — a cwd that isn't a git repo, a missing
    commit message, an agent with no cwd, an unknown action — are 400s with a
    plain-language detail; anything else (a WSL/bridge failure) is a 500.
    """
    reason = str(e) or "failed"
    if reason == "not_a_repo":
        return HTTPException(status_code=400,
                             detail="agent cwd is not a git repository")
    if reason == "message_required":
        return HTTPException(status_code=400,
                             detail="commit requires a non-empty message")
    if reason == "no_cwd":
        return HTTPException(status_code=400,
                             detail="agent has no working directory to run git in")
    if reason == "unknown_action":
        return HTTPException(status_code=400,
                             detail="action must be status|diff|commit")
    return HTTPException(status_code=500, detail=f"git failed: {reason}")


@app.post("/sessions/{session_id}/git")
async def session_git(session_id: str, req: GitActionRequest):
    """Run one OPERATOR-TRIGGERED git action in the agent's cwd (§11 #47).

    Semi-automation means the operator pulls the trigger — there is NO
    auto-commit cadence anywhere (the decided lean: operator-triggered first,
    cadence deferred). The command runs non-interactively through the bridge's
    WSL exec path (never keystrokes into the TUI pane), with the agent's #19
    git identity (`identity.git_env`) explicitly injected — the launch-time
    GIT_* env belongs to the claude process and does NOT reach this
    subprocess, so without the injection an operator-triggered commit would
    silently fall off the AI-touched author query.

    `status`/`diff` are read-only and run anytime; `commit` (stage-all +
    commit) stages the WHOLE shared repo, so it is 409-gated on ANY mid-turn
    agent in the same project (one project, many agents — a sibling's
    half-written files would land in the commit just as surely as the
    addressed agent's), and while it runs the project's queued prompts are
    deferred (`_flush_queue`) so no new turn starts under the in-flight
    `add -A`. 404 unknown session; 400 when the driver lacks the `git`
    capability, the cwd is not a git repo, or the commit message is missing.
    A failed git command (e.g. "nothing to commit") is an honest `ok: false`
    result, not an error.
    """
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    session = sessions[session_id]
    if not (session.driver and session.driver.supports("git")):
        raise HTTPException(status_code=400,
                            detail="Driver has no git surface (bridge agents only)")
    if req.action != "commit":
        try:
            return await session.driver.git(req.action, req.message)
        except RuntimeError as e:
            raise _git_http_error(e)
    # --- commit: the busy gate covers the whole project, not one agent ---
    if session.status == "running":
        raise HTTPException(
            status_code=409,
            detail="agent is mid-turn — a commit now would race its file "
                   "writes; retry when idle")
    pkey = storage.project_key(session.cwd)
    if pkey:
        busy = sorted(sid for sid, s in list(sessions.items())
                      if s.status == "running"
                      and storage.project_key(s.cwd) == pkey)
        if busy:
            raise HTTPException(
                status_code=409,
                detail=f"agent(s) mid-turn in this project ({', '.join(busy)}) "
                       f"— `git add -A` spans the shared repo and would race "
                       f"their file writes; retry when the project is idle")
        _git_commits_inflight[pkey] = _git_commits_inflight.get(pkey, 0) + 1
    try:
        return await session.driver.git(req.action, req.message)
    except RuntimeError as e:
        raise _git_http_error(e)
    finally:
        if pkey:
            left = _git_commits_inflight.get(pkey, 1) - 1
            if left <= 0:
                _git_commits_inflight.pop(pkey, None)
            else:  # pragma: no cover - concurrent commits in one project
                _git_commits_inflight[pkey] = left
            # Wake every flush this commit deferred (queued prompts must not
            # sit stranded once the tree is safe again). (Snapshot: this
            # finally runs right after an await — mutation-safe iteration.)
            for s in list(sessions.values()):
                if s.prompt_queue and storage.project_key(s.cwd) == pkey:
                    _schedule_flush(s)


# ============================================================================
# §11 #48 — Change-log watcher (on-demand; engine: sidecar/changelog.py)
# ============================================================================

class ChangelogRefreshRequest(BaseModel):
    # The project to refresh; omitted -> the open project.
    cwd: str | None = None


@app.post("/projects/changelog/refresh")
async def refresh_changelog(req: ChangelogRefreshRequest | None = None):
    """Refresh the project's AI-authored change-log doc (§11 #48 — on-demand v1).

    Enumerates the fleet's commits via the #19 attribution query (`git log
    --author='@agents.awl-cc-dash.invalid'`, run non-interactively in the
    project cwd through the shared registry bridge's WSL exec path) and
    re-renders `<project>/.awl-cc-dash/docs/change-log.md` via the Library
    with provenance (`created_by="changelog-watcher"`). Triggered by the
    operator or the product-shipped `changelog-watcher` agent — no live
    file-watch (deferred by decision). 400 when no project is resolvable
    (pass `cwd` or open a project) or the cwd is not a git repo; 502 when the
    git enumeration itself fails.
    """
    cwd = (req.cwd if req else None) or _open_project
    if not cwd:
        raise HTTPException(
            status_code=400,
            detail="no project to refresh — pass cwd or open a project first")
    root = storage.project_root(cwd)
    if root is None or not root.is_dir():
        raise HTTPException(status_code=400, detail=f"not a directory: {cwd}")
    bridge = _get_registry_bridge()
    # git runs INSIDE WSL, so hand it the in-WSL spelling of the canonical
    # root. Critical for WSL-internal projects (§8.1): `_open_project` is the
    # canonical \\wsl.localhost\<distro>\… UNC key, which win_to_wsl would
    # pass through untranslated — the in-WSL `cd` would fail and every
    # refresh would 502 (review finding). storage.doc_path_wsl owns the
    # translation for all three spellings (UNC → /…, C:\… → /mnt/c/…, POSIX
    # passes through).
    git_cwd = storage.doc_path_wsl(root)

    def _run_git(args: list[str]) -> dict[str, Any]:
        return bridge.git_run(git_cwd, args)

    try:
        return await asyncio.to_thread(changelog.refresh, cwd, _run_git)
    except changelog.NotAGitRepoError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=502,
                            detail=f"changelog refresh failed: {e}")


# ============================================================================
# §11 #49 — System check (one honest aggregation of the existing probes)
# ============================================================================

def _driver_capability_map() -> dict[str, Any]:
    """Each driver's capability set, imported lazily (per the drivers-package
    contract) so an unavailable engine reads as honest detail, never a crash."""
    import importlib
    out: dict[str, Any] = {}
    for name, modpath, clsname in (("bridge", "drivers.bridge", "BridgeDriver"),
                                   ("sdk", "drivers.sdk", "SDKDriver")):
        try:
            mod = importlib.import_module(modpath)
            out[name] = sorted(getattr(mod, clsname).CAPABILITIES)
        except Exception as e:
            out[name] = {"unavailable": str(e)}
    return out


@app.get("/system-check")
async def system_check_endpoint():
    """One honest health JSON over the EXISTING probes (§11 #49).

    Aggregates: sidecar basics (we're answering — version, live sessions,
    open project), tmux/WSL2 liveness (the raising `TmuxBridge.ping` probe
    the §7.2 System-probe loop also rides, then the session-count read —
    `list` alone folds outages into "zero sessions" and cannot honestly
    fail), ttyd presence (the §11 #29 console-attach
    dependency), the account/auth read (§11 #33 split-source, read-only,
    over the well-known creds locations), and driver availability +
    capabilities. Each check is `{status: ok|fail|skipped, detail}`;
    `ok` is true only when nothing FAILED (skipped = "couldn't probe",
    stated, never a quiet pass). The easy-run half is the product-shipped
    `assets/agents/system-check.md` agent, which drives this endpoint.
    """
    checks: dict[str, Any] = {}
    checks["sidecar"] = system_check.ok_result(
        f"answering — v{app.version}; {len(sessions)} live session(s); "
        f"open project: {_open_project or 'none'}")
    try:
        bridge = _get_registry_bridge()
    except Exception as e:
        checks["tmux"] = system_check.fail_result(
            f"bridge unavailable: {e}")
        checks["ttyd"] = system_check.skipped_result(
            "bridge unavailable — cannot probe ttyd")
    else:
        def _tmux_probe():
            # ping() RAISES on a real outage — bridge.list alone can't serve
            # as the probe: it folds every failure into "zero sessions", so a
            # dead WSL would read as a healthy idle one (review finding).
            bridge.ping()
            return bridge.list()
        checks["tmux"] = await asyncio.to_thread(
            system_check.check_tmux, _tmux_probe)
        if checks["tmux"]["status"] == "ok":
            checks["ttyd"] = await asyncio.to_thread(
                system_check.check_ttyd, bridge.resolve_ttyd)
        else:
            checks["ttyd"] = system_check.skipped_result(
                "tmux/WSL unreachable — cannot probe ttyd")
    checks["auth"] = await asyncio.to_thread(
        system_check.check_auth, system_check.default_auth_candidates())
    checks["drivers"] = system_check.check_drivers(
        default_driver_name(), _driver_capability_map())
    return system_check.aggregate(checks)


# ============================================================================
# Entry point
# ============================================================================

if __name__ == "__main__":
    import uvicorn
    # Bind WSL-reachable by default so in-WSL agents' HTTP hooks reach the
    # sidecar over the host gateway IP (127.0.0.1 is NOT reachable from WSL2 — see
    # the hook spike). On a single-user laptop this exposes the dev port on the
    # LAN; override with AWL_SIDECAR_HOST=127.0.0.1 to keep it loopback-only (the
    # hook channel then degrades — injects stay pending — but everything else
    # works).
    host = os.environ.get("AWL_SIDECAR_HOST", "0.0.0.0")
    uvicorn.run(app, host=host, port=7690, log_level="info")
