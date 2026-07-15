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
import state_store
import scratchpad
import watermark
import runstate
import marquee
import console_catalog
import settings_io
import utility_llm
import subagents_naming

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
                    self._was_running = False
                    _raise_response_card(self)
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


async def _flush_queue(session: "SessionState") -> None:
    """Send the next queued prompt iff the agent is idle and one is queued.

    Re-entrancy is gated by flipping status to ``running`` *before* the only
    ``await`` (driver.send), so a concurrent flush sees ``running`` and returns —
    strict one-in-flight, no double-send.

    Piggyback (§7.6): any payloads parked for this agent ride THIS delivery —
    they never initiate a turn of their own. The parked block is prepended to
    the prompt (one bounded block; parking was already watermark-deduped per
    source→target at fire time, so nothing delivers twice).
    """
    if session.status == "running" or not session.prompt_queue or not session.driver:
        return
    entry = session.prompt_queue.popleft()
    prompt = entry["prompt"]
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
    the WSL2/tmux backbone answers (one `tmux ls` through the shared registry
    bridge). A failure raises the coalesced System `infra` Error card; recovery
    auto-resolves it. (Sidecar-down needs no probe — a dead sidecar can't raise
    cards; the frontend's /health failure covers it, §4.3/#38.)"""
    while True:
        try:
            await asyncio.sleep(SYSTEM_PROBE_INTERVAL)
            try:
                bridge = _get_registry_bridge()
                await asyncio.to_thread(bridge.list)
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


async def reconnect_sessions(project_key: str | None = None):
    """Restore bridge sessions that outlived a previous sidecar process (§9.9).

    With ``project_key`` set, only that project's records restore (the §9.1
    open flow); without it, every persisted record restores (startup).

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
    state_store.install_hooks()   # write-through persistence (§8.3)
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
    # First session for a project loads its persisted state/ (lazy, §11 #3) and
    # registers the agent→project mapping the write-through hooks route by.
    state_store.load_project(req.cwd)
    state_store.register_agent(session_id, req.cwd)
    # Resolve the dashboard-owned identity (round-robin color/icon/number, with
    # any caller-provided overrides), then advance the round-robin counter.
    identity = assign_identity(
        req.identity.model_dump() if req.identity else None, _identity_ordinal
    )
    _identity_ordinal += 1
    # Retired numbers are NEVER reused (§7.12): an auto-assigned number that was
    # retired skips forward to the next free one (explicit requests pass through).
    if not (req.identity and req.identity.number is not None):
        if deletion.is_retired(identity["number"]):
            identity["number"] = deletion.next_free_number(identity["number"])
            _identity_ordinal = max(_identity_ordinal, identity["number"])
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
    return [s.to_dict() for s in sessions.values()]


@app.get("/sessions/{session_id}")
async def get_session(session_id: str):
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    return sessions[session_id].to_dict()


@app.delete("/sessions/{session_id}")
async def close_session(session_id: str, hard: bool = False):
    """Retire (soft, default) or — with ?hard=true — permanent **Delete**:
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
    """Enqueue a prompt on the per-agent ordered queue (never 409-drop).

    An idle agent flushes immediately; a busy agent queues per disposition
    (`queue`/`next`), or — for `now` — is interrupted so the resulting idle
    flushes it at the head. `hold` stages for manual release. The entry
    carries `source` + `recipients` (default the operator -> this agent)."""
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    session = sessions[session_id]
    if not session.driver:
        raise HTTPException(status_code=503, detail="Session not connected yet")

    # `inject` rides the hook channel, not the prompt queue: it's pushed to
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
    runstate.ingest(agent, str(event), body)
    return {}


@app.post("/internal/hooks/subagent/{agent}")
async def hook_subagent(agent: str, body: dict[str, Any] | None = None):
    """SubagentStart/SubagentStop → the subagent registry (§7.17): agent_id /
    agent_type / transcript_path become the roster's authoritative
    active-vs-quiet signal, blended over the transcript-derived list."""
    event = (body or {}).get("hook_event_name") or \
            (body or {}).get("hookEventName") or "SubagentStart"
    runstate.ingest_subagent(agent, str(event), body)
    return {}


# --- Plan/Decision detection via the PreToolUse hook channel ---
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
    (name, path, last-opened, agent count) plus which project is open (if any)."""
    entries = [_project_entry(key, meta)
               for key, meta in state_store.known_projects().items()]
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
    state_store.touch_projects_index(key)
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
    await reconnect_sessions(project_key=key)
    _open_project = key
    state_store.touch_projects_index(key)
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
    ``<root>/<subdir>`` when the store dir doesn't exist yet. No ``subdir``
    keeps listing the project root itself — the browse-read-only surface
    (other ``subdir`` values likewise browse ``<root>/<subdir>`` read-only)."""
    root = storage.project_root(cwd)
    if not root:
        raise HTTPException(status_code=400, detail="cwd required")
    if subdir in ("plans", "docs"):
        store_dir = storage.plans_dir(cwd) if subdir == "plans" else storage.docs_dir(cwd)
        if store_dir is not None and store_dir.is_dir():
            return library.list_markdown(str(store_dir))
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
    then aggregates every sidecar under the store's ``plans/`` + ``docs/``."""
    if not storage.project_root(cwd):
        raise HTTPException(status_code=400, detail="cwd required")
    library.migrate_plan_reviews(cwd)
    return library.aggregate_metas(cwd)


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
    for s in sessions.values():
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


@app.post("/sessions/{session_id}/console/run")
async def console_run(session_id: str, req: ConsoleRunRequest):
    """Route a slash-command to the focused agent over the bridge (send/keys), then
    read the screen back. Interactive commands (e.g. /model, /clear) drop the agent
    into a sub-prompt — flagged so the caller drives the follow-on rather than
    blind-sending."""
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    session = sessions[session_id]
    drv = session.driver
    if drv is None or not hasattr(drv, "_bridge") or not hasattr(drv, "tmux_name"):
        raise HTTPException(status_code=400, detail="Console requires a bridge agent")
    interactive = console_catalog.is_interactive(req.command.split()[0] if req.command else "")
    try:
        drv._bridge.send(drv.tmux_name, req.command)          # type: ignore[attr-defined]
        await asyncio.sleep(1.0)
        screen = drv._bridge.read(drv.tmux_name, lines=40)["content"]  # type: ignore[attr-defined]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"console run failed: {e}")
    return {"command": req.command, "interactive": interactive, "screen": screen}


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
async def settings_account(creds_path: str):
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
    text: str
    scope: Literal["grammar", "language", "refactor"] = "grammar"
    model: str | None = None

class SummarizeRequest(BaseModel):
    text: str
    model: str | None = None


@app.post("/utility/revise")
async def utility_revise(req: ReviseRequest):
    try:
        return {"scope": req.scope, "result": await utility_llm.revise(req.text, req.scope, req.model)}
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"revise pass failed: {e}")


