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
import json
import logging
import os
import re
import sys
import time
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

# Transcript retention pin (ARCHITECTURE §8.6): Claude Code auto-deletes sessions
# inactive longer than `cleanupPeriodDays` (default 30 days) — unacceptable for
# long-term-referenced transcripts, which are the dashboard's master record. Every
# materialized per-agent settings payload pins this (10 years — effectively never;
# one constant to adjust), guaranteeing retention for dashboard agents without
# touching global Claude config.
TRANSCRIPT_RETENTION_DAYS = 3650

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


class AdaptiveCadence:
    """Adaptive poll cadence (§11 #34 → §4.3/§6.2): fast while active, coasting
    while idle, snapping back instantly on any activity.

    The rules: poll at ``active_interval`` (1 s) while the agent is running or
    was active within the last ``idle_after`` seconds (30 s); back off to
    ``idle_interval`` (5 s) once that window passes with no activity; any
    ``nudge()`` — a send, an interrupt, a hook ingest, observed screen or
    transcript activity — snaps the next interval back to active immediately.
    The hook channel (§7.4) already PUSHES run-state on lifecycle events, so an
    idle agent's poll can afford to coast: activity always arrives as a nudge
    before staleness is visible.

    Pure logic with an injectable ``clock`` so it unit-tests hermetically.
    """

    def __init__(self, active_interval: float = 1.0, idle_interval: float = 5.0,
                 idle_after: float = 30.0, clock=time.monotonic) -> None:
        self.active_interval = active_interval
        self.idle_interval = idle_interval
        self.idle_after = idle_after
        self._clock = clock
        self._last_activity = clock()

    def nudge(self) -> None:
        """Record activity — the next ``interval()`` snaps back to active."""
        self._last_activity = self._clock()

    def idle_for(self) -> float:
        """Seconds since the last recorded activity."""
        return self._clock() - self._last_activity

    def interval(self) -> float:
        """The sleep to use for the NEXT poll cycle."""
        if self.idle_for() < self.idle_after:
            return self.active_interval
        return self.idle_interval


