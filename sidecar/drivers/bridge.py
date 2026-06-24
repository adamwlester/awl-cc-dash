"""Bridge driver — runs the agent as a real Claude Code TUI session in tmux/WSL2.

Uses the repo-root `bridge` package (TmuxBridge). Unlike the SDK driver there is
no live message stream, so we poll the session's JSONL transcript for new entries
and the screen for status. Transcript `message.content` blocks are already in
Anthropic block format (each carries its own `type`), which is exactly what the
frontend renders, so mapping is a thin transform.

Note: the sidecar runs with its own directory on sys.path (not the repo root), so
we add the repo root here before importing `bridge`. The cleaner long-term fix is
an editable install of the bridge package.
"""

from __future__ import annotations

import asyncio
import logging
import sys
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, AsyncIterator

from .base import AgentDriver, DriverConfig, EventCallback

# Make the repo-root `bridge` package importable from the sidecar.
_REPO_ROOT = str(Path(__file__).resolve().parents[2])
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

logger = logging.getLogger("awl-sidecar.bridge")

_STATE_TO_STATUS = {
    "generating": "running",
    "permission_prompt": "running",
    "idle": "idle",
}

# Claude Code's overall context window. Context % is the latest assistant
# entry's input + cache-read + cache-creation tokens over this window — no
# `/context` call needed (proven in the bridge diagnostic).
CONTEXT_WINDOW = 1_000_000


def derive_context_usage(entries: list[dict]) -> dict:
    """Derive overall context usage and turn count from transcript entries.

    Pure function (no live session) so it can be unit-tested directly.

      * context tokens = ``input_tokens + cache_read_input_tokens +
        cache_creation_input_tokens`` on the LATEST assistant entry's
        ``message.usage`` (this is the cumulative context, not a per-turn delta).
      * turn count = number of ``user`` entries whose ``message.content`` is a
        plain string (real prompts), excluding entries carrying tool_results
        (whose content is a list of blocks).

    Args:
        entries: Parsed JSONL transcript entries (as from ``read_log``).

    Returns:
        dict with ``tokens``, ``window``, ``percent`` (0–100, 2dp), ``turns``.
    """
    tokens = 0
    for entry in reversed(entries):
        if entry.get("type") == "assistant":
            usage = (entry.get("message") or {}).get("usage") or {}
            tokens = (
                (usage.get("input_tokens") or 0)
                + (usage.get("cache_read_input_tokens") or 0)
                + (usage.get("cache_creation_input_tokens") or 0)
            )
            break

    turns = sum(
        1
        for e in entries
        if e.get("type") == "user"
        and isinstance((e.get("message") or {}).get("content"), str)
    )

    percent = round(tokens / CONTEXT_WINDOW * 100, 2) if CONTEXT_WINDOW else 0.0
    return {
        "tokens": tokens,
        "window": CONTEXT_WINDOW,
        "percent": percent,
        "turns": turns,
    }


def _entry_to_event(entry: dict) -> dict | None:
    """Convert a transcript JSONL entry into a frontend event, or None to skip."""
    etype = entry.get("type")
    msg = entry.get("message", {}) or {}
    ts = entry.get("timestamp") or datetime.now().isoformat()
    if etype == "assistant":
        return {
            "type": "assistant",
            "sdk_type": "AssistantMessage",
            "content": msg.get("content", []),
            "model": msg.get("model"),
            "timestamp": ts,
        }
    if etype == "user":
        return {
            "type": "user",
            "sdk_type": "UserMessage",
            "content": msg.get("content", []),
            "timestamp": ts,
        }
    return None


class BridgeDriver(AgentDriver):
    name = "bridge"
    CAPABILITIES = {"interrupt", "context"}

    def __init__(self, config: DriverConfig, on_event: EventCallback) -> None:
        super().__init__(config, on_event)
        from bridge import TmuxBridge  # type: ignore[import-not-found]
        self._bridge = TmuxBridge()
        self._name = f"awl-{uuid.uuid4().hex[:8]}"
        self._seen = 0
        self._closed = False
        self._last_state: str | None = None

    async def start(self) -> None:
        await asyncio.to_thread(
            self._bridge.create, self._name,
            cwd=self.config.cwd, model=self.config.model,
        )
        # Best-effort: wait for the Claude Code TUI to finish loading.
        try:
            await asyncio.to_thread(self._bridge.wait_idle, self._name, 60, 1.0)
        except Exception as e:  # pragma: no cover - environment dependent
            logger.warning("wait_idle failed for %s: %s", self._name, e)
        self.on_event({
            "type": "status_change", "status": "idle",
            "timestamp": datetime.now().isoformat(),
        })

    async def send(self, prompt: str) -> None:
        await asyncio.to_thread(self._bridge.send, self._name, prompt)

    async def events(self) -> AsyncIterator[dict[str, Any]]:
        while not self._closed:
            # 1) New transcript entries -> assistant/user events.
            try:
                entries = await asyncio.to_thread(self._bridge.read_log, self._name)
            except Exception:
                entries = []  # transcript may not exist until the first turn
            if len(entries) > self._seen:
                for entry in entries[self._seen:]:
                    event = _entry_to_event(entry)
                    if event:
                        yield event
                self._seen = len(entries)

            # 2) Screen state -> status_change events.
            try:
                st = await asyncio.to_thread(self._bridge.status, self._name)
                state = st.get("state")
            except Exception:
                state = None
            if state and state != self._last_state:
                self._last_state = state
                mapped = _STATE_TO_STATUS.get(state)
                if mapped:
                    yield {
                        "type": "status_change", "status": mapped,
                        "timestamp": datetime.now().isoformat(),
                    }

            await asyncio.sleep(1.0)

    async def interrupt(self) -> None:
        try:
            await asyncio.to_thread(self._bridge.interrupt, self._name)
        except Exception as e:  # pragma: no cover - best effort
            logger.warning("interrupt failed for %s: %s", self._name, e)

    async def get_context_usage(self) -> Any:
        """Derive overall context usage and turn count from the transcript.

        No `/context` call needed — the math lives in ``derive_context_usage``.
        Returns None if the transcript can't be read yet (e.g. before the first
        turn), so the API serves an empty object rather than erroring.
        """
        try:
            entries = await asyncio.to_thread(self._bridge.read_log, self._name)
        except Exception:
            return None
        return derive_context_usage(entries)

    async def close(self) -> None:
        self._closed = True
        try:
            await asyncio.to_thread(self._bridge.close, self._name)
        except Exception:  # pragma: no cover - best effort
            pass
