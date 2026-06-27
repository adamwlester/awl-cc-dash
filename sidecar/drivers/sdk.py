"""SDK driver — runs the agent as an in-process Claude Agent SDK subprocess.

This is a backup / limited-use engine reserved for specific non-interactive
tasks — NOT the default (the product is built around the `bridge` driver, the
primary path and the default when no driver is named). Select it explicitly with
`AWL_DRIVER=sdk` or the per-session `driver` field. It preserves the sidecar's
original behavior: a persistent `ClaudeSDKClient` per session, with messages
streamed off `receive_messages()`.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from typing import Any, AsyncIterator

from claude_agent_sdk import ClaudeAgentOptions, ClaudeSDKClient

from serialize import serialize_message, safe_serialize
from .base import AgentDriver, DriverConfig, EventCallback

logger = logging.getLogger("awl-sidecar.sdk")


class SDKDriver(AgentDriver):
    name = "sdk"
    CAPABILITIES = {"set_model", "set_mode", "context", "interrupt"}

    def __init__(self, config: DriverConfig, on_event: EventCallback) -> None:
        super().__init__(config, on_event)
        self._client: ClaudeSDKClient | None = None

    async def start(self) -> None:
        extra: dict[str, str] = {}
        if self.config.agent_type:
            extra["--agent"] = self.config.agent_type

        options = ClaudeAgentOptions(
            permission_mode=self.config.permission_mode,  # type: ignore[arg-type]
            model=self.config.model,
            cwd=self.config.cwd,
            system_prompt=self.config.system_prompt,
            extra_args=extra,
        )
        client = ClaudeSDKClient(options=options)
        await client.connect()
        self._client = client
        self.on_event({
            "type": "status_change", "status": "idle",
            "timestamp": datetime.now().isoformat(),
        })

    async def send(self, prompt: str) -> None:
        if not self._client:
            raise RuntimeError("SDK client not connected")
        await self._client.query(prompt)

    async def events(self) -> AsyncIterator[dict[str, Any]]:
        if not self._client:
            return
        async for message in self._client.receive_messages():
            yield serialize_message(message)

    async def interrupt(self) -> None:
        if self._client:
            self._client.interrupt()

    async def set_model(self, model: str) -> None:
        if self._client:
            await self._client.set_model(model)

    async def set_mode(self, mode: str) -> None:
        if self._client:
            await self._client.set_permission_mode(mode)

    async def get_context_usage(self) -> Any:
        if not self._client:
            return None
        usage = await self._client.get_context_usage()
        return safe_serialize(usage)

    async def close(self) -> None:
        if self._client:
            try:
                await self._client.disconnect()
            except Exception:  # pragma: no cover - best effort
                pass
            self._client = None
