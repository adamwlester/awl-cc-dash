"""
AWL Dashboard — FastAPI Sidecar (v2)
=====================================
Multi-turn sessions via ClaudeSDKClient.
Each session maintains a persistent Claude subprocess.
"""

import asyncio
import json
import logging
import uuid
from datetime import datetime
from typing import Any, Literal

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

from claude_agent_sdk import ClaudeAgentOptions, ClaudeSDKClient

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("awl-sidecar")

app = FastAPI(title="AWL Dashboard Sidecar", version="0.2.0")
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
                 permission_mode: str, cwd: str | None, system_prompt: str | None):
        self.session_id = session_id
        self.agent_type = agent_type
        self.model = model
        self.permission_mode = permission_mode
        self.cwd = cwd
        self.system_prompt = system_prompt
        self.status: Literal["connecting", "idle", "running", "error", "closed"] = "connecting"
        self.created_at = datetime.now().isoformat()
        self.events: list[dict[str, Any]] = []
        self.subscribers: list[asyncio.Queue[dict[str, Any]]] = []
        self.pending_permission: dict[str, Any] | None = None
        self.total_cost_usd: float = 0.0
        self.total_turns: int = 0
        self.client: ClaudeSDKClient | None = None
        self.message_task: asyncio.Task | None = None

    def to_dict(self) -> dict:
        return {
            "session_id": self.session_id,
            "agent_type": self.agent_type,
            "model": self.model,
            "permission_mode": self.permission_mode,
            "status": self.status,
            "created_at": self.created_at,
            "total_cost_usd": round(self.total_cost_usd, 6),
            "total_turns": self.total_turns,
            "event_count": len(self.events),
            "has_pending_permission": self.pending_permission is not None,
        }

    def push_event(self, event: dict[str, Any]):
        self.events.append(event)
        for q in self.subscribers:
            try:
                q.put_nowait(event)
            except asyncio.QueueFull:
                pass  # subscriber too slow, skip

sessions: dict[str, SessionState] = {}

# ============================================================================
# Serialization
# ============================================================================

def serialize_message(message: Any) -> dict[str, Any]:
    """Convert SDK message to JSON-serializable dict with stable type field."""
    result: dict[str, Any] = {"timestamp": datetime.now().isoformat()}
    msg_type = type(message).__name__
    result["sdk_type"] = msg_type

    # Map to frontend event types
    type_map = {
        "AssistantMessage": "assistant",
        "UserMessage": "user",
        "SystemMessage": "system",
        "ResultMessage": "result",
        "StreamEvent": "stream_event",
        "RateLimitEvent": "rate_limit",
    }
    result["type"] = type_map.get(msg_type, msg_type.lower())

    # Serialize all public attributes
    for key, value in getattr(message, '__dict__', {}).items():
        if key.startswith('_'):
            continue
        result[key] = _safe_serialize(value)

    return result


def _safe_serialize(value: Any, depth: int = 0) -> Any:
    if depth > 5:
        return str(value)
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, dict):
        return {k: _safe_serialize(v, depth + 1) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_safe_serialize(v, depth + 1) for v in value]
    if hasattr(value, '__dict__'):
        return {k: _safe_serialize(v, depth + 1) for k, v in value.__dict__.items()
                if not k.startswith('_')}
    try:
        json.dumps(value)
        return value
    except (TypeError, ValueError):
        return str(value)


# ============================================================================
# Session Lifecycle
# ============================================================================

async def start_session(session: SessionState):
    """Connect the ClaudeSDKClient and start listening for messages."""
    extra = {}
    if session.agent_type:
        extra["--agent"] = session.agent_type

    options = ClaudeAgentOptions(
        permission_mode=session.permission_mode,  # type: ignore[arg-type]
        model=session.model,
        cwd=session.cwd,
        system_prompt=session.system_prompt,
        extra_args=extra,
    )

    try:
        client = ClaudeSDKClient(options=options)
        await client.connect()
        session.client = client
        session.status = "idle"
        session.push_event({
            "type": "status_change", "status": "idle",
            "timestamp": datetime.now().isoformat(),
        })
        logger.info(f"Session {session.session_id} connected")

        # Start background message listener
        session.message_task = asyncio.create_task(
            _listen_messages(session)
        )
    except Exception as e:
        logger.error(f"Session {session.session_id} connect failed: {e}")
        session.status = "error"
        session.push_event({
            "type": "error", "error": str(e),
            "timestamp": datetime.now().isoformat(),
        })


