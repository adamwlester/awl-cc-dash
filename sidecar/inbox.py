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
  * **review** — the workflow-approval gate (§11 #23, spike-proven in
    `tests/workflow_approval_probe/`): raised by the PreToolUse(Workflow) hook
    with the parsed script preview (`parse_workflow_script`); the operator's
    approve/reject answer completes the HELD hook response in `main`
    (approve → allow launches, reject → deny aborts).

Pure store + classifiers (process-local, like `eventbus`); hermetically testable.
`reset()` clears it.
"""
from __future__ import annotations

import itertools
import os
import re
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

# The type set is OPEN-ENDED, not a closed enum (§7.8) — `type` is stored as a
# string. This tuple is the current vocabulary, not a validation gate.
TYPES = ("permission", "error", "warning", "plan", "decision", "response", "review")

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


def update_item_data(agent_id: str, item_id: str, updates: dict[str, Any]) -> bool:
    """Merge fields into an OPEN item's ``data`` (e.g. the workflow gate's
    ``timed_out`` flag once its held hook response lapsed). Resolved or missing
    items are left untouched (returns False)."""
    for it in _INBOX.get(agent_id, ()):
        if it["id"] == item_id and not it["resolved"]:
            it["data"].update(updates)
            it["updated_at"] = datetime.now().isoformat()
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
# Workflow-approval gate (§11 #23) — the Review card's preview parser + the
# hold-timeout knob. The gate itself (the held PreToolUse(Workflow) hook and
# the resolve→verdict round-trip) lives in `main`; these stay here as the pure,
# hermetically-testable pieces.
# ---------------------------------------------------------------------------

# How long the workflow PreToolUse hook's HTTP response is HELD awaiting the
# operator's Review-card verdict before giving up and returning {} — the honest
# fallback that hands the gate back to Claude Code's own on-pane
# 'Run a dynamic workflow?' dialog (spike-proven; tests/workflow_approval_probe/).
WORKFLOW_APPROVAL_TIMEOUT_DEFAULT_S = 600.0

# The margin between the sidecar's hold and the agent's hook-CLIENT timeout:
# the client is launched with hold + this margin baked into its --settings
# (BridgeDriver._build_hook_settings), and per-gate the sidecar clamps its hold
# to the launch-time client timeout minus this margin (main._workflow_hold_s) —
# one constant, so the "sidecar always answers before the client gives up"
# invariant survives the knob changing between an agent's launch and a later
# gate (bridge agents outlive sidecar restarts, §9.9).
WORKFLOW_CLIENT_MARGIN_S = 30.0


def workflow_approval_timeout_s() -> float:
    """The workflow-approval hold in seconds (default 600), env-configurable
    via ``AWL_WORKFLOW_APPROVAL_TIMEOUT``. Read at call time so a running
    sidecar honors the knob without a module reload; an unparsable value falls
    back to the default."""
    raw = os.environ.get("AWL_WORKFLOW_APPROVAL_TIMEOUT", "")
    try:
        return float(raw) if raw else WORKFLOW_APPROVAL_TIMEOUT_DEFAULT_S
    except ValueError:
        return WORKFLOW_APPROVAL_TIMEOUT_DEFAULT_S


def _meta_block(script: str) -> str | None:
    """The balanced-brace body of the script's ``export const meta = { ... }``
    declaration, or None when the script declares no meta. A tiny quote-aware
    brace scanner (braces inside '/"/` strings don't count) — regex alone can't
    balance braces. An unterminated block tolerantly yields the tail."""
    m = re.search(r"export\s+const\s+meta\s*=\s*\{", script)
    if not m:
        return None
    start = m.end() - 1  # at the opening brace
    depth = 0
    quote: str | None = None
    j = start
    while j < len(script):
        ch = script[j]
        if quote:
            if ch == "\\":
                j += 1  # skip the escaped character
            elif ch == quote:
                quote = None
        elif ch in "'\"`":
            quote = ch
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return script[start:j + 1]
        j += 1
    return script[start:]


def parse_workflow_script(script: str | None) -> dict[str, Any]:
    """Recover the Review card's preview from a Workflow call's
    ``tool_input.script`` — name / description / phase titles out of the
    script's ``export const meta`` block (the fields the spike proved
    recoverable from the intercepted payload). The field searches are
    word-bounded AND scoped to the meta block, so decoys elsewhere in the
    script (a ``filename:`` before meta, a ``title:`` inside an agent-prompt
    string) or near-miss keys inside it (``subtitle:``) can't pollute the
    approval card; a meta-less script falls back to a best-effort whole-script
    search. Tolerant of ' or " quoting; an empty/missing script yields the
    all-empty shape, never raises."""
    if not script:
        return {"has_meta": False, "name": None, "description": None,
                "phase_titles": []}
    meta = _meta_block(script)
    scope = meta if meta is not None else script

    def _one(field: str) -> str | None:
        m = re.search(rf"\b{field}\s*:\s*(['\"])(.*?)\1", scope, re.S)
        return m.group(2) if m else None

    titles = re.findall(r"\btitle\s*:\s*(['\"])(.*?)\1", scope, re.S)
    return {
        "has_meta": meta is not None,
        "name": _one("name"),
        "description": _one("description"),
        "phase_titles": [t[1] for t in titles],
    }


# Cap on how much of a scriptPath-launched workflow's file the preview reader
# ingests — meta lives at the top of a workflow script; a preview needs no more.
_SCRIPT_PREVIEW_CAP_CHARS = 262_144


def read_script_for_preview(script_path: Any) -> str | None:
    """Best-effort read of a ``scriptPath``-launched Workflow's script text for
    the Review-card preview (§11 #23) — a Workflow call may carry a file path
    instead of the inline ``script`` (both shapes observed by the spike's
    capture server). Tries the path as given, plus its Windows translation when
    it is a WSL ``/mnt/<drive>/`` path (bridge agents run inside WSL2 while the
    sidecar reads from Windows — the Library's file-stored workflows live on
    ``/mnt/c/...``). Returns None — never raises — when the file is
    unreachable; the card then still shows the raw path."""
    if not script_path or not isinstance(script_path, str):
        return None
    candidates = [script_path]
    m = re.match(r"^/mnt/([a-zA-Z])/(.+)$", script_path)
    if m:
        candidates.append(f"{m.group(1).upper()}:/{m.group(2)}")
    for cand in candidates:
        try:
            p = Path(cand)
            if p.is_file():
                return p.read_text(encoding="utf-8", errors="replace")[
                    :_SCRIPT_PREVIEW_CAP_CHARS]
        except OSError:  # pragma: no cover - unreadable-path shapes vary by OS
            continue
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
