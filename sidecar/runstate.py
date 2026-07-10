"""Run-state arbiter — the hook-pushed run-state channel + screen-poll merge (§7.4, §11 #21).

Every bridge agent's lifecycle hooks POST run-state to the sidecar (the Option C
hybrid, proven by `test_hook_event_stream_live`): `permission_mode`, the current
tool, and `prompt_id` ride the hook payloads. This module is the per-agent
**arbiter** that ingests those pushes and merges them with the bridge's ~1 s
screen-poll:

  * **Authoritative-when-fresh:** a push within the freshness window wins over
    the poll; past it, the screen-poll is the watchdog floor (HTTP-hook failures
    are silent, so a pure-push model is unsafe — §7.4).
  * **Event-specific fields:** `permission_mode` is only trusted from events
    that actually carry it — the `Notification` event LACKS it (spike caveat),
    so a Notification ingest never clears/overwrites the mode.
  * **Ordering/dedup under concurrent load:** hook POSTs arrive concurrently and
    can interleave. Every ingest takes a process-wide monotonic sequence under a
    lock; per-field updates are last-write-wins in ingest order, and an exact
    duplicate delivery (same event name + prompt_id + tool_use_id + tool) within
    the same prompt is dropped. (The live companion,
    `test_runstate_arbiter_live.py`, verifies real-payload field presence;
    the hermetic tier hammers the lock with threads.)

It also owns the **subagent registry** fed by `SubagentStart` / `SubagentStop`
hooks (`agent_id`, `agent_type`, `transcript_path` — the roster's
active-vs-quiet signal, §7.17), which `GET /sessions/{id}/subagents` blends over
the transcript-derived list.

Process-local and hermetically testable (mirrors ``eventbus``); ``reset()``
clears it.
"""

from __future__ import annotations

import os
import threading
import time
from typing import Any

# Pushed state is authoritative for this many seconds; past it the screen-poll
# is the floor. The bridge polls ~1 s, hooks fire per tool boundary — 10 s keeps
# push authority across normal tool cadence without masking a dead hook channel.
FRESHNESS_S = 10.0

# Events whose payloads carry a trustworthy `permission_mode`. `Notification`
# is deliberately absent (the spike-mapped gap).
_MODE_BEARING_EVENTS = {
    "UserPromptSubmit", "PreToolUse", "PostToolUse", "Stop",
    "SubagentStart", "SubagentStop",
}

_lock = threading.Lock()
_seq = 0

# agent_id -> run-state record
_STATE: dict[str, dict[str, Any]] = {}
# agent_id -> {subagent_id -> record}
_SUBAGENTS: dict[str, dict[str, dict[str, Any]]] = {}
# recent-delivery dedup keys per agent (bounded)
_SEEN: dict[str, list[str]] = {}
_SEEN_MAX = 64

# Env-guarded ingest capture (``AWL_RUNSTATE_DEBUG=1``): a bounded per-agent
# list of every ingested delivery (event name + the arbiter-relevant fields +
# the raw payload key set), so a live test can read back EXACTLY which hook
# events the installed CLI fired and what each payload carried (§11 #21's live
# verify). Off by default — zero cost in production.
_DEBUG: dict[str, list[dict[str, Any]]] = {}
_DEBUG_MAX = 500


def _debug_enabled() -> bool:
    return os.environ.get("AWL_RUNSTATE_DEBUG") == "1"


def debug_log(agent_id: str) -> list[dict[str, Any]]:
    """The captured ingest deliveries for an agent (empty unless the
    ``AWL_RUNSTATE_DEBUG=1`` capture is enabled)."""
    with _lock:
        return [dict(r) for r in _DEBUG.get(agent_id, [])]


def reset() -> None:
    global _seq
    with _lock:
        _seq = 0
        _STATE.clear()
        _SUBAGENTS.clear()
        _SEEN.clear()
        _DEBUG.clear()


def _dedup_key(event: str, payload: dict[str, Any]) -> str | None:
    """A stable identity for one hook delivery, when the payload gives us one.

    Keyed on (event, prompt_id, tool_use_id|tool_name): an exact redelivery of
    the same boundary dedups; distinct boundaries always differ (tool_use_id is
    unique per call; events without any identifying fields return None and are
    never dropped).
    """
    pid = payload.get("prompt_id")
    tuid = payload.get("tool_use_id") or payload.get("toolUseId")
    tool = payload.get("tool_name") or payload.get("toolName")
    if pid is None and tuid is None:
        return None
    return f"{event}:{pid}:{tuid or tool}"