async def _listen_messages(session: SessionState):
    """Continuously read messages from the SDK client and push to event stream."""
    if not session.client:
        return
    try:
        async for message in session.client.receive_messages():
            event = serialize_message(message)
            session.push_event(event)

            # Track cost and turns from result messages
            if event.get("type") == "result":
                data = event.get("data", event)
                cost = data.get("total_cost_usd") or event.get("total_cost_usd")
                if cost:
                    session.total_cost_usd = float(cost)
                turns = data.get("num_turns") or event.get("num_turns")
                if turns:
                    session.total_turns = int(turns)
                session.status = "idle"
                session.push_event({
                    "type": "status_change", "status": "idle",
                    "timestamp": datetime.now().isoformat(),
                })

    except asyncio.CancelledError:
        logger.info(f"Session {session.session_id} message listener cancelled")
    except Exception as e:
        logger.error(f"Session {session.session_id} message listener error: {e}")
        session.status = "error"
        session.push_event({
            "type": "error", "error": str(e),
            "timestamp": datetime.now().isoformat(),
        })


# ============================================================================
# Request Models
# ============================================================================

class CreateSessionRequest(BaseModel):
    agent_type: str | None = None
    model: str | None = None
    permission_mode: str = "acceptEdits"
    cwd: str | None = None
    system_prompt: str | None = None

class SendPromptRequest(BaseModel):
    prompt: str

class SetModelRequest(BaseModel):
    model: str

class SetModeRequest(BaseModel):
    mode: Literal["default", "acceptEdits", "plan", "bypassPermissions", "dontAsk"]


# ============================================================================
# Endpoints
# ============================================================================

@app.get("/health")
async def health():
    return {
        "status": "ok",
        "active_sessions": len(sessions),
        "version": "0.2.0",
    }


@app.post("/sessions")
async def create_session(req: CreateSessionRequest):
    session_id = str(uuid.uuid4())[:8]
    session = SessionState(
        session_id=session_id,
        agent_type=req.agent_type,
        model=req.model,
        permission_mode=req.permission_mode,
        cwd=req.cwd,
        system_prompt=req.system_prompt,
    )
    sessions[session_id] = session
    logger.info(f"Created session {session_id}")

    # Start the SDK client and wait for it to connect
    asyncio.create_task(start_session(session))

    # Poll until connected or timeout (15s)
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

    # Cancel listener and disconnect client
    if session.message_task and not session.message_task.done():
        session.message_task.cancel()
    if session.client:
        try:
            await session.client.disconnect()
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
    if not session.client:
        raise HTTPException(status_code=503, detail="Session not connected yet")

    session.status = "running"
    session.push_event({
        "type": "status_change", "status": "running",
        "timestamp": datetime.now().isoformat(),
    })

    # Send the query — receive_messages() will pick up the response
    try:
        await session.client.query(req.prompt)
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
            # Replay history
            for event in list(session.events):
                yield {"event": "message", "data": json.dumps(event)}

            # Stream live
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
    if session.client:
        session.client.interrupt()
    return {"status": "interrupted"}


@app.post("/sessions/{session_id}/model")
async def set_model(session_id: str, req: SetModelRequest):
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    session = sessions[session_id]
    if session.client:
        await session.client.set_model(req.model)
        session.model = req.model
    return {"status": "ok", "model": req.model}


@app.post("/sessions/{session_id}/mode")
async def set_mode(session_id: str, req: SetModeRequest):
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    session = sessions[session_id]
    if session.client:
        await session.client.set_permission_mode(req.mode)
        session.permission_mode = req.mode
    return {"status": "ok", "mode": req.mode}


@app.get("/sessions/{session_id}/context")
async def get_context_usage(session_id: str):
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    session = sessions[session_id]
    if not session.client:
        raise HTTPException(status_code=503, detail="Not connected")
    try:
        usage = await session.client.get_context_usage()
        return _safe_serialize(usage)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# Entry point
# ============================================================================

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=7690, log_level="info")
