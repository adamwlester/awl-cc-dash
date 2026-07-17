"""Agent driver interface.

A driver is the thing that actually runs a Claude Code agent for one session and
emits events. The sidecar is written against this interface so it never needs to
know whether the agent is an in-process Claude Agent SDK subprocess (`sdk`) or a
real Claude Code TUI session driven over the tmux bridge (`bridge`).

Contract:
  * `start()`            — bring the agent up; emit a `status_change: idle` event
                           on success; raise on failure.
  * `send(prompt)`       — send a user prompt (the turn's events arrive via `events()`).
  * `events()`           — async generator yielding already-serialized event dicts
                           (each has a top-level `type`; assistant/user events carry a
                           `content` list of typed blocks). Runs until `close()`.
  * `interrupt()`        — best-effort stop of the current turn.
  * `set_model(model)`   — best-effort; update the active model.
  * `set_mode(mode)`     — best-effort; update the permission mode.
  * `set_effort(effort)` — best-effort; update reasoning effort.
  * `set_fast(on)`       — best-effort; toggle fast mode.
  * `set_thinking(on)`   — best-effort; toggle extended thinking.
  * `set_display_name(name)` — best-effort; register the agent's display name
                           with the underlying engine (§7.5 name registration).
  * `answer_permission(approve)` — answer a pending tool-permission prompt.
  * `get_context_usage()`— return context usage (or None if unsupported).
  * `stop()`             — gracefully end the agent's process while KEEPING any
                           persisted record (the §3.4 close-and-stop path; also
                           the retire path's archive-failure degrade). Default
                           is a safe no-op — see the method.
  * `close()`            — tear the agent down and stop `events()`.

Drivers that surface tool-permission prompts emit a `permission_request` event
(carrying the parsed detail) when the agent pauses on one, and a
`permission_resolved` event when it leaves that state by any means. The sidecar
turns those into the session's `pending_permission` flag.

Optional capabilities a driver may not support are advertised via `CAPABILITIES`
so the API layer can answer gracefully instead of erroring.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, AsyncIterator, Callable, Optional


@dataclass
class DriverConfig:
    agent_type: Optional[str] = None
    model: Optional[str] = None
    # bypassPermissions is the product's launch default (2026-07-17 decision):
    # launching in it arms the Bypass ring segment implicitly, so no arm_bypass
    # is needed for a default create. Historical roster/archive read-backs keep
    # their own "acceptEdits" fallback — that reflects what OLD records were
    # launched with, not this default.
    permission_mode: str = "bypassPermissions"
    cwd: Optional[str] = None
    system_prompt: Optional[str] = None
    # Per-agent launch config (applied AT LAUNCH only — a running TUI can't be
    # re-scoped). allowed/disallowed tools -> --allowedTools/--disallowedTools;
    # permission_rules {allow,deny,ask} + enabled_plugins {"id": bool} ->
    # injected via a per-agent --settings file; mcp_servers (a chosen subset, or
    # None to inherit the global registry) -> a per-agent --mcp-config.
    allowed_tools: Optional[list[str]] = None
    disallowed_tools: Optional[list[str]] = None
    permission_rules: Optional[dict[str, list[str]]] = None
    enabled_plugins: Optional[dict[str, bool]] = None
    mcp_servers: Optional[list[str]] = None
    # Arm-without-activate (§7.11, §11 #13): pass
    # `--allow-dangerously-skip-permissions` at launch so the Bypass segment
    # joins the Shift+Tab mode ring WITHOUT being the launch mode. The bridge
    # driver forwards it to TmuxBridge.create; other drivers ignore it.
    arm_bypass: bool = False
    # Dashboard-owned agent identity (role/number/name/color/icon), assigned at
    # create time. Not a launch flag — it rides along so the bridge driver can
    # persist it in the runtime record for restart-survival. Drivers ignore it.
    identity: Optional[dict[str, Any]] = None
    # Per-agent reply-format preset id (§7.14, §11 #39). The bridge driver
    # resolves it to a format instruction and appends it to the agent's system
    # prompt at launch (`--append-system-prompt`); other drivers ignore it.
    response_preset: Optional[str] = None
    # Per-agent attached Library docs (§7.16, §11 #44 — the "light" v1): doc
    # references (store/project paths or bare filenames) chosen at Create. The
    # bridge driver resolves them to WSL-reachable absolute paths and leads the
    # appended system prompt with a short consult-these-docs preamble, COMPOSED
    # with the response-preset instruction (never clobbering it); other drivers
    # ignore it. Automatic relevance retrieval stays out of scope (§10 #6).
    attached_docs: Optional[list[str]] = None


EventCallback = Callable[[dict[str, Any]], None]


class AgentDriver:
    """Base class for session drivers. Subclasses implement the methods below."""

    name: str = "base"
    # Capability flags — subclasses override what they actually support.
    CAPABILITIES: set[str] = set()

    def __init__(self, config: DriverConfig, on_event: EventCallback) -> None:
        self.config = config
        self.on_event = on_event

    def supports(self, capability: str) -> bool:
        return capability in self.CAPABILITIES

    async def start(self) -> None:  # pragma: no cover - interface
        raise NotImplementedError

    async def send(self, prompt: str) -> None:  # pragma: no cover - interface
        raise NotImplementedError

    async def events(self) -> AsyncIterator[dict[str, Any]]:  # pragma: no cover - interface
        raise NotImplementedError
        yield  # pragma: no cover - makes this an async generator

    async def interrupt(self) -> None:
        return None

    async def set_model(self, model: str) -> None:
        return None

    async def set_mode(self, mode: str) -> None:
        return None

    async def set_effort(self, effort: str) -> None:
        return None

    async def set_fast(self, on: bool) -> None:
        return None

    async def set_thinking(self, on: bool) -> None:
        return None

    async def set_display_name(self, name: str) -> None:
        """Register ``name`` as the engine-side session display name (§7.5).

        Capability-gated (``set_display_name``): the default is a no-op for
        drivers with no display-name surface (e.g. the sdk driver)."""
        return None

    async def answer_permission(self, approve: bool) -> None:
        return None

    async def get_context_usage(self) -> Any:
        return None

    async def get_subagents(self) -> Any:
        """Return this agent's subagents (or None if the driver can't observe them)."""
        return None

    async def stop(self) -> None:
        """Gracefully end the agent's process while KEEPING any persisted record.

        The record-keeping counterpart of ``close()`` (whose bridge
        implementation also removes the roster row): the §3.4 close-and-stop
        path, and the retire path's degrade when the archive write fails. The
        base default is a deliberate **no-op — NOT ``close()``**: for a driver
        whose ``close()`` removes persisted records, inheriting a
        record-destroying stop would silently reintroduce exactly the data
        loss this split exists to prevent. Drivers with a real stop/close
        distinction (the bridge driver) override this; callers treat an
        un-overridden stop as "no record-keeping stop exists" and fall back
        to ``close()`` only where that close is known record-safe."""
        return None

    async def close(self) -> None:
        return None
