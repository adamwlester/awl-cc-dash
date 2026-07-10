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
from typing import Any, Callable

# The type set is OPEN-ENDED, not a closed enum (§7.8) — `type` is stored as a
# string. This tuple is the current vocabulary, not a validation gate.
TYPES = ("permission", "error", "warning", "plan", "decision", "response")

_id_counter = itertools.count(1)
# agent_id -> list[item dict]; items carry resolved=True once handled.
_INBOX: dict[str, list[dict[str, Any]]] = defaultdict(list)

# Optional write-through persist hook (installed by state_store): fired with the
# agent id after any mutation so items land in state/inbox.json (§8.3).
_persist_hook: Callable[[str], None] | None = None


def set_persist_hook(fn: Callable[[str], None] | None) -> None:
    """Install (or clear) the write-through persist hook."""
    global _persist_hook
    _persist_hook = fn


def _notify(agent_id: str) -> None:
    if _persist_hook is not None:
        try:
            _persist_hook(agent_id)
        except Exception:  # pragma: no cover - persistence must never break raises
            pass


def reset() -> None:
    _INBOX.clear()


def restore(agent_id: str, items: list[dict[str, Any]]) -> None:
    """Seed an agent's items from a persisted store (project load) — no hooks.

    Advances the id counter past any restored ``ibx<N>`` ids so new items never
    collide with reloaded ones.
    """
    global _id_counter
    _INBOX[agent_id] = list(items)
    max_n = 0
    for it in items:
        m = re.match(r"^ibx(\d+)$", str(it.get("id") or ""))
        if m:
            max_n = max(max_n, int(m.group(1)))
    if max_n:
        current = next(_id_counter)
        _id_counter = itertools.count(max(current, max_n + 1))


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
                _notify(agent_id)
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
    _notify(agent_id)
    return it


def resolve_item(agent_id: str, item_id: str, answer: Any = None) -> bool:
    for it in _INBOX.get(agent_id, ()):
        if it["id"] == item_id and not it["resolved"]:
            it["resolved"] = True
            it["answer"] = answer
            it["resolved_at"] = datetime.now().isoformat()
            _notify(agent_id)
            return True
    return False


def drop_agent(agent_id: str) -> None:
    """Remove ALL of an agent's items (hard delete, §7.12/§11 #11)."""
    if _INBOX.pop(agent_id, None) is not None:
        _notify(agent_id)


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
    # Account-level subscription/usage caps (§7.2 System cards): the wording the
    # TUI uses for plan limits — widened per §11 #27 (the spike's unmatched leg).
    ("usage_cap", re.compile(
        r"\b(weekly (usage )?limit|usage limit (reached|hit|exceeded)|"
        r"session limit reached|out of (usage|credits)|"
        r"usage credits? (are )?(exhausted|depleted)|requires usage credits|"
        r"credit balance is too low)\b", re.I)),
    # Account auth expiry / logged-out states (§7.2): deterministic wording match
    # — the *reactive* mid-session expiry screen signal is best-effort (§11 #27's
    # honest boundary; it cannot be forced on demand to verify).
    ("auth", re.compile(
        r"\b(auth(entication)? (error|failed|expired)|"
        r"OAuth token (has )?expired|token expired|re-?authenticate|"
        r"please run /login|not logged in|invalid api key)\b", re.I)),
    ("api", re.compile(r"\b(5\d\d|overloaded|api error|internal server error|service unavailable)\b", re.I)),
    ("tool_mcp", re.compile(r"\b(mcp\b.*(fail|error)|tool (execution )?(failed|error)|server failed)", re.I)),
    ("config", re.compile(r"\b(invalid|bad|malformed)\b.*\b(config|configuration|settings)\b", re.I)),
]

# Error subtypes that are ACCOUNT/FLEET-level, not one agent's problem: they
# additionally coalesce into ONE System-sourced fleet-wide card (§7.2).
SYSTEM_WIDE_SUBTYPES = {"rate_limit", "usage_cap", "auth"}


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
