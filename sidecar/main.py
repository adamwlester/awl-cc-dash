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
import json
import logging
import os
import re
import shlex
import uuid
from collections import deque
from datetime import datetime
from pathlib import Path
from typing import Any, Literal

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

from drivers import create_driver, default_driver_name, AgentDriver, DriverConfig
from identity import assign_identity
import eventbus
import hookbus
import links
import inbox
import checklist
import deletion
import library
import templates_store
import storage

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("awl-sidecar")

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

class SessionState:
    def __init__(self, session_id: str, agent_type: str | None, model: str | None,
                 permission_mode: str, cwd: str | None, system_prompt: str | None,
                 driver_name: str | None = None,
                 allowed_tools: list[str] | None = None,
                 disallowed_tools: list[str] | None = None,
                 permission_rules: dict[str, list[str]] | None = None,
                 enabled_plugins: dict[str, bool] | None = None,
                 mcp_servers: list[str] | None = None,
                 identity: dict[str, Any] | None = None):
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
        # Dashboard-owned identity (role/number/name/color/icon), assigned at
        # create and surfaced on to_dict so the UI reads it everywhere.
        self.identity = identity
        self.status: Literal["connecting", "idle", "running", "error", "closed"] = "connecting"
        self.created_at = datetime.now().isoformat()
        self.events: list[dict[str, Any]] = []
        self.subscribers: list[asyncio.Queue[dict[str, Any]]] = []
        # OD-01 dedup set: deterministic ids already emitted, so a transcript
        # re-poll / reconnect replays without duplicates (no-op on a repeat).
        self._emitted_ids: set[str] = set()
        # OD-02 per-agent ORDERED prompt queue (not strict FIFO) + a Hold staging
        # slot. Sends to a busy agent are queued, not 409-dropped, and flushed on
        # the proven generating->idle transition. `held` items are parked (link-
        # only) and never auto-flushed (released manually into the Editor).
        self.prompt_queue: deque[dict[str, Any]] = deque()
        self.held: list[dict[str, Any]] = []
        # OD-04 serialized reply-to: the peer (agent id) whose inbound message this
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
        # OD-10 lifecycle caps (notify-only). Set on Create, editable; the cap
        # poll-loop raises a Warning inbox card on crossing — the run continues.
        self.max_turns: int | None = None
        self.max_context_pct: float | None = None
        self.context_pct: float | None = None   # latest derived context usage %
        # Locally-derived turn count (each generating->idle = one turn), so the
        # OD-10 cap loop works for the bridge driver too (it emits status_change,
        # not the SDK's `result` with num_turns).
        self.turn_count: int = 0
        self._was_running: bool = False
        self.total_cost_usd: float = 0.0
        self.total_turns: int = 0
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
            },
        }

    def push_event(self, event: dict[str, Any]):
        # OD-01/OD-22: stamp the envelope (id/agent_id/seq/ts/source/recipients)
        # at the single fan-out choke point. A re-polled transcript entry (same
        # deterministic id) dedups to a no-op (stamp returns None).
        event = eventbus.stamp(event, agent_id=self.session_id,
                               emitted_ids=self._emitted_ids)
        if event is None:
            return
        self.events.append(event)
        # OD-04: mark where the current turn's output begins so the reply-to
        # engine can lift just this turn's assistant text on the next idle.
        if event.get("type") == "status_change" and event.get("status") == "running":
            self._turn_start_idx = len(self.events)
            self._was_running = True
        for q in self.subscribers:
            try:
                q.put_nowait(event)
            except asyncio.QueueFull:
                pass  # subscriber too slow, skip
        # Mirror into the bounded cross-agent ring + merged subscribers (OD-01).
        eventbus.publish_global(event)

    def enqueue(self, entry: dict[str, Any], disposition: str) -> dict[str, Any]:
        """Place a prompt per its OD-02 disposition (an ordered queue, not FIFO):

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
            # OD-02: the generating->idle transition is the proven flush signal.
            if st == "idle":
                if self._was_running:        # one completed turn (OD-10 cap loop)
                    self.turn_count += 1
                    self._was_running = False
                # OD-04: relay this finished turn back to a linked peer FIRST (uses
                # this turn's output before a queued prompt starts a new turn), then
                # flush the next queued prompt.
                _maybe_relay_reply(self)
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
            # OD-09 Error section: raise a STICKY inbox card (persists until
            # Retry/Dismiss). Best-effort subtype from the message text.
            msg = event.get("error") or event.get("message") or ""
            cls = inbox.classify_error(msg) or {"subtype": "error", "message": str(msg)[:500]}
            inbox.raise_item(self.session_id, "error", cls, sticky=True,
                             dedup_key=f"error:{cls['subtype']}")
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
            # OD-04 reply-to relay, then OD-02 flush of the next queued prompt.
            _maybe_relay_reply(self)
            _schedule_flush(self)

sessions: dict[str, SessionState] = {}


async def _flush_queue(session: "SessionState") -> None:
    """OD-02: send the next queued prompt iff the agent is idle and one is queued.

    Re-entrancy is gated by flipping status to ``running`` *before* the only
    ``await`` (driver.send), so a concurrent flush sees ``running`` and returns —
    strict one-in-flight, no double-send.
    """
    if session.status == "running" or not session.prompt_queue or not session.driver:
        return
    entry = session.prompt_queue.popleft()
    session.status = "running"  # gate re-entry before the await
    session.push_event({
        "type": "status_change", "status": "running",
        "timestamp": datetime.now().isoformat(),
        "source": entry.get("source", "user"),
        "recipients": entry.get("recipients", ["user"]),
    })
    try:
        await session.driver.send(entry["prompt"])
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
    """OD-04 link fire: if this agent just finished answering a linked peer's
    inbound, route THIS turn's output back to that peer over the link (delivered
    by the link's OD-05 trigger), then set the peer's reply-to back to this agent
    — strict one-in-flight alternation, bounded by the OD-07 End-After cap.

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

    # Account the fire (one message, one direction) and check the End-After cap.
    lk.messages += 1
    lk.tokens += max(1, len(text) // 4)  # rough token estimate for the token cap
    capped = lk.over_cap()
    if capped:
        lk.active = False
    else:
        # Set up the peer's reply-to back here so the conversation alternates.
        target.answering_source = session.session_id
        target.answering_link = link_id

    logger.info("link_fire %s -> %s msg=%d exchanges=%d capped=%s trigger=%s",
                session.session_id, src, lk.messages, lk.exchanges, capped, lk.trigger)
    session.push_event({
        "type": "link_fire", "link_id": link_id, "text": text,
        "timestamp": datetime.now().isoformat(),
        "source": session.session_id, "recipients": [src],
        "exchanges": lk.exchanges, "capped": capped,
    })

    trigger = lk.trigger or "queue"
    if trigger == "inject":
        # Mid-run delivery via the OD-02 hook channel.
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
        session.push_event({
            "type": "error", "error": str(e),
            "timestamp": datetime.now().isoformat(),
        })


async def reconnect_sessions():
    """Rebind to bridge sessions that outlived a previous sidecar process.

    Bridge sessions run as real Claude Code TUIs in tmux/WSL2 and survive a
    sidecar restart. On startup we read the runtime records, and for each whose
    tmux session is still alive we rebuild the session state and a resumed driver
    bound to that tmux name, then resume event pumping (the transcript replay
    restores history). Records whose tmux session is gone are pruned.
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
        if tmux_name not in alive:
            logger.info("Pruning dead session record %s (tmux %s gone)", sid, tmux_name)
            runtime_store.remove_record(sid)
            continue
        if sid in sessions:
            continue

        identity = rec.get("identity")
        # Keep the round-robin counter ahead of any restored agent's number so a
        # newly-created agent doesn't reuse a reconnected one's color/number.
        if isinstance(identity, dict) and isinstance(identity.get("number"), int):
            _identity_ordinal = max(_identity_ordinal, identity["number"])
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
        )
        try:
            driver = BridgeDriver(
                config, session.handle_event,
                resume_name=tmux_name, session_id=sid,
                claude_session_id=rec.get("claude_session_id"),
            )
            session.driver = driver
            await driver.start()  # resume() path — rebinds, doesn't recreate
            session.status = "idle"
            session.listen_task = asyncio.create_task(_listen(session))
            logger.info("Reconnected session %s to live tmux session %s", sid, tmux_name)
        except Exception as e:
            logger.error("Reconnect failed for %s: %s", sid, e)
            session.status = "error"


CAP_POLL_INTERVAL = 3.0  # seconds


async def _cap_poll_loop():
    """OD-10 notify-only cap loop: compare each agent's live turns / context-% to
    its stored caps and raise a Warning inbox card on crossing (dedup'd per
    subtype so it fires once). The run is NOT auto-killed — the user chooses
    Continue / Raise cap / Stop. This is the same loop that feeds OD-09's Warning
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
    await reconnect_sessions()
    asyncio.create_task(_cap_poll_loop())


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

class CreateSessionRequest(BaseModel):
    agent_type: str | None = None
    model: str | None = None
    permission_mode: str = "acceptEdits"
    cwd: str | None = None
    system_prompt: str | None = None
    driver: str | None = None  # "sdk" | "bridge"; None -> AWL_DRIVER, else default "bridge"
    # Per-agent launch config (applied at create time only — see DriverConfig).
    allowed_tools: list[str] | None = None
    disallowed_tools: list[str] | None = None
    permission_rules: dict[str, list[str]] | None = None  # {allow,deny,ask}
    enabled_plugins: dict[str, bool] | None = None         # {"id@mkt": bool}
    mcp_servers: list[str] | None = None                   # subset; None = global
    identity: IdentityInput | None = None                  # dashboard-owned id fields
    max_turns: int | None = None                           # OD-10 cap (notify-only)
    max_context_pct: float | None = None                   # OD-10 cap (notify-only)

class SendPromptRequest(BaseModel):
    prompt: str
    # OD-22 addressing (built in now so linking / multi-target sends need no later
    # migration). source = who the prompt is from (default the operator);
    # recipients = typed addressees (user | <agent-id> | scratch), default the
    # target agent. These drive routing + the From/To filter + Sent/Received — not
    # visibility. Full agent-to-agent routing lands with OD-02/linking.
    source: str = "user"
    recipients: list[str] | None = None
    # OD-02 send-timing disposition. `queue` (the polite default) waits for the
    # turn AND the existing queue; `next` jumps ahead at the next idle; `now`
    # interrupts the current run and delivers immediately; `hold` stages for
    # manual release; `inject` = true mid-run delivery via the OD-02 hook channel
    # (spike-proven on the installed build — lands at the next tool boundary
    # without stopping the turn; if the agent is idle it lands on its next run).
    disposition: Literal["now", "next", "queue", "hold", "inject"] = "queue"

class SetModelRequest(BaseModel):
    model: str

class SetModeRequest(BaseModel):
    mode: Literal["default", "acceptEdits", "plan", "bypassPermissions", "dontAsk"]

class AnswerPermissionRequest(BaseModel):
    # approve = Yes (Enter); deny = No (Escape). Always-allow is unsupported
    # (option 2 was never verified live), so the choice is binary.
    approve: bool

class CreateLinkRequest(BaseModel):
    a: str
    b: str
    direction: Literal["a2b", "b2a", "both"] = "both"
    relationship: list[str] = ["direct"]          # subset of {direct, shared}
    shared_content: list[str] = []                # OD-06 content-type filter
    shared_backfill: bool = False
    trigger: Literal["now", "next", "queue", "inject", "hold"] = "queue"  # OD-05
    end_after_exchanges: int | None = 25          # OD-07 default
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
    comments: list[Any] | None = None

class SetEffortRequest(BaseModel):
    effort: str

class SetFastRequest(BaseModel):
    on: bool

class SetThinkingRequest(BaseModel):
    on: bool


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


@app.post("/sessions")
async def create_session(req: CreateSessionRequest):
    global _identity_ordinal
    session_id = str(uuid.uuid4())[:8]
    # Resolve the dashboard-owned identity (round-robin color/icon/number, with
    # any caller-provided overrides), then advance the round-robin counter.
    identity = assign_identity(
        req.identity.model_dump() if req.identity else None, _identity_ordinal
    )
    _identity_ordinal += 1
    session = SessionState(
        session_id=session_id,
        agent_type=req.agent_type,
        model=req.model,
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
    )
    session.max_turns = req.max_turns                  # OD-10 caps
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
    return [s.to_dict() for s in sessions.values()]


@app.get("/sessions/{session_id}")
async def get_session(session_id: str):
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    return sessions[session_id].to_dict()


@app.delete("/sessions/{session_id}")
async def close_session(session_id: str, hard: bool = False):
    """Retire (soft, default) or — with ?hard=true — OD-19 permanent **Delete**:
    a hard wipe of the agent's private footprint (runtime record, tmux session,
    on-disk transcript) while everything SHARED is tombstoned (links → inactive
    tombstones; feed/scratchpad history is kept and attributed). The agent's
    number is retired (never reused). Queue + inbox (operational state) are dropped.
    """
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    session = sessions[session_id]

    if session.listen_task and not session.listen_task.done():
        session.listen_task.cancel()

    if hard:
        # --- OD-19 hard wipe + tombstone ---
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
        # interrupt + close the live tmux session
        if drv is not None:
            try:
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
        # remove the dashboard runtime record
        try:
            import runtime_store
            runtime_store.remove_record(session_id)
        except Exception:
            pass
        # tombstone shared links (inactive, non-functional) + retire the number
        for lid in link_ids:
            lk = links.get_link(lid)
            if lk:
                lk.active = False
        if isinstance(number, int):
            deletion.retire_number(number)
        # drop operational state
        session.prompt_queue.clear()
        session.held.clear()
        for it in inbox.items_for(session_id):
            inbox.resolve_item(session_id, it["id"])
        session.status = "closed"
        del sessions[session_id]
        logger.info("Deleted (hard) session %s (number %s retired)", session_id, number)
        return {"status": "deleted", "session_id": session_id,
                "wiped": plan["wipe"], "tombstoned": plan["tombstone"]}

    # --- soft Retire (default) ---
    if session.driver:
        try:
            await session.driver.close()
        except Exception:
            pass
    session.status = "closed"
    del sessions[session_id]
    logger.info(f"Closed session {session_id}")
    return {"status": "closed", "session_id": session_id}


@app.post("/sessions/{session_id}/send")
async def send_prompt(session_id: str, req: SendPromptRequest):
    """OD-02: enqueue a prompt on the per-agent ordered queue (never 409-drop).

    An idle agent flushes immediately; a busy agent queues per disposition
    (`queue`/`next`), or — for `now` — is interrupted so the resulting idle
    flushes it at the head. `hold` stages for manual release. OD-22: the entry
    carries `source` + `recipients` (default the operator -> this agent)."""
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    session = sessions[session_id]
    if not session.driver:
        raise HTTPException(status_code=503, detail="Session not connected yet")

    # `inject` rides the OD-02 hook channel, not the prompt queue: it's pushed to
    # the agent mid-turn at its next tool boundary (no stop). Queue it on the
    # durable inbox and surface a synthesized feed event (the inject text is not
    # written to the agent's JSONL transcript, so the sidecar owns its visibility).
    if req.disposition == "inject":
        inj = hookbus.enqueue_inject(session_id, req.prompt, kind="inject",
                                     source=req.source)
        session.push_event({
            "type": "inject", "text": req.prompt, "kind": "inject",
            "inject_id": inj["id"],
            "timestamp": datetime.now().isoformat(),
            "source": req.source,
            "recipients": req.recipients if req.recipients is not None else [session_id],
        })
        return {"status": "injected", "session_id": session_id, "inject_id": inj["id"]}

    entry = {
        "id": str(uuid.uuid4())[:8],
        "prompt": req.prompt,
        "source": req.source,
        "recipients": req.recipients if req.recipients is not None else [session_id],
        "disposition": req.disposition,
        "enqueued_at": datetime.now().isoformat(),
    }
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
    """OD-01 merged cross-agent SSE stream — the single feed all panels subscribe
    to, replacing the per-session `/history` poll.

    Replays the bounded ring (optionally from `?since=<seq>` for scroll-backfill)
    then streams live, with **server-side** From/To filtering: `?source=a,b`
    (sender) and `?recipient=user,c` (any addressee). Each event carries the OD-01
    envelope (id/agent_id/seq/ts) + OD-22 source/recipients.
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
# OD-02 hook channel — inbox-drain endpoints (the bridge points each agent's
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


@app.post("/internal/hooks/post-tool-use/{agent}")
async def hook_post_tool_use(agent: str):
    """PostToolUse drain: hand back ALL pending injects (active + passive) as one
    `additionalContext` block so a running agent receives them mid-turn at the
    next tool boundary. Empty -> `{}` (a 2xx no-op).

    ``agent`` is a PATH param (the sidecar session id the bridge baked into the
    hook URL) — claude's http-hook client does not reliably forward a query
    string, so the id rides the path.
    """
    injects = hookbus.drain(agent)
    if injects:
        logger.info("hook drain post-tool-use agent=%s delivered=%d", agent, len(injects))
    _surface_delivered_injects(agent, injects)
    return hookbus.post_tool_use_output(injects)


@app.post("/internal/hooks/stop/{agent}")
async def hook_stop(agent: str):
    """Stop backstop: for the no-tool-call turn, surface only ACTIVE injects via
    `decision:"block"` so a pure-text turn still catches them at turn-end. Passive
    `context` injects are left pending (blocking Stop would force a continuation)."""
    injects = hookbus.drain(agent, kinds={"inject"})
    if injects:
        logger.info("hook drain stop agent=%s delivered=%d", agent, len(injects))
    _surface_delivered_injects(agent, injects)
    return hookbus.stop_output(injects)


# --- OD-09 Plan/Decision detection via the OD-02 PreToolUse hook channel ---
# The agent's ExitPlanMode (Plan) and AskUserQuestion (Decision) tool calls are
# visible to hooks even when the screen isn't. The spike confirmed the hook
# channel works; these raise the typed Inbox card (detect-and-surface). Returning
# `{}` allows the tool to proceed so the agent isn't blocked if no one answers —
# the user answers by attaching. (The richer hold-for-answer round-trip via
# updatedInput is a fast-follow that needs its own live proof.)

def _raise_plandecision(agent: str, body: dict[str, Any], itype: str) -> None:
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


# ============================================================================
# OD-09 inbox — the merged "needs you" surface across all five typed sections.
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
    for sid, s in sessions.items():
        if s.pending_permission:
            grouped.setdefault(sid, []).append({
                "id": f"perm:{sid}", "agent_id": sid, "type": "permission",
                "data": s.pending_permission, "resolved": False,
            })
    return {"inbox": grouped, "fleet_badge": len(grouped)}


@app.post("/inbox/{agent}/{item_id}/resolve")
async def resolve_inbox_item(agent: str, item_id: str, body: dict[str, Any] | None = None):
    ok = inbox.resolve_item(agent, item_id, answer=(body or {}).get("answer"))
    if not ok:
        raise HTTPException(status_code=404, detail="Inbox item not found")
    return {"status": "resolved", "agent": agent, "item_id": item_id}


# ============================================================================
# OD-11 run-strip checklist (done÷total, barber-pole floor)
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
    """OD-11: the agent's self-reported checklist parsed from its transcript
    (done÷total + current item); barber-pole indeterminate when none published."""
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    return checklist.parse_checklist(_assistant_texts(sessions[session_id]))


# ============================================================================
# OD-16 Templates store (dashboard runtime store; reusable / project-agnostic)
# ============================================================================

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
# OD-15 Library — project-scoped read + render + the plan-review side-store
# ============================================================================

@app.get("/library/documents")
async def library_documents(cwd: str, subdir: str | None = None):
    """List the project's markdown Plans/Documents (read-only, project-scoped)."""
    root = storage.project_root(cwd)
    if not root:
        raise HTTPException(status_code=400, detail="cwd required")
    return library.list_markdown(str(root), subdir)


@app.get("/library/document")
async def library_document(path: str):
    try:
        return library.read_document(path)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Document not found")


@app.get("/library/reviews")
async def library_reviews(cwd: str):
    return library.load_reviews_for_cwd(cwd)


@app.post("/library/reviews")
async def library_set_review(req: ReviewRequest):
    return library.set_review_for_cwd(
        req.cwd, req.filename, owner=req.owner, state=req.state,
        verdict=req.verdict, comments=req.comments)


# ============================================================================
# Tier-2 linking (OD-04..08) — link CRUD + the reply-to conversation kickoff.
# The on-idle reply-to relay lives in SessionState.handle_event / _maybe_relay_reply.
# ============================================================================

@app.post("/links")
async def create_link(req: CreateLinkRequest):
    """Create an agent-to-agent link (OD-06 relationship config)."""
    lk = links.add_link(
        a=req.a, b=req.b, direction=req.direction,
        relationship=req.relationship, shared_content=req.shared_content,
        shared_backfill=req.shared_backfill, trigger=req.trigger,
        end_after_exchanges=req.end_after_exchanges,
        end_after_tokens=req.end_after_tokens,
    )
    return lk.to_dict()


@app.get("/links")
async def list_links():
    """All links, plus the OD-08 grouped-by-agent view (each link under both
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
    and record that its reply routes back to `from_agent` (OD-04). The relay then
    alternates automatically until the OD-07 cap."""
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


@app.post("/sessions/{session_id}/mode")
async def set_mode(session_id: str, req: SetModeRequest):
    """Set the permission mode on a live session — honestly.

    The bridge driver cannot set the permission mode on a running TUI (it only
    cycles via Shift+Tab, with no reliable absolute set), so it does NOT advertise
    `set_mode`; this returns a 400 rather than falsely reporting success (matching
    `set_fast` / `set_thinking`). The *initial* mode is applied at launch via the
    `--permission-mode` flag (see the bridge driver). Mid-run mode change is under
    separate research and intentionally not attempted here.
    """
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    session = sessions[session_id]
    if not (session.driver and session.driver.supports("set_mode")):
        raise HTTPException(status_code=400, detail="Driver has no mode control")
    await session.driver.set_mode(req.mode)
    session.permission_mode = req.mode
    return {"status": "ok", "mode": req.mode}


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


@app.post("/sessions/{session_id}/effort")
async def set_effort(session_id: str, req: SetEffortRequest):
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    session = sessions[session_id]
    if not (session.driver and session.driver.supports("set_effort")):
        raise HTTPException(status_code=400, detail="Driver has no effort control")
    await session.driver.set_effort(req.effort)
    return {"status": "ok", "effort": req.effort}


@app.post("/sessions/{session_id}/fast")
async def set_fast(session_id: str, req: SetFastRequest):
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    session = sessions[session_id]
    if not (session.driver and session.driver.supports("set_fast")):
        raise HTTPException(status_code=400, detail="Driver has no fast control")
    await session.driver.set_fast(req.on)
    return {"status": "ok", "fast": req.on}


@app.post("/sessions/{session_id}/thinking")
async def set_thinking(session_id: str, req: SetThinkingRequest):
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    session = sessions[session_id]
    if not (session.driver and session.driver.supports("set_thinking")):
        raise HTTPException(status_code=400, detail="Driver has no thinking control")
    await session.driver.set_thinking(req.on)
    return {"status": "ok", "thinking": req.on}


@app.get("/sessions/{session_id}/context")
async def get_context_usage(session_id: str):
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    session = sessions[session_id]
    if not session.driver:
        raise HTTPException(status_code=503, detail="Not connected")
    if not session.driver.supports("context"):
        return {}
    try:
        usage = await session.driver.get_context_usage()
        return usage or {}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


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
        result = await session.driver.get_subagents()
        return result or {"count": 0, "subagents": []}
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


# ============================================================================
# Usage (token / context aggregate)
# ============================================================================

@app.get("/usage")
async def get_usage():
    """Token/context aggregate for the Usage tab + the footer token pill.

    Per-agent context (tokens/window/percent/work_steps/tool_total) from every
    driver that supports it, plus fleet totals. The window is model-aware now
    (200K default, 1M for 1M-context models). Per-agent cost stays out of scope
    (the bridge emits none). Plan / rate-limit windows are intentionally NOT here
    — the clean source is the OAuth credentials + live API, not the transcript
    (see the run's verify-and-report).
    """
    agents = []
    fleet_tokens = 0
    for sid, session in sessions.items():
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
# Entry point
# ============================================================================

if __name__ == "__main__":
    import uvicorn
    # OD-02: bind WSL-reachable by default so in-WSL agents' HTTP hooks reach the
    # sidecar over the host gateway IP (127.0.0.1 is NOT reachable from WSL2 — see
    # the hook spike). On a single-user laptop this exposes the dev port on the
    # LAN; override with AWL_SIDECAR_HOST=127.0.0.1 to keep it loopback-only (the
    # hook channel then degrades — injects stay pending — but everything else
    # works).
    host = os.environ.get("AWL_SIDECAR_HOST", "0.0.0.0")
    uvicorn.run(app, host=host, port=7690, log_level="info")
