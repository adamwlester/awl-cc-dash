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
import re
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

# Context % is the latest assistant entry's input + cache-read + cache-creation
# tokens over the model's context window — no `/context` call needed (proven in
# the bridge diagnostic). The window is MODEL-DEPENDENT: 200K for most models,
# 1M only for the 1M-context variants (recon's confirmed mapping). The
# authoritative source is the statusline payload's `context_window_size`
# (see the Usage research); this transcript-side heuristic keys off the model id.
DEFAULT_CONTEXT_WINDOW = 200_000
CONTEXT_WINDOW_1M = 1_000_000
# Model ids known to carry a 1M-token context window beyond the `1m` name marker.
_KNOWN_1M_MODELS: frozenset[str] = frozenset()


def context_window_for_model(model: str | None) -> int:
    """Context-window size (tokens) for a model id.

    1M for 1M-context variants (model id contains ``1m`` or is in
    ``_KNOWN_1M_MODELS``); 200K for everything else. Falls back to the 200K
    default for an unknown/missing model.
    """
    if not model:
        return DEFAULT_CONTEXT_WINDOW
    m = model.lower()
    if "1m" in m or m in _KNOWN_1M_MODELS:
        return CONTEXT_WINDOW_1M
    return DEFAULT_CONTEXT_WINDOW

# Tool-name → by-tool category for the Turns breakdown the Agent panel shows
# (design: Read/search · Edit · Bash · MCP · Subagent · Web). The native tool
# set is fixed; any MCP tool is prefixed ``mcp__``; anything unmatched (TodoWrite,
# ExitPlanMode, …) falls to "other" so the buckets always sum to tool_total.
# (The design's "Coordinating" slice is a dashboard-synthesized cross-agent
# concept the bridge can't know from one transcript, so it is NOT derived here.)
_TOOL_CATEGORY = {
    "Read": "read", "Glob": "read", "Grep": "read", "LS": "read",
    "NotebookRead": "read",
    "Edit": "edit", "Write": "edit", "MultiEdit": "edit", "NotebookEdit": "edit",
    "Bash": "bash", "BashOutput": "bash", "KillBash": "bash", "KillShell": "bash",
    # Subagent spawn tool: this Claude Code build names it "Agent" (live-verified
    # — it writes the subagent's full transcript to <parent-uuid>/subagents/
    # agent-<id>.jsonl and returns a tool_result with the subagent's usage); the
    # Agent SDK / older builds name it "Task". Both count as one subagent step.
    "Agent": "subagent", "Task": "subagent",
    "WebFetch": "web", "WebSearch": "web",
}
_TOOL_BUCKETS = ("read", "edit", "bash", "mcp", "subagent", "web", "other")


def classify_tool(name: str | None) -> str:
    """Map a Claude Code tool-use name to a Turns-breakdown category.

    Any ``mcp__*`` tool is "mcp"; the native set maps via ``_TOOL_CATEGORY``;
    everything else (including a missing name) is "other".
    """
    if not name:
        return "other"
    if name.startswith("mcp__"):
        return "mcp"
    return _TOOL_CATEGORY.get(name, "other")