def ingest(agent_id: str, event: str, payload: dict[str, Any] | None = None) -> dict[str, Any] | None:
    """Ingest one hook push. Returns the updated record, or None when deduped.

    Field semantics (per-field last-write-wins in ingest order, under the lock):
      * ``permission_mode`` — only from mode-bearing events (never Notification).
      * ``current_tool``    — set by PreToolUse/PostToolUse (cleared on Stop).
      * ``phase``           — "running" from UserPromptSubmit/PreToolUse/PostToolUse,
                              "idle" from Stop. Notification does not move phase.
      * ``prompt_id``       — recorded when present (v2.1.196+ payloads).
    """
    global _seq
    payload = payload or {}
    with _lock:
        if _debug_enabled():
            dbg = _DEBUG.setdefault(agent_id, [])
            dbg.append({
                "ts": time.time(),
                "event": event,
                "permission_mode": payload.get("permission_mode")
                or payload.get("permissionMode"),
                "tool_name": payload.get("tool_name") or payload.get("toolName"),
                "tool_use_id": payload.get("tool_use_id")
                or payload.get("toolUseId"),
                "prompt_id": payload.get("prompt_id"),
                "payload_keys": sorted(payload.keys()),
            })
            del dbg[:-_DEBUG_MAX]
        key = _dedup_key(event, payload)
        if key is not None:
            seen = _SEEN.setdefault(agent_id, [])
            if key in seen:
                return None
            seen.append(key)
            del seen[:-_SEEN_MAX]

        _seq += 1
        rec = _STATE.setdefault(agent_id, {
            "permission_mode": None,
            "current_tool": None,
            "phase": None,
            "prompt_id": None,
            "last_event": None,
            "last_push_ts": 0.0,
            "seq": 0,
        })
        rec["seq"] = _seq
        rec["last_event"] = event
        rec["last_push_ts"] = time.time()

        mode = payload.get("permission_mode") or payload.get("permissionMode")
        if mode and event in _MODE_BEARING_EVENTS:
            rec["permission_mode"] = mode

        pid = payload.get("prompt_id")
        if pid is not None:
            rec["prompt_id"] = pid

        tool = payload.get("tool_name") or payload.get("toolName")
        if event in ("PreToolUse", "PostToolUse"):
            if tool:
                rec["current_tool"] = tool
            rec["phase"] = "running"
        elif event == "UserPromptSubmit":
            rec["phase"] = "running"
        elif event == "Stop":
            rec["phase"] = "idle"
            rec["current_tool"] = None
        # Notification: freshness + last_event only — no mode, no phase move.

        return dict(rec)


def ingest_subagent(agent_id: str, event: str, payload: dict[str, Any] | None = None) -> dict[str, Any] | None:
    """Ingest a SubagentStart/SubagentStop push into the subagent registry.

    Also counts as a run-state freshness signal for the parent (rides the same
    channel, §7.17). Returns the subagent record, or None without an id.
    """
    payload = payload or {}
    sub_id = payload.get("agent_id") or payload.get("agentId")
    ingest(agent_id, event, payload)   # freshness + mode if carried
    if not sub_id:
        return None
    with _lock:
        subs = _SUBAGENTS.setdefault(agent_id, {})
        rec = subs.setdefault(sub_id, {
            "agent_id": sub_id,
            "type": None,
            "transcript_path": None,
            "status": None,
            "started_at": None,
            "stopped_at": None,
            "last_assistant_message": None,
        })
        rec["type"] = payload.get("agent_type") or payload.get("agentType") or rec["type"]
        tp = payload.get("transcript_path") or payload.get("transcriptPath")
        if tp:
            rec["transcript_path"] = tp
        now = time.time()
        if event == "SubagentStart":
            rec["status"] = "running"
            rec["started_at"] = now
        elif event == "SubagentStop":
            rec["status"] = "stopped"
            rec["stopped_at"] = now
            lam = payload.get("last_assistant_message")
            if lam:
                rec["last_assistant_message"] = str(lam)[:2000]
        return dict(rec)


def get(agent_id: str) -> dict[str, Any] | None:
    """The raw pushed record for an agent (None when nothing ever pushed)."""
    rec = _STATE.get(agent_id)
    return dict(rec) if rec else None


def effective(agent_id: str, poll_status: str | None = None, *,
              freshness_s: float = FRESHNESS_S) -> dict[str, Any]:
    """The arbitrated run-state: pushed fields when fresh, poll floor otherwise.

    Returns ``{source, age_s, phase, permission_mode, current_tool, prompt_id,
    last_event}`` — ``source`` is "push" when the last push is within the
    freshness window, else "poll" (pushed fields still reported, marked stale by
    ``age_s``). ``poll_status`` is the caller's screen-poll status; it is the
    phase used whenever push is not fresh. ``last_event`` is the name of the
    last ingested hook event (observability: which event the freshness rides).
    """
    rec = _STATE.get(agent_id)
    now = time.time()
    if rec:
        age = now - rec["last_push_ts"]
        fresh = age < freshness_s   # strict: freshness_s=0 means never fresh
        return {
            "source": "push" if fresh else "poll",
            "age_s": round(age, 2),
            "phase": rec["phase"] if fresh else poll_status,
            "permission_mode": rec["permission_mode"],
            "current_tool": rec["current_tool"] if fresh else None,
            "prompt_id": rec["prompt_id"],
            "last_event": rec["last_event"],
        }
    return {
        "source": "poll",
        "age_s": None,
        "phase": poll_status,
        "permission_mode": None,
        "current_tool": None,
        "prompt_id": None,
        "last_event": None,
    }


def subagents_live(agent_id: str) -> list[dict[str, Any]]:
    """The hook-fed subagent records for an agent (roster active-vs-quiet signal)."""
    return [dict(r) for r in _SUBAGENTS.get(agent_id, {}).values()]


def drop_agent(agent_id: str) -> None:
    """Forget an agent's run-state + subagent registry (delete/close)."""
    with _lock:
        _STATE.pop(agent_id, None)
        _SUBAGENTS.pop(agent_id, None)
        _SEEN.pop(agent_id, None)
        _DEBUG.pop(agent_id, None)
