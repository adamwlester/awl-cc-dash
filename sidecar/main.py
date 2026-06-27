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
import re
import uuid
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
        self.pending_permission: dict[str, Any] | None = None
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
        self.events.append(event)
        for q in self.subscribers:
            try:
                q.put_nowait(event)
            except asyncio.QueueFull:
                pass  # subscriber too slow, skip

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

sessions: dict[str, SessionState] = {}

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


@app.on_event("startup")
async def _on_startup():
    await reconnect_sessions()


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

class SendPromptRequest(BaseModel):
    prompt: str

class SetModelRequest(BaseModel):
    model: str

class SetModeRequest(BaseModel):
    mode: Literal["default", "acceptEdits", "plan", "bypassPermissions", "dontAsk"]

class AnswerPermissionRequest(BaseModel):
    # approve = Yes (Enter); deny = No (Escape). Always-allow is unsupported
    # (option 2 was never verified live), so the choice is binary.
    approve: bool

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
async def close_session(session_id: str):
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    session = sessions[session_id]

    if session.listen_task and not session.listen_task.done():
        session.listen_task.cancel()
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
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    session = sessions[session_id]
    if session.status == "running":
        raise HTTPException(status_code=409, detail="Session is busy")
    if not session.driver:
        raise HTTPException(status_code=503, detail="Session not connected yet")

    session.status = "running"
    session.push_event({
        "type": "status_change", "status": "running",
        "timestamp": datetime.now().isoformat(),
    })

    try:
        await session.driver.send(req.prompt)
    except Exception as e:
        session.status = "error"
        session.push_event({
            "type": "error", "error": str(e),
            "timestamp": datetime.now().isoformat(),
        })
        raise HTTPException(status_code=500, detail=str(e))

    return {"status": "sent", "session_id": session_id}


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
    uvicorn.run(app, host="127.0.0.1", port=7690, log_level="info")