@app.post("/utility/summarize")
async def utility_summarize(req: SummarizeRequest):
    try:
        return {"result": await utility_llm.summarize(req.text, req.model)}
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"summarize pass failed: {e}")


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
    alternates automatically until the End-After cap."""
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
    return {"status": "ok",
            "thinking": result if isinstance(result, bool) else req.on}


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
        result = await session.driver.get_subagents() or {"count": 0, "subagents": []}
        # Relabel subagents to the group+member scheme (A2, no `s` prefix). v1 groups
        # the current flat set as one run (A); full per-run segmentation + the
        # subagent-transcript ingest is the follow-on.
        subs = result.get("subagents") or []
        if subs:
            result["subagents"] = subagents_naming.assign_names([subs])
        # Blend the hook-fed registry over the transcript-derived list (§7.17):
        # SubagentStart/Stop pushes are the authoritative active-vs-quiet signal
        # — matched by the subagent's engine agent_id; unmatched hook records
        # (start seen before the transcript catches up) are appended.
        live = runstate.subagents_live(session_id)
        if live:
            by_id = {s.get("agent_id"): s for s in result.get("subagents", [])
                     if s.get("agent_id")}
            extra = []
            for rec in live:
                target = by_id.get(rec["agent_id"])
                if target is not None:
                    target["live_status"] = rec["status"]
                    target["transcript_path"] = rec.get("transcript_path")
                    if rec.get("type") and not target.get("type"):
                        target["type"] = rec["type"]
                else:
                    extra.append({
                        "id": None, "tool_use_id": None,
                        "agent_id": rec["agent_id"], "type": rec.get("type"),
                        "description": None, "prompt": None,
                        "status": "running" if rec["status"] == "running" else "done",
                        "live_status": rec["status"],
                        "transcript_path": rec.get("transcript_path"),
                        "usage": None,
                    })
            if extra:
                result["subagents"] = list(result.get("subagents", [])) + extra
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
    # Bind WSL-reachable by default so in-WSL agents' HTTP hooks reach the
    # sidecar over the host gateway IP (127.0.0.1 is NOT reachable from WSL2 — see
    # the hook spike). On a single-user laptop this exposes the dev port on the
    # LAN; override with AWL_SIDECAR_HOST=127.0.0.1 to keep it loopback-only (the
    # hook channel then degrades — injects stay pending — but everything else
    # works).
    host = os.environ.get("AWL_SIDECAR_HOST", "0.0.0.0")
    uvicorn.run(app, host=host, port=7690, log_level="info")