def derive_context_usage(entries: list[dict]) -> dict:
    """Derive context usage, work-step count, and tool breakdown from a transcript.

    Pure function (no live session) so it can be unit-tested directly. Subagent
    (``isSidechain``) entries are excluded from every count — they are the
    subagent's own turns/tools, not the parent agent's (the parent's single
    ``Task`` tool_use, which lives on the main line, is what counts as one
    "subagent" step for the parent).

      * context tokens = ``input_tokens + cache_read_input_tokens +
        cache_creation_input_tokens`` on the LATEST main-line assistant entry's
        ``message.usage`` (cumulative context, not a per-turn delta).
      * ``work_steps`` = number of distinct main-line assistant inferences
        (distinct ``message.id``; a streamed response split across several JSONL
        lines shares one id, so it counts once). This is the agentic work-step
        unit the ``--max-turns`` / Lifecycle auto-stop cap actually limits — the
        Turns bar's numerator.
      * ``tools`` = by-tool-category counts of every main-line ``tool_use`` block
        (the Agent panel's by-tool Turns breakdown).
      * ``turns`` = legacy prompt-round count: ``user`` entries whose content is a
        plain string. Kept for backward-compatibility, but it is a *prompt-round*
        count (and is polluted by slash-command/meta string entries), NOT the
        work-step unit — prefer ``work_steps``.

    Args:
        entries: Parsed JSONL transcript entries (as from ``read_log``).

    Returns:
        dict with ``tokens``, ``window``, ``percent`` (0–100, 2dp), ``turns``
        (legacy prompt rounds), ``work_steps``, ``tools`` (per-category counts),
        and ``tool_total``.
    """
    tokens = 0
    model = None
    for entry in reversed(entries):
        if entry.get("type") == "assistant" and not entry.get("isSidechain"):
            msg = entry.get("message") or {}
            usage = msg.get("usage") or {}
            tokens = (
                (usage.get("input_tokens") or 0)
                + (usage.get("cache_read_input_tokens") or 0)
                + (usage.get("cache_creation_input_tokens") or 0)
            )
            model = msg.get("model")
            break

    turns = sum(
        1
        for e in entries
        if e.get("type") == "user"
        and isinstance((e.get("message") or {}).get("content"), str)
    )

    # Work steps = distinct main-line assistant inferences; tool breakdown =
    # every main-line tool_use block bucketed by category. One pass over the
    # transcript, skipping subagent sidechains.
    seen_ids: set = set()
    work_steps = 0
    tools = {bucket: 0 for bucket in _TOOL_BUCKETS}
    for e in entries:
        if e.get("type") != "assistant" or e.get("isSidechain"):
            continue
        msg = e.get("message") or {}
        # Entries without a message.id (rare) each count as their own step.
        key = msg.get("id") or f"__noid_{id(e)}"
        if key not in seen_ids:
            seen_ids.add(key)
            work_steps += 1
        for block in msg.get("content") or []:
            if isinstance(block, dict) and block.get("type") == "tool_use":
                tools[classify_tool(block.get("name"))] += 1
    tool_total = sum(tools.values())

    window = context_window_for_model(model)
    percent = round(tokens / window * 100, 2) if window else 0.0
    return {
        "tokens": tokens,
        "window": window,
        "model": model,
        "percent": percent,
        "turns": turns,
        "work_steps": work_steps,
        "tools": tools,
        "tool_total": tool_total,
    }


# Subagent spawn tools: this Claude Code build names the tool "Agent"; the Agent
# SDK / older builds name it "Task". Both spawn one subagent.
_SUBAGENT_TOOLS = ("Agent", "Task")

# Result statuses that mean the subagent did NOT finish cleanly. Anything else
# (notably "completed") with a present result reads as done; absence of a result
# reads as still running.
_BAD_SUBAGENT_STATUSES = {"error", "failed", "cancelled", "canceled", "interrupted"}

# Fallback parsing of the text Claude Code appends to a subagent's tool_result,
# used only when the structured ``toolUseResult`` field is absent:
#   "agentId: <id> (use SendMessage …)\n<usage>subagent_tokens: N\ntool_uses: N\n
#    duration_ms: N</usage>"
_AGENTID_RE = re.compile(r"agentId:\s*(?P<agent_id>\S+)")
_USAGE_RE = re.compile(
    r"subagent_tokens:\s*(?P<tokens>\d+)\s*"
    r"tool_uses:\s*(?P<tool_uses>\d+)\s*"
    r"duration_ms:\s*(?P<duration>\d+)",
    re.DOTALL,
)


