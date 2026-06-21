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
  * `get_context_usage()`— return context usage (or None if unsupported).
  * `close()`            — tear the agent down and stop `events()`.

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
    permission_mode: str = "acceptEdits"
    cwd: Optional[str] = None
    system_prompt: Optional[str] = None


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

    async def get_context_usage(self) -> Any:
        return None

    async def close(self) -> None:
        return None
