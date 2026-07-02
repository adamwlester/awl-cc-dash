"""Inbox (the "needs you" surface) + lifecycle-cap derivation — store + classifiers.

Five typed sections raised over two mechanisms:
  * **permission** — screen-anchored (lives on SessionState.pending_permission;
    surfaced into the merged inbox view by `main`).
  * **error** — best-effort: structural (tmux/session gone), a no-output stall
    watchdog, and text **pattern-match** (`classify_error`). **Sticky** (persists
    until Retry/Dismiss).
  * **warning** — synthesized from the lifecycle-cap poll-loop (`cap_warnings`):
    max-turns + context-% crossings (deterministic, local). The rate/usage-cap
    subtype is gated on settings/account usage data and is not derived here.
  * **plan** / **decision** — screen-blind; raised via the PreToolUse hook
    channel (the agent's ExitPlanMode / AskUserQuestion tool calls are visible to
    hooks). The detect→answer→resume round-trip lives in `main`; this module holds
    the card + the pending answer slot.

Pure store + classifiers (process-local, like `eventbus`); hermetically testable.
`reset()` clears it.
"""
from __future__ import annotations

import itertools
import re
from collections import defaultdict
from datetime import datetime
from typing import Any

TYPES = ("permission", "error", "warning", "plan", "decision")

_id_counter = itertools.count(1)
# agent_id -> list[item dict]; items carry resolved=True once handled.
_INBOX: dict[str, list[dict[str, Any]]] = defaultdict(list)


def reset() -> None:
    _INBOX.clear()


def raise_item(agent_id: str, itype: str, data: dict[str, Any] | None = None, *,
               sticky: bool = False, item_id: str | None = None,
               dedup_key: str | None = None) -> dict[str, Any]:
    """Raise (or, with a matching `dedup_key`, update) an open inbox item.

    `dedup_key` keeps a re-detected error/warning from piling up duplicates — the
    existing open item with the same key is updated in place instead.
    """
    if dedup_key is not None:
        for it in _INBOX.get(agent_id, ()):
            if not it.get("resolved") and it.get("dedup_key") == dedup_key:
                it["data"] = data or {}
                it["updated_at"] = datetime.now().isoformat()
                return it
    it = {
        "id": item_id or f"ibx{next(_id_counter)}",
        "agent_id": agent_id,
        "type": itype,
        "data": data or {},
        "sticky": sticky,
        "dedup_key": dedup_key,
        "resolved": False,
        "answer": None,
        "created_at": datetime.now().isoformat(),
    }
    _INBOX[agent_id].append(it)
    return it


def resolve_item(agent_id: str, item_id: str, answer: Any = None) -> bool:
    for it in _INBOX.get(agent_id, ()):
        if it["id"] == item_id and not it["resolved"]:
            it["resolved"] = True
            it["answer"] = answer
            it["resolved_at"] = datetime.now().isoformat()
            return True
    return False


def get_item(agent_id: str, item_id: str) -> dict[str, Any] | None:
    for it in _INBOX.get(agent_id, ()):
        if it["id"] == item_id:
            return it
    return None


def items_for(agent_id: str, include_resolved: bool = False) -> list[dict[str, Any]]:
    return [i for i in _INBOX.get(agent_id, ())
            if include_resolved or not i["resolved"]]


def all_open() -> dict[str, list[dict[str, Any]]]:
    """Open items grouped by agent (agents with no open items are omitted)."""
    out: dict[str, list[dict[str, Any]]] = {}
    for agent_id in _INBOX:
        opens = items_for(agent_id)
        if opens:
            out[agent_id] = opens
    return out


def fleet_badge() -> int:
    """Fleet badge: the number of agents with >=1 open request (any type)."""
    return sum(1 for agent_id in _INBOX if items_for(agent_id))


# ---------------------------------------------------------------------------
# Error classifier — best-effort text pattern-match (the catalog grows
# iteratively; the architecture is fixed). Returns {subtype, message} or None.
# ---------------------------------------------------------------------------

_ERROR_PATTERNS = [
    ("rate_limit", re.compile(r"\b(429|rate[ _-]?limit|quota exceeded|too many requests)\b", re.I)),
    ("api", re.compile(r"\b(5\d\d|overloaded|api error|internal server error|service unavailable)\b", re.I)),
    ("tool_mcp", re.compile(r"\b(mcp\b.*(fail|error)|tool (execution )?(failed|error)|server failed)", re.I)),
    ("config", re.compile(r"\b(invalid|bad|malformed)\b.*\b(config|configuration|settings)\b", re.I)),
]


def classify_error(text: str | None) -> dict[str, Any] | None:
    if not text:
        return None
    for subtype, pat in _ERROR_PATTERNS:
        if pat.search(text):
            return {"subtype": subtype, "message": text.strip()[:500]}
    return None


# ---------------------------------------------------------------------------
# Lifecycle-cap crossing -> Warning subtypes (notify-only; the run continues until
# the user chooses Continue / Raise cap / Stop). Deterministic + local.
# ---------------------------------------------------------------------------

def cap_warnings(*, turns: int | None, max_turns: int | None,
                 context_pct: float | None, max_context_pct: float | None
                 ) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    if max_turns is not None and turns is not None and turns >= max_turns:
        out.append({"subtype": "max_turns", "value": turns, "cap": max_turns})
    if max_context_pct is not None and context_pct is not None and \
            context_pct >= max_context_pct:
        out.append({"subtype": "context_pct", "value": context_pct,
                    "cap": max_context_pct})
    return out