def _flatten_result_text(content: Any) -> str:
    """Flatten a tool_result ``content`` (string or list of blocks) to text."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, dict) and block.get("type") == "text":
                parts.append(block.get("text") or "")
            elif isinstance(block, str):
                parts.append(block)
        return "\n".join(parts)
    return ""


def _subagent_result(entry: dict, block: dict) -> dict:
    """Extract a subagent's result detail (agent_id, status, usage), structured-first.

    Prefers the entry's structured ``toolUseResult`` (agentId / status / totalTokens
    / totalToolUseCount / totalDurationMs / resolvedModel); falls back to parsing
    the ``agentId`` line + ``<usage>`` block out of the tool_result text.
    """
    is_error = bool(block.get("is_error"))
    tur = entry.get("toolUseResult")
    if isinstance(tur, dict) and tur.get("agentId"):
        return {
            "agent_id": tur.get("agentId"),
            "status_raw": tur.get("status"),
            "is_error": is_error,
            "usage": {
                "tokens": tur.get("totalTokens"),
                "tool_uses": tur.get("totalToolUseCount"),
                "duration_ms": tur.get("totalDurationMs"),
                "model": tur.get("resolvedModel"),
            },
        }
    # Fallback: parse the agentId line + <usage> summary out of the result text.
    text = _flatten_result_text(block.get("content"))
    agent_id = None
    m_id = _AGENTID_RE.search(text)
    if m_id:
        agent_id = m_id.group("agent_id")
    usage: dict[str, Any] = {
        "tokens": None, "tool_uses": None, "duration_ms": None, "model": None,
    }
    m_u = _USAGE_RE.search(text)
    if m_u:
        usage["tokens"] = int(m_u.group("tokens"))
        usage["tool_uses"] = int(m_u.group("tool_uses"))
        usage["duration_ms"] = int(m_u.group("duration"))
    return {
        "agent_id": agent_id,
        "status_raw": None,
        "is_error": is_error,
        "usage": usage,
    }


def _subagent_status(result: dict | None) -> str:
    """Map a paired result (or None) to running / done / error."""
    if result is None:
        return "running"
    if result["is_error"] or (result.get("status_raw") or "").lower() in _BAD_SUBAGENT_STATUSES:
        return "error"
    return "done"


def derive_subagents(entries: list[dict]) -> dict:
    """Derive a parent agent's subagents from its JSONL transcript.

    A subagent is spawned by an ``Agent`` (this CC build) or ``Task`` (SDK/older)
    ``tool_use`` block on the parent's MAIN line. Its result returns as a matching
    ``tool_result`` (paired by ``tool_use`` id) carrying a structured
    ``toolUseResult`` — ``agentId``, ``status``, ``totalTokens``,
    ``totalToolUseCount``, ``totalDurationMs``, ``resolvedModel`` — and the
    subagent's own full transcript persists at
    ``<project>/<parent-uuid>/subagents/agent-<agentId>.jsonl``.

    A spawn with no matching result yet is still ``running``; once the result
    lands it is ``done`` (or ``error`` if the result is flagged). The ``s1`` /
    ``s2`` … ids are **dashboard-minted in spawn order** — neither driver mints a
    stable per-subagent id (subagents are opaque until the Task returns), so this
    is a synthesized identity, not a read of an existing field.

    Pure function (no live session) so it can be unit-tested directly. Subagent
    sidechain entries are ignored — only the parent's main-line ``Agent``/``Task``
    spawn and its result count.

    Returns ``{"count": N, "subagents": [ {id, tool_use_id, agent_id, type,
    description, prompt, status, usage}, … ]}`` in spawn order.
    """
    # 1) Collect spawns (Agent/Task tool_use blocks on the main line), in order.
    spawns: list[dict] = []
    for e in entries:
        if e.get("type") != "assistant" or e.get("isSidechain"):
            continue
        for block in (e.get("message") or {}).get("content") or []:
            if not isinstance(block, dict) or block.get("type") != "tool_use":
                continue
            if block.get("name") not in _SUBAGENT_TOOLS:
                continue
            inp = block.get("input") or {}
            spawns.append({
                "tool_use_id": block.get("id"),
                "type": inp.get("subagent_type") or inp.get("description"),
                "description": inp.get("description"),
                "prompt": inp.get("prompt"),
            })

    # 2) Index the matching results by tool_use id (only the spawned ids).
    spawn_ids = {sp["tool_use_id"] for sp in spawns if sp["tool_use_id"] is not None}
    results: dict[Any, dict] = {}
    if spawn_ids:
        for e in entries:
            if e.get("type") != "user" or e.get("isSidechain"):
                continue
            content = (e.get("message") or {}).get("content")
            if not isinstance(content, list):
                continue
            for block in content:
                if not isinstance(block, dict) or block.get("type") != "tool_result":
                    continue
                tuid = block.get("tool_use_id")
                if tuid is not None and tuid in spawn_ids:
                    results[tuid] = _subagent_result(e, block)

    # 3) Build the ordered list with dashboard-minted s-ids.
    subagents = []
    for i, sp in enumerate(spawns, start=1):
        res = results.get(sp["tool_use_id"])
        subagents.append({
            "id": f"s{i}",
            "tool_use_id": sp["tool_use_id"],
            "agent_id": res["agent_id"] if res else None,
            "type": sp["type"],
            "description": sp["description"],
            "prompt": sp["prompt"],
            "status": _subagent_status(res),
            "usage": res["usage"] if res else None,
        })

    return {"count": len(subagents), "subagents": subagents}


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
        "set_model", "set_effort", "subagents",
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

    def _build_settings(self) -> dict | None:
        """Per-agent --settings payload: permission rules + plugin enablement.

        ``permission_rules`` {allow,deny,ask} -> ``permissions`` (deny is the
        reliable hard-block in all modes); ``enabled_plugins`` {"id": bool} ->
        ``enabledPlugins`` (per-agent plugin enable/disable — live-verified).
        Returns None when neither is set (no --settings file is written).
        """
        settings: dict[str, Any] = {}
        rules = self.config.permission_rules or {}
        perms = {k: list(rules[k]) for k in ("allow", "deny", "ask") if rules.get(k)}
        if perms:
            settings["permissions"] = perms
        if self.config.enabled_plugins:
            settings["enabledPlugins"] = dict(self.config.enabled_plugins)
        return settings or None

    def _build_mcp_config(self) -> dict | None:
        """Per-agent --mcp-config payload for a chosen server subset.

        None -> inherit the global MCP registry (no --mcp-config). A list (even
        empty) -> a strict ``{"mcpServers": {...}}`` of just those servers.
        """
        if self.config.mcp_servers is None:
            return None
        from bridge.registry import build_agent_mcp_config  # type: ignore[import-not-found]
        return build_agent_mcp_config(
            self._bridge, self.config.mcp_servers, project_cwd=self.config.cwd,
        )

    def _create_session(self) -> None:
        """Sync: build the per-agent launch config and spawn the tmux session.

        All blocking work (MCP registry read + tmux create) runs here so
        ``start()`` can offload it to a thread in one hop.
        """
        self._bridge.create(
            self._name,
            cwd=self.config.cwd,
            model=self.config.model,
            permission_mode=self.config.permission_mode,
            allowed_tools=self.config.allowed_tools,
            disallowed_tools=self.config.disallowed_tools,
            settings=self._build_settings(),
            mcp_config=self._build_mcp_config(),
        )

    async def start(self) -> None:
        if self._resuming:
            # Rebind to the still-alive tmux session; do not recreate. All launch
            # config (mode, tools, permission rules, plugins, MCP) was applied at
            # the original launch — resume does not relaunch claude.
            await asyncio.to_thread(self._bridge.resume, self._name)
        else:
            # Apply ALL per-agent launch config (permission mode + tool gates +
            # permission rules + plugin enablement + MCP scope) via the claude
            # launch flags — the only point a TUI reads them. The startup-gate
            # clearer handles the bypassPermissions warning gate; an unknown mode
            # is dropped and the TUI starts in its default mode.
            await asyncio.to_thread(self._create_session)
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
                    # Applied per-agent launch config — kept for readback after a
                    # sidecar restart (reconnect rebinds, it does not relaunch).
                    "allowed_tools": self.config.allowed_tools,
                    "disallowed_tools": self.config.disallowed_tools,
                    "permission_rules": self.config.permission_rules,
                    "enabled_plugins": self.config.enabled_plugins,
                    "mcp_servers": self.config.mcp_servers,
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

    async def get_subagents(self) -> Any:
        """Derive this agent's subagents from its transcript (see ``derive_subagents``).

        Returns the empty shape (rather than erroring) when the transcript can't
        be read yet — e.g. before the first turn.
        """
        try:
            entries = await asyncio.to_thread(self._bridge.read_log, self._name)
        except Exception:
            return {"count": 0, "subagents": []}
        return derive_subagents(entries)

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
