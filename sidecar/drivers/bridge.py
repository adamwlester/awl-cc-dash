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
    "idle": "idle",
    # NOTE: "permission_prompt" is deliberately NOT mapped to a status. A paused
    # permission prompt is surfaced as a distinct `permission_request` event (so
    # the session's pending flag flips), not folded into "running".
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


def _save_record(record: dict) -> None:
    """Persist a session record, tolerating either import layout."""
    try:
        from runtime_store import save_record  # sidecar dir on sys.path (runtime)
    except ImportError:  # pragma: no cover - import-path fallback
        from ..runtime_store import save_record  # package import (tests)
    save_record(record)


def _remove_record(session_id: str) -> None:
    try:
        from runtime_store import remove_record
    except ImportError:  # pragma: no cover - import-path fallback
        from ..runtime_store import remove_record
    remove_record(session_id)


class BridgeDriver(AgentDriver):
    name = "bridge"
    # interrupt/context/permission/resume are proven. Of the session-control
    # commands, only model and effort drive a live session cleanly (confirmed via
    # the "Set model to …"/"Set effort level to …" messages); fast/thinking/mode
    # were not wired (see set_* methods for the live findings).
    CAPABILITIES = {
        "interrupt", "context", "permission", "resume",
        "set_model", "set_effort",
    }

    def __init__(
        self,
        config: DriverConfig,
        on_event: EventCallback,
        *,
        resume_name: str | None = None,
        session_id: str | None = None,
    ) -> None:
        super().__init__(config, on_event)
        from bridge import TmuxBridge  # type: ignore[import-not-found]
        self._bridge = TmuxBridge()
        # When resuming, bind to the existing tmux session by name instead of
        # generating a fresh one and creating.
        self._name = resume_name or f"awl-{uuid.uuid4().hex[:8]}"
        self._resuming = resume_name is not None
        self._session_id = session_id
        self._seen = 0
        self._closed = False
        self._last_state: str | None = None

    def bind_session_id(self, session_id: str) -> None:
        """Associate the sidecar session id (used for the runtime record)."""
        self._session_id = session_id

    @property
    def tmux_name(self) -> str:
        return self._name

    async def start(self) -> None:
        if self._resuming:
            # Rebind to the still-alive tmux session; do not recreate.
            await asyncio.to_thread(self._bridge.resume, self._name)
        else:
            await asyncio.to_thread(
                self._bridge.create, self._name,
                cwd=self.config.cwd, model=self.config.model,
            )
        # Best-effort: wait for the Claude Code TUI to finish loading.
        try:
            await asyncio.to_thread(self._bridge.wait_idle, self._name, 60, 1.0)
        except Exception as e:  # pragma: no cover - environment dependent
            logger.warning("wait_idle failed for %s: %s", self._name, e)

        # Persist a minimal record so a restarted sidecar can rebind to this
        # still-alive tmux session.
        if self._session_id:
            try:
                _save_record({
                    "session_id": self._session_id,
                    "tmux_name": self._name,
                    "driver": "bridge",
                    "model": self.config.model,
                    "permission_mode": self.config.permission_mode,
                    "cwd": self.config.cwd,
                })
            except Exception as e:  # pragma: no cover - best effort
                logger.warning("could not persist runtime record: %s", e)

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

            # 2) Screen state -> status_change / permission events.
            try:
                st = await asyncio.to_thread(self._bridge.status, self._name)
                state = st.get("state")
            except Exception:
                st, state = {}, None
            if state and state != self._last_state:
                prev = self._last_state
                self._last_state = state
                if state == "permission_prompt":
                    # Surface as a distinct event carrying the parsed detail so
                    # the session's pending flag flips — never as "running".
                    yield {
                        "type": "permission_request",
                        "data": st.get("permission") or {},
                        "timestamp": datetime.now().isoformat(),
                    }
                else:
                    # Left the prompt by any means (incl. the user answering in
                    # the terminal) — clear stale pending state.
                    if prev == "permission_prompt":
                        yield {
                            "type": "permission_resolved",
                            "timestamp": datetime.now().isoformat(),
                        }
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

    async def answer_permission(self, approve: bool) -> None:
        """Answer a pending tool-permission prompt with the proven keys.

        Approve = Enter (selects the default option 1, "Yes"); deny = Escape
        (yields "User rejected"). Always-allow (option 2) is intentionally NOT
        offered — it was never verified live.
        """
        key = "Enter" if approve else "Escape"
        await asyncio.to_thread(self._bridge.keys, self._name, key)

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

    # --- Session-control commands ---------------------------------------------
    #
    # Findings from live discovery on Claude Code 2.1.187 (see the DEVLOG entry):
    #   * /model <name>  + Enter  → sets directly ("Set model to …"). WIRED.
    #   * /effort <level> + Enter → sets directly ("Set effort level to …"). WIRED.
    #   * /fast          → opens an interactive panel (Tab to toggle, Enter to
    #                      confirm); a reliable toggle-to-target could not be
    #                      confirmed via screen scraping. NOT wired — reported.
    #   * /thinking      → "No commands match" — no such command. NOT wired.
    #   * permission mode → cycles via Shift+Tab only (relative, no absolute
    #                      set); no clean way to jump to a specific mode. NOT wired.
    # Only the two confirmed-clean controls are advertised via CAPABILITIES below.

    async def set_model(self, model: str) -> None:
        # Fully-typed `/model <name>` + Enter sets directly (autocomplete does
        # not intercept a complete command).
        await asyncio.to_thread(self._bridge.send, self._name, f"/model {model}")

    async def set_effort(self, effort: str) -> None:
        await asyncio.to_thread(self._bridge.send, self._name, f"/effort {effort}")

    async def set_mode(self, mode: str) -> None:
        # Permission mode cycles with Shift+Tab in the TUI; there is no reliable
        # absolute-set form. Left a no-op rather than force a fragile cycle.
        return None

    async def set_fast(self, on: bool) -> None:
        # /fast opens an interactive panel; a reliable scrape-driven toggle could
        # not be confirmed. Left a no-op (not advertised) rather than fake it.
        return None

    async def set_thinking(self, on: bool) -> None:
        # No /thinking command exists in this Claude Code build. Left a no-op.
        return None

    async def close(self) -> None:
        self._closed = True
        if self._session_id:
            try:
                _remove_record(self._session_id)
            except Exception:  # pragma: no cover - best effort
                pass
        try:
            await asyncio.to_thread(self._bridge.close, self._name)
        except Exception:  # pragma: no cover - best effort
            pass