def _entry_to_event(entry: dict) -> dict | None:
    """Convert a transcript JSONL entry into a frontend event, or None to skip.

    Each transcript event carries ``anchor`` = the JSONL entry's own
    ``uuid`` and ``source_kind='t'`` so the sidecar can mint a *deterministic*
    event id (``{agent_id}:t:{uuid}``). Re-polling the same entry then dedups to
    a no-op and a reconnect replays without duplicates. A missing uuid leaves
    ``anchor=None`` (the sidecar falls back to a seq-based id).
    """
    etype = entry.get("type")
    msg = entry.get("message", {}) or {}
    ts = entry.get("timestamp") or datetime.now().isoformat()
    anchor = entry.get("uuid")
    if etype == "assistant":
        return {
            "type": "assistant",
            "sdk_type": "AssistantMessage",
            "content": msg.get("content", []),
            "model": msg.get("model"),
            "timestamp": ts,
            "anchor": anchor,
            "source_kind": "t",
        }
    if etype == "user":
        return {
            "type": "user",
            "sdk_type": "UserMessage",
            "content": msg.get("content", []),
            "timestamp": ts,
            "anchor": anchor,
            "source_kind": "t",
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
    # interrupt/context/permission/resume are proven; model + effort drive a live
    # session via typed slash commands; mode/fast/thinking drive it via the
    # proven keys() levers — Shift+Tab ring / Meta+T modal / Meta+O + Space (see
    # the findings block at "Session-control commands" below).
    CAPABILITIES = {
        "interrupt", "context", "permission", "resume",
        "set_model", "set_effort", "set_mode", "set_fast", "set_thinking",
        "subagents", "set_display_name", "context_breakdown", "cost",
        # Timeline (§7.19, §11 #15): in-place conversation rewind + fork-from-N.
        "rewind", "fork",
    }

    def __init__(
        self,
        config: DriverConfig,
        on_event: EventCallback,
        *,
        resume_name: str | None = None,
        session_id: str | None = None,
        claude_session_id: str | None = None,
        cold_restore: bool = False,
        transcript_path: str | None = None,
        persisted_record: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(config, on_event)
        from bridge import TmuxBridge  # type: ignore[import-not-found]
        self._bridge = TmuxBridge()
        # When resuming, bind to the existing tmux session by name instead of
        # generating a fresh one and creating.
        self._name = resume_name or f"awl-{uuid.uuid4().hex[:8]}"
        self._resuming = resume_name is not None and not cold_restore
        # Cold-restore (§9.9): the tmux session is GONE (reboot/WSL shutdown) —
        # relaunch `claude --resume <claude_session_id>` in the same cwd so the
        # same conversation rebuilds from its transcript. A full create: launch
        # config, hooks, and the retention pin all apply.
        self._cold_restore = cold_restore and claude_session_id is not None
        self._session_id = session_id
        # The claude --session-id (uuid) that names this agent's transcript file.
        # Set by create() (read back from the bridge) or, on resume, passed in
        # from the persisted runtime record and re-registered with the bridge.
        self._claude_session_id = claude_session_id
        self._seen = 0
        self._closed = False
        self._last_state: str | None = None
        # §11 #34 — the batched, adaptive poll:
        #   * _cadence: 1 s while running/recently active, coasting to 5 s
        #     after ~30 s idle, snapped back by nudge() on any activity.
        #   * _entries: the accumulated parsed transcript (the emit buffer;
        #     _seen indexes into it). The legacy read_log path replaces it
        #     wholesale; the poll_bundle path replaces on an offset-0 (full)
        #     read and extends on incremental reads.
        #   * _log_offset: transcript bytes consumed so far (complete lines
        #     only — see consume_transcript_chunk).
        self._cadence = AdaptiveCadence()
        self._entries: list[dict] = []
        self._log_offset = 0
        # Post-/clear transcript-rotation re-resolve (§7.13, §11 #35): set when a
        # Console /clear rotated the JSONL but the NEW <id>.jsonl hasn't appeared
        # yet (it may only be created on the first post-/clear turn). While
        # pending, events() stops reading the orphaned old file and retries the
        # re-resolve each poll until the rotated file lands.
        self._rotation_pending = False
        # The resolved WSL transcript path, persisted in the roster record (§8.6
        # #2: resolution is verified, not trusted — and the verified result is
        # remembered so the mapping survives restarts and scheme drift). On
        # resume it is seeded from the persisted record, so a known path is
        # never pointlessly re-resolved.
        self._transcript_path: str | None = transcript_path
        # The last-persisted runtime/roster record, kept so later refreshes
        # (e.g. the transcript path resolving after the first turn) re-save the
        # full record rather than a fragment. On resume paths it is seeded from
        # the FULL persisted record, so a record refresh never drops fields
        # another writer persisted.
        self._record: dict[str, Any] | None = \
            dict(persisted_record) if persisted_record else None

    def bind_session_id(self, session_id: str) -> None:
        """Associate the sidecar session id (used for the runtime record)."""
        self._session_id = session_id

    @property
    def tmux_name(self) -> str:
        return self._name

    def _build_hook_settings(self) -> dict | None:
        """Hook channel — the per-agent PostToolUse + Stop HTTP hooks.

        Points each agent at the sidecar's inbox-drain endpoints (keyed by THIS
        agent's sidecar session id) over the WSL-reachable host gateway URL — the
        spike-proven path that delivers a queued inject mid-turn. PostToolUse
        drains at the next tool boundary; Stop backstops the no-tool-call turn.
        Returns None (hooks omitted, launch still succeeds) when hooks are
        disabled, the session id isn't bound yet, or the host gateway can't
        resolve. Set ``AWL_DISABLE_HOOKS=1`` to opt out fleet-wide.
        """
        if os.environ.get("AWL_DISABLE_HOOKS") == "1" or not self._session_id:
            return None
        try:
            base = self._bridge.sidecar_hook_base_url()
        except Exception:
            base = None
        if not base:
            return None
        agent = self._session_id
        # agent id rides the PATH (claude's http-hook client doesn't reliably
        # forward a query string — verified in the hook-channel spike).
        def _http(url_suffix: str) -> dict:
            return {"type": "http",
                    "url": f"{base}/internal/hooks/{url_suffix}/{agent}",
                    "timeout": 5}
        return {
            "hooks": {
                "PostToolUse": [{"matcher": "", "hooks": [_http("post-tool-use")]}],
                "Stop": [{"matcher": "", "hooks": [_http("stop")]}],
                # Inbox detection: surface the agent's own Plan (ExitPlanMode) and Decision
                # (AskUserQuestion) tool calls as typed Inbox cards — these are
                # screen-blind but hook-visible. Returns allow (detect-and-surface).
                # The "" catch-all rides alongside for the run-state channel
                # (§7.4) — all matching PreToolUse hooks fire, so plan/decision
                # detection and run-state ingestion coexist.
                "PreToolUse": [
                    {"matcher": "ExitPlanMode", "hooks": [_http("plan")]},
                    {"matcher": "AskUserQuestion", "hooks": [_http("decision")]},
                    {"matcher": "", "hooks": [_http("run-state")]},
                ],
                # Run-state push channel (§7.4, Option C hybrid): lifecycle events
                # POST run-state (permission_mode, tool, prompt_id) — authoritative
                # -when-fresh over the screen poll. Notification carries NO
                # permission_mode (spike caveat); the arbiter keys per event.
                "UserPromptSubmit": [{"matcher": "", "hooks": [_http("run-state")]}],
                "Notification": [{"matcher": "", "hooks": [_http("run-state")]}],
                # Subagent lifecycle → the roster's active-vs-quiet signal (§7.17).
                "SubagentStart": [{"matcher": "", "hooks": [_http("subagent")]}],
                "SubagentStop": [{"matcher": "", "hooks": [_http("subagent")]}],
            }
        }

    def _build_statusline_settings(self) -> dict | None:
        """Per-turn statusLine capture (§7.18 source 2, §11 #31).

        A configured statusLine ``command`` receives Claude Code's status JSON
        (incl. ``context_window`` — the freshest PER-TURN snapshot, a
        boundary-emitted value, not a continuous mid-run gauge; boundary mapped
        live by ``test_usage_context_sources_live``) on stdin each time the
        status bar renders. The command appends each payload as ONE line to the
        per-agent launch-config dir (``~/.awl-cc-dash-agents/<name>/
        statusline.jsonl``, WSL-side — ``tr -d '\\n'`` collapses any payload
        newlines so the file stays line-per-render), with a size guard that
        keeps the tail when the file passes ~2 MB. The command's stdout (the
        rendered status line) is a static ``awl-cc-dash`` marker — deliberately
        inert so it can never confuse the screen-state classifier.

        Best-effort: reading is lazy (``get_statusline_snapshot`` tails the
        last line on demand) and an absent/failed capture degrades to
        ``per_turn: null``. Set ``AWL_DISABLE_STATUSLINE=1`` to opt out
        fleet-wide.
        """
        if os.environ.get("AWL_DISABLE_STATUSLINE") == "1":
            return None
        from bridge.paths import WSL_AWL_DIR  # type: ignore[import-not-found]
        path = f"{WSL_AWL_DIR}/{self._name}/statusline.jsonl"
        cmd = (
            f"f='{path}'; mkdir -p \"$(dirname \"$f\")\"; "
            "cat | tr -d '\\n' >> \"$f\"; echo >> \"$f\"; "
            "if [ \"$(wc -c < \"$f\")\" -gt 2000000 ]; then "
            "tail -n 500 \"$f\" > \"$f.tmp\" && mv \"$f.tmp\" \"$f\"; fi; "
            "echo awl-cc-dash"
        )
        return {"statusLine": {"type": "command", "command": cmd, "padding": 0}}

    def _build_settings(self) -> dict:
        """Per-agent --settings payload: retention pin + permission rules + plugins + hooks + statusLine.

        Always carries ``cleanupPeriodDays`` (= ``TRANSCRIPT_RETENTION_DAYS``) — the
        §8.6 transcript-retention pin, so a settings file is written for EVERY agent
        (Claude Code's 30-day auto-delete default must never apply to dashboard
        agents). On top of that: ``permission_rules`` {allow,deny,ask} ->
        ``permissions`` (deny is the reliable hard-block in all modes);
        ``enabled_plugins`` {"id": bool} -> ``enabledPlugins`` (per-agent plugin
        enable/disable — live-verified); the hook-channel ``hooks`` block (the
        inject channel); plus the ``statusLine`` per-turn capture command
        (§11 #31, see ``_build_statusline_settings``).
        """
        settings: dict[str, Any] = {
            "cleanupPeriodDays": TRANSCRIPT_RETENTION_DAYS,
        }
        # Plan-mode output redirects into the project store (§8.5): the ABSOLUTE
        # WSL path <canonical-root>/.awl-cc-dash/plans — a relative "./" would
        # resolve against the agent's raw cwd and break subfolder launches.
        if self.config.cwd:
            try:
                import storage  # sidecar dir on sys.path (runtime)
            except ImportError:  # pragma: no cover - package import (tests)
                from .. import storage  # type: ignore[no-redef]
            plans_wsl = storage.plans_dir_wsl(self.config.cwd)
            if plans_wsl:
                settings["plansDirectory"] = plans_wsl
        rules = self.config.permission_rules or {}
        perms = {k: list(rules[k]) for k in ("allow", "deny", "ask") if rules.get(k)}
        if perms:
            settings["permissions"] = perms
        if self.config.enabled_plugins:
            settings["enabledPlugins"] = dict(self.config.enabled_plugins)
        hooks = self._build_hook_settings()
        if hooks:
            settings.update(hooks)
        statusline = self._build_statusline_settings()
        if statusline:
            settings.update(statusline)
        return settings

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
        ``start()`` can offload it to a thread in one hop. A cold-restore passes
        ``resume_session_id`` so the launch is ``claude --resume <id>`` — the
        same conversation, rebuilt from its transcript (§9.9).
        """
        kwargs: dict[str, Any] = {}
        if self._cold_restore:
            kwargs["resume_session_id"] = self._claude_session_id
        # Name registration (§7.5): the dashboard identity NAME doubles as the
        # Claude Code session display name, set at launch via `claude --name`.
        display_name = (self.config.identity or {}).get("name") or None
        # Per-agent git attribution (§7.5, §11 #19): derive this agent's git
        # author name + synthetic per-agent email from its identity and inject
        # them as GIT_* env on the launch command, so any `git` it runs commits
        # under its own identity (the AI-touched query keys off the fixed
        # `agents.awl-cc-dash.invalid` domain). Every dashboard agent — named or
        # not — gets attribution, so nothing AI-authored escapes the query.
        try:
            import identity as _identity  # sidecar dir on sys.path (runtime)
        except ImportError:  # pragma: no cover - package import (tests)
            from .. import identity as _identity  # type: ignore[no-redef]
        git_author_name, git_author_email = _identity.git_author(self.config.identity)
        info = self._bridge.create(
            self._name,
            cwd=self.config.cwd,
            model=self.config.model,
            permission_mode=self.config.permission_mode,
            allowed_tools=self.config.allowed_tools,
            disallowed_tools=self.config.disallowed_tools,
            settings=self._build_settings(),
            mcp_config=self._build_mcp_config(),
            display_name=display_name,
            git_author_name=git_author_name,
            git_author_email=git_author_email,
            **kwargs,
        )
        # Remember the launched claude session id so it can be persisted for
        # restart-survival (resume re-registers it so transcript resolution holds).
        self._claude_session_id = (info or {}).get("session_id") or \
            self._bridge.session_id_for(self._name) or self._claude_session_id

    async def start(self) -> None:
        if self._resuming:
            # Rebind to the still-alive tmux session; do not recreate. All launch
            # config (mode, tools, permission rules, plugins, MCP) was applied at
            # the original launch — resume does not relaunch claude. Re-register
            # the persisted claude session id so find_transcript resolves THIS
            # session's own <id>.jsonl (a fresh bridge has no in-memory map).
            # cwd/model/resume_session_id ride along so the fall-through — the
            # tmux session died in the race window since the alive-check —
            # cold-restores the SAME conversation in the right cwd instead of
            # creating a blank session (§9.9).
            if self._claude_session_id:
                self._bridge.register_session_id(self._name, self._claude_session_id)
            await asyncio.to_thread(
                self._bridge.resume, self._name,
                cwd=self.config.cwd, model=self.config.model,
                resume_session_id=self._claude_session_id,
            )
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
        # still-alive tmux session (or cold-restore a dead one, §9.9). On
        # resume paths the persisted record (seeded in __init__) is the BASE —
        # fields another writer persisted are carried forward, never dropped.
        if self._session_id:
            record = dict(self._record) if self._record else {}
            record.update({
                "session_id": self._session_id,
                "tmux_name": self._name,
                "driver": "bridge",
                "model": self.config.model,
                "permission_mode": self.config.permission_mode,
                "cwd": self.config.cwd,
                # The claude --session-id naming this agent's transcript, so a
                # restarted sidecar resolves the right <id>.jsonl on resume.
                "claude_session_id": self._claude_session_id,
                # The verified transcript path (§8.6 #2) — seeded from the
                # persisted record when known, else resolved lazily once the
                # transcript exists (see events()) and refreshed on resolve.
                "transcript_path": self._transcript_path,
                # Applied per-agent launch config — kept for readback after a
                # sidecar restart (reconnect rebinds, it does not relaunch).
                "allowed_tools": self.config.allowed_tools,
                "disallowed_tools": self.config.disallowed_tools,
                "permission_rules": self.config.permission_rules,
                "enabled_plugins": self.config.enabled_plugins,
                "mcp_servers": self.config.mcp_servers,
                # Dashboard-owned identity, persisted so it survives restart.
                "identity": self.config.identity,
            })
            self._record = record
            try:
                _save_record(self._record)
            except Exception as e:  # pragma: no cover - best effort
                logger.warning("could not persist runtime record: %s", e)

        self.on_event({
            "type": "status_change", "status": "idle",
            "timestamp": datetime.now().isoformat(),
        })

    def nudge(self) -> None:
        """Snap the adaptive poll cadence back to active (§11 #34).

        Called internally on send/interrupt/permission-answer and observed
        activity; the sidecar also calls it on hook ingest and console runs —
        the push channels that see activity before the poll does.
        """
        self._cadence.nudge()

    async def send(self, prompt: str) -> None:
        self.nudge()
        await asyncio.to_thread(self._bridge.send, self._name, prompt)

    def _resolve_and_persist_transcript_path(self) -> None:
        """Resolve this agent's transcript path once and persist it (§8.6/#4).

        Called (in a thread) after the first successful transcript read — the
        file provably exists then — so the verified path lands in the roster
        record and the mapping survives restarts and scheme drift.
        """
        try:
            from bridge.transcript import find_transcript  # type: ignore[import-not-found]
            path = find_transcript(self._bridge, self._name)
        except Exception:  # pragma: no cover - environment dependent
            path = None
        if not path:
            return
        self._transcript_path = path
        if self._record is not None:
            self._record["transcript_path"] = path
            try:
                _save_record(self._record)
            except Exception as e:  # pragma: no cover - best effort
                logger.warning("could not refresh runtime record: %s", e)

    def _apply_rotation(self, new_id: str) -> None:
        """Adopt a rotated claude session id (post-/clear, §7.13/§11 #35).

        A ``/clear`` starts a NEW conversation, so the fresh transcript is
        replayed from 0 — every entry in the rotated ``<new-id>.jsonl`` is a new
        event (their uuids are new, so the sidecar's deterministic-id dedup
        can't drop them). The persisted runtime record is refreshed so a
        restarted sidecar resolves the rotated file, and ``_transcript_path`` is
        cleared so the next successful read re-resolves + re-persists the
        verified path (the existing ``events()`` lazy-resolve).
        """
        self._claude_session_id = new_id
        self._seen = 0
        self._transcript_path = None
        self._rotation_pending = False
        # §11 #34: the incremental-read state resets with the conversation —
        # the rotated file replays from byte 0 into a fresh buffer.
        self._entries = []
        self._log_offset = 0
        self.nudge()
        if self._record is not None:
            self._record["claude_session_id"] = new_id
            self._record["transcript_path"] = None
            try:
                _save_record(self._record)
            except Exception as e:  # pragma: no cover - best effort
                logger.warning("could not refresh runtime record after rotation: %s", e)

    async def handle_transcript_rotation(self) -> dict[str, Any]:
        """Re-resolve the transcript after a Console ``/clear`` (§7.13, §11 #35).

        A ``/clear`` rotates the agent's JSONL to a new ``<new-id>.jsonl`` while
        the live process keeps its original ``--session-id`` argv, orphaning the
        pinned resolution (live-proven, ``test_console_clear_transcript_live``).
        Called by the console-run path when it detects a ``/clear``; asks the
        bridge to re-resolve (newest-``.jsonl``-in-project-dir, since nothing
        else names the rotated id) and re-register the id, then adopts it via
        ``_apply_rotation``. When the rotated file hasn't appeared yet (some
        builds only create it on the first post-/clear turn), a pending flag is
        left so ``events()`` retries every poll until it lands — post-/clear
        turns are never lost either way.
        """
        try:
            new_id = await asyncio.to_thread(
                self._bridge.reresolve_session_id, self._name
            )
        except Exception as e:  # pragma: no cover - environment dependent
            logger.warning("post-/clear re-resolve failed for %s: %s", self._name, e)
            new_id = None
        if new_id:
            self._apply_rotation(new_id)
            logger.info("transcript rotated for %s -> %s", self._name, new_id)
            return {"rotated": True, "claude_session_id": new_id, "pending": False}
        self._rotation_pending = True
        return {"rotated": False, "claude_session_id": self._claude_session_id,
                "pending": True}

    async def events(self) -> AsyncIterator[dict[str, Any]]:
        # §11 #34 — the batched, adaptive poll loop. Once the transcript path
        # is resolved, each cycle is ONE WSL round-trip (poll_bundle: both
        # screen slices + the transcript's new bytes) instead of the ~5 spawns
        # the read_log+status pair cost; before resolution (transcript only
        # exists after the first turn) the legacy resolving path runs. The
        # cycle sleep is the AdaptiveCadence interval — 1 s active, coasting
        # to 5 s after ~30 s of no activity, snapped back by nudge().
        from bridge.bridge import parse_permission_prompt  # type: ignore[import-not-found]
        from bridge.transcript import consume_transcript_chunk  # type: ignore[import-not-found]

        while not self._closed:
            # 0) Pending post-/clear rotation: the rotated <id>.jsonl hadn't
            # appeared yet — retry the re-resolve (single immediate check) and
            # skip the orphaned old file until it lands.
            if self._rotation_pending:
                try:
                    new_id = await asyncio.to_thread(
                        self._bridge.reresolve_session_id, self._name, 0.0
                    )
                except Exception:  # pragma: no cover - environment dependent
                    new_id = None
                if new_id:
                    self._apply_rotation(new_id)
                    logger.info("transcript rotated for %s -> %s (deferred)",
                                self._name, new_id)

            # 1) Read the cycle's inputs — transcript entries + screen state.
            st: dict[str, Any] = {}
            state: str | None = None
            screen_read = False
            if not self._rotation_pending and self._transcript_path:
                # Batched path: ONE WSL spawn for screen + transcript delta.
                try:
                    bundle = await asyncio.to_thread(
                        self._bridge.poll_bundle, self._name,
                        self._transcript_path, self._log_offset)
                except Exception:  # pragma: no cover - environment dependent
                    bundle = None
                if bundle is not None:
                    start_offset = self._log_offset
                    if bundle.get("size", -1) < 0:
                        # The resolved file vanished (wipe/external rotation) —
                        # fall back to the resolving path next cycle.
                        self._transcript_path = None
                        self._entries = []
                        self._log_offset = 0
                    else:
                        new_entries, consumed = consume_transcript_chunk(
                            bundle.get("chunk") or b"")
                        if consumed:
                            self._log_offset = start_offset + consumed
                            if start_offset == 0:
                                # Offset-0 read = a full-file snapshot —
                                # REPLACE the buffer (never extend: the legacy
                                # path may have pre-filled it).
                                self._entries = new_entries
                            else:
                                self._entries.extend(new_entries)
                    # Screen state from the same round-trip: the state slice
                    # is exactly what status() classifies; the detail slice is
                    # its permission re-read.
                    state = self._bridge._detect_state(bundle.get("screen") or "")
                    st = {"state": state}
                    if state == "permission_prompt":
                        parsed = parse_permission_prompt(
                            bundle.get("screen_detail") or "")
                        if parsed:
                            st["permission"] = parsed
                    screen_read = True
            elif not self._rotation_pending:
                # Legacy resolving path (no transcript yet): read_log resolves
                # the file via the pinned session id.
                try:
                    entries = await asyncio.to_thread(
                        self._bridge.read_log, self._name)
                except Exception:
                    entries = []  # transcript may not exist until the first turn
                if entries and self._transcript_path is None:
                    # The transcript exists now — resolve + persist its
                    # verified path once; the buffer stays offset-0 so the
                    # first bundle read re-snapshots (and replaces) it.
                    await asyncio.to_thread(
                        self._resolve_and_persist_transcript_path)
                if entries:
                    self._entries = entries

            # 2) Emit new transcript entries -> assistant/user events.
            if len(self._entries) > self._seen:
                self.nudge()  # transcript activity — stay on the fast cadence
                for entry in self._entries[self._seen:]:
                    event = _entry_to_event(entry)
                    if event:
                        yield event
                self._seen = len(self._entries)

            # 3) Screen state -> status_change / permission events. (The
            # legacy path — and a failed bundle — still uses status().)
            if not screen_read:
                try:
                    st = await asyncio.to_thread(self._bridge.status, self._name)
                    state = st.get("state")
                except Exception:
                    st, state = {}, None
            if state and state != "idle":
                self.nudge()  # generating / permission prompt = activity
            if state and state != self._last_state:
                self.nudge()  # any state flip = activity
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

            await asyncio.sleep(self._cadence.interval())

    async def interrupt(self) -> None:
        self.nudge()
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
        self.nudge()
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

    async def get_statusline_snapshot(self) -> dict | None:
        """The freshest per-turn statusLine payload (§7.18 source 2, §11 #31).

        Lazily tails the last line of the per-agent ``statusline.jsonl`` the
        launch-time statusLine command appends to (see
        ``_build_statusline_settings``) and parses it as JSON. This is a
        PER-TURN snapshot — the statusLine fires at turn boundaries, not
        continuously mid-run (boundary mapped live by
        ``test_usage_context_sources_live``) — so the value is the freshest
        *boundary* number, fresher than post-hoc JSONL but never a live gauge.
        Best-effort: absent file / torn or unparseable line → None (the
        endpoint serves ``per_turn: null``).
        """
        try:
            line = await asyncio.to_thread(
                self._bridge.statusline_tail, self._name)
        except Exception:
            return None
        if not line:
            return None
        try:
            payload = json.loads(line)
        except (json.JSONDecodeError, ValueError):
            return None
        return payload if isinstance(payload, dict) else None

    # --- /context deep readout (§7.18 source 1, §11 #30) -----------------------

    # Early-break bar for the bounded screen poll. The proving spike (2.1.198)
    # required {system_prompt, free_space} + 4 rows, but CC 2.1.206's compact
    # `/context` view lists ONLY NON-ZERO categories ("Estimated usage by
    # category" — live-caught 2026-07-15), so a young session legitimately
    # renders as few as 3 rows. `free_space` is the always-present anchor; a
    # session with real usage still yields the full set in the same paint.
    _BREAKDOWN_MIN_ROWS = 3
    _BREAKDOWN_REQUIRED = frozenset({"free_space"})

    async def get_context_breakdown(self) -> dict[str, Any]:
        """Pull the per-category `/context` breakdown + compaction history.

        The §7.18 on-demand deep readout (§11 #30): idle-gated (a slash command
        typed mid-turn is held as typeahead and would fire at the boundary —
        never blind-send), then ``/context`` via the console path with a bounded
        wait + screen scrape (the spike mechanics: `/context` renders to the
        screen, not a generating turn). If the screen parse misses the WORKS bar
        the transcript's own markdown table (`/context` also records one — a
        steadier read-back) is parsed as the fallback. Compaction history is
        derived from ``compact_boundary`` transcript metadata (Lever B).

        This is a point-in-time, idle-gated pull — the on-demand accordion
        source, NEVER polled; the JSONL floor stays ``get_context_usage``.

        Returns:
            ``{"rows": [{key, tokens, percent, raw}, ...], "compact_history":
            {"count", "boundaries"}}`` — rows in canonical category order,
            empty when nothing parsed (honest miss).

        Raises:
            RuntimeError("busy") when the screen never reached idle (the
            endpoint maps it to an honest 409).
        """
        from bridge.transcript import (  # type: ignore[import-not-found]
            CONTEXT_CATEGORY_ORDER, compact_history, find_context_markdown,
            parse_context_output,
        )

        def _pull() -> dict:
            if not self._bridge._idle_gate(self._name, timeout=5.0):
                raise RuntimeError("busy")
            self._bridge.send(self._name, "/context")
            parsed: dict = {}
            for _ in range(10):
                time.sleep(1.5)
                screen = self._bridge.scrollback(
                    self._name, max_lines=200)["content"]
                parsed = parse_context_output(screen)
                if len(parsed) >= self._BREAKDOWN_MIN_ROWS and \
                        self._BREAKDOWN_REQUIRED <= set(parsed):
                    break
            return parsed

        parsed = await asyncio.to_thread(_pull)
        try:
            entries = await asyncio.to_thread(self._bridge.read_log, self._name)
        except Exception:
            entries = []
        if not (len(parsed) >= self._BREAKDOWN_MIN_ROWS and
                self._BREAKDOWN_REQUIRED <= set(parsed)):
            # Screen scrape missed — the transcript markdown table is the
            # steadier secondary read-back (same line shape, same parser).
            md = find_context_markdown(entries)
            if md:
                fallback = parse_context_output(md)
                if len(fallback) > len(parsed):
                    parsed = fallback
        rows = [
            {"key": key, **parsed[key]}
            for key in CONTEXT_CATEGORY_ORDER if key in parsed
        ]
        return {"rows": rows, "compact_history": compact_history(entries)}

    # --- Per-agent cost (§7.15, §11 #32) ---------------------------------------

    async def get_cost(self) -> dict[str, Any]:
        """Harvest this agent's per-session cost via the `/cost` console scrape.

        The spike-proven path (§11 #32, ``test_per_agent_cost_live`` — WORKS,
        overturning the old "honest blank"): `/cost` opens the unified Usage
        dialog whose per-SESSION panel renders ``Total cost: $X`` plus a
        per-model breakdown — Claude Code's OWN estimate, and for a bridge
        agent the session IS that one agent. Idle-gated (a slash command typed
        mid-turn misfires), point-in-time, on-demand — the endpoint is pulled
        lazily, never on a poll loop. The dialog is dismissed with Escape.

        Returns:
            ``{"usd": float|None, "per_model": [floats], "raw": str}`` —
            ``usd: None`` when no per-session Total-cost line rendered (the
            honest miss, e.g. a build/account without the panel — never a
            fabricated figure).

        Raises:
            RuntimeError("busy") when the screen never reached idle.
        """
        from bridge.bridge import parse_cost_output  # type: ignore[import-not-found]

        def _pull() -> str:
            if not self._bridge._idle_gate(self._name, timeout=5.0):
                raise RuntimeError("busy")
            self._bridge.send(self._name, "/cost")
            time.sleep(3.0)  # the Usage dialog renders (not a generating turn)
            screen = self._bridge.scrollback(self._name, max_lines=150)["content"]
            try:
                self._bridge.keys(self._name, "Escape")  # dismiss the dialog
            except Exception as e:  # pragma: no cover - best effort
                logger.debug("Escape after /cost failed for %s: %s", self._name, e)
            return screen

        screen = await asyncio.to_thread(_pull)
        parsed = parse_cost_output(screen)
        if parsed is None:
            return {"usd": None, "per_model": [], "raw": screen[-1500:]}
        return parsed

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
    # Live findings — all five controls now drive a real running TUI. (The first
    # 2.1.187 discovery pass left mode/fast/thinking as no-ops; the levers were
    # then proven live and are wired per §11 #12.)
    #   * /model <name>  + Enter  → sets directly ("Set model to …"). WIRED (send).
    #   * /effort <level> + Enter → sets directly ("Set effort level to …"). WIRED (send).
    #   * permission mode → NO absolute set exists on the TUI (no slash command,
    #     no hot-applied setting — confirmed at every layer by the mode-control
    #     research), but the Shift+Tab ring cycles deterministically at a
    #     known-idle screen with the resulting mode read back from the status
    #     line — proven live incl. behavior, not just the indicator
    #     (test_permission_mode_cycle_live, 2026-07-02). WIRED via
    #     bridge.set_permission_mode (bounded cycle). Bypass/Auto are
    #     LAUNCH-GATED (§7.11): an un-armed segment is SILENTLY ABSENT from the
    #     ring (test_bypass_auto_preconditions_live), so the bridge's honest
    #     {ok: False, reason: "unreachable"} — surfaced here as a RuntimeError —
    #     IS the un-armed signal the UI needs (§11 #13's backend half). The
    #     pre-arm is a launch choice and already works through create():
    #     DriverConfig.permission_mode → --permission-mode, with the
    #     startup-gate clearer accepting the bypass warning.
    #   * thinking → no /thinking command exists, but `Meta+T` opens a modal
    #     that both SHOWS the current state (✔ on the active option) and sets it
    #     absolutely — proven live (test_thinking_toggle_live, 2026-07-02).
    #     WIRED via bridge.set_thinking (open → read first → toggle only if
    #     needed → read back).
    #   * fast → `Meta+O` opens the Fast panel; `Space` is the toggle lever
    #     (Enter/Escape only close it) and the panel's "Fast mode OFF/ON" line
    #     is a plain-text scrape — proven live (test_fast_mode_toggle_live,
    #     2026-07-04). A credit-gated account reports "requires usage credits"
    #     and no keystroke can enable Fast → the honest degrade is
    #     RuntimeError("credit_gated"), never a faked toggle. WIRED via
    #     bridge.set_fast.
    # Contract: each wired set_* returns the READ-BACK state (never an echo of
    # the value sent) and raises RuntimeError(<reason>) on {ok: False} — reasons
    # "busy" (screen not idle, retryable), "unreachable" (mode not in the armed
    # ring), "credit_gated" (Fast without credits), "unreadable" (panel/status
    # scrape failed) — so the endpoint maps them to honest 409/400s.

    async def set_model(self, model: str) -> None:
        # Fully-typed `/model <name>` + Enter sets directly (autocomplete does
        # not intercept a complete command).
        await asyncio.to_thread(self._bridge.send, self._name, f"/model {model}")

    async def set_effort(self, effort: str) -> None:
        await asyncio.to_thread(self._bridge.send, self._name, f"/effort {effort}")

    async def set_mode(self, mode: str) -> str:
        """Cycle the live TUI to `mode` (bounded Shift+Tab ring, idle-gated).

        Returns the read-back mode; raises RuntimeError("busy"/"unreachable")
        on the honest failures (see the findings block above).
        """
        result = await asyncio.to_thread(
            self._bridge.set_permission_mode, self._name, mode)
        if not result.get("ok"):
            raise RuntimeError(result.get("reason") or "failed")
        return result["mode"]

    async def set_fast(self, on: bool) -> bool:
        """Set Fast mode via the Meta+O panel (Space toggle, read-first).

        Returns the read-back state; raises RuntimeError("busy"/"credit_gated"/
        "unreadable") on the honest failures.
        """
        result = await asyncio.to_thread(self._bridge.set_fast, self._name, on)
        if not result.get("ok"):
            raise RuntimeError(result.get("reason") or "failed")
        return bool(result["on"])

    async def set_thinking(self, on: bool) -> bool:
        """Set extended thinking via the Meta+T modal (read-first, absolute).

        Returns the read-back state; raises RuntimeError("busy"/"unreadable")
        on the honest failures.
        """
        result = await asyncio.to_thread(self._bridge.set_thinking, self._name, on)
        if not result.get("ok"):
            raise RuntimeError(result.get("reason") or "failed")
        return bool(result["on"])

    async def set_display_name(self, name: str) -> None:
        """Register ``name`` as the LIVE session's Claude Code display name (§7.5).

        Drives the ``/rename <name>`` slash command over ``send()`` — the
        console-run path proves slash commands land on a live TUI. The
        launch-time counterpart is the ``claude --name`` flag (present on CC
        2.1.202), which ``_create_session`` passes from ``config.identity``.
        Best-effort: the TUI acks on-screen; there is no structured read-back
        (the registered name lands in ``~/.claude/sessions/<pid>.json``).
        """
        if not name:
            return
        await asyncio.to_thread(self._bridge.send, self._name, f"/rename {name}")

    # --- Timeline: Rewind / Fork (§7.19, §11 #15) ------------------------------
    #
    # Both drive the TUI-native path proven live (test_rewind_handoff_live) and
    # gate on Claude Code >= 2.1.191. Failures are surfaced as RuntimeError(reason)
    # like the other live levers so the endpoint maps them to honest HTTP codes:
    #   * "version_unsupported" -> 400 (the CLI is too old / unresolvable);
    #   * "busy"                -> 409 (the screen isn't idle for the /rewind menu);
    #   * anything else         -> 500 (an unexpected bridge failure).

    async def rewind(self, to_prompt_index: int = 1) -> dict:
        """Rewind this session's conversation to an earlier prompt (in-place).

        Wraps ``TmuxBridge.rewind`` (the ``/rewind`` menu driver). Raises
        RuntimeError("version_unsupported" | "busy" | <message>) — never a fake
        success — so the endpoint degrades honestly.
        """
        from bridge.bridge import (  # type: ignore[import-not-found]
            TmuxBridgeError, VersionUnsupportedError,
        )
        try:
            result = await asyncio.to_thread(
                self._bridge.rewind, self._name, to_prompt_index)
        except VersionUnsupportedError:
            raise RuntimeError("version_unsupported")
        except TmuxBridgeError as e:
            raise RuntimeError("busy" if str(e).startswith("busy") else str(e))
        self.nudge()
        return result

    async def fork(self, new_name: str, *, cwd: str | None = None,
                   model: str | None = None, to_prompt_index: int | None = None,
                   isolate: bool = True, git_author_name: str | None = None,
                   git_author_email: str | None = None) -> dict:
        """Branch a NEW tmux session from THIS one via ``--fork-session``.

        Wraps ``TmuxBridge.fork`` (version gate + per-fork file-state policy +
        ``--fork-session`` spawn + optional rewind-in-fork). ``new_name`` is the
        fork's tmux session name (minted by the caller). Returns the bridge fork
        descriptor (source id, the fork's fresh claude id, cwd, filestate,
        rewound_to); the sidecar adopts it as a live SessionState. Raises
        RuntimeError("version_unsupported" | "busy" | <message>) on failure.
        """
        from bridge.bridge import (  # type: ignore[import-not-found]
            TmuxBridgeError, VersionUnsupportedError,
        )
        try:
            result = await asyncio.to_thread(
                lambda: self._bridge.fork(
                    self._name, new_name, cwd=cwd, model=model,
                    to_prompt_index=to_prompt_index, isolate=isolate,
                    git_author_name=git_author_name,
                    git_author_email=git_author_email))
        except VersionUnsupportedError:
            raise RuntimeError("version_unsupported")
        except TmuxBridgeError as e:
            raise RuntimeError("busy" if str(e).startswith("busy") else str(e))
        self.nudge()
        return result

    async def stop(self) -> None:
        """End the tmux session gracefully but KEEP the persisted record.

        The §3.4 "Close & stop agents" path: the process ends, the transcript
        persists, and the roster record survives so a later project open can
        cold-restore the same conversation (§9.9). Contrast ``close()``, the
        retire path, which also removes the record.
        """
        self._closed = True
        try:
            await asyncio.to_thread(self._bridge.close, self._name)
        except Exception:  # pragma: no cover - best effort
            pass

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
